import json
from fastapi.testclient import TestClient  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app import db  # noqa: E402

db.init_db()
client = TestClient(app)

AGENT = {"name": "Ava", "system_prompt": "You are Ava, support for Fictional Co.", "voice": "v", "model": "m"}


def test_agents_crud():
    r = client.post("/agents", json=AGENT)
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    r2 = client.get(f"/agents/{aid}")
    assert r2.status_code == 200 and r2.json()["system_prompt"] == AGENT["system_prompt"]
    assert client.get("/agents/nope").status_code == 404


def test_agents_validation():
    assert client.post("/agents", json={"name": "", "system_prompt": "x"}).status_code == 422
    assert client.post("/agents", json={"name": "x"}).status_code == 422


def test_calls_flow():
    aid = client.post("/agents", json=AGENT).json()["id"]
    r = client.post("/calls", json={"agent_id": aid})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["room"].startswith("call-") and body["token"] and body["status"] == "created"
    assert "agent_dispatched" in body  # False here: no worker online in tests
    g = client.get(f"/calls/{body['call_id']}")
    assert g.status_code == 200 and g.json()["transcript"] == []
    assert client.post("/calls", json={"agent_id": "agent-nope"}).status_code == 404
    assert client.get("/calls/call-nope").status_code == 404


def test_supervisor_token():
    import base64
    aid = client.post("/agents", json=AGENT).json()["id"]
    cid = client.post("/calls", json={"agent_id": aid}).json()["call_id"]
    assert client.post("/calls/call-nope/supervisor-token").status_code == 404
    r = client.post(f"/calls/{cid}/supervisor-token")
    assert r.status_code == 200, r.text
    payload = r.json()["token"].split(".")[1] + "=="
    grants = json.loads(base64.urlsafe_b64decode(payload))["video"]
    assert grants["canPublish"] is False and grants["hidden"] is True
    assert grants["canPublishData"] is True  # supervisor must send whispers
    client.post(f"/calls/{cid}/end")
    assert client.post(f"/calls/{cid}/supervisor-token").status_code == 409


def test_end_empty_call_is_not_pass():
    aid = client.post("/agents", json=AGENT).json()["id"]
    cid = client.post("/calls", json={"agent_id": aid}).json()["call_id"]
    r = client.post(f"/calls/{cid}/end")
    assert r.status_code == 200
    data = r.json()["compliance"]
    assert data["recording"]["pass"] is False
    assert data["refund"]["pass"] is None and data["refund"]["error"]


def test_pages_served():
    r = client.get("/")
    assert r.status_code == 200 and "Customer call" in r.text
    r2 = client.get("/supervisor")
    assert r2.status_code == 200 and "Supervisor" in r2.text


def test_delete_agent():
    aid = client.post("/agents", json=AGENT).json()["id"]
    assert client.delete(f"/agents/{aid}").status_code == 204
    assert client.get(f"/agents/{aid}").status_code == 404
    assert client.delete("/agents/agent-nope").status_code == 404


def test_delete_agent_blocked_by_live_call():
    aid = client.post("/agents", json=AGENT).json()["id"]
    cid = client.post("/calls", json={"agent_id": aid}).json()["call_id"]
    assert client.delete(f"/agents/{aid}").status_code == 409
    client.post(f"/calls/{cid}/end")
    assert client.delete(f"/agents/{aid}").status_code == 204
    # ended-call history still readable (no join on agents)
    assert client.get(f"/calls/{cid}").status_code == 200


def test_recordings_lifecycle():
    aid = client.post("/agents", json=AGENT).json()["id"]
    cid = client.post("/calls", json={"agent_id": aid}).json()["call_id"]
    g = client.get(f"/calls/{cid}").json()
    assert g["recording"] is not None and g["recording"]["filepath"].endswith(".ogg")
    assert g["recording"]["status"] in ("recording", "unavailable")
    r = client.post(f"/calls/{cid}/end")
    assert r.status_code == 200
    g2 = client.get(f"/calls/{cid}").json()
    assert g2["recording"]["status"] in ("stopped", "stop-failed", "unavailable")


def test_takeover_token():
    import base64
    aid = client.post("/agents", json=AGENT).json()["id"]
    cid = client.post("/calls", json={"agent_id": aid}).json()["call_id"]
    assert client.post("/calls/call-nope/takeover-token").status_code == 404
    r = client.post(f"/calls/{cid}/takeover-token")
    assert r.status_code == 200, r.text
    payload = r.json()["token"].split(".")[1] + "=="
    grants = json.loads(base64.urlsafe_b64decode(payload))["video"]
    assert grants["canPublish"] is True and grants["canSubscribe"] is True
    client.post(f"/calls/{cid}/end")
    assert client.post(f"/calls/{cid}/takeover-token").status_code == 409
