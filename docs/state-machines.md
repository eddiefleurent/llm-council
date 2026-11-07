# State Machine Audit

This document is the maintained inventory of the application's explicit and
implicit state machines, their invariants, and the transitions the code can
actually reach. It focuses on states that matter for correctness: persistence,
retry/deadline behavior, concurrency guards, streaming, and UI state that can
desynchronize from the backend.

## Reading guide

- **Explicit machine**: state is named or structured in code (`council_run`,
  `active_generations`, `status`, recorder booleans).
- **Implicit machine**: state is distributed across React state, refs, browser
  APIs, and async effects.
- **Confirmed defect**: a reachable invalid state/transition with evidence and
  regression coverage.
- **Watch item**: reachable or plausible, but lower impact or not fixed in this
  pass.

## Machine inventory

| # | Machine | Kind | Owner | Durable state | Concurrency guard |
|---|---------|------|-------|---------------|-------------------|
| 1 | Conversation persistence lifecycle | explicit + implicit | `backend/storage.py`, `frontend/src/App.jsx` | conversation JSON files | per-conversation generation lock for destructive/message admission paths |
| 2 | Generation admission / SSE worker lifecycle | explicit | `backend/main.py` | `active_generations`, worker tasks | `generations_lock` |
| 3 | Council checkpoint pipeline | explicit | `backend/council.py`, `storage.finish_council_run` | `conversation["council_run"]` | same generation lock; one active run per conversation |
| 4 | OpenRouter model-call retry/deadline | explicit | `backend/openrouter.py` | none | `asyncio.timeout` per call; parallel calls via `asyncio.gather` |
| 5 | Model discovery cache | explicit | `backend/models.py` | in-process cache | `_cache_lock` single-flight refresh |
| 6 | Voice transcription retry | explicit backend + implicit frontend | `backend/transcription.py`, `frontend/src/components/VoiceButton.jsx` | none durable | tenacity retry policy; recorder start/stop guards |
| 7 | Frontend session restore / draft mode | implicit | `frontend/src/App.jsx` | `sessionStorage`, `localStorage` | restore is one-shot on mount |
| 8 | Frontend SSE event application | implicit | `frontend/src/App.jsx`, `api.js` | React state only | one `activeGenerationConversationId` per UI |
| 9 | Composer / attachment / config locks | implicit | `frontend/src/components/ChatInterface.jsx`, `CouncilConfig.jsx` | React state only | derived `isLocked` state |
| 10 | Stage tab selection | implicit | `Stage1.jsx`, `Stage2.jsx` | React state only | index clamp against current result set |

## 1. Conversation persistence lifecycle

### States

| State | Meaning |
|-------|---------|
| `absent` | No JSON file for the conversation id. |
| `created_empty` | File exists with `messages: []`; may have per-conversation config. |
| `has_user_turn` | Last persisted turn is a user message, possibly with an attachment payload. |
| `checkpoint_running` | `council_run.status == "running"` with completed stage artifacts so far. |
| `checkpoint_failed` | `council_run.status == "failed"` and `stage3.error` is present. |
| `checkpoint_complete` | `council_run.status == "complete"`; a successful resume is a no-op model-wise. |
| `assistant_recorded` | Assistant message exists; for council mode it carries `stage1`, `stage2`, `stage3`, `errors`, `metadata`. |
| `deleted` | File removed. |

### Invariants

- Conversation ids are validated against path traversal before file access
  (`storage._safe_path_exists`, `_safe_open_read`, `_safe_open_write`,
  `_get_safe_path`).
- `save_conversation` writes via temp file + `os.replace`, so updates are atomic.
- `finish_council_run` writes the assistant message and run metadata together;
  it either appends a new assistant turn or replaces the failed assistant index
  stored in the checkpoint (`storage.py:430-452`).
- `add_user_message` pops `council_run`, so starting a new turn invalidates the
  old checkpoint (`storage.py:208-230`).
