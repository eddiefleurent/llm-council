"""
One-off script: re-run Stage 2+3 for a conversation where Stage 1 succeeded
but Stage 2/3 failed. Patches the conversation file in place.

Usage:
    python -m scripts.retry_stage2_3 <conversation_id>
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import apply_online_variant
from backend.council import (
    calculate_aggregate_rankings,
    calculate_tournament_rankings,
    stage2_collect_rankings,
    stage3_synthesize_final,
)


async def retry(conversation_id: str) -> None:
    data_path = Path("data/conversations") / f"{conversation_id}.json"
    if not data_path.exists():
        print(f"Conversation not found: {data_path}")
        sys.exit(1)

    with data_path.open() as f:
        convo = json.load(f)

    # Find the failed assistant message
    msg = next(
        (m for m in reversed(convo["messages"]) if m["role"] == "assistant"),
        None,
    )
    if not msg:
        print("No assistant message found.")
        sys.exit(1)

    stage1 = msg.get("stage1")
    if not stage1:
        print("No Stage 1 data stored — cannot retry without re-running Stage 1.")
        sys.exit(1)

    # Resolve models — apply :online if web search was enabled
    council_models = convo.get("council_models", [])
    chairman_model = convo.get("chairman_model")
    web_search = convo.get("web_search_enabled", False)

    if web_search:
        council_models = [apply_online_variant(m) for m in council_models]
        chairman_model = apply_online_variant(chairman_model)

    print(f"Re-running Stage 2+3 for conversation: {conversation_id}")
    print(f"  Council: {council_models}")
    print(f"  Chairman: {chairman_model}")
    print(f"  Stage 1 responses: {len(stage1)}")

    # Get the user query that triggered this assistant message (walk backward from it)
    msg_index = convo["messages"].index(msg)
    user_query = next(
        (
            m["content"]
            for m in reversed(convo["messages"][:msg_index])
            if m["role"] == "user"
        ),
        "",
    )

    # Stage 2
    print("\n[Stage 2] Running rankings...")
    stage2_results, label_to_model, stage2_errors = await stage2_collect_rankings(
        user_query, stage1, council_models
    )
    print(f"[Stage 2] {len(stage2_results)} successful, {len(stage2_errors)} failed")

    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
    tournament_rankings = calculate_tournament_rankings(stage2_results, label_to_model)

    # Stage 3
    print("\n[Stage 3] Running chairman synthesis...")
    stage3_result, stage3_errors = await stage3_synthesize_final(
        user_query,
        stage1,
        stage2_results,
        label_to_model,
        aggregate_rankings,
        tournament_rankings,
        chairman_model,
    )
    resp_len = len(stage3_result.get("response", ""))
    print(f"[Stage 3] response length: {resp_len} chars")

    # Patch the message in place — preserve any existing Stage 1 errors
    stage1_errors = (
        msg["errors"].get("stage1", []) if isinstance(msg.get("errors"), dict) else []
    )
    errors = {"stage1": stage1_errors, "stage2": stage2_errors, "stage3": stage3_errors}
    msg["stage2"] = stage2_results
    msg["stage3"] = stage3_result
    msg["errors"] = errors if any([stage1_errors, stage2_errors, stage3_errors]) else None

    with data_path.open("w") as f:
        json.dump(convo, f, indent=2)

    print(f"\nDone. Conversation patched at {data_path}")
    if stage3_errors:
        print(f"  ⚠ Stage 3 still has errors: {stage3_errors}")
    else:
        print("  ✓ Stage 3 succeeded")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python -m scripts.retry_stage2_3 <conversation_id> [--chairman <model_id>]"
        )
        sys.exit(1)
    # Optional --chairman override
    chairman_override = None
    if "--chairman" in sys.argv:
        idx = sys.argv.index("--chairman")
        if idx + 1 < len(sys.argv):
            chairman_override = sys.argv[idx + 1]

    async def _main() -> None:
        await retry(sys.argv[1])

    if chairman_override:
        import backend.council as _c

        _orig = _c._normalize_chairman_model
        _c._normalize_chairman_model = lambda _: chairman_override  # type: ignore[assignment]

    asyncio.run(_main())
