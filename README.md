# LLM Council

![llmcouncil](header.jpg)

The idea of this repo is that instead of asking a question to your favorite LLM provider (e.g. OpenAI GPT 5.1, Google Gemini 3.0 Pro, Anthropic Claude Sonnet 4.5, xAI Grok 4, eg.c), you can group them into your "LLM Council". This repo is a simple, local web app that essentially looks like ChatGPT except it uses OpenRouter to send your query to multiple LLMs, it then asks them to review and rank each other's work, and finally a Chairman LLM produces the final response.

In a bit more detail, here is what happens when you submit a query:

1. **Stage 1: First opinions**. The user query is given to all LLMs individually, and the responses are collected. The individual responses are shown in a "tab view", so that the user can inspect them all one by one.
2. **Stage 2: Review**. Each individual LLM is given the responses of the other LLMs. Under the hood, the LLM identities are anonymized so that the LLM can't play favorites when judging their outputs. The LLM is asked to rank them in accuracy and insight.
3. **Stage 3: Final response**. The designated Chairman of the LLM Council takes all of the model's responses and compiles them into a single final answer that is presented to the user.

## About This Fork

This is an actively maintained fork of [karpathy/llm-council](https://github.com/karpathy/llm-council). While the original was a weekend hack project, this fork adds production features, better UX, and ongoing improvements. See the [Changelog](#changelog) below for what's new.

The original concept by @karpathy remains brilliant: it's nice and useful to see multiple responses side by side, and the cross-opinions of all LLMs on each other's outputs provide valuable insights when evaluating model quality.

## Setup

### 1. Install Dependencies

The project uses [uv](https://docs.astral.sh/uv/) for project management.

**Backend:**
```bash
uv sync
```

**Frontend:**
```bash
cd frontend
pnpm install
cd ..
```

### 2. Configure API Key

Create a `.env` file in the project root:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
```

Get your API key at [openrouter.ai](https://openrouter.ai/). Make sure to purchase the credits you need, or sign up for automatic top up.

### 3. Configure Models (Optional)

Models are configured through the **UI** using the gear icon in the sidebar. You can:
- Add/remove council members from any OpenRouter provider
- Select the chairman model
- Enable web search (`:online` variant) for real-time information
- Models are auto-discovered from OpenRouter's API

Configuration is saved to `data/council_config.json`. Default models are defined in `backend/config.py` as fallbacks.

## Running the Application

**Option 1: Use the start script**
```bash
./start.sh
```

**Option 2: Run manually**

Terminal 1 (Backend):
```bash
uv run python -m backend.main
```

Terminal 2 (Frontend):
```bash
cd frontend
pnpm run dev
```

Then open <http://localhost:5173> in your browser.

## How Ranking Works

In **Stage 2**, council members rank each other's responses using two algorithms:

1. **Mean Position Averaging**: Each response's average position across all rankings (lower = better)
2. **Tournament-Style Pairwise (Condorcet)**: Head-to-head wins between responses (more robust to outliers)

Responses are anonymized as "Response A", "Response B", etc. to prevent bias. Models provide rankings in this format:

```text
FINAL RANKING:
1. Response C
2. Response A
3. Response B
```

Both ranking methods appear in the metadata, and the Chairman sees both when synthesizing the final answer in Stage 3.

## Changelog

Major improvements since forking from karpathy/llm-council:

- **Dynamic Model Configuration** - Configure council/chairman via UI with auto-discovery from OpenRouter
- **Web Search Toggle** - Enable `:online` variant for real-time information access
- **Multi-turn Conversations** - Full conversation context with smart summarization
- **Error Handling** - Graceful degradation when models fail, detailed error reporting
- **Tournament Rankings** - Condorcet voting algorithm alongside mean position averaging
- **Model Pricing Display** - See pricing and context limits in model selector
- **Copy to Clipboard** - One-click copy for responses across all stages
- **Context Indicator** - Visual feedback when using conversation history
- **Conversation Management** - Clear history, delete conversations, draft mode
- **Comprehensive Tests** - Unit and integration tests with pytest
- **Dark Mode** - Dark theme with toggle button, persisted via localStorage

## Tech Stack

- **Backend:** FastAPI (Python 3.10+), async httpx, OpenRouter API
- **Frontend:** React + Vite, react-markdown for rendering
- **Storage:** JSON files in `data/conversations/`
- **Package Management:** uv for Python, pnpm for JavaScript
