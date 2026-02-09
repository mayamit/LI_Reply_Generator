"""POST /api/v1/generate — build prompt, call LLM, persist draft, return reply."""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.errors import normalize_db_error
from backend.app.db.session import get_db
from backend.app.models.llm import GenerateRequest, GenerateResponse, LLMFailure, LLMSuccess
from backend.app.models.post_context import PostContextPayload
from backend.app.models.presets import get_default_preset, get_preset_by_id
from backend.app.services.llm_client import generate_reply
from backend.app.services.prompt_builder import build_prompt
from backend.app.services.reply_repository import create_draft, update_generated_reply
from backend.app.services.validation import validate_and_build_payload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/v1/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    """Validate input, build prompt, persist draft, call LLM, return result."""
    correlation_id = str(uuid.uuid4())

    # 1. Validate context + resolve preset
    payload_result, errors = validate_and_build_payload(body.context)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert payload_result is not None

    if body.preset_id is None:
        preset = get_default_preset()
    else:
        preset = get_preset_by_id(body.preset_id)
        if preset is None:
            raise HTTPException(
                status_code=422, detail=[f"Unknown preset_id: {body.preset_id}"]
            )

    # Re-create payload with the request's preset_id
    payload = PostContextPayload(
        post_text=payload_result.post_text,
        preset_id=preset.id,
        preset_label=preset.label,
        tone=preset.tone,
        length_bucket=preset.length_bucket,
        intent=preset.intent,
        author_name=payload_result.author_name,
        author_profile_url=payload_result.author_profile_url,
        post_url=payload_result.post_url,
        article_text=payload_result.article_text,
        image_ref=payload_result.image_ref,
        validation_warnings=payload_result.validation_warnings,
    )

    # 2. Build prompt (needed for draft record)
    prompt_text, prompt_metadata = build_prompt(payload, preset)

    # 3. Create draft record
    record_id: int | None = None
    try:
        record = create_draft(
            db,
            post_text=payload.post_text,
            preset_id=preset.id,
            prompt_text=prompt_text,
            created_date=datetime.now(UTC),
            author_name=payload.author_name,
            author_profile_url=payload.author_profile_url,
            post_url=payload.post_url,
            article_text=payload.article_text,
            image_ref=payload.image_ref,
        )
        db.commit()
        record_id = record.id
    except Exception as exc:
        db.rollback()
        normalize_db_error(exc, operation="create_draft", correlation_id=correlation_id)
        # Non-blocking: continue with generation even if persistence fails

    # 4. Generate reply via LLM
    result, _ = generate_reply(payload, preset)

    # 5. Persist generated reply if we have a record and generation succeeded
    if record_id is not None and isinstance(result, LLMSuccess):
        try:
            update_generated_reply(
                db,
                record_id,
                generated_reply=result.reply_text,
                generated_at=datetime.now(UTC),
                llm_model_identifier=result.model_id,
                llm_request_id=result.request_id,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            normalize_db_error(
                exc, operation="update_generated_reply",
                correlation_id=correlation_id,
            )
            # Non-blocking: user still gets the reply text

    # 6. Return response
    response = GenerateResponse(
        result=result,
        prompt_metadata=prompt_metadata,
        record_id=record_id,
    )

    if isinstance(result, LLMFailure) and result.error_category == "not_configured":
        raise HTTPException(status_code=503, detail=result.user_message)

    return response
