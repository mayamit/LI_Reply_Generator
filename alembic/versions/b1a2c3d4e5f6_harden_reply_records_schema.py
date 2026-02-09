"""harden reply_records schema: add indexes and status constraint

Revision ID: b1a2c3d4e5f6
Revises: 0ce53af38a4f
Create Date: 2026-02-09 20:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1a2c3d4e5f6"
down_revision: str | None = "0ce53af38a4f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_reply_records_created_date",
        "reply_records",
        ["created_date"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_reply_records_status",
        "reply_records",
        ["status"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_reply_records_author_name",
        "reply_records",
        ["author_name"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_reply_records_author_name", table_name="reply_records")
    op.drop_index("ix_reply_records_status", table_name="reply_records")
    op.drop_index("ix_reply_records_created_date", table_name="reply_records")
