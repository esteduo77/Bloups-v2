from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class FamilyMembership(db.Model):
    __tablename__ = "family_memberships"

    id = db.Column(db.Integer, primary_key=True)

    family_id = db.Column(
        db.Integer,
        db.ForeignKey("family_groups.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    invited_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    member_role = db.Column(
        db.String(20),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="active"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    accepted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    # Cette date ne doit être renseignée qu'après vérification
    # appropriée du lien de responsabilité parentale.
    relationship_verified_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    __table_args__ = (
        db.UniqueConstraint(
            "family_id",
            "user_id",
            name="uq_family_membership_user"
        ),
        db.CheckConstraint(
            "member_role IN ('parent', 'child')",
            name="ck_family_member_role"
        ),
        db.CheckConstraint(
            "status IN ('pending', 'active', 'revoked')",
            name="ck_family_membership_status"
        ),
        db.CheckConstraint(
            "invited_by_id IS NULL OR invited_by_id != user_id",
            name="ck_family_no_self_invitation"
        ),
        db.Index(
            "ix_family_membership_user_status",
            "user_id",
            "status"
        ),
        db.Index(
            "ix_family_membership_family_status",
            "family_id",
            "status"
        )
    )
