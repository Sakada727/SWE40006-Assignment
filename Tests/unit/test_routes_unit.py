import pytest


@pytest.fixture
def client(flask_app):
    """A test client that is already registered and logged in as 'alice'."""
    logged_in = flask_app.test_client()
    logged_in.post("/register", data={"username": "alice", "password": "password123"})
    return logged_in


def test_api_lists_no_tasks_at_start(client):
    response = client.get("/api/tasks")
    assert response.status_code == 200
    assert response.get_json() == []


def test_api_creates_a_task(client):
    response = client.post("/api/tasks", json={"title": "Write report"})
    assert response.status_code == 201
    body = response.get_json()
    assert body["title"] == "Write report"
    assert body["done"] is False


def test_api_rejects_a_blank_title(client):
    response = client.post("/api/tasks", json={"title": "   "})
    assert response.status_code == 400
    assert "must not be blank" in response.get_json()["error"]


def test_form_adds_a_task_to_the_page(client):
    response = client.post("/tasks", data={"title": "Buy milk"}, follow_redirects=True)
    assert response.status_code == 200          # redirected back to the /tasks list page
    assert b"Buy milk" in response.data


def test_form_blank_title_shows_an_error(client):
    response = client.post("/tasks", data={"title": "   "})
    assert response.status_code == 400
    assert b"must not be blank" in response.data


def test_complete_marks_a_task_done(client):
    client.post("/api/tasks", json={"title": "Ship release"})            # creates task number 1
    response = client.post("/tasks/1/complete", follow_redirects=True)   # each test starts with an empty database, so the first task gets id 1
    assert b"Completed" in response.data


def test_complete_unknown_task_returns_404(client):
    response = client.post("/tasks/999/complete")
    assert response.status_code == 404          # no task has that id


def test_delete_removes_a_task(client):
    client.post("/api/tasks", json={"title": "Temporary task"})
    response = client.post("/tasks/1/delete", follow_redirects=True)
    assert response.status_code == 200
    assert b"Temporary task" not in response.data
    assert client.get("/api/tasks").get_json() == []


def test_delete_unknown_task_returns_404(client):
    response = client.post("/tasks/999/delete")
    assert response.status_code == 404