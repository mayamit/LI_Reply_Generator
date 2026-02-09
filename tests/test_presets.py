"""Tests for preset schema, validation, and default enforcement (Story 2.1)."""

import pytest
from backend.app.models.presets import (
    DEFAULT_PRESETS,
    LengthBucket,
    ReplyPreset,
    get_default_preset,
    get_preset_by_id,
    get_preset_labels,
    validate_presets,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# AC1: All presets conform to schema
# ---------------------------------------------------------------------------


class TestSchemaConformance:
    def test_all_presets_have_required_fields(self) -> None:
        for p in DEFAULT_PRESETS:
            assert p.id
            assert p.label
            assert p.tone
            assert p.intent
            assert p.length_bucket in LengthBucket

    def test_length_bucket_is_enum(self) -> None:
        for p in DEFAULT_PRESETS:
            assert isinstance(p.length_bucket, LengthBucket)

    def test_allow_hashtags_is_bool(self) -> None:
        for p in DEFAULT_PRESETS:
            assert isinstance(p.allow_hashtags, bool)

    def test_invalid_length_bucket_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReplyPreset(
                id="bad",
                label="Bad",
                tone="x",
                length_bucket="tiny",  # type: ignore[arg-type]
                intent="y",
            )

    def test_minimum_preset_count(self) -> None:
        assert len(DEFAULT_PRESETS) >= 5


# ---------------------------------------------------------------------------
# AC2: Exactly one preset marked as default
# ---------------------------------------------------------------------------


class TestDefaultPreset:
    def test_exactly_one_default(self) -> None:
        defaults = [p for p in DEFAULT_PRESETS if p.is_default]
        assert len(defaults) == 1

    def test_get_default_preset_returns_it(self) -> None:
        default = get_default_preset()
        assert default.is_default is True
        assert default.id


# ---------------------------------------------------------------------------
# AC3: IDs are unique and stable
# ---------------------------------------------------------------------------


class TestUniqueIds:
    def test_all_ids_unique(self) -> None:
        ids = [p.id for p in DEFAULT_PRESETS]
        assert len(ids) == len(set(ids))

    def test_ids_are_deterministic_strings(self) -> None:
        for p in DEFAULT_PRESETS:
            assert isinstance(p.id, str)
            assert len(p.id) > 0
            assert " " not in p.id  # no spaces in IDs


# ---------------------------------------------------------------------------
# AC4: Missing/invalid field → startup fails
# ---------------------------------------------------------------------------


class TestValidationFailures:
    def test_validate_presets_passes(self) -> None:
        # Should not raise
        validate_presets()

    def test_duplicate_ids_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        duped = list(DEFAULT_PRESETS) + [DEFAULT_PRESETS[0]]
        monkeypatch.setattr("backend.app.models.presets.DEFAULT_PRESETS", duped)
        with pytest.raises(RuntimeError, match="Duplicate preset IDs"):
            validate_presets()

    def test_no_default_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        no_defaults = [p.model_copy(update={"is_default": False}) for p in DEFAULT_PRESETS]
        monkeypatch.setattr("backend.app.models.presets.DEFAULT_PRESETS", no_defaults)
        with pytest.raises(RuntimeError, match="No preset is marked as default"):
            validate_presets()

    def test_multiple_defaults_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        multi = [p.model_copy(update={"is_default": True}) for p in DEFAULT_PRESETS]
        monkeypatch.setattr("backend.app.models.presets.DEFAULT_PRESETS", multi)
        with pytest.raises(RuntimeError, match="Multiple presets marked as default"):
            validate_presets()

    def test_empty_library_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("backend.app.models.presets.DEFAULT_PRESETS", [])
        with pytest.raises(RuntimeError, match="empty"):
            validate_presets()


# ---------------------------------------------------------------------------
# AC5: Access by ID returns correct preset deterministically
# ---------------------------------------------------------------------------


class TestAccessById:
    def test_all_presets_accessible_by_id(self) -> None:
        for p in DEFAULT_PRESETS:
            result = get_preset_by_id(p.id)
            assert result is not None
            assert result.id == p.id
            assert result.label == p.label

    def test_unknown_id_returns_none(self) -> None:
        assert get_preset_by_id("nonexistent_id") is None

    def test_get_preset_labels_returns_all(self) -> None:
        labels = get_preset_labels()
        assert len(labels) == len(DEFAULT_PRESETS)
        for p in DEFAULT_PRESETS:
            assert p.id in labels
            assert labels[p.id] == p.label


# ---------------------------------------------------------------------------
# AC6: Default preset used when no selection made
# ---------------------------------------------------------------------------


class TestDefaultFallback:
    def test_default_preset_is_stable(self) -> None:
        d1 = get_default_preset()
        d2 = get_default_preset()
        assert d1.id == d2.id
        assert d1 == d2
