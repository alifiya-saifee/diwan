"""When the studio works on its own, and what it plans. Set in the studio's Setup by the Marketing manager.

  automatic   off until they turn it on; nothing starts by itself before that
  at          the hour it starts, in the business's time zone (09:00 unless they change it)
  rhythm      daily, every 2 days, or weekly: how often the trend search runs and how far ahead it plans
  no repeats  the same angle not within repeat_angle_days, the same listing not within repeat_listing_days

At the hour, the trend search runs (once per rhythm), then a listing is picked and its 3 scripts are written; they wait
for a person on the Run tab, as a run started by hand does. Daily and every 2 days plan one video; weekly plans one for
each of the next 7 days, shown as a week that can be reordered, and each day's scripts are written that morning, so
they are written from that day's facts. Nothing is filmed or published without a person.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import re

from diwan import business, topics
from diwan.office import Office

DEFAULTS = {"auto": "off", "at": "09:00", "rhythm": "daily", "repeat_angle_days": "3", "repeat_listing_days": "7", "compare_months": "12",
            "refresh": "off", "refresh_at": "07:00", "topic_share": "50", "repeat_topic_days": "14",
            "auto_post": "off", "approve_brief": "on", "archive_days": "90", "ad_budget": "0", "cpl_limit": "0"}
EVERY = {"daily": 1, "every 2 days": 2, "weekly": 7}
LABELS = {"auto": "Automatic", "at": "Start at", "rhythm": "Rhythm", "repeat_angle_days": "Don't repeat an angle within (days)",
          "repeat_listing_days": "Don't repeat a listing within (days)", "compare_months": "Compare posts from the last (months)",
          "refresh": "Refresh competitor posts every day", "refresh_at": "Refresh at",
          "topic_share": "Informational videos, as a share of all (%)", "repeat_topic_days": "Don't repeat a topic within (days)",
          "auto_post": "Post by itself at the approved time", "approve_brief": "An automatic run waits for a yes on the brief",
          "archive_days": "Archive live posts after (days)", "ad_budget": "Ad budget a month (AED)", "cpl_limit": "Limit per qualified lead (AED)"}


class Invalid(ValueError):
    pass


def settings(office: Office) -> dict:
    out = dict(DEFAULTS)
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "setting.changed" and c.get("person") == "rhythm" and c.get("key") in DEFAULTS:
            out[c["key"]] = str(c.get("value"))
    return out


def save(office: Office, values: dict, *, by: str) -> list[str]:
    cur, new = settings(office), {}
    for k, v in values.items():
        if k not in DEFAULTS:
            continue
        v = str(v).strip()
        if k in ("auto", "refresh", "auto_post", "approve_brief") and v not in ("on", "off"):
            raise Invalid(f"{LABELS[k]} is on or off.")
        if k == "rhythm" and v not in EVERY:
            raise Invalid(f"Rhythm is one of: {', '.join(EVERY)}.")
        if k in ("at", "refresh_at"):
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                raise Invalid(f"{LABELS[k]} is a time like 09:00.") from None
        if k.startswith("repeat_") and not (v.isdigit() and 0 <= int(v) <= 60):
            raise Invalid("Days are a whole number from 0 to 60.")
        if k == "topic_share" and not (v.isdigit() and 0 <= int(v) <= 100):
            raise Invalid("The share is a whole number from 0 to 100.")
        if k in ("archive_days", "ad_budget", "cpl_limit") and not v.isdigit():
            raise Invalid(f"{LABELS[k]} is a whole number.")
        if k == "compare_months" and not (v.isdigit() and 1 <= int(v) <= 60):
            raise Invalid("Months are a whole number from 1 to 60.")
        if v != cur[k]:
            new[k] = v
    for k, v in new.items():
        office.log.append("setting.changed", actor=by, content={"person": "rhythm", "key": k, "value": v})
    return list(new)


def every(office: Office) -> timedelta:
    return timedelta(days=EVERY[settings(office)["rhythm"]])


# ---------- what was used when (the no-repeat rules read this) ----------

def used(office: Office) -> list[dict]:
    """[{ref, angle, at}] for every script a person approved."""
    made = {e["content"]["id"]: e["content"] for e in office.log.list() if e["type"] == "content.made"}
    out = [{"ref": made[c["choice"]]["ref"], "angle": made[c["choice"]].get("angle"), "job": made[c["choice"]].get("job"), "at": e["at"][:10]}
           for e in office.log.list() if e["type"] == "decision.made" and (c := e["content"]).get("answer") == "approve"
           and c.get("choice") in made and made[c["choice"]].get("kind") == "script"]
    return out


def recent_angles(office: Office, today: date) -> set[str]:
    days = int(settings(office)["repeat_angle_days"])
    return {u["angle"] for u in used(office) if u["angle"] and (today - date.fromisoformat(u["at"])).days < days}


def _local_today(office: Office, now: datetime | None = None) -> date:
    return business.local(now or datetime.now(timezone.utc), office).date()


# ---------- the plan ----------

def plans(office: Office) -> list[dict]:
    return [e["content"] | {"made_at": e["at"]} for e in office.log.list() if e["type"] == "plan.made"]


def current(office: Office, today: date | None = None) -> dict | None:
    """The latest plan that still has a day from today on."""
    today = today or _local_today(office)
    for p in reversed(plans(office)):
        if any(date.fromisoformat(d["date"]) >= today for d in p["days"]):
            return p
    return None


def started(office: Office) -> set[str]:
    """The planned days whose run has started (by date)."""
    return {e["content"]["date"] for e in office.log.list() if e["type"] == "plan.started"}


def listings(office: Office) -> list[dict]:
    """What a video can be made for: our confirmed products and services, and listings that are not sold or let; with a
    permit when the business needs one."""
    from diwan import products
    need = business.permit_needed(office)
    own = [p for p in products.items(office).values() if not need or p.get("permit")]
    return own + [n.props for n in office.graph().of("listing") if (not need or n.props.get("permit")) and n.status not in ("sold", "let", "withdrawn", "retired")]


def _pick(office: Office, day: date, taken: dict[str, date]) -> tuple[str | None, str]:
    """The listing for a day: one not used within the no-repeat window, the least recently used first."""
    days = int(settings(office)["repeat_listing_days"])
    last = dict(taken)
    for u in used(office):
        d = date.fromisoformat(u["at"])
        if u["ref"] not in last or d > last[u["ref"]]:
            last[u["ref"]] = d
    pool = listings(office)
    if not pool:
        return None, "No listing has a permit yet, so there is nothing to make a video for."
    free = [x for x in pool if x["ref"] not in last or (day - last[x["ref"]]).days >= days]
    ranked = sorted(free or pool, key=lambda x: last.get(x["ref"], date.min))
    ref = ranked[0]["ref"]
    if free:
        return ref, f"Last posted {(day - last[ref]).days} days ago" if ref in last else "Not posted yet"
    return ref, f"used {(day - last[ref]).days} days ago: only {len(pool)} listing{'s' if len(pool) != 1 else ''} with a permit, fewer than your {days}-day rule needs"


def _recent_types(office: Office, today: date) -> list[str]:
    """What the last 7 days' runs were about: "topic" or "listing" (a property or a product)."""
    return ["topic" if e["content"].get("ref") and topics.get(office, e["content"]["ref"]) else "listing"
            for e in office.log.list() if e["type"] == "plan.started" and (today - date.fromisoformat(e["content"]["date"])).days < 7]


