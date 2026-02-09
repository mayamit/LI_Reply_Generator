"""Tests for history listing and filtering queries (Story 3.2).

Covers all 5 acceptance criteria:
  AC1: Results ordered by created_date DESC
  AC2: Filter by status
  AC3: Filter by author_name (contains, case-insensitive)
  AC4: Filter by date range
  AC5: Pagination (offset/limit)
"""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.services.reply_repository import (
    DEFAULT_PAGE_SIZE,
    approve_reply,
    count_records,
    create_draft,
    list_records,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_T0 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2025, 1, 2, 10, 0, 0, tzinfo=UTC)
_T2 = datetime(2025, 1, 3, 10, 0, 0, tzinfo=UTC)
_T3 = datetime(2025, 1, 4, 10, 0, 0, tzinfo=UTC)
_T4 = datetime(2025, 1, 5, 10, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db() -> Session:  # type: ignore[misc]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def _seed(db: Session) -> list[int]:
    """Seed 5 records with varying dates, authors, and statuses.

    Returns list of record IDs in creation order (oldest first).
    """
    ids = []
    for i, (ts, author) in enumerate([
        (_T0, "Alice Smith"),
        (_T1, "Bob Jones"),
        (_T2, "Alice Smith"),
        (_T3, None),
        (_T4, "Charlie Brown"),
    ]):
        r = create_draft(
            db,
            post_text=f"Post {i}",
            preset_id="prof_short_agree",
            prompt_text=f"Prompt {i}",
            created_date=ts,
            author_name=author,
        )
        ids.append(r.id)
    # Approve records 0 and 2 (both Alice)
    approve_reply(db, ids[0], final_reply="Final 0", approved_at=_T1)
    approve_reply(db, ids[2], final_reply="Final 2", approved_at=_T3)
    db.commit()
    return ids


# ---------------------------------------------------------------------------
# AC1: Results ordered by created_date DESC
# ---------------------------------------------------------------------------


class TestOrdering:
    def test_default_order_is_newest_first(self, db: Session) -> None:
        _seed(db)
        records = list_records(db)
        dates = [r.created_date for r in records]
        assert dates == sorted(dates, reverse=True)

    def test_ordering_stable_across_calls(self, db: Session) -> None:
        _seed(db)
        r1 = list_records(db)
        r2 = list_records(db)
        assert [r.id for r in r1] == [r.id for r in r2]


# ---------------------------------------------------------------------------
# AC2: Filter by status
# ---------------------------------------------------------------------------


class TestStatusFilter:
    def test_filter_approved_only(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, status="approved")
        assert len(records) == 2
        assert all(r.status == "approved" for r in records)

    def test_filter_draft_only(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, status="draft")
        assert len(records) == 3
        assert all(r.status == "draft" for r in records)

    def test_no_filter_returns_all(self, db: Session) -> None:
        _seed(db)
        records = list_records(db)
        assert len(records) == 5

    def test_count_matches_filter(self, db: Session) -> None:
        _seed(db)
        assert count_records(db, status="approved") == 2
        assert count_records(db, status="draft") == 3
        assert count_records(db) == 5


# ---------------------------------------------------------------------------
# AC3: Filter by author_name (contains, case-insensitive)
# ---------------------------------------------------------------------------


class TestAuthorFilter:
    def test_filter_by_exact_name(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, author_name="Alice Smith")
        assert len(records) == 2

    def test_filter_by_partial_name(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, author_name="alice")
        assert len(records) == 2

    def test_filter_case_insensitive(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, author_name="ALICE")
        assert len(records) == 2

    def test_filter_no_match(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, author_name="Zara")
        assert len(records) == 0

    def test_combined_author_and_status(self, db: Session) -> None:
        _seed(db)
        records = list_records(
            db, author_name="Alice", status="approved",
        )
        assert len(records) == 2
        assert all(r.status == "approved" for r in records)


# ---------------------------------------------------------------------------
# AC4: Filter by date range
# ---------------------------------------------------------------------------


class TestDateRangeFilter:
    def test_created_after(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, created_after=_T3)
        assert len(records) == 2  # T3 and T4
        # SQLite returns naive datetimes; compare naive-to-naive
        assert all(
            r.created_date >= _T3.replace(tzinfo=None) for r in records
        )

    def test_created_before(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, created_before=_T1)
        assert len(records) == 2  # T0 and T1
        assert all(
            r.created_date <= _T1.replace(tzinfo=None) for r in records
        )

    def test_date_range(self, db: Session) -> None:
        _seed(db)
        records = list_records(
            db, created_after=_T1, created_before=_T3,
        )
        assert len(records) == 3  # T1, T2, T3
        t1_naive = _T1.replace(tzinfo=None)
        t3_naive = _T3.replace(tzinfo=None)
        for r in records:
            assert t1_naive <= r.created_date <= t3_naive

    def test_date_range_no_match(self, db: Session) -> None:
        _seed(db)
        future = datetime(2099, 1, 1, tzinfo=UTC)
        records = list_records(db, created_after=future)
        assert len(records) == 0


# ---------------------------------------------------------------------------
# AC5: Pagination
# ---------------------------------------------------------------------------


class TestPagination:
    def test_default_page_size(self) -> None:
        assert DEFAULT_PAGE_SIZE == 20

    def test_limit_restricts_results(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, limit=2)
        assert len(records) == 2

    def test_offset_skips_records(self, db: Session) -> None:
        _seed(db)
        all_records = list_records(db)
        page2 = list_records(db, offset=2, limit=2)
        assert len(page2) == 2
        assert page2[0].id == all_records[2].id
        assert page2[1].id == all_records[3].id

    def test_offset_past_end_returns_empty(self, db: Session) -> None:
        _seed(db)
        records = list_records(db, offset=100)
        assert len(records) == 0

    def test_pagination_preserves_ordering(self, db: Session) -> None:
        _seed(db)
        page1 = list_records(db, offset=0, limit=3)
        page2 = list_records(db, offset=3, limit=3)
        all_ids = [r.id for r in page1] + [r.id for r in page2]
        full = [r.id for r in list_records(db, limit=100)]
        assert all_ids == full

    def test_empty_db_returns_empty(self, db: Session) -> None:
        records = list_records(db)
        assert records == []
