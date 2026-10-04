"""Call recording via LiveKit Egress (stretch: local disk).

Audio-only room composite -> MP3 file per call. Best effort by design: a
recording failure must never break the call itself.
"""
import logging
import os

logger = logging.getLogger("egress")


def _api_cfg():
    url = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")
    http_url = url.replace("ws://", "http://").replace("wss://", "https://")
    return http_url, os.environ.get("LIVEKIT_API_KEY", "devkey"), os.environ.get("LIVEKIT_API_SECRET", "")


async def start_recording(room: str, call_id: str) -> str | None:
    """Start an audio-only MP3 room composite. Returns egress_id or None."""
    from livekit import api
    from livekit.protocol import egress as eg

    http_url, key, secret = _api_cfg()
    if not secret:
        return None
    lk = api.LiveKitAPI(url=http_url, api_key=key, api_secret=secret)
    try:
        req = eg.RoomCompositeEgressRequest(
            room_name=room,
            audio_only=True,
            file=eg.EncodedFileOutput(
                file_type=eg.EncodedFileType.MP3,
                filepath=f"/out/recordings/{call_id}.mp3",
            ),
        )
        res = await lk.egress.start_room_composite_egress(req)
        logger.info("egress %s recording room %s", res.egress_id, room)
        return res.egress_id
    except Exception as exc:
        logger.warning("egress start failed (recording skipped): %s", exc)
        return None
    finally:
        await lk.aclose()


async def stop_recording(egress_id: str | None) -> bool:
    """Stop an egress. True unless there was nothing to stop or it failed."""
    from livekit import api
    from livekit.protocol import egress as eg

    if not egress_id:
        return False
    http_url, key, secret = _api_cfg()
    lk = api.LiveKitAPI(url=http_url, api_key=key, api_secret=secret)
    try:
        await lk.egress.stop_egress(eg.StopEgressRequest(egress_id=egress_id))
        return True
    except Exception as exc:
        logger.warning("egress stop failed: %s", exc)
        return False
    finally:
        await lk.aclose()
