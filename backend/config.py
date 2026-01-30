"""Configuration for the LLM Council."""

import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Validate API key at startup
if not OPENROUTER_API_KEY:
    raise ValueError(
        "OPENROUTER_API_KEY is not set. "
        "Please create a .env file with your API key: OPENROUTER_API_KEY=sk-or-v1-..."
    )

# Default council members - list of OpenRouter model identifiers
# These are used when no custom council is configured
DEFAULT_COUNCIL_MODELS = [
    "google/gemini-3-pro-preview",
    "anthropic/claude-opus-4.5",
    "x-ai/grok-4.1-fast",
]

# Default chairman model - synthesizes final response
DEFAULT_CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# Legacy aliases for backward compatibility
COUNCIL_MODELS = DEFAULT_COUNCIL_MODELS
CHAIRMAN_MODEL = DEFAULT_CHAIRMAN_MODEL

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# Council configuration storage file
COUNCIL_CONFIG_FILE = "data/council_config.json"


def _normalize_council_models(value) -> List[str]:
    """
    Normalize and validate council models value.
    Returns a defensive copy to prevent mutation of defaults.
    Treats empty lists or lists with non-string/blank entries as invalid.
    """
    if isinstance(value, list) and value:  # Must be non-empty list
        # Ensure all entries are non-empty strings
        if all(isinstance(m, str) and m.strip() for m in value):
            return list(value)  # Return a copy
    return list(DEFAULT_COUNCIL_MODELS)  # Return a copy of defaults


def get_council_config() -> dict:
    """
    Get the current council configuration.

    Returns a dict with:
    - council_models: List of model IDs for the council (defensive copy)
    - chairman_model: Model ID for the chairman
    - web_search_enabled: Whether to use :online variant for web search
    """
    import json

    # Try to load from config file
    if os.path.exists(COUNCIL_CONFIG_FILE):
        try:
            with open(COUNCIL_CONFIG_FILE, "r") as f:
                config = json.load(f)

                # Validate chairman_model - must be non-empty string
                chairman = config.get("chairman_model")
                if not isinstance(chairman, str) or not chairman.strip():
                    chairman = DEFAULT_CHAIRMAN_MODEL

                # Web search defaults to False if not present
                web_search_enabled = config.get("web_search_enabled", False)
                if not isinstance(web_search_enabled, bool):
                    web_search_enabled = False

                return {
                    "council_models": _normalize_council_models(config.get("council_models")),
                    "chairman_model": chairman,
                    "web_search_enabled": web_search_enabled
                }
        except (json.JSONDecodeError, IOError):
            pass

    # Return defaults (defensive copies)
    return {
        "council_models": list(DEFAULT_COUNCIL_MODELS),
        "chairman_model": DEFAULT_CHAIRMAN_MODEL,
        "web_search_enabled": False
    }


def apply_online_variant(model_id: str) -> str:
    """
    Apply the :online variant to a model ID for web search capability.
    
    According to OpenRouter docs, append ':online' to any model ID to enable
    real-time web search capabilities.
    
    Args:
        model_id: The base model ID (e.g., "openai/gpt-5.2")
        
    Returns:
        Model ID with :online suffix (e.g., "openai/gpt-5.2:online")
    """
    if not model_id:
        return model_id
    # Don't double-apply the suffix
    if model_id.endswith(":online"):
        return model_id
    return f"{model_id}:online"


def get_effective_models(
    council_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None,
    web_search_enabled: Optional[bool] = None
) -> dict:
    """
    Get effective model IDs with :online suffix applied if web search is enabled.
    
    Args:
        council_models: List of council model IDs (uses config if None)
        chairman_model: Chairman model ID (uses config if None)
        web_search_enabled: Whether web search is enabled (uses config if None)
        
    Returns:
        Dict with 'council_models' and 'chairman_model' keys, with :online suffix
        applied if web_search_enabled is True
    """
    config = get_council_config()
    
    if council_models is None:
        council_models = config["council_models"]
    if chairman_model is None:
        chairman_model = config["chairman_model"]
    if web_search_enabled is None:
        web_search_enabled = config["web_search_enabled"]
    
    if web_search_enabled:
        council_models = [apply_online_variant(m) for m in council_models]
        chairman_model = apply_online_variant(chairman_model)
    
    return {
        "council_models": council_models,
        "chairman_model": chairman_model,
        "web_search_enabled": web_search_enabled
    }


def save_council_config(
    council_models: List[str],
    chairman_model: str,
    web_search_enabled: bool = False
) -> None:
    """
    Save council configuration to file.

    Args:
        council_models: List of model IDs for the council
        chairman_model: Model ID for the chairman
        web_search_enabled: Whether to enable web search (:online variant)
    """
    import json
    import tempfile

    # Ensure data directory exists
    dir_path = os.path.dirname(COUNCIL_CONFIG_FILE)
    os.makedirs(dir_path, exist_ok=True)

    config = {
        "council_models": council_models,
        "chairman_model": chairman_model,
        "web_search_enabled": web_search_enabled
    }

    # Use atomic write: temp file + replace to prevent corruption on crash
    with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False) as tmp:
        json.dump(config, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, COUNCIL_CONFIG_FILE)
