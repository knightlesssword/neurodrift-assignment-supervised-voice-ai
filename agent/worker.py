"""Voice worker (Part B): Deepgram STT/TTS + Ollama LLM + Silero VAD.

- Persona (system prompt, voice, model) comes from SQLite via room->call->agent
  lookup. Nothing persona-related is hard-coded here.
- Barge-in: allow_interruptions=True + use_tts_aligned_transcript=True, so the
  chat history keeps only the portion actually spoken before interruption.
- Supervisor whisper arrives on data topic "supervisor-whisper" and is inserted
  as a hidden system message: used in the next reply, never spoken, never
  mentions a supervisor.
- Live transcript lines are published on data topic "transcript".
- Per-turn latency (Part G) is derived from framework ChatMessage.metrics.
"""
import asyncio
import json
import logging
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from livekit import agents, rtc  # noqa: E402
from livekit.agents import Agent, AgentSession, JobContext, JobProcess, WorkerOptions  # noqa: E402
from livekit.agents.llm import ChatMessage  # noqa: E402
from livekit.plugins import deepgram, openai, silero  # noqa: E402

from backend.app import db  # noqa: E402

logger = logging.getLogger("support-worker")

TOPIC_WHISPER = "supervisor-whisper"
TOPIC_TRANSCRIPT = "transcript"

GUIDANCE_TEMPLATE = (
    "Private guidance for your next reply (do not read it out, "
    "do not mention a supervisor or guidance): {guidance}"
)


def guidance_message(guidance: str) -> ChatMessage:
    """Hidden system message carrying supervisor guidance into the next reply."""
    return ChatMessage(role="system", content=[GUIDANCE_TEMPLATE.format(guidance=guidance.strip())])


def transcript_payload(speaker: str, text: str, ts: float) -> bytes:
    return json.dumps({"speaker": speaker, "text": text, "ts": ts}).encode()


def clean_agent_text(text: str) -> str:
    """Strip a leading role echo some chat templates leak (e.g. 'assistant\\n...')."""
    stripped = text.strip()
    low = stripped.lower()
    if low == "assistant":
        return ""
    if low.startswith("assistant\n"):
        return stripped.split("\n", 1)[1].strip()
    if low.startswith("assistant:"):
        return stripped.split(":", 1)[1].strip()
    return stripped


def latency_ms_from_metrics(user_m: dict, asst_m: dict) -> dict:
    """Map framework MetricsReport fields to Part G stages 1-3 (ms)."""
    out = {}
    if isinstance(user_m.get("transcription_delay"), (int, float)):
        out["stt_ms"] = user_m["transcription_delay"] * 1000.0
    if isinstance(asst_m.get("llm_node_ttft"), (int, float)):
        out["llm_ms"] = asst_m["llm_node_ttft"] * 1000.0
    if isinstance(asst_m.get("tts_node_ttfb"), (int, float)):
        out["tts_ms"] = asst_m["tts_node_ttfb"] * 1000.0
    return out


def publish_stage_ms(asst_created: float, llm_ttfs: float | None, tts_ttfb: float | None,
                     speaking_at: float | None) -> float | None:
    """Stage 4: TTS-first-audio -> audio flowing to the published track.

    tts_first is derived (assistant created + llm->tts + tts first bytes);
    speaking_at is the agent_state_changed->speaking event time. Approximation,
    documented in README; None when the turn never reached playback.
    """
    if speaking_at is None:
        return None
    tts_first = asst_created + (llm_ttfs or 0.0) + (tts_ttfb or 0.0)
    d = (speaking_at - tts_first) * 1000.0
    return d if d >= 0 else 0.0


def lookup_agent(room: str) -> dict:
    conn = db.get_conn()
    try:
        call = conn.execute("SELECT * FROM calls WHERE id=? OR room=?", (room, room)).fetchone()
        if not call:
            raise RuntimeError(f"no call row for room {room}")
        agent = conn.execute("SELECT * FROM agents WHERE id=?", (call["agent_id"],)).fetchone()
        if not agent:
            raise RuntimeError(f"agent {call['agent_id']} not found for room {room}")
        return {"call_id": call["id"], "name": agent["name"],
                "system_prompt": agent["system_prompt"], "voice": agent["voice"], "model": agent["model"]}
    finally:
        conn.close()


def save_transcript(call_id: str, speaker: str, text: str, ts: float) -> None:
    conn = db.get_conn()
    try:
        conn.execute("INSERT INTO transcript_entries (call_id,ts,speaker,text) VALUES (?,?,?,?)",
                     (call_id, ts, speaker, text))
        conn.execute("UPDATE calls SET status='active' WHERE id=? AND status='created'", (call_id,))
        conn.commit()
    finally:
        conn.close()


def save_latency(call_id: str, turn: int, stages: dict) -> None:
    conn = db.get_conn()
    try:
        conn.execute("INSERT INTO latency_turns (call_id,turn,stt_ms,llm_ms,tts_ms,publish_ms) VALUES (?,?,?,?,?,?)",
                     (call_id, turn, stages.get("stt_ms"), stages.get("llm_ms"),
                      stages.get("tts_ms"), stages.get("publish_ms")))
        conn.commit()
    finally:
        conn.close()


