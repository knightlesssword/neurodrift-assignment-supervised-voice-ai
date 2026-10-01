# Agent Instructions

## Source of truth

Read `project.txt` before making any changes. Follow it as the authoritative assignment specification. Read `project.md` for the organised implementation checklist. If the files appear to conflict, do not silently invent a resolution; follow `project.txt` and report the ambiguity.

## Global rules

- Build only the specified local proof of concept.
- Do not use LiveKit Cloud. LiveKit must be self-hosted.
- Do not implement optional stretch goals until all required parts work end to end.
- Do not add unrequested product features, services, infrastructure, or complexity.
- Do not fabricate latency measurements, test results, compliance results, screenshots, or recording evidence.
- Keep secrets out of source control.
- Make changes small, reviewable, and documented.
- Do not overwrite another agent's work. Coordinate file ownership and integrate through the lead agent.
- Before using a new dependency, confirm it serves a requirement and is compatible with the selected versions.
- Preserve a working end-to-end path. Prefer integration and correctness over cosmetic polish.
- If an assignment requirement cannot be met or is ambiguous, report it clearly instead of pretending it is complete.

## Multi-agent workflow

Use multiple agents when the installed OpenCode environment supports delegation. The lead/orchestrator owns the overall plan, architecture decisions, shared interfaces, integration, final testing, and README. Delegate independent tasks with explicit file ownership. If subagents or delegation are unavailable, continue sequentially without pretending parallel work occurred.

### Lead agent / orchestrator

Owns:
- Reading `project.txt` and maintaining the requirement checklist.
- Choosing the minimum coherent implementation and recording decisions.
- Defining shared API schemas, database entities, call states, and event contracts before parallel work begins.
- Assigning isolated tasks and file ownership.
- Resolving integration conflicts.
- Running or coordinating end-to-end verification.
- Ensuring the README and screen-recording checklist match what actually works.
- Reviewing all changes and removing unnecessary complexity.

Do not delegate the entire project without defining interfaces first.

### Backend agent

Owns backend files only, as assigned by the lead.

Responsibilities:
- Implement FastAPI `POST /agents`, `GET /agents/{id}`, `POST /calls`, and `GET /calls/{id}`.
- Implement validated request/response schemas and persistence for agent configurations, calls, transcripts, compliance results, and latency measurements.
- Implement call orchestration, room selection/creation, participant-token issuance, and agent dispatch using the chosen LiveKit Agents workflow.
- Return explicit errors and call states.
- Coordinate schemas and interfaces with the agent-worker owner before implementing shared contracts.

Do not implement the audio pipeline or duplicate worker logic inside API handlers.

### Voice-agent agent

Owns the Python LiveKit Agents worker and session files, as assigned by the lead.

Responsibilities:
- Implement the STT → LLM → TTS flow with VAD and turn detection.
- Load the selected agent's configuration, including system prompt, from persistent configuration rather than hard-coding it.
- Handle barge-in and reconcile conversation history with the portion of agent speech actually delivered according to available framework events.
- Receive supervisor guidance through a LiveKit data channel and apply it to the next reply without reading it aloud or mentioning a supervisor.
- Emit transcript events and the timestamps required for latency measurements.
- Report worker/session status and failures through the agreed application contract.

Do not create a second, incompatible data model or invent event fields independently of the lead.

### Frontend agent

Owns frontend files only, as assigned by the lead.

Responsibilities:
- Implement the customer page: select agent, start a call, use the microphone, and display a live speaker-labelled transcript.
- Implement the supervisor page: join the same room, listen to customer and agent tracks, and send private guidance over the data channel.
- Use the API and shared contracts agreed with the lead.
- Keep supervisor audio from being published to the customer during normal monitoring.
- Handle connection errors, permissions, and disconnected states visibly.

Do not place server secrets in browser code. Do not implement unrelated UI features.

### Compliance and testing agent

Use this role only if delegation is available and it can work independently after the data contracts are agreed.

Responsibilities:
- Implement or review the deterministic recording-disclosure check based on transcript timestamps. Do not use an LLM for this rule.
- Implement or review the LLM refund-promise check with structured pass/fail output and the offending line.
- Ensure evaluator errors are distinguishable from policy failures and never become a false pass.
- Add focused tests for the deterministic rule, structured result validation, and edge cases.
- Avoid changing shared models without coordination.

If the lead assigns compliance to the backend agent instead, this role should focus on tests and review rather than duplicating implementation.

### Documentation and verification agent

Use this role only when available and when the implementation has stable interfaces.

Responsibilities:
- Draft README setup instructions based only on the actual repository configuration.
- Document the self-hosted LiveKit ports and why each is required, including signalling, TCP fallback, and UDP media range.
- Prepare an architecture diagram and a manual verification checklist.
- Add the latency table only from real measured calls supplied by the implementation/testing workflow.
- Record known limitations and realistic next steps.
- Verify the requested 3–5 minute demo checklist: call, interruption, whisper effect, and compliance result.

Do not invent setup commands, port values, measurements, or features. Confirm them from the actual configuration and runtime.

## Parallelisation rules

1. The lead first reads the assignment and establishes the minimum architecture, database choice, provider choices, API contracts, transcript format, call-state model, and event/timing contract.
2. Delegate backend, voice-agent, and frontend work only after their interfaces are documented. These areas can be developed in parallel if their file ownership is distinct.
3. Compliance can be delegated once transcript and call schemas are agreed.
4. Documentation should reflect actual implementation, so final setup details and measured results must be verified after integration.
5. The lead integrates early, resolves contract mismatches, runs the full application, and tests the complete flow.
6. If parallel work creates conflicts, the lead resolves them. Do not have multiple agents edit the same file simultaneously unless the orchestrator explicitly coordinates it.
7. Prefer a small number of meaningful tasks over spawning agents for trivial work. Use only agents/tools actually available in the current OpenCode setup.

## Required handoff format

Every delegated agent should report:
- Files created or changed.
- Requirements covered.
- Commands or tests actually run and their actual results.
- Configuration or credentials required, without exposing secret values.
- Known limitations and unresolved integration questions.
- Any shared interfaces that changed.

## Final acceptance gate

The lead must verify every required item in `project.md` against the actual implementation. A task is not complete merely because code was written. Do not claim a requirement passes without evidence from a test or a real end-to-end check. Stretch goals are secondary to the required assignment.
