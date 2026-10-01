"""Test isolation: all tests share one temp SQLite DB, never ./data/app.db.

conftest.py imports before any test module, so this wins over import order.
"""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
# Self-signed test JWTs only; the real secret lives in .env (never committed).
os.environ["LIVEKIT_URL"] = "ws://localhost:7880"
os.environ["LIVEKIT_API_KEY"] = "devkey"
os.environ["LIVEKIT_API_SECRET"] = "test-secret-0123456789abcdef-LOCALONLY"
