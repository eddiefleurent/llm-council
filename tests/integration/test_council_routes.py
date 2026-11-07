"""HTTP/SSE parity and recovery tests with an entirely mocked model layer."""

import asyncio
import json

import httpx
import pytest

from backend import main, security, storage

TEST_API_TOKEN = "test-api-token"


@pytest.fixture
async def app_client(monkeypatch, tmp_path):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    monkeypatch.setenv(security.API_TOKEN_ENV, TEST_API_TOKEN)
    main.active_generations.clear()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {TEST_API_TOKEN}"},
    ) as client:
        yield client


async def test_http_and_sse_use_same_context_pipeline_and_persist_metadata(
    monkeypatch, app_client
):
    captured = []

    async def pipeline(messages, *args, **kwargs):
        captured.append(messages)
        state = {
            "messages": messages,
            "status": "complete",
            "prompt_version": main.PROMPT_VERSION,
        }
        kwargs["save_checkpoint"](state)
        stages = (
            [{"model": "a", "response": "candidate"}],
            [],
            {"model": "b", "response": "final"},
            {"errors": {}, "prompt_version": main.PROMPT_VERSION},
        )
        if kwargs.get("on_event"):
            await kwargs["on_event"]({"type": "stage3_complete", "data": stages[2]})
        return stages

    monkeypatch.setattr(main, "run_full_council", pipeline)
    payload = {
        "content": "use the attachment",
        "review_mode": "analyst",
        "attachment": {
            "filename": "facts.txt",
            "content_type": "text/plain",
            "size_bytes": 4,
            "extracted_text": "X=12",
        },
    }
    for name in ["regular", "stream"]:
        storage.create_conversation(name)
        storage.add_user_message(name, "Budget is 200")
    regular = await app_client.post("/api/conversations/regular/message", json=payload)
    streamed = await app_client.post(
        "/api/conversations/stream/message/stream", json=payload
    )
    assert regular.status_code == streamed.status_code == 200
    assert captured[0] == captured[1]
    assert "Budget is 200" in json.dumps(captured[0])
    assert "X=12" in json.dumps(captured[0])
    assert '"type": "complete"' in streamed.text
    for name in ["regular", "stream"]:
        saved = storage.get_conversation(name)["messages"][-1]
        assert saved["metadata"]["prompt_version"] == main.PROMPT_VERSION


async def test_resume_rejects_missing_stale_and_active_runs(app_client):
    assert (
        await app_client.post("/api/conversations/missing/resume")
    ).status_code == 404
    storage.create_conversation("test")
    assert (await app_client.post("/api/conversations/test/resume")).status_code == 409
    storage.save_council_checkpoint("test", {"prompt_version": "old"})
    assert (await app_client.post("/api/conversations/test/resume")).status_code == 409
    main.active_generations.add("test")
    assert (await app_client.post("/api/conversations/test/resume")).status_code == 409
    main.active_generations.clear()


async def test_message_endpoints_reject_active_generations(app_client):
    storage.create_conversation("busy")
    main.active_generations.add("busy")

    for path in ("/message", "/message/stream"):
        response = await app_client.post(
            f"/api/conversations/busy{path}", json={"content": "hello"}
        )
        assert response.status_code == 409

    main.active_generations.clear()


async def test_delete_endpoints_reject_active_generations(app_client):
    storage.create_conversation("active")
    storage.create_conversation("idle")
    main.active_generations.add("active")

    response = await app_client.delete("/api/conversations/active")
    assert response.status_code == 409
    assert storage.get_conversation("active") is not None

    response = await app_client.delete("/api/conversations/idle")
    assert response.status_code == 200
    assert storage.get_conversation("idle") is None

    response = await app_client.delete("/api/conversations?confirm=true")
    assert response.status_code == 409
    assert storage.get_conversation("active") is not None

    main.active_generations.clear()
    response = await app_client.delete("/api/conversations?confirm=true")
    assert response.status_code == 200
    assert storage.get_conversation("active") is None


async def test_stream_generation_blocks_conversation_deletion(monkeypatch, app_client):
    storage.create_conversation("stream")
    release_worker = asyncio.Event()

    async def slow_worker(
        conversation_id,
        content,
        content_for_context,
        attachment,
        is_first_message,
        event_queue,
        review_mode="peer",
    ):
        await release_worker.wait()
        await event_queue.put({"type": "complete"})
        await event_queue.put(None)

    monkeypatch.setattr(main, "_run_council_stream_worker", slow_worker)
    request_task = asyncio.create_task(
        app_client.post(
            "/api/conversations/stream/message/stream", json={"content": "hello"}
        )
    )
    try:
        for _ in range(100):
            if "stream" in main.active_generations:
                break
            await asyncio.sleep(0.01)
        assert "stream" in main.active_generations

        response = await app_client.delete("/api/conversations/stream")
        assert response.status_code == 409
        assert storage.get_conversation("stream") is not None
    finally:
        release_worker.set()

    response = await request_task
    assert response.status_code == 200
    assert '"type": "complete"' in response.text
    assert "stream" not in main.active_generations
