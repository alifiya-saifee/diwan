"""HeyGen: an AI presenter reads an approved script. Off until HEYGEN_API_KEY, HEYGEN_AVATAR_ID and HEYGEN_VOICE_ID are set.

The avatar must be of a person who agreed to it (HeyGen asks for that consent when a custom avatar is made); each
generation is started by a person in the studio, who confirms that consent, and it is recorded.

  POST https://api.heygen.com/v2/video/generate   (X-Api-Key) → {"data": {"video_id"}}
  GET  https://api.heygen.com/v1/video_status.get?video_id=…  → {"data": {"status": "completed", "video_url"}}
"""
from __future__ import annotations

import httpx

from diwan.config import env

BASE = "https://api.heygen.com"
TRANSPORT: httpx.BaseTransport | None = None


class HeyGenError(RuntimeError):
    pass


def missing() -> list[str]:
    return [k for k in ("HEYGEN_API_KEY", "HEYGEN_AVATAR_ID", "HEYGEN_VOICE_ID") if not env(k)]


def ready() -> bool:
    return not missing()


def _client() -> httpx.Client:
    if not ready():
        raise HeyGenError("needs " + ", ".join(missing()))
    return httpx.Client(transport=TRANSPORT, timeout=60, headers={"X-Api-Key": env("HEYGEN_API_KEY")})


def generate(script: str, *, width: int = 720, height: int = 1280, title: str = "") -> str:
    body = {"title": title[:80], "dimension": {"width": width, "height": height},
            "video_inputs": [{"character": {"type": "avatar", "avatar_id": env("HEYGEN_AVATAR_ID"), "avatar_style": "normal"},
                              "voice": {"type": "text", "input_text": script[:4500], "voice_id": env("HEYGEN_VOICE_ID")}}]}
    with _client() as c:
        r = c.post(f"{BASE}/v2/video/generate", json=body)
    d = r.json() if r.content else {}
    if r.status_code >= 300 or d.get("error"):
        raise HeyGenError(str((d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else d.get("error") or r.text[:200]))
    return d["data"]["video_id"]


def status(video_id: str) -> tuple[str, str | None]:
    with _client() as c:
        r = c.get(f"{BASE}/v1/video_status.get", params={"video_id": video_id})
    d = (r.json() if r.content else {}).get("data") or {}
    return d.get("status", "unknown"), d.get("video_url")


def download(url: str) -> bytes:
    with httpx.Client(transport=TRANSPORT, timeout=120, follow_redirects=True) as c:
        r = c.get(url)
    if r.status_code >= 300:
        raise HeyGenError(f"could not download the video ({r.status_code})")
    return r.content
