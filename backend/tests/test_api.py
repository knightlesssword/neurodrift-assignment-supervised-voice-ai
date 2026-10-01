import os
import tempfile

tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/test.db"
os.environ.setdefault("LIVEKIT_API_SECRET", "test-secret-0123456789abcdef-LOCAL")

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
    g = client.get(f"/calls/{body['call_id']}")
    assert g.status_code == 200 and g.json()["transcript"] == []
    assert client.post("/calls", json={"agent_id": "agent-nope"}).status_code == 404
    assert client.get("/calls/call-nope").status_code == 404


def test_end_empty_call_is_not_pass():
    aid = client.post("/agents", json=AGENT).json()["id"]
    cid = client.post("/calls", json={"agent_id": aid}).json()["call_id"]
    r = client.post(f"/calls/{cid}/end")
    assert r.status_code == 200
    data = r.json()["compliance"]
    assert data["recording"]["pass"] is False
    assert data["refund"]["pass"] is None and data["refund"]["error"]
