import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import CopyButton from './CopyButton';
import VoiceButton from './VoiceButton';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  messageMode,
  onSetMessageMode,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
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

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
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

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>{messageMode === 'chairman' ? 'Chairman is responding...' : 'Consulting the council...'}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <div className="input-main">
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
        </div>
        <div className="input-actions">
          <VoiceButton
            onTranscription={handleTranscription}
            disabled={isLoading}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading}
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
