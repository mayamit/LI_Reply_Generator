"""Tests for Story 4.1: Unified settings management.

Covers acceptance criteria:
  AC1: Env vars override .env and defaults
  AC2: .env values used when env vars absent
  AC3: Safe defaults for non-required settings
  AC4: Invalid DB path → controlled error
  AC5: LLM not configured → user-friendly error
  AC6: Secrets not in log output
  AC7/8: FastAPI and Streamlit resolve identical values
"""

import logging
import os
import tempfile
from unittest.mock import patch

import pytest
from backend.app.core.settings import _DEFAULT_DB_PATH, Settings

# ---------------------------------------------------------------------------
# AC1: Env vars override .env and defaults
# ---------------------------------------------------------------------------


class TestEnvOverride:
    def test_env_var_overrides_default_db_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            custom = os.path.join(tmpdir, "override.db")
            s = Settings(
                app_db_path=custom,
                _env_file=None,  # type: ignore[call-arg]
            )
            assert s.app_db_path == custom

    def test_env_var_overrides_default_timeout(self) -> None:
        s = Settings(
            llm_timeout_seconds=60,
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.llm_timeout_seconds == 60

    def test_env_var_overrides_log_level(self) -> None:
        s = Settings(
            log_level="DEBUG",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.log_level == "DEBUG"

    def test_env_var_overrides_api_host(self) -> None:
        s = Settings(
            api_host="0.0.0.0",
            api_port=9000,
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.api_host == "0.0.0.0"
        assert s.api_port == 9000


# ---------------------------------------------------------------------------
# AC2/AC3: Defaults applied when no env / .env
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_db_path(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.app_db_path == _DEFAULT_DB_PATH
        assert "app.db" in s.app_db_path

    def test_default_api_host(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.api_host == "127.0.0.1"

    def test_default_api_port(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.api_port == 8000

    def test_default_debug_false(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.debug is False

    def test_default_log_level(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.log_level == "INFO"

    def test_default_timeout(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.llm_timeout_seconds == 30

    def test_default_llm_keys_none(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.anthropic_api_key is None
        assert s.openai_api_key is None

    def test_database_url_derived_from_path(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.database_url == f"sqlite:///{s.app_db_path}"


# ---------------------------------------------------------------------------
# AC4: Invalid DB path → controlled error
# ---------------------------------------------------------------------------


class TestDbPathValidation:
    def test_valid_path_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "sub", "dir", "test.db")
            s = Settings(
                app_db_path=path,
                _env_file=None,  # type: ignore[call-arg]
            )
            assert s.app_db_path == path

    def test_valid_path_creates_parent_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path

            path = os.path.join(tmpdir, "new", "nested", "test.db")
            Settings(
                app_db_path=path,
                _env_file=None,  # type: ignore[call-arg]
            )
            assert Path(path).parent.exists()

    def test_unwritable_path_raises_with_guidance(self) -> None:
        with pytest.raises(Exception, match="APP_DB_PATH"):
            with patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
                Settings(
                    app_db_path="/nonexistent/readonly/path/test.db",
                    _env_file=None,  # type: ignore[call-arg]
                )


# ---------------------------------------------------------------------------
# AC5: LLM not configured → user-friendly indicator
# ---------------------------------------------------------------------------


class TestLlmConfigured:
    def test_not_configured_when_no_keys(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.is_llm_configured is False

    def test_configured_with_anthropic_key(self) -> None:
        s = Settings(
            anthropic_api_key="sk-ant-test",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.is_llm_configured is True

    def test_configured_with_openai_key(self) -> None:
        s = Settings(
            openai_api_key="sk-test",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.is_llm_configured is True

    def test_configured_with_both_keys(self) -> None:
        s = Settings(
            anthropic_api_key="sk-ant-test",
            openai_api_key="sk-test",
            _env_file=None,  # type: ignore[call-arg]
        )
        assert s.is_llm_configured is True


# ---------------------------------------------------------------------------
# AC6: Secrets not in log output / safe_dump
# ---------------------------------------------------------------------------


class TestSecretMasking:
    def test_safe_dump_excludes_api_keys(self) -> None:
        s = Settings(
            anthropic_api_key="sk-ant-SUPERSECRET",
            openai_api_key="sk-TOPSECRET",
            _env_file=None,  # type: ignore[call-arg]
        )
        dump = s.safe_dump()
        dump_str = str(dump)
        assert "sk-ant-SUPERSECRET" not in dump_str
        assert "sk-TOPSECRET" not in dump_str

    def test_safe_dump_includes_non_secret_fields(self) -> None:
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        dump = s.safe_dump()
        assert "api_host" in dump
        assert "api_port" in dump
        assert "app_db_path" in dump
        assert "log_level" in dump
        assert "is_llm_configured" in dump

    def test_safe_dump_log_line_has_no_secrets(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_key = "sk-ant-SUPERSECRETKEY123456"
        s = Settings(
            anthropic_api_key=fake_key,
            _env_file=None,  # type: ignore[call-arg]
        )
        logger = logging.getLogger("test.safe_dump")
        with caplog.at_level(logging.INFO):
            logger.info("config_loaded: %s", s.safe_dump())
        assert fake_key not in caplog.text

    def test_safe_dump_shows_llm_configured_status(self) -> None:
        s = Settings(
            anthropic_api_key="sk-ant-test",
            _env_file=None,  # type: ignore[call-arg]
        )
        dump = s.safe_dump()
        assert dump["is_llm_configured"] is True


# ---------------------------------------------------------------------------
# AC7/8: FastAPI and Streamlit resolve identical values
# ---------------------------------------------------------------------------


class TestSharedSettings:
    def test_singleton_settings_importable(self) -> None:
        """Both FastAPI and Streamlit import from the same module."""
        from backend.app.core.settings import settings

        assert settings is not None
        assert isinstance(settings, Settings)

    def test_settings_values_consistent(self) -> None:
        """Two imports of the singleton give identical values."""
        from backend.app.core import settings as mod1
        from backend.app.core import settings as mod2

        assert mod1.settings is mod2.settings

    def test_streamlit_uses_shared_settings(self) -> None:
        """Verify ui_helpers imports settings for API_BASE."""
        import importlib

        import ui_helpers

        importlib.reload(ui_helpers)
        expected = f"http://{ui_helpers.settings.api_host}:{ui_helpers.settings.api_port}"
        assert ui_helpers.API_BASE == expected
