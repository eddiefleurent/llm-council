import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onClearConversations,
  isLoading = false,
}) {
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
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
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
  );
}
