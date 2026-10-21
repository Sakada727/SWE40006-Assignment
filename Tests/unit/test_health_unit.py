from sqlalchemy.exc import OperationalError

from app import create_app
from models import db


def test_health_reports_database_and_version(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert "version" in body


def test_health_reports_the_commit_it_was_built_from():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                      "GIT_SHA": "abc1234def5678"})
    body = app.test_client().get("/health").get_json()
    assert body["version"] == "abc1234def5678"
    with app.app_context():
        db.engine.dispose()


def test_health_fails_when_the_database_is_unreachable(client, monkeypatch):
    def broken(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db.session, "execute", broken)
    response = client.get("/health")
    assert response.status_code == 503             # so a bad deploy is rolled back
    assert response.get_json()["database"] == "unreachable"


def test_home_page_links_to_login_and_shows_version(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'id="go-login"' in response.data
    assert b'id="app-version"' in response.data


def test_home_page_offers_links_page_once_logged_in(client):
    client.post("/register", data={"username": "alice", "password": "password123"})
    response = client.get("/")
    assert b'id="go-links"' in response.data
