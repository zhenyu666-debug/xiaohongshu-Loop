import { useState } from 'react';
import { LOAD_STATS } from '../data/mockData';

export function LoadData() {
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [progress, setProgress] = useState(0);
  const [activeTab, setActiveTab] = useState<'run' | 'details'>('run');

  const handleLoad = () => {
    setLoading(true);
    setProgress(0);
    const interval = setInterval(() => {
      setProgress(p => {
        if (p >= 100) {
          clearInterval(interval);
          setLoading(false);
          setLoaded(true);
          return 100;
        }
        return p + Math.floor(Math.random() * 8) + 3;
      });
    }, 300);
  };

  const totalAdded = Object.values(LOAD_STATS).reduce((s, v) => s + v.added, 0);
  const totalLoaded = Object.values(LOAD_STATS).reduce((s, v) => s + v.loaded, 0);
  const totalFailed = Object.values(LOAD_STATS).reduce((s, v) => s + v.failed, 0);

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
        <span style={{ fontWeight: 600, fontSize: 14 }}>Load Data</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-muted)' }}>·</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-secondary)' }}>Entity Resolution MDM</span>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {loading ? (
            <span className="badge badge-blue">
              <span className="spinner" style={{ width: 10, height: 10, borderWidth: 1.5, marginRight: 5 }} />
              Loading...
            </span>
          ) : loaded ? (
            <span className="badge badge-green">
              <span className="status-dot status-dot-green" style={{ marginRight: 6 }} />
              All data loaded
            </span>
          ) : (
            <span className="badge">Not loaded</span>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 0,
        borderBottom: '1px solid var(--tg-dark-border)',
        padding: '0 20px',
        background: 'var(--tg-dark-card)',
      }}>
        {(['run', 'details'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 16px',
              background: 'none',
              border: 'none',
              borderBottom: activeTab === tab ? '2px solid var(--tg-blue)' : '2px solid transparent',
              color: activeTab === tab ? 'var(--tg-blue-light)' : 'var(--tg-text-secondary)',
              fontSize: 12,
              fontWeight: activeTab === tab ? 600 : 400,
              fontFamily: 'inherit',
              cursor: 'pointer',
              textTransform: 'capitalize',
            }}
          >
            {tab === 'run' ? 'Run Load' : 'Load Details'}
          </button>
        ))}
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
        {activeTab === 'run' ? (
          <div style={{ maxWidth: 700 }}>
            {/* Stats cards */}
            <div className="stats-grid" style={{ marginBottom: 24 }}>
              <div className="stat-card">
                <div className="stat-card-value">{totalAdded}</div>
                <div className="stat-card-label">Total Added</div>
              </div>
              <div className="stat-card stat-card-success">
                <div className="stat-card-value">{totalLoaded}</div>
                <div className="stat-card-label">Loaded</div>
              </div>
              <div className="stat-card stat-card-error">
                <div className="stat-card-value">{totalFailed}</div>
                <div className="stat-card-label">Failed</div>
              </div>
              <div className="stat-card">
                <div className="stat-card-value">{Object.keys(LOAD_STATS).length}</div>
                <div className="stat-card-label">Vertex Types</div>
              </div>
            </div>

            {/* Run button */}
            {!loaded && (
              <button
                className="btn btn-primary"
                onClick={handleLoad}
                disabled={loading}
                style={{ marginBottom: 24, fontSize: 14, padding: '10px 24px' }}
              >
                {loading ? (
                  <>
                    <span className="spinner" />
                    Loading...
                  </>
                ) : (
                  '▶ Start Loading'
                )}
              </button>
            )}

            {loaded && (
              <button
                className="btn btn-secondary"
                onClick={() => { setLoaded(false); setProgress(0); }}
                style={{ marginBottom: 24 }}
              >
                ↺ Reload Data
              </button>
            )}

            {/* Progress bar */}
            {(loading || loaded) && (
              <div style={{ marginBottom: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--tg-text-muted)', marginBottom: 6 }}>
                  <span>Progress</span>
                  <span>{Math.min(progress, 100)}%</span>
                </div>
                <div className="progress-bar">
                  <div
                    className={`progress-bar-fill ${loaded ? 'success' : ''}`}
                    style={{ width: `${Math.min(progress, 100)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Per-type progress */}
            <div className="panel">
              <div className="panel-header">Vertex Type Loading Status</div>
              <table>
                <thead>
                  <tr>
                    <th>Vertex Type</th>
                    <th>Added</th>
                    <th>Loaded</th>
                    <th>Failed</th>
                    <th>Status</th>
                    <th>Progress</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(LOAD_STATS).map(([vtype, stats]) => (
                    <tr key={vtype}>
                      <td>
                        <span style={{
                          display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                          background: {
                            Account: '#2d9cdb', IP: '#27ae60', Email: '#f2994a',
                            LastName: '#bb6bd9', Phone: '#eb5757', Address: '#f2c94c',
                            Device: '#6fcfea', VideoPlay: '#95d5b2', Video: '#d4a373',
                            MergedAccount: '#ff9f1c',
                          }[vtype] || '#6e7681',
                          marginRight: 8,
                        }} />
                        <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{vtype}</span>
                      </td>
                      <td>{stats.added}</td>
                      <td>{stats.loaded}</td>
                      <td>{stats.failed}</td>
                      <td>
                        <span className={`badge ${stats.failed > 0 ? 'badge-green' : 'badge-green'}`}>
                          <span className={`status-dot status-dot-${stats.failed > 0 ? 'yellow' : 'green'}`} style={{ marginRight: 5 }} />
                          {stats.failed > 0 ? 'Partial' : 'Complete'}
                        </span>
                      </td>
                      <td style={{ width: 120 }}>
                        <div className="progress-bar" style={{ marginTop: 4 }}>
                          <div
                            className={`progress-bar-fill ${stats.failed > 0 ? '' : 'success'}`}
                            style={{ width: `${stats.loaded / stats.added * 100}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div style={{ maxWidth: 900 }}>
            <h3 style={{ marginBottom: 16 }}>Load Details</h3>
            <div className="panel">
              <div className="panel-header">Load History</div>
              <table>
                <thead>
                  <tr>
                    <th>Job ID</th>
                    <th>Started</th>
                    <th>Duration</th>
                    <th>Vertices</th>
                    <th>Edges</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    { id: 'JOB-2024-001', start: '2024-10-19 10:23:15', dur: '12s', verts: '10,234', edges: '45,892', status: 'success' },
                    { id: 'JOB-2024-002', start: '2024-10-19 11:05:42', dur: '8s', verts: '10,234', edges: '45,892', status: 'success' },
                    { id: 'JOB-2024-003', start: '2024-10-19 14:30:01', dur: '15s', verts: '10,234', edges: '45,892', status: 'success' },
                  ].map((job, i) => (
                    <tr key={i}>
                      <td><span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{job.id}</span></td>
                      <td>{job.start}</td>
                      <td>{job.dur}</td>
                      <td>{job.verts}</td>
                      <td>{job.edges}</td>
                      <td><span className="badge badge-green">Success</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
