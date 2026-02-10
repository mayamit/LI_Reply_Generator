"""Pydantic models for capturing and validating LinkedIn post context."""

import re

from pydantic import BaseModel, Field, field_validator

# Soft warning threshold for article_text length.
# Inputs above this get a warning; the hard limit (50k) still applies.
ARTICLE_TEXT_WARN_LENGTH = 10_000

_MULTI_WHITESPACE = re.compile(r"[^\S\n]+")
_MULTI_NEWLINES = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces/tabs (preserving single newlines)."""
    text = text.strip()
    text = _MULTI_WHITESPACE.sub(" ", text)
    text = _MULTI_NEWLINES.sub("\n\n", text)
    return text


class PostContextInput(BaseModel):
    """Raw input from the user (Streamlit form or API request)."""

    post_text: str = Field(..., min_length=10, max_length=20_000)
    preset_id: str
    author_name: str | None = Field(default=None, max_length=200)
    author_profile_url: str | None = Field(default=None, max_length=2_000)
    post_url: str | None = Field(default=None, max_length=2_000)
    article_text: str | None = Field(default=None, max_length=50_000)
    image_ref: str | None = Field(default=None, max_length=2_000)
    follower_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    repost_count: int | None = Field(default=None, ge=0)

    @field_validator(
        "post_text",
        "article_text",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, v: str | None) -> str | None:
        """Strip and normalize whitespace in text fields."""
        if isinstance(v, str):
            return normalize_whitespace(v)
        return v

    @field_validator("author_name", mode="before")
    @classmethod
    def strip_author_name(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator(
        "author_profile_url",
        "post_url",
        "image_ref",
        mode="before",
    )
    @classmethod
    def strip_url(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            return v.strip()
        return v


class PostContextPayload(BaseModel):
    """Validated output ready for downstream prompt assembly."""

    post_text: str
    preset_id: str
    preset_label: str
    tone: str
    length_bucket: str
    intent: str
    author_name: str | None = None
    author_profile_url: str | None = None
    post_url: str | None = None
    article_text: str | None = None
    image_ref: str | None = None
    follower_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    repost_count: int | None = None
    validation_warnings: list[str] = Field(default_factory=list)
