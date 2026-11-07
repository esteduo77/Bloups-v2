from datetime import date, datetime, timezone

from sqlalchemy import func

from models import db
from models.user import User
from models.family_group import FamilyGroup
from models.family_membership import FamilyMembership


def calculate_age(birth_date):
    today = date.today()
    return (
        today.year - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def get_active_parent_membership(family_id, user_id):
    return FamilyMembership.query.filter_by(
        family_id=family_id,
        user_id=user_id,
        member_role="parent",
        status="active"
    ).first()


def create_family(parent, name):
    name = (name or "").strip()

    if not parent or not parent.is_active:
        raise ValueError("Compte parent invalide.")

    if calculate_age(parent.birth_date) < 18:
        raise PermissionError(
            "Seul un compte adulte peut créer un groupe familial."
        )

    if len(name) < 2 or len(name) > 80:
        raise ValueError(
            "Le nom du groupe doit contenir entre 2 et 80 caractères."
        )

    family = FamilyGroup(
        name=name,
        created_by_id=parent.id
    )

    db.session.add(family)
    db.session.flush()

    membership = FamilyMembership(
        family_id=family.id,
        user_id=parent.id,
        invited_by_id=parent.id,
        member_role="parent",
        status="active"
    )

    db.session.add(membership)
    db.session.commit()

    return family


def invite_child(family_id, parent, child_username):
    if not get_active_parent_membership(family_id, parent.id):
        raise PermissionError(
            "Tu n'es pas responsable de ce groupe familial."
        )

    family = db.session.get(FamilyGroup, family_id)

    if not family or not family.is_active:
        raise ValueError("Groupe familial introuvable.")

    child_username = (child_username or "").strip()

    child = User.query.filter_by(
        username=child_username,
        is_active=True
    ).first()

    if not child:
        raise ValueError("Compte enfant introuvable.")

    if child.id == parent.id:
        raise ValueError("Tu ne peux pas t'inviter toi-même.")

    if calculate_age(child.birth_date) >= 18:
        raise ValueError(
            "Ce compte ne correspond pas à un compte enfant."
        )

    membership = FamilyMembership.query.filter_by(
        family_id=family_id,
        user_id=child.id
    ).first()

    if membership:
        if membership.status == "pending":
            raise ValueError("Une invitation est déjà en attente.")

        if membership.status == "active":
            raise ValueError("Ce compte appartient déjà à ce groupe.")

        # Réactivation d'une ancienne association révoquée.
        membership.member_role = "child"
        membership.status = "pending"
        membership.invited_by_id = parent.id
        membership.accepted_at = None
        membership.relationship_verified_at = None
        membership.created_at = datetime.now(timezone.utc)
    else:
        membership = FamilyMembership(
            family_id=family_id,
            user_id=child.id,
            invited_by_id=parent.id,
            member_role="child",
            status="pending"
        )
        db.session.add(membership)

    db.session.commit()

    return membership


def accept_child_invitation(membership_id, child):
    membership = db.session.get(
        FamilyMembership,
        membership_id
    )

    if not membership:
        raise ValueError("Invitation introuvable.")

    if membership.user_id != child.id:
        raise PermissionError(
            "Cette invitation ne t'est pas destinée."
        )

    if membership.member_role != "child":
        raise ValueError("Type d'invitation invalide.")

    if membership.status != "pending":
        raise ValueError("Cette invitation n'est plus en attente.")

    family = db.session.get(
        FamilyGroup,
        membership.family_id
    )

    if not family or not family.is_active:
        raise ValueError("Ce groupe familial n'est plus actif.")

    inviter = db.session.get(User, membership.invited_by_id)

    if (
        not inviter
        or not inviter.is_active
        or not get_active_parent_membership(
            membership.family_id,
            inviter.id
        )
    ):
        raise PermissionError(
            "L'invitation n'est plus valide : le responsable qui l'a envoyée n'est plus actif dans ce groupe."
        )

    membership.status = "active"
    membership.accepted_at = datetime.now(timezone.utc)

    # L'acceptation par l'enfant ne prouve pas à elle seule
    # le lien de responsabilité de l'adulte.
    membership.relationship_verified_at = None

    db.session.commit()

    return membership


def get_family_members(family_id, user):
    membership = FamilyMembership.query.filter_by(
        family_id=family_id,
        user_id=user.id,
        status="active"
    ).first()

    if not membership:
        raise PermissionError(
            "Tu ne peux pas consulter ce groupe familial."
        )

    query = FamilyMembership.query.filter_by(
        family_id=family_id
    )

    if membership.member_role != "parent":
        query = query.filter(
            FamilyMembership.status == "active"
        )
    else:
        query = query.filter(
            FamilyMembership.status.in_(["active", "pending"])
        )

    return query.all()


def invite_second_parent(family_id, inviter, email):
    family = db.session.get(FamilyGroup, family_id)

    if not family or not family.is_active:
        raise ValueError("Groupe familial introuvable.")

    if family.created_by_id != inviter.id:
        raise PermissionError(
            "Seul le créateur du groupe peut inviter un second responsable."
        )

    if not inviter.is_active or not inviter.birth_date:
        raise PermissionError("Compte responsable invalide.")

    if calculate_age(inviter.birth_date) < 18:
        raise PermissionError("Un compte adulte est nécessaire.")

    if not get_active_parent_membership(family_id, inviter.id):
        raise PermissionError("Tu n'es pas responsable actif de ce groupe.")

    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Adresse e-mail obligatoire.")

    invitee = User.query.filter(
        func.lower(User.email) == email,
        User.is_active.is_(True)
    ).first()

    if not invitee:
        raise ValueError("Aucun compte actif ne correspond à cette adresse.")

    if invitee.id == inviter.id:
        raise ValueError("Tu ne peux pas t'inviter toi-même.")

    if not invitee.birth_date or calculate_age(invitee.birth_date) < 18:
        raise ValueError("Le second responsable doit être majeur.")

    if not invitee.email_verified_at:
        raise ValueError("L'adresse e-mail du compte doit être vérifiée.")

    existing_membership = FamilyMembership.query.filter_by(
        family_id=family_id,
        user_id=invitee.id
    ).first()

    if existing_membership and existing_membership.member_role == "child":
        raise ValueError("Ce compte est déjà associé comme enfant à ce groupe.")

    parent_count = FamilyMembership.query.filter_by(
        family_id=family_id,
        member_role="parent"
    ).filter(
        FamilyMembership.status.in_(["active", "pending"])
    ).count()

    if parent_count >= 2 and not (
        existing_membership and existing_membership.status == "revoked"
    ):
        raise ValueError("Ce groupe possède déjà deux responsables.")

    if existing_membership:
        if existing_membership.status == "pending":
            raise ValueError("Une invitation est déjà en attente.")
        if existing_membership.status == "active":
            raise ValueError("Ce compte est déjà responsable de ce groupe.")

        existing_membership.member_role = "parent"
        existing_membership.status = "pending"
        existing_membership.invited_by_id = inviter.id
        existing_membership.accepted_at = None
        existing_membership.relationship_verified_at = None
        existing_membership.created_at = datetime.now(timezone.utc)
        membership = existing_membership
    else:
        membership = FamilyMembership(
            family_id=family_id,
            user_id=invitee.id,
            invited_by_id=inviter.id,
            member_role="parent",
            status="pending"
        )
        db.session.add(membership)

    db.session.commit()
    return membership


def accept_parent_invitation(membership_id, invitee):
    membership = db.session.get(FamilyMembership, membership_id)

    if not membership:
        raise ValueError("Invitation introuvable.")
    if membership.user_id != invitee.id:
        raise PermissionError("Cette invitation ne t'est pas destinée.")
    if membership.member_role != "parent":
        raise ValueError("Type d'invitation invalide.")
    if membership.status != "pending":
        raise ValueError("Cette invitation n'est plus en attente.")

    family = db.session.get(FamilyGroup, membership.family_id)
    if not family or not family.is_active:
        raise ValueError("Ce groupe familial n'est plus actif.")
    if membership.invited_by_id != family.created_by_id:
        raise PermissionError("Invitation non autorisée.")

    inviter = db.session.get(User, family.created_by_id)

    if (
        not inviter
        or not inviter.is_active
        or not get_active_parent_membership(
            family.id,
            inviter.id
        )
    ):
        raise PermissionError(
            "L'invitation n'est plus valide : le créateur n'est plus responsable actif de ce groupe."
        )

    if not invitee.is_active or not invitee.birth_date:
        raise PermissionError("Compte responsable invalide.")
    if calculate_age(invitee.birth_date) < 18:
        raise PermissionError("Un compte adulte est nécessaire.")
    if not invitee.email_verified_at:
        raise PermissionError("L'adresse e-mail doit être vérifiée.")

    membership.status = "active"
    membership.accepted_at = datetime.now(timezone.utc)

    # L'acceptation et la vérification de l'e-mail ne prouvent pas
    # le lien légal de responsabilité.
    membership.relationship_verified_at = None

    db.session.commit()
    return membership


def decline_parent_invitation(membership_id, invitee):
    membership = db.session.get(FamilyMembership, membership_id)

    if not membership:
        raise ValueError("Invitation introuvable.")
    if membership.user_id != invitee.id:
        raise PermissionError("Cette invitation ne t'est pas destinée.")
    if membership.member_role != "parent":
        raise ValueError("Type d'invitation invalide.")
    if membership.status != "pending":
        raise ValueError("Cette invitation n'est plus en attente.")

    membership.status = "revoked"
    db.session.commit()
    return membership


def get_my_pending_invitations(user):
    return FamilyMembership.query.filter_by(
        user_id=user.id,
        status="pending"
    ).all()
