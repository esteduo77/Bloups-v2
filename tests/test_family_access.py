import os
from datetime import date

os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app
from models import db
from models.user import User
from models.family_group import FamilyGroup
from models.family_membership import FamilyMembership
from services.family_service import (
    get_family_members,
    get_my_pending_invitations,
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


def make_user(username, age=35):
    today = date.today()
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
        birth_date=date(today.year - age, today.month, min(today.day, 28)),
        is_active=True,
        account_status="active"
    )
    db.session.add(user)
    db.session.flush()
    return user


def make_family():
    parent = make_user("parent")
    child = make_user("child", age=13)
    pending_child = make_user("pendingchild", age=12)
    outsider = make_user("outsider")

    group = FamilyGroup(name="Famille test", created_by_id=parent.id)
    db.session.add(group)
    db.session.flush()

    db.session.add_all([
        FamilyMembership(
            family_id=group.id, user_id=parent.id,
            invited_by_id=parent.id, member_role="parent",
            status="active"
        ),
        FamilyMembership(
            family_id=group.id, user_id=child.id,
            invited_by_id=parent.id, member_role="child",
            status="active"
        ),
        FamilyMembership(
            family_id=group.id, user_id=pending_child.id,
            invited_by_id=parent.id, member_role="child",
            status="pending"
        ),
    ])
    db.session.commit()
    return group, parent, child, pending_child, outsider


def test_parent_actif_peut_voir_membres_et_invitations_en_attente(app):
    with app.app_context():
        group, parent, child, pending_child, outsider = make_family()

        members = get_family_members(group.id, parent)

        assert {item.user_id for item in members} == {
            parent.id, child.id, pending_child.id
        }


def test_enfant_actif_ne_voit_pas_les_invitations_en_attente(app):
    with app.app_context():
        group, parent, child, pending_child, outsider = make_family()

        members = get_family_members(group.id, child)

        assert {item.user_id for item in members} == {
            parent.id, child.id
        }
        assert all(item.status == "active" for item in members)


def test_utilisateur_exterieur_ne_peut_pas_voir_le_groupe(app):
    with app.app_context():
        group, parent, child, pending_child, outsider = make_family()

        with pytest.raises(PermissionError):
            get_family_members(group.id, outsider)



def test_groupe_desactive_inaccessible_aux_membres(app):
    with app.app_context():
        group, parent, child, pending_child, outsider = make_family()

        group.is_active = False
        db.session.commit()

        with pytest.raises(PermissionError):
            get_family_members(group.id, parent)


def test_invitations_des_groupes_desactives_non_affichees(app):
    with app.app_context():
        group, parent, child, pending_child, outsider = make_family()

        group.is_active = False
        db.session.commit()

        invitations = get_my_pending_invitations(pending_child)

        assert invitations == []
