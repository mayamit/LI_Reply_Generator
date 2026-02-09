"""Application settings loaded from environment / .env file.

Config precedence (highest to lowest):
    1. Environment variables
    2. ``.env`` file in project root
    3. Defaults defined in this module
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is three levels up from this file (backend/app/core/settings.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DB_PATH = str(_PROJECT_ROOT / "data" / "app.db")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    debug: bool = False

    # Database — override via APP_DB_PATH env var
    app_db_path: str = _DEFAULT_DB_PATH

    @property
    def database_url(self) -> str:
        """SQLite connection URL derived from ``app_db_path``."""
        return f"sqlite:///{self.app_db_path}"

    # LLM provider keys (at most one should be set)
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    llm_timeout_seconds: int = 30


settings = Settings()
