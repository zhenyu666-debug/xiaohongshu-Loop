import { VERTEX_TYPES, EDGE_TYPES } from '../data/schema';

export function MapData() {
  const isLoaded = true;

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
        <span style={{ fontWeight: 600, fontSize: 14 }}>Map Data To Graph</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-muted)' }}>·</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-secondary)' }}>Entity Resolution MDM</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {isLoaded ? (
            <span className="badge badge-green">
              <span className="status-dot status-dot-green" style={{ marginRight: 6 }} />
              All mappings configured
            </span>
          ) : (
            <span className="badge badge-orange">Not started</span>
          )}
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
        <div style={{ maxWidth: 900 }}>
          <h3 style={{ marginBottom: 6, color: 'var(--tg-text-primary)' }}>Data Sources</h3>
          <p style={{ fontSize: 12, color: 'var(--tg-text-secondary)', marginBottom: 16 }}>
            Configure how your source data maps to the FraudRisk graph schema.
          </p>

          {/* Data source table */}
          <div className="panel" style={{ marginBottom: 20 }}>
            <div className="panel-header">Data Sources</div>
            <table>
              <thead>
                <tr>
                  <th>Data Source</th>
                  <th>Type</th>
                  <th>Format</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { name: 'account_data.csv', type: 'Account', format: 'CSV', status: 'ready' },
                  { name: 'ip_data.csv', type: 'IP', format: 'CSV', status: 'ready' },
                  { name: 'email_data.csv', type: 'Email', format: 'CSV', status: 'ready' },
                  { name: 'device_data.csv', type: 'Device', format: 'CSV', status: 'ready' },
                  { name: 'video_data.csv', type: 'Video', format: 'CSV', status: 'ready' },
                ].map((ds, i) => (
                  <tr key={i}>
                    <td>
                      <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{ds.name}</span>
                    </td>
                    <td><span className="badge badge-blue">{ds.type}</span></td>
                    <td><span className="badge">{ds.format}</span></td>
                    <td>
                      <span className="badge badge-green">
                        <span className="status-dot status-dot-green" style={{ marginRight: 5 }} />Configured
                      </span>
                    </td>
                    <td>
                      <button className="btn btn-secondary btn-xs">Edit</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Vertex mappings */}
          <h3 style={{ marginBottom: 6 }}>Vertex Mappings</h3>
          <p style={{ fontSize: 12, color: 'var(--tg-text-secondary)', marginBottom: 16 }}>
            Each vertex type maps to a data source and primary key.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))', gap: 12 }}>
            {VERTEX_TYPES.map(v => (
              <div key={v.name} className="panel">
                <div className="panel-header">
                  <span style={{
                    width: 10, height: 10, borderRadius: '50%',
                    background: {
                      Account: '#2d9cdb', IP: '#27ae60', Email: '#f2994a',
                      LastName: '#bb6bd9', Phone: '#eb5757', Address: '#f2c94c',
                      Device: '#6fcfea', VideoPlay: '#95d5b2', Video: '#d4a373',
                      MergedAccount: '#ff9f1c',
                    }[v.name] || '#6e7681',
                    display: 'inline-block',
                  }} />
                  {v.name}
                </div>
                <div className="panel-body" style={{ padding: 10 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: '4px 8px', fontSize: 12 }}>
                    <span style={{ color: 'var(--tg-text-muted)' }}>Source:</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--tg-text-primary)' }}>
                      {v.name.toLowerCase()}_data.csv
                    </span>
                    <span style={{ color: 'var(--tg-text-muted)' }}>Primary ID:</span>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', color: 'var(--tg-blue-light)' }}>
                      {v.attributes[0]?.name || 'id'}
                    </span>
                    <span style={{ color: 'var(--tg-text-muted)' }}>Attributes:</span>
                    <span style={{ color: 'var(--tg-text-secondary)', fontSize: 11 }}>
                      {v.attributes.slice(1, 3).map(a => a.name).join(', ')}
                      {v.attributes.length > 3 && ` +${v.attributes.length - 3} more`}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
