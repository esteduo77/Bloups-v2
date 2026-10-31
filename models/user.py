from datetime import datetime, timezone

from models import db


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

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )
