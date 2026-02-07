import React, { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { uploadDocuments, listDocuments, deleteDocument } from '../api';

function DocumentsPage({ user }) {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResults, setUploadResults] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await listDocuments();
      setDocuments(response.data.documents);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;

    setUploading(true);
    setUploadProgress(0);
    setUploadResults(null);

    try {
      const response = await uploadDocuments(acceptedFiles, (progressEvent) => {
        const progress = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        );
        setUploadProgress(progress);
      });

      setUploadResults(response.data.uploaded);
      fetchDocuments();
    } catch (err) {
      setUploadResults([{ filename: 'Upload', status: 'error', error: err.message }]);
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'application/vnd.ms-powerpoint': ['.ppt'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
      'text/csv': ['.csv'],
      'text/html': ['.html', '.htm'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
      'image/bmp': ['.bmp'],
      'image/tiff': ['.tiff', '.tif'],
      'image/gif': ['.gif'],
      'image/webp': ['.webp'],
    },
    disabled: uploading,
  });

  const handleDelete = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"?`)) return;

    try {
      await deleteDocument(docId);
      fetchDocuments();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete document');
    }
  };

  return (
    <div className="documents-page">
      <h1>Knowledge Base Documents</h1>

      <div
        {...getRootProps()}
        className={`upload-zone ${isDragActive ? 'active' : ''}`}
      >
        <input {...getInputProps()} />
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: 'var(--accent)', marginBottom: 12 }}>
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="17 8 12 3 7 8" />
          <line x1="12" y1="3" x2="12" y2="15" />
        </svg>
        <h3>{isDragActive ? 'Drop files here' : 'Drag & drop files or click to upload'}</h3>
        <p>Supported: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, HTML, Images (JPG, PNG, BMP, TIFF, GIF, WEBP)</p>
      </div>

      {uploading && (
        <div className="upload-progress">
          <div className="progress-bar">
            <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
          </div>
          <p style={{ textAlign: 'center', marginTop: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
            Uploading and processing... {uploadProgress}%
          </p>
        </div>
      )}

      {uploadResults && (
        <div style={{ marginBottom: 20 }}>
          {uploadResults.map((result, index) => (
            <div
              key={index}
              style={{
                padding: '10px 14px',
                marginBottom: 6,
                borderRadius: 'var(--radius-sm)',
                background: result.status === 'success'
                  ? 'rgba(46, 213, 115, 0.1)'
                  : 'rgba(255, 71, 87, 0.1)',
                border: `1px solid ${result.status === 'success' ? 'var(--success)' : 'var(--danger)'}`,
                fontSize: 13,
                color: result.status === 'success' ? 'var(--success)' : 'var(--danger)',
              }}
            >
              {result.filename}: {result.status === 'success'
                ? `${result.chunks} text chunks${result.multimodal_items ? `, ${result.multimodal_items} multimodal items` : ''}${result.entities ? `, ${result.entities} entities` : ''}`
                : `Error - ${result.error}`}
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>Loading documents...</p>
      ) : documents.length === 0 ? (
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40 }}>
          No documents uploaded yet. Upload documents to build the knowledge base.
        </p>
      ) : (
        <table className="documents-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Type</th>
              <th>Chunks</th>
              <th>Uploaded By</th>
              <th>Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id}>
                <td>{doc.filename}</td>
                <td>
                  <span className="file-type-badge">{doc.file_type?.replace('.', '') || 'N/A'}</span>
                </td>
                <td>{doc.num_chunks}</td>
                <td>{doc.uploaded_by}</td>
                <td>{new Date(doc.uploaded_at).toLocaleDateString()}</td>
                <td>
                  {(user.is_admin || doc.uploaded_by === user.username) && (
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleDelete(doc.id, doc.filename)}
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default DocumentsPage;