- A completed council checkpoint is intentionally retained so resume after
  completion makes no model calls; it is discarded on the next user message.

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| `absent` | `POST /api/conversations` | `created_empty` | optional config validated first |
| `created_empty` / `assistant_recorded` | accepted message admission | `has_user_turn` | user message appended and `council_run` removed |
| `has_user_turn` | council pipeline persist | `checkpoint_running` / `checkpoint_failed` / `checkpoint_complete` | `save_council_checkpoint` upserts `council_run` |
| `checkpoint_*` | pipeline completion | `assistant_recorded` | `finish_council_run` appends or replaces assistant turn |
| any non-deleted | `DELETE /api/conversations/{id}` | `deleted` | rejected with 409 while that id is in `active_generations` |
| any non-deleted | `DELETE /api/conversations?confirm=true` | `deleted` | rejected with 409 while any generation is active |

### Evidence

- Atomic save: `backend/storage.py:154-174`.
- Checkpoint completion/assistant replacement: `backend/storage.py:422-452`.
- New user message clears checkpoint: `backend/storage.py:227-230`.
- Delete guards: `backend/main.py:444-477`.

## 2. Generation admission and SSE worker lifecycle

### States

| State | Meaning |
|-------|---------|
| `idle` | Conversation id is not in `active_generations`. |
| `admitted` | Id added under `generations_lock`; HTTP/SSE request may proceed. |
| `worker_running` | Detached stream worker or non-stream request is executing model/storage work. |
| `releasing` | Worker finished; cleanup callback removes id under `generations_lock`. |
| `rejected` | Request returned 404/409 before admission. |

### Invariants

- At most one active generation per conversation **per server process**.
- Admission re-checks both "already active" and "conversation exists" inside
  `generations_lock`, closing the previous check-then-act window with delete
  (`backend/main.py:621-630`, `805-814`).
- Delete endpoints use the same lock and active set, so they cannot delete a
  conversation while its worker is admitted (`backend/main.py:450-477`).
- Stream workers are detached from the SSE response; client disconnect does not
  cancel generation (`backend/main.py:926-950`).
- `active_generations` is released only when the worker task completes, not when
  the HTTP stream ends.

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| `idle` | valid message/resume request | `admitted` | id added inside lock |
| `admitted` | worker starts | `worker_running` | user message and checkpoint writes begin |
| `worker_running` | worker completes/fails/cancelled | `releasing` -> `idle` | cleanup callback discards id |
| `idle` | second message/resume for same id | `rejected` | 409 |
| `idle` | message/resume for missing id | `rejected` | 404 |
| `worker_running` | delete same id | `rejected` | 409 |
| any `worker_running` | clear all | `rejected` | 409 |
| `worker_running` | SSE client disconnect | `worker_running` | worker continues; queue consumer stops |

### Evidence

- Registry and lock: `backend/main.py:53-57`.
- Admission: `backend/main.py:621-630`, `805-814`.
- Resume admission already inside lock: `backend/main.py:748-765`.
- Cleanup callback: `backend/main.py:885-900`.
- Stream detach behavior: `backend/main.py:926-950`.

## 3. Council checkpoint pipeline

### States

| State | Meaning |
|-------|---------|
| `no_checkpoint` | No `council_run` on the conversation. |
| `running` | Pipeline admitted and persisting stage artifacts. |
| `stage1_complete` | `stage1` and `errors.stage1` persisted. |
| `stage2_complete` | `stage2`, `label_to_model`, and `errors.stage2` persisted. |
| `stage3_complete` | `stage3` and `errors.stage3` persisted. |
| `complete` | `status == "complete"`; `stage3.error` absent. |
| `failed` | `status == "failed"`; normally `stage3.error` present. |

### Invariants

- `PROMPT_VERSION` must equal `"evidence-v1"`; stale checkpoints are rejected
  with 409 (`backend/main.py:748-764`, `backend/council.py:755-756`).
- Completed stages are reused on resume; missing/failed stages rerun
  (`backend/council.py:785-858`).
- The whole pipeline is bounded by `deadline_seconds=240`; each model call has
  its own 120-second deadline.
