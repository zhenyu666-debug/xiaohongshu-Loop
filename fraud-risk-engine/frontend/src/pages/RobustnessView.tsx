import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';

// ---------------------------------------------------------------------------
// Types - match the /api/robustness response
// ---------------------------------------------------------------------------

interface RobustnessReport {
  node_count: number;
  edge_count: number;
  density: number;
  avg_degree: number;
  clustering_coefficient: number;
  diameter_small: number | null;
  node_connectivity_estimate: number;
  edge_connectivity: number;
  assortativity: number;
}

interface RobustnessAlert {
  kind: string;
  severity: string;
  score: number;
  title: string;
  description: string;
  involved: string[];
  evidence: {
    node_count: number;
    edge_count: number;
    density: number;
    avg_degree: number;
    clustering_coefficient: number;
    diameter_small: number | null;
    edge_connectivity: number;
    node_connectivity_estimate: number;
    assortativity: number;
    triggered_kinds: string[];
    thresholds: Record<string, number>;
  };
}

interface RobustnessAPIResponse {
  ok: boolean;
  report: RobustnessReport;
  alert: RobustnessAlert | null;
}

// ---------------------------------------------------------------------------
// Palette
// ---------------------------------------------------------------------------

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ff5d6c',
  high: '#ff9c4a',
  medium: '#ffd866',
  low: '#6ad1ff',
};

const DD = String.fromCharCode(45, 45);  // '--' (dashes inside CSS vars)

// ---------------------------------------------------------------------------
// D3 shape graph - one node per reported node, edges per reported edge_count
// seeded by density/edge_count/avg_degree so the same report renders identically.
// ---------------------------------------------------------------------------

interface GraphNode {
  id: number;
  x: number;
  y: number;
}

interface GraphEdge {
  source: GraphNode | number;
  target: GraphNode | number;
}

function buildShapeGraph(report: RobustnessReport): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const n = Math.min(Math.max(report.node_count, 2), 80);
  const maxE = (n * (n - 1)) / 2;
  const targetE = Math.min(Math.max(report.edge_count, 0), maxE);
  const nodes: GraphNode[] = [];
  for (let i = 0; i < n; i++) nodes.push({ id: i, x: 0, y: 0 });
  let seed = Math.floor(report.density * 1e6) + report.edge_count * 31 + Math.floor(report.avg_degree * 100);
  if (seed === 0) seed = 1;
  const rand = () => { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; };
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();
  let attempts = 0;
  while (edges.length < targetE && attempts < targetE * 4 + 50) {
    const s = Math.floor(rand() * n);
    const t = Math.floor(rand() * n);
    if (s === t) { attempts++; continue; }
    const key = s < t ? s + '-' + t : t + '-' + s;
    if (seen.has(key)) { attempts++; continue; }
    seen.add(key);
    edges.push({ source: s, target: t });
    attempts++;
  }
  return { nodes, edges };
}

function RobustnessGraph({ report, alertSeverity }: { report: RobustnessReport; alertSeverity: string | null }) {
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    const W = svgRef.current.clientWidth || 700;
    const H = svgRef.current.clientHeight || 480;
    const { nodes, edges } = buildShapeGraph(report);
    const g = svg.append('g');
    svg.call(d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.2, 4]).on('zoom', (e) => g.attr('transform', e.transform.toString())));
    const linkColor = alertSeverity ? (SEVERITY_COLORS[alertSeverity] || '#3a4055') : '#3a4055';
    const nodeColor = alertSeverity ? (SEVERITY_COLORS[alertSeverity] || '#6ad1ff') : '#6ad1ff';
    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(45).strength(0.4))
      .force('charge', d3.forceManyBody().strength(-180))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius(7));
    const link = g.append('g').selectAll('line').data(edges).join('line')
      .attr('stroke', linkColor).attr('stroke-width', 0.8).attr('stroke-opacity', 0.55);
    const node = g.append('g').selectAll('circle').data(nodes).join('circle')
      .attr('r', 4)
      .attr('fill', nodeColor)
      .attr('stroke', '#0f1115')
      .attr('stroke-width', 0.5);
    sim.on('tick', () => {
      link.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
          .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y);
      node.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y);
    });
    return () => { sim.stop(); };
  }, [report, alertSeverity]);
  return <svg ref={svgRef} style={{ width: '100%', height: '100%', display: 'block', background: 'var(' + DD + 'tg-dark-bg2, #0d1117)' }} />;
}

