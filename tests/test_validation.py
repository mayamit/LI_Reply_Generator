"""Tests for the shared validation service."""

from backend.app.models.post_context import PostContextInput
from backend.app.services.validation import check_linkedin_url, validate_and_build_payload

# --- check_linkedin_url ---


def test_linkedin_url_valid() -> None:
    assert check_linkedin_url("https://www.linkedin.com/in/janedoe") is None


def test_linkedin_url_subdomain() -> None:
    assert check_linkedin_url("https://linkedin.com/posts/123") is None


def test_linkedin_url_invalid() -> None:
    result = check_linkedin_url("https://example.com/foo")
    assert result is not None
    assert "not appear to be a LinkedIn link" in result


def test_linkedin_url_none() -> None:
    assert check_linkedin_url(None) is None


def test_linkedin_url_empty() -> None:
    assert check_linkedin_url("") is None


def test_linkedin_url_malformed() -> None:
    result = check_linkedin_url("not-a-url")
    assert result is not None


# --- validate_and_build_payload ---


def test_payload_build_success() -> None:
    ctx = PostContextInput(post_text="A" * 20, preset_id="prof_short_agree")
    payload, errors = validate_and_build_payload(ctx)
    assert errors == []
    assert payload is not None
    assert payload.preset_label == "Professional – Short Agreement"
    assert payload.tone == "professional"
    assert payload.validation_warnings == []


def test_payload_build_with_warnings() -> None:
    ctx = PostContextInput(
        post_text="A" * 20,
        preset_id="prof_short_agree",
        author_profile_url="https://example.com/profile",
        post_url="https://twitter.com/status/123",
    )
    payload, errors = validate_and_build_payload(ctx)
    assert errors == []
    assert payload is not None
    assert len(payload.validation_warnings) == 2


def test_payload_build_invalid_preset() -> None:
    ctx = PostContextInput(post_text="A" * 20, preset_id="nonexistent")
    payload, errors = validate_and_build_payload(ctx)
    assert payload is None
    assert len(errors) == 1
    assert "Unknown preset_id" in errors[0]
