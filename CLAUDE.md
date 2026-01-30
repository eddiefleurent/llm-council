# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 3-stage deliberation system where multiple LLMs collaboratively answer user questions. The key innovation is anonymized peer review in Stage 2, preventing models from playing favorites.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `DEFAULT_COUNCIL_MODELS` and `DEFAULT_CHAIRMAN_MODEL` as fallback defaults
- Legacy aliases `COUNCIL_MODELS` and `CHAIRMAN_MODEL` maintained for compatibility
- Uses environment variable `OPENROUTER_API_KEY` from `.env`
- **Validates API key at startup** - fails fast with clear error message
- `get_council_config()`: Returns current council config (from file or defaults)
- `save_council_config()`: Persists council config to `data/council_config.json`
- `get_effective_models()`: Returns models with `:online` suffix if web search enabled
- `apply_online_variant()`: Helper to append `:online` to model IDs
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`models.py`** - OpenRouter Model Discovery
- `fetch_models_from_openrouter()`: Fetches all available models from OpenRouter API
- `get_available_models()`: Returns cached models (5-minute TTL)
- `get_models_grouped_by_provider()`: Groups models by provider for UI
- `PRIORITY_PROVIDERS`: Top providers shown first (OpenAI, Anthropic, Google, xAI, etc.)
- `PROVIDER_DISPLAY_NAMES`: Human-readable provider names
- `validate_model_ids()`: Validates model IDs exist in OpenRouter

**`openrouter.py`**
- `query_model()`: Single async model query
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`
- Returns dict with 'content' and optional 'reasoning_details'
- **`ModelQueryError` dataclass**: Structured error info (type, message, status_code, model)
- **`is_error()` helper**: Check if response is an error
- Handles specific HTTP errors: 401 (auth), 402 (payment), 404 (not found), 429 (rate limit), 5xx (server)

**`council.py`** - The Core Logic
- `stage1_collect_responses(messages, council_models=None)`: Parallel queries to all council models
  - Accepts `messages` list for conversation context
  - Optional `council_models` parameter (defaults to configured)
  - Returns tuple: (results, errors)
- `stage2_collect_rankings(user_query, stage1_results, council_models=None)`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Optional `council_models` parameter
  - Returns tuple: (rankings_list, label_to_model_dict, errors)
- `stage3_synthesize_final(user_query, stage1_results, stage2_results, chairman_model=None)`:
  - Chairman synthesizes from all responses + rankings
  - Optional `chairman_model` parameter
  - Returns tuple: (result, errors)
- `run_full_council(messages, council_models=None, chairman_model=None, web_search_enabled=None)`: Full orchestration
  - Now accepts optional model parameters and web search flag
  - Metadata now includes `council_models`, `chairman_model`, and `web_search_enabled` used
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section
- `calculate_aggregate_rankings()`: Mean position averaging
- **`calculate_tournament_rankings()`**: Pairwise comparison (Condorcet voting) - more robust to outliers
- `generate_conversation_title(user_query, chairman_model=None)`: Uses configurable chairman

**`context.py`** - Multi-turn Conversation Support
- `build_context_messages()`: Builds message history with smart summarization
- `summarize_older_messages()`: Summarizes old messages for long conversations
- `format_assistant_message()`: Extracts stage3 response for context
- Keeps last 5 exchanges verbatim, summarizes older ones

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, title, messages[]}`
- Messages now include optional `errors` field: `{stage1: [], stage2: [], stage3: []}`
- `add_assistant_message()`: Accepts optional `errors` parameter for persistence
- `delete_all_conversations()`: Clear all history

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- POST `/api/conversations/{id}/message` returns metadata in addition to stages
- DELETE `/api/conversations` clears all conversations
- Metadata includes: label_to_model, aggregate_rankings, tournament_rankings, council_models, chairman_model, web_search_enabled, errors

**Model Discovery Endpoints:**
- GET `/api/models` - List all models grouped by provider
- GET `/api/models/{provider_id}` - List models for a specific provider
- POST `/api/models/refresh` - Force refresh the models cache

**Council Configuration Endpoints:**
- GET `/api/council/config` - Get current config (with defaults)
- PUT `/api/council/config` - Update council models, chairman, and web search setting
- POST `/api/council/config/reset` - Reset to defaults

### Frontend Structure (`frontend/src/`)

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- **Draft mode**: Conversations created on first message (prevents empty convos)
- **Clear history**: Deletes all conversations with confirmation
- Handles message sending and metadata storage

