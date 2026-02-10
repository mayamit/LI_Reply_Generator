"""Shared validation logic for post context inputs.

Used by both the FastAPI route and the Streamlit UI so that validation
rules live in one place and are testable without framework dependencies.
"""

from urllib.parse import urlparse

from backend.app.models.post_context import (
    ARTICLE_TEXT_WARN_LENGTH,
    PostContextInput,
    PostContextPayload,
)
from backend.app.models.presets import get_preset_by_id


def check_linkedin_url(url: str | None) -> str | None:
    """Return a warning string if *url* is not a LinkedIn URL, else ``None``.

    ``None`` or empty input is silently accepted (field is optional).
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
    except Exception:
        return f"Could not parse URL: {url}"
    if not host.endswith("linkedin.com"):
        return f"URL does not appear to be a LinkedIn link: {url}"
    return None


def validate_and_build_payload(
    ctx: PostContextInput,
) -> tuple[PostContextPayload | None, list[str]]:
    """Validate a :class:`PostContextInput` and build the downstream payload.

    Returns ``(payload, errors)`` where *errors* is empty on success.
    Soft issues (non-LinkedIn URLs) are surfaced as ``validation_warnings``
    on the payload rather than hard errors.
    """
    errors: list[str] = []

    preset = get_preset_by_id(ctx.preset_id)
    if preset is None:
        errors.append(f"Unknown preset_id: {ctx.preset_id}")
        return None, errors

    warnings: list[str] = []

    # Soft warning for large article_text
    if ctx.article_text and len(ctx.article_text) > ARTICLE_TEXT_WARN_LENGTH:
        warnings.append(
            f"Article text is long ({len(ctx.article_text):,} chars). "
            f"Very long articles may reduce reply quality or increase latency."
        )

    for url_value, field_label in [
        (ctx.author_profile_url, "Author profile URL"),
        (ctx.post_url, "Post URL"),
    ]:
        msg = check_linkedin_url(url_value)
        if msg:
            warnings.append(f"{field_label}: {msg}")

    payload = PostContextPayload(
        post_text=ctx.post_text,
        preset_id=preset.id,
        preset_label=preset.label,
        tone=preset.tone,
        length_bucket=preset.length_bucket,
        intent=preset.intent,
        author_name=ctx.author_name,
        author_profile_url=ctx.author_profile_url,
        post_url=ctx.post_url,
        article_text=ctx.article_text,
        image_ref=ctx.image_ref,
        follower_count=ctx.follower_count,
        like_count=ctx.like_count,
        comment_count=ctx.comment_count,
        repost_count=ctx.repost_count,
        validation_warnings=warnings,
    )
    return payload, []
