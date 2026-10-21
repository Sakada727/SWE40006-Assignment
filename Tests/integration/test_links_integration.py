import threading

import pytest
from sqlalchemy.exc import IntegrityError

from models import Link, User, db

pytestmark = pytest.mark.integration      # labels every test in this file


def register(client, username="alice", password="password123"):
    return client.post("/register", data={"username": username, "password": password})


@pytest.fixture
def alice(db_app):
    client = db_app.test_client()
    register(client)
    return client


def stored_links(application):
    """Read the rows straight from PostgreSQL, bypassing the web layer."""
    with application.app_context():
        db.session.remove()
        return db.session.execute(db.select(Link).order_by(Link.id)).scalars().all()


def test_link_created_through_the_api_is_stored(db_app, alice):
    response = alice.post("/api/links", json={"url": "https://www.swinburne.edu.au"})
    assert response.status_code == 201
    links = stored_links(db_app)
    assert [(link.original_url, link.short_code, link.clicks) for link in links] == [
        ("https://www.swinburne.edu.au", response.get_json()["short_code"], 0)
    ]


def test_following_a_link_updates_the_click_count_in_the_database(db_app, alice):
    code = alice.post("/api/links", json={"url": "https://example.com"}).get_json()["short_code"]
    visitor = db_app.test_client()
    for _ in range(3):
        assert visitor.get(f"/s/{code}").status_code == 302
    assert stored_links(db_app)[0].clicks == 3


def test_concurrent_clicks_are_all_counted(db_app, alice):
    """The click counter is a single UPDATE ... SET clicks = clicks + 1, so
    PostgreSQL must not lose any of several simultaneous visits."""
    code = alice.post("/api/links", json={"url": "https://example.com"}).get_json()["short_code"]

    def visit():
        db_app.test_client().get(f"/s/{code}")

    threads = [threading.Thread(target=visit) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert stored_links(db_app)[0].clicks == 10


def test_database_rejects_a_duplicate_short_code(db_app, alice):
    alice.post("/api/links", json={"url": "https://example.com/first"})
    with db_app.app_context():
        existing = db.session.execute(db.select(Link)).scalar_one()
        owner = db.session.execute(db.select(User)).scalar_one()
        db.session.add(Link(original_url="https://example.com/second",
                            short_code=existing.short_code, user_id=owner.id))
        with pytest.raises(IntegrityError):    # enforced by the UNIQUE constraint itself
            db.session.commit()
        db.session.rollback()


def test_deleting_a_link_removes_the_row(db_app, alice):
    link_id = alice.post("/api/links", json={"url": "https://example.com"}).get_json()["id"]
    alice.post(f"/links/{link_id}/delete")
    assert stored_links(db_app) == []
