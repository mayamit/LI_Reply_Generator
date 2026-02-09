"""POST /api/v1/approve — approve a draft reply (idempotent)."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.errors import normalize_db_error
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
    correlation_id = str(uuid.uuid4())

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
    except Exception as exc:
        db.rollback()
        error = normalize_db_error(
            exc, operation="approve_reply", correlation_id=correlation_id,
        )
        raise HTTPException(status_code=error.http_status, detail=error.user_message)

    log_event(logger, "info", "reply_approved", record_id=record.id)

    return ApproveResponse(
        record_id=record.id,
        status=record.status,
        approved_at=record.approved_at.isoformat() if record.approved_at else None,
    )
