"""Unit tests for context formatting helpers."""

import pytest

from backend.context import (
    MAX_SUMMARY_CHARS,
    build_context_messages,
    format_user_message,
    summarize_older_messages,
)


@pytest.mark.asyncio
async def test_build_context_messages_includes_attachment_content():
    history = [
        {
            "role": "user",
            "content": "Please review this file",
            "attachment": {
                "filename": "notes.txt",
                "content_type": "text/plain",
                "size_bytes": 12,
                "extracted_text": "Important context",
            },
        }
    ]
    messages = await build_context_messages(history, "Follow-up question")
    assert "Attached file: notes.txt" in messages[0]["content"]
    assert "Important context" in messages[0]["content"]
    assert messages[-1]["content"] == "Follow-up question"


def test_format_user_message_skips_invalid_attachment_payload():
    message = {
        "role": "user",
        "content": "hello",
        "attachment": {"filename": "x.txt"},
    }
    assert format_user_message(message) == "hello"


@pytest.mark.asyncio
async def test_summarize_older_messages_preserves_every_chunk(monkeypatch):
    prompts = []

    async def query(_model, messages, **kwargs):
        prompts.append(messages[0]["content"])
        return {"content": "memory"}

    monkeypatch.setattr("backend.context.query_model", query)
    content = "EARLY CONSTRAINT " + "A" * MAX_SUMMARY_CHARS + " LATEST FACT"
    summary = await summarize_older_messages([{"role": "user", "content": content}])
    assert summary == "memory\nmemory"
    assert "EARLY CONSTRAINT" in prompts[0]
    assert "LATEST FACT" in prompts[-1]
    assert all("Preserve explicit" in prompt for prompt in prompts)


@pytest.mark.asyncio
async def test_context_budget_compacts_even_short_history(monkeypatch):
    async def summarize(messages):
        assert "budget=200" in messages[0]["content"]
        return "budget=200"

    monkeypatch.setattr("backend.context.summarize_older_messages", summarize)
    history = [{"role": "user", "content": "budget=200 " + "x" * 2000}]
    messages = await build_context_messages(
        history, "follow-up", max_context_tokens=200
    )
    assert "budget=200" in messages[0]["content"]
    assert messages[-1]["content"] == "follow-up"


@pytest.mark.asyncio
async def test_context_budget_does_not_silently_drop_failed_summary(monkeypatch):
    async def summarize(messages):
        return messages[0]["content"]

    monkeypatch.setattr("backend.context.summarize_older_messages", summarize)
    with pytest.raises(ValueError, match="context budget"):
        await build_context_messages(
            [{"role": "user", "content": "x" * 2000}], "q", max_context_tokens=200
        )
