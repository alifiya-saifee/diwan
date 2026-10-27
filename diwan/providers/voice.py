"""Muse Voice Transcribe, live. Protocol: open wss://api.meta.ai/v1/asr/realtime, send a JSON handshake as the first
frame (the key travels in it), wait for {"sessionId"}, then stream 16-bit mono PCM at 16 kHz as binary frames.
DIARIZATION mode labels speakers; a finished turn arrives as `speechComplete`; `endStream` closes the session.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable

from diwan.config import env, offline

MODEL = "muse-voice-transcribe-1.0"
URL = "wss://api.meta.ai/v1/asr/realtime"


class VoiceError(RuntimeError):
    pass


def key() -> str | None:
    return env("META_API_KEY") or env("MODEL_API_KEY")


def available() -> bool:
    return bool(key()) and not offline()


def handshake() -> dict:
    return {"authorization": {"accessToken": f"Bearer {key()}"}, "audioEncoding": "PCM_16KHZ", "model": env("META_MODEL_VOICE", MODEL),
            "mode": "DIARIZATION", "partialMode": "CUMULATIVE"}


class Turns:
    """The server's events -> partial lines while someone talks, and finished turns with their speaker label."""

    def __init__(self):
        self.speaker: str | None = None

    def feed(self, ev: dict) -> dict | None:
        t = ev.get("type")
        if t == "speaker":
            self.speaker = ev.get("label")
        elif t == "transcript" and not ev.get("final"):
            return {"partial": ev.get("transcript", ""), "speaker": self.speaker}
        elif t == "speechComplete" and (text := (ev.get("transcript") or "").strip()):
            return {"final": text, "speaker": self.speaker or "speaker_0", "turn": ev.get("turnId")}
        elif t == "error":
            raise VoiceError(ev.get("message") or "transcription error")
        return None


async def stream(audio: AsyncIterator[bytes], on_turn: Callable[[dict], None], connect=None) -> None:
    if not available():
        raise VoiceError("Live transcription needs META_API_KEY")
    import websockets
    async with (connect or websockets.connect)(URL, max_size=2**22) as ws:
        await ws.send(json.dumps(handshake()))
        ack = json.loads(await asyncio.wait_for(ws.recv(), 10))
        if "sessionId" not in ack:
            raise VoiceError(f"Transcription session refused: {str(ack)[:200]}")
        turns = Turns()

        async def pump():
            async for chunk in audio:
                await ws.send(chunk)
            await ws.send(json.dumps({"type": "endStream"}))

        sender = asyncio.create_task(pump())
        try:
            async for msg in ws:
                if isinstance(msg, (bytes, bytearray)):
                    continue
                if out := turns.feed(json.loads(msg)):
                    on_turn(out)
        finally:
            sender.cancel()
