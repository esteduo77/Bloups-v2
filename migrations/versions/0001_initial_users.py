from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(30), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("account_status", sa.String(30), nullable=False, server_default="pending_email"),
        sa.Column("email_verified_at", sa.DateTime(timezone=True)),
        sa.Column("guardian_email", sa.String(254)),
        sa.Column("guardian_consent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email")
    )


def downgrade():
    op.drop_table("users")
