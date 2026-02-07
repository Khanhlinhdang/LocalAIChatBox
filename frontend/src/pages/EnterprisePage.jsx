import React, { useState, useEffect, useCallback } from 'react';
import {
  getEnterpriseDashboard, listRoles, createRole, updateRole, deleteRole,
  assignRole, removeRole, getUserRoles, listAllPermissions,
  listTenants, createTenant, updateTenant, deleteTenant, assignUserToTenant,
  getAuditLogs, getComplianceReport, gdprExportData, gdprDeleteData,
  getLDAPStatus, getLDAPConfig, getEncryptionStatus, generateEncryptionKey,
  exportAuditCSV, getAdminUsers
} from '../api';

const TABS = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'roles', label: 'Roles & RBAC' },
  { id: 'tenants', label: 'Multi-Tenancy' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'audit', label: 'Audit Logs' },
  { id: 'security', label: 'Security' },
];

function EnterprisePage({ user }) {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Dashboard
  const [dashboard, setDashboard] = useState(null);

  // Roles
  const [roles, setRoles] = useState([]);
  const [allPermissions, setAllPermissions] = useState([]);
  const [users, setUsers] = useState([]);
  const [showCreateRole, setShowCreateRole] = useState(false);
  const [newRole, setNewRole] = useState({ name: '', description: '', permissions: [] });
  const [showAssignRole, setShowAssignRole] = useState(false);
  const [assignData, setAssignData] = useState({ user_id: '', role_name: '' });

  // Tenants
  const [tenants, setTenants] = useState([]);
  const [showCreateTenant, setShowCreateTenant] = useState(false);
  const [newTenant, setNewTenant] = useState({ name: '', slug: '', description: '', max_users: 0 });
  const [showAssignTenant, setShowAssignTenant] = useState(false);
  const [assignTenantData, setAssignTenantData] = useState({ user_id: '', tenant_id: '' });

  // Compliance
  const [complianceReport, setComplianceReport] = useState(null);
  const [gdprUserId, setGdprUserId] = useState('');

  // Audit
  const [auditLogs, setAuditLogs] = useState({ logs: [], total: 0 });
  const [auditFilter, setAuditFilter] = useState({ action: '', limit: 50, offset: 0 });

  // Security
  const [ldapStatus, setLdapStatus] = useState(null);
  const [ldapConfig, setLdapConfig] = useState(null);
  const [encryptionStatus, setEncryptionStatus] = useState(null);

  const showMsg = (msg, isError = false) => {
    if (isError) { setError(msg); setSuccess(''); }
    else { setSuccess(msg); setError(''); }
    setTimeout(() => { setError(''); setSuccess(''); }, 4000);
  };

  // =============== LOADERS ===============

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getEnterpriseDashboard();
      setDashboard(res.data);
    } catch { showMsg('Failed to load dashboard', true); }
    setLoading(false);
  }, []);

  const loadRoles = useCallback(async () => {
    try {
      const [rolesRes, permsRes, usersRes] = await Promise.all([
        listRoles(), listAllPermissions(), getAdminUsers()
      ]);
      setRoles(rolesRes.data.roles || []);
      setAllPermissions(permsRes.data.permissions || []);
      setUsers(usersRes.data.users || usersRes.data || []);
    } catch { showMsg('Failed to load roles', true); }
  }, []);

  const loadTenants = useCallback(async () => {
    try {
      const res = await listTenants();
      setTenants(res.data.tenants || []);
    } catch { showMsg('Failed to load tenants', true); }
  }, []);

  const loadAuditLogs = useCallback(async () => {
    try {
      const res = await getAuditLogs(auditFilter);
      setAuditLogs(res.data);
    } catch { showMsg('Failed to load audit logs', true); }
  }, [auditFilter]);

  const loadSecurity = useCallback(async () => {
    try {
      const [ldapSt, ldapCf, encSt] = await Promise.all([
        getLDAPStatus().catch(() => ({ data: { status: 'error' } })),
        getLDAPConfig().catch(() => ({ data: {} })),
        getEncryptionStatus().catch(() => ({ data: { enabled: false } })),
      ]);
      setLdapStatus(ldapSt.data);
      setLdapConfig(ldapCf.data);
      setEncryptionStatus(encSt.data);
    } catch { showMsg('Failed to load security status', true); }
  }, []);

  const loadCompliance = useCallback(async () => {
    try {
      const res = await getComplianceReport('general');
      setComplianceReport(res.data);
    } catch { showMsg('Failed to load compliance report', true); }
  }, []);

  useEffect(() => {
    const loaders = {
      dashboard: loadDashboard,
      roles: loadRoles,
      tenants: loadTenants,
      compliance: loadCompliance,
      audit: loadAuditLogs,
      security: loadSecurity,
    };
    loaders[activeTab]?.();
  }, [activeTab, loadDashboard, loadRoles, loadTenants, loadCompliance, loadAuditLogs, loadSecurity]);

  // =============== HANDLERS ===============

  const handleCreateRole = async () => {
    if (!newRole.name) return showMsg('Name required', true);
    try {
      await createRole(newRole.name, newRole.description, newRole.permissions);
      showMsg('Role created');
      setShowCreateRole(false);
      setNewRole({ name: '', description: '', permissions: [] });
      loadRoles();
    } catch (e) { showMsg(e.response?.data?.detail || 'Failed', true); }
  };

  const handleDeleteRole = async (roleId) => {
    if (!window.confirm('Delete this role?')) return;
    try {
      await deleteRole(roleId);
      showMsg('Role deleted');
      loadRoles();
    } catch (e) { showMsg(e.response?.data?.detail || 'Failed', true); }
  };

  const handleAssignRole = async () => {
    if (!assignData.user_id || !assignData.role_name) return showMsg('Select user and role', true);
    try {
      await assignRole(parseInt(assignData.user_id), assignData.role_name);
      showMsg('Role assigned');
      setShowAssignRole(false);
      setAssignData({ user_id: '', role_name: '' });
    } catch (e) { showMsg(e.response?.data?.detail || 'Failed', true); }
  };

  const handleCreateTenant = async () => {
    if (!newTenant.name || !newTenant.slug) return showMsg('Name and slug required', true);
    try {
      await createTenant(newTenant);
      showMsg('Tenant created');
      setShowCreateTenant(false);
      setNewTenant({ name: '', slug: '', description: '', max_users: 0 });
      loadTenants();
    } catch (e) { showMsg(e.response?.data?.detail || 'Failed', true); }
  };

  const handleDeleteTenant = async (tenantId) => {
    if (!window.confirm('Delete this tenant?')) return;
    try {
      await deleteTenant(tenantId);
      showMsg('Tenant deleted');
      loadTenants();
    } catch (e) { showMsg(e.response?.data?.detail || 'Failed', true); }
  };

  const handleAssignTenant = async () => {
    if (!assignTenantData.user_id || !assignTenantData.tenant_id) return showMsg('Select user and tenant', true);
    try {
      await assignUserToTenant(parseInt(assignTenantData.user_id), parseInt(assignTenantData.tenant_id));
      showMsg('User assigned to tenant');
      setShowAssignTenant(false);
    } catch (e) { showMsg(e.response?.data?.detail || 'Failed', true); }
  };

  const handleGDPRExport = async () => {
    if (!gdprUserId) return showMsg('Enter user ID', true);
    try {
      const res = await gdprExportData(parseInt(gdprUserId));
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `gdpr_export_user_${gdprUserId}.json`; a.click();
      showMsg('Data exported');
    } catch (e) { showMsg(e.response?.data?.detail || 'Export failed', true); }
  };

  const handleGDPRDelete = async () => {
    if (!gdprUserId) return showMsg('Enter user ID', true);
    if (!window.confirm(`DELETE ALL DATA for user ${gdprUserId}? This cannot be undone!`)) return;
    try {
      await gdprDeleteData(parseInt(gdprUserId), true);
      showMsg('User data deleted (GDPR)');
    } catch (e) { showMsg(e.response?.data?.detail || 'Deletion failed', true); }
  };

  const handleExportAuditCSV = async () => {
    try {
      const res = await exportAuditCSV();
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url; a.download = 'audit_logs.csv'; a.click();
      showMsg('Audit CSV exported');
    } catch { showMsg('Export failed', true); }
  };

  const handleGenerateKey = async () => {
    try {
      const res = await generateEncryptionKey();
      window.prompt('Generated encryption key (save securely):', res.data.key);
    } catch { showMsg('Key generation failed', true); }
  };

  const togglePermission = (perm) => {
    setNewRole(prev => {
      const perms = prev.permissions.includes(perm)
        ? prev.permissions.filter(p => p !== perm)
        : [...prev.permissions, perm];
      return { ...prev, permissions: perms };
    });
  };

  // =============== RENDER ===============

  const renderDashboard = () => {
    if (!dashboard) return <div className="loading-text">Loading...</div>;
    const { stats, encryption, ldap, recent_activity } = dashboard;
    return (
      <div className="enterprise-dashboard">
        <div className="stats-grid">
          <div className="stat-card"><div className="stat-value">{stats.total_users}</div><div className="stat-label">Users</div></div>
          <div className="stat-card"><div className="stat-value">{stats.total_roles}</div><div className="stat-label">Roles</div></div>
          <div className="stat-card"><div className="stat-value">{stats.total_tenants}</div><div className="stat-label">Tenants</div></div>
          <div className="stat-card"><div className="stat-value">{stats.total_documents}</div><div className="stat-label">Documents</div></div>
          <div className="stat-card"><div className="stat-value">{stats.total_permissions}</div><div className="stat-label">Doc Permissions</div></div>
        </div>
        <div className="dashboard-row">
          <div className="dashboard-card">
            <h3>Security Status</h3>
            <div className="status-list">
              <div className="status-item">
                <span>Encryption at Rest</span>
                <span className={`status-badge ${encryption?.enabled ? 'active' : 'inactive'}`}>
                  {encryption?.enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
              <div className="status-item">
                <span>LDAP / SSO</span>
                <span className={`status-badge ${ldap?.enabled ? 'active' : 'inactive'}`}>
                  {ldap?.enabled ? 'ENABLED' : 'DISABLED'}
                </span>
              </div>
              <div className="status-item">
                <span>RBAC</span>
                <span className="status-badge active">ENABLED</span>
              </div>
              <div className="status-item">
                <span>Audit Logging</span>
                <span className="status-badge active">ENABLED</span>
              </div>
            </div>
          </div>
          <div className="dashboard-card">
            <h3>Recent Activity</h3>
            <div className="activity-list">
              {(recent_activity || []).map((a, i) => (
                <div key={i} className="activity-item">
                  <span className="activity-action">{a.action}</span>
                  <span className="activity-type">{a.resource_type}</span>
                  <span className="activity-time">{a.created_at ? new Date(a.created_at).toLocaleString() : ''}</span>
                </div>
              ))}
              {(!recent_activity || recent_activity.length === 0) && <div className="empty-text">No recent activity</div>}
            </div>
          </div>
        </div>
      </div>
    );
  };

  const renderRoles = () => (
    <div className="enterprise-section">
      <div className="section-header">
        <h3>Roles & RBAC</h3>
        <div className="header-actions">
          <button className="btn btn-primary btn-sm" onClick={() => setShowAssignRole(true)}>Assign Role</button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowCreateRole(true)}>Create Role</button>
        </div>
      </div>

      {showCreateRole && (
        <div className="modal-overlay" onClick={() => setShowCreateRole(false)}>
          <div className="modal-content modal-large" onClick={e => e.stopPropagation()}>
            <h3>Create Role</h3>
            <input placeholder="Role name" value={newRole.name} onChange={e => setNewRole({...newRole, name: e.target.value})} className="input" />
            <input placeholder="Description" value={newRole.description} onChange={e => setNewRole({...newRole, description: e.target.value})} className="input" style={{marginTop: 8}} />
            <div className="permissions-grid" style={{marginTop: 12}}>
              <label style={{fontWeight: 600, marginBottom: 4}}>Permissions:</label>
              {allPermissions.map(p => (
                <label key={p.value} className="permission-checkbox">
                  <input type="checkbox" checked={newRole.permissions.includes(p.value)} onChange={() => togglePermission(p.value)} />
                  {p.value}
                </label>
              ))}
            </div>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleCreateRole}>Create</button>
              <button className="btn btn-outline" onClick={() => setShowCreateRole(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {showAssignRole && (
        <div className="modal-overlay" onClick={() => setShowAssignRole(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Assign Role to User</h3>
            <select className="input" value={assignData.user_id} onChange={e => setAssignData({...assignData, user_id: e.target.value})}>
              <option value="">Select user</option>
              {users.map(u => <option key={u.id} value={u.id}>{u.username} ({u.full_name})</option>)}
            </select>
            <select className="input" style={{marginTop: 8}} value={assignData.role_name} onChange={e => setAssignData({...assignData, role_name: e.target.value})}>
              <option value="">Select role</option>
              {roles.map(r => <option key={r.id} value={r.name}>{r.name}</option>)}
            </select>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleAssignRole}>Assign</button>
              <button className="btn btn-outline" onClick={() => setShowAssignRole(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="table-container">
        <table>
          <thead><tr><th>Role</th><th>Description</th><th>System</th><th>Permissions</th><th>Actions</th></tr></thead>
          <tbody>
            {roles.map(role => (
              <tr key={role.id}>
                <td><strong>{role.name}</strong></td>
                <td>{role.description}</td>
                <td>{role.is_system ? '✓' : '—'}</td>
                <td><span className="permissions-count">{role.permissions?.length || 0} permissions</span></td>
                <td>
                  {!role.is_system && (
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeleteRole(role.id)}>Delete</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderTenants = () => (
    <div className="enterprise-section">
      <div className="section-header">
        <h3>Multi-Tenancy</h3>
        <div className="header-actions">
          <button className="btn btn-primary btn-sm" onClick={() => setShowAssignTenant(true)}>Assign User</button>
          <button className="btn btn-primary btn-sm" onClick={() => setShowCreateTenant(true)}>Create Tenant</button>
        </div>
      </div>

      {showCreateTenant && (
        <div className="modal-overlay" onClick={() => setShowCreateTenant(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Create Tenant</h3>
            <input placeholder="Tenant name" value={newTenant.name} onChange={e => setNewTenant({...newTenant, name: e.target.value})} className="input" />
            <input placeholder="Slug (url-friendly)" value={newTenant.slug} onChange={e => setNewTenant({...newTenant, slug: e.target.value})} className="input" style={{marginTop: 8}} />
            <input placeholder="Description" value={newTenant.description} onChange={e => setNewTenant({...newTenant, description: e.target.value})} className="input" style={{marginTop: 8}} />
            <input type="number" placeholder="Max users (0=unlimited)" value={newTenant.max_users} onChange={e => setNewTenant({...newTenant, max_users: parseInt(e.target.value) || 0})} className="input" style={{marginTop: 8}} />
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleCreateTenant}>Create</button>
              <button className="btn btn-outline" onClick={() => setShowCreateTenant(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {showAssignTenant && (
        <div className="modal-overlay" onClick={() => setShowAssignTenant(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h3>Assign User to Tenant</h3>
            <select className="input" value={assignTenantData.user_id} onChange={e => setAssignTenantData({...assignTenantData, user_id: e.target.value})}>
              <option value="">Select user</option>
              {users.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
            </select>
            <select className="input" style={{marginTop: 8}} value={assignTenantData.tenant_id} onChange={e => setAssignTenantData({...assignTenantData, tenant_id: e.target.value})}>
              <option value="">Select tenant</option>
              {tenants.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            <div className="modal-actions">
              <button className="btn btn-primary" onClick={handleAssignTenant}>Assign</button>
              <button className="btn btn-outline" onClick={() => setShowAssignTenant(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      <div className="table-container">
        <table>
          <thead><tr><th>Name</th><th>Slug</th><th>Users</th><th>Documents</th><th>Max Users</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {tenants.map(t => (
              <tr key={t.id}>
                <td><strong>{t.name}</strong></td>
                <td><code>{t.slug}</code></td>
                <td>{t.user_count}</td>
                <td>{t.document_count}</td>
                <td>{t.max_users === 0 ? '∞' : t.max_users}</td>
                <td><span className={`status-badge ${t.is_active ? 'active' : 'inactive'}`}>{t.is_active ? 'Active' : 'Inactive'}</span></td>
                <td><button className="btn btn-danger btn-sm" onClick={() => handleDeleteTenant(t.id)}>Delete</button></td>
              </tr>
            ))}
            {tenants.length === 0 && <tr><td colSpan="7" className="empty-text">No tenants created yet</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );

  const renderCompliance = () => (
    <div className="enterprise-section">
      <div className="section-header">
        <h3>Compliance & GDPR</h3>
      </div>

      {complianceReport && (
        <div className="compliance-report">
          <div className="stats-grid">
            <div className="stat-card"><div className="stat-value">{complianceReport.users?.total}</div><div className="stat-label">Total Users</div></div>
            <div className="stat-card"><div className="stat-value">{complianceReport.users?.active}</div><div className="stat-label">Active Users</div></div>
            <div className="stat-card"><div className="stat-value">{complianceReport.documents?.total}</div><div className="stat-label">Documents</div></div>
            <div className="stat-card"><div className="stat-value">{complianceReport.audit_activity?.total_actions_30d}</div><div className="stat-label">Actions (30d)</div></div>
          </div>

          <div className="dashboard-row">
            <div className="dashboard-card">
              <h3>Compliance Status</h3>
              <div className="status-list">
                {complianceReport.compliance_status && Object.entries(complianceReport.compliance_status).map(([key, val]) => (
                  <div key={key} className="status-item">
                    <span>{key.replace(/_/g, ' ')}</span>
                    <span className={`status-badge ${val ? 'active' : 'inactive'}`}>{val ? 'YES' : 'NO'}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="dashboard-card">
              <h3>GDPR Operations</h3>
              <div className="gdpr-section">
                <div className="gdpr-row">
                  <input type="number" placeholder="User ID" value={gdprUserId} onChange={e => setGdprUserId(e.target.value)} className="input input-sm" />
                  <button className="btn btn-primary btn-sm" onClick={handleGDPRExport}>Export Data (Art. 15)</button>
                  <button className="btn btn-danger btn-sm" onClick={handleGDPRDelete}>Delete Data (Art. 17)</button>
                </div>
                <div className="gdpr-stats">
                  <span>Exports (30d): {complianceReport.gdpr?.data_export_requests_30d || 0}</span>
                  <span>Deletions (30d): {complianceReport.gdpr?.data_deletion_requests_30d || 0}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderAudit = () => (
    <div className="enterprise-section">
      <div className="section-header">
        <h3>Audit Logs</h3>
        <div className="header-actions">
          <button className="btn btn-primary btn-sm" onClick={handleExportAuditCSV}>Export CSV</button>
        </div>
      </div>

      <div className="audit-filters">
        <input placeholder="Filter by action" value={auditFilter.action} onChange={e => setAuditFilter({...auditFilter, action: e.target.value})} className="input input-sm" />
        <button className="btn btn-outline btn-sm" onClick={loadAuditLogs}>Apply</button>
        <span className="audit-total">Total: {auditLogs.total}</span>
      </div>

      <div className="table-container">
        <table>
          <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Resource</th><th>Details</th><th>IP</th></tr></thead>
          <tbody>
            {(auditLogs.logs || []).map(log => (
              <tr key={log.id}>
                <td className="nowrap">{log.created_at ? new Date(log.created_at).toLocaleString() : ''}</td>
                <td>{log.user_id}</td>
                <td><code>{log.action}</code></td>
                <td>{log.resource_type}{log.resource_id ? `#${log.resource_id}` : ''}</td>
                <td className="details-cell">{log.details}</td>
                <td>{log.ip_address || '—'}</td>
              </tr>
            ))}
            {(!auditLogs.logs || auditLogs.logs.length === 0) && <tr><td colSpan="6" className="empty-text">No audit logs yet</td></tr>}
          </tbody>
        </table>
      </div>

      {auditLogs.total > auditFilter.limit && (
        <div className="pagination">
          <button className="btn btn-outline btn-sm" disabled={auditFilter.offset === 0}
            onClick={() => setAuditFilter({...auditFilter, offset: Math.max(0, auditFilter.offset - auditFilter.limit)})}>
            Previous
          </button>
          <span>Page {Math.floor(auditFilter.offset / auditFilter.limit) + 1} of {Math.ceil(auditLogs.total / auditFilter.limit)}</span>
          <button className="btn btn-outline btn-sm" disabled={auditFilter.offset + auditFilter.limit >= auditLogs.total}
            onClick={() => setAuditFilter({...auditFilter, offset: auditFilter.offset + auditFilter.limit})}>
            Next
          </button>
        </div>
      )}
    </div>
  );

  const renderSecurity = () => (
    <div className="enterprise-section">
      <div className="section-header">
        <h3>Security Configuration</h3>
      </div>

      <div className="dashboard-row">
        <div className="dashboard-card">
          <h3>🔒 Encryption at Rest</h3>
          <div className="status-list">
            <div className="status-item">
              <span>Status</span>
              <span className={`status-badge ${encryptionStatus?.enabled ? 'active' : 'inactive'}`}>
                {encryptionStatus?.enabled ? 'ENABLED' : 'DISABLED'}
              </span>
            </div>
            {encryptionStatus?.algorithm && (
              <div className="status-item">
                <span>Algorithm</span>
                <span>{encryptionStatus.algorithm}</span>
              </div>
            )}
          </div>
          <div style={{marginTop: 12}}>
            <button className="btn btn-outline btn-sm" onClick={handleGenerateKey}>Generate Key</button>
            <p className="help-text">Set ENCRYPTION_KEY env var in docker-compose.yml to enable</p>
          </div>
        </div>

        <div className="dashboard-card">
          <h3>🔑 LDAP / Active Directory SSO</h3>
          <div className="status-list">
            <div className="status-item">
              <span>Status</span>
              <span className={`status-badge ${ldapStatus?.status === 'connected' ? 'active' : ldapStatus?.enabled ? 'warning' : 'inactive'}`}>
                {ldapStatus?.status?.toUpperCase() || 'UNKNOWN'}
              </span>
            </div>
            {ldapConfig && (
              <>
                <div className="status-item">
                  <span>Server</span>
                  <span>{ldapConfig.server_url}</span>
                </div>
                <div className="status-item">
                  <span>Base DN</span>
                  <span>{ldapConfig.base_dn}</span>
                </div>
                <div className="status-item">
                  <span>SSL/TLS</span>
                  <span>{ldapConfig.use_ssl ? 'SSL' : ldapConfig.use_tls ? 'TLS' : 'None'}</span>
                </div>
                <div className="status-item">
                  <span>Auto-create users</span>
                  <span>{ldapConfig.auto_create_users ? 'Yes' : 'No'}</span>
                </div>
                <div className="status-item">
                  <span>ldap3 installed</span>
                  <span className={`status-badge ${ldapConfig.ldap3_installed ? 'active' : 'inactive'}`}>
                    {ldapConfig.ldap3_installed ? 'YES' : 'NO'}
                  </span>
                </div>
              </>
            )}
          </div>
          <p className="help-text" style={{marginTop: 12}}>Configure via LDAP_* environment variables in docker-compose.yml</p>
        </div>
      </div>
    </div>
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard': return renderDashboard();
      case 'roles': return renderRoles();
      case 'tenants': return renderTenants();
      case 'compliance': return renderCompliance();
      case 'audit': return renderAudit();
      case 'security': return renderSecurity();
      default: return renderDashboard();
    }
  };

  return (
    <div className="enterprise-page">
      <div className="page-header">
        <h1>Enterprise Management</h1>
        <p>RBAC, Multi-Tenancy, Compliance & Security</p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      <div className="enterprise-tabs">
        {TABS.map(tab => (
          <button key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>

      <div className="enterprise-content">
        {loading ? <div className="loading-text">Loading...</div> : renderContent()}
      </div>
    </div>
  );
}

export default EnterprisePage;
