"""Tests for engagement-score ranking (Story 6.4)."""

from datetime import UTC, datetime, timedelta

import pytest
from backend.app.db.base import Base
from backend.app.models.reply_record import ReplyRecord
from backend.app.services.reply_repository import list_records, list_top_authors
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_T1 = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)
_T2 = _T1 + timedelta(minutes=5)
_T3 = _T1 + timedelta(minutes=10)


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


def _make_record(
    db: Session,
    *,
    author_name: str | None = "Author",
    engagement_score: int | None = 50,
    created_date: datetime = _T1,
) -> ReplyRecord:
    """Insert a minimal ReplyRecord directly (bypass scoring logic)."""
    record = ReplyRecord(
        post_text="text",
        preset_id="p1",
        prompt_text="prompt",
        created_date=created_date,
        status="draft",
        author_name=author_name,
        engagement_score=engagement_score,
    )
    db.add(record)
    db.flush()
    return record


# ---------------------------------------------------------------------------
# list_records sort_by="engagement_score"
# ---------------------------------------------------------------------------


class TestSortByEngagementScore:
    def test_higher_scores_first(self, db: Session) -> None:
        _make_record(db, author_name="Low", engagement_score=10)
        _make_record(db, author_name="High", engagement_score=90)
        _make_record(db, author_name="Mid", engagement_score=50)
        db.commit()

        records = list_records(db, sort_by="engagement_score")
        scores = [r.engagement_score for r in records]
        assert scores == [90, 50, 10]

    def test_nulls_appear_last(self, db: Session) -> None:
        _make_record(db, author_name="Scored", engagement_score=30)
        _make_record(db, author_name="Null", engagement_score=None)
        _make_record(db, author_name="Zero", engagement_score=0)
        db.commit()

        records = list_records(db, sort_by="engagement_score")
        names = [r.author_name for r in records]
        assert names[-1] == "Null"
        assert names[0] == "Scored"

    def test_equal_scores_tiebreak_by_created_date(
        self, db: Session,
    ) -> None:
        _make_record(db, author_name="Older", engagement_score=50, created_date=_T1)
        _make_record(db, author_name="Newer", engagement_score=50, created_date=_T2)
        db.commit()

        records = list_records(db, sort_by="engagement_score")
        names = [r.author_name for r in records]
        # Newer created_date first (DESC tiebreak)
        assert names == ["Newer", "Older"]

    def test_equal_scores_same_date_tiebreak_by_id(
        self, db: Session,
    ) -> None:
        r1 = _make_record(
            db, author_name="First", engagement_score=50, created_date=_T1,
        )
        r2 = _make_record(
            db, author_name="Second", engagement_score=50, created_date=_T1,
        )
        db.commit()

        records = list_records(db, sort_by="engagement_score")
        ids = [r.id for r in records]
        # Higher id first (DESC tiebreak)
        assert ids == [r2.id, r1.id]


class TestDefaultSortUnchanged:
    def test_default_sort_is_created_date_desc(self, db: Session) -> None:
        _make_record(db, author_name="Old", created_date=_T1, engagement_score=90)
        _make_record(db, author_name="New", created_date=_T3, engagement_score=10)
        db.commit()

        records = list_records(db)
        names = [r.author_name for r in records]
        assert names == ["New", "Old"]


# ---------------------------------------------------------------------------
# list_top_authors
# ---------------------------------------------------------------------------


class TestListTopAuthors:
    def test_ranked_by_max_score(self, db: Session) -> None:
        _make_record(db, author_name="Alice", engagement_score=80)
        _make_record(db, author_name="Alice", engagement_score=60)
        _make_record(db, author_name="Bob", engagement_score=90)
        db.commit()

        result = list_top_authors(db)
        assert result[0]["author_name"] == "Bob"
        assert result[0]["max_score"] == 90
        assert result[1]["author_name"] == "Alice"
        assert result[1]["max_score"] == 80

    def test_record_count(self, db: Session) -> None:
        _make_record(db, author_name="Alice", engagement_score=50)
        _make_record(db, author_name="Alice", engagement_score=60)
        _make_record(db, author_name="Alice", engagement_score=70)
        _make_record(db, author_name="Bob", engagement_score=90)
        db.commit()

        result = list_top_authors(db)
        alice = next(r for r in result if r["author_name"] == "Alice")
        bob = next(r for r in result if r["author_name"] == "Bob")
        assert alice["record_count"] == 3
        assert bob["record_count"] == 1

    def test_excludes_null_authors(self, db: Session) -> None:
        _make_record(db, author_name=None, engagement_score=99)
        _make_record(db, author_name="Alice", engagement_score=50)
        db.commit()

        result = list_top_authors(db)
        names = [r["author_name"] for r in result]
        assert None not in names
        assert names == ["Alice"]

    def test_tiebreak_alphabetical(self, db: Session) -> None:
        _make_record(db, author_name="Zara", engagement_score=50)
        _make_record(db, author_name="Alice", engagement_score=50)
        db.commit()

        result = list_top_authors(db)
        names = [r["author_name"] for r in result]
        assert names == ["Alice", "Zara"]

    def test_limit(self, db: Session) -> None:
        _make_record(db, author_name="A", engagement_score=90)
        _make_record(db, author_name="B", engagement_score=80)
        _make_record(db, author_name="C", engagement_score=70)
        db.commit()

        result = list_top_authors(db, limit=2)
        assert len(result) == 2
        assert result[0]["author_name"] == "A"

    def test_empty_table(self, db: Session) -> None:
        result = list_top_authors(db)
        assert result == []
