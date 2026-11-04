from datetime import datetime, timedelta, timezone

from flask import current_app, url_for
from sqlalchemy.exc import IntegrityError

from models import db
from models.email_outbox import EmailOutbox
from services.security import create_token
from services.email import send_email


MAX_ATTEMPTS = 8


def enqueue_email(recipient, subject, body, dedupe_key):
    existing = EmailOutbox.query.filter_by(dedupe_key=dedupe_key).first()
    if existing:
        return existing

    message = EmailOutbox(
        recipient=recipient,
        subject=subject,
        body=body,
        dedupe_key=dedupe_key,
        status="pending"
    )
    db.session.add(message)

    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return EmailOutbox.query.filter_by(dedupe_key=dedupe_key).first()

    return message


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
    enqueue_email(
        approval.guardian_email,
        "Autorisation de contact — BLOOPS",
        (
            "Une demande de contact nécessite votre autorisation.\n\n"
            f"Pour consulter la demande : {link}\n\n"
            "Ce lien expire après 48 heures. "
            "Chaque représentant légal doit répondre séparément."
        ),
        f"parental-approval-{approval.id}"
    )


def send_contact_request_notification(receiver, sender):
    enqueue_email(
        receiver.email,
        "Nouvelle demande de contact — BLOOPS",
        (
            f"{sender.username} souhaite vous ajouter à vos contacts.\n\n"
            "Connectez-vous à BLOOPS pour consulter cette demande."
        ),
        f"contact-request-{sender.id}-{receiver.id}"
    )


def send_contact_request_ready_notification(contact_request, sender, receiver):
    enqueue_email(
        receiver.email,
        "Demande de contact autorisée — BLOOPS",
        (
            f"Les deux représentants légaux de {sender.username} "
            "ont autorisé cette demande.\n\n"
            "Connectez-vous à BLOOPS pour accepter ou refuser "
            "la demande de contact."
        ),
        f"contact-ready-{contact_request.id}"
    )


def process_email_queue(limit=50):
    now = datetime.now(timezone.utc)
    messages = (
        EmailOutbox.query
        .filter(
            EmailOutbox.status == "pending",
            EmailOutbox.next_attempt_at <= now
        )
        .order_by(EmailOutbox.created_at.asc())
        .limit(limit)
        .all()
    )

    sent = 0
    failed = 0

    for message in messages:
        try:
            send_email(message.recipient, message.subject, message.body)
            message.status = "sent"
            message.sent_at = datetime.now(timezone.utc)
            message.last_error = None
            sent += 1
        except Exception as error:
            message.attempts += 1
            message.last_error = str(error)[:2000]
            if message.attempts >= MAX_ATTEMPTS:
                message.status = "failed"
                failed += 1
            else:
                delay_minutes = min(2 ** message.attempts, 24 * 60)
                message.next_attempt_at = (
                    datetime.now(timezone.utc)
                    + timedelta(minutes=delay_minutes)
                )
            current_app.logger.exception(
                "Échec d'envoi de l'e-mail %s", message.id
            )
        db.session.commit()

    return {"sent": sent, "failed": failed, "processed": len(messages)}
