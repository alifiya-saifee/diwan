"""Marketing's media kept in Supabase Storage as well as on this server: every picture, carousel slide, cover, video and
the logo is uploaded once it is made, so a new server or a wiped disk does not lose them.

  POST {SUPABASE_URL}/storage/v1/object/{bucket}/{name}    service key    the file (x-upsert: the same name is replaced)

The bucket is created by a person in Supabase (Storage → New bucket) and named in .env as SUPABASE_BUCKET; nothing here
creates one or makes one public. The service key stays on the server and is never logged or sent to a page.

Saving is not publishing: these copies are never used to post to Instagram (that still needs PUBLIC_BASE_URL).
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from diwan.config import env

KEYS = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SUPABASE_BUCKET")
TRANSPORT = None  # tests put a stand-in here; never set in the app


class StorageError(RuntimeError):
    pass


def missing() -> list[str]:
    return [k for k in KEYS if not env(k)]


def ready() -> bool:
    return not missing()


def public_url(name: str) -> str:
    return f"{env('SUPABASE_URL').rstrip('/')}/storage/v1/object/public/{env('SUPABASE_BUCKET')}/{name}"


def put(path: str | Path, name: str | None = None) -> str:
    """Upload one file; returns its name in the bucket."""
    p = Path(path)
    name = name or p.name
    kind = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    key = env("SUPABASE_SERVICE_KEY")
    with httpx.Client(transport=TRANSPORT, timeout=120) as c:
        r = c.post(f"{env('SUPABASE_URL').rstrip('/')}/storage/v1/object/{env('SUPABASE_BUCKET')}/{name}", content=p.read_bytes(),
                   headers={"Authorization": f"Bearer {key}", "apikey": key, "Content-Type": kind, "x-upsert": "true"})
    if r.status_code not in (200, 201):
        raise StorageError(f"Supabase Storage returned {r.status_code}: {r.text[:160]}")
    return name


def files_in(data) -> list[Path]:
    """The media files a made thing points at (any "/media/<file>" it carries), that exist here."""
    from diwan.providers import meta
    found: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and x.startswith("/media/"):
            found.append(x.removeprefix("/media/"))
    walk(data)
    return [p for n in dict.fromkeys(found) if (p := meta.MEDIA / n).is_file()]
