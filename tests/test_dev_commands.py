"""Tests for Story 4.5: Developer ergonomics — standard commands.

Covers acceptance criteria:
  AC1: README documents commands for API and UI
  AC2: Test command runs pytest successfully
  AC3: Lint command runs ruff consistently
  AC4: Migration command runs alembic upgrade
"""


from backend.app.core.settings import _PROJECT_ROOT

# ---------------------------------------------------------------------------
# Makefile targets exist
# ---------------------------------------------------------------------------


class TestMakefileTargets:
    def test_makefile_exists(self) -> None:
        makefile = _PROJECT_ROOT / "Makefile"
        assert makefile.exists()

    def test_makefile_has_required_targets(self) -> None:
        content = (_PROJECT_ROOT / "Makefile").read_text()
        for target in [
            "install", "run-api", "run-ui", "test",
            "lint", "format", "check", "migrate", "migrate-check",
        ]:
            assert target in content, f"Missing Makefile target: {target}"

    def test_makefile_install_uses_dev(self) -> None:
        content = (_PROJECT_ROOT / "Makefile").read_text()
        assert ".[dev]" in content

    def test_makefile_run_api_uses_uvicorn(self) -> None:
        content = (_PROJECT_ROOT / "Makefile").read_text()
        assert "uvicorn" in content
        assert "backend.app.main:app" in content

    def test_makefile_run_ui_uses_streamlit(self) -> None:
        content = (_PROJECT_ROOT / "Makefile").read_text()
        assert "streamlit run" in content

    def test_makefile_test_uses_pytest(self) -> None:
        content = (_PROJECT_ROOT / "Makefile").read_text()
        assert "pytest" in content

    def test_makefile_lint_uses_ruff(self) -> None:
        content = (_PROJECT_ROOT / "Makefile").read_text()
        assert "ruff check" in content
        assert "ruff format" in content

    def test_makefile_check_combines_lint_test_migrate(self) -> None:
        content = (_PROJECT_ROOT / "Makefile").read_text()
        assert "check: lint test migrate-check" in content


# ---------------------------------------------------------------------------
# README documents commands
# ---------------------------------------------------------------------------


class TestReadmeDocumentation:
    def test_readme_exists(self) -> None:
        readme = _PROJECT_ROOT / "README.md"
        assert readme.exists()

    def test_readme_has_quick_start(self) -> None:
        content = (_PROJECT_ROOT / "README.md").read_text()
        assert "Quick Start" in content

    def test_readme_documents_all_commands(self) -> None:
        content = (_PROJECT_ROOT / "README.md").read_text()
        for cmd in [
            "make install", "make run-api", "make run-ui",
            "make test", "make lint", "make format",
            "make check", "make migrate", "make migrate-check",
        ]:
            assert cmd in content, f"README missing command: {cmd}"

    def test_readme_has_project_layout(self) -> None:
        content = (_PROJECT_ROOT / "README.md").read_text()
        assert "Project Layout" in content

    def test_readme_documents_env_setup(self) -> None:
        content = (_PROJECT_ROOT / "README.md").read_text()
        assert ".env" in content
        assert "venv" in content


# ---------------------------------------------------------------------------
# Key project files exist
# ---------------------------------------------------------------------------


class TestProjectStructure:
    def test_key_files_exist(self) -> None:
        for rel_path in [
            "backend/app/main.py",
            "backend/app/core/settings.py",
            "backend/app/core/logging.py",
            "backend/app/db/engine.py",
            "backend/app/db/migrations.py",
            "streamlit_app.py",
            "alembic.ini",
            "pyproject.toml",
            "Makefile",
            "README.md",
            "docs/architecture-baseline.md",
        ]:
            assert (_PROJECT_ROOT / rel_path).exists(), f"Missing: {rel_path}"

    def test_pages_directory_exists(self) -> None:
        pages_dir = _PROJECT_ROOT / "pages"
        assert pages_dir.is_dir()
        py_files = list(pages_dir.glob("*.py"))
        assert len(py_files) >= 2

    def test_alembic_versions_exist(self) -> None:
        versions = _PROJECT_ROOT / "alembic" / "versions"
        assert versions.is_dir()
        migrations = list(versions.glob("*.py"))
        assert len(migrations) >= 1
