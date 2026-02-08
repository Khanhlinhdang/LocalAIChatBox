import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  getLightRAGGraph,
  getLightRAGLabels,
  getLightRAGPopularLabels,
  searchLightRAGLabels,
  searchLightRAGEntities,
  editLightRAGEntity,
  editLightRAGRelation,
  getLightRAGHealth
} from '../api';

// ============================================================
// Color palette for entity types
// ============================================================
const ENTITY_COLORS = [
  '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
  '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
  '#86bc25', '#008fd5', '#e3120b', '#6b4c9a', '#eb7bc0',
  '#d4a017', '#2ca02c', '#00bfff', '#ff6347', '#8b4513',
];

function getEntityColor(entityType, colorMap) {
  if (!colorMap.has(entityType)) {
    const idx = colorMap.size % ENTITY_COLORS.length;
    colorMap.set(entityType, ENTITY_COLORS[idx]);
  }
  return colorMap.get(entityType);
}

// ============================================================
// Force-directed layout simulation
// ============================================================
function forceLayout(nodes, edges, width, height, iterations = 150) {
  const positions = {};
  const k = Math.sqrt((width * height) / Math.max(nodes.length, 1));
  
  // Initialize random positions
  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    const r = Math.min(width, height) * 0.35;
    positions[node.id] = {
      x: width / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 50,
      y: height / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 50,
      vx: 0,
      vy: 0,
    };
  });

  const edgeMap = {};
  edges.forEach(e => {
    if (!edgeMap[e.source]) edgeMap[e.source] = [];
    if (!edgeMap[e.target]) edgeMap[e.target] = [];
    edgeMap[e.source].push(e.target);
    edgeMap[e.target].push(e.source);
  });

  for (let iter = 0; iter < iterations; iter++) {
    const temp = 0.1 * (1 - iter / iterations);
    
    // Repulsive forces
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const n1 = positions[nodes[i].id];
        const n2 = positions[nodes[j].id];
        const dx = n1.x - n2.x;
        const dy = n1.y - n2.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (k * k) / dist;
        const fx = (dx / dist) * force * temp;
        const fy = (dy / dist) * force * temp;
        n1.vx += fx;
        n1.vy += fy;
        n2.vx -= fx;
        n2.vy -= fy;
      }
    }

    // Attractive forces (edges)
    edges.forEach(e => {
      const s = positions[e.source];
      const t = positions[e.target];
      if (!s || !t) return;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist * dist) / k;
      const fx = (dx / dist) * force * temp;
      const fy = (dy / dist) * force * temp;
      s.vx += fx;
      s.vy += fy;
      t.vx -= fx;
      t.vy -= fy;
    });

    // Gravity toward center
    nodes.forEach(node => {
      const pos = positions[node.id];
      const dx = width / 2 - pos.x;
      const dy = height / 2 - pos.y;
      pos.vx += dx * 0.001;
      pos.vy += dy * 0.001;
    });

    // Apply velocities
    nodes.forEach(node => {
      const pos = positions[node.id];
      const speed = Math.sqrt(pos.vx * pos.vx + pos.vy * pos.vy);
      const maxSpeed = 10;
      if (speed > maxSpeed) {
        pos.vx = (pos.vx / speed) * maxSpeed;
        pos.vy = (pos.vy / speed) * maxSpeed;
      }
      pos.x += pos.vx;
      pos.y += pos.vy;
      pos.vx *= 0.9;
      pos.vy *= 0.9;
      // Keep in bounds
      pos.x = Math.max(60, Math.min(width - 60, pos.x));
      pos.y = Math.max(60, Math.min(height - 60, pos.y));
    });
  }

  return positions;
}

