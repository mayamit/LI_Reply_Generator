"""Tests for engagement signal persistence (Story 6.1)."""

from datetime import UTC, datetime

import pytest
from backend.app.db.base import Base
from backend.app.models.post_context import PostContextInput, PostContextPayload
from backend.app.services.reply_repository import create_draft, get_by_id
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


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


class TestEngagementPersistence:
    """AC1: create_draft() with engagement fields stores them on the record."""

    def test_create_draft_with_all_engagement_fields(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="A test post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
            follower_count=5000,
            like_count=120,
            comment_count=30,
            repost_count=15,
        )
        db.commit()
        assert record.follower_count == 5000
        assert record.like_count == 120
        assert record.comment_count == 30
        assert record.repost_count == 15

    def test_create_draft_with_follower_count_only(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="A test post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
            follower_count=1000,
        )
        db.commit()
        assert record.follower_count == 1000
        assert record.like_count is None
        assert record.comment_count is None
        assert record.repost_count is None


class TestEngagementIsolation:
    """AC2: Two records with different metrics are isolated."""

    def test_records_have_independent_metrics(self, db: Session) -> None:
        r1 = create_draft(
            db,
            post_text="Post one text.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
            follower_count=100,
            like_count=10,
            comment_count=5,
            repost_count=2,
        )
        r2 = create_draft(
            db,
            post_text="Post two text.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
            follower_count=9999,
            like_count=500,
            comment_count=200,
            repost_count=80,
        )
        db.commit()

        assert r1.follower_count == 100
        assert r2.follower_count == 9999
        assert r1.like_count == 10
        assert r2.like_count == 500


class TestEngagementDefaults:
    """AC3: Missing values default to None, no errors."""

    def test_defaults_to_none(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="A test post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
        )
        db.commit()
        assert record.follower_count is None
        assert record.like_count is None
        assert record.comment_count is None
        assert record.repost_count is None


class TestEngagementValidation:
    """Negative values are rejected by Pydantic."""

    def test_negative_follower_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PostContextInput(
                post_text="A test post for validation.",
                preset_id="prof_short_agree",
                follower_count=-1,
            )

    def test_negative_like_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PostContextInput(
                post_text="A test post for validation.",
                preset_id="prof_short_agree",
                like_count=-5,
            )

    def test_negative_comment_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PostContextInput(
                post_text="A test post for validation.",
                preset_id="prof_short_agree",
                comment_count=-1,
            )

    def test_negative_repost_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PostContextInput(
                post_text="A test post for validation.",
                preset_id="prof_short_agree",
                repost_count=-1,
            )


class TestPayloadIncludesEngagement:
    """PostContextPayload includes engagement fields."""

    def test_payload_carries_engagement_fields(self) -> None:
        payload = PostContextPayload(
            post_text="Test post.",
            preset_id="prof_short_agree",
            preset_label="Professional Short Agree",
            tone="professional",
            length_bucket="short",
            intent="agree",
            follower_count=500,
            like_count=42,
            comment_count=7,
            repost_count=3,
        )
        assert payload.follower_count == 500
        assert payload.like_count == 42
        assert payload.comment_count == 7
        assert payload.repost_count == 3

    def test_payload_defaults_to_none(self) -> None:
        payload = PostContextPayload(
            post_text="Test post.",
            preset_id="prof_short_agree",
            preset_label="Professional Short Agree",
            tone="professional",
            length_bucket="short",
            intent="agree",
        )
        assert payload.follower_count is None
        assert payload.like_count is None
        assert payload.comment_count is None
        assert payload.repost_count is None


class TestEngagementRoundTrip:
    """Round-trip: create with metrics, get_by_id, verify all values."""

    def test_round_trip(self, db: Session) -> None:
        record = create_draft(
            db,
            post_text="Round trip test post.",
            preset_id="prof_short_agree",
            prompt_text="Prompt.",
            created_date=_NOW,
            follower_count=10_000,
            like_count=250,
            comment_count=45,
            repost_count=20,
        )
        db.commit()

        fetched = get_by_id(db, record.id)
        assert fetched.follower_count == 10_000
        assert fetched.like_count == 250
        assert fetched.comment_count == 45
        assert fetched.repost_count == 20
