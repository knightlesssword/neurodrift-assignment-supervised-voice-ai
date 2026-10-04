# Supervised Voice AI Agent — Local PoC (Self-Hosted LiveKit)

Contact-centre proof of concept: an AI agent answers a customer call in real time;
a human supervisor can silently listen, privately steer the agent (whisper), while
post-call compliance checks and per-turn latency measurements are recorded.

`project.txt` is the authoritative spec. This README documents only what actually
runs — no invented numbers, ports, or features.

## 1. What works (verified end to end, 2026-10-01)

- Customer browser call with live speaker-labelled transcript (Part D).
- Greeting with recording disclosure; barge-in stops agent speech, history keeps
  the spoken portion (TTS-aligned transcript) — worker logs
  `agent speech interrupted` (Part B).
- Supervisor hidden listen (subscribe-only token, publishes nothing) + typed
  whisper over the `supervisor-whisper` data topic applied to the next reply
  with no supervisor mention — worker logs `whisper stored (27 chars)` and the
  next replies offered the 10% discount (Part E).
- Post-call: timestamped transcript saved; deterministic 30s disclosure check;
  LLM refund check via local Ollama with `{pass, offending_line}`; all exposed
  in `GET /calls/{id}` (Part F).
- Per-turn stage timings in ms persisted per turn (Part G, table below).

## 2. Architecture

```
browser (customer.html) ──WebRTC audio + data──┐
browser (supervisor.html) ─data whisper/listens ┼─► LiveKit 1.8.4 (docker)
FastAPI backend :8000 ──tokens/dispatch/compliance──┘         ▲
   │ SQLite ./data/app.db (agents/calls/transcript/latency/compliance)  │ job
   └─ agent worker (support-agent): Deepgram STT/TTS ─ Ollama LLM ─ Silero VAD
```

- Backend owns API, tokens, dispatch, compliance, pages. It never touches audio.
- Worker owns the realtime pipeline. It reads the persona (system prompt, voice,
  model) from SQLite via room→call→agent lookup — nothing hard-coded.
- Transcript lines flow worker→browser on the reliable `transcript` data topic
  and are also persisted with `time.time()` timestamps.
- Whisper flows supervisor→worker on reliable `supervisor-whisper` and is
  inserted as a hidden system message for the next reply only.

## 3. Setup (reviewer, from scratch)

Prereqs: Docker Desktop, Python 3.11, Ollama.app (or any Ollama on :11434).

```bash
git clone <repo> && cd <repo>
cp .env.example .env   # fill DEEPGRAM_API_KEY; keep secrets out of git
docker compose up -d livekit            # self-hosted server (Part A)
ollama pull llama3.2:3b                 # local LLM (CPU-friendly)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
set -a; . ./.env; set +a
.venv/bin/uvicorn backend.app.main:app --port 8000   # API + pages
.venv/bin/python agent/worker.py dev                 # registers support-agent
```

