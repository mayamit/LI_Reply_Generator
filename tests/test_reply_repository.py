"""Tests for the ReplyRecord schema and repository (Issue #13, Story 3.1)."""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.models.reply_record import VALID_STATUSES, ReplyRecord
from backend.app.services.reply_repository import (
    InvalidTransitionError,
    RecordNotFoundError,
    approve_reply,
    create_draft,
    get_by_id,
    update_generated_reply,
)
from sqlalchemy import create_engine, inspect, text
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


# ---------------------------------------------------------------------------
# Story 3.1: Schema hardening — indexes
# ---------------------------------------------------------------------------


class TestIndexes:
    def test_indexes_exist_on_fresh_schema(self, db: Session) -> None:
        """AC3: Indexes on created_date, status, author_name exist."""
        insp = inspect(db.bind)
        indexes = insp.get_indexes("reply_records")
        index_names = {idx["name"] for idx in indexes}
        assert "ix_reply_records_created_date" in index_names
        assert "ix_reply_records_status" in index_names
        assert "ix_reply_records_author_name" in index_names

    def test_index_columns_correct(self, db: Session) -> None:
        insp = inspect(db.bind)
        indexes = {
            idx["name"]: idx["column_names"]
            for idx in insp.get_indexes("reply_records")
        }
        assert indexes["ix_reply_records_created_date"] == [
            "created_date",
        ]
        assert indexes["ix_reply_records_status"] == ["status"]
        assert indexes["ix_reply_records_author_name"] == [
            "author_name",
        ]


# ---------------------------------------------------------------------------
# Story 3.1: Schema hardening — status constraint
# ---------------------------------------------------------------------------


class TestStatusConstraint:
    def test_valid_statuses_constant(self) -> None:
        assert "draft" in VALID_STATUSES
        assert "approved" in VALID_STATUSES
        assert len(VALID_STATUSES) == 2

    def test_draft_status_accepted(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Test post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()
        assert record.status == "draft"

    def test_approved_status_accepted(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Test post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()
        approved = approve_reply(
            db,
            record.id,
            final_reply="Final.",
            approved_at=_LATER,
        )
        db.commit()
        assert approved.status == "approved"

    def test_invalid_status_rejected_by_db(self, db: Session) -> None:
        """AC4: Invalid status values are rejected."""
        from sqlalchemy.exc import IntegrityError

        record = ReplyRecord(
            post_text="Test.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
            status="invalid_status",
        )
        db.add(record)
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


# ---------------------------------------------------------------------------
# Story 3.1: Schema hardening — server default
# ---------------------------------------------------------------------------


class TestServerDefault:
    def test_status_defaults_to_draft(self, db: Session) -> None:
        """Status column has server_default='draft'."""
        result = db.execute(
            text("PRAGMA table_info('reply_records')")
        )
        columns = {row[1]: row for row in result.fetchall()}
        status_col = columns["status"]
        # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
        assert status_col[4] == "'draft'"


# ---------------------------------------------------------------------------
# Story 3.1: Fresh install smoke test
# ---------------------------------------------------------------------------


class TestFreshInstall:
    def test_create_all_on_fresh_db(self) -> None:
        """AC1: Fresh install creates table successfully."""
        eng = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(eng)
        insp = inspect(eng)
        assert "reply_records" in insp.get_table_names()
        eng.dispose()

    def test_full_lifecycle_on_fresh_db(self) -> None:
        """Smoke test: create → update → approve on fresh DB."""
        eng = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(eng)
        sess = sessionmaker(bind=eng, expire_on_commit=False)()

        record = create_draft(
            sess,
            post_text="Lifecycle test.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        sess.commit()
        assert record.status == "draft"

        update_generated_reply(
            sess,
            record.id,
            generated_reply="Generated.",
            generated_at=_LATER,
        )
        sess.commit()

        approved = approve_reply(
            sess,
            record.id,
            final_reply="Final.",
            approved_at=_EVEN_LATER,
        )
        sess.commit()
        assert approved.status == "approved"

        sess.close()
        eng.dispose()
