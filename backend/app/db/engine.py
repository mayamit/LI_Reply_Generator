"""SQLAlchemy engine configuration for SQLite."""

import logging
from pathlib import Path

from sqlalchemy import create_engine, text

from backend.app.core.settings import settings

logger = logging.getLogger(__name__)

# Ensure the parent directory exists so SQLite can create the file
_db_path = Path(settings.app_db_path)
_db_path.parent.mkdir(parents=True, exist_ok=True)


def get_resolved_db_path() -> Path:
    """Return the resolved absolute path to the SQLite database file."""
    return _db_path.resolve()


engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},  # required for SQLite
)

logger.info(
    "db_initialized: path=%s url=%s",
    get_resolved_db_path(),
    settings.database_url,
)


class DatabaseInitError(Exception):
    """Raised when the database cannot be initialized."""


def init_db() -> None:
    """Verify the database is accessible by executing a simple query.

    Called at startup by both FastAPI and Streamlit to confirm the DB
    file can be created/opened. Raises :class:`DatabaseInitError` with
    actionable guidance on failure.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("db_init_verified: path=%s", get_resolved_db_path())
    except Exception as exc:
        msg = (
            f"Cannot open database at '{get_resolved_db_path()}': {exc}. "
            f"Check file permissions or set APP_DB_PATH to a writable location."
        )
        logger.error("db_init_failed: %s", msg)
        raise DatabaseInitError(msg) from exc
