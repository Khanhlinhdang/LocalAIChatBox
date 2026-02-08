import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  sendChatQueryMultiTurn, getChatHistory, clearChatHistory,
  listChatSessions, createChatSession, getSessionMessages,
  deleteChatSession, updateChatSession, exportChat,
  lightragQuery, lightragQueryStream, lightragQueryWithContext,
  getLightRAGHealth,
} from '../api';

// LightRAG query modes
const LIGHTRAG_MODES = [
  { value: 'hybrid', label: 'Hybrid', desc: 'Best overall – local + global', icon: '🔀' },
  { value: 'local', label: 'Local', desc: 'Entity-centric search', icon: '📍' },
  { value: 'global', label: 'Global', desc: 'Community-level analysis', icon: '🌐' },
  { value: 'naive', label: 'Naive', desc: 'Simple vector search', icon: '🔍' },
  { value: 'mix', label: 'Mix', desc: 'KG + vector retrieval', icon: '🧬' },
];

function ChatPage({ user }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [useKG, setUseKG] = useState(true);
  const [useMultimodal, setUseMultimodal] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [editTitle, setEditTitle] = useState('');
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // RAG Engine toggle: 'enhanced' | 'lightrag'
  const [ragEngine, setRagEngine] = useState('enhanced');
  // LightRAG-specific settings
  const [lightragMode, setLightragMode] = useState('hybrid');
  const [lightragStreaming, setLightragStreaming] = useState(true);
  const [lightragTopK, setLightragTopK] = useState(60);
  const [lightragHealth, setLightragHealth] = useState(null);
  const [showLightragSettings, setShowLightragSettings] = useState(false);

  useEffect(() => {
    loadSessions();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Load LightRAG health when engine switches
  useEffect(() => {
    if (ragEngine === 'lightrag') {
      getLightRAGHealth().then(res => setLightragHealth(res.data)).catch(() => setLightragHealth(null));
    }
  }, [ragEngine]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadSessions = async () => {
    try {
      const response = await listChatSessions();
      setSessions(response.data.sessions || []);
    } catch (err) {
      console.error('Failed to load sessions:', err);
    }
    setHistoryLoaded(true);
  };

  const handleNewSession = async () => {
    try {
      const response = await createChatSession('New Chat');
      const newSession = response.data;
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      setMessages([]);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleSelectSession = async (sessionId) => {
    setActiveSessionId(sessionId);
    try {
      const response = await getSessionMessages(sessionId);
      const msgs = [];
      (response.data.messages || []).forEach(m => {
        msgs.push({ role: 'user', content: m.question, timestamp: m.created_at });
        msgs.push({
          role: 'assistant', content: m.answer,
          sources: m.sources_used, searchMode: m.search_mode,
          entitiesFound: m.entities_found ? JSON.parse(m.entities_found) : [],
          timestamp: m.created_at,
        });
      });
      setMessages(msgs);
    } catch (err) {
      console.error('Failed to load session:', err);
      setMessages([]);
    }
  };

  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this conversation?')) return;
    try {
      await deleteChatSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleRenameSession = async (sessionId) => {
    if (!editTitle.trim()) return;
    try {
      await updateChatSession(sessionId, editTitle);
      setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, title: editTitle } : s));
      setEditingSessionId(null);
    } catch (err) {
      console.error('Failed to rename session:', err);
    }
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    setMessages(prev => [...prev, { role: 'user', content: question }]);
    setLoading(true);

    try {
      if (ragEngine === 'lightrag') {
        // ── LightRAG engine ──
        const startTime = Date.now();
        let answerText = '';

        if (lightragStreaming) {
          await lightragQueryStream(
            question, lightragMode,
            { top_k: lightragTopK },
            (chunk) => {
              answerText += chunk;
              // Live-update the last assistant message while streaming
              setMessages(prev => {
                const last = prev[prev.length - 1];
                if (last && last.role === 'assistant' && last._streaming) {
                  return [...prev.slice(0, -1), { ...last, content: answerText }];
                }
                return [...prev, {
                  role: 'assistant', content: answerText,
                  searchMode: `lightrag:${lightragMode}`, _streaming: true,
                }];
              });
            }
          );
        } else {
          const res = await lightragQuery(question, lightragMode, { top_k: lightragTopK });
          answerText = res.data.response || res.data.result || JSON.stringify(res.data);
        }

        const duration = Date.now() - startTime;
        // Finalize the message (remove _streaming flag)
        setMessages(prev => {
          const cleaned = prev.filter(m => !m._streaming);
          return [...cleaned, {
            role: 'assistant',
            content: answerText,
            searchMode: `lightrag:${lightragMode}`,
            queryDuration: duration,
          }];
        });
      } else {
        // ── Enhanced RAG engine ──
        const response = await sendChatQueryMultiTurn(
          question, activeSessionId, useKG, useMultimodal, 'hybrid', 5, 5
        );
        const data = response.data;

        if (data.session_id && !activeSessionId) {
          setActiveSessionId(data.session_id);
          loadSessions();
        }

        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.answer,
          sources: data.sources,
          numSources: data.num_sources,
          entitiesFound: data.entities_found || [],
          graphConnections: data.graph_connections || 0,
          multimodalResults: data.multimodal_results || 0,
          searchMode: data.search_mode || 'hybrid',
        }]);
      }
    } catch (err) {
      setMessages(prev => {
        const cleaned = prev.filter(m => !m._streaming);
        return [...cleaned, {
          role: 'assistant', content: 'Sorry, an error occurred. Please try again.', error: true,
        }];
      });
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

  const handleExport = async (format) => {
    try {
      const response = await exportChat(format, activeSessionId);
      const blob = new Blob([response.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chat_export.${format === 'markdown' ? 'md' : format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  const handleClearHistory = async () => {
    if (!window.confirm('Clear all chat history?')) return;
    try {
      await clearChatHistory();
      setMessages([]);
    } catch (err) {
      console.error('Failed to clear history:', err);
    }
  };

  const autoResize = (e) => {
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  return (
    <div className="chat-page-wrapper">
      {/* Sessions Sidebar */}
      <div className={`chat-sidebar ${showSidebar ? 'open' : 'closed'}`}>
        <div className="sidebar-header">
          <h3>Conversations</h3>
          <button className="btn btn-primary btn-sm" onClick={handleNewSession}>+ New</button>
        </div>
        <div className="sessions-list">
          {sessions.map(session => (
            <div
              key={session.id}
              className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
              onClick={() => handleSelectSession(session.id)}
            >
              {editingSessionId === session.id ? (
                <input
                  value={editTitle}
                  onChange={e => setEditTitle(e.target.value)}
                  onBlur={() => handleRenameSession(session.id)}
                  onKeyDown={e => e.key === 'Enter' && handleRenameSession(session.id)}
                  autoFocus
                  className="session-rename-input"
                  onClick={e => e.stopPropagation()}
                />
              ) : (
                <>
                  <div className="session-title">{session.title}</div>
                  <div className="session-meta">
                    {session.message_count || 0} messages
                    <span className="session-date">
                      {new Date(session.updated_at || session.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="session-actions">
                    <button className="btn-icon" onClick={(e) => {
                      e.stopPropagation();
                      setEditingSessionId(session.id);
                      setEditTitle(session.title);
                    }} title="Rename">✏️</button>
                    <button className="btn-icon" onClick={(e) => handleDeleteSession(session.id, e)} title="Delete">🗑️</button>
                  </div>
                </>
              )}
            </div>
          ))}
          {sessions.length === 0 && historyLoaded && (
            <p className="sidebar-empty">No conversations yet</p>
          )}
        </div>
        <div className="sidebar-footer">
          <div className="export-buttons">
            <button className="btn btn-outline btn-sm" onClick={() => handleExport('json')} title="Export JSON">📥 JSON</button>
            <button className="btn btn-outline btn-sm" onClick={() => handleExport('markdown')} title="Export Markdown">📝 MD</button>
            <button className="btn btn-outline btn-sm" onClick={() => handleExport('csv')} title="Export CSV">📊 CSV</button>
          </div>
        </div>
      </div>

      {/* Toggle Sidebar */}
      <button className="sidebar-toggle" onClick={() => setShowSidebar(!showSidebar)}>
        {showSidebar ? '◀' : '▶'}
      </button>

      {/* Chat Area */}
      <div className="chat-page">
        {messages.length === 0 && historyLoaded ? (
          <div className="chat-empty">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--accent)' }}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <h2>Welcome, {user.full_name}!</h2>
            <p>Start a new conversation or select one from the sidebar. Multi-turn context is enabled for deeper conversations.</p>
            <button className="btn btn-primary" onClick={handleNewSession}>Start New Chat</button>
          </div>
        ) : (
          <div className="chat-messages">
            {messages.length > 0 && (
              <div style={{ textAlign: 'center', marginBottom: 8 }}>
                <button className="btn btn-outline btn-sm" onClick={handleClearHistory}>Clear History</button>
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
                          <circle cx="12" cy="12" r="3"/><circle cx="4" cy="6" r="2"/><circle cx="20" cy="6" r="2"/><circle cx="4" cy="18" r="2"/><circle cx="20" cy="18" r="2"/>
                          <line x1="6" y1="7" x2="9.5" y2="10.5"/><line x1="18" y1="7" x2="14.5" y2="10.5"/><line x1="6" y1="17" x2="9.5" y2="13.5"/><line x1="18" y1="17" x2="14.5" y2="13.5"/>
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
                        <summary>
                          Sources ({msg.numSources} documents)
                          {msg.multimodalResults > 0 && ` | ${msg.multimodalResults} multimodal`}
                        </summary>
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
                  <div className="typing-indicator"><span></span><span></span><span></span></div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}

        <div className="chat-input-area">
          {/* RAG Engine Selector */}
          <div className="chat-engine-toggle" style={{ display: 'flex', gap: 6, padding: '6px 0', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)' }}>
              <button
                className={`mode-btn ${ragEngine === 'enhanced' ? 'active' : ''}`}
                onClick={() => setRagEngine('enhanced')}
                title="ChromaDB + Knowledge Graph"
                style={{ borderRadius: '8px 0 0 8px', borderRight: 'none' }}
              >📚 Enhanced RAG</button>
              <button
                className={`mode-btn ${ragEngine === 'lightrag' ? 'active' : ''}`}
                onClick={() => setRagEngine('lightrag')}
                title="LightRAG – dual-level retrieval with KG"
                style={{ borderRadius: '0 8px 8px 0' }}
              >⚡ LightRAG</button>
            </div>

            {ragEngine === 'enhanced' ? (
              /* Enhanced RAG controls */
              <>
                <button className={`mode-btn ${useKG ? 'active' : ''}`} onClick={() => setUseKG(!useKG)}
                  title={useKG ? 'KG-RAG enabled' : 'Basic RAG mode'}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="3"/><circle cx="4" cy="6" r="2"/><circle cx="20" cy="6" r="2"/>
                    <circle cx="4" cy="18" r="2"/><circle cx="20" cy="18" r="2"/>
                    <line x1="6" y1="7" x2="9.5" y2="10.5"/><line x1="18" y1="7" x2="14.5" y2="10.5"/>
                    <line x1="6" y1="17" x2="9.5" y2="13.5"/><line x1="18" y1="17" x2="14.5" y2="13.5"/>
                  </svg>
                  {useKG ? 'KG-RAG' : 'Basic RAG'}
                </button>
                <button className={`mode-btn ${useMultimodal ? 'active' : ''}`} onClick={() => setUseMultimodal(!useMultimodal)}
                  title={useMultimodal ? 'Multimodal enabled' : 'Text only'}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                    <circle cx="8.5" cy="8.5" r="1.5"/>
                    <polyline points="21 15 16 10 5 21"/>
                  </svg>
                  {useMultimodal ? 'Multimodal' : 'Text Only'}
                </button>
              </>
            ) : (
              /* LightRAG controls */
              <>
                {LIGHTRAG_MODES.map(m => (
                  <button key={m.value}
                    className={`mode-btn ${lightragMode === m.value ? 'active' : ''}`}
                    onClick={() => setLightragMode(m.value)}
                    title={m.desc}
                    style={{ fontSize: 12, padding: '4px 10px' }}
                  >{m.icon} {m.label}</button>
                ))}
                <button
                  className={`mode-btn ${lightragStreaming ? 'active' : ''}`}
                  onClick={() => setLightragStreaming(!lightragStreaming)}
                  title="Toggle streaming"
                  style={{ fontSize: 12, padding: '4px 10px' }}
                >📡 {lightragStreaming ? 'Stream' : 'Batch'}</button>
                <button
                  className="mode-btn"
                  onClick={() => setShowLightragSettings(!showLightragSettings)}
                  style={{ fontSize: 12, padding: '4px 8px' }}
                >⚙️</button>
                {lightragHealth && (
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 10, marginLeft: 4,
                    background: lightragHealth.initialized ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                    color: lightragHealth.initialized ? '#22c55e' : '#ef4444',
                  }}>
                    {lightragHealth.initialized ? `${lightragHealth.graph_nodes || 0} nodes` : 'Not ready'}
                  </span>
                )}
              </>
            )}
          </div>

          {/* LightRAG advanced settings */}
          {ragEngine === 'lightrag' && showLightragSettings && (
            <div style={{
              display: 'flex', gap: 12, alignItems: 'center', padding: '4px 0', fontSize: 12, color: 'var(--text-secondary)',
            }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                Top-K:
                <input type="number" value={lightragTopK} onChange={e => setLightragTopK(parseInt(e.target.value) || 10)}
                  min={1} max={200}
                  style={{ width: 50, background: 'var(--bg-secondary)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)', padding: '2px 4px', fontSize: 12 }} />
              </label>
            </div>
          )}

          <div className="chat-input-wrapper">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => { setInput(e.target.value); autoResize(e); }}
              onKeyDown={handleKeyDown}
              placeholder={ragEngine === 'lightrag'
                ? `Ask with LightRAG (${lightragMode} mode)...`
                : useKG ? "Ask with Knowledge Graph enhanced RAG..." : "Ask a question (basic RAG mode)..."}
              rows={1}
              disabled={loading}
            />
            <button className="btn-send" onClick={handleSend} disabled={!input.trim() || loading}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChatPage;
