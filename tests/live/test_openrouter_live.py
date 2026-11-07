"""Opt-in live OpenRouter smoke tests.

Run with a real key, for example:

    RUN_LIVE_OPENROUTER=1 OPENROUTER_API_KEY=... uv run pytest tests/live -m live

These tests spend money and are skipped unless RUN_LIVE_OPENROUTER=1 and a
non-dummy OPENROUTER_API_KEY is present.
"""

import os

import pytest

from backend.council import chairman_direct_response, run_full_council
from backend.models import get_available_models

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_OPENROUTER") != "1"
        or not os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENROUTER_API_KEY") == "pytest-dummy-key",
        reason="live OpenRouter tests require RUN_LIVE_OPENROUTER=1 and a real OPENROUTER_API_KEY",
    ),
]

PREFERRED_COUNCIL_MODELS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    "meta-llama/llama-3.3-8b-instruct",
    "mistralai/mistral-small-3.1-24b-instruct",
]
PREFERRED_CHAIRMAN_MODELS = [
    "openai/gpt-4o-mini",
    "google/gemini-2.0-flash-001",
    *PREFERRED_COUNCIL_MODELS,
]
LIVE_PROMPT = [{"role": "user", "content": "Reply with exactly: OK"}]


def _env_models(name):
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


async def _live_models():
    council_models = _env_models("LIVE_COUNCIL_MODELS")
    chairman_model = os.getenv("LIVE_CHAIRMAN_MODEL", "").strip()
    if council_models and chairman_model:
        return council_models, chairman_model

    cache = await get_available_models()
    available = set(cache.models_by_id)
    if not council_models:
        council_models = [m for m in PREFERRED_COUNCIL_MODELS if m in available][:2]
    if not chairman_model:
        chairman_model = next(
            (m for m in PREFERRED_CHAIRMAN_MODELS if m in available), None
        )

    if len(council_models) < 2 or not chairman_model:
        pytest.skip("No preferred cheap live models are available on OpenRouter")
    return council_models, chairman_model


async def test_openrouter_catalog_is_reachable():
    cache = await get_available_models(force_refresh=True)
    assert cache.models
    assert len(cache.models_by_id) == len(cache.models)


async def test_chairman_direct_live_smoke():
    _, chairman_model = await _live_models()
    result, errors = await chairman_direct_response(
        LIVE_PROMPT, chairman_model=chairman_model, web_search_enabled=False
    )

    assert errors == []
    assert result.get("response", "").strip()
    assert not result.get("error")


async def test_council_analyst_live_smoke():
    council_models, chairman_model = await _live_models()
    panel, _, answer, metadata = await run_full_council(
        LIVE_PROMPT,
        council_models=council_models,
        chairman_model=chairman_model,
        web_search_enabled=False,
        review_mode="analyst",
        deadline_seconds=180,
    )

    assert len(panel) == len(council_models)
    assert answer.get("response", "").strip()
    assert not answer.get("error")
    assert metadata["status"] == "complete"
    assert metadata["errors"]["stage1"] == []
    assert metadata["errors"]["stage2"] == []
    assert metadata["errors"]["stage3"] == []
