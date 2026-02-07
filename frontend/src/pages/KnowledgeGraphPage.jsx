import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getKGStats, getKGEntities, searchKGEntities, getKGEntity, rebuildKG, getKGFullGraph, exportKnowledgeGraph } from '../api';

const ENTITY_COLORS = {
  PERSON: '#ff6b6b', ORGANIZATION: '#4ecdc4', PROJECT: '#45b7d1',
  TECHNOLOGY: '#96ceb4', PRODUCT: '#ffeaa7', LOCATION: '#a29bfe',
  CONCEPT: '#fd79a8', EVENT: '#74b9ff', UNKNOWN: '#636e72',
};

/* ---- Simple force-directed layout (no D3 dependency) ---- */
function useForceGraph(canvasRef, graphData, onNodeClick) {
  const nodesRef = useRef([]);
  const edgesRef = useRef([]);
  const animRef = useRef(null);
  const dragRef = useRef(null);
  const panRef = useRef({ x: 0, y: 0, scale: 1 });
  const isPanningRef = useRef(false);
  const lastMouseRef = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !graphData) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.parentElement.clientWidth;
    const H = canvas.height = 500;
    const cx = W / 2, cy = H / 2;

    // Init nodes with positions
    const nodeMap = {};
    const nodes = (graphData.nodes || []).map((n, i) => {
      const angle = (2 * Math.PI * i) / (graphData.nodes.length || 1);
      const r = 120 + Math.random() * 100;
      const node = { ...n, x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r, vx: 0, vy: 0, radius: 6 + Math.min((n.degree || 1) * 2, 18) };
      nodeMap[n.id] = node;
      return node;
    });
    const edges = (graphData.edges || []).map(e => ({
      ...e, source: nodeMap[e.source], target: nodeMap[e.target]
    })).filter(e => e.source && e.target);
    nodesRef.current = nodes;
    edgesRef.current = edges;

    const tick = () => {
      // Forces
      for (let i = 0; i < nodes.length; i++) {
        // Center gravity
        nodes[i].vx += (cx - nodes[i].x) * 0.0005;
        nodes[i].vy += (cy - nodes[i].y) * 0.0005;
        // Repulsion
        for (let j = i + 1; j < nodes.length; j++) {
          let dx = nodes[j].x - nodes[i].x;
          let dy = nodes[j].y - nodes[i].y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;
          let force = 800 / (dist * dist);
          nodes[i].vx -= dx / dist * force;
          nodes[i].vy -= dy / dist * force;
          nodes[j].vx += dx / dist * force;
          nodes[j].vy += dy / dist * force;
        }
      }
      // Spring (edges)
      for (const e of edges) {
        let dx = e.target.x - e.source.x;
        let dy = e.target.y - e.source.y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        let force = (dist - 100) * 0.003;
        e.source.vx += dx / dist * force;
        e.source.vy += dy / dist * force;
        e.target.vx -= dx / dist * force;
        e.target.vy -= dy / dist * force;
      }
      // Apply velocity
      for (const n of nodes) {
        if (dragRef.current && dragRef.current.id === n.id) continue;
        n.vx *= 0.85; n.vy *= 0.85;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(20, Math.min(W - 20, n.x));
        n.y = Math.max(20, Math.min(H - 20, n.y));
      }
      draw();
      animRef.current = requestAnimationFrame(tick);
    };

    const draw = () => {
      const p = panRef.current;
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.scale(p.scale, p.scale);

      // Edges
      ctx.lineWidth = 0.5;
      for (const e of edges) {
        ctx.strokeStyle = 'rgba(79,140,255,0.25)';
        ctx.beginPath();
        ctx.moveTo(e.source.x, e.source.y);
        ctx.lineTo(e.target.x, e.target.y);
        ctx.stroke();
        // Edge label (only if zoomed in enough)
        if (p.scale > 0.7 && e.relation) {
          const mx = (e.source.x + e.target.x) / 2;
          const my = (e.source.y + e.target.y) / 2;
          ctx.fillStyle = 'rgba(160,160,176,0.6)';
          ctx.font = '8px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(e.relation.substring(0, 15), mx, my);
        }
      }
      // Nodes
      for (const n of nodes) {
        const color = ENTITY_COLORS[n.type] || ENTITY_COLORS.UNKNOWN;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.85;
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
        // Label
        if (p.scale > 0.5) {
          ctx.fillStyle = '#e0e0e0';
          ctx.font = `${Math.max(9, 11 / p.scale)}px sans-serif`;
          ctx.textAlign = 'center';
          const label = n.id.length > 20 ? n.id.substring(0, 18) + '…' : n.id;
          ctx.fillText(label, n.x, n.y - n.radius - 4);
        }
      }
      ctx.restore();
    };

    animRef.current = requestAnimationFrame(tick);

    // Mouse interactions
    const toWorld = (mx, my) => ({
      wx: (mx - panRef.current.x) / panRef.current.scale,
      wy: (my - panRef.current.y) / panRef.current.scale
    });

    const findNode = (mx, my) => {
      const { wx, wy } = toWorld(mx, my);
      for (let i = nodes.length - 1; i >= 0; i--) {
        const dx = wx - nodes[i].x, dy = wy - nodes[i].y;
        if (dx * dx + dy * dy < nodes[i].radius * nodes[i].radius * 1.5) return nodes[i];
      }
      return null;
    };

    const handleMouseDown = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const node = findNode(mx, my);
      if (node) {
        dragRef.current = node;
        canvas.style.cursor = 'grabbing';
      } else {
        isPanningRef.current = true;
        canvas.style.cursor = 'move';
      }
      lastMouseRef.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseMove = (e) => {
      const dx = e.clientX - lastMouseRef.current.x;
      const dy = e.clientY - lastMouseRef.current.y;
      lastMouseRef.current = { x: e.clientX, y: e.clientY };
      if (dragRef.current) {
        dragRef.current.x += dx / panRef.current.scale;
        dragRef.current.y += dy / panRef.current.scale;
        dragRef.current.vx = 0; dragRef.current.vy = 0;
      } else if (isPanningRef.current) {
        panRef.current.x += dx;
        panRef.current.y += dy;
      }
    };

    const handleMouseUp = (e) => {
      if (dragRef.current) {
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left, my = e.clientY - rect.top;
        const node = findNode(mx, my);
        // If it was a click (not drag), trigger entity click
        if (node && node.id === dragRef.current.id) {
          onNodeClick?.(node.id);
        }
      }
      dragRef.current = null;
      isPanningRef.current = false;
      canvas.style.cursor = 'default';
    };

    const handleWheel = (e) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left, my = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.1 : 0.9;
      const newScale = Math.max(0.2, Math.min(4, panRef.current.scale * factor));
      panRef.current.x = mx - (mx - panRef.current.x) * (newScale / panRef.current.scale);
      panRef.current.y = my - (my - panRef.current.y) * (newScale / panRef.current.scale);
      panRef.current.scale = newScale;
    };

    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseleave', handleMouseUp);
    canvas.addEventListener('wheel', handleWheel, { passive: false });

    return () => {
      cancelAnimationFrame(animRef.current);
      canvas.removeEventListener('mousedown', handleMouseDown);
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseup', handleMouseUp);
      canvas.removeEventListener('mouseleave', handleMouseUp);
      canvas.removeEventListener('wheel', handleWheel);
    };
  }, [canvasRef, graphData, onNodeClick]);
}

