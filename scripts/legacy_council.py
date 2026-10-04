"""Frozen ranking-only prompt baseline for opt-in evaluations, not app routing."""

import json
from pathlib import Path

from backend.config import get_effective_models
from backend.council import (
    STAGE2_RUBRIC,
    _format_aggregate_rankings,
    _format_ranker_preferences,
    _format_tournament_rankings,
    _index_to_alpha_label,
    calculate_aggregate_rankings,
    calculate_tournament_rankings,
    model_context_limit,
    parse_ranking_from_text,
    stage1_collect_responses,
)
from backend.openrouter import ModelQueryError, query_model, query_models_parallel


async def run_legacy(messages, models, chairman, web):
    config = get_effective_models(models, chairman, web)
    models, chairman = config["council_models"], config["chairman_model"]
    prompts = json.loads(
        (
            Path(__file__).resolve().parents[1] / "tests/evals/legacy_prompts.json"
        ).read_text()
    )
    candidates, panel_errors = await stage1_collect_responses(messages, models)
    if not candidates:
        return (
            [],
            [],
            {"response": "All panel models failed", "error": True},
            {"errors": {"stage1": panel_errors}},
        )
    labels = [f"Response {_index_to_alpha_label(i)}" for i in range(len(candidates))]
    mapping = dict(zip(labels, [r["model"] for r in candidates], strict=True))
    query = messages[-1]["content"]
    ranking_prompt = prompts["ranking_prompt"].format(
        user_query=query,
        responses_text="\n\n".join(
            f"{label}:\n{r['response']}"
            for label, r in zip(labels, candidates, strict=True)
        ),
        STAGE2_RUBRIC=STAGE2_RUBRIC,
        allowed_labels_json=json.dumps(labels),
    )
    responses = await query_models_parallel(
        models,
        [{"role": "user", "content": ranking_prompt}],
        max_tokens=4096,
        context_limit=min([await model_context_limit(m) for m in models]),
    )
    reviews, errors = [], []
    for model, response in responses.items():
        if isinstance(response, ModelQueryError):
            errors.append(response.to_dict())
            continue
        parsed = parse_ranking_from_text(response["content"], set(labels))
        if not parsed:
            errors.append(
                {
                    "model": model,
                    "error_type": "parse_failure",
                    "usage": response.get("usage", {}),
                }
            )
            continue
        reviews.append(
            {
                **response,
                "model": model,
                "ranking": response["content"],
                "parsed_ranking": parsed,
            }
        )
    aggregate = calculate_aggregate_rankings(reviews, mapping)
    tournament = calculate_tournament_rankings(reviews, mapping)
    prompt = prompts["chairman_prompt"].format(
        user_query=query,
        stage1_text="\n\n".join(
            f"Model: {r['model']}\nResponse: {r['response']}" for r in candidates
        ),
        ranker_preferences=_format_ranker_preferences(reviews, mapping),
        aggregate_text=_format_aggregate_rankings(aggregate),
        tournament_text=_format_tournament_rankings(tournament),
    )
    final = await query_model(
        chairman,
        [{"role": "user", "content": prompt}],
        max_tokens=8192,
        context_limit=await model_context_limit(chairman),
    )
    final_errors = []
    if isinstance(final, ModelQueryError):
        final_errors = [final.to_dict()]
        answer = {"response": final.message, "error": True}
    else:
        answer = {**final, "response": final["content"]}
    return (
        candidates,
        reviews,
        answer,
        {
            "errors": {
                "stage1": panel_errors,
                "stage2": errors,
                "stage3": final_errors,
            },
            "prompt_version": "legacy-ranking",
        },
    )
