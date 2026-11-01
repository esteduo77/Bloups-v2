from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    jsonify
)
from sqlalchemy import or_

from models import db
from models.user import User
from models.contact import Contact
from models.contact_request import ContactRequest
from models.parental_approval import ParentalApproval

from extensions import limiter
from routes.account import get_current_user
from services.security import verify_token
from services.contact_service import (
    create_contact_request,
    accept_contact_request,
    reject_contact_request,
    cancel_contact_request,
    decide_parental_approval,
    parental_approvals_complete
)
from services.contact_notifications import (
    send_guardian_approval,
    send_contact_request_notification
)


contacts = Blueprint("contacts", __name__, url_prefix="/contacts")


def require_user():
    return get_current_user()


@contacts.route("/rechercher", methods=["GET"])
@limiter.limit("20 per minute")
def rechercher():
    user = require_user()
    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    term = request.args.get("q", "").strip()
    if len(term) < 2:
        return jsonify({
            "results": [],
            "message": "Saisis au moins deux caractères."
        })

    users = User.query.filter(
        User.is_active.is_(True),
        User.id != user.id,
        User.username.ilike(f"%{term}%")
    ).limit(20).all()

    return jsonify({
        "results": [
            {"id": item.id, "username": item.username}
            for item in users
        ]
    })


@contacts.route("/demander/<int:user_id>", methods=["POST"])
@limiter.limit("10 per hour")
def demander(user_id):
    sender = require_user()
    if not sender:
        return jsonify({"error": "Connexion requise."}), 401

    receiver = db.session.get(User, user_id)
    if not receiver:
        return jsonify({"error": "Utilisateur introuvable."}), 404

    try:
        contact_request = create_contact_request(sender, receiver)
        approvals = ParentalApproval.query.filter_by(
            request_id=contact_request.id
        ).all()

        if approvals:
            for approval in approvals:
                try:
                    send_guardian_approval(approval)
                except Exception:
                    current_app.logger.exception(
                        "Échec d'envoi d'une autorisation parentale."
                    )

            return jsonify({
                "message": (
                    "Demande créée. Les deux représentants légaux "
                    "doivent donner leur accord."
                ),
                "request_id": contact_request.id,
                "parental_approval_required": True
            }), 201

        try:
            send_contact_request_notification(receiver, sender)
        except Exception:
            current_app.logger.exception(
                "Échec de notification d'une demande de contact."
            )

        return jsonify({
            "message": "Demande de contact envoyée.",
            "request_id": contact_request.id,
            "parental_approval_required": False
        }), 201

    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erreur lors de la création d'une demande de contact."
        )
        return jsonify({"error": "Une erreur interne est survenue."}), 500


@contacts.route("/mes-contacts", methods=["GET"])
def mes_contacts():
    user = require_user()
    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    rows = Contact.query.filter(
        or_(
            Contact.user_id == user.id,
            Contact.contact_user_id == user.id
        )
    ).all()

    contact_ids = [
        row.contact_user_id if row.user_id == user.id else row.user_id
        for row in rows
    ]

    users = User.query.filter(User.id.in_(contact_ids)).all() if contact_ids else []

    return jsonify({
        "contacts": [
            {"id": item.id, "username": item.username}
            for item in users
        ]
    })


@contacts.route("/demandes", methods=["GET"])
def demandes():
    user = require_user()
    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    received = ContactRequest.query.filter_by(
        receiver_id=user.id,
        status="pending"
    ).all()
    sent = ContactRequest.query.filter_by(
        sender_id=user.id,
        status="pending"
    ).all()

    def serialize(item, direction):
        other_id = (
            item.sender_id if direction == "received"
            else item.receiver_id
        )
        other = db.session.get(User, other_id)
        return {
            "id": item.id,
            "username": other.username if other else "Compte indisponible",
            "direction": direction,
            "parental_approval_complete": parental_approvals_complete(item.id)
        }

    return jsonify({
        "received": [serialize(item, "received") for item in received],
        "sent": [serialize(item, "sent") for item in sent]
    })


@contacts.route("/accepter/<int:request_id>", methods=["POST"])
def accepter(request_id):
    user = require_user()
    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    contact_request = db.session.get(ContactRequest, request_id)
    if not contact_request:
        return jsonify({"error": "Demande introuvable."}), 404

    try:
        accept_contact_request(contact_request, user)
        return jsonify({"message": "Contact ajouté."})
    except PermissionError as error:
        return jsonify({"error": str(error)}), 403
    except ValueError as error:
        db.session.rollback()
        return jsonify({"error": str(error)}), 400


@contacts.route("/refuser/<int:request_id>", methods=["POST"])
def refuser(request_id):
    user = require_user()
    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    contact_request = db.session.get(ContactRequest, request_id)
    if not contact_request:
        return jsonify({"error": "Demande introuvable."}), 404

    try:
        reject_contact_request(contact_request, user)
        return jsonify({"message": "Demande refusée."})
    except PermissionError as error:
        return jsonify({"error": str(error)}), 403
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@contacts.route("/annuler/<int:request_id>", methods=["POST"])
def annuler(request_id):
    user = require_user()
    if not user:
        return jsonify({"error": "Connexion requise."}), 401

    contact_request = db.session.get(ContactRequest, request_id)
    if not contact_request:
        return jsonify({"error": "Demande introuvable."}), 404

    try:
        cancel_contact_request(contact_request, user)
        return jsonify({"message": "Demande annulée."})
    except PermissionError as error:
        return jsonify({"error": str(error)}), 403
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@contacts.route(
    "/autorisation-parentale/<token>",
    methods=["GET", "POST"]
)
@limiter.limit("10 per hour")
def approval_parentale(token):
    approval_id = verify_token(
        current_app.config["SECRET_KEY"],
        token,
        "contact_parental_approval",
        max_age=172800
    )

    if not approval_id:
        return "Lien invalide ou expiré.", 400

    approval = db.session.get(ParentalApproval, approval_id)
    if not approval:
        return "Autorisation introuvable.", 404

    if approval.status != "pending":
        return "Cette autorisation a déjà été traitée.", 409

    contact_request = db.session.get(ContactRequest, approval.request_id)
    if not contact_request or contact_request.status != "pending":
        return "Cette demande n'est plus active.", 409

    sender = db.session.get(User, contact_request.sender_id)
    receiver = db.session.get(User, contact_request.receiver_id)

    if request.method == "GET":
        return render_template(
            "autorisation_parentale.html",
            token=token,
            sender=sender,
            receiver=receiver
        )

    choice = request.form.get("decision")
    if choice not in ("approved", "rejected"):
        return "Décision invalide.", 400

    try:
        decide_parental_approval(approval, choice)
    except ValueError as error:
        db.session.rollback()
        return str(error), 400

    return render_template(
        "autorisation_parentale.html",
        token=token,
        sender=sender,
        receiver=receiver,
        completed=True,
        decision=choice
    )