- Stage artifacts are persisted before their SSE completion events are emitted
  (`backend/council.py:773-873`).
- `status` is `"failed"` iff `stage3.error` is present after the pipeline body
  (`backend/council.py:871-873`).

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| `no_checkpoint` | new council run | `running` | initial state persisted with messages/config/review mode |
| `running` | stage1 returns | `stage1_complete` | successful responses and per-model errors persisted |
| `stage1_complete` | stage2 returns | `stage2_complete` | anonymized reviews, mapping, errors persisted |
| `stage2_complete` | stage3 returns | `stage3_complete` -> `complete`/`failed` | final metadata persisted |
| `running`/`stage1_complete`/`stage2_complete` | deadline exceeded | `failed` | deadline error recorded on active stage |
| `failed`/`complete` | `POST /resume` | rerun missing stages or no-op | requires matching prompt version and no active generation |
| any checkpoint | new user message | `no_checkpoint` | `add_user_message` pops `council_run` |

### Evidence

- Pipeline state machine: `backend/council.py:724-898`.
- Deadline handling: `backend/council.py:784`, `859-873`.
- Resume guard: `backend/main.py:748-774`.

## 4. OpenRouter model-call retry/deadline

### States

| State | Meaning |
|-------|---------|
| `attempting` | One HTTP attempt inside the retry loop. |
| `retry_wait` | Retriable failure; sleeping before next attempt. |
| `succeeded` | Usable text content returned. |
| `failed_terminal` | Non-retriable error or retries exhausted. |
| `deadline_exceeded` | Outer `asyncio.timeout` expired. |

### Invariants

- `_MAX_ATTEMPTS = 4`; waits are `_RETRY_WAIT = [1, 2, 4]` seconds.
- Retriable HTTP statuses are `{429, 500, 502, 503, 504}`; provider error
  bodies use the same retry policy when they carry those codes.
- 401/402/404 are terminal. Timeouts retry until the single outer deadline.
- `query_model` bounds all attempts and retry waits with one
  `asyncio.timeout(timeout)`; per-attempt httpx timeout is the same value, but
  the outer deadline is authoritative (`backend/openrouter.py:248-263`).

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| `attempting` | 2xx with choices/content | `succeeded` | returns content, usage, attempt count |
| `attempting` | 429/5xx before final attempt | `retry_wait` | sleep 1s/2s/4s by attempt index |
| `retry_wait` | sleep completes | `attempting` | next attempt |
| `attempting` | 401/402/404 | `failed_terminal` | no retry |
| `attempting` | retriable status on attempt 4 | `failed_terminal` | error says all attempts failed |
| `attempting` | timeout before final attempt | `retry_wait` | same backoff |
| `attempting`/`retry_wait` | outer deadline expires | `deadline_exceeded` | `TimeoutError` -> `ModelQueryError("timeout")` |
| any | unexpected exception | `failed_terminal` | logged and converted to `ModelQueryError("unknown")` |

### Evidence

- Retry constants and classification: `backend/openrouter.py:15-18`, `84-190`,
  `214-240`.
- Outer deadline: `backend/openrouter.py:254-263`.

## 5. Model discovery cache

### States

| State | Meaning |
|-------|---------|
| `empty` | No models loaded yet (`last_updated` epoch). |
| `fresh` | Cache age <= 300 seconds. |
| `stale` | Cache age > 300 seconds. |
| `refreshing` | One coroutine holds `_cache_lock` and fetches OpenRouter. |

### Invariants

- Refresh is single-flight per process because the network fetch happens while
  holding `_cache_lock` (`backend/models.py:205-228`).
- `force_refresh=True` bypasses freshness but still serializes through the lock.
- Successful refresh atomically replaces models, by-id map, provider groups, and
  timestamp.

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| `empty`/`stale` | `get_available_models()` | `refreshing` -> `fresh` | fetch then populate cache |
| `fresh` | `get_available_models()` | `fresh` | return cached `ModelsCache` |
| any | `get_available_models(force_refresh=True)` | `refreshing` -> `fresh` | bypass TTL |
| `refreshing` | fetch raises | previous cache state | exception propagates; cache is not partially updated |

