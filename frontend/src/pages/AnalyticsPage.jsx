import React, { useState, useEffect } from 'react';
import {
  getAnalyticsOverview, getAnalyticsDaily, getAnalyticsTopUsers,
  getAnalyticsPopularQueries, getAnalyticsDocuments, getAnalyticsActions
} from '../api';

function AnalyticsPage({ user }) {
  const [overview, setOverview] = useState(null);
  const [daily, setDaily] = useState([]);
  const [topUsers, setTopUsers] = useState([]);
  const [popularQueries, setPopularQueries] = useState([]);
  const [documentStats, setDocumentStats] = useState(null);
  const [actions, setActions] = useState([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => { fetchAll(); }, [days]);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [ov, da, tu, pq, ds, ac] = await Promise.all([
        getAnalyticsOverview(days),
        getAnalyticsDaily(days),
        getAnalyticsTopUsers(days),
        getAnalyticsPopularQueries(days),
        getAnalyticsDocuments(),
        getAnalyticsActions(days),
      ]);
      setOverview(ov.data);
      setDaily(da.data.daily_activity || []);
      setTopUsers(tu.data.top_users || []);
      setPopularQueries(pq.data.popular_queries || []);
      setDocumentStats(ds.data);
      setActions(ac.data.action_breakdown || []);
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  const maxDailyCount = Math.max(1, ...daily.map(d => d.count));
  const maxActionCount = Math.max(1, ...actions.map(a => a.count));
  const actionColors = ['#4f8cff', '#2ed573', '#ff6b6b', '#ffa502', '#a29bfe', '#fd79a8', '#4ecdc4', '#ffeaa7'];

  if (loading) {
    return <div className="analytics-page"><p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40 }}>Loading analytics...</p></div>;
  }

  return (
    <div className="analytics-page">
      <div className="analytics-header">
        <h1>Usage Analytics</h1>
        <div className="analytics-period">
          {[7, 14, 30, 90].map(d => (
            <button key={d} className={`btn btn-sm ${days === d ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setDays(d)}>{d}d</button>
          ))}
        </div>
      </div>

      {/* Overview Cards */}
      {overview && (
        <div className="analytics-cards">
          <div className="analytics-card">
            <div className="analytics-card-value">{overview.total_queries || 0}</div>
            <div className="analytics-card-label">Total Queries</div>
          </div>
          <div className="analytics-card">
            <div className="analytics-card-value">{overview.total_documents || 0}</div>
            <div className="analytics-card-label">Documents</div>
          </div>
          <div className="analytics-card">
            <div className="analytics-card-value">{overview.total_users || 0}</div>
            <div className="analytics-card-label">Active Users</div>
          </div>
          <div className="analytics-card">
            <div className="analytics-card-value">{overview.total_actions || 0}</div>
            <div className="analytics-card-label">Total Actions</div>
          </div>
        </div>
      )}

      {/* Daily Activity Chart */}
      <div className="analytics-section">
        <h3>Daily Activity</h3>
        <div className="analytics-chart">
          {daily.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: 20 }}>No activity data</p>
          ) : (
            <div className="bar-chart">
              {daily.slice(-30).map((d, i) => (
                <div key={i} className="bar-col" title={`${d.date}: ${d.count} actions`}>
                  <div className="bar" style={{ height: `${(d.count / maxDailyCount) * 100}%` }}></div>
                  <div className="bar-label">{d.date.slice(5)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="analytics-grid">
        {/* Action Breakdown */}
        <div className="analytics-section">
          <h3>Action Breakdown</h3>
          <div className="action-bars">
            {actions.map((a, i) => (
              <div key={i} className="action-bar-row">
                <div className="action-bar-label">{a.action}</div>
                <div className="action-bar-track">
                  <div className="action-bar-fill" style={{
                    width: `${(a.count / maxActionCount) * 100}%`,
                    background: actionColors[i % actionColors.length]
                  }}></div>
                </div>
                <div className="action-bar-count">{a.count}</div>
              </div>
            ))}
            {actions.length === 0 && <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>No data</p>}
          </div>
        </div>

        {/* Top Users */}
        <div className="analytics-section">
          <h3>Top Users</h3>
          <table className="analytics-table">
            <thead><tr><th>User</th><th>Actions</th></tr></thead>
            <tbody>
              {topUsers.map((u, i) => (
                <tr key={i}>
                  <td>{u.username}</td>
                  <td><span className="count-badge">{u.action_count}</span></td>
                </tr>
              ))}
              {topUsers.length === 0 && <tr><td colSpan={2} style={{ color: 'var(--text-secondary)' }}>No data</td></tr>}
            </tbody>
          </table>
        </div>
      </div>

      <div className="analytics-grid">
        {/* Popular Queries */}
        <div className="analytics-section">
          <h3>Popular Queries</h3>
          <div className="popular-queries-list">
            {popularQueries.map((q, i) => (
              <div key={i} className="popular-query-item">
                <span className="query-rank">#{i + 1}</span>
                <span className="query-text">{q.query}</span>
                <span className="count-badge">{q.count}</span>
              </div>
            ))}
            {popularQueries.length === 0 && <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>No queries yet</p>}
          </div>
        </div>

        {/* Document Stats */}
        <div className="analytics-section">
          <h3>Documents by Type</h3>
          <div className="doc-type-stats">
            {documentStats?.by_type?.map((d, i) => (
              <div key={i} className="doc-type-row">
                <span className="file-type-badge">{d.file_type?.replace('.', '') || 'unknown'}</span>
                <span className="count-badge">{d.count}</span>
              </div>
            ))}
            {(!documentStats?.by_type || documentStats.by_type.length === 0) &&
              <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>No documents</p>}
          </div>
          <h4 style={{ marginTop: 16 }}>Documents by User</h4>
          <div className="doc-type-stats">
            {documentStats?.by_user?.map((d, i) => (
              <div key={i} className="doc-type-row">
                <span>{d.uploaded_by}</span>
                <span className="count-badge">{d.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default AnalyticsPage;
