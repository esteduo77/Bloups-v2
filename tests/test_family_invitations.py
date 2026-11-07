import os
from datetime import date, datetime, timezone

os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app
from models import db
from models.user import User
from models.family_group import FamilyGroup
from models.family_membership import FamilyMembership
from services.family_service import (
    accept_child_invitation,
    accept_parent_invitation,
    decline_parent_invitation,
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


def make_user(username, age=35, verified=True):
    today = date.today()
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
        birth_date=date(
            today.year - age,
            today.month,
            min(today.day, 28)
        ),
        is_active=True,
        account_status="active",
        email_verified_at=(
            datetime.now(timezone.utc) if verified else None
        )
    )
    db.session.add(user)
    db.session.flush()
    return user


def make_family():
    parent = make_user("parent")
    child = make_user("child", age=13)
    second_parent = make_user("secondparent")

    family = FamilyGroup(
        name="Famille test",
        created_by_id=parent.id
    )
    db.session.add(family)
    db.session.flush()

    parent_membership = FamilyMembership(
        family_id=family.id,
        user_id=parent.id,
        invited_by_id=parent.id,
        member_role="parent",
        status="active"
    )
    db.session.add(parent_membership)
    db.session.commit()

    return family, parent, child, second_parent, parent_membership


def test_enfant_accepte_si_inviteur_est_responsable_actif(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=child.id,
            invited_by_id=parent.id,
            member_role="child",
            status="pending"
        )
        db.session.add(invitation)
        db.session.commit()

        result = accept_child_invitation(invitation.id, child)

        assert result.status == "active"
        assert result.relationship_verified_at is None


def test_enfant_ne_peut_pas_accepter_si_inviteur_n_est_plus_actif(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=child.id,
            invited_by_id=parent.id,
            member_role="child",
            status="pending"
        )
        db.session.add(invitation)
        parent_membership.status = "revoked"
        db.session.commit()

        with pytest.raises(PermissionError):
            accept_child_invitation(invitation.id, child)

        assert invitation.status == "pending"


def test_second_responsable_refuse_si_createur_n_est_plus_actif(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=second_parent.id,
            invited_by_id=parent.id,
            member_role="parent",
            status="pending"
        )
        db.session.add(invitation)
        parent_membership.status = "revoked"
        db.session.commit()

        with pytest.raises(PermissionError):
            accept_parent_invitation(invitation.id, second_parent)

        assert invitation.status == "pending"



def test_responsable_peut_refuser_sa_propre_invitation(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=second_parent.id,
            invited_by_id=parent.id,
            member_role="parent",
            status="pending"
        )
        db.session.add(invitation)
        db.session.commit()

        result = decline_parent_invitation(
            invitation.id,
            second_parent
        )

        assert result.status == "revoked"


def test_utilisateur_ne_peut_pas_refuser_invitation_d_autrui(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        outsider = make_user("outsider")

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=second_parent.id,
            invited_by_id=parent.id,
            member_role="parent",
            status="pending"
        )
        db.session.add(invitation)
        db.session.commit()

        with pytest.raises(PermissionError):
            decline_parent_invitation(invitation.id, outsider)

        assert invitation.status == "pending"


def test_invitation_deja_traitee_ne_peut_pas_etre_refusee(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=second_parent.id,
            invited_by_id=parent.id,
            member_role="parent",
            status="active"
        )
        db.session.add(invitation)
        db.session.commit()

        with pytest.raises(ValueError):
            decline_parent_invitation(
                invitation.id,
                second_parent
            )

        assert invitation.status == "active"



def test_compte_desactive_ne_voit_pas_ses_invitations(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=second_parent.id,
            invited_by_id=parent.id,
            member_role="parent",
            status="pending"
        )
        db.session.add(invitation)
        db.session.commit()

        second_parent.is_active = False
        db.session.commit()

        from services.family_service import get_my_pending_invitations

        assert get_my_pending_invitations(second_parent) == []


def test_compte_desactive_ne_peut_pas_refuser_invitation(app):
    with app.app_context():
        family, parent, child, second_parent, parent_membership = (
            make_family()
        )

        invitation = FamilyMembership(
            family_id=family.id,
            user_id=second_parent.id,
            invited_by_id=parent.id,
            member_role="parent",
            status="pending"
        )
        db.session.add(invitation)
        db.session.commit()

        second_parent.is_active = False
        db.session.commit()

        with pytest.raises(PermissionError):
            decline_parent_invitation(
                invitation.id,
                second_parent
            )

        assert invitation.status == "pending"
