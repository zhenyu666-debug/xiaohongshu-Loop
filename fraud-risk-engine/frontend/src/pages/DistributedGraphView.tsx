import { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';

interface ClusterNode {
  id: string;
  host: string;
  port: number;
  role: 'primary' | 'replica';
  shards: number[];
  cpu: number;
  memory_mb: number;
}

interface TopologyLink {
  from: string;
  to: string;
  latency_ms: number;
}

interface PartitionMap {
  [partition: number]: string[];
}

interface ClusterData {
  ok: boolean;
  source: string;
  nodes: ClusterNode[];
  replication_factor: number;
  total_partitions: number;
  partition_map?: PartitionMap;
  topology: TopologyLink[];
}

interface ScaleResult {
  ok: boolean;
  strategy: string;
  rebalance_triggered: boolean;
  total_nodes: number;
  replication_factor: number;
  total_partitions: number;
  nodes: ClusterNode[];
  partition_map: PartitionMap;
  topology: TopologyLink[];
  rebalance_estimate_gb: number;
}

interface QueryPlanData {
  ok: boolean;
  query_type: string;
  account_id: string;
  hops: number;
  plan: {
    strategy: string;
    partitions_touched: number;
    total_partitions: number;
    partition_ids: number[];
    network_hops: number;
    cross_partition_cost_ms: number;
    estimated_latency_ms: number;
    nodes_visited: number;
    edges_traversed: number;
  };
}

const ROLE_COLORS: Record<string, string> = {
  primary: '#2d9cdb',
  replica: '#6ad1ff',
};

const PARTITION_COLORS = [
  '#e85255', '#f5a623', '#ffd866', '#6ad1ff',
  '#5b9cf6', '#7ed321', '#bb8fce', '#50e3c2',
  '#f7b731', '#a55eea', '#26de81', '#fd9644',
  '#4b7bec', '#d1a3ff', '#20bf6b', '#3867d6',
];

const STRATEGY_COLORS: Record<string, string> = {
  hash: '#6ad1ff',
  range: '#f5a623',
  consistent_hash: '#7ed321',
};

interface SimNode {
  id: string;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

interface SimLink {
  source: SimNode | string;
  target: SimNode | string;
  latency_ms?: number;
}

function ClusterGraph({ nodes, links, onNodeClick, selectedNodeId }: {
  nodes: ClusterNode[];
  links: TopologyLink[];
  onNodeClick: (n: ClusterNode) => void;
  selectedNodeId: string | null;
}) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const W = svgRef.current.clientWidth || 600;
    const H = svgRef.current.clientHeight || 420;
    const g = svg.append('g');
    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.3, 3])
        .on('zoom', e => g.attr('transform', e.transform.toString()))
    );

    const simNodes: SimNode[] = nodes.map(n => ({ id: n.id }));
    const simLinks: SimLink[] = links.map(l => ({
      source: l.from,
      target: l.to,
      latency_ms: l.latency_ms,
    }));

    const sim = d3.forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimLink>(simLinks).id(d => d.id).distance(120).strength(0.3))
      .force('charge', d3.forceManyBody<SimNode>().strength(-300))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide<SimNode>().radius(40));

    const link = g.append('g').selectAll<SVGLineElement, SimLink>('line')
      .data(simLinks).join('line')
      .attr('stroke', '#3a4055').attr('stroke-width', 1.5).attr('stroke-opacity', 0.7);

    const linkLabel = g.append('g').selectAll<SVGTextElement, SimLink>('text')
      .data(simLinks).join('text')
      .attr('fill', '#6e7681').attr('font-size', 8)
      .attr('text-anchor', 'middle').attr('pointer-events', 'none')
      .text(d => d.latency_ms ? d.latency_ms + 'ms' : '');

    const node = g.append('g').selectAll<SVGGElement, SimNode>('g')
      .data(simNodes).join('g').style('cursor', 'pointer')
      .on('click', (_, d) => {
        const cn = nodes.find(n => n.id === d.id);
        if (cn) onNodeClick(cn);
      });

    node.append('circle')
      .attr('r', 28)
      .attr('fill', d => {
        const cn = nodes.find(n => n.id === d.id);
        return cn ? (ROLE_COLORS[cn.role] || '#6ad1ff') : '#6ad1ff';
      })
      .attr('stroke', d => selectedNodeId === d.id ? '#ffd866' : '#0f1115')
      .attr('stroke-width', d => selectedNodeId === d.id ? 3 : 1.5)
      .attr('opacity', 0.85);

    node.append('text')
      .attr('text-anchor', 'middle').attr('dy', '0.35em')
      .attr('fill', '#0d1117').attr('font-size', 11).attr('font-weight', 700)
      .attr('pointer-events', 'none')
      .text(d => d.id.toUpperCase());

    node.append('text')
      .attr('text-anchor', 'middle').attr('dy', 44)
      .attr('fill', '#8b949e').attr('font-size', 9).attr('pointer-events', 'none')
      .text(d => {
        const cn = nodes.find(n => n.id === d.id);
        return cn ? cn.shards.length + ' shards ' + cn.cpu + '% CPU' : '';
      });

    sim.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x ?? 0)
        .attr('y1', d => (d.source as SimNode).y ?? 0)
        .attr('x2', d => (d.target as SimNode).x ?? 0)
        .attr('y2', d => (d.target as SimNode).y ?? 0);
      linkLabel
        .attr('x', d => (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2)
        .attr('y', d => (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2);
      node.attr('transform', d => 'translate(' + (d.x ?? 0) + ',' + (d.y ?? 0) + ')');
    });
    return () => { sim.stop(); };
  }, [nodes, links, selectedNodeId, onNodeClick]);

  return (
    <svg ref={svgRef} style={{ width: '100%', height: 420, display: 'block' }} />
  );
}

