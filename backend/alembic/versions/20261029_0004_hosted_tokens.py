"""Add hosted token billing tables and plan fields."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261029_0004"
down_revision = "20261029_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_plans", sa.Column("token_balance", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_plans", sa.Column("trial_tokens_used", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_plans", sa.Column("trial_period_start", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.add_column("user_plans", sa.Column("premium_until", sa.DateTime(), nullable=True))
    op.add_column("user_plans", sa.Column("daily_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user_plans", sa.Column("daily_date", sa.Date(), nullable=True))
    op.add_column("user_plans", sa.Column("has_purchased", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("redeem_codes", sa.Column("token_grant", sa.Integer(), nullable=False, server_default="0"))


    op.create_table(
        "usage_events", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("model", sa.String(), nullable=False), sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False), sa.Column("tokens_charged", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_usage_events_user_id", "usage_events", ["user_id"])
    op.create_table(
        "audit_logs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("admin_email", sa.String(), nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("change", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_logs"); op.drop_table("usage_events")
    op.drop_column("redeem_codes", "token_grant"); op.drop_column("user_plans", "has_purchased")
    op.drop_column("user_plans", "daily_date"); op.drop_column("user_plans", "daily_count")
    op.drop_column("user_plans", "premium_until"); op.drop_column("user_plans", "trial_period_start")
    op.drop_column("user_plans", "trial_tokens_used"); op.drop_column("user_plans", "token_balance")
