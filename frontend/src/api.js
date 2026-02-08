import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
});

// Attach token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth
export const login = (username, password) =>
  api.post('/auth/login', { username, password });

export const register = (data) =>
  api.post('/auth/register', data);

export const getMe = () =>
  api.get('/auth/me');

export const changePassword = (currentPassword, newPassword) =>
  api.put('/auth/password', { current_password: currentPassword, new_password: newPassword });

// Chat
export const sendChatQuery = (question, useContext = true, useKnowledgeGraph = true, k = 5, includeMultimodal = true, searchMode = 'hybrid') =>
  api.post('/chat/query', {
    question,
    use_context: useContext,
    use_knowledge_graph: useKnowledgeGraph,
    include_multimodal: includeMultimodal,
    search_mode: searchMode,
    k,
  });

export const sendChatQueryMultiTurn = (question, sessionId = null, useKnowledgeGraph = true, includeMultimodal = true, searchMode = 'hybrid', k = 5, contextTurns = 5) =>
  api.post('/chat/query-multiturn', {
    question,
    session_id: sessionId,
    use_context: true,
    use_knowledge_graph: useKnowledgeGraph,
    include_multimodal: includeMultimodal,
    search_mode: searchMode,
    k,
    context_turns: contextTurns,
  });

export const getChatHistory = (limit = 50) =>
  api.get(`/chat/history?limit=${limit}`);

export const clearChatHistory = () =>
  api.delete('/chat/history');

// Chat Sessions
export const createChatSession = (title = 'New Chat') =>
  api.post('/chat/sessions', { title });

export const listChatSessions = () =>
  api.get('/chat/sessions');

export const getSessionMessages = (sessionId) =>
  api.get(`/chat/sessions/${sessionId}/messages`);

export const updateChatSession = (sessionId, title) =>
  api.put(`/chat/sessions/${sessionId}`, { title });

export const deleteChatSession = (sessionId) =>
  api.delete(`/chat/sessions/${sessionId}`);

// Documents
export const uploadDocuments = (files, onProgress, folderId = null, description = null) => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  if (folderId) formData.append('folder_id', folderId);
  if (description) formData.append('description', description);
  return api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
  });
};

export const listDocuments = () =>
  api.get('/documents/list');

export const deleteDocument = (docId) =>
  api.delete(`/documents/${docId}`);

export const moveDocument = (docId, folderId) =>
  api.put(`/documents/${docId}/move`, { folder_id: folderId });

export const setDocumentTags = (docId, tagIds) =>
  api.put(`/documents/${docId}/tags`, { tag_ids: tagIds });

export const uploadDocumentVersion = (docId, file, changeNote = '', onProgress) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('change_note', changeNote);
  return api.post(`/documents/${docId}/version`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
  });
};

export const getDocumentVersions = (docId) =>
  api.get(`/documents/${docId}/versions`);

export const searchDocumentsAdvanced = (params) =>
  api.get('/documents/search', { params });

// Folders
export const createFolder = (name, parentId = null, color = '#4f8cff') =>
  api.post('/folders', { name, parent_id: parentId, color });

export const listFolders = () =>
  api.get('/folders');

export const updateFolder = (folderId, data) =>
  api.put(`/folders/${folderId}`, data);

export const deleteFolder = (folderId) =>
  api.delete(`/folders/${folderId}`);

// Tags
export const createTag = (name, color = '#4f8cff') =>
  api.post('/tags', { name, color });

export const listTags = () =>
  api.get('/tags');

export const deleteTag = (tagId) =>
  api.delete(`/tags/${tagId}`);

// Admin
export const getAdminStats = () =>
  api.get('/admin/stats');

export const getAdminUsers = () =>
  api.get('/admin/users');

export const updateUser = (userId, data) =>
  api.put(`/admin/users/${userId}`, data);

export const deleteUser = (userId) =>
  api.delete(`/admin/users/${userId}`);

// Health
export const healthCheck = () =>
  api.get('/health');

// Multimodal
export const getMultimodalInfo = () =>
  api.get('/multimodal/info');

export const getMultimodalStats = () =>
  api.get('/multimodal/stats');

// Search
export const searchDocuments = (query, k = 10, includeMultimodal = true) =>
  api.get(`/search?q=${encodeURIComponent(query)}&k=${k}&include_multimodal=${includeMultimodal}`);

