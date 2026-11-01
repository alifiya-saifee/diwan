"""Start Diwan on a host: everything that must survive a restart lives on the disk at DIWAN_DATA (default /data).

A host sits behind a proxy, so the owner's first password can't be set through the page (access.setup is local only).
DIWAN_OWNER_PASSWORD, in the host's settings and never in the repo, sets it once, on the first start.
"""
from __future__ import annotations

import os
from pathlib import Path

data = Path(os.environ.get("DIWAN_DATA", "/data"))
(data / "media").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DIWAN_DB", str(data / "diwan.db"))
os.environ.setdefault("DIWAN_MEDIA", str(data / "media"))
os.environ.setdefault("DIWAN_LOCAL_ASR", "0")  # Muse Voice transcribes; a small host can't hold the local Whisper model

import uvicorn  # noqa: E402

from diwan import access  # noqa: E402

password = os.environ.get("DIWAN_OWNER_PASSWORD")
if password and not access.has_password(access.owner_id()):
    access.set_password(access.owner_id(), password)

uvicorn.run("diwan.app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), proxy_headers=True, forwarded_allow_ips="*")