### Evidence

- TTL and lock: `backend/models.py:16`, `57-66`, `205-228`.

## 6. Voice transcription retry and recorder lifecycle

### Backend states

| State | Meaning |
|-------|---------|
| `idle` | No transcription request. |
| `attempting` | Groq Whisper call in progress. |
| `retry_wait` | Transient failure; tenacity backoff before next attempt. |
| `succeeded` | Text returned to frontend. |
| `failed_terminal` | Permanent error or 4 attempts exhausted. |

Backend invariants: up to 4 total attempts, exponential backoff capped at 10s,
retries only transient Groq/network errors, and permanent auth/request/payment
errors are not retried (`backend/transcription.py:48-146`).

### Frontend states

| State | Meaning |
|-------|---------|
| `idle` | Ready to start. |
| `starting` | `getUserMedia`/`MediaRecorder` setup in progress. |
| `recording` | Microphone stream active and recorder started. |
| `stopping` | `stop()` called; waiting for recorder `onstop`. |
| `transcribing` | Audio blob sent to `/api/transcribe`. |
| `error` | User-visible error; recorder resources released. |
| `setup_modal` | Missing `GROQ_API_KEY` modal shown. |

Frontend invariants after the fix: each recording session owns its stream and
chunks locally; `starting`/`stopping` are guarded by refs and disabled states;
any failure after `getUserMedia` stops tracks immediately; `onstop` stops only
its own stream (`frontend/src/components/VoiceButton.jsx:36-168`).

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| `idle` | click start | `starting` | duplicate starts ignored |
| `starting` | stream+recorder ready | `recording` | refs stored, recorder started |
| `starting` | getUserMedia/MediaRecorder failure | `error` | acquired tracks stopped in `catch` |
| `recording` | click stop | `stopping` -> `transcribing`/`error` | recorder `onstop` owns cleanup |
| `stopping` | empty chunks | `error` | "No audio recorded" |
| `transcribing` | API success | `idle` with text appended | transcription text added to composer |
| `transcribing` | API failure | `error` or `setup_modal` | backend retry policy already applied |
| any active | component unmount | resources released | stream tracks stopped, handlers detached |

### Evidence

- Backend retry policy: `backend/transcription.py:100-146`.
- Frontend guards/local session: `frontend/src/components/VoiceButton.jsx`.

## 7. Frontend session restore and draft mode

### States

| State | Meaning |
|-------|---------|
| `fresh_draft` | First load in this browser session; no conversation selected. |
| `restoring` | Refresh detected; fetching `lastConversationId`. |
| `persisted_selected` | A backend conversation is selected and loaded. |
| `draft_after_reset` | User started new chat or all conversations were cleared/deleted. |

### Invariants

- `sessionStorage.appLoaded` distinguishes fresh load from refresh.
- `localStorage.lastConversationId` is written only for a persisted, non-draft
  selection (`frontend/src/App.jsx:135-140`).
- Restore failure falls back to draft so the composer never points at a missing
  conversation (`frontend/src/App.jsx:111-133`).
- Draft config is separate from persisted conversation config until the first
  message creates the conversation (`frontend/src/App.jsx:281-317`).

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| none | first app load | `fresh_draft` | `appLoaded` set |
| refresh with saved id | mount restore succeeds | `persisted_selected` | conversation id restored |
| refresh with saved id | mount restore fails | `draft_after_reset` | fallback draft |
| `persisted_selected` | New Conversation | `draft_after_reset` | message mode reset |
| `draft_after_reset` | first send | `persisted_selected` | conversation created with draft/global config |
| `persisted_selected` | delete current, others remain | `persisted_selected` | select first remaining |
| `persisted_selected` | delete current, none remain / clear all | `draft_after_reset` | list and localStorage updated |

### Evidence

- Restore/draft state: `frontend/src/App.jsx:16-45`, `105-166`, `281-317`.

