"""LLM client abstraction with provider-agnostic interface.

Providers
---------
- **MockProvider** — deterministic stub for tests and when no key is configured.
- **AnthropicProvider** — uses the ``anthropic`` SDK (requires ``ANTHROPIC_API_KEY``).
- **OpenAIProvider** — uses the ``openai`` SDK (requires ``OPENAI_API_KEY``).

The module exposes :func:`get_provider` (factory) and :func:`generate_reply`
(high-level orchestrator that validates, builds the prompt, calls the provider,
and returns a standardised :class:`LLMResult`).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Protocol, runtime_checkable

from backend.app.core.settings import settings
from backend.app.models.llm import ErrorCategory, LLMFailure, LLMResult, LLMSuccess
from backend.app.models.post_context import PostContextPayload
from backend.app.models.presets import ReplyPreset
from backend.app.services.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface every LLM provider must satisfy."""

    @property
    def provider_name(self) -> str: ...

    def call(self, prompt_text: str, timeout_seconds: int, *, image_data: str | None = None) -> LLMResult:
        """Send *prompt_text* to the LLM and return a standardised result."""
        ...


# ---------------------------------------------------------------------------
# Mock provider (tests + unconfigured fallback)
# ---------------------------------------------------------------------------


class MockProvider:
    """Returns a canned reply.  Used in tests and when no API key is set."""

    provider_name: str = "mock"

    def call(self, prompt_text: str, timeout_seconds: int, *, image_data: str | None = None) -> LLMResult:
        return LLMSuccess(
            reply_text="This is a mock reply for testing purposes.",
            model_id="mock-v1",
            request_id=str(uuid.uuid4()),
            latency_ms=0,
        )


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------


