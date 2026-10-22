"""Print what is stored in the database the app is configured to use (DATABASE_URL).

Run it on a server or locally:  python dbtestcheck.py
"""
from sqlalchemy import func

from app import app
from models import Link, Task, User, db

with app.app_context():
    for name, model in (("users", User), ("tasks", Task), ("links", Link)):
        print(f"{name}:", db.session.execute(db.select(func.count()).select_from(model)).scalar())

    print("\nUsers:")
    for u in db.session.execute(db.select(User).order_by(User.id)).scalars():
        print(" ", u.id, u.username)

    print("\nTasks:")
    for t in db.session.execute(db.select(Task).order_by(Task.id)).scalars():
        print(" ", t.to_dict())

    print("\nLinks:")
    for link in db.session.execute(db.select(Link).order_by(Link.id)).scalars():
        print(" ", link.to_dict())
