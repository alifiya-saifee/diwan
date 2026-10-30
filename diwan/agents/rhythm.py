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

from diwan import business
from diwan.office import Office

DEFAULTS = {"auto": "off", "at": "09:00", "rhythm": "daily", "repeat_angle_days": "3", "repeat_listing_days": "7"}
EVERY = {"daily": 1, "every 2 days": 2, "weekly": 7}
LABELS = {"auto": "Automatic", "at": "Start at", "rhythm": "Rhythm", "repeat_angle_days": "Don't repeat an angle within (days)",
          "repeat_listing_days": "Don't repeat a listing within (days)"}


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
        if k == "auto" and v not in ("on", "off"):
            raise Invalid("Automatic is on or off.")
        if k == "rhythm" and v not in EVERY:
            raise Invalid(f"Rhythm is one of: {', '.join(EVERY)}.")
        if k == "at":
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                raise Invalid("Start at is a time like 09:00.") from None
        if k.startswith("repeat_") and not (v.isdigit() and 0 <= int(v) <= 60):
            raise Invalid("Days are a whole number from 0 to 60.")
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
    out = [{"ref": made[c["choice"]]["ref"], "angle": made[c["choice"]].get("angle"), "at": e["at"][:10]}
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
    """Listings a video can be made for: with a permit, not sold or let."""
    return [n.props for n in office.graph().of("listing") if n.props.get("permit") and n.status not in ("sold", "let", "withdrawn", "retired")]


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
        return ref, "not used for " + (f"{(day - last[ref]).days} days" if ref in last else "a video yet")
    return ref, f"used {(day - last[ref]).days} days ago: only {len(pool)} listing{'s' if len(pool) != 1 else ''} with a permit, fewer than your {days}-day rule needs"


def make_plan(office: Office, today: date, *, auto: bool, by: str = "mkt") -> dict:
    """One day (daily, every 2 days) or the next 7 (weekly), each with its listing and why."""
    n = 7 if settings(office)["rhythm"] == "weekly" else 1
    days, taken = [], {}
    for i in range(n):
        d = today + timedelta(days=i)
        ref, why = _pick(office, d, taken)
        if ref:
            taken[ref] = d
        days.append({"date": d.isoformat(), "ref": ref, "why": why})
    content = {"rhythm": settings(office)["rhythm"], "auto": auto, "days": days}
    office.log.append("plan.made", actor=by, agent="plan", content=content)
    return content


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
    ds[i]["why"] = ds[j]["why"] = "moved by hand"
    content = {**{k: p[k] for k in ("rhythm", "auto")}, "days": ds, "moved_by": by}
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
