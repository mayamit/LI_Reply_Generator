"""Tests for history list UI integration (Story 3.3).

Streamlit UI rendering requires a running Streamlit server, so these tests
verify the data layer integration that powers the history page.
"""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.models.presets import get_preset_labels
from backend.app.services.reply_repository import (
    approve_reply,
    count_records,
    create_draft,
    list_records,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_T0 = datetime(2025, 3, 1, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2025, 3, 2, 10, 0, 0, tzinfo=UTC)
_T2 = datetime(2025, 3, 3, 10, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db() -> Session:  # type: ignore[misc]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# AC1: Empty state
# ---------------------------------------------------------------------------


class TestEmptyState:
    def test_no_records_returns_zero_count(self, db: Session) -> None:
        assert count_records(db) == 0

    def test_no_records_returns_empty_list(self, db: Session) -> None:
        assert list_records(db) == []


# ---------------------------------------------------------------------------
# AC2: Records displayed with correct fields
# ---------------------------------------------------------------------------


class TestRecordDisplay:
    def test_records_have_display_fields(self, db: Session) -> None:
        create_draft(
            db,
            post_text="Test post content.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
            author_name="Jane Doe",
        )
        db.commit()

        records = list_records(db)
        assert len(records) == 1
        r = records[0]
        # All display fields accessible
        assert r.author_name == "Jane Doe"
        assert r.preset_id == "prof_short_agree"
        assert r.status == "draft"
        assert r.created_date is not None

    def test_preset_label_resolvable(self) -> None:
        labels = get_preset_labels()
        assert "prof_short_agree" in labels
        assert len(labels["prof_short_agree"]) > 0

    def test_records_ordered_newest_first(self, db: Session) -> None:
        create_draft(
            db,
            post_text="Old post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        create_draft(
            db,
            post_text="New post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T2,
        )
        db.commit()

        records = list_records(db)
        assert records[0].post_text == "New post."
        assert records[1].post_text == "Old post."


# ---------------------------------------------------------------------------
# AC3: Status filter
# ---------------------------------------------------------------------------


class TestStatusFilter:
    def test_filter_shows_only_matching_status(
        self, db: Session,
    ) -> None:
        r1 = create_draft(
            db,
            post_text="Draft post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        r2 = create_draft(
            db,
            post_text="Approved post.",
            preset_id="casual_medium_add",
            prompt_text="Prompt.",
            created_date=_T1,
        )
        approve_reply(
            db, r2.id, final_reply="Final.", approved_at=_T2,
        )
        db.commit()

        drafts = list_records(db, status="draft")
        assert len(drafts) == 1
        assert drafts[0].id == r1.id

        approved = list_records(db, status="approved")
        assert len(approved) == 1
        assert approved[0].id == r2.id

    def test_all_filter_returns_everything(
        self, db: Session,
    ) -> None:
        create_draft(
            db,
            post_text="Post 1.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        r2 = create_draft(
            db,
            post_text="Post 2.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T1,
        )
        approve_reply(
            db, r2.id, final_reply="Final.", approved_at=_T2,
        )
        db.commit()

        all_records = list_records(db)
        assert len(all_records) == 2


# ---------------------------------------------------------------------------
# AC4: Record navigable by ID (detail view readiness)
# ---------------------------------------------------------------------------


class TestDetailNavigation:
    def test_record_accessible_by_id(self, db: Session) -> None:
        from backend.app.services.reply_repository import get_by_id

        record = create_draft(
            db,
            post_text="Navigable post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        db.commit()

        fetched = get_by_id(db, record.id)
        assert fetched.post_text == "Navigable post."


# ---------------------------------------------------------------------------
# Page module imports
# ---------------------------------------------------------------------------


class TestPageImports:
    def test_history_page_importable(self) -> None:
        """Verify the history page module can be imported."""
        import importlib

        spec = importlib.util.find_spec("pages.1_History")
        # Module is findable (may not be runnable outside Streamlit)
        assert spec is not None

    def test_detail_page_importable(self) -> None:
        import importlib

        spec = importlib.util.find_spec("pages.2_Detail")
        assert spec is not None
