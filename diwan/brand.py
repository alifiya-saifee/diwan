"""The brand profile every marketing writer works from: who we are, who we talk to, how we sound, the words we use and
the ones we never use, the claims we never make, how we sign off. The Marketing manager owns it.

It lives in the office's log (setting.changed, person "brand"), so every change keeps who made it and when. The Idea
generator, Script writer and Content writer get it in their instructions, and the Copywriter's review sends back any
script or post that uses a word the brand never uses. With nothing set, writers are told so instead of guessing.
"""
from __future__ import annotations

import re

from diwan.office import Office

FIELDS = {  # key: (label, what to write, used as a list)
    "name": ("Brand name", "The name customers know you by", False),
    "positioning": ("Who we are", "One sentence: what we do, for whom, and why us", False),
    "audience": ("Who we talk to", "Who the customers are, in a sentence", False),
    "voice": ("How we sound", "3 to 5 words, e.g. warm, straight-talking", True),
    "say": ("Words and phrases we use", "Words that sound like you, comma-separated", True),
    "avoid": ("Words we never use", "Words you never want in a post, comma-separated", True),
    "never_claim": ("Claims we never make", "Promises you never make, comma-separated", True),
    "cta": ("How we sign off", "The last line of every post", False),
    "hashtags": ("Our hashtags", "Your own hashtags, e.g. #YourBrand", True),
}
USED_BY = ["Idea generator", "Script writer", "Content writer", "Copywriter (review)"]


def _split(v: str) -> list[str]:
    """The items of a list field, however it was written: "luxury, hurry", one per line, or a sentence that quotes them
    ('We never say "luxury", "hurry" or "best investment"'). Quoted words win; otherwise split on commas, "and", "or"."""
    v = v or ""
    quoted = re.findall(r"[\"“”']([^\"“”']{2,60})[\"“”']", v)
    if quoted:
        return [q.strip() for q in quoted if q.strip()]
    v = re.sub(r"^\s*(we\s+)?(never|don't|do not)\s+(say|use|claim)\s*:?\s*", "", v, flags=re.I)
    items = [re.sub(r"^(that|any|a|an|the)\s+", "", x.strip(" ."), flags=re.I) for x in re.split(r"[,\n;]|\s+(?:and|or)\s+", v)]
    return [x for x in items if x]


def profile(office: Office) -> dict:
    """The current profile: each field's value, who set it and when (the latest change wins)."""
    out = {k: {"value": "", "by": None, "at": None} for k in FIELDS}
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "setting.changed" and c.get("person") == "brand" and c.get("key") in FIELDS:
            out[c["key"]] = {"value": str(c.get("value") or "").strip(), "by": e["actor"], "at": e["at"], "via": c.get("via")}
    return out


def is_set(office: Office) -> bool:
    p = profile(office)
    return bool(p["voice"]["value"] or p["positioning"]["value"])


def save(office: Office, values: dict, *, by: str, via: str = "typed") -> list[str]:
    """Record the fields that changed. Returns their keys."""
    cur, changed = profile(office), []
    for k, v in values.items():
        if k in FIELDS and str(v or "").strip() != cur[k]["value"]:
            office.log.append("setting.changed", actor=by, content={"person": "brand", "key": k, "value": str(v or "").strip(), "via": via})
            changed.append(k)
    return changed


def avoid_words(office: Office) -> list[str]:
    p = profile(office)
    return _split(p["avoid"]["value"]) + _split(p["never_claim"]["value"])


def broken(office: Office, text: str) -> str | None:
    """The first never-use word or never-make claim found in the text."""
    low = text.lower()
    return next((w for w in avoid_words(office) if re.search(rf"(?<!\w){re.escape(w.lower())}(?!\w)", low)), None)


def brief(office: Office) -> str:
    """The profile as the writers read it."""
    p = profile(office)
    if not is_set(office):
        return ("No brand profile is set yet. Write plainly and factually; the Marketing manager has not defined the voice, so do not "
                "invent a tagline, a slogan or a sign-off of your own.")
    lines = [f"{FIELDS[k][0]}: {p[k]['value']}" for k in FIELDS if p[k]["value"]]
    return "\n".join(lines) + "\nWrite in this voice. Never use the words or make the claims listed above."


def cta(office: Office, default: str = "Message us to book a viewing.") -> str:
    return profile(office)["cta"]["value"] or default


def hashtags(office: Office) -> list[str]:
    tags = []
    for part in _split(profile(office)["hashtags"]["value"]):
        tags += ["#" + h.lstrip("#") for h in part.split() if h.lstrip("#")]
    return tags


DRAFT_SCHEMA = {"name": "brand", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": list(FIELDS),
                "properties": {k: {"type": "string"} for k in FIELDS}}}


def draft(office: Office) -> dict:
    """The Brand brain proposes a profile from what the office knows: confirmed company knowledge, our own posts and our
    listings. Nothing is saved; a person reads it, edits it and saves. Returns {"values", "sources", "by"} or {"needs"}."""
    from diwan.agents import runner, studio
    from diwan.agents.charters import get
    g = office.graph()
    know = {n.id: g.record(n.id) for n in g.of("knowledge", status="confirmed")}
    ours = sorted(studio.posts(office, "own"), key=lambda p: -((p.get("likes") or 0) + (p.get("comments") or 0)))[:8]
    posts = {f"post{i + 1}": (p.get("caption") or "")[:300] for i, p in enumerate(ours) if p.get("caption")}
    areas = sorted({n.props["community"] for n in g.of("listing")})
    if not know and not posts:
        return {"needs": "Add company knowledge (Knowledge page) or import our own posts first, so the draft is based on something real."}
    c = get("mbrand")
    system = runner.instructions(c, office.log) + ("\nDraft the brand profile in the `brand` format from the sources only. Where the sources "
                                                   "say nothing about a field, leave it empty rather than invent. Lists are comma-separated.")
    user = runner.user_message("Draft our brand profile. Our listings are in: " + ", ".join(areas), {**know, **posts})
    if not runner.has_model(c, system, user, schema=DRAFT_SCHEMA):
        return {"needs": "A model (META_API_KEY), or this month's budget, to draft it. You can type the profile yourself."}
    data = runner.call(c, system, user, schema=DRAFT_SCHEMA).data
    return {"values": {k: (data.get(k) or "").strip() for k in FIELDS}, "sources": list(know) + list(posts), "by": "Brand brain (Muse Spark)"}
