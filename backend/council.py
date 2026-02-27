"""3-stage LLM Council orchestration."""

import json
from typing import Any

from .config import (
    get_council_config,
    get_effective_models,
)
from .openrouter import ModelQueryError, is_error, query_model, query_models_parallel

STAGE2_RUBRIC = """- Correctness/Factuality (weight 40%): Is the response accurate and free of clear errors?
- Completeness (weight 25%): Does it cover key parts of the question and constraints?
- Reasoning quality (weight 20%): Is the logic coherent, non-contradictory, and well-justified?
- Practical usefulness (weight 10%): Is it actionable and specific enough for the user?
- Safety/uncertainty handling (weight 5%): Does it avoid overclaiming and call out uncertainty when needed?"""


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
    # Use provided models or fall back to configured/default
    if council_models is None:
        config = get_council_config()
        council_models = config["council_models"]

    # Log which models are being queried
    print(
        f"[Stage 1] Querying {len(council_models)} council models: {', '.join(council_models)}"
    )

    # Query all models in parallel with full conversation context
    responses = await query_models_parallel(council_models, messages)

    # Format results, separating successes from errors
    stage1_results = []
    stage1_errors = []
    for model, response in responses.items():
        if is_error(response):
            if isinstance(response, ModelQueryError):
                stage1_errors.append(response.to_dict())
            else:
                stage1_errors.append(
                    {
                        "error_type": "unknown",
                        "message": "Unknown error occurred",
                        "model": model,
                    }
                )
        else:
            stage1_results.append(
                {"model": model, "response": response.get("content", "")}
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
) -> tuple[list[dict[str, Any]], dict[str, str], list[dict[str, Any]]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1
        council_models: Optional list of model IDs to use (defaults to configured council)

    Returns:
        Tuple of (rankings list, label_to_model mapping, errors list)
    """
    # Use provided models or fall back to configured/default
    if council_models is None:
        config = get_council_config()
        council_models = config["council_models"]

    # Log which models are being queried
    print(
        f"[Stage 2] Querying {len(council_models)} council models for rankings: {', '.join(council_models)}"
    )

    # Create anonymized labels for responses (Response A..Z, AA, AB, etc.)
    labels = [_index_to_alpha_label(i) for i in range(len(stage1_results))]

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results, strict=False)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join(
        [
            f"Response {label}:\n{result['response']}"
            for label, result in zip(labels, stage1_results, strict=False)
        ]
    )
    allowed_labels_json = json.dumps(list(label_to_model.keys()))

    ranking_prompt = f"""You are an impartial expert judge evaluating anonymized
responses to one user question.

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Scoring rubric (use this strictly):
{STAGE2_RUBRIC}

Evaluation rules:
- Judge only the content quality, not writing style alone.
- Penalize hallucinations and unsupported claims heavily.
- Prefer responses that acknowledge uncertainty over confident wrong claims.
- Use each response label exactly once in your final ranking (no ties).
- Keep output concise.

Output requirements (STRICT):
- Return exactly one valid JSON object and nothing else.
- Do not use markdown code fences.
- Use this exact schema:
  {{"final_ranking": ["Response X", "Response Y", "..."]}}
- `final_ranking` must be an array containing each allowed label exactly once.
- Allowed labels for this task are:
  {allowed_labels_json}

Now provide your JSON output:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(council_models, messages)

    # Format results, separating successes from errors
    stage2_results = []
    stage2_errors = []
    for model, response in responses.items():
        if is_error(response):
            if isinstance(response, ModelQueryError):
                stage2_errors.append(response.to_dict())
            else:
                stage2_errors.append(
                    {
                        "error_type": "unknown",
                        "message": "Unknown error occurred",
                        "model": model,
                    }
                )
        else:
            full_text = response.get("content", "")
            expected_labels = set(label_to_model.keys())
            parsed = parse_ranking_from_text(full_text, expected_labels=expected_labels)
            stage2_results.append(
                {"model": model, "ranking": full_text, "parsed_ranking": parsed}
            )

    # Log results
    print(
        f"[Stage 2] Results: {len(stage2_results)} successful, {len(stage2_errors)} failed"
    )
    if stage2_errors:
        for error in stage2_errors:
            print(
                f"  ✗ {error.get('model', 'unknown')}: {error.get('error_type', 'unknown')} - {error.get('message', '')}"
            )

    return stage2_results, label_to_model, stage2_errors


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: list[dict[str, Any]],
    stage2_results: list[dict[str, Any]],
    label_to_model: dict[str, str],
    aggregate_rankings: list[dict[str, Any]],
    tournament_rankings: list[dict[str, Any]],
    chairman_model: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        label_to_model: Mapping from anonymized label to model ID
        aggregate_rankings: Mean-position ranking summary
        tournament_rankings: Pairwise ranking summary
        chairman_model: Optional model ID for chairman (defaults to configured
            chairman)

    Returns:
        Tuple of (result dict with 'model' and 'response' keys, errors list)
    """
    # Use provided model or fall back to configured/default
    if chairman_model is None:
        config = get_council_config()
        chairman_model = config["chairman_model"]

    # Log chairman model
    print(f"[Stage 3] Chairman model: {chairman_model}")

    # Build comprehensive context for chairman
    stage1_text = "\n\n".join(
        [
            f"Model: {result['model']}\nResponse: {result['response']}"
            for result in stage1_results
        ]
    )

    ranker_preferences = _format_ranker_preferences(stage2_results, label_to_model)
    aggregate_text = _format_aggregate_rankings(aggregate_rankings)
    tournament_text = _format_tournament_rankings(tournament_rankings)

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models
have provided responses to a user's question, and then ranked each other's
responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Ranking Signals:
Per-ranker parsed preferences:
{ranker_preferences}

Aggregate mean-position ranking:
{aggregate_text}

Tournament pairwise ranking:
{tournament_text}

Synthesis policy:
- Use rankings as weak evidence, not ground truth.
- Prioritize factual correctness and internal consistency over popularity.
- If top-ranked responses conflict, resolve explicitly and explain the tradeoff.
- If uncertainty remains, state it clearly and suggest how to verify.
- Include concrete steps/examples when useful.

Provide a clear, well-reasoned final answer that represents the council's
collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(chairman_model, messages)

    stage3_errors = []
    if is_error(response):
        if isinstance(response, ModelQueryError):
            error_info = response.to_dict()
            stage3_errors.append(error_info)
            print(
                f"[Stage 3] ✗ Chairman failed: {error_info.get('error_type', 'unknown')} - {error_info.get('message', '')}"
            )
            return {
                "model": chairman_model,
                "response": f"Error: {error_info['message']}",
                "error": error_info,
            }, stage3_errors
        else:
            stage3_errors.append(
                {
                    "error_type": "unknown",
                    "message": "Unknown error occurred",
                    "model": chairman_model,
                }
            )
            print("[Stage 3] ✗ Chairman failed: unknown error")
            return {
                "model": chairman_model,
                "response": "Error: Unable to generate final synthesis.",
            }, stage3_errors

    print("[Stage 3] ✓ Chairman synthesis complete")
    return {
        "model": chairman_model,
        "response": response.get("content", ""),
    }, stage3_errors


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
        mapped = [f"{label}->{label_to_model.get(label, 'unknown')}" for label in parsed]
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
    # Use provided model or fall back to configured/default
    if chairman_model is None:
        config = get_council_config()
        chairman_model = config["chairman_model"]

    # Apply :online suffix if web search is enabled
    effective = get_effective_models(
        chairman_model=chairman_model, web_search_enabled=web_search_enabled
    )
    chairman_model = effective["chairman_model"]

    print(f"[Chairman Direct] Model: {chairman_model}")

    # Query the chairman model directly with conversation context
    response = await query_model(chairman_model, messages)

    errors = []
    if is_error(response):
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
        else:
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
    return {"model": chairman_model, "response": response.get("content", "")}, errors


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
    # Use provided model or fall back to configured/default
    if chairman_model is None:
        config = get_council_config()
        chairman_model = config["chairman_model"]

    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use chairman model for title generation (configurable)
    response = await query_model(chairman_model, messages, timeout=30.0)

    if is_error(response):
        # Fallback to a generic title
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
) -> tuple[list, list, dict, dict]:
    """
    Run the complete 3-stage council process with conversation context.

    Args:
        messages: Full message history in OpenAI format
        council_models: Optional list of model IDs for the council (defaults to configured)
        chairman_model: Optional model ID for the chairman (defaults to configured)
        web_search_enabled: Optional flag to enable web search (defaults to configured)

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
        metadata includes 'errors' list with any failures from all stages
    """
    all_errors = []

    # Defensive check: ensure messages is not empty
    if not messages:
        return (
            [],
            [],
            {
                "model": "error",
                "response": "No messages provided. Please enter a query.",
            },
            {
                "errors": {
                    "stage1": [
                        {"error_type": "validation", "message": "Empty messages list"}
                    ],
                    "stage2": [],
                    "stage3": [],
                }
            },
        )

    # Get effective models (applies :online suffix if web search enabled)
    effective = get_effective_models(council_models, chairman_model, web_search_enabled)
    council_models = effective["council_models"]
    chairman_model = effective["chairman_model"]
    web_search_enabled = effective["web_search_enabled"]

    # Extract current query from messages
    current_query = messages[-1]["content"]

    # Stage 1: Collect individual responses (with full context)
    stage1_results, stage1_errors = await stage1_collect_responses(
        messages, council_models
    )
    all_errors.extend(stage1_errors)

    # If no models responded successfully, return error with details
    if not stage1_results:
        error_summary = _summarize_errors(stage1_errors)
        return (
            [],
            [],
            {
                "model": "error",
                "response": f"All models failed to respond. {error_summary}",
            },
            {"errors": {"stage1": stage1_errors, "stage2": [], "stage3": []}},
        )

    # Stage 2: Collect rankings (uses current query only for ranking prompt)
    stage2_results, label_to_model, stage2_errors = await stage2_collect_rankings(
        current_query, stage1_results, council_models
    )
    all_errors.extend(stage2_errors)

    # Calculate aggregate rankings (both methods)
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
    tournament_rankings = calculate_tournament_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result, stage3_errors = await stage3_synthesize_final(
        current_query,
        stage1_results,
        stage2_results,
        label_to_model,
        aggregate_rankings,
        tournament_rankings,
        chairman_model,
    )
    all_errors.extend(stage3_errors)

    # Prepare metadata with structured per-stage errors
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "tournament_rankings": tournament_rankings,
        "council_models": council_models,
        "chairman_model": chairman_model,
        "web_search_enabled": web_search_enabled,
        "errors": {
            "stage1": stage1_errors,
            "stage2": stage2_errors,
            "stage3": stage3_errors,
        }
        if any([stage1_errors, stage2_errors, stage3_errors])
        else None,
    }

    # Final summary
    total_errors = len(all_errors)
    print(f"[Council] Complete! Total errors: {total_errors}")
    if total_errors > 0:
        print(f"[Council] ⚠ {total_errors} model(s) failed during the process")

    return stage1_results, stage2_results, stage3_result, metadata


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
