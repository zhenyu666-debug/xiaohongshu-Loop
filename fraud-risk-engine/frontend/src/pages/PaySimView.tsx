import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';

// ---------------------------------------------------------------------------
// Types — match the /api/bankfraud/sample response
// ---------------------------------------------------------------------------

export interface BankFraudNode {
  id: string;
  label: string;
  type: 'fraud' | 'normal';
  is_fraud: number;
  color: string;
  radius: number;
  features: number[];
}

export interface BankFraudEdge {
  source: string;
  target: string;
  type: string;
  color: string;
  amount: number;
}

export interface BankFraudStats {
  total_count: number;
  fraud_count: number;
  normal_count: number;
  fraud_rate: number;
  feature_names: string[];
  fraud_mean: number[];
  normal_mean: number[];
}

export interface BankFraudAPIResponse {
  ok: boolean;
  source: string;
  total_rows: number;
  stats: BankFraudStats;
  nodes: BankFraudNode[];
  edges: BankFraudEdge[];
}

// ---------------------------------------------------------------------------
// Feature heatmap chart
// ---------------------------------------------------------------------------

function FeatureHeatmap({ stats }: { stats: BankFraudStats }) {
  const { feature_names, fraud_mean, normal_mean } = stats;
  const W = 180, H = 120, PAD = 24;
  const max = Math.max(...fraud_mean, ...normal_mean, 0.01);
  const n = feature_names.length;
  const bh = (H - PAD * 2) / n;

  return (
    <div style={{ padding: '12px 14px', borderTop: '1px solid var(--tg-dark-border)' }}>
      <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
        Feature Means (F13–F19)
      </div>
      {feature_names.map((name, i) => (
        <div key={name} style={{ marginBottom: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
            <span style={{ fontSize: 10, color: 'var(--tg-text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>
              {name}
            </span>
            <span style={{ fontSize: 9, color: '#ff5d6c' }}>{fraud_mean[i].toFixed(3)}</span>
            <span style={{ fontSize: 9, color: '#6ad1ff' }}>{normal_mean[i].toFixed(3)}</span>
          </div>
          {/* Normal bar */}
          <div style={{ height: 4, background: 'var(--tg-dark-bg)', borderRadius: 2, overflow: 'hidden', marginBottom: 2 }}>
            <div style={{ width: `${(normal_mean[i] / max) * 100}%`, height: '100%', background: '#6ad1ff', borderRadius: 2, transition: 'width 0.3s' }} />
          </div>
          {/* Fraud bar */}
          <div style={{ height: 4, background: 'var(--tg-dark-bg)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ width: `${(fraud_mean[i] / max) * 100}%`, height: '100%', background: '#ff5d6c', borderRadius: 2, transition: 'width 0.3s' }} />
          </div>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
        <span style={{ fontSize: 10, color: '#ff5d6c' }}>■ Fraud</span>
        <span style={{ fontSize: 10, color: '#6ad1ff' }}>■ Normal</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// D3 Force Graph
// ---------------------------------------------------------------------------

interface SimNode extends BankFraudNode {
  x: number;
  y: number;
}

interface SimEdge {
  source: SimNode | string;
  target: SimNode | string;
  type: string;
  color: string;
}

function BankFraudGraph({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
}: {
  nodes: BankFraudNode[];
  edges: BankFraudEdge[];
  selectedNode: BankFraudNode | null;
  onSelectNode: (n: BankFraudNode | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const simNodes: SimNode[] = nodes.map(n => ({ ...n, x: 0, y: 0 }));
    const nodeMap = new Map(simNodes.map(n => [n.id, n]));

    const simEdges: SimEdge[] = edges
      .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map(e => ({
        source: e.source,
        target: e.target,
        type: e.type,
        color: e.color,
      }));

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const W = svgRef.current.clientWidth || 900;
    const H = svgRef.current.clientHeight || 580;

    const defs = svg.append('defs');

    // Fraud glow
    const glow = defs.append('filter').attr('id', 'glow-fraud');
    glow.append('feGaussianBlur').attr('stdDeviation', 4).attr('result', 'coloredBlur');
    const feMerge = glow.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    const g = svg.append('g');

    const edgeSel = g.append('g')
      .selectAll<SVGLineElement, SimEdge>('line')
      .data(simEdges)
      .enter()
      .append('line')
      .attr('stroke', d => d.color)
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.5);

    const nodeSel = g.append('g')
      .selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .enter()
      .append('g')
      .attr('cursor', 'pointer')
      .on('click', (_, d) => onSelectNode(d as BankFraudNode))
      .on('mouseenter', (event, d) => {
        d3.select(event.currentTarget).select('circle')
          .attr('filter', 'url(#glow-fraud)');
        edgeSel.attr('stroke-opacity', e => {
          const src = typeof e.source === 'string' ? e.source : (e.source as SimNode).id;
          const tgt = typeof e.target === 'string' ? e.target : (e.target as SimNode).id;
          return src === d.id || tgt === d.id ? 1 : 0.05;
        });
      })
      .on('mouseleave', () => {
        d3.selectAll('.graph-node-hovered').select('circle').attr('filter', null);
        edgeSel.attr('stroke-opacity', 0.5);
      });

    nodeSel.append('circle')
      .attr('r', d => d.radius || 7)
      .attr('fill', d => d.color)
      .attr('fill-opacity', 0.85)
      .attr('stroke', d => d.is_fraud ? '#ff5d6c' : '#ffffff22')
      .attr('stroke-width', d => d.is_fraud ? 2 : 1);

    nodeSel.append('text')
      .text(d => d.label)
      .attr('text-anchor', 'middle')
      .attr('dy', d => (d.radius || 7) + 12)
      .attr('font-size', 8)
      .attr('fill', d => d.is_fraud ? '#ff5d6c' : 'var(--tg-text-muted)')
      .attr('pointer-events', 'none');

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 5])
        .on('zoom', e => g.attr('transform', e.transform.toString()))
    );

    const sim = d3.forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimEdge>(simEdges)
        .id(d => d.id)
        .distance(60)
        .strength(0.3))
      .force('charge', d3.forceManyBody().strength(d => d.is_fraud ? -400 : -150))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius(d => (d.radius || 7) + 5));

    simRef.current = sim;

    sim.on('tick', () => {
      edgeSel
        .attr('x1', d => (d.source as SimNode).x)
        .attr('y1', d => (d.source as SimNode).y)
        .attr('x2', d => (d.target as SimNode).x)
        .attr('y2', d => (d.target as SimNode).y);
      nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); };
  }, [nodes, edges, onSelectNode]);

  return (
    <svg ref={svgRef} style={{ width: '100%', height: '100%', display: 'block' }} />
  );
}

// ---------------------------------------------------------------------------
// Node inspector
// ---------------------------------------------------------------------------

function NodeInspector({ node, stats }: { node: BankFraudNode; stats: BankFraudStats }) {
  return (
    <div style={{
      width: 260, minWidth: 260,
      borderLeft: '1px solid var(--tg-dark-border)',
      background: 'var(--tg-dark-card)',
      overflowY: 'auto',
      padding: 16,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h3 style={{ fontSize: 13 }}>Record Inspector</h3>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <span style={{
          width: 40, height: 40, borderRadius: '50%',
          background: node.is_fraud ? '#ff5d6c' : '#6ad1ff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: '#fff',
        }}>
          {node.is_fraud ? 'FRAUD' : 'NORM'}
        </span>
        <div>
          <div style={{ fontWeight: 700, fontSize: 13 }}>{node.id}</div>
          <span style={{ fontSize: 10, color: node.is_fraud ? '#ff5d6c' : '#6ad1ff', fontWeight: 600 }}>
            {node.is_fraud ? '⚠ FRAUD' : '✓ Normal'}
          </span>
        </div>
      </div>

      <div style={{ background: 'var(--tg-dark-bg)', borderRadius: 6, padding: 10 }}>
        {stats.feature_names.map((name, i) => (
          <div key={name} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid var(--tg-dark-border)', fontSize: 12 }}>
            <span style={{ color: 'var(--tg-text-muted)' }}>{name}</span>
            <span style={{ color: node.is_fraud ? '#ff5d6c' : 'var(--tg-text-primary)', fontFamily: 'JetBrains Mono, monospace' }}>
              {node.features[i].toFixed(4)}
            </span>
          </div>
        ))}
        <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 12 }}>
          <span style={{ color: 'var(--tg-text-muted)' }}>Label</span>
          <span style={{ color: node.is_fraud ? '#ff5d6c' : '#6ad1ff', fontWeight: 600 }}>
            {node.is_fraud ? 'Fraud' : 'Normal'}
          </span>
        </div>
      </div>

      <div style={{ marginTop: 12, fontSize: 10, color: 'var(--tg-text-muted)', lineHeight: 1.6 }}>
        Records with similar feature values are connected with edges.
        Fraud records cluster together due to distinct feature patterns.
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PaySimView() {
  const [data, setData] = useState<BankFraudAPIResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<BankFraudNode | null>(null);
  const [showFraudOnly, setShowFraudOnly] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    try {
      const res = await fetch('/api/bankfraud/sample?sample_size=300&fraud_ratio=0.5');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: BankFraudAPIResponse = await res.json();
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const visibleNodes = data
    ? showFraudOnly
      ? data.nodes.filter(n => n.is_fraud)
      : data.nodes
    : [];

  const visibleEdges = data
    ? showFraudOnly
      ? data.edges.filter(e => {
          const src = data.nodes.find(n => n.id === e.source);
          return src?.is_fraud;
        })
      : data.edges
    : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        height: 'var(--header-height)',
        borderBottom: '1px solid var(--tg-dark-border)',
        display: 'flex', alignItems: 'center',
        padding: '0 20px', gap: 12,
        background: 'var(--tg-dark-bg)',
        flexShrink: 0,
      }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: '#ff5d6c' }}>⚠</span>
        <span style={{ fontWeight: 600, fontSize: 14 }}>Banking Fraud Detection</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-muted)' }}>
          — Real banking data · Kaggle dataset · {data?.stats?.total_count.toLocaleString() ?? '—'} records
        </span>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--tg-text-secondary)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showFraudOnly}
              onChange={e => setShowFraudOnly(e.target.checked)}
              style={{ accentColor: '#ff5d6c' }}
            />
            Fraud only
          </label>
          <button
            onClick={fetchData}
            disabled={loading}
            style={{
              padding: '4px 14px', fontSize: 12, borderRadius: 4,
              background: 'var(--tg-blue)', color: '#fff',
              border: 'none', cursor: 'pointer', fontWeight: 600,
            }}
          >
            {loading ? 'Loading…' : '↻ Reload'}
          </button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left sidebar */}
        <div style={{
          width: 200, minWidth: 200,
          borderRight: '1px solid var(--tg-dark-border)',
          overflowY: 'auto',
          background: 'var(--tg-dark-card)',
        }}>
          {data ? (
            <>
              {/* Fraud stats */}
              <div style={{ padding: '12px 14px' }}>
                <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                  Dataset Stats
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  <div style={{ background: 'var(--tg-dark-bg)', borderRadius: 6, padding: '8px 10px', textAlign: 'center' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#ff5d6c' }}>{data.stats.fraud_count}</div>
                    <div style={{ fontSize: 10, color: 'var(--tg-text-muted)' }}>Fraud</div>
                  </div>
                  <div style={{ background: 'var(--tg-dark-bg)', borderRadius: 6, padding: '8px 10px', textAlign: 'center' }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: '#6ad1ff' }}>{data.stats.normal_count}</div>
                    <div style={{ fontSize: 10, color: 'var(--tg-text-muted)' }}>Normal</div>
                  </div>
                </div>
                <div style={{ marginTop: 8, background: 'var(--tg-dark-bg)', borderRadius: 6, padding: '8px 10px', textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, color: data.stats.fraud_rate > 30 ? '#ff5d6c' : '#ffd866' }}>
                    {data.stats.fraud_rate}%
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--tg-text-muted)' }}>Fraud rate</div>
                </div>
              </div>

              {/* Graph stats */}
              <div style={{ padding: '12px 14px', borderTop: '1px solid var(--tg-dark-border)' }}>
                <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                  Graph Stats
                </div>
                {[
                  ['Nodes', data.nodes.length, '#6ad1ff'],
                  ['Edges', data.edges.length, '#6ad1ff'],
                  ['Fraud nodes', data.nodes.filter(n => n.is_fraud).length, '#ff5d6c'],
                  ['Total rows', data.stats.total_count.toLocaleString(), '#6ad1ff'],
                ].map(([label, val, color]) => (
                  <div key={String(label)} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 11, color: 'var(--tg-text-secondary)' }}>{label}</span>
                    <span style={{ fontSize: 11, color, fontWeight: 600 }}>{String(val)}</span>
                  </div>
                ))}
              </div>

              {/* Feature heatmap */}
              <FeatureHeatmap stats={data.stats} />

              {/* Legend */}
              <div style={{ padding: '12px 14px', borderTop: '1px solid var(--tg-dark-border)' }}>
                <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
                  Legend
                </div>
                {[
                  ['#ff5d6c', '⚠ Fraud record'],
                  ['#6ad1ff', '✓ Normal record'],
                  ['#ff5d6c88', 'Similar edge'],
                ].map(([color, label]) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                    <span style={{ width: 9, height: 9, borderRadius: '50%', background: color.startsWith('#ff') && !color.includes('88') ? color : color.split('88')[0], display: 'inline-block', flexShrink: 0, opacity: color.includes('88') ? 0.5 : 1 }} />
                    <span style={{ fontSize: 11, color: 'var(--tg-text-secondary)' }}>{label}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ padding: 16, fontSize: 12, color: 'var(--tg-text-muted)' }}>
              {error ? `Error: ${error}` : 'Loading…'}
            </div>
          )}
        </div>

        {/* Graph canvas */}
        <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'var(--tg-dark-bg)' }}>
          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--tg-text-muted)' }}>
              Loading banking fraud data…
            </div>
          ) : data ? (
            <>
              <BankFraudGraph
                nodes={visibleNodes}
                edges={visibleEdges}
                selectedNode={selectedNode}
                onSelectNode={setSelectedNode}
              />

              {/* Overlay: instructions */}
              <div style={{
                position: 'absolute', top: 12, right: 12,
                background: 'rgba(13,17,23,0.8)',
                border: '1px solid var(--tg-dark-border)',
                borderRadius: 4, padding: '4px 10px',
                fontSize: 10, color: 'var(--tg-text-muted)',
              }}>
                Click node to inspect · Scroll to zoom · Drag to pan
              </div>

              {/* Overlay: source */}
              <div style={{
                position: 'absolute', bottom: 12, left: 12,
                background: 'rgba(13,17,23,0.85)',
                border: '1px solid var(--tg-dark-border)',
                borderRadius: 4, padding: '4px 10px',
                fontSize: 10, color: 'var(--tg-text-muted)',
              }}>
                Banking Fraud Dataset · kaggle.com · {data.source}
              </div>
            </>
          ) : null}
        </div>

        {/* Right inspector */}
        {selectedNode && data && (
          <NodeInspector node={selectedNode} stats={data.stats} />
        )}
      </div>
    </div>
  );
}
