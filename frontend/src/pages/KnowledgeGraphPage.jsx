import React, { useState, useEffect, useCallback } from 'react';
import { getKGStats, getKGEntities, searchKGEntities, getKGEntity, rebuildKG } from '../api';

const ENTITY_COLORS = {
  PERSON: '#ff6b6b',
  ORGANIZATION: '#4ecdc4',
  PROJECT: '#45b7d1',
  TECHNOLOGY: '#96ceb4',
  PRODUCT: '#ffeaa7',
  LOCATION: '#a29bfe',
  CONCEPT: '#fd79a8',
  UNKNOWN: '#636e72',
};

function KnowledgeGraphPage({ user }) {
  const [stats, setStats] = useState(null);
  const [entities, setEntities] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [subgraph, setSubgraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [filterType, setFilterType] = useState('ALL');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, entitiesRes] = await Promise.all([
        getKGStats(),
        getKGEntities(),
      ]);
      setStats(statsRes.data);
      setEntities(entitiesRes.data.entities || []);
    } catch (err) {
      console.error('Failed to fetch KG data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      const res = await searchKGEntities(searchQuery);
      setSearchResults(res.data.results || []);
    } catch (err) {
      console.error('Search failed:', err);
    }
  }, [searchQuery]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.trim()) {
        handleSearch();
      } else {
        setSearchResults(null);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, handleSearch]);

  const handleEntityClick = async (entityName) => {
    setSelectedEntity(entityName);
    try {
      const res = await getKGEntity(entityName, 2);
      setSubgraph(res.data);
    } catch (err) {
      console.error('Failed to get entity subgraph:', err);
    }
  };

  const handleRebuild = async () => {
    if (!window.confirm('Rebuild the entire Knowledge Graph? This may take a while for large document sets.')) return;
    setRebuilding(true);
    try {
      await rebuildKG();
      await fetchData();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to rebuild Knowledge Graph');
    } finally {
      setRebuilding(false);
    }
  };

  const filteredEntities = filterType === 'ALL'
    ? entities
    : entities.filter(e => e.type === filterType);

  const entityTypes = [...new Set(entities.map(e => e.type))];

  if (loading) {
    return (
      <div className="kg-page">
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40 }}>
          Loading Knowledge Graph...
        </p>
      </div>
    );
  }

  return (
    <div className="kg-page">
      <div className="kg-header">
        <h1>Knowledge Graph</h1>
        {user.is_admin && (
          <button className="btn btn-outline" onClick={handleRebuild} disabled={rebuilding}>
            {rebuilding ? 'Rebuilding...' : 'Rebuild Graph'}
          </button>
        )}
      </div>

      {/* Stats */}
      {stats && (
        <div className="kg-stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_nodes}</div>
            <div className="stat-label">Entities</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_edges}</div>
            <div className="stat-label">Relationships</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{Object.keys(stats.entity_types || {}).length}</div>
            <div className="stat-label">Entity Types</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{Object.keys(stats.relation_types || {}).length}</div>
            <div className="stat-label">Relation Types</div>
          </div>
        </div>
      )}

      {/* Type distribution */}
      {stats && stats.entity_types && Object.keys(stats.entity_types).length > 0 && (
        <div className="kg-type-distribution">
          {Object.entries(stats.entity_types).map(([type, count]) => (
            <div key={type} className="type-chip" style={{ borderColor: ENTITY_COLORS[type] || ENTITY_COLORS.UNKNOWN }}>
              <span className="type-dot" style={{ background: ENTITY_COLORS[type] || ENTITY_COLORS.UNKNOWN }}></span>
              {type}: {count}
            </div>
          ))}
        </div>
      )}

      {/* Search */}
      <div className="kg-search">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search entities..."
          className="kg-search-input"
        />
      </div>

      {/* Search Results */}
      {searchResults && (
        <div className="kg-search-results">
          <h3>Search Results ({searchResults.length})</h3>
          {searchResults.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>No entities found.</p>
          ) : (
            <div className="entity-cards">
              {searchResults.map((entity, i) => (
                <div
                  key={i}
                  className="entity-card"
                  onClick={() => handleEntityClick(entity.name)}
                  style={{ borderLeftColor: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}
                >
                  <div className="entity-card-name">{entity.name}</div>
                  <div className="entity-card-type" style={{ color: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}>
                    {entity.type}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Selected Entity Subgraph */}
      {selectedEntity && subgraph && (
        <div className="kg-subgraph">
          <div className="kg-subgraph-header">
            <h3>Connections: {selectedEntity}</h3>
            <button className="btn btn-outline btn-sm" onClick={() => { setSelectedEntity(null); setSubgraph(null); }}>
              Close
            </button>
          </div>

          {subgraph.edges.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, padding: '12px 0' }}>No connections found for this entity.</p>
          ) : (
            <div className="kg-graph-visual">
              {/* Center node */}
              <div className="graph-center-node" style={{ background: ENTITY_COLORS[subgraph.nodes.find(n => n.id === selectedEntity)?.type] || ENTITY_COLORS.UNKNOWN }}>
                {selectedEntity}
              </div>

              {/* Connections list */}
              <div className="graph-connections">
                {subgraph.edges.map((edge, i) => (
                  <div key={i} className="graph-edge">
                    <span
                      className="edge-node"
                      onClick={() => handleEntityClick(edge.source === selectedEntity ? edge.target : edge.source)}
                      style={{ cursor: 'pointer' }}
                    >
                      {edge.source === selectedEntity ? edge.target : edge.source}
                    </span>
                    <span className="edge-relation">{edge.relation}</span>
                    <span className="edge-direction">
                      {edge.source === selectedEntity ? '(outgoing)' : '(incoming)'}
                    </span>
                  </div>
                ))}
              </div>

              {/* All nodes in subgraph */}
              <div className="graph-nodes-list">
                <h4>All entities in this subgraph ({subgraph.nodes.length})</h4>
                <div className="entities-list">
                  {subgraph.nodes.map((node, i) => (
                    <span
                      key={i}
                      className={`entity-tag entity-type-${(node.type || 'concept').toLowerCase()}`}
                      onClick={() => handleEntityClick(node.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      {node.id}
                      <span className="entity-type-label">{node.type}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* All Entities */}
      {!searchResults && (
        <div className="kg-all-entities">
          <div className="kg-entities-header">
            <h3>All Entities ({filteredEntities.length})</h3>
            <div className="kg-filter">
              <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                <option value="ALL">All Types</option>
                {entityTypes.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
          </div>

          {filteredEntities.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: 40 }}>
              No entities in the Knowledge Graph yet. Upload documents to build the graph.
            </p>
          ) : (
            <div className="entity-cards">
              {filteredEntities.map((entity, i) => (
                <div
                  key={i}
                  className="entity-card"
                  onClick={() => handleEntityClick(entity.name)}
                  style={{ borderLeftColor: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}
                >
                  <div className="entity-card-name">{entity.name}</div>
                  <div className="entity-card-meta">
                    <span className="entity-card-type" style={{ color: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}>
                      {entity.type}
                    </span>
                    <span className="entity-card-connections">{entity.connections} connections</span>
                  </div>
                  {entity.source_files && entity.source_files.length > 0 && (
                    <div className="entity-card-files">
                      {entity.source_files.slice(0, 3).map((f, j) => (
                        <span key={j} className="file-tag">{f}</span>
                      ))}
                      {entity.source_files.length > 3 && (
                        <span className="file-tag">+{entity.source_files.length - 3} more</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default KnowledgeGraphPage;
