"""JSON-based storage for conversations."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import DATA_DIR


def ensure_data_dir():
    """Ensure the data directory exists."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def _get_safe_path(conversation_id: str) -> str:
    """
    Construct and validate a safe file path for a conversation.

    This function validates that the resulting path stays within DATA_DIR,
    preventing path traversal attacks.

    Args:
        conversation_id: The conversation identifier

    Returns:
        Validated absolute path within DATA_DIR

    Raises:
        ValueError: If the path would escape DATA_DIR
    """
    base_dir = os.path.realpath(DATA_DIR)
    # Construct and normalize the path
    fullpath = os.path.realpath(os.path.join(base_dir, f"{conversation_id}.json"))

    # Ensure the resulting path is within the data directory (path traversal protection)
    if not fullpath.startswith(base_dir + os.sep):
        raise ValueError("Invalid conversation_id: path traversal detected")

    return fullpath


def _safe_open_read(conversation_id: str):
    """
    Safely open a conversation file for reading with path validation.

    Validates the path is within DATA_DIR before opening.
    Following CodeQL's recommended pattern for path injection prevention.
    """
    base_dir = os.path.realpath(DATA_DIR)
    fullpath = os.path.realpath(os.path.join(base_dir, f"{conversation_id}.json"))

    # GOOD: Verify path is within base directory before any file operation
    if not fullpath.startswith(base_dir + os.sep):
        raise ValueError("Invalid conversation_id: path traversal detected")

    return open(fullpath)


def _safe_open_write(conversation_id: str):
    """
    Safely open a conversation file for writing with path validation.

    Validates the path is within DATA_DIR before opening.
    Following CodeQL's recommended pattern for path injection prevention.
    """
    base_dir = os.path.realpath(DATA_DIR)
    fullpath = os.path.realpath(os.path.join(base_dir, f"{conversation_id}.json"))

    # GOOD: Verify path is within base directory before any file operation
    if not fullpath.startswith(base_dir + os.sep):
        raise ValueError("Invalid conversation_id: path traversal detected")

    return open(fullpath, "w")


def _safe_path_exists(conversation_id: str) -> bool:
    """
    Safely check if a conversation file exists with path validation.

    Validates the path is within DATA_DIR before checking existence.
    """
    base_dir = os.path.realpath(DATA_DIR)
    fullpath = os.path.realpath(os.path.join(base_dir, f"{conversation_id}.json"))

    # GOOD: Verify path is within base directory before any file operation
    if not fullpath.startswith(base_dir + os.sep):
        raise ValueError("Invalid conversation_id: path traversal detected")

    return os.path.exists(fullpath)


def create_conversation(
    conversation_id: str,
    council_models: list[str] | None = None,
    chairman_model: str | None = None,
    web_search_enabled: bool | None = None,
) -> dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation
        council_models: Optional list of council model IDs (inherits from global if None)
        chairman_model: Optional chairman model ID (inherits from global if None)
        web_search_enabled: Optional web search setting (inherits from global if None)

    Returns:
        New conversation dict
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": [],
    }

    # Add per-conversation config if provided
    if council_models is not None:
        conversation["council_models"] = council_models
    if chairman_model is not None:
        conversation["chairman_model"] = chairman_model
    if web_search_enabled is not None:
        conversation["web_search_enabled"] = web_search_enabled

    # Save to file with path validation
    with _safe_open_write(conversation_id) as f:
        json.dump(conversation, f, indent=2)

    return conversation


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    if not _safe_path_exists(conversation_id):
        return None

    with _safe_open_read(conversation_id) as f:
        return json.load(f)


def save_conversation(conversation: dict[str, Any]):
    """
    Save a conversation to storage.

    Args:
        conversation: Conversation dict to save
    """
    ensure_data_dir()

    with _safe_open_write(conversation["id"]) as f:
        json.dump(conversation, f, indent=2)


def list_conversations() -> list[dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            path = os.path.join(DATA_DIR, filename)
            with open(path) as f:
                data = json.load(f)
                # Return metadata only
                conversations.append(
                    {
                        "id": data["id"],
                        "created_at": data["created_at"],
                        "title": data.get("title", "New Conversation"),
                        "message_count": len(data["messages"]),
                    }
                )

    # Sort by creation time, newest first
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    return conversations


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({"role": "user", "content": content})

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: list[dict[str, Any]],
    stage2: list[dict[str, Any]],
    stage3: dict[str, Any],
    errors: dict[str, list[dict[str, Any]]] | None = None,
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
        errors: Optional dict with 'stage1', 'stage2', 'stage3' error lists
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    message = {
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
    }

    # Add errors if any exist
    if errors and any(errors.values()):
        message["errors"] = errors

    conversation["messages"].append(message)

    save_conversation(conversation)


def add_chairman_message(
    conversation_id: str,
    response: dict[str, Any],
    errors: list[dict[str, Any]] | None = None,
):
    """
    Add a chairman-only message to a conversation.

    These are direct responses from the chairman model without the full
    3-stage council process. Used for follow-up refinement.

    Args:
        conversation_id: Conversation identifier
        response: Chairman response dict with 'model' and 'response' keys
        errors: Optional list of errors from the chairman query
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    message = {
        "role": "assistant",
        "mode": "chairman",
        "stage3": response,
        # No stage1/stage2 for chairman-only messages
        "stage1": None,
        "stage2": None,
    }

    if errors:
        message["errors"] = {"chairman": errors}

    conversation["messages"].append(message)
    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)


def get_conversation_config(conversation_id: str) -> dict[str, Any]:
    """
    Get the configuration for a specific conversation.

    If the conversation doesn't have persisted config, falls back to global config.
    Each field falls back independently - partial overrides are supported.

    Args:
        conversation_id: Conversation identifier

    Returns:
        Dict with council_models, chairman_model, and web_search_enabled
    """
    from .config import get_council_config

    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    # Start with global defaults
    global_config = get_council_config()

    # Overlay conversation-specific config (each field independently)
    return {
        "council_models": conversation.get(
            "council_models", global_config["council_models"]
        ),
        "chairman_model": conversation.get(
            "chairman_model", global_config["chairman_model"]
        ),
        "web_search_enabled": conversation.get(
            "web_search_enabled", global_config["web_search_enabled"]
        ),
    }


def update_conversation_config(
    conversation_id: str,
    council_models: list[str],
    chairman_model: str,
    web_search_enabled: bool = False,
):
    """
    Update the configuration for a specific conversation.

    Args:
        conversation_id: Conversation identifier
        council_models: List of council model IDs
        chairman_model: Chairman model ID
        web_search_enabled: Whether web search is enabled
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["council_models"] = council_models
    conversation["chairman_model"] = chairman_model
    conversation["web_search_enabled"] = web_search_enabled

    save_conversation(conversation)


def delete_all_conversations() -> list[dict[str, str]]:
    """
    Delete all conversation files from the data directory.

    Returns:
        List of dicts with 'filename' and 'error' for any files that failed to delete.
        Empty list if all deletions succeeded.
    """
    ensure_data_dir()
    failures = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            path = os.path.join(DATA_DIR, filename)
            try:
                os.remove(path)
            except OSError as e:
                failures.append({"filename": filename, "error": str(e)})
    return failures


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a single conversation file.

    Args:
        conversation_id: Conversation identifier

    Returns:
        True if deleted, False if the conversation did not exist.
    """
    if not _safe_path_exists(conversation_id):
        return False

    path = _get_safe_path(conversation_id)
    os.remove(path)
    return True
