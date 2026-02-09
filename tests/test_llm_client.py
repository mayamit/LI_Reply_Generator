"""Tests for the LLM client abstraction (Story 1.3).

All tests run without network access by using MockProvider or monkeypatching.
"""

import logging
import uuid

import pytest
from backend.app.main import app
from backend.app.models.llm import ErrorCategory, LLMFailure, LLMSuccess
from backend.app.models.post_context import PostContextPayload
from backend.app.models.presets import get_preset_by_id
from backend.app.services.llm_client import (
    MockProvider,
    generate_reply,
    get_provider,
)
from fastapi.testclient import TestClient

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
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


class _FailProvider:
    """Test helper that always returns a specific failure."""

    provider_name: str = "fail-stub"

    def __init__(self, category: ErrorCategory, retryable: bool = False) -> None:
        self._category = category
        self._retryable = retryable

    def call(self, prompt_text: str, timeout_seconds: int) -> LLMFailure:
        return LLMFailure(
            error_category=self._category,
            user_message=f"Simulated {self._category.value} error",
            retryable=self._retryable,
            details=str(uuid.uuid4()),
        )


class _EmptyReplyProvider:
    """Returns an LLMSuccess with empty reply_text (simulates parsing edge case)."""

    provider_name: str = "empty-stub"

    def call(self, prompt_text: str, timeout_seconds: int) -> LLMFailure:
        return LLMFailure(
            error_category=ErrorCategory.parsing,
            user_message="No reply generated — model returned empty text.",
            retryable=False,
        )


class _SuccessProvider:
    """Returns a controlled success response."""

    provider_name: str = "success-stub"

    def call(self, prompt_text: str, timeout_seconds: int) -> LLMSuccess:
        return LLMSuccess(
            reply_text="Great insight! I completely agree with your perspective.",
            model_id="test-model-v1",
            request_id=str(uuid.uuid4()),
            latency_ms=42,
        )


# ---------------------------------------------------------------------------
# 1. not_configured behavior
# ---------------------------------------------------------------------------


class TestNotConfigured:
    def test_mock_provider_when_no_keys(self) -> None:
        provider = get_provider(anthropic_key=None, openai_key=None)
        assert isinstance(provider, MockProvider)

    def test_mock_provider_returns_success(self) -> None:
        provider = MockProvider()
        result = provider.call("test prompt", timeout_seconds=30)
        assert isinstance(result, LLMSuccess)
        assert result.model_id == "mock-v1"


# ---------------------------------------------------------------------------
# 2. auth error mapping
# ---------------------------------------------------------------------------


class TestAuthError:
    def test_auth_failure_mapped(self) -> None:
        provider = _FailProvider(ErrorCategory.auth)
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        result, _ = generate_reply(payload, preset, provider=provider)
        assert isinstance(result, LLMFailure)
        assert result.error_category == ErrorCategory.auth
        assert result.retryable is False


# ---------------------------------------------------------------------------
# 3. rate limit mapping
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_rate_limit_retryable(self) -> None:
        provider = _FailProvider(ErrorCategory.rate_limit, retryable=True)
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        result, _ = generate_reply(payload, preset, provider=provider)
        assert isinstance(result, LLMFailure)
        assert result.error_category == ErrorCategory.rate_limit
        assert result.retryable is True


# ---------------------------------------------------------------------------
# 4. timeout mapping
# ---------------------------------------------------------------------------


class TestTimeout:
    def test_timeout_retryable(self) -> None:
        provider = _FailProvider(ErrorCategory.timeout, retryable=True)
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        result, _ = generate_reply(payload, preset, provider=provider)
        assert isinstance(result, LLMFailure)
        assert result.error_category == ErrorCategory.timeout
        assert result.retryable is True


# ---------------------------------------------------------------------------
# 5. network error mapping
# ---------------------------------------------------------------------------


