"""Settings from the environment, then a local .env. Keys are read here and never logged or printed."""
from __future__ import annotations

import os
from contextvars import ContextVar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The test console runs Rania on a copy of the office. For that one request it can force rules only or a live model,
# and it always keeps every message in the sandbox, without touching the environment the rest of the server reads.
TRIAL: ContextVar[dict] = ContextVar("diwan_trial", default={})


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
    return TRIAL.get().get("offline", env("DIWAN_OFFLINE") == "1")


def tape_mode() -> str:
    """cache (default): a recorded reply first, else live and save it. replay: live if possible, else tape.
    record: live, and save every reply. off: live only."""
    return TRIAL.get().get("tape") or env("DIWAN_TAPE", "cache")


def sandbox_only() -> bool:
    """True inside a test-console run: nothing is sent to WhatsApp, Instagram or anyone's phone."""
    return bool(TRIAL.get().get("sandbox"))


# Settings a person may enter from the Settings screen. Values go into the local .env (never into the event log), and
# screens only ever learn whether each one is set.
SETTABLE = {"AISENSY_PROJECT_ID", "AISENSY_PROJECT_API_PWD", "AISENSY_API_KEY", "AISENSY_WEBHOOK_TOKEN",
            "WHATSAPP_PROVIDER", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET",
            "IG_ACCESS_TOKEN", "IG_USER_ID", "IG_VERIFY_TOKEN", "PUBLIC_BASE_URL",
            "HEYGEN_API_KEY", "HEYGEN_AVATAR_ID", "HEYGEN_VOICE_ID",
            "LISTING_FEED_URL", "PORTAL_SECRET_PROPERTYFINDER", "PORTAL_SECRET_BAYUT", "PORTAL_SECRET_DUBIZZLE", "NOTIFY_TEMPLATE",
            "ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"}


def set_env(updates: dict[str, str]) -> list[str]:
    """Write allowed settings into .env (mode 600). An empty value removes the setting. Returns the names changed."""
    bad = set(updates) - SETTABLE
    if bad:
        raise ValueError(f"not a setting: {', '.join(sorted(bad))}")
    f = ROOT / ".env"
    lines = f.read_text().splitlines() if f.exists() else []
    done = set()
    out = []
    for line in lines:
        k = line.partition("=")[0].strip()
        if k in updates:
            done.add(k)
            if updates[k]:
                out.append(f"{k}={updates[k]}")
            continue
        out.append(line)
    out += [f"{k}={v}" for k, v in updates.items() if k not in done and v]
    f.write_text("\n".join(out) + "\n")
    f.chmod(0o600)
    for k, v in updates.items():
        os.environ.pop(k, None)
    return sorted(updates)
