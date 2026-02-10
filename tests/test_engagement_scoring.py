"""Tests for engagement scoring (Stories 6.2 & 6.3)."""

import json
from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.services.engagement_scoring import (
    CAPS,
    WEIGHTS,
    EngagementScore,
    compute_engagement_score,
    score_to_label,
)
from backend.app.services.reply_repository import count_by_author, create_draft
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ALL_SIGNAL_KEYS = {
    "follower_count", "like_count", "comment_count",
    "repost_count", "interaction_count",
}

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# AC1: Deterministic – same inputs → same score
# ---------------------------------------------------------------------------


class TestDeterministic:
    def test_same_inputs_same_score(self) -> None:
        kwargs = dict(
            follower_count=5000,
            like_count=200,
            comment_count=50,
            repost_count=30,
            interaction_count=10,
        )
        results = [compute_engagement_score(**kwargs) for _ in range(5)]
        scores = [r.score for r in results]
        assert len(set(scores)) == 1

    def test_breakdowns_identical_across_calls(self) -> None:
        kwargs = dict(follower_count=100, like_count=10)
        a = compute_engagement_score(**kwargs)
        b = compute_engagement_score(**kwargs)
        assert a.breakdown == b.breakdown


# ---------------------------------------------------------------------------
# AC2: Missing signals
# ---------------------------------------------------------------------------


class TestMissingSignals:
    def test_all_none_returns_zero(self) -> None:
        result = compute_engagement_score()
        assert result.score == 0

    def test_all_none_no_errors(self) -> None:
        result = compute_engagement_score()
        assert isinstance(result, EngagementScore)
        assert result.breakdown is not None

    def test_partial_signals(self) -> None:
        result = compute_engagement_score(follower_count=1000, comment_count=50)
        assert 0 <= result.score <= 100

    def test_explicit_none_values(self) -> None:
        result = compute_engagement_score(
            follower_count=None,
            like_count=None,
            comment_count=None,
            repost_count=None,
            interaction_count=None,
        )
        assert result.score == 0


# ---------------------------------------------------------------------------
# AC3: Explainable – breakdown has all 5 keys with float values
# ---------------------------------------------------------------------------


class TestExplainability:
    def test_breakdown_has_all_keys(self) -> None:
        result = compute_engagement_score(follower_count=500)
        assert set(result.breakdown.keys()) == ALL_SIGNAL_KEYS

    def test_breakdown_values_are_floats(self) -> None:
        result = compute_engagement_score(like_count=100, comment_count=20)
        for value in result.breakdown.values():
            assert isinstance(value, float)

    def test_missing_signal_contributes_zero(self) -> None:
        result = compute_engagement_score(follower_count=500)
        assert result.breakdown["like_count"] == 0.0
        assert result.breakdown["comment_count"] == 0.0
        assert result.breakdown["repost_count"] == 0.0
        assert result.breakdown["interaction_count"] == 0.0


# ---------------------------------------------------------------------------
# Score range
# ---------------------------------------------------------------------------


class TestScoreRange:
    def test_minimum_score(self) -> None:
        result = compute_engagement_score()
        assert result.score == 0

    def test_maximum_score(self) -> None:
        result = compute_engagement_score(
            follower_count=999_999,
            like_count=999_999,
            comment_count=999_999,
            repost_count=999_999,
            interaction_count=999_999,
        )
        assert result.score == 100

    @pytest.mark.parametrize(
        "kwargs",
        [
            dict(follower_count=1),
            dict(like_count=500, comment_count=500),
            dict(interaction_count=25),
            dict(
                follower_count=50_000,
                like_count=500,
                comment_count=500,
                repost_count=500,
                interaction_count=25,
            ),
        ],
    )
    def test_score_always_in_range(self, kwargs: dict) -> None:
        result = compute_engagement_score(**kwargs)
        assert 0 <= result.score <= 100


# ---------------------------------------------------------------------------
# Defensive: negative inputs treated as 0
# ---------------------------------------------------------------------------


class TestNegativeInputs:
    def test_negative_values_treated_as_zero(self) -> None:
        result = compute_engagement_score(
            follower_count=-100,
            like_count=-50,
            comment_count=-10,
            repost_count=-5,
            interaction_count=-1,
        )
        assert result.score == 0

    def test_negative_mixed_with_positive(self) -> None:
        negative = compute_engagement_score(follower_count=-100, like_count=200)
        positive = compute_engagement_score(follower_count=0, like_count=200)
        assert negative.score == positive.score


# ---------------------------------------------------------------------------
# Golden test: known input → expected output
# ---------------------------------------------------------------------------


class TestGoldenOutput:
    def test_known_score(self) -> None:
        result = compute_engagement_score(
            follower_count=5000,
            like_count=200,
            comment_count=50,
            repost_count=30,
            interaction_count=10,
        )
        assert result.score == 64


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


