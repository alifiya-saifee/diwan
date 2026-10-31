"""What a video can be about besides one property or product: a topic to explain (how buying off-plan works, what a
permit is, what a service covers). It is not selling one thing, so it has no price and no permit; its words come only
from facts the business has confirmed.

Where topics come from (nothing here is invented):
  a confirmed, customer-facing, in-date knowledge card (company, approved answers, projects, areas)
  a confirmed product or service, explained ("How X works")
  a topic a person typed in Setup, with the facts a video may use

A topic is shaped like a product for the writers (`item` "topic", `title`, `what`, `features` = its facts), so the
studio runs it through the same steps: ideas, three scripts, a film list, a post, the same checks and approvals.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan import products

try:
    from diwan import knowledge as kn  # the Knowledge cards; without that page, topics are services and typed ones only
except ImportError:  # pragma: no cover
    kn = None
from diwan.office import Office

TAB_OK = ("company", "answer", "project", "area")  # people (staff bios) and brand (voice rules) are not subjects
ANGLES = {  # id: what it is
    "explainer": "Explain it simply, one step at a time",
    "myth-vs-fact": "Open on a common belief, then what is true (only facts given here)",
    "question": "Open on the question people ask first, then answer it",
    "checklist": "What to check or do, in order",
    "why-it-matters": "Why it matters to the viewer, then what to do about it",
}
FORMATS = ("to camera", "voice-over")


def _facts(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(s.strip()) > 8][:8]


def _typed(office: Office) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for e in office.log.list():
        if e["type"] == "topic.saved":
            c = e["content"]
            out[c["ref"]] = {**out.get(c["ref"], {}), **c, "by": e["actor"], "at": e["at"]}
    return out


def excluded(office: Office) -> set[str]:
    """Cards and services a person said not to make videos about (they stay in Knowledge for the agents)."""
    return {r for r, t in _typed(office).items() if t.get("excluded") and t.get("status") == "removed"}


def exclude(office: Office, ref: str, *, by: str, on: bool = True) -> None:
    office.log.append("topic.saved", actor=by, content={"ref": ref, "status": "removed" if on else "confirmed", "excluded": on})


def items(office: Office, *, all_: bool = False) -> dict[str, dict]:
    """{ref: topic} of every topic a video may be about now (all_: the excluded ones too, marked)."""
    g, out = office.graph(), {}
    today = datetime.now(timezone.utc).date().isoformat()
    for n in (g.of("knowledge") if kn else []):
        if kn.tab(n) in TAB_OK and kn.usable(n) and (n.props.get("text") or "").strip():
            out[n.id] = {"ref": n.id, "title": n.props.get("title") or n.label, "what": n.props["text"].strip(), "features": _facts(n.props["text"]),
                         "source": "card", "kind": "topic", "from": f"the {kn.tab(n)} card {n.id}"}
    for r, p in products.items(office).items():
        out[f"ABOUT-{r}"] = {"ref": f"ABOUT-{r}", "title": f"How {p['title']} works", "what": p.get("what") or "", "features": list(p.get("features") or []),
                             "source": "product", "kind": "topic", "from": f"the {p.get('kind') or 'product'} {p['title']}"}
    for r, t in _typed(office).items():
        if t.get("title") and t.get("status") == "confirmed":
            if t.get("moment") and t.get("until", "") < today:
                continue  # news goes out of date: a moment is not a topic for ever
            out[r] = {"ref": r, "title": t["title"], "what": t["what"], "features": _facts(t["what"]), "source": "typed", "kind": "topic", "from": "a topic typed in Setup",
                      **({"moment": True, "until": t["until"], "from": "a moment a person typed", "format": t.get("format")} if t.get("moment") else {})}
    skip = excluded(office)
    return {r: t | ({"excluded": True} if r in skip else {}) for r, t in out.items() if (t["features"] or t["what"]) and (all_ or r not in skip)}


def get(office: Office, ref: str) -> dict | None:
    if ref.startswith("JOB-"):  # a post about the brand itself
        from diwan.agents import journey
        return journey.item(office, ref)
    return items(office).get(ref)


def record(t: dict) -> str:
    """One line for the writers, like a listing's record."""
    return f"{t['title']} (topic, {t.get('from', '')}): {t.get('what') or ''} · facts: {'; '.join(t.get('features') or []) or 'none recorded'}"


def typed(office: Office) -> list[dict]:
    """The topics typed in Setup, with removed ones left out."""
    return [t for t in _typed(office).values() if t.get("title") and t.get("status") != "removed"]


def save(office: Office, values: dict, *, by: str, ref: str | None = None) -> str:
    """Type a topic in (no ref) or change or remove one. The facts are what the writers may use: a video is never written
    from a title alone."""
    title, what = str(values.get("title", "")).strip()[:90], str(values.get("what", "")).strip()[:2000]
    status = values.get("status", "confirmed")
    if status not in ("confirmed", "removed"):
        raise ValueError("Status is confirmed or removed.")
    if ref:
        if not _typed(office).get(ref, {}).get("title"):
            raise ValueError(f"No topic {ref}.")
        v = {k: x for k, x in {"title": title, "what": what}.items() if x} | {"status": status}
    else:
        if not title:
            raise ValueError("Give the topic a name.")
        if len(what) < 30:
            raise ValueError("Write the facts a video may use (at least a sentence or two): a script is written only from them, never from the title alone.")
        known = {t["ref"] for t in _typed(office).values()}
        base = "T-" + (re.sub(r"[^A-Z0-9]+", "-", title.upper()).strip("-")[:18] or "TOPIC")
        ref, n = base, 1
        while ref in known:
            n += 1
            ref = f"{base}-{n}"
        v = {"title": title, "what": what, "status": status}
    office.log.append("topic.saved", actor=by, content={"ref": ref, **v})
    return ref


MOMENT_DAYS = 7


def save_moment(office: Office, values: dict, *, by: str) -> str:
    """Something that just happened and matters more than the plan. A person says what happened: the writers use only
    those facts, and it lapses by itself."""
    until = str(values.get("until") or "").strip() or (datetime.now(timezone.utc).date() + timedelta(days=MOMENT_DAYS)).isoformat()
    try:
        datetime.strptime(until, "%Y-%m-%d")
    except ValueError:
        raise ValueError("The end date is a date like 2026-11-07.") from None
    ref = save(office, values, by=by)
    office.log.append("topic.saved", actor=by, content={"ref": ref, "moment": True, "until": until})
    return ref


def pick_angles(n: int, avoid: set[str]) -> list[dict]:
    """The angles for one topic's scripts: ones not used lately first; each says why it was chosen."""
    fresh = [a for a in ANGLES if a not in avoid]
    order = (fresh + [a for a in ANGLES if a in avoid])[:n]
    return [{"angle": a, "slot": "explore" if a in fresh else "repeat", "why": ANGLES[a] if a in fresh else f"{ANGLES[a]} (used lately: too few others)"} for a in order]


def format_for(lst: dict) -> str:
    """How a script is spoken: a topic is a person talking to camera; a property or product keeps its shots and a voice-over."""
    return "to camera" if lst.get("item") == "topic" else "voice-over"
