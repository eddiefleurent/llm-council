"""Context management for multi-message conversations with smart summarization."""

from typing import Any

from .config import CHAIRMAN_MODEL
from .openrouter import is_error, query_model


async def summarize_older_messages(messages: list[dict[str, str]]) -> str:
    """Summarize older messages into a concise conversation summary."""
    conversation_text = ""
    for msg in messages:
        role = msg["role"].capitalize()
        if msg["role"] == "user":
            conversation_text += f"{role}: {msg['content']}\n\n"
        else:
            if "stage3" in msg and "response" in msg["stage3"]:
                conversation_text += f"{role}: {msg['stage3']['response']}\n\n"
            elif "content" in msg:
                conversation_text += f"{role}: {msg['content']}\n\n"

    summary_prompt = f"""Summarize the following conversation concisely in 2-3 sentences. Focus on key topics, questions asked, and important context that would be needed to understand follow-up questions.

Conversation:
{conversation_text}

Concise summary:"""

    messages_for_api = [{"role": "user", "content": summary_prompt}]
    response = await query_model(CHAIRMAN_MODEL, messages_for_api, timeout=30.0)

    if is_error(response):
        return "Previous conversation: " + conversation_text[:200] + "..."

    return response.get("content", "").strip()


def format_assistant_message(assistant_msg: dict[str, Any]) -> str:
    """Convert council's 3-stage output into clean text for context."""
    if "stage3" in assistant_msg and "response" in assistant_msg["stage3"]:
        return assistant_msg["stage3"]["response"]

    if "content" in assistant_msg:
        return assistant_msg["content"]

    return "[Assistant response]"


async def build_context_messages(
    conversation_messages: list[dict[str, Any]],
    current_query: str,
    recent_message_limit: int = 5,
) -> list[dict[str, str]]:
    """Build message history with smart summarization for long conversations."""
    if len(conversation_messages) == 0:
        return [{"role": "user", "content": current_query}]

    num_recent_messages = recent_message_limit * 2

    if len(conversation_messages) <= num_recent_messages:
        formatted_messages = []
        for msg in conversation_messages:
            if msg["role"] == "user":
                formatted_messages.append({"role": "user", "content": msg["content"]})
            else:
                content = format_assistant_message(msg)
                formatted_messages.append({"role": "assistant", "content": content})

        formatted_messages.append({"role": "user", "content": current_query})
        return formatted_messages

    older_messages = conversation_messages[:-num_recent_messages]
    recent_messages = conversation_messages[-num_recent_messages:]

    summary = await summarize_older_messages(older_messages)

    formatted_messages = [
        {"role": "user", "content": f"[Previous conversation summary: {summary}]"},
        {
            "role": "assistant",
            "content": "I understand the previous conversation context.",
        },
    ]

    for msg in recent_messages:
        if msg["role"] == "user":
            formatted_messages.append({"role": "user", "content": msg["content"]})
        else:
            content = format_assistant_message(msg)
            formatted_messages.append({"role": "assistant", "content": content})

    formatted_messages.append({"role": "user", "content": current_query})
    return formatted_messages
