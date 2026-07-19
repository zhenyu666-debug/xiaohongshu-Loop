import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { MOCK_NODES, MOCK_EDGES, GraphNode, GraphEdge } from '../data/mockData';

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimEdge {
  id: string;
  source: SimNode | string;
  target: SimNode | string;
  type: string;
  score?: number;
}

const NODE_COLORS: Record<string, string> = {
  Account: '#2d9cdb', IP: '#27ae60', Email: '#f2994a',
  LastName: '#bb6bd9', Phone: '#eb5757', Address: '#f2c94c',
  Device: '#6fcfea', VideoPlay: '#95d5b2', Video: '#d4a373',
  MergedAccount: '#ff9f1c',
};

export function ExploreGraph() {
  const svgRef = useRef<SVGSVGElement>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(['Account', 'IP', 'Email', 'LastName', 'Phone', 'Address', 'Device', 'VideoPlay', 'Video', 'MergedAccount']));
  const [selectedEdgeTypes, setSelectedEdgeTypes] = useState<Set<string>>(new Set(['SAME_OWNER', 'MERGED_INTO', 'HAS_IP', 'HAS_EMAIL', 'HAS_LASTNAME', 'HAS_PHONE', 'HAS_ADDRESS', 'HAS_DEVICE', 'PLAYS_VIDEO', 'VIDEO_PLAYED']));
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [limit, setLimit] = useState(15);
  const [showOnlySameOwner, setShowOnlySameOwner] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedEdgeFilter, setSelectedEdgeFilter] = useState<string>('');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const allTypes = [...new Set(MOCK_NODES.map(n => n.type))];
  const allEdgeTypes = [...new Set(MOCK_EDGES.map(e => e.type))];

  const toggleType = useCallback((type: string) => {
    setSelectedTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type); else next.add(type);
      return next;
    });
  }, []);

  const toggleEdgeType = useCallback((type: string) => {
    setSelectedEdgeTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type); else next.add(type);
      return next;
    });
  }, []);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const W = svgRef.current.clientWidth || 900;
    const H = svgRef.current.clientHeight || 600;

    // Filter nodes and edges
    const visibleNodes = MOCK_NODES.filter(n => selectedTypes.has(n.type)).slice(0, limit);
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

    let visibleEdges = MOCK_EDGES.filter(e =>
      visibleNodeIds.has(e.source) &&
      visibleNodeIds.has(e.target) &&
      selectedEdgeTypes.has(e.type)
    );

    if (showOnlySameOwner) {
      visibleEdges = visibleEdges.filter(e => e.type === 'SAME_OWNER' || e.type === 'MERGED_INTO');
    }

    if (selectedEdgeFilter) {
      visibleEdges = visibleEdges.filter(e => e.type === selectedEdgeFilter);
    }

    // Deep copy for simulation
    const simNodes: SimNode[] = visibleNodes.map(n => ({ ...n }));
    const nodeMap = new Map(simNodes.map(n => [n.id, n]));

    const simEdges: SimEdge[] = visibleEdges.map(e => ({
      ...e,
      source: nodeMap.get(e.source) || e.source,
      target: nodeMap.get(e.target) || e.target,
    }));

    // Arrow marker
    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', d => {
        const n = nodeMap.get(d);
        return n ? 24 : 18;
      })
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#30363d');

    // Arrow for SAME_OWNER
    defs.append('marker')
      .attr('id', 'arrow-same')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 26)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#f2994a');

    const g = svg.append('g');

    // Edge elements
    const edgeG = g.append('g').attr('class', 'edges');
    const edgeSel = edgeG.selectAll<SVGLineElement, SimEdge>('line')
      .data(simEdges, d => d.id)
      .enter()
      .append('line')
      .attr('stroke', d => {
        if (d.type === 'SAME_OWNER') return '#f2994a';
        if (d.type === 'MERGED_INTO') return '#ff9f1c';
        return '#30363d';
      })
      .attr('stroke-width', d => d.type === 'SAME_OWNER' ? 2.5 : d.type === 'MERGED_INTO' ? 2 : 1)
      .attr('stroke-opacity', d => d.type === 'SAME_OWNER' ? 0.9 : 0.6)
      .attr('marker-end', d => {
        if (d.type === 'SAME_OWNER' || d.type === 'MERGED_INTO') return 'none';
        return 'url(#arrow)';
      })
      .attr('stroke-dasharray', d => {
        if (d.type === 'MERGED_INTO') return '5,3';
        return 'none';
      });

    // Node groups
    const nodeG = g.append('g').attr('class', 'nodes');
    const nodeSel = nodeG.selectAll<SVGGElement, SimNode>('g')
      .data(simNodes, d => d.id)
      .enter()
      .append('g')
      .attr('class', 'graph-node')
      .attr('cursor', 'pointer')
      .on('click', (_, d) => setSelectedNode(d as GraphNode))
      .on('mouseenter', (_, d) => setHoveredNode(d.id))
      .on('mouseleave', () => setHoveredNode(null));

    // Glow filter for selected
    defs.append('filter').attr('id', 'glow').append('feGaussianBlur')
      .attr('stdDeviation', 3).attr('result', 'coloredBlur');
    const feMerge = defs.select('filter').append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Same-owner glow filter
    defs.append('filter').attr('id', 'glow-same').append('feGaussianBlur')
      .attr('stdDeviation', 4).attr('result', 'coloredBlur');
    const feMerge2 = defs.select('[id="glow-same"]').append('feMerge');
    feMerge2.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge2.append('feMergeNode').attr('in', 'SourceGraphic');

    // Node circles
    nodeSel.append('circle')
      .attr('r', d => d.type === 'Account' ? 22 : d.type === 'MergedAccount' ? 18 : 14)
      .attr('fill', d => NODE_COLORS[d.type] || '#6e7681')
      .attr('fill-opacity', d => d.type === 'Account' ? 1 : 0.85)
      .attr('stroke', d => {
        if (d.type === 'Account') return '#ffffff33';
        return '#ffffff18';
      })
      .attr('stroke-width', d => d.type === 'Account' ? 1.5 : 1)
      .attr('filter', d => d.type === 'Account' ? 'url(#glow)' : null);

    // Node labels
    nodeSel.append('text')
      .text(d => d.id)
      .attr('text-anchor', 'middle')
      .attr('dy', '3px')
      .attr('font-size', d => d.type === 'Account' ? 10 : 9)
      .attr('font-weight', d => d.type === 'Account' ? 700 : 500)
      .attr('fill', 'white')
      .attr('font-family', 'Inter, sans-serif')
      .attr('pointer-events', 'none');

    // Same-owner edges — highlight connected nodes
    nodeSel.on('mouseenter.glow', (event, d) => {
      const connectedEdges = simEdges.filter(e => {
        const src = typeof e.source === 'string' ? e.source : (e.source as SimNode).id;
        const tgt = typeof e.target === 'string' ? e.target : (e.target as SimNode).id;
        return src === d.id || tgt === d.id;
      });
      edgeSel.attr('stroke-opacity', e => {
        const src = typeof e.source === 'string' ? e.source : (e.source as SimNode).id;
        const tgt = typeof e.target === 'string' ? e.target : (e.target as SimNode).id;
        return src === d.id || tgt === d.id ? 1 : 0.1;
      });
    });

    // Zoom
    svg.call(d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', e => g.attr('transform', e.transform.toString()))
    );

    // Simulation
    const sim = d3.forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimEdge>(simEdges)
        .id(d => d.id)
        .distance(d => d.type === 'SAME_OWNER' ? 80 : 60)
        .strength(d => d.type === 'SAME_OWNER' ? 0.8 : 0.3))
      .force('charge', d3.forceManyBody().strength(d => d.type === 'Account' ? -400 : -150))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius(d => (d as SimNode).type === 'Account' ? 30 : 18));

    simulationRef.current = sim;

    sim.on('tick', () => {
      edgeSel
        .attr('x1', d => (d.source as SimNode).x)
        .attr('y1', d => (d.source as SimNode).y)
        .attr('x2', d => (d.target as SimNode).x)
        .attr('y2', d => (d.target as SimNode).y);

      nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); };
  }, [selectedTypes, selectedEdgeTypes, limit, showOnlySameOwner, selectedEdgeFilter]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        height: 'var(--header-height)',
        borderBottom: '1px solid var(--tg-dark-border)',
        display: 'flex', alignItems: 'center',
        padding: '0 20px', gap: 12,
        background: 'var(--tg-dark-bg)',
      }}>
        <span style={{ fontWeight: 600, fontSize: 14 }}>Explore Graph</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-muted)' }}>·</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-secondary)' }}>Interactive Graph Viewer</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--tg-text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showOnlySameOwner}
              onChange={e => setShowOnlySameOwner(e.target.checked)}
              style={{ accentColor: 'var(--tg-blue)' }}
            />
            Same Owner Only
          </label>
          <select
            value={selectedEdgeFilter}
            onChange={e => setSelectedEdgeFilter(e.target.value)}
            style={{ fontSize: 12 }}
          >
            <option value="">All Edges</option>
            {allEdgeTypes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--tg-text-secondary)' }}>
            Limit:
            <input
              type="number"
              value={limit}
              onChange={e => setLimit(Math.max(5, parseInt(e.target.value) || 5))}
              min={5} max={30}
              style={{ width: 50, padding: '2px 6px', fontSize: 12 }}
            />
          </label>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left sidebar: filters */}
        <div style={{
          width: 200, minWidth: 200,
          borderRight: '1px solid var(--tg-dark-border)',
          overflowY: 'auto',
          padding: '12px 0',
          background: 'var(--tg-dark-card)',
        }}>
          {/* Vertex types */}
          <div style={{ padding: '0 14px 12px' }}>
            <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
              Vertex Types
            </div>
            {allTypes.map(type => (
              <label key={type} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '3px 0', fontSize: 12,
                cursor: 'pointer',
                color: selectedTypes.has(type) ? 'var(--tg-text-primary)' : 'var(--tg-text-muted)',
              }}>
                <input
                  type="checkbox"
                  checked={selectedTypes.has(type)}
                  onChange={() => toggleType(type)}
                  style={{ accentColor: NODE_COLORS[type] }}
                />
                <span style={{
                  width: 9, height: 9, borderRadius: '50%',
                  background: NODE_COLORS[type] || '#6e7681',
                  display: 'inline-block', flexShrink: 0,
                }} />
                {type}
              </label>
            ))}
          </div>

          <div className="divider" style={{ margin: '0 14px' }} />

          {/* Edge types */}
          <div style={{ padding: '12px 14px' }}>
            <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
              Edge Types
            </div>
            {allEdgeTypes.map(type => (
              <label key={type} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '3px 0', fontSize: 12,
                cursor: 'pointer',
                color: selectedEdgeTypes.has(type) ? 'var(--tg-text-primary)' : 'var(--tg-text-muted)',
              }}>
                <input
                  type="checkbox"
                  checked={selectedEdgeTypes.has(type)}
                  onChange={() => toggleEdgeType(type)}
                  style={{ accentColor: type === 'SAME_OWNER' ? '#f2994a' : type === 'MERGED_INTO' ? '#ff9f1c' : 'var(--tg-blue)' }}
                />
                <span style={{
                  color: type === 'SAME_OWNER' ? '#f2994a' : type === 'MERGED_INTO' ? '#ff9f1c' : 'var(--tg-text-muted)',
                  fontSize: 10,
                  fontFamily: 'JetBrains Mono, monospace',
                }}>
                  {type.length > 12 ? type.slice(0, 11) + '…' : type}
                </span>
              </label>
            ))}
          </div>

          <div className="divider" style={{ margin: '0 14px' }} />

          {/* Stats */}
          <div style={{ padding: '12px 14px' }}>
            <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
              Graph Stats
            </div>
            <div style={{ fontSize: 11, color: 'var(--tg-text-secondary)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span>Vertices:</span>
                <span style={{ color: 'var(--tg-blue)', fontWeight: 600 }}>{MOCK_NODES.filter(n => selectedTypes.has(n.type)).length}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span>Edges:</span>
                <span style={{ color: 'var(--tg-blue)', fontWeight: 600 }}>{MOCK_EDGES.filter(e => selectedEdgeTypes.has(e.type)).length}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span>Same Owner:</span>
                <span style={{ color: '#f2994a', fontWeight: 600 }}>{MOCK_EDGES.filter(e => e.type === 'SAME_OWNER').length}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Merged Into:</span>
                <span style={{ color: '#ff9f1c', fontWeight: 600 }}>{MOCK_EDGES.filter(e => e.type === 'MERGED_INTO').length}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Graph canvas */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'var(--tg-dark-bg)' }}>
          <svg ref={svgRef} className="graph-svg" />

          {/* Bottom legend */}
          <div style={{
            position: 'absolute', bottom: 12, left: 12,
            background: 'rgba(13,17,23,0.9)',
            border: '1px solid var(--tg-dark-border)',
            borderRadius: 6, padding: '8px 12px',
            fontSize: 11,
          }}>
            <div style={{ color: 'var(--tg-text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Legend
            </div>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#2d9cdb', display: 'inline-block' }} />
                Account
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#27ae60', display: 'inline-block' }} />
                IP
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#f2994a', display: 'inline-block' }} />
                Email
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 16, height: 2, background: '#f2994a', display: 'inline-block', borderRadius: 1 }} />
                SAME_OWNER
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 16, height: 2, background: '#ff9f1c', display: 'inline-block', borderRadius: 1, borderTop: '2px dashed #ff9f1c' }} />
                MERGED_INTO
              </span>
            </div>
          </div>

          {/* Instructions */}
          <div style={{
            position: 'absolute', top: 12, right: 12,
            background: 'rgba(13,17,23,0.8)',
            border: '1px solid var(--tg-dark-border)',
            borderRadius: 4, padding: '4px 10px',
            fontSize: 10, color: 'var(--tg-text-muted)',
          }}>
            Click node to inspect · Scroll to zoom · Drag to pan
          </div>
        </div>

        {/* Right: Node inspector */}
        {selectedNode && (
          <div style={{
            width: 260, minWidth: 260,
            borderLeft: '1px solid var(--tg-dark-border)',
            overflowY: 'auto',
            background: 'var(--tg-dark-card)',
            padding: 16,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontSize: 13 }}>Vertex Inspector</h3>
              <button
                className="btn btn-secondary btn-xs"
                onClick={() => setSelectedNode(null)}
                style={{ padding: '2px 8px' }}
              >
                ✕
              </button>
            </div>

            {/* Node badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <span style={{
                width: 36, height: 36, borderRadius: '50%',
                background: NODE_COLORS[selectedNode.type] || '#6e7681',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700, color: 'white',
              }}>
                {selectedNode.type.slice(0, 2)}
              </span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13 }}>{selectedNode.id}</div>
                <span className="badge">{selectedNode.type}</span>
              </div>
            </div>

            {/* Properties */}
            <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Properties
            </div>
            <div style={{ background: 'var(--tg-dark-bg)', borderRadius: 6, padding: 10, marginBottom: 14 }}>
              {Object.entries(selectedNode.properties).map(([k, v]) => (
                <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--tg-dark-border)', fontSize: 12 }}>
                  <span style={{ color: 'var(--tg-text-muted)', fontFamily: 'JetBrains Mono, monospace' }}>{k}</span>
                  <span style={{ color: 'var(--tg-text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>{String(v)}</span>
                </div>
              ))}
            </div>

            {/* Connected edges */}
            <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Connected Edges
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {MOCK_EDGES
                .filter(e => e.source === selectedNode.id || e.target === selectedNode.id)
                .map(e => {
                  const other = e.source === selectedNode.id ? e.target : e.source;
                  return (
                    <div key={e.id} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      background: 'var(--tg-dark-bg)', borderRadius: 4,
                      padding: '5px 8px', fontSize: 11,
                    }}>
                      <span style={{
                        color: e.type === 'SAME_OWNER' ? '#f2994a' : e.type === 'MERGED_INTO' ? '#ff9f1c' : 'var(--tg-text-muted)',
                        fontFamily: 'JetBrains Mono, monospace', fontSize: 10,
                      }}>
                        {e.type}
                      </span>
                      <span style={{ color: 'var(--tg-text-muted)' }}>→</span>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{other}</span>
                      {e.score !== undefined && (
                        <span style={{ marginLeft: 'auto', color: '#f2994a', fontFamily: 'JetBrains Mono, monospace' }}>
                          {e.score.toFixed(2)}
                        </span>
                      )}
                    </div>
                  );
                })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
