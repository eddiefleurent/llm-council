"""Mock transport tests; never use paid model calls."""

import httpx
import pytest

from backend import openrouter


@pytest.mark.parametrize("content", [None, "", "   "])
async def test_empty_provider_answer_is_error(monkeypatch, content):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": content}}]}
        )
    )
    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    response = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert response.error_type == "empty_response"


async def test_preserve_usage_citations_and_truncation(monkeypatch):
    real_client = httpx.AsyncClient

    def respond(request):
        import json

        body = json.loads(request.content)
        assert body["max_tokens"] == 128
        assert body["provider"]["require_parameters"] is True
        return httpx.Response(
            200,
            json={
                "id": "generation",
                "usage": {"cost": 0.01, "prompt_tokens": 12},
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": "answer",
                            "annotations": [{"url": "https://example.com"}],
                        },
                    }
                ],
            },
        )

    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await openrouter.query_model(
        "model",
        [{"role": "user", "content": "q"}],
        max_tokens=128,
        response_format={"type": "json_object"},
    )
    assert result["usage"]["cost"] == 0.01
    assert result["annotations"] == [{"url": "https://example.com"}]
    assert result["truncated"] is True
    assert result["attempts"] == 1
    assert result["generation_id"] == "generation"


async def test_context_limit_fails_before_network():
    result = await openrouter.query_model(
        "model", [{"role": "user", "content": "large input"}], context_limit=1
    )
    assert result.error_type == "context_limit"


async def test_total_deadline_bounds_retries(monkeypatch):
    import asyncio

    calls = []
    real_client = httpx.AsyncClient

    async def respond(request):
        calls.append(request)
        return httpx.Response(429)

    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await openrouter.query_model(
        "model", [{"role": "user", "content": "q"}], timeout=0.02
    )
    assert result.error_type == "timeout"
    assert len(calls) == 1
    assert result.latency_seconds < 1
    await asyncio.sleep(0)
