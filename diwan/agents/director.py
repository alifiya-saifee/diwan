"""The Creative Director: looks at AI-made pictures before anyone is offered them. Each one is scored against the post, the
business and what wins for competitors. Below the bar it is redrawn; if it still fails it is not offered. It only judges;
it never decides on a person's behalf what gets published. If the look can't be done, the pictures say "not checked".
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from diwan import brand, business
from diwan.office import Office
from diwan.providers import meta

PASS_SCORE = 4  # out of 5: below this a picture goes back
SCHEMA = {"name": "creative_review", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["images"], "properties": {"images": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["n", "score", "problem"],
                               "properties": {"n": {"type": "integer"}, "score": {"type": "integer"}, "problem": {"type": "string"}}}}}}}


def _jpeg(path: str | Path) -> bytes:
    img = Image.open(path).convert("RGB")
    img.thumbnail((512, 512))
    out = BytesIO()
    img.save(out, "JPEG", quality=80)
    return out.getvalue()


def review(office: Office, title: str, what: str, paths: list[str]) -> dict | None:
    """{"score", "failed": {index: problem}} for the pictures, in order. None when they could not be looked at."""
    from diwan.agents import reader, style, taste
    if not paths or not meta.ready():
        return None
    system = ("You are a strict creative director at a top agency. You judge pictures for one social post. " + business.describe(office) + "\n" + brand.brief(office) + "\n" + style.brief(office) + "\n" + taste.brief(office) + "\n"
              "Score each picture from 1 to 5. 5 only if all of these hold: it is clearly about this post; it clearly belongs to this business, its trade and its place; "
              "it does not look like generic stock art or clip-art icons; it is on brand; any words are easy to read; it would hold up beside a leading competitor's best post. "
              "A picture that could belong to any company in any country scores 2 or lower. These are illustrations on purpose: they never show real named places, landmarks or people, "
              "so never mark one down for that, or for being a drawing. Judge whether it feels right for this trade and region and whether a viewer would stop for it. If it is under 4, problem says in one short line what is wrong; otherwise problem is empty.")
    try:
        got = meta.look(system, f"The post: {title}. It says: {what[:400]}\nWhat wins for competitors: {reader.winning(office)['line']}\n"
                                f"Pictures attached, numbered from 0, in order. Judge all {len(paths)}.", [_jpeg(p) for p in paths], SCHEMA, agent="mthumb")
    except (meta.MetaError, OSError, ValueError):
        return None
    marks = {r["n"]: r for r in got.get("images") or [] if isinstance(r.get("n"), int) and 0 <= r["n"] < len(paths)}
    if len(marks) < len(paths):
        return None  # a review that skipped a picture has not looked at it
    return {"score": round(sum(r["score"] for r in marks.values()) / len(marks), 1),
            "failed": {i: r["problem"] or "not good enough" for i, r in marks.items() if r["score"] < PASS_SCORE}}
