import pytest

from app import create_app
from models import User, db


@pytest.fixture
def two_user_app():
    """A fresh app whose app context is NOT left open, so separate clients stay isolated."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def register(client, username="alice", password="password123"):
    return client.post("/register", data={"username": username, "password": password})


def login(client, username="alice", password="password123"):
    return client.post("/login", data={"username": username, "password": password})




def test_register_creates_account_and_logs_in(client):
    response = register(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert client.get("/tasks").status_code == 200


def test_register_rejects_duplicate_username(client):
    register(client)
    other = register(client.application.test_client())
    assert other.status_code == 400
    assert b"already taken" in other.data


def test_register_rejects_short_password(client):
    response = register(client, password="short")
    assert response.status_code == 400


def test_password_is_stored_hashed(client, flask_app):
    register(client)
    with flask_app.app_context():
        user = db.session.execute(db.select(User).filter_by(username="alice")).scalar_one()
        assert user.password_hash != "password123"
        assert user.check_password("password123")




def test_login_succeeds_with_correct_password(client):
    register(client)
    client.post("/logout")
    response = login(client)
    assert response.status_code == 302
    assert client.get("/tasks").status_code == 200


def test_login_wrong_password_is_rejected(client):
    register(client)
    client.post("/logout")
    response = login(client, password="wrong-password")
    assert response.status_code == 401
    assert b"Invalid username or password." in response.data


def test_login_unknown_user_gives_same_error(client):
    response = login(client, username="nobody")
    assert response.status_code == 401
    assert b"Invalid username or password." in response.data


def test_logout_blocks_access_again(client):
    register(client)
    client.post("/logout")
    response = client.get("/tasks")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]




def test_tasks_page_requires_login(client):
    response = client.get("/tasks")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_api_requires_login(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/tasks", json={"title": "x"}).status_code == 401




def test_users_only_see_their_own_tasks(two_user_app):
    alice = two_user_app.test_client()
    bob = two_user_app.test_client()

    register(alice, "alice")
    alice.post("/api/tasks", json={"title": "Alice task"})

    register(bob, "bob")
    assert bob.get("/api/tasks").get_json() == []
    bob.post("/api/tasks", json={"title": "Bob task"})

    alice_titles = [t["title"] for t in alice.get("/api/tasks").get_json()]
    bob_titles = [t["title"] for t in bob.get("/api/tasks").get_json()]
    assert alice_titles == ["Alice task"]
    assert bob_titles == ["Bob task"]


def test_user_cannot_delete_or_complete_another_users_task(two_user_app):
    alice = two_user_app.test_client()
    bob = two_user_app.test_client()

    register(alice, "alice")
    task_id = alice.post("/api/tasks", json={"title": "Alice task"}).get_json()["id"]

    register(bob, "bob")
    assert bob.post(f"/tasks/{task_id}/delete").status_code == 404
    assert bob.post(f"/tasks/{task_id}/complete").status_code == 404

    remaining = alice.get("/api/tasks").get_json()
    assert len(remaining) == 1 and remaining[0]["done"] is False


# ---- returning to the page that asked for a login ----

def test_login_returns_to_the_page_that_required_it(client):
    register(client)
    client.post("/logout")
    assert client.get("/tasks").headers["Location"].endswith("/login?next=/tasks")
    response = client.post("/login?next=/tasks", data={"username": "alice", "password": "password123"})
    assert response.headers["Location"] == "/tasks"


@pytest.mark.parametrize("target", ["//evil.example", "https://evil.example", "/\\evil.example", "tasks"])
def test_login_never_redirects_off_the_site(client, target):
    register(client)
    client.post("/logout")
    response = client.post("/login", query_string={"next": target},
                           data={"username": "alice", "password": "password123"})
    assert response.headers["Location"] == "/links"


def test_login_cookie_is_not_sent_with_cross_site_posts(client):
    response = register(client)
    assert "SameSite=Lax" in response.headers["Set-Cookie"]