// ============================================================
// WebGL Graph Renderer Component
// ============================================================
function GraphCanvas({
  nodes, edges, positions, colorMap,
  selectedNode, setSelectedNode,
  hoveredNode, setHoveredNode,
  zoom, pan, onPanChange, onZoomChange,
  showEdgeLabels, showNodeLabels,
}) {
  const canvasRef = useRef(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragNode, setDragNode] = useState(null);
  const [dragStart, setDragStart] = useState(null);

  const nodeMap = useMemo(() => {
    const m = {};
    nodes.forEach(n => { m[n.id] = n; });
    return m;
  }, [nodes]);

  // Calculate node degrees for sizing
  const degrees = useMemo(() => {
    const d = {};
    nodes.forEach(n => { d[n.id] = 0; });
    edges.forEach(e => {
      d[e.source] = (d[e.source] || 0) + 1;
      d[e.target] = (d[e.target] || 0) + 1;
    });
    return d;
  }, [nodes, edges]);

  const getNodeSize = useCallback((nodeId) => {
    const deg = degrees[nodeId] || 0;
    const maxDeg = Math.max(...Object.values(degrees), 1);
    const minSize = 6;
    const maxSize = 24;
    return minSize + (maxSize - minSize) * Math.sqrt(deg / maxDeg);
  }, [degrees]);

  // Draw graph
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(pan.x, pan.y);
    ctx.scale(zoom, zoom);

    // Draw edges
    edges.forEach(edge => {
      const sp = positions[edge.source];
      const tp = positions[edge.target];
      if (!sp || !tp) return;

      const isHighlighted = hoveredNode === edge.source || hoveredNode === edge.target ||
                            selectedNode === edge.source || selectedNode === edge.target;

      ctx.beginPath();
      // Curved edge
      const midX = (sp.x + tp.x) / 2;
      const midY = (sp.y + tp.y) / 2;
      const dx = tp.x - sp.x;
      const dy = tp.y - sp.y;
      const cx = midX - dy * 0.1;
      const cy = midY + dx * 0.1;
      
      ctx.moveTo(sp.x, sp.y);
      ctx.quadraticCurveTo(cx, cy, tp.x, tp.y);
      ctx.strokeStyle = isHighlighted ? '#60a5fa' : 'rgba(150,150,170,0.25)';
      ctx.lineWidth = isHighlighted ? 2 / zoom : 1 / zoom;
      ctx.stroke();

      // Edge label
      if (showEdgeLabels && edge.label && zoom > 0.6) {
        ctx.fillStyle = isHighlighted ? '#93c5fd' : 'rgba(150,150,170,0.5)';
        ctx.font = `${9 / zoom}px sans-serif`;
        ctx.textAlign = 'center';
        const label = edge.label.length > 20 ? edge.label.slice(0, 20) + '...' : edge.label;
        ctx.fillText(label, cx, cy - 4 / zoom);
      }

      // Arrow
      if (isHighlighted) {
        const angle = Math.atan2(tp.y - cy, tp.x - cx);
        const nodeSize = getNodeSize(edge.target);
        const ax = tp.x - Math.cos(angle) * (nodeSize + 2);
        const ay = tp.y - Math.sin(angle) * (nodeSize + 2);
        const arrowSize = 6 / zoom;
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax - arrowSize * Math.cos(angle - 0.4), ay - arrowSize * Math.sin(angle - 0.4));
        ctx.lineTo(ax - arrowSize * Math.cos(angle + 0.4), ay - arrowSize * Math.sin(angle + 0.4));
        ctx.closePath();
        ctx.fillStyle = '#60a5fa';
        ctx.fill();
      }
    });

    // Draw nodes
    nodes.forEach(node => {
      const pos = positions[node.id];
      if (!pos) return;
      const size = getNodeSize(node.id);
      const color = getEntityColor(node.entity_type, colorMap);
      const isSelected = selectedNode === node.id;
      const isHovered = hoveredNode === node.id;
      const isNeighbor = hoveredNode && edges.some(
        e => (e.source === hoveredNode && e.target === node.id) ||
             (e.target === hoveredNode && e.source === node.id)
      );
      const isDimmed = hoveredNode && !isHovered && !isNeighbor;

      // Node circle with border
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, size, 0, 2 * Math.PI);
      ctx.fillStyle = isDimmed ? 'rgba(100,100,120,0.3)' : color;
      ctx.fill();
      
      if (isSelected || isHovered) {
        ctx.strokeStyle = isSelected ? '#fbbf24' : '#60a5fa';
        ctx.lineWidth = 3 / zoom;
        ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.lineWidth = 1 / zoom;
        ctx.stroke();
      }

      // Node label
      if (showNodeLabels && (!isDimmed || isSelected) && zoom > 0.3) {
        ctx.fillStyle = isDimmed ? 'rgba(180,180,180,0.4)' : '#e2e8f0';
        ctx.font = `${Math.max(10, 11) / zoom}px sans-serif`;
        ctx.textAlign = 'center';
        const label = node.label.length > 25 ? node.label.slice(0, 25) + '...' : node.label;
        ctx.fillText(label, pos.x, pos.y + size + 14 / zoom);
      }
    });

    ctx.restore();
  }, [nodes, edges, positions, zoom, pan, selectedNode, hoveredNode, colorMap, showEdgeLabels, showNodeLabels, getNodeSize]);

  // Mouse event handlers
  const getGraphCoords = useCallback((e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left - pan.x) / zoom,
      y: (e.clientY - rect.top - pan.y) / zoom,
    };
  }, [zoom, pan]);

  const findNodeAt = useCallback((gx, gy) => {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const pos = positions[nodes[i].id];
      if (!pos) continue;
      const size = getNodeSize(nodes[i].id);
      const dx = gx - pos.x;
      const dy = gy - pos.y;
      if (dx * dx + dy * dy <= (size + 4) * (size + 4)) {
        return nodes[i];
      }
    }
    return null;
  }, [nodes, positions, getNodeSize]);

  const handleMouseDown = (e) => {
    const coords = getGraphCoords(e);
    const node = findNodeAt(coords.x, coords.y);
    if (node) {
      setDragNode(node.id);
      setDragStart({ x: e.clientX, y: e.clientY });
    } else {
      setIsDragging(true);
      setDragStart({ x: e.clientX, y: e.clientY });
    }
  };

  const handleMouseMove = (e) => {
    const coords = getGraphCoords(e);
    
    if (dragNode && dragStart) {
      // Drag node
      const pos = positions[dragNode];
      if (pos) {
        pos.x = coords.x;
        pos.y = coords.y;
        // Force re-render
        setHoveredNode(dragNode);
      }
    } else if (isDragging && dragStart) {
      // Pan canvas
      const dx = e.clientX - dragStart.x;
      const dy = e.clientY - dragStart.y;
      onPanChange({ x: pan.x + dx, y: pan.y + dy });
      setDragStart({ x: e.clientX, y: e.clientY });
    } else {
      const node = findNodeAt(coords.x, coords.y);
      setHoveredNode(node ? node.id : null);
    }
  };

  const handleMouseUp = (e) => {
    if (dragNode && dragStart) {
      const dist = Math.sqrt(
        (e.clientX - dragStart.x) ** 2 + (e.clientY - dragStart.y) ** 2
      );
      if (dist < 5) {
        // Click (not drag)
        setSelectedNode(dragNode === selectedNode ? null : dragNode);
      }
    } else if (!isDragging) {
      setSelectedNode(null);
    }
    setDragNode(null);
    setIsDragging(false);
    setDragStart(null);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.1, Math.min(5, zoom * factor));
    
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    
    const newPanX = mx - (mx - pan.x) * (newZoom / zoom);
    const newPanY = my - (my - pan.y) * (newZoom / zoom);
    
    onZoomChange(newZoom);
    onPanChange({ x: newPanX, y: newPanY });
  };

  return (
    <canvas
      ref={canvasRef}
      width={1200}
      height={700}
      style={{ width: '100%', height: '100%', cursor: dragNode ? 'grabbing' : hoveredNode ? 'pointer' : 'grab' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => { setHoveredNode(null); setDragNode(null); setIsDragging(false); }}
      onWheel={handleWheel}
    />
  );
}

