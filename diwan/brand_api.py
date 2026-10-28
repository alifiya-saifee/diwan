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