def _type_for(office: Office, today: date, planned: list[str]) -> str:
    """Listing or topic, to keep the share the Marketing manager set: a topic when topics are below it."""
    share = int(settings(office)["topic_share"])
    if share <= 0 or not topics.items(office):
        return "listing"
    if share >= 100:
        return "topic"
    seen = _recent_types(office, today) + planned
    return "topic" if seen and seen.count("topic") / len(seen) < share / 100 else "listing"


def _market_words(office: Office) -> dict[str, str]:
    """Words of the topics that win for competitors (Why they win), with who: a topic that shares them is worth making now."""
    from diwan.agents import reader
    out: dict[str, str] = {}
    try:
        for a in reader.patterns(office)["accounts"]:
            for f in a["patterns"]:
                if f["dim"] == "topic":
                    for w in re.findall(r"[a-z]{4,}", f["value"].lower()):
                        out.setdefault(w, a["account"])
    except Exception:  # noqa: BLE001  the plan never waits on the analysis
        pass
    return out


def _pick_topic(office: Office, day: date, taken: dict[str, date]) -> tuple[str | None, str]:
    """The topic for a day: one not covered within the no-repeat window; those matching what wins for competitors first,
    then the ones a person typed, then the least recently covered."""
    days = int(settings(office)["repeat_topic_days"])
    last = dict(taken)
    for u in used(office):
        d = date.fromisoformat(u["at"])
        if u["ref"] not in last or d > last[u["ref"]]:
            last[u["ref"]] = d
    pool = [t for t in topics.items(office).values() if not t.get("moment")]
    if not pool:
        return None, "No topic to make a video about yet."
    market = _market_words(office)
    hit = lambda t: sorted({market[w] for w in re.findall(r"[a-z]{4,}", f"{t['title']} {t['what']}".lower()) if w in market})  # noqa: E731
    free = [t for t in pool if t["ref"] not in last or (day - last[t["ref"]]).days >= days]
    ranked = sorted(free or pool, key=lambda t: (-len(hit(t)), t["source"] != "typed", -min(len(t["features"]), 5), last.get(t["ref"], date.min)))
    t = ranked[0]
    if not free:
        return t["ref"], f"covered {(day - last[t['ref']]).days} days ago: only {len(pool)} topic{'s' if len(pool) != 1 else ''}, fewer than your {days}-day rule needs"
    why = f"Last covered {(day - last[t['ref']]).days} days ago" if t["ref"] in last else "Not covered yet"
    return t["ref"], why + (f". It is working for @{hit(t)[0]} right now" if hit(t) else "")


