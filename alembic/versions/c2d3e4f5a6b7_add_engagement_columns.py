"""add engagement columns (follower_count, like_count, comment_count, repost_count)

Revision ID: c2d3e4f5a6b7
Revises: b1a2c3d4e5f6
Create Date: 2026-02-10 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "b1a2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reply_records") as batch_op:
        batch_op.add_column(sa.Column("follower_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("like_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("comment_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("repost_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reply_records") as batch_op:
        batch_op.drop_column("repost_count")
        batch_op.drop_column("comment_count")
        batch_op.drop_column("like_count")
        batch_op.drop_column("follower_count")
