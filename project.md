# Project Guide: Supervised Voice AI Agent on Self-Hosted LiveKit

## 1. Purpose and scope

Build the take-home assignment described in `project.txt`: a small, locally runnable proof of concept for a supervised voice AI agent using a self-hosted LiveKit server. End-to-end functionality matters more than polish. The developer must be able to explain every line of submitted code.

Treat `project.txt` as the source of truth. Do not silently change requirements, add product features, or expand this into a production platform.

## 2. Required deliverables

### Part A: Self-hosted LiveKit

- Run LiveKit locally using Docker. Do not use LiveKit Cloud.
- Use an API key and secret from the self-hosted server configuration.
- Document the ports opened and why they are needed, covering signalling, TCP fallback, and the UDP media range.

### Part B: Python voice agent

- Use the LiveKit Agents framework in Python.
- Implement the pipeline: speech-to-text (STT) → LLM → text-to-speech (TTS), with voice activity detection (VAD) and turn detection.
- Provider choices are open. Free tiers and local models are allowed. Select only providers that can be configured and run with the available credentials and environment.
- The agent must use a fictional-company customer-support persona.
- Store the system prompt in the database, not hard-coded in the agent implementation.
- Implement barge-in: when the customer speaks over the agent, the agent must stop talking immediately.
- After interruption, conversation history must include only the part of the agent response actually spoken before the interruption, not the entire generated sentence.

### Part C: FastAPI backend

Implement these endpoints:

- `POST /agents`: create an agent configuration containing name, system prompt, voice, and model. Persist it in SQLite or PostgreSQL.
- `GET /agents/{id}`: fetch an agent configuration.
- `POST /calls`: start a call for a given agent. Create or choose a room, issue a participant token, and ensure an agent worker joins the room with that agent's configuration.
- `GET /calls/{id}`: return call status and, once the call ends, its transcript and compliance results.

Use appropriate request and response validation, clear error responses, and persistent call state. Keep API orchestration separate from the real-time audio pipeline.

### Part D: Customer web client

- Use React or plain JavaScript.
- Let the customer pick an agent, click Call, and talk through the browser microphone.
- Show a live transcript with a speaker label on every line: agent or user.

### Part E: Supervisor page

- Provide a second browser page for a supervisor to join the same room.
- The supervisor can listen to both customer and agent audio without the customer being able to tell the supervisor is present.
- The supervisor can type a private instruction, such as “offer a 10% discount”, and send it over a LiveKit data channel.
- The agent must use the instruction in its next reply, without reading it aloud and without mentioning a supervisor.

### Part F: Post-call compliance

When a call ends:

- Save the transcript with timestamps and speaker labels.
- Check: “The agent must say the call is being recorded within the first 30 seconds.”
  - This must be checked deterministically from timestamps. Do not use an LLM for this rule.
- Check: “The agent must not promise a refund.”
  - Use an LLM for this rule.
  - Return structured output with pass/fail and the offending line.
- Expose the results through `GET /calls/{id}`.

Do not treat an evaluation error or timeout as a compliance pass.

### Part G: Latency measurement

For every agent turn, record the duration, in milliseconds, for these stages:

1. User stops speaking → final STT result.
2. Final STT result → LLM first token.
3. LLM first token → TTS first audio.
4. TTS first audio → audio published.

Record the timestamps needed to calculate the requested stage durations. Include a table of real measurements from actual calls in the README. Do not invent or fabricate results. Explain the event boundaries used for measurements.

## 3. Optional stretch goals

Only after the required end-to-end flow works, consider two of the assignment's listed stretch goals:

- Supervisor takeover: supervisor clicks a button, the agent goes silent, supervisor speaks directly to the customer, then control can be handed back to the agent.
- Recording: record the full call, both sides, using LiveKit Egress and store it on local disk or S3.
- Concurrency: run at least two agent worker processes and demonstrate three simultaneous calls being shared between them.
- One-command setup: use Docker Compose to start the LiveKit server, backend, agent worker(s), and database.

Do not let optional goals jeopardize required functionality. Do not invent additional stretch goals.

## 4. Implementation principles

- Keep the proof of concept small and understandable.
- Prefer clear module boundaries and explicit responsibilities over unnecessary abstraction.
- Keep the self-hosted LiveKit server, FastAPI backend, agent worker, browser client, and persistence responsibilities distinct.
- Keep configuration and secrets out of source control. Provide an example environment configuration with placeholder values, not real secrets.
- Validate request data and business rules. Handle missing agents, invalid inputs, unavailable services, duplicate requests, disconnects, and provider errors with explicit states or errors.
- Persist agent configuration, call state, timestamped transcript entries, compliance results, and per-turn latency measurements.
- Keep logs useful for debugging, with call identifiers to correlate events. Never log API secrets or access tokens.
- Avoid adding infrastructure or libraries unless needed for a requirement or justified by a concrete implementation constraint.
- Do not claim the customer physically heard audio merely because the LLM generated text. Track speech progress using available framework events and document limitations.
- Do not hard-code measured latency values, compliance outcomes, provider availability, or successful setup claims.
- Pin dependencies and document reproducible setup steps.
- Add focused tests for validation, deterministic compliance timing, call-state behaviour, and other critical logic. Include end-to-end manual verification steps for audio, interruption, whisper, and compliance.
- Keep documentation honest about known limitations and what would be done next.

## 5. Suggested module responsibilities

The exact file layout is an implementation decision. Keep these responsibilities clear:

- **Backend API:** agent and call endpoints, validation, call orchestration, participant tokens, status/results.
- **Persistence:** agent configurations, calls, transcript entries, compliance results, latency measurements.
- **Agent worker:** LiveKit job handling, session lifecycle, STT/LLM/TTS pipeline, VAD, turn detection, interruption handling, supervisor instructions, and timing events.
- **Customer UI:** agent selection, call initiation, microphone interaction, live transcript.
- **Supervisor UI:** room connection, listening, private instruction input, and optionally takeover if selected as a stretch goal.
- **Compliance:** deterministic recording-disclosure check and LLM refund-promise check.
- **Documentation:** setup, architecture diagram, ports, measured latency table, known limitations, and next steps.

## 6. Completion checklist

- [ ] Self-hosted LiveKit runs locally, not LiveKit Cloud.
- [ ] README explains signalling, TCP fallback, and UDP media ports.
- [ ] Python LiveKit agent completes an end-to-end voice conversation.
- [ ] VAD, turn detection, and barge-in work.
- [ ] Interrupted agent speech history reflects only the portion spoken before interruption, within the limits of available event data.
- [ ] Agent configuration and system prompt are stored in the database.
- [ ] All four required API endpoints work.
- [ ] Customer browser can call the agent and display a speaker-labelled live transcript.
- [ ] Supervisor can listen and send private guidance over a LiveKit data channel.
- [ ] Guidance affects the next reply without being spoken or exposing the supervisor.
- [ ] Timestamped transcript is saved after the call.
- [ ] Both compliance checks run and their structured results appear in `GET /calls/{id}`.
- [ ] Per-turn stage timings are recorded in milliseconds.
- [ ] README contains real latency measurements from actual calls.
- [ ] README includes setup steps, architecture diagram, ports and reasons, limitations, and next steps.
- [ ] A 3–5 minute screen recording demonstrates a call, interruption, whisper taking effect, and compliance result.
- [ ] Code and design are understandable enough to explain during the 45–60 minute review.
