/**
 * Shared provider color mapping for consistent UI styling.
 * Used by CouncilConfig and ModelSelector components.
 */
export const PROVIDER_COLORS = {
  openai: { bg: '#10a37f', text: '#fff' },
  anthropic: { bg: '#d4a27f', text: '#000' },
  google: { bg: '#4285f4', text: '#fff' },
  'x-ai': { bg: '#000', text: '#fff' },
  'meta-llama': { bg: '#0668e1', text: '#fff' },
  mistralai: { bg: '#f7931a', text: '#000' },
  deepseek: { bg: '#6366f1', text: '#fff' },
  cohere: { bg: '#39594d', text: '#fff' },
};

/**
 * Get the color scheme for a provider.
 * Returns a default gray color for unknown providers.
 * 
 * @param {string} providerId - The provider identifier
 * @returns {{ bg: string, text: string }} The color scheme
 */
export function getProviderColor(providerId) {
  return PROVIDER_COLORS[providerId] || { bg: '#6b7280', text: '#fff' };
}
