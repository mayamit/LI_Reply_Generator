"""Alembic migration runner for programmatic startup use."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from backend.app.core.logging import setup_logging
from backend.app.db.engine import engine

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"


class MigrationError(Exception):
    """Raised when a migration fails with actionable context."""


def _get_alembic_cfg() -> Config:
    return Config(str(_ALEMBIC_INI))


def get_current_revision() -> str | None:
    """Return the current Alembic revision of the database, or None."""
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


def get_head_revision() -> str:
    """Return the head revision from the migration scripts."""
    cfg = _get_alembic_cfg()
    script = ScriptDirectory.from_config(cfg)
    return script.get_current_head()  # type: ignore[return-value]


def check_schema_current() -> bool:
    """Return True if the DB is at the latest migration head.

    Logs a warning if schema drift is detected.
    """
    current = get_current_revision()
    head = get_head_revision()
    if current != head:
        logger.warning(
            "db_schema_drift: current=%s head=%s — run 'make migrate'",
            current,
            head,
        )
        return False
    return True


def run_migrations() -> None:
    """Run ``alembic upgrade head`` programmatically.

    Called at application startup to ensure the database schema is
    up-to-date.  Logs structured events on success or failure.

    Note: Alembic's env.py calls ``fileConfig()`` which reconfigures
    the root logger.  We re-apply our logging setup afterwards.
    """
    current = get_current_revision()
    head = get_head_revision()
    logger.info(
        "db_migration_started: current=%s head=%s",
        current,
        head,
    )
    if current == head:
        logger.info("db_migration_succeeded: already at head")
        return
    try:
        cfg = _get_alembic_cfg()
        command.upgrade(cfg, "head")
    except Exception as exc:
        logger.exception(
            "db_migration_failed: current=%s target=head error=%s",
            current,
            exc,
        )
        raise MigrationError(
            f"Migration failed (current={current}, target=head): {exc}. "
            f"Check alembic/versions/ for the failing migration."
        ) from exc
    finally:
        # Alembic's fileConfig() reconfigures the root logger, so
        # re-apply our structured logging setup.
        setup_logging()
    logger.info("db_migration_succeeded: new_head=%s", get_head_revision())
