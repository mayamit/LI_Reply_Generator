"""POST /api/v1/approve — approve a draft reply (idempotent)."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.logging import log_event
from backend.app.db.session import get_db
from backend.app.models.llm import ApproveRequest, ApproveResponse
from backend.app.services.reply_repository import (
    InvalidTransitionError,
    RecordNotFoundError,
    approve_reply,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/v1/approve", response_model=ApproveResponse)
def approve(body: ApproveRequest, db: Session = Depends(get_db)) -> ApproveResponse:
    """Approve a draft reply record. Idempotent — safe to call multiple times."""
    if not body.final_reply or not body.final_reply.strip():
        raise HTTPException(status_code=422, detail="final_reply must be non-empty")

    try:
        record = approve_reply(
            db,
            body.record_id,
            final_reply=body.final_reply,
            approved_at=datetime.now(UTC),
        )
        db.commit()
    except RecordNotFoundError:
        raise HTTPException(status_code=404, detail=f"Record not found: {body.record_id}")
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        db.rollback()
        log_event(
            logger, "exception", "db_write_failed",
            operation="approve_reply", error_category="db",
        )
        raise HTTPException(status_code=500, detail="Failed to save approval. Please retry.")

    log_event(logger, "info", "reply_approved", record_id=record.id)

    return ApproveResponse(
        record_id=record.id,
        status=record.status,
        approved_at=record.approved_at.isoformat() if record.approved_at else None,
    )
