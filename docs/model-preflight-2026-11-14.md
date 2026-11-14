# Model preflight choices — 2026-11-14

**Status: draft for provider-source review. No shipped model IDs changed.**

The refreshed OpenRouter catalog contained 471 entries. Every ID currently used by `MODEL_PRESETS`, `DEFAULT_COUNCIL_MODELS`, and `DEFAULT_CHAIRMAN_MODEL` was present, including the rolling family aliases. **Retired configured IDs: none.** The catalog describes these aliases as redirecting to the latest model in their family, so pinning a catalog-date candidate would not improve freshness by itself.

Catalog creation dates below are discovery signals only. They do not establish a stable release, model quality, or a safe role/tier replacement. Provider release/model notes were not fetched: this run is limited to GitHub, package registries, and OpenRouter, and the relevant provider documentation hosts are outside that allowlist. OpenRouter is the sole source verified for candidate IDs, availability, dates, context, and listed prices. No provider API keys or paid completion calls were used.

## Review choices

| Provider | Latest general-purpose catalog candidate(s) | Existing preset/default treatment | Choice pending provider-source review |
| --- | --- | --- | --- |
| Anthropic | [`anthropic/claude-fable-5.2`](https://openrouter.ai/anthropic/claude-fable-5.2), 2026-11-09 | Presets use `~anthropic/claude-opus-latest`, `~anthropic/claude-sonnet-latest`, and `~anthropic/claude-haiku-latest`. | Keep the family aliases unless Fable is confirmed as stable and deliberately selected for a matching role; its listed rates are above Claude Opus Latest, and it is not a same-family replacement. Official review starting point: [Claude models](https://docs.anthropic.com/en/docs/about-claude/models). |
| xAI | [`x-ai/grok-4.7`](https://openrouter.ai/x-ai/grok-4.7), 2026-09-21 | Presets/defaults use `~x-ai/grok-latest`. | Keep the rolling alias; do not pin solely by catalog date. Official review starting point: [xAI models](https://docs.x.ai/docs/models). |
| DeepSeek | [`deepseek/deepseek-v4.1-flash-1017`](https://openrouter.ai/deepseek/deepseek-v4.1-flash-1017), 2026-10-17 | Budget uses `~deepseek/deepseek-flash-latest`; Flagship remains DeepSeek-free. | Keep the rolling Flash alias in Budget; do not add DeepSeek to Flagship. Official review starting point: [DeepSeek API docs](https://api-docs.deepseek.com/). |
| Google | [`google/gemini-4-hydrogen`](https://openrouter.ai/google/gemini-4-hydrogen), 2026-11-12 | Already used in Balanced, Budget, and Speed; Argon and Carbon are also configured. | No change; do not add it to every preset. Official review starting point: [Gemini model docs](https://ai.google.dev/gemini-api/docs/models). |
| OpenAI | [`openai/gpt-6.1-terra`](https://openrouter.ai/openai/gpt-6.1-terra) and [`openai/gpt-6.1-terra-pro`](https://openrouter.ai/openai/gpt-6.1-terra-pro), 2026-10-26 | Presets use rolling Astra, Sol, and Luna family aliases. | Treat Terra as a separate family choice, not a replacement for an existing alias; verify release status and role/tier fit first. The catalog says Pro mode can spend substantially more per request, so do not infer cost parity from the listed base rates. Official review starting point: [OpenAI models](https://platform.openai.com/docs/models). |
| Z.ai | [`z-ai/glm-5.3-prime`](https://openrouter.ai/z-ai/glm-5.3-prime), 2026-09-23; [`z-ai/glm-5.3-flashx`](https://openrouter.ai/z-ai/glm-5.3-flashx), 2026-09-18 | Presets use `~z-ai/glm-latest` and `~z-ai/glm-flash-latest`. | Prime and FlashX have different listed price tiers from the current Flash alias; do not substitute without a role-specific decision. Official review starting point: [Z.ai GLM docs](https://docs.z.ai/guides/llm). |
| MiniMax | [`minimax/minimax-m3.1-flash`](https://openrouter.ai/minimax/minimax-m3.1-flash), 2026-10-19 | Already used in Budget. | No change. Official review starting point: [MiniMax text chat docs](https://platform.minimax.io/docs/guides/text-chat). |
| MoonshotAI | [`moonshotai/kimi-k3.1-pro`](https://openrouter.ai/moonshotai/kimi-k3.1-pro), 2026-10-23 | Presets use `~moonshotai/kimi-latest`. | Keep the rolling alias pending family-level and tier review. Official review starting point: [Kimi API docs](https://platform.moonshot.ai/docs/guide/start-using-kimi-api). |
| NVIDIA | [`nvidia/nemotron-3.5-super-vl`](https://openrouter.ai/nvidia/nemotron-3.5-super-vl), 2026-10-15 | Already used in Budget; Large Council uses Nemotron 3 Ultra. | No change. The newer `nvidia/switchyard` catalog entry is a model router, not a chat model, and is excluded. Official review starting point: [Nemotron 3.5 Super VL](https://build.nvidia.com/nvidia/nemotron-3-5-super-vl). |
| Thinking Machines | [`thinkingmachines/inkling-2-small`](https://openrouter.ai/thinkingmachines/inkling-2-small), 2026-11-09 | Already used in Budget. | No change. Official review starting point: [Thinking Machines Lab](https://thinkingmachines.ai/). |

## Source and validation references

- Refetched public catalog: [OpenRouter models API](https://openrouter.ai/api/v1/models).
- All per-model OpenRouter links above identify the exact candidate IDs in the catalog.
- Official provider links above are provided for manual review only; they were not fetched in this network-restricted run and do not constitute confirmation of stable release status.

No preset/default change is proposed in this draft. If a reviewer confirms a stable candidate and its intended quality/cost/speed role from provider notes, make that narrowly scoped change and update the affected preset/default tests in a follow-up revision.
