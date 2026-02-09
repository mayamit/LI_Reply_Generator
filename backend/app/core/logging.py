"""Structured logging baseline and event taxonomy.

Event taxonomy (minimum set)::

    app_start              — application process starting
    config_loaded          — settings resolved successfully
    db_initialized         — engine created, DB path resolved
    db_migration_started   — alembic upgrade beginning
    db_migration_succeeded — alembic upgrade completed
    db_migration_failed    — alembic upgrade error (with traceback)
    db_write_failed        — repository write error
    db_read_failed         — repository read error
    prompt_assembled       — prompt built for LLM
    llm_call_start         — LLM provider call initiated
    llm_call_success       — LLM call returned a reply
    llm_call_failure       — LLM call failed
    reply_approved         — draft approved by user

Rules:
    - Never log API keys or secrets.
    - Log record IDs and content *lengths*, not raw content.

Usage::

    from backend.app.core.logging import log_event
    log_event(logger, "info", "db_write_failed",
              operation="create_draft", error_category="db")
"""

import logging
import sys

# Canonical event names for grep-ability and observability.
EVENT_APP_START = "app_start"
EVENT_CONFIG_LOADED = "config_loaded"
EVENT_DB_INITIALIZED = "db_initialized"
EVENT_DB_MIGRATION_STARTED = "db_migration_started"
EVENT_DB_MIGRATION_SUCCEEDED = "db_migration_succeeded"
EVENT_DB_MIGRATION_FAILED = "db_migration_failed"
EVENT_DB_WRITE_FAILED = "db_write_failed"
EVENT_DB_READ_FAILED = "db_read_failed"
EVENT_PROMPT_ASSEMBLED = "prompt_assembled"
EVENT_LLM_CALL_START = "llm_call_start"
EVENT_LLM_CALL_SUCCESS = "llm_call_success"
EVENT_LLM_CALL_FAILURE = "llm_call_failure"
EVENT_REPLY_APPROVED = "reply_approved"


_HANDLER_ATTR = "_li_reply_gen"


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a simple structured format.

    Safe to call multiple times — only adds the handler once and
    restores it if Alembic's ``fileConfig()`` removes it.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Check if our handler is already attached
    for h in root.handlers:
        if getattr(h, _HANDLER_ATTR, False):
            return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    setattr(handler, _HANDLER_ATTR, True)
    root.addHandler(handler)


def log_event(
    logger: logging.Logger,
    level: str,
    event_name: str,
    **kwargs: object,
) -> None:
    """Emit a structured log line with consistent ``event_name: key=value`` format.

    Parameters
    ----------
    logger:
        The logger instance (provides the component via ``logger.name``).
    level:
        Log level name — ``"info"``, ``"warning"``, ``"error"``, or ``"exception"``.
    event_name:
        Canonical event name (e.g. ``"db_write_failed"``).
    **kwargs:
        Arbitrary key-value pairs appended as ``key=value``.
    """
    parts = " ".join(f"{k}={v}" for k, v in kwargs.items())
    message = f"{event_name}: {parts}" if parts else event_name
    log_fn = getattr(logger, level, logger.info)
    log_fn(message)
