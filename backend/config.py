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

                return {
                    "council_models": _normalize_council_models(config.get("council_models")),
                    "chairman_model": chairman
                }
        except (json.JSONDecodeError, IOError):
            pass

    # Return defaults (defensive copies)
    return {
        "council_models": list(DEFAULT_COUNCIL_MODELS),
        "chairman_model": DEFAULT_CHAIRMAN_MODEL
    }


def save_council_config(council_models: List[str], chairman_model: str) -> None:
    """
    Save council configuration to file.

    Args:
        council_models: List of model IDs for the council
        chairman_model: Model ID for the chairman
    """
    import json
    import tempfile

    # Ensure data directory exists
    dir_path = os.path.dirname(COUNCIL_CONFIG_FILE)
    os.makedirs(dir_path, exist_ok=True)

    config = {
        "council_models": council_models,
        "chairman_model": chairman_model
    }

    # Use atomic write: temp file + replace to prevent corruption on crash
    with tempfile.NamedTemporaryFile("w", dir=dir_path, delete=False) as tmp:
        json.dump(config, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
    os.replace(tmp.name, COUNCIL_CONFIG_FILE)
