"""FastAPI backend (Part C). 4 required endpoints + list/end helpers."""
import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from . import db
from . import compliance as comp
from . import dispatch as disp
from . import egress as egr
from . import livekit_tokens as tok
from .schemas import AgentCreate, CallCreate


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Supervised Voice AI PoC", lifespan=lifespan)

WEB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "web")


@app.get("/", include_in_schema=False)
def customer_page():
    return FileResponse(os.path.join(WEB_DIR, "customer.html"))


@app.get("/supervisor", include_in_schema=False)
def supervisor_page():
    return FileResponse(os.path.join(WEB_DIR, "supervisor.html"))


def _row_to_agent(r) -> dict:
    return {"id": r["id"], "name": r["name"], "system_prompt": r["system_prompt"], "voice": r["voice"], "model": r["model"]}


@app.post("/agents", status_code=201)
def create_agent(body: AgentCreate):
    agent_id = "agent-" + uuid.uuid4().hex[:8]
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO agents (id,name,system_prompt,voice,model,created_at) VALUES (?,?,?,?,?,?)",
            (agent_id, body.name, body.system_prompt, body.voice, body.model, time.time()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": agent_id, **body.model_dump()}


@app.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    conn = db.get_conn()
    try:
        r = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    finally:
        conn.close()
    if not r:
        raise HTTPException(404, f"agent {agent_id} not found")
    return _row_to_agent(r)


@app.get("/agents")
def list_agents():
    conn = db.get_conn()
    try:
        rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    finally:
        conn.close()
    return [_row_to_agent(r) for r in rows]


@app.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str):
    """Delete an agent config. Blocked (409) while live calls reference it;
    ended-call history keeps working (GET /calls never joins agents)."""
    conn = db.get_conn()
    try:
        a = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        if not a:
            raise HTTPException(404, f"agent {agent_id} not found")
        live = conn.execute(
            "SELECT id FROM calls WHERE agent_id=? AND status != 'ended'", (agent_id,)
        ).fetchall()
        if live:
            ids = ", ".join(r[0] for r in live)
            raise HTTPException(409, f"agent {agent_id} has live call(s) [{ids}]; end them first")
        conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
        conn.commit()
    finally:
        conn.close()
    return None


@app.post("/calls", status_code=201)
async def start_call(body: CallCreate):
    conn = db.get_conn()
    try:
        a = conn.execute("SELECT * FROM agents WHERE id=?", (body.agent_id,)).fetchone()
        if not a:
            raise HTTPException(404, f"agent {body.agent_id} not found")
        call_id = "call-" + uuid.uuid4().hex[:8]
        room = call_id  # room == call_id: single join target for customer+supervisor+agent
        now = time.time()
        conn.execute(
            "INSERT INTO calls (id,agent_id,room,status,created_at) VALUES (?,?,?,?,?)",
            (call_id, body.agent_id, room, "created", now),
        )
        conn.commit()
    finally:
        conn.close()
    # Explicit dispatch: registered support-agent worker joins this room (dispatch model).
    dispatched = await disp.dispatch_agent(room, call_id)
    # Best-effort recording (stretch): never fail the call if egress is down.
    egress_id = await egr.start_recording(room, call_id)
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO recordings (call_id,egress_id,filepath,status) VALUES (?,?,?,?)",
            (call_id, egress_id, f"recordings/{call_id}.mp3",
             "recording" if egress_id else "unavailable"),
        )
        conn.commit()
    finally:
        conn.close()
    try:
        token = tok.mint_token(room, f"customer-{call_id}")
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    return {"call_id": call_id, "room": room, "token": token,
            "url": tok.livekit_url(), "status": "created", "agent_dispatched": dispatched}


@app.post("/calls/{call_id}/supervisor-token")
def supervisor_token(call_id: str):
    """Subscribe-only hidden token for the supervisor page (Part E listen)."""
    conn = db.get_conn()
    try:
        c = conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
    finally:
        conn.close()
    if not c:
        raise HTTPException(404, f"call {call_id} not found")
    if c["status"] == "ended":
        raise HTTPException(409, f"call {call_id} already ended")
    try:
        token = tok.mint_token(c["room"], f"supervisor-{call_id}", subscribe_only=True)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    return {"room": c["room"], "token": token, "url": tok.livekit_url()}


@app.get("/calls/{call_id}")
def get_call(call_id: str):
    conn = db.get_conn()
    try:
        c = conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        if not c:
            raise HTTPException(404, f"call {call_id} not found")
        t = conn.execute(
            "SELECT ts,speaker,text FROM transcript_entries WHERE call_id=? ORDER BY ts", (call_id,)
        ).fetchall()
        comp_row = conn.execute("SELECT * FROM compliance_results WHERE call_id=?", (call_id,)).fetchone()
        lat = conn.execute(
            "SELECT turn,stt_ms,llm_ms,tts_ms,publish_ms FROM latency_turns WHERE call_id=? ORDER BY turn",
            (call_id,),
        ).fetchall()
        rec = conn.execute("SELECT * FROM recordings WHERE call_id=?", (call_id,)).fetchone()
    finally:
        conn.close()
    return {
        "call_id": c["id"],
        "agent_id": c["agent_id"],
        "room": c["room"],
        "status": c["status"],
        "transcript": [{"ts": r["ts"], "speaker": r["speaker"], "text": r["text"]} for r in t],
        "compliance": dict(comp_row) if comp_row else None,
        "latency": [dict(r) for r in lat],
        "recording": dict(rec) if rec else None,
    }


@app.post("/calls/{call_id}/end")
def end_call(call_id: str):
    """End a call: stop recording, freeze transcript, run compliance, persist."""
    conn = db.get_conn()
    try:
        c = conn.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
        if not c:
            raise HTTPException(404, f"call {call_id} not found")
        rec = conn.execute("SELECT * FROM recordings WHERE call_id=?", (call_id,)).fetchone()
        stopped = asyncio.run(egr.stop_recording(rec["egress_id"] if rec else None))
        if rec and rec["egress_id"]:
            conn.execute("UPDATE recordings SET status=? WHERE call_id=?",
                         ("stopped" if stopped else "stop-failed", call_id))
        entries = conn.execute(
            "SELECT ts,speaker,text FROM transcript_entries WHERE call_id=? ORDER BY ts", (call_id,)
        ).fetchall()
        ed = [{"ts": r["ts"], "speaker": r["speaker"], "text": r["text"]} for r in entries]
        rec = comp.check_recording_disclosure(ed, c["created_at"]) if ed else {"pass": False, "evidence": None, "reason": "empty transcript"}
        ref = comp.check_refund_promise(ed) if ed else {"pass": None, "offending_line": None, "error": "empty transcript"}
        conn.execute(
            """INSERT OR REPLACE INTO compliance_results
               (call_id,recording_pass,recording_evidence,recording_reason,refund_pass,refund_offending_line,refund_error)
               VALUES (?,?,?,?,?,?,?)""",
            (call_id, int(rec["pass"]) if rec["pass"] is not None else None, rec.get("evidence"),
             rec.get("reason"), int(ref["pass"]) if ref["pass"] is not None else None,
             ref.get("offending_line"), ref.get("error")),
        )
        conn.execute("UPDATE calls SET status='ended', ended_at=? WHERE id=?", (time.time(), call_id))
        conn.commit()
    finally:
        conn.close()
    return {"call_id": call_id, "status": "ended",
            "compliance": {"recording": rec, "refund": ref}}
