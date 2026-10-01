from backend.app.compliance import check_recording_disclosure

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
