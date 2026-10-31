"""Zoom meetings for online appointments (docs/calendar-basics-spec.md), through a Server-to-Server OAuth app made in
the office's own Zoom account (ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET in .env).

  POST https://zoom.us/oauth/token?grant_type=account_credentials&account_id=…   basic auth client id : secret
  POST   https://api.zoom.us/v2/users/me/meetings      a scheduled meeting (type 2)
  PATCH  https://api.zoom.us/v2/meetings/{id}           a new time
  DELETE https://api.zoom.us/v2/meetings/{id}
The token lives about an hour and is kept in memory only. Nothing is retried silently: a refusal is raised with Zoom's
reason, and the caller records it.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from diwan.config import env

KEYS = ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET")
API = "https://api.zoom.us/v2"
TRANSPORT = None  # tests put a stand-in here; never set in the app
_token: dict = {}


class ZoomError(RuntimeError):
    pass


def missing() -> list[str]:
    return [k for k in KEYS if not env(k)]


def available() -> bool:
    return not missing()


def _client() -> httpx.Client:
    return httpx.Client(transport=TRANSPORT, timeout=20)


def _check(r: httpx.Response, what: str) -> dict:
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") and r.content else {}
    if r.status_code >= 300:
        raise ZoomError(f"Zoom refused {what} ({r.status_code}): {str(data.get('message') or data.get('reason') or r.text)[:200]}")
    return data


def token() -> str:
    if not available():
        raise ZoomError("Zoom is not connected: " + ", ".join(missing()))
    if _token.get("key") == env("ZOOM_CLIENT_ID") and _token.get("until", 0) > time.time() + 60:
        return _token["value"]
    with _client() as c:
        r = c.post("https://zoom.us/oauth/token", params={"grant_type": "account_credentials", "account_id": env("ZOOM_ACCOUNT_ID")},
                   auth=(env("ZOOM_CLIENT_ID"), env("ZOOM_CLIENT_SECRET")))
    data = _check(r, "the sign-in")
    _token.update(key=env("ZOOM_CLIENT_ID"), value=data["access_token"], until=time.time() + int(data.get("expires_in", 3600)))
    return data["access_token"]


def _utc(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create(topic: str, start: datetime, minutes: int) -> dict:
    """A scheduled meeting with a waiting room; returns {id, url}."""
    with _client() as c:
        r = c.post(f"{API}/users/me/meetings", headers={"Authorization": f"Bearer {token()}"},
                   json={"topic": topic[:200], "type": 2, "start_time": _utc(start), "duration": minutes, "timezone": "UTC",
                         "settings": {"waiting_room": True, "join_before_host": False}})
    data = _check(r, "the meeting")
    return {"id": str(data["id"]), "url": data["join_url"]}


def move(mid: str, start: datetime, minutes: int) -> None:
    with _client() as c:
        r = c.patch(f"{API}/meetings/{mid}", headers={"Authorization": f"Bearer {token()}"},
                    json={"start_time": _utc(start), "duration": minutes, "timezone": "UTC"})
    _check(r, "the new time")


def delete(mid: str) -> None:
    with _client() as c:
        r = c.delete(f"{API}/meetings/{mid}", headers={"Authorization": f"Bearer {token()}"})
    if r.status_code != 404:  # already gone is fine
        _check(r, "the cancellation")
