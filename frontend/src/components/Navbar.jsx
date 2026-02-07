import React from 'react';
import { Link, useLocation } from 'react-router-dom';

function Navbar({ user, onLogout }) {
  const location = useLocation();

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        RAG Chat
      </Link>

      <div className="navbar-links">
        <Link to="/" className={location.pathname === '/' ? 'active' : ''}>
          Chat
        </Link>
        <Link to="/documents" className={location.pathname === '/documents' ? 'active' : ''}>
          Documents
        </Link>
        <Link to="/research" className={location.pathname === '/research' ? 'active' : ''}>
          Research
        </Link>
        <Link to="/knowledge-graph" className={location.pathname === '/knowledge-graph' ? 'active' : ''}>
          Graph
        </Link>
        <Link to="/analytics" className={location.pathname === '/analytics' ? 'active' : ''}>
          Analytics
        </Link>
        {user.is_admin && (
          <>
            <Link to="/admin" className={location.pathname === '/admin' ? 'active' : ''}>
              Admin
            </Link>
            <Link to="/settings" className={location.pathname === '/settings' ? 'active' : ''}>
              Settings
            </Link>
          </>
        )}
      </div>

      <div className="navbar-user">
        <div className="navbar-user-info">
          <div className="name">{user.full_name}</div>
          <div className="role">{user.is_admin ? 'Admin' : 'User'}</div>
        </div>
        <button className="btn btn-outline btn-sm" onClick={onLogout}>
          Logout
        </button>
      </div>
    </nav>
  );
}

export default Navbar;