// ---------------------------------------------------------------------------
// Measures table - one row per measure, threshold-aware highlighting
// ---------------------------------------------------------------------------

interface Measure {
  label: string;
  value: string;
  hint: string;
  highlight?: 'low' | 'high' | 'neutral';
}

function formatMeasure(
  label: string,
  raw: number | null,
  fmt: (n: number) => string,
  hint: string,
  threshold?: { low_max?: number; dense_min?: number },
): Measure {
  let highlight: Measure['highlight'] = 'neutral';
  let display = raw == null ? '-' : fmt(raw);
  if (raw != null) {
    if (threshold && threshold.low_max != null && raw <= threshold.low_max) highlight = 'low';
    else if (threshold && threshold.dense_min != null && raw >= threshold.dense_min) highlight = 'high';
  }
  return { label, value: display, hint, highlight };
}

function MeasuresTable({ report }: { report: RobustnessReport }) {
  const measures: Measure[] = [
    formatMeasure('Nodes', report.node_count, (n) => n.toLocaleString(), 'Total account vertices'),
    formatMeasure('Edges', report.edge_count, (n) => n.toLocaleString(), 'Total undirected fund-flow edges'),
    formatMeasure('Density', report.density, (n) => n.toFixed(4), 'Edge density 0..1', { dense_min: 0.30 }),
    formatMeasure('Avg degree', report.avg_degree, (n) => n.toFixed(2), 'Mean vertex degree'),
    formatMeasure('Clustering', report.clustering_coefficient, (n) => n.toFixed(4), 'Triangle transitivity 0..1'),
    formatMeasure('Diameter (small)', report.diameter_small, (n) => String(n), 'BFS eccentricity of the largest component'),
    formatMeasure('Edge connectivity', report.edge_connectivity, (n) => String(n), 'Min cut edges to disconnect', { low_max: 2 }),
    formatMeasure('Node connectivity', report.node_connectivity_estimate, (n) => String(n), 'Min cut vertices to disconnect'),
    formatMeasure('Assortativity', report.assortativity, (n) => n.toFixed(4), 'Degree-degree Pearson correlation -1..1'),
  ];
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <tbody>
        {measures.map((m) => {
          const color =
            m.highlight === 'low' ? '#ff5d6c' :
            m.highlight === 'high' ? '#ff9c4a' :
            'var(' + DD + 'tg-text-primary)';
          const badge = m.highlight === 'low' || m.highlight === 'high' ? ' !' : '';
          return (
            <tr key={m.label} style={{ borderBottom: '1px solid var(' + DD + 'tg-dark-border)' }}>
              <td style={{ padding: '5px 4px', color: 'var(' + DD + 'tg-text-muted)' }} title={m.hint}>{m.label}{badge}</td>
              <td style={{ padding: '5px 4px', textAlign: 'right', color, fontFamily: 'JetBrains Mono, monospace', fontWeight: 600 }}>{m.value}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Alert card - surfaces the RiskAlert produced by robustness_alert_from_report
// ---------------------------------------------------------------------------

function AlertCard({ alert }: { alert: RobustnessAlert | null }) {
  if (!alert) {
    return (
      <div style={{
        padding: 14,
        background: 'var(' + DD + 'tg-dark-bg2, #0d1117)',
        borderRadius: 6,
        border: '1px solid var(' + DD + 'tg-dark-border)',
        color: 'var(' + DD + 'tg-text-muted)',
        fontSize: 12,
        lineHeight: 1.6,
      }}>
        <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>No alert</div>
        <div>The graph topology is within normal thresholds. <code>edge_connectivity &gt; 2</code> and <code>density &lt; 0.30</code>.</div>
      </div>
    );
  }
  const sev = (alert.severity || 'low').toLowerCase();
  const color = SEVERITY_COLORS[sev] || '#6ad1ff';
  return (
    <div style={{
      padding: 14,
      background: 'var(' + DD + 'tg-dark-bg2, #0d1117)',
      borderRadius: 6,
      border: '1px solid var(' + DD + 'tg-dark-border)',
      borderLeft: '3px solid ' + color,
      fontSize: 12,
      lineHeight: 1.6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
          padding: '2px 8px', borderRadius: 3,
          background: color, color: '#0d1117',
        }}>{sev}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(' + DD + 'tg-text-primary)' }}>{alert.title}</span>
      </div>
      <div style={{ color: 'var(' + DD + 'tg-text-secondary)', marginBottom: 10 }}>{alert.description}</div>
      <div style={{ display: 'flex', gap: 12, fontSize: 11, color: 'var(' + DD + 'tg-text-muted)' }}>
        <span>Score: <strong style={{ color, fontFamily: 'JetBrains Mono, monospace' }}>{alert.score.toFixed(3)}</strong></span>
        <span>Kind: <strong style={{ color: 'var(' + DD + 'tg-text-secondary)', fontFamily: 'JetBrains Mono, monospace' }}>{alert.kind}</strong></span>
      </div>
      {alert.evidence.triggered_kinds.length > 1 && (
        <div style={{ marginTop: 8, fontSize: 11, color: 'var(' + DD + 'tg-text-muted)' }}>
          Also triggered: {alert.evidence.triggered_kinds.slice(1).join(', ')}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export function RobustnessView() {
  const [data, setData] = useState<RobustnessAPIResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsBuild, setNeedsBuild] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNeedsBuild(false);
    try {
      const res = await fetch('/api/robustness');
      if (res.status === 400) {
        const body = await res.json().catch(() => ({ detail: 'no dataset loaded' }));
        setNeedsBuild(true);
        setError(body.detail || 'no dataset loaded');
        setData(null);
        return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const json: RobustnessAPIResponse = await res.json();
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const buildDataset = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch('/api/dataset', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      await fetchData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setLoading(false);
    }
  }, [fetchData]);

  const report = data?.report ?? null;
  const alert = data?.alert ?? null;
  const borderColor = 'var(' + DD + 'tg-dark-border)';

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left sidebar */}
      <div style={{
        width: 260, minWidth: 260,
        background: 'var(' + DD + 'tg-dark-card, #161b22)',
        borderRight: '1px solid ' + borderColor,
        overflowY: 'auto',
      }}>
        <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid ' + borderColor }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(' + DD + 'tg-text-primary)', marginBottom: 4 }}>
            Graph Robustness
          </div>
          <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', lineHeight: 1.5 }}>
            TIGER port - stdlib-only measures over the funds-flow undirected projection.
          </div>
        </div>

        <div style={{ padding: '12px 14px', borderBottom: '1px solid ' + borderColor, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <button
            onClick={fetchData}
            disabled={loading || needsBuild}
            style={{
              padding: '6px 12px', fontSize: 12, borderRadius: 4,
              background: 'var(' + DD + 'tg-blue)', color: '#fff',
              border: 'none', cursor: loading ? 'wait' : 'pointer', fontWeight: 600,
              opacity: loading || needsBuild ? 0.5 : 1,
            }}
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          {needsBuild && (
            <button
              onClick={buildDataset}
              disabled={loading}
              style={{
                padding: '6px 12px', fontSize: 12, borderRadius: 4,
                background: 'var(' + DD + 'tg-orange, #f2994a)', color: '#0d1117',
                border: 'none', cursor: loading ? 'wait' : 'pointer', fontWeight: 600,
              }}
            >
              Build dataset first
            </button>
          )}
        </div>

        <div style={{ padding: '12px 14px' }}>
          <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
            Measures
          </div>
          {report ? <MeasuresTable report={report} /> : (
            <div style={{ fontSize: 12, color: 'var(' + DD + 'tg-text-muted)' }}>
              {error ? 'Error: ' + error : 'No data'}
            </div>
          )}
        </div>

        <div style={{ padding: '12px 14px', borderTop: '1px solid ' + borderColor }}>
          <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
            Thresholds
          </div>
          <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-secondary)', lineHeight: 1.6 }}>
            <div>edge_connectivity &le; 2 -&gt; hub-and-spoke alert</div>
            <div>density &ge; 0.30 -&gt; dense-clique alert</div>
          </div>
        </div>
      </div>

      {/* Main canvas */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'var(' + DD + 'tg-dark-bg, #0d1117)' }}>
        {loading && !report && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: 'var(' + DD + 'tg-text-muted)', fontSize: 13 }}>Computing robustness...</span>
          </div>
        )}
        {!loading && !report && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 8 }}>
            <span style={{ color: 'var(' + DD + 'tg-text-muted)', fontSize: 13 }}>{error || 'No data - POST /api/dataset first.'}</span>
            {needsBuild && (
              <button onClick={buildDataset} style={{
                padding: '6px 14px', fontSize: 12, borderRadius: 4,
                background: 'var(' + DD + 'tg-blue)', color: '#fff',
                border: 'none', cursor: 'pointer', fontWeight: 600,
              }}>Build dataset</button>
            )}
          </div>
        )}
        {report && (
          <>
            <RobustnessGraph report={report} alertSeverity={alert?.severity ?? null} />
            <div style={{
              position: 'absolute', top: 12, left: 12,
              background: 'rgba(13,17,23,0.88)',
              border: '1px solid ' + borderColor,
              borderRadius: 6, padding: '8px 12px', fontSize: 11,
            }}>
              <div style={{ color: 'var(' + DD + 'tg-text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Shape view</div>
              <div style={{ color: 'var(' + DD + 'tg-text-secondary)', lineHeight: 1.5 }}>
                {report.node_count} nodes - {report.edge_count} edges<br />
                density = {report.density.toFixed(4)} - avg degree = {report.avg_degree.toFixed(2)}
              </div>
            </div>
            <div style={{
              position: 'absolute', top: 12, right: 12,
              background: 'rgba(13,17,23,0.8)',
              border: '1px solid ' + borderColor,
              borderRadius: 4, padding: '4px 10px',
              fontSize: 10, color: 'var(' + DD + 'tg-text-muted)',
            }}>Scroll to zoom - Drag to pan</div>
          </>
        )}
      </div>

      {/* Right inspector */}
      <div style={{
        width: 320, minWidth: 320,
        background: 'var(' + DD + 'tg-dark-card, #161b22)',
        borderLeft: '1px solid ' + borderColor,
        overflowY: 'auto',
      }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid ' + borderColor, fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Surfaced alert
        </div>
        <div style={{ padding: 14 }}><AlertCard alert={alert} /></div>
        {alert && (
          <>
            <div style={{ padding: '12px 14px', borderTop: '1px solid ' + borderColor, fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Evidence
            </div>
            <pre style={{
              margin: 0, padding: '12px 14px', fontSize: 10,
              color: 'var(' + DD + 'tg-text-secondary)', fontFamily: 'JetBrains Mono, monospace',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              maxHeight: 360, overflowY: 'auto',
            }}>{JSON.stringify(alert.evidence, null, 2)}</pre>
          </>
        )}
      </div>
    </div>
  );
}
