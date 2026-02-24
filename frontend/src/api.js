/**
 * API client for the LLM Council backend.
 */

// Dynamically determine API base URL:
// - Behind reverse proxy (HTTPS on port 443): Use same origin (proxy routes /api/* to backend)
// - Direct access (HTTP or explicit port): Use same hostname but port 8001
const getApiBase = () => {
  const { protocol, hostname, port } = window.location;
  
  // If we're on HTTPS with default port (443), assume reverse proxy handles /api/* routing
  // This avoids mixed-content issues when Caddy/nginx proxies both frontend and backend
  if (protocol === 'https:' && (port === '' || port === '443')) {
    return '';  // Use relative URLs - same origin
  }
  
  // Direct access (development or Docker without reverse proxy)
  const host = hostname.includes(':') && !hostname.startsWith('[') ? `[${hostname}]` : hostname;
  return `${protocol}//${host}:8001`;
};

const API_BASE = getApiBase();

export const api = {
  // ============================================================================
  // Model Discovery
  // ============================================================================
  
  /**
   * Get all available models grouped by provider.
   * Returns providers sorted with priority providers first.
   */
  async getModels() {
    const response = await fetch(`${API_BASE}/api/models`);
    if (!response.ok) {
      throw new Error('Failed to fetch models');
    }
    return response.json();
  },

  /**
   * Get models for a specific provider.
   */
  async getModelsForProvider(providerId) {
    const response = await fetch(
      `${API_BASE}/api/models/${encodeURIComponent(providerId)}`
    );
    if (!response.ok) {
      throw new Error(`Failed to fetch models for provider: ${providerId}`);
    }
    return response.json();
  },

  /**
   * Force refresh the models cache from OpenRouter.
   */
  async refreshModels() {
    const response = await fetch(`${API_BASE}/api/models/refresh`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to refresh models');
    }
    return response.json();
  },

  // ============================================================================
  // Council Configuration
  // ============================================================================

  /**
   * Get the current council configuration.
   */
  async getCouncilConfig() {
    const response = await fetch(`${API_BASE}/api/council/config`);
    if (!response.ok) {
      throw new Error('Failed to get council config');
    }
    return response.json();
  },

  /**
   * Update the council configuration.
   */
  async updateCouncilConfig(councilModels, chairmanModel, webSearchEnabled = false) {
    const response = await fetch(`${API_BASE}/api/council/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        council_models: councilModels,
        chairman_model: chairmanModel,
        web_search_enabled: webSearchEnabled,
      }),
    });
    if (!response.ok) {
      let errorMessage = 'Failed to update council config';
      try {
        const error = await response.json();
        errorMessage = error.detail || errorMessage;
      } catch {
        // If JSON parsing fails, try to get text or use status text
        try {
          errorMessage = await response.text() || response.statusText || errorMessage;
        } catch {
          errorMessage = response.statusText || errorMessage;
        }
      }
      throw new Error(errorMessage);
    }
    return response.json();
  },

  /**
   * Reset council configuration to defaults.
   */
  async resetCouncilConfig() {
    const response = await fetch(`${API_BASE}/api/council/config/reset`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error('Failed to reset council config');
    }
    return response.json();
  },

  // ============================================================================
  // Conversations
  // ============================================================================

  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   * @param {Object} config - Optional config {council_models, chairman_model, web_search_enabled}
   */
  async createConversation(config = null) {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config || {}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      const error = new Error('Failed to get conversation');
      error.status = response.status;
      throw error;
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {string} mode - "council" (full 3-stage) or "chairman" (direct chairman only)
   */
  async sendMessage(conversationId, content, mode = 'council', attachment = null) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, mode, attachment }),
      }
    );
    if (!response.ok) {
      let errorMessage = 'Failed to send message';
      try {
        const error = await response.json();
        errorMessage = error.detail || errorMessage;
      } catch {
        // Keep fallback
      }
      throw new Error(errorMessage);
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @param {string} mode - "council" (full 3-stage) or "chairman" (direct chairman only)
   * @returns {Promise<void>}
   */
  async sendMessageStream(
    conversationId,
    content,
    onEvent,
    mode = 'council',
    attachment = null
  ) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, mode, attachment }),
      }
    );

    if (!response.ok) {
      let errorMessage = 'Failed to send message';
      try {
        const error = await response.json();
        errorMessage = error.detail || errorMessage;
      } catch {
        // Keep fallback
      }
      throw new Error(errorMessage);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },
  
  /**
   * Get the configuration for a specific conversation.
   * @param {string} conversationId - The conversation ID
   * @returns {Promise<{council_models: string[], chairman_model: string, web_search_enabled: boolean}>}
   */
  async getConversationConfig(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/config`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation config');
    }
    return response.json();
  },

  /**
   * Upload an attachment and extract text content on the backend.
   */
  async extractFileContent(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/api/files/extract`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorMessage = 'Failed to process file';
      try {
        const error = await response.json();
        errorMessage = error.detail || errorMessage;
      } catch {
        // Keep fallback
      }
      throw new Error(errorMessage);
    }

    return response.json();
  },

  /**
   * Update the configuration for a specific conversation.
   * @param {string} conversationId - The conversation ID
   * @param {string[]} councilModels - List of council model IDs
   * @param {string} chairmanModel - Chairman model ID
   * @param {boolean} webSearchEnabled - Whether web search is enabled
   */
  async updateConversationConfig(conversationId, councilModels, chairmanModel, webSearchEnabled = false) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/config`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          council_models: councilModels,
          chairman_model: chairmanModel,
          web_search_enabled: webSearchEnabled,
        }),
      }
    );
    if (!response.ok) {
      let errorMessage = 'Failed to update conversation config';
      try {
        const error = await response.json();
        errorMessage = error.detail || errorMessage;
      } catch {
        try {
          errorMessage = await response.text() || response.statusText || errorMessage;
        } catch {
          errorMessage = response.statusText || errorMessage;
        }
      }
      throw new Error(errorMessage);
    }
    return response.json();
  },

  /**
   * Delete all conversations from the backend.
   * Requires confirm=true query parameter to prevent accidental deletion.
   */
  async deleteAllConversations() {
    const response = await fetch(`${API_BASE}/api/conversations?confirm=true`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete conversations');
    }
    return response.json();
  },

  /**
   * Delete a single conversation from the backend.
   * @param {string} conversationId - The conversation ID
   */
  async deleteConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      {
        method: 'DELETE',
      }
    );
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
    return response.json();
  },

  // ============================================================================
  // Voice Transcription
  // ============================================================================

  /**
   * Transcribe audio using Groq's Whisper API.
   * @param {Blob} audioBlob - The audio blob to transcribe
   * @param {string} filename - Optional filename (default: "audio.webm")
   * @returns {Promise<{text: string}>} - The transcribed text
   */
  async transcribeAudio(audioBlob, filename = 'audio.webm') {
    const formData = new FormData();
    formData.append('audio', audioBlob, filename);

    const response = await fetch(`${API_BASE}/api/transcribe`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorMessage = 'Failed to transcribe audio';
      try {
        const error = await response.json();
        errorMessage = error.detail || errorMessage;
      } catch {
        errorMessage = response.statusText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    return response.json();
  },
};
