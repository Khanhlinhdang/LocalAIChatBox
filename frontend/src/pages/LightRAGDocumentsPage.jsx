import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  getLightRAGDocuments,
  lightragInsertText,
  lightragUploadDocument,
  lightragDeleteDocument,
  lightragClearDocuments,
  getLightRAGPipelineStatus,
  getLightRAGDocumentStatusCounts,
} from '../api';

// ============================================================
// Status badge colors
// ============================================================
const STATUS_STYLES = {
  processed: { bg: 'rgba(34,197,94,0.15)', color: '#22c55e', label: 'Processed' },
  processing: { bg: 'rgba(59,130,246,0.15)', color: '#3b82f6', label: 'Processing' },
  pending: { bg: 'rgba(234,179,8,0.15)', color: '#eab308', label: 'Pending' },
  failed: { bg: 'rgba(239,68,68,0.15)', color: '#ef4444', label: 'Failed' },
  unknown: { bg: 'rgba(100,116,139,0.15)', color: '#94a3b8', label: 'Unknown' },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.unknown;
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 500,
      background: s.bg, color: s.color,
    }}>
      {s.label}
    </span>
  );
}

// ============================================================
// Main Documents Page
// ============================================================
export default function LightRAGDocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [statusCounts, setStatusCounts] = useState({});
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Upload states
  const [showUpload, setShowUpload] = useState(false);
  const [uploadMode, setUploadMode] = useState('file'); // file | text
  const [textInput, setTextInput] = useState('');
  const [textDescription, setTextDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState('');

  // Confirm delete
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [clearConfirm, setClearConfirm] = useState(false);

  // Auto-refresh for pipeline
  const [autoRefresh, setAutoRefresh] = useState(false);
  const refreshInterval = useRef(null);

  // Load documents
  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [docsRes, countsRes] = await Promise.all([
        getLightRAGDocuments(statusFilter || undefined),
        getLightRAGDocumentStatusCounts(),
      ]);
      setDocuments(docsRes.data.documents || docsRes.data || []);
      setStatusCounts(countsRes.data || {});
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  }, [statusFilter]);

  const loadPipeline = useCallback(async () => {
    try {
      const res = await getLightRAGPipelineStatus();
      setPipelineStatus(res.data);
    } catch (e) {
      console.warn('Pipeline status failed:', e);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    loadPipeline();
  }, [loadDocuments, loadPipeline]);

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      refreshInterval.current = setInterval(() => {
        loadDocuments();
        loadPipeline();
      }, 5000);
    }
    return () => {
      if (refreshInterval.current) clearInterval(refreshInterval.current);
    };
  }, [autoRefresh, loadDocuments, loadPipeline]);

  // Clear success message
  useEffect(() => {
    if (successMsg) {
      const t = setTimeout(() => setSuccessMsg(null), 5000);
      return () => clearTimeout(t);
    }
  }, [successMsg]);

  // Upload file
  const handleFileUpload = async (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    setUploading(true);
    setError(null);
    try {
      for (const file of files) {
        await lightragUploadDocument(file);
      }
      setSuccessMsg(`${files.length} file(s) uploaded successfully`);
      setShowUpload(false);
      loadDocuments();
      loadPipeline();
    } catch (err) {
      setError(err.response?.data?.detail || `Upload failed: ${err.message}`);
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // Insert text
  const handleInsertText = async () => {
    if (!textInput.trim()) return;
    setUploading(true);
    setError(null);
    try {
      await lightragInsertText(textInput, textDescription || 'Manual text input');
      setSuccessMsg('Text inserted successfully');
      setTextInput('');
      setTextDescription('');
      setShowUpload(false);
      loadDocuments();
      loadPipeline();
    } catch (err) {
      setError(err.response?.data?.detail || `Insert failed: ${err.message}`);
    }
    setUploading(false);
  };

  // Delete document
  const handleDelete = async (docId) => {
    try {
      await lightragDeleteDocument(docId);
      setSuccessMsg(`Document deleted`);
      setDeleteConfirm(null);
      loadDocuments();
    } catch (err) {
      setError(err.response?.data?.detail || 'Delete failed');
    }
  };

  // Clear all
  const handleClear = async () => {
    try {
      await lightragClearDocuments();
      setSuccessMsg('All documents cleared');
      setClearConfirm(false);
      loadDocuments();
      loadPipeline();
    } catch (err) {
      setError(err.response?.data?.detail || 'Clear failed');
    }
  };

  // Paginate
  const paginatedDocs = documents.slice((page - 1) * pageSize, page * pageSize);
  const totalPages = Math.max(1, Math.ceil(documents.length / pageSize));

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#0f1117', color: '#e2e8f0' }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '12px 20px',
        background: '#1a1b23', borderBottom: '1px solid rgba(100,100,150,0.2)', flexWrap: 'wrap',
      }}>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: '#93c5fd' }}>
          📄 LightRAG Documents
        </h2>
        
        {/* Status counts */}
        <div style={{ display: 'flex', gap: 8, fontSize: 12 }}>
          {Object.entries(statusCounts).map(([status, count]) => (
            <span key={status} onClick={() => setStatusFilter(status === statusFilter ? '' : status)}
              style={{
                padding: '2px 8px', borderRadius: 10, cursor: 'pointer',
                background: status === statusFilter ? (STATUS_STYLES[status]?.color || '#94a3b8') : (STATUS_STYLES[status]?.bg || 'rgba(100,100,130,0.15)'),
                color: status === statusFilter ? '#fff' : (STATUS_STYLES[status]?.color || '#94a3b8'),
              }}>
              {status}: {count}
            </span>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Pipeline indicator */}
        {pipelineStatus && pipelineStatus.is_busy && (
          <span style={{
            padding: '3px 10px', borderRadius: 10, fontSize: 11,
            background: 'rgba(59,130,246,0.15)', color: '#3b82f6',
            animation: 'pulse 2s infinite',
          }}>
            ⏳ Processing: {pipelineStatus.current_task || '...'}
          </span>
        )}

        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#94a3b8', cursor: 'pointer' }}>
          <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
          Auto-refresh
        </label>
        
        <button onClick={() => setShowUpload(!showUpload)} style={primaryBtnStyle}>
          ➕ Add Document
        </button>
        <button onClick={() => setClearConfirm(true)} style={dangerBtnStyle}>
          🗑️ Clear All
        </button>
        <button onClick={() => { loadDocuments(); loadPipeline(); }} style={btnStyle}>
          🔃 Refresh
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div style={{ margin: '8px 20px', padding: '8px 16px', borderRadius: 8, background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.3)', color: '#fca5a5', fontSize: 13 }}>
          ⚠️ {error}
        </div>
      )}
      {successMsg && (
        <div style={{ margin: '8px 20px', padding: '8px 16px', borderRadius: 8, background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.3)', color: '#86efac', fontSize: 13 }}>
          ✅ {successMsg}
        </div>
      )}

      {/* Upload panel */}
      {showUpload && (
        <div style={{
          margin: '8px 20px', padding: 16, borderRadius: 10,
          background: '#1a1b23', border: '1px solid rgba(100,100,150,0.3)',
        }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
            <button onClick={() => setUploadMode('file')}
              style={{ ...tabBtnStyle, ...(uploadMode === 'file' ? activeTabStyle : {}) }}>
              📁 Upload File
            </button>
            <button onClick={() => setUploadMode('text')}
              style={{ ...tabBtnStyle, ...(uploadMode === 'text' ? activeTabStyle : {}) }}>
              📝 Insert Text
            </button>
          </div>

          {uploadMode === 'file' ? (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <div style={{
                border: '2px dashed #334155', borderRadius: 10, padding: '30px 20px',
                cursor: 'pointer', transition: 'border-color 0.2s',
              }}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = '#3b82f6'; }}
                onDragLeave={e => { e.currentTarget.style.borderColor = '#334155'; }}
                onDrop={e => {
                  e.preventDefault();
                  e.currentTarget.style.borderColor = '#334155';
                  const dt = e.dataTransfer;
                  if (dt.files.length > 0) {
                    handleFileUpload({ target: { files: dt.files } });
                  }
                }}>
                <div style={{ fontSize: 36, marginBottom: 8 }}>📤</div>
                <div style={{ color: '#94a3b8' }}>Drop files here or click to browse</div>
                <div style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>
                  Supports: PDF, DOCX, TXT, HTML, MD, CSV
                </div>
              </div>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.txt,.html,.md,.csv"
                style={{ display: 'none' }} onChange={handleFileUpload} />
              {uploading && <div style={{ color: '#3b82f6', marginTop: 8 }}>⏳ Uploading...</div>}
            </div>
          ) : (
            <div>
              <input
                placeholder="Description (optional)"
                value={textDescription}
                onChange={e => setTextDescription(e.target.value)}
                style={{ ...inputStyle, marginBottom: 8 }}
              />
              <textarea
                placeholder="Paste or type text content to index..."
                value={textInput}
                onChange={e => setTextInput(e.target.value)}
                style={{ ...inputStyle, minHeight: 120, resize: 'vertical' }}
              />
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
                <span style={{ color: '#64748b', fontSize: 11, lineHeight: '30px' }}>
                  {textInput.length} characters
                </span>
                <button onClick={handleInsertText} disabled={!textInput.trim() || uploading}
                  style={{ ...primaryBtnStyle, opacity: !textInput.trim() ? 0.5 : 1 }}>
                  {uploading ? '⏳ Inserting...' : '📥 Insert Text'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Document list */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 20px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
            <div style={{ fontSize: 24 }}>⏳</div>
            <div>Loading documents...</div>
          </div>
        ) : documents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#64748b' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📭</div>
            <div style={{ fontSize: 16 }}>No documents found</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>Upload files or insert text to build your knowledge graph</div>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(100,100,150,0.3)', fontSize: 11, color: '#94a3b8', textTransform: 'uppercase' }}>
                <th style={thStyle}>Document</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Chunks</th>
                <th style={thStyle}>Size</th>
                <th style={thStyle}>Created</th>
                <th style={{ ...thStyle, width: 80, textAlign: 'center' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {paginatedDocs.map((doc, i) => (
                <tr key={doc.id || i}
                  style={{
                    borderBottom: '1px solid rgba(100,100,150,0.1)',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.05)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td style={tdStyle}>
                    <div style={{ fontWeight: 500 }}>{doc.name || doc.id || `Document ${i + 1}`}</div>
                    {doc.source && <div style={{ fontSize: 11, color: '#64748b' }}>{doc.source}</div>}
                  </td>
                  <td style={tdStyle}>
                    <StatusBadge status={doc.status || 'unknown'} />
                  </td>
                  <td style={tdStyle}>{doc.chunks_count ?? doc.chunk_count ?? '-'}</td>
                  <td style={tdStyle}>{doc.content_length ? formatSize(doc.content_length) : '-'}</td>
                  <td style={tdStyle}>
                    <span style={{ fontSize: 12, color: '#94a3b8' }}>
                      {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '-'}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    {deleteConfirm === doc.id ? (
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'center' }}>
                        <button onClick={() => handleDelete(doc.id)} style={{ ...dangerBtnStyle, padding: '2px 6px', fontSize: 11 }}>Yes</button>
                        <button onClick={() => setDeleteConfirm(null)} style={{ ...btnStyle, padding: '2px 6px', fontSize: 11 }}>No</button>
                      </div>
                    ) : (
                      <button onClick={() => setDeleteConfirm(doc.id)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 14 }}
                        title="Delete">🗑️</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8,
          padding: '8px 20px', borderTop: '1px solid rgba(100,100,150,0.2)', fontSize: 13,
        }}>
          <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
            style={{ ...btnStyle, opacity: page <= 1 ? 0.4 : 1 }}>← Prev</button>
          <span style={{ color: '#94a3b8' }}>Page {page} of {totalPages}</span>
          <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
            style={{ ...btnStyle, opacity: page >= totalPages ? 0.4 : 1 }}>Next →</button>
        </div>
      )}

      {/* Clear confirmation modal */}
      {clearConfirm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
        }}>
          <div style={{
            background: '#1e293b', borderRadius: 12, padding: 24, maxWidth: 400, textAlign: 'center',
            border: '1px solid rgba(239,68,68,0.3)',
          }}>
            <div style={{ fontSize: 36, marginBottom: 8 }}>⚠️</div>
            <h3 style={{ color: '#fca5a5', margin: '0 0 8px' }}>Clear All Documents?</h3>
            <p style={{ color: '#94a3b8', fontSize: 13, margin: '0 0 16px' }}>
              This will permanently delete all documents and the entire knowledge graph. This action cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
              <button onClick={() => setClearConfirm(false)} style={btnStyle}>Cancel</button>
              <button onClick={handleClear} style={dangerBtnStyle}>🗑️ Yes, Clear Everything</button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}

// ============================================================
// Utilities
// ============================================================
function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ============================================================
// Styles
// ============================================================
const btnStyle = {
  background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
  padding: '5px 12px', color: '#e2e8f0', cursor: 'pointer', fontSize: 12,
};
const primaryBtnStyle = {
  background: '#2563eb', border: '1px solid #3b82f6', borderRadius: 6,
  padding: '5px 12px', color: '#fff', cursor: 'pointer', fontSize: 12, fontWeight: 500,
};
const dangerBtnStyle = {
  background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 6,
  padding: '5px 12px', color: '#fca5a5', cursor: 'pointer', fontSize: 12,
};
const tabBtnStyle = {
  background: 'transparent', border: '1px solid transparent', borderRadius: 6,
  padding: '6px 16px', color: '#94a3b8', cursor: 'pointer', fontSize: 13,
};
const activeTabStyle = {
  background: '#1e293b', borderColor: '#334155', color: '#e2e8f0',
};
const inputStyle = {
  width: '100%', background: '#0f1117', border: '1px solid #334155',
  borderRadius: 6, padding: '8px 12px', color: '#e2e8f0', fontSize: 13,
  boxSizing: 'border-box',
};
const thStyle = {
  padding: '8px 12px', textAlign: 'left', fontWeight: 500,
};
const tdStyle = {
  padding: '10px 12px', fontSize: 13,
};
