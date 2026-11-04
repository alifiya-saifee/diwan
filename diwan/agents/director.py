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


AGAINST = {"name": "creative_review", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["images", "against"], "properties": {
    "images": SCHEMA["schema"]["properties"]["images"], "against": {"type": "string"}}}}


def review(office: Office, title: str, what: str, paths: list[str], against: list[dict] | None = None) -> dict | None:
    """{"score", "failed": {index: problem}, "against"} for the pictures, in order. None when they could not be looked at.
    `against` is the competitors' best posts for the same thing (occasions.study): their pictures are shown after ours,
    a 5 means ours holds up beside them, and `against` says in one line how ours compares."""
    from diwan.agents import reader, style, taste
    if not paths or not meta.ready():
        return None
    refs = [(p, c) for p in (against or []) if (c := reader._cover(p.get("thumb")))]
    if refs:
        system = ("You are a strict creative director at a top agency. You judge pictures for one social post. " + business.describe(office) + "\n" + brand.brief(office) + "\n"
                  "Score each of OUR pictures from 1 to 5. 5 only if it is clearly about this post, clearly this business's, on brand, its words easy to read, not generic "
                  "stock or clip-art, and at least as strong as the best competitor post shown after ours. If it is under 4, problem says in one short line what is wrong; "
                  "otherwise problem is empty. against: one sentence comparing ours with theirs, naming what theirs does better if anything.")
        try:
            got = meta.look(system, f"The post: {title}. It says: {what[:400]}\nOur pictures are numbered from 0: judge all {len(paths)}. After them come "
                                    f"{len(refs)} competitor posts for the same day, for comparison only: "
                                    + "; ".join(f"@{p['account']} ({p['likes']} likes)" for p, _ in refs),
                            [_jpeg(p) for p in paths] + [c for _, c in refs], AGAINST, agent="mthumb")
        except (meta.MetaError, OSError, ValueError):
            got = None
        if got:
            marks = {r["n"]: r for r in got.get("images") or [] if isinstance(r.get("n"), int) and 0 <= r["n"] < len(paths)}
            if len(marks) == len(paths):
                return {"score": round(sum(r["score"] for r in marks.values()) / len(marks), 1), "against": (got.get("against") or "")[:240],
                        "failed": {i: r["problem"] or "not good enough" for i, r in marks.items() if r["score"] < PASS_SCORE}}
    system = ("You are a strict creative director at a top agency. You judge pictures for one social post. " + business.describe(office) + "\n" + brand.brief(office) + "\n" + style.brief(office) + "\n" + taste.brief(office) + "\n"
              "Score each picture from 1 to 5. 5 only if all of these hold: it is clearly about this post; it clearly belongs to this business, its trade and its place; "
              "it does not look like generic stock art or clip-art icons; it is on brand; any words are easy to read; it would hold up beside a leading competitor's best post. "
              "A picture that could belong to any company in any country scores 2 or lower. They never show recognisable faces, so never mark one down for that. Mark down anything that looks painted, drawn, cartoonish or like a 3D render: it should look like real estate photography. "
              "When the post names a place, the picture must look like that place (its skyline, water, streets); a generic city scores 2 or lower. Judge whether it feels right for this trade and region and whether a viewer would stop for it. If it is under 4, problem says in one short line what is wrong; otherwise problem is empty.")
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


DONE_SCHEMA = {"name": "change_check", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["done", "how"],
               "properties": {"done": {"type": "boolean"}, "how": {"type": "string"}}}}


def done(office: Office, asked: str, before: list[str], after: list[str]) -> dict | None:
    """Did the new pictures do what the person asked? {done, how}: how says in one line what changed, or what didn't.
    It looks at both versions, so "make it festive" is judged by what is on the picture, not by what the code meant to do."""
    if not before or not after or not meta.ready():
        return None
    try:
        got = meta.look("You check a designer's revision for a client. The client asked for one change. The first pictures are BEFORE, the rest AFTER. "
                        "done is true only if the AFTER pictures clearly do what was asked and nothing the client didn't ask for got worse. "
                        "how: one short sentence the client reads, saying what changed, or what is still not done.",
                        f"The client asked: {asked[:300]}\nBEFORE: {len(before)} picture(s), then AFTER: {len(after)} picture(s).",
                        [_jpeg(p) for p in before] + [_jpeg(p) for p in after], DONE_SCHEMA, agent="mthumb")
    except (meta.MetaError, OSError, ValueError):
        return None
    return {"done": bool(got.get("done")), "how": (got.get("how") or "")[:240]} if isinstance(got.get("done"), bool) else None


SCRIPT_SCHEMA = {"name": "script_review", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["score", "why", "fix"],
                 "properties": {"score": {"type": "integer"}, "why": {"type": "string"}, "fix": {"type": "string"}}}}


def script(office: Office, sc: dict, what: str) -> dict | None:
    """The same strict eye on a script before anyone is offered it: {score 1-5, why, fix}. None when it can't be judged.
    It never sees which writer made it, and it never rewrites: the Script writer does, with `fix` as the note."""
    if not meta.ready():
        return None
    from diwan.agents import reader
    system = ("You are a demanding head of marketing at a top agency judging one short social video or post script, blind. " + business.describe(office) + "\n"
              + brand.brief(office) + "\nScore 1 to 5. Most work is a 3. 5 only if you would publish it untouched: the first 1.5 seconds stop a scroll with a "
              "specific number, place or surprising detail (never the title read back, never 'Looking for...?' or 'Imagine...'); every line adds a new, concrete "
              "fact a viewer cares about; nothing is said twice; it sounds like a person talking, in this brand's voice; it is right for the post's job (a greeting "
              "greets and never sells); a filmer could shoot it. why: one sentence. fix: the one change that would most raise the score, as an instruction to the writer.")
    try:
        got = meta.look(system, f"The post: {what[:600]}\nWhat wins for competitors: {reader.winning(office)['line']}\n\nHook: {sc.get('hook_en', '')}\n"
                                + "\n".join(sc.get("lines_en") or []), [], SCRIPT_SCHEMA, agent="mscript")
    except (meta.MetaError, OSError, ValueError):
        return None
    if not isinstance(got.get("score"), int):
        return None
    return {"score": max(1, min(5, got["score"])), "why": (got.get("why") or "")[:240], "fix": (got.get("fix") or "")[:300]}


PICK_SCHEMA = {"name": "hook_pick", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["best", "why"],
               "properties": {"best": {"type": "integer"}, "why": {"type": "string"}}}}


def best_hook(office: Office, hooks: list[str], lines: list[str], what: str) -> int | None:
    """Which opening (numbered from 0) would most stop a buyer scrolling, for the same script. None when it can't be judged."""
    if not meta.ready() or len(hooks) < 2:
        return None
    try:
        got = meta.look("You are a demanding head of marketing at a top agency. Choose the one opening that would most make a buyer stop scrolling and keep "
                        "watching, for this business and this post: specific beats vague, about the viewer beats about us, never 'Looking for...?' or 'Imagine...'. "
                        + business.describe(office), f"The post: {what[:800]}\nThe rest of the script: {' / '.join(lines)}\n\n"
                        + "\n".join(f"{i}: {h}" for i, h in enumerate(hooks)), [], PICK_SCHEMA, agent="mscript")
    except (meta.MetaError, OSError, ValueError):
        return None
    b = got.get("best")
    return b if isinstance(b, int) and 0 <= b < len(hooks) else None
