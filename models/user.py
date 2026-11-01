from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(254),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    birth_date = db.Column(
        db.Date,
        nullable=False
    )

    role = db.Column(
        db.String(20),
        nullable=False,
        default="user"
    )

    account_status = db.Column(
        db.String(30),
        nullable=False,
        default="pending_email"
    )

    email_verified_at = db.Column(db.DateTime(timezone=True))
    guardian_email = db.Column(db.String(254))
    guardian_consent_at = db.Column(db.DateTime(timezone=True))

    bio = db.Column(
        db.String(300),
        nullable=False,
        default=""
    )

    profile_visibility = db.Column(
        db.String(10),
        nullable=False,
        default="private"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )
