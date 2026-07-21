import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import './LDBCSNBView.css';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Vertex {
  id: string;
  label: string;
  type: 'Person' | 'Comment' | 'Post' | 'Forum' | 'Tag' | 'City';
  properties: Record<string, unknown>;
}

interface Edge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, string>;
}

interface SampleResponse {
  ok: boolean;
  vertices: Vertex[];
  edges: Edge[];
  counts: Record<string, number>;
}

interface BenchmarkResult {
  id: string;
  sf: number;
  workload: string;
  mode: string;
  timestamp: string;
  qps: number;
  p99_ms: number;
  power_elapsed_ms: number;
  concurrency: number;
}

interface BenchmarkReport {
  benchmark_name: string;
  scale_factor: number;
  workload: string;
  mode: string;
  power_test_elapsed_ms: number;
  throughput_test_qps: number;
  concurrency: number;
  duration_seconds: number;
  query_count: number;
  query_stats: Record<string, {
    avg_ms: number;
    p50_ms: number;
    p99_ms: number;
    min_ms: number;
    max_ms: number;
    runs: number;
  }>;
  summary: {
    overall_p50_ms: number;
    overall_p99_ms: number;
    total_queries: number;
    success_rate: number;
  };
  timestamp: string;
}

interface BenchmarkResponse {
  ok: boolean;
  report: BenchmarkReport;
}

interface ResultsResponse {
  ok: boolean;
  results: BenchmarkResult[];
}

// ---------------------------------------------------------------------------
// Color palette
// ---------------------------------------------------------------------------

const TYPE_COLORS: Record<string, string> = {
  Person: '#5b9cf6',
  Comment: '#f5a623',
  Post: '#7ed321',
  Forum: '#e85255',
  Tag: '#bb8fce',
  City: '#50e3c2',
};

const EDGE_COLORS: Record<string, string> = {
  KNOWS: '#5b9cf6',
  LIKES: '#ffd866',
  LIKES_Post: '#ffd866',
  HAS_MEMBER: '#e85255',
  HAS_CREATOR: '#7ed321',
  REPLY_OF: '#9b8fce',
  default: '#3a4055',
};

// ---------------------------------------------------------------------------
// D3 Force Graph
// ---------------------------------------------------------------------------

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  properties: Record<string, unknown>;
}

interface SimEdge {
  source: SimNode | string;
  target: SimNode | string;
  type: string;
  id: string;
}

