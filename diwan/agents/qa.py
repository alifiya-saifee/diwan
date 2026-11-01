"""Supervision in the content studio. Each room lead checks every piece of work from its room the moment it is made,
against written acceptance rules. A failed check names the rule, what was wrong, the agent who must fix it and how;
the work goes back to that agent with the reason, up to two more tries. If it still fails, the Marketing lead raises it
to a person with the whole history. Nothing that failed a check moves on silently.

When a problem is found downstream (the permit checker holds a post), `blame` traces it to the agent whose work caused
it (the script, or the post text) so the right one fixes it, not the one that noticed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from diwan.agents import lessons
from diwan.agents.charters import get
from diwan.office import Office

BANNED = r"\b(guaranteed?|risk.?free|assured returns?|best investment|will (double|rise|go up)|100% (safe|return)|free (golden )?visa|visa included|get (a|your) (golden )?visa)\b"
MAX_TRIES = 3  # the first try and two returns


@dataclass(frozen=True)
class Check:
    id: str
    rule: str                                        # the acceptance rule, as the supervisor reads it
    owner: str                                       # the agent who fixes it
    test: Callable[[Office, str, dict], tuple[bool, str]]
    fix: str                                         # the instruction sent back with the work


def _listing(o: Office, ref: str) -> dict:
    from diwan.agents.studio import _listing as item
    return item(o, ref)


def _brief(o: Office, ref: str) -> str:
    from diwan.agents.studio import _brief as brief
    return brief(o, ref)


def _needed(o: Office) -> bool:
    from diwan import business
    return business.permit_needed(o)


GENERIC = {"unit", "apartment", "villa", "townhouse", "flat", "dubai", "with", "the", "and"}


def _names_listing(o: Office, ref: str, text: str) -> bool:
    """The text is about this listing: it names the ref, or a distinctive word of its title (the building, the villa)."""
    if _listing(o, ref)["item"] == "topic":
        return True  # a topic like "About us" has no name to repeat
    t = text.lower()
    words = {w for w in __import__("re").findall(r"[a-z]{4,}|\d+", _listing(o, ref)["title"].lower())} - GENERIC  # "Villa 88" is named by its number
    return ref.lower() in t or any(w in t for w in words)


def _money(text: str) -> set[int]:
    from diwan.agents.studio import _amounts
    return _amounts(text)


MAX_SPOKEN = 65  # about 25 seconds at 2.5 words a second
BROCHURE = re.compile(r"\b(premier|solutions?|seamless(ly)?|world.class|unparalleled|one.stop|state.of.the.art|personali[sz]ed care|second to none)\b", re.I)


def _creative(o: Office, ref: str, it: dict) -> tuple[bool, str]:
    """Only pictures the AI made are judged here: a post's real photos are the post."""
    from diwan.agents import director
    if it.get("background") != "Muse Image":
        return True, ""
    seen = director.review(o, _listing(o, ref)["title"], " ".join(x["text"] for x in it["images"]), [x["path"] for x in it["images"]])
    if not seen or not seen["failed"]:
        return True, ""
    return False, f"{seen['score']}/5: " + next(iter(seen["failed"].values()))[:120]


def _script_text(item: dict) -> str:
    return " ".join([item.get("hook_en", ""), *item.get("lines_en", [])])


def _right_size(path: str) -> bool:
    from PIL import Image
    try:
        with Image.open(path) as img:
            return img.size == (1080, 1350)
    except OSError:
        return False


CLAIM = re.compile(r"\b(\d[\d,.]*)(?:\+?\s*(?:%|percent\b|(?:years?|clients?|customers?|families|deals?|homes?|sales|awards?|agents?|brokers?|projects?)\b)|(?:st|nd|rd|th)?[- ](?:floor|storey|story)\b)", re.I)


STORY = re.compile(r"\b(?:I|we)(?:'d| had| have| once| always| never)? +(?:thought|assumed|believed|remember(?:ed)?|used to|felt|worried|feared|kept seeing|wondered|didn't think)\b"
                   r"|\b(?:most|many|some) (?:[\w-]+ ){0,3}(?:think|believe|assume|expect|feel|worry)\b", re.I)


