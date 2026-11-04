"""Création des groupes familiaux et des associations."""

from alembic import op
import sqlalchemy as sa


revision = "0007_family_groups"
down_revision = "0006_email_outbox"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "family_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False
        )
    )

    op.create_index(
        "ix_family_groups_created_by",
        "family_groups",
        ["created_by_id"]
    )

    op.create_table(
        "family_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "family_id",
            sa.Integer(),
            sa.ForeignKey("family_groups.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "invited_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True
        ),
        sa.Column(
            "member_role",
            sa.String(20),
            nullable=False
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True
        ),
        sa.Column(
            "relationship_verified_at",
            sa.DateTime(timezone=True),
            nullable=True
        ),
        sa.UniqueConstraint(
            "family_id",
            "user_id",
            name="uq_family_membership_user"
        ),
        sa.CheckConstraint(
            "member_role IN ('parent', 'child')",
            name="ck_family_member_role"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'revoked')",
            name="ck_family_membership_status"
        ),
        sa.CheckConstraint(
            "invited_by_id IS NULL OR invited_by_id != user_id",
            name="ck_family_no_self_invitation"
        )
    )

    op.create_index(
        "ix_family_membership_user_status",
        "family_memberships",
        ["user_id", "status"]
    )

    op.create_index(
        "ix_family_membership_family_status",
        "family_memberships",
        ["family_id", "status"]
    )


def downgrade():
    op.drop_index(
        "ix_family_membership_family_status",
        table_name="family_memberships"
    )

    op.drop_index(
        "ix_family_membership_user_status",
        table_name="family_memberships"
    )

    op.drop_table("family_memberships")

    op.drop_index(
        "ix_family_groups_created_by",
        table_name="family_groups"
    )

    op.drop_table("family_groups")
