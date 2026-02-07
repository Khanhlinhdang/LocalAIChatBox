import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ChatPage from './pages/ChatPage';
import DocumentsPage from './pages/DocumentsPage';
import KnowledgeGraphPage from './pages/KnowledgeGraphPage';
import DeepResearchPage from './pages/DeepResearchPage';
import SettingsPage from './pages/SettingsPage';
import AdminPage from './pages/AdminPage';
import AnalyticsPage from './pages/AnalyticsPage';
import Navbar from './components/Navbar';
import './App.css';

function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));

  useEffect(() => {
    const savedUser = localStorage.getItem('user');
    if (savedUser && token) {
      setUser(JSON.parse(savedUser));
    }
  }, [token]);

  const handleLogin = (tokenData, userData) => {
    localStorage.setItem('token', tokenData);
    localStorage.setItem('user', JSON.stringify(userData));
    setToken(tokenData);
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
  };

  if (!token || !user) {
    return (
      <Router>
        <div className="app">
          <Routes>
            <Route path="/register" element={<RegisterPage onLogin={handleLogin} />} />
            <Route path="*" element={<LoginPage onLogin={handleLogin} />} />
          </Routes>
        </div>
      </Router>
    );
  }

  return (
    <Router>
      <div className="app">
        <Navbar user={user} onLogout={handleLogout} />
        <div className="main-content">
          <Routes>
            <Route path="/" element={<ChatPage user={user} />} />
            <Route path="/documents" element={<DocumentsPage user={user} />} />
            <Route path="/research" element={<DeepResearchPage user={user} />} />
            <Route path="/knowledge-graph" element={<KnowledgeGraphPage user={user} />} />
            <Route path="/analytics" element={<AnalyticsPage user={user} />} />
            {user.is_admin && (
              <>
                <Route path="/admin" element={<AdminPage user={user} />} />
                <Route path="/settings" element={<SettingsPage user={user} />} />
              </>
            )}
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;
