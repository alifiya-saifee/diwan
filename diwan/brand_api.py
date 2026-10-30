"""The brand profile over HTTP: read it, save it, or have the Brand brain draft one for a person to edit."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
from pydantic import BaseModel

from diwan import brand

router = APIRouter()


def _office():
    from diwan.app import S
    return S.office


@router.get("/api/brand")
def get_brand():
    return {"fields": [{"key": k, "label": lab, "hint": hint, "list": lst} for k, (lab, hint, lst) in brand.FIELDS.items()],
            "profile": brand.profile(_office()), "set": brand.is_set(_office()), "used_by": brand.USED_BY}


class BrandIn(BaseModel):
    values: dict
    by: str = "maya"
    via: str = "typed"


@router.post("/api/brand")
def save_brand(body: BrandIn):
    changed = brand.save(_office(), body.values, by=body.by, via=body.via)
    return {"ok": True, "changed": changed}


@router.post("/api/brand/draft")
async def draft_brand():
    """One model call; nothing is saved until a person presses Save."""
    try:
        return await asyncio.to_thread(brand.draft, _office())
    except Exception as e:  # the model failed or timed out: say so, keep what was typed
        return {"needs": f"The draft failed: {str(e)[:160]}. You can type the profile yourself."}


@router.get("/api/memory/marketing")
def marketing_memory(upto: int | None = None):
    """The marketing team's memory as a graph, rewindable to any event."""
    from diwan.brain import marketing_graph
    return marketing_graph(_office(), upto)


class LearnIn(BaseModel):
    urls: list[str] = []
    document: str = ""          # pasted text: a company profile, a brochure
    document_name: str = "company profile"
    company: str = ""
    by: str = "maya"


@router.post("/api/brand/learn")
async def learn_company(body: LearnIn):
    """The Brand brain reads public pages and proposes knowledge cards (each proven by a quote) and a brand draft."""
    from diwan import learn
    try:
        docs = {body.document_name or "company profile": body.document} if body.document.strip() else {}
        return await asyncio.to_thread(learn.learn, _office(), body.urls[:6], documents=docs, by=body.by, company=body.company)
    except Exception as e:
        return {"needs": f"Reading the pages failed: {str(e)[:160]}"}


@router.get("/api/brand/demo-profile")
def demo_profile():
    """The fictional company profile the demo learns from."""
    from pathlib import Path
    return {"name": "Diwan Realty company profile", "text": (Path(__file__).parent / "demo_profile.md").read_text()}


@router.get("/api/business")
def get_business():
    """What business we are and where, with every country and its time zones to pick from."""
    from diwan import business
    from diwan.agents import studio
    return {"fields": [{"key": k, "label": lab, "hint": hint} for k, (lab, hint) in business.FIELDS.items()],
            "profile": business.profile(_office()), "missing": business.missing(_office()), "countries": business.countries(),
            "platforms_known": list(studio.LIMITS)}


class BusinessIn(BaseModel):
    values: dict
    by: str = "maya"


@router.post("/api/business")
def save_business(body: BusinessIn):
    from diwan import business
    try:
        return {"ok": True, "changed": business.save(_office(), body.values, by=body.by), "business": business.get(_office())}
    except business.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/studio/why/read")
async def read_posts():
    """Muse Spark reads the competitor posts not read yet (paid, Marketing's budget); nothing is read twice."""
    from diwan.agents import reader
    try:
        r = await asyncio.to_thread(reader.read, _office())
    except Exception as e:
        return {"needs": f"Reading failed: {str(e)[:160]}"}
    return r | {"why": reader.patterns(_office())}


@router.get("/api/studio/style")
def style_notes():
    from diwan.agents import style
    return {"notes": style.notes(_office()), "deleted": [n for n in style.notes(_office(), all_=True) if n["id"] in style.deleted(_office())]}


class NoteIn(BaseModel):
    note: str
    by: str = "maya"


@router.post("/api/studio/style/delete")
def delete_note(body: NoteIn):
    from diwan.agents import style
    try:
        style.delete(_office(), body.note, by=body.by)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}


@router.post("/api/studio/style/restore")
def restore_note(body: NoteIn):
    from diwan.agents import style
    style.restore(_office(), body.note, by=body.by)
    return {"ok": True}


@router.get("/api/studio/rhythm")
def get_rhythm():
    from diwan.agents import rhythm
    return {"settings": rhythm.settings(_office()), "labels": rhythm.LABELS, "rhythms": list(rhythm.EVERY), "next": rhythm.next_run(_office())}


class RhythmIn(BaseModel):
    values: dict
    by: str = "maya"


@router.post("/api/studio/rhythm")
def save_rhythm(body: RhythmIn):
    from diwan.agents import rhythm
    try:
        return {"ok": True, "changed": rhythm.save(_office(), body.values, by=body.by), "next": rhythm.next_run(_office())}
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/studio/plan/week")
def plan_week(by: str = "maya"):
    """Plan from today by hand, on the current rhythm (weekly: the next 7 days). Nothing is written until each day."""
    from datetime import datetime, timezone
    from diwan import business
    from diwan.agents import rhythm
    return rhythm.make_plan(_office(), business.local(datetime.now(timezone.utc), _office()).date(), auto=False, by=by)


class MoveIn(BaseModel):
    day: str
    step: int
    by: str = "maya"


@router.post("/api/studio/plan/move")
def plan_move(body: MoveIn):
    from diwan.agents import rhythm
    try:
        return {"ok": True, "plan": rhythm.move(_office(), body.day, body.step, by=body.by)}
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/studio/our-ads")
async def our_ads():
    """Our own ad account's last 30 days, read-only."""
    from diwan.providers import ads
    if not ads.ready():
        return {"ok": False, "needs": f"Our ads need {', '.join(ads.missing()) or 'online mode'} in .env."}
    try:
        return {"ok": True} | await asyncio.to_thread(ads.report)
    except ads.AdsError as e:
        return {"ok": False, "needs": f"Meta refused: {e}"}


@router.get("/api/studio/approvers")
def get_approvers():
    from diwan.agents import approvers
    return {"roles": approvers.ROLES, "set": approvers.get(_office()), "team": approvers.team()}


class ApproversIn(BaseModel):
    values: dict
    by: str = "layla"


@router.post("/api/studio/approvers")
def save_approvers(body: ApproversIn):
    from diwan.agents import approvers
    try:
        return {"ok": True, "changed": approvers.save(_office(), body.values, by=body.by)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