// ============================================================
// Properties Panel Component
// ============================================================
function PropertiesPanel({ node, edges, nodes, onEditEntity, onEditRelation, onSelectNode }) {
  const [editing, setEditing] = useState(null);
  const [editValue, setEditValue] = useState('');

  if (!node) return null;

  const nodeEdges = edges.filter(e => e.source === node.id || e.target === node.id);
  const neighbors = [...new Set(nodeEdges.map(e => e.source === node.id ? e.target : e.source))];

  const handleSave = async (field) => {
    await onEditEntity(node.id, { [field]: editValue });
    setEditing(null);
  };

  return (
    <div style={{
      position: 'absolute', top: 10, right: 10, width: 320,
      background: 'rgba(30,30,40,0.95)', borderRadius: 12, padding: 16,
      border: '1px solid rgba(100,100,150,0.3)', maxHeight: 'calc(100% - 20px)',
      overflow: 'auto', fontSize: 13, color: '#e2e8f0',
    }}>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: '#93c5fd' }}>
        📋 Entity Properties
      </div>
      
      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#94a3b8', fontSize: 11 }}>NAME</span>
        <div style={{ fontWeight: 600 }}>{node.label}</div>
      </div>
      
      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#94a3b8', fontSize: 11 }}>TYPE</span>
        {editing === 'entity_type' ? (
          <div style={{ display: 'flex', gap: 4 }}>
            <input value={editValue} onChange={e => setEditValue(e.target.value)}
              style={{ flex: 1, background: '#1e293b', border: '1px solid #475569', borderRadius: 4, padding: '2px 6px', color: '#e2e8f0' }}
              autoFocus onKeyDown={e => e.key === 'Enter' && handleSave('entity_type')} />
            <button onClick={() => handleSave('entity_type')} style={{ background: '#3b82f6', border: 'none', borderRadius: 4, padding: '2px 8px', color: 'white', cursor: 'pointer' }}>✓</button>
          </div>
        ) : (
          <div onClick={() => { setEditing('entity_type'); setEditValue(node.entity_type); }}
            style={{ cursor: 'pointer', padding: '2px 8px', background: '#1e293b', borderRadius: 4 }}>
            {node.entity_type}
          </div>
        )}
      </div>
      
      <div style={{ marginBottom: 8 }}>
        <span style={{ color: '#94a3b8', fontSize: 11 }}>DESCRIPTION</span>
        {editing === 'description' ? (
          <div>
            <textarea value={editValue} onChange={e => setEditValue(e.target.value)}
              style={{ width: '100%', background: '#1e293b', border: '1px solid #475569', borderRadius: 4, padding: 6, color: '#e2e8f0', minHeight: 60 }}
              autoFocus />
            <button onClick={() => handleSave('description')} style={{ background: '#3b82f6', border: 'none', borderRadius: 4, padding: '2px 8px', color: 'white', cursor: 'pointer', marginTop: 4 }}>Save</button>
          </div>
        ) : (
          <div onClick={() => { setEditing('description'); setEditValue(node.description || ''); }}
            style={{ cursor: 'pointer', padding: 6, background: '#1e293b', borderRadius: 4, minHeight: 30 }}>
            {node.description || 'Click to add description...'}
          </div>
        )}
      </div>

      <div style={{ marginTop: 16 }}>
        <span style={{ color: '#94a3b8', fontSize: 11 }}>CONNECTIONS ({nodeEdges.length})</span>
        {nodeEdges.slice(0, 20).map((edge, i) => {
          const otherId = edge.source === node.id ? edge.target : edge.source;
          return (
            <div key={i} onClick={() => onSelectNode(otherId)}
              style={{ padding: '4px 8px', margin: '2px 0', background: '#1e293b', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}>
              <span style={{ color: '#60a5fa' }}>{otherId}</span>
              <span style={{ color: '#94a3b8', marginLeft: 8 }}>{edge.label || edge.keywords || ''}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// Main LightRAG Graph Page
// ============================================================
export default function LightRAGGraphPage() {
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [positions, setPositions] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null);
  const colorMapRef = useRef(new Map());

  // View state
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  // Settings
  const [showEdgeLabels, setShowEdgeLabels] = useState(false);
  const [showNodeLabels, setShowNodeLabels] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showLegend, setShowLegend] = useState(true);

  // Search & filter
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [filterLabel, setFilterLabel] = useState('');
  const [availableLabels, setAvailableLabels] = useState([]);
  const [maxNodes, setMaxNodes] = useState(500);
  const [maxDepth, setMaxDepth] = useState(3);

  // Load graph data
  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getLightRAGGraph(filterLabel || null, maxDepth, maxNodes);
      const data = res.data;
      
      if (data.nodes && data.nodes.length > 0) {
        setNodes(data.nodes);
        setEdges(data.edges || []);
        
        // Calculate layout
        const layoutPositions = forceLayout(data.nodes, data.edges || [], 1200, 700, 100);
        setPositions(layoutPositions);
      } else {
        setNodes([]);
        setEdges([]);
        setPositions({});
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    }
    setLoading(false);
  }, [filterLabel, maxNodes, maxDepth]);

  // Load labels
  const loadLabels = useCallback(async () => {
    try {
      const res = await getLightRAGPopularLabels(30);
      setAvailableLabels(res.data.labels || []);
    } catch (e) {
      console.warn('Failed to load labels:', e);
    }
  }, []);

  // Load health
  const loadHealth = useCallback(async () => {
    try {
      const res = await getLightRAGHealth();
      setHealth(res.data);
    } catch (e) {
      console.warn('Health check failed:', e);
    }
  }, []);

  useEffect(() => {
    loadGraph();
    loadLabels();
    loadHealth();
  }, [loadGraph, loadLabels, loadHealth]);

  // Search entities
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    try {
      const res = await searchLightRAGEntities(query);
      setSearchResults(res.data.entities || []);
    } catch (e) {
      setSearchResults([]);
    }
  };

  // Focus on a node
  const focusNode = useCallback((nodeId) => {
    const pos = positions[nodeId];
    if (pos) {
      setSelectedNode(nodeId);
      setPan({ x: 600 - pos.x * zoom, y: 350 - pos.y * zoom });
    }
  }, [positions, zoom]);

  // Edit entity
  const handleEditEntity = async (entityName, data) => {
    try {
      await editLightRAGEntity(entityName, data);
      // Refresh
      await loadGraph();
    } catch (e) {
      console.error('Edit entity failed:', e);
    }
  };

  // Get selected node data
  const selectedNodeData = useMemo(() => {
    if (!selectedNode) return null;
    return nodes.find(n => n.id === selectedNode);
  }, [selectedNode, nodes]);

  // Legend
  const legendItems = useMemo(() => {
    const types = {};
    nodes.forEach(n => {
      if (!types[n.entity_type]) {
        types[n.entity_type] = {
          type: n.entity_type,
          color: getEntityColor(n.entity_type, colorMapRef.current),
          count: 0,
        };
      }
      types[n.entity_type].count++;
    });
    return Object.values(types).sort((a, b) => b.count - a.count);
  }, [nodes]);

  // Reset view
  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setSelectedNode(null);
    setHoveredNode(null);
  };

  // Re-layout
  const reLayout = () => {
    if (nodes.length > 0) {
      const newPositions = forceLayout(nodes, edges, 1200, 700, 150);
      setPositions(newPositions);
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#0f1117' }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '8px 16px',
        background: '#1a1b23', borderBottom: '1px solid rgba(100,100,150,0.2)',
        flexWrap: 'wrap',
      }}>
        <h2 style={{ margin: 0, fontSize: 16, color: '#93c5fd', fontWeight: 600 }}>
          ⚡ LightRAG Knowledge Graph
        </h2>
        
        {/* Health badge */}
        {health && (
          <span style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 10,
            background: health.initialized ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)',
            color: health.initialized ? '#22c55e' : '#ef4444',
          }}>
            {health.initialized ? `${health.graph_nodes || 0} nodes • ${health.graph_edges || 0} edges` : 'Not initialized'}
          </span>
        )}
        
        <div style={{ flex: 1 }} />

        {/* Search */}
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            placeholder="Search entities..."
            value={searchQuery}
            onChange={e => handleSearch(e.target.value)}
            style={{
              background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
              padding: '5px 12px', color: '#e2e8f0', width: 200, fontSize: 13,
            }}
          />
          {searchResults.length > 0 && (
            <div style={{
              position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
              background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
              maxHeight: 200, overflow: 'auto', marginTop: 4,
            }}>
              {searchResults.map((r, i) => (
                <div key={i} onClick={() => { focusNode(r.id); setSearchQuery(''); setSearchResults([]); }}
                  style={{ padding: '6px 12px', cursor: 'pointer', borderBottom: '1px solid #1e293b', fontSize: 12 }}
                  onMouseEnter={e => e.target.style.background = '#334155'}
                  onMouseLeave={e => e.target.style.background = 'transparent'}>
                  <span style={{ color: getEntityColor(r.entity_type, colorMapRef.current) }}>●</span>
                  <span style={{ marginLeft: 6, color: '#e2e8f0' }}>{r.label}</span>
                  <span style={{ float: 'right', color: '#64748b', fontSize: 11 }}>{r.entity_type}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Label filter */}
        <select
          value={filterLabel}
          onChange={e => setFilterLabel(e.target.value)}
          style={{
            background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
            padding: '5px 8px', color: '#e2e8f0', fontSize: 13,
          }}
        >
          <option value="">All Labels</option>
          {availableLabels.map(l => (
            <option key={l.label} value={l.label}>{l.label} ({l.count})</option>
          ))}
        </select>

        {/* Controls */}
        <button onClick={reLayout} title="Re-layout" style={btnStyle}>🔄 Layout</button>
        <button onClick={resetView} title="Reset view" style={btnStyle}>🎯 Reset</button>
        <button onClick={() => setShowLegend(!showLegend)} title="Legend" style={btnStyle}>
          {showLegend ? '🏷️' : '🏷️'}
        </button>
        <button onClick={() => setShowSettings(!showSettings)} title="Settings" style={btnStyle}>⚙️</button>
        <button onClick={loadGraph} title="Refresh" style={btnStyle}>🔃 Refresh</button>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {loading && (
          <div style={{
            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(15,17,23,0.8)', zIndex: 50,
          }}>
            <div style={{ textAlign: 'center', color: '#94a3b8' }}>
              <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
              <div>Loading graph...</div>
            </div>
          </div>
        )}

        {error && (
          <div style={{
            position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)',
            background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: 8, padding: '8px 16px', color: '#fca5a5', zIndex: 50, fontSize: 13,
          }}>
            ⚠️ {error}
          </div>
        )}

        {nodes.length === 0 && !loading && (
          <div style={{
            position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
            textAlign: 'center', color: '#64748b',
          }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>🕸️</div>
            <div style={{ fontSize: 16 }}>No graph data</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>Upload documents to LightRAG to build the knowledge graph</div>
          </div>
        )}

        {/* Graph canvas */}
        <GraphCanvas
          nodes={nodes}
          edges={edges}
          positions={positions}
          colorMap={colorMapRef.current}
          selectedNode={selectedNode}
          setSelectedNode={setSelectedNode}
          hoveredNode={hoveredNode}
          setHoveredNode={setHoveredNode}
          zoom={zoom}
          pan={pan}
          onPanChange={setPan}
          onZoomChange={setZoom}
          showEdgeLabels={showEdgeLabels}
          showNodeLabels={showNodeLabels}
        />

        {/* Zoom controls */}
        <div style={{
          position: 'absolute', bottom: 16, left: 16, display: 'flex',
          flexDirection: 'column', gap: 4,
        }}>
          <button onClick={() => setZoom(z => Math.min(5, z * 1.3))} style={zoomBtnStyle}>+</button>
          <button onClick={() => setZoom(z => Math.max(0.1, z / 1.3))} style={zoomBtnStyle}>−</button>
          <button onClick={resetView} style={zoomBtnStyle}>⟲</button>
          <div style={{ textAlign: 'center', fontSize: 10, color: '#64748b', marginTop: 2 }}>
            {Math.round(zoom * 100)}%
          </div>
        </div>

        {/* Legend */}
        {showLegend && legendItems.length > 0 && (
          <div style={{
            position: 'absolute', bottom: 16, right: selectedNodeData ? 340 : 16,
            background: 'rgba(30,30,40,0.9)', borderRadius: 8, padding: 12,
            border: '1px solid rgba(100,100,150,0.3)', maxHeight: 200,
            overflow: 'auto', minWidth: 120,
          }}>
            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6, fontWeight: 600 }}>ENTITY TYPES</div>
            {legendItems.map(item => (
              <div key={item.type} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3, fontSize: 12 }}
                onClick={() => setFilterLabel(item.type === filterLabel ? '' : item.type)}
                role="button" tabIndex={0}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: item.color, flexShrink: 0 }} />
                <span style={{ color: '#e2e8f0', cursor: 'pointer' }}>{item.type}</span>
                <span style={{ color: '#64748b', fontSize: 10, marginLeft: 'auto' }}>{item.count}</span>
              </div>
            ))}
          </div>
        )}

        {/* Settings panel */}
        {showSettings && (
          <div style={{
            position: 'absolute', top: 10, left: 10,
            background: 'rgba(30,30,40,0.95)', borderRadius: 10, padding: 16,
            border: '1px solid rgba(100,100,150,0.3)', width: 220, fontSize: 13,
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#93c5fd', marginBottom: 12 }}>⚙️ Graph Settings</div>
            
            <label style={labelStyle}>
              <input type="checkbox" checked={showNodeLabels} onChange={e => setShowNodeLabels(e.target.checked)} />
              Show node labels
            </label>
            <label style={labelStyle}>
              <input type="checkbox" checked={showEdgeLabels} onChange={e => setShowEdgeLabels(e.target.checked)} />
              Show edge labels
            </label>
            <label style={labelStyle}>
              <input type="checkbox" checked={showLegend} onChange={e => setShowLegend(e.target.checked)} />
              Show legend
            </label>
            
            <div style={{ marginTop: 12 }}>
              <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 4 }}>Max Nodes</div>
              <input type="number" value={maxNodes} onChange={e => setMaxNodes(parseInt(e.target.value) || 100)}
                min={10} max={5000} style={inputStyle} />
            </div>
            <div style={{ marginTop: 8 }}>
              <div style={{ color: '#94a3b8', fontSize: 11, marginBottom: 4 }}>Max Depth</div>
              <input type="number" value={maxDepth} onChange={e => setMaxDepth(parseInt(e.target.value) || 1)}
                min={1} max={10} style={inputStyle} />
            </div>
            
            <button onClick={() => { loadGraph(); setShowSettings(false); }}
              style={{ ...btnStyle, width: '100%', marginTop: 12, justifyContent: 'center' }}>
              Apply & Refresh
            </button>
          </div>
        )}

        {/* Properties panel */}
        {selectedNodeData && (
          <PropertiesPanel
            node={selectedNodeData}
            edges={edges}
            nodes={nodes}
            onEditEntity={handleEditEntity}
            onEditRelation={() => {}}
            onSelectNode={focusNode}
          />
        )}
      </div>

      {/* Status bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 16, padding: '4px 16px',
        background: '#1a1b23', borderTop: '1px solid rgba(100,100,150,0.2)',
        fontSize: 11, color: '#64748b',
      }}>
        <span>Nodes: {nodes.length}</span>
        <span>Edges: {edges.length}</span>
        {health && <span>Total: {health.graph_nodes || 0} nodes / {health.graph_edges || 0} edges</span>}
        <span>Zoom: {Math.round(zoom * 100)}%</span>
        {selectedNode && <span style={{ color: '#93c5fd' }}>Selected: {selectedNode}</span>}
      </div>
    </div>
  );
}

// ============================================================
// Styles
// ============================================================
const btnStyle = {
  background: '#1e293b', border: '1px solid #334155', borderRadius: 6,
  padding: '5px 10px', color: '#e2e8f0', cursor: 'pointer', fontSize: 12,
  display: 'flex', alignItems: 'center', gap: 4,
};

const zoomBtnStyle = {
  background: 'rgba(30,30,40,0.9)', border: '1px solid rgba(100,100,150,0.3)',
  borderRadius: 6, width: 32, height: 32, color: '#e2e8f0', cursor: 'pointer',
  fontSize: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
};

const labelStyle = {
  display: 'flex', alignItems: 'center', gap: 6, color: '#e2e8f0',
  marginBottom: 6, cursor: 'pointer', fontSize: 12,
};

const inputStyle = {
  width: '100%', background: '#1e293b', border: '1px solid #334155',
  borderRadius: 4, padding: '4px 8px', color: '#e2e8f0', fontSize: 12,
};
