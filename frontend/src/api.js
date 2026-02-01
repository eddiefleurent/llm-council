/**
 * API client for the LLM Council backend.
 */

const API_BASE = 'http://localhost:8001';

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
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
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
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
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
