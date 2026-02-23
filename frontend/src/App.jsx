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

  // Draft conversation config (used before conversation is created)
  const [draftConfig, setDraftConfig] = useState(null);

  // Message mode: "council" (full 3-stage) or "chairman" (direct chairman only)
  const [messageMode, setMessageMode] = useState('council');

  // Mobile sidebar state
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  // Theme state
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem('theme');
    return savedTheme || 'light';
  });

  // Apply theme to root element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prevTheme => prevTheme === 'light' ? 'dark' : 'light');
  };

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Fresh-load vs refresh detection
  useEffect(() => {
    const isRefresh = sessionStorage.getItem('appLoaded');

    if (!isRefresh) {
      // Fresh page load - start with new draft conversation
      sessionStorage.setItem('appLoaded', 'true');
      // Set draft mode directly instead of calling handleNewConversation
      setIsDraftMode(true);
      setCurrentConversationId(null);
      setCurrentConversation({
        id: null,
        created_at: new Date().toISOString(),
        title: 'New Conversation',
        messages: [],
      });
    } else {
      // Browser refresh - try to restore last conversation
      const lastId = localStorage.getItem('lastConversationId');
      if (lastId) {
        // Check if conversation still exists
        api.getConversation(lastId)
          .then(() => {
            setCurrentConversationId(lastId);
            setIsDraftMode(false);
          })
          .catch((error) => {
            console.error('Failed to restore conversation:', error);

            // Only clear state for 404 (conversation not found)
            // For network errors or 5xx errors, keep existing state
            if (error.status === 404) {
              // Conversation was deleted, start fresh
              setIsDraftMode(true);
              setCurrentConversationId(null);
              setCurrentConversation({
                id: null,
                created_at: new Date().toISOString(),
                title: 'New Conversation',
                messages: [],
              });
            } else {
              // Network error or server error - show user a message but keep state
              console.warn('Could not restore last conversation due to network/server error');
              // Fall back to draft mode for safety
              setIsDraftMode(true);
              setCurrentConversationId(null);
              setCurrentConversation({
                id: null,
                created_at: new Date().toISOString(),
                title: 'New Conversation',
                messages: [],
              });
            }
          });
      } else {
        // No last conversation, start fresh
        setIsDraftMode(true);
        setCurrentConversationId(null);
        setCurrentConversation({
          id: null,
          created_at: new Date().toISOString(),
          title: 'New Conversation',
          messages: [],
        });
      }
    }
  }, []); // Empty deps intentional - run once on mount

  // Save current conversation ID to localStorage for refresh recovery
  useEffect(() => {
    if (currentConversationId && !isDraftMode) {
      localStorage.setItem('lastConversationId', currentConversationId);
    }
  }, [currentConversationId, isDraftMode]);

  // Load conversation details when selected
  // IMPORTANT: Skip loading if isLoading is true - prevents race condition where
  // loadConversation overwrites optimistic UI state during message streaming
  useEffect(() => {
    if (currentConversationId && !isDraftMode && !isLoading) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId, isDraftMode, isLoading]);

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
    setIsSidebarOpen(false); // Close sidebar on mobile when conversation is selected
  };

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  const closeSidebar = () => {
    setIsSidebarOpen(false);
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

  const handleDeleteConversation = async (conversationId) => {
    if (isLoading) return;

    const conversationToDelete = conversations.find((conv) => conv.id === conversationId);
    const conversationTitle = conversationToDelete?.title || 'this conversation';
    if (!window.confirm(`Delete "${conversationTitle}"? This cannot be undone.`)) return;

    setIsLoading(true);
    try {
      await api.deleteConversation(conversationId);

      const remainingConversations = conversations.filter((conv) => conv.id !== conversationId);
      setConversations(remainingConversations);

      if (localStorage.getItem('lastConversationId') === conversationId) {
        localStorage.removeItem('lastConversationId');
      }

      if (currentConversationId === conversationId) {
        if (remainingConversations.length > 0) {
          setIsDraftMode(false);
          setCurrentConversationId(remainingConversations[0].id);
        } else {
          setIsDraftMode(true);
          setCurrentConversationId(null);
          setCurrentConversation({
            id: null,
            created_at: new Date().toISOString(),
            title: 'New Conversation',
            messages: [],
          });
        }
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (content) => {
    const effectiveMode = messageMode;
    setIsLoading(true);
    try {
      let conversationId = currentConversationId;

      // If in draft mode, create the conversation first
      if (isDraftMode) {
        // Use draft config if set, otherwise inherit global config
        let config = draftConfig;
        if (!config) {
          const globalConfig = await api.getCouncilConfig();
          config = {
            council_models: globalConfig.council_models,
            chairman_model: globalConfig.chairman_model,
            web_search_enabled: globalConfig.web_search_enabled,
          };
        }

        const newConv = await api.createConversation(config);
        conversationId = newConv.id;

        // Set both conversation ID and full conversation object
        setCurrentConversationId(conversationId);
        setCurrentConversation(newConv);
        setIsDraftMode(false);
        setDraftConfig(null); // Clear draft config

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

      if (effectiveMode === 'chairman') {
        // Chairman-only mode: simpler assistant message
        const assistantMessage = {
          role: 'assistant',
          mode: 'chairman',
          stage1: null,
          stage2: null,
          stage3: null,
          loading: { chairman: false },
        };

        setCurrentConversation((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
        }));

        await api.sendMessageStream(conversationId, content, (eventType, event) => {
          switch (eventType) {
            case 'chairman_start':
              setCurrentConversation((prev) => {
                const messages = prev.messages.slice(0, -1);
                const lastMsg = prev.messages[prev.messages.length - 1];
                return {
                  ...prev,
                  messages: [...messages, { ...lastMsg, loading: { chairman: true } }],
                };
              });
              break;

            case 'chairman_complete':
              setCurrentConversation((prev) => {
                const messages = prev.messages.slice(0, -1);
                const lastMsg = prev.messages[prev.messages.length - 1];
                return {
                  ...prev,
                  messages: [
                    ...messages,
                    {
                      ...lastMsg,
                      stage3: event.data,
                      errors: event.errors ? { chairman: event.errors } : undefined,
                      loading: { chairman: false },
                    },
                  ],
                };
              });
              break;

            case 'title_complete':
              // Title updated; conversations list will refresh on 'complete'
              break;

            case 'complete':
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
        }, 'chairman');
      } else {
        // Full council mode
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

        setCurrentConversation((prev) => ({
          ...prev,
          messages: [...prev.messages, assistantMessage],
        }));

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

        await api.sendMessageStream(conversationId, content, (eventType, event) => {
          switch (eventType) {
            case 'stage1_start':
              updateLastMessageLoading({ stage1: true });
              break;

            case 'stage1_complete':
              setCurrentConversation((prev) => {
                const messages = prev.messages.slice(0, -1);
                const lastMsg = prev.messages[prev.messages.length - 1];
                return {
                  ...prev,
                  messages: [
                    ...messages,
                    {
                      ...lastMsg,
                      stage1: event.data,
                      errors: {
                        ...(lastMsg.errors || {}),
                        stage1: event.errors || []
                      },
                      loading: { stage1: false, stage2: false, stage3: false }
                    }
                  ]
                };
              });
              break;

            case 'stage2_start':
              updateLastMessageLoading({ stage2: true });
              break;

            case 'stage2_complete':
              setCurrentConversation((prev) => {
                const messages = prev.messages.slice(0, -1);
                const lastMsg = prev.messages[prev.messages.length - 1];
                return {
                  ...prev,
                  messages: [
                    ...messages,
                    {
                      ...lastMsg,
                      stage2: event.data,
                      metadata: event.metadata,
                      errors: {
                        ...(lastMsg.errors || {}),
                        stage2: event.errors || []
                      },
                      loading: { stage1: false, stage2: false, stage3: false }
                    }
                  ]
                };
              });
              break;

            case 'stage3_start':
              updateLastMessageLoading({ stage3: true });
              break;

            case 'stage3_complete':
              setCurrentConversation((prev) => {
                const messages = prev.messages.slice(0, -1);
                const lastMsg = prev.messages[prev.messages.length - 1];
                return {
                  ...prev,
                  messages: [
                    ...messages,
                    {
                      ...lastMsg,
                      stage3: event.data,
                      errors: {
                        ...(lastMsg.errors || {}),
                        stage3: event.errors || []
                      },
                      loading: { stage1: false, stage2: false, stage3: false }
                    }
                  ]
                };
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
        }, 'council');
      }
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
      {/* Mobile sidebar overlay */}
      <div
        className={`sidebar-mobile-overlay ${isSidebarOpen ? 'active' : ''}`}
        onClick={closeSidebar}
      />
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onClearConversations={handleClearConversations}
        onDeleteConversation={handleDeleteConversation}
        isLoading={isLoading}
        theme={theme}
        onToggleTheme={toggleTheme}
        isMobileOpen={isSidebarOpen}
        onCloseSidebar={closeSidebar}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        messageMode={messageMode}
        onSetMessageMode={setMessageMode}
        onToggleSidebar={toggleSidebar}
        isDraftMode={isDraftMode}
        draftConfig={draftConfig}
        onDraftConfigChange={setDraftConfig}
      />
    </div>
  );
}

export default App;