def finish_call_via_backend(call_id: str) -> None:
    base = os.environ.get("BACKEND_URL", "http://localhost:8000")
    try:
        req = urllib.request.Request(f"{base}/calls/{call_id}/end", method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            logger.info("call %s finished: %s", call_id, r.read()[:200])
    except Exception as exc:
        logger.error("call %s finish failed: %s", call_id, exc)


def prewarm(proc: JobProcess):
    # Keep one warm process ready (VAD weights loaded) so dispatches join fast.
    # Must be sync: the worker calls prewarm_fnc without awaiting it.
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    await ctx.connect()
    room_name = ctx.room.name
    cfg = lookup_agent(room_name)
    call_id = cfg["call_id"]
    try:  # explicit dispatch carries call_id in job metadata; room lookup is the fallback
        meta = getattr(getattr(ctx, "job", None), "metadata", None)
        if meta:
            call_id = json.loads(meta).get("call_id", call_id)
    except Exception:
        pass
    log = logging.LoggerAdapter(logger, {"call_id": call_id})
    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not deepgram_key:
        raise RuntimeError("DEEPGRAM_API_KEY is not set")
    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    session = AgentSession(
        stt=deepgram.STT(),
        # Ollama speaks the OpenAI chat API; api_key is a required-but-ignored dummy.
        llm=openai.LLM(model=cfg["model"], base_url=ollama_base, api_key="ollama-local"),
        tts=deepgram.TTS(model=cfg["voice"]),
        vad=ctx.proc.userdata.get("vad") or silero.VAD.load(),
        allow_interruptions=True,
        use_tts_aligned_transcript=True,
    )
    agent = Agent(instructions=cfg["system_prompt"])
    turns = {"n": 0, "speaking_at": None, "user_m": {}, "asst_m": {}, "asst_created": None}

    async def publish(speaker: str, text: str):
        ts = time.time()
        save_transcript(call_id, speaker, text, ts)
        try:
            await ctx.room.local_participant.publish_data(
                transcript_payload(speaker, text, ts), topic=TOPIC_TRANSCRIPT, reliable=True)
        except Exception as exc:
            log.warning("transcript publish failed: %s", exc)

    def on_data(packet: rtc.DataPacket):
        try:
            if packet.topic != TOPIC_WHISPER:
                return
            guidance = packet.data.decode().strip()
            if not guidance:
                return
            session.history.insert(guidance_message(guidance))
            log.info("whisper stored (%d chars), applies to next reply", len(guidance))
        except Exception as exc:
            log.warning("whisper handling failed: %s", exc)

    ctx.room.on("data_received", on_data)

    emptied = asyncio.Event()
    customer_ever_joined = asyncio.Event()

    def on_participant_joined(*_args):
        # The agent is dispatched before the customer opens the page; the
        # join event both arms the end-of-call trigger and releases the
        # greeting (RoomIO needs a subscriber to publish audio).
        customer_ever_joined.set()

    def on_participant_left(*_args):
        # End the call once everyone else has left (customer hangup).
        if customer_ever_joined.is_set() and not ctx.room.remote_participants:
            log.info("room emptied, ending call")
            emptied.set()

    ctx.room.on("participant_connected", on_participant_joined)
    ctx.room.on("participant_disconnected", on_participant_left)

    @session.on("user_input_transcribed")
    def _user_transcribed(ev):
        if ev.is_final and ev.transcript.strip():
            turns["n"] += 1
            asyncio.get_event_loop().create_task(publish("user", ev.transcript.strip()))

    @session.on("conversation_item_added")
    def _item_added(ev):
        item = ev.item
        if not isinstance(item, ChatMessage) or not item.text_content:
            return
        text = clean_agent_text(item.text_content or "")
        if not text or item.role not in ("user", "assistant"):
            return
        if item.role == "user":
            turns["user_m"] = dict(item.metrics or {})
        else:
            turns["asst_m"] = dict(item.metrics or {})
            turns["asst_created"] = item.created_at
            asyncio.get_event_loop().create_task(publish("agent", text))
            stages = latency_ms_from_metrics(turns["user_m"], turns["asst_m"])
            stages["publish_ms"] = publish_stage_ms(
                turns["asst_created"], turns["asst_m"].get("llm_node_ttfs"),
                turns["asst_m"].get("tts_node_ttfb"), turns["speaking_at"])
            turns["speaking_at"] = None
            save_latency(call_id, turns["n"], stages)
            log.info("turn %d latency ms: %s", turns["n"], {k: round(v, 1) if v is not None else None for k, v in stages.items()})

    @session.on("agent_state_changed")
    def _agent_state(ev):
        if str(getattr(ev.new_state, "value", ev.new_state)) == "speaking" and turns["speaking_at"] is None:
            turns["speaking_at"] = time.time()

    @session.on("speech_created")
    def _speech(ev):
        handle = ev.speech_handle
        def _done(_h):
            if handle.interrupted:
                log.info("agent speech interrupted; history keeps spoken portion only")
        handle.add_done_callback(_done)

    @session.on("error")
    def _sess_error(ev):
        log.error("session error: %s", ev)

    await session.start(room=ctx.room, agent=agent)
    log.info("worker joined room %s as agent '%s'", room_name, cfg["name"])

    # RoomIO only publishes the agent audio track once someone subscribes;
    # with an empty room the first speech would stall forever. The worker is
    # usually dispatched before the customer opens the page, so wait for them —
    # but a fast customer can beat the (slow-spawning) job into the room, in
    # which case no join event fires and we must not wait at all.
    if not customer_ever_joined.is_set() and not ctx.room.remote_participants:
        log.info("waiting for customer to join before greeting")
        await customer_ever_joined.wait()

    try:
        # Greeting carries the recording disclosure (per DB persona prompt).
        handle = session.generate_reply(instructions="Greet the caller briefly.")
        await asyncio.wait_for(handle, timeout=120)
        log.info("greeting done, exc=%s", handle.exception())
    except asyncio.TimeoutError:
        log.error("greeting timed out after 120s; staying in room for user speech")

    await emptied.wait()
    await session.aclose()
    finish_call_via_backend(call_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm,
                                     agent_name="support-agent", num_idle_processes=1))