**`api.js`**
- `deleteAllConversations()`: API call to clear history
- `getModels()`: Fetch all models grouped by provider
- `getModelsForProvider(providerId)`: Get models for specific provider
- `refreshModels()`: Force refresh models cache
- `getCouncilConfig()`: Get current council configuration
- `updateCouncilConfig(councilModels, chairmanModel, webSearchEnabled)`: Update configuration
- `resetCouncilConfig()`: Reset to defaults

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
- **Config button**: Opens council configuration panel (gear icon)

**`components/CouncilConfig.jsx`**
- Modal panel for configuring council models and chairman
- Shows current config with model chips (color-coded by provider)
- Add/remove council members
- Select chairman model
- **Web Search toggle**: Enable/disable `:online` variant for real-time web search
- Reset to defaults button
- Validates configuration before saving

**`components/ModelSelector.jsx`**
- Two-step model selection: providers → models
- Priority providers shown first (OpenAI, Anthropic, Google, xAI)
- Models sorted by creation date (newest first)
- Shows context length and selection status
- Dark-themed overlay matching screenshot design

**`components/Stage1.jsx`**
- Tab view of individual model responses
- Copy button for each response
- Uses `getModelDisplayName()` for safe model name display
- **Error display**: Shows failed models in warning section with error details
- Model count in title: "[X queried, Y successful, Z failed]"

**`components/Stage2.jsx`**
- Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display
- Shows "Extracted Ranking" below each evaluation
- Aggregate rankings shown with average position and vote count
- Uses `getModelDisplayName()` for safe model name display
- **Error display**: Shows failed models in warning section with error details
- Model count in title: "[X queried, Y successful, Z failed]"

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

### Dynamic Model Configuration
- Council models and chairman are now configurable via UI
- Defaults maintained in `config.py` for backward compatibility
- Config persisted to `data/council_config.json`
- Models auto-discovered from OpenRouter API with 5-minute cache
- Priority providers (OpenAI, Anthropic, Google, xAI) shown first in UI
- Validation ensures selected models exist before saving

### Web Search (`:online` variant)
- Enabled via toggle in Council Configuration UI
- When enabled, `:online` suffix is appended to all model IDs
- Uses OpenRouter's built-in web search plugin
- Provides real-time information access beyond model training data
- Applied at query time via `get_effective_models()` - base model IDs stored in config
- See: [OpenRouter :online variant docs](https://openrouter.ai/docs/guides/routing/model-variants/online)

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
- **Error persistence**: Errors are now saved to conversation files alongside stages
- **Error visibility**: Failed models displayed in UI with error type/message
  - Stage 1/2 show warning sections: "⚠ Failed Models: model-name - error-type"
  - Error types: timeout, rate_limit, auth, payment, not_found, server, unknown
  - Visual count in stage titles: "[3 models queried, 2 successful, 1 failed]"

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

### Frontend Quality Commands
- **Lint all files**: `npm run lint` (from `frontend/` directory)
- **Lint specific file**: `npx eslint src/components/ModelSelector.jsx`
- **Auto-fix issues**: `npm run lint -- --fix` (only fixes auto-fixable issues like whitespace)
- **Build frontend**: `npm run build` - Vite builds to `dist/`
- **Note**: Unused variables (unused state, catch parameters) must be manually removed - ESLint `--fix` doesn't handle these
- **ModelSelector behavior**: Loads providers fresh on each modal open (no caching) - uses `useEffect` dependency on `isOpen`

## Common Gotchas

1. **Module Import Errors**: Run backend as `python -m backend.main` from project root
2. **CORS Issues**: Frontend must match allowed origins in `main.py`
3. **Ranking Parse Failures**: Fallback regex extracts any "Response X" patterns
4. **Metadata Persistence**: Rankings metadata (label_to_model, aggregate_rankings, tournament_rankings) is ephemeral (not persisted), only in API responses. Errors ARE persisted in conversation files for debugging.
5. **Model as Array**: Some APIs return model as array - use `getModelDisplayName()`

## Data Flow Summary

```text
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

## Git Workflow

### Creating Pull Requests
This repo is a personal fork maintained by the user. When creating PRs:
- Always push to `origin` (the user's fork: `eddiefleurent/llm-council`)
- Create PRs to `main` branch of the **same fork** (NOT upstream)
- **IMPORTANT**: Use `--repo eddiefleurent/llm-council --base main` to avoid creating PRs on upstream

Example workflow:
```bash
git checkout -b feature/my-feature
# ... make changes ...
git add -A && git commit -m "feat: description"
git push -u origin HEAD
gh pr create --repo eddiefleurent/llm-council --base main --title "feat: description" --body "## Summary\n- Change 1\n- Change 2"
```

**Note**: Without `--repo`, `gh pr create` defaults to the upstream repo (karpathy/llm-council) which is NOT what we want.
