"""Pydantic models for LLM generation requests and results."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.models.post_context import PostContextInput


class ErrorCategory(StrEnum):
    """Categorised LLM failure reasons."""

    auth = "auth"
    rate_limit = "rate_limit"
    network = "network"
    timeout = "timeout"
    provider = "provider"
    parsing = "parsing"
    not_configured = "not_configured"
    validation = "validation"
    unknown = "unknown"


class GenerateRequest(BaseModel):
    """Incoming request to generate a reply."""

    context: PostContextInput
    preset_id: str


class LLMSuccess(BaseModel):
    """Successful LLM generation result."""

    status: Literal["success"] = "success"
    reply_text: str
    model_id: str | None = None
    request_id: str | None = None
    latency_ms: int = 0


class LLMFailure(BaseModel):
    """Failed LLM generation result."""

    status: Literal["error"] = "error"
    error_category: ErrorCategory
    user_message: str
    retryable: bool = False
    details: str | None = None


LLMResult = LLMSuccess | LLMFailure
"""Discriminated union returned by the LLM client."""


class GenerateResponse(BaseModel):
    """API response envelope for reply generation."""

    result: LLMSuccess | LLMFailure = Field(..., discriminator="status")
    prompt_metadata: dict[str, object] | None = None
