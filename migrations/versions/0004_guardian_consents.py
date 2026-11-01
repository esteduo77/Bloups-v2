from alembic import op
import sqlalchemy as sa


revision = "0004_guardian_consents"
down_revision = "0003_contacts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "guardian_consent_1_at",
            sa.DateTime(timezone=True),
            nullable=True
        )
    )
    op.add_column(
        "users",
        sa.Column(
            "guardian_consent_2_at",
            sa.DateTime(timezone=True),
            nullable=True
        )
    )


def downgrade():
    op.drop_column("users", "guardian_consent_2_at")
    op.drop_column("users", "guardian_consent_1_at")
