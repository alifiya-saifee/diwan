"""The occasions a business greets its followers on, so nobody has to remember them: learned, never typed in.

The calendar is researched for this business: its country, its audience and the languages it posts in (Setup → Your
business). One Muse Spark web search finds the next twelve months' occasions, each with its date and the page that
confirms it, the greeting people use (and in the business's other language), the hashtags people really use, the words
captions mention it with, one true line about it, the same occasion's date last time (to study what competitors posted
then) and what a respectful greeting card would show. A date that no page found in the search confirms is not kept.
It is refreshed every RESEARCH_DAYS days (moon-dependent dates are confirmed late). A person can add, change or remove an
occasion (Setup → Our occasions): their word wins over the research.

LEAD_DAYS before the day it is offered on the Run tab: one yes prepares a greeting post that goes out on the day itself.
A greeting greets: no price, no listing, no offer, no code word (journey JOBS["greeting"], qa, studio.post_text).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from diwan import brand, business
from diwan.office import Office

LEAD_DAYS = 30
RESEARCH_DAYS = 30  # the calendar is searched again after this: expected dates get confirmed, new ones announced
AHEAD_DAYS = 380  # how far ahead the research looks
WINDOW = 4  # days either side of last time's day: moon dates shift, and some post the eve or the day after
MAX_STUDIED = 4  # their best occasion posts looked at, by engagement per follower
FIELDS = ("title", "on", "expected", "greeting", "greeting_local", "tags", "about", "sombre", "last", "words", "motif", "source")
STUDY_SCHEMA = {"name": "occasion_study", "strict": True, "schema": {"type": "object", "additionalProperties": False,
                "required": ["works", "look", "words", "avoid"], "properties": {
                    "works": {"type": "array", "items": {"type": "string"}}, "look": {"type": "string"},
                    "words": {"type": "string"}, "avoid": {"type": "string"}}}}


def _key(title: str, on: str) -> str:
    return f"{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}-{on[:4]}"


def _row(r: dict, by: str) -> dict | None:
    """One occasion, checked: a real date, a title and a greeting. None when it is not usable."""
    try:
        on = date.fromisoformat(str(r.get("on", ""))[:10]).isoformat()
    except ValueError:
        return None
    if not (r.get("title") or "").strip() or not (r.get("greeting") or "").strip():
        return None
    last = str(r.get("last") or "")[:10]
    try:
        last = date.fromisoformat(last).isoformat() if last else ""
    except ValueError:
        last = ""
    tags = [("#" + t.lstrip("#")).replace(" ", "") for t in (r.get("tags") or []) if str(t).strip()][:4]
    return {"key": _key(r["title"], on), "title": r["title"].strip(), "on": on, "expected": bool(r.get("expected")),
            "greeting": r["greeting"].strip(), "greeting_ar": (r.get("greeting_local") or r.get("greeting_ar") or "").strip(), "tags": tags,
            "about": (r.get("about") or "").strip(), "sombre": bool(r.get("sombre")), "last": last,
            "words": [w.strip().lower() for w in (r.get("words") or []) if str(w).strip()][:8], "motif": (r.get("motif") or "").strip(),
            "source": (r.get("source") or "").strip(), "by": by}


def _site(url: str) -> str:
    """The site a page is on (timeoutdubai.com for any of its pages): a date's source must be a site the search opened."""
    from urllib.parse import urlparse
    host = urlparse(url if "://" in url else f"https://{url}").hostname or ""
    return host.removeprefix("www.")


def researched(office: Office) -> dict | None:
    """The latest calendar researched for this business's country, if any."""
    from diwan.agents import studio
    c = business.get(office)["country"]
    return studio.made(office, "occasion calendar", c) if c else None


def _edits(office: Office) -> dict[str, dict | None]:
    """What a person added or changed (a row) or removed (None), by key; the latest word wins."""
    out: dict[str, dict | None] = {}
    for e in office.log.list():
        if e["type"] == "setting.changed" and e["content"].get("person") == "occasions":
            out[e["content"]["key"]] = e["content"].get("value")
    return out


