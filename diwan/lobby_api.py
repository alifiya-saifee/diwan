"""The Lobby room over HTTP (diwan/lobby_room.py). Everyone reads; the Sales lead and the owner propose; only the owner decides."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from diwan import lobby_room as room

router = APIRouter()


def _office():
    from diwan.app import S
    return S.office


def _call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except KeyError as e:
        raise HTTPException(404, f"Nothing called {e.args[0]}") from None
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class By(BaseModel):
    by: str
    reason: str = ""


class Draft(BaseModel):
    by: str
    draft: dict[str, Any]


class Edits(BaseModel):
    by: str
    edits: dict[str, Any] = {}


@router.get("/api/lobby-room")
def view(by: str = "layla"):
    return room.room(_office(), by)


@router.post("/api/lobby-room/propose")
def propose(body: Draft):
    return {"id": _call(room.propose, _office(), body.draft, by=body.by)}


@router.post("/api/lobby-room/playbooks")
def add_playbook(body: Draft):
    return {"id": _call(room.add_playbook, _office(), body.draft, by=body.by)}


@router.post("/api/lobby-room/playbooks/{pb}/remove")
def remove_playbook(pb: str, body: By):
    _call(room.remove_playbook, _office(), pb, by=body.by)
    return {"ok": True}


@router.post("/api/lobby-room/threads/run")
def run_threads(body: By):
    if not room.PEOPLE.get(body.by, {}).get("role") == "Owner":
        raise HTTPException(403, "Only the owner runs the week's threads early")
    return {"threads": _call(room.run_week, _office())}


@router.post("/api/lobby-room/rules")
def rules(body: Draft):
    return _call(room.set_settings, _office(), body.draft, by=body.by)


@router.post("/api/lobby-room/{xid}/approve")
def approve(xid: str, body: Edits):
    return _call(room.approve, _office(), xid, by=body.by, edits=body.edits)


@router.post("/api/lobby-room/{xid}/refuse")
def refuse(xid: str, body: By):
    _call(room.refuse, _office(), xid, by=body.by, reason=body.reason)
    return {"ok": True}


@router.post("/api/lobby-room/{xid}/keep")
def keep(xid: str, body: By):
    _call(room.finish, _office(), xid, "kept", by=body.by, reason=body.reason)
    return {"ok": True}


@router.post("/api/lobby-room/{xid}/rollback")
def rollback(xid: str, body: By):
    _call(room.finish, _office(), xid, "rolled back", by=body.by, reason=body.reason)
    return {"ok": True}
