import { useState } from 'react';
import Call from './pages/Call.jsx';
import Supervise from './pages/Supervise.jsx';
import Agents from './pages/Agents.jsx';
import './styles.css';

// Minimal hash router: #/call (Part D), #/supervise (Part E), #/agents.
function route() {
  const h = window.location.hash.replace(/^#\/?/, '');
  return h === 'supervise' || h === 'agents' ? h : 'call';
}

export default function App() {
  const [view, setView] = useState(route());
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBase') || '');

  function nav(v) {
    window.location.hash = '/' + v;
    setView(v);
  }

  function saveBase(v) {
    setApiBase(v);
    if (v.trim()) localStorage.setItem('apiBase', v.trim());
    else localStorage.removeItem('apiBase');
  }

  return (
    <div className="app">
      <header>
        <h1>Supervised Voice AI</h1>
        <nav>
          <button className={view === 'call' ? 'active' : ''} onClick={() => nav('call')}>Call</button>
          <button className={view === 'supervise' ? 'active' : ''} onClick={() => nav('supervise')}>Supervise</button>
          <button className={view === 'agents' ? 'active' : ''} onClick={() => nav('agents')}>Agents</button>
        </nav>
      </header>
      <main>
        <div className="row">
          <label title="Blank = same-origin /api (vite dev proxy). Set only for a remote backend.">
            Backend <input value={apiBase} onChange={e => saveBase(e.target.value)} placeholder="http://localhost:8000" size="26" />
          </label>
        </div>
        {view === 'call' && <Call />}
        {view === 'supervise' && <Supervise />}
        {view === 'agents' && <Agents />}
      </main>
    </div>
  );
}
