import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as d3 from 'd3';

// ===========================================================================
// Types - aligned with /api/funds/* responses
// ===========================================================================

interface FundsPathRow {
  source: string;
  target: string;
  pathNodes: string[];
  totalAmount: number;
  edge_count: number;
}

interface FundsPathResult {
  results: Array<{
    paths: FundsPathRow[];
    path_count: number;
    max_amount: number;
    max_hops: number;
    seed_id: string;
    start_ts: string;
  }>;
}

interface FundsCirclesResult {
  results: Array<{
    totalAmount: number;
    ringCount: number;
    accountIds: string[];
    byAccount: Record<string, { ring_len_count: number; totalAmount: number }>;
    min_total: number;
    max_hops: number;
    min_hops: number;
  }>;
}

interface FundsBurstRow {
  suspiciousSource: string;
  suspiciousTarget: string;
  transferAmount: number;
  historicalAverage: number;
  ratio: number;
  ts: string;
  tx_id: string;
}

interface FundsBurstResult {
  results: Array<{
    suspicious: FundsBurstRow[];
    flagged_count: number;
    burst_factor: number;
    start_ts: string;
  }>;
}

interface FundsPathAPIResponse {
  ok: boolean;
  result: FundsPathResult;
  alert: RiskAlert | null;
}

interface FundsCirclesAPIResponse {
  ok: boolean;
  result: FundsCirclesResult;
  alert: RiskAlert | null;
}

interface FundsBurstAPIResponse {
  ok: boolean;
  result: FundsBurstResult;
  alert: RiskAlert | null;
}

interface RiskAlert {
  kind: string;
  severity: string;
  score: number;
  title: string;
  description: string;
  involved: string[];
  evidence: Record<string, unknown>;
}

interface MonitorStatus {
  running: boolean;
  started_at: string | null;
  last_run_at: string | null;
  last_alert_count: number;
  last_alert_kinds: string[];
  runs_total: number;
  runs_failed: number;
  config: {
    interval_minutes: number;
    webhook_url: string | null;
    dry_run: boolean;
    dataset_seed: number | null;
  };
  last_error: string | null;
}

type FundsResult = FundsPathResult | FundsCirclesResult | FundsBurstResult;

interface DetectorRun {
  detector: 'path' | 'circles' | 'burst';
  alert: RiskAlert | null;
  result: FundsResult | null;
  loading: boolean;
  error: string | null;
}

// ===========================================================================
// Palette + helpers
// ===========================================================================

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ff5d6c',
  high: '#ff9c4a',
  medium: '#ffd866',
  low: '#6ad1ff',
};

const KIND_LABELS: Record<string, string> = {
  funds_path_trace: 'Path Trace',
  circular_funds_rings: 'Circular Funds',
  burst_transactions_funds: 'Burst Amount',
  burst_transactions: 'Burst Amount',
};

const DD = String.fromCharCode(45, 45);  // '--' for CSS vars

function fmtMoney(n: number): string {
  if (!Number.isFinite(n)) return '--';
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toFixed(2);
}

function fmtRelative(iso: string | null): string {
  if (!iso) return 'never';
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return iso;
  const delta = Math.round((Date.now() - t) / 1000);
  if (delta < 60) return delta + 's ago';
  if (delta < 3600) return Math.floor(delta / 60) + 'm ago';
  if (delta < 86400) return Math.floor(delta / 3600) + 'h ago';
  return Math.floor(delta / 86400) + 'd ago';
}

// ===========================================================================
// Status pill
// ===========================================================================

function StatusPill({ monitor }: { monitor: MonitorStatus | null }) {
  const running = !!monitor?.running;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 10px', borderRadius: 10, fontSize: 11,
      background: running ? 'rgba(106,209,255,0.12)' : 'rgba(255,255,255,0.04)',
      border: '1px solid ' + (running ? '#6ad1ff' : 'var(' + DD + 'tg-dark-border)'),
      color: running ? '#6ad1ff' : 'var(' + DD + 'tg-text-muted)',
    }}>
      <span className={running ? 'status-dot status-dot-green' : 'status-dot status-dot-gray'} />
      {running ? 'monitor running' : 'monitor idle'}
      {monitor?.last_run_at && (
        <span style={{ marginLeft: 4, color: 'var(' + DD + 'tg-text-muted)' }}>
          · last {fmtRelative(monitor.last_run_at)}
        </span>
      )}
    </span>
  );
}

// ===========================================================================
// AlertCard - mirrors RobustnessView's alert card
// ===========================================================================

