"""SQLAlchemy engine configuration for SQLite."""

from pathlib import Path

from sqlalchemy import create_engine

from backend.app.core.settings import settings

# Ensure the data/ directory exists so SQLite can create the file
_db_path = settings.database_url.replace("sqlite:///", "")
Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},  # required for SQLite
)