def all_(office: Office) -> list[dict]:
    """The business's occasions: what research found, with a person's additions, changes and removals."""
    rows = {r["key"]: r for r in (researched(office) or {}).get("rows", [])}
    for k, v in _edits(office).items():
        if v is None:
            rows.pop(k, None)
        else:
            rows[k] = v
    return sorted(rows.values(), key=lambda r: r["on"])


def get(office: Office, key: str) -> dict | None:
    return next((o for o in all_(office) if o["key"] == key), None)


def save(office: Office, row: dict, *, by: str, key: str | None = None) -> dict:
    """A person adds or changes an occasion (a changed date or greeting replaces the researched one)."""
    r = _row(row, by)
    if not r:
        raise ValueError("An occasion needs a title, a date (YYYY-MM-DD) and its greeting.")
    if key and key != r["key"]:
        office.log.append("setting.changed", actor=by, content={"person": "occasions", "key": key, "value": None})
    office.log.append("setting.changed", actor=by, content={"person": "occasions", "key": r["key"], "value": r})
    return r


def remove(office: Office, key: str, *, by: str) -> None:
    """Not an occasion for this business: it is not offered, now or after the next research."""
    office.log.append("setting.changed", actor=by, content={"person": "occasions", "key": key, "value": None})


def research_due(office: Office, today: date | None = None) -> bool:
    c = business.get(office)["country"]
    if not c:
        return False
    r = researched(office)
    return not r or (today or date.today()) - date.fromisoformat(r["day"]) >= timedelta(days=RESEARCH_DAYS)


def research(office: Office, *, by: str = "mtrend", today: date | None = None, cause: int | None = None) -> dict:
    """Search the web for this business's occasions in the next year. {rows, dropped, sources} or {needs}."""
    from diwan.agents import studio
    from diwan.providers import meta
    from diwan.providers.chat import parse_json
    b = business.get(office)
    if not b["country"]:
        return {"needs": "the country in Setup → Your business"}
    if not meta.ready():
        return {"needs": "Muse Spark (META_API_KEY) for the web search"}
    today = today or date.today()
    other = [x for x in business.languages(office) if x.lower() != "english"]
    prompt = (f"Search the web, then list the occasions that {business.describe(office)} in {b['country_name']}{' (' + b['city'] + ')' if b.get('city') else ''} "
              f"would greet its followers on social media between {today.isoformat()} and {(today + timedelta(days=AHEAD_DAYS)).isoformat()}: national days, "
              "public and religious holidays, days of remembrance, the new year, and any that its audience there widely marks. Skip commercial days such as Black Friday. "
              "Answer with JSON only: {\"occasions\": [{\"title\", \"on\" (YYYY-MM-DD: the first day; for a moon-dependent day the officially expected date), "
              "\"expected\" (true if the date is confirmed later, e.g. by moon sighting), \"greeting\" (how people greet each other for it in English), "
              f"\"greeting_local\" ({'the same greeting in ' + ' and '.join(other) if other else 'empty'}), \"tags\" (2 or 3 hashtags people really use for it), "
              "\"about\" (one true sentence about it), \"sombre\" (true for a day of remembrance or mourning), \"last\" (YYYY-MM-DD: the date it fell on last time), "
              "\"words\" (3 to 6 words or short phrases captions use to mention it, including in the local language), \"motif\" (what a respectful greeting-card "
              "background for it would show: symbols, light and colours only, no people, no text, no real buildings), \"source\" (the URL of the page that confirms the date)}]}")
    got = meta.search(prompt, country=b["country"], agent="mtrend")
    try:
        raw = parse_json(got["text"]).get("occasions") or []
    except (ValueError, AttributeError):
        raw = []
    opened = {_site(x.get("url") or "") for x in got.get("sources", []) + got.get("cited", [])} - {""}
    rows, dropped, keys = [], [], set()
    for r in raw:
        row = _row(r if isinstance(r, dict) else {}, "research")
        if not row:
            dropped.append({"title": (r or {}).get("title") if isinstance(r, dict) else str(r)[:60], "why": "no usable date, title or greeting"})
        elif row["key"] in keys:
            continue  # the same occasion twice
        elif _site(row["source"]) not in opened:
            dropped.append({"title": row["title"], "why": "its date's source is not a site the search opened"})
        elif not 0 <= (date.fromisoformat(row["on"]) - today).days <= AHEAD_DAYS:
            dropped.append({"title": row["title"], "why": f"{row['on']} is not in the next year"})
        else:
            rows.append(row)
            keys.add(row["key"])
    out = {"country": b["country"], "day": today.isoformat(), "rows": rows, "dropped": dropped,
           "sources": [{"title": x.get("title"), "url": x.get("url")} for x in got.get("cited", [])][:12]}
    studio._made(office, by, "occasion calendar", b["country"], out, cause)
    return out


