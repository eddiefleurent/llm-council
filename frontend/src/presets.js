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
 * All model IDs were validated against the OpenRouter API on 2026-02-18.
 */
export const MODEL_PRESETS = [
  {
    id: 'flagship',
    name: 'Flagship',
    description: 'Top-tier models for maximum quality',
    icon: '⭐',
    council_models: [
      'anthropic/claude-opus-4.6',
      'openai/gpt-5.2',
      'google/gemini-3-pro-preview',
      'x-ai/grok-4',
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
      'openai/gpt-5.2-chat',
      'google/gemini-3-pro-preview',
      'x-ai/grok-4.1-fast',
      'moonshotai/kimi-k2.5',
    ],
    chairman_model: 'google/gemini-3-pro-preview',
  },
  {
    id: 'budget',
    name: 'Budget',
    description: 'Cost-effective models for everyday use',
    icon: '💰',
    council_models: [
      'anthropic/claude-haiku-4.5',
      'z-ai/glm-5',
      'deepseek/deepseek-v3.2-speciale',
      'moonshotai/kimi-k2.5',
      'google/gemini-3-flash-preview',
      'minimax/minimax-m2.5',
    ],
    chairman_model: 'deepseek/deepseek-v3.2-speciale',
  },
  {
    id: 'large-council',
    name: 'Large Council',
    description: 'Seven diverse models for broad consensus',
    icon: '🏛️',
    council_models: [
      'anthropic/claude-sonnet-4.6',
      'openai/gpt-5.2-chat',
      'google/gemini-3-flash-preview',
      'x-ai/grok-4.1-fast',
      'moonshotai/kimi-k2.5',
      'deepseek/deepseek-v3.2-speciale',
      'z-ai/glm-5',
    ],
    chairman_model: 'google/gemini-3-pro-preview',
  },
  {
    id: 'speed',
    name: 'Speed',
    description: 'Fastest responses with lightweight models',
    icon: '⚡',
    council_models: [
      'anthropic/claude-haiku-4.5',
      'openai/gpt-5.2-chat',
      'google/gemini-3-flash-preview',
    ],
    chairman_model: 'google/gemini-3-flash-preview',
  },
];
