import os
from datetime import date

# Utilise une base temporaire avant d'importer l'application.
os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app
from models import db
from models.user import User
from services.security import create_token


@pytest.fixture
def app():
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "cle-test-bloops",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })

    with application.app_context():
        db.drop_all()
        db.create_all()

        yield application

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def birth_date_for_age(age):
    today = date.today()
    return date(today.year - age, today.month, today.day)


def create_test_user(age):
    user = User(
        username=f"testeur{age}",
        email=f"testeur{age}@example.com",
        password_hash="hash-de-test",
        birth_date=birth_date_for_age(age),
        guardian_email=(
            "parent@example.com" if age < 15 else None
        ),
        account_status=(
            "pending_parent" if age < 15 else "pending_email"
        ),
        is_active=False,
    )

    db.session.add(user)
    db.session.commit()

    return user


def make_token(app, purpose, user_id):
    return create_token(
        app.config["SECRET_KEY"],
        purpose,
        user_id
    )


def test_adulte_active_apres_verification_email(app, client):
    with app.app_context():
        user = create_test_user(16)
        token = make_token(app, "email_verification", user.id)
        user_id = user.id

    response = client.post(f"/verifier-email/{token}")

    assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, user_id)

        assert user.email_verified_at is not None
        assert user.is_active is True
        assert user.account_status == "active"


def test_mineur_attend_consentement_parent(app, client):
    with app.app_context():
        user = create_test_user(13)
        token = make_token(app, "email_verification", user.id)
        user_id = user.id

    client.post(f"/verifier-email/{token}")

    with app.app_context():
        user = db.session.get(User, user_id)

        assert user.email_verified_at is not None
        assert user.guardian_consent_at is None
        assert user.is_active is False


def test_mineur_attend_verification_email(app, client):
    with app.app_context():
        user = create_test_user(13)
        token = make_token(app, "parent_consent", user.id)
        user_id = user.id

    client.post(f"/consentement-parent/{token}")

    with app.app_context():
        user = db.session.get(User, user_id)

        assert user.guardian_consent_at is not None
        assert user.email_verified_at is None
        assert user.is_active is False


def test_mineur_active_apres_deux_confirmations(app, client):
    with app.app_context():
        user = create_test_user(13)

        email_token = make_token(
            app, "email_verification", user.id
        )
        parent_token = make_token(
            app, "parent_consent", user.id
        )

        user_id = user.id

    client.post(f"/verifier-email/{email_token}")
    client.post(f"/consentement-parent/{parent_token}")

    with app.app_context():
        user = db.session.get(User, user_id)

        assert user.email_verified_at is not None
        assert user.guardian_consent_at is not None
        assert user.is_active is True
        assert user.account_status == "active"
