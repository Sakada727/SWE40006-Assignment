import pytest

from models import Task, db

pytestmark = pytest.mark.integration      # labels every test in this file


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


def test_task_created_through_the_api_is_stored(db_app, db_client):
    response = db_client.post("/api/tasks", json={"title": "Deploy to production"})
    assert response.status_code == 201                       
    assert stored_tasks(db_app) == [("Deploy to production", False)]


def test_completing_a_task_updates_the_stored_row(db_app, db_client):
    task_id = db_client.post("/api/tasks", json={"title": "Run tests"}).get_json()["id"] 
    db_client.post(f"/tasks/{task_id}/complete")
    assert stored_tasks(db_app) == [("Run tests", True)]       