import os
from datetime import date, datetime, timezone

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
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def birth_date_for_age(age):
    today = date.today()
    try:
        return date(today.year - age, today.month, today.day)
    except ValueError:
        return date(today.year - age, today.month, today.day - 1)


def create_test_user(age, second_guardian=True):
    user = User(
        username=f"testeur{age}",
        email=f"testeur{age}@example.com",
        password_hash="hash-de-test",
        birth_date=birth_date_for_age(age),
        guardian_email="parent1@example.com" if age < 15 else None,
        guardian_email_2=(
            "parent2@example.com"
            if age < 15 and second_guardian else None
        ),
        account_status="pending_parent" if age < 15 else "pending_email",
        is_active=False,
    )
    db.session.add(user)
    db.session.commit()
    return user


def make_token(app, purpose, user_id):
    return create_token(app.config["SECRET_KEY"], purpose, user_id)


def test_utilisateur_15_ans_ou_plus_actif_apres_verification(app, client):
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


def test_mineur_reste_en_attente_apres_verification_email(app, client):
    with app.app_context():
        user = create_test_user(13)
        token = make_token(app, "email_verification", user.id)
        user_id = user.id

    client.post(f"/verifier-email/{token}")

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.email_verified_at is not None
        assert user.guardian_consent_1_at is None
        assert user.guardian_consent_2_at is None
        assert user.is_active is False


def test_un_seul_consentement_suffit_avec_email_verifie(app, client):
    with app.app_context():
        user = create_test_user(13, second_guardian=False)
        user.email_verified_at = datetime.now(timezone.utc)
        db.session.commit()
        token = make_token(app, "parent_consent_1", user.id)
        user_id = user.id

    response = client.post(
        f"/consentement-parent/1/{token}",
        data={"decision": "approved"}
    )
    assert response.status_code == 200

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.guardian_consent_1_at is not None
        assert user.guardian_consent_2_at is None
        assert user.is_active is True
        assert user.account_status == "active"


def test_deuxieme_consentement_refuse_sans_deuxieme_adresse(app, client):
    with app.app_context():
        user = create_test_user(13, second_guardian=False)
        token = make_token(app, "parent_consent_2", user.id)

    response = client.post(
        f"/consentement-parent/2/{token}",
        data={"decision": "approved"}
    )
    assert response.status_code == 403


def test_deux_consentements_et_email_activent_le_mineur(app, client):
    with app.app_context():
        user = create_test_user(13)
        user.email_verified_at = datetime.now(timezone.utc)
        db.session.commit()
        user_id = user.id
        token_1 = make_token(app, "parent_consent_1", user.id)
        token_2 = make_token(app, "parent_consent_2", user.id)

    response_1 = client.post(
        f"/consentement-parent/1/{token_1}",
        data={"decision": "approved"}
    )
    response_2 = client.post(
        f"/consentement-parent/2/{token_2}",
        data={"decision": "approved"}
    )

    assert response_1.status_code == 200
    assert response_2.status_code == 200

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.guardian_consent_1_at is not None
        assert user.guardian_consent_2_at is not None
        assert user.is_active is True
        assert user.account_status == "active"


def test_lien_parental_ne_peut_pas_etre_reutilise(app, client):
    with app.app_context():
        user = create_test_user(13)
        token = make_token(app, "parent_consent_1", user.id)

    first = client.post(
        f"/consentement-parent/1/{token}",
        data={"decision": "approved"}
    )
    second = client.post(
        f"/consentement-parent/1/{token}",
        data={"decision": "approved"}
    )

    assert first.status_code == 200
    assert second.status_code == 409
