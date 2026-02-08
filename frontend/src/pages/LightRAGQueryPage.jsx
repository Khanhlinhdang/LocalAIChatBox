import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  lightragQuery,
  lightragQueryStream,
  lightragQueryWithContext,
  getLightRAGStrategies,
  getLightRAGHealth,
} from '../api';

// ============================================================
// Query mode descriptions
// ============================================================
const QUERY_MODES = [
  { value: 'hybrid', label: 'Hybrid', desc: 'Best overall - combines local + global context', icon: '🔀' },
  { value: 'local', label: 'Local', desc: 'Entity-centric search with relationships', icon: '📍' },
  { value: 'global', label: 'Global', desc: 'Community-level thematic analysis', icon: '🌐' },
  { value: 'naive', label: 'Naive', desc: 'Simple vector similarity search', icon: '🔍' },
  { value: 'mix', label: 'Mix', desc: 'Knowledge graph + vector retrieval', icon: '🧬' },
];

// ============================================================
// Simple Markdown Renderer
// ============================================================
function SimpleMarkdown({ text }) {
  if (!text) return null;

  const renderLine = (line, i) => {
    // Headers
    if (line.startsWith('### ')) return <h3 key={i} style={{ color: '#93c5fd', fontSize: 15, margin: '12px 0 6px' }}>{line.slice(4)}</h3>;
    if (line.startsWith('## ')) return <h2 key={i} style={{ color: '#93c5fd', fontSize: 17, margin: '14px 0 8px' }}>{line.slice(3)}</h2>;
    if (line.startsWith('# ')) return <h1 key={i} style={{ color: '#93c5fd', fontSize: 20, margin: '16px 0 10px' }}>{line.slice(2)}</h1>;
    
    // List items
    if (line.match(/^[\-\*]\s/)) return <li key={i} style={{ marginLeft: 16, marginBottom: 2 }}>{renderInline(line.slice(2))}</li>;
    if (line.match(/^\d+\.\s/)) return <li key={i} style={{ marginLeft: 16, marginBottom: 2, listStyleType: 'decimal' }}>{renderInline(line.replace(/^\d+\.\s/, ''))}</li>;
    
    // Empty line
    if (line.trim() === '') return <br key={i} />;
    
    // Normal paragraph
    return <p key={i} style={{ margin: '4px 0' }}>{renderInline(line)}</p>;
  };

  const renderInline = (text) => {
    // Bold
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} style={{ color: '#e2e8f0' }}>{part.slice(2, -2)}</strong>;
      }
      // Code
      const codeParts = part.split(/(`[^`]+`)/g);
      return codeParts.map((cp, j) => {
        if (cp.startsWith('`') && cp.endsWith('`')) {
          return <code key={`${i}-${j}`} style={{ background: '#1e293b', padding: '1px 4px', borderRadius: 3, fontSize: '0.9em', color: '#f0abfc' }}>{cp.slice(1, -1)}</code>;
        }
        return cp;
      });
    });
  };

  return (
    <div style={{ lineHeight: 1.65, color: '#cbd5e1' }}>
      {text.split('\n').map(renderLine)}
    </div>
  );
}

// ============================================================
// Query History Item
// ============================================================
function HistoryItem({ item, onReplay }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={{
      background: '#1a1b23', borderRadius: 10, marginBottom: 8,
      border: '1px solid rgba(100,100,150,0.2)',
    }}>
      <div onClick={() => setExpanded(!expanded)}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
          cursor: 'pointer',
        }}>
        <span style={{ fontSize: 14 }}>
          {QUERY_MODES.find(m => m.value === item.mode)?.icon || '🔍'}
        </span>
        <span style={{ flex: 1, fontSize: 13, color: '#e2e8f0' }}>
          {item.query.length > 80 ? item.query.slice(0, 80) + '...' : item.query}
        </span>
        <span style={{ fontSize: 10, color: '#64748b' }}>
          {item.mode} • {item.duration ? `${(item.duration / 1000).toFixed(1)}s` : ''}
        </span>
        <span style={{ fontSize: 12, color: '#64748b' }}>{expanded ? '▲' : '▼'}</span>
      </div>
      
      {expanded && (
        <div style={{ padding: '0 14px 14px', borderTop: '1px solid rgba(100,100,150,0.15)' }}>
          <div style={{ padding: '10px 0' }}>
            <SimpleMarkdown text={item.response} />
          </div>
          
          {item.context && (
            <details style={{ marginTop: 8 }}>
              <summary style={{ cursor: 'pointer', color: '#94a3b8', fontSize: 12 }}>
                📋 Retrieved Context
              </summary>
              <pre style={{
                background: '#0f1117', padding: 10, borderRadius: 6, fontSize: 11,
                whiteSpace: 'pre-wrap', color: '#94a3b8', maxHeight: 200, overflow: 'auto',
                marginTop: 6,
              }}>
                {typeof item.context === 'string' ? item.context : JSON.stringify(item.context, null, 2)}
              </pre>
            </details>
          )}
          
          <button onClick={() => onReplay(item)} style={{ ...btnStyle, marginTop: 8, fontSize: 11 }}>
            🔄 Re-run query
          </button>
        </div>
      )}
    </div>
  );
}

// ============================================================
// Main Query Page
// ============================================================
export default function LightRAGQueryPage() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [streaming, setStreaming] = useState(true);
  const [onlyContext, setOnlyContext] = useState(false);
  const [topK, setTopK] = useState(60);
  const [onlyNeedContext, setOnlyNeedContext] = useState(false);

  // Response state
  const [response, setResponse] = useState('');
  const [isQuerying, setIsQuerying] = useState(false);
  const [error, setError] = useState(null);
  const [queryDuration, setQueryDuration] = useState(null);

  // History & health
  const [history, setHistory] = useState([]);
  const [health, setHealth] = useState(null);
  const [showSettings, setShowSettings] = useState(false);

  const responseRef = useRef(null);
  const abortRef = useRef(null);

  // Load health
  useEffect(() => {
    getLightRAGHealth().then(res => setHealth(res.data)).catch(() => {});
  }, []);

  // Auto-scroll response
  useEffect(() => {
    if (responseRef.current) {
      responseRef.current.scrollTop = responseRef.current.scrollHeight;
    }
  }, [response]);

  // Execute query
  const executeQuery = useCallback(async () => {
    if (!query.trim() || isQuerying) return;
    
    setIsQuerying(true);
    setResponse('');
    setError(null);
    setQueryDuration(null);
    const startTime = Date.now();

    try {
      if (onlyNeedContext) {
        // Context-only query
        const res = await lightragQueryWithContext(query, mode, topK);
        const data = res.data;
        const ctx = data.context || data.response || JSON.stringify(data);
        setResponse(ctx);
        setQueryDuration(Date.now() - startTime);
        addHistory(query, mode, ctx, Date.now() - startTime, ctx);
      } else if (streaming) {
        // Streaming query
        let fullResponse = '';
        await lightragQueryStream(
          query,
          mode,
          { only_need_context: onlyContext, top_k: topK },
          (chunk) => {
            fullResponse += chunk;
            setResponse(fullResponse);
          }
        );
        setQueryDuration(Date.now() - startTime);
        addHistory(query, mode, fullResponse, Date.now() - startTime);
      } else {
        // Normal query
        const res = await lightragQuery(query, mode, onlyContext, streaming, topK);
        const data = res.data;
        const responseText = data.response || data.result || JSON.stringify(data);
        setResponse(responseText);
        setQueryDuration(Date.now() - startTime);
        addHistory(query, mode, responseText, Date.now() - startTime);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.response?.data?.detail || err.message);
      }
    }
    setIsQuerying(false);
  }, [query, mode, streaming, onlyContext, topK, onlyNeedContext, isQuerying]);

  const addHistory = (q, m, resp, dur, ctx) => {
    setHistory(prev => [{
      query: q, mode: m, response: resp, duration: dur,
      context: ctx, timestamp: Date.now(),
    }, ...prev].slice(0, 50));
  };

  // Handle Enter key
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      executeQuery();
    }
  };

  // Replay query
  const handleReplay = (item) => {
    setQuery(item.query);
    setMode(item.mode);
  };

  // Clear
  const clearResponse = () => {
    setResponse('');
    setError(null);
    setQueryDuration(null);
  };

  return (
    <div style={{ height: '100%', display: 'flex', background: '#0f1117', color: '#e2e8f0' }}>
      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px',
          background: '#1a1b23', borderBottom: '1px solid rgba(100,100,150,0.2)',
        }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#93c5fd' }}>
            🔎 LightRAG Query
          </h2>
          
          {health && (
            <span style={{
              fontSize: 11, padding: '2px 8px', borderRadius: 10,
              background: health.initialized ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
              color: health.initialized ? '#22c55e' : '#ef4444',
            }}>
              {health.initialized ? `${health.graph_nodes || 0} nodes` : 'Not ready'}
            </span>
          )}

          <div style={{ flex: 1 }} />
          
          <button onClick={() => setShowSettings(!showSettings)} style={btnStyle}>⚙️ Settings</button>
        </div>

        {/* Query mode selector */}
        <div style={{
          display: 'flex', gap: 6, padding: '10px 20px',
          background: '#13141c', borderBottom: '1px solid rgba(100,100,150,0.15)',
          overflowX: 'auto',
        }}>
          {QUERY_MODES.map(m => (
            <button key={m.value} onClick={() => setMode(m.value)}
              title={m.desc}
              style={{
                background: mode === m.value ? '#2563eb' : '#1e293b',
                border: `1px solid ${mode === m.value ? '#3b82f6' : '#334155'}`,
                borderRadius: 8, padding: '6px 14px', color: '#e2e8f0',
                cursor: 'pointer', fontSize: 12, whiteSpace: 'nowrap',
                transition: 'all 0.15s',
              }}>
              {m.icon} {m.label}
            </button>
          ))}
        </div>

        {/* Settings panel */}
        {showSettings && (
          <div style={{
            padding: '12px 20px', background: '#1a1b23',
            borderBottom: '1px solid rgba(100,100,150,0.2)',
            display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap',
          }}>
            <label style={checkboxStyle}>
              <input type="checkbox" checked={streaming} onChange={e => setStreaming(e.target.checked)} />
              Stream response
            </label>
            <label style={checkboxStyle}>
              <input type="checkbox" checked={onlyContext} onChange={e => setOnlyContext(e.target.checked)} />
              Context only (no LLM)
            </label>
            <label style={checkboxStyle}>
              <input type="checkbox" checked={onlyNeedContext} onChange={e => setOnlyNeedContext(e.target.checked)} />
              Return full context
            </label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>Top-K:</span>
              <input type="number" value={topK} onChange={e => setTopK(parseInt(e.target.value) || 10)}
                min={1} max={200}
                style={{ width: 60, ...inputStyle, padding: '3px 6px' }} />
            </div>
          </div>
        )}

        {/* Response area */}
        <div ref={responseRef} style={{
          flex: 1, overflow: 'auto', padding: 20,
        }}>
          {error && (
            <div style={{
              padding: '12px 16px', borderRadius: 10,
              background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)',
              color: '#fca5a5', marginBottom: 12, fontSize: 13,
            }}>
              ⚠️ {error}
            </div>
          )}

          {response ? (
            <div style={{
              background: '#1a1b23', borderRadius: 12, padding: 20,
              border: '1px solid rgba(100,100,150,0.2)',
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                marginBottom: 12, paddingBottom: 8, borderBottom: '1px solid rgba(100,100,150,0.15)',
              }}>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>
                  {QUERY_MODES.find(m => m.value === mode)?.icon} {mode.toUpperCase()} mode
                  {queryDuration && ` • ${(queryDuration / 1000).toFixed(1)}s`}
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => navigator.clipboard.writeText(response)} style={{ ...btnStyle, fontSize: 11 }}>
                    📋 Copy
                  </button>
                  <button onClick={clearResponse} style={{ ...btnStyle, fontSize: 11 }}>✕ Clear</button>
                </div>
              </div>
              <SimpleMarkdown text={response} />
              {isQuerying && (
                <span style={{
                  display: 'inline-block', width: 8, height: 16, background: '#3b82f6',
                  animation: 'blink 1s step-end infinite', marginLeft: 2,
                }} />
              )}
            </div>
          ) : !isQuerying ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: '#475569' }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>🔎</div>
              <div style={{ fontSize: 16, color: '#64748b' }}>Ask a question about your knowledge base</div>
              <div style={{ fontSize: 13, marginTop: 8 }}>
                LightRAG uses dual-level retrieval with knowledge graph entities and community detection
              </div>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: 20, flexWrap: 'wrap' }}>
                {[
                  'What are the main topics discussed?',
                  'Summarize the key findings',
                  'What entities are most connected?',
                ].map((suggestion, i) => (
                  <button key={i} onClick={() => setQuery(suggestion)}
                    style={{
                      ...btnStyle, padding: '8px 14px', fontSize: 12,
                      background: '#1a1b23', maxWidth: 240,
                    }}>
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '40px 20px', color: '#64748b' }}>
              <div style={{ fontSize: 24, marginBottom: 8, animation: 'pulse 2s infinite' }}>⏳</div>
              <div>Querying knowledge graph ({mode} mode)...</div>
            </div>
          )}
        </div>

        {/* Query input */}
        <div style={{
          padding: '12px 20px', background: '#1a1b23',
          borderTop: '1px solid rgba(100,100,150,0.2)',
        }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a question... (Shift+Enter for new line)"
              rows={2}
              style={{
                flex: 1, background: '#0f1117', border: '1px solid #334155',
                borderRadius: 10, padding: '10px 14px', color: '#e2e8f0',
                fontSize: 14, resize: 'none', lineHeight: 1.5,
                outline: 'none',
              }}
            />
            <button onClick={executeQuery}
              disabled={!query.trim() || isQuerying}
              style={{
                ...primaryBtnStyle,
                opacity: !query.trim() || isQuerying ? 0.5 : 1,
                alignSelf: 'flex-end', padding: '10px 20px',
                fontSize: 14,
              }}>
              {isQuerying ? '⏳' : '🚀'} {isQuerying ? 'Querying...' : 'Send'}
            </button>
          </div>
        </div>
      </div>

      {/* History sidebar */}
      <div style={{
        width: 320, background: '#13141c', borderLeft: '1px solid rgba(100,100,150,0.2)',
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        <div style={{
          padding: '12px 14px', borderBottom: '1px solid rgba(100,100,150,0.2)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#93c5fd' }}>📜 History</span>
          <span style={{ fontSize: 11, color: '#64748b' }}>{history.length} queries</span>
          <div style={{ flex: 1 }} />
          {history.length > 0 && (
            <button onClick={() => setHistory([])} style={{ ...btnStyle, fontSize: 11, padding: '2px 8px' }}>
              Clear
            </button>
          )}
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: 8 }}>
          {history.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 12px', color: '#475569', fontSize: 13 }}>
              No queries yet
            </div>
          ) : (
            history.map((item, i) => (
              <HistoryItem key={i} item={item} onReplay={handleReplay} />
            ))
          )}
        </div>
      </div>

      <style>{`
        @keyframes blink {
          50% { opacity: 0; }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

// ============================================================
// Styles
// ============================================================
const btnStyle = {
  background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
  padding: '5px 12px', color: '#e2e8f0', cursor: 'pointer', fontSize: 12,
};
const primaryBtnStyle = {
  background: '#2563eb', border: '1px solid #3b82f6', borderRadius: 8,
  padding: '8px 16px', color: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 500,
};
const inputStyle = {
  background: '#0f1117', border: '1px solid #334155', borderRadius: 4,
  color: '#e2e8f0', fontSize: 12,
};
const checkboxStyle = {
  display: 'flex', alignItems: 'center', gap: 6, color: '#e2e8f0',
  fontSize: 12, cursor: 'pointer',
};
