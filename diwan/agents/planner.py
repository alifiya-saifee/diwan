"""The Strategist chooses what to post and when. rhythm.make_plan gives the plain plan; this hands it, with everything that
could go on it and what is working, to the model, and keeps its choices only where they hold up. The code decides what may
go on a day; the model decides what should. Without a model, or when it fails, the plain plan stands.
"""
from __future__ import annotations

from datetime import date

import re

from diwan.office import Office

SCHEMA = {"name": "plan", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["days"], "properties": {"days": {"type": "array", "items": {
    "type": "object", "additionalProperties": False, "required": ["date", "ref", "why"],
    "properties": {"date": {"type": "string"}, "ref": {"type": "string"}, "why": {"type": "string"}}}}}}}
MAX_LISTINGS, TRIES = 12, 2
NOTES = re.compile(r"\bK\d+\b|\bT-[A-Z0-9-]{3,}|\bJOB-|\bcard\b|\bslot\b|\bref\b", re.I)


def options(office: Office, today: date) -> dict[str, dict]:
    """Everything that may go on the plan: {ref: what it is, what job it does, when it last went out}."""
    from diwan import topics
    from diwan.agents import journey, rhythm
    last = {}
    for u in rhythm.used(office):
        last[u["ref"]] = max(last.get(u["ref"], ""), u["at"])
    ago = lambda ref: (today - date.fromisoformat(last[ref])).days if ref in last else None  # noqa: E731
    out = {}
    fresh = {m["ref"] for m in journey.moments(office)}
    left, _ = journey._left(office)
    for ref, t in journey.items(office).items():
        if ref[4:] in left:
            out[ref] = {"title": t["title"], "type": "topic", "job": ref[4:], "says": journey.JOBS[ref[4:]]["what"], "days_since": ago(ref)}
    dull = {n.id for n in journey._cards(office) if (n.props.get("kind") or "") in journey.HOUSEKEEPING}  # office hours are not a post
    for t in topics.items(office).values():
        if not t.get("moment") and t["ref"] not in dull:
            if not str(t.get("what", "")).strip():
                continue  # nothing true to base it on: no evidence, no recommendation
            out[t["ref"]] = {"title": t["title"], "type": "topic", "job": "educate", "says": str(t.get("what", ""))[:140], "days_since": ago(t["ref"])}
    stock = sorted(rhythm.listings(office), key=lambda x: (x["ref"] not in fresh, x["ref"] in last, last.get(x["ref"], "")))
    for x in stock[:MAX_LISTINGS]:  # the newest and the longest unused: a long request drops on the way
        out[x["ref"]] = {"title": x.get("title") or x["ref"], "type": "listing", "job": "offer", "says": str(x.get("area") or x.get("what") or "")[:80], "days_since": ago(x["ref"]), "just_added": x["ref"] in fresh}
    from diwan.agents import taste
    fits = {r: round(taste.score(office, r), 2) for r in out}
    keep = {r: o | {"fit": fits[r]} for r, o in out.items() if not taste.ruled_out(office, r)}  # repeatedly turned down
    return dict(sorted((keep or out).items(), key=lambda kv: -fits[kv[0]]))


def evidence(office: Office, refs: list[str]) -> dict[str, str]:
    """{ref: what this post is based on, in words}: where its facts come from and what competitors' winning posts show."""
    from diwan.agents import journey, marketing, reader
    win = reader.winning(office)
    new = {m["ref"] for m in journey.moments(office)}
    out = {}
    for ref in refs:
        lst = marketing._subject(office, ref)
        if not lst:
            continue
        src = "New in your catalog" if ref in new and lst["item"] != "topic" else "Your catalog" if lst["item"] != "topic" else \
            "Something you added" if lst.get("moment") or lst.get("source") == "typed" else "Your company facts" if ref.startswith("JOB-") else "Your knowledge base"
        shows = {"Reel, to camera": "a person talking to camera", "Reel, voice-over": "photos or footage without a person"}.get(marketing.format_of(office, ref), "text on images")
        n = win["on_screen"].get(shows, 0)
        out[ref] = src + (f". {n} of {win['posts']} winning competitor posts show {shows}" if win["posts"] else "")
    return out


def _context(office: Office) -> dict:
    """What a marketing lead would look at before choosing."""
    from diwan.agents import journey, marketing, reader, rhythm, style, taste
    a = journey.account(office)
    return {"stage": journey.stage(office), "posts_so_far": a["posts"], "still_to_do_of_the_first_nine": journey._left(office)[0],
            "what_brought_leads": [{"title": r["title"], "leads": r["leads"], "deals": r["deals"]} for r in marketing.results(office)[:5]],
            "topics_winning_for_competitors": sorted(set(rhythm._market_words(office)))[:30], "what_winning_competitor_posts_show": reader.winning(office)["line"], "what_the_owner_has_told_us": style.brief(office), "learned_from_decisions_and_results": taste.brief(office),
            "share_of_teaching_posts_percent": rhythm.settings(office)["topic_share"]}


