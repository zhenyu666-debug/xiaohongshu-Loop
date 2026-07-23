import { useState } from 'react';
import './index.css';
import { DesignSchema } from './pages/DesignSchema';
import { MapData } from './pages/MapData';
import { LoadData } from './pages/LoadData';
import { WriteQueries } from './pages/WriteQueries';
import { ExploreGraph } from './pages/ExploreGraph';
import { PaySimView } from './pages/PaySimView';
import { MedGraphView } from './pages/MedGraphView';
import { RobustnessView } from './pages/RobustnessView';
import { FundsMonitorPanel } from './pages/FundsMonitorPanel';
import { DistributedGraphView } from './pages/DistributedGraphView';

type Page = 'design' | 'map' | 'load' | 'queries' | 'explore' | 'paysim' | 'medgraph' | 'robustness' | 'funds' | 'distributed';

const NAV_ITEMS: { id: Page; label: string; icon: string }[] = [
  { id: 'design', label: 'Design Schema', icon: '⬡' },
  { id: 'map', label: 'Map Data To Graph', icon: '↔' },
  { id: 'load', label: 'Load Data', icon: '▷' },
  { id: 'queries', label: 'Write Queries', icon: '✎' },
  { id: 'explore', label: 'Explore Graph', icon: '◎' },
  { id: 'paysim', label: 'PaySim Fraud', icon: '⚠' },
  { id: 'medgraph', label: 'MedGraph', icon: '✚' },
  { id: 'robustness', label: 'Graph Robustness', icon: '◊' },
  { id: 'funds', label: 'Funds Monitor', icon: '₣' },
  { id: 'distributed', label: 'Distributed', icon: '⊞' },
];

function App() {
  const [activePage, setActivePage] = useState<Page>('design');

  const renderPage = () => {
    switch (activePage) {
      case 'design':      return <DesignSchema />;
      case 'map':         return <MapData />;
      case 'load':        return <LoadData />;
      case 'queries':     return <WriteQueries />;
      case 'explore':     return <ExploreGraph />;
      case 'paysim':      return <PaySimView />;
      case 'medgraph':    return <MedGraphView />;
      case 'robustness':  return <RobustnessView />;
      case 'funds':       return <FundsMonitorPanel />;
      case 'distributed':  return <DistributedGraphView />;
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw', overflow: 'hidden' }}>
      {/* Sidebar */}
      <aside style={{
        width: 'var(--sidebar-width)',
        minWidth: 'var(--sidebar-width)',
        background: 'var(--sidebar-bg)',
        borderRight: '1px solid var(--tg-dark-border)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Logo / Header */}
        <div style={{
          height: 'var(--header-height)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          borderBottom: '1px solid var(--tg-dark-border)',
          gap: 8,
        }}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="#2d9cdb" strokeWidth="2"/>
            <circle cx="12" cy="12" r="5" fill="#2d9cdb"/>
            <circle cx="12" cy="4" r="2" fill="#2d9cdb"/>
            <circle cx="12" cy="20" r="2" fill="#2d9cdb"/>
            <circle cx="4" cy="12" r="2" fill="#2d9cdb"/>
            <circle cx="20" cy="12" r="2" fill="#2d9cdb"/>
          </svg>
          <span style={{ fontWeight: 700, fontSize: 14, color: '#e6edf3' }}>Graph Studio</span>
        </div>

        {/* Graph name */}
        <div style={{
          padding: '10px 16px',
          borderBottom: '1px solid var(--tg-dark-border)',
          fontSize: 12,
        }}>
          <div style={{ color: 'var(--tg-text-secondary)', marginBottom: 2 }}>Graph</div>
          <div style={{ color: 'var(--tg-text-primary)', fontWeight: 600 }}>FraudRisk</div>
        </div>

        {/* Nav items */}
        <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 16px',
                background: activePage === item.id ? 'rgba(45,156,219,0.12)' : 'transparent',
                borderLeft: activePage === item.id ? '3px solid var(--tg-blue)' : '3px solid transparent',
                color: activePage === item.id ? 'var(--tg-blue-light)' : 'var(--tg-text-secondary)',
                fontSize: 13,
                fontWeight: activePage === item.id ? 600 : 400,
                fontFamily: 'inherit',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => {
                if (activePage !== item.id) {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)';
                  (e.currentTarget as HTMLElement).style.color = 'var(--tg-text-primary)';
                }
              }}
              onMouseLeave={e => {
                if (activePage !== item.id) {
                  (e.currentTarget as HTMLElement).style.background = 'transparent';
                  (e.currentTarget as HTMLElement).style.color = 'var(--tg-text-secondary)';
                }
              }}
            >
              <span style={{ fontSize: 16, width: 20, textAlign: 'center' }}>{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        {/* Bottom: graph status */}
        <div style={{
          padding: '10px 16px',
          borderTop: '1px solid var(--tg-dark-border)',
          fontSize: 11,
          color: 'var(--tg-text-muted)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            <span className="status-dot status-dot-green" />
            <span>FraudRisk Graph</span>
          </div>
          <div>v3.2.0 · Starter Kit</div>
        </div>
      </aside>

      {/* Main content */}
      <main style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {renderPage()}
      </main>
    </div>
  );
}

export default App;
