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
 * All model IDs were validated against the OpenRouter API on 2026-03-21.
 */
export const MODEL_PRESETS = [
  {
    id: 'flagship',
    name: 'Flagship',
    description: 'Top-tier models for maximum quality',
    icon: '⭐',
    council_models: [
      'anthropic/claude-opus-4.6',
      'openai/gpt-5.4',
      'google/gemini-3.1-pro-preview',
      'x-ai/grok-4.20-multi-agent-beta',
      'deepseek/deepseek-v3.2-speciale',
    ],
    chairman_model: 'anthropic/claude-opus-4.6',
  },
  {
    id: 'balanced',
    name: 'Balanced',
    description: 'Great quality at reasonable cost',
    icon: '⚖️',
    council_models: [
      'anthropic/claude-sonnet-4.6',
      'openai/gpt-5.4-mini',
      'google/gemini-3.1-pro-preview',
      'x-ai/grok-4.20-multi-agent-beta',
      'moonshotai/kimi-k2.5',
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
      'z-ai/glm-5',
      'moonshotai/kimi-k2.5',
      'google/gemini-3-flash-preview',
      'minimax/minimax-m2.7',
      'nvidia/nemotron-3-super-120b-a12b',
    ],
    chairman_model: 'google/gemini-3-flash-preview',
  },
  {
    id: 'large-council',
    name: 'Large Council',
    description: 'Seven diverse models for broad consensus',
    icon: '🏛️',
    council_models: [
      'anthropic/claude-sonnet-4.6',
      'openai/gpt-5.4',
      'google/gemini-3-flash-preview',
      'x-ai/grok-4.20-multi-agent-beta',
      'moonshotai/kimi-k2.5',
      'z-ai/glm-5',
      'nvidia/nemotron-3-super-120b-a12b',
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
      'openai/gpt-5.4-mini',
      'google/gemini-3.1-flash-lite-preview',
    ],
    chairman_model: 'google/gemini-3.1-flash-lite-preview',
  },
];
