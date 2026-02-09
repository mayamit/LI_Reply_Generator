"""Tests for Story 4.3: Migration execution workflow and guardrails.

Covers acceptance criteria:
  AC1: Fresh environment → schema created successfully
  AC2: Existing DB → upgrades to head without data loss
  AC3: Migration failure → logs include revision and actionable message
  AC4: Auto-upgrade at startup runs once and proceeds on success
  AC5: Schema drift detection warns or fails fast
"""

from unittest.mock import patch

import pytest
from backend.app.db.migrations import (
    MigrationError,
    check_schema_current,
    get_current_revision,
    get_head_revision,
    run_migrations,
)

# ---------------------------------------------------------------------------
# AC1: Fresh environment — schema created successfully
# ---------------------------------------------------------------------------


class TestFreshMigration:
    def test_run_migrations_succeeds(self) -> None:
        """Smoke test: migrations run without error on the dev DB."""
        run_migrations()  # should not raise

    def test_head_revision_is_not_none(self) -> None:
        head = get_head_revision()
        assert head is not None
        assert isinstance(head, str)
        assert len(head) > 0


# ---------------------------------------------------------------------------
# AC2: Existing DB — upgrades to head, already-at-head is no-op
# ---------------------------------------------------------------------------


class TestExistingDb:
    def test_already_at_head_is_noop(self) -> None:
        """When DB is already at head, run_migrations returns immediately."""
        with patch("backend.app.db.migrations.logger") as mock_logger:
            run_migrations()

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "already at head" in call_text

    def test_current_matches_head(self) -> None:
        current = get_current_revision()
        head = get_head_revision()
        assert current == head


# ---------------------------------------------------------------------------
# AC3: Migration failure → logs include revision and actionable message
# ---------------------------------------------------------------------------


class TestMigrationFailure:
    def test_failure_raises_migration_error(self) -> None:
        with (
            patch(
                "backend.app.db.migrations.get_current_revision",
                return_value="old_rev",
            ),
            patch(
                "backend.app.db.migrations.command.upgrade",
                side_effect=RuntimeError("column already exists"),
            ),
            pytest.raises(MigrationError, match="old_rev"),
        ):
            run_migrations()

    def test_failure_message_includes_target(self) -> None:
        with (
            patch(
                "backend.app.db.migrations.get_current_revision",
                return_value="abc123",
            ),
            patch(
                "backend.app.db.migrations.command.upgrade",
                side_effect=RuntimeError("table not found"),
            ),
            pytest.raises(MigrationError, match="target=head"),
        ):
            run_migrations()

    def test_failure_message_includes_cause(self) -> None:
        with (
            patch(
                "backend.app.db.migrations.get_current_revision",
                return_value="abc123",
            ),
            patch(
                "backend.app.db.migrations.command.upgrade",
                side_effect=RuntimeError("table not found"),
            ),
            pytest.raises(MigrationError, match="table not found"),
        ):
            run_migrations()

    def test_failure_logged_with_revision(self) -> None:
        with (
            patch(
                "backend.app.db.migrations.get_current_revision",
                return_value="deadbeef",
            ),
            patch(
                "backend.app.db.migrations.command.upgrade",
                side_effect=RuntimeError("fail"),
            ),
            patch("backend.app.db.migrations.logger") as mock_logger,
            pytest.raises(MigrationError),
        ):
            run_migrations()

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "db_migration_failed" in call_text
        assert "deadbeef" in call_text

    def test_migration_error_has_actionable_guidance(self) -> None:
        with (
            patch(
                "backend.app.db.migrations.get_current_revision",
                return_value="old",
            ),
            patch(
                "backend.app.db.migrations.command.upgrade",
                side_effect=RuntimeError("oops"),
            ),
            pytest.raises(MigrationError, match="alembic/versions/"),
        ):
            run_migrations()


# ---------------------------------------------------------------------------
# AC4: Auto-upgrade logs structured events
# ---------------------------------------------------------------------------


class TestAutoUpgrade:
    def test_startup_logs_migration_started(self) -> None:
        with patch("backend.app.db.migrations.logger") as mock_logger:
            run_migrations()

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "db_migration_started" in call_text

    def test_startup_logs_current_and_head(self) -> None:
        with patch("backend.app.db.migrations.logger") as mock_logger:
            run_migrations()

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "current=" in call_text
        assert "head=" in call_text


# ---------------------------------------------------------------------------
# AC5: Schema drift detection
# ---------------------------------------------------------------------------


class TestSchemaDrift:
    def test_no_drift_when_at_head(self) -> None:
        assert check_schema_current() is True

    def test_drift_detected_when_behind(self) -> None:
        with patch(
            "backend.app.db.migrations.get_current_revision",
            return_value="old_revision",
        ):
            assert check_schema_current() is False

    def test_drift_logged_as_warning(self) -> None:
        with (
            patch(
                "backend.app.db.migrations.get_current_revision",
                return_value="old_revision",
            ),
            patch("backend.app.db.migrations.logger") as mock_logger,
        ):
            check_schema_current()

        calls = [str(c) for c in mock_logger.method_calls]
        call_text = " ".join(calls)
        assert "db_schema_drift" in call_text
        assert "make migrate" in call_text

    def test_drift_returns_false_for_none_revision(self) -> None:
        """A fresh DB with no revision is behind head."""
        with patch(
            "backend.app.db.migrations.get_current_revision",
            return_value=None,
        ):
            assert check_schema_current() is False
