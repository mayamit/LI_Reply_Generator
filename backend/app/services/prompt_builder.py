"""Deterministic prompt assembly from post context + preset.

This module transforms a validated PostContextPayload and a ReplyPreset into a
prompt string ready for LLM consumption.  The output is fully deterministic:
identical inputs always produce byte-for-byte identical output.

Usage::

    from backend.app.services.prompt_builder import build_prompt

    prompt_text, metadata = build_prompt(payload, preset)
"""

import logging
import re

from backend.app.models.post_context import PostContextPayload
from backend.app.models.presets import ReplyPreset, get_preset_by_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ARTICLE_CHARS: int = 12_000
"""Maximum character length for article_text before truncation."""

TRUNCATION_MARKER: str = "\n[…]"
"""Appended to article_text when truncated."""

_LENGTH_GUIDANCE: dict[str, str] = {
    "short": "Keep the reply concise — roughly 1–3 sentences.",
    "medium": "Aim for a medium-length reply — roughly 3–5 sentences.",
    "long": "A longer, more detailed reply is appropriate — roughly 5–8 sentences.",
}

# Regex: three or more consecutive newlines (with optional whitespace-only lines)
_EXCESS_BLANK_LINES = re.compile(r"(\n[ \t]*){3,}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in *text*.

    - Strip leading/trailing whitespace
    - Convert Windows newlines (``\\r\\n``) to ``\\n``
    - Collapse runs of >2 consecutive blank lines to exactly 2
    """
    text = text.strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text


def truncate_article(
    article_text: str,
    max_chars: int = MAX_ARTICLE_CHARS,
) -> tuple[str, bool, int]:
    """Truncate *article_text* if it exceeds *max_chars*.

    Returns ``(text, truncation_applied, original_length)``.
    """
    original_length = len(article_text)
    if original_length <= max_chars:
        return article_text, False, original_length
    truncated = article_text[:max_chars] + TRUNCATION_MARKER
    return truncated, True, original_length


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------


def build_prompt(
    payload: PostContextPayload,
    preset: ReplyPreset | None = None,
) -> tuple[str, dict[str, object]]:
    """Build a deterministic LLM prompt from *payload* and *preset*.

    If *preset* is ``None`` it is resolved from ``payload.preset_id``.

    Returns ``(prompt_text, prompt_metadata)``.

    Raises:
        ValueError: If the preset cannot be resolved.
    """
    if preset is None:
        preset = get_preset_by_id(payload.preset_id)
    if preset is None:
        raise ValueError(f"Unknown preset_id: {payload.preset_id}")

    metadata: dict[str, object] = {
        "preset_id": preset.id,
        "truncation_applied": False,
    }

    sections: list[str] = []

    # ── 1. Role / instructions ──────────────────────────────────────────
    role_lines = (
        "You are a LinkedIn reply assistant. Write a reply to the post below.\n"
        "The reply must be professional, authentic, and non-generic.\n"
        "Write in a natural LinkedIn comment style — no preamble, no quotes."
    )
    sections.append(role_lines)

    # ── 2. Preset directives ────────────────────────────────────────────
    length_line = _LENGTH_GUIDANCE.get(preset.length_bucket, "")
    preset_block = f"Tone: {preset.tone}\nIntent: {preset.intent}\n{length_line}"
    if preset.guidance_bullets:
        bullets = "\n".join(f"- {b}" for b in preset.guidance_bullets)
        preset_block += f"\nGuidance:\n{bullets}"
    sections.append(preset_block)

    # ── 3. Context ──────────────────────────────────────────────────────
    context_parts: list[str] = []

    if payload.author_name:
        author_line = f"Author: {payload.author_name}"
        if payload.author_profile_url:
            author_line += f" ({payload.author_profile_url})"
        context_parts.append(author_line)

    if payload.post_url:
        context_parts.append(f"Post URL: {payload.post_url}")

    context_parts.append(f"Post text:\n{payload.post_text}")

    if payload.article_text:
        article, truncated, original_length = truncate_article(payload.article_text)
        if truncated:
            metadata["truncation_applied"] = True
            metadata["original_article_length"] = original_length
        context_parts.append(f"Linked article text:\n{article}")

    if payload.image_ref:
        context_parts.append(
            f"User-provided image context (not directly visible to the model): {payload.image_ref}"
        )

    sections.append("\n".join(context_parts))

    # ── 4. Output requirements ──────────────────────────────────────────
    output_line = "Return only the reply text. No quotes, no preamble."
    if not preset.allow_hashtags:
        output_line += " Do not include hashtags."
    sections.append(output_line)

    # ── Assemble ────────────────────────────────────────────────────────
    prompt_text = normalize_whitespace("\n\n".join(sections))

    metadata["prompt_length"] = len(prompt_text)

    logger.info(
        "Prompt assembled: preset_id=%s length=%d",
        preset.id,
        len(prompt_text),
    )

    return prompt_text, metadata
