"""Création de la file d'attente des e-mails."""

from alembic import op
import sqlalchemy as sa

revision = "0006_email_outbox"
down_revision = "0005_user_blocks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.String(180), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("dedupe_key", name="uq_email_outbox_dedupe_key"),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_email_outbox_status"),
    )
    op.create_index("ix_email_outbox_pending", "email_outbox", ["status", "next_attempt_at"])


def downgrade():
    op.drop_index("ix_email_outbox_pending", table_name="email_outbox")
    op.drop_table("email_outbox")
