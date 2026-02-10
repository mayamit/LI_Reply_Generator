"""Batch recomputation of engagement scores for all ReplyRecords.

Called periodically by the scheduler to keep scores fresh as
interaction counts evolve over time.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from backend.app.models.reply_record import ReplyRecord
from backend.app.services.engagement_scoring import compute_engagement_score
from backend.app.services.reply_repository import count_by_author

logger = logging.getLogger(__name__)

_PAGE_SIZE = 200


def recompute_all_scores(db: Session) -> int:
    """Recompute engagement scores for every ReplyRecord.

    Iterates all records in pages, recomputes each score using current
    signal values and interaction counts, and updates only records whose
    score has changed.  Returns the number of records updated.

    This function is **idempotent**: unchanged inputs produce unchanged
    scores.
    """
    updated = 0
    offset = 0

    while True:
        records: list[ReplyRecord] = (
            db.query(ReplyRecord)
            .order_by(ReplyRecord.id)
            .offset(offset)
            .limit(_PAGE_SIZE)
            .all()
        )
        if not records:
            break

        for record in records:
            interaction_count = count_by_author(db, record.author_name)
            result = compute_engagement_score(
                follower_count=record.follower_count,
                like_count=record.like_count,
                comment_count=record.comment_count,
                repost_count=record.repost_count,
                interaction_count=interaction_count,
            )
            new_breakdown = json.dumps(result.breakdown)
            if (
                record.engagement_score != result.score
                or record.score_breakdown != new_breakdown
            ):
                record.engagement_score = result.score
                record.score_breakdown = new_breakdown
                updated += 1

        offset += _PAGE_SIZE

    if updated:
        db.flush()

    logger.info(
        "score_recomputation_complete: updated=%d total_scanned=%d",
        updated,
        offset if not records else offset + len(records),
    )
    return updated
