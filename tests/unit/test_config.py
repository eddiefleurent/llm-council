"""Unit tests for config module."""

from backend.config import apply_online_variant, get_effective_models


def test_apply_online_variant_basic():
    """Test applying :online suffix to a model ID."""
    result = apply_online_variant("openai/gpt-5.2")
    assert result == "openai/gpt-5.2:online"


def test_apply_online_variant_no_double_apply():
    """Test that :online suffix is not applied twice."""
    result = apply_online_variant("openai/gpt-5.2:online")
    assert result == "openai/gpt-5.2:online"


def test_apply_online_variant_empty():
    """Test applying :online to empty string."""
    result = apply_online_variant("")
    assert result == ""


def test_apply_online_variant_none():
    """Test applying :online to None."""
    result = apply_online_variant(None)
    assert result is None


def test_get_effective_models_with_web_search_enabled():
    """Test that models get :online suffix when web search is enabled."""
    council = ["openai/gpt-5", "anthropic/claude-4"]
    chairman = "google/gemini-3"

    result = get_effective_models(council, chairman, web_search_enabled=True)

    assert result["council_models"] == [
        "openai/gpt-5:online",
        "anthropic/claude-4:online",
    ]
    assert result["chairman_model"] == "google/gemini-3:online"
    assert result["web_search_enabled"] is True


def test_get_effective_models_with_web_search_disabled():
    """Test that models are unchanged when web search is disabled."""
    council = ["openai/gpt-5", "anthropic/claude-4"]
    chairman = "google/gemini-3"

    result = get_effective_models(council, chairman, web_search_enabled=False)

    assert result["council_models"] == ["openai/gpt-5", "anthropic/claude-4"]
    assert result["chairman_model"] == "google/gemini-3"
    assert result["web_search_enabled"] is False
