"""LiveKit participant token issuance (self-hosted server, no Cloud)."""
import os
from livekit import api


def _cfg():
    url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    key = os.environ.get("LIVEKIT_API_KEY", "devkey")
    secret = os.environ.get("LIVEKIT_API_SECRET", "")
    if not secret:
        raise RuntimeError("LIVEKIT_API_SECRET is not set (see .env)")
    return url, key, secret


def livekit_url() -> str:
    return _cfg()[0]


def mint_token(room: str, identity: str, *, subscribe_only: bool = False) -> str:
    """Mint a participant JWT. Supervisor gets subscribe-only (hidden listener)."""
    _, key, secret = _cfg()
    grants = api.VideoGrants(
        room_join=True,
        room=room,
        can_publish=not subscribe_only,
        can_subscribe=True,
        can_publish_data=not subscribe_only,
        hidden=subscribe_only,
    )
    token = api.AccessToken(key, secret).with_identity(identity).with_grants(grants)
    return token.to_jwt()
