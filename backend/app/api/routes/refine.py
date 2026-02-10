"""POST /api/v1/refine — refine an existing reply with additional instructions."""

import logging

from fastapi import APIRouter, HTTPException

from backend.app.models.llm import LLMFailure, RefineRequest, RefineResponse
from backend.app.services.llm_client import get_provider

logger = logging.getLogger(__name__)

router = APIRouter()

_REFINE_PROMPT_TEMPLATE = (
    "You are a LinkedIn reply assistant. Below is a LinkedIn reply that was "
    "previously generated. Rewrite it according to the instruction provided.\n\n"
    "Original reply:\n{reply_text}\n\n"
    "Instruction: {instruction}\n\n"
    "Return only the rewritten reply text. No quotes, no preamble, no explanation."
)


@router.post("/api/v1/refine", response_model=RefineResponse)
def refine(body: RefineRequest) -> RefineResponse:
    """Refine an existing reply with additional instructions."""
    if not body.reply_text.strip():
        raise HTTPException(status_code=422, detail="reply_text must be non-empty")
    if not body.instruction.strip():
        raise HTTPException(status_code=422, detail="instruction must be non-empty")

    provider = get_provider()

    prompt = _REFINE_PROMPT_TEMPLATE.format(
        reply_text=body.reply_text.strip(),
        instruction=body.instruction.strip(),
    )

    from backend.app.core.settings import settings

    result = provider.call(prompt, settings.llm_timeout_seconds)

    if isinstance(result, LLMFailure) and result.error_category == "not_configured":
        raise HTTPException(status_code=503, detail=result.user_message)

    return RefineResponse(result=result)
