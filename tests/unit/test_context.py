"""Unit tests for context formatting helpers."""

import pytest

from backend.context import (
    MAX_SUMMARY_CHARS,
    TRUNCATION_PREFIX,
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
async def test_summarize_older_messages_truncates_and_keeps_most_recent_text(monkeypatch):
    captured = {}

    async def fake_query_model(_model, messages, _timeout=None, **_kwargs):
        captured["prompt"] = messages[0]["content"]
        return {"content": "summary"}

    monkeypatch.setattr("backend.context.query_model", fake_query_model)

    long_content = "A" * (MAX_SUMMARY_CHARS + 500)
    messages = [{"role": "user", "content": long_content}]

    summary = await summarize_older_messages(messages)

    assert summary == "summary"
    prompt = captured["prompt"]
    conversation_section = prompt.split("Conversation:\n", maxsplit=1)[1].split(
        "\n\nConcise summary:",
        maxsplit=1,
    )[0]

    expected_tail = f"User: {long_content}\n\n"
    assert conversation_section.startswith(TRUNCATION_PREFIX)
    assert conversation_section.endswith(
        expected_tail[-(MAX_SUMMARY_CHARS - len(TRUNCATION_PREFIX)) :]
    )
    assert len(conversation_section) == MAX_SUMMARY_CHARS
