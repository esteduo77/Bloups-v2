import os
from datetime import date

os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app
from models import db
from models.user import User
from models.contact import Contact
from models.contact_request import ContactRequest
from models.user_block import UserBlock
from services.contact_service import (
    block_user,
    unblock_user,
    create_contact_request,
    accept_contact_request,
    get_blocked_users,
)


@pytest.fixture
def app():
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "cle-test-bloops",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "RATELIMIT_ENABLED": False,
    })
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def make_user(username):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
        birth_date=date(2000, 1, 1),
        is_active=True,
        account_status="active",
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_blocage_enregistre_et_apparait_dans_la_liste(app):
    with app.app_context():
        first = make_user("alice")
        second = make_user("bob")

        block_user(first, second)

        assert UserBlock.query.filter_by(
            blocker_id=first.id,
            blocked_user_id=second.id
        ).one()
        assert [u.id for u in get_blocked_users(first)] == [second.id]


def test_impossible_de_se_bloquer_soi_meme(app):
    with app.app_context():
        user = make_user("alice")
        with pytest.raises(ValueError):
            block_user(user, user)


def test_blocage_supprime_contact_et_annule_demande(app):
    with app.app_context():
        first = make_user("alice")
        second = make_user("bob")
        low, high = sorted((first.id, second.id))
        db.session.add(Contact(user_id=low, contact_user_id=high))
        pending = ContactRequest(
            sender_id=first.id, receiver_id=second.id, status="pending"
        )
        db.session.add(pending)
        db.session.commit()

        block_user(first, second)

        assert Contact.query.filter_by(
            user_id=low, contact_user_id=high
        ).first() is None
        assert db.session.get(ContactRequest, pending.id).status == "cancelled"


def test_blocage_empeche_demande_dans_les_deux_sens(app):
    with app.app_context():
        first = make_user("alice")
        second = make_user("bob")
        block_user(first, second)

        with pytest.raises(ValueError):
            create_contact_request(first, second)
        with pytest.raises(ValueError):
            create_contact_request(second, first)


def test_deblocage_ne_recree_pas_le_contact(app):
    with app.app_context():
        first = make_user("alice")
        second = make_user("bob")
        block_user(first, second)
        unblock_user(first, second)

        assert UserBlock.query.filter_by(
            blocker_id=first.id, blocked_user_id=second.id
        ).first() is None
        assert Contact.query.count() == 0


def test_seul_auteur_du_blocage_peut_debloquer(app):
    with app.app_context():
        first = make_user("alice")
        second = make_user("bob")
        third = make_user("charlie")
        block_user(first, second)

        with pytest.raises(ValueError):
            unblock_user(third, second)
        assert UserBlock.query.count() == 1


def test_acceptation_ancienne_demande_refusee_apres_blocage(app):
    with app.app_context():
        first = make_user("alice")
        second = make_user("bob")
        pending = ContactRequest(
            sender_id=first.id, receiver_id=second.id, status="pending"
        )
        db.session.add(pending)
        db.session.commit()
        block_user(first, second)

        with pytest.raises(ValueError):
            accept_contact_request(pending, second)