def _made_up(o: Office, ref: str, text: str):
    """A memory or a belief is not a fact unless the facts say it. A listing's lifestyle line is not held to this."""
    return STORY.search(text) if _listing(o, ref)["item"] == "topic" and not STORY.search(_brief(o, ref)) else None


def _stray_claims(o: Office, ref: str, text: str) -> list[str]:
    """Numbers that sound like a track record ("15 years", "500 families", "98%") and appear in no source."""
    from diwan import brand
    from diwan.agents import journey
    known = " ".join([_brief(o, ref), brand.brief(o), *journey.company(o, k=50)])
    return [m.group(0) for m in CLAIM.finditer(text) if not re.search(rf"(?<![\d,.]){re.escape(m.group(1).rstrip('.,'))}(?!\d)", known)]


CHECKS: dict[str, list[Check]] = {
    "ideas": [
        Check("idea-no-notes", "The idea title reads as a hook, with no internal notes.", "midea",
              lambda o, ref, it: (lambda m: (not m, m.group(0) if m else ""))(re.search(r"\bno cards?\b|\bcard ids?\b|\bTBD\b|\[[^\]]*\]|\bK\d+\b|\bT-[A-Z0-9-]{3,}\b", it["pick"]["title"], re.I)),
              "Write the title as the hook a viewer would see."),
        Check("idea-names-listing", "The chosen idea is about this listing (names its building, title or ref).", "midea",
              lambda o, ref, it: (_names_listing(o, ref, it["pick"]["title"]), it["pick"]["title"][:80]),
              "Make the idea about the listing by name."),
        Check("idea-real-cards", "Every card an idea builds on is on the research board.", "midea",
              lambda o, ref, it: (lambda board: (all(c in board for i in it["ideas"] for c in i["cards"]), "unknown card"))({b["id"] for b in _board(o)}),
              "Only build on cards that are pinned on the board."),
    ],
    "film list": [
        Check("film-enough-shots", "At least 4 shots.", "mfilm", lambda o, ref, it: (len(it["shots"]) >= 4, f"{len(it['shots'])} shots"), "Add shots until there are at least 4."),
        Check("film-ends-on-price", "The last shot is the price card (or the end card when no price is public), with the permit number when one is needed.", "mfilm",
              lambda o, ref, it: (("price card" in it["shots"][-1].lower() or ("end card" in it["shots"][-1].lower() and _listing(o, ref).get("price_aed") is None))
                                  and (not _needed(o) or _listing(o, ref)["item"] == "topic" or "permit" in it["shots"][-1].lower()), it["shots"][-1][:80]),
              "End on the price card, with the permit number when one is needed."),
    ],
    "script": [
        Check("script-hook-short", "The hook is 12 words or fewer.", "mscript",
              lambda o, ref, it: (len(it["hook_en"].split()) <= 12, f"{len(it['hook_en'].split())} words: \"{it['hook_en'][:80]}\""), "Cut the hook to 12 words or fewer."),
        Check("script-short", f"At most {MAX_SPOKEN} spoken words, about 25 seconds.", "mscript",
              lambda o, ref, it: (bool(it.get("slides")) or len(_script_text(it).split()) <= MAX_SPOKEN, f"{len(_script_text(it).split())} words"),  # pictures are read, not spoken
              f"Cut it to {MAX_SPOKEN} words or fewer, keeping one idea."),
        Check("script-plain", "No brochure language: it sounds like someone talking.", "mscript",
              lambda o, ref, it: (lambda m: (not m, m.group(0) if m else ""))(BROCHURE.search(_script_text(it))),
              "Say it in plain spoken words: what the person gets, not how good we are."),
        Check("script-length", "5 to 8 lines, about 30 seconds.", "mscript",
              lambda o, ref, it: (5 <= len(it["lines_en"]) <= 8, f"{len(it['lines_en'])} lines"), "Write 5 to 8 lines."),
        Check("script-real-amounts", "Every amount is on the listing.", "mscript",
              lambda o, ref, it: (lambda stray: (not stray, ", ".join(f"AED {a:,}" for a in stray)))(_money(_script_text(it)) - {_listing(o, ref)["price_aed"], 0} - (_money(_brief(o, ref)) if _listing(o, ref)["item"] == "topic" else set())),
              "Use only the listing's price; remove every other amount."),
        Check("script-no-promises", "No promised returns or guarantees.", "mscript",
              lambda o, ref, it: (lambda m: (not m, m.group(0) if m else ""))(re.search(BANNED, _script_text(it), re.I)), "Remove the promise; describe the property instead."),
        Check("script-real-claims", "Every number claimed about us comes from the listing, the brand or a confirmed company fact.", "mscript",
              lambda o, ref, it: (lambda stray: (not stray, ", ".join(stray)))(_stray_claims(o, ref, _script_text(it))),
              "Remove that claim, or use only the numbers in the facts given."),
        Check("script-no-made-up-story", "A post about the brand, a topic or a moment tells no personal story or belief the facts do not show.", "mscript",
              lambda o, ref, it: (lambda m: (not m, m.group(0) if m else ""))(_made_up(o, ref, _script_text(it))),
              "Say the fact plainly. Nobody in the facts thought, felt or remembered this."),
        Check("script-natural", "It sounds like a person, with no planning words in it.", "mscript",
              lambda o, ref, it: (lambda m: (not m, m.group(0) if m else ""))(re.search(r"\b(facts first|investor facts|price reveal|market check|walkthrough script|the angle|our angle|this hook)\b", _script_text(it), re.I)),
              "Say it the way a person would; that phrase is our planning language, not something a viewer hears."),
        Check("script-no-placeholders", "No placeholders, brackets or notes to self.", "mscript",
              lambda o, ref, it: (lambda m: (not m, m.group(0) if m else ""))(re.search(r"\[[^\]]*\]|\bTBD\b|\bnot in (the )?listing\b|\bplaceholder\b", _script_text(it), re.I)),
              "Remove the placeholder; leave out any fact the listing does not have."),
        Check("script-no-repeats", "No line says the same thing twice, and no line repeats the hook.", "mscript",
              lambda o, ref, it: (lambda ls: (len(ls) == len(set(ls)), "a repeated line"))([re.sub(r"[^a-z0-9]", "", l.lower()) for l in [it["hook_en"], *it["lines_en"]]]),
              "Make every line say something new; the hook is said once, then the lines move on."),
        Check("script-call-to-action", "The script ends by asking the viewer to get in touch.", "mscript",
              lambda o, ref, it: (bool(re.search(r"\b(message|dm|call|whatsapp|book|contact|enquire|inquire|link in bio|get in touch|reach out|speak to|talk to|follow|ask us|tell us)\b", (it["lines_en"] or [""])[-1], re.I)),
                                  (it["lines_en"] or [""])[-1][:80]),
              "End with a line inviting the viewer to get in touch, in the brand's own sign-off."),
        Check("script-brand", "No word the brand never uses, no claim it never makes.", "mscript",
              lambda o, ref, it: (lambda w: (not w, w or ""))(__import__("diwan.brand", fromlist=["broken"]).broken(o, _script_text(it))),
              "Rewrite without that word; the brand profile lists what we never say."),
        Check("script-arabic", "The hook is also written in Arabic.", "mscript",
              lambda o, ref, it: ("Arabic" not in __import__("diwan.business", fromlist=["languages"]).languages(o)
                                  or bool(re.search(r"[؀-ۿ]", it.get("hook_ar", ""))), "no Arabic hook"), "Add the hook in Arabic."),
        Check("script-not-repeated", "It is not the same as a script already used.", "mscript",
              lambda o, ref, it: (lambda old: (not old, f"too close to {old['id']}: \"{old['hook_en'][:60]}\"" if old else ""))(
                  __import__("diwan.agents.style", fromlist=["too_close"]).too_close(o, it)),
              "Say it a new way: a different hook, a different first feature, a different structure."),
        Check("script-lessons", "Every lesson taught to the Script writer is kept.", "mscript",
              lambda o, ref, it: (lambda ls: (not ls, ls["rule"] if ls else ""))(lessons.broken(o.log, "mscript", _script_text(it))), "Follow the lesson."),
    ],
    "post text": [
        Check("post-permit", "The permit number is in the post.", "mwriter",
              lambda o, ref, it: (not _needed(o) or _listing(o, ref)["item"] == "topic" or (bool(_listing(o, ref).get("permit")) and _listing(o, ref)["permit"] in it["text"]), "permit missing"), "Add the permit number."),
        Check("post-no-notes", "The post is what the public reads, with no internal notes.", "mwriter",
              lambda o, ref, it: (lambda m: (not m, m.group(0) if m else ""))(re.search(r"^\s*(verdict|evidence|missing|next|actions|post \(unchanged\)):", it["text"], re.I | re.M)),
              "Write only the post itself."),
        Check("post-code", "The post carries its code word, so a lead can be traced to it.", "mwriter",
              lambda o, ref, it: (not it.get("code") or it["code"] in it["text"], it.get("code") or ""), "Keep the code word in the last line."),
        Check("post-length", "2,200 characters or fewer (Instagram's limit).", "mwriter", lambda o, ref, it: (len(it["text"]) <= 2200, f"{len(it['text'])} characters"),
              "Shorten to 2,200 characters."),
        Check("post-hashtags", "10 hashtags or fewer.", "mwriter", lambda o, ref, it: (it["text"].count("#") <= 10, f"{it['text'].count('#')} hashtags"), "Keep the 10 best hashtags."),
        Check("post-brand", "No word the brand never uses, no claim it never makes.", "mwriter",
              lambda o, ref, it: (lambda w: (not w, w or ""))(__import__("diwan.brand", fromlist=["broken"]).broken(o, it["text"])),
              "Rewrite without that word; the brand profile lists what we never say."),
        Check("post-lessons", "Every lesson taught to the Content writer is kept.", "mwriter",
              lambda o, ref, it: (lambda ls: (not ls, ls["rule"] if ls else ""))(lessons.broken(o.log, "mwriter", it["text"])), "Follow the lesson."),
    ],
    "slides": [
        Check("slides-creative", "AI-made pictures pass the Creative Director. Real photos are not held back here.", "mart",
              lambda o, ref, it: _creative(o, ref, it), "Make a picture that clearly belongs to this business and this post, not generic art."),
        Check("slides-exist", "Every image exists and is 1080 by 1350.", "mart",
              lambda o, ref, it: (lambda bad: (not bad, ", ".join(bad)))([x["served"] for x in it["images"] if not _right_size(x["path"])]), "Make the image again."),
        Check("slides-count", "1 to 10 images.", "mart", lambda o, ref, it: (1 <= len(it["images"]) <= 10, f"{len(it['images'])} images"), "Keep to Instagram's limit of 10."),
    ],
    "cut": [
        Check("cut-exists", "The captioned video exists and plays.", "mcap", lambda o, ref, it: (Path(it["path"]).exists() and Path(it["path"]).stat().st_size > 0, it["path"]),
              "Render the cut again."),
        Check("cut-has-captions", "At least one caption line.", "mcap", lambda o, ref, it: (it["lines"] >= 1, f"{it['lines']} lines"), "Caption what is said."),
    ],
    "slot": [
        Check("slot-future", "The slot is in the future.", "msched",
              lambda o, ref, it: (datetime.fromisoformat(it["at"]) > datetime.now(timezone(timedelta(hours=4))), it["at"]), "Pick a time after now."),
        Check("slot-waking-hours", "Between 8 AM and 11 PM Dubai time.", "msched",
              lambda o, ref, it: (8 <= datetime.fromisoformat(it["at"]).astimezone(timezone(timedelta(hours=4))).hour <= 23, it["at"]), "Pick a waking hour."),
    ],
    "versions": [
        Check("versions-limits", "Every platform version is within that platform's limit.", "mcross",
              lambda o, ref, it: (lambda lim: (all(len(v) <= lim.get(p, 10**6) for p, v in it["versions"].items()), "over a limit"))(__import__("diwan.agents.studio", fromlist=["LIMITS"]).LIMITS),
              "Cut each version to its platform's limit."),
    ],
}


