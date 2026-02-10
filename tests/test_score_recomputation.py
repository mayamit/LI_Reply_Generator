"""Tests for score recomputation job (Story 6.5)."""

import json
import time
from datetime import UTC, datetime

import pytest
from backend.app.core.scheduler import RepeatingJob
from backend.app.db.base import Base
from backend.app.models.reply_record import ReplyRecord
from backend.app.services.reply_repository import create_draft
from backend.app.services.score_recomputation import recompute_all_scores
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db() -> Session:  # type: ignore[misc]
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


def _insert_record(
    db: Session,
    *,
    author_name: str | None = "Alice",
    follower_count: int | None = 100,
    like_count: int | None = None,
    comment_count: int | None = None,
    repost_count: int | None = None,
    engagement_score: int | None = 0,
    score_breakdown: str | None = None,
) -> ReplyRecord:
    """Insert a record directly, bypassing auto-scoring in create_draft."""
    record = ReplyRecord(
        post_text="text",
        preset_id="p1",
        prompt_text="prompt",
        created_date=_NOW,
        status="draft",
        author_name=author_name,
        follower_count=follower_count,
        like_count=like_count,
        comment_count=comment_count,
        repost_count=repost_count,
        engagement_score=engagement_score,
        score_breakdown=score_breakdown,
    )
    db.add(record)
    db.flush()
    return record


# ---------------------------------------------------------------------------
# AC1: Scores are recomputed successfully
# ---------------------------------------------------------------------------


class TestRecomputeUpdatesStaleScores:
    def test_stale_score_updated(self, db: Session) -> None:
        record = _insert_record(
            db, follower_count=5000, engagement_score=0,
        )
        db.commit()
        assert record.engagement_score == 0

        updated = recompute_all_scores(db)
        db.commit()

        db.refresh(record)
        assert record.engagement_score > 0
        assert updated == 1

    def test_updates_breakdown(self, db: Session) -> None:
        _insert_record(db, follower_count=500, score_breakdown=None)
        db.commit()

        recompute_all_scores(db)
        db.commit()

        record = db.query(ReplyRecord).first()
        assert record.score_breakdown is not None
        breakdown = json.loads(record.score_breakdown)
        assert "follower_count" in breakdown


# ---------------------------------------------------------------------------
# AC2: Failure is logged and app continues
# ---------------------------------------------------------------------------


class TestFailureHandling:
    def test_exception_does_not_propagate_from_scheduler(self) -> None:
        call_count = {"n": 0}

        def failing_job() -> None:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated failure")

        job = RepeatingJob(failing_job, interval_seconds=0.05)
        job.start()
        time.sleep(0.2)
        job.stop()

        # Job ran at least twice: failed once, then recovered
        assert call_count["n"] >= 2


# ---------------------------------------------------------------------------
# AC3: Idempotent — same inputs → same scores
# ---------------------------------------------------------------------------


class TestIdempotent:
    def test_recompute_twice_same_result(self, db: Session) -> None:
        _insert_record(db, follower_count=1000, like_count=50)
        db.commit()

        recompute_all_scores(db)
        db.commit()
        record = db.query(ReplyRecord).first()
        score_after_first = record.engagement_score

        updated = recompute_all_scores(db)
        db.commit()
        db.refresh(record)

        assert record.engagement_score == score_after_first
        assert updated == 0  # No changes on second run


# ---------------------------------------------------------------------------
# Interaction count affects recomputation
# ---------------------------------------------------------------------------


class TestInteractionCountRecompute:
    def test_new_records_increase_score_on_recompute(
        self, db: Session,
    ) -> None:
        # Create first record via create_draft (gets auto-scored)
        r1 = create_draft(
            db,
            post_text="first",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Alice",
            follower_count=100,
        )
        db.commit()
        original_score = r1.engagement_score

        # Create a second record for same author (increases interaction count)
        create_draft(
            db,
            post_text="second",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Alice",
            follower_count=100,
        )
        db.commit()

        # Recompute — r1's interaction_count is now 2 (both records)
        recompute_all_scores(db)
        db.commit()

        db.refresh(r1)
        assert r1.engagement_score >= original_score


# ---------------------------------------------------------------------------
# Scheduler start/stop
# ---------------------------------------------------------------------------


class TestRepeatingJob:
    def test_start_and_stop(self) -> None:
        counter = {"n": 0}

        def increment() -> None:
            counter["n"] += 1

        job = RepeatingJob(increment, interval_seconds=0.05)
        job.start()
        time.sleep(0.2)
        job.stop()

        final = counter["n"]
        assert final >= 1

        # After stop, count should not increase
        time.sleep(0.15)
        assert counter["n"] == final

    def test_stop_before_start_is_safe(self) -> None:
        job = RepeatingJob(lambda: None, interval_seconds=60)
        job.stop()  # Should not raise


# ---------------------------------------------------------------------------
# Empty table
# ---------------------------------------------------------------------------


class TestEmptyTable:
    def test_no_records_returns_zero(self, db: Session) -> None:
        updated = recompute_all_scores(db)
        assert updated == 0
