import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MedGraphNode {
  id: string;
  label: string;
  kind: 'patient' | 'encounter' | 'condition' | 'medication' | 'provider' | 'payer';
  gender?: string;
  race?: string;
  city?: string;
  age?: number;
  cost?: number;
  start?: string;
  code?: string;
  speciality?: string;
}

interface MedGraphEdge {
  source: string;
  target: string;
  kind: string;
}

interface MedGraphStats {
  patient_count: number;
  encounter_count: number;
  condition_count: number;
  medication_count: number;
  provider_count: number;
  payer_count: number;
  avg_encounter_cost: number;
  condition_distribution: Record<string, number>;
}

interface MedGraphAPIResponse {
  ok: boolean;
  source: string;
  seed: number;
  stats: MedGraphStats;
  patients: { id: string; name: string; gender: string; race: string; city: string; encounter_count: number }[];
  nodes: MedGraphNode[];
  edges: MedGraphEdge[];
}

interface PatientDetail {
  patient: { id: string; name: string; gender: string; race: string; birthday: string; city: string };
  encounters: { id: string; class: string; cost: number; start: string }[];
  conditions: { id: string; description: string; code: string; start: string }[];
  medications: { id: string; description: string; code: string; cost: number }[];
}

// ---------------------------------------------------------------------------
// Color map per node kind
// ---------------------------------------------------------------------------

const KIND_COLORS: Record<string, string> = {
  patient:    '#5b9cf6',
  encounter:  '#f5a623',
  condition:  '#e85255',
  medication: '#7ed321',
  provider:   '#bb8fce',
  payer:      '#50e3c2',
};

const KIND_RADII: Record<string, number> = {
  patient:    14,
  encounter:  8,
  condition:  5,
  medication: 5,
  provider:   7,
  payer:      6,
};

// ---------------------------------------------------------------------------
// Condition distribution chart (SVG bar chart)
// ---------------------------------------------------------------------------

