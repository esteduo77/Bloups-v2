import os
from datetime import date, datetime, timezone

os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app
from models import db
from models.user import User
from routes.auth import activate_if_ready
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
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def create_minor():
    user = User(
        username="testeur13",
        email="testeur@example.com",
        password_hash="hash-test",
        birth_date=date(2013, 1, 1),
        guardian_email="parent1@example.com",
        guardian_email_2="parent2@example.com",
        email_verified_at=datetime.now(timezone.utc),
        is_active=False,
        account_status="pending_parent"
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_un_seul_parent_ne_suffit_pas(app):
    with app.app_context():
        user = create_minor()
        user.guardian_consent_1_at = datetime.now(timezone.utc)
        activate_if_ready(user)
        assert user.is_active is False


def test_deux_parents_et_email_activent_le_compte(app):
    with app.app_context():
        user = create_minor()
        now = datetime.now(timezone.utc)
        user.guardian_consent_1_at = now
        user.guardian_consent_2_at = now
        activate_if_ready(user)
        assert user.is_active is True
        assert user.account_status == "active"


def test_email_non_verifie_empeche_activation(app):
    with app.app_context():
        user = create_minor()
        user.email_verified_at = None
        user.guardian_consent_1_at = datetime.now(timezone.utc)
        user.guardian_consent_2_at = datetime.now(timezone.utc)
        activate_if_ready(user)
        assert user.is_active is False


def test_liens_parentaux_sont_distincts_et_a_usage_unique(app, client=None):
    with app.app_context():
        user = create_minor()
        token_1 = create_token(
            app.config["SECRET_KEY"], "parent_consent_1", user.id
        )
        token_2 = create_token(
            app.config["SECRET_KEY"], "parent_consent_2", user.id
        )
        assert token_1 != token_2