function PartitionHeatmap({ nodes, totalPartitions }: {
  nodes: ClusterNode[];
  totalPartitions: number;
}) {
  const maxShards = Math.max(...nodes.map(n => n.shards.length), 1);
  const cellSize = 20;
  const gap = 2;

  return (
    <div style={{ overflowX: 'auto', padding: '8px 0' }}>
      <svg width={Math.max(nodes.length * (maxShards * (cellSize + gap) + 50), 400)} height={40 + nodes.length * 30}>
        {nodes.map((node, ni) => (
          <g key={node.id} transform={'translate(50, ' + (ni * 30 + 10) + ')'}>
            <text x={-4} y={12} textAnchor='end'
              style={{ fontSize: 9, fill: '#8b949e', fontFamily: 'monospace' }}>
              {node.id}
            </text>
            {Array.from({ length: maxShards }, (_, si) => {
              const shard = node.shards[si];
              const owned = shard !== undefined;
              return owned ? (
                <rect key={si}
                  x={si * (cellSize + gap)} y={0}
                  width={cellSize} height={cellSize}
                  rx={2}
                  fill={PARTITION_COLORS[(shard - 1) % PARTITION_COLORS.length]}
                  opacity={0.85}
                />
              ) : (
                <rect key={si}
                  x={si * (cellSize + gap)} y={0}
                  width={cellSize} height={cellSize}
                  rx={2} fill='#21262d'
                />
              );
            })}
          </g>
        ))}
        <g transform='translate(50, 0)'>
          {Array.from({ length: maxShards }, (_, si) => (
            <text key={si}
              x={si * (cellSize + gap) + cellSize / 2} y={-2}
              textAnchor='middle'
              style={{ fontSize: 7, fill: '#8b949e' }}>
              {si + 1}
            </text>
          ))}
        </g>
      </svg>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6, fontSize: 9, color: '#8b949e' }}>
        {PARTITION_COLORS.slice(0, Math.min(totalPartitions, 16)).map((c, i) => (
          <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: c, display: 'inline-block' }} />
            P{i + 1}
          </span>
        ))}
      </div>
    </div>
  );
}

