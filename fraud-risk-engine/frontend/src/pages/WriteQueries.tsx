import { useState } from 'react';
import { GSQL_QUERIES } from '../data/queries';

export function WriteQueries() {
  const [selectedQuery, setSelectedQuery] = useState(0);
  const [code, setCode] = useState(GSQL_QUERIES[0].code);
  const [installed, setInstalled] = useState<Record<string, boolean>>({});
  const [running, setRunning] = useState(false);
  const [output, setOutput] = useState<string | null>(null);
  const [installing, setInstalling] = useState(false);
  const [installOutput, setInstallOutput] = useState<string | null>(null);

  const query = GSQL_QUERIES[selectedQuery];

  const handleInstall = () => {
    setInstalling(true);
    setInstallOutput(null);
    setTimeout(() => {
      setInstalling(false);
      setInstalled(prev => ({ ...prev, [query.id]: true }));
      setInstallOutput(`[INFO] Query "${query.name}" installed successfully.\n[INFO] Compiling GSQL to C++... done.\n[INFO] Query ready at endpoint: /query/FraudRisk/${query.name}`);
    }, 1800);
  };

  const handleRun = () => {
    setRunning(true);
    setOutput(null);
    setTimeout(() => {
      setRunning(false);
      if (query.id === 'apAccountMatching') {
        setOutput(JSON.stringify({
          results: [
            { "@@accountCount": 6, "@@edgesInserted": 3, "message": "Entity resolution complete" },
          ],
        }, null, 2));
      } else if (query.id === 'tgWCC') {
        setOutput(JSON.stringify({
          results: [{
            components: {
              "A001": { "comp_id": "69206017" },
              "A002": { "comp_id": "69206017" },
              "A006": { "comp_id": "69206017" },
              "A003": { "comp_id": "83405123" },
              "A004": { "comp_id": "83405123" },
              "A005": { "comp_id": "10023456" },
            },
            vertexCount: 6,
          }],
        }, null, 2));
      } else {
        setOutput(JSON.stringify({ results: [{ "message": `Query ${query.name} executed successfully` }] }, null, 2));
      }
    }, 1200);
  };

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
        <span style={{ fontWeight: 600, fontSize: 14 }}>Write Queries</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-muted)' }}>·</span>
        <span style={{ fontSize: 12, color: 'var(--tg-text-secondary)' }}>GSQL Editor</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm">+ New Query</button>
        </div>
      </div>

      {/* Body: split layout */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Left: query list */}
        <div style={{
          width: 220, minWidth: 220,
          borderRight: '1px solid var(--tg-dark-border)',
          overflowY: 'auto',
          background: 'var(--tg-dark-card)',
        }}>
          <div style={{ padding: '8px 0' }}>
            <div style={{ padding: '4px 14px 8px', fontSize: 11, color: 'var(--tg-text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Installed Queries
            </div>
            {GSQL_QUERIES.map((q, i) => (
              <button
                key={q.id}
                onClick={() => { setSelectedQuery(i); setCode(q.code); setOutput(null); }}
                style={{
                  width: '100%',
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 14px',
                  background: selectedQuery === i ? 'rgba(45,156,219,0.12)' : 'transparent',
                  borderLeft: selectedQuery === i ? '3px solid var(--tg-blue)' : '3px solid transparent',
                  color: selectedQuery === i ? 'var(--tg-blue-light)' : 'var(--tg-text-secondary)',
                  fontFamily: 'inherit',
                  fontSize: 12,
                  fontWeight: selectedQuery === i ? 600 : 400,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span style={{ fontSize: 14 }}>{installed[q.id] ? '✓' : '○'}</span>
                <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 11 }}>{q.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Center + right: editor + output */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Toolbar */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 14px',
            borderBottom: '1px solid var(--tg-dark-border)',
            background: 'var(--tg-dark-card)',
          }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleInstall}
              disabled={installing || installed[query.id]}
            >
              {installing ? (
                <><span className="spinner" />Installing...</>
              ) : installed[query.id] ? (
                <>✓ Installed</>
              ) : (
                <>↑ Install Query</>
              )}
            </button>
            <button
              className="btn btn-success btn-sm"
              onClick={handleRun}
              disabled={running || !installed[query.id]}
            >
              {running ? (
                <><span className="spinner" />Running...</>
              ) : (
                <>▶ Run Query</>
              )}
            </button>

            {/* Params */}
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: 'var(--tg-text-muted)' }}>threshold:</span>
              <input
                type="number"
                defaultValue={0.6}
                min={0}
                max={1}
                step={0.1}
                style={{ width: 70, padding: '3px 8px', fontSize: 12 }}
              />
              <span style={{ fontSize: 11, color: 'var(--tg-text-muted)' }}>max_iter:</span>
              <input
                type="number"
                defaultValue={10}
                style={{ width: 60, padding: '3px 8px', fontSize: 12 }}
              />
            </div>
          </div>

          {/* Install output */}
          {installOutput && (
            <div style={{
              padding: '8px 14px',
              background: 'rgba(39,174,96,0.08)',
              borderBottom: '1px solid rgba(39,174,96,0.2)',
              fontSize: 11,
              color: 'var(--tg-green)',
              fontFamily: 'JetBrains Mono, monospace',
              whiteSpace: 'pre',
            }}>
              {installOutput}
            </div>
          )}

          {/* Code editor */}
          <div style={{ flex: 1, overflow: 'hidden', padding: 14 }}>
            <div style={{ fontSize: 12, color: 'var(--tg-text-secondary)', marginBottom: 8, fontFamily: 'JetBrains Mono, monospace' }}>
              CREATE QUERY <span style={{ color: 'var(--tg-blue-light)', fontWeight: 700 }}>{query.name}</span>
            </div>
            <textarea
              value={code}
              onChange={e => setCode(e.target.value)}
              style={{
                width: '100%', height: 'calc(100% - 30px)',
                background: 'var(--code-bg)',
                border: '1px solid var(--code-border)',
                borderRadius: 6,
                fontFamily: 'JetBrains Mono, monospace',
                fontSize: 12,
                color: '#79c0ff',
                padding: 14,
                resize: 'none',
                outline: 'none',
                lineHeight: 1.6,
                tabSize: 2,
              }}
              spellCheck={false}
            />
          </div>

          {/* Output */}
          {output && (
            <div style={{
              borderTop: '1px solid var(--tg-dark-border)',
              padding: 14,
              maxHeight: 220,
              overflowY: 'auto',
            }}>
              <div style={{ fontSize: 11, color: 'var(--tg-text-muted)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span className="status-dot status-dot-green" />
                Query Output
                <span style={{ marginLeft: 'auto', fontFamily: 'JetBrains Mono, monospace', color: 'var(--tg-green)' }}>
                  {query.name} completed in ~200ms
                </span>
              </div>
              <pre className="json-output">{output}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
