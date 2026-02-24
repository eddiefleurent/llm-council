import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import CopyButton from './CopyButton';
import VoiceButton from './VoiceButton';
import CouncilConfig from './CouncilConfig';
import { api } from '../api';
import { getModelDisplayName } from '../utils';
import './ChatInterface.css';

const MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024;
const SUPPORTED_ATTACHMENT_EXTENSIONS = ['txt', 'md', 'pdf', 'json', 'csv'];
const ATTACHMENT_ACCEPT = SUPPORTED_ATTACHMENT_EXTENSIONS.map((extension) => `.${extension}`).join(',');

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  messageMode,
  onSetMessageMode,
  onToggleSidebar,
  isDraftMode = false,
  draftConfig = null,
  onDraftConfigChange,
}) {
  const [input, setInput] = useState('');
  const [showConfig, setShowConfig] = useState(false);
  const [attachment, setAttachment] = useState(null);
  const [attachmentError, setAttachmentError] = useState('');
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const [conversationConfig, setConversationConfig] = useState(null);
  const [loadingConfig, setLoadingConfig] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const hasInlineLoading = conversation?.messages?.some(
    (msg) => msg.role === 'assistant' && msg.loading && Object.values(msg.loading).some(Boolean)
  );

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const loadConversationConfig = useCallback(async () => {
    if (!conversation?.id) return;

    // Clear stale config before loading
    setConversationConfig(null);
    setLoadingConfig(true);
    try {
      const config = await api.getConversationConfig(conversation.id);
      setConversationConfig(config);
    } catch (error) {
      console.error('Failed to load conversation config:', error);
      setConversationConfig(null); // Clear on error
    } finally {
      setLoadingConfig(false);
    }
  }, [conversation?.id]);

  const loadGlobalConfigForDraft = useCallback(async () => {
    // Clear stale config before loading
    setConversationConfig(null);
    setLoadingConfig(true);
    try {
      const config = await api.getCouncilConfig();
      setConversationConfig({
        council_models: config.council_models,
        chairman_model: config.chairman_model,
        web_search_enabled: config.web_search_enabled,
      });
    } catch (error) {
      console.error('Failed to load global config:', error);
      setConversationConfig(null); // Clear on error
    } finally {
      setLoadingConfig(false);
    }
  }, []);

  // Load conversation config when conversation changes
  useEffect(() => {
    if (conversation?.id) {
      loadConversationConfig();
    } else if (isDraftMode && draftConfig) {
      // Use draft config for display
      setConversationConfig(draftConfig);
    } else if (isDraftMode) {
      // Load global config for draft mode
      loadGlobalConfigForDraft();
    } else {
      setConversationConfig(null);
    }
  }, [conversation?.id, isDraftMode, draftConfig, loadConversationConfig, loadGlobalConfigForDraft]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if ((input.trim() || attachment) && !isLoading && !isUploadingAttachment) {
      onSendMessage(input, attachment);
      setInput('');
      setAttachment(null);
      setAttachmentError('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      // Reset height after sending
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  // Handle voice transcription - append to current input
  const handleTranscription = useCallback((text) => {
    setInput((prev) => {
      // If there's existing text, add a space before the new text
      if (prev.trim()) {
        return prev + ' ' + text;
      }
      return text;
    });
  }, []);

  const validateAttachmentFile = (file) => {
    const extension = file.name.split('.').pop()?.toLowerCase() || '';
    if (!SUPPORTED_ATTACHMENT_EXTENSIONS.includes(extension)) {
      throw new Error(
        `Unsupported file type. Supported types: ${SUPPORTED_ATTACHMENT_EXTENSIONS.join(', ')}.`
      );
    }
    if (file.size > MAX_ATTACHMENT_SIZE_BYTES) {
      throw new Error('File is too large (max 5MB).');
    }
  };

  const handleAttachmentSelect = async (event) => {
    const inputEl = event.target;
    const file = inputEl.files?.[0];
    if (!file) return;

    try {
      setAttachmentError('');
      validateAttachmentFile(file);
      setIsUploadingAttachment(true);
      const extracted = await api.extractFileContent(file);
      setAttachment(extracted);
    } catch (error) {
      setAttachment(null);
      setAttachmentError(error.message || 'Failed to process attachment.');
    } finally {
      setIsUploadingAttachment(false);
      inputEl.value = '';
    }
  };

  const removeAttachment = () => {
    setAttachment(null);
    setAttachmentError('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="mobile-header">
          <button
            className="hamburger-btn"
            onClick={onToggleSidebar}
            aria-label="Toggle sidebar"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12"></line>
              <line x1="3" y1="6" x2="21" y2="6"></line>
              <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
          </button>
          <h1>LLM Council</h1>
        </div>
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="mobile-header">
        <button
          className="hamburger-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </button>
        <h1>LLM Council</h1>
      </div>
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          <>
            {conversation.messages.length > 6 && (
              <div className="context-indicator">
                💭 Using conversation context ({conversation.messages.length} messages)
              </div>
            )}
            {conversation.messages.map((msg, index) => (
              <div key={index} className="message-group">
                {msg.role === 'user' ? (
                  <div className="user-message">
                    <div className="message-label">You</div>
                    <div className="message-content">
                      <div className="markdown-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                      </div>
                      {msg.attachment && (
                        <div className="attachment-indicator">
                          Attached: {msg.attachment.filename}
                        </div>
                      )}
                    </div>
                    <CopyButton
                      text={msg.content}
                      label="Copy message"
                    />
                  </div>
                ) : msg.mode === 'chairman' ? (
                  <div className="assistant-message chairman-direct">
                    <div className="message-label">Chairman Direct</div>

                    {/* Chairman loading */}
                    {msg.loading?.chairman && (
                      <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Chairman is responding...</span>
                      </div>
                    )}

                    {/* Chairman response (reuse Stage3 component) */}
                    {msg.stage3 && <Stage3 finalResponse={msg.stage3} chairmanOnly />}
                  </div>
                ) : (
                  <div className="assistant-message">
                    <div className="message-label">LLM Council</div>

                    {/* Stage 1 */}
                    {msg.loading?.stage1 && (
                      <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Running Stage 1: Collecting individual responses...</span>
                      </div>
                    )}
                    {msg.stage1 && <Stage1 responses={msg.stage1} errors={msg.errors?.stage1} />}

                    {/* Stage 2 */}
                    {msg.loading?.stage2 && (
                      <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Running Stage 2: Peer rankings...</span>
                      </div>
                    )}
                    {msg.stage2 && (
                      <Stage2
                        rankings={msg.stage2}
                        labelToModel={msg.metadata?.label_to_model}
                        aggregateRankings={msg.metadata?.aggregate_rankings}
                        errors={msg.errors?.stage2}
                      />
                    )}

                    {/* Stage 3 */}
                    {msg.loading?.stage3 && (
                      <div className="stage-loading">
                        <div className="spinner"></div>
                        <span>Running Stage 3: Final synthesis...</span>
                      </div>
                    )}
                    {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                  </div>
                )}
              </div>
            ))}
          </>
        )}

        {isLoading && !hasInlineLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>{messageMode === 'chairman' ? 'Chairman is responding...' : 'Consulting the council...'}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <div className="input-header">
          <div className="mode-toggle">
            <button
              type="button"
              className={`mode-button ${messageMode === 'council' ? 'active' : ''}`}
              onClick={() => onSetMessageMode('council')}
              disabled={isLoading}
              title="Full council deliberation (all 3 stages)"
            >
              Council
            </button>
            <button
              type="button"
              className={`mode-button ${messageMode === 'chairman' ? 'active' : ''}`}
              onClick={() => onSetMessageMode('chairman')}
              disabled={isLoading}
              title="Chat directly with the chairman model"
            >
              Chairman
            </button>
          </div>
          <button
            type="button"
            className="config-btn-chat"
            onClick={() => setShowConfig(true)}
            disabled={isLoading}
            title="Configure models for this conversation"
            aria-label="Configure models"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>
        </div>
        <div className="input-row">
          <div className="input-main">
            <textarea
              className="message-input"
              placeholder={
                messageMode === 'chairman'
                  ? "Chat with the chairman... (Shift+Enter for new line, Enter to send)"
                  : conversation.messages.length === 0
                    ? "Ask your question... (Shift+Enter for new line, Enter to send)"
                    : "Ask a follow-up question... (Shift+Enter for new line, Enter to send)"
              }
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              rows={1}
            />
            {attachment && (
              <div className="attachment-chip">
                <span className="attachment-name">{attachment.filename}</span>
                <button
                  type="button"
                  className="attachment-remove"
                  onClick={removeAttachment}
                  disabled={isLoading || isUploadingAttachment}
                  aria-label="Remove attachment"
                >
                  Remove
                </button>
              </div>
            )}
            {isUploadingAttachment && (
              <div className="attachment-status">Processing attachment...</div>
            )}
            {attachmentError && (
              <div className="attachment-error">{attachmentError}</div>
            )}
            {conversationConfig && !loadingConfig && (
              <div className="model-indicator">
                <span className="indicator-label">
                  {conversationConfig.web_search_enabled && '🌐 '}
                  Council: {conversationConfig.council_models.length} models
                </span>
                <span className="indicator-separator">•</span>
                <span className="indicator-label">
                  Chairman: {getModelDisplayName(conversationConfig.chairman_model)}
                </span>
              </div>
            )}
          </div>
          <div className="input-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept={ATTACHMENT_ACCEPT}
              onChange={handleAttachmentSelect}
              style={{ display: 'none' }}
            />
            <button
              type="button"
              className="attach-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || isUploadingAttachment}
            >
              Attach
            </button>
            <VoiceButton
              onTranscription={handleTranscription}
              disabled={isLoading || isUploadingAttachment}
            />
            <button
              type="submit"
              className="send-button"
              disabled={(!input.trim() && !attachment) || isLoading || isUploadingAttachment}
            >
              Send
            </button>
          </div>
        </div>
      </form>

      <CouncilConfig
        isOpen={showConfig}
        onClose={() => {
          setShowConfig(false);
          if (conversation?.id) {
            loadConversationConfig(); // Reload config after closing
          } else if (isDraftMode && !draftConfig) {
            // Only reload global config if no custom draft config exists
            loadGlobalConfigForDraft();
          }
        }}
        conversationId={conversation?.id}
        isNewConversation={conversation?.messages?.length === 0 || isDraftMode}
        isDraftMode={isDraftMode}
        draftConfig={draftConfig}
        onDraftConfigChange={onDraftConfigChange}
      />
    </div>
  );
}
