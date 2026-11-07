"""Fixtures for deterministic end-to-end API tests."""

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from backend import config, council, main, storage
from backend.openrouter import ModelQueryError

COUNCIL_MODELS = ["test/model-a", "test/model-b"]
CHAIRMAN_MODEL = "test/chairman"


def _allowed_labels(prompt: str) -> list[str]:
    marker = "Allowed labels: "
    index = prompt.find(marker)
    if index == -1:
        return []
    line = prompt[index + len(marker) :].splitlines()[0]
    try:
        labels = json.loads(line)
    except json.JSONDecodeError:
        return []
    return labels if isinstance(labels, list) else []


class FakeOpenRouter:
    """Deterministic model layer that exercises the real council pipeline."""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self.stage1_handler = None
        self.stage2_handler = None
        self.stage3_handler = None

    async def query_model(self, model, messages, timeout=120.0, **kwargs):
        self.calls.append({"model": model, "messages": messages, "kwargs": kwargs})
        result = await self._generate(model, messages)
        if isinstance(result, ModelQueryError):
            return result
        if isinstance(result, dict):
            return result
        return {
            "content": result,
            "usage": {"cost": 0.001, "prompt_tokens": 12, "completion_tokens": 8},
            "generation_id": f"gen-{len(self.calls)}",
            "latency_seconds": 0.01,
            "attempts": 1,
            "annotations": [],
        }

    async def _generate(self, model: str, messages: list[dict[str, str]]):
        system = "\n".join(
            message.get("content", "")
            for message in messages
            if message.get("role") == "system"
        )
        last_content = messages[-1].get("content", "") if messages else ""

        if "Generate a very short title" in last_content:
            return "Test Conversation"

        if "impartial analyst" in system:
            if self.stage2_handler is not None:
                handled = await self.stage2_handler(model, last_content)
                if handled is not None:
                    return handled
            review = {"findings": [], "final_ranking": _allowed_labels(last_content)}
            return json.dumps(review)

        if "Answer the user's actual request" in system:
            if self.stage3_handler is not None:
                handled = await self.stage3_handler(model, last_content)
                if handled is not None:
                    return handled
            return "Final council answer"

        if model == CHAIRMAN_MODEL:
            return "Chairman direct answer"

        if self.stage1_handler is not None:
            handled = await self.stage1_handler(model, messages)
            if handled is not None:
                return handled
        return f"Candidate answer from {model}"


@pytest.fixture
async def harness(monkeypatch, tmp_path):
    """Run the FastAPI app with isolated storage and a fake OpenRouter layer."""
    fake = FakeOpenRouter()

    async def empty_catalog():
        return {}

    monkeypatch.setattr(council, "_get_model_catalog", empty_catalog)
    monkeypatch.setattr(council, "query_model", fake.query_model)

    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path / "conversations"))
    config_path = tmp_path / "council_config.json"
    config_path.write_text(
        json.dumps(
            {
                "council_models": COUNCIL_MODELS,
                "chairman_model": CHAIRMAN_MODEL,
                "web_search_enabled": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "COUNCIL_CONFIG_FILE", str(config_path))
    main.active_generations.clear()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        try:
            yield SimpleNamespace(client=client, fake=fake)
        finally:
            main.active_generations.clear()
