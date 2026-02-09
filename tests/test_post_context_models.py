"""Tests for PostContextInput Pydantic model validation."""

import pytest
from backend.app.models.post_context import PostContextInput
from pydantic import ValidationError

# --- Valid inputs ---


def test_valid_minimal_input() -> None:
    ctx = PostContextInput(post_text="A" * 10, preset_id="prof_short_agree")
    assert ctx.post_text == "A" * 10
    assert ctx.preset_id == "prof_short_agree"
    assert ctx.author_name is None


def test_valid_complete_input() -> None:
    ctx = PostContextInput(
        post_text="This is a valid LinkedIn post with enough characters.",
        preset_id="casual_medium_add",
        author_name="Jane Doe",
        author_profile_url="https://linkedin.com/in/janedoe",
        post_url="https://linkedin.com/posts/12345",
        article_text="Some article body text here.",
        image_ref="photo of a sunset",
    )
    assert ctx.author_name == "Jane Doe"
    assert ctx.post_url == "https://linkedin.com/posts/12345"


# --- post_text validation ---


def test_post_text_required() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PostContextInput(preset_id="prof_short_agree")  # type: ignore[call-arg]
    assert any(e["loc"] == ("post_text",) for e in exc_info.value.errors())


def test_post_text_min_length() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PostContextInput(post_text="short", preset_id="prof_short_agree")
    errors = exc_info.value.errors()
    assert any("at least 10" in e["msg"] for e in errors)


def test_post_text_max_length() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PostContextInput(post_text="x" * 20_001, preset_id="prof_short_agree")
    errors = exc_info.value.errors()
    assert any("at most 20000" in e["msg"] for e in errors)


# --- URL max length ---


def test_url_max_length() -> None:
    with pytest.raises(ValidationError):
        PostContextInput(
            post_text="A" * 10,
            preset_id="prof_short_agree",
            author_profile_url="https://example.com/" + "a" * 2_000,
        )


# --- Whitespace stripping ---


def test_whitespace_stripped_from_post_text() -> None:
    ctx = PostContextInput(post_text="  hello world!  ", preset_id="x")
    assert ctx.post_text == "hello world!"


def test_whitespace_stripped_from_urls() -> None:
    ctx = PostContextInput(
        post_text="A" * 10,
        preset_id="x",
        author_profile_url="  https://linkedin.com/in/foo  ",
        post_url="  https://linkedin.com/posts/123  ",
    )
    assert ctx.author_profile_url == "https://linkedin.com/in/foo"
    assert ctx.post_url == "https://linkedin.com/posts/123"


def test_whitespace_stripped_from_author_name() -> None:
    ctx = PostContextInput(post_text="A" * 10, preset_id="x", author_name="  Alice  ")
    assert ctx.author_name == "Alice"
