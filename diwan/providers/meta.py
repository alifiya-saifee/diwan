"""Meta Model API beyond chat: web search with citations (Muse Spark, Responses API), images (Muse Image) and recorded
audio (Muse Voice Transcribe, file API). Each raises MetaError when it cannot run, with the reason; callers record that
as a blocked step, never as invented output.
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx

from diwan.config import ROOT, env, offline

TRANSPORT: httpx.BaseTransport | None = None  # tests swap in a fake
MEDIA = Path(env("DIWAN_MEDIA") or ROOT / "media")  # a test server keeps its files apart


class MetaError(RuntimeError):
    pass


def key() -> str | None:
    return env("META_API_KEY") or env("MODEL_API_KEY")


def ready() -> bool:
    return bool(key()) and not offline()


def _base() -> str:
    return env("META_API_BASE", "https://api.meta.ai/v1")


def _client(timeout: float) -> httpx.Client:
    if not ready():
        raise MetaError("needs META_API_KEY")
    return httpx.Client(transport=TRANSPORT, timeout=timeout, headers={"Authorization": f"Bearer {key()}"})


def search(prompt: str, *, country: str = "AE", timeout: float = 120) -> dict:
    """{text, sources[{title,url,snippet}], cited[{title,url}], queries} from Muse Spark with web search."""
    body = {"model": env("META_MODEL_SPARK", "muse-spark-1.3"), "input": prompt, "include": ["web_search_call.results"],
            "tools": [{"type": "web_search", "search_context_size": "medium", "user_location": {"type": "approximate", "country": country}}]}
    t0 = time.monotonic()
    with _client(timeout) as c:
        r = c.post(f"{_base()}/responses", json=body)
    if r.status_code != 200:
        raise MetaError(f"web search returned {r.status_code}: {r.text[:200]}")
    text, sources, cited, queries = [], [], [], []
    for item in r.json().get("output", []):
        if item.get("type") == "web_search_call":
            queries.append((item.get("action") or {}).get("query") or item.get("query"))
            sources += [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("snippet")} for x in item.get("results") or []]
        for part in item.get("content") or []:
            if part.get("type") == "output_text":
                text.append(part.get("text", ""))
                cited += [{"title": a.get("title"), "url": a.get("url")} for a in part.get("annotations") or [] if a.get("type") == "url_citation"]
    return {"text": "\n".join(text), "sources": sources, "cited": cited, "queries": [q for q in queries if q],
            "latency_ms": round((time.monotonic() - t0) * 1000)}


def image(prompt: str, name: str, size: str = "1024x1792") -> str:
    """Generate with Muse Image, save under media/, return the served path."""
    with _client(120) as c:
        r = c.post(f"{_base()}/images/generations", json={"model": env("META_MODEL_IMAGE", "muse-image-1.0"), "prompt": prompt[:3000],
                                                          "n": 1, "size": size, "response_format": "b64_json"})
    if r.status_code != 200:
        raise MetaError(f"Muse Image returned {r.status_code}: {r.text[:200]}")
    MEDIA.mkdir(exist_ok=True)
    path = MEDIA / f"{name}.webp"
    path.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
    return f"/media/{path.name}"


def transcribe(wav: bytes, *, mode: str = "DIARIZATION") -> dict:
    """A recorded clip (mono 16-bit WAV) → {"text", "turns": [{"speaker","text","start","end"}]} as far as the API gives them."""
    req = {"model": env("META_MODEL_VOICE", "muse-voice-transcribe-1.0"), "mode": mode, "audioEncoding": "WAV"}
    with _client(180) as c:
        r = c.post(f"{_base()}/asr/transcribe", files={"request": (None, json.dumps(req), "application/json"), "audio": ("clip.wav", wav, "audio/wav")})
    if r.status_code != 200:
        raise MetaError(f"Voice Transcribe returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    turns = d.get("turns") or d.get("segments") or []
    norm = [{"speaker": t.get("speaker") or t.get("label"), "text": (t.get("transcript") or t.get("text") or "").strip(),
             "start": _sec(t, "start"), "end": _sec(t, "end")} for t in turns]
    text = d.get("transcript") or d.get("text") or " ".join(t["text"] for t in norm)
    return {"text": text.strip(), "turns": [t for t in norm if t["text"]]}


def _sec(t: dict, k: str) -> float | None:
    """Seconds from `start`/`end`, or from `startMs`/`endMs`."""
    if isinstance(t.get(k), (int, float)):
        return float(t[k])
    ms = t.get(f"{k}Ms")
    return ms / 1000 if isinstance(ms, (int, float)) else None


def media_path(served: str) -> Path:
    return MEDIA / Path(served).name