class TestConstants:
    def test_weights_sum_to_one(self) -> None:
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    def test_all_signals_have_caps(self) -> None:
        assert set(WEIGHTS.keys()) == set(CAPS.keys())


# ---------------------------------------------------------------------------
# count_by_author – DB fixture test
# ---------------------------------------------------------------------------


class TestCountByAuthor:
    def test_returns_zero_for_none(self, db: Session) -> None:
        assert count_by_author(db, None) == 0

    def test_returns_zero_when_no_records(self, db: Session) -> None:
        assert count_by_author(db, "Nobody") == 0

    def test_counts_exact_match_case_insensitive(self, db: Session) -> None:
        for _ in range(3):
            create_draft(
                db,
                post_text="hello",
                preset_id="p1",
                prompt_text="prompt",
                created_date=_NOW,
                author_name="Alice Smith",
            )
        create_draft(
            db,
            post_text="other",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Bob Jones",
        )
        db.commit()

        assert count_by_author(db, "Alice Smith") == 3
        assert count_by_author(db, "alice smith") == 3
        assert count_by_author(db, "ALICE SMITH") == 3
        assert count_by_author(db, "Bob Jones") == 1

    def test_does_not_match_substring(self, db: Session) -> None:
        create_draft(
            db,
            post_text="post",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Alice Smith",
        )
        db.commit()

        assert count_by_author(db, "Alice") == 0


# ---------------------------------------------------------------------------
# Story 6.3: Score persistence in create_draft
# ---------------------------------------------------------------------------


class TestScorePersistence:
    def test_create_draft_persists_score(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="hello",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Alice",
            follower_count=5000,
            like_count=200,
            comment_count=50,
            repost_count=30,
        )
        db.commit()
        assert record.engagement_score is not None
        assert 0 <= record.engagement_score <= 100

    def test_create_draft_persists_breakdown(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="hello",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            follower_count=1000,
        )
        db.commit()
        assert record.score_breakdown is not None
        breakdown = json.loads(record.score_breakdown)
        assert set(breakdown.keys()) == ALL_SIGNAL_KEYS


class TestScoreWithNullSignals:
    def test_no_signals_gives_zero(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="hello",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
        )
        db.commit()
        assert record.engagement_score == 0

    def test_no_signals_breakdown_all_zero(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="hello",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
        )
        db.commit()
        breakdown = json.loads(record.score_breakdown)
        assert all(v == 0.0 for v in breakdown.values())


class TestInteractionCountIntegration:
    def test_interaction_count_increases_score(self, db: Session) -> None:
        """Creating prior records for the same author increases interaction_count."""
        # First draft — no prior records for this author
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

        # Second draft — 1 prior record for Alice
        r2 = create_draft(
            db,
            post_text="second",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Alice",
            follower_count=100,
        )
        db.commit()

        assert r2.engagement_score >= r1.engagement_score

    def test_different_author_no_interaction_boost(
        self, db: Session,
    ) -> None:
        create_draft(
            db,
            post_text="alice post",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Alice",
            follower_count=100,
        )
        db.commit()

        bob = create_draft(
            db,
            post_text="bob post",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            author_name="Bob",
            follower_count=100,
        )
        db.commit()

        breakdown = json.loads(bob.score_breakdown)
        assert breakdown["interaction_count"] == 0.0


class TestScoreBreakdownJson:
    def test_breakdown_is_valid_json(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="hello",
            preset_id="p1",
            prompt_text="prompt",
            created_date=_NOW,
            follower_count=500,
            like_count=50,
        )
        db.commit()
        breakdown = json.loads(record.score_breakdown)
        assert isinstance(breakdown, dict)
        assert set(breakdown.keys()) == ALL_SIGNAL_KEYS
        for v in breakdown.values():
            assert isinstance(v, float)


# ---------------------------------------------------------------------------
# Story 6.6: score_to_label display helper
# ---------------------------------------------------------------------------


class TestScoreToLabel:
    def test_none_returns_dash(self) -> None:
        assert score_to_label(None) == "—"

    def test_zero_returns_dash(self) -> None:
        assert score_to_label(0) == "—"

    def test_low_boundary(self) -> None:
        assert score_to_label(1) == "Low"
        assert score_to_label(39) == "Low"

    def test_medium_boundary(self) -> None:
        assert score_to_label(40) == "Medium"
        assert score_to_label(69) == "Medium"

    def test_high_boundary(self) -> None:
        assert score_to_label(70) == "High"
        assert score_to_label(100) == "High"

    @pytest.mark.parametrize("score,expected", [
        (15, "Low"),
        (50, "Medium"),
        (85, "High"),
    ])
    def test_representative_values(self, score: int, expected: str) -> None:
        assert score_to_label(score) == expected
