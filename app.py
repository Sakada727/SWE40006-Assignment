import os
import threading

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from models import Link, Task, User, db, generate_short_code, validate_title, validate_url


def normalise_database_url(url):
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


def create_app(config=None):
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if config:
        app.config.update(config)
    app.config["SQLALCHEMY_DATABASE_URI"] = normalise_database_url(
        app.config["SQLALCHEMY_DATABASE_URI"]
    )
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    # The commit this image was built from (baked in by the Dockerfile), so every
    # environment can report exactly which version it is running.
    app.config.setdefault("GIT_SHA", os.environ.get("GIT_SHA", "dev"))

    db.init_app(app)

    @app.context_processor
    def inject_version():
        return {"app_version": app.config["GIT_SHA"][:7]}

    login_manager = LoginManager()
    login_manager.login_view = "login"      
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        
        if request.path.startswith("/api/"):
            return jsonify({"error": "Login required."}), 401
        return redirect(url_for("login", next=request.path))

    tables_lock = threading.Lock()

    def ensure_tables():  # create the tables the first time they are needed
        if app.config.get("_TABLES_READY"):
            return
        with tables_lock:  # gunicorn runs several threads; only one should create tables
            if app.config.get("_TABLES_READY"):
                return
            try:
                db.create_all()
            except SQLAlchemyError:
                # Another gunicorn worker created the same table a moment earlier.
                # Its CREATE has committed by now, so a second pass finds the tables.
                db.session.rollback()
                db.create_all()
            app.config["_TABLES_READY"] = True

    @app.before_request   # runs before every request for pages that use the database
    def prepare_database():
        if request.path == "/" or request.path.startswith(
            ("/tasks", "/links", "/s/", "/api/", "/login", "/register", "/logout")
        ):
            ensure_tables()


    def all_tasks():
        """Only the logged-in user's own tasks."""
        return db.session.execute(
            db.select(Task).filter_by(user_id=current_user.id).order_by(Task.id)
        ).scalars().all()

    def own_task_or_404(task_id):
        """Look a task up by id, but only if it belongs to the logged-in user."""
        task = db.session.execute(
            db.select(Task).filter_by(id=task_id, user_id=current_user.id)
        ).scalar_one_or_none()
        if task is None:
            abort(404)
        return task

    def my_links():
        """Only the logged-in user's own short links, newest first."""
        return db.session.execute(
            db.select(Link).filter_by(user_id=current_user.id).order_by(Link.id.desc())
        ).scalars().all()

    def own_link_or_404(link_id):
        link = db.session.execute(
            db.select(Link).filter_by(id=link_id, user_id=current_user.id)
        ).scalar_one_or_none()
        if link is None:
            abort(404)
        return link

    def create_link(url):
        """Save a new short link for the current user, picking a random unused code."""
        for _ in range(10):
            code = generate_short_code()
            taken = db.session.execute(
                db.select(Link).filter_by(short_code=code)
            ).scalar_one_or_none()
            if taken is None:
                link = Link(original_url=url, short_code=code, user_id=current_user.id)
                db.session.add(link)
                db.session.commit()
                return link
        abort(500)   

    def link_json(link):
        data = link.to_dict()
        data["short_url"] = url_for("follow_link", code=link.short_code, _external=True)
        return data

    

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/health")
    def health():
        """Used by Docker, the deploy health check and the smoke test.

        It runs a real query, so a deploy whose container cannot reach its
        database fails the health check and is rolled back.
        """
        body = {"version": app.config["GIT_SHA"]}
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            app.logger.exception("Health check could not reach the database")
            db.session.rollback()
            return jsonify(status="error", database="unreachable", **body), 503
        return jsonify(status="ok", database="ok", **body)

    

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET":
            return render_template("register.html", error=None)
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or len(username) > 50 or len(password) < 8:
            error = "Username is required (max 50 characters) and the password needs at least 8 characters."
            return render_template("register.html", error=error), 400
        taken = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
        if taken is not None:
            return render_template("register.html", error="That username is already taken."), 400
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("links_page"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template("login.html", error=None)
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none()
        if user is None or not user.check_password(password):
            return render_template("login.html", error="Invalid username or password."), 401
        login_user(user)
        return redirect(url_for("links_page"))

    @app.route("/logout", methods=["POST"])
    def logout():
        logout_user()
        return redirect(url_for("login"))

    # ---------- tasks ----------

    @app.route("/tasks", methods=["GET"])
    @login_required
    def tasks_page():
        return render_template("tasks.html", tasks=all_tasks(), error=None)

    @app.route("/tasks", methods=["POST"])
    @login_required
    def add_task_form():
        try:
            title = validate_title(request.form.get("title"))
        except ValueError as exc:
            return render_template("tasks.html", tasks=all_tasks(), error=str(exc)), 400
        db.session.add(Task(title=title, user_id=current_user.id))
        db.session.commit()
        return redirect(url_for("tasks_page"))

    @app.route("/tasks/<int:task_id>/complete", methods=["POST"])
    @login_required
    def complete_task_form(task_id):
        task = own_task_or_404(task_id)
        task.done = True
        db.session.commit()
        return redirect(url_for("tasks_page"))

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    @login_required
    def delete_task_form(task_id):
        task = own_task_or_404(task_id)
        db.session.delete(task)
        db.session.commit()
        return redirect(url_for("tasks_page"))

    @app.route("/api/tasks", methods=["GET"])
    @login_required
    def api_list_tasks():
        return jsonify([task.to_dict() for task in all_tasks()])

    @app.route("/api/tasks", methods=["POST"])
    @login_required
    def api_create_task():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        try:
            title = validate_title(data.get("title"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        task = Task(title=title, user_id=current_user.id)
        db.session.add(task)
        db.session.commit()
        return jsonify(task.to_dict()), 201

    

    @app.route("/links", methods=["GET"])
    @login_required
    def links_page():
        return render_template("links.html", links=my_links(), error=None)

    @app.route("/links", methods=["POST"])
    @login_required
    def add_link_form():
        try:
            url = validate_url(request.form.get("url"))
        except ValueError as exc:
            return render_template("links.html", links=my_links(), error=str(exc)), 400
        create_link(url)
        return redirect(url_for("links_page"))

    @app.route("/links/<int:link_id>/delete", methods=["POST"])
    @login_required
    def delete_link_form(link_id):
        link = own_link_or_404(link_id)
        db.session.delete(link)
        db.session.commit()
        return redirect(url_for("links_page"))

    @app.route("/s/<code>")
    def follow_link(code):
        """Public: anyone with the short link is redirected to the original address."""
        link = db.session.execute(
            db.select(Link).filter_by(short_code=code)
        ).scalar_one_or_none()
        if link is None:
            abort(404)
     
        db.session.execute(
            db.update(Link).where(Link.id == link.id).values(clicks=Link.clicks + 1)
        )
        db.session.commit()
        return redirect(link.original_url, code=302)   # 302, so browsers do not cache it and skip the counter

    @app.route("/api/links", methods=["GET"])
    @login_required
    def api_list_links():
        return jsonify([link_json(link) for link in my_links()])

    @app.route("/api/links", methods=["POST"])
    @login_required
    def api_create_link():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        try:
            url = validate_url(data.get("url"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(link_json(create_link(url))), 201

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)