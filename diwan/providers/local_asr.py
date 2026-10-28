"""Local speech-to-text (faster-whisper on this machine), a development fallback for when no Meta key is set.
Muse Voice Transcribe is always used first; anything transcribed here is labelled "local Whisper"."""
from __future__ import annotations

import io
import wave

from diwan.config import env

_model = None


def available() -> bool:
    if env("DIWAN_LOCAL_ASR") == "0":
        return False
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribe(wav: bytes) -> dict:
    import numpy as np
    from faster_whisper import WhisperModel
    global _model
    if _model is None:
        _model = WhisperModel(env("LOCAL_ASR_MODEL", "base"), device="cpu", compute_type="int8")
    w = wave.open(io.BytesIO(wav))
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    segs, _ = _model.transcribe(audio, beam_size=3, vad_filter=True)
    turns = [{"speaker": None, "text": s.text.strip(), "start": float(s.start), "end": float(s.end)} for s in segs if s.text.strip()]
    return {"text": " ".join(t["text"] for t in turns), "turns": turns}