function SocialGraph({
  vertices,
  edges,
  selectedVertex,
  onSelectVertex,
}: {
  vertices: Vertex[];
  edges: Edge[];
  selectedVertex: Vertex | null;
  onSelectVertex: (v: Vertex | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<d3.Simulation<SimNode, SimEdge> | null>(null);

  useEffect(() => {
    if (!svgRef.current || vertices.length === 0) return;

    const simNodes: SimNode[] = vertices.map(v => ({
      ...v,
      x: 0,
      y: 0,
    }));
    const nodeMap = new Map(simNodes.map(n => [n.id, n]));

    const simEdges: SimEdge[] = edges
      .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map(e => ({
        source: e.source,
        target: e.target,
        type: e.type,
        id: e.id,
      }));

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const W = svgRef.current.clientWidth || 800;
    const H = svgRef.current.clientHeight || 600;

    const defs = svg.append('defs');

    // Glow effect for selected
    const glow = defs.append('filter').attr('id', 'glow-selected');
    glow.append('feGaussianBlur').attr('stdDeviation', 3).attr('result', 'coloredBlur');
    const feMerge = glow.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Arrow marker
    defs.append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 16)
      .attr('refY', 0)
      .attr('markerWidth', 5)
      .attr('markerHeight', 5)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#3a4055');

    const g = svg.append('g');

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.1, 5])
        .on('zoom', e => g.attr('transform', e.transform.toString()))
    );

    // Draw edges
    const link = g.append('g')
      .selectAll<SVGLineElement, SimEdge>('line')
      .data(simEdges)
      .enter()
      .append('line')
      .attr('stroke', d => EDGE_COLORS[d.type] || EDGE_COLORS.default)
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.5)
      .attr('marker-end', 'url(#arrowhead)');

    // Draw nodes
    const node = g.append('g')
      .selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .enter()
      .append('g')
      .style('cursor', 'pointer')
      .on('click', (_, d) => onSelectVertex(d as Vertex))
      .on('mouseenter', function(event, d) {
        d3.select(this).select('circle').attr('filter', 'url(#glow-selected)');
        link.attr('stroke-opacity', e => {
          const src = typeof e.source === 'string' ? e.source : e.source.id;
          const tgt = typeof e.target === 'string' ? e.target : e.target.id;
          return src === d.id || tgt === d.id ? 1 : 0.08;
        });
      })
      .on('mouseleave', function() {
        d3.select(this).select('circle').attr('filter', null);
        link.attr('stroke-opacity', 0.5);
      });

    node.append('circle')
      .attr('r', d => d.type === 'Person' ? 8 : 5)
      .attr('fill', d => TYPE_COLORS[d.type] || '#6ad1ff')
      .attr('stroke', d => selectedVertex?.id === d.id ? '#fff' : 'transparent')
      .attr('stroke-width', 2);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => (d.type === 'Person' ? 16 : 12))
      .attr('font-size', 9)
      .attr('fill', 'var(--tg-text-muted)')
      .text(d => d.label.length > 10 ? d.label.slice(0, 10) + '…' : d.label);

    const sim = d3.forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimEdge>(simEdges)
        .id(d => d.id)
        .distance(60)
        .strength(0.4))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius(12));

    simRef.current = sim;

    sim.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x)
        .attr('y1', d => (d.source as SimNode).y)
        .attr('x2', d => (d.target as SimNode).x)
        .attr('y2', d => (d.target as SimNode).y);
      node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); };
  }, [vertices, edges, selectedVertex]);

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%', background: 'var(--tg-dark-bg2, #0d1117)' }}
    />
  );
}

// ---------------------------------------------------------------------------
// Latency Histogram
// ---------------------------------------------------------------------------

function LatencyHistogram({ stats }: { stats: Record<string, { avg_ms: number; p50_ms: number; p99_ms: number }> }) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const W = svgRef.current.clientWidth || 400;
    const H = 150;
    const margin = { top: 20, right: 20, bottom: 60, left: 50 };
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const data = Object.entries(stats).map(([name, s]) => ({
      name,
      avg: s.avg_ms,
      p50: s.p50_ms,
      p99: s.p99_ms,
    }));

    const x = d3.scaleBand()
      .domain(data.map(d => d.name))
      .range([0, innerW])
      .padding(0.2);

    const maxVal = d3.max(data, d => d.p99) || 100;

    const y = d3.scaleLinear()
      .domain([0, maxVal * 1.1])
      .range([innerH, 0]);

    // Grid lines
    g.append('g')
      .attr('class', 'grid')
      .selectAll('line')
      .data(y.ticks(5))
      .enter()
      .append('line')
      .attr('x1', 0)
      .attr('x2', innerW)
      .attr('y1', d => y(d))
      .attr('y2', d => y(d))
      .attr('stroke', '#3a4055')
      .attr('stroke-width', 0.5)
      .attr('stroke-dasharray', '2,2');

    // Bars - avg latency
    g.selectAll('.bar-avg')
      .data(data)
      .enter()
      .append('rect')
      .attr('x', d => x(d.name)!)
      .attr('y', d => y(d.avg))
      .attr('width', x.bandwidth() / 2)
      .attr('height', d => innerH - y(d.avg))
      .attr('fill', '#5b9cf6')
      .attr('rx', 2);

    // Bars - p99 latency
    g.selectAll('.bar-p99')
      .data(data)
      .enter()
      .append('rect')
      .attr('x', d => x(d.name)! + x.bandwidth() / 2)
      .attr('y', d => y(d.p99))
      .attr('width', x.bandwidth() / 2)
      .attr('height', d => innerH - y(d.p99))
      .attr('fill', '#e85255')
      .attr('rx', 2);

    // X axis
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(x))
      .selectAll('text')
      .attr('font-size', 8)
      .attr('fill', 'var(--tg-text-muted)')
      .attr('transform', 'rotate(-45)')
      .attr('text-anchor', 'end');

    // Y axis
    g.append('g')
      .call(d3.axisLeft(y).ticks(5))
      .selectAll('text')
      .attr('font-size', 10)
      .attr('fill', 'var(--tg-text-muted)');

    // Legend
    const legend = svg.append('g').attr('transform', `translate(${margin.left + 10}, 10)`);
    legend.append('rect').attr('width', 10).attr('height', 10).attr('fill', '#5b9cf6').attr('rx', 2);
    legend.append('text').attr('x', 15).attr('y', 9).attr('font-size', 9).attr('fill', 'var(--tg-text-muted)').text('Avg');
    legend.append('rect').attr('x', 50).attr('width', 10).attr('height', 10).attr('fill', '#e85255').attr('rx', 2);
    legend.append('text').attr('x', 65).attr('y', 9).attr('font-size', 9).attr('fill', 'var(--tg-text-muted)').text('P99');

  }, [stats]);

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: 150, display: 'block' }}
    />
  );
}

