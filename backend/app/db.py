"""SQLite persistence. Shared by backend API and agent worker (same host file)."""
import os
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS agents (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  voice TEXT NOT NULL DEFAULT 'deepgram-aura-asteria',
  model TEXT NOT NULL DEFAULT 'llama3.2:3b',
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS calls (
  id TEXT PRIMARY KEY,
  agent_id TEXT NOT NULL REFERENCES agents(id),
  room TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'created',
  created_at REAL NOT NULL,
  ended_at REAL
);
CREATE TABLE IF NOT EXISTS transcript_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  call_id TEXT NOT NULL REFERENCES calls(id),
  ts REAL NOT NULL,
  speaker TEXT NOT NULL CHECK (speaker IN ('agent','user')),
  text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transcript_call ON transcript_entries(call_id, ts);
CREATE TABLE IF NOT EXISTS latency_turns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  call_id TEXT NOT NULL REFERENCES calls(id),
  turn INTEGER NOT NULL,
  stt_ms REAL,
  llm_ms REAL,
  tts_ms REAL,
  publish_ms REAL
);
CREATE TABLE IF NOT EXISTS compliance_results (
  call_id TEXT PRIMARY KEY REFERENCES calls(id),
  recording_pass INTEGER,
  recording_evidence TEXT,
  recording_reason TEXT,
  refund_pass INTEGER,
  refund_offending_line TEXT,
  refund_error TEXT
);
"""


def _db_path() -> Path:
    url = os.environ.get("DATABASE_URL", "sqlite:///./data/app.db")
    path = url.replace("sqlite:///", "", 1)
    return Path(path)


def get_conn() -> sqlite3.Connection:
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
