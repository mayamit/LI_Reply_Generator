"""Reply preset definitions (EPIC 2 placeholder — hardcoded seed data)."""

from pydantic import BaseModel


class ReplyPreset(BaseModel):
    """A canned combination of tone, length, and intent for a LinkedIn reply."""

    id: str
    label: str
    tone: str
    length_bucket: str  # "short" | "medium" | "long"
    intent: str
    guidance_bullets: list[str] | None = None


DEFAULT_PRESETS: list[ReplyPreset] = [
    ReplyPreset(
        id="prof_short_agree",
        label="Professional – Short Agreement",
        tone="professional",
        length_bucket="short",
        intent="agree",
        guidance_bullets=[
            "Acknowledge the author's point directly",
            "Add a brief supporting observation",
        ],
    ),
    ReplyPreset(
        id="casual_medium_add",
        label="Casual – Medium Add-On",
        tone="casual",
        length_bucket="medium",
        intent="add_perspective",
        guidance_bullets=[
            "Use a conversational, approachable voice",
            "Offer an additional angle or personal experience",
        ],
    ),
    ReplyPreset(
        id="supportive_short_encourage",
        label="Supportive – Short Encouragement",
        tone="supportive",
        length_bucket="short",
        intent="encourage",
        guidance_bullets=[
            "Express genuine appreciation for the post",
            "Encourage the author to keep sharing",
        ],
    ),
    ReplyPreset(
        id="contrarian_medium_challenge",
        label="Contrarian – Medium Challenge",
        tone="contrarian",
        length_bucket="medium",
        intent="challenge",
        guidance_bullets=[
            "Respectfully present an alternative viewpoint",
            "Back up the counterpoint with reasoning",
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
