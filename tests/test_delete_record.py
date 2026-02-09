"""Tests for record deletion (Story 3.5).

Covers all 3 acceptance criteria:
  AC1: Delete action exists (tested via repository method)
  AC2: Record is permanently removed after deletion
  AC3: Deleting a nonexistent record raises a controlled error
"""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.services.reply_repository import (
    RecordNotFoundError,
    approve_reply,
    count_records,
    create_draft,
    delete_record,
    get_by_id,
    list_records,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_T0 = datetime(2025, 5, 1, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2025, 5, 1, 10, 5, 0, tzinfo=UTC)


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
# AC2: Record permanently removed
# ---------------------------------------------------------------------------


class TestDeleteRemovesRecord:
    def test_delete_removes_draft(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="To be deleted.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        db.commit()
        rid = record.id

        delete_record(db, rid)
        db.commit()

        with pytest.raises(RecordNotFoundError):
            get_by_id(db, rid)

    def test_delete_removes_approved(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Approved then deleted.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        approve_reply(
            db, record.id, final_reply="Final.", approved_at=_T1,
        )
        db.commit()

        delete_record(db, record.id)
        db.commit()

        with pytest.raises(RecordNotFoundError):
            get_by_id(db, record.id)

    def test_delete_decrements_count(self, db: Session) -> None:
        r1 = create_draft(
            db,
            post_text="Post 1.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        create_draft(
            db,
            post_text="Post 2.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T1,
        )
        db.commit()
        assert count_records(db) == 2

        delete_record(db, r1.id)
        db.commit()
        assert count_records(db) == 1

    def test_delete_removes_from_list(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Listed then removed.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        db.commit()
        assert len(list_records(db)) == 1

        delete_record(db, record.id)
        db.commit()
        assert len(list_records(db)) == 0

    def test_delete_does_not_affect_other_records(
        self, db: Session,
    ) -> None:
        r1 = create_draft(
            db,
            post_text="Keep this.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        r2 = create_draft(
            db,
            post_text="Delete this.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T1,
        )
        db.commit()

        delete_record(db, r2.id)
        db.commit()

        kept = get_by_id(db, r1.id)
        assert kept.post_text == "Keep this."


# ---------------------------------------------------------------------------
# AC3: Controlled error on failure
# ---------------------------------------------------------------------------


class TestDeleteErrors:
    def test_delete_nonexistent_raises(self, db: Session) -> None:
        with pytest.raises(RecordNotFoundError):
            delete_record(db, 99999)

    def test_double_delete_raises(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Double delete.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_T0,
        )
        db.commit()

        delete_record(db, record.id)
        db.commit()

        with pytest.raises(RecordNotFoundError):
            delete_record(db, record.id)
