"""Start Diwan on a host: everything that must survive a restart lives on the disk at DIWAN_DATA (default /data).

A host sits behind a proxy, so the owner's first password can't be set through the page (access.setup is local only).
DIWAN_OWNER_PASSWORD, in the host's settings and never in the repo, sets it once, on the first start.

DIWAN_TEAM_PASSWORD is for a public demo on a host with no lasting disk (the office is fictional and starts fresh each
time): every person without a login gets that password, so the demo people can always sign in. Never with Supabase logins.
"""
from __future__ import annotations

import os
from pathlib import Path

data = Path(os.environ.get("DIWAN_DATA", "/data"))
(data / "media").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DIWAN_DB", str(data / "diwan.db"))
os.environ.setdefault("DIWAN_MEDIA", str(data / "media"))
os.environ.setdefault("DIWAN_LOCAL_ASR", "0")  # Muse Voice transcribes; a small host can't hold the local Whisper model

from diwan import access  # noqa: E402
from diwan.people import PEOPLE  # noqa: E402


def logins() -> list[str]:
    """The passwords the host's settings give, for whoever has none yet. Returns who got one."""
    given = []
    password = os.environ.get("DIWAN_OWNER_PASSWORD")
    if password and not access.has_password(access.owner_id()):
        access.set_password(access.owner_id(), password)
        given.append(access.owner_id())
    team = os.environ.get("DIWAN_TEAM_PASSWORD")
    if team and not access.supabase():
        for p in PEOPLE:
            if not access.has_password(p):
                access.set_password(p, team)
                given.append(p)
    return given


if __name__ == "__main__":
    import uvicorn

    logins()
    uvicorn.run("diwan.app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), proxy_headers=True, forwarded_allow_ips="*")
