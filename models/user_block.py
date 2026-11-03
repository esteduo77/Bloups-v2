from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class UserBlock(db.Model):
    __tablename__ = "user_blocks"

    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    blocked_user_id = db.Column(
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
            "blocker_id", "blocked_user_id",
            name="uq_user_block_pair"
        ),
        db.CheckConstraint(
            "blocker_id != blocked_user_id",
            name="ck_user_block_not_self"
        ),
        db.Index("ix_user_blocks_blocker", "blocker_id"),
        db.Index("ix_user_blocks_blocked", "blocked_user_id"),
    )
