from alembic import op
import sqlalchemy as sa


revision = "0005_user_blocks"
down_revision = "0004_guardian_consents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "blocker_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "blocked_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.UniqueConstraint(
            "blocker_id", "blocked_user_id",
            name="uq_user_block_pair"
        ),
        sa.CheckConstraint(
            "blocker_id != blocked_user_id",
            name="ck_user_block_not_self"
        )
    )
    op.create_index(
        "ix_user_blocks_blocker", "user_blocks", ["blocker_id"]
    )
    op.create_index(
        "ix_user_blocks_blocked", "user_blocks", ["blocked_user_id"]
    )


def downgrade():
    op.drop_index("ix_user_blocks_blocked", table_name="user_blocks")
    op.drop_index("ix_user_blocks_blocker", table_name="user_blocks")
    op.drop_table("user_blocks")
