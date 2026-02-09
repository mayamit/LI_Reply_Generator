"""SQLAlchemy ORM model for the ReplyRecord table."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base

VALID_STATUSES = ("draft", "approved")


class ReplyRecord(Base):
    """Persistence for the draft → approved reply lifecycle."""

    __tablename__ = "reply_records"
    __table_args__ = (
        Index("ix_reply_records_created_date", "created_date"),
        Index("ix_reply_records_status", "status"),
        Index("ix_reply_records_author_name", "author_name"),
        CheckConstraint(
            "status IN ('draft', 'approved')",
            name="ck_reply_records_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    author_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    author_profile_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
    )
    post_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
    )
    post_text: Mapped[str] = mapped_column(Text, nullable=False)
    article_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_ref: Mapped[str | None] = mapped_column(
        String(2048), nullable=True,
    )
    preset_id: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="draft", server_default="draft",
    )
    created_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=False,
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
    )
    llm_model_identifier: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    llm_request_id: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
