"""Post-call compliance checks (Part F).

Rule 1 (deterministic, NO LLM): agent must say the call is being recorded
within the first 30 s (timestamps from transcript_entries).
Rule 2 (LLM): agent must not promise a refund. Uses local Ollama
(http://localhost:11434). Evaluator errors/timeouts -> error state, NEVER pass.
"""
import json
import os
import re
import urllib.request

RECORDING_RE = re.compile(r"\brecord\w*\b", re.IGNORECASE)
WINDOW_S = 30.0


def check_recording_disclosure(entries: list[dict], call_started_ts: float) -> dict:
    """entries: [{ts, speaker, text}] sorted by ts. Pure function, unit-tested."""
    for e in entries:
        if e["speaker"] != "agent":
            continue
        if e["ts"] - call_started_ts <= WINDOW_S and RECORDING_RE.search(e["text"]):
            return {"pass": True, "evidence": e["text"], "reason": "disclosure found"}
    agent_lines = [e for e in entries if e["speaker"] == "agent"]
    if not agent_lines:
        return {"pass": False, "evidence": None, "reason": "no agent speech at all"}
    return {"pass": False, "evidence": None, "reason": "no recording disclosure in first 30s"}


REFUND_PROMPT = """You audit a support-call transcript. Reply with JSON only:
{{"pass": true/false, "offending_line": "<exact agent line or null>"}}.
Rule: the AGENT must not promise a refund (e.g. "we will refund you",
"you'll get your money back"). General help is fine. Transcript:
{transcript}
"""


def check_refund_promise(entries: list[dict]) -> dict:
    """LLM check via local Ollama. Returns pass/fail + offending line, or error."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    host = base.replace("/v1", "")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
    transcript = "\n".join(f"[{e['speaker']}] {e['text']}" for e in entries)
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": REFUND_PROMPT.format(transcript=transcript[:6000])}],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
    ).encode()
    try:
        req = urllib.request.Request(f"{host}/api/chat", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode())
        content = data.get("message", {}).get("content", "{}")
        parsed = json.loads(content)
        verdict = parsed.get("pass")
        if not isinstance(verdict, bool):
            return {"pass": None, "offending_line": None, "error": f"bad verdict: {content[:200]}"}
        line = parsed.get("offending_line")
        return {"pass": verdict, "offending_line": line if isinstance(line, str) else None, "error": None}
    except Exception as exc:  # evaluator failure is NEVER a pass
        return {"pass": None, "offending_line": None, "error": f"evaluator error: {exc}"}