def _handled(office: Office) -> set[str]:
    """Occasions already prepared, or turned down for this year."""
    return {e["content"].get("occasion") for e in office.log.list() if e["type"] == "topic.saved" and e["content"].get("occasion")}


def upcoming(office: Office, today: date, within: int = LEAD_DAYS) -> list[dict]:
    """Occasions in the next `within` days not prepared or turned down yet, soonest first, each with days to go."""
    done = _handled(office)
    out = []
    for o in all_(office):
        days = (date.fromisoformat(o["on"]) - today).days
        if 0 <= days <= within and o["key"] not in done:
            out.append(o | {"days": days})
    return sorted(out, key=lambda o: o["days"])


def facts(office: Office, o: dict) -> str:
    """The true lines a greeting may use: the occasion's own, and the brand's name. Nothing about us is invented."""
    name = brand.profile(office).get("name", {}).get("value") or "the team"
    on = date.fromisoformat(o["on"])
    when = f"{'is expected on' if o['expected'] else 'falls on'} {on.day} {on.strftime('%B %Y')}"  # %-d is Linux-only
    wish = (f"{name} honours their memory." if o["sombre"] else f"Everyone at {name} wishes you and your family {o['greeting'].lower().replace('happy ', 'a happy ')}.")
    return f"{o['title']} {when}. {o['about']} {wish}"


def prepare(office: Office, key: str, *, by: str, on: str | None = None) -> str:
    """One yes: the occasion becomes a greeting post for its day. Returns the topic's ref."""
    from diwan import topics
    o = get(office, key)
    if not o:
        raise ValueError(f"No occasion {key}.")
    day = on or o["on"]
    o = o | {"on": day}
    ref = topics.save_moment(office, {"title": f"{o['title']} {day[:4]}", "what": facts(office, o),
                                      "until": (date.fromisoformat(day) + timedelta(days=1)).isoformat()}, by=by)
    office.log.append("topic.saved", actor=by, content={"ref": ref, "occasion": key, "greeting": True, "on": day, "tags": o["tags"],
                                                        "greet": o["greeting"], "greet_ar": o["greeting_ar"], "sombre": o["sombre"],
                                                        "motif": o.get("motif", ""), "words": o.get("words", [])})
    return ref


def _about(o: dict, caption: str) -> bool:
    """Whether a caption is about this occasion: its name, its greetings, its hashtags or the words people mention it with."""
    low = caption.lower().replace("#", "").replace("-", " ")
    words = {o["title"].lower(), o["greeting"].lower(), o["greeting_ar"], *(t.lstrip("#").lower() for t in o["tags"]), *o.get("words", [])}
    return any(w and re.search(rf"(?<!\w){re.escape(w)}(?!\w)", low) for w in words)


def studied(office: Office, key: str) -> dict | None:
    from diwan.agents import studio
    return studio.made(office, "occasion study", key)


