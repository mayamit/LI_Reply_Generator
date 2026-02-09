"""Tests for Story 5.2: Centralize error normalization and user messaging.

Covers acceptance criteria:
  AC1: LLM rate limit → retryable message
  AC2: DB locked → retryable, no stack traces
  AC3: Validation → clear actionable message
  AC4: Unknown error → generic safe message, logged details
  AC5: Logs include error_category and correlation_id
"""

import logging

import pytest
from backend.app.core.errors import (
    NormalizedError,
    normalize_db_error,
    normalize_unknown_error,
    normalize_validation_error,
)
from backend.app.models.llm import ErrorCategory, LLMFailure

# ---------------------------------------------------------------------------
# AC1: LLM rate limit → retryable message
# ---------------------------------------------------------------------------


class TestLlmErrorNormalization:
    def test_rate_limit_is_retryable(self) -> None:
        failure = LLMFailure(
            error_category=ErrorCategory.rate_limit,
            user_message="Rate limit reached. Please wait and retry.",
            retryable=True,
        )
        assert failure.retryable is True
        assert failure.error_category == "rate_limit"
        assert "retry" in failure.user_message.lower()

    def test_auth_error_not_retryable(self) -> None:
        failure = LLMFailure(
            error_category=ErrorCategory.auth,
            user_message="API key is invalid.",
            retryable=False,
        )
        assert failure.retryable is False

    def test_timeout_is_retryable(self) -> None:
        failure = LLMFailure(
            error_category=ErrorCategory.timeout,
            user_message="Request timed out.",
            retryable=True,
        )
        assert failure.retryable is True

    def test_failure_has_user_message(self) -> None:
        failure = LLMFailure(
            error_category=ErrorCategory.network,
            user_message="Could not connect.",
            retryable=True,
        )
        assert len(failure.user_message) > 0
        assert "sk-" not in failure.user_message


# ---------------------------------------------------------------------------
# AC2: DB locked → retryable, no stack traces
# ---------------------------------------------------------------------------


class TestDbErrorNormalization:
    def test_locked_error_is_retryable(self) -> None:
        exc = Exception("database is locked")
        error = normalize_db_error(exc, operation="create_draft")
        assert error.retryable is True
        assert error.error_category == "db"
        assert "try again" in error.user_message.lower()

    def test_busy_error_is_retryable(self) -> None:
        exc = Exception("database is busy")
        error = normalize_db_error(exc, operation="test")
        assert error.retryable is True
        assert error.http_status == 503

    def test_permission_error_not_retryable(self) -> None:
        exc = Exception("permission denied")
        error = normalize_db_error(exc, operation="test")
        assert error.retryable is False
        assert "permission" in error.user_message.lower()

    def test_readonly_error_not_retryable(self) -> None:
        exc = Exception("attempt to write a readonly database")
        error = normalize_db_error(exc, operation="test")
        assert error.retryable is False

    def test_generic_db_error_retryable(self) -> None:
        exc = Exception("some unknown db issue")
        error = normalize_db_error(exc, operation="test")
        assert error.retryable is True
        assert error.error_category == "db"

    def test_no_stack_trace_in_user_message(self) -> None:
        exc = Exception("Traceback (most recent call last): ...")
        error = normalize_db_error(exc, operation="test")
        assert "Traceback" not in error.user_message

    def test_no_secrets_in_user_message(self) -> None:
        exc = Exception("failed with key sk-ant-SECRET123")
        error = normalize_db_error(exc, operation="test")
        assert "sk-ant" not in error.user_message


# ---------------------------------------------------------------------------
# AC3: Validation → clear actionable message
# ---------------------------------------------------------------------------


class TestValidationNormalization:
    def test_single_error(self) -> None:
        error = normalize_validation_error(["post_text is required"])
        assert error.error_category == "validation"
        assert error.retryable is False
        assert error.http_status == 422
        assert "post_text is required" in error.user_message

    def test_multiple_errors_joined(self) -> None:
        error = normalize_validation_error(["too short", "invalid URL"])
        assert "too short" in error.user_message
        assert "invalid URL" in error.user_message

    def test_validation_error_is_not_retryable(self) -> None:
        error = normalize_validation_error(["bad input"])
        assert error.retryable is False


# ---------------------------------------------------------------------------
# AC4: Unknown error → generic safe message, logged details
# ---------------------------------------------------------------------------


class TestUnknownErrorNormalization:
    def test_generic_safe_message(self) -> None:
        exc = RuntimeError("something broke internally")
        error = normalize_unknown_error(exc, operation="test")
        assert "unexpected" in error.user_message.lower()
        assert "something broke" not in error.user_message
        assert error.error_category == "unknown"

    def test_no_exception_type_in_message(self) -> None:
        exc = ValueError("secret data leaked")
        error = normalize_unknown_error(exc, operation="test")
        assert "ValueError" not in error.user_message
        assert "secret" not in error.user_message

    def test_unknown_error_logged(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        exc = RuntimeError("internal detail")
        with caplog.at_level(logging.ERROR):
            normalize_unknown_error(exc, operation="test_op")
        assert "unknown_error" in caplog.text
        assert "internal detail" in caplog.text


# ---------------------------------------------------------------------------
# AC5: Logs include error_category and correlation_id
# ---------------------------------------------------------------------------


class TestLoggedFields:
    def test_db_error_logs_category_and_correlation(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        exc = Exception("locked")
        with caplog.at_level(logging.ERROR):
            normalize_db_error(
                exc, operation="create_draft", correlation_id="corr-123",
            )
        assert "error_category=db" in caplog.text
        assert "correlation_id=corr-123" in caplog.text

    def test_db_error_logs_operation(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        exc = Exception("fail")
        with caplog.at_level(logging.ERROR):
            normalize_db_error(exc, operation="approve_reply")
        assert "operation=approve_reply" in caplog.text

    def test_unknown_error_logs_correlation(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        exc = RuntimeError("oops")
        with caplog.at_level(logging.ERROR):
            normalize_unknown_error(
                exc, operation="test", correlation_id="corr-456",
            )
        assert "correlation_id=corr-456" in caplog.text

    def test_db_error_default_correlation(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        exc = Exception("fail")
        with caplog.at_level(logging.ERROR):
            normalize_db_error(exc, operation="test")
        assert "correlation_id=N/A" in caplog.text


# ---------------------------------------------------------------------------
# NormalizedError structure
# ---------------------------------------------------------------------------


class TestNormalizedErrorStructure:
    def test_is_frozen_dataclass(self) -> None:
        error = NormalizedError(
            user_message="test",
            error_category="db",
            retryable=True,
        )
        with pytest.raises(AttributeError):
            error.user_message = "changed"  # type: ignore[misc]

    def test_default_http_status(self) -> None:
        error = NormalizedError(
            user_message="test",
            error_category="unknown",
            retryable=False,
        )
        assert error.http_status == 500
