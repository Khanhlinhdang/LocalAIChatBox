import React, { useState, useEffect, useRef, useCallback } from 'react';
import { startResearch, getResearchProgress, getResearchResult, generateReport, getResearchHistory, deleteResearch, getStrategies, exportResearchAs } from '../api';

function DeepResearchPage({ user }) {
  const [query, setQuery] = useState('');
  const [strategy, setStrategy] = useState('source-based');
  const [strategies, setStrategies] = useState([]);
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

  useEffect(() => {
    fetchStrategies();
    fetchHistory();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    };
  }, []);

  const fetchStrategies = async () => {
    try {
      const res = await getStrategies();
      setStrategies(res.data.strategies || []);
    } catch (err) {
      console.error('Failed to fetch strategies:', err);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await getResearchHistory();
      setHistory(res.data.tasks || []);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  const startPolling = useCallback((taskId) => {
    // Clean up existing connections
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }

    // Try SSE first, fall back to polling
    try {
      const token = localStorage.getItem('token');
      const baseUrl = process.env.REACT_APP_API_URL || '/api';
      const evtSource = new EventSource(`${baseUrl}/research/${taskId}/stream?token=${token}`);
      sseRef.current = evtSource;

      evtSource.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          setProgress(data);

          if (data.done || data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
            evtSource.close();
            sseRef.current = null;

            if (data.status === 'completed') {
              const resultRes = await getResearchResult(taskId);
              setResult(resultRes.data);
            }
            fetchHistory();
          }
        } catch (e) {
          console.error('SSE parse error:', e);
        }
      };

      evtSource.onerror = () => {
        // SSE failed, fall back to polling
        evtSource.close();
        sseRef.current = null;
        console.log('SSE unavailable, falling back to polling');
        startFallbackPolling(taskId);
      };
    } catch (e) {
      // SSE not supported, use polling
      startFallbackPolling(taskId);
    }
  }, []);

  const startFallbackPolling = useCallback((taskId) => {
    if (pollingRef.current) clearInterval(pollingRef.current);

    pollingRef.current = setInterval(async () => {
      try {
        const res = await getResearchProgress(taskId);
        setProgress(res.data);

        if (res.data.status === 'completed' || res.data.status === 'failed' || res.data.status === 'cancelled') {
          clearInterval(pollingRef.current);
          pollingRef.current = null;

          if (res.data.status === 'completed') {
            const resultRes = await getResearchResult(taskId);
            setResult(resultRes.data);
          }
          fetchHistory();
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 2000);
  }, []);

  const handleStartResearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResult(null);
    setReport(null);
    setProgress(null);

    try {
      const res = await startResearch(query, strategy);
      const taskId = res.data.task_id;
      setActiveTask(taskId);
      setProgress({ status: 'pending', progress: 0, message: 'Starting research...' });
      startPolling(taskId);
      fetchHistory();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to start research');
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
    } finally {
      setGenerating(false);
    }
  };

  const handleSelectTask = async (task) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
    setActiveTask(task.id);
    setReport(null);

    if (task.status === 'completed') {
      setProgress({ status: 'completed', progress: 100, message: 'Research completed' });
      try {
        const res = await getResearchResult(task.id);
        setResult(res.data);
        if (res.data.report) setReport(res.data.report);
      } catch (err) {
        console.error('Failed to load result:', err);
      }
    } else if (task.status === 'running' || task.status === 'pending') {
      setProgress({ status: task.status, progress: task.progress || 0, message: task.progress_message || '' });
      setResult(null);
      startPolling(task.id);
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
      if (activeTask === taskId) {
        setActiveTask(null);
        setResult(null);
        setReport(null);
        setProgress(null);
      }
      fetchHistory();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'var(--success)';
      case 'running': return 'var(--primary)';
      case 'pending': return 'var(--warning, #f0ad4e)';
      case 'failed': return 'var(--danger)';
      default: return 'var(--text-secondary)';
    }
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
      const contentDisp = res.headers['content-disposition'];
      const filename = contentDisp ? contentDisp.split('filename=')[1]?.replace(/"/g, '') : `research.${format}`;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert(err.response?.data?.detail || `Failed to export as ${format}`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="research-page">
      {/* Input Section */}
      <div className="research-input-section">
        <h1>Deep Research</h1>
        <div className="research-form">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Enter your research query... (e.g., 'What are the latest trends in renewable energy?')"
            className="research-query-input"
            rows={3}
          />
          <div className="research-controls">
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="research-strategy-select"
            >
              {strategies.map(s => (
                <option key={s.id} value={s.id}>{s.name} - {s.description}</option>
              ))}
            </select>
            <button
              className="btn btn-primary"
              onClick={handleStartResearch}
              disabled={loading || !query.trim() || (progress && (progress.status === 'running' || progress.status === 'pending'))}
            >
              {loading ? 'Starting...' : 'Start Research'}
            </button>
          </div>
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
                    <span className="history-strategy">{task.strategy}</span>
                  </div>
                  <div className="history-item-date">
                    {task.created_at ? new Date(task.created_at).toLocaleDateString() : ''}
                  </div>
                  <button
                    className="history-delete-btn"
                    onClick={(e) => handleDeleteTask(task.id, e)}
                    title="Delete"
                  >x</button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="research-main">
          {/* Progress Bar */}
          {progress && (progress.status === 'running' || progress.status === 'pending') && (
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
                <div className="result-actions">
                  {!report && (
                    <button
                      className="btn btn-primary"
                      onClick={handleGenerateReport}
                      disabled={generating}
                    >
                      {generating ? 'Generating Report...' : 'Generate Report'}
                    </button>
                  )}
                  <div className="export-buttons">
                    <button className="btn btn-outline" onClick={() => handleExport('markdown')} disabled={exporting} title="Export as Markdown">
                      📄 MD
                    </button>
                    <button className="btn btn-outline" onClick={() => handleExport('pdf')} disabled={exporting} title="Export as PDF">
                      📕 PDF
                    </button>
                    <button className="btn btn-outline" onClick={() => handleExport('docx')} disabled={exporting} title="Export as Word">
                      📘 DOCX
                    </button>
                    <button className="btn btn-outline" onClick={() => handleExport('json')} disabled={exporting} title="Export as JSON">
                      📦 JSON
                    </button>
                  </div>
                </div>
              </div>

              {/* Knowledge / Findings */}
              <div className="result-section">
                <h4>Findings</h4>
                <div className="result-content markdown-content">
                  {(result.knowledge || '').split('\n').map((line, i) => (
                    <p key={i}>{line}</p>
                  ))}
                </div>
              </div>

              {/* Report */}
              {report && (
                <div className="result-section report-section">
                  <h4>Detailed Report</h4>
                  <div className="result-content markdown-content">
                    {report.split('\n').map((line, i) => (
                      <p key={i}>{line}</p>
                    ))}
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

              {/* Metadata */}
              {result.completed_at && (
                <div className="result-meta">
                  <span>Strategy: {result.strategy}</span>
                  <span>Completed: {new Date(result.completed_at).toLocaleString()}</span>
                </div>
              )}
            </div>
          )}

          {/* Empty State */}
          {!progress && !result && (
            <div className="research-empty">
              <h3>Start a Deep Research Task</h3>
              <p>Enter a research query above and select a strategy. The AI will perform iterative multi-hop search and analysis to provide comprehensive findings.</p>
              <div className="strategy-info">
                <h4>Available Strategies</h4>
                {strategies.map(s => (
                  <div key={s.id} className="strategy-card">
                    <strong>{s.name}</strong>
                    <span className="strategy-desc">{s.description}</span>
                    <span className="strategy-best">Best for: {s.best_for}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DeepResearchPage;
