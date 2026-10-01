"""Explicit agent dispatch (Part C: make sure a worker joins the room)."""
import json
import logging
import os

logger = logging.getLogger("dispatch")

AGENT_NAME = "support-agent"


def _api_cfg():
    url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    http_url = url.replace("ws://", "http://").replace("wss://", "https://")
    return http_url, os.environ.get("LIVEKIT_API_KEY", "devkey"), os.environ.get("LIVEKIT_API_SECRET", "")


async def dispatch_agent(room: str, call_id: str) -> bool:
    """Ask the registered support-agent worker to join room. False if no worker."""
    from livekit import api
    from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest

    http_url, key, secret = _api_cfg()
    if not secret:
        logger.error("LIVEKIT_API_SECRET missing, skipping dispatch")
        return False
    lk = api.LiveKitAPI(url=http_url, api_key=key, api_secret=secret)
    try:
        req = CreateAgentDispatchRequest(
            agent_name=AGENT_NAME, room=room, metadata=json.dumps({"call_id": call_id}))
        res = await lk.agent_dispatch.create_dispatch(req)
        logger.info("dispatch %s -> room %s", res.id, room)
        return True
    except Exception as exc:
        logger.warning("dispatch failed (worker offline?): %s", exc)
        return False
    finally:
        await lk.aclose()
