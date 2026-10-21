import os

import pytest

from app import create_app
from models import db


@pytest.fixture
def database_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set, so no real database is available.")
    database_name = url.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in database_name.lower():
        # These tests drop every table, so never point them at real data.
        pytest.fail(f"Refusing to run: database name '{database_name}' does not contain 'test'.")
    return url


@pytest.fixture
def db_app(database_url):
    application = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": database_url})
    with application.app_context():
        db.drop_all()          # start every test from an empty database
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def db_client(db_app):
    return db_app.test_client()