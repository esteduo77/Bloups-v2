from alembic import op
import sqlalchemy as sa


revision = "0002_profile"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("bio", sa.String(300), nullable=False, server_default="")
    )
    op.add_column(
        "users",
        sa.Column("profile_visibility", sa.String(10), nullable=False, server_default="private")
    )


def downgrade():
    op.drop_column("users", "profile_visibility")
    op.drop_column("users", "bio")
