from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user

from config import Config, normalise_database_url
from models import Task, User, db, validate_title


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)  # overrides, e.g. from tests
    app.config["SQLALCHEMY_DATABASE_URI"] = normalise_database_url(
        app.config["SQLALCHEMY_DATABASE_URI"]
    )
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = Config.SECRET_KEY

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"      # visitors who are not logged in are sent to /login
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        # API clients get a JSON 401; browser pages are sent to the login form.
        if request.path.startswith("/api/"):
            return jsonify({"error": "Login required."}), 401
        return redirect(url_for("login", next=request.path))

    def ensure_tables():  # create the tables the first time they are needed
        if not app.config.get("_TABLES_READY"):
            db.create_all()
            app.config["_TABLES_READY"] = True

    @app.before_request   # runs before every request for pages that use the database
    def prepare_database():
        if request.path.startswith(("/tasks", "/api/", "/login", "/register", "/logout")):
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

    @app.route("/")
    def index():
        return "Hello, world!"

    @app.route("/health")
    def health():
        return {"status": "ok"}

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
        return redirect(url_for("tasks_page"))

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
        return redirect(url_for("tasks_page"))

    @app.route("/logout", methods=["POST"])
    def logout():
        logout_user()
        return redirect(url_for("login"))

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

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)