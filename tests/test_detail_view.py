"""Tests for history detail view data layer (Story 3.4).

Covers all 3 acceptance criteria:
  AC1: All stored fields are accessible for display
  AC2: Draft records have empty approved fields
  AC3: URL fields are present for link rendering
"""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.models.presets import get_preset_labels
from backend.app.services.reply_repository import (
    RecordNotFoundError,
    approve_reply,
    create_draft,
    get_by_id,
    update_generated_reply,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_T0 = datetime(2025, 4, 1, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2025, 4, 1, 10, 5, 0, tzinfo=UTC)
_T2 = datetime(2025, 4, 1, 10, 10, 0, tzinfo=UTC)


@pytest.fixture()
def db() -> Session:  # type: ignore[misc]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def _create_full_record(db: Session) -> int:
    """Create a record with all fields populated, return its id."""
    record = create_draft(
        db,
        post_text="Full detail test post content.",
        preset_id="prof_short_agree",
        prompt_text="Full prompt text.",
        created_date=_T0,
        author_name="Jane Doe",
        author_profile_url="https://linkedin.com/in/janedoe",
        post_url="https://linkedin.com/posts/12345",
        article_text="Article body for testing.",
        image_ref="diagram.png",
    )
    db.commit()
    update_generated_reply(
        db,
        record.id,
        generated_reply="This is the LLM-generated reply.",
        generated_at=_T1,
        llm_model_identifier="claude-sonnet-4-5-20250929",
        llm_request_id="req-abc-123",
    )
    db.commit()
    return record.id


# ---------------------------------------------------------------------------
# AC1: All stored fields are displayed
# ---------------------------------------------------------------------------


class TestAllFieldsDisplayed:
    def test_draft_record_has_all_context_fields(
        self, db: Session,
    ) -> None:
        rid = _create_full_record(db)
        r = get_by_id(db, rid)

        # Context fields
        assert r.author_name == "Jane Doe"
        assert r.author_profile_url == "https://linkedin.com/in/janedoe"
        assert r.post_url == "https://linkedin.com/posts/12345"
        assert r.post_text == "Full detail test post content."
        assert r.article_text == "Article body for testing."
        assert r.image_ref == "diagram.png"

    def test_draft_record_has_generation_fields(
        self, db: Session,
    ) -> None:
        rid = _create_full_record(db)
        r = get_by_id(db, rid)

        assert r.preset_id == "prof_short_agree"
        assert r.generated_reply == "This is the LLM-generated reply."
        assert r.generated_at is not None
        assert r.llm_model_identifier == "claude-sonnet-4-5-20250929"
        assert r.llm_request_id == "req-abc-123"

    def test_approved_record_has_all_fields(
        self, db: Session,
    ) -> None:
        rid = _create_full_record(db)
        approve_reply(
            db, rid, final_reply="Polished final reply.", approved_at=_T2,
        )
        db.commit()

        r = get_by_id(db, rid)
        assert r.status == "approved"
        assert r.final_reply == "Polished final reply."
        assert r.approved_at is not None
        # Original fields still present
        assert r.generated_reply == "This is the LLM-generated reply."
        assert r.post_text == "Full detail test post content."

    def test_preset_label_resolvable_for_display(self) -> None:
        labels = get_preset_labels()
        assert "prof_short_agree" in labels

    def test_timestamps_accessible(self, db: Session) -> None:
        rid = _create_full_record(db)
        r = get_by_id(db, rid)
        assert r.created_date is not None
        # Can format for display
        assert r.created_date.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# AC2: Draft records show empty approved fields
# ---------------------------------------------------------------------------


class TestDraftEmptyApproved:
    def test_draft_has_no_final_reply(self, db: Session) -> None:
        rid = _create_full_record(db)
        r = get_by_id(db, rid)
        assert r.status == "draft"
        assert r.final_reply is None

    def test_draft_has_no_approved_at(self, db: Session) -> None:
        rid = _create_full_record(db)
        r = get_by_id(db, rid)
        assert r.approved_at is None

    def test_minimal_draft_has_empty_optional_fields(
        self, db: Session,
    ) -> None:
        record = create_draft(
            db,
            post_text="Minimal post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        db.commit()

        r = get_by_id(db, record.id)
        assert r.author_name is None
        assert r.author_profile_url is None
        assert r.post_url is None
        assert r.article_text is None
        assert r.image_ref is None
        assert r.generated_reply is None
        assert r.final_reply is None
        assert r.approved_at is None


# ---------------------------------------------------------------------------
# AC3: URL fields present for link rendering
# ---------------------------------------------------------------------------


class TestUrlFields:
    def test_author_profile_url_present(self, db: Session) -> None:
        rid = _create_full_record(db)
        r = get_by_id(db, rid)
        assert r.author_profile_url is not None
        assert r.author_profile_url.startswith("https://")

    def test_post_url_present(self, db: Session) -> None:
        rid = _create_full_record(db)
        r = get_by_id(db, rid)
        assert r.post_url is not None
        assert r.post_url.startswith("https://")

    def test_urls_none_when_not_provided(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="No URL post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        db.commit()
        r = get_by_id(db, record.id)
        assert r.author_profile_url is None
        assert r.post_url is None


# ---------------------------------------------------------------------------
# Not found
# ---------------------------------------------------------------------------


class TestNotFound:
    def test_nonexistent_record_raises(self, db: Session) -> None:
        with pytest.raises(RecordNotFoundError):
            get_by_id(db, 99999)
