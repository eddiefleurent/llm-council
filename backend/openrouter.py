"""OpenRouter API client for making LLM requests."""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    OPENROUTER_CALL_TIMEOUT,
    OPENROUTER_STALL_TIMEOUT,
)

logger = logging.getLogger(__name__)

# Retry config for transient failures (429, 5xx)
_MAX_ATTEMPTS = 4  # 1 initial + 3 retries
_RETRY_WAIT = [1, 2, 4]  # seconds between attempts
_RETRIABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class ModelQueryError:
    """Structured error information from a failed model query."""

    error_type: str  # 'auth', 'rate_limit', 'not_found', 'payment', 'server', 'timeout', 'unknown'
    message: str
    status_code: int | None = None
    model: str | None = None
    latency_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "status_code": self.status_code,
            "model": self.model,
            "latency_seconds": self.latency_seconds,
        }


def _classify_provider_error(err: Any) -> tuple[str, int, str]:
    """Map a provider error object to (error_type, code, message)."""
    if not isinstance(err, dict):
        err = {"message": str(err)}
    try:
        err_code = int(err.get("code", 500))
    except TypeError, ValueError:
        err_code = 500
    err_msg = err.get("message", "Unknown provider error")
    if err_code == 401:
        error_type = "auth"
    elif err_code == 402:
        error_type = "payment"
    elif err_code == 404:
        error_type = "not_found"
    elif err_code == 429:
        error_type = "rate_limit"
    else:
        error_type = "server"
    return error_type, err_code, err_msg


