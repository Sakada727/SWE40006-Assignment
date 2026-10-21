import pytest

from models import Task, User, db

pytestmark = pytest.mark.integration      # labels every test in this file


def register(client, username="alice", password="password123"):
    return client.post("/register", data={"username": username, "password": password})


@pytest.fixture
def logged_in_client(db_app):
    """A client that has registered (and is therefore logged in) as 'alice'."""
    client = db_app.test_client()
    register(client)
    return client


def stored_tasks(application):
    """Read the rows straight from the database, bypassing the web layer."""
    with application.app_context():
        db.session.remove()
        return [
            (task.title, task.done)
            for task in db.session.execute(db.select(Task).order_by(Task.id)).scalars()
        ]


def test_app_is_connected_to_postgresql(db_app):
    with db_app.app_context():
        assert db.engine.dialect.name == "postgresql"


def test_task_created_through_the_api_is_stored(db_app, logged_in_client):
    response = logged_in_client.post("/api/tasks", json={"title": "Deploy to production"})
    assert response.status_code == 201
    assert stored_tasks(db_app) == [("Deploy to production", False)]


def test_completing_a_task_updates_the_stored_row(db_app, logged_in_client):
    task_id = logged_in_client.post("/api/tasks", json={"title": "Run tests"}).get_json()["id"]
    logged_in_client.post(f"/tasks/{task_id}/complete")
    assert stored_tasks(db_app) == [("Run tests", True)]


def test_registered_user_is_stored_with_a_hashed_password(db_app, logged_in_client):
    with db_app.app_context():
        user = db.session.execute(db.select(User)).scalar_one()
        assert user.username == "alice"
        assert user.password_hash != "password123"      # never stored as plain text
        assert user.check_password("password123")


def test_task_is_stored_against_its_owner(db_app):
    alice = db_app.test_client()
    bob = db_app.test_client()
    register(alice, "alice")
    register(bob, "bob")

    alice.post("/api/tasks", json={"title": "Alice task"})

    with db_app.app_context():
        task = db.session.execute(db.select(Task)).scalar_one()
        owner = db.session.get(User, task.user_id)
        assert owner.username == "alice"                 # the foreign key points at the right user
        assert bob.get("/api/tasks").get_json() == []    # and the other user sees nothing