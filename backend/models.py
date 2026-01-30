"""OpenRouter model discovery and management."""

import httpx
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio

from .config import OPENROUTER_API_KEY

# OpenRouter models API endpoint
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Cache TTL - models list doesn't change that frequently
CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class ModelInfo:
    """Information about a single model from OpenRouter."""
    id: str  # e.g., "anthropic/claude-3.5-sonnet"
    name: str  # Display name
    provider: str  # e.g., "anthropic"
    context_length: int
    pricing_prompt: float  # per million tokens
    pricing_completion: float  # per million tokens
    description: Optional[str] = None
    created: Optional[int] = None  # Unix timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "context_length": self.context_length,
            "pricing": {
                "prompt": self.pricing_prompt,
                "completion": self.pricing_completion
            },
            "description": self.description,
            "created": self.created
        }


@dataclass
class ModelsCache:
    """In-memory cache for OpenRouter models."""
    models: List[ModelInfo] = field(default_factory=list)
    models_by_id: Dict[str, ModelInfo] = field(default_factory=dict)
    models_by_provider: Dict[str, List[ModelInfo]] = field(default_factory=dict)
    last_updated: Optional[datetime] = None
    
    def is_stale(self) -> bool:
        """Check if cache needs refresh."""
        if self.last_updated is None:
            return True
        return datetime.now() - self.last_updated > timedelta(seconds=CACHE_TTL_SECONDS)


# Global cache instance
_cache = ModelsCache()
_cache_lock = asyncio.Lock()


# Priority providers - these appear at the top of the selection UI
PRIORITY_PROVIDERS = [
    "openai",
    "anthropic", 
    "google",
    "x-ai",
    "meta-llama",
    "mistralai",
    "deepseek",
    "cohere",
]

# Provider display names for nicer UI
PROVIDER_DISPLAY_NAMES = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "x-ai": "xAI",
    "meta-llama": "Meta",
    "mistralai": "Mistral",
    "deepseek": "DeepSeek",
    "cohere": "Cohere",
}


def _parse_model(model_data: Dict[str, Any]) -> Optional[ModelInfo]:
    """Parse a model from the OpenRouter API response."""
    model_id = model_data.get("id", "")
    
    # Skip models without proper ID format
    if "/" not in model_id:
        return None
    
    provider = model_id.split("/")[0]
    
    # Get pricing info (per million tokens)
    pricing = model_data.get("pricing", {})
    prompt_price = float(pricing.get("prompt", 0)) * 1_000_000  # Convert to per-million
    completion_price = float(pricing.get("completion", 0)) * 1_000_000
    
    return ModelInfo(
        id=model_id,
        name=model_data.get("name", model_id),
        provider=provider,
        context_length=model_data.get("context_length", 0),
        pricing_prompt=prompt_price,
        pricing_completion=completion_price,
        description=model_data.get("description"),
        created=model_data.get("created")
    )


async def fetch_models_from_openrouter() -> List[ModelInfo]:
    """
    Fetch the list of available models from OpenRouter API.
    
    Returns:
        List of ModelInfo objects
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(OPENROUTER_MODELS_URL, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        models_data = data.get("data", [])
        
        models = []
        for model_data in models_data:
            model_info = _parse_model(model_data)
            if model_info:
                models.append(model_info)
        
        return models


def _organize_models(models: List[ModelInfo]) -> Dict[str, List[ModelInfo]]:
    """
    Organize models by provider and sort by creation date (newest first).
    
    Args:
        models: List of ModelInfo objects
        
    Returns:
        Dict mapping provider name to sorted list of models
    """
    by_provider: Dict[str, List[ModelInfo]] = {}
    
    for model in models:
        if model.provider not in by_provider:
            by_provider[model.provider] = []
        by_provider[model.provider].append(model)
    
    # Sort each provider's models by creation date (newest first)
    # Models without created date go to the end
    for provider in by_provider:
        by_provider[provider].sort(
            key=lambda m: (m.created or 0),
            reverse=True
        )
    
    return by_provider


async def get_available_models(force_refresh: bool = False) -> ModelsCache:
    """
    Get available models, using cache if valid.
    
    Args:
        force_refresh: If True, bypass cache and fetch fresh data
        
    Returns:
        ModelsCache with all model data
    """
    global _cache
    
    async with _cache_lock:
        if not force_refresh and not _cache.is_stale():
            return _cache
        
        models = await fetch_models_from_openrouter()
        
        _cache.models = models
        _cache.models_by_id = {m.id: m for m in models}
        _cache.models_by_provider = _organize_models(models)
        _cache.last_updated = datetime.now()
        
        return _cache


async def get_models_grouped_by_provider() -> Dict[str, Any]:
    """
    Get models organized by provider for the frontend UI.
    
    Returns a dict with:
    - providers: List of provider info sorted with priority providers first
    - total_models: Total number of available models
    """
    cache = await get_available_models()
    
    # Build provider list
    providers = []
    seen_providers = set()
    
    # Add priority providers first (if they have models)
    for provider_id in PRIORITY_PROVIDERS:
        if provider_id in cache.models_by_provider:
            seen_providers.add(provider_id)
            models = cache.models_by_provider[provider_id]
            providers.append({
                "id": provider_id,
                "name": PROVIDER_DISPLAY_NAMES.get(provider_id, provider_id.title()),
                "model_count": len(models),
                "models": [m.to_dict() for m in models]
            })
    
    # Add remaining providers alphabetically
    other_providers = sorted([
        p for p in cache.models_by_provider.keys()
        if p not in seen_providers
    ])
    
    for provider_id in other_providers:
        models = cache.models_by_provider[provider_id]
        providers.append({
            "id": provider_id,
            "name": PROVIDER_DISPLAY_NAMES.get(provider_id, provider_id.title()),
            "model_count": len(models),
            "models": [m.to_dict() for m in models]
        })
    
    return {
        "providers": providers,
        "total_models": len(cache.models)
    }


async def get_models_for_provider(provider_id: str) -> List[Dict[str, Any]]:
    """
    Get models for a specific provider.
    
    Args:
        provider_id: The provider identifier (e.g., "anthropic")
        
    Returns:
        List of model dicts sorted by creation date (newest first)
    """
    cache = await get_available_models()
    
    models = cache.models_by_provider.get(provider_id, [])
    return [m.to_dict() for m in models]


def validate_model_ids(model_ids: List[str], cache: ModelsCache) -> tuple[List[str], List[str]]:
    """
    Validate that model IDs exist in OpenRouter.
    
    Args:
        model_ids: List of model IDs to validate
        cache: Current models cache
        
    Returns:
        Tuple of (valid_ids, invalid_ids)
    """
    valid = []
    invalid = []
    
    for model_id in model_ids:
        if model_id in cache.models_by_id:
            valid.append(model_id)
        else:
            invalid.append(model_id)
    
    return valid, invalid
