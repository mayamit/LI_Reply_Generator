"""Reply preset definitions — seeded, read-only preset library (EPIC 2).

Presets are immutable at runtime.  Exactly one preset must have
``is_default=True``.  The library is validated at application startup
via :func:`validate_presets`.
"""

import logging
from enum import StrEnum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LengthBucket(StrEnum):
    short = "short"
    medium = "medium"
    long = "long"


class ReplyPreset(BaseModel):
    """A canned combination of tone, length, and intent for a LinkedIn reply."""

    id: str
    label: str
    tone: str
    length_bucket: LengthBucket
    intent: str
    guidance_bullets: list[str] | None = None
    allow_hashtags: bool = False
    is_default: bool = False


DEFAULT_PRESETS: list[ReplyPreset] = [
    # --- 1. Professional – Short Agreement (DEFAULT) ---
    ReplyPreset(
        id="prof_short_agree",
        label="Professional – Short Agreement",
        tone="professional",
        length_bucket=LengthBucket.short,
        intent="agree",
        is_default=True,
        guidance_bullets=[
            "Acknowledge the author's point directly",
            "Add a brief supporting observation",
        ],
    ),
    # --- 2. Casual – Medium Add-On ---
    ReplyPreset(
        id="casual_medium_add",
        label="Casual – Medium Add-On",
        tone="casual",
        length_bucket=LengthBucket.medium,
        intent="add_perspective",
        guidance_bullets=[
            "Use a conversational, approachable voice",
            "Offer an additional angle or personal experience",
        ],
    ),
    # --- 3. Supportive – Short Encouragement ---
    ReplyPreset(
        id="supportive_short_encourage",
        label="Supportive – Short Encouragement",
        tone="supportive",
        length_bucket=LengthBucket.short,
        intent="encourage",
        guidance_bullets=[
            "Express genuine appreciation for the post",
            "Encourage the author to keep sharing",
        ],
    ),
    # --- 4. Contrarian – Medium Challenge ---
    ReplyPreset(
        id="contrarian_medium_challenge",
        label="Contrarian – Medium Challenge",
        tone="contrarian",
        length_bucket=LengthBucket.medium,
        intent="challenge",
        guidance_bullets=[
            "Respectfully present an alternative viewpoint",
            "Back up the counterpoint with reasoning",
        ],
    ),
    # --- 5. Professional – Medium Insight ---
    ReplyPreset(
        id="prof_medium_insight",
        label="Professional – Medium Insight",
        tone="professional",
        length_bucket=LengthBucket.medium,
        intent="share_insight",
        guidance_bullets=[
            "Share a relevant professional insight or data point",
            "Connect the insight back to the original post",
        ],
    ),
    # --- 6. Casual – Short React ---
    ReplyPreset(
        id="casual_short_react",
        label="Casual – Short Reaction",
        tone="casual",
        length_bucket=LengthBucket.short,
        intent="react",
        guidance_bullets=[
            "Express a genuine, brief reaction",
            "Keep it conversational and authentic",
        ],
    ),
    # --- 7. Supportive – Medium Story ---
    ReplyPreset(
        id="supportive_medium_story",
        label="Supportive – Medium Personal Story",
        tone="supportive",
        length_bucket=LengthBucket.medium,
        intent="share_experience",
        guidance_bullets=[
            "Relate a brief personal or professional experience",
            "Show empathy and connection to the author's situation",
        ],
    ),
    # --- 8. Professional – Long Analysis ---
    ReplyPreset(
        id="prof_long_analysis",
        label="Professional – Long Analysis",
        tone="professional",
        length_bucket=LengthBucket.long,
        intent="analyze",
        guidance_bullets=[
            "Provide a structured, thoughtful analysis",
            "Reference specific points from the original post",
            "Offer a clear takeaway or recommendation",
        ],
    ),
]

_PRESET_MAP: dict[str, ReplyPreset] = {p.id: p for p in DEFAULT_PRESETS}


def get_preset_by_id(preset_id: str) -> ReplyPreset | None:
    """Return the preset matching *preset_id*, or ``None``."""
    return _PRESET_MAP.get(preset_id)


def get_preset_labels() -> dict[str, str]:
    """Return ``{id: label}`` for every available preset."""
    return {p.id: p.label for p in DEFAULT_PRESETS}


def get_default_preset() -> ReplyPreset:
    """Return the single default preset.

    Raises ``RuntimeError`` if no default is found (should never happen
    after :func:`validate_presets` passes at startup).
    """
    for p in DEFAULT_PRESETS:
        if p.is_default:
            return p
    raise RuntimeError("No default preset defined")


def validate_presets() -> None:
    """Validate the preset library at application startup.

    Checks:
    - All presets conform to the schema (guaranteed by Pydantic construction)
    - All IDs are unique
    - Exactly one preset is marked as default
    - ``length_bucket`` uses a valid enum value (enforced by ``LengthBucket``)

    Raises ``RuntimeError`` with a developer-facing message on failure.
    """
    if not DEFAULT_PRESETS:
        raise RuntimeError("Preset library is empty")

    # Unique IDs
    ids = [p.id for p in DEFAULT_PRESETS]
    if len(ids) != len(set(ids)):
        dupes = [pid for pid in ids if ids.count(pid) > 1]
        raise RuntimeError(f"Duplicate preset IDs: {set(dupes)}")

    # Exactly one default
    defaults = [p for p in DEFAULT_PRESETS if p.is_default]
    if len(defaults) == 0:
        raise RuntimeError("No preset is marked as default (is_default=True)")
    if len(defaults) > 1:
        raise RuntimeError(f"Multiple presets marked as default: {[p.id for p in defaults]}")

    logger.info(
        "validate_presets: %d presets loaded, default=%s",
        len(DEFAULT_PRESETS),
        defaults[0].id,
    )
