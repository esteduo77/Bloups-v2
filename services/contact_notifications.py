from flask import current_app, url_for

from services.security import create_token
from services.email import send_email


def send_guardian_approval(approval):
    token = create_token(
        current_app.config["SECRET_KEY"],
        "contact_parental_approval",
        approval.id
    )

    link = url_for(
        "contacts.approval_parentale",
        token=token,
        _external=True
    )

    send_email(
        approval.guardian_email,
        "Autorisation de contact — BLOOPS",
        (
            "Une demande de contact nécessite votre autorisation.\n\n"
            "Pour consulter la demande et prendre une décision :\n"
            f"{link}\n\n"
            "Ce lien expire après 48 heures. "
            "Chaque représentant légal doit répondre séparément."
        )
    )


def send_contact_request_notification(receiver, sender):
    send_email(
        receiver.email,
        "Nouvelle demande de contact — BLOOPS",
        (
            f"{sender.username} souhaite vous ajouter à ses contacts.\n\n"
            "Connectez-vous à BLOOPS pour consulter cette demande."
        )
    )
