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
      logging.py         # structured logging + event taxonomy
    db/
      engine.py          # SQLAlchemy engine (SQLite)
      session.py         # session factory + FastAPI dependency
      base.py            # declarative base for ORM models
      migrations.py      # programmatic Alembic runner
    models/
      reply_record.py    # ReplyRecord ORM model
      presets.py         # reply presets (tone, length, intent)
      post_context.py    # input/output validation models
      llm.py             # LLM request/response models
    services/
      llm_client.py      # LLM provider abstraction
      prompt_builder.py  # deterministic prompt assembly
      reply_repository.py # CRUD for reply records
      validation.py      # shared input validation
    api/routes/
      health.py          # GET /health
      post_context.py    # POST /api/v1/post-context
      generate.py        # POST /api/v1/generate
      approve.py         # POST /api/v1/approve
streamlit_app.py         # Streamlit UI (main page)
pages/
  1_History.py           # History list page
  2_Detail.py            # Record detail page
alembic/                 # Alembic migrations
docs/
  architecture-baseline.md # Architecture conventions
data/                    # SQLite DB file (gitignored)
tests/                   # pytest tests
```

## Common Commands

| Command              | Description                              |
|----------------------|------------------------------------------|
| `make install`       | Install project + dev dependencies       |
| `make run-api`       | Start FastAPI dev server                 |
| `make run-ui`        | Start Streamlit UI                       |
| `make test`          | Run pytest                               |
| `make lint`          | Run ruff linter + format check           |
| `make format`        | Auto-fix lint issues + format code       |
| `make check`         | Run lint + test + migrate-check together |
| `make migrate`       | Apply Alembic migrations                 |
| `make migrate-check` | Verify DB schema is at head (CI-ready)   |

## Prompt Builder

The deterministic prompt assembly module lives at `backend/app/services/prompt_builder.py`. Run its tests with `pytest tests/test_prompt_builder.py -v`.

## LLM Integration

The LLM client abstraction lives at `backend/app/services/llm_client.py`. It auto-selects a provider based on env vars:

| Variable | Provider |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic (preferred) |
| `OPENAI_API_KEY` | OpenAI (fallback) |
| `LLM_TIMEOUT_SECONDS` | Request timeout (default: 30) |
| *(none set)* | MockProvider (returns canned reply) |

## Database

The SQLite database lives at `data/app.db`. This directory is gitignored.
To reset the DB, delete `data/app.db` and re-run `make migrate`.

## Non-Goals (current scope)

- No LinkedIn scraping or automation
- No auto-posting to LinkedIn
- No browser extensions or plugins
- No multi-user auth (local-first, single user)
