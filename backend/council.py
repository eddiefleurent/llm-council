"""3-stage LLM Council orchestration."""

import asyncio
import copy
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from .config import (
    DEFAULT_CHAIRMAN_MODEL,
    get_council_config,
    get_effective_models,
)
from .models import get_available_models
from .openrouter import ModelQueryError, query_model
from .reviews import (
    PROMPT_VERSION,
    REVIEW_POLICY,
    SYNTHESIS_POLICY,
    candidate_payload,
    parse_review,
    review_schema,
)

STAGE2_RUBRIC = """- Correctness/Factuality (weight 40%): Is the response accurate and free of clear errors?
- Completeness (weight 25%): Does it cover key parts of the question and constraints?
- Reasoning quality (weight 20%): Is the logic coherent, non-contradictory, and well-justified?
- Practical usefulness (weight 10%): Is it actionable and specific enough for the user?
- Safety/uncertainty handling (weight 5%): Does it avoid overclaiming and call out uncertainty when needed?"""


def _normalize_council_models(council_models: list[str] | None) -> list[str]:
    """Resolve council models from input or configured defaults."""
    if council_models is None:
        council_models = get_council_config().get("council_models", [])
    if not isinstance(council_models, list):
        return list(get_council_config().get("council_models", []))
    return [
        model for model in council_models if isinstance(model, str) and model.strip()
    ]


def _normalize_chairman_model(chairman_model: str | None) -> str:
    """Resolve chairman model from input or configuration."""
    if chairman_model is None:
        chairman_model = get_council_config().get("chairman_model")
    if isinstance(chairman_model, str) and chairman_model.strip():
        return chairman_model
    return DEFAULT_CHAIRMAN_MODEL


def _index_to_alpha_label(index: int) -> str:
    """Convert zero-based index to spreadsheet-style alpha labels (A..Z, AA..)."""
    if index < 0:
        raise ValueError("index must be non-negative")

    label = []
    current = index
    while True:
        current, remainder = divmod(current, 26)
        label.append(chr(65 + remainder))
        if current == 0:
            break
        current -= 1
    return "".join(reversed(label))


