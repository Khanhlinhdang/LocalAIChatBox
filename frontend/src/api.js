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

// Settings
export const getLDRSettings = () =>
  api.get('/settings/ldr');

export const updateLDRSettings = (settings) =>
  api.put('/settings/ldr', { settings });

export default api;
