"""OpenRouter API client for making LLM requests."""

from dataclasses import dataclass
from typing import Any

import httpx

from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


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

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL, headers=headers, json=payload
            )

            # Handle specific HTTP error codes
            if response.status_code == 401:
                return ModelQueryError(
                    error_type="auth",
                    message="Invalid API key. Please check your OPENROUTER_API_KEY.",
                    status_code=401,
                    model=model,
                )
            elif response.status_code == 402:
                return ModelQueryError(
                    error_type="payment",
                    message="Payment required. Please add credits to your OpenRouter account.",
                    status_code=402,
                    model=model,
                )
            elif response.status_code == 404:
                return ModelQueryError(
                    error_type="not_found",
                    message=f'Model "{model}" not found on OpenRouter.',
                    status_code=404,
                    model=model,
                )
            elif response.status_code == 429:
                return ModelQueryError(
                    error_type="rate_limit",
                    message="Rate limit exceeded. Please wait before retrying.",
                    status_code=429,
                    model=model,
                )
            elif response.status_code >= 500:
                return ModelQueryError(
                    error_type="server",
                    message=f"OpenRouter server error (HTTP {response.status_code}). Please try again.",
                    status_code=response.status_code,
                    model=model,
                )

            response.raise_for_status()

            data = response.json()
            message = data["choices"][0]["message"]

            return {
                "content": message.get("content"),
                "reasoning_details": message.get("reasoning_details"),
            }

    except httpx.TimeoutException:
        return ModelQueryError(
            error_type="timeout",
            message=f"Request timed out after {timeout}s.",
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
        print(f"Error querying model {model}: {e}")
        return ModelQueryError(error_type="unknown", message=str(e), model=model)


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
