from datetime import datetime, timezone

from models import db


def utc_now():
    return datetime.now(timezone.utc)


class ParentalApproval(db.Model):
    __tablename__ = "parental_approvals"

    id = db.Column(db.Integer, primary_key=True)

    request_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "contact_requests.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    guardian_number = db.Column(
        db.Integer,
        nullable=False
    )

    # Adresse enregistrée au moment de la demande.
    guardian_email = db.Column(
        db.String(254),
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    decided_at = db.Column(
        db.DateTime(timezone=True)
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now
    )

    __table_args__ = (
        db.UniqueConstraint(
            "request_id",
            "guardian_number",
            name="uq_request_guardian"
        ),
        db.CheckConstraint(
            "guardian_number IN (1, 2)",
            name="ck_guardian_number"
        ),
        db.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_approval_status"
        ),
    )
