"""Application settings loaded from environment / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is three levels up from this file (backend/app/core/settings.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = f"sqlite:///{_PROJECT_ROOT / 'data' / 'app.db'}"
    debug: bool = False


settings = Settings()