async def _query_model(
    model: str,
    messages: list[dict[str, str]],
    timeout: float = OPENROUTER_CALL_TIMEOUT,
    *,
    stall_timeout: float = OPENROUTER_STALL_TIMEOUT,
    max_tokens: int = 4096,
    response_format: dict | None = None,
    context_limit: int = 32000,
) -> dict[str, Any] | ModelQueryError:
    """
    Query a single model via OpenRouter API.

    The response is streamed so that a slow-but-progressing generation is
    distinguished from a stalled connection: ``stall_timeout`` bounds how long
    one attempt may receive no data at all (provider keep-alive frames count as
    data), while ``timeout`` bounds the whole call across retries.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Total call deadline in seconds across all attempts
        stall_timeout: Per-attempt idle limit in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details',
        or ModelQueryError if the request failed
    """
    started = time.monotonic()
    # Conservative UTF-8 byte estimate; never silently truncate task evidence.
    estimated_tokens = sum(len(m["content"].encode("utf-8")) + 8 for m in messages)
    if estimated_tokens + max_tokens > context_limit:
        return ModelQueryError(
            "context_limit", "Input exceeds the configured context budget.", model=model
        )
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
    }

    if response_format is not None:
        payload["response_format"] = response_format
        payload["provider"] = {"require_parameters": True}

    stall = min(stall_timeout, timeout)
    request_timeout = httpx.Timeout(
        connect=min(15.0, stall),
        read=stall,
        write=min(30.0, stall),
        pool=stall,
    )

    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with (
                httpx.AsyncClient(timeout=request_timeout) as client,
                client.stream(
                    "POST", OPENROUTER_API_URL, headers=headers, json=payload
                ) as response,
            ):
                # Non-retriable errors — return immediately
                if response.status_code == 401:
                    return ModelQueryError(
                        error_type="auth",
                        message="Invalid API key. Please check your OPENROUTER_API_KEY.",
                        status_code=401,
                        model=model,
                    )
                if response.status_code == 402:
                    return ModelQueryError(
                        error_type="payment",
                        message="Payment required. Please add credits to your OpenRouter account.",
                        status_code=402,
                        model=model,
                    )
                if response.status_code == 404:
                    return ModelQueryError(
                        error_type="not_found",
                        message=f'Model "{model}" not found on OpenRouter.',
                        status_code=404,
                        model=model,
                    )

                # Retriable errors (429, 5xx)
                if response.status_code in _RETRIABLE_STATUS_CODES:
                    error_type = (
                        "rate_limit" if response.status_code == 429 else "server"
                    )
                    message_text = (
                        "Rate limit exceeded."
                        if response.status_code == 429
                        else f"OpenRouter server error (HTTP {response.status_code})."
                    )
                    if attempt < _MAX_ATTEMPTS - 1:
                        wait = _RETRY_WAIT[attempt]
                        logger.warning(
                            "[%s] %s (attempt %d/%d), retrying in %ds...",
                            model,
                            message_text,
                            attempt + 1,
                            _MAX_ATTEMPTS,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    return ModelQueryError(
                        error_type=error_type,
                        message=f"{message_text} All {_MAX_ATTEMPTS} attempts failed.",
                        status_code=response.status_code,
                        model=model,
                    )

                response.raise_for_status()

                content_parts: list[str] = []
                reasoning_parts: list[str] = []
                reasoning_details: dict[Any, dict[str, Any]] = {}
                annotations: list[Any] = []
                finish_reason: str | None = None
                usage: dict[str, Any] = {}
                generation_id: str | None = None
                provider_error: Any = None
                saw_data = False
                saw_done = False
                # Upstream failures can arrive as a plain JSON body instead of
                # SSE frames; keep non-data lines for classification.
                raw_body = bytearray()

                async for line in response.aiter_lines():
                    line = line.strip()
                    # Blank separators and SSE comments (e.g.
                    # ": OPENROUTER PROCESSING" keep-alives) carry no data
                    # but still prove the connection is alive.
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        if len(raw_body) < 16384:
                            raw_body.extend(line.encode("utf-8") + b"\n")
                        continue
                    saw_data = True
                    data_str = line.removeprefix("data:").strip()
                    if data_str == "[DONE]":
                        saw_done = True
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning("[%s] Skipping unparseable stream chunk", model)
                        continue
                    if not isinstance(chunk, dict):
                        continue
                    # OpenRouter can emit an error frame mid-stream when the
                    # underlying provider fails.
                    if "error" in chunk:
                        provider_error = chunk["error"]
                        break
                    generation_id = chunk.get("id") or generation_id
                    if chunk.get("usage"):
                        usage.update(chunk["usage"])
                    for choice in chunk.get("choices") or []:
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            content_parts.append(delta["content"])
                        if delta.get("reasoning"):
                            reasoning_parts.append(delta["reasoning"])
                        for detail in delta.get("reasoning_details") or []:
                            idx = detail.get("index", len(reasoning_details))
                            if idx in reasoning_details:
                                merged = reasoning_details[idx]
                                merged["text"] = (merged.get("text") or "") + (
                                    detail.get("text") or ""
                                )
                            else:
                                reasoning_details[idx] = dict(detail)
                        if delta.get("annotations"):
                            annotations.extend(delta["annotations"])
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]

                if provider_error is None and not saw_data and raw_body:
                    # The whole body was a classic JSON response rather than
                    # SSE frames.
                    try:
                        parsed = json.loads(raw_body.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict) and "error" in parsed:
                        provider_error = parsed["error"]
                    elif isinstance(parsed, dict) and parsed.get("choices"):
                        # Provider ignored streaming and returned a complete
                        # JSON completion; use its message as the payload.
                        message = parsed["choices"][0].get("message") or {}
                        if message.get("content"):
                            content_parts.append(message["content"])
                        if message.get("reasoning"):
                            reasoning_parts.append(message["reasoning"])
                        for detail in message.get("reasoning_details") or []:
                            reasoning_details.setdefault(
                                detail.get("index", len(reasoning_details)),
                                dict(detail),
                            )
                        annotations.extend(message.get("annotations") or [])
                        finish_reason = parsed["choices"][0].get("finish_reason")
                        generation_id = parsed.get("id") or generation_id
                        if parsed.get("usage"):
                            usage.update(parsed["usage"])

                if provider_error is not None:
                    error_type, err_code, err_msg = _classify_provider_error(
                        provider_error
                    )
                    # Retry on retriable codes
                    if (
                        err_code in _RETRIABLE_STATUS_CODES
                        and attempt < _MAX_ATTEMPTS - 1
                    ):
                        wait = _RETRY_WAIT[attempt]
                        logger.warning(
                            "[%s] Provider error %s: %s (attempt %d/%d), retrying in %ds...",
                            model,
                            err_code,
                            err_msg,
                            attempt + 1,
                            _MAX_ATTEMPTS,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    return ModelQueryError(
                        error_type=error_type,
                        message=f"Provider error: {err_msg}",
                        status_code=err_code,
                        model=model,
                    )

                if finish_reason is None and not saw_done:
                    # The stream ended without a completion signal (no
                    # finish_reason, no [DONE]) — accumulated content may be
                    # truncated mid-generation and must not be accepted.
                    if attempt < _MAX_ATTEMPTS - 1:
                        wait = _RETRY_WAIT[attempt]
                        logger.warning(
                            "[%s] Stream ended before completion (attempt %d/%d), retrying in %ds...",
                            model,
                            attempt + 1,
                            _MAX_ATTEMPTS,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue
                    return ModelQueryError(
                        error_type="incomplete_stream",
                        message=f"Stream ended before the response completed. All {_MAX_ATTEMPTS} attempts failed.",
                        model=model,
                    )

                content = "".join(content_parts)
                if not content.strip():
                    return ModelQueryError(
                        "empty_response",
                        "Provider returned no usable text.",
                        model=model,
                    )
                return {
                    "content": content,
                    "reasoning": "".join(reasoning_parts) or None,
                    "reasoning_details": list(reasoning_details.values()) or None,
                    "annotations": annotations,
                    "usage": usage,
                    "generation_id": generation_id,
                    "finish_reason": finish_reason,
                    "truncated": finish_reason == "length",
                    "latency_seconds": round(time.monotonic() - started, 3),
                    "attempts": attempt + 1,
                }

        except httpx.TimeoutException:
            if attempt < _MAX_ATTEMPTS - 1:
                wait = _RETRY_WAIT[attempt]
                logger.warning(
                    "[%s] Timeout (attempt %d/%d), retrying in %ds...",
                    model,
                    attempt + 1,
                    _MAX_ATTEMPTS,
                    wait,
                )
                await asyncio.sleep(wait)
                continue
            return ModelQueryError(
                error_type="timeout",
                message=f"Request timed out after {timeout}s. All {_MAX_ATTEMPTS} attempts failed.",
                model=model,
            )
        except httpx.HTTPStatusError as e:
            return ModelQueryError(
                error_type="unknown",
                message=f"HTTP error: {e}",
                status_code=e.response.status_code if e.response else None,
                model=model,
            )
        except Exception as e:
            logger.exception("Error querying model %s", model)
            return ModelQueryError(error_type="unknown", message=str(e), model=model)

    # Should never reach here
    return ModelQueryError(
        error_type="unknown", message="Unexpected retry loop exit.", model=model
    )


async def query_model(
    model: str,
    messages: list[dict[str, str]],
    timeout: float = OPENROUTER_CALL_TIMEOUT,
    **kwargs: Any,
) -> dict[str, Any] | ModelQueryError:
    """Bound all attempts and retry waits by one total call deadline."""
    started = time.monotonic()
    try:
        async with asyncio.timeout(timeout):
            result = await _query_model(model, messages, timeout, **kwargs)
    except TimeoutError:
        result = ModelQueryError("timeout", "Model call deadline exceeded", model=model)
    if isinstance(result, ModelQueryError):
        result.latency_seconds = round(time.monotonic() - started, 3)
    return result


async def query_models_parallel(
    models: list[str], messages: list[dict[str, str]], **kwargs: Any
) -> dict[str, dict[str, Any] | ModelQueryError]:
    """
    Query multiple models in parallel.

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict or ModelQueryError
    """
    import asyncio

    # Create tasks for all models
    tasks = [query_model(model, messages, **kwargs) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return dict(zip(models, responses, strict=False))


def is_error(response: dict[str, Any] | ModelQueryError | None) -> bool:
    """Check if a response is an error."""
    return isinstance(response, ModelQueryError) or response is None
