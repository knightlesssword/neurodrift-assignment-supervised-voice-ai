// Backend API client. Mirrors backend/app/main.py exactly; no extra endpoints.
// Same-origin in dev via vite proxy (see vite.config.js): call with '/api/...'.
// For a direct backend URL, set localStorage 'apiBase' (e.g. http://localhost:8000)
// and paths below are used without the /api prefix.
export function apiBase() {
  const raw = (localStorage.getItem('apiBase') || '').trim().replace(/\/$/, '');
  return raw || '/api';
}

async function req(method, path, body) {
  const r = await fetch(apiBase() + path, {
    method,
    headers: {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await r.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = {raw: text}; }
  if (!r.ok) throw new Error(`${method} ${path} → ${r.status}: ${typeof data === 'object' ? JSON.stringify(data).slice(0, 200) : data}`);
  return data;
}

export const listAgents = () => req('GET', '/agents');
export const createAgent = (a) => req('POST', '/agents', a);
export const startCall = (agent_id) => req('POST', '/calls', {agent_id});
export const getCall = (id) => req('GET', `/calls/${id}`);
export const supervisorToken = (id) => req('POST', `/calls/${id}/supervisor-token`);
export const endCall = (id) => req('POST', `/calls/${id}/end`);
