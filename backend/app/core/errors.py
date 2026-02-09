"""Centralized error normalization for user-facing messages.

Every error surfaced to the UI must pass through this module to ensure:
- Consistent structure (user_message, error_category, retryable)
- No stack traces or secrets in user-facing output
- Detailed info logged for debugging
"""

import logging
from dataclasses import dataclass

from backend.app.core.logging import log_event

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizedError:
    """Standardized error representation for API responses."""

    user_message: str
    error_category: str
    retryable: bool
    http_status: int = 500


def normalize_db_error(
    exc: Exception,
    *,
    operation: str,
    correlation_id: str | None = None,
) -> NormalizedError:
    """Normalize a database error into a user-friendly message."""
    exc_msg = str(exc).lower()

    if "locked" in exc_msg or "busy" in exc_msg:
        error = NormalizedError(
            user_message=(
                "The database is temporarily busy. Please try again in a moment."
            ),
            error_category="db",
            retryable=True,
            http_status=503,
        )
    elif "readonly" in exc_msg or "read-only" in exc_msg or "permission" in exc_msg:
        error = NormalizedError(
            user_message=(
                "A database permission error occurred. "
                "Check APP_DB_PATH points to a writable location."
            ),
            error_category="db",
            retryable=False,
            http_status=500,
        )
    else:
        error = NormalizedError(
            user_message="A database error occurred. Please try again.",
            error_category="db",
            retryable=True,
            http_status=500,
        )

    log_event(
        logger, "error", "db_write_failed",
        operation=operation,
        error_category=error.error_category,
        retryable=error.retryable,
        correlation_id=correlation_id or "N/A",
        detail=str(exc),
    )
    return error


def normalize_validation_error(
    messages: list[str],
) -> NormalizedError:
    """Normalize validation errors into a single user-friendly message."""
    joined = "; ".join(messages)
    return NormalizedError(
        user_message=f"Validation failed: {joined}",
        error_category="validation",
        retryable=False,
        http_status=422,
    )


def normalize_unknown_error(
    exc: Exception,
    *,
    operation: str,
    correlation_id: str | None = None,
) -> NormalizedError:
    """Normalize an unexpected error into a safe generic message."""
    log_event(
        logger, "exception", "unknown_error",
        operation=operation,
        error_category="unknown",
        correlation_id=correlation_id or "N/A",
        detail=f"{type(exc).__name__}: {exc}",
    )
    return NormalizedError(
        user_message="An unexpected error occurred. Please try again.",
        error_category="unknown",
        retryable=False,
        http_status=500,
    )
