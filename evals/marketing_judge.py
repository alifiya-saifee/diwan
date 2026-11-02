"""A blind judge for what the Marketing room makes and says: always the same model and effort, never told which
setting or agent made it. Scores 1 to 5 with a one-line reason, from the chair of a demanding head of marketing at a
Dubai brokerage. Paid: about $0.002 a text, $0.004 a picture set.
"""
from __future__ import annotations

import io
from pathlib import Path

from diwan import config
from diwan.providers import meta

SCORE = {"name": "score", "strict": True, "schema": {"type": "object", "additionalProperties": False,
         "required": ["score", "why", "makes_sense"], "properties": {"score": {"type": "integer"}, "why": {"type": "string"},
                                                                   "makes_sense": {"type": "boolean"}}}}
LOOK = {"name": "poster", "strict": True, "schema": {"type": "object", "additionalProperties": False,
        "required": ["score", "why", "company_shown", "logo_shown", "text_readable", "professional", "matches_words"],
        "properties": {"score": {"type": "integer"}, "why": {"type": "string"}, "company_shown": {"type": "boolean"},
                       "logo_shown": {"type": "boolean"}, "text_readable": {"type": "boolean"}, "professional": {"type": "boolean"},
                       "matches_words": {"type": "boolean"}}}}
ANSWER = {"name": "answer", "strict": True, "schema": {"type": "object", "additionalProperties": False,
          "required": ["score", "why", "true_to_facts", "answered_the_question", "reasoned"],
          "properties": {"score": {"type": "integer"}, "why": {"type": "string"}, "true_to_facts": {"type": "boolean"},
                         "answered_the_question": {"type": "boolean"}, "reasoned": {"type": "boolean"}}}}
CHAIR = ("You are a demanding head of marketing at a Dubai real-estate brokerage, judging work blind. Most work is a 3. "
         "Give 5 only to work you would publish untouched, 4 to work needing a small touch, 2 or 1 to work you would throw away.")


def _ask(system: str, text: str, images: list[bytes], schema: dict) -> dict | None:
    token = config.TRIAL.set({"provider": "meta"})
    try:
        return meta.look(system, text[:12000], images, schema, agent="mkt")
    except meta.MetaError as e:
        return {"score": None, "why": f"not judged: {e}"}
    finally:
        config.TRIAL.reset(token)


def _jpeg(p: str | Path, width: int = 720) -> bytes:
    from PIL import Image
    im = Image.open(p).convert("RGB")
    im.thumbnail((width, width * 2))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=82)
    return b.getvalue()


def text(what: str, body: str, context: str = "") -> dict | None:
    """A script, caption, plan reason or idea. `context`: what it was for (the listing, the occasion)."""
    return _ask(CHAIR + f" Score this {what} 1-5: specific, natural, true to its facts, right for the moment, would it stop a "
                "buyer scrolling? makes_sense: is it what a real brokerage would expect here?", f"For: {context}\n\n{body}", [], SCORE)


def pictures(what: str, paths: list[str | Path], context: str = "") -> dict | None:
    """Posters, slides, a cover or video frames, judged together as one post."""
    imgs = [_jpeg(p) for p in paths[:6] if Path(p).exists()]
    if not imgs:
        return {"score": None, "why": "no picture to judge"}
    return _ask(CHAIR + f" Score this {what} 1-5 as a finished social post: layout, typography, readability, brand presence, would a "
                "professional brokerage publish it beside its competitors' best? company_shown: the company's name is visible. logo_shown: a "
                "company logo (a mark, not just words) is visible. matches_words: the pictures show what the words say.",
                f"For: {context}", imgs, LOOK)


def answer(question: str, reply: str, facts: str) -> dict | None:
    """The Marketing lead's or Nova's answer, against the data it had."""
    return _ask(CHAIR + " Judge an assistant's answer to its marketing manager. true_to_facts: every number and claim matches the facts "
                "below (unknown is fine if said). answered_the_question: it answered what was asked. reasoned: it says why, not only what. "
                "Score 1-5 for how useful and sound it is.", f"Question: {question}\n\nAnswer: {reply}\n\nFacts it had:\n{facts}", [], ANSWER)


CHANGED = {"name": "changed", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["landed", "score", "why"],
           "properties": {"landed": {"type": "boolean"}, "score": {"type": "integer"}, "why": {"type": "string"}}}}


def changed(asked: str, before: list[str | Path], after: list[str | Path]) -> dict | None:
    """Did a requested change land? Before and after shown together; the judge is not told what the code meant to do."""
    b, a = [_jpeg(p) for p in before[:3] if Path(p).exists()], [_jpeg(p) for p in after[:3] if Path(p).exists()]
    if not b or not a:
        return {"landed": None, "score": None, "why": "missing before or after"}
    return _ask(CHAIR + " A client asked a designer for a change. The first pictures are BEFORE, the rest AFTER. landed: the AFTER clearly "
                "does what the client asked, the way the client most likely meant it. score 1-5: the AFTER as a finished post.",
                f"The client asked: {asked}\nBEFORE: {len(b)} picture(s), then AFTER: {len(a)}.", b + a, CHANGED)