function AlertCard({ alert }: { alert: RiskAlert | null }) {
  if (!alert) {
    return (
      <div style={{
        padding: 14, background: 'var(' + DD + 'tg-dark-bg2, #0d1117)',
        borderRadius: 6, border: '1px solid var(' + DD + 'tg-dark-border)',
        color: 'var(' + DD + 'tg-text-muted)', fontSize: 12, lineHeight: 1.6,
      }}>
        <div style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>No alert</div>
        <div>Detector ran cleanly. Try increasing burst_factor or lowering min_total to surface more signal.</div>
      </div>
    );
  }
  const sev = (alert.severity || 'low').toLowerCase();
  const color = SEVERITY_COLORS[sev] || '#6ad1ff';
  return (
    <div style={{
      padding: 14, background: 'var(' + DD + 'tg-dark-bg2, #0d1117)',
      borderRadius: 6, border: '1px solid var(' + DD + 'tg-dark-border)',
      borderLeft: '3px solid ' + color, fontSize: 12, lineHeight: 1.6,
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
        <span>Involved: <strong style={{ fontFamily: 'JetBrains Mono, monospace' }}>{alert.involved.length}</strong></span>
      </div>
    </div>
  );
}

// ===========================================================================
// Burst inspector - scatter of (ratio, amount) + top table
// ===========================================================================

interface BurstScatterProps {
  rows: FundsBurstRow[];
}

function BurstScatter({ rows }: BurstScatterProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    const W = svgRef.current.clientWidth || 300;
    const H = svgRef.current.clientHeight || 200;
    const margin = { top: 8, right: 12, bottom: 24, left: 36 };
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;
    const g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    if (rows.length === 0) return;
    const xs = d3.extent(rows, d => d.ratio) as [number, number];
    const ys = d3.extent(rows, d => d.transferAmount) as [number, number];
    const x = d3.scaleLinear().domain([Math.max(1, xs[0]), xs[1] * 1.05 || 10]).range([0, innerW]);
    const y = d3.scaleLog().domain([Math.max(1, ys[0]), ys[1] * 1.05 || 1000]).range([innerH, 0]);

    // Axes
    g.append('g').attr('transform', 'translate(0,' + innerH + ')')
      .call(d3.axisBottom(x).ticks(5))
      .selectAll('text').attr('fill', 'var(' + DD + 'tg-text-muted)').attr('font-size', 9);
    g.append('g').call(d3.axisLeft(y).ticks(4, '~s'))
      .selectAll('text').attr('fill', 'var(' + DD + 'tg-text-muted)').attr('font-size', 9);

    // Axis labels
    g.append('text').attr('x', innerW / 2).attr('y', innerH + 18)
      .attr('text-anchor', 'middle').attr('fill', 'var(' + DD + 'tg-text-muted)')
      .attr('font-size', 10).text('ratio (transfer / historical avg)');
    g.append('text').attr('transform', 'translate(-26,' + innerH / 2 + ') rotate(-90)')
      .attr('text-anchor', 'middle').attr('fill', 'var(' + DD + 'tg-text-muted)')
      .attr('font-size', 10).text('transfer amount');

    // 5x threshold line (typical burst_factor)
    g.append('line')
      .attr('x1', x(5)).attr('x2', x(5))
      .attr('y1', 0).attr('y2', innerH)
      .attr('stroke', '#ffd866').attr('stroke-dasharray', '3,2').attr('stroke-width', 1);
    g.append('text').attr('x', x(5) + 3).attr('y', 10)
      .attr('fill', '#ffd866').attr('font-size', 9).text('5x');

    // Dots
    g.selectAll('circle.b')
      .data(rows.slice(0, 200))
      .enter()
      .append('circle')
      .attr('class', 'b')
      .attr('cx', d => x(d.ratio))
      .attr('cy', d => y(d.transferAmount))
      .attr('r', 3)
      .attr('fill', '#ff5d6c')
      .attr('opacity', 0.7);
  }, [rows]);
  return <svg ref={svgRef} style={{ width: '100%', height: 200, display: 'block' }} />;
}

// ===========================================================================
// Path inspector - top-N longest paths as a horizontal mini graph
// ===========================================================================

interface PathVizProps {
  paths: FundsPathRow[];
}

