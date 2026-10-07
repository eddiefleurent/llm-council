"""Behavioral coverage for context, evidence review, and resumable orchestration."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from backend import council, storage
from backend.openrouter import ModelQueryError
from backend.reviews import parse_review


@pytest.fixture
def fake_models(monkeypatch):
    async def catalog(*args, **kwargs):
        return SimpleNamespace(
            models_by_id={
                "a": SimpleNamespace(
                    context_length=100000, supported_parameters=["structured_outputs"]
                ),
                "b": SimpleNamespace(context_length=100000, supported_parameters=[]),
            }
        )

    monkeypatch.setattr(council, "get_available_models", catalog)


def test_review_rejects_unknown_labels_and_duplicate_rankings():
    base = {"findings": [], "final_ranking": ["Response A", "Response A"]}
    with pytest.raises(ValueError):
        parse_review(json.dumps(base), {"Response A", "Response B"})
    base = {
        "findings": [
            {
                "kind": "error",
                "responses": ["Response Z"],
                "claim": "x",
                "assessment": "wrong",
                "evidence": [],
                "resolution": "unsupported",
            }
        ],
        "final_ranking": [],
    }
    with pytest.raises(ValueError):
        parse_review(json.dumps(base), {"Response A"})


async def test_reviews_and_synthesis_keep_context_and_hide_model_ids(
    monkeypatch, fake_models
):
    calls = []

    async def query(model, messages, **kwargs):
        calls.append((model, messages, kwargs))
        return {
            "content": json.dumps({"findings": [], "final_ranking": []}),
            "annotations": [{"url": "https://example.com"}],
            "usage": {"cost": 0.1},
        }

    monkeypatch.setattr(council, "query_model", query)
    context = [
        {"role": "user", "content": "Budget is 200. Attached source: X=12."},
        {"role": "assistant", "content": "Understood"},
        {"role": "user", "content": "Compare options"},
    ]
    candidates = [
        {
            "model": "secret/model-a",
            "response": "X=12",
            "annotations": [{"url": "https://example.com"}],
        }
    ]
    reviews, labels, errors = await council.stage2_collect_rankings(
        "Compare options", candidates, ["a", "b"], context=context
    )
    assert not errors
    assert calls[0][2]["response_format"]["type"] == "json_schema"
    assert calls[1][2]["response_format"] is None
    result, errors = await council.stage3_synthesize_final(
        "Compare options", candidates, reviews, labels, [], [], "a", context=context
    )
    for _, messages, _ in calls:
        assert messages[0]["role"] == "system"
        assert messages[1:4] == context
        assert "secret/model-a" not in json.dumps(messages)
        assert "https://example.com" in json.dumps(messages)
    assert result["usage"]["cost"] == 0.1


async def test_failed_synthesis_resume_reuses_completed_stages(
    monkeypatch, fake_models
):
    calls = []
    fail = True

    async def query(model, messages, **kwargs):
        calls.append(model)
        if model == "a":
            return {"content": "candidate answer"}
        if kwargs.get("max_tokens") == 4096:
            return {"content": '{"findings": [], "final_ranking": []}'}
        if fail:
            return ModelQueryError("server", "unavailable", model=model)
        return {"content": "final answer"}

    monkeypatch.setattr(council, "query_model", query)
    snapshots = []
    inputs = [{"role": "user", "content": "question with attached source"}]
    result = await council.run_full_council(
        inputs,
        ["a"],
        "b",
        False,
        review_mode="analyst",
        save_checkpoint=snapshots.append,
    )
    assert result[3]["status"] == "failed"
    assert calls == ["a", "b", "b"]
    fail = False
    result = await council.run_full_council(
        inputs, checkpoint=snapshots[-1], save_checkpoint=snapshots.append
    )
    assert calls == ["a", "b", "b", "b"]
    assert result[2]["response"] == "final answer"
    assert result[3]["errors"]["stage3"] == []
    # Repeated resume is idempotent after success.
    await council.run_full_council(inputs, checkpoint=snapshots[-1])
    assert len(calls) == 4


async def test_deadline_cancels_work_and_preserves_completed_panel(
    monkeypatch, fake_models
):
    cancelled = asyncio.Event()

    async def stage1(*args, **kwargs):
        return [{"model": "a", "response": "answer"}], []

    async def stage2(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    monkeypatch.setattr(council, "stage1_collect_responses", stage1)
    monkeypatch.setattr(council, "stage2_collect_rankings", stage2)
    snapshots = []
    result = await council.run_full_council(
        [{"role": "user", "content": "q"}],
        ["a"],
        "b",
        False,
        deadline_seconds=0.02,
        save_checkpoint=snapshots.append,
    )
    assert cancelled.is_set()
    assert snapshots[-1]["stage1"][0]["response"] == "answer"
    assert "stage2" not in snapshots[-1]
    assert result[3]["errors"]["stage2"][0]["error_type"] == "deadline"


def test_finish_resume_replaces_failed_message_and_new_turn_invalidates_checkpoint(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(storage, "DATA_DIR", str(tmp_path))
    storage.create_conversation("test")
    storage.add_user_message("test", "question")
    storage.save_council_checkpoint("test", {"status": "failed"})
    storage.finish_council_run("test", [], [], {"response": "failed"}, {"errors": {}})
    storage.finish_council_run("test", [], [], {"response": "success"}, {"errors": {}})
    conversation = storage.get_conversation("test")
    assert len(conversation["messages"]) == 2
    assert conversation["messages"][-1]["stage3"]["response"] == "success"
    storage.add_user_message("test", "new question")
    assert "council_run" not in storage.get_conversation("test")


@pytest.mark.parametrize("discovery_fails", [False, True])
async def test_run_shares_discovery_across_stages_and_refreshes_next_run(
    monkeypatch, discovery_fails
):
    from backend import models

    discovery_calls = []
    completions = []

    async def fetch():
        discovery_calls.append(True)
        if discovery_fails:
            raise TimeoutError("Catalog unavailable")
        return [
            models.ModelInfo(
                id=model,
                name=model,
                provider="test",
                context_length=100000,
                pricing_prompt=0,
                pricing_completion=0,
                supported_parameters=["structured_outputs"],
            )
            for model in ["a", "b", "c", "d", "e", "f", "g", "chairman"]
        ]

    async def query(model, messages, **kwargs):
        completions.append((model, kwargs))
        assert kwargs["context_limit"] == (32000 if discovery_fails else 100000)
        if messages[0]["content"] == council.REVIEW_POLICY:
            assert bool(kwargs["response_format"]) is not discovery_fails
            return {"content": '{"findings": [], "final_ranking": []}'}
        return {"content": "answer"}

    monkeypatch.setattr(models, "_cache", models.ModelsCache())
    monkeypatch.setattr(models, "fetch_models_from_openrouter", fetch)
    monkeypatch.setattr(council, "query_model", query)
    inputs = [{"role": "user", "content": "question"}]
    snapshots = []
    for run in range(2):
        # Expire successful discovery too, to check that each run resolves afresh.
        models._cache.last_updated = None
        result = await council.run_full_council(
            inputs,
            ["a", "b", "c", "d", "e", "f", "g"],
            "chairman",
            False,
            save_checkpoint=snapshots.append,
        )
        assert result[3]["status"] == "complete"
        assert len(discovery_calls) == run + 1
        assert len(completions) == (run + 1) * 15

    models._cache.last_updated = None
    await council.run_full_council(inputs, checkpoint=snapshots[-1])
    assert len(discovery_calls) == 2
    assert len(completions) == 30
