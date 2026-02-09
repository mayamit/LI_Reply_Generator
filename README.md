# LI Reply Generator

Local-first tool for drafting LinkedIn replies using AI.

## Prerequisites

- Python 3.11+
- pip (or a virtualenv manager of your choice)

## Quick Start

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies (including dev tools)
make install

# 3. Copy the example env file
cp .env.example .env

# 4. Run database migrations
make migrate

# 5. Start the API (runs on http://127.0.0.1:8000)
make run-api

# 6. In a second terminal, start the Streamlit UI
make run-ui
```

## Project Layout

```
backend/
  app/
    main.py              # FastAPI entry point
    core/
      settings.py        # pydantic-settings config (.env)
      logging.py         # structured logging setup
    db/
      engine.py          # SQLAlchemy engine (SQLite)
      session.py         # session factory + FastAPI dependency
      base.py            # declarative base for ORM models
    api/routes/
      health.py          # GET /health
streamlit_app.py         # Streamlit UI
alembic/                 # Alembic migrations
data/                    # SQLite DB file (gitignored)
tests/                   # pytest tests
```

## Common Commands

| Command          | Description                          |
|------------------|--------------------------------------|
| `make install`   | Install project + dev dependencies   |
| `make run-api`   | Start FastAPI dev server             |
| `make run-ui`    | Start Streamlit UI                   |
| `make test`      | Run pytest                           |
| `make lint`      | Run ruff linter + format check       |
| `make format`    | Auto-fix lint issues + format code   |
| `make migrate`   | Apply Alembic migrations             |

## Prompt Builder

The deterministic prompt assembly module lives at `backend/app/services/prompt_builder.py`. Run its tests with `pytest tests/test_prompt_builder.py -v`.

## Database

The SQLite database lives at `data/app.db`. This directory is gitignored.
To reset the DB, delete `data/app.db` and re-run `make migrate`.

## Non-Goals (current scope)

- No LinkedIn scraping or automation
- No auto-posting to LinkedIn
- No browser extensions or plugins
- No multi-user auth (local-first, single user)