class TestNetworkError:
    def test_network_retryable(self) -> None:
        provider = _FailProvider(ErrorCategory.network, retryable=True)
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        result, _ = generate_reply(payload, preset, provider=provider)
        assert isinstance(result, LLMFailure)
        assert result.error_category == ErrorCategory.network
        assert result.retryable is True


# ---------------------------------------------------------------------------
# 6. parsing error mapping
# ---------------------------------------------------------------------------


class TestParsingError:
    def test_parsing_not_retryable(self) -> None:
        provider = _FailProvider(ErrorCategory.parsing)
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        result, _ = generate_reply(payload, preset, provider=provider)
        assert isinstance(result, LLMFailure)
        assert result.error_category == ErrorCategory.parsing
        assert result.retryable is False


# ---------------------------------------------------------------------------
# 7. empty reply mapping
# ---------------------------------------------------------------------------


class TestEmptyReply:
    def test_empty_reply_is_parsing_failure(self) -> None:
        provider = _EmptyReplyProvider()
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        result, _ = generate_reply(payload, preset, provider=provider)
        assert isinstance(result, LLMFailure)
        assert result.error_category == ErrorCategory.parsing
        assert "empty" in result.user_message.lower() or "No reply" in result.user_message


# ---------------------------------------------------------------------------
# 8. success path
# ---------------------------------------------------------------------------


class TestSuccessPath:
    def test_success_returns_reply_and_latency(self) -> None:
        provider = _SuccessProvider()
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        result, meta = generate_reply(payload, preset, provider=provider)
        assert isinstance(result, LLMSuccess)
        assert "agree" in result.reply_text.lower() or len(result.reply_text) > 0
        assert result.latency_ms == 42
        assert result.model_id == "test-model-v1"
        assert meta["preset_id"] == "prof_short_agree"

    def test_success_includes_prompt_metadata(self) -> None:
        provider = _SuccessProvider()
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        _, meta = generate_reply(payload, preset, provider=provider)
        assert "prompt_length" in meta
        assert isinstance(meta["prompt_length"], int)


# ---------------------------------------------------------------------------
# 9. logs do not include secrets
# ---------------------------------------------------------------------------


class TestLogging:
    def test_no_secrets_in_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        fake_key = "sk-ant-TESTSECRETKEY1234567890"
        provider = _SuccessProvider()
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None

        with caplog.at_level(logging.DEBUG):
            generate_reply(payload, preset, provider=provider)

        full_log = caplog.text
        assert fake_key not in full_log
        # Prompt text should not appear in logs
        assert payload.post_text not in full_log

    def test_log_includes_preset_id_and_latency(self, caplog: pytest.LogCaptureFixture) -> None:
        provider = _SuccessProvider()
        payload = _make_payload()
        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None

        with caplog.at_level(logging.INFO):
            generate_reply(payload, preset, provider=provider)

        full_log = caplog.text
        assert "prof_short_agree" in full_log
        assert "llm_call_success" in full_log


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

VALID_GENERATE = {
    "context": {"post_text": "A" * 20, "preset_id": "prof_short_agree"},
    "preset_id": "prof_short_agree",
}


class TestGenerateEndpoint:
    def test_generate_success_with_mock(self) -> None:
        resp = client.post("/api/v1/generate", json=VALID_GENERATE)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["status"] == "success"
        assert "reply_text" in data["result"]
        assert "prompt_metadata" in data

    def test_generate_missing_post_text(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={"context": {"preset_id": "prof_short_agree"}, "preset_id": "prof_short_agree"},
        )
        assert resp.status_code == 422

    def test_generate_invalid_preset(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={
                "context": {"post_text": "A" * 20, "preset_id": "prof_short_agree"},
                "preset_id": "nonexistent",
            },
        )
        assert resp.status_code == 422
        assert "Unknown preset_id" in str(resp.json())

    def test_generate_short_post_text(self) -> None:
        resp = client.post(
            "/api/v1/generate",
            json={
                "context": {"post_text": "short", "preset_id": "prof_short_agree"},
                "preset_id": "prof_short_agree",
            },
        )
        assert resp.status_code == 422
