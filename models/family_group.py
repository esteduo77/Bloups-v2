from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class FamilyGroup(db.Model):
    __tablename__ = "family_groups"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(80), nullable=False)

    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
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