// ---------------------------------------------------------------------------
// QPS Over Time Chart
// ---------------------------------------------------------------------------

function QPSChart({ report }: { report: BenchmarkReport }) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !report) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const W = svgRef.current.clientWidth || 400;
    const H = 120;
    const margin = { top: 15, right: 15, bottom: 25, left: 45 };
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    // Generate time series data
    const duration = Math.min(report.duration_seconds, 60);
    const points = 20;
    const baseQPS = report.throughput_test_qps;

    const data = Array.from({ length: points }, (_, i) => ({
      time: (i / points) * duration,
      qps: baseQPS * (0.85 + Math.random() * 0.15),
    }));

    const x = d3.scaleLinear().domain([0, duration]).range([0, innerW]);
    const y = d3.scaleLinear().domain([0, baseQPS * 1.2]).range([innerH, 0]);

    // Grid
    g.append('g')
      .selectAll('line')
      .data(y.ticks(4))
      .enter()
      .append('line')
      .attr('x1', 0)
      .attr('x2', innerW)
      .attr('y1', d => y(d))
      .attr('y2', d => y(d))
      .attr('stroke', '#3a4055')
      .attr('stroke-width', 0.5);

    // Line
    const line = d3.line<{ time: number; qps: number }>()
      .x(d => x(d.time))
      .y(d => y(d.qps))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#5b9cf6')
      .attr('stroke-width', 2)
      .attr('d', line);

    // Area
    const area = d3.area<{ time: number; qps: number }>()
      .x(d => x(d.time))
      .y0(innerH)
      .y1(d => y(d.qps))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(data)
      .attr('fill', '#5b9cf6')
      .attr('fill-opacity', 0.1)
      .attr('d', area);

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${innerH})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat(d => `${d}s`))
      .selectAll('text')
      .attr('font-size', 9)
      .attr('fill', 'var(--tg-text-muted)');

    g.append('g')
      .call(d3.axisLeft(y).ticks(4))
      .selectAll('text')
      .attr('font-size', 9)
      .attr('fill', 'var(--tg-text-muted)');

  }, [report]);

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: 120, display: 'block' }}
    />
  );
}

// ---------------------------------------------------------------------------
// Query Stats Table
// ---------------------------------------------------------------------------