function QueryPlanCard({ plan }: { plan: QueryPlanData['plan'] }) {
  const costColor = plan.network_hops === 0 ? '#6ad1ff'
    : plan.network_hops < 4 ? '#ffd866'
    : '#ff5d6c';
  return (
    <div style={{
      padding: 14, borderRadius: 6,
      background: '#0d1117', border: '1px solid #30363d',
      fontSize: 11, fontFamily: 'monospace',
    }}>
      <div style={{ color: '#8b949e', marginBottom: 8, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
        Query Plan
      </div>
      <div style={{ color: '#e6edf3', marginBottom: 6, lineHeight: 1.5 }}>{plan.strategy}</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '2px 12px', color: '#8b949e' }}>
        <span>Partitions touched</span>
        <span style={{ color: costColor, textAlign: 'right' }}>{plan.partitions_touched}/{plan.total_partitions}</span>
        <span>Network hops</span>
        <span style={{ color: costColor, textAlign: 'right' }}>{plan.network_hops}</span>
        <span>Cross-partition cost</span>
        <span style={{ color: costColor, textAlign: 'right' }}>{plan.cross_partition_cost_ms} ms</span>
        <span>Estimated latency</span>
        <span style={{ color: costColor, textAlign: 'right' }}>{plan.estimated_latency_ms} ms</span>
        <span>Nodes visited</span>
        <span style={{ textAlign: 'right' }}>{plan.nodes_visited}</span>
        <span>Edges traversed</span>
        <span style={{ textAlign: 'right' }}>{plan.edges_traversed}</span>
      </div>
      <div style={{ marginTop: 8, fontSize: 9, color: '#6e7681' }}>
        Partitions: [{plan.partition_ids.join(', ')}]
      </div>
    </div>
  );
}

function ScaleControls({ onScale }: { onScale: (nodes: number, strategy: string, rebalance: boolean) => void }) {
  const [nodes, setNodes] = useState(4);
  const [strategy, setStrategy] = useState('hash');
  const [rebalance, setRebalance] = useState(true);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div>
        <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 4 }}>
          Target cluster size: <strong style={{ color: '#e6edf3' }}>{nodes} nodes</strong>
        </div>
        <input type='range' min={2} max={16} value={nodes}
          onChange={e => setNodes(Number(e.target.value))}
          style={{ width: '100%' }} />
      </div>
      <div style={{ display: 'flex', gap: 6 }}>
        {(['hash', 'range', 'consistent_hash'] as const).map(s => (
          <button key={s} onClick={() => setStrategy(s)}
            style={{
              flex: 1, padding: '4px 6px', fontSize: 10, borderRadius: 4,
              background: strategy === s ? STRATEGY_COLORS[s] : 'transparent',
              border: '1px solid ' + STRATEGY_COLORS[s],
              color: strategy === s ? '#0d1117' : STRATEGY_COLORS[s],
              cursor: 'pointer', fontWeight: strategy === s ? 600 : 400,
            }}>
            {s === 'consistent_hash' ? 'CH' : s}
          </button>
        ))}
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, cursor: 'pointer' }}>
        <input type='checkbox' checked={rebalance} onChange={e => setRebalance(e.target.checked)} />
        <span style={{ color: '#8b949e' }}>Trigger rebalance</span>
      </label>
      <button onClick={() => onScale(nodes, strategy, rebalance)}
        style={{
          padding: '6px 12px', fontSize: 12, borderRadius: 4,
          background: '#2d9cdb', border: 'none',
          color: '#fff', fontWeight: 600, cursor: 'pointer',
        }}>
        Apply Scale
      </button>
    </div>
  );
}