async def stage1_collect_responses(
    messages: list[dict[str, str]], council_models: list[str] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        messages: Full message history including current query
        council_models: Optional list of model IDs to use (defaults to configured council)

    Returns:
        Tuple of (successful responses list, errors list)
    """
    council_models = _normalize_council_models(council_models)

    # Log which models are being queried
    print(
        f"[Stage 1] Querying {len(council_models)} council models: {', '.join(council_models)}"
    )

    # Query all models in parallel with full conversation context
    async def collect(model):
        return await query_model(
            model,
            messages,
            max_tokens=4096,
            context_limit=await model_context_limit(model),
        )

    responses = dict(
        zip(
            council_models,
            await asyncio.gather(*(collect(model) for model in council_models)),
            strict=True,
        )
    )

    # Format results, separating successes from errors
    stage1_results = []
    stage1_errors = []
    for model, response in responses.items():
        if isinstance(response, ModelQueryError):
            stage1_errors.append(response.to_dict())
        elif isinstance(response, dict):
            stage1_results.append(
                {**response, "model": model, "response": response.get("content", "")}
            )
        else:
            stage1_errors.append(
                {
                    "error_type": "unknown",
                    "message": "Unknown error occurred",
                    "model": model,
                }
            )

    # Log results
    print(
        f"[Stage 1] Results: {len(stage1_results)} successful, {len(stage1_errors)} failed"
    )
    if stage1_errors:
        for error in stage1_errors:
            print(
                f"  ✗ {error.get('model', 'unknown')}: {error.get('error_type', 'unknown')} - {error.get('message', '')}"
            )

    return stage1_results, stage1_errors


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: list[dict[str, Any]],
    council_models: list[str] | None = None,
    *,
    context: list[dict[str, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    """Review evidence, retaining optional rankings for existing clients."""
    models = _normalize_council_models(council_models)
    labels = [
        f"Response {_index_to_alpha_label(i)}" for i in range(len(stage1_results))
    ]
    mapping = dict(zip(labels, [r["model"] for r in stage1_results], strict=True))
    prompt = (
        "Candidate answers:\n"
        + candidate_payload(stage1_results, labels)
        + "\nAllowed labels: "
        + json.dumps(labels)
        + "\nOutput schema: "
        + json.dumps(review_schema()["json_schema"]["schema"])
    )
    messages = [
        {"role": "system", "content": REVIEW_POLICY},
        *(context or [{"role": "user", "content": user_query}]),
        {"role": "user", "content": prompt},
    ]
    try:
        catalog = (await get_available_models()).models_by_id
    except Exception:
        catalog = {}

    async def review(model):
        info = catalog.get(model.removesuffix(":online"))
        supported = (
            info is not None and "structured_outputs" in info.supported_parameters
        )
        return await query_model(
            model,
            messages,
            max_tokens=4096,
            response_format=review_schema() if supported else None,
            context_limit=info.context_length if info else 32000,
        )

    responses = await asyncio.gather(*(review(m) for m in models))
    results, errors = [], []
    for model, response in zip(models, responses, strict=True):
        if isinstance(response, ModelQueryError):
            errors.append(response.to_dict())
            continue
        try:
            parsed = parse_review(response["content"], set(labels))
            results.append(
                {
                    **response,
                    "model": model,
                    "ranking": response["content"],
                    "parsed_ranking": parsed.final_ranking,
                    "review": parsed.model_dump(),
                }
            )
        except ValueError, TypeError, KeyError:
            errors.append(
                {
                    "error_type": "parse_failure",
                    "model": model,
                    "message": "Invalid structured review",
                    "raw_text": response.get("content"),
                    "usage": response.get("usage", {}),
                    "latency_seconds": response.get("latency_seconds"),
                }
            )
    return results, mapping, errors


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: list[dict[str, Any]],
    stage2_results: list[dict[str, Any]],
    label_to_model: dict[str, str],
    aggregate_rankings: list[dict[str, Any]],
    tournament_rankings: list[dict[str, Any]],
    chairman_model: str | None = None,
    *,
    context: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Synthesize from anonymous candidates and evidence-focused reviews."""
    chairman_model = _normalize_chairman_model(chairman_model)
    labels = list(label_to_model)
    reviews = [
        r.get("review", {"final_ranking": r.get("parsed_ranking", [])})
        for r in stage2_results
    ]
    prompt = (
        "Candidate answers:\n"
        + candidate_payload(stage1_results, labels)
        + "\nIndependent reviews (may be incomplete):\n"
        + json.dumps(reviews)
    )
    messages = [
        {"role": "system", "content": SYNTHESIS_POLICY},
        *(context or [{"role": "user", "content": user_query}]),
        {"role": "user", "content": prompt},
    ]
    response = await query_model(
        chairman_model,
        messages,
        max_tokens=8192,
        context_limit=await model_context_limit(chairman_model),
    )
    if isinstance(response, ModelQueryError):
        error = response.to_dict()
        return {
            "model": chairman_model,
            "response": "Error: " + error["message"],
            "error": error,
        }, [error]
    return {**response, "model": chairman_model, "response": response["content"]}, []


async def model_context_limit(model: str) -> int:
    try:
        info = (await get_available_models()).models_by_id.get(
            model.removesuffix(":online")
        )
        return info.context_length if info and info.context_length > 0 else 32000
    except Exception:
        return 32000


def parse_ranking_from_text(
    ranking_text: str, expected_labels: set[str] | None = None
) -> list[str]:
    """
    Parse strict JSON ranking output from a model response.

    Args:
        ranking_text: The full text response from the model (JSON object string)
        expected_labels: Optional set of labels that must appear exactly once

    Returns:
        List of response labels in ranked order
    """
    try:
        payload = json.loads(ranking_text)
    except json.JSONDecodeError:
        # Fallback: extract a valid JSON object embedded in surrounding text.
        # Try every "{" occurrence; for each, advance through "}" positions.
        payload = None
        search_start = 0
        while True:
            start = ranking_text.find("{", search_start)
            if start == -1:
                break
            pos = start
            while True:
                end = ranking_text.find("}", pos)
                if end == -1:
                    break
                try:
                    payload = json.loads(ranking_text[start : end + 1])
                    if isinstance(payload, dict) and "final_ranking" in payload:
                        break
                    payload = None
                    pos = end + 1
                except json.JSONDecodeError:
                    pos = end + 1
            if payload is not None:
                break
            search_start = start + 1
        if payload is None:
            return []

    if not isinstance(payload, dict):
        return []

    numbered = payload.get("final_ranking")
    if not isinstance(numbered, list):
        return []
    if not all(isinstance(label, str) for label in numbered):
        return []
    if len(numbered) != len(set(numbered)):
        return []

    if expected_labels is not None:
        if len(numbered) != len(expected_labels):
            return []
        if set(numbered) != expected_labels:
            return []

    return numbered


def calculate_aggregate_rankings(
    stage2_results: list[dict[str, Any]], label_to_model: dict[str, str]
) -> list[dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)
    expected_labels = set(label_to_model.keys())

    for ranking in stage2_results:
        # Prefer pre-parsed ranking from Stage 2, fall back to strict parsing.
        parsed_ranking = ranking.get("parsed_ranking")
        if not parsed_ranking:
            ranking_text = ranking.get("ranking", "")
            parsed_ranking = (
                parse_ranking_from_text(ranking_text, expected_labels=expected_labels)
                if ranking_text
                else []
            )
        if not parsed_ranking:
            continue

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append(
                {
                    "model": model,
                    "average_rank": round(avg_rank, 2),
                    "rankings_count": len(positions),
                }
            )

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x["average_rank"])

    return aggregate


