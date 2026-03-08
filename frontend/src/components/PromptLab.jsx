import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../api';
import './PromptLab.css';

export default function PromptLab({ isOpen, onClose, onCommit, chairmanModel }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = { role: 'user', content: input };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);

    try {
      const response = await api.promptLabChat(newMessages, chairmanModel);
      setMessages([...newMessages, { role: 'assistant', content: response.content }]);
    } catch (error) {
      console.error('Prompt Lab error:', error);
      setMessages([...newMessages, { role: 'assistant', content: `Error: ${error.message}` }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCommit = () => {
    // Find the last assistant message if possible, or use the last user message
    const lastAssistantMessage = [...messages].reverse().find(m => m.role === 'assistant');
    const lastUserMessage = [...messages].reverse().find(m => m.role === 'user');

    // Default to the last user message if no assistant message is present
    const finalPrompt = lastAssistantMessage?.content || lastUserMessage?.content || '';

    if (finalPrompt) {
      onCommit(finalPrompt);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="prompt-lab-overlay" onClick={onClose}>
      <div className="prompt-lab-container" onClick={(e) => e.stopPropagation()}>
        <div className="prompt-lab-header">
          <div className="header-title">
            <span className="lab-icon">🧪</span>
            <h2>Outcome-Based Prompt Lab</h2>
          </div>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="prompt-lab-messages">
          {messages.length === 0 ? (
            <div className="lab-empty-state">
              <p>Welcome to the Prompt Lab! 🚀</p>
              <p>Tell the Chairman what you&apos;re trying to achieve, and we&apos;ll help you frame it as a clear outcome.</p>
            </div>
          ) : (
            messages.map((msg, index) => (
              <div key={index} className={`lab-message ${msg.role}`}>
                <div className="message-label">{msg.role === 'user' ? 'You' : 'Architect'}</div>
                <div className="message-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="lab-message assistant loading">
              <div className="spinner"></div>
              <span>Architect is thinking...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="prompt-lab-footer">
          <form className="lab-input-form" onSubmit={handleSend}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Refine your outcome here..."
              rows={1}
            />
            <button type="submit" className="lab-send-btn" disabled={!input.trim() || isLoading}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="m5 12 7-7 7 7" />
                <path d="M12 19V5" />
              </svg>
            </button>
          </form>
          <div className="lab-actions">
            <button
              className="commit-btn"
              onClick={handleCommit}
              disabled={messages.length === 0 || isLoading}
              title="Send the current result to the Council as an Outcome"
            >
              Commit as Outcome to Council
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
