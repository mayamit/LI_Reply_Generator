"""Tests for the prompt builder module (Story 1.2)."""

import pytest
from backend.app.models.post_context import PostContextPayload
from backend.app.models.presets import ReplyPreset, get_preset_by_id
from backend.app.services.prompt_builder import (
    MAX_ARTICLE_CHARS,
    TRUNCATION_MARKER,
    build_prompt,
    normalize_whitespace,
    truncate_article,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_payload(**overrides: object) -> PostContextPayload:
    defaults: dict[str, object] = {
        "post_text": "This is a sample LinkedIn post for testing.",
        "preset_id": "prof_short_agree",
        "preset_label": "Professional – Short Agreement",
        "tone": "professional",
        "length_bucket": "short",
        "intent": "agree",
    }
    defaults.update(overrides)
    return PostContextPayload(**defaults)  # type: ignore[arg-type]


def _get_preset(preset_id: str = "prof_short_agree") -> ReplyPreset:
    preset = get_preset_by_id(preset_id)
    assert preset is not None
    return preset


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_identical_inputs_produce_identical_output(self) -> None:
        payload = _make_payload()
        preset = _get_preset()
        text_a, meta_a = build_prompt(payload, preset)
        text_b, meta_b = build_prompt(payload, preset)
        assert text_a == text_b
        assert meta_a == meta_b

    def test_determinism_with_all_optional_fields(self) -> None:
        payload = _make_payload(
            author_name="Jane Doe",
            author_profile_url="https://linkedin.com/in/janedoe",
            post_url="https://linkedin.com/posts/123",
            article_text="Some article content here.",
            image_ref="photo of a whiteboard",
        )
        preset = _get_preset()
        text_a, _ = build_prompt(payload, preset)
        text_b, _ = build_prompt(payload, preset)
        assert text_a == text_b


# ---------------------------------------------------------------------------
# Article truncation
# ---------------------------------------------------------------------------


class TestArticleTruncation:
    def test_short_article_not_truncated(self) -> None:
        text, truncated, orig = truncate_article("short text")
        assert text == "short text"
        assert truncated is False
        assert orig == len("short text")

    def test_long_article_truncated(self) -> None:
        long_text = "x" * (MAX_ARTICLE_CHARS + 500)
        text, truncated, orig = truncate_article(long_text)
        assert truncated is True
        assert orig == MAX_ARTICLE_CHARS + 500
        assert text.endswith(TRUNCATION_MARKER)
        assert len(text) == MAX_ARTICLE_CHARS + len(TRUNCATION_MARKER)

    def test_truncation_metadata_in_build_prompt(self) -> None:
        payload = _make_payload(article_text="y" * (MAX_ARTICLE_CHARS + 100))
        _, meta = build_prompt(payload)
        assert meta["truncation_applied"] is True
        assert meta["original_article_length"] == MAX_ARTICLE_CHARS + 100

    def test_no_truncation_metadata_when_short(self) -> None:
        payload = _make_payload(article_text="brief article")
        _, meta = build_prompt(payload)
        assert meta["truncation_applied"] is False
        assert "original_article_length" not in meta


# ---------------------------------------------------------------------------
# Article omitted when None / empty
# ---------------------------------------------------------------------------


class TestArticleOmitted:
    def test_none_article_omitted(self) -> None:
        payload = _make_payload(article_text=None)
        text, _ = build_prompt(payload)
        assert "Linked article text" not in text

    def test_empty_article_omitted(self) -> None:
        payload = _make_payload(article_text="")
        text, _ = build_prompt(payload)
        assert "Linked article text" not in text


# ---------------------------------------------------------------------------
# Image ref handling
# ---------------------------------------------------------------------------


class TestImageRef:
    def test_image_ref_included_as_user_context(self) -> None:
        payload = _make_payload(image_ref="diagram of a workflow")
        text, _ = build_prompt(payload)
        assert "diagram of a workflow" in text
        assert "not directly visible to the model" in text

    def test_no_image_ref_no_image_section(self) -> None:
        payload = _make_payload(image_ref=None)
        text, _ = build_prompt(payload)
        assert "image context" not in text


# ---------------------------------------------------------------------------
# Preset missing / invalid
# ---------------------------------------------------------------------------


class TestPresetErrors:
    def test_invalid_preset_raises(self) -> None:
        payload = _make_payload(preset_id="nonexistent")
        with pytest.raises(ValueError, match="Unknown preset_id"):
            build_prompt(payload)

    def test_explicit_none_preset_resolved_from_payload(self) -> None:
        payload = _make_payload()
        text, meta = build_prompt(payload, preset=None)
        assert meta["preset_id"] == "prof_short_agree"
        assert len(text) > 0


# ---------------------------------------------------------------------------
# Whitespace normalization
# ---------------------------------------------------------------------------


class TestWhitespaceNormalization:
    def test_strip_leading_trailing(self) -> None:
        assert normalize_whitespace("  hello  ") == "hello"

    def test_windows_newlines_converted(self) -> None:
        result = normalize_whitespace("line1\r\nline2\r\nline3")
        assert "\r" not in result
        assert result == "line1\nline2\nline3"

    def test_excess_blank_lines_collapsed(self) -> None:
        result = normalize_whitespace("a\n\n\n\n\nb")
        assert result == "a\n\nb"

    def test_two_blank_lines_preserved(self) -> None:
        result = normalize_whitespace("a\n\nb")
        assert result == "a\n\nb"

    def test_normalization_applied_to_prompt(self) -> None:
        payload = _make_payload(post_text="Test post\r\nwith windows\r\nnewlines")
        text, _ = build_prompt(payload)
        assert "\r" not in text


# ---------------------------------------------------------------------------
# Prompt content requirements
# ---------------------------------------------------------------------------


class TestPromptContent:
    def test_post_text_always_present(self) -> None:
        payload = _make_payload()
        text, _ = build_prompt(payload)
        assert payload.post_text in text

    def test_author_name_included_when_present(self) -> None:
        payload = _make_payload(author_name="Alice Smith")
        text, _ = build_prompt(payload)
        assert "Alice Smith" in text

    def test_author_profile_url_included_with_name(self) -> None:
        payload = _make_payload(
            author_name="Alice",
            author_profile_url="https://linkedin.com/in/alice",
        )
        text, _ = build_prompt(payload)
        assert "https://linkedin.com/in/alice" in text

    def test_preset_tone_and_intent_in_prompt(self) -> None:
        payload = _make_payload()
        text, _ = build_prompt(payload)
        assert "professional" in text
        assert "agree" in text

    def test_no_hashtags_instruction(self) -> None:
        payload = _make_payload()
        text, _ = build_prompt(payload)
        assert "no hashtags" in text.lower()

    def test_metadata_includes_prompt_length(self) -> None:
        payload = _make_payload()
        _, meta = build_prompt(payload)
        assert "prompt_length" in meta
        assert isinstance(meta["prompt_length"], int)
        assert meta["prompt_length"] > 0
