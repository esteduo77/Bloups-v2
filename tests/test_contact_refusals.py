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
from services.contact_service import (
    decide_parental_approval,
    reject_contact_request,
    accept_contact_request,
)


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


def make_request(sender, receiver, with_approvals=True):
    item = ContactRequest(
        sender_id=sender.id,
        receiver_id=receiver.id,
        status="pending"
    )
    db.session.add(item)
    db.session.flush()

    approvals = []
    if with_approvals:
        approvals = [
            ParentalApproval(
                request_id=item.id,
                guardian_number=1,
                guardian_email="parent1@example.com",
                status="pending"
            ),
            ParentalApproval(
                request_id=item.id,
                guardian_number=2,
                guardian_email="parent2@example.com",
                status="pending"
            )
        ]
        db.session.add_all(approvals)

    db.session.commit()
    return item, approvals


def test_refus_parental_cloture_demande_et_autre_accord(app, monkeypatch):
    with app.app_context():
        sender = make_user("alice", date(2013, 1, 1))
        receiver = make_user("bob")
        contact_request, approvals = make_request(sender, receiver)

        monkeypatch.setattr(
            "services.contact_notifications.send_contact_request_rejected_notification",
            lambda *args, **kwargs: None
        )

        decide_parental_approval(approvals[0], "rejected")

        assert contact_request.status == "rejected"
        assert approvals[0].status == "rejected"
        assert approvals[1].status == "rejected"
        assert approvals[0].decided_at is not None
        assert approvals[1].decided_at is not None


def test_refus_destinataire_cloture_accords_et_notifie(app, monkeypatch):
    with app.app_context():
        sender = make_user("alice", date(2013, 1, 1))
        receiver = make_user("bob")
        contact_request, approvals = make_request(sender, receiver)
        calls = []

        monkeypatch.setattr(
            "services.contact_notifications.send_contact_request_rejected_notification",
            lambda *args, **kwargs: calls.append((args, kwargs))
        )

        reject_contact_request(contact_request, receiver)

        assert contact_request.status == "rejected"
        assert all(item.status == "rejected" for item in approvals)
        assert all(item.decided_at is not None for item in approvals)
        assert len(calls) == 1
        assert calls[0][1]["reason"] == "receiver"


def test_refus_parental_cree_notification_en_file(app):
    with app.app_context():
        sender = make_user("alice", date(2013, 1, 1))
        receiver = make_user("bob")
        contact_request, approvals = make_request(sender, receiver)

        decide_parental_approval(approvals[0], "rejected")

        message = EmailOutbox.query.filter_by(
            dedupe_key=f"contact-rejected-{contact_request.id}"
        ).one()
        assert message.recipient == sender.email
        assert message.status == "pending"


def test_demande_refusee_ne_peut_pas_etre_acceptee(app):
    with app.app_context():
        sender = make_user("alice")
        receiver = make_user("bob")
        contact_request, _ = make_request(
            sender, receiver, with_approvals=False
        )
        contact_request.status = "rejected"
        db.session.commit()

        with pytest.raises(ValueError):
            accept_contact_request(contact_request, receiver)


def test_decision_parentale_deja_traitee_ne_peut_pas_etre_rejouee(app):
    with app.app_context():
        sender = make_user("alice", date(2013, 1, 1))
        receiver = make_user("bob")
        _, approvals = make_request(sender, receiver)

        approvals[0].status = "rejected"
        db.session.commit()

        with pytest.raises(ValueError):
            decide_parental_approval(approvals[0], "approved")


def test_un_seul_refus_parental_cloture_la_demande(app, monkeypatch):
    with app.app_context():
        sender = make_user("alice", date(2013, 1, 1))
        receiver = make_user("bob")

        contact_request, approvals = make_request(
            sender, receiver, with_approvals=False
        )

        approval = ParentalApproval(
            request_id=contact_request.id,
            guardian_number=1,
            guardian_email="parent1@example.com",
            status="pending"
        )
        db.session.add(approval)
        db.session.commit()

        monkeypatch.setattr(
            "services.contact_notifications.send_contact_request_rejected_notification",
            lambda *args, **kwargs: None
        )

        decide_parental_approval(approval, "rejected")

        assert contact_request.status == "rejected"
        assert approval.status == "rejected"