Demo: `POST /agents` (Swagger at http://localhost:8000/docs), open
http://localhost:8000/ (customer, allow mic) → Call; second tab
http://localhost:8000/supervisor → paste call-id → Listen → whisper →
ask about discounts → Hang up → `GET /calls/{id}`.
Tests: `.venv/bin/python -m pytest backend/tests/ agent/tests/ -q` (25 passed).

Seed prompt that satisfies the disclosure rule: tell the agent to state once,
in its first message only, that the call is being recorded.

## 4. Self-hosted LiveKit ports (Part A)

| Port | Purpose |
|---|---|
| `7880/tcp` | Signalling: WebSocket SDP offer/answer + ICE, HTTP API, token verify (`port:` in livekit.yaml). |
| `7881/tcp` | ICE-TCP fallback: media over TCP when UDP is blocked. |
| `50000–50010/udp` | WebRTC media: SRTP/SRTCP Opus audio, ICE host/srflx candidates (narrowed from the 50000–50100 default; ~5 concurrent calls). |
| `3478/udp` | Embedded TURN/UDP relay (+STUN). Required on Docker Desktop: container IPs (172.x) are unroutable from the host, so direct host candidates fail; relay via the signal host works. |

`livekit.yaml` also sets `rtc.node_ip: 127.0.0.1` + `enable_loopback_candidate`:
the demo runs entirely on one Mac, so the server advertises loopback host
candidates routed via the published UDP mapping. (An earlier `LIVEKIT_NODE_IP`
env was removed — it is not a real LiveKit variable.) No LiveKit Cloud anywhere:
API key/secret are ours (`devkey` + 32+-char secret in `livekit.yaml`/`.env`).

## 5. Latency (Part G) — real measured numbers

Boundaries: (1) VAD end-of-speech → final STT (`transcription_delay`);
(2) LLM node start → first token (`llm_node_ttft`); (3) first text → first TTS
audio (`tts_node_ttfb`); (4) TTS-first-audio → agent `speaking` state
(approximation: measures TTS-output→playback-start since per-chunk publish has
no discrete event — usually ≈0ms, documented limit, not a real zero).

| turn | user_stop→stt | stt→llm | llm→tts | tts→published* |
|---|---|---|---|---|
| 0 (greeting) | — | 2621.0 | 564.9 | 1.2 |
| 2 | 358.3 | 152.2 | 726.4 | 0.0 |
| 4 | 312.1 | 207.1 | 763.2 | 0.0 |
| 5 | 1209.2 | 215.6 | 890.0 | 0.0 |
| 6 | 1657.4 | 163.9 | 618.0 | 0.0 |
| 7 | 1110.8 | 184.0 | 351.3 | 0.0 |
| 8 | 1052.7 | 174.2 | 776.3 | 0.0 |

All ms, from `latency_turns` of real voice calls (Deepgram STT/TTS +
`llama3.2:3b` on CPU). Turn 0 LLM is slow (cold model load); warm turns ≈200ms.
STT grows with utterance length (endpointing). Biggest lever: LLM/TTS choice.

## 6. Known limitations

- Refund judge (local 3b LLM) is nondeterministic and imprecise: it failed a
  user-requested 10% *discount* once (`false` + line) and passed similar content
  later. Discount ≠ refund. Production needs a stronger judge + human review.
- STT mishearings happen (`discount` → `disconnect` once); no custom vocabulary.
- `publish_ms` is an approximation (see §5), not wire time.
- Greeting waits for the first subscriber (framework publishes audio only with a
  subscriber present); empty-room calls show no transcript until someone joins.
- Single worker, `dev` mode; no auth on API; supervisor token is bearer — fine
  for a local PoC, not for production.
- Deprecation warnings from `livekit-agents` 1.8.3 (top-level turn params,
  `metrics_collected`) are worked around via `turn_handling`-free defaults and
  `ChatMessage.metrics`; Cloud inference endpoints (EOU/adaptive) 401 and fall
  back to local models automatically.

## 7. Stretch goals (done) + what next

- **One-command setup:** `docker compose up` starts LiveKit, Redis, backend,
  agent worker, and Egress (SQLite on `./data`, Ollama stays native).
  Server-side calls use internal `ws://livekit:7880`; browsers get
  `PUBLIC_LIVEKIT_URL` (`ws://localhost:7880`).
- **Recording:** audio-only room-composite Egress per call to
  `recordings/<call-id>.ogg` (Opus-in-Ogg — request OGG explicitly, filenames
  match content), best-effort so it never breaks calls; path + status exposed
  in `GET /calls/{id}` as `recording`. Verified: multi-MB files from real calls.
- Takeover and concurrency demos deliberately skipped (first touches the live
  audio path, second needs 3 live audio sources to demo).

Remaining production direction: stronger compliance judge + eval set; Postgres +
auth; worker pool; TURN/TLS + real domain for remote clients; latency attack
order: model choice first, then endpointing tuning.
