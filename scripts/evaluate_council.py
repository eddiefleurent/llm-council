"""Opt-in live comparison; run as python -m scripts.evaluate_council --help."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from backend.council import chairman_direct_response, run_full_council
from scripts.legacy_council import run_legacy


async def evaluate(args):
    cases = json.loads(Path(args.cases).read_text())
    # JSONL is appended after every run, preserving results if a later call fails.
    with Path(args.output).open("x") as output:
        for case in cases:
            for mode in args.modes:
                started = time.monotonic()
                messages = case["messages"]
                try:
                    if mode == "chairman":
                        async with asyncio.timeout(240):
                            answer, errors = await chairman_direct_response(
                                messages, args.chairman, args.web
                            )
                        results = [answer]
                        metadata = {"errors": {"stage3": errors}}
                    elif mode == "legacy":
                        async with asyncio.timeout(240):
                            panel, reviews, answer, metadata = await run_legacy(
                                messages, args.models, args.chairman, args.web
                            )
                        results = [*panel, *reviews, answer]
                    else:
                        panel, reviews, answer, metadata = await run_full_council(
                            messages,
                            args.models,
                            args.chairman,
                            args.web,
                            review_mode=mode,
                        )
                        results = [*panel, *reviews, answer]
                except TimeoutError:
                    answer = {"response": "Evaluation deadline exceeded", "error": True}
                    results = []
                    metadata = {"errors": {"run": [{"error_type": "deadline"}]}}
                costs = [r.get("usage", {}).get("cost") for r in results]
                # Missing billing data is unknown, never reported as zero cost.
                known_cost = sum(c for c in costs if isinstance(c, (int, float)))
                record = {
                    "case": case["id"],
                    "mode": mode,
                    "answer": answer,
                    "metadata": metadata,
                    "calls": results,
                    "latency_seconds": round(time.monotonic() - started, 3),
                    "reported_cost": known_cost,
                    "cost_complete": bool(costs)
                    and all(isinstance(c, (int, float)) for c in costs)
                    and not any(metadata.get("errors", {}).values())
                    if isinstance(metadata.get("errors"), dict)
                    else False,
                    "rubric": case.get("rubric", []),
                    "human_scores": {
                        "correctness": None,
                        "constraints": None,
                        "citations": None,
                        "usefulness": None,
                    },
                }
                output.write(json.dumps(record) + "\n")
                output.flush()
                print(f"Saved {case['id']} / {mode}")


def main():
    parser = argparse.ArgumentParser(
        description="Run paid, live council comparisons; inspect rubric and human_scores in the output."
    )
    parser.add_argument(
        "--cases", required=True, help="JSON array of id/messages/rubric objects"
    )
    parser.add_argument(
        "--output", required=True, help="New JSONL file (never overwrites)"
    )
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--chairman", required=True)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["chairman", "legacy", "peer", "analyst"],
        default=["chairman", "legacy", "peer", "analyst"],
    )
    parser.add_argument("--web", action="store_true")
    args = parser.parse_args()
    asyncio.run(evaluate(args))


if __name__ == "__main__":
    main()