function PathViz({ paths }: PathVizProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();
    const W = svgRef.current.clientWidth || 300;
    const H = svgRef.current.clientHeight || 200;
    const margin = { top: 8, right: 8, bottom: 8, left: 8 };
    const innerW = W - margin.left - margin.right;
    const innerH = H - margin.top - margin.bottom;
    const g = svg.append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    if (paths.length === 0) return;
    const top = [...paths].sort((a, b) => b.totalAmount - a.totalAmount).slice(0, 10);
    const ROW_H = Math.min(18, innerH / Math.max(top.length, 1));

    top.forEach((p, i) => {
      const y = i * ROW_H + ROW_H / 2;
      const nodes = p.pathNodes;
      const xStep = innerW / Math.max(nodes.length - 1, 1);

      // Chain of dots
      nodes.forEach((acc, j) => {
        g.append('circle')
          .attr('cx', j * xStep).attr('cy', y).attr('r', 3)
          .attr('fill', j === 0 || j === nodes.length - 1 ? '#6ad1ff' : '#ffd866');
        if (j > 0) {
          g.append('line')
            .attr('x1', (j - 1) * xStep).attr('x2', j * xStep)
            .attr('y1', y).attr('y2', y)
            .attr('stroke', '#3a4055').attr('stroke-width', 1);
        }
      });
      // Total label on the right
      g.append('text')
        .attr('x', innerW - 4).attr('y', y + 3)
        .attr('text-anchor', 'end')
        .attr('fill', '#ff9c4a')
        .attr('font-size', 9)
        .attr('font-family', 'JetBrains Mono, monospace')
        .text(fmtMoney(p.totalAmount));
      // Hops label on the left
      g.append('text')
        .attr('x', 0).attr('y', y + 3)
        .attr('text-anchor', 'start')
        .attr('fill', 'var(' + DD + 'tg-text-muted)')
        .attr('font-size', 9)
        .text(p.edge_count + 'h');
    });
  }, [paths]);
  return <svg ref={svgRef} style={{ width: '100%', height: 200, display: 'block' }} />;
}

// ===========================================================================
// Circles inspector - hop distribution bar chart
// ===========================================================================

interface CirclesVizProps {
  byAccount: Record<string, { ring_len_count: number; totalAmount: number }>;
  ringCount: number;
  accountIds: string[];
}

