/**
 * Utility functions for LLM Council frontend.
 */

/**
 * Extract a display-friendly model name from a model identifier.
 * Handles various edge cases: arrays, null/undefined, missing slash.
 *
 * @param {string|string[]|null|undefined} model - The model identifier
 * @returns {string} The display name (e.g., "gpt-5.1" from "openai/gpt-5.1")
 */
export function getModelDisplayName(model) {
  // Handle null/undefined
  if (!model) {
    return 'Unknown';
  }

  // Handle array (some APIs return model as array)
  if (Array.isArray(model)) {
    model = model[0];
    if (!model) {
      return 'Unknown';
    }
  }

  // Handle non-string types
  if (typeof model !== 'string') {
    return String(model);
  }

  // Extract the part after the slash, or return the whole thing
  const parts = model.split('/');
  return parts.length > 1 ? parts[1] : model;
}
