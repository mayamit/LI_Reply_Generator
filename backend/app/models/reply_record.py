"""SQLAlchemy ORM model for the ReplyRecord table."""

from datetime import datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class ReplyRecord(Base):
    """Minimal persistence for the draft → approved reply lifecycle (EPIC 1)."""

    __tablename__ = "reply_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    author_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_text: Mapped[str] = mapped_column(Text, nullable=False)
    article_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    preset_id: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    generated_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    llm_model_identifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_request_id: Mapped[str | None] = mapped_column(Text, nullable=True)
