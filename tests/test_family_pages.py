import os
from datetime import date

os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app
from models import db
from models.user import User


@pytest.fixture
def app():
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "cle-test-bloops",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def create_user(age):
    today = date.today()
    birth_date = date(
        today.year - age,
        today.month,
        min(today.day, 28)
    )

    user = User(
        username=f"testeur{age}",
        email=f"testeur{age}@example.com",
        password_hash="hash-test",
        birth_date=birth_date,
        is_active=True,
        account_status="active"
    )

    db.session.add(user)
    db.session.commit()
    return user


def test_espace_famille_redirige_si_non_connecte(client):
    response = client.get("/famille/espace")

    assert response.status_code == 302
    assert "/connexion" in response.location


def test_adulte_peut_voir_creation_groupe(app, client):
    with app.app_context():
        user = create_user(30)
        user_id = user.id

    with client.session_transaction() as session:
        session["user_id"] = user_id

    response = client.get("/famille/espace")

    assert response.status_code == 200
    assert b"Mon espace Famille" in response.data
    assert b"create-family-form" in response.data


def test_mineur_ne_voit_pas_creation_groupe(app, client):
    with app.app_context():
        user = create_user(13)
        user_id = user.id

    with client.session_transaction() as session:
        session["user_id"] = user_id

    response = client.get("/famille/espace")

    assert response.status_code == 200
    assert b"create-family-form" not in response.data
