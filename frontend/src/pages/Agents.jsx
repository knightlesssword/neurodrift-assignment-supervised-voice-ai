import { useEffect, useState } from 'react';
import { listAgents, createAgent } from '../api.js';

// Agent configs (POST /agents, GET /agents). System prompt lives in the DB.
export default function Agents() {
  const [agents, setAgents] = useState([]);
  const [error, setError] = useState('');
  const [form, setForm] = useState({name: '', system_prompt: '', voice: 'aura-asteria-en', model: 'llama3.2:3b'});

  async function load() {
    try { setAgents(await listAgents()); }
    catch (e) { setError(String(e)); }
  }
  useEffect(() => { load(); }, []);

  async function onCreate(e) {
    e.preventDefault();
    setError('');
    try {
      await createAgent(form);
      setForm({name: '', system_prompt: '', voice: 'aura-asteria-en', model: 'llama3.2:3b'});
      await load();
    } catch (err) { setError(String(err)); }
  }

  const set = k => e => setForm(f => ({...f, [k]: e.target.value}));
  return (
    <section>
      <h2>Agents</h2>
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>id</th><th>name</th><th>voice</th><th>model</th></tr></thead>
        <tbody>
          {agents.map(a => <tr key={a.id}><td className="mono">{a.id}</td><td>{a.name}</td><td>{a.voice}</td><td>{a.model}</td></tr>)}
        </tbody>
      </table>
      <h3>New agent</h3>
      <form onSubmit={onCreate} className="form">
        <label>Name <input value={form.name} onChange={set('name')} required maxLength="100" /></label>
        <label>System prompt <textarea value={form.system_prompt} onChange={set('system_prompt')} required rows="4" /></label>
        <label>Voice <input value={form.voice} onChange={set('voice')} /></label>
        <label>Model <input value={form.model} onChange={set('model')} /></label>
        <button type="submit">Create agent</button>
      </form>
      <p className="muted">Tip: include “state once, in your first message only, that the call is being recorded” so the deterministic disclosure check passes.</p>
    </section>
  );
}