function CirclesViz({ byAccount, ringCount, accountIds }: CirclesVizProps) {
  const top = useMemo(() => {
    const entries = Object.entries(byAccount).map(([k, v]) => ({
      account: k,
      ringCount: v.ring_len_count || 0,
      totalAmount: v.totalAmount || 0,
    }));
    return entries.sort((a, b) => b.ringCount - a.ringCount).slice(0, 20);
  }, [byAccount]);

  const maxR = Math.max(1, ...top.map(t => t.ringCount));
  return (
    <div style={{ padding: '8px 0' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 6, fontSize: 11 }}>
        <span style={{ color: 'var(' + DD + 'tg-text-muted)' }}>Total rings detected</span>
        <strong style={{ color: '#ff5d6c', fontFamily: 'JetBrains Mono, monospace' }}>{ringCount}</strong>
        <span style={{ color: 'var(' + DD + 'tg-text-muted)' }}>Unique accounts in rings</span>
        <strong style={{ fontFamily: 'JetBrains Mono, monospace' }}>{accountIds.length}</strong>
      </div>
      <div style={{ marginTop: 12 }}>
        <div style={{ fontSize: 10, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>
          Top 20 accounts by ring involvement
        </div>
        {top.map(t => (
          <div key={t.account} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{
              width: 84, fontSize: 10, color: 'var(' + DD + 'tg-text-secondary)',
              fontFamily: 'JetBrains Mono, monospace', overflow: 'hidden',
              textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }} title={t.account}>{t.account}</span>
            <div style={{
              flex: 1, height: 5, background: 'var(' + DD + 'tg-dark-bg)',
              borderRadius: 2, overflow: 'hidden',
            }}>
              <div style={{
                width: ((t.ringCount / maxR) * 100) + '%', height: '100%',
                background: '#ff5d6c', borderRadius: 2,
              }} />
            </div>
            <span style={{
              minWidth: 36, textAlign: 'right', fontSize: 10,
              fontFamily: 'JetBrains Mono, monospace', color: '#ff5d6c',
            }}>{t.ringCount}</span>
            <span style={{
              minWidth: 56, textAlign: 'right', fontSize: 10,
              fontFamily: 'JetBrains Mono, monospace',
              color: 'var(' + DD + 'tg-text-muted)',
            }}>{fmtMoney(t.totalAmount)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ===========================================================================
// Main panel
// ===========================================================================

export function FundsMonitorPanel() {
  const [datasetReady, setDatasetReady] = useState(false);
  const [needsBuild, setNeedsBuild] = useState(false);
  const [buildError, setBuildError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Detector knobs
  const [seedAccount, setSeedAccount] = useState('A000001');
  const [minTotal, setMinTotal] = useState(50000);
  const [maxHops, setMaxHops] = useState(6);
  const [minHops, setMinHops] = useState(3);
  const [burstFactor, setBurstFactor] = useState(5.0);

  // Detector runs
  const [pathRun, setPathRun] = useState<DetectorRun>({ detector: 'path', alert: null, result: null, loading: false, error: null });
  const [circlesRun, setCirclesRun] = useState<DetectorRun>({ detector: 'circles', alert: null, result: null, loading: false, error: null });
  const [burstRun, setBurstRun] = useState<DetectorRun>({ detector: 'burst', alert: null, result: null, loading: false, error: null });
  const [selected, setSelected] = useState<'path' | 'circles' | 'burst' | null>(null);

  // Monitor
  const [monitor, setMonitor] = useState<MonitorStatus | null>(null);
  const [monitorCfg, setMonitorCfg] = useState({
    interval_minutes: 60,
    webhook_url: '',
    dry_run: true,
    dataset_seed: '',
  });
  const [monitorBusy, setMonitorBusy] = useState(false);

  // Auto-pick highest-degree seed default — left to user override; backend
  // already resolves a sensible seed via `funds_paths(...)` if start_id is empty.

  // Probe readiness + monitor status on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch('/api/dataset');
        if (cancelled) return;
        if (r.ok) {
          const body = await r.json();
          setDatasetReady(!!body?.accounts);
        } else {
          setNeedsBuild(true);
        }
      } catch { /* ignore */ }
      try {
        const r = await fetch('/api/funds/monitor');
        if (cancelled) return;
        if (r.ok) {
          const body: MonitorStatus = await r.json();
          setMonitor(body);
          setMonitorCfg(prev => ({
            interval_minutes: body.config.interval_minutes ?? prev.interval_minutes,
            webhook_url: body.config.webhook_url ?? prev.webhook_url,
            dry_run: body.config.dry_run ?? prev.dry_run,
            dataset_seed: body.config.dataset_seed != null ? String(body.config.dataset_seed) : prev.dataset_seed,
          }));
        }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const refreshMonitor = useCallback(async () => {
    try {
      const r = await fetch('/api/funds/monitor');
      if (r.ok) setMonitor(await r.json());
    } catch { /* ignore */ }
  }, []);

  // Refresh monitor status when a run finishes, so last_alert_count updates
  useEffect(() => {
    if (!busy) refreshMonitor();
  }, [busy, refreshMonitor]);

  const buildDataset = useCallback(async () => {
    setBusy(true); setBuildError(null);
    try {
      const r = await fetch('/api/dataset', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({}) });
      if (!r.ok) {
        const body = await r.json().catch(() => ({ detail: 'HTTP ' + r.status }));
        throw new Error(body.detail || 'HTTP ' + r.status);
      }
      setDatasetReady(true);
      setNeedsBuild(false);
    } catch (e: unknown) {
      setBuildError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  // Run the three detectors in parallel. Each updates its own slot.
  const runDetectors = useCallback(async () => {
    if (!datasetReady) {
      setNeedsBuild(true);
      return;
    }
    setSelected(null);
    setBusy(true);

    const callPath = async () => {
      setPathRun({ detector: 'path', alert: null, result: null, loading: true, error: null });
      try {
        const u = '/api/funds/path?start_id=' + encodeURIComponent(seedAccount) +
          '&max_hops=' + maxHops + '&max_paths=200';
        const r = await fetch(u);
        if (!r.ok) {
          const body = await r.json().catch(() => ({ detail: 'HTTP ' + r.status }));
          setPathRun({ detector: 'path', alert: null, result: null, loading: false, error: body.detail || ('HTTP ' + r.status) });
          return;
        }
        const body: FundsPathAPIResponse = await r.json();
        setPathRun({ detector: 'path', alert: body.alert ?? null, result: body.result ?? null, loading: false, error: null });
      } catch (e: unknown) {
        setPathRun({ detector: 'path', alert: null, result: null, loading: false, error: e instanceof Error ? e.message : String(e) });
      }
    };
    const callCircles = async () => {
      setCirclesRun({ detector: 'circles', alert: null, result: null, loading: true, error: null });
      try {
        const u = '/api/funds/circles?min_total=' + minTotal + '&max_hops=' + maxHops + '&min_hops=' + minHops;
        const r = await fetch(u);
        if (!r.ok) {
          const body = await r.json().catch(() => ({ detail: 'HTTP ' + r.status }));
          setCirclesRun({ detector: 'circles', alert: null, result: null, loading: false, error: body.detail || ('HTTP ' + r.status) });
          return;
        }
        const body: FundsCirclesAPIResponse = await r.json();
        setCirclesRun({ detector: 'circles', alert: body.alert ?? null, result: body.result ?? null, loading: false, error: null });
      } catch (e: unknown) {
        setCirclesRun({ detector: 'circles', alert: null, result: null, loading: false, error: e instanceof Error ? e.message : String(e) });
      }
    };
    const callBurst = async () => {
      setBurstRun({ detector: 'burst', alert: null, result: null, loading: true, error: null });
      try {
        const u = '/api/funds/burst?burst_factor=' + burstFactor;
        const r = await fetch(u);
        if (!r.ok) {
          const body = await r.json().catch(() => ({ detail: 'HTTP ' + r.status }));
          setBurstRun({ detector: 'burst', alert: null, result: null, loading: false, error: body.detail || ('HTTP ' + r.status) });
          return;
        }
        const body: FundsBurstAPIResponse = await r.json();
        setBurstRun({ detector: 'burst', alert: body.alert ?? null, result: body.result ?? null, loading: false, error: null });
      } catch (e: unknown) {
        setBurstRun({ detector: 'burst', alert: null, result: null, loading: false, error: e instanceof Error ? e.message : String(e) });
      }
    };

    await Promise.all([callPath(), callCircles(), callBurst()]);
    setBusy(false);
  }, [datasetReady, seedAccount, maxHops, minTotal, minHops, burstFactor]);

  // Note: a previous draft had a `runDetectorsInline` double-fetch; we keep the
  // call sites using `runDetectors` below to make behavioural drift impossible.
  const runDetectorsInline = runDetectors;

  // Monitor controls
  const startMonitor = useCallback(async () => {
    setMonitorBusy(true);
    try {
      const u = new URLSearchParams();
      u.set('interval_minutes', String(monitorCfg.interval_minutes));
      if (monitorCfg.webhook_url) u.set('webhook_url', monitorCfg.webhook_url);
      u.set('dry_run', String(monitorCfg.dry_run));
      if (monitorCfg.dataset_seed) u.set('dataset_seed', monitorCfg.dataset_seed);
      const r = await fetch('/api/funds/monitor/start?' + u.toString(), { method: 'POST' });
      if (r.ok) await refreshMonitor();
    } catch { /* ignore */ }
    setMonitorBusy(false);
  }, [monitorCfg, refreshMonitor]);

  const stopMonitor = useCallback(async () => {
    setMonitorBusy(true);
    try {
      const r = await fetch('/api/funds/monitor/stop', { method: 'POST' });
      if (r.ok) await refreshMonitor();
    } catch { /* ignore */ }
    setMonitorBusy(false);
  }, [refreshMonitor]);

  const triggerNow = useCallback(async () => {
    if (!monitor?.running) return;
    setBusy(true);
    try {
      const u = new URLSearchParams();
      u.set('interval_minutes', String(monitorCfg.interval_minutes));
      if (monitorCfg.dataset_seed) u.set('dataset_seed', monitorCfg.dataset_seed);
      // The monitor doesn't expose a dedicated "tick now" endpoint; instead we run
      // the three detectors inline, then refresh monitor status for fresh counts.
      await runDetectorsInline();
    } finally {
      setBusy(false);
      refreshMonitor();
    }
  }, [monitor, monitorCfg, runDetectorsInline, refreshMonitor]);

  // ---------------- Render ----------------

  const allAlerts: Array<{ detector: 'path' | 'circles' | 'burst'; alert: RiskAlert }> = [];
  if (pathRun.alert) allAlerts.push({ detector: 'path', alert: pathRun.alert });
  if (circlesRun.alert) allAlerts.push({ detector: 'circles', alert: circlesRun.alert });
  if (burstRun.alert) allAlerts.push({ detector: 'burst', alert: burstRun.alert });

  const borderColor = 'var(' + DD + 'tg-dark-border)';
  const borderLabel: Record<'path' | 'circles' | 'burst', string> = {
    path: '#6ad1ff',
    circles: '#ff5d6c',
    burst: '#ff9c4a',
  };

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left sidebar */}
      <aside style={{
        width: 280, minWidth: 280,
        background: 'var(' + DD + 'tg-dark-card, #161b22)',
        borderRight: '1px solid ' + borderColor,
        overflowY: 'auto',
      }}>
        <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid ' + borderColor }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(' + DD + 'tg-text-primary)' }}>Funds Monitor</div>
            <StatusPill monitor={monitor} />
          </div>
          <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', marginTop: 4 }}>
            Path trace · circular rings · burst amount
          </div>
        </div>

        {/* Dataset */}
        <Section title="Dataset" border={borderColor}>
          {!datasetReady && (
            <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', marginBottom: 8 }}>
              {needsBuild ? 'No dataset loaded.' : 'Checking…'}
            </div>
          )}
          {buildError && (
            <div style={{ fontSize: 11, color: '#ff5d6c', marginBottom: 8 }}>{buildError}</div>
          )}
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={buildDataset} disabled={busy} style={btnStyle(busy, '#6ad1ff')}>
              {busy ? 'Building…' : (datasetReady ? 'Rebuild' : 'Build dataset')}
            </button>
            <button onClick={runDetectorsInline} disabled={busy || !datasetReady} style={btnStyle(busy || !datasetReady, '#2d9cdb')}>
              {busy ? 'Running…' : 'Run detectors'}
            </button>
          </div>
        </Section>

        {/* Detector knobs */}
        <Section title="Detector settings" border={borderColor}>
          <Field label="Seed account (path)">
            <input value={seedAccount} onChange={e => setSeedAccount(e.target.value)} style={inputStyle} />
          </Field>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <Field label="Min total (circles)">
              <input type="number" min={0} value={minTotal} onChange={e => setMinTotal(Number(e.target.value))} style={inputStyle} />
            </Field>
            <Field label="Burst factor">
              <input type="number" min={1} step={0.5} value={burstFactor} onChange={e => setBurstFactor(Number(e.target.value))} style={inputStyle} />
            </Field>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <Field label="Min hops">
              <input type="number" min={3} max={8} value={minHops} onChange={e => setMinHops(Number(e.target.value))} style={inputStyle} />
            </Field>
            <Field label="Max hops">
              <input type="number" min={3} max={8} value={maxHops} onChange={e => setMaxHops(Number(e.target.value))} style={inputStyle} />
            </Field>
          </div>
        </Section>

        {/* Monitor */}
        <Section title="Background monitor" border={borderColor}>
          <Field label="Interval (minutes)">
            <input type="number" min={1} value={monitorCfg.interval_minutes} onChange={e => setMonitorCfg(s => ({ ...s, interval_minutes: Number(e.target.value) }))} style={inputStyle} />
          </Field>
          <Field label="Webhook URL (optional)">
            <input value={monitorCfg.webhook_url} onChange={e => setMonitorCfg(s => ({ ...s, webhook_url: e.target.value }))} placeholder="https://hooks.slack.com/..." style={inputStyle} />
          </Field>
          <Field label="Dataset seed (optional)">
            <input value={monitorCfg.dataset_seed} onChange={e => setMonitorCfg(s => ({ ...s, dataset_seed: e.target.value }))} placeholder="42" style={inputStyle} />
          </Field>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(' + DD + 'tg-text-secondary)', marginBottom: 8, cursor: 'pointer' }}>
            <input type="checkbox" checked={monitorCfg.dry_run} onChange={e => setMonitorCfg(s => ({ ...s, dry_run: e.target.checked }))} />
            Dry-run (don&apos;t POST webhook)
          </label>
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={startMonitor} disabled={monitorBusy || !!monitor?.running} style={btnStyle(monitorBusy || !!monitor?.running, '#6ad1ff')}>
              Start
            </button>
            <button onClick={stopMonitor} disabled={monitorBusy || !monitor?.running} style={btnStyle(monitorBusy || !monitor?.running, '#ff5d6c')}>
              Stop
            </button>
            <button onClick={triggerNow} disabled={busy || !monitor?.running} style={btnStyle(busy || !monitor?.running, '#ff9c4a')}>
              Tick now
            </button>
          </div>
          {monitor && (
            <div style={{ marginTop: 10, fontSize: 10, color: 'var(' + DD + 'tg-text-muted)', lineHeight: 1.6, fontFamily: 'JetBrains Mono, monospace' }}>
              runs_total={monitor.runs_total} · runs_failed={monitor.runs_failed}<br />
              last_alert_count={monitor.last_alert_count}<br />
              last_kinds=[{monitor.last_alert_kinds.join(', ')}]
              {monitor.last_error && <div style={{ color: '#ff5d6c', marginTop: 4 }}>err: {monitor.last_error}</div>}
            </div>
          )}
        </Section>
      </aside>

      {/* Center: alerts table + selected viz */}
      <main style={{ flex: 1, overflowY: 'auto', padding: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(' + DD + 'tg-text-primary)', margin: 0 }}>Funds-flow alerts</h2>
          <span style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)' }}>
            {allAlerts.length} alert{allAlerts.length === 1 ? '' : 's'} surfaced
          </span>
        </div>

        {allAlerts.length === 0 && (
          <div style={{
            padding: 18, borderRadius: 6,
            border: '1px dashed ' + borderColor,
            color: 'var(' + DD + 'tg-text-muted)', fontSize: 13,
          }}>
            {busy
              ? 'Running detectors…'
              : (datasetReady ? 'Click "Run detectors" to surface path / circle / burst signal.' : 'Build a dataset first.')}
          </div>
        )}

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid ' + borderColor }}>
              <Th>Kind</Th>
              <Th>Severity</Th>
              <Th>Title</Th>
              <Th style={{ textAlign: 'right' }}>Score</Th>
              <Th style={{ textAlign: 'right' }}>Involved</Th>
              <Th></Th>
            </tr>
          </thead>
          <tbody>
            {allAlerts.map(({ detector, alert }) => {
              const sev = (alert.severity || 'low').toLowerCase();
              const color = SEVERITY_COLORS[sev] || '#6ad1ff';
              return (
                <tr key={detector}
                  onClick={() => setSelected(detector)}
                  style={{
                    cursor: 'pointer',
                    background: selected === detector ? 'rgba(45,156,219,0.06)' : 'transparent',
                    borderLeft: '3px solid ' + (selected === detector ? borderLabel[detector] : 'transparent'),
                  }}>
                  <Td>{KIND_LABELS[alert.kind] || alert.kind}</Td>
                  <Td>
                    <span style={{
                      display: 'inline-block', padding: '2px 8px', borderRadius: 3,
                      fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                      background: color, color: '#0d1117',
                    }}>{sev}</span>
                  </Td>
                  <Td>{alert.title}</Td>
                  <Td mono style={{ textAlign: 'right' }}>{alert.score.toFixed(3)}</Td>
                  <Td mono style={{ textAlign: 'right' }}>{alert.involved.length}</Td>
                  <Td mono style={{ textAlign: 'right', color: 'var(' + DD + 'tg-text-muted)' }}>
                    {selected === detector ? 'viewing ▸' : 'click →'}
                  </Td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {/* Selected inspector below the table */}
          {selected && (
            <div style={{ marginTop: 22 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(' + DD + 'tg-text-primary)', marginBottom: 10 }}>
                {selected === 'path' ? 'Multi-hop path trace' : selected === 'circles' ? 'Circular funds rings' : 'Burst-amount edges'}
                <span style={{ marginLeft: 8, fontSize: 11, color: 'var(' + DD + 'tg-text-muted)' }}>
                  [{KIND_LABELS[(selected === 'path' ? pathRun : selected === 'circles' ? circlesRun : burstRun).alert?.kind || ''] || '—'}]
                </span>
              </h3>
              {selected === 'path' && (
                <PathViz paths={(pathRun.result as FundsPathResult | null)?.results?.[0]?.paths || []} />
              )}
              {selected === 'circles' && (
                <CirclesViz
                  byAccount={(circlesRun.result as FundsCirclesResult | null)?.results?.[0]?.byAccount || {}}
                  ringCount={(circlesRun.result as FundsCirclesResult | null)?.results?.[0]?.ringCount ?? 0}
                  accountIds={(circlesRun.result as FundsCirclesResult | null)?.results?.[0]?.accountIds ?? []}
                />
              )}
              {selected === 'burst' && (
                <BurstScatter rows={(burstRun.result as FundsBurstResult | null)?.results?.[0]?.suspicious || []} />
              )}
            </div>
          )}
      </main>

      {/* Right inspector */}
      <aside style={{
        width: 320, minWidth: 320,
        background: 'var(' + DD + 'tg-dark-card, #161b22)',
        borderLeft: '1px solid ' + borderColor,
        overflowY: 'auto', padding: 14,
      }}>
        <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
          Selected alert
        </div>
        {selected
          ? <AlertCard alert={(selected === 'path' ? pathRun : selected === 'circles' ? circlesRun : burstRun).alert} />
          : <AlertCard alert={null} />
        }

        {selected && (
          <>
            <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', margin: '16px 0 8px' }}>
              Evidence
            </div>
            <pre style={{
              fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
              padding: 12, borderRadius: 4,
              background: 'var(' + DD + 'tg-dark-bg2, #0d1117)',
              border: '1px solid var(' + DD + 'tg-dark-border)',
              color: 'var(' + DD + 'tg-text-secondary)',
              overflowX: 'auto', maxHeight: 340, margin: 0,
            }}>
              {JSON.stringify((selected === 'path' ? pathRun : selected === 'circles' ? circlesRun : burstRun).alert?.evidence || {}, null, 2)}
            </pre>

            {selected === 'burst' && burstRun.result && (
              <BurstTable rows={(burstRun.result as FundsBurstResult).results?.[0]?.suspicious || []} />
            )}
            {selected === 'path' && pathRun.result && (
              <PathTable rows={(pathRun.result as FundsPathResult).results?.[0]?.paths || []} />
            )}
          </>
        )}
      </aside>
    </div>
  );
}

// ===========================================================================
// Sub-components: BurstTable, PathTable, Section, Field, btnStyle, inputStyle
// ===========================================================================

function BurstTable({ rows }: { rows: FundsBurstRow[] }) {
  const top = rows.slice(0, 30);
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
        Top {top.length} burst edges
      </div>
      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {top.map(r => (
          <div key={r.tx_id} style={{
            display: 'grid', gridTemplateColumns: '1fr 1fr auto auto',
            gap: 6, padding: '4px 0',
            borderBottom: '1px solid var(' + DD + 'tg-dark-border)',
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
          }}>
            <span style={{ color: 'var(' + DD + 'tg-text-secondary)' }} title={r.suspiciousSource}>{shorten(r.suspiciousSource)}</span>
            <span style={{ color: 'var(' + DD + 'tg-text-secondary)' }} title={r.suspiciousTarget}>{shorten(r.suspiciousTarget)}</span>
            <span style={{ color: '#ff5d6c', textAlign: 'right' }}>{r.ratio.toFixed(2)}x</span>
            <span style={{ color: 'var(' + DD + 'tg-text-muted)', textAlign: 'right' }}>{fmtMoney(r.transferAmount)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PathTable({ rows }: { rows: FundsPathRow[] }) {
  const top = [...rows].sort((a, b) => b.totalAmount - a.totalAmount).slice(0, 20);
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
        Top {top.length} longest paths
      </div>
      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {top.map((r, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: 'auto 1fr auto',
            gap: 6, padding: '4px 0',
            borderBottom: '1px solid var(' + DD + 'tg-dark-border)',
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11,
          }}>
            <span style={{ color: 'var(' + DD + 'tg-text-muted)' }}>{r.edge_count}h</span>
            <span style={{ color: 'var(' + DD + 'tg-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.pathNodes.join(' → ')}>
              {r.pathNodes.map(shorten).join(' → ')}
            </span>
            <span style={{ color: '#ff9c4a', textAlign: 'right' }}>{fmtMoney(r.totalAmount)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function shorten(s: string): string {
  if (!s) return '';
  return s.length > 8 ? s.slice(0, 8) + '…' : s;
}

function Section({ title, border, children }: { title: string; border: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: '12px 14px', borderBottom: '1px solid ' + border }}>
      <div style={{ fontSize: 11, color: 'var(' + DD + 'tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'block', marginBottom: 8 }}>
      <div style={{ fontSize: 10, color: 'var(' + DD + 'tg-text-muted)', marginBottom: 3 }}>{label}</div>
      {children}
    </label>
  );
}

function Th({ children, style }: { children?: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <th style={{
      textAlign: 'left', padding: '8px 10px',
      color: 'var(' + DD + 'tg-text-muted)',
      fontWeight: 600, fontSize: 11,
      textTransform: 'uppercase', letterSpacing: '0.5px',
      ...(style || {}),
    }}>{children}</th>
  );
}

function Td({ children, style, mono }: { children?: React.ReactNode; style?: React.CSSProperties; mono?: boolean }) {
  return (
    <td style={{
      padding: '8px 10px',
      color: 'var(' + DD + 'tg-text-primary)',
      fontFamily: mono ? 'JetBrains Mono, monospace' : 'inherit',
      ...(style || {}),
    }}>{children}</td>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '5px 8px', fontSize: 12,
  borderRadius: 4, border: '1px solid var(' + DD + 'tg-dark-border)',
  background: 'var(' + DD + 'tg-dark-bg, #0d1117)',
  color: 'var(' + DD + 'tg-text-primary)',
  fontFamily: 'JetBrains Mono, monospace',
  boxSizing: 'border-box',
};

function btnStyle(disabled: boolean, accent: string): React.CSSProperties {
  return {
    padding: '6px 10px', fontSize: 12, fontWeight: 600,
    borderRadius: 4, cursor: disabled ? 'not-allowed' : 'pointer',
    border: '1px solid ' + accent,
    background: disabled ? 'transparent' : accent,
    color: disabled ? 'var(' + DD + 'tg-text-muted)' : '#0d1117',
    opacity: disabled ? 0.5 : 1,
    fontFamily: 'inherit',
  };
}
