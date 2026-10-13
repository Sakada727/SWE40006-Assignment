from sqlalchemy import func

from app import app
from models import Task, User, db

with app.app_context():
    print("users:", db.session.execute(db.select(func.count()).select_from(User)).scalar())
    print("tasks:", db.session.execute(db.select(func.count()).select_from(Task)).scalar())

    print("\nUsers:")
    for u in db.session.execute(db.select(User).order_by(User.id)).scalars():
        print(" ", u.id, u.username)

    print("\nTasks:")
    for t in db.session.execute(db.select(Task).order_by(Task.id)).scalars():
        print(" ", t.to_dict())