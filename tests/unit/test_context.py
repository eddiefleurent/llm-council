"""Unit tests for context formatting helpers."""

import pytest

from backend.context import build_context_messages, format_user_message


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
