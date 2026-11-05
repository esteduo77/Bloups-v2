from flask import Blueprint, jsonify, request, current_app

from models import db
from models.user import User
from models.family_group import FamilyGroup
from models.family_membership import FamilyMembership

from routes.account import get_current_user
from services.family_service import (
    create_family,
    invite_child,
    accept_child_invitation,
    get_family_members,
    get_my_pending_invitations,
    invite_second_parent,
    accept_parent_invitation,
    decline_parent_invitation
)

from extensions import limiter
from services.contact_notifications import send_family_parent_invitation_notification


family = Blueprint("family", __name__, url_prefix="/famille")


def require_user():
    return get_current_user()


@family.route("/creer", methods=["POST"])
@limiter.limit("5 per hour")
def creer():
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    data = request.get_json(silent=True) or {}

    try:
        result = create_family(user, data.get("name", ""))

        return jsonify({
            "message": "Groupe familial créé.",
            "family_id": result.id,
            "name": result.name
        }), 201

    except PermissionError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 403

    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erreur lors de la création d'un groupe familial."
        )
        return jsonify({"error": "Erreur interne."}), 500


@family.route("/mes-groupes", methods=["GET"])
def mes_groupes():
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    memberships = FamilyMembership.query.filter_by(
        user_id=user.id,
        status="active"
    ).all()

    results = []

    for membership in memberships:
        group = db.session.get(
            FamilyGroup,
            membership.family_id
        )

        if group and group.is_active:
            results.append({
                "id": group.id,
                "name": group.name,
                "my_role": membership.member_role
            })

    return jsonify({"families": results})


@family.route("/<int:family_id>/inviter-enfant", methods=["POST"])
@limiter.limit("10 per hour")
def inviter_enfant(family_id):
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    data = request.get_json(silent=True) or {}

    try:
        membership = invite_child(
            family_id,
            user,
            data.get("username", "")
        )

        return jsonify({
            "message": "Invitation envoyée au compte enfant.",
            "membership_id": membership.id,
            "status": membership.status
        }), 201

    except PermissionError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 403

    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erreur lors de l'invitation d'un enfant."
        )
        return jsonify({"error": "Erreur interne."}), 500


@family.route("/invitations", methods=["GET"])
def invitations():
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    pending = get_my_pending_invitations(user)

    results = []

    for membership in pending:
        group = db.session.get(
            FamilyGroup,
            membership.family_id
        )
        parent = db.session.get(
            User,
            membership.invited_by_id
        ) if membership.invited_by_id else None

        results.append({
            "membership_id": membership.id,
            "family_name": group.name if group else "Groupe familial",
            "invited_by": parent.username if parent else "Compte indisponible",
            "role": membership.member_role
        })

    return jsonify({"invitations": results})


@family.route(
    "/invitations/<int:membership_id>/accepter",
    methods=["POST"]
)
@limiter.limit("10 per hour")
def accepter_invitation(membership_id):
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    try:
        accept_child_invitation(membership_id, user)

        return jsonify({
            "message": "Association au groupe acceptée.",
            "relationship_verified": False
        })

    except PermissionError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 403

    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erreur lors de l'acceptation d'une invitation familiale."
        )
        return jsonify({"error": "Erreur interne."}), 500


@family.route("/<int:family_id>/membres", methods=["GET"])
def membres(family_id):
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    try:
        memberships = get_family_members(family_id, user)

        results = []

        for membership in memberships:
            member = db.session.get(User, membership.user_id)

            if member:
                results.append({
                    "username": member.username,
                    "role": membership.member_role,
                    "status": membership.status,
                    "relationship_verified": (
                        membership.relationship_verified_at is not None
                    )
                })

        return jsonify({"members": results})

    except PermissionError as error:
        return jsonify({"error": str(error)}), 403



@family.route("/<int:family_id>/inviter-responsable", methods=["POST"])
@limiter.limit("5 per hour")
def inviter_responsable(family_id):
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    data = request.get_json(silent=True) or {}

    try:
        membership = invite_second_parent(
            family_id,
            user,
            data.get("email", "")
        )

        family_group = db.session.get(FamilyGroup, family_id)
        invitee = db.session.get(User, membership.user_id)

        try:
            send_family_parent_invitation_notification(
                membership,
                family_group,
                user,
                invitee
            )
        except Exception:
            current_app.logger.exception(
                "Impossible de mettre en file l'e-mail d'invitation du second responsable."
            )

        return jsonify({
            "message": (
                "Invitation créée. Elle est disponible dans l'espace Famille "
                "du compte invité."
            ),
            "membership_id": membership.id,
            "status": membership.status
        }), 201

    except PermissionError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 403

    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erreur lors de l'invitation d'un second responsable."
        )
        return jsonify({"error": "Erreur interne."}), 500


@family.route(
    "/invitations/<int:membership_id>/accepter-responsable",
    methods=["POST"]
)
@limiter.limit("10 per hour")
def accepter_invitation_responsable(membership_id):
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    try:
        accept_parent_invitation(membership_id, user)
        return jsonify({
            "message": "Invitation au groupe familial acceptée.",
            "relationship_verified": False
        })

    except PermissionError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 403

    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erreur lors de l'acceptation d'une invitation de responsable."
        )
        return jsonify({"error": "Erreur interne."}), 500


@family.route(
    "/invitations/<int:membership_id>/refuser-responsable",
    methods=["POST"]
)
@limiter.limit("10 per hour")
def refuser_invitation_responsable(membership_id):
    user = require_user()

    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    try:
        decline_parent_invitation(membership_id, user)
        return jsonify({"message": "Invitation refusée."})

    except PermissionError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 403

    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erreur lors du refus d'une invitation de responsable."
        )
        return jsonify({"error": "Erreur interne."}), 500
