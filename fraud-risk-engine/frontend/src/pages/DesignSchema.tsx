import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { VERTEX_TYPES, EDGE_TYPES, FEATURE_EDGE_NAMES } from '../data/schema';

export function DesignSchema() {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth || 900;
    const height = svgRef.current.clientHeight || 520;

    // Layout: center Account, feature vertices around it
    const centerX = width / 2;
    const centerY = height / 2;
    const featureRadius = 160;

    const nodes = VERTEX_TYPES.map((v, i) => {
      if (v.name === 'Account') {
        return { ...v, x: centerX, y: centerY };
      }
      // Place feature vertices in a circle
      const angle = ((i - 1) / (VERTEX_TYPES.length - 1)) * 2 * Math.PI - Math.PI / 2;
      return { ...v, x: centerX + featureRadius * Math.cos(angle), y: centerY + featureRadius * Math.sin(angle) };
    });

    const nodeMap = new Map(nodes.map(n => [n.name, n]));

    const links = EDGE_TYPES
      .filter(e => e.from === 'Account' || e.to === 'Account')
      .map(e => ({
        source: nodeMap.get(e.from)!,
        target: nodeMap.get(e.to)!,
        edge: e,
      }))
      .filter(l => l.source && l.target);

    // Arrow marker
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 28)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#30363d');

    const g = svg.append('g');

    // Draw edges
    g.selectAll('line')
      .data(links)
      .enter()
      .append('line')
      .attr('x1', d => (d.source as any).x)
      .attr('y1', d => (d.source as any).y)
      .attr('x2', d => (d.target as any).x)
      .attr('y2', d => (d.target as any).y)
      .attr('stroke', '#30363d')
      .attr('stroke-width', d => FEATURE_EDGE_NAMES.includes(d.edge.name) ? 1.5 : 1)
      .attr('stroke-dasharray', d => d.edge.directed ? 'none' : '4,3')
      .attr('marker-end', d => d.edge.directed ? 'url(#arrowhead)' : null);

    // Draw edge labels
    g.selectAll('text')
      .data(links)
      .enter()
      .append('text')
      .text(d => d.edge.name)
      .attr('x', d => ((d.source as any).x + (d.target as any).x) / 2)
      .attr('y', d => ((d.source as any).y + (d.target as any).y) / 2 - 5)
      .attr('text-anchor', 'middle')
      .attr('font-size', 9)
      .attr('fill', '#6e7681')
      .attr('font-family', 'JetBrains Mono, monospace');

    // Draw nodes
    const nodeGs = g.selectAll('g.node')
      .data(nodes)
      .enter()
      .append('g')
      .attr('transform', d => `translate(${d.x},${d.y})`)
      .attr('class', 'graph-node');

    const isCenter = (d: any) => d.name === 'Account';
    const isMerged = (d: any) => d.name === 'MergedAccount';
    const isFeature = (d: any) => FEATURE_EDGE_NAMES.some(f => {
      const e = EDGE_TYPES.find(e => e.name === f);
      return e && (e.from === d.name || e.to === d.name);
    }) && d.name !== 'Account' && d.name !== 'MergedAccount';

    nodeGs.append('circle')
      .attr('r', d => isCenter(d) ? 42 : isMerged(d) ? 32 : 28)
      .attr('fill', d => {
        const colors: Record<string, string> = {
          Account: '#2d9cdb', IP: '#27ae60', Email: '#f2994a',
          LastName: '#bb6bd9', Phone: '#eb5757', Address: '#f2c94c',
          Device: '#6fcfea', VideoPlay: '#95d5b2', Video: '#d4a373',
          MergedAccount: '#ff9f1c',
        };
        return colors[d.name] || '#6e7681';
      })
      .attr('fill-opacity', d => isCenter(d) ? 1 : 0.85)
      .attr('stroke', d => isCenter(d) ? '#1a6fa3' : '#ffffff22')
      .attr('stroke-width', d => isCenter(d) ? 2 : 1);

    nodeGs.append('text')
      .text(d => d.name)
      .attr('text-anchor', 'middle')
      .attr('dy', isCenter ? '-2px' : '3px')
      .attr('font-size', d => isCenter(d) ? 11 : 10)
      .attr('font-weight', d => isCenter(d) ? 700 : 500)
      .attr('fill', 'white')
      .attr('font-family', 'Inter, sans-serif');

    nodeGs.append('text')
      .text(d => d.attributes.slice(0, 3).map(a => a.name).join(', '))
      .attr('text-anchor', 'middle')
      .attr('dy', d => isCenter(d) ? '12px' : '14px')
      .attr('font-size', 8)
      .attr('fill', 'rgba(255,255,255,0.6)')
      .attr('font-family', 'JetBrains Mono, monospace');

    // D3 zoom
    svg.call(d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', e => g.attr('transform', e.transform.toString()))
    );
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div style={{
        height: 'var(--header-height)',
        borderBottom: '1px solid var(--tg-dark-border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: 12,
        background: 'var(--tg-dark-bg)',
      }}>
        <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--tg-text-primary)' }}>Design Schema</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-muted)' }}>·</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-secondary)' }}>Entity Resolution MDM</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm">↺ Revert</button>
          <button className="btn btn-secondary btn-sm">↻ Refresh</button>
          <button className="btn btn-primary btn-sm">✓ Publish Changes</button>
        </span>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Schema list (left panel) */}
        <div style={{
          width: 280,
          minWidth: 280,
          borderRight: '1px solid var(--tg-dark-border)',
          overflowY: 'auto',
          padding: '12px 0',
        }}>
          {VERTEX_TYPES.map(v => (
            <div key={v.name} style={{ padding: '8px 16px' }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 6,
                fontWeight: 600,
                fontSize: 12,
                color: v.name === 'Account' ? 'var(--tg-blue-light)' : 'var(--tg-text-primary)',
              }}>
                <span style={{
                  width: 12, height: 12, borderRadius: '50%',
                  background: {
                    Account: '#2d9cdb', IP: '#27ae60', Email: '#f2994a',
                    LastName: '#bb6bd9', Phone: '#eb5757', Address: '#f2c94c',
                    Device: '#6fcfea', VideoPlay: '#95d5b2', Video: '#d4a373',
                    MergedAccount: '#ff9f1c',
                  }[v.name] || '#6e7681',
                  display: 'inline-block',
                  flexShrink: 0,
                }} />
                {v.name}
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--tg-text-muted)', fontWeight: 400 }}>
                  {v.attributes.length} attrs
                </span>
              </div>
              {v.attributes.slice(0, 6).map(attr => (
                <div key={attr.name} style={{
                  fontSize: 11,
                  color: 'var(--tg-text-muted)',
                  padding: '1px 0 1px 20px',
                  fontFamily: 'JetBrains Mono, monospace',
                }}>
                  {attr.name} <span style={{ color: 'var(--tg-text-muted)', opacity: 0.5 }}>{attr.type}</span>
                </div>
              ))}
              {v.attributes.length > 6 && (
                <div style={{ fontSize: 10, color: 'var(--tg-text-muted)', paddingLeft: 20 }}>
                  +{v.attributes.length - 6} more...
                </div>
              )}
              <div style={{ height: 1, background: 'var(--tg-dark-border)', margin: '8px 0 0' }} />
            </div>
          ))}
        </div>

        {/* SVG canvas (right) */}
        <div style={{ flex: 1, overflow: 'hidden', background: 'var(--tg-dark-bg)', position: 'relative' }}>
          <svg ref={svgRef} style={{ width: '100%', height: '100%' }} />
          <div style={{
            position: 'absolute', bottom: 12, right: 12,
            fontSize: 11, color: 'var(--tg-text-muted)',
            background: 'rgba(13,17,23,0.8)', padding: '4px 10px',
            borderRadius: 4, border: '1px solid var(--tg-dark-border)',
          }}>
            Scroll to zoom · Drag to pan
          </div>
        </div>
      </div>
    </div>
  );
}
