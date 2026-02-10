"""Tests for engagement scoring (Story 6.2)."""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.services.engagement_scoring import (
    CAPS,
    WEIGHTS,
    EngagementScore,
    compute_engagement_score,
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
