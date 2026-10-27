"""Recorded replies. With keys present and DIWAN_TAPE=record, every live reply is saved here; without keys the same
request replays the saved reply, marked as a tape so no screen can pass it off as live.

A tape is keyed by the agent, the exact prompt and the schema, so a changed prompt never replays an old answer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from diwan.config import ROOT
from diwan.providers.chat import Reply

DIR = ROOT / "tapes"


def key(agent: str, system: str, user: str, schema: dict) -> str:
    raw = json.dumps([agent, system, user, schema], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def path(agent: str, k: str, root: Path | None = None) -> Path:
    return (root or DIR) / agent / f"{k}.json"


def load(agent: str, k: str, root: Path | None = None) -> Reply | None:
    p = path(agent, k, root)
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return Reply(d["data"], {**d["usage"], "provider": "tape", "recorded_from": d["usage"].get("provider")})


def save(agent: str, k: str, reply: Reply, root: Path | None = None) -> None:
    p = path(agent, k, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"data": reply.data, "usage": reply.usage}, ensure_ascii=False, indent=1))
