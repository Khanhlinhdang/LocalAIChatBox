import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { sendChatQuery, getChatHistory, clearChatHistory } from '../api';

function ChatPage({ user }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [useKG, setUseKG] = useState(true);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadHistory = async () => {
    try {
      const response = await getChatHistory(30);
      const history = response.data.conversations.reverse();
      const historyMessages = [];
      history.forEach((conv) => {
        historyMessages.push({
          role: 'user',
          content: conv.question,
          timestamp: conv.created_at,
        });
        historyMessages.push({
          role: 'assistant',
          content: conv.answer,
          timestamp: conv.created_at,
        });
      });
      setMessages(historyMessages);
    } catch (err) {
      console.error('Failed to load history:', err);
    }
    setHistoryLoaded(true);
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: question },
    ]);
    setLoading(true);

    try {
      const response = await sendChatQuery(question, true, useKG);
      const { answer, sources, num_sources, entities_found, graph_connections } = response.data;
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: answer,
          sources: sources,
          numSources: num_sources,
          entitiesFound: entities_found || [],
          graphConnections: graph_connections || 0,
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, an error occurred while processing your question. Please try again.',
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClearHistory = async () => {
    if (window.confirm('Are you sure you want to clear all chat history?')) {
      try {
        await clearChatHistory();
        setMessages([]);
      } catch (err) {
        console.error('Failed to clear history:', err);
      }
    }
  };

  const autoResize = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  return (
    <div className="chat-page">
      {messages.length === 0 && historyLoaded ? (
        <div className="chat-empty">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--accent)' }}>
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          <h2>Welcome, {user.full_name}!</h2>
          <p>
            Ask questions about your company's knowledge base. The Knowledge Graph enhances answers by discovering relationships across documents.
          </p>
        </div>
      ) : (
        <div className="chat-messages">
          {messages.length > 0 && (
            <div style={{ textAlign: 'center', marginBottom: 8 }}>
              <button className="btn btn-outline btn-sm" onClick={handleClearHistory}>
                Clear History
              </button>
            </div>
          )}
          {messages.map((msg, index) => (
            <div key={index} className={`chat-message ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? user.full_name[0].toUpperCase() : 'AI'}
              </div>
              <div className="message-content">
                <ReactMarkdown>{msg.content}</ReactMarkdown>

                {msg.entitiesFound && msg.entitiesFound.length > 0 && (
                  <div className="message-entities">
                    <div className="entities-header">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="3"/>
                        <circle cx="4" cy="6" r="2"/>
                        <circle cx="20" cy="6" r="2"/>
                        <circle cx="4" cy="18" r="2"/>
                        <circle cx="20" cy="18" r="2"/>
                        <line x1="6" y1="7" x2="9.5" y2="10.5"/>
                        <line x1="18" y1="7" x2="14.5" y2="10.5"/>
                        <line x1="6" y1="17" x2="9.5" y2="13.5"/>
                        <line x1="18" y1="17" x2="14.5" y2="13.5"/>
                      </svg>
                      Knowledge Graph: {msg.graphConnections} connections
                    </div>
                    <div className="entities-list">
                      {msg.entitiesFound.map((entity, i) => (
                        <span key={i} className={`entity-tag entity-type-${(entity.type || 'concept').toLowerCase()}`}>
                          {entity.name}
                          <span className="entity-type-label">{entity.type}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {msg.sources && msg.sources.length > 0 && (
                  <div className="message-sources">
                    <details>
                      <summary>Sources ({msg.numSources} documents used)</summary>
                      {msg.sources.map((source, i) => (
                        <div key={i} className="source-item">
                          {source.length > 200 ? source.substring(0, 200) + '...' : source}
                        </div>
                      ))}
                    </details>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-message assistant">
              <div className="message-avatar">AI</div>
              <div className="message-content">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      )}

      <div className="chat-input-area">
        <div className="chat-mode-toggle">
          <button
            className={`mode-btn ${useKG ? 'active' : ''}`}
            onClick={() => setUseKG(!useKG)}
            title={useKG ? 'Knowledge Graph RAG enabled - click to use Basic RAG' : 'Basic RAG mode - click to enable Knowledge Graph'}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"/>
              <circle cx="4" cy="6" r="2"/>
              <circle cx="20" cy="6" r="2"/>
              <circle cx="4" cy="18" r="2"/>
              <circle cx="20" cy="18" r="2"/>
              <line x1="6" y1="7" x2="9.5" y2="10.5"/>
              <line x1="18" y1="7" x2="14.5" y2="10.5"/>
              <line x1="6" y1="17" x2="9.5" y2="13.5"/>
              <line x1="18" y1="17" x2="14.5" y2="13.5"/>
            </svg>
            {useKG ? 'KG-RAG' : 'Basic RAG'}
          </button>
        </div>
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              autoResize(e);
            }}
            onKeyDown={handleKeyDown}
            placeholder={useKG
              ? "Ask with Knowledge Graph enhanced RAG..."
              : "Ask a question (basic RAG mode)..."
            }
            rows={1}
            disabled={loading}
          />
          <button
            className="btn-send"
            onClick={handleSend}
            disabled={!input.trim() || loading}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
