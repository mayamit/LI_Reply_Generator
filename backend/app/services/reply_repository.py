"""Repository for ReplyRecord CRUD operations (EPIC 1 persistence).

All methods operate on a caller-supplied SQLAlchemy ``Session`` so that
transaction boundaries remain under the caller's control.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models.reply_record import ReplyRecord

logger = logging.getLogger(__name__)


class RecordNotFoundError(Exception):
    """Raised when a ReplyRecord cannot be found by id."""


class InvalidTransitionError(Exception):
    """Raised when a status transition violates lifecycle rules."""


# ---------------------------------------------------------------------------
# Repository methods
# ---------------------------------------------------------------------------


def create_draft(
    db: Session,
    *,
    post_text: str,
    preset_id: str,
    prompt_text: str,
    created_date: datetime,
    author_name: str | None = None,
    author_profile_url: str | None = None,
    post_url: str | None = None,
    article_text: str | None = None,
    image_ref: str | None = None,
) -> ReplyRecord:
    """Create a new draft ReplyRecord and flush to obtain an id."""
    record = ReplyRecord(
        post_text=post_text,
        preset_id=preset_id,
        prompt_text=prompt_text,
        created_date=created_date,
        status="draft",
        author_name=author_name,
        author_profile_url=author_profile_url,
        post_url=post_url,
        article_text=article_text,
        image_ref=image_ref,
    )
    db.add(record)
    db.flush()
    logger.info(
        "reply_record_created: id=%d preset_id=%s post_text_len=%d",
        record.id,
        preset_id,
        len(post_text),
    )
    return record


def update_generated_reply(
    db: Session,
    record_id: int,
    *,
    generated_reply: str,
    generated_at: datetime,
    llm_model_identifier: str | None = None,
    llm_request_id: str | None = None,
) -> ReplyRecord:
    """Attach LLM-generated reply text to an existing draft."""
    record = get_by_id(db, record_id)
    record.generated_reply = generated_reply
    record.generated_at = generated_at
    record.llm_model_identifier = llm_model_identifier
    record.llm_request_id = llm_request_id
    db.flush()
    logger.info(
        "reply_record_updated_generated: id=%d reply_len=%d",
        record.id,
        len(generated_reply),
    )
    return record


def approve_reply(
    db: Session,
    record_id: int,
    *,
    final_reply: str,
    approved_at: datetime,
) -> ReplyRecord:
    """Transition a record to *approved* (idempotent).

    If the record is already approved the call is a no-op and the existing
    record is returned unchanged.

    Raises:
        InvalidTransitionError: If *final_reply* is empty/whitespace.
        RecordNotFoundError: If *record_id* does not exist.
    """
    if not final_reply or not final_reply.strip():
        raise InvalidTransitionError("final_reply must be non-empty for approval")

    record = get_by_id(db, record_id)

    # Idempotent: already approved → return as-is
    if record.status == "approved":
        logger.info("reply_record_approved: id=%d (idempotent no-op)", record.id)
        return record

    record.status = "approved"
    record.final_reply = final_reply
    record.approved_at = approved_at
    db.flush()
    logger.info("reply_record_approved: id=%d", record.id)
    return record


DEFAULT_PAGE_SIZE = 20


def list_records(
    db: Session,
    *,
    status: str | None = None,
    author_name: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    offset: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
) -> list[ReplyRecord]:
    """List ReplyRecords with optional filters, ordered by created_date DESC.

    Args:
        status: Filter by exact status (``"draft"`` or ``"approved"``).
        author_name: Filter by substring match (case-insensitive).
        created_after: Inclusive lower bound on ``created_date``.
        created_before: Inclusive upper bound on ``created_date``.
        offset: Number of records to skip (for pagination).
        limit: Maximum records to return (default 20).
    """
    query = db.query(ReplyRecord).order_by(ReplyRecord.created_date.desc())

    if status is not None:
        query = query.filter(ReplyRecord.status == status)

    if author_name is not None:
        query = query.filter(
            ReplyRecord.author_name.ilike(f"%{author_name}%")
        )

    if created_after is not None:
        query = query.filter(ReplyRecord.created_date >= created_after)

    if created_before is not None:
        query = query.filter(ReplyRecord.created_date <= created_before)

    return list(query.offset(offset).limit(limit).all())


def count_records(
    db: Session,
    *,
    status: str | None = None,
    author_name: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> int:
    """Return total count matching the same filters as :func:`list_records`."""
    query = db.query(ReplyRecord)

    if status is not None:
        query = query.filter(ReplyRecord.status == status)
    if author_name is not None:
        query = query.filter(
            ReplyRecord.author_name.ilike(f"%{author_name}%")
        )
    if created_after is not None:
        query = query.filter(ReplyRecord.created_date >= created_after)
    if created_before is not None:
        query = query.filter(ReplyRecord.created_date <= created_before)

    return query.count()


def get_by_id(db: Session, record_id: int) -> ReplyRecord:
    """Fetch a ReplyRecord by primary key.

    Raises:
        RecordNotFoundError: If no record with *record_id* exists.
    """
    record = db.get(ReplyRecord, record_id)
    if record is None:
        raise RecordNotFoundError(f"ReplyRecord not found: id={record_id}")
    return record