def make_plan(office: Office, today: date, *, auto: bool, by: str = "mkt", days_ahead: int | None = None) -> dict:
    """One day (daily, every 2 days) or the next 7 (weekly), each with its subject (a listing or a topic) and why. A post
    with a reason to go first (a moment, a comeback, the first nine) takes its day; the rest keep the usual mix."""
    from diwan.agents import journey
    n = days_ahead or (7 if settings(office)["rhythm"] == "weekly" else 1)
    days, taken, types = [], {}, []
    first = journey.upcoming(office, n, today)
    for i in range(n):
        d = today + timedelta(days=i)
        if i < len(first):
            slot = first[i]
            if slot["ref"]:
                taken[slot["ref"]] = d
            types.append(slot["type"])
            days.append({"date": d.isoformat(), "ref": slot["ref"], "why": f"{journey.JOBS[slot['job']]['label']}: {slot['why']}", "type": slot["type"], "job": slot["job"], "status": "pending"})
            continue
        typ = _type_for(office, today, types)
        ref, why = _pick_topic(office, d, taken) if typ == "topic" else _pick(office, d, taken)
        if typ == "topic" and not ref:
            typ, (ref, why) = "listing", _pick(office, d, taken)
        if ref:
            taken[ref] = d
        types.append(typ)
        days.append({"date": d.isoformat(), "ref": ref, "why": why, "type": typ, "status": "pending"})
    content = {"rhythm": settings(office)["rhythm"], "auto": auto, "days": days}
    office.log.append("plan.made", actor=by, agent="plan", content=content)
    return content


def decide_day(office: Office, day: str, decision: str, *, by: str) -> dict:
    """A person's answer on a planned day. Approved stays on the plan and goes ahead without asking about its brief again.
    Rejected comes off, and the day takes the next best post (never one already rejected from this plan)."""
    p = current(office)
    if not p:
        raise Invalid("There is no plan to change.")
    if decision not in ("approve", "reject"):
        raise Invalid("Approve or reject.")
    ds = [dict(d) for d in p["days"]]
    d = next((x for x in ds if x["date"] == day), None)
    if d is None:
        raise Invalid("That day isn't on the plan.")
    if day in started(office):
        raise Invalid("That day's post has started: stop it from Waiting for you.")
    removed = list(p.get("removed") or [])
    if decision == "approve":
        if not d.get("ref"):
            raise Invalid("Nothing is planned that day.")
        d["status"] = "approved"
    else:
        if d.get("ref"):
            removed.append({"date": day, "ref": d["ref"], "by": by})
        when = date.fromisoformat(day)
        taken = {x["ref"]: date.fromisoformat(x["date"]) for x in ds if x.get("ref") and x is not d} | {r["ref"]: when for r in removed}
        ref, why = _pick(office, when, taken)
        if ref in {r["ref"] for r in removed} or any(x.get("ref") == ref for x in ds if x is not d):
            ref, why = None, "Removed. Nothing else to suggest for this day yet."
        d.update(ref=ref, why=why, type="listing", status="pending", job=None)
    content = {**{k: p[k] for k in ("rhythm", "auto")}, "days": ds, "removed": removed, "decided_by": by}
    office.log.append("plan.made", actor=by, agent="plan", content=content)
    return content


def approved(office: Office, ref: str | None, day: str | None = None) -> bool:
    """A person said yes to this subject on the plan: its automatic run need not ask about the brief."""
    p = current(office)
    return bool(p and ref) and any(d.get("ref") == ref and d.get("status") == "approved" and (not day or d["date"] == day) for d in p["days"])


def start_day(office: Office, day: str, *, by: str) -> str:
    """Write a planned day's post now, without waiting for the morning."""
    p = current(office)
    d = next((x for x in (p or {}).get("days", []) if x["date"] == day), None)
    if not d or not d.get("ref"):
        raise Invalid("Nothing is planned that day.")
    if day in started(office):
        raise Invalid("That day's post has already started.")
    office.log.append("plan.started", actor=by, agent="mkt", content={"date": day, "ref": d["ref"], "auto": False})
    return d["ref"]


