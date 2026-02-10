"""add engagement_score and score_breakdown columns

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-02-10 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reply_records") as batch_op:
        batch_op.add_column(sa.Column("engagement_score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("score_breakdown", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reply_records") as batch_op:
        batch_op.drop_column("score_breakdown")
        batch_op.drop_column("engagement_score")
