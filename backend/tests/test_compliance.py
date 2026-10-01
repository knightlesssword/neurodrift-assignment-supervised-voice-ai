import json

from backend.app.compliance import check_recording_disclosure, check_refund_promise

T0 = 1000.0


def test_disclosure_pass():
    e = [{"ts": T0 + 5, "speaker": "agent", "text": "Hi, this call is being recorded."}]
    r = check_recording_disclosure(e, T0)
    assert r["pass"] is True and r["evidence"]


def test_disclosure_late_is_fail():
    e = [{"ts": T0 + 31, "speaker": "agent", "text": "This call is being recorded."}]
    assert check_recording_disclosure(e, T0)["pass"] is False


def test_disclosure_user_does_not_count():
    e = [{"ts": T0 + 5, "speaker": "user", "text": "is this being recorded?"}]
    assert check_recording_disclosure(e, T0)["pass"] is False


def test_disclosure_boundary_30s():
    e = [{"ts": T0 + 30.0, "speaker": "agent", "text": "Note: this call is recorded."}]
    assert check_recording_disclosure(e, T0)["pass"] is True
    e2 = [{"ts": T0 + 30.01, "speaker": "agent", "text": "Note: this call is recorded."}]
    assert check_recording_disclosure(e2, T0)["pass"] is False


class _Resp:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_refund_prompt_formats_without_crash(monkeypatch):
    """Regression: literal JSON braces in the prompt must not break .format()."""
    import backend.app.compliance as C

    seen = {}

    def fake_urlopen(req, timeout=90):
        seen["body"] = req.data.decode()
        inner = '{"pass": false, "offending_line": "We will refund you in full."}'
        return _Resp(('{"message": {"content": %s}}' % json.dumps(inner)).encode())

    monkeypatch.setattr(C.urllib.request, "urlopen", fake_urlopen)
    out = check_refund_promise([{"speaker": "agent", "text": "We will refund you in full."}])
    assert out == {"pass": False, "offending_line": "We will refund you in full.", "error": None}
    prompt = json.loads(seen["body"])["messages"][0]["content"]
    assert '{"pass"' in prompt  # schema example reached the model intact


def test_refund_evaluator_error_is_never_pass(monkeypatch):
    import backend.app.compliance as C

    def boom(req, timeout=90):
        raise TimeoutError("ollama down")

    monkeypatch.setattr(C.urllib.request, "urlopen", boom)
    out = check_refund_promise([{"speaker": "agent", "text": "hello"}])
    assert out["pass"] is None and out["error"]
