import os
from datetime import date

os.environ.setdefault("BLOOPS_SECRET_KEY", "cle-test-bloops")
os.environ.setdefault("BLOOPS_DATABASE_URL", "sqlite:///:memory:")

import pytest

from app import create_app
from models import db
from models.user import User
from models.contact_request import ContactRequest
from models.parental_approval import ParentalApproval
from models.email_outbox import EmailOutbox
from services.contact_notifications import enqueue_email, process_email_queue
from services.contact_service import decide_parental_approval


@pytest.fixture
def app(monkeypatch):
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


def make_user(username, birth_date=date(2000, 1, 1)):
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="test-hash",
        birth_date=birth_date,
        is_active=True,
        account_status="active"
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_notification_enregistree(app):
    with app.app_context():
        enqueue_email("test@example.com", "Test", "Message de test", "test-notification-1")
        message = EmailOutbox.query.one()
        assert message.status == "pending"
        assert message.attempts == 0


def test_doublon_empeche(app):
    with app.app_context():
        enqueue_email("test@example.com", "Test", "Message", "notification-unique")
        enqueue_email("test@example.com", "Test", "Message", "notification-unique")
        assert EmailOutbox.query.count() == 1


def test_envoi_reussi(app, monkeypatch):
    with app.app_context():
        enqueue_email("test@example.com", "Test", "Message", "notification-ok")
        monkeypatch.setattr("services.contact_notifications.send_email", lambda *args: None)
        result = process_email_queue()
        message = EmailOutbox.query.one()
        assert result["sent"] == 1
        assert message.status == "sent"
        assert message.sent_at is not None


def test_echec_programme_nouvelle_tentative(app, monkeypatch):
    with app.app_context():
        enqueue_email("test@example.com", "Test", "Message", "notification-failed")

        def fake_send_email(*args):
            raise RuntimeError("SMTP indisponible")

        monkeypatch.setattr("services.contact_notifications.send_email", fake_send_email)
        result = process_email_queue()
        message = EmailOutbox.query.one()
        assert result["processed"] == 1
        assert message.status == "pending"
        assert message.attempts == 1
        assert message.last_error is not None


def test_deux_accords_creent_notification_destinataire(app):
    with app.app_context():
        sender = make_user("alice")
        receiver = make_user("bob")
        contact_request = ContactRequest(
            sender_id=sender.id,
            receiver_id=receiver.id,
            status="pending"
        )
        db.session.add(contact_request)
        db.session.flush()
        approval_1 = ParentalApproval(
            request_id=contact_request.id,
            guardian_number=1,
            guardian_email="parent1@example.com",
            status="approved"
        )
        approval_2 = ParentalApproval(
            request_id=contact_request.id,
            guardian_number=2,
            guardian_email="parent2@example.com",
            status="pending"
        )
        db.session.add_all([approval_1, approval_2])
        db.session.commit()
        decide_parental_approval(approval_2, "approved")
        notification = EmailOutbox.query.filter_by(
            dedupe_key=f"contact-ready-{contact_request.id}"
        ).one()
        assert notification.recipient == receiver.email
        assert notification.status == "pending"


def test_un_seul_accord_parental_notifie_le_destinataire(app):
    with app.app_context():
        sender = make_user("alice")
        receiver = make_user("bob")

        contact_request = ContactRequest(
            sender_id=sender.id,
            receiver_id=receiver.id,
            status="pending"
        )
        db.session.add(contact_request)
        db.session.flush()

        approval = ParentalApproval(
            request_id=contact_request.id,
            guardian_number=1,
            guardian_email="parent1@example.com",
            status="pending"
        )
        db.session.add(approval)
        db.session.commit()

        decide_parental_approval(approval, "approved")

        notification = EmailOutbox.query.filter_by(
            dedupe_key=f"contact-ready-{contact_request.id}"
        ).one()

        assert notification.recipient == receiver.email
        assert notification.status == "pending"
