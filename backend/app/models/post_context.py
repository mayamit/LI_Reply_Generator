"""Pydantic models for capturing and validating LinkedIn post context."""

from pydantic import BaseModel, Field, field_validator


class PostContextInput(BaseModel):
    """Raw input from the user (Streamlit form or API request)."""

    post_text: str = Field(..., min_length=10, max_length=20_000)
    preset_id: str
    author_name: str | None = Field(default=None, max_length=200)
    author_profile_url: str | None = Field(default=None, max_length=2_000)
    post_url: str | None = Field(default=None, max_length=2_000)
    article_text: str | None = Field(default=None, max_length=50_000)
    image_ref: str | None = Field(default=None, max_length=2_000)

    @field_validator(
        "post_text",
        "author_name",
        "article_text",
        mode="before",
    )
    @classmethod
    def strip_text(cls, v: str | None) -> str | None:
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
    validation_warnings: list[str] = Field(default_factory=list)