def calculate_tournament_rankings(
    stage2_results: list[dict[str, Any]], label_to_model: dict[str, str]
) -> list[dict[str, Any]]:
    """
    Calculate rankings using tournament-style pairwise comparison.

    For each pair of models, count how many rankers preferred one over the other.
    The model with more pairwise wins ranks higher. This method is more robust
    to outlier rankings than simple position averaging.

    Args:
        stage2_results: Rankings from each model with parsed_ranking
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts sorted by win_percentage (descending):
        [
            {
                "model": "openai/gpt-4o",
                "wins": 4.0,
                "losses": 1.0,
                "ties": 1.0,
                "win_percentage": 0.75,
                "total_matchups": 6
            },
            ...
        ]
    """
    from collections import defaultdict

    # Get all models from label_to_model
    models = list(set(label_to_model.values()))

    if len(models) < 2:
        # Need at least 2 models for pairwise comparison
        return [
            {
                "model": m,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "win_percentage": 0.0,
                "total_matchups": 0,
            }
            for m in models
        ]

    # Track pairwise wins: pairwise_wins[(model_a, model_b)] = count of times a ranked above b
    pairwise_wins = defaultdict(int)

    # Process each ranker's parsed ranking
    # Use pre-parsed ranking if available, otherwise parse from text
    expected_labels = set(label_to_model.keys())
    for ranking in stage2_results:
        parsed_ranking = ranking.get("parsed_ranking")
        if not parsed_ranking:
            # Fallback: parse from raw ranking text (consistent with calculate_aggregate_rankings)
            ranking_text = ranking.get("ranking", "")
            parsed_ranking = (
                parse_ranking_from_text(ranking_text, expected_labels=expected_labels)
                if ranking_text
                else []
            )

        if not parsed_ranking:
            continue

        # Convert labels to model names and get their positions
        model_positions = {}
        for position, label in enumerate(parsed_ranking):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name] = position

        # For each pair of models, record who was ranked higher (lower position = better)
        ranked_models = list(model_positions.keys())
        for i in range(len(ranked_models)):
            for j in range(i + 1, len(ranked_models)):
                model_a = ranked_models[i]
                model_b = ranked_models[j]
                pos_a = model_positions[model_a]
                pos_b = model_positions[model_b]

                # Ensure consistent ordering for the key
                if model_a > model_b:
                    model_a, model_b = model_b, model_a
                    pos_a, pos_b = pos_b, pos_a

                if pos_a < pos_b:
                    pairwise_wins[(model_a, model_b, "a")] += 1
                elif pos_b < pos_a:
                    pairwise_wins[(model_a, model_b, "b")] += 1
                # Equal positions would be a tie (shouldn't happen with rankings)

    # Calculate wins, losses, and ties for each model
    model_stats = {model: {"wins": 0.0, "losses": 0.0, "ties": 0.0} for model in models}

    # Process each unique pair of models
    processed_pairs = set()
    for i in range(len(models)):
        for j in range(i + 1, len(models)):
            model_a, model_b = models[i], models[j]
            if model_a > model_b:
                model_a, model_b = model_b, model_a

            pair_key = (model_a, model_b)
            if pair_key in processed_pairs:
                continue
            processed_pairs.add(pair_key)

            a_wins = pairwise_wins.get((model_a, model_b, "a"), 0)
            b_wins = pairwise_wins.get((model_a, model_b, "b"), 0)

            if a_wins > b_wins:
                model_stats[model_a]["wins"] += 1
                model_stats[model_b]["losses"] += 1
            elif b_wins > a_wins:
                model_stats[model_b]["wins"] += 1
                model_stats[model_a]["losses"] += 1
            elif a_wins == b_wins and (a_wins > 0 or b_wins > 0):
                # Tie - both get 0.5
                model_stats[model_a]["ties"] += 1
                model_stats[model_b]["ties"] += 1

    # Calculate win percentage and build results
    results = []

    for model in models:
        stats = model_stats[model]
        total_matchups = stats["wins"] + stats["losses"] + stats["ties"]
        # Win percentage: wins + 0.5*ties / actual matchups participated in
        if total_matchups > 0:
            win_pct = (stats["wins"] + 0.5 * stats["ties"]) / total_matchups
        else:
            win_pct = 0.0

        results.append(
            {
                "model": model,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "ties": stats["ties"],
                "win_percentage": round(win_pct, 3),
                "total_matchups": int(total_matchups),
            }
        )

    # Sort by win percentage (higher is better)
    results.sort(key=lambda x: (-x["win_percentage"], x["losses"]))

    return results


