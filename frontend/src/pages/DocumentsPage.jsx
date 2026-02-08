import React, { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  uploadDocuments, listDocuments, deleteDocument,
  listFolders, createFolder, deleteFolder, moveDocument,
  listTags, createTag, deleteTag, setDocumentTags,
  uploadDocumentVersion, getDocumentVersions,
  searchDocumentsAdvanced, exportDocumentsList
} from '../api';
import LightRAGDocumentsPage from './LightRAGDocumentsPage';

function DocumentsPage({ user }) {
  // Tab: 'documents' | 'lightrag'
  const [activeTab, setActiveTab] = useState('documents');
  const [documents, setDocuments] = useState([]);
  const [folders, setFolders] = useState([]);
  const [tags, setTags] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResults, setUploadResults] = useState(null);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterFolder, setFilterFolder] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [sortOrder, setSortOrder] = useState('desc');

  // Modals
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderColor, setNewFolderColor] = useState('#4f8cff');
  const [showNewTag, setShowNewTag] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [newTagColor, setNewTagColor] = useState('#4f8cff');
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [showVersions, setShowVersions] = useState(null);
  const [versions, setVersions] = useState([]);
  const [showTagEditor, setShowTagEditor] = useState(null);
  const [selectedTagIds, setSelectedTagIds] = useState([]);
  const [showMoveModal, setShowMoveModal] = useState(null);

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      const [docsRes, foldersRes, tagsRes] = await Promise.all([
        listDocuments(), listFolders(), listTags()
      ]);
      setDocuments(docsRes.data.documents || []);
      setFolders(foldersRes.data.folders || []);
      setTags(tagsRes.data.tags || []);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    setUploading(true); setUploadProgress(0); setUploadResults(null);
    try {
      const response = await uploadDocuments(acceptedFiles, (e) => {
        setUploadProgress(Math.round((e.loaded * 100) / e.total));
      }, selectedFolder);
      setUploadResults(response.data.uploaded);
      fetchAll();
    } catch (err) {
      setUploadResults([{ filename: 'Upload', status: 'error', error: err.message }]);
    } finally {
      setUploading(false);
    }
  }, [selectedFolder]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'], 'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'application/vnd.ms-powerpoint': ['.ppt'],
      'text/plain': ['.txt'], 'text/markdown': ['.md'], 'text/csv': ['.csv'],
      'text/html': ['.html', '.htm'],
      'image/jpeg': ['.jpg', '.jpeg'], 'image/png': ['.png'], 'image/bmp': ['.bmp'],
      'image/tiff': ['.tiff', '.tif'], 'image/gif': ['.gif'], 'image/webp': ['.webp'],
    },
    disabled: uploading,
  });

  const handleDelete = async (docId, filename) => {
    if (!window.confirm(`Delete "${filename}"?`)) return;
    try { await deleteDocument(docId); fetchAll(); }
    catch (err) { alert(err.response?.data?.detail || 'Failed to delete'); }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      await createFolder(newFolderName, null, newFolderColor);
      setNewFolderName(''); setShowNewFolder(false); fetchAll();
    } catch (err) { alert(err.response?.data?.detail || 'Failed to create folder'); }
  };

  const handleDeleteFolder = async (folderId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this folder? Documents will be moved to root.')) return;
    try { await deleteFolder(folderId); fetchAll(); }
    catch (err) { alert(err.response?.data?.detail || 'Failed to delete folder'); }
  };

  const handleCreateTag = async () => {
    if (!newTagName.trim()) return;
    try {
      await createTag(newTagName, newTagColor);
      setNewTagName(''); setShowNewTag(false); fetchAll();
    } catch (err) { alert(err.response?.data?.detail || 'Failed to create tag'); }
  };

  const handleDeleteTag = async (tagId) => {
    if (!window.confirm('Delete this tag?')) return;
    try { await deleteTag(tagId); fetchAll(); }
    catch (err) { alert(err.response?.data?.detail || 'Failed'); }
  };

  const handleMoveDocument = async (docId, folderId) => {
    try { await moveDocument(docId, folderId); setShowMoveModal(null); fetchAll(); }
    catch (err) { alert('Failed to move document'); }
  };

  const handleSetTags = async (docId) => {
    try { await setDocumentTags(docId, selectedTagIds); setShowTagEditor(null); fetchAll(); }
    catch (err) { alert('Failed to set tags'); }
  };

  const handleViewVersions = async (docId) => {
    try {
      const res = await getDocumentVersions(docId);
      setVersions(res.data.versions || []);
      setShowVersions(docId);
    } catch (err) { console.error(err); }
  };

  const handleVersionUpload = async (docId, file) => {
    try {
      await uploadDocumentVersion(docId, file, 'New version');
      handleViewVersions(docId); fetchAll();
    } catch (err) { alert('Failed to upload version'); }
  };

  const handleExport = async (format) => {
    try {
      const response = await exportDocumentsList(format);
      const blob = new Blob([response.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `documents.${format}`; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { console.error('Export failed:', err); }
  };

  // Filter documents
  const filteredDocs = documents.filter(doc => {
    if (searchQuery && !doc.filename.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    if (filterType && doc.file_type !== filterType) return false;
    if (filterFolder === '0' && doc.folder_id !== null) return false;
    if (filterFolder && filterFolder !== '0' && doc.folder_id !== parseInt(filterFolder)) return false;
    if (filterTag && !(doc.tags || []).some(t => t.id === parseInt(filterTag))) return false;
    return true;
  }).sort((a, b) => {
    let cmp = 0;
    if (sortBy === 'name') cmp = a.filename.localeCompare(b.filename);
    else if (sortBy === 'size') cmp = (a.file_size_mb || 0) - (b.file_size_mb || 0);
    else if (sortBy === 'type') cmp = (a.file_type || '').localeCompare(b.file_type || '');
    else cmp = new Date(a.uploaded_at) - new Date(b.uploaded_at);
    return sortOrder === 'desc' ? -cmp : cmp;
  });

  const fileTypes = [...new Set(documents.map(d => d.file_type).filter(Boolean))];

  return (
    <div className="documents-page">
      {/* Tab Switcher */}
      <div style={{
        display: 'flex', gap: 0, marginBottom: 0, borderBottom: '1px solid var(--border)',
        background: 'var(--bg-secondary)', padding: '0 16px',
      }}>
        <button
          onClick={() => setActiveTab('documents')}
          style={{
            padding: '12px 20px', border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500,
            background: activeTab === 'documents' ? 'var(--bg-primary)' : 'transparent',
            color: activeTab === 'documents' ? 'var(--accent)' : 'var(--text-secondary)',
            borderBottom: activeTab === 'documents' ? '2px solid var(--accent)' : '2px solid transparent',
            transition: 'all 0.2s',
          }}
        >📁 Documents</button>
        <button
          onClick={() => setActiveTab('lightrag')}
          style={{
            padding: '12px 20px', border: 'none', cursor: 'pointer', fontSize: 14, fontWeight: 500,
            background: activeTab === 'lightrag' ? 'var(--bg-primary)' : 'transparent',
            color: activeTab === 'lightrag' ? '#eab308' : 'var(--text-secondary)',
            borderBottom: activeTab === 'lightrag' ? '2px solid #eab308' : '2px solid transparent',
            transition: 'all 0.2s',
          }}
        >⚡ LightRAG Index</button>
      </div>

      {activeTab === 'lightrag' ? (
        <LightRAGDocumentsPage />
      ) : (
      <>
      <div className="docs-header">
        <h1>Knowledge Base</h1>
        <div className="docs-header-actions">
          <button className="btn btn-outline btn-sm" onClick={() => handleExport('csv')}>📥 Export CSV</button>
          <button className="btn btn-outline btn-sm" onClick={() => handleExport('json')}>📥 Export JSON</button>
        </div>
      </div>

      {/* Folders Bar */}
      <div className="folders-bar">
        <div className="folders-list">
          <div className={`folder-chip ${selectedFolder === null ? 'active' : ''}`}
            onClick={() => { setSelectedFolder(null); setFilterFolder(''); }}>
            📁 All
          </div>
          <div className={`folder-chip ${filterFolder === '0' ? 'active' : ''}`}
            onClick={() => { setSelectedFolder(0); setFilterFolder('0'); }}>
            📄 Unfiled
          </div>
          {folders.map(f => (
            <div key={f.id} className={`folder-chip ${selectedFolder === f.id ? 'active' : ''}`}
              style={{ borderColor: f.color }}
              onClick={() => { setSelectedFolder(f.id); setFilterFolder(String(f.id)); }}>
              <span className="folder-dot" style={{ background: f.color }}></span>
              {f.name} ({f.document_count})
              <button className="folder-delete-btn" onClick={(e) => handleDeleteFolder(f.id, e)}>×</button>
            </div>
          ))}
          <button className="folder-add-btn" onClick={() => setShowNewFolder(true)}>+ Folder</button>
        </div>
      </div>

      {showNewFolder && (
        <div className="inline-form">
          <input value={newFolderName} onChange={e => setNewFolderName(e.target.value)}
            placeholder="Folder name" className="input-sm" />
          <input type="color" value={newFolderColor} onChange={e => setNewFolderColor(e.target.value)} />
          <button className="btn btn-primary btn-sm" onClick={handleCreateFolder}>Create</button>
          <button className="btn btn-outline btn-sm" onClick={() => setShowNewFolder(false)}>Cancel</button>
        </div>
      )}

      {/* Tags Bar */}
      <div className="tags-bar">
        <div className="tags-list">
          <span className="tags-label">Tags:</span>
          {tags.map(t => (
            <span key={t.id}
              className={`tag-chip ${filterTag === String(t.id) ? 'active' : ''}`}
              style={{ borderColor: t.color, color: filterTag === String(t.id) ? '#fff' : t.color,
                background: filterTag === String(t.id) ? t.color : 'transparent' }}
              onClick={() => setFilterTag(filterTag === String(t.id) ? '' : String(t.id))}>
              {t.name} ({t.document_count})
              <button className="tag-delete-btn" onClick={(e) => { e.stopPropagation(); handleDeleteTag(t.id); }}>×</button>
            </span>
          ))}
          <button className="tag-add-btn" onClick={() => setShowNewTag(true)}>+ Tag</button>
        </div>
      </div>

      {showNewTag && (
        <div className="inline-form">
          <input value={newTagName} onChange={e => setNewTagName(e.target.value)}
            placeholder="Tag name" className="input-sm" />
          <input type="color" value={newTagColor} onChange={e => setNewTagColor(e.target.value)} />
          <button className="btn btn-primary btn-sm" onClick={handleCreateTag}>Create</button>
          <button className="btn btn-outline btn-sm" onClick={() => setShowNewTag(false)}>Cancel</button>
        </div>
      )}

      {/* Upload Zone */}
      <div {...getRootProps()} className={`upload-zone ${isDragActive ? 'active' : ''}`}>
        <input {...getInputProps()} />
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--accent)', marginBottom: 12 }}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <h3>{isDragActive ? 'Drop files here' : 'Drag & drop files or click to upload'}</h3>
        <p>Supported: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, HTML, Images</p>
        {selectedFolder && selectedFolder !== 0 && (
          <p style={{ color: 'var(--accent)', fontSize: 12 }}>
            Uploading to: {folders.find(f => f.id === selectedFolder)?.name || 'Root'}
          </p>
        )}
      </div>

      {uploading && (
        <div className="upload-progress">
          <div className="progress-bar"><div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} /></div>
          <p style={{ textAlign: 'center', marginTop: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
            Uploading... {uploadProgress}%
          </p>
        </div>
      )}

      {uploadResults && (
        <div style={{ marginBottom: 20 }}>
          {uploadResults.map((result, index) => (
            <div key={index} style={{
              padding: '10px 14px', marginBottom: 6, borderRadius: 'var(--radius-sm)',
              background: result.status === 'success' ? 'rgba(46,213,115,0.1)' : 'rgba(255,71,87,0.1)',
              border: `1px solid ${result.status === 'success' ? 'var(--success)' : 'var(--danger)'}`,
              fontSize: 13, color: result.status === 'success' ? 'var(--success)' : 'var(--danger)',
            }}>
              {result.filename}: {result.status === 'success'
                ? `${result.chunks} chunks${result.multimodal_items ? `, ${result.multimodal_items} multimodal` : ''}${result.entities ? `, ${result.entities} entities` : ''}`
                : `Error - ${result.error}`}
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="docs-filters">
        <input type="text" placeholder="Search documents..." value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)} className="filter-input" />
        <select value={filterType} onChange={e => setFilterType(e.target.value)} className="filter-select">
          <option value="">All Types</option>
          {fileTypes.map(t => <option key={t} value={t}>{t?.replace('.', '')}</option>)}
        </select>
        <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="filter-select">
          <option value="date">Sort: Date</option>
          <option value="name">Sort: Name</option>
          <option value="size">Sort: Size</option>
          <option value="type">Sort: Type</option>
        </select>
        <button className="btn btn-outline btn-sm" onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}>
          {sortOrder === 'desc' ? '↓' : '↑'}
        </button>
      </div>

      {/* Documents Table */}
      {loading ? (
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>Loading...</p>
      ) : filteredDocs.length === 0 ? (
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40 }}>
          No documents found.
        </p>
      ) : (
        <table className="documents-table">
          <thead>
            <tr>
              <th>Filename</th><th>Type</th><th>Chunks</th><th>Ver</th><th>Tags</th><th>Uploaded By</th><th>Date</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredDocs.map(doc => (
              <tr key={doc.id}>
                <td>
                  <div className="doc-name">
                    {doc.filename}
                    {doc.folder_id && (
                      <span className="doc-folder-badge" style={{ borderColor: folders.find(f => f.id === doc.folder_id)?.color || '#666' }}>
                        📁 {folders.find(f => f.id === doc.folder_id)?.name || 'Unknown'}
                      </span>
                    )}
                  </div>
                </td>
                <td><span className="file-type-badge">{doc.file_type?.replace('.', '') || 'N/A'}</span></td>
                <td>{doc.num_chunks}</td>
                <td><span className="version-badge">v{doc.version || 1}</span></td>
                <td>
                  <div className="doc-tags">
                    {(doc.tags || []).map((t, i) => (
                      <span key={i} className="doc-tag-chip">{t.name}</span>
                    ))}
                  </div>
                </td>
                <td>{doc.uploaded_by}</td>
                <td>{new Date(doc.uploaded_at).toLocaleDateString()}</td>
                <td>
                  <div className="doc-actions">
                    <button className="btn btn-outline btn-sm" onClick={() => handleViewVersions(doc.id)} title="Versions">📋</button>
                    <button className="btn btn-outline btn-sm" onClick={() => {
                      setShowTagEditor(doc.id);
                      setSelectedTagIds((doc.tags || []).map(t => t.id));
                    }} title="Tags">🏷️</button>
                    <button className="btn btn-outline btn-sm" onClick={() => setShowMoveModal(doc.id)} title="Move">📁</button>
                    {(user.is_admin || doc.uploaded_by === user.username) && (
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(doc.id, doc.filename)}>Delete</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Version Modal */}
      {showVersions && (
        <div className="modal-overlay" onClick={() => setShowVersions(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Document Versions</h3>
            <div className="version-upload">
              <label className="btn btn-primary btn-sm">
                Upload New Version
                <input type="file" hidden onChange={e => {
                  if (e.target.files[0]) handleVersionUpload(showVersions, e.target.files[0]);
                }} />
              </label>
            </div>
            {versions.length === 0 ? <p style={{ color: 'var(--text-secondary)' }}>No previous versions</p> : (
              <div className="versions-list">
                {versions.map((v, i) => (
                  <div key={i} className="version-item">
                    <div className="version-number">v{v.version_number}</div>
                    <div className="version-info">
                      <div>{v.filename}</div>
                      <div className="version-meta">{v.uploaded_by} · {new Date(v.created_at).toLocaleDateString()}</div>
                      {v.change_note && <div className="version-note">{v.change_note}</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
            <button className="btn btn-outline" onClick={() => setShowVersions(null)} style={{ marginTop: 12 }}>Close</button>
          </div>
        </div>
      )}

      {/* Tag Editor Modal */}
      {showTagEditor && (
        <div className="modal-overlay" onClick={() => setShowTagEditor(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Edit Document Tags</h3>
            <div className="tag-selector">
              {tags.map(t => (
                <label key={t.id} className="tag-checkbox">
                  <input type="checkbox" checked={selectedTagIds.includes(t.id)}
                    onChange={e => {
                      if (e.target.checked) setSelectedTagIds(prev => [...prev, t.id]);
                      else setSelectedTagIds(prev => prev.filter(id => id !== t.id));
                    }} />
                  <span style={{ color: t.color }}>{t.name}</span>
                </label>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button className="btn btn-primary btn-sm" onClick={() => handleSetTags(showTagEditor)}>Save</button>
              <button className="btn btn-outline btn-sm" onClick={() => setShowTagEditor(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Move Modal */}
      {showMoveModal && (
        <div className="modal-overlay" onClick={() => setShowMoveModal(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Move Document to Folder</h3>
            <div className="move-folder-list">
              <div className="move-folder-item" onClick={() => handleMoveDocument(showMoveModal, null)}>
                📄 Root (No folder)
              </div>
              {folders.map(f => (
                <div key={f.id} className="move-folder-item" onClick={() => handleMoveDocument(showMoveModal, f.id)}>
                  <span className="folder-dot" style={{ background: f.color }}></span>
                  {f.name}
                </div>
              ))}
            </div>
            <button className="btn btn-outline" onClick={() => setShowMoveModal(null)} style={{ marginTop: 12 }}>Cancel</button>
          </div>
        </div>
      )}
      </>
      )}
    </div>
  );
}

export default DocumentsPage;
