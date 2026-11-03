"""Flag usage rows whose token counts were estimated."""

from alembic import op
import sqlalchemy as sa

revision = "20261103_0010"
down_revision = "20261102_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usage_events", sa.Column("estimated", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("usage_events", "estimated", server_default=None)


def downgrade() -> None:
    op.drop_column("usage_events", "estimated")