// Batch Processing (admin)
export const batchProcessDocuments = () =>
  api.post('/documents/batch-process');

// Knowledge Graph
export const getKGStats = () =>
  api.get('/knowledge-graph/stats');

export const getKGEntities = () =>
  api.get('/knowledge-graph/entities');

export const searchKGEntities = (query) =>
  api.get(`/knowledge-graph/search?q=${encodeURIComponent(query)}`);

export const getKGEntity = (entityName, hops = 2) =>
  api.get(`/knowledge-graph/entity/${encodeURIComponent(entityName)}?hops=${hops}`);

export const rebuildKG = () =>
  api.post('/knowledge-graph/rebuild');

export const getKGFullGraph = (maxNodes = 500) =>
  api.get(`/knowledge-graph/full?max_nodes=${maxNodes}`);

// Analytics
export const getAnalyticsOverview = (days = 30) =>
  api.get(`/analytics/overview?days=${days}`);

export const getAnalyticsDaily = (days = 30) =>
  api.get(`/analytics/daily?days=${days}`);

export const getAnalyticsTopUsers = (days = 30, limit = 10) =>
  api.get(`/analytics/top-users?days=${days}&limit=${limit}`);

export const getAnalyticsPopularQueries = (days = 30, limit = 20) =>
  api.get(`/analytics/popular-queries?days=${days}&limit=${limit}`);

export const getAnalyticsDocuments = () =>
  api.get('/analytics/documents');

export const getAnalyticsActions = (days = 30) =>
  api.get(`/analytics/actions?days=${days}`);

// Export
export const exportChat = (format = 'json', sessionId = null) => {
  const params = new URLSearchParams({ format });
  if (sessionId) params.append('session_id', sessionId);
  return api.get(`/export/chat?${params}`, { responseType: 'blob' });
};

export const exportResearch = (taskId, format = 'markdown') =>
  api.get(`/export/research/${taskId}?format=${format}`, { responseType: 'blob' });

export const exportKnowledgeGraph = (format = 'json') =>
  api.get(`/export/knowledge-graph?format=${format}`, { responseType: 'blob' });

export const exportDocumentsList = (format = 'csv') =>
  api.get(`/export/documents?format=${format}`, { responseType: 'blob' });

// Deep Research
export const startResearch = (query, strategy = 'source-based', overrides = null) =>
  api.post('/research/start', { query, strategy, overrides });

export const getResearchProgress = (taskId) =>
  api.get(`/research/${taskId}/progress`);

export const getResearchResult = (taskId) =>
  api.get(`/research/${taskId}/result`);

export const generateReport = (taskId) =>
  api.post(`/research/${taskId}/report`);

export const getResearchHistory = (limit = 20) =>
  api.get(`/research/history?limit=${limit}`);

export const deleteResearch = (taskId) =>
  api.delete(`/research/${taskId}`);

export const getStrategies = () =>
  api.get('/research/strategies');

// Research Export (PDF/DOCX/MD/JSON)
export const exportResearchAs = (taskId, format = 'markdown') =>
  api.get(`/research/${taskId}/export?format=${format}`, { responseType: 'blob' });

// Research SSE Streaming
export const streamResearchProgress = (taskId) => {
  const token = localStorage.getItem('token');
  const baseUrl = process.env.REACT_APP_API_URL || '/api';
  return new EventSource(`${baseUrl}/research/${taskId}/stream?token=${token}`);
};

// Search Engines
export const getSearchEngines = () =>
  api.get('/search/engines');

export const testSearch = (query, engine = 'auto') =>
  api.post(`/search/test?query=${encodeURIComponent(query)}&engine=${engine}`);

// Token Usage
export const getTokenStats = (days = 30) =>
  api.get(`/tokens/stats?days=${days}`);

export const getAllTokenStats = (days = 30) =>
  api.get(`/tokens/stats/all?days=${days}`);

// Research Scheduler
export const createResearchSchedule = (name, query, strategy = 'source-based', intervalHours = 24) =>
  api.post('/research/schedules', { name, query, strategy, interval_hours: intervalHours });

export const getResearchSchedules = () =>
  api.get('/research/schedules');

