import asyncio

from backend.app import egress as E


class _EgressSvc:
    def __init__(self, ok=True):
        self.ok = ok

    async def start_room_composite_egress(self, req):
        assert req.audio_only is True
        assert req.file.filepath.endswith(".ogg")

        class R:
            egress_id = "eg-123" if self.ok else None

        if not self.ok:
            raise RuntimeError("no egress worker")
        return R()

    async def stop_egress(self, req):
        assert req.egress_id == "eg-123"
        return True


class _LK:
    def __init__(self, *a, **k):
        self.egress = _EgressSvc()

    async def aclose(self):
        pass


class _LKFail(_LK):
    def __init__(self, *a, **k):
        self.egress = _EgressSvc(ok=False)


def test_start_stop_roundtrip(monkeypatch):
    import livekit.api as api
    monkeypatch.setattr(api, "LiveKitAPI", _LK)
    assert asyncio.run(E.start_recording("room-x", "call-x")) == "eg-123"
    assert asyncio.run(E.stop_recording("eg-123")) is True
    assert asyncio.run(E.stop_recording(None)) is False


def test_start_failure_never_breaks_call(monkeypatch):
    import livekit.api as api
    monkeypatch.setattr(api, "LiveKitAPI", _LKFail)
    assert asyncio.run(E.start_recording("room-x", "call-x")) is None