export function DistributedGraphView() {
  const [cluster, setCluster] = useState<ClusterData | null>(null);
  const [scaled, setScaled] = useState<ScaleResult | null>(null);
  const [queryPlan, setQueryPlan] = useState<QueryPlanData | null>(null);
  const [loading, setLoading] = useState(false);
  const [queryType, setQueryType] = useState('single_partition');
  const [selectedNode, setSelectedNode] = useState<ClusterNode | null>(null);
  const [activeTab, setActiveTab] = useState<'topology' | 'scale' | 'query'>('topology');

  const fetchCluster = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch('/api/distributed/cluster');
      if (!r.ok) return;
      setCluster(await r.json());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  const fetchQueryPlan = useCallback(async () => {
    try {
      const r = await fetch('/api/distributed/query_plan?query_type=' + queryType + '&hops=2');
      if (!r.ok) return;
      setQueryPlan(await r.json());
    } catch { /* ignore */ }
  }, [queryType]);

  useEffect(() => { fetchCluster(); }, [fetchCluster]);
  useEffect(() => { fetchQueryPlan(); }, [fetchQueryPlan]);

  const handleScale = useCallback(async (targetNodes: number, strategy: string, rebalance: boolean) => {
    setLoading(true);
    try {
      const u = '/api/distributed/scale?target_nodes=' + targetNodes + '&strategy=' + strategy + '&rebalance=' + rebalance;
      const r = await fetch(u, { method: 'POST' });
      if (!r.ok) return;
      const data: ScaleResult = await r.json();
      setScaled(data);
      setCluster({
        ok: true, source: 'scaled', nodes: data.nodes,
        replication_factor: data.replication_factor,
        total_partitions: data.total_partitions,
        partition_map: data.partition_map,
        topology: data.topology,
      });
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  const displayNodes = cluster?.nodes ?? [];
  const displayLinks = cluster?.topology ?? [];
  const totalPartitions = cluster?.total_partitions ?? 8;

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      <div style={{
        width: 260, minWidth: 260,
        background: '#161b22',
        borderRight: '1px solid #30363d',
        overflowY: 'auto',
      }}>
        <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid #30363d' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#e6edf3', marginBottom: 4 }}>
            Distributed Graph
          </div>
          <div style={{ fontSize: 11, color: '#8b949e', lineHeight: 1.5 }}>
            Cluster topology &middot; Partition awareness &middot; Query routing
          </div>
        </div>

        <div style={{ display: 'flex', borderBottom: '1px solid #30363d' }}>
          {(['topology', 'scale', 'query'] as const).map(id => {
            const labels: Record<string, string> = { topology: 'Topology', scale: 'Scale', query: 'Query' };
            return (
              <button key={id} onClick={() => setActiveTab(id)}
                style={{
                  flex: 1, padding: '8px 4px', fontSize: 10,
                  background: 'transparent', border: 'none',
                  borderBottom: activeTab === id ? '2px solid #2d9cdb' : '2px solid transparent',
                  color: activeTab === id ? '#2d9cdb' : '#8b949e',
                  cursor: 'pointer', fontWeight: activeTab === id ? 600 : 400,
                }}>
                {labels[id]}
              </button>
            );
          })}
        </div>

        <div style={{ padding: '12px 14px' }}>
          {activeTab === 'topology' && (
            <>
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Cluster Stats
                </div>
                {cluster && (
                  <div style={{ fontSize: 11, fontFamily: 'monospace', color: '#8b949e' }}>
                    <div>Nodes: <strong style={{ color: '#e6edf3' }}>{cluster.nodes.length}</strong></div>
                    <div>Partitions: <strong style={{ color: '#e6edf3' }}>{cluster.total_partitions}</strong></div>
                    <div>Replication: <strong style={{ color: '#e6edf3' }}>RF={cluster.replication_factor}</strong></div>
                    <div>Source: <span style={{ color: cluster.source === 'tigergraph' ? '#7ed321' : '#ffd866' }}>{cluster.source}</span></div>
                  </div>
                )}
              </div>
              <button onClick={fetchCluster} disabled={loading}
                style={{ width: '100%', padding: '5px 8px', fontSize: 11, borderRadius: 4, background: '#2d9cdb', border: 'none', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>
                {loading ? 'Loading...' : 'Refresh Cluster'}
              </button>
            </>
          )}

          {activeTab === 'scale' && (
            <>
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Scale Simulation
                </div>
                <ScaleControls onScale={handleScale} />
              </div>
              {scaled && (
                <div style={{ marginTop: 8, padding: '8px 10px', borderRadius: 4, background: '#0d1117', border: '1px solid #30363d', fontSize: 10, fontFamily: 'monospace' }}>
                  <div style={{ color: '#8b949e', marginBottom: 4 }}>Result</div>
                  <div>Strategy: <strong style={{ color: STRATEGY_COLORS[scaled.strategy] || '#6ad1ff' }}>{scaled.strategy}</strong></div>
                  <div>New nodes: <strong style={{ color: '#e6edf3' }}>{scaled.total_nodes}</strong></div>
                  <div>Partitions: <strong style={{ color: '#e6edf3' }}>{scaled.total_partitions}</strong></div>
                  <div>Rebalance: <strong style={{ color: scaled.rebalance_triggered ? '#ff5d6c' : '#6ad1ff' }}>
                    {scaled.rebalance_triggered ? scaled.rebalance_estimate_gb + ' GB' : 'skipped'}
                  </strong></div>
                </div>
              )}
            </>
          )}

          {activeTab === 'query' && (
            <>
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Query Type
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {([
                    ['single_partition', 'Single-partition', '#6ad1ff'],
                    ['cross_partition', 'Cross-partition', '#ffd866'],
                    ['full_scan', 'Full scan', '#ff5d6c'],
                  ] as const).map(([val, label, color]) => (
                    <button key={val} onClick={() => setQueryType(val)}
                      style={{
                        padding: '5px 8px', fontSize: 10, borderRadius: 4,
                        background: queryType === val ? color : 'transparent',
                        border: '1px solid ' + color,
                        color: queryType === val ? '#0d1117' : color,
                        cursor: 'pointer', fontWeight: queryType === val ? 600 : 400,
                        textAlign: 'left',
                      }}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              {queryPlan && <QueryPlanCard plan={queryPlan.plan} />}
            </>
          )}
        </div>

        {selectedNode && (
          <div style={{ padding: '12px 14px', borderTop: '1px solid #30363d' }}>
            <div style={{ fontSize: 10, color: '#8b949e', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Node {selectedNode.id}
            </div>
            <div style={{ fontSize: 10, fontFamily: 'monospace', color: '#8b949e', lineHeight: 1.8 }}>
              <div>Role: <strong style={{ color: ROLE_COLORS[selectedNode.role] }}>{selectedNode.role}</strong></div>
              <div>Host: <strong style={{ color: '#e6edf3' }}>{selectedNode.host}</strong></div>
              <div>Port: {selectedNode.port}</div>
              <div>CPU: <strong style={{ color: selectedNode.cpu > 85 ? '#ff5d6c' : '#e6edf3' }}>{selectedNode.cpu}%</strong></div>
              <div>Memory: {(selectedNode.memory_mb / 1024).toFixed(0)} GB</div>
              <div>Shards: {selectedNode.shards.join(', ') || 'none'}</div>
            </div>
          </div>
        )}
      </div>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: '#0d1117' }}>
        {loading && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10, background: 'rgba(13,17,23,0.8)' }}>
            <span style={{ color: '#8b949e', fontSize: 13 }}>Loading cluster data...</span>
          </div>
        )}
        {!loading && displayNodes.length === 0 && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <span style={{ color: '#8b949e', fontSize: 13 }}>No cluster data</span>
          </div>
        )}

        {displayNodes.length > 0 && (
          <>
            <ClusterGraph
              nodes={displayNodes}
              links={displayLinks}
              onNodeClick={setSelectedNode}
              selectedNodeId={selectedNode?.id ?? null}
            />

            <div style={{
              position: 'absolute', top: 12, left: 12,
              background: 'rgba(13,17,23,0.88)',
              border: '1px solid #30363d',
              borderRadius: 6, padding: '8px 12px', fontSize: 11,
            }}>
              <div style={{ color: '#8b949e', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Cluster topology
              </div>
              <div style={{ color: '#8b949e', lineHeight: 1.5 }}>
                {displayNodes.length} nodes &middot; {totalPartitions} partitions &middot; RF={cluster?.replication_factor}
              </div>
            </div>

            <div style={{
              position: 'absolute', bottom: 12, left: 12, right: 12,
              background: 'rgba(13,17,23,0.88)',
              border: '1px solid #30363d',
              borderRadius: 6, padding: '8px 12px',
            }}>
              <div style={{ color: '#8b949e', marginBottom: 6, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Partition heatmap
              </div>
              <PartitionHeatmap nodes={displayNodes} totalPartitions={totalPartitions} />
            </div>

            <div style={{
              position: 'absolute', top: 12, right: 12,
              background: 'rgba(13,17,23,0.88)',
              border: '1px solid #30363d',
              borderRadius: 6, padding: '8px 12px', fontSize: 10,
            }}>
              <div style={{ color: '#8b949e', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Legend
              </div>
              {(['primary', 'replica'] as const).map(role => (
                <div key={role} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', background: ROLE_COLORS[role], display: 'inline-block', flexShrink: 0 }} />
                  <span style={{ color: '#8b949e' }}>{role.charAt(0).toUpperCase() + role.slice(1)}</span>
                </div>
              ))}
              <div style={{ marginTop: 4, color: '#6e7681' }}>
                Scroll to zoom &middot; Click node to inspect
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