class AnthropicProvider:
    """Calls the Anthropic Messages API via the ``anthropic`` SDK."""

    provider_name: str = "anthropic"

    def __init__(self, api_key: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    def call(self, prompt_text: str, timeout_seconds: int, *, image_data: str | None = None) -> LLMResult:
        import anthropic

        request_id = str(uuid.uuid4())
        start = time.monotonic()

        # Build message content — multimodal if image is provided
        if image_data:
            content: list[dict] = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data,
                    },
                },
                {"type": "text", "text": prompt_text},
            ]
        else:
            content = prompt_text  # type: ignore[assignment]

        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
                timeout=float(timeout_seconds),
            )
        except anthropic.AuthenticationError:
            return LLMFailure(
                error_category=ErrorCategory.auth,
                user_message="Anthropic API key is invalid or expired.",
                retryable=False,
                details=request_id,
            )
        except anthropic.RateLimitError:
            return LLMFailure(
                error_category=ErrorCategory.rate_limit,
                user_message="Anthropic rate limit reached. Please wait and retry.",
                retryable=True,
                details=request_id,
            )
        except anthropic.APITimeoutError:
            return LLMFailure(
                error_category=ErrorCategory.timeout,
                user_message="Request to Anthropic timed out.",
                retryable=True,
                details=request_id,
            )
        except anthropic.APIConnectionError:
            return LLMFailure(
                error_category=ErrorCategory.network,
                user_message="Could not connect to Anthropic API.",
                retryable=True,
                details=request_id,
            )
        except anthropic.APIStatusError as exc:
            return LLMFailure(
                error_category=ErrorCategory.provider,
                user_message=f"Anthropic API error (HTTP {exc.status_code}).",
                retryable=exc.status_code >= 500,
                details=request_id,
            )
        except Exception as exc:
            return LLMFailure(
                error_category=ErrorCategory.unknown,
                user_message="Unexpected error calling Anthropic.",
                retryable=False,
                details=f"{request_id}: {type(exc).__name__}",
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        # Parse response
        try:
            text_block = next(
                (b for b in response.content if b.type == "text"),
                None,
            )
            reply_text = (text_block.text if text_block else "").strip()
        except Exception:
            return LLMFailure(
                error_category=ErrorCategory.parsing,
                user_message="Failed to parse Anthropic response.",
                retryable=False,
                details=request_id,
            )

        if not reply_text:
            return LLMFailure(
                error_category=ErrorCategory.parsing,
                user_message="No reply generated — model returned empty text.",
                retryable=False,
                details=request_id,
            )

        return LLMSuccess(
            reply_text=reply_text,
            model_id=response.model,
            request_id=request_id,
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


class OpenAIProvider:
    """Calls the OpenAI Chat Completions API via the ``openai`` SDK."""

    provider_name: str = "openai"

    def __init__(self, api_key: str) -> None:
        import openai

        self._client = openai.OpenAI(api_key=api_key)

    def call(self, prompt_text: str, timeout_seconds: int, *, image_data: str | None = None) -> LLMResult:
        import openai

        request_id = str(uuid.uuid4())
        start = time.monotonic()

        # Build message content — multimodal if image is provided
        if image_data:
            content: list[dict] = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_data}"},
                },
                {"type": "text", "text": prompt_text},
            ]
        else:
            content = prompt_text  # type: ignore[assignment]

        try:
            response = self._client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=1024,
                timeout=float(timeout_seconds),
            )
        except openai.AuthenticationError:
            return LLMFailure(
                error_category=ErrorCategory.auth,
                user_message="OpenAI API key is invalid or expired.",
                retryable=False,
                details=request_id,
            )
        except openai.RateLimitError:
            return LLMFailure(
                error_category=ErrorCategory.rate_limit,
                user_message="OpenAI rate limit reached. Please wait and retry.",
                retryable=True,
                details=request_id,
            )
        except openai.APITimeoutError:
            return LLMFailure(
                error_category=ErrorCategory.timeout,
                user_message="Request to OpenAI timed out.",
                retryable=True,
                details=request_id,
            )
        except openai.APIConnectionError:
            return LLMFailure(
                error_category=ErrorCategory.network,
                user_message="Could not connect to OpenAI API.",
                retryable=True,
                details=request_id,
            )
        except openai.APIStatusError as exc:
            return LLMFailure(
                error_category=ErrorCategory.provider,
                user_message=f"OpenAI API error (HTTP {exc.status_code}).",
                retryable=exc.status_code >= 500,
                details=request_id,
            )
        except Exception as exc:
            return LLMFailure(
                error_category=ErrorCategory.unknown,
                user_message="Unexpected error calling OpenAI.",
                retryable=False,
                details=f"{request_id}: {type(exc).__name__}",
            )

        latency_ms = int((time.monotonic() - start) * 1000)

        # Parse response
        try:
            choice = response.choices[0] if response.choices else None
            reply_text = (choice.message.content if choice and choice.message else "").strip()
        except Exception:
            return LLMFailure(
                error_category=ErrorCategory.parsing,
                user_message="Failed to parse OpenAI response.",
                retryable=False,
                details=request_id,
            )

        if not reply_text:
            return LLMFailure(
                error_category=ErrorCategory.parsing,
                user_message="No reply generated — model returned empty text.",
                retryable=False,
                details=request_id,
            )

        return LLMSuccess(
            reply_text=reply_text,
            model_id=response.model,
            request_id=request_id,
            latency_ms=latency_ms,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_provider(
    *,
    anthropic_key: str | None = None,
    openai_key: str | None = None,
) -> LLMProvider:
    """Return the best available provider based on configured API keys.

    Resolution order: Anthropic > OpenAI > Mock.
    """
    ak = anthropic_key if anthropic_key is not None else settings.anthropic_api_key
    ok = openai_key if openai_key is not None else settings.openai_api_key

    if ak:
        logger.info("LLM provider: Anthropic")
        return AnthropicProvider(api_key=ak)
    if ok:
        logger.info("LLM provider: OpenAI")
        return OpenAIProvider(api_key=ok)
    logger.warning("No LLM API key configured — using MockProvider")
    return MockProvider()


# ---------------------------------------------------------------------------
# High-level orchestrator
# ---------------------------------------------------------------------------


def generate_reply(
    payload: PostContextPayload,
    preset: ReplyPreset,
    *,
    provider: LLMProvider | None = None,
    image_data: str | None = None,
) -> tuple[LLMResult, dict[str, object]]:
    """Build prompt, call LLM, return ``(result, prompt_metadata)``.

    If *provider* is ``None`` the default provider is resolved via
    :func:`get_provider`.
    """
    correlation_id = str(uuid.uuid4())

    # 1. Build prompt
    prompt_text, prompt_metadata = build_prompt(payload, preset)

    # 2. Resolve provider
    if provider is None:
        provider = get_provider()

    # 3. Call LLM
    logger.info(
        "llm_call_start: correlation_id=%s preset_id=%s provider=%s prompt_length=%d image=%s",
        correlation_id,
        preset.id,
        provider.provider_name,
        len(prompt_text),
        bool(image_data),
    )

    timeout = settings.llm_timeout_seconds
    result = provider.call(prompt_text, timeout, image_data=image_data)

    # 4. Log outcome (never log prompt content or secrets)
    if isinstance(result, LLMSuccess):
        logger.info(
            "llm_call_success: correlation_id=%s model_id=%s latency_ms=%d",
            correlation_id,
            result.model_id,
            result.latency_ms,
        )
    else:
        logger.warning(
            "llm_call_failure: correlation_id=%s error_category=%s retryable=%s",
            correlation_id,
            result.error_category,
            result.retryable,
        )

    return result, prompt_metadata
