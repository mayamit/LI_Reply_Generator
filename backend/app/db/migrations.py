"""Alembic migration runner for programmatic startup use."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from backend.app.core.logging import setup_logging

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _PROJECT_ROOT / "alembic.ini"


def run_migrations() -> None:
    """Run ``alembic upgrade head`` programmatically.

    Called at application startup to ensure the database schema is
    up-to-date.  Logs structured events on success or failure.

    Note: Alembic's env.py calls ``fileConfig()`` which reconfigures
    the root logger.  We re-apply our logging setup afterwards.
    """
    logger.info("db_migration_started")
    try:
        cfg = Config(str(_ALEMBIC_INI))
        command.upgrade(cfg, "head")
    except Exception:
        logger.exception("db_migration_failed")
        raise
    finally:
        # Alembic's fileConfig() reconfigures the root logger, so
        # re-apply our structured logging setup.
        setup_logging()
    logger.info("db_migration_succeeded")
