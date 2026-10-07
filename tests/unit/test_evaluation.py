"""Verify comparisons run all modes and report unknown costs honestly."""

import json
from types import SimpleNamespace

from scripts import evaluate_council, legacy_council


async def test_evaluation_runs_all_modes_and_records_partial_cost(
    monkeypatch, tmp_path
):
    calls = []

    async def direct(*args):
        calls.append("chairman")
        return {"response": "answer", "usage": {"cost": 0.1}}, []

    async def council(*args, **kwargs):
        calls.append(kwargs.get("review_mode", "legacy"))
        return [{"response": "candidate"}], [], {"response": "answer"}, {"errors": {}}

    monkeypatch.setattr(evaluate_council, "chairman_direct_response", direct)
    monkeypatch.setattr(evaluate_council, "run_full_council", council)
    monkeypatch.setattr(evaluate_council, "run_legacy", council)
    cases = tmp_path / "cases.json"
    cases.write_text(
        json.dumps(
            [{"id": "test", "messages": [{"role": "user", "content": "question"}]}]
        )
    )
    output = tmp_path / "results.jsonl"
    await evaluate_council.evaluate(
        SimpleNamespace(
            cases=cases,
            output=output,
            modes=["chairman", "legacy", "peer", "analyst"],
            models=["a"],
            chairman="b",
            web=False,
        )
    )
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert calls == ["chairman", "legacy", "peer", "analyst"]
    assert records[0]["reported_cost"] == 0.1
    assert records[0]["cost_complete"] is True
    assert records[-1]["cost_complete"] is False
    assert records[-1]["human_scores"]["correctness"] is None


async def test_frozen_legacy_prompts_render_and_keep_ranking_baseline(monkeypatch):
    async def collect(*args):
        return [{"model": "a", "response": "answer"}], []

    async def reviews(models, messages, **kwargs):
        assert '"final_ranking"' in messages[0]["content"]
        assert "EARLY CONSTRAINT" not in messages[0]["content"]
        return {"a": {"content": '{"final_ranking": ["Response A"]}'}}

    async def synthesize(model, messages, **kwargs):
        assert "Ranking Signals" in messages[0]["content"]
        assert "Model: a" in messages[0]["content"]
        return {"content": "final"}

    async def limit(model):
        return 128000

    monkeypatch.setattr(legacy_council, "stage1_collect_responses", collect)
    monkeypatch.setattr(legacy_council, "query_models_parallel", reviews)
    monkeypatch.setattr(legacy_council, "query_model", synthesize)
    monkeypatch.setattr(legacy_council, "model_context_limit", limit)
    result = await legacy_council.run_legacy(
        [
            {"role": "user", "content": "EARLY CONSTRAINT"},
            {"role": "user", "content": "current"},
        ],
        ["a"],
        "b",
        False,
    )
    assert result[2]["response"] == "final"
