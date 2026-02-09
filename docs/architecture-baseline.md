# Architecture Baseline — Local-First MVP

This document defines the project-wide conventions for configuration,
database lifecycle, migrations, and logging.

---

## 1. Configuration Precedence

Settings are resolved via `pydantic-settings` in this order (highest wins):

1. **Environment variables** (e.g. `APP_DB_PATH=/custom/path.db`)
2. **`.env` file** in the project root
3. **Defaults** in `backend/app/core/settings.py`

### Key settings

| Setting              | Env var              | Default                  |
|----------------------|----------------------|--------------------------|
| DB file path         | `APP_DB_PATH`        | `./data/app.db`          |
| API host             | `API_HOST`           | `127.0.0.1`              |
| API port             | `API_PORT`           | `8000`                   |
| Debug mode           | `DEBUG`              | `false`                  |
| Anthropic API key    | `ANTHROPIC_API_KEY`  | *(none)*                 |
| OpenAI API key       | `OPENAI_API_KEY`     | *(none)*                 |
| LLM timeout          | `LLM_TIMEOUT_SECONDS`| `30`                     |

### Secrets handling

- API keys are loaded from env vars or `.env` only — **never stored in SQLite**.
- `.env` is listed in `.gitignore`.
- Secrets must **never appear in log output**.

---

## 2. SQLite Database Location & Lifecycle

### Path resolution

- Default: `<project_root>/data/app.db`
- Override: set `APP_DB_PATH` env var to an absolute or relative path.
- The parent directory is created automatically if it does not exist.
- The resolved path is logged at startup (`db_initialized` event).

### Lifecycle

1. On first run, SQLite creates the file automatically.
2. Alembic migrations run at FastAPI startup (`alembic upgrade head`).
3. The database is local-only — no cloud sync.

### Deferred

- Encryption at rest: not implemented in MVP, can be added later.

---

## 3. Alembic Migrations

### Conventions

- **Every schema change** must have an Alembic migration — no manual DDL.
- Migrations are auto-run at FastAPI startup via `run_migrations()`.
- Migration files live in `alembic/versions/`.
- `alembic.ini` at project root configures the migration environment.

### Commands

```bash
# Generate a new migration after changing ORM models:
alembic revision --autogenerate -m "description"

# Run migrations manually:
alembic upgrade head

# Check current revision:
alembic current
```

### Failure handling

- Migration failures are logged as `db_migration_failed` with full traceback.
- The application will **not start** if migrations fail.

---

## 4. Structured Logging & Event Taxonomy

### Format

```
2025-06-01 12:00:00 | INFO     | module.name | event_name: key=value
```

### Minimum event taxonomy

| Event                     | Level | When                              |
|---------------------------|-------|-----------------------------------|
| `app_start`               | INFO  | Application process starting      |
| `config_loaded`           | INFO  | Settings resolved                 |
| `db_initialized`          | INFO  | Engine created, DB path resolved  |
| `db_migration_started`    | INFO  | Alembic upgrade beginning         |
| `db_migration_succeeded`  | INFO  | Alembic upgrade completed         |
| `db_migration_failed`     | ERROR | Alembic upgrade error             |
| `db_write_failed`         | ERROR | Repository write error            |
| `db_read_failed`          | ERROR | Repository read error             |

### Rules

- **Never log API keys or secrets.**
- Log record IDs and content **lengths**, not raw content.
- Use `logger.exception()` for errors to include tracebacks.
- Event names are grep-friendly constants defined in
  `backend/app/core/logging.py`.

---

## 5. Error Classification

| Category     | Examples                          | Surfaced as           |
|--------------|-----------------------------------|-----------------------|
| `config`     | Missing required setting          | Startup failure       |
| `db`         | Migration failure, write failure  | Logged + HTTP 500     |
| `provider`   | LLM auth, rate limit, timeout     | Structured LLMFailure |
| `validation` | Bad input, unknown preset         | HTTP 422              |
