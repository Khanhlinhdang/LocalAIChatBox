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
export const sendChatQuery = (question, useContext = true, useKnowledgeGraph = true, k = 5) =>
  api.post('/chat/query', { question, use_context: useContext, use_knowledge_graph: useKnowledgeGraph, k });

export const getChatHistory = (limit = 50) =>
  api.get(`/chat/history?limit=${limit}`);

export const clearChatHistory = () =>
  api.delete('/chat/history');

// Documents
export const uploadDocuments = (files, onProgress) => {
  const formData = new FormData();
  files.forEach((file) => formData.append('files', file));
  return api.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
  });
};

export const listDocuments = () =>
  api.get('/documents/list');

export const deleteDocument = (docId) =>
  api.delete(`/documents/${docId}`);

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