def move(office: Office, day: str, step: int, *, by: str) -> dict:
    """Swap a planned day's listing with the next or previous day's (only days not started yet)."""
    p = current(office)
    if not p:
        raise Invalid("There is no plan to change.")
    ds = [dict(d) for d in p["days"]]
    i = next((k for k, d in enumerate(ds) if d["date"] == day), None)
    j = None if i is None else i + step
    if i is None or j is None or not 0 <= j < len(ds):
        raise Invalid("That day can't move there.")
    if {ds[i]["date"], ds[j]["date"]} & started(office):
        raise Invalid("A day whose scripts are written can't move.")
    ds[i]["ref"], ds[j]["ref"] = ds[j]["ref"], ds[i]["ref"]
    if "type" in ds[i] and "type" in ds[j]:
        ds[i]["type"], ds[j]["type"] = ds[j]["type"], ds[i]["type"]
    ds[i]["why"] = ds[j]["why"] = "moved by hand"
    content = {**{k: p[k] for k in ("rhythm", "auto")}, "days": ds, "removed": p.get("removed") or [], "moved_by": by}
    office.log.append("plan.made", actor=by, agent="plan", content=content)
    return content


def due(office: Office, now: datetime | None = None) -> str | None:
    """Called every minute. At the hour, on a day the rhythm runs, plan if needed and return the listing to run today
    (once); otherwise None."""
    s = settings(office)
    if s["auto"] != "on":
        return None
    now = now or datetime.now(timezone.utc)
    local = business.local(now, office)
    if local.strftime("%H:%M") < s["at"]:
        return None
    today = local.date()
    if today.isoformat() in started(office):
        return None
    p = current(office, today)
    if not p or not any(d["date"] == today.isoformat() for d in p["days"]):
        last = next((date.fromisoformat(x["days"][0]["date"]) for x in reversed(plans(office)) if x.get("auto")), None)
        if last and (today - last).days < EVERY[s["rhythm"]] and s["rhythm"] != "weekly":
            return None  # every 2 days: not today
        p = make_plan(office, today, auto=True)
    slot = next(d for d in p["days"] if d["date"] == today.isoformat())
    office.log.append("plan.started", actor="mkt", agent="mkt", content={"date": today.isoformat(), "ref": slot["ref"], "auto": True})
    return slot["ref"]


def next_run(office: Office, now: datetime | None = None) -> str | None:
    """When the next automatic run is, as a sentence, or None when automatic is off."""
    s = settings(office)
    if s["auto"] != "on":
        return None
    local = business.local(now or datetime.now(timezone.utc), office)
    today = local.date()
    d = today if local.strftime("%H:%M") < s["at"] and today.isoformat() not in started(office) else today + timedelta(days=1)
    last = next((date.fromisoformat(x["days"][0]["date"]) for x in reversed(plans(office)) if x.get("auto")), None)
    while s["rhythm"] != "weekly" and last and (d - last).days < EVERY[s["rhythm"]]:
        d += timedelta(days=1)
    when = "today" if d == today else "tomorrow" if d == today + timedelta(days=1) else d.strftime("%A %d %b")
    return f"Next automatic run: {when} at {s['at']} {business.tz_label(office)} ({s['rhythm']})."


# ---------- the daily refresh of competitor posts ----------

def last_refresh(office: Office) -> dict | None:
    return next(({**e["content"], "at": e["at"]} for e in reversed(office.log.list()) if e["type"] == "competitors.refreshed"), None)


def refresh_due(office: Office, now: datetime | None = None) -> bool:
    """At the hour, once a day (in the business's time zone), when the daily refresh is on. A refresh that failed counts as
    the day's try: it is not repeated every minute."""
    s = settings(office)
    if s["refresh"] != "on":
        return False
    local = business.local(now or datetime.now(timezone.utc), office)
    if local.strftime("%H:%M") < s["refresh_at"]:
        return False
    last = last_refresh(office)
    return not (last and business.local(datetime.fromisoformat(last["at"]), office).date() == local.date())


def next_refresh(office: Office, now: datetime | None = None) -> str | None:
    s = settings(office)
    if s["refresh"] != "on":
        return None
    local = business.local(now or datetime.now(timezone.utc), office)
    last = last_refresh(office)
    done = bool(last and business.local(datetime.fromisoformat(last["at"]), office).date() == local.date())
    when = "tomorrow" if done else "today"
    return f"Next refresh: {when} at {s['refresh_at']} {business.tz_label(office)}."
