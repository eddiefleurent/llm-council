"""Unit tests for storage module."""

import pytest
import os
import json
import tempfile
from unittest.mock import patch
from backend import storage


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(storage, 'DATA_DIR', tmpdir):
            yield tmpdir


def test_create_conversation(temp_data_dir):
    """Test creating a new conversation."""
    conv_id = "test-123"
    result = storage.create_conversation(conv_id)

    assert result["id"] == conv_id
    assert result["title"] == "New Conversation"
    assert result["messages"] == []
    assert "created_at" in result

    # Verify file was created
    path = os.path.join(temp_data_dir, f"{conv_id}.json")
    assert os.path.exists(path)


@pytest.mark.usefixtures("temp_data_dir")
def test_get_conversation():
    """Test retrieving a conversation."""
    conv_id = "test-456"
    storage.create_conversation(conv_id)

    result = storage.get_conversation(conv_id)

    assert result is not None
    assert result["id"] == conv_id


@pytest.mark.usefixtures("temp_data_dir")
def test_get_conversation_not_found():
    """Test retrieving non-existent conversation returns None."""
    result = storage.get_conversation("nonexistent")
    assert result is None


@pytest.mark.usefixtures("temp_data_dir")
def test_add_user_message():
    """Test adding a user message to conversation."""
    conv_id = "test-789"
    storage.create_conversation(conv_id)

    storage.add_user_message(conv_id, "Hello, world!")

    conv = storage.get_conversation(conv_id)
    assert len(conv["messages"]) == 1
    assert conv["messages"][0]["role"] == "user"
    assert conv["messages"][0]["content"] == "Hello, world!"


@pytest.mark.usefixtures("temp_data_dir")
def test_add_assistant_message():
    """Test adding an assistant message with stages."""
    conv_id = "test-101"
    storage.create_conversation(conv_id)

    stage1 = [{"model": "gpt-4", "response": "Test response"}]
    stage2 = [{"model": "gpt-4", "ranking": "1. Response A"}]
    stage3 = {"model": "gpt-4", "response": "Final answer"}

    storage.add_assistant_message(conv_id, stage1, stage2, stage3)

    conv = storage.get_conversation(conv_id)
    assert len(conv["messages"]) == 1
    assert conv["messages"][0]["role"] == "assistant"
    assert conv["messages"][0]["stage1"] == stage1
    assert conv["messages"][0]["stage2"] == stage2
    assert conv["messages"][0]["stage3"] == stage3


@pytest.mark.usefixtures("temp_data_dir")
def test_list_conversations():
    """Test listing all conversations."""
    storage.create_conversation("conv-1")
    storage.create_conversation("conv-2")
    storage.create_conversation("conv-3")

    result = storage.list_conversations()

    assert len(result) == 3
    ids = [c["id"] for c in result]
    assert "conv-1" in ids
    assert "conv-2" in ids
    assert "conv-3" in ids


@pytest.mark.usefixtures("temp_data_dir")
def test_update_conversation_title():
    """Test updating conversation title."""
    conv_id = "test-title"
    storage.create_conversation(conv_id)

    storage.update_conversation_title(conv_id, "My Custom Title")

    conv = storage.get_conversation(conv_id)
    assert conv["title"] == "My Custom Title"


@pytest.mark.usefixtures("temp_data_dir")
def test_delete_all_conversations():
    """Test deleting all conversations."""
    storage.create_conversation("conv-1")
    storage.create_conversation("conv-2")

    storage.delete_all_conversations()

    result = storage.list_conversations()
    assert len(result) == 0
