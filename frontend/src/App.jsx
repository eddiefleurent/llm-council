import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDraftMode, setIsDraftMode] = useState(false);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId && !isDraftMode) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId, isDraftMode]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = () => {
    // Set draft mode instead of creating conversation immediately
    setIsDraftMode(true);
    setCurrentConversationId(null);
    setCurrentConversation({
      id: null,
      created_at: new Date().toISOString(),
      title: 'New Conversation',
      messages: [],
    });
  };

  const handleSelectConversation = (id) => {
    setIsDraftMode(false);
    setCurrentConversationId(id);
  };

  const handleClearConversations = async () => {
    if (!window.confirm('Clear all conversations? This cannot be undone.')) return;
    setIsLoading(true);
    try {
      await api.deleteAllConversations();
      setConversations([]);
      setCurrentConversationId(null);
      setCurrentConversation(null);
      setIsDraftMode(false);
    } catch (error) {
      console.error('Failed to clear conversations:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (content) => {
    setIsLoading(true);
    try {
      let conversationId = currentConversationId;

      // If in draft mode, create the conversation first
      if (isDraftMode) {
        const newConv = await api.createConversation();
        conversationId = newConv.id;
        setCurrentConversationId(conversationId);
        setIsDraftMode(false);

        // Update conversations list using functional updater to avoid stale state
        setConversations((prev) => [
          { id: newConv.id, created_at: newConv.created_at, title: 'New Conversation', message_count: 0 },
          ...prev,
        ]);
      }

      if (!conversationId) return;

      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Helper to immutably update the last message in a conversation
      const updateLastMessage = (updates) => {
        setCurrentConversation((prev) => {
          const messages = prev.messages.slice(0, -1);
          const lastMsg = prev.messages[prev.messages.length - 1];
          return {
            ...prev,
            messages: [
              ...messages,
              { ...lastMsg, ...updates },
            ],
          };
        });
      };

      // Helper to immutably update loading state of the last message
      const updateLastMessageLoading = (loadingUpdates) => {
        setCurrentConversation((prev) => {
          const messages = prev.messages.slice(0, -1);
          const lastMsg = prev.messages[prev.messages.length - 1];
          return {
            ...prev,
            messages: [
              ...messages,
              { ...lastMsg, loading: { ...lastMsg.loading, ...loadingUpdates } },
            ],
          };
        });
      };

      // Send message with streaming
      await api.sendMessageStream(conversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            updateLastMessageLoading({ stage1: true });
            break;

          case 'stage1_complete':
            updateLastMessage({
              stage1: event.data,
              loading: { stage1: false, stage2: false, stage3: false },
            });
            break;

          case 'stage2_start':
            updateLastMessageLoading({ stage2: true });
            break;

          case 'stage2_complete':
            updateLastMessage({
              stage2: event.data,
              metadata: event.metadata,
              loading: { stage1: false, stage2: false, stage3: false },
            });
            break;

          case 'stage3_start':
            updateLastMessageLoading({ stage3: true });
            break;

          case 'stage3_complete':
            updateLastMessage({
              stage3: event.data,
              loading: { stage1: false, stage2: false, stage3: false },
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list
            loadConversations();
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onClearConversations={handleClearConversations}
        isLoading={isLoading}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
}

export default App;
