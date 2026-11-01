from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    contact_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "contact_user_id",
            name="uq_contact_pair"
        ),
        db.CheckConstraint(
            "user_id < contact_user_id",
            name="ck_contact_order"
        ),
    )
