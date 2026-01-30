import { useState } from 'react';
import CouncilConfig from './CouncilConfig';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onClearConversations,
  isLoading = false,
}) {
  const [showConfig, setShowConfig] = useState(false);
  const handleConversationClick = (id) => {
    // Prevent switching while a response is being generated
    if (isLoading) return;
    onSelectConversation(id);
  };

  const handleNewConversation = () => {
    // Prevent creating new conversation while a response is being generated
    if (isLoading) return;
    onNewConversation();
  };

  return (
    <>
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="header-title-row">
          <h1>LLM Council</h1>
          <button 
            type="button"
            className="config-btn"
            onClick={() => setShowConfig(true)}
            title="Configure Council"
            aria-label="Configure Council"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </button>
        </div>
        <button 
          className="new-conversation-btn" 
          onClick={handleNewConversation}
          disabled={isLoading}
          title={isLoading ? 'Please wait for the current response to complete' : ''}
        >
          + New Conversation
        </button>
        <button
          className="clear-history-btn"
          onClick={() => {
            if (typeof onClearConversations === 'function') onClearConversations();
          }}
          disabled={isLoading}
        >
          Clear History
        </button>
      </div>

      {isLoading && (
        <div className="sidebar-loading-warning">
          ⏳ Response in progress...
        </div>
      )}

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              } ${isLoading && conv.id !== currentConversationId ? 'disabled' : ''}`}
              onClick={() => handleConversationClick(conv.id)}
              title={isLoading && conv.id !== currentConversationId ? 'Please wait for the current response to complete' : ''}
            >
              <div className="conversation-title">
                {conv.title || 'New Conversation'}
              </div>
              <div className="conversation-meta">
                {conv.message_count} messages
              </div>
            </div>
          ))
        )}
      </div>
    </div>
    
    <CouncilConfig 
      isOpen={showConfig} 
      onClose={() => setShowConfig(false)} 
    />
    </>
  );
}
