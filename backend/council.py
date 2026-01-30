"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple, Optional
from .openrouter import query_models_parallel, query_model, ModelQueryError, is_error
from .config import DEFAULT_COUNCIL_MODELS, DEFAULT_CHAIRMAN_MODEL, get_council_config


async def stage1_collect_responses(
    messages: List[Dict[str, str]],
    council_models: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
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
    print(f"[Stage 1] Querying {len(council_models)} council models: {', '.join(council_models)}")

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
                stage1_errors.append({
                    'error_type': 'unknown',
                    'message': 'Unknown error occurred',
                    'model': model
                })
        else:
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    # Log results
    print(f"[Stage 1] Results: {len(stage1_results)} successful, {len(stage1_errors)} failed")
    if stage1_errors:
        for error in stage1_errors:
            print(f"  ✗ {error.get('model', 'unknown')}: {error.get('error_type', 'unknown')} - {error.get('message', '')}")

    return stage1_results, stage1_errors


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    council_models: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]]]:
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
    print(f"[Stage 2] Querying {len(council_models)} council models for rankings: {', '.join(council_models)}")
    
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

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
                stage2_errors.append({
                    'error_type': 'unknown',
                    'message': 'Unknown error occurred',
                    'model': model
                })
        else:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    # Log results
    print(f"[Stage 2] Results: {len(stage2_results)} successful, {len(stage2_errors)} failed")
    if stage2_errors:
        for error in stage2_errors:
            print(f"  ✗ {error.get('model', 'unknown')}: {error.get('error_type', 'unknown')} - {error.get('message', '')}")

    return stage2_results, label_to_model, stage2_errors


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman_model: Optional[str] = None
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2
        chairman_model: Optional model ID for chairman (defaults to configured chairman)

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
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(chairman_model, messages)

    stage3_errors = []
    if is_error(response):
        if isinstance(response, ModelQueryError):
            error_info = response.to_dict()
            stage3_errors.append(error_info)
            print(f"[Stage 3] ✗ Chairman failed: {error_info.get('error_type', 'unknown')} - {error_info.get('message', '')}")
            return {
                "model": chairman_model,
                "response": f"Error: {error_info['message']}",
                "error": error_info
            }, stage3_errors
        else:
            stage3_errors.append({
                'error_type': 'unknown',
                'message': 'Unknown error occurred',
                'model': chairman_model
            })
            print("[Stage 3] ✗ Chairman failed: unknown error")
            return {
                "model": chairman_model,
                "response": "Error: Unable to generate final synthesis."
            }, stage3_errors

    print("[Stage 3] ✓ Chairman synthesis complete")
    return {
        "model": chairman_model,
        "response": response.get('content', '')
    }, stage3_errors


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
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

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


def calculate_tournament_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
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
        return [{"model": m, "wins": 0, "losses": 0, "ties": 0, "win_percentage": 0.0, "total_matchups": 0} for m in models]

    # Track pairwise wins: pairwise_wins[(model_a, model_b)] = count of times a ranked above b
    pairwise_wins = defaultdict(int)

    # Process each ranker's parsed ranking
    # Use pre-parsed ranking if available, otherwise parse from text
    for ranking in stage2_results:
        parsed_ranking = ranking.get('parsed_ranking')
        if not parsed_ranking:
            # Fallback: parse from raw ranking text (consistent with calculate_aggregate_rankings)
            ranking_text = ranking.get('ranking', '')
            parsed_ranking = parse_ranking_from_text(ranking_text) if ranking_text else []

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
                    pairwise_wins[(model_a, model_b, 'a')] += 1
                elif pos_b < pos_a:
                    pairwise_wins[(model_a, model_b, 'b')] += 1
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

            a_wins = pairwise_wins.get((model_a, model_b, 'a'), 0)
            b_wins = pairwise_wins.get((model_a, model_b, 'b'), 0)

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

        results.append({
            "model": model,
            "wins": stats["wins"],
            "losses": stats["losses"],
            "ties": stats["ties"],
            "win_percentage": round(win_pct, 3),
            "total_matchups": int(total_matchups)
        })

    # Sort by win percentage (higher is better)
    results.sort(key=lambda x: (-x['win_percentage'], x['losses']))

    return results


async def generate_conversation_title(user_query: str, chairman_model: Optional[str] = None) -> str:
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

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    messages: List[Dict[str, str]],
    council_models: Optional[List[str]] = None,
    chairman_model: Optional[str] = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process with conversation context.

    Args:
        messages: Full message history in OpenAI format
        council_models: Optional list of model IDs for the council (defaults to configured)
        chairman_model: Optional model ID for the chairman (defaults to configured)

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
        metadata includes 'errors' list with any failures from all stages
    """
    all_errors = []
    
    # Defensive check: ensure messages is not empty
    if not messages:
        return [], [], {
            "model": "error",
            "response": "No messages provided. Please enter a query."
        }, {"errors": [{"error_type": "validation", "message": "Empty messages list"}]}
    
    # Get config if models not specified
    if council_models is None or chairman_model is None:
        config = get_council_config()
        if council_models is None:
            council_models = config["council_models"]
        if chairman_model is None:
            chairman_model = config["chairman_model"]
    
    # Extract current query from messages
    current_query = messages[-1]["content"]

    # Stage 1: Collect individual responses (with full context)
    stage1_results, stage1_errors = await stage1_collect_responses(messages, council_models)
    all_errors.extend(stage1_errors)

    # If no models responded successfully, return error with details
    if not stage1_results:
        error_summary = _summarize_errors(stage1_errors)
        return [], [], {
            "model": "error",
            "response": f"All models failed to respond. {error_summary}"
        }, {"errors": all_errors}

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
        chairman_model
    )
    all_errors.extend(stage3_errors)

    # Prepare metadata with structured per-stage errors
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
        "tournament_rankings": tournament_rankings,
        "council_models": council_models,
        "chairman_model": chairman_model,
        "errors": {
            "stage1": stage1_errors,
            "stage2": stage2_errors,
            "stage3": stage3_errors
        } if any([stage1_errors, stage2_errors, stage3_errors]) else None
    }

    # Final summary
    total_errors = len(all_errors)
    print(f"[Council] Complete! Total errors: {total_errors}")
    if total_errors > 0:
        print(f"[Council] ⚠ {total_errors} model(s) failed during the process")

    return stage1_results, stage2_results, stage3_result, metadata


def _summarize_errors(errors: List[Dict[str, Any]]) -> str:
    """Create a human-readable summary of errors."""
    if not errors:
        return "Please try again."

    # Group by error type
    by_type = {}
    for error in errors:
        error_type = error.get('error_type', 'unknown')
        if error_type not in by_type:
            by_type[error_type] = []
        by_type[error_type].append(error)

    summaries = []
    if 'auth' in by_type:
        summaries.append("API key issue - please check your OPENROUTER_API_KEY")
    if 'payment' in by_type:
        summaries.append("Payment required - please add credits to OpenRouter")
    if 'rate_limit' in by_type:
        summaries.append(f"{len(by_type['rate_limit'])} model(s) rate limited")
    if 'not_found' in by_type:
        models = [e.get('model', 'unknown') for e in by_type['not_found']]
        summaries.append(f"Model(s) not found: {', '.join(models)}")
    if 'timeout' in by_type:
        summaries.append(f"{len(by_type['timeout'])} model(s) timed out")
    if 'server' in by_type:
        summaries.append("OpenRouter server error")

    return "; ".join(summaries) if summaries else "Please try again."
