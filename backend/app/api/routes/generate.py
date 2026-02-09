"""POST /api/v1/generate — build prompt, call LLM, return reply."""

from fastapi import APIRouter, HTTPException

from backend.app.models.llm import GenerateRequest, GenerateResponse, LLMFailure
from backend.app.models.post_context import PostContextPayload
from backend.app.models.presets import get_preset_by_id
from backend.app.services.llm_client import generate_reply
from backend.app.services.validation import validate_and_build_payload

router = APIRouter()


@router.post("/api/v1/generate", response_model=GenerateResponse)
def generate(body: GenerateRequest) -> GenerateResponse:
    """Validate input, build prompt, call LLM, return result."""
    # 1. Validate context + resolve preset
    payload_result, errors = validate_and_build_payload(body.context)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert payload_result is not None

    preset = get_preset_by_id(body.preset_id)
    if preset is None:
        raise HTTPException(status_code=422, detail=[f"Unknown preset_id: {body.preset_id}"])

    # Re-create payload with the request's preset_id (may differ from context.preset_id)
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

    # 2. Generate reply
    result, prompt_metadata = generate_reply(payload, preset)

    # 3. Return — use 200 for both success and LLM failures (they are expected)
    #    Only use 5xx/4xx for validation issues above.
    response = GenerateResponse(result=result, prompt_metadata=prompt_metadata)

    # If not_configured, hint to the user via 503
    if isinstance(result, LLMFailure) and result.error_category == "not_configured":
        raise HTTPException(status_code=503, detail=result.user_message)

    return response