## 8. Frontend SSE event application

### States

| State | Meaning |
|-------|---------|
| `idle` | No generation tracked by the UI. |
| `sending` | `handleSendMessage` is creating/streaming a response. |
| `stage_loading` | Optimistic assistant message has `loading.stageN == true`. |
| `stage_data` | Stage payload/errors merged into the optimistic assistant message. |
| `complete` | Terminal `complete` event received; list refreshed and active id cleared. |
| `error` | Terminal `error` event or stream exception; conversation reloaded if visible. |
| `background_unknown` | Stream ended without terminal event; UI clears active id and reloads, while the detached backend worker may still be running. |

### Invariants

- Only one UI-tracked generation is allowed at a time
  (`activeGenerationConversationId`).
- Events update only the current conversation's last assistant message through
  `updateCurrentAssistantMessage`.
- `complete`/`error` are terminal for the UI stream; unknown events are logged.
- If the stream terminates without a terminal event, the UI performs a sync and
  clears `activeGenerationConversationId` (`frontend/src/App.jsx:528-548`).

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| `idle` | send accepted | `sending` | active id set before optimistic messages |
| `sending` | `stage1_start`/`stage2_start`/`stage3_start` | `stage_loading` | loading flag updated |
| `stage_loading` | matching `*_complete` | `stage_data` | payload, errors, metadata merged |
| `stage_data` | `complete` | `complete` -> `idle` | conversations reload; visible conversation syncs |
| any sending state | `error` event/exception | `error` -> `idle` | visible conversation reloads from backend |
| any sending state | stream ends without terminal | `background_unknown` -> `idle` | UI syncs; backend may still hold `active_generations` |

### Evidence

- Event handlers and terminal cleanup: `frontend/src/App.jsx:343-548`.
- SSE parser: `frontend/src/api.js:270-324`, `471-486`.

## 9. Composer, attachment, and configuration locks

### States

| Surface | States |
|---------|--------|
| Conversation selection | `fresh_draft`, `restoring`, `persisted_selected`, `draft_after_reset` |
| Send admission | unlocked, blocked by current generation, blocked by other generation, blocked by mutation, blocked by upload |
| Attachment | `none`, `uploading`, `ready`, `error` |
| Config modal | closed, loading, editing, saving, error |
| Voice recorder | idle, starting, recording, stopping, transcribing, error, setup modal |

### Invariants

- `isLocked = isLoading || isUploadingAttachment || isSendLocked ||
  isMutatingConversations` (`frontend/src/components/ChatInterface.jsx:147`).
- Send submission checks the same conditions plus non-empty content
  (`ChatInterface.jsx:108-122`).
- Conversation deletion/clear sets `isMutatingConversations` in `App.jsx` and now
  locks the composer while the API call is in flight.
- Config edits are scoped to draft, new conversation, or persisted conversation;
  "Set as default" may also update global config for eligible scopes.

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| composer unlocked | select file | `uploading` | client-side type/size validation first |
| `uploading` | ingest succeeds | `ready` | payload stored in React state only |
| `uploading` | ingest fails | `error` | previous attachment restored |
| composer unlocked | open config | config loading/editing | per-conversation or draft/global config loaded |
| config editing | save succeeds | closed | draft state or conversation/global config updated |
| any composer state | generation starts in this conversation | send locked | textarea still allows drafting, submit blocked |
| any composer state | generation starts elsewhere | send locked externally | user can draft but not send |
| any composer state | delete/clear starts | mutation locked | send/attach/config/voice disabled until API settles |

### Evidence

- Lock derivation and submit guard: `frontend/src/components/ChatInterface.jsx`.
- Mutation state: `frontend/src/App.jsx:192-245`, prop passed at `574-585`.

## 10. Stage tab selection

### States

| Component | State |
|-----------|-------|
| `Stage1` | `activeTab` requested index, `isCollapsed` bool, derived `activeIndex` |
| `Stage2` | `activeTab` requested index, `isCollapsed` bool, derived `activeIndex` |

