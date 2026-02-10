"""SQLAlchemy ORM model for the presets table."""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class PresetRecord(Base):
    """Persistent storage for reply presets."""

    __tablename__ = "presets"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    tone: Mapped[str] = mapped_column(String(50), nullable=False)
    length_bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_bullets: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_hashtags: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0",
    )
