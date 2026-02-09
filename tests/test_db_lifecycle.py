"""Tests for Story 4.2: Database initialization and lifecycle management.

Covers acceptance criteria:
  AC1: Missing ./data directory created automatically
  AC2: DB file created and opened on first run
  AC3: APP_DB_PATH used exactly as configured
  AC4: Invalid/unwritable path → controlled error
  AC5: DB locked → categorized as retryable
  AC6: FastAPI and Streamlit resolve same DB path
"""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from backend.app.core.settings import Settings
from backend.app.db.engine import DatabaseInitError, get_resolved_db_path, init_db
from backend.app.services.reply_repository import (
    DatabaseLockedError,
    _handle_operational_error,
    create_draft,
)
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# AC1: Missing directory created automatically
# ---------------------------------------------------------------------------


class TestDirectoryCreation:
    def test_parent_dir_created_for_new_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "new", "nested", "app.db")
            Settings(
                app_db_path=db_path,
                _env_file=None,  # type: ignore[call-arg]
            )
            assert Path(db_path).parent.exists()

    def test_existing_dir_no_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "app.db")
            s = Settings(
                app_db_path=db_path,
                _env_file=None,  # type: ignore[call-arg]
            )
            assert s.app_db_path == db_path


# ---------------------------------------------------------------------------
# AC2: DB file created and opened successfully
# ---------------------------------------------------------------------------


class TestDbFileCreation:
    def test_sqlite_creates_file_on_connect(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            eng = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"check_same_thread": False},
            )
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            assert Path(db_path).exists()

    def test_init_db_succeeds(self) -> None:
        # init_db uses the global engine which points at data/app.db
        init_db()  # should not raise


# ---------------------------------------------------------------------------
# AC3: APP_DB_PATH used exactly as configured
# ---------------------------------------------------------------------------


class TestDbPathHonored:
    def test_custom_path_used(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            custom = os.path.join(tmpdir, "custom.db")
            s = Settings(
                app_db_path=custom,
                _env_file=None,  # type: ignore[call-arg]
            )
            assert s.app_db_path == custom
            assert s.database_url == f"sqlite:///{custom}"

    def test_resolved_path_is_absolute(self) -> None:
        resolved = get_resolved_db_path()
        assert resolved.is_absolute()


# ---------------------------------------------------------------------------
# AC4: Invalid/unwritable path → controlled error
# ---------------------------------------------------------------------------


class TestDbInitError:
    def test_init_db_failure_raises_database_init_error(self) -> None:
        with patch(
            "backend.app.db.engine.engine.connect",
            side_effect=Exception("cannot open"),
        ):
            with pytest.raises(DatabaseInitError, match="APP_DB_PATH"):
                init_db()

    def test_init_error_message_is_actionable(self) -> None:
        with patch(
            "backend.app.db.engine.engine.connect",
            side_effect=Exception("permission denied"),
        ):
            with pytest.raises(DatabaseInitError) as exc_info:
                init_db()
            assert "writable location" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC5: DB locked → categorized as retryable
# ---------------------------------------------------------------------------


class TestDatabaseLocked:
    def test_locked_error_raises_database_locked(self) -> None:
        exc = OperationalError(
            "INSERT INTO ...",
            params={},
            orig=Exception("database is locked"),
        )
        with pytest.raises(DatabaseLockedError, match="retry"):
            _handle_operational_error(exc, "test_op")

    def test_busy_error_raises_database_locked(self) -> None:
        exc = OperationalError(
            "UPDATE ...",
            params={},
            orig=Exception("database is busy"),
        )
        with pytest.raises(DatabaseLockedError, match="retry"):
            _handle_operational_error(exc, "test_op")

    def test_non_locked_error_reraised(self) -> None:
        exc = OperationalError(
            "INSERT ...",
            params={},
            orig=Exception("disk I/O error"),
        )
        with pytest.raises(OperationalError):
            _handle_operational_error(exc, "test_op")

    def test_create_draft_locked_raises(self) -> None:
        mock_db = MagicMock(spec=Session)
        mock_db.flush.side_effect = OperationalError(
            "INSERT ...",
            params={},
            orig=Exception("database is locked"),
        )
        with pytest.raises(DatabaseLockedError):
            create_draft(
                mock_db,
                post_text="Test post text for locked DB scenario",
                preset_id="prof_short_agree",
                prompt_text="test prompt",
                created_date=datetime.now(UTC),
            )

    def test_locked_error_logged_as_retryable(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        exc = OperationalError(
            "INSERT ...",
            params={},
            orig=Exception("database is locked"),
        )
        with caplog.at_level(logging.WARNING):
            with pytest.raises(DatabaseLockedError):
                _handle_operational_error(exc, "create_draft")
        assert "retryable" in caplog.text
        assert "db_write_failed" in caplog.text


# ---------------------------------------------------------------------------
# AC6: FastAPI and Streamlit resolve same path
# ---------------------------------------------------------------------------


class TestSharedDbPath:
    def test_engine_uses_settings_path(self) -> None:
        from backend.app.core.settings import settings
        from backend.app.db.engine import get_resolved_db_path

        expected = Path(settings.app_db_path).resolve()
        assert get_resolved_db_path() == expected

    def test_streamlit_imports_shared_settings(self) -> None:
        """Streamlit uses the same settings module as FastAPI."""
        import streamlit_app
        from backend.app.core.settings import settings

        assert streamlit_app.settings is settings
