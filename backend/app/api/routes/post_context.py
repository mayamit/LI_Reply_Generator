"""POST /api/v1/post-context — validate input and return enriched payload."""

from fastapi import APIRouter, HTTPException

from backend.app.models.post_context import PostContextInput, PostContextPayload
from backend.app.services.validation import validate_and_build_payload

router = APIRouter()


@router.post("/api/v1/post-context", response_model=PostContextPayload)
def create_post_context(body: PostContextInput) -> PostContextPayload:
    """Validate post context and return the enriched payload."""
    payload, errors = validate_and_build_payload(body)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    assert payload is not None  # guaranteed when errors is empty
    return payload