function ConditionChart({ dist }: { dist: Record<string, number> }) {
  const entries = Object.entries(dist).sort((a, b) => b[1] - a[1]).slice(0, 8);
  if (!entries.length) return null;
  const max = entries[0][1];
  const W = 200, H = 100, PAD = 8;
  const barH = Math.min(10, (H - PAD * 2) / entries.length);

  return (
    <div style={{ padding: '12px 14px', borderTop: '1px solid var(--tg-dark-border)' }}>
      <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
        Conditions
      </div>
      <svg width={W} height={H}>
        {entries.map(([label, count], i) => {
          const bw = ((count / max) * (W - PAD * 2));
          const y = PAD + i * (barH + 2);
          return (
            <g key={label}>
              <rect x={0} y={y} width={bw} height={barH} fill={KIND_COLORS.condition} opacity={0.7} rx={2} />
              <text x={bw + 4} y={y + barH - 1} fontSize={9} fill="var(--tg-text-muted)">
                {label} ({count})
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

// ---------------------------------------------------------------------------
// D3 force-directed graph
// ---------------------------------------------------------------------------

function MedGraphGraph({
  nodes,
  edges,
  selectedNode,
  onSelect,
}: {
  nodes: MedGraphNode[];
  edges: MedGraphEdge[];
  selectedNode: MedGraphNode | null;
  onSelect: (n: MedGraphNode | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const W = svgRef.current.clientWidth || 700;
    const H = svgRef.current.clientHeight || 480;

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrowhead').attr('viewBox', '0 -5 10 10')
      .attr('refX', 18).attr('refY', 0).attr('markerWidth', 6).attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path').attr('d', 'M0,-5L10,0L0,5').attr('fill', '#5b6477');

    const g = svg.append('g');

    const sim = d3.forceSimulation(nodes as d3.SimulationNodeDatum[])
      .force('link', d3.forceLink(edges).id((d: any) => d.id).distance(60).strength(0.5))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius((d: any) => KIND_RADII[d.kind] + 5));

    const link = g.append('g').selectAll('line')
      .data(edges).join('line')
      .attr('stroke', '#3a4055').attr('stroke-width', 1)
      .attr('marker-end', 'url(#arrowhead)');

    const node = g.append('g').selectAll('g')
      .data(nodes).join('g')
      .style('cursor', 'pointer')
      .on('click', (_: MouseEvent, d: any) => onSelect(d as MedGraphNode))
      .call(d3.drag<SVGGElement, MedGraphNode>()
        .on('start', (event, d: any) => {
          if (!event.active) sim.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event, d: any) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event, d: any) => {
          if (!event.active) sim.alphaTarget(0);
          d.fx = null; d.fy = null;
        })
      );

    node.append('circle')
      .attr('r', d => KIND_RADII[d.kind])
      .attr('fill', d => KIND_COLORS[d.kind])
      .attr('stroke', d => selectedNode?.id === d.id ? '#fff' : 'transparent')
      .attr('stroke-width', 2);

    node.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', d => KIND_RADII[d.kind] + 12)
      .attr('font-size', 9)
      .attr('fill', 'var(--tg-text-muted)')
      .text(d => d.label.length > 12 ? d.label.slice(0, 12) + '…' : d.label);

    sim.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    return () => { sim.stop(); };
  }, [nodes, edges, selectedNode]);

  return (
    <svg
      ref={svgRef}
      style={{ width: '100%', height: '100%', background: 'var(--tg-dark-bg2)' }}
    />
  );
}

// ---------------------------------------------------------------------------
// Node inspector panel
// ---------------------------------------------------------------------------

function NodeInspector({ node }: { node: MedGraphNode | null }) {
  if (!node) return (
    <div style={{ padding: 16, color: 'var(--tg-text-muted)', fontSize: 12 }}>
      Click a node to inspect
    </div>
  );

  const kindLabel: Record<string, string> = {
    patient: 'Patient', encounter: 'Encounter', condition: 'Condition',
    medication: 'Medication', provider: 'Provider', payer: 'Payer',
  };

  return (
    <div style={{ padding: 16, fontSize: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{
          width: 12, height: 12, borderRadius: '50%',
          background: KIND_COLORS[node.kind], flexShrink: 0,
        }} />
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--tg-text-main)' }}>
          {node.label}
        </span>
        <span style={{ fontSize: 10, color: 'var(--tg-text-muted)', marginLeft: 'auto' }}>
          {kindLabel[node.kind]}
        </span>
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          {node.gender && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>Gender</td><td style={{ textAlign: 'right' }}>{node.gender}</td></tr>}
          {node.race && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>Race</td><td style={{ textAlign: 'right' }}>{node.race}</td></tr>}
          {node.city && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>City</td><td style={{ textAlign: 'right' }}>{node.city}</td></tr>}
          {node.age && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>Age</td><td style={{ textAlign: 'right' }}>{node.age}</td></tr>}
          {node.code && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>Code</td><td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 11 }}>{node.code}</td></tr>}
          {node.speciality && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>Speciality</td><td style={{ textAlign: 'right' }}>{node.speciality}</td></tr>}
          {node.cost != null && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>Cost</td><td style={{ textAlign: 'right' }}>${node.cost.toFixed(2)}</td></tr>}
          {node.start && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>Date</td><td style={{ textAlign: 'right' }}>{node.start.slice(0, 10)}</td></tr>}
          {node.id && <tr><td style={{ color: 'var(--tg-text-muted)', padding: '2px 0' }}>ID</td><td style={{ textAlign: 'right', fontFamily: 'monospace', fontSize: 10 }}>{node.id}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Patient list with filter
// ---------------------------------------------------------------------------

function PatientList({
  patients,
  onSelect,
}: {
  patients: MedGraphAPIResponse['patients'];
  onSelect: (id: string) => void;
}) {
  const [filter, setFilter] = useState('');
  const filtered = patients.filter(p =>
    p.name.toLowerCase().includes(filter.toLowerCase()) ||
    p.city.toLowerCase().includes(filter.toLowerCase())
  );
  return (
    <div>
      <div style={{ padding: '12px 14px', borderTop: '1px solid var(--tg-dark-border)' }}>
        <input
          type="text"
          placeholder="Search patients…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          style={{
            width: '100%', background: 'var(--tg-dark-bg2)',
            border: '1px solid var(--tg-dark-border)', borderRadius: 4,
            color: 'var(--tg-text-main)', padding: '4px 8px',
            fontSize: 12, outline: 'none',
          }}
        />
      </div>
      <div style={{ overflowY: 'auto', maxHeight: 200 }}>
        {filtered.slice(0, 50).map(p => (
          <div
            key={p.id}
            onClick={() => onSelect(p.id)}
            style={{
              padding: '6px 14px', cursor: 'pointer', fontSize: 12,
              borderBottom: '1px solid var(--tg-dark-border)',
            }}
            onMouseEnter={e => (e.currentTarget.style.background = 'var(--tg-dark-bg2)')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
          >
            <div style={{ color: 'var(--tg-text-main)' }}>{p.name}</div>
            <div style={{ color: 'var(--tg-text-muted)', fontSize: 10 }}>
              {p.city} · {p.gender} · {p.encounter_count} encounters
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main view
// ---------------------------------------------------------------------------

export function MedGraphView() {
  const [data, setData] = useState<MedGraphAPIResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<MedGraphNode | null>(null);
  const [selectedPatient, setSelectedPatient] = useState<PatientDetail | null>(null);
  const [nPatients, setNPatients] = useState(80);
  const [seed, setSeed] = useState(42);
  const [showKind, setShowKind] = useState<Set<string>>(new Set(Object.keys(KIND_COLORS)));

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedPatient(null);
    try {
      const res = await fetch(`/api/medgraph/sample?n_patients=${nPatients}&seed=${seed}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: MedGraphAPIResponse = await res.json();
      setData(json);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [nPatients, seed]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Fetch patient detail when a patient node is clicked
  const handleNodeClick = useCallback(async (node: MedGraphNode | null) => {
    setSelectedNode(node);
    if (!node || node.kind !== 'patient') { setSelectedPatient(null); return; }
    try {
      const res = await fetch(`/api/medgraph/patient/${node.id}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: PatientDetail = await res.json();
      setSelectedPatient(json);
    } catch { /* ignore */ }
  }, []);

  const visibleNodes = data ? data.nodes.filter(n => showKind.has(n.kind)) : [];
  const nodeIds = new Set(visibleNodes.map(n => n.id));
  const visibleEdges = data
    ? data.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
    : [];

  const stats = data?.stats;

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left sidebar */}
      <div style={{ width: 220, background: 'var(--tg-dark-bg)', borderRight: '1px solid var(--tg-dark-border)', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '14px', borderBottom: '1px solid var(--tg-dark-border)' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--tg-text-main)', marginBottom: 4 }}>
            Synthea MedGraph
          </div>
          <div style={{ fontSize: 11, color: 'var(--tg-text-muted)' }}>
            Patient health graph — TigerGraph DevLabs
          </div>
        </div>

        {/* Controls */}
        <div style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 6, borderBottom: '1px solid var(--tg-dark-border)' }}>
          <label style={{ fontSize: 11, color: 'var(--tg-text-muted)' }}>
            Patients: {nPatients}
            <input type="range" min={20} max={200} value={nPatients}
              onChange={e => setNPatients(Number(e.target.value))}
              style={{ width: '100%', marginTop: 4 }} />
          </label>
          <div style={{ display: 'flex', gap: 6 }}>
            <input type="number" value={seed} onChange={e => setSeed(Number(e.target.value))}
              style={{ width: 60, background: 'var(--tg-dark-bg2)', border: '1px solid var(--tg-dark-border)',
                       borderRadius: 4, color: 'var(--tg-text-main)', padding: '2px 6px', fontSize: 11 }} />
            <button onClick={fetchData}
              style={{ flex: 1, padding: '4px 8px', background: 'var(--tg-accent)', border: 'none',
                       borderRadius: 4, color: '#fff', fontSize: 11, cursor: 'pointer' }}>
              Reload
            </button>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--tg-dark-border)' }}>
            <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Statistics</div>
            {[
              ['Patients', stats.patient_count, KIND_COLORS.patient],
              ['Encounters', stats.encounter_count, KIND_COLORS.encounter],
              ['Conditions', stats.condition_count, KIND_COLORS.condition],
              ['Medications', stats.medication_count, KIND_COLORS.medication],
              ['Avg Cost', `$${stats.avg_encounter_cost.toFixed(0)}`, KIND_COLORS.encounter],
            ].map(([label, val, color]) => (
              <div key={String(label)} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, fontSize: 12 }}>
                <span style={{ color: 'var(--tg-text-muted)' }}>{label}</span>
                <span style={{ color: 'var(--tg-text-main)', fontWeight: 600 }}>{String(val)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Kind filter */}
        <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--tg-dark-border)' }}>
          <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>Show</div>
          {Object.entries(KIND_COLORS).map(([kind, color]) => (
            <label key={kind} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, fontSize: 11, cursor: 'pointer' }}>
              <input type="checkbox" checked={showKind.has(kind)}
                onChange={() => {
                  const next = new Set(showKind);
                  next.has(kind) ? next.delete(kind) : next.add(kind);
                  setShowKind(next);
                }} />
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
              <span style={{ color: 'var(--tg-text-main)', textTransform: 'capitalize' }}>{kind}</span>
            </label>
          ))}
        </div>

        {/* Condition chart */}
        {stats && <ConditionChart dist={stats.condition_distribution} />}

        {/* Patient list */}
        {data && <PatientList patients={data.patients} onSelect={(id) => {
          const n = data.nodes.find(n => n.id === id);
          if (n) handleNodeClick(n);
        }} />}
      </div>

      {/* Main canvas */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {loading && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(15,17,23,0.8)', zIndex: 10 }}>
            <span style={{ color: 'var(--tg-text-main)', fontSize: 14 }}>Loading MedGraph…</span>
          </div>
        )}
        {error && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: 'var(--tg-error)', fontSize: 13 }}>Error: {error}</span>
          </div>
        )}
        {!loading && !error && data && (
          <MedGraphGraph
            nodes={visibleNodes}
            edges={visibleEdges}
            selectedNode={selectedNode}
            onSelect={handleNodeClick}
          />
        )}
      </div>

      {/* Right inspector */}
      <div style={{ width: 240, background: 'var(--tg-dark-bg)', borderLeft: '1px solid var(--tg-dark-border)', overflowY: 'auto' }}>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--tg-dark-border)', fontSize: 12, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
          Inspector
        </div>
        <NodeInspector node={selectedNode} />

        {selectedPatient && (
          <>
            <div style={{ padding: '12px 14px', borderTop: '1px solid var(--tg-dark-border)', fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 8 }}>
              Conditions ({selectedPatient.conditions.length})
            </div>
            {selectedPatient.conditions.map(c => (
              <div key={c.id} style={{ padding: '4px 14px', fontSize: 11, borderBottom: '1px solid var(--tg-dark-border)' }}>
                <div style={{ color: 'var(--tg-text-main)' }}>{c.description}</div>
                <div style={{ color: 'var(--tg-text-muted)', fontFamily: 'monospace', fontSize: 10 }}>{c.code}</div>
              </div>
            ))}
            <div style={{ padding: '12px 14px', borderTop: '1px solid var(--tg-dark-border)', fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginTop: 8 }}>
              Medications ({selectedPatient.medications.length})
            </div>
            {selectedPatient.medications.map(m => (
              <div key={m.id} style={{ padding: '4px 14px', fontSize: 11, borderBottom: '1px solid var(--tg-dark-border)' }}>
                <div style={{ color: 'var(--tg-text-main)' }}>{m.description}</div>
                <div style={{ color: 'var(--tg-text-muted)', fontFamily: 'monospace', fontSize: 10 }}>${m.cost.toFixed(2)}</div>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
