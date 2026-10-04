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
 * All model IDs were validated against the OpenRouter API on 2026-10-04.
 */
export const MODEL_PRESETS = [
  {
    id: 'flagship',
    name: 'Flagship',
    description: 'Top-tier models for maximum quality',
    icon: '⭐',
    council_models: [
      'anthropic/claude-opus-5.5',
      'openai/gpt-6-astra',
      'google/gemini-3.1-pro-preview',
      'x-ai/grok-4.7',
    ],
    chairman_model: 'anthropic/claude-opus-5.5',
  },
  {
    id: 'balanced',
    name: 'Balanced',
    description: 'Great quality at reasonable cost',
    icon: '⚖️',
    council_models: [
      'anthropic/claude-sonnet-5.5',
      'openai/gpt-6.1-sol',
      'google/gemini-3.8-flash',
      'x-ai/grok-4.7',
      'moonshotai/kimi-k3',
    ],
    chairman_model: 'google/gemini-3.1-pro-preview',
  },
  {
    id: 'budget',
    name: 'Budget',
    description: 'Cost-effective models for everyday use',
    icon: '💰',
    council_models: [
      'anthropic/claude-haiku-4.5',
      'z-ai/glm-5.3-flash',
      'moonshotai/kimi-k3',
      'google/gemini-3.8-flash',
      'minimax/minimax-m3',
      'nvidia/nemotron-3-ultra-550b-a55b',
    ],
    chairman_model: 'google/gemini-3.8-flash',
  },
  {
    id: 'large-council',
    name: 'Large Council',
    description: 'Seven diverse models for broad consensus',
    icon: '🏛️',
    council_models: [
      'anthropic/claude-sonnet-5.5',
      'openai/gpt-6-astra',
      'google/gemini-3.8-flash',
      'x-ai/grok-4.7',
      'moonshotai/kimi-k3',
      'z-ai/glm-5.3',
      'nvidia/nemotron-3-ultra-550b-a55b',
    ],
    chairman_model: 'google/gemini-3.1-pro-preview',
  },
  {
    id: 'speed',
    name: 'Speed',
    description: 'Fastest responses with lightweight models',
    icon: '⚡',
    council_models: [
      'anthropic/claude-haiku-4.5',
      'openai/gpt-6-luna',
      'google/gemini-3.5-flash-lite',
    ],
    chairman_model: 'google/gemini-3.5-flash-lite',
  },
];
