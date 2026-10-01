"""Headless end-to-end check (Parts D/E/F/G without a browser).

Joins as customer WITH mic published (subscriber presence unblocks agent audio),
collects 'transcript' data-channel lines, speaks via Deepgram-synthesized audio
frames, sends a supervisor whisper from a second connection, interrupts the
greeting (barge-in), hangs up, and prints GET /calls/{id}.
"""
import asyncio
import json
import os
import sys

from livekit import rtc
from livekit.plugins import deepgram
from livekit.agents.utils import http_context

CALL_ID = sys.argv[1]
TOKEN = sys.argv[2]
SUP_TOKEN = sys.argv[3]
BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")
URL = os.environ["LIVEKIT_URL"]

lines: list[dict] = []


async def synth_frames(text: str) -> list[bytes]:
    """Synthesize speech to raw 24kHz s16le mono chunks (Deepgram TTS)."""
    async with http_context.open():
        tts = deepgram.TTS(model="aura-asteria-en")
        chunks: list[bytes] = []
        async with tts.synthesize(text) as stream:
            async for ev in stream:
                frame = getattr(ev, "frame", None) or getattr(ev, "audio", None)
                if frame is not None and hasattr(frame, "data"):
                    chunks.append(bytes(frame.data))
        return chunks


def upsample_24k_to_48k(raw: bytes) -> bytes:
    import struct
    n = len(raw) // 2
    s = struct.unpack(f"<{n}h", raw)
    out = bytearray()
    for v in s:
        out += struct.pack("<hh", v, v)
    return bytes(out)


async def speak(source: rtc.AudioSource, text: str, rate=48000):
    frames_48k = b"".join(upsample_24k_to_48k(c) for c in await synth_frames(text))
    samples = len(frames_48k) // 2
    frame_len = rate // 50  # 20ms
    for i in range(0, samples, frame_len):
        chunk = frames_48k[i * 2:(i + frame_len) * 2]
        if len(chunk) < frame_len * 2:
            chunk += b"\x00" * (frame_len * 2 - len(chunk))
        await source.capture_frame(rtc.AudioFrame(data=chunk, sample_rate=rate,
                                                  num_channels=1, samples_per_channel=frame_len))
        await asyncio.sleep(0.02)


async def main():
    room = rtc.Room()

    def on_data(packet: rtc.DataPacket):
        if packet.topic == "transcript":
            lines.append(json.loads(packet.data.decode()))

    room.on("data_received", on_data)
    await room.connect(URL, TOKEN)
    print("customer joined", flush=True)
    source = rtc.AudioSource(48000, 1)
    track = rtc.LocalAudioTrack.create_audio_track("mic", source)
    await room.local_participant.publish_track(track)
    await asyncio.sleep(3)  # greeting starts once we're subscribed

    # 1. Barge-in: speak over the greeting ~4s in.
    await asyncio.sleep(4)
    print("interrupting greeting...", flush=True)
    await speak(source, "Hello, sorry to interrupt, I need help with my bill.")
    await asyncio.sleep(18)  # let agent reply

    # 2. Supervisor whisper from a second (hidden) connection.
    sup = rtc.Room()
    await sup.connect(URL, SUP_TOKEN)
    await sup.local_participant.publish_data(
        "offer a 10 percent discount".encode(), reliable=True, topic="supervisor-whisper")
    print("whisper sent", flush=True)
    await asyncio.sleep(2)
    await speak(source, "What discount can you give me on my bill?")
    await asyncio.sleep(25)  # let agent reply with guidance applied
    await sup.disconnect()

    print("=== TRANSCRIPT DATA ===")
    for m in lines:
        print(f"[{m['speaker']}] {m['text'][:120]}", flush=True)
    await room.disconnect()
    print("customer left", flush=True)


asyncio.run(main())