def choose(office: Office, days: list[dict], today: date, locked: set[str], rejected: set[str] = frozenset()) -> tuple[list[dict], str]:
    """The days as the Strategist would have them, and who chose ("muse-spark" or "rules"). Days in `locked` do not change,
    and what a person rejected is not offered."""
    from diwan.agents import journey, rhythm, runner
    from diwan.agents.charters import get
    free = [d for d in days if d["date"] not in locked]
    if not free:
        return days, "rules"
    pool = {r: o for r, o in options(office, today).items() if r not in rejected}
    moments = {m["ref"] for m in journey.moments(office)}
    fixed = {d["date"] for d in free if d.get("ref") in moments}  # something that just happened keeps its early day
    if journey.stage(office) == "introduce" and "introduce" in journey._left(office)[0]:
        fixed |= {d["date"] for d in free if d.get("job") == "introduce"}  # a stranger meets us before being sold to
    open_days = [d for d in free if d["date"] not in fixed]
    if not open_days or not pool:
        return days, "rules"
    c = get("plan")
    system = runner.instructions(c, office.log)
    user = runner.user_message(
        "Choose what to post on each of these days, as the head of marketing would for this business right now. One post for each date, "
        "from the options only, by their key. Build a stranger's trust before selling, mix teaching and offers, put what works sooner, and prefer options with a higher fit, which is learned from this business's own decisions and leads, and "
        "never use the same option twice. For each day give why in one plain sentence a business owner would say out loud, naming no codes.",
        {"dates": [d["date"] for d in open_days], "already_on_the_plan": [{"date": d["date"], "title": pool.get(d.get("ref"), {}).get("title", "")} for d in days if d["date"] in locked | fixed],
         "options": pool, "the_account": _context(office)})
    if not runner.has_model(c, system, user, schema=SCHEMA):
        return days, "rules"
    office.log.append("agent.started", actor="plan", agent="plan", content={"task": f"Choosing the next {len(open_days)} days with the model"})
    for attempt in range(TRIES):
        try:
            picks = {p["date"]: p for p in runner.call(c, system, user, schema=SCHEMA).data["days"]}
            break
        except Exception as e:  # noqa: BLE001  a plain plan beats no plan
            if attempt == TRIES - 1:
                office.log.append("step.blocked", actor="plan", agent="plan", content={"step": "plan", "needs": f"Muse Spark failed, using the plain plan: {str(e)[:120]}"})
                return days, "rules"
    taken = {d.get("ref") for d in days if d["date"] not in {x["date"] for x in open_days}}
    out, kept = [], 0
    for d in days:
        p = picks.get(d["date"]) if d in open_days else None
        if not p or p["ref"] not in pool or p["ref"] in taken or _too_soon(office, p["ref"], pool, rhythm) or NOTES.search(p["why"]) or len(p["why"]) > 160:
            out.append(d)  # a choice that does not hold up: the plain plan keeps the day
            taken.add(d.get("ref"))
            continue
        o = pool[p["ref"]]
        taken.add(p["ref"])
        kept += 1
        out.append({"date": d["date"], "ref": p["ref"], "why": p["why"].strip(), "type": o["type"], "status": "pending", **({"job": o["job"]} if p["ref"].startswith("JOB-") else {})})
    # a plain day that kept its place can now repeat a choice: nothing goes out twice, and no day is left blank
    seen, final = set(), []
    for d in out:
        if d.get("ref") in seen:
            spare = next((r for r in pool if r not in seen and r not in {x.get("ref") for x in out} and not _too_soon(office, r, pool, rhythm)), None)
            if not spare:
                continue  # nothing else to post: the day stays empty
            d = {"date": d["date"], "ref": spare, "why": "Not posted yet", "type": pool[spare]["type"], "status": "pending", **({"job": pool[spare]["job"]} if spare.startswith("JOB-") else {})}
        seen.add(d.get("ref"))
        final.append(d)
    return final, "muse-spark" if kept else "rules"


def _too_soon(office: Office, ref: str, pool: dict, rhythm) -> bool:
    o, s = pool[ref], rhythm.settings(office)
    days = int(s["repeat_topic_days"] if o["type"] == "topic" else s["repeat_listing_days"])
    return o["days_since"] is not None and o["days_since"] < days