def _format_ranker_preferences(
    stage2_results: list[dict[str, Any]], label_to_model: dict[str, str]
) -> str:
    """Format parsed per-ranker preferences for Stage 3 synthesis."""
    if not stage2_results:
        return "- No ranking data available."

    expected_labels = set(label_to_model.keys())
    lines = []
    for result in stage2_results:
        parsed = result.get("parsed_ranking") or parse_ranking_from_text(
            result.get("ranking", ""), expected_labels=expected_labels
        )
        if not parsed:
            continue
        mapped = [
            f"{label}->{label_to_model.get(label, 'unknown')}" for label in parsed
        ]
        lines.append(f"- {result['model']}: {', '.join(mapped)}")

    return "\n".join(lines) if lines else "- No parseable rankings available."


def _format_aggregate_rankings(aggregate_rankings: list[dict[str, Any]]) -> str:
    """Format aggregate ranking metrics for Stage 3 synthesis."""
    if not aggregate_rankings:
        return "- No aggregate ranking data available."

    lines = []
    for idx, item in enumerate(aggregate_rankings, start=1):
        lines.append(
            f"{idx}. {item['model']} (avg_rank={item['average_rank']}, "
            f"votes={item['rankings_count']})"
        )
    return "\n".join(lines)


def _format_tournament_rankings(tournament_rankings: list[dict[str, Any]]) -> str:
    """Format tournament ranking metrics for Stage 3 synthesis."""
    if not tournament_rankings:
        return "- No tournament ranking data available."

    lines = []
    for idx, item in enumerate(tournament_rankings, start=1):
        lines.append(
            f"{idx}. {item['model']} (win_pct={item['win_percentage']}, "
            f"wins={item['wins']}, losses={item['losses']}, ties={item['ties']})"
        )
    return "\n".join(lines)


