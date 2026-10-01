"""Focused STT/user-turn test: waits for the agent (track published), then speaks."""
import asyncio
import os
import struct
import sys
import urllib.request
import json

from livekit import api, rtc
from livekit.plugins import deepgram
from livekit.agents.utils import http_context

CALL_ID, TOKEN = sys.argv[1], sys.argv[2]
URL = os.environ["LIVEKIT_URL"]
BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")


async def agent_ready() -> bool:
    lk = api.LiveKitAPI(url=URL.replace("ws://", "http://"),
                        api_key=os.environ["LIVEKIT_API_KEY"], api_secret=os.environ["LIVEKIT_API_SECRET"])
    try:
        for _ in range(40):
            parts = await lk.room.list_participants(api.ListParticipantsRequest(room=CALL_ID))
            for p in parts.participants:
                if p.identity.startswith("agent-") and len(p.tracks) > 0:
                    return True
            await asyncio.sleep(3)
        return False
    finally:
        await lk.aclose()


async def synth_48k(text: str) -> bytes:
    async with http_context.open():
        tts = deepgram.TTS(model="aura-asteria-en")
        chunks: list[bytes] = []
        async with tts.synthesize(text) as stream:
            async for ev in stream:
                frame = getattr(ev, "frame", None) or getattr(ev, "audio", None)
                if frame is not None and hasattr(frame, "data"):
                    chunks.append(bytes(frame.data))
    raw = b"".join(chunks)
    s = struct.unpack(f"<{len(raw)//2}h", raw)
    up = bytearray()
    for v in s:
        up += struct.pack("<hh", v, v)
    return bytes(up)


async def main():
    room = rtc.Room()
    opts = rtc.RoomOptions(connect_timeout=90)  # allow ICE TCP fallback time
    for attempt in range(2):
        try:
            await room.connect(URL, TOKEN, opts)
            break
        except Exception as e:
            print(f"connect try {attempt} failed: {type(e).__name__}; retrying...", flush=True)
            await asyncio.sleep(30)
    else:
        print("CONNECT FAILED", flush=True)
        return
    print("joined", flush=True)
    source = rtc.AudioSource(48000, 1)
    opts = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    await room.local_participant.publish_track(
        rtc.LocalAudioTrack.create_audio_track("mic", source), opts)
    print("mic published; waiting for agent audio track...", flush=True)
    if not await agent_ready():
        print("AGENT NEVER READY", flush=True)
        await room.disconnect()
        return
    print("agent ready, waiting 25s for greeting to finish...", flush=True)
    await asyncio.sleep(25)
    data = await synth_48k("Hello Ava, I need help with my bill please.")
    rate, flen = 48000, 960
    for i in range(0, len(data) // 2, flen):
        chunk = data[i * 2:(i + flen) * 2]
        if len(chunk) < flen * 2:
            chunk += b"\x00" * (flen * 2 - len(chunk))
        await source.capture_frame(rtc.AudioFrame(data=chunk, sample_rate=rate,
                                                  num_channels=1, samples_per_channel=flen))
        await asyncio.sleep(0.02)
    print(f"speech done ({len(data)//2/rate:.1f}s), waiting for reply...", flush=True)
    for _ in range(30):
        await asyncio.sleep(4)
        with urllib.request.urlopen(f"{BACKEND}/calls/{CALL_ID}", timeout=15) as r:
            d = json.loads(r.read().decode())
        if len(d["transcript"]) >= 2:
            break
    with urllib.request.urlopen(f"{BACKEND}/calls/{CALL_ID}", timeout=15) as r:
        d = json.loads(r.read().decode())
    print(f"lines={len(d['transcript'])}", flush=True)
    for m in d["transcript"]:
        print(f"[{m['speaker']}] {m['text'][:120]}", flush=True)
    print("latency:", d["latency"], flush=True)
    await room.disconnect()


asyncio.run(main())