### Invariants

- Rendering must never index past the current `responses`/`rankings` array.
- `activeIndex = min(activeTab, length - 1)` keeps the UI on the last valid tab
  when a preserved React state outlives a shorter result set
  (`Stage1.jsx:18`, `Stage2.jsx:33`).

### Transition table

| From | Event | To | Guard / effect |
|------|-------|----|----------------|
| any | click tab `i` | requested `activeTab = i` | only rendered when `0 <= i < length` |
| any | result set shrinks below `activeTab` | derived `activeIndex = length - 1` | no out-of-range render |
| any | collapse toggle | `isCollapsed` flips | tab content hidden/shown |

### Evidence

- Clamp: `frontend/src/components/Stage1.jsx:16-18`, `Stage2.jsx:31-33`.

## Confirmed defects and fixes

| Priority | Issue | Defect | Evidence | Fix | Regression |
|----------|-------|--------|----------|-----|------------|
| P1 | [#178](https://github.com/eddiefleurent/llm-council/issues/178) | Stage tab state could survive a conversation switch and index past the new conversation's shorter Stage 1/Stage 2 arrays, crashing React. | `ChatInterface` uses `key={index}` for message groups; `Stage1`/`Stage2` kept unclamped `activeTab`. | Clamp derived `activeIndex` to the current array length. | `frontend/tests/e2e/stage-tabs.spec.js` |
| P1 | [#179](https://github.com/eddiefleurent/llm-council/issues/179) | Conversation deletion could race generation because delete endpoints ignored `active_generations`, and send admission checked existence before the lock. Detached workers made this reachable after client disconnect too. | `main.py` delete routes had no guard; send/stream fetched conversation before `generations_lock`; frontend composer stayed enabled during mutation calls. | Delete endpoints now reject active generations with 409; send/stream re-check existence inside the lock; composer locks during `isMutatingConversations`. | `tests/integration/test_council_routes.py`; `frontend/tests/e2e/conversation-mutations.spec.js` |
| P2 | [#180](https://github.com/eddiefleurent/llm-council/issues/180) | Voice recorder could leak microphone tracks after post-`getUserMedia` setup failure and could mix sessions across rapid start/stop because stream/chunks were shared refs and starting/stopping were not states. | `VoiceButton.jsx` stored `streamRef` before `MediaRecorder` construction and had no starting/stopping guards. | Recorder sessions now own stream/chunks locally; starting/stopping refs disable overlapping transitions; failures stop tracks immediately. | `frontend/tests/e2e/voice.spec.js` |

## Watch items

| Priority | Area | Observation | Why not fixed here |
|----------|------|-------------|--------------------|
| P3 | SSE disconnect | UI clears `activeGenerationConversationId` when the stream ends without a terminal event, but the detached backend worker may still hold the generation lock. A subsequent send can get a backend 409 until the worker finishes; deletion is now safely rejected. | There is no generation-status endpoint to distinguish "worker finished while disconnected" from "still running"; choosing one UI behavior trades off stuck-spinners vs premature unlocks. |
| P3 | Checkpoint unexpected exceptions | `run_full_council` catches `TimeoutError` and persists `failed`; other unexpected exceptions can leave the last persisted status as `running` if they escape stage collectors/storage. Model-call failures are normally converted to structured errors before this point. | Requires deciding whether all unexpected pipeline exceptions should become resumable failed checkpoints vs HTTP 500s; stage collectors already isolate model failures. |
| P3 | Conversation creation atomicity | `create_conversation` writes JSON directly while later updates use atomic replace. A crash exactly during create could leave a torn file. | Low likelihood and no concurrency path; can be aligned with `save_conversation` separately. |
| P3 | Clear-all partial failures | `storage.delete_all_conversations` returns per-file failures, but the endpoint ignores the return value. | Orthogonal to state-machine admission; should be handled as an API error-reporting change. |

## Verification commands

Backend:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```

Frontend:

```bash
cd frontend
pnpm test
pnpm test:e2e
```
