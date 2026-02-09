"""SQLAlchemy engine configuration for SQLite."""

import logging
from pathlib import Path

from sqlalchemy import create_engine

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
