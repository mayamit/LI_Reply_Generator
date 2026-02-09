"""Tests for the ReplyRecord schema and repository (Issue #13)."""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.services.reply_repository import (
    InvalidTransitionError,
    RecordNotFoundError,
    approve_reply,
    create_draft,
    get_by_id,
    update_generated_reply,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def db() -> Session:  # type: ignore[misc]
    """Yield an in-memory SQLite session with the schema created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2025, 6, 1, 12, 5, 0, tzinfo=UTC)
_EVEN_LATER = datetime(2025, 6, 1, 12, 10, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# 1. Schema creation
# ---------------------------------------------------------------------------


class TestSchemaCreation:
    def test_table_exists(self, db: Session) -> None:
        result = db.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='reply_records'")
        )
        assert result.fetchone() is not None

    def test_all_columns_present(self, db: Session) -> None:
        result = db.execute(text("PRAGMA table_info('reply_records')"))
        columns = {row[1] for row in result.fetchall()}
        expected = {
            "id",
            "author_name",
            "author_profile_url",
            "post_url",
            "post_text",
            "article_text",
            "image_ref",
            "preset_id",
            "prompt_text",
            "generated_reply",
            "final_reply",
            "status",
            "created_date",
            "generated_at",
            "approved_at",
            "llm_model_identifier",
            "llm_request_id",
        }
        assert expected == columns


# ---------------------------------------------------------------------------
# 2. Create draft
# ---------------------------------------------------------------------------


class TestCreateDraft:
    def test_creates_draft_with_required_fields(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="A test post.",
            preset_id="prof_short_agree",
            prompt_text="Generated prompt text.",
            created_date=_NOW,
        )
        db.commit()
        assert record.id is not None
        assert record.status == "draft"
        assert record.post_text == "A test post."
        assert record.created_date == _NOW

    def test_creates_draft_with_optional_fields(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="A test post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
            author_name="Jane Doe",
            author_profile_url="https://linkedin.com/in/janedoe",
            post_url="https://linkedin.com/posts/123",
            article_text="Some article.",
            image_ref="diagram.png",
        )
        db.commit()
        assert record.author_name == "Jane Doe"
        assert record.image_ref == "diagram.png"


# ---------------------------------------------------------------------------
# 3. Update generated reply
# ---------------------------------------------------------------------------


class TestUpdateGeneratedReply:
    def test_updates_generated_fields(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Post text.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()

        updated = update_generated_reply(
            db,
            record.id,
            generated_reply="This is the LLM reply.",
            generated_at=_LATER,
            llm_model_identifier="claude-sonnet-4-5-20250929",
            llm_request_id="req-123",
        )
        db.commit()

        assert updated.generated_reply == "This is the LLM reply."
        assert updated.generated_at == _LATER
        assert updated.llm_model_identifier == "claude-sonnet-4-5-20250929"
        assert updated.llm_request_id == "req-123"
        assert updated.status == "draft"  # still draft


# ---------------------------------------------------------------------------
# 4. Approve reply
# ---------------------------------------------------------------------------


class TestApproveReply:
    def test_approve_transitions_to_approved(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()

        approved = approve_reply(
            db,
            record.id,
            final_reply="My final polished reply.",
            approved_at=_EVEN_LATER,
        )
        db.commit()

        assert approved.status == "approved"
        assert approved.final_reply == "My final polished reply."
        assert approved.approved_at == _EVEN_LATER


# ---------------------------------------------------------------------------
# 5. Approve idempotency
# ---------------------------------------------------------------------------


class TestApproveIdempotency:
    def test_double_approve_is_noop(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()

        approve_reply(
            db,
            record.id,
            final_reply="Final reply.",
            approved_at=_LATER,
        )
        db.commit()

        # Second approve — should be a no-op
        result = approve_reply(
            db,
            record.id,
            final_reply="Different text.",
            approved_at=_EVEN_LATER,
        )
        db.commit()

        assert result.status == "approved"
        # Original values preserved (idempotent)
        assert result.final_reply == "Final reply."
        assert result.approved_at == _LATER


# ---------------------------------------------------------------------------
# 6. Invalid approval (empty reply)
# ---------------------------------------------------------------------------


class TestInvalidApproval:
    def test_empty_final_reply_rejected(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()

        with pytest.raises(InvalidTransitionError, match="non-empty"):
            approve_reply(db, record.id, final_reply="", approved_at=_LATER)

    def test_whitespace_only_final_reply_rejected(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()

        with pytest.raises(InvalidTransitionError, match="non-empty"):
            approve_reply(db, record.id, final_reply="   ", approved_at=_LATER)


# ---------------------------------------------------------------------------
# 7. Not-found handling
# ---------------------------------------------------------------------------


class TestNotFound:
    def test_get_by_id_not_found(self, db: Session) -> None:
        with pytest.raises(RecordNotFoundError):
            get_by_id(db, 9999)

    def test_update_generated_not_found(self, db: Session) -> None:
        with pytest.raises(RecordNotFoundError):
            update_generated_reply(
                db,
                9999,
                generated_reply="reply",
                generated_at=_NOW,
            )

    def test_approve_not_found(self, db: Session) -> None:
        with pytest.raises(RecordNotFoundError):
            approve_reply(db, 9999, final_reply="reply", approved_at=_NOW)


# ---------------------------------------------------------------------------
# 8. getById returns accurate data
# ---------------------------------------------------------------------------


class TestGetById:
    def test_returns_all_fields(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Full test post.",
            preset_id="casual_medium_add",
            prompt_text="Full prompt.",
            created_date=_NOW,
            author_name="Bob",
        )
        db.commit()

        fetched = get_by_id(db, record.id)
        assert fetched.post_text == "Full test post."
        assert fetched.preset_id == "casual_medium_add"
        assert fetched.author_name == "Bob"
        assert fetched.status == "draft"
