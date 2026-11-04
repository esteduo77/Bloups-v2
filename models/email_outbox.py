from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class EmailOutbox(db.Model):
    __tablename__ = "email_outbox"

    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(254), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    dedupe_key = db.Column(db.String(180), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    attempts = db.Column(db.Integer, nullable=False, default=0)
    next_attempt_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    last_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    sent_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_email_outbox_status"),
        db.Index("ix_email_outbox_pending", "status", "next_attempt_at"),
    )