function KnowledgeGraphPage({ user }) {
  const [stats, setStats] = useState(null);
  const [entities, setEntities] = useState([]);
  const [fullGraph, setFullGraph] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [subgraph, setSubgraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [filterType, setFilterType] = useState('ALL');
  const [showGraph, setShowGraph] = useState(true);
  const canvasRef = useRef(null);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const [statsRes, entitiesRes, graphRes] = await Promise.all([
        getKGStats(), getKGEntities(), getKGFullGraph()
      ]);
      setStats(statsRes.data);
      setEntities(entitiesRes.data.entities || []);
      setFullGraph(graphRes.data);
    } catch (err) {
      console.error('Failed to fetch KG data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleNodeClick = useCallback((entityName) => {
    handleEntityClick(entityName);
  }, []);

  useForceGraph(canvasRef, showGraph ? fullGraph : null, handleNodeClick);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    try {
      const res = await searchKGEntities(searchQuery);
      setSearchResults(res.data.results || []);
    } catch (err) { console.error('Search failed:', err); }
  }, [searchQuery]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery.trim()) handleSearch();
      else setSearchResults(null);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, handleSearch]);

  const handleEntityClick = async (entityName) => {
    setSelectedEntity(entityName);
    try {
      const res = await getKGEntity(entityName, 2);
      setSubgraph(res.data);
    } catch (err) { console.error('Failed to get entity subgraph:', err); }
  };

  const handleRebuild = async () => {
    if (!window.confirm('Rebuild the entire Knowledge Graph?')) return;
    setRebuilding(true);
    try { await rebuildKG(); await fetchData(); }
    catch (err) { alert(err.response?.data?.detail || 'Failed to rebuild'); }
    finally { setRebuilding(false); }
  };

  const handleExport = async (format) => {
    try {
      const response = await exportKnowledgeGraph(format);
      const blob = new Blob([typeof response.data === 'object' ? JSON.stringify(response.data, null, 2) : response.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url;
      a.download = `knowledge-graph.${format}`; a.click();
      URL.revokeObjectURL(url);
    } catch (err) { console.error('Export failed:', err); }
  };

  const filteredEntities = filterType === 'ALL' ? entities : entities.filter(e => e.type === filterType);
  const entityTypes = [...new Set(entities.map(e => e.type))];

  if (loading) {
    return <div className="kg-page"><p style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: 40 }}>Loading Knowledge Graph...</p></div>;
  }

  return (
    <div className="kg-page">
      <div className="kg-header">
        <h1>Knowledge Graph</h1>
        <div className="kg-header-actions">
          <button className="btn btn-outline btn-sm" onClick={() => handleExport('json')}>📥 JSON</button>
          <button className="btn btn-outline btn-sm" onClick={() => handleExport('csv')}>📥 CSV</button>
          <button className="btn btn-outline btn-sm" onClick={() => handleExport('graphml')}>📥 GraphML</button>
          <button className="btn btn-outline btn-sm" onClick={() => setShowGraph(g => !g)}>
            {showGraph ? '📋 List View' : '🕸️ Graph View'}
          </button>
          {user.is_admin && (
            <button className="btn btn-outline" onClick={handleRebuild} disabled={rebuilding}>
              {rebuilding ? 'Rebuilding...' : 'Rebuild Graph'}
            </button>
          )}
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="kg-stats-grid">
          <div className="stat-card"><div className="stat-value">{stats.total_nodes}</div><div className="stat-label">Entities</div></div>
          <div className="stat-card"><div className="stat-value">{stats.total_edges}</div><div className="stat-label">Relationships</div></div>
          <div className="stat-card"><div className="stat-value">{Object.keys(stats.entity_types || {}).length}</div><div className="stat-label">Entity Types</div></div>
          <div className="stat-card"><div className="stat-value">{Object.keys(stats.relation_types || {}).length}</div><div className="stat-label">Relation Types</div></div>
        </div>
      )}

      {/* Type distribution */}
      {stats?.entity_types && Object.keys(stats.entity_types).length > 0 && (
        <div className="kg-type-distribution">
          {Object.entries(stats.entity_types).map(([type, count]) => (
            <div key={type} className="type-chip" style={{ borderColor: ENTITY_COLORS[type] || ENTITY_COLORS.UNKNOWN }}>
              <span className="type-dot" style={{ background: ENTITY_COLORS[type] || ENTITY_COLORS.UNKNOWN }}></span>
              {type}: {count}
            </div>
          ))}
        </div>
      )}

      {/* Interactive Graph Canvas */}
      {showGraph && fullGraph && (fullGraph.nodes?.length > 0) && (
        <div className="kg-canvas-wrapper">
          <div className="kg-canvas-hint">Scroll to zoom · Drag nodes · Click node for details · Drag background to pan</div>
          <canvas ref={canvasRef} className="kg-canvas" />
        </div>
      )}

      {/* Search */}
      <div className="kg-search">
        <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search entities..." className="kg-search-input" />
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
                <div key={i} className="entity-card" onClick={() => handleEntityClick(entity.name)}
                  style={{ borderLeftColor: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}>
                  <div className="entity-card-name">{entity.name}</div>
                  <div className="entity-card-type" style={{ color: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}>{entity.type}</div>
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
            <button className="btn btn-outline btn-sm" onClick={() => { setSelectedEntity(null); setSubgraph(null); }}>Close</button>
          </div>
          {subgraph.edges.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', fontSize: 13, padding: '12px 0' }}>No connections found.</p>
          ) : (
            <div className="kg-graph-visual">
              <div className="graph-center-node" style={{ background: ENTITY_COLORS[subgraph.nodes.find(n => n.id === selectedEntity)?.type] || ENTITY_COLORS.UNKNOWN }}>
                {selectedEntity}
              </div>
              <div className="graph-connections">
                {subgraph.edges.map((edge, i) => (
                  <div key={i} className="graph-edge">
                    <span className="edge-node" onClick={() => handleEntityClick(edge.source === selectedEntity ? edge.target : edge.source)} style={{ cursor: 'pointer' }}>
                      {edge.source === selectedEntity ? edge.target : edge.source}
                    </span>
                    <span className="edge-relation">{edge.relation}</span>
                    <span className="edge-direction">{edge.source === selectedEntity ? '→' : '←'}</span>
                  </div>
                ))}
              </div>
              <div className="graph-nodes-list">
                <h4>Subgraph entities ({subgraph.nodes.length})</h4>
                <div className="entities-list">
                  {subgraph.nodes.map((node, i) => (
                    <span key={i} className={`entity-tag entity-type-${(node.type || 'concept').toLowerCase()}`}
                      onClick={() => handleEntityClick(node.id)} style={{ cursor: 'pointer' }}>
                      {node.id} <span className="entity-type-label">{node.type}</span>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* All Entities (list view or when graph hidden) */}
      {!searchResults && (
        <div className="kg-all-entities">
          <div className="kg-entities-header">
            <h3>All Entities ({filteredEntities.length})</h3>
            <div className="kg-filter">
              <select value={filterType} onChange={e => setFilterType(e.target.value)}>
                <option value="ALL">All Types</option>
                {entityTypes.map(type => <option key={type} value={type}>{type}</option>)}
              </select>
            </div>
          </div>
          {filteredEntities.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: 40 }}>No entities yet.</p>
          ) : (
            <div className="entity-cards">
              {filteredEntities.map((entity, i) => (
                <div key={i} className="entity-card" onClick={() => handleEntityClick(entity.name)}
                  style={{ borderLeftColor: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}>
                  <div className="entity-card-name">{entity.name}</div>
                  <div className="entity-card-meta">
                    <span className="entity-card-type" style={{ color: ENTITY_COLORS[entity.type] || ENTITY_COLORS.UNKNOWN }}>{entity.type}</span>
                    <span className="entity-card-connections">{entity.connections} connections</span>
                  </div>
                  {entity.source_files?.length > 0 && (
                    <div className="entity-card-files">
                      {entity.source_files.slice(0, 3).map((f, j) => <span key={j} className="file-tag">{f}</span>)}
                      {entity.source_files.length > 3 && <span className="file-tag">+{entity.source_files.length - 3} more</span>}
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
