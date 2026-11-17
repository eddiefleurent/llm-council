"""Mock transport tests; never use paid model calls."""

import json

import httpx
import pytest

from backend import openrouter


def _sse_response(*frames: dict, done: bool = True) -> httpx.Response:
    """Build an SSE body from chunk dicts, terminated by [DONE]."""
    payload = "".join(f"data: {json.dumps(frame)}\n\n" for frame in frames)
    if done:
        payload += "data: [DONE]\n\n"
    return httpx.Response(200, content=payload.encode("utf-8"))


@pytest.mark.parametrize("content", [None, "", "   "])
async def test_empty_provider_answer_is_error(monkeypatch, content):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: _sse_response(
            {"choices": [{"delta": {"content": content}, "finish_reason": "stop"}]}
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
        body = json.loads(request.content)
        assert body["max_tokens"] == 128
        assert body["provider"]["require_parameters"] is True
        assert body["stream"] is True
        return _sse_response(
            {
                "id": "generation",
                "choices": [
                    {
                        "delta": {
                            "content": "answer",
                            "annotations": [{"url": "https://example.com"}],
                        },
                        "finish_reason": "length",
                    }
                ],
            },
            {"choices": [], "usage": {"cost": 0.01, "prompt_tokens": 12}},
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


async def test_stream_error_frame_retries_then_succeeds(monkeypatch):
    real_client = httpx.AsyncClient
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return _sse_response(
                {"error": {"code": 503, "message": "provider overloaded"}}
            )
        return _sse_response(
            {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}
        )

    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result["content"] == "ok"
    assert result["attempts"] == 2
    assert len(calls) == 2


async def test_stream_skips_keepalives_and_malformed_frames(monkeypatch):
    real_client = httpx.AsyncClient
    body = (
        b": OPENROUTER PROCESSING\n\n"
        b"data: {not valid json\n\n"
        b'data: {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}\n\n'
        b"data: [DONE]\n\n"
    )
    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=body)
            ),
            **kwargs,
        ),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result["content"] == "ok"


async def test_reasoning_details_merged_across_deltas(monkeypatch):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: _sse_response(
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_details": [
                                {"type": "reasoning.text", "index": 0, "text": "part "}
                            ]
                        }
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "reasoning_details": [
                                {
                                    "type": "reasoning.text",
                                    "index": 0,
                                    "text": "two",
                                    "signature": "sig-1",
                                }
                            ],
                            "content": "done",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
        )
    )
    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result["reasoning_details"][0]["text"] == "part two"
    assert result["reasoning_details"][0]["signature"] == "sig-1"


async def test_plain_json_error_body_retries_then_succeeds(monkeypatch):
    real_client = httpx.AsyncClient
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={"error": {"code": 503, "message": "provider overloaded"}},
            )
        return _sse_response(
            {"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}
        )

    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result["content"] == "ok"
    assert result["attempts"] == 2
    assert len(calls) == 2


async def test_plain_json_error_body_terminal_preserves_message(monkeypatch):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, json={"error": {"code": 404, "message": "model retired"}}
                )
            ),
            **kwargs,
        ),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result.error_type == "not_found"
    assert "model retired" in result.message


async def test_plain_json_completion_accepted(monkeypatch):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "id": "generation",
                "usage": {"prompt_tokens": 3},
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": "classic answer"},
                    }
                ],
            },
        )
    )
    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result["content"] == "classic answer"
    assert result["generation_id"] == "generation"


async def test_incomplete_stream_retries_then_succeeds(monkeypatch):
    real_client = httpx.AsyncClient
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            # Stream cut mid-generation: deltas but no finish_reason/[DONE].
            return _sse_response(
                {"choices": [{"delta": {"content": "partial"}}]}, done=False
            )
        return _sse_response(
            {"choices": [{"delta": {"content": "full"}, "finish_reason": "stop"}]}
        )

    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result["content"] == "full"
    assert result["attempts"] == 2


async def test_incomplete_stream_terminal_after_retries(monkeypatch):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        openrouter.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(
                lambda request: _sse_response(
                    {"choices": [{"delta": {"content": "partial"}}]}, done=False
                )
            ),
            **kwargs,
        ),
    )
    result = await openrouter.query_model("model", [{"role": "user", "content": "q"}])
    assert result.error_type == "incomplete_stream"


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
