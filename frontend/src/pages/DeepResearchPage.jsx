import React, { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  startResearch, getResearchProgress, getResearchResult, generateReport,
  getResearchHistory, deleteResearch, getStrategies, exportResearchAs,
  getLDRHealth, getLDRStrategies, getLDRSearchEngines,
  startLDRResearch, getLDRProgress, getLDRResult, startLDRFollowUp,
} from '../api';

function DeepResearchPage({ user }) {
  // Core state
  const [query, setQuery] = useState('');
  const [strategy, setStrategy] = useState('source-based');
  const [history, setHistory] = useState([]);
  const [activeTask, setActiveTask] = useState(null);
  const [progress, setProgress] = useState(null);
  const [result, setResult] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const pollingRef = useRef(null);
  const sseRef = useRef(null);

  // Engine toggle: 'builtin' | 'ldr'
  const [engine, setEngine] = useState('builtin');
  const [builtinStrategies, setBuiltinStrategies] = useState([]);
  const [ldrStrategies, setLdrStrategies] = useState([]);
  const [ldrEngines, setLdrEngines] = useState([]);
  const [ldrHealth, setLdrHealth] = useState(null);
  const [searchEngine, setSearchEngine] = useState('auto');
  const [researchMode, setResearchMode] = useState('detailed');
  const [iterations, setIterations] = useState(3);
  const [questionsPerIter, setQuestionsPerIter] = useState(3);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [strategyCategory, setStrategyCategory] = useState('all');
  const [followUpQuery, setFollowUpQuery] = useState('');
  const [showFollowUp, setShowFollowUp] = useState(false);

  useEffect(() => {
    fetchBuiltinStrategies();
    fetchHistory();
    fetchLDRInfo();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, []);

  const fetchBuiltinStrategies = async () => {
    try {
      const res = await getStrategies();
      setBuiltinStrategies(res.data.strategies || []);
    } catch (err) { console.error('Failed to fetch strategies:', err); }
  };

  const fetchLDRInfo = async () => {
    try {
      const [healthRes, stratRes, engRes] = await Promise.all([
        getLDRHealth(), getLDRStrategies(), getLDRSearchEngines(),
      ]);
      setLdrHealth(healthRes.data);
      setLdrStrategies(stratRes.data.strategies || []);
      setLdrEngines(engRes.data.engines || []);
    } catch (err) {
      console.error('LDR info fetch failed:', err);
      setLdrHealth({ status: 'unavailable' });
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await getResearchHistory();
      setHistory(res.data.tasks || []);
    } catch (err) { console.error('Failed to fetch history:', err); }
  };

  const currentStrategies = engine === 'ldr' ? ldrStrategies : builtinStrategies;
  const filteredStrategies = strategyCategory === 'all'
    ? currentStrategies
    : currentStrategies.filter(s => s.category === strategyCategory);
  const ldrCategories = [...new Set(ldrStrategies.map(s => s.category || 'general'))];

  const startPolling = useCallback((taskId, isLDR = false) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }

    const getProgressFn = isLDR ? getLDRProgress : getResearchProgress;
    const getResultFn = isLDR ? getLDRResult : getResearchResult;

    // Try SSE first for built-in engine
    if (!isLDR) {
      try {
        const token = localStorage.getItem('token');
        const baseUrl = process.env.REACT_APP_API_URL || '/api';
        const evtSource = new EventSource(`${baseUrl}/research/${taskId}/stream?token=${token}`);
        sseRef.current = evtSource;
        evtSource.onmessage = async (event) => {
          try {
            const data = JSON.parse(event.data);
            setProgress(data);
            if (data.done || data.status === 'completed' || data.status === 'failed') {
              evtSource.close(); sseRef.current = null;
              if (data.status === 'completed') {
                const r = await getResultFn(taskId);
                setResult(r.data);
              }
              fetchHistory();
            }
          } catch (e) { console.error('SSE parse error:', e); }
        };
        evtSource.onerror = () => {
          evtSource.close(); sseRef.current = null;
          startFallbackPolling(taskId, getProgressFn, getResultFn);
        };
        return;
      } catch (e) { /* fall through to polling */ }
    }

    startFallbackPolling(taskId, getProgressFn, getResultFn);
  }, []);

  const startFallbackPolling = useCallback((taskId, getProgressFn, getResultFn) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const res = await getProgressFn(taskId);
        setProgress(res.data);
        if (['completed', 'failed', 'cancelled'].includes(res.data.status)) {
          clearInterval(pollingRef.current); pollingRef.current = null;
          if (res.data.status === 'completed') {
            const r = await getResultFn(taskId);
            setResult(r.data);
          }
          fetchHistory();
        }
      } catch (err) { console.error('Polling error:', err); }
    }, 2000);
  }, []);

  const handleStartResearch = async () => {
    if (!query.trim()) return;
    setLoading(true); setResult(null); setReport(null); setProgress(null);
    setShowFollowUp(false);

    try {
      let taskId;
      const isLDR = engine === 'ldr';

      if (isLDR) {
        const res = await startLDRResearch(query, strategy, {
          research_mode: researchMode,
          search_engine: searchEngine,
          iterations, questions_per_iteration: questionsPerIter,
        });
        taskId = res.data.task_id;
      } else {
        const res = await startResearch(query, strategy);
        taskId = res.data.task_id;
      }

      setActiveTask(taskId);
      setProgress({ status: 'pending', progress: 0, message: 'Starting research...' });
      startPolling(taskId, isLDR);
      fetchHistory();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to start research');
    } finally {
      setLoading(false);
    }
  };

  const handleFollowUp = async () => {
    if (!followUpQuery.trim() || !activeTask) return;
    setLoading(true); setResult(null); setReport(null); setProgress(null);

    try {
      const res = await startLDRFollowUp(activeTask, followUpQuery);
      const taskId = res.data.task_id;
      setActiveTask(taskId);
      setFollowUpQuery('');
      setShowFollowUp(false);
      setProgress({ status: 'pending', progress: 0, message: 'Starting follow-up research...' });
      startPolling(taskId, true);
      fetchHistory();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to start follow-up');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!activeTask) return;
    setGenerating(true);
    try {
      const res = await generateReport(activeTask);
      setReport(res.data.report);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to generate report');
    } finally { setGenerating(false); }
  };

  const handleSelectTask = async (task) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    setActiveTask(task.id);
    setReport(null); setShowFollowUp(false);

    const isLDR = (task.strategy || '').startsWith('ldr:');
    const getResultFn = isLDR ? getLDRResult : getResearchResult;

    if (task.status === 'completed') {
      setProgress({ status: 'completed', progress: 100, message: 'Research completed' });
      try {
        const res = await getResultFn(task.id);
        setResult(res.data);
        if (res.data.report) setReport(res.data.report);
      } catch (err) { console.error('Failed to load result:', err); }
    } else if (['running', 'pending'].includes(task.status)) {
      setProgress({ status: task.status, progress: task.progress || 0, message: task.progress_message || '' });
      setResult(null);
      startPolling(task.id, isLDR);
    } else {
      setProgress({ status: task.status, progress: 0, message: task.progress_message || '' });
      setResult(null);
    }
  };

  const handleDeleteTask = async (taskId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this research task?')) return;
    try {
      await deleteResearch(taskId);
      if (activeTask === taskId) { setActiveTask(null); setResult(null); setReport(null); setProgress(null); }
      fetchHistory();
    } catch (err) { alert(err.response?.data?.detail || 'Failed to delete'); }
  };

  const handleExport = async (format) => {
    if (!activeTask) return;
    setExporting(true);
    try {
      const res = await exportResearchAs(activeTask, format);
      const blob = new Blob([res.data], { type: res.headers['content-type'] });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const cd = res.headers['content-disposition'];
      a.download = cd ? cd.split('filename=')[1]?.replace(/"/g, '') : `research.${format}`;
      document.body.appendChild(a); a.click();
      window.URL.revokeObjectURL(url); document.body.removeChild(a);
    } catch (err) { alert(`Export failed: ${err.response?.data?.detail || err.message}`); }
    finally { setExporting(false); }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'var(--success)';
      case 'running': return 'var(--accent)';
      case 'pending': return '#f59e0b';
      case 'failed': return 'var(--danger)';
      default: return 'var(--text-secondary)';
    }
  };

  const getEngineLabel = (strat) => {
    if (!strat) return '';
    return strat.startsWith('ldr:') ? '⚡LDR' : '📚Built-in';
  };

  return (
    <div className="research-page">
      {/* Input Section */}
      <div className="research-input-section">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <h1 style={{ margin: 0 }}>Deep Research</h1>
          {/* Engine Toggle */}
          <div style={{ display: 'flex', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)' }}>
            <button
              className={`mode-btn ${engine === 'builtin' ? 'active' : ''}`}
              onClick={() => { setEngine('builtin'); setStrategy('source-based'); setStrategyCategory('all'); }}
              style={{ borderRadius: '8px 0 0 8px', borderRight: 'none', padding: '8px 16px' }}
            >📚 Built-in Engine</button>
            <button
              className={`mode-btn ${engine === 'ldr' ? 'active' : ''}`}
              onClick={() => { setEngine('ldr'); setStrategy('source-based'); setStrategyCategory('all'); }}
              style={{ borderRadius: '0 8px 8px 0', padding: '8px 16px' }}
              title="30+ strategies, 27+ search engines"
            >⚡ LDR Advanced</button>
          </div>
        </div>

        {/* LDR Health indicator */}
        {engine === 'ldr' && ldrHealth && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, marginTop: 8,
            fontSize: 12, color: ldrHealth.status === 'ready' ? '#22c55e' : '#ef4444',
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: ldrHealth.status === 'ready' ? '#22c55e' : '#ef4444',
            }}></span>
            LDR: {ldrHealth.status} | {ldrHealth.strategies_count} strategies | {ldrHealth.search_engines_count} engines
          </div>
        )}

        <div className="research-form" style={{ marginTop: 12 }}>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={engine === 'ldr'
              ? "Enter your research query... (LDR: 30+ strategies, multi-engine search, follow-up research)"
              : "Enter your research query... (Built-in: iterative multi-hop search and analysis)"}
            className="research-query-input"
            rows={3}
          />

          <div className="research-controls" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Strategy Category filter (LDR only) */}
            {engine === 'ldr' && (
              <select
                value={strategyCategory}
                onChange={(e) => { setStrategyCategory(e.target.value); }}
                className="research-strategy-select"
                style={{ maxWidth: 140 }}
              >
                <option value="all">All Categories</option>
                {ldrCategories.map(c => (
                  <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
                ))}
              </select>
            )}

            {/* Strategy selector */}
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="research-strategy-select"
              style={{ flex: 1, minWidth: 200 }}
            >
              {filteredStrategies.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} - {s.description}
                </option>
              ))}
            </select>

            {/* LDR-specific controls */}
            {engine === 'ldr' && (
              <>
                {/* Research Mode */}
                <select
                  value={researchMode}
                  onChange={(e) => setResearchMode(e.target.value)}
                  className="research-strategy-select"
                  style={{ maxWidth: 130 }}
                >
                  <option value="quick">Quick</option>
                  <option value="detailed">Detailed</option>
                  <option value="report">Full Report</option>
                </select>

                {/* Search Engine */}
                <select
                  value={searchEngine}
                  onChange={(e) => setSearchEngine(e.target.value)}
                  className="research-strategy-select"
                  style={{ maxWidth: 160 }}
                >
                  {ldrEngines.map(eng => (
                    <option key={eng.id} value={eng.id}>
                      {eng.name} {eng.api_key_required ? '🔑' : ''}
                    </option>
                  ))}
                </select>

                {/* Advanced toggle */}
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  style={{ fontSize: 12 }}
                >⚙️ {showAdvanced ? 'Hide' : 'Options'}</button>
              </>
            )}

            <button
              className="btn btn-primary"
              onClick={handleStartResearch}
              disabled={loading || !query.trim() || (progress && ['running', 'pending'].includes(progress.status))}
              style={{ minWidth: 130 }}
            >
              {loading ? 'Starting...' : engine === 'ldr' ? '⚡ Research' : '🔍 Research'}
            </button>
          </div>

          {/* Advanced LDR settings */}
          {engine === 'ldr' && showAdvanced && (
            <div style={{
              display: 'flex', gap: 16, alignItems: 'center', marginTop: 8,
              padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8,
              fontSize: 13, color: 'var(--text-secondary)',
            }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                Iterations:
                <input type="number" value={iterations} onChange={e => setIterations(parseInt(e.target.value) || 1)}
                  min={1} max={10}
                  style={{ width: 50, background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)', padding: '2px 4px' }} />
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                Questions/iter:
                <input type="number" value={questionsPerIter} onChange={e => setQuestionsPerIter(parseInt(e.target.value) || 1)}
                  min={1} max={10}
                  style={{ width: 50, background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text-primary)', padding: '2px 4px' }} />
              </label>
            </div>
          )}
        </div>
      </div>

      <div className="research-layout">
        {/* History Sidebar */}
        <div className="research-sidebar">
          <h3>Research History</h3>
          {history.length === 0 ? (
            <p className="empty-message">No research tasks yet</p>
          ) : (
            <div className="research-history-list">
              {history.map(task => (
                <div
                  key={task.id}
                  className={`history-item ${activeTask === task.id ? 'active' : ''}`}
                  onClick={() => handleSelectTask(task)}
                >
                  <div className="history-item-query">{task.query}</div>
                  <div className="history-item-meta">
                    <span className="history-status" style={{ color: getStatusColor(task.status) }}>
                      {task.status}
                    </span>
                    <span className="history-strategy" style={{ fontSize: 10 }}>
                      {getEngineLabel(task.strategy)} {(task.strategy || '').replace('ldr:', '')}
                    </span>
                  </div>
                  <div className="history-item-date">
                    {task.created_at ? new Date(task.created_at).toLocaleDateString() : ''}
                  </div>
                  <button className="history-delete-btn" onClick={(e) => handleDeleteTask(task.id, e)} title="Delete">x</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="research-main">
          {/* Progress */}
          {progress && ['running', 'pending'].includes(progress.status) && (
            <div className="research-progress">
              <div className="progress-header">
                <span className="progress-label">Research in progress...</span>
                <span className="progress-percent">{Math.round(progress.progress)}%</span>
              </div>
              <div className="progress-bar-container">
                <div className="progress-bar-fill" style={{ width: `${progress.progress}%` }}></div>
              </div>
              <div className="progress-message">{progress.message}</div>
            </div>
          )}

          {/* Error */}
          {progress && progress.status === 'failed' && (
            <div className="research-error">
              <h3>Research Failed</h3>
              <p>{progress.message}</p>
            </div>
          )}

          {/* Results */}
          {result && result.status === 'completed' && (
            <div className="research-results">
              <div className="result-header">
                <h3>Research Results: {result.query}</h3>
                <div className="result-actions" style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {!report && (
                    <button className="btn btn-primary btn-sm" onClick={handleGenerateReport} disabled={generating}>
                      {generating ? 'Generating...' : '📄 Generate Report'}
                    </button>
                  )}
                  <button className="btn btn-outline btn-sm" onClick={() => setShowFollowUp(!showFollowUp)}>
                    🔄 Follow-up
                  </button>
                  <div className="export-buttons" style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-outline btn-sm" onClick={() => handleExport('markdown')} disabled={exporting}>MD</button>
                    <button className="btn btn-outline btn-sm" onClick={() => handleExport('pdf')} disabled={exporting}>PDF</button>
                    <button className="btn btn-outline btn-sm" onClick={() => handleExport('docx')} disabled={exporting}>DOCX</button>
                    <button className="btn btn-outline btn-sm" onClick={() => handleExport('json')} disabled={exporting}>JSON</button>
                  </div>
                </div>
              </div>

              {/* Follow-up Research */}
              {showFollowUp && (
                <div style={{
                  display: 'flex', gap: 8, margin: '12px 0', padding: 12,
                  background: 'var(--bg-secondary)', borderRadius: 8,
                }}>
                  <input
                    type="text" value={followUpQuery}
                    onChange={(e) => setFollowUpQuery(e.target.value)}
                    placeholder="Ask a follow-up question based on this research..."
                    style={{
                      flex: 1, padding: '8px 12px', background: 'var(--bg-primary)',
                      border: '1px solid var(--border)', borderRadius: 6,
                      color: 'var(--text-primary)', fontSize: 14,
                    }}
                    onKeyDown={(e) => e.key === 'Enter' && handleFollowUp()}
                  />
                  <button className="btn btn-primary btn-sm" onClick={handleFollowUp}
                    disabled={!followUpQuery.trim() || loading}>
                    ⚡ Follow Up
                  </button>
                </div>
              )}

              {/* Result Metadata */}
              {result.metadata && (
                <div style={{
                  display: 'flex', gap: 12, flexWrap: 'wrap', margin: '12px 0',
                  padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8,
                  fontSize: 12, color: 'var(--text-secondary)',
                }}>
                  {result.engine && <span>Engine: <strong>{result.engine === 'ldr' ? '⚡LDR' : '📚Built-in'}</strong></span>}
                  {result.strategy && <span>Strategy: <strong>{(result.strategy || '').replace('ldr:', '')}</strong></span>}
                  {result.metadata.research_mode && <span>Mode: <strong>{result.metadata.research_mode}</strong></span>}
                  {result.metadata.search_engine && <span>Search: <strong>{result.metadata.search_engine}</strong></span>}
                  {result.metadata.iterations && <span>Iterations: <strong>{result.metadata.iterations}</strong></span>}
                  {result.metadata.total_sources && <span>Sources: <strong>{result.metadata.total_sources}</strong></span>}
                  {result.duration_seconds > 0 && <span>Duration: <strong>{result.duration_seconds}s</strong></span>}
                </div>
              )}

              {/* Knowledge / Findings */}
              <div className="result-section">
                <h4>Findings</h4>
                <div className="result-content markdown-content">
                  <ReactMarkdown>{result.knowledge || ''}</ReactMarkdown>
                </div>
              </div>

              {/* Report */}
              {report && (
                <div className="result-section report-section">
                  <h4>Detailed Report</h4>
                  <div className="result-content markdown-content">
                    <ReactMarkdown>{report}</ReactMarkdown>
                  </div>
                </div>
              )}

              {/* Sources */}
              {result.sources && result.sources.length > 0 && (
                <div className="result-section">
                  <h4>Sources ({result.sources.length})</h4>
                  <div className="sources-list">
                    {result.sources.map((source, i) => (
                      <div key={i} className="source-item">
                        {typeof source === 'object' ? (
                          <>
                            <span className="source-number">[{i + 1}]</span>
                            <div className="source-details">
                              <div className="source-title">{source.title || 'Source'}</div>
                              {source.url && (
                                <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-url">
                                  {source.url}
                                </a>
                              )}
                              {source.snippet && <div className="source-snippet">{source.snippet}</div>}
                              {source.source_engine && <span className="source-engine">{source.source_engine}</span>}
                              {source.source && <span className="source-engine">{source.source}</span>}
                            </div>
                          </>
                        ) : (
                          <span>{source}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Completion info */}
              {result.completed_at && (
                <div className="result-meta">
                  <span>Completed: {new Date(result.completed_at).toLocaleString()}</span>
                </div>
              )}
            </div>
          )}

          {/* Empty State */}
          {!progress && !result && (
            <div className="research-empty">
              <h3>🔬 Start a Deep Research Task</h3>
              <p>
                {engine === 'ldr'
                  ? 'LDR Advanced Engine: 30+ research strategies, 27+ search engines, multi-iteration analysis, follow-up research, and structured report generation.'
                  : 'Built-in Engine: Iterative multi-hop search with sub-question decomposition and knowledge accumulation.'}
              </p>
              <div className="strategy-info">
                <h4>{engine === 'ldr' ? 'LDR Strategies' : 'Available Strategies'}
                  {engine === 'ldr' && <span style={{ fontSize: 12, color: 'var(--text-secondary)', marginLeft: 8 }}>
                    ({filteredStrategies.length} of {ldrStrategies.length})
                  </span>}
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
                  {filteredStrategies.slice(0, 12).map(s => (
                    <div key={s.id} className="strategy-card" style={{ cursor: 'pointer', padding: '10px 14px' }}
                      onClick={() => { setStrategy(s.id); }}>
                      <strong style={{ fontSize: 13 }}>{s.name}</strong>
                      {s.category && <span style={{
                        fontSize: 10, padding: '1px 6px', borderRadius: 4, marginLeft: 6,
                        background: 'var(--bg-secondary)', color: 'var(--text-secondary)',
                      }}>{s.category}</span>}
                      <div className="strategy-desc" style={{ fontSize: 12, marginTop: 4 }}>{s.description}</div>
                      <div className="strategy-best" style={{ fontSize: 11 }}>Best for: {s.best_for}</div>
                    </div>
                  ))}
                </div>
                {filteredStrategies.length > 12 && (
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 8 }}>
                    + {filteredStrategies.length - 12} more strategies available in the dropdown
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DeepResearchPage;
