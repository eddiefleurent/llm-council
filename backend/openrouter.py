"""OpenRouter API client for making LLM requests."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "status_code": self.status_code,
            "model": self.model,
        }


async def query_model(
    model: str, messages: list[dict[str, str]], timeout: float = 120.0
) -> dict[str, Any] | ModelQueryError:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content' and optional 'reasoning_details',
        or ModelQueryError if the request failed
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OPENROUTER_API_URL, headers=headers, json=payload
                )

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

                data = response.json()

                # OpenRouter can return 200 OK with an error body when the
                # underlying provider fails (no `choices` field in that case)
                if "error" in data and "choices" not in data:
                    err = data["error"]
                    if not isinstance(err, dict):
                        err = {"message": str(err)}
                    try:
                        err_code = int(err.get("code", 500))
                    except (TypeError, ValueError):
                        err_code = 500
                    err_msg = err.get("message", "Unknown provider error")
                    error_type = "rate_limit" if err_code == 429 else "server"
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

                msg = data["choices"][0]["message"]

                return {
                    "content": msg.get("content"),
                    "reasoning_details": msg.get("reasoning_details"),
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
            logger.exception("Error querying model %s: %s", model, e)
            return ModelQueryError(error_type="unknown", message=str(e), model=model)

    # Should never reach here
    return ModelQueryError(
        error_type="unknown", message="Unexpected retry loop exit.", model=model
    )


async def query_models_parallel(
    models: list[str], messages: list[dict[str, str]]
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
    tasks = [query_model(model, messages) for model in models]

    # Wait for all to complete
    responses = await asyncio.gather(*tasks)

    # Map models to their responses
    return dict(zip(models, responses, strict=False))


def is_error(response: dict[str, Any] | ModelQueryError | None) -> bool:
    """Check if a response is an error."""
    return isinstance(response, ModelQueryError) or response is None
