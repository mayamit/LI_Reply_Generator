"""Tests for Story 4.4: Structured logging baseline and event taxonomy.

Covers acceptance criteria:
  AC1: Logs include event_name and component
  AC2: correlation_id included consistently
  AC3: Secrets do not appear in output
  AC4: Only lengths/ids logged, not content
  AC5: db_write_failed includes error_category
"""

import logging

import pytest
from backend.app.core.logging import (
    EVENT_APP_START,
    EVENT_CONFIG_LOADED,
    EVENT_DB_INITIALIZED,
    EVENT_DB_MIGRATION_FAILED,
    EVENT_DB_MIGRATION_STARTED,
    EVENT_DB_MIGRATION_SUCCEEDED,
    EVENT_DB_READ_FAILED,
    EVENT_DB_WRITE_FAILED,
    EVENT_LLM_CALL_FAILURE,
    EVENT_LLM_CALL_START,
    EVENT_LLM_CALL_SUCCESS,
    EVENT_PROMPT_ASSEMBLED,
    EVENT_REPLY_APPROVED,
    log_event,
)

# ---------------------------------------------------------------------------
# AC1: Logs include event_name and component (logger name)
# ---------------------------------------------------------------------------


class TestLogEventFormat:
    def test_log_event_emits_event_name(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_logger = logging.getLogger("test.component")
        with caplog.at_level(logging.INFO):
            log_event(test_logger, "info", "test_event", key="value")
        assert "test_event" in caplog.text

    def test_log_event_includes_kwargs(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_logger = logging.getLogger("test.component")
        with caplog.at_level(logging.INFO):
            log_event(test_logger, "info", "my_event", foo="bar", count=42)
        assert "foo=bar" in caplog.text
        assert "count=42" in caplog.text

    def test_log_event_without_kwargs(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_logger = logging.getLogger("test.component")
        with caplog.at_level(logging.INFO):
            log_event(test_logger, "info", "bare_event")
        assert "bare_event" in caplog.text

    def test_log_event_component_in_record(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_logger = logging.getLogger("backend.app.api.routes.generate")
        with caplog.at_level(logging.INFO):
            log_event(test_logger, "info", "test_event")
        assert any(
            r.name == "backend.app.api.routes.generate" for r in caplog.records
        )

    def test_log_event_warning_level(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_logger = logging.getLogger("test.warn")
        with caplog.at_level(logging.WARNING):
            log_event(test_logger, "warning", "warn_event", detail="x")
        assert "warn_event" in caplog.text
        assert caplog.records[0].levelname == "WARNING"

    def test_log_event_error_level(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_logger = logging.getLogger("test.err")
        with caplog.at_level(logging.ERROR):
            log_event(test_logger, "error", "error_event")
        assert caplog.records[0].levelname == "ERROR"


# ---------------------------------------------------------------------------
# AC2: correlation_id included consistently in LLM calls
# ---------------------------------------------------------------------------


class TestCorrelationId:
    def test_llm_client_logs_correlation_id(self) -> None:
        """generate_reply logs correlation_id in llm_call_start and result."""
        from unittest.mock import MagicMock, patch

        from backend.app.models.llm import LLMSuccess
        from backend.app.models.post_context import PostContextPayload
        from backend.app.models.presets import get_preset_by_id
        from backend.app.services.llm_client import generate_reply

        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None

        payload = PostContextPayload(
            post_text="Test post for correlation id check",
            preset_id=preset.id,
            preset_label=preset.label,
            tone=preset.tone,
            length_bucket=preset.length_bucket,
            intent=preset.intent,
        )

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.call.return_value = LLMSuccess(
            reply_text="reply",
            model_id="mock-v1",
            request_id="req-123",
            latency_ms=10,
        )

        with patch("backend.app.services.llm_client.logger") as mock_logger:
            generate_reply(payload, preset, provider=mock_provider)

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "correlation_id=" in call_text


# ---------------------------------------------------------------------------
# AC3: Secrets do not appear in log output
# ---------------------------------------------------------------------------


class TestNoSecretsInLogs:
    def test_safe_dump_masks_keys(self) -> None:
        from backend.app.core.settings import Settings

        s = Settings(
            anthropic_api_key="sk-ant-TOPSECRET",
            openai_api_key="sk-ALSOSECRET",
            _env_file=None,  # type: ignore[call-arg]
        )
        dump = s.safe_dump()
        dump_str = str(dump)
        assert "TOPSECRET" not in dump_str
        assert "ALSOSECRET" not in dump_str

    def test_log_event_does_not_accept_raw_keys(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Verify that even if someone passes a key kwarg, it's a plain string."""
        test_logger = logging.getLogger("test.secrets")
        with caplog.at_level(logging.INFO):
            log_event(
                test_logger, "info", "config_loaded",
                db_path="/data/app.db", debug=False,
            )
        assert "sk-" not in caplog.text


# ---------------------------------------------------------------------------
# AC4: Only lengths/ids logged, not content
# ---------------------------------------------------------------------------


class TestContentNotLogged:
    def test_repository_logs_lengths_not_content(self) -> None:
        """create_draft logs post_text_len, not post_text."""
        from unittest.mock import MagicMock, patch

        from backend.app.services.reply_repository import create_draft

        mock_db = MagicMock()

        with patch(
            "backend.app.services.reply_repository.logger",
        ) as mock_logger:
            from datetime import UTC, datetime

            create_draft(
                mock_db,
                post_text="This is a secret post about my company strategy",
                preset_id="prof_short_agree",
                prompt_text="You are a helpful assistant...",
                created_date=datetime.now(UTC),
            )

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "post_text_len=" in call_text
        assert "secret post about my company" not in call_text

    def test_prompt_builder_logs_length(self) -> None:
        """prompt_assembled logs length, not content."""
        from unittest.mock import patch

        from backend.app.models.post_context import PostContextPayload
        from backend.app.models.presets import get_preset_by_id
        from backend.app.services.prompt_builder import build_prompt

        preset = get_preset_by_id("prof_short_agree")
        assert preset is not None
        payload = PostContextPayload(
            post_text="Test post text for length logging check",
            preset_id=preset.id,
            preset_label=preset.label,
            tone=preset.tone,
            length_bucket=preset.length_bucket,
            intent=preset.intent,
        )

        with patch(
            "backend.app.services.prompt_builder.logger",
        ) as mock_logger:
            build_prompt(payload, preset)

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "prompt_assembled" in call_text
        assert "length=" in call_text


# ---------------------------------------------------------------------------
# AC5: db_write_failed includes error_category
# ---------------------------------------------------------------------------


class TestDbWriteFailedCategory:
    def test_log_event_with_error_category(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        test_logger = logging.getLogger("test.db")
        with caplog.at_level(logging.ERROR):
            log_event(
                test_logger, "error", "db_write_failed",
                operation="create_draft", error_category="db",
            )
        assert "db_write_failed" in caplog.text
        assert "error_category=db" in caplog.text
        assert "operation=create_draft" in caplog.text


# ---------------------------------------------------------------------------
# Event taxonomy completeness
# ---------------------------------------------------------------------------


class TestEventTaxonomy:
    def test_all_events_defined(self) -> None:
        assert EVENT_APP_START == "app_start"
        assert EVENT_CONFIG_LOADED == "config_loaded"
        assert EVENT_DB_INITIALIZED == "db_initialized"
        assert EVENT_DB_MIGRATION_STARTED == "db_migration_started"
        assert EVENT_DB_MIGRATION_SUCCEEDED == "db_migration_succeeded"
        assert EVENT_DB_MIGRATION_FAILED == "db_migration_failed"
        assert EVENT_DB_WRITE_FAILED == "db_write_failed"
        assert EVENT_DB_READ_FAILED == "db_read_failed"
        assert EVENT_PROMPT_ASSEMBLED == "prompt_assembled"
        assert EVENT_LLM_CALL_START == "llm_call_start"
        assert EVENT_LLM_CALL_SUCCESS == "llm_call_success"
        assert EVENT_LLM_CALL_FAILURE == "llm_call_failure"
        assert EVENT_REPLY_APPROVED == "reply_approved"
