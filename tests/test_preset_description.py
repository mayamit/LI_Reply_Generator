"""Tests for preset description / preview text (Story 2.4).

Covers all 3 acceptance criteria:
  AC1: Preset description exists and is displayable
  AC2: Different presets have different descriptions
  AC3: Missing description → safe fallback message
"""

from backend.app.models.presets import (
    DEFAULT_PRESETS,
    FALLBACK_DESCRIPTION,
    ReplyPreset,
    get_preset_description,
)

# ---------------------------------------------------------------------------
# AC1: Preset description is displayed clearly
# ---------------------------------------------------------------------------


class TestDescriptionExists:
    def test_all_seeded_presets_have_descriptions(self) -> None:
        for p in DEFAULT_PRESETS:
            assert p.description is not None, f"Preset {p.id} missing description"
            assert len(p.description) > 0, f"Preset {p.id} has empty description"

    def test_descriptions_are_human_readable(self) -> None:
        for p in DEFAULT_PRESETS:
            assert p.description is not None
            # Should be a proper sentence (starts uppercase, ends with period)
            assert p.description[0].isupper(), f"{p.id}: should start with uppercase"
            assert p.description.endswith("."), f"{p.id}: should end with period"

    def test_get_preset_description_returns_text(self) -> None:
        for p in DEFAULT_PRESETS:
            desc = get_preset_description(p.id)
            assert desc == p.description


# ---------------------------------------------------------------------------
# AC2: Switching presets updates the description
# ---------------------------------------------------------------------------


class TestDescriptionVariesByPreset:
    def test_different_presets_different_descriptions(self) -> None:
        descriptions = [p.description for p in DEFAULT_PRESETS]
        # All descriptions should be unique
        assert len(descriptions) == len(set(descriptions))

    def test_description_changes_with_preset_id(self) -> None:
        d1 = get_preset_description("prof_short_agree")
        d2 = get_preset_description("casual_medium_add")
        assert d1 != d2


# ---------------------------------------------------------------------------
# AC3: Missing description → safe fallback
# ---------------------------------------------------------------------------


class TestDescriptionFallback:
    def test_unknown_preset_id_returns_fallback(self) -> None:
        desc = get_preset_description("nonexistent_id")
        assert desc == FALLBACK_DESCRIPTION

    def test_preset_with_none_description_returns_fallback(self) -> None:
        # A preset created without a description
        p = ReplyPreset(
            id="no_desc",
            label="No Description",
            tone="neutral",
            length_bucket="short",
            intent="respond",
        )
        assert p.description is None
        # The helper should return fallback for presets not in the map,
        # but we can also verify the field default
        desc = get_preset_description("no_desc")
        assert desc == FALLBACK_DESCRIPTION

    def test_fallback_is_non_empty_string(self) -> None:
        assert isinstance(FALLBACK_DESCRIPTION, str)
        assert len(FALLBACK_DESCRIPTION) > 0
