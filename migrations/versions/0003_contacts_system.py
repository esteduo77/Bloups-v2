from alembic import op
import sqlalchemy as sa


revision = "0003_contacts"
down_revision = "0002_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("guardian_email_2", sa.String(254), nullable=True)
    )

    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "contact_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False
        ),
        sa.UniqueConstraint(
            "user_id",
            "contact_user_id",
            name="uq_contact_pair"
        ),
        sa.CheckConstraint(
            "user_id < contact_user_id",
            name="ck_contact_order"
        )
    )

    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "sender_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "receiver_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending"
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
        ),
        sa.CheckConstraint(
            "sender_id != receiver_id",
            name="ck_request_not_self"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="ck_request_status"
        )
    )

    op.create_index(
        "ix_contact_request_receiver_status",
        "contact_requests",
        ["receiver_id", "status"]
    )

    op.create_index(
        "ix_contact_request_sender_status",
        "contact_requests",
        ["sender_id", "status"]
    )

    op.create_table(
        "parental_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Integer(),
            sa.ForeignKey("contact_requests.id", ondelete="CASCADE"),
            nullable=False
        ),
        sa.Column(
            "guardian_number",
            sa.Integer(),
            nullable=False
        ),
        sa.Column(
            "guardian_email",
            sa.String(254),
            nullable=False
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending"
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False
        ),
        sa.UniqueConstraint(
            "request_id",
            "guardian_number",
            name="uq_request_guardian"
        ),
        sa.CheckConstraint(
            "guardian_number IN (1, 2)",
            name="ck_guardian_number"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_approval_status"
        )
    )


def downgrade():
    op.drop_table("parental_approvals")

    op.drop_index(
        "ix_contact_request_sender_status",
        table_name="contact_requests"
    )
    op.drop_index(
        "ix_contact_request_receiver_status",
        table_name="contact_requests"
    )

    op.drop_table("contact_requests")
    op.drop_table("contacts")

    op.drop_column("users", "guardian_email_2")
