from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class ContactRequest(db.Model):
    __tablename__ = "contact_requests"

    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    receiver_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now
    )

    __table_args__ = (
        db.CheckConstraint(
            "sender_id != receiver_id",
            name="ck_request_not_self"
        ),
        db.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="ck_request_status"
        ),
        db.Index(
            "ix_contact_request_receiver_status",
            "receiver_id",
            "status"
        ),
        db.Index(
            "ix_contact_request_sender_status",
            "sender_id",
            "status"
        ),
    )
