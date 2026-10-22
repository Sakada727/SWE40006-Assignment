import pytest

from app import create_app
from models import db


@pytest.fixture
def flask_app():
    
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()           
        yield app                 
        db.session.remove()       
        db.drop_all()


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()  