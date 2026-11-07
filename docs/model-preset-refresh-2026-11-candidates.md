# Model preset refresh preflight — 2026-11-07

## Finding

The refreshed OpenRouter catalog returned 460 models. All 17 distinct model IDs
currently in MODEL_PRESETS, DEFAULT_COUNCIL_MODELS, and DEFAULT_CHAIRMAN_MODEL
are present, so no currently configured ID is retired. The already-merged
[PR #164](https://github.com/eddiefleurent/llm-council/pull/164) contains the
latest verified-in-catalog preset/default update; this review does not undo
those choices.

Catalog creation date is only a discovery signal. I did not locate provider
release/model notes through the allowed GitHub/OpenRouter sources; first-party
provider websites outside the allowlist were not contacted. The candidates
below are therefore not treated as stable provider releases. No provider API
key or paid completion call was used.

## Choices for provider verification

| Provider | Newest general-purpose candidate in the catalog | Choice to review | Catalog observation |
| --- | --- | --- | --- |
| Anthropic | [anthropic/claude-haiku-5.5](https://openrouter.ai/models/anthropic/claude-haiku-5.5) — created 2026-10-07 | If confirmed stable, consider replacing anthropic/claude-haiku-4.5 in Budget and Speed. | Catalog labels it a Haiku 4.5 successor, with lower listed token prices and 1M context; no answer-quality claim is made. |
| xAI | [x-ai/grok-4.7](https://openrouter.ai/models/x-ai/grok-4.7) — created 2026-09-21 | Keep; it is already used across presets and factory defaults. | No newer general-purpose chat candidate found. |
| DeepSeek | [deepseek/deepseek-v4.1-flash-1017](https://openrouter.ai/models/deepseek/deepseek-v4.1-flash-1017) — created 2026-10-17 | Keep in Budget only; do not add it to Flagship. | Already configured in Budget. |
| Google | [google/gemini-4-argon](https://openrouter.ai/models/google/gemini-4-argon) — created 2026-10-13 | Keep; already used by Flagship and factory defaults. | The newer [google/gemini-omni-1.2-flash](https://openrouter.ai/models/google/gemini-omni-1.2-flash) — created 2026-11-05 — has video output and is excluded from the chat shortlist. |
| OpenAI | [openai/gpt-6.1-terra](https://openrouter.ai/models/openai/gpt-6.1-terra) and [openai/gpt-6.1-terra-pro](https://openrouter.ai/models/openai/gpt-6.1-terra-pro) — created 2026-10-26 | If confirmed stable and role-appropriate, review Terra for Balanced; do not promote Pro into a higher-cost role based on date alone. | Catalog pricing is not higher than the current GPT-6.1 Sol entry, but does not establish model quality, latency, or provider release status. |
| Z.ai | [z-ai/glm-5.3-prime](https://openrouter.ai/models/z-ai/glm-5.3-prime) — created 2026-09-23 | Premium/large-council choice only if a higher-cost tier is intended. | Do not replace the Budget GLM Flash or standard GLM model silently; catalog pricing is substantially higher. |
| MiniMax | [minimax/minimax-m3.1-flash](https://openrouter.ai/models/minimax-m3.1-flash) — created 2026-10-19 | Keep; already present in Budget. | Catalog lists lower token prices than MiniMax M3. |
| Moonshot | [moonshotai/kimi-k3.1-pro](https://openrouter.ai/models/moonshotai/kimi-k3.1-pro) — created 2026-10-23 | Keep; already present in Balanced and Large Council. | Do not infer same-tier equivalence from creation date; listed token pricing differs from Kimi K3. |
| NVIDIA | [nvidia/nemotron-3.5-lightning](https://openrouter.ai/models/nvidia/nemotron-3.5-lightning) — created 2026-08-11 | Possible Budget/Speed choice only after provider confirmation; do not replace Nemotron 3 Ultra in place. | nvidia/switchyard is a routing alias and nvidia/nemotron-3.5-super-vl is a specialized vision-language endpoint, so neither is a general-chat candidate. |

## Retired IDs and implementation status

No current preset/default ID is missing from the catalog. The 13 historical
preset IDs already asserted absent by frontend/tests/presets.test.mjs are:

- x-ai/grok-4.20-multi-agent
- x-ai/grok-4.20-multi-agent-beta
- x-ai/grok-4.1-fast
- anthropic/claude-opus-4.6
- anthropic/claude-sonnet-4.6
- openai/gpt-5.4
- openai/gpt-5.4-mini
- moonshotai/kimi-k2.5
- z-ai/glm-5
- google/gemini-3-flash-preview
- google/gemini-3.1-flash-lite-preview
- minimax/minimax-m2.7
- nvidia/nemotron-3-super-120b-a12b

No preset, factory default, or preset test assertion was changed: the current
IDs are present, and no successor was verified with provider release/model
notes within the network policy. This proposal does not claim measured answer
quality.

## Sources

- [OpenRouter public model catalog](https://openrouter.ai/api/v1/models)
- Candidate catalog detail pages are linked in the table.
- First-party provider release/model notes were not verified from the allowed
  destinations; treat each candidate as a choice pending that confirmation.