def _board(o: Office) -> list[dict]:
    from diwan.agents.studio import board
    return board(o)


def supervisor(agent: str) -> str:
    """The room lead who checks this agent's work."""
    return get(agent).parent or "mkt"


def review(office: Office, kind: str, ref: str, item: dict | None, *, cause: int | None, attempt: int) -> list[dict]:
    """Check one piece of work; log the verdict as the supervisor. Returns the failures."""
    if item is None or kind not in CHECKS:
        return []
    fails = []
    for c in CHECKS[kind]:
        try:
            ok, detail = c.test(office, ref, item)
        except Exception as e:  # a check that cannot run is a failure, not a pass
            ok, detail = False, f"check could not run: {e}"
        if not ok:
            fails.append({"check": c.id, "rule": c.rule, "found": detail, "owner": c.owner, "fix": c.fix})
    sup = supervisor(CHECKS[kind][0].owner)
    if fails:
        office.log.append("qa.failed", actor=sup, agent=sup, caused_by=cause,
                          content={"kind": kind, "ref": ref, "item": item.get("id"), "attempt": attempt, "fails": fails,
                                   "returned_to": sorted({f["owner"] for f in fails})})
    else:
        office.log.append("qa.passed", actor=sup, agent=sup, caused_by=cause,
                          content={"kind": kind, "ref": ref, "item": item.get("id"), "attempt": attempt, "checks": [c.id for c in CHECKS[kind]]})
    return fails


