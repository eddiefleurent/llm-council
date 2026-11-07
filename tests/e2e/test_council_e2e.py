"""Deterministic end-to-end coverage for the council API pipeline."""

import json

import pytest

from backend.openrouter import ModelQueryError
from tests.e2e.conftest import CHAIRMAN_MODEL, COUNCIL_MODELS

pytestmark = pytest.mark.e2e


def _sse_events(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        payload = "\n".join(
            line.removeprefix("data:").strip()
            for line in block.splitlines()
            if line.startswith("data:")
        )
        if payload:
            events.append(json.loads(payload))
    return events


async def _create_conversation(client):
    response = await client.post("/api/conversations", json={})
    assert response.status_code == 200
    return response.json()["id"]


async def test_council_json_run_persists_full_pipeline(harness):
    conversation_id = await _create_conversation(harness.client)

    response = await harness.client.post(
        f"/api/conversations/{conversation_id}/message",
        json={"content": "What is 2+2?", "review_mode": "peer"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "council"
    assert [result["model"] for result in data["stage1"]] == COUNCIL_MODELS
    assert all(
        "Candidate answer from" in result["response"] for result in data["stage1"]
    )
    assert len(data["stage2"]) == 2
    assert all(
        result["parsed_ranking"] == ["Response A", "Response B"]
        for result in data["stage2"]
    )
    assert data["stage3"]["response"] == "Final council answer"

    metadata = data["metadata"]
    assert metadata["status"] == "complete"
    assert metadata["prompt_version"] == "evidence-v1"
    assert metadata["review_mode"] == "peer"
    assert metadata["council_models"] == COUNCIL_MODELS
    assert metadata["chairman_model"] == CHAIRMAN_MODEL
    assert metadata["label_to_model"] == {
        "Response A": "test/model-a",
        "Response B": "test/model-b",
    }
    assert metadata["errors"] == {"stage1": [], "stage2": [], "stage3": []}

    saved = await harness.client.get(f"/api/conversations/{conversation_id}")
    assert saved.status_code == 200
    assistant = saved.json()["messages"][-1]
    assert assistant["role"] == "assistant"
    assert assistant["stage3"]["response"] == "Final council answer"
    assert assistant["metadata"]["prompt_version"] == "evidence-v1"


async def test_council_stream_emits_ordered_events_and_persists(harness):
    conversation_id = await _create_conversation(harness.client)

    response = await harness.client.post(
        f"/api/conversations/{conversation_id}/message/stream",
        json={"content": "Stream a council answer", "review_mode": "peer"},
    )

    assert response.status_code == 200
    events = _sse_events(response.text)
    event_types = [event["type"] for event in events]
    assert event_types == [
        "stage1_start",
        "stage1_complete",
        "stage2_start",
        "stage2_complete",
        "stage3_start",
        "stage3_complete",
        "title_complete",
        "complete",
    ]
    assert "error" not in event_types

    stage2_complete = next(
        event for event in events if event["type"] == "stage2_complete"
    )
    assert stage2_complete["metadata"]["label_to_model"] == {
        "Response A": "test/model-a",
        "Response B": "test/model-b",
    }
    stage3_complete = next(
        event for event in events if event["type"] == "stage3_complete"
    )
    assert stage3_complete["data"]["response"] == "Final council answer"

    saved = await harness.client.get(f"/api/conversations/{conversation_id}")
    assert saved.status_code == 200
    assert saved.json()["messages"][-1]["stage3"]["response"] == "Final council answer"


async def test_chairman_mode_bypasses_council_stages(harness):
    conversation_id = await _create_conversation(harness.client)

    response = await harness.client.post(
        f"/api/conversations/{conversation_id}/message",
        json={"content": "Refine the answer", "mode": "chairman"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "chairman"
    assert data["stage3"]["response"] == "Chairman direct answer"
    assert data["errors"] == []
    assert {call["model"] for call in harness.fake.calls} == {CHAIRMAN_MODEL}

    saved = await harness.client.get(f"/api/conversations/{conversation_id}")
    assistant = saved.json()["messages"][-1]
    assert assistant["mode"] == "chairman"
    assert assistant["stage1"] is None
    assert assistant["stage2"] is None
    assert assistant["stage3"]["response"] == "Chairman direct answer"


async def test_analyst_mode_uses_chairman_as_sole_reviewer(harness):
    conversation_id = await _create_conversation(harness.client)

    response = await harness.client.post(
        f"/api/conversations/{conversation_id}/message",
        json={"content": "Review this carefully", "review_mode": "analyst"},
    )

    assert response.status_code == 200
    data = response.json()
    assert [result["model"] for result in data["stage1"]] == COUNCIL_MODELS
    assert len(data["stage2"]) == 1
    assert data["stage2"][0]["model"] == CHAIRMAN_MODEL
    assert data["metadata"]["review_mode"] == "analyst"
    assert data["metadata"]["label_to_model"] == {
        "Response A": "test/model-a",
        "Response B": "test/model-b",
    }


async def test_stage_failures_are_reported_and_council_completes(harness):
    async def fail_model_a_stage1(model, messages):
        if model == "test/model-a":
            return ModelQueryError("auth", "Invalid API key", model=model)
        return None

    async def fail_model_a_stage2(model, prompt):
        if model == "test/model-a":
            return ModelQueryError("auth", "Invalid API key", model=model)
        return None

    harness.fake.stage1_handler = fail_model_a_stage1
    harness.fake.stage2_handler = fail_model_a_stage2
    conversation_id = await _create_conversation(harness.client)

    response = await harness.client.post(
        f"/api/conversations/{conversation_id}/message",
        json={"content": "Handle partial failure", "review_mode": "peer"},
    )

    assert response.status_code == 200
    data = response.json()
    assert [result["model"] for result in data["stage1"]] == ["test/model-b"]
    assert [result["model"] for result in data["stage2"]] == ["test/model-b"]
    assert data["stage3"]["response"] == "Final council answer"
    assert data["metadata"]["status"] == "complete"
    assert data["metadata"]["errors"]["stage1"][0]["error_type"] == "auth"
    assert data["metadata"]["errors"]["stage2"][0]["error_type"] == "auth"


async def test_attachment_context_reaches_council_stages(harness):
    conversation_id = await _create_conversation(harness.client)

    response = await harness.client.post(
        f"/api/conversations/{conversation_id}/message",
        json={
            "content": "Summarize the attachment",
            "review_mode": "peer",
            "attachment": {
                "filename": "facts.txt",
                "content_type": "text/plain",
                "size_bytes": 4,
                "extracted_text": "X=12",
            },
        },
    )

    assert response.status_code == 200
    stage1_calls = [
        call
        for call in harness.fake.calls
        if call["model"] in COUNCIL_MODELS
        and not any(message["role"] == "system" for message in call["messages"])
    ]
    assert stage1_calls
    assert any(
        "BEGIN ATTACHMENT CONTENT" in message["content"]
        and "X=12" in message["content"]
        for call in stage1_calls
        for message in call["messages"]
    )

    synthesis_calls = [
        call
        for call in harness.fake.calls
        if call["model"] == CHAIRMAN_MODEL
        and any(
            "Answer the user's actual request" in message.get("content", "")
            for message in call["messages"]
            if message["role"] == "system"
        )
    ]
    assert synthesis_calls
    assert any(
        "BEGIN ATTACHMENT CONTENT" in message["content"]
        for call in synthesis_calls
        for message in call["messages"]
    )


async def test_failed_stage3_resumes_without_duplicating_assistant_message(harness):
    attempts = 0

    async def flaky_stage3(model, prompt):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return ModelQueryError("server", "temporary chairman failure", model=model)
        return None

    harness.fake.stage3_handler = flaky_stage3
    conversation_id = await _create_conversation(harness.client)

    first = await harness.client.post(
        f"/api/conversations/{conversation_id}/message",
        json={"content": "Resume me", "review_mode": "peer"},
    )
    assert first.status_code == 200
    assert first.json()["metadata"]["status"] == "failed"
    assert "temporary chairman failure" in first.json()["stage3"]["response"]

    before = await harness.client.get(f"/api/conversations/{conversation_id}")
    assert len(before.json()["messages"]) == 2

    resumed = await harness.client.post(f"/api/conversations/{conversation_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["metadata"]["status"] == "complete"
    assert resumed.json()["stage3"]["response"] == "Final council answer"

    after = await harness.client.get(f"/api/conversations/{conversation_id}")
    messages = after.json()["messages"]
    assert len(messages) == 2
    assert messages[-1]["stage3"]["response"] == "Final council answer"
