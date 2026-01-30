# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COUNCIL_MODELS` (list of OpenRouter model identifiers)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Uses environment variable `OPENROUTER_API_KEY` from `.env`
- **Validates API key at startup** - fails fast with clear error message
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`openrouter.py`**
- `query_model()`: Single async model query
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`
- Returns dict with 'content' and optional 'reasoning_details'
- **`ModelQueryError` dataclass**: Structured error info (type, message, status_code, model)
- **`is_error()` helper**: Check if response is an error
- Handles specific HTTP errors: 401 (auth), 402 (payment), 404 (not found), 429 (rate limit), 5xx (server)

**`council.py`** - The Core Logic
- `stage1_collect_responses()`: Parallel queries to all council models
  - Now accepts `messages` list for conversation context
  - Returns tuple: (results, errors)
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Returns tuple: (rankings_list, label_to_model_dict, errors)
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings
  - Returns tuple: (result, errors)
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section
- `calculate_aggregate_rankings()`: Mean position averaging
- **`calculate_tournament_rankings()`**: Pairwise comparison (Condorcet voting) - more robust to outliers
- `generate_conversation_title()`: Uses CHAIRMAN_MODEL (configurable)

**`context.py`** - Multi-turn Conversation Support
- `build_context_messages()`: Builds message history with smart summarization
- `summarize_older_messages()`: Summarizes old messages for long conversations
- `format_assistant_message()`: Extracts stage3 response for context
- Keeps last 5 exchanges verbatim, summarizes older ones

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, title, messages[]}`
- `delete_all_conversations()`: Clear all history

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- DELETE `/api/conversations` clears all conversations
- Metadata includes: label_to_model, aggregate_rankings, tournament_rankings, errors

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- **Draft mode**: Conversations created on first message (prevents empty convos)
- **Clear history**: Deletes all conversations with confirmation
- Handles message sending and metadata storage

**`api.js`**
- `deleteAllConversations()`: API call to clear history

**`utils.js`**
- `getModelDisplayName()`: Safely extracts model name, handles arrays/null

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable)
- Enter to send, Shift+Enter for new line
- **Always visible input form** for follow-up questions
- **Context indicator**: Shows when using conversation history (>6 messages)
- Dynamic placeholder text for follow-ups

**`components/CopyButton.jsx`**
- Copy-to-clipboard functionality with visual feedback
- Used in user messages, Stage 1, and Stage 3

**`components/Sidebar.jsx`**
- **Loading state**: Disables switching during response generation
- **Clear History button**: Red-styled, with confirmation
- Shows "Response in progress" warning

**`components/Stage1.jsx`**
- Tab view of individual model responses
- Copy button for each response
- Uses `getModelDisplayName()` for safe model name display

**`components/Stage2.jsx`**
- Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display
- Shows "Extracted Ranking" below each evaluation
- Aggregate rankings shown with average position and vote count
- Uses `getModelDisplayName()` for safe model name display

**`components/Stage3.jsx`**
- Final synthesized answer from chairman
- Green-tinted background (#f0fff0)
- Copy button for response

**Styling (`*.css`)**
- Light mode theme (not dark mode)
- Primary color: #4a90e2 (blue)
- Global markdown styling in `index.css` with `.markdown-content` class
- Text overflow fixes for long content
- Loading/disabled states for sidebar

## Key Design Decisions

### Stage 2 Prompt Format
The Stage 2 prompt is very specific to ensure parseable output:
```
1. Evaluate each response individually first
2. Provide "FINAL RANKING:" header
3. Numbered list format: "1. Response C", "2. Response A", etc.
4. No additional text after ranking section
```

### Ranking Algorithms
Two methods available in metadata:
1. **Mean Position Averaging** (`aggregate_rankings`): Simple average of positions
2. **Tournament-Style Pairwise** (`tournament_rankings`): Counts head-to-head wins, more robust to outliers

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "openai/gpt-5.1", ...}`
- Frontend displays model names in **bold** for readability
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- **Structured errors**: `ModelQueryError` with type, message, status code
- Continue with successful responses if some models fail
- Aggregate errors in metadata for debugging
- Human-readable error summaries for users

### Multi-turn Conversations
- Stage 1 receives full conversation context
- Long conversations (>10 messages) get summarized
- Recent 5 exchanges kept verbatim
- Stage 2 and 3 use current query only (ranking is per-response)

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`). Run as `python -m backend.main` from project root.

### Port Configuration
- Backend: 8001
- Frontend: 5173 (Vite default)

### Model Name Safety
Always use `getModelDisplayName()` in frontend - handles arrays, null, missing slash.

### Test Suite
- `pytest.ini` configured for async tests
- `tests/unit/` for unit tests
- `tests/integration/` for API tests
- Run with: `uv run pytest` or `pytest`

## Common Gotchas

1. **Module Import Errors**: Run backend as `python -m backend.main` from project root
2. **CORS Issues**: Frontend must match allowed origins in `main.py`
3. **Ranking Parse Failures**: Fallback regex extracts any "Response X" patterns
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only in API responses
5. **Model as Array**: Some APIs return model as array - use `getModelDisplayName()`

## Data Flow Summary

```
User Query
    ↓
Build Context (summarize if long conversation)
    ↓
Stage 1: Parallel queries with context → [responses, errors]
    ↓
Stage 2: Anonymize → Parallel ranking → [rankings, errors]
    ↓
Calculate Rankings (mean + tournament)
    ↓
Stage 3: Chairman synthesis → [result, errors]
    ↓
Return: {stage1, stage2, stage3, metadata: {rankings, errors}}
    ↓
Frontend: Display with tabs + copy buttons + validation UI
```

The entire flow is async/parallel where possible to minimize latency.