def study(office: Office, key: str, cause: int | None = None) -> dict:
    """What the competitors posted for this occasion last year, read once: their posts around last year's day through
    Instagram business discovery, the ones about the occasion, and their best few looked at by Muse Spark for what made
    them work. {posts, accounts, notes}; notes is empty when there was nothing to learn from, and says why."""
    today = date.today().isoformat()
    if (done := studied(office, key)) is not None and (done.get("posts") or done.get("day") == today):
        return done  # read once; nothing found is tried again the next day, as competitors' old posts don't change but our reading can
    from diwan.agents import reader, studio
    from diwan.providers import instagram, meta
    o = get(office, key)
    if not o or not o.get("last"):
        return {"posts": [], "accounts": [], "notes": {}, "why": "the research found no date for last time"}
    day = date.fromisoformat(o["last"])
    since, until = (day - timedelta(days=WINDOW)).isoformat(), (day + timedelta(days=WINDOW)).isoformat()
    found, accounts = [], []
    for acc in studio.competitors(office.graph()):
        try:
            got = instagram.posts_between(acc, since, until, pages=12)
        except Exception as e:  # noqa: BLE001  an account that can't be read is said, not skipped silently
            accounts.append({"account": acc, "read": 0, "why": str(e)[:120]})
            continue
        accounts.append({"account": acc, "read": got.get("read", 0), "oldest": got.get("oldest")})
        found += [p | {"followers": got.get("followers")} for p in got["posts"] if _about(o, p.get("caption") or "")]
    rate = lambda p: (p["likes"] + p["comments"]) / max(1, p.get("followers") or 1)  # noqa: E731
    best = sorted(found, key=rate, reverse=True)[:MAX_STUDIED]
    notes, why = {}, ""
    covers = [(p, c) for p in best if (c := reader._cover(p.get("thumb") or p.get("media_url")))]
    if not found:
        why = f"none of {len(accounts)} competitors posted about {o['title']} between {since} and {until}"
    elif not meta.ready():
        why = "Muse Spark is not set up, so their posts were found but not looked at"
    elif covers:
        try:
            notes = meta.look(
                "You are a creative director studying competitors' greeting posts for one occasion, to brief a designer who must beat them. "
                "Look at each picture and its caption and say what the strongest ones do. works: 3 to 5 short, concrete points (layout, what is pictured, "
                "how big the greeting is, Arabic or not, colours, logo placement, tone of the words). look: one sentence on the look a designer should aim for "
                "to stand beside the best of these and beat it. words: one sentence on how the best captions greet. avoid: one sentence on what the weaker ones get wrong.",
                "\n".join(f"Picture {i}: @{p['account']}, {p['likes']} likes, {p['comments']} comments, {p.get('followers') or '?'} followers. Caption: {p['caption'][:300]}"
                          for i, (p, _) in enumerate(covers)), [c for _, c in covers], STUDY_SCHEMA, agent="mtrend")
        except (meta.MetaError, OSError, ValueError) as e:
            why = f"their posts were found but could not be looked at: {str(e)[:100]}"
    else:
        why = "their posts were found but Instagram gave no pictures for them"
    out = {"occasion": key, "day": today, "window": [since, until], "accounts": accounts, "why": why, "notes": notes,
           "posts": [{"account": p["account"], "at": (p.get("at") or "")[:10], "likes": p["likes"], "comments": p["comments"], "followers": p.get("followers"),
                      "caption": (p.get("caption") or "")[:300], "permalink": p.get("permalink"), "thumb": p.get("thumb") or p.get("media_url")} for p in best]}
    studio._made(office, "mtrend", "occasion study", key, out, cause)
    return out


def brief(office: Office, lst: dict) -> str:
    """For the writer and the designer: what the competitors' best posts for this occasion did, when it was learned."""
    key = lst.get("occasion")
    s = studied(office, key) if key else None
    if not s or not s.get("notes"):
        return ""
    n = s["notes"]
    return (f"\n\nWhat the competitors' best {(get(office, key) or {}).get('title', 'occasion')} posts last year did ({len(s['posts'])} looked at): " + "; ".join(n.get("works") or [])
            + f". Aim higher: {n.get('look', '')} Their best greetings: {n.get('words', '')} Avoid: {n.get('avoid', '')} Never copy their words.")


def when(day: str) -> str:
    """2026-12-02 as a person reads it: Wed 2 Dec."""
    d = date.fromisoformat(day)
    return f"{d:%a} {d.day} {d:%b}"  # %-d is Linux-only


def skip(office: Office, key: str, *, by: str) -> None:
    """Not this year: it is not offered again."""
    office.log.append("topic.saved", actor=by, content={"ref": f"OCC-{key}", "occasion": key, "status": "removed"})
