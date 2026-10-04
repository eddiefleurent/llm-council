# Council deliberation

The default council independently answers a task, reviews the candidates for
specific errors and omissions, then synthesizes an answer using the supporting
evidence. Agreement is not treated as proof. Candidate model IDs are omitted from
review and synthesis prompts; models can still self-identify in their answer text.

`backend/reviews.py` contains the versioned policies and review schema. Rankings
remain available for existing clients but are optional and secondary to findings.
Every stage receives the same context, including attachment text and follow-up
history. Citation annotations returned by OpenRouter are retained and supplied to
synthesis. This preserves provenance; it does not independently verify every URL.
Existing `:online` search configuration continues to apply.

## API

The existing message and message/stream routes accept an optional review mode:

```json
{"content": "Compare these options", "review_mode": "analyst"}
```

- `peer` (default): each council model reviews all candidates.
- `analyst`: the configured chairman performs one review, followed by a separate
  synthesis call. With N panelists, this uses N+2 primary completions instead of
  2N+1. Actual costs depend on tokens, models, search and retries.

No default quality advantage is assumed. The frontend continues to show raw review
JSON and optional rankings. Mode selection and resumption are backend API features.

POST `/api/conversations/{id}/resume` resumes the latest council turn. Saved
successful stages are reused; an interrupted stage may need to run again. A failed
synthesis retries only synthesis. A successful resume replaces the previous failed
assistant turn, and repeating resume after completion makes no model calls.
Starting a new message discards the old checkpoint. Resume uses the saved model
configuration and input context, not subsequently edited settings. Checkpoints from
an incompatible prompt version are rejected with 409.

Stages are saved before completion events. The final assistant message and its
metadata are saved together. JSON writes use atomic replacement to avoid torn
files. As before, the generation lock is per-process: use one server worker with
this file storage implementation. This is not a distributed job queue. Completed
stages survive restart, but unfinished network requests do not. A checkpoint
contains the same potentially sensitive inputs as the conversation history.

## Limits and telemetry

- Each model call has a 120-second total deadline, including retries and waits.
- The council pipeline has a 240-second deadline across all stages. A resume gets
  a fresh deadline. Context summarization is separately bounded to 60 seconds.
- Title generation has a 10-second deadline and 128 output tokens. Panel and
  review outputs have 4096-token limits; synthesis has 8192. These limits also
  constrain reasoning tokens where the provider counts them toward completion.
- Input size is checked against model catalog context lengths, reserving output
  capacity. If discovery is unavailable, the conservative fallback is 32000.
- Context preparation has a 48000 estimated-token budget. UTF-8 byte counts plus
  message overhead are used as a deliberately conservative estimate, not an exact
  tokenizer. This can reject inputs that a particular model could fit. Evidence
  is never silently trimmed to make an oversized stage fit.
- Older history is summarized in chunks, preserving explicit constraints, facts,
  decisions, rejected options, and unresolved questions. Recent turns are retained
  verbatim when they fit. Summaries are model-generated and can still lose detail;
  failed/truncated summaries retain original source chunks and fail explicitly if
  the result cannot fit.
- Successful calls retain `usage`, `generation_id`, `latency_seconds`, `attempts`,
  `finish_reason`, `truncated`, and `annotations`. Empty text is a failure. Failed
  calls include latency; billing for timed-out attempts may be unknown.
- Invalid reviews are recorded as parse failures. Synthesis can proceed with a
  partial panel or absent reviews, and the metadata preserves those errors.
- Structured outputs use OpenRouter JSON Schema only when model discovery advertises
  support, with `require_parameters` routing. All reviews are validated locally.

## Comparing quality

Run the opt-in **paid** evaluation command from the repository root:

```bash
uv run python -m scripts.evaluate_council \
  --cases tests/evals/council_cases.json \
  --output /tmp/council-comparison.jsonl \
  --models YOUR_PANEL_MODEL_1 YOUR_PANEL_MODEL_2 \
  --chairman YOUR_CHAIRMAN_MODEL
```

Modes are `chairman`, `legacy`, `peer`, and `analyst`; `--modes` selects a subset.
`--web` enables the existing search setting. Use the same models across modes.
Legacy uses frozen original Stage 2/3 prompt templates, including its latest-query
context limitation, with the new transport limits/telemetry. It is a prompt/pipeline
baseline, not an exact reconstruction of historical provider behavior.

Add real tasks as JSON objects containing `id`, OpenAI-style `messages`, and an
explicit `rubric`. The supplied cases cover prior constraints, conflicting source
records and a correct minority position. Outputs include answers, per-call usage,
latency and blank human scoring fields. Score correctness, constraint adherence,
citation support and usefulness on a consistent 0–4 scale. Blind the mode labels
while judging; repeat runs before drawing conclusions. Unit tests establish
behavior and recovery, not answer-quality gains.

Results are flushed after each mode to a new JSONL file. Missing cost data is
marked incomplete, never assumed to be free. Reported cost is only known returned
usage; timeout/retry charges can be missing. Title and summary costs are excluded
because the harness accepts already-prepared messages. No paid evaluation is run
by the test suite.

Design references:
- [OpenRouter Fusion](https://openrouter.ai/docs/guides/routing/routers/fusion-router)
- [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