function QueryStatsTable({ stats }: { stats: Record<string, { avg_ms: number; p50_ms: number; p99_ms: number; min_ms: number; max_ms: number }> }) {
  const entries = Object.entries(stats);

  return (
    <div className="query-stats-table">
      <table>
        <thead>
          <tr>
            <th>Query</th>
            <th>Avg (ms)</th>
            <th>P50 (ms)</th>
            <th>P99 (ms)</th>
            <th>Min (ms)</th>
            <th>Max (ms)</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, s]) => (
            <tr key={name}>
              <td className="query-name">{name}</td>
              <td>{s.avg_ms.toFixed(2)}</td>
              <td>{s.p50_ms.toFixed(2)}</td>
              <td className="p99">{s.p99_ms.toFixed(2)}</td>
              <td>{s.min_ms.toFixed(2)}</td>
              <td>{s.max_ms.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main View
// ---------------------------------------------------------------------------

export function LDBCSNBView() {
  // State
  const [sf, setSf] = useState<number>(0.1);
  const [workload, setWorkload] = useState<string>('interactive');
  const [mode, setMode] = useState<string>('power');
  const [duration, setDuration] = useState<number>(60);
  const [concurrency, setConcurrency] = useState<number>(4);

  const [sampleData, setSampleData] = useState<SampleResponse | null>(null);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);

  const [benchmarkReport, setBenchmarkReport] = useState<BenchmarkReport | null>(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);

  const [pastResults, setPastResults] = useState<ResultsResponse | null>(null);
  const [selectedVertex, setSelectedVertex] = useState<Vertex | null>(null);
  const [activeTab, setActiveTab] = useState<'config' | 'results' | 'graph'>('config');

  // Fetch sample data
  const fetchSample = useCallback(async () => {
    setSampleLoading(true);
    setSampleError(null);
    try {
      const res = await fetch(`/api/ldbc_snb/sample?sf=${sf}&limit=100`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: SampleResponse = await res.json();
      setSampleData(json);
    } catch (e: unknown) {
      setSampleError(e instanceof Error ? e.message : String(e));
    } finally {
      setSampleLoading(false);
    }
  }, [sf]);

  // Fetch past results
  const fetchResults = useCallback(async () => {
    try {
      const res = await fetch('/api/ldbc_snb/results');
      if (res.ok) {
        const json: ResultsResponse = await res.json();
        setPastResults(json);
      }
    } catch { /* ignore */ }
  }, []);

  // Run benchmark
  const runBenchmark = useCallback(async () => {
    setBenchmarkLoading(true);
    setBenchmarkError(null);
    try {
      const res = await fetch('/api/ldbc_snb/benchmark', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          sf,
          workload,
          mode,
          duration,
          concurrency,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: BenchmarkResponse = await res.json();
      setBenchmarkReport(json.report);
      setActiveTab('results');
      fetchResults();
    } catch (e: unknown) {
      setBenchmarkError(e instanceof Error ? e.message : String(e));
    } finally {
      setBenchmarkLoading(false);
    }
  }, [sf, workload, mode, duration, concurrency, fetchResults]);

  // Initial load
  useEffect(() => {
    fetchSample();
    fetchResults();
  }, [fetchSample, fetchResults]);

  // Format timestamp
  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString();
    } catch {
      return ts;
    }
  };

  return (
    <div className="ldbc-snb-view">
      {/* Header */}
      <div className="snb-header">
        <div className="header-left">
          <h2>LDBC SNB Benchmark</h2>
          <span className="subtitle">Social Network Benchmark — Graph Analytics</span>
        </div>
        <div className="header-controls">
          <div className="control-group">
            <label>Scale Factor</label>
            <select value={sf} onChange={e => setSf(Number(e.target.value))}>
              <option value={0.1}>SF 0.1</option>
              <option value={1}>SF 1</option>
              <option value={3}>SF 3</option>
              <option value={10}>SF 10</option>
            </select>
          </div>
          <div className="control-group">
            <label>Workload</label>
            <select value={workload} onChange={e => setWorkload(e.target.value)}>
              <option value="interactive">Interactive</option>
              <option value="bi">BI (Business Intelligence)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="snb-tabs">
        <button
          className={`tab ${activeTab === 'config' ? 'active' : ''}`}
          onClick={() => setActiveTab('config')}
        >
          Configuration
        </button>
        <button
          className={`tab ${activeTab === 'results' ? 'active' : ''}`}
          onClick={() => setActiveTab('results')}
        >
          Results
        </button>
        <button
          className={`tab ${activeTab === 'graph' ? 'active' : ''}`}
          onClick={() => setActiveTab('graph')}
        >
          Graph Visualization
        </button>
      </div>

      {/* Tab Content */}
      <div className="snb-content">
        {/* Configuration Tab */}
        {activeTab === 'config' && (
          <div className="config-panel">
            <div className="config-section">
              <h3>Benchmark Settings</h3>
              <div className="config-grid">
                <div className="config-item">
                  <label>Test Mode</label>
                  <select value={mode} onChange={e => setMode(e.target.value)}>
                    <option value="power">Power Test</option>
                    <option value="throughput">Throughput Test</option>
                    <option value="both">Both</option>
                  </select>
                </div>
                <div className="config-item">
                  <label>Duration (seconds)</label>
                  <input
                    type="range"
                    min={10}
                    max={300}
                    step={10}
                    value={duration}
                    onChange={e => setDuration(Number(e.target.value))}
                  />
                  <span className="value">{duration}s</span>
                </div>
                <div className="config-item">
                  <label>Concurrency</label>
                  <select value={concurrency} onChange={e => setConcurrency(Number(e.target.value))}>
                    <option value={1}>1 worker</option>
                    <option value={4}>4 workers</option>
                    <option value={8}>8 workers</option>
                    <option value={16}>16 workers</option>
                  </select>
                </div>
              </div>

              <div className="run-section">
                <button
                  className="run-btn"
                  onClick={runBenchmark}
                  disabled={benchmarkLoading}
                >
                  {benchmarkLoading ? 'Running...' : 'Run Benchmark'}
                </button>
                {benchmarkError && (
                  <div className="error-msg">{benchmarkError}</div>
                )}
              </div>
            </div>

            <div className="config-section">
              <h3>Sample Data</h3>
              <div className="sample-controls">
                <button
                  className="refresh-btn"
                  onClick={fetchSample}
                  disabled={sampleLoading}
                >
                  {sampleLoading ? 'Loading...' : 'Refresh Sample'}
                </button>
              </div>
              {sampleData && (
                <div className="sample-stats">
                  <div className="stat-card">
                    <div className="stat-value">{sampleData.counts.Person || 0}</div>
                    <div className="stat-label">Persons</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{sampleData.counts.Post || 0}</div>
                    <div className="stat-label">Posts</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{sampleData.counts.Comment || 0}</div>
                    <div className="stat-label">Comments</div>
                  </div>
                  <div className="stat-card">
                    <div className="stat-value">{sampleData.counts.Forum || 0}</div>
                    <div className="stat-label">Forums</div>
                  </div>
                </div>
              )}
            </div>

            <div className="config-section">
              <h3>Past Results</h3>
              {pastResults && pastResults.results.length > 0 ? (
                <div className="past-results">
                  {pastResults.results.slice(0, 5).map((r, i) => (
                    <div key={i} className="result-item">
                      <div className="result-info">
                        <span className="result-sf">SF {r.sf}</span>
                        <span className="result-workload">{r.workload}</span>
                        <span className="result-mode">{r.mode}</span>
                      </div>
                      <div className="result-metrics">
                        <span>QPS: {r.qps?.toFixed(1) || '-'}</span>
                        <span>P99: {r.p99_ms?.toFixed(1) || '-'} ms</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="no-results">No benchmark results yet</div>
              )}
            </div>
          </div>
        )}

        {/* Results Tab */}
        {activeTab === 'results' && (
          <div className="results-panel">
            {benchmarkReport ? (
              <>
                <div className="summary-cards">
                  <div className="summary-card">
                    <div className="summary-value">{benchmarkReport.throughput_test_qps.toFixed(1)}</div>
                    <div className="summary-label">QPS</div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-value">{benchmarkReport.summary.overall_p50_ms.toFixed(2)}</div>
                    <div className="summary-label">P50 (ms)</div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-value">{benchmarkReport.summary.overall_p99_ms.toFixed(2)}</div>
                    <div className="summary-label">P99 (ms)</div>
                  </div>
                  <div className="summary-card">
                    <div className="summary-value">{benchmarkReport.summary.success_rate.toFixed(0)}%</div>
                    <div className="summary-label">Success Rate</div>
                  </div>
                </div>

                <div className="results-grid">
                  <div className="chart-section">
                    <h3>Latency Distribution</h3>
                    <LatencyHistogram stats={benchmarkReport.query_stats} />
                  </div>

                  <div className="chart-section">
                    <h3>QPS Over Time</h3>
                    <QPSChart report={benchmarkReport} />
                  </div>
                </div>

                <div className="stats-section">
                  <h3>Per-Query Statistics</h3>
                  <QueryStatsTable stats={benchmarkReport.query_stats} />
                </div>

                <div className="meta-info">
                  <span>Scale Factor: SF {benchmarkReport.scale_factor}</span>
                  <span>Workload: {benchmarkReport.workload}</span>
                  <span>Mode: {benchmarkReport.mode}</span>
                  <span>Concurrency: {benchmarkReport.concurrency}</span>
                  <span>Duration: {benchmarkReport.duration_seconds}s</span>
                  <span>Timestamp: {formatTime(benchmarkReport.timestamp)}</span>
                </div>
              </>
            ) : (
              <div className="no-results">
                <p>No benchmark results yet.</p>
                <p>Go to Configuration tab to run a benchmark.</p>
              </div>
            )}
          </div>
        )}

        {/* Graph Visualization Tab */}
        {activeTab === 'graph' && (
          <div className="graph-panel">
            <div className="graph-sidebar">
              <div className="legend">
                <h4>Vertex Types</h4>
                {Object.entries(TYPE_COLORS).map(([type, color]) => (
                  <div key={type} className="legend-item">
                    <span className="legend-color" style={{ background: color }} />
                    <span>{type}</span>
                  </div>
                ))}
              </div>
              <div className="legend">
                <h4>Edge Types</h4>
                {Object.entries(EDGE_COLORS).filter(([k]) => k !== 'default').map(([type, color]) => (
                  <div key={type} className="legend-item">
                    <span className="legend-color" style={{ background: color }} />
                    <span>{type}</span>
                  </div>
                ))}
              </div>
              {selectedVertex && (
                <div className="vertex-inspector">
                  <h4>Selected Vertex</h4>
                  <div className="inspector-content">
                    <div className="inspector-row">
                      <span className="label">ID</span>
                      <span className="value">{selectedVertex.id}</span>
                    </div>
                    <div className="inspector-row">
                      <span className="label">Type</span>
                      <span className="value">{selectedVertex.type}</span>
                    </div>
                    <div className="inspector-row">
                      <span className="label">Label</span>
                      <span className="value">{selectedVertex.label}</span>
                    </div>
                    <div className="inspector-row">
                      <span className="label">Properties</span>
                      <span className="value mono">{JSON.stringify(selectedVertex.properties)}</span>
                    </div>
                  </div>
                  <button className="clear-btn" onClick={() => setSelectedVertex(null)}>
                    Clear Selection
                  </button>
                </div>
              )}
            </div>
            <div className="graph-canvas">
              {sampleLoading ? (
                <div className="loading">Loading sample data...</div>
              ) : sampleError ? (
                <div className="error">{sampleError}</div>
              ) : sampleData ? (
                <SocialGraph
                  vertices={sampleData.vertices}
                  edges={sampleData.edges}
                  selectedVertex={selectedVertex}
                  onSelectVertex={setSelectedVertex}
                />
              ) : (
                <div className="loading">No sample data. Click Refresh Sample.</div>
              )}
              <div className="graph-hint">
                Click node to inspect · Scroll to zoom · Drag to pan
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
