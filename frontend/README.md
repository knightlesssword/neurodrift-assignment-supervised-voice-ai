# Frontend (React + Vite) — customer call, supervisor monitor, agent configs

Plain React (JS, no TypeScript), `livekit-client@2.15.4` (pinned, same version
as the verified plain-JS pages in `../web/`), no UI frameworks, no animation
libraries. Backend and agent code are untouched; every call below matches an
existing FastAPI route 1:1.

## Run

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173 — API proxied to http://localhost:8000
```

Backend (`:8000`), LiveKit (docker), and the agent worker must already run —
see root README. The dev server proxies `/api/*` → `:8000`, so no CORS change
was needed on the backend. For a remote backend, set it in the header field
(stored in localStorage); note that cross-origin then requires CORS on the
server, which this PoC backend does not provide — keep the proxy instead.

## Views

- `#/call` (Part D): pick agent → Call → mic → live `agent:`/`user:` transcript.
  Hang up runs `POST /calls/{id}/end` and shows compliance + per-turn latency.
- `#/supervise` (Part E): paste call-id → hidden subscribe-only listen, both
  audios, typed whisper on the `supervisor-whisper` data topic.
- `#/agents` (Part C helper): list + create agent configs (prompt stored in DB).

## API contract (exact backend shapes)

| UI action | Request | Response used |
|---|---|---|
| list/create agents | `GET /agents`, `POST /agents {name,system_prompt,voice,model}` | `{id,…}` |
| start call | `POST /calls {agent_id}` | `{call_id,room,token,url,status,agent_dispatched}` |
| supervisor join | `POST /calls/{id}/supervisor-token` | `{room,token,url}` (hidden, data-ok) |
| end + results | `POST /calls/{id}/end`, `GET /calls/{id}` | `{status,transcript,compliance,latency}` |

## Known items (no backend change made — workarounds)

- Remote-backend use needs server CORS; workaround: always use the dev proxy.
- A production build (`npm run build` → `dist/`) has no server wired: the
  FastAPI app serves only `web/*.html`. Workaround: keep `npm run dev` for the
  demo, or later add one static mount on the backend (not done here per scope).
