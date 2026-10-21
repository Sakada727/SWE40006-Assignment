import pytest

from app import create_app
from models import db


@pytest.fixture
def flask_app():
    # A brand-new app using a throwaway in-memory database for each test
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()           # build the empty tasks table
        yield app                 # the test runs here
        db.session.remove()       # cleanup after the test
        db.drop_all()
        db.engine.dispose()       # close the in-memory database connection


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()   # a fake browser that talks to the app