def _escalate_to(office: Office, kind: str) -> str:
    """Who a stuck piece of work goes to: the person set in Setup to pick scripts (for ideas, scripts and film lists) or
    to approve publishing (everything later); the owner until one is set."""
    from diwan.agents import approvers
    from diwan.people import BY_ROLE
    role = "script" if kind in ("ideas", "script", "film list") else "publish"
    return approvers.get(office)[role] or BY_ROLE["Owner"]


def escalate(office: Office, kind: str, ref: str, fails: list[dict], *, cause: int | None) -> None:
    """Still failing after the returns: the Marketing lead raises it to the owner, with what was tried."""
    office.log.append("qa.escalated", actor="mkt", agent="mkt", caused_by=cause, content={"kind": kind, "ref": ref, "fails": fails})
    office.log.append("decision.needed", actor="mkt", agent="mkt", caused_by=cause,
                      content={"who": _escalate_to(office, kind), "refs": [ref], "options": ["Fix it myself", "Accept as is", "Stop this reel"],
                               "question": f"The {kind} for {ref} failed review {MAX_TRIES} times: " + "; ".join(f"{f['rule']} (found: {f['found']})" for f in fails)})


def blame(office: Office, ref: str, reason: str, script: dict | None, text: dict) -> str:
    """Who caused a problem the permit checker found downstream: the Script writer if it came from the script,
    otherwise the Content writer who wrote the post."""
    low = reason.lower()
    if script and ("amount" in low or "promise" in low):
        st = _script_text(script)
        if "amount" in low and (_money(st) - {_listing(office, ref)["price_aed"], 0}):
            return "mscript"
        if "promise" in low and re.search(BANNED, st, re.I):
            return "mscript"
    return "mwriter"


def feedback_text(fails: list[dict]) -> str:
    return "Your last draft was sent back by your supervisor:\n" + "\n".join(f"- {f['rule']} Found: {f['found']}. Fix: {f['fix']}" for f in fails)
