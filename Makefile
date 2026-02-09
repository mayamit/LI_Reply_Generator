.PHONY: install run-api run-ui test lint format migrate

install:
	pip install -e ".[dev]"

run-api:
	uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

run-ui:
	streamlit run streamlit_app.py

test:
	pytest -v

lint:
	ruff check backend/ tests/
	ruff format --check backend/ tests/

format:
	ruff check --fix backend/ tests/
	ruff format backend/ tests/

migrate:
	alembic upgrade head
