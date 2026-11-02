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


def _guard(what: str, agent: str) -> None:
    """Every paid Meta service stops at its part's monthly budget, like the chat calls."""
    from diwan import costs
    if not costs.allowed(agent):
        raise MetaError(f"this month's model budget (USD {costs.budget(costs.part_of(agent)):g}) is used up, so no {what}")


def _usage(d: dict) -> dict:
    u = d.get("usage") or {}
    return {"provider": "meta", "model": d.get("model"), "input_tokens": u.get("input_tokens") or u.get("prompt_tokens"),
            "output_tokens": u.get("output_tokens") or u.get("completion_tokens"),
            "reasoning_tokens": (u.get("output_tokens_details") or u.get("completion_tokens_details") or {}).get("reasoning_tokens")}


def _send(path: str, body: dict, timeout: float) -> httpx.Response:
    """A call that took too long or lost the line is a failure the caller can report, not a crash of the whole run."""
    try:
        with _client(timeout) as c:
            return c.post(f"{_base()}{path}", json=body)
    except httpx.HTTPError as e:
        raise MetaError(f"Muse did not answer in time or the line dropped ({type(e).__name__})") from None


def search(prompt: str, *, country: str = "", timeout: float = 120, agent: str = "mtrend", max_searches: int | None = None) -> dict:
    """{text (the final answer only), sources[{title,url,snippet}], cited[{title,url}], queries} from Muse Spark with web search.
    Paid: the tokens plus a fee per search, written to the ledger and stopped at the budget. The number of searches is capped
    in the request (DIWAN_MAX_SEARCHES, 3): a prompt's "use at most two searches" alone was ignored, up to 26 searches a call."""
    from diwan import costs
    _guard("web search", agent)
    cap = max_searches or int(env("DIWAN_MAX_SEARCHES", "3"))
    body = {"model": env("META_MODEL_SPARK", "muse-spark-1.3"), "input": prompt, "include": ["web_search_call.results"], "max_tool_calls": cap,
            "tools": [{"type": "web_search", "search_context_size": env("DIWAN_SEARCH_CONTEXT", "low"),
                       **({"user_location": {"type": "approximate", "country": country}} if country else {})}]}
    t0 = time.monotonic()
    r = _send("/responses", body, timeout)
    if r.status_code == 400 and "max_tool_calls" in r.text:  # an endpoint without the cap: ask again without it
        body.pop("max_tool_calls")
        r = _send("/responses", body, timeout)
    if r.status_code != 200:
        raise MetaError(f"web search returned {r.status_code}: {r.text[:200]}")
    text, sources, cited, queries = [], [], [], []
    d = r.json()
    searches = sum(1 for item in d.get("output", []) if item.get("type") == "web_search_call")
    costs.record(agent, _usage(d), extra_usd=searches * costs.fee("search", 0.01), what=f"web search x{searches}")
    for item in d.get("output", []):
        if item.get("type") == "web_search_call":
            queries.append((item.get("action") or {}).get("query") or item.get("query"))
            sources += [{"title": x.get("title"), "url": x.get("url"), "snippet": x.get("snippet")} for x in item.get("results") or []]
        for part in item.get("content") or []:
            if part.get("type") == "output_text":
                text.append(part.get("text", ""))  # each message; the model narrates between searches, so only the last is the answer
                cited += [{"title": a.get("title"), "url": a.get("url")} for a in part.get("annotations") or [] if a.get("type") == "url_citation"]
    return {"text": text[-1] if text else "", "sources": sources, "cited": cited, "queries": [q for q in queries if q],
            "latency_ms": round((time.monotonic() - t0) * 1000)}


def look(system: str, text: str, images: list[bytes], schema: dict, *, agent: str, timeout: float = 180) -> dict:
    """Muse Spark reads text plus pictures (JPEG bytes, sent as data URIs) and answers JSON matching `schema`
    ({"name", "schema", "strict"}). Paid by tokens; stopped at the budget."""
    from diwan import costs
    from diwan.providers.chat import parse_json
    _guard("image reading", agent)
    content = [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(b).decode()}}
                                                 for b in images]
    body = {"model": env("META_MODEL_SPARK", "muse-spark-1.3"), "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "response_format": {"type": "json_schema", "json_schema": schema}, "reasoning_effort": "low", "max_tokens": 6000}
    r = _send("/chat/completions", body, timeout)
    if r.status_code != 200:
        raise MetaError(f"Muse Spark returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    costs.record(agent, _usage(d), what=f"read {len(images)} image{'s' if len(images) != 1 else ''}")
    try:
        return parse_json(d["choices"][0]["message"].get("content") or "")
    except Exception as e:
        raise MetaError(f"Muse Spark's answer was not the JSON asked for: {e}") from None


def image(prompt: str, name: str, size: str = "1024x1792") -> str:
    """Generate with Muse Image, save under media/, return the served path. Paid per image; stopped at the budget."""
    from diwan import costs
    _guard("image", "mthumb")
    r = _send("/images/generations", {"model": env("META_MODEL_IMAGE", "muse-image-1.0"), "prompt": prompt[:3000], "n": 1, "size": size, "response_format": "b64_json"}, 120)
    if r.status_code != 200:
        raise MetaError(f"Muse Image returned {r.status_code}: {r.text[:200]}")
    MEDIA.mkdir(exist_ok=True)
    costs.record("mthumb", {"provider": "meta", "model": env("META_MODEL_IMAGE", "muse-image-1.0")}, extra_usd=costs.fee("image", 0.04), what="image")
    path = MEDIA / f"{name}.webp"
    path.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
    return f"/media/{path.name}"


def transcribe(wav: bytes, *, mode: str = "DIARIZATION") -> dict:
    """A recorded clip (mono 16-bit WAV) → {"text", "turns": [{"speaker","text","start","end"}]} as far as the API gives them."""
    from diwan import costs
    _guard("transcription", "mtrans")
    req = {"model": env("META_MODEL_VOICE", "muse-voice-transcribe-1.0"), "mode": mode, "audioEncoding": "WAV"}
    with _client(180) as c:
        r = c.post(f"{_base()}/asr/transcribe", files={"request": (None, json.dumps(req), "application/json"), "audio": ("clip.wav", wav, "audio/wav")})
    if r.status_code != 200:
        raise MetaError(f"Voice Transcribe returned {r.status_code}: {r.text[:200]}")
    d = r.json()
    minutes = max(len(wav) - 44, 0) / 32_000 / 60  # 16 kHz, 16-bit mono
    costs.record("mtrans", {"provider": "meta", "model": req["model"]}, extra_usd=round(minutes, 3) * costs.fee("asr_minute", 0.006), what=f"transcription {minutes:.1f} min")
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
