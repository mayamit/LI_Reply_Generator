"""Tests for Story 5.3: Input quality guardrails.

Covers acceptance criteria:
  AC1: article_text exceeds limit → warning
  AC2: URLs exceed max length → validation prevents submission
  AC3: Excessive whitespace → normalized consistently
  AC4: Validation errors are specific and actionable
"""

import pytest
from backend.app.models.post_context import (
    ARTICLE_TEXT_WARN_LENGTH,
    PostContextInput,
    normalize_whitespace,
)
from backend.app.services.validation import validate_and_build_payload
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# AC1: article_text exceeds configured limit → warning
# ---------------------------------------------------------------------------


class TestArticleTextWarning:
    def test_short_article_no_warning(self) -> None:
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
            article_text="Short article.",
        )
        payload, errors = validate_and_build_payload(ctx)
        assert not errors
        assert payload is not None
        assert not any("long" in w.lower() for w in payload.validation_warnings)

    def test_long_article_triggers_warning(self) -> None:
        long_article = "x" * (ARTICLE_TEXT_WARN_LENGTH + 1)
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
            article_text=long_article,
        )
        payload, errors = validate_and_build_payload(ctx)
        assert not errors
        assert payload is not None
        assert any("long" in w.lower() for w in payload.validation_warnings)

    def test_warning_includes_char_count(self) -> None:
        length = ARTICLE_TEXT_WARN_LENGTH + 500
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
            article_text="a" * length,
        )
        payload, errors = validate_and_build_payload(ctx)
        assert payload is not None
        warning_text = " ".join(payload.validation_warnings)
        assert str(length) in warning_text.replace(",", "")

    def test_article_at_threshold_no_warning(self) -> None:
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
            article_text="a" * ARTICLE_TEXT_WARN_LENGTH,
        )
        payload, errors = validate_and_build_payload(ctx)
        assert payload is not None
        assert not any("long" in w.lower() for w in payload.validation_warnings)

    def test_article_above_hard_limit_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PostContextInput(
                post_text="Test post with enough characters",
                preset_id="prof_short_agree",
                article_text="a" * 50_001,
            )

    def test_no_article_no_warning(self) -> None:
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
        )
        payload, errors = validate_and_build_payload(ctx)
        assert payload is not None
        assert not any("article" in w.lower() for w in payload.validation_warnings)


# ---------------------------------------------------------------------------
# AC2: URLs exceed max length → validation prevents submission
# ---------------------------------------------------------------------------


class TestUrlMaxLength:
    def test_url_within_limit_accepted(self) -> None:
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
            post_url="https://linkedin.com/posts/" + "a" * 100,
        )
        assert ctx.post_url is not None

    def test_url_exceeds_limit_rejected(self) -> None:
        with pytest.raises(ValidationError, match="post_url"):
            PostContextInput(
                post_text="Test post with enough characters",
                preset_id="prof_short_agree",
                post_url="https://example.com/" + "a" * 2_000,
            )

    def test_profile_url_exceeds_limit_rejected(self) -> None:
        with pytest.raises(ValidationError, match="author_profile_url"):
            PostContextInput(
                post_text="Test post with enough characters",
                preset_id="prof_short_agree",
                author_profile_url="https://example.com/" + "a" * 2_000,
            )

    def test_image_ref_exceeds_limit_rejected(self) -> None:
        with pytest.raises(ValidationError, match="image_ref"):
            PostContextInput(
                post_text="Test post with enough characters",
                preset_id="prof_short_agree",
                image_ref="a" * 2_001,
            )

    def test_author_name_exceeds_limit_rejected(self) -> None:
        with pytest.raises(ValidationError, match="author_name"):
            PostContextInput(
                post_text="Test post with enough characters",
                preset_id="prof_short_agree",
                author_name="a" * 201,
            )


# ---------------------------------------------------------------------------
# AC3: Excessive whitespace → normalized consistently
# ---------------------------------------------------------------------------


class TestWhitespaceNormalization:
    def test_normalize_whitespace_function(self) -> None:
        assert normalize_whitespace("  hello   world  ") == "hello world"

    def test_collapse_multiple_spaces(self) -> None:
        assert normalize_whitespace("a    b    c") == "a b c"

    def test_collapse_tabs(self) -> None:
        assert normalize_whitespace("a\t\tb") == "a b"

    def test_preserve_single_newlines(self) -> None:
        result = normalize_whitespace("line1\nline2")
        assert "line1\nline2" == result

    def test_collapse_excessive_newlines(self) -> None:
        result = normalize_whitespace("line1\n\n\n\n\nline2")
        assert result == "line1\n\nline2"

    def test_strip_leading_trailing(self) -> None:
        assert normalize_whitespace("  text  ") == "text"

    def test_post_text_normalized_on_input(self) -> None:
        ctx = PostContextInput(
            post_text="  This   has   excessive    whitespace  ",
            preset_id="prof_short_agree",
        )
        assert "  " not in ctx.post_text
        assert ctx.post_text == "This has excessive whitespace"

    def test_article_text_normalized_on_input(self) -> None:
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
            article_text="  Article   with   spaces  ",
        )
        assert ctx.article_text == "Article with spaces"

    def test_empty_after_normalization_still_fails_min_length(self) -> None:
        with pytest.raises(ValidationError):
            PostContextInput(
                post_text="   ",
                preset_id="prof_short_agree",
            )


# ---------------------------------------------------------------------------
# AC4: Validation errors are specific and actionable
# ---------------------------------------------------------------------------


class TestActionableErrors:
    def test_post_text_too_short_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            PostContextInput(
                post_text="short",
                preset_id="prof_short_agree",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("post_text",) for e in errors)

    def test_post_text_too_long_error(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            PostContextInput(
                post_text="a" * 20_001,
                preset_id="prof_short_agree",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("post_text",) for e in errors)

    def test_field_hints_in_streamlit_source(self) -> None:
        """Verify actionable hints are defined for key fields."""
        import os

        generate_page = os.path.join(
            os.path.dirname(__file__), os.pardir, "pages", "0_Generate.py",
        )
        source = open(generate_page).read()
        assert "_FIELD_HINTS" in source
        assert "post_text" in source
        assert "article_text" in source

    def test_url_stripped_before_validation(self) -> None:
        ctx = PostContextInput(
            post_text="Test post with enough characters",
            preset_id="prof_short_agree",
            post_url="  https://linkedin.com/post/123  ",
        )
        assert ctx.post_url == "https://linkedin.com/post/123"
