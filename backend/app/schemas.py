"""Pydantic request/response schemas for the 4 required endpoints (+2 helpers)."""
from typing import Literal
from pydantic import BaseModel, Field

Speaker = Literal["agent", "user"]


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    system_prompt: str = Field(min_length=1, max_length=8000)
    voice: str = Field(default="deepgram-aura-asteria", max_length=100)
    model: str = Field(default="llama3.2:3b", max_length=100)


class AgentOut(BaseModel):
    id: str
    name: str
    system_prompt: str
    voice: str
    model: str


class CallCreate(BaseModel):
    agent_id: str = Field(min_length=1)


class CallOut(BaseModel):
    call_id: str
    room: str
    token: str
    url: str
    status: str


class TranscriptLine(BaseModel):
    ts: float
    speaker: Speaker
    text: str


class ComplianceOut(BaseModel):
    recording_pass: bool | None = None
    recording_evidence: str | None = None
    recording_reason: str | None = None
    refund_pass: bool | None = None
    refund_offending_line: str | None = None
    refund_error: str | None = None


class LatencyTurn(BaseModel):
    turn: int
    stt_ms: float | None = None
    llm_ms: float | None = None
    tts_ms: float | None = None
    publish_ms: float | None = None