async def chairman_direct_response(
    messages: list[dict[str, str]],
    chairman_model: str | None = None,
    web_search_enabled: bool | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Query the chairman model directly without the full council process.

    Used for follow-up refinement where the user wants to iterate on the
    answer with just the chairman, without running all 3 stages again.

    Args:
        messages: Full message history in OpenAI format
        chairman_model: Optional model ID for chairman (defaults to configured chairman)
        web_search_enabled: Whether to enable web search via :online variant (defaults to configured)

    Returns:
        Tuple of (result dict with 'model' and 'response' keys, errors list)
    """
    chairman_model = _normalize_chairman_model(chairman_model)

    # Apply :online suffix if web search is enabled
    effective = get_effective_models(
        chairman_model=chairman_model, web_search_enabled=web_search_enabled
    )
    effective_chairman = effective["chairman_model"]
    chairman_model = (
        _normalize_chairman_model(effective_chairman)
        if isinstance(effective_chairman, str)
        else _normalize_chairman_model(None)
    )

    print(f"[Chairman Direct] Model: {chairman_model}")

    # Query the chairman model directly with conversation context
    response = await query_model(
        chairman_model,
        messages,
        max_tokens=8192,
        context_limit=await model_context_limit(chairman_model),
    )

    errors = []
    if isinstance(response, ModelQueryError):
        error_info = response.to_dict()
        errors.append(error_info)
        print(
            f"[Chairman Direct] ✗ Failed: {error_info.get('error_type', 'unknown')} - {error_info.get('message', '')}"
        )
        return {
            "model": chairman_model,
            "response": f"Error: {error_info['message']}",
            "error": error_info,
        }, errors
    if not isinstance(response, dict):
        errors.append(
            {
                "error_type": "unknown",
                "message": "Unknown error occurred",
                "model": chairman_model,
            }
        )
        print("[Chairman Direct] ✗ Failed: unknown error")
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate response.",
        }, errors

    print("[Chairman Direct] ✓ Response complete")
    return {
        **response,
        "model": chairman_model,
        "response": response.get("content", ""),
    }, errors


async def generate_conversation_title(
    user_query: str, chairman_model: str | None = None
) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message
        chairman_model: Optional model ID for title generation (defaults to configured chairman)

    Returns:
        A short title (3-5 words)
    """
    chairman_model = _normalize_chairman_model(chairman_model)

    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use chairman model for title generation (configurable)
    response = await query_model(chairman_model, messages, timeout=10.0, max_tokens=128)

    if isinstance(response, ModelQueryError):
        # Fallback to a generic title
        return "New Conversation"
    if not isinstance(response, dict):
        return "New Conversation"

    title = response.get("content", "New Conversation").strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip("\"'")

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    messages: list[dict[str, str]],
    council_models: list[str] | None = None,
    chairman_model: str | None = None,
    web_search_enabled: bool | None = None,
    *,
    review_mode: str = "peer",
    deadline_seconds: float = 240,
    checkpoint: dict | None = None,
    save_checkpoint: Callable[[dict], None] | None = None,
    on_event: Callable[[dict], Awaitable[None]] | None = None,
) -> tuple[list, list, dict, dict]:
    """One bounded, checkpointed pipeline for HTTP, SSE and resumed runs."""
    if not messages:
        raise ValueError("No messages provided")
    if review_mode not in ("peer", "analyst"):
        raise ValueError("Unknown review mode")
    started = time.monotonic()
    state = (
        copy.deepcopy(checkpoint)
        if checkpoint
        else {
            "messages": messages,
            "config": get_effective_models(
                council_models, chairman_model, web_search_enabled
            ),
            "review_mode": review_mode,
            "prompt_version": PROMPT_VERSION,
            "errors": {"stage1": [], "stage2": [], "stage3": []},
        }
    )
    if state["prompt_version"] != PROMPT_VERSION:
        raise ValueError("Checkpoint prompt version is no longer supported")
    messages = state["messages"]
    config = state["config"]
    models = config["council_models"]
    chairman = config["chairman_model"]
    current = messages[-1]["content"]
    active_stage = "stage1"

    def persist():
        if save_checkpoint:
            save_checkpoint(copy.deepcopy(state))

    async def emit(event):
        if on_event:
            await on_event(event)

    state["status"] = "running"
    persist()
    try:
        async with asyncio.timeout(deadline_seconds):
            if not state.get("stage1"):
                await emit({"type": "stage1_start"})
                (
                    state["stage1"],
                    state["errors"]["stage1"],
                ) = await stage1_collect_responses(messages, models)
                persist()
            await emit(
                {
                    "type": "stage1_complete",
                    "data": state["stage1"],
                    "errors": state["errors"]["stage1"],
                }
            )
            if not state["stage1"]:
                state["stage3"] = {
                    "model": chairman,
                    "response": "All models failed to respond.",
                    "error": True,
                }
            else:
                active_stage = "stage2"
                if "stage2" not in state:
                    await emit({"type": "stage2_start"})
                    reviewers = (
                        [chairman] if state["review_mode"] == "analyst" else models
                    )
                    (
                        state["stage2"],
                        state["label_to_model"],
                        state["errors"]["stage2"],
                    ) = await stage2_collect_rankings(
                        current, state["stage1"], reviewers, context=messages
                    )
                    persist()
                mapping = state["label_to_model"]
                aggregate = calculate_aggregate_rankings(state["stage2"], mapping)
                tournament = calculate_tournament_rankings(state["stage2"], mapping)
                await emit(
                    {
                        "type": "stage2_complete",
                        "data": state["stage2"],
                        "errors": state["errors"]["stage2"],
                        "metadata": {
                            "label_to_model": mapping,
                            "aggregate_rankings": aggregate,
                            "tournament_rankings": tournament,
                        },
                    }
                )
                active_stage = "stage3"
                if not state.get("stage3") or state["stage3"].get("error"):
                    await emit({"type": "stage3_start"})
                    (
                        state["stage3"],
                        state["errors"]["stage3"],
                    ) = await stage3_synthesize_final(
                        current,
                        state["stage1"],
                        state["stage2"],
                        mapping,
                        aggregate,
                        tournament,
                        chairman,
                        context=messages,
                    )
                    persist()
    except TimeoutError:
        error = {
            "error_type": "deadline",
            "message": "Council deadline exceeded; completed stages can be resumed.",
            "stage": active_stage,
        }
        state["errors"][active_stage] = [error]
        state["stage3"] = {
            "model": chairman,
            "response": error["message"],
            "error": error,
        }
    state["status"] = "failed" if state["stage3"].get("error") else "complete"
    state["latency_seconds"] = round(time.monotonic() - started, 3)
    persist()
    mapping = state.get("label_to_model", {})
    metadata = {
        **config,
        "prompt_version": PROMPT_VERSION,
        "review_mode": state["review_mode"],
        "label_to_model": mapping,
        "errors": state["errors"],
        "status": state["status"],
        "aggregate_rankings": calculate_aggregate_rankings(
            state.get("stage2", []), mapping
        ),
        "tournament_rankings": calculate_tournament_rankings(
            state.get("stage2", []), mapping
        ),
        "latency_seconds": state["latency_seconds"],
    }
    await emit(
        {
            "type": "stage3_complete",
            "data": state["stage3"],
            "errors": state["errors"]["stage3"],
            "metadata": metadata,
        }
    )
    return state.get("stage1", []), state.get("stage2", []), state["stage3"], metadata


def _summarize_errors(errors: list[dict[str, Any]]) -> str:
    """Create a human-readable summary of errors."""
    if not errors:
        return "Please try again."

    # Group by error type
    by_type = {}
    for error in errors:
        error_type = error.get("error_type", "unknown")
        if error_type not in by_type:
            by_type[error_type] = []
        by_type[error_type].append(error)

    summaries = []
    if "auth" in by_type:
        summaries.append("API key issue - please check your OPENROUTER_API_KEY")
    if "payment" in by_type:
        summaries.append("Payment required - please add credits to OpenRouter")
    if "rate_limit" in by_type:
        summaries.append(f"{len(by_type['rate_limit'])} model(s) rate limited")
    if "not_found" in by_type:
        models = [e.get("model", "unknown") for e in by_type["not_found"]]
        summaries.append(f"Model(s) not found: {', '.join(models)}")
    if "timeout" in by_type:
        summaries.append(f"{len(by_type['timeout'])} model(s) timed out")
    if "server" in by_type:
        summaries.append("OpenRouter server error")

    return "; ".join(summaries) if summaries else "Please try again."
