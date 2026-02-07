import React, { useState, useEffect } from 'react';
import { getAdminStats, getAdminUsers, updateUser, deleteUser, batchProcessDocuments } from '../api';

function AdminPage({ user }) {
  const [stats, setStats] = useState(null);
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, usersRes] = await Promise.all([
        getAdminStats(),
        getAdminUsers(),
      ]);
      setStats(statsRes.data);
      setUsers(usersRes.data.users);
    } catch (err) {
      console.error('Failed to fetch admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (userId, currentStatus) => {
    try {
      await updateUser(userId, { is_active: !currentStatus });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleToggleAdmin = async (userId, currentStatus) => {
    try {
      await updateUser(userId, { is_admin: !currentStatus });
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (!window.confirm(`Are you sure you want to delete user "${username}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await deleteUser(userId);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  const handleBatchProcess = async () => {
    if (!window.confirm('Re-process all documents with multimodal extraction? This may take a while.')) return;
    setBatchProcessing(true);
    try {
      const res = await batchProcessDocuments();
      alert(`Batch processing complete: ${res.data.documents_processed} documents processed`);
      fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Batch processing failed');
    } finally {
      setBatchProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="admin-page">
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40 }}>
          Loading admin dashboard...
        </p>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <h1>Admin Dashboard</h1>

      {stats && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.users}</div>
            <div className="stat-label">Total Users</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.active_users}</div>
            <div className="stat-label">Active Users</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.documents}</div>
            <div className="stat-label">Documents</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_chunks || 0}</div>
            <div className="stat-label">Text Chunks</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.multimodal_chunks || 0}</div>
            <div className="stat-label">Multimodal Chunks</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.conversations}</div>
            <div className="stat-label">Total Conversations</div>
          </div>
          <div className="stat-card">
            <div className="stat-value" style={{ fontSize: 16 }}>{stats.llm_model}</div>
            <div className="stat-label">LLM Model</div>
          </div>
          {stats.knowledge_graph && (
            <>
              <div className="stat-card">
                <div className="stat-value">{stats.knowledge_graph.total_nodes}</div>
                <div className="stat-label">KG Entities</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.knowledge_graph.total_edges}</div>
                <div className="stat-label">KG Relationships</div>
              </div>
            </>
          )}
        </div>
      )}

      <div className="admin-section">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Multimodal Processing</h2>
          <button
            className="btn btn-primary"
            onClick={handleBatchProcess}
            disabled={batchProcessing}
          >
            {batchProcessing ? 'Processing...' : 'Re-process All Documents'}
          </button>
        </div>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
          Re-process all existing documents with multimodal content extraction (images, tables, equations).
        </p>
      </div>

      <div className="admin-section">
        <h2>User Management</h2>
        <table className="users-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Username</th>
              <th>Full Name</th>
              <th>Email</th>
              <th>Status</th>
              <th>Role</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.id}</td>
                <td><strong>{u.username}</strong></td>
                <td>{u.full_name}</td>
                <td>{u.email}</td>
                <td>
                  <span className={`status-badge ${u.is_active ? 'active' : 'inactive'}`}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td>
                  <span className={`status-badge ${u.is_admin ? 'admin' : 'active'}`}>
                    {u.is_admin ? 'Admin' : 'User'}
                  </span>
                </td>
                <td>{new Date(u.created_at).toLocaleDateString()}</td>
                <td>
                  {u.id !== user.id && (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => handleToggleActive(u.id, u.is_active)}
                      >
                        {u.is_active ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => handleToggleAdmin(u.id, u.is_admin)}
                      >
                        {u.is_admin ? 'Demote' : 'Promote'}
                      </button>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeleteUser(u.id, u.username)}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default AdminPage;
