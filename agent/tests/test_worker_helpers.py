import json

import pytest

from agent.worker import (  # noqa: E402
    guidance_message,
    latency_ms_from_metrics,
    publish_stage_ms,
    transcript_payload,
)


def test_guidance_is_hidden_system_message():
    m = guidance_message("offer a 10% discount")
    assert m.role == "system"
    assert "offer a 10% discount" in m.content[0]
    assert "never read it out" in m.content[0].lower()
    assert "never mention" in m.content[0].lower()
    assert "verbatim" in m.content[0].lower()


def test_transcript_payload_roundtrip():
    p = json.loads(transcript_payload("agent", "hello", 123.0).decode())
    assert p == {"speaker": "agent", "text": "hello", "ts": 123.0}


def test_latency_mapping_seconds_to_ms():
    out = latency_ms_from_metrics({"transcription_delay": 0.4}, {"llm_node_ttft": 0.9, "tts_node_ttfb": 0.3})
    assert out == {"stt_ms": 400.0, "llm_ms": 900.0, "tts_ms": 300.0}


def test_latency_mapping_ignores_missing():
    assert latency_ms_from_metrics({}, {}) == {}


def test_publish_stage_none_when_no_playback():
    assert publish_stage_ms(100.0, 0.5, 0.3, None) is None


def test_publish_stage_math():
    # tts_first = 100 + 0.5 + 0.3 = 100.8; speaking at 101.0 -> ~200ms
    assert publish_stage_ms(100.0, 0.5, 0.3, 101.0) == pytest.approx(200.0)


def test_clean_agent_text_strips_role_echo():
    from agent.worker import clean_agent_text
    assert clean_agent_text("assistant\nHello there") == "Hello there"
    assert clean_agent_text("Assistant: hi") == "hi"
    assert clean_agent_text("Hello there") == "Hello there"
    assert clean_agent_text("assistant") == ""
