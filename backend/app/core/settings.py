"""Application settings loaded from environment / .env file.

Config precedence (highest to lowest):
    1. Environment variables
    2. ``.env`` file in project root
    3. Defaults defined in this module

Secrets (API keys) are never exposed in ``repr()``, ``str()``, or logs.
"""

from pathlib import Path

from pydantic import model_validator
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
    log_level: str = "INFO"

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

    @property
    def is_llm_configured(self) -> bool:
        """Return True if at least one LLM API key is set."""
        return bool(self.anthropic_api_key or self.openai_api_key)

    @model_validator(mode="after")
    def _validate_db_path(self) -> "Settings":
        """Ensure the DB path parent directory exists or can be created."""
        parent = Path(self.app_db_path).parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = (
                f"Cannot create database directory '{parent}': {exc}. "
                f"Set APP_DB_PATH to a writable location."
            )
            raise ValueError(msg) from exc
        return self

    def safe_dump(self) -> dict[str, object]:
        """Return settings dict with secrets masked — safe for logging."""
        return {
            "api_host": self.api_host,
            "api_port": self.api_port,
            "debug": self.debug,
            "log_level": self.log_level,
            "app_db_path": self.app_db_path,
            "llm_timeout_seconds": self.llm_timeout_seconds,
            "is_llm_configured": self.is_llm_configured,
        }


settings = Settings()