export const updateResearchSchedule = (scheduleId, data) =>
  api.put(`/research/schedules/${scheduleId}`, data);

export const deleteResearchSchedule = (scheduleId) =>
  api.delete(`/research/schedules/${scheduleId}`);

// Settings
export const getLDRSettings = () =>
  api.get('/settings/ldr');

export const updateLDRSettings = (settings) =>
  api.put('/settings/ldr', { settings });

// ==================== ENTERPRISE / PHASE 4 ====================

// Enterprise Dashboard
export const getEnterpriseDashboard = () =>
  api.get('/enterprise/dashboard');

// Roles
export const listRoles = () =>
  api.get('/enterprise/roles');

export const createRole = (name, description, permissions) =>
  api.post('/enterprise/roles', { name, description, permissions });

export const updateRole = (roleId, data) =>
  api.put(`/enterprise/roles/${roleId}`, data);

export const deleteRole = (roleId) =>
  api.delete(`/enterprise/roles/${roleId}`);

export const assignRole = (userId, roleName) =>
  api.post('/enterprise/roles/assign', { user_id: userId, role_name: roleName });

export const removeRole = (userId, roleId) =>
  api.post('/enterprise/roles/remove', { user_id: userId, role_id: roleId });

export const getUserRoles = (userId) =>
  api.get(`/enterprise/users/${userId}/roles`);

export const getUserPermissions = (userId) =>
  api.get(`/enterprise/users/${userId}/permissions`);

export const listAllPermissions = () =>
  api.get('/enterprise/permissions/list');

// Tenants
export const listTenants = () =>
  api.get('/enterprise/tenants');

export const createTenant = (data) =>
  api.post('/enterprise/tenants', data);

export const updateTenant = (tenantId, data) =>
  api.put(`/enterprise/tenants/${tenantId}`, data);

export const deleteTenant = (tenantId) =>
  api.delete(`/enterprise/tenants/${tenantId}`);

export const assignUserToTenant = (userId, tenantId) =>
  api.post('/enterprise/tenants/assign-user', { user_id: userId, tenant_id: tenantId });

// Document Permissions
export const getDocumentPermissions = (docId) =>
  api.get(`/enterprise/documents/${docId}/permissions`);

export const grantDocumentPermission = (documentId, userId, accessLevel) =>
  api.post('/enterprise/documents/permissions', { document_id: documentId, user_id: userId, access_level: accessLevel });

export const revokeDocumentPermission = (permId) =>
  api.delete(`/enterprise/documents/permissions/${permId}`);

// LDAP / SSO
export const getLDAPStatus = () =>
  api.get('/enterprise/ldap/status');

export const getLDAPConfig = () =>
  api.get('/enterprise/ldap/config');

// Encryption
export const getEncryptionStatus = () =>
  api.get('/enterprise/encryption/status');

export const generateEncryptionKey = () =>
  api.post('/enterprise/encryption/generate-key');

// Compliance / GDPR
export const getAuditLogs = (params = {}) =>
  api.get('/enterprise/audit-logs', { params });

export const gdprExportData = (userId) =>
  api.post('/enterprise/gdpr/export', { user_id: userId });

export const gdprDeleteData = (userId, deleteAccount = false) =>
  api.post('/enterprise/gdpr/delete', { user_id: userId, delete_account: deleteAccount });

export const getComplianceReport = (reportType = 'general') =>
  api.get(`/enterprise/compliance/report?report_type=${reportType}`);

export const exportAuditCSV = (startDate = null, endDate = null) => {
  const params = new URLSearchParams();
  if (startDate) params.append('start_date', startDate);
  if (endDate) params.append('end_date', endDate);
  return api.get(`/enterprise/compliance/audit-csv?${params}`, { responseType: 'blob' });
};

// ==================== LightRAG ====================

// LightRAG Health
export const getLightRAGHealth = () =>
  api.get('/lightrag/health');

// LightRAG Query
export const lightragQuery = (query, mode = 'hybrid', options = {}) =>
  api.post('/lightrag/query', {
    query,
    mode,
    ...options
  });

export const lightragQueryWithContext = (query, mode = 'hybrid', top_k = null) =>
  api.post('/lightrag/query/context', { query, mode, top_k });

