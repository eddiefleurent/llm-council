"""Opt-in live comparison; run as python -m scripts.evaluate_council --help."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from backend.council import chairman_direct_response, run_full_council
from scripts.legacy_council import run_legacy


def _metadata_errors(metadata):
    errors = metadata.get("errors", {}) if isinstance(metadata, dict) else {}
    if isinstance(errors, dict):
        for value in errors.values():
            if isinstance(value, list):
                yield from value
            elif value:
                yield value
    elif isinstance(errors, list):
        yield from errors


def _automated_checks(answer, metadata, cost_complete):
    response = answer.get("response") if isinstance(answer, dict) else ""
    status = metadata.get("status") if isinstance(metadata, dict) else None
    return {
        "completed": not (isinstance(answer, dict) and answer.get("error"))
        and status != "failed",
        "answer_nonempty": bool(str(response).strip()),
        "no_model_errors": not any(_metadata_errors(metadata)),
        "cost_complete": cost_complete,
    }


async def evaluate(args):
    cases = json.loads(Path(args.cases).read_text())
    failed = False
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
                cost_complete = (
                    bool(costs)
                    and all(isinstance(c, (int, float)) for c in costs)
                    and not any(metadata.get("errors", {}).values())
                    if isinstance(metadata.get("errors"), dict)
                    else False
                )
                checks = _automated_checks(answer, metadata, cost_complete)
                if not (
                    checks["completed"]
                    and checks["answer_nonempty"]
                    and checks["no_model_errors"]
                ):
                    failed = True
                record = {
                    "case": case["id"],
                    "mode": mode,
                    "answer": answer,
                    "metadata": metadata,
                    "calls": results,
                    "latency_seconds": round(time.monotonic() - started, 3),
                    "reported_cost": known_cost,
                    "cost_complete": cost_complete,
                    "automated_checks": checks,
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
    return not (failed and getattr(args, "fail_on_checks", False))


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
    parser.add_argument(
        "--fail-on-checks",
        action="store_true",
        help="Exit nonzero if automated completion/error checks fail",
    )
    args = parser.parse_args()
    if not asyncio.run(evaluate(args)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
