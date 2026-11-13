/**
 * Predefined model presets for one-click council configuration.
 *
 * Each preset specifies a set of council models and a chairman model.
 * Model IDs are validated against OpenRouter at save time — if a model
 * is retired or renamed, the existing backend validation will catch it
 * with a clear error message.
 *
 * MAINTENANCE: When new model versions are released, update the IDs here.
 * Run the app and try saving each preset — backend validation will flag
 * any stale IDs immediately.
 *
 * Models with a `~provider/family-latest` alias are pinned to that alias,
 * which always redirects to the newest model in the family, so those
 * presets never need version bumps.
 *
 * All model IDs were validated against the OpenRouter API on 2026-11-13.
 */
export const MODEL_PRESETS = [
  {
    id: 'flagship',
    name: 'Flagship',
    description: 'Top-tier models for maximum quality',
    icon: '⭐',
    council_models: [
      '~anthropic/claude-opus-latest',
      '~openai/gpt-astra-latest',
      'google/gemini-4-argon',
      'google/gemini-4-carbon',
      '~x-ai/grok-latest',
    ],
    chairman_model: '~anthropic/claude-opus-latest',
  },
  {
    id: 'balanced',
    name: 'Balanced',
    description: 'Great quality at reasonable cost',
    icon: '⚖️',
    council_models: [
      '~anthropic/claude-sonnet-latest',
      '~openai/gpt-sol-latest',
      'google/gemini-4-hydrogen',
      '~x-ai/grok-latest',
      '~moonshotai/kimi-latest',
    ],
    chairman_model: 'google/gemini-4-argon',
  },
  {
    id: 'budget',
    name: 'Budget',
    description: 'Cost-effective models for everyday use',
    icon: '💰',
    council_models: [
      '~anthropic/claude-haiku-latest',
      '~z-ai/glm-flash-latest',
      '~moonshotai/kimi-latest',
      '~deepseek/deepseek-flash-latest',
      'google/gemini-4-hydrogen',
      'minimax/minimax-m3.1-flash',
      'nvidia/nemotron-3.5-super-vl',
      'thinkingmachines/inkling-2-small',
    ],
    chairman_model: 'google/gemini-4-hydrogen',
  },
  {
    id: 'large-council',
    name: 'Large Council',
    description: 'Seven diverse models for broad consensus',
    icon: '🏛️',
    council_models: [
      '~anthropic/claude-sonnet-latest',
      '~openai/gpt-astra-latest',
      'google/gemini-4-hydrogen',
      '~x-ai/grok-latest',
      '~moonshotai/kimi-latest',
      '~z-ai/glm-latest',
      'nvidia/nemotron-3-ultra-550b-a55b',
    ],
    chairman_model: 'google/gemini-4-argon',
  },
  {
    id: 'speed',
    name: 'Speed',
    description: 'Fastest responses with lightweight models',
    icon: '⚡',
    council_models: [
      '~anthropic/claude-haiku-latest',
      '~openai/gpt-luna-latest',
      'google/gemini-4-hydrogen',
    ],
    chairman_model: 'google/gemini-4-hydrogen',
  },
];