// LightRAG Streaming Query
export const lightragQueryStream = async (query, mode = 'hybrid', options = {}, onChunk) => {
  const token = localStorage.getItem('token');
  const response = await fetch(`${API_BASE}/lightrag/query/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ query, mode, stream: true, ...options }),
  });

  if (!response.ok) throw new Error(`Stream error: ${response.statusText}`);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (line.trim()) {
        try {
          const data = JSON.parse(line);
          if (data.chunk) onChunk(data.chunk);
          if (data.done) return;
          if (data.error) throw new Error(data.error);
        } catch (e) {
          if (e.message !== 'Unexpected end of JSON input') console.warn('Parse error:', e);
        }
      }
    }
  }
};

// LightRAG Strategies
export const getLightRAGStrategies = () =>
  api.get('/lightrag/strategies');

// LightRAG Documents
export const getLightRAGDocuments = (status = null) =>
  api.get('/lightrag/documents', { params: status ? { status } : {} });

export const lightragInsertText = (text, file_path = null) =>
  api.post('/lightrag/documents/text', { text, file_path });

export const lightragUploadDocument = (file) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/lightrag/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000,
  });
};

export const lightragDeleteDocument = (docId) =>
  api.delete(`/lightrag/documents/${docId}`);

export const lightragClearDocuments = () =>
  api.delete('/lightrag/documents');

export const getLightRAGPipelineStatus = () =>
  api.get('/lightrag/documents/pipeline_status');

export const getLightRAGDocumentStatusCounts = () =>
  api.get('/lightrag/documents/status_counts');

// LightRAG Graph
export const getLightRAGGraph = (label = null, maxDepth = 3, maxNodes = 1000) =>
  api.get('/lightrag/graphs', { params: { label, max_depth: maxDepth, max_nodes: maxNodes } });

export const getLightRAGLabels = () =>
  api.get('/lightrag/graph/label/list');

export const getLightRAGPopularLabels = (limit = 10) =>
  api.get('/lightrag/graph/label/popular', { params: { limit } });

export const searchLightRAGLabels = (q, limit = 10) =>
  api.get('/lightrag/graph/label/search', { params: { q, limit } });

export const searchLightRAGEntities = (q) =>
  api.get('/lightrag/graph/entity/search', { params: { q } });

export const checkLightRAGEntityExists = (name) =>
  api.get('/lightrag/graph/entity/exists', { params: { name } });

export const editLightRAGEntity = (entityName, data) =>
  api.post('/lightrag/graph/entity/edit', { entity_name: entityName, ...data });

export const editLightRAGRelation = (source, target, data) =>
  api.post('/lightrag/graph/relation/edit', { source, target, ...data });


// ==================== LDR (Local Deep Research) API ====================

// Health & Info
export const getLDRHealth = () => api.get('/ldr/health');
export const getLDRStrategies = (category) =>
  api.get('/ldr/strategies', { params: category ? { category } : {} });
export const getLDRSearchEngines = () => api.get('/ldr/search-engines');

// Research
export const startLDRResearch = (query, strategy = 'source-based', options = {}) =>
  api.post('/ldr/research/start', {
    query, strategy,
    research_mode: options.research_mode || 'detailed',
    search_engine: options.search_engine || 'auto',
    iterations: options.iterations || 3,
    questions_per_iteration: options.questions_per_iteration || 3,
    overrides: options.overrides || null,
  });

export const getLDRProgress = (taskId) => api.get(`/ldr/research/${taskId}/progress`);
export const getLDRResult = (taskId) => api.get(`/ldr/research/${taskId}/result`);

// Follow-up Research
export const startLDRFollowUp = (parentTaskId, query) =>
  api.post('/ldr/research/follow-up', { parent_task_id: parentTaskId, query });

// News & Subscriptions
export const getLDRNewsFeed = (topics, limit = 20) =>
  api.get('/ldr/news/feed', { params: { topics: topics?.join(','), limit } });
export const createLDRSubscription = (query, subType = 'search', intervalHours = 24) =>
  api.post('/ldr/news/subscriptions', { query, sub_type: subType, interval_hours: intervalHours });

// Analytics
export const getLDRStrategyAnalytics = () => api.get('/ldr/analytics/strategies');
export const getLDREngineAnalytics = () => api.get('/ldr/analytics/engines');

export default api;
