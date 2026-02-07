import React, { useState, useEffect } from 'react';
import { getLDRSettings, updateLDRSettings } from '../api';

function SettingsPage({ user }) {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await getLDRSettings();
      setSettings(res.data.settings || {});
    } catch (err) {
      console.error('Failed to fetch settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await updateLDRSettings(settings);
      setSettings(res.data.settings || settings);
      setMessage('Settings saved successfully');
      setTimeout(() => setMessage(''), 3000);
    } catch (err) {
      setMessage(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="settings-page">
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40 }}>
          Loading settings...
        </p>
      </div>
    );
  }

  const settingsGroups = [
    {
      title: 'LLM Configuration',
      items: [
        { key: 'llm.provider', label: 'Provider', type: 'select', options: ['ollama', 'openai', 'anthropic'] },
        { key: 'llm.model', label: 'Model Name', type: 'text' },
        { key: 'llm.temperature', label: 'Temperature', type: 'number', step: 0.1, min: 0, max: 2 },
        { key: 'llm.ollama.url', label: 'Ollama URL', type: 'text' },
        { key: 'llm.context_length', label: 'Context Length', type: 'number' },
      ]
    },
    {
      title: 'Search Configuration',
      items: [
        { key: 'search.tool', label: 'Search Tool', type: 'select', options: ['searxng', 'duckduckgo', 'wikipedia'] },
        { key: 'search.iterations', label: 'Search Iterations', type: 'number', min: 1, max: 10 },
        { key: 'search.questions_per_iteration', label: 'Questions per Iteration', type: 'number', min: 1, max: 10 },
        { key: 'search.max_results', label: 'Max Results', type: 'number', min: 5, max: 200 },
        { key: 'search.searxng.url', label: 'SearXNG URL', type: 'text' },
      ]
    },
    {
      title: 'Embedding Configuration',
      items: [
        { key: 'embedding.provider', label: 'Provider', type: 'select', options: ['sentence-transformers', 'ollama'] },
        { key: 'embedding.model', label: 'Model Name', type: 'text' },
      ]
    },
    {
      title: 'Report Configuration',
      items: [
        { key: 'report.searches_per_section', label: 'Searches per Section', type: 'number', min: 1, max: 5 },
      ]
    },
  ];

  return (
    <div className="settings-page">
      <div className="settings-header">
        <h1>System Settings</h1>
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>

      {message && (
        <div className={`settings-message ${message.includes('success') ? 'success' : 'error'}`}>
          {message}
        </div>
      )}

      {settingsGroups.map(group => (
        <div key={group.title} className="settings-group">
          <h2>{group.title}</h2>
          <div className="settings-grid">
            {group.items.map(item => (
              <div key={item.key} className="setting-item">
                <label>{item.label}</label>
                {item.type === 'select' ? (
                  <select
                    value={settings[item.key] || ''}
                    onChange={(e) => handleChange(item.key, e.target.value)}
                  >
                    {item.options.map(opt => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : item.type === 'number' ? (
                  <input
                    type="number"
                    value={settings[item.key] ?? ''}
                    onChange={(e) => handleChange(item.key, parseFloat(e.target.value) || 0)}
                    step={item.step || 1}
                    min={item.min}
                    max={item.max}
                  />
                ) : (
                  <input
                    type="text"
                    value={settings[item.key] || ''}
                    onChange={(e) => handleChange(item.key, e.target.value)}
                  />
                )}
                <span className="setting-key">{item.key}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default SettingsPage;
