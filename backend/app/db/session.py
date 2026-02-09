"""Database session factory."""

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.engine import engine

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
