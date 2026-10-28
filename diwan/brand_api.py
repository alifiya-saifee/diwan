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
