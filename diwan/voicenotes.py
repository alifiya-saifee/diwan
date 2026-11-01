"""A WhatsApp voice note, as words. WhatsApp keeps them as Ogg Opus; the transcriber takes 16 kHz mono WAV. Nothing is kept on disk, and a
note that can't be read stays what it was: "a voice note", which the owner can play on their phone.
"""
from __future__ import annotations

import io
import wave

import httpx

from diwan.config import env
from diwan.providers import whatsapp


def wav(ogg: bytes) -> bytes:
    import av
    pcm = bytearray()
    with av.open(io.BytesIO(ogg)) as box:
        fit = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in box.decode(audio=0):
            for f in fit.resample(frame):
                pcm += bytes(f.planes[0])[: f.samples * 2]
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(bytes(pcm))
    return out.getvalue()


def fetch(media: str, transport=None) -> bytes:
    """WhatsApp gives a short-lived address for the media id, then the file, both with the line's own token."""
    token = env("PERSONAL_WHATSAPP_TOKEN")
    with httpx.Client(transport=transport, timeout=30, headers={"Authorization": f"Bearer {token}"}) as c:
        return c.get(c.get(f"{whatsapp.GRAPH}/{media}").json()["url"]).content


def transcribe(media: str) -> str | None:
    from diwan.providers import local_asr, meta
    try:
        clip = wav(fetch(media))
    except Exception:  # noqa: BLE001  the owner still hears that a voice note came
        return None
    try:
        return meta.transcribe(clip)["text"] or None
    except Exception:  # noqa: BLE001  then the local model, if it's installed
        try:
            return local_asr.transcribe(clip)["text"] or None
        except Exception:  # noqa: BLE001
            return None
