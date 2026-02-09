.PHONY: install run-api run-ui test lint format check migrate migrate-check

install:
	pip install -e ".[dev]"

run-api:
	uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

run-ui:
	streamlit run streamlit_app.py

test:
	pytest -v

lint:
	ruff check backend/ tests/ streamlit_app.py pages/
	ruff format --check backend/ tests/ streamlit_app.py pages/

format:
	ruff check --fix backend/ tests/ streamlit_app.py pages/
	ruff format backend/ tests/ streamlit_app.py pages/

check: lint test migrate-check

migrate:
	alembic upgrade head

migrate-check:
	python -c "from backend.app.db.migrations import check_schema_current; exit(0 if check_schema_current() else 1)"
