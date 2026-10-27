"""Settings from the environment, then a local .env. Keys are read here and never logged or printed."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env(name: str, default: str | None = None) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == name and v.strip():
                return v.strip().strip('"').strip("'")
    return default


def offline() -> bool:
    """DIWAN_OFFLINE=1 forces every agent onto recorded tapes, even when keys are present."""
    return env("DIWAN_OFFLINE") == "1"


def tape_mode() -> str:
    """off: live only. replay: live if possible, else tape. record: live, and save every reply to a tape."""
    return env("DIWAN_TAPE", "replay")
