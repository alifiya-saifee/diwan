"""Broker calendars (docs/calendar-spec.md). Nothing about hours, days or kinds of appointment is fixed here: the
office's opening hours and its kinds of appointment are the owner's setting (`setting.changed` person "sales", keys
"hours" and "appointments"), and each broker's own shift and working days narrow them (diwan/leads.py). A time is free
when it is inside all of that and does not overlap a booked appointment."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.graph import Graph

DUBAI = timezone(timedelta(hours=4))
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
HOURS = {"open": "10:00", "close": "19:00", "days": [0, 1, 2, 3, 4, 5]}  # the demo office; the owner changes it
APPOINTMENTS = [
    {"id": "viewing", "name": "Site visit", "minutes": 60, "where": "property"},
    {"id": "office", "name": "Office meeting", "minutes": 60, "where": "office"},
    {"id": "video", "name": "Video call", "minutes": 30, "where": "video"},
    {"id": "call", "name": "Phone call", "minutes": 15, "where": "phone"},  # a call the client asked for at a time
]
WHERE = {"property": "At the property", "office": "At the office", "video": "Video call", "phone": "Phone call"}


def hours(g: Graph) -> dict:
    return HOURS | (g.settings.get("sales", {}).get("hours") or {})


def appointments(g: Graph) -> list[dict]:
    """The owner's kinds of appointment. A list saved before phone calls existed (or one that left it out) still gets the
    "Phone call" kind: a call the client asks for must always be a real appointment, on the calendar with its chat."""
    ks = list(g.settings.get("sales", {}).get("appointments") or APPOINTMENTS)
    if not any(k.get("where") == "phone" for k in ks):
        ks.append(next(k for k in APPOINTMENTS if k["where"] == "phone"))
    return ks


def kind(g: Graph, kid: str | None) -> dict:
    ks = appointments(g)
    return next((k for k in ks if k["id"] == kid), None) or next((k for k in ks if k["where"] == "property"), ks[0])


def _hm(v: str) -> int:
    m = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", v or "")
    if not m:
        raise ValueError("Use a time like 10:00")
    return int(m[1]) * 60 + int(m[2])


def set_hours(office, value: dict, *, by: str) -> dict:
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes the opening hours")
    v = hours(office.graph()) | {k: value[k] for k in HOURS if k in value}
    if _hm(v["open"]) >= _hm(v["close"]):
        raise ValueError("Opening must be before closing")
    v["days"] = sorted({int(d) for d in v["days"] if 0 <= int(d) <= 6})
    if not v["days"]:
        raise ValueError("Open at least one day")
    office.log.append("setting.changed", actor=by, content={"person": "sales", "key": "hours", "value": v})
    return v


def set_appointments(office, ks: list[dict], *, by: str) -> list[dict]:
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes the kinds of appointment")
    out, seen = [], set()
    for k in ks:
        nm = str(k.get("name") or "").strip()
        if not nm:
            raise ValueError("Each kind needs a name")
        kid = k.get("id") or re.sub(r"[^a-z0-9]+", "_", nm.lower()).strip("_")
        if kid in seen:
            raise ValueError(f"Two kinds are called {nm}")
        try:
            minutes = int(k.get("minutes"))
        except (TypeError, ValueError):
            raise ValueError(f"{nm}: how many minutes?") from None
        if not 15 <= minutes <= 240 or minutes % 15:
            raise ValueError(f"{nm}: 15 to 240 minutes, in steps of 15")
        if k.get("where") not in WHERE:
            raise ValueError(f"{nm}: where it happens")
        seen.add(kid)
        out.append({"id": kid, "name": nm, "minutes": minutes, "where": k["where"]})
    if not any(k["where"] == "property" for k in out):
        raise ValueError("Keep one kind at the property: a client asking to see a property needs it")
    office.log.append("setting.changed", actor=by, content={"person": "sales", "key": "appointments", "value": out})
    return out


def window(g: Graph, broker: str, day) -> tuple[int, int] | None:
    """Minutes from midnight when this broker can be booked on `day`: the office's hours and days, narrowed by the
    broker's own shift and working days. None on a day off."""
    from diwan import leads
    h = hours(g)
    days = leads.setting(g, broker, "days")
    if day.weekday() not in h["days"] or (days is not None and day.weekday() not in days):
        return None
    lo, hi = _hm(h["open"]), _hm(h["close"])
    if shift := leads.setting(g, broker, "shift"):
        a, b = (_hm(x) for x in shift.split("-"))
        lo, hi = max(lo, a), min(hi, b)
    return (lo, hi) if lo < hi else None


def booked(g: Graph, broker: str) -> list[tuple[datetime, datetime, str]]:
    out = []
    for v in g.of("viewing", status={"booked", "requested"}):  # a time waiting for the owner is held too
        if v.props["broker"] == broker:
            s = datetime.fromisoformat(v.props["at"])
            out.append((s, s + timedelta(minutes=int(v.props.get("minutes") or 60)), v.id))
    return out


def busy(g: Graph, broker: str) -> set[str]:
    return {s.isoformat() for s, _, _ in booked(g, broker)}


# The broker's own time (docs/calendar-own-time-spec.md): busy blocks, weekly or once, and days off. Events
# `calendar.blocked` (a new id, or the same id to change it) and `calendar.unblocked`; graph nodes of type "block".
WEEK = timedelta(days=7)


def blocks(g: Graph, broker: str | None = None) -> list:
    return [b for b in g.of("block", status="active") if broker is None or b.props["broker"] == broker]


def occurrences(b, lo: datetime, hi: datetime) -> list[tuple[datetime, datetime]]:
    """The times a block covers between lo and hi: once, or every week from its start until its `until` day."""
    p = b.props
    s, e = datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"])
    if p.get("repeat") != "weekly":
        return [(s, e)] if s < hi and lo < e else []
    until = datetime.fromisoformat(p["until"] + "T23:59:59+04:00") if p.get("until") else None
    k = max(0, (lo - e) // WEEK)
    out = []
    while s + k * WEEK < hi and (until is None or s + k * WEEK <= until):
        a, z = s + k * WEEK, e + k * WEEK
        if a < hi and lo < z:
            out.append((a, z))
        k += 1
    return out


def blocked(g: Graph, broker: str, t: datetime, end: datetime):
    """The block that covers any of t..end, or None."""
    return next((b for b in blocks(g, broker) if occurrences(b, t, end)), None)


def is_open(g: Graph, broker: str, t: datetime, minutes: int = 60, ignore: str | None = None) -> bool:
    t = t.astimezone(DUBAI)
    w = window(g, broker, t.date())
    start = t.hour * 60 + t.minute
    if not w or start < w[0] or start + minutes > w[1]:
        return False
    end = t + timedelta(minutes=minutes)
    if blocked(g, broker, t, end):
        return False
    return not any(s < end and t < e for s, e, vid in booked(g, broker) if vid != ignore)


def _may(by: str, broker: str) -> None:
    from diwan import leads, qualify
    if broker not in leads.brokers() and not (broker == by and by in qualify.owner_ids()):  # the owner keeps time of their own too
        raise ValueError(f"{broker} is not a broker")
    if by != broker and by not in qualify.owner_ids():
        raise PermissionError("A broker changes only their own calendar; the owner changes anyone's")


def block(office, *, by: str, broker: str, start: datetime, end: datetime, reason: str = "", repeat: str | None = None,
          until: str | None = None, kind: str = "busy", bid: str | None = None, now: datetime | None = None) -> dict:
    """Mark time the broker can't be booked: `kind` "busy" (a few hours, once or every week) or "off" (whole days).
    Refused when it covers an appointment already booked, so the client is never left without their broker."""
    from diwan.people import name
    _may(by, broker)
    g = office.graph()
    now = now or datetime.now(DUBAI)
    if bid and (bid not in g.nodes or g.nodes[bid].type != "block" or g.nodes[bid].status != "active"):
        raise ValueError("No such busy time")
    if bid and g.nodes[bid].props["broker"] != broker:
        _may(by, g.nodes[bid].props["broker"])
    if kind not in ("busy", "off") or repeat not in (None, "weekly"):
        raise ValueError("Unknown kind of busy time")
    if end <= start:
        raise ValueError("The end must be after the start")
    if end <= now:
        raise ValueError("That time has already passed")
    if kind == "busy" and end - start > timedelta(hours=24):
        raise ValueError("For more than a day, use Day off")
    if until and until < start.astimezone(DUBAI).date().isoformat():
        raise ValueError("Stop repeating after it starts")
    probe = type("B", (), {"props": {"start": start.isoformat(), "end": end.isoformat(), "repeat": repeat, "until": until}})
    clash = [(s, vid) for s, e, vid in booked(g, broker) if e > now and occurrences(probe, s, e)]
    if clash:
        s, vid = min(clash)
        v = g.nodes[vid].props
        more = f" (and {len(clash) - 1} more)" if len(clash) > 1 else ""
        raise ValueError(f"{name(broker)} has {v.get('kind_name') or 'a site visit'} with {v.get('customer')} on {say(s)}{more}: move it first")
    bid = bid or f"B{len(g.of('block')) + 1}"
    content = {"id": bid, "broker": broker, "kind": kind, "start": start.astimezone(DUBAI).isoformat(), "end": end.astimezone(DUBAI).isoformat(),
               "reason": (reason or "").strip()[:120] or None, "repeat": repeat, "until": until}
    office.log.append("calendar.blocked", actor=by, content=content)
    return content


def day_off(office, *, by: str, broker: str, first: str, last: str, reason: str = "", now: datetime | None = None) -> dict:
    from datetime import date
    a, z = date.fromisoformat(first), date.fromisoformat(last)
    if z < a:
        raise ValueError("The last day can't be before the first")
    start = datetime(a.year, a.month, a.day, tzinfo=DUBAI)
    return block(office, by=by, broker=broker, start=start, end=datetime(z.year, z.month, z.day, tzinfo=DUBAI) + timedelta(days=1),
                 reason=reason, kind="off", now=now)


def unblock(office, bid: str, *, by: str) -> None:
    g = office.graph()
    b = g.nodes.get(bid)
    if not b or b.type != "block" or b.status != "active":
        raise ValueError("No such busy time")
    _may(by, b.props["broker"])
    office.log.append("calendar.unblocked", actor=by, content={"id": bid})


def free(g: Graph, broker: str, after: datetime, n: int = 3, minutes: int = 60, ignore: str | None = None) -> list[datetime]:
    """The next free start times on the hour (and half hour for short kinds), within two weeks."""
    step = 30 if minutes <= 30 else 60
    t = after.astimezone(DUBAI).replace(second=0, microsecond=0)
    t = t.replace(minute=0) + timedelta(hours=1)
    out = []
    while len(out) < n and t < after + timedelta(days=14):
        if is_open(g, broker, t, minutes, ignore):
            out.append(t)
        t += timedelta(minutes=step)
    return out


def nearest(g: Graph, broker: str, want: datetime, now: datetime, n: int = 3, minutes: int = 60, ignore: str | None = None) -> list[datetime]:
    """Free times closest to the time asked for (same day first), never in the past: what a good receptionist offers."""
    near = sorted(free(g, broker, max(now, want - timedelta(days=2)), max(40, n), minutes, ignore),
                  key=lambda t: (t.date() != want.date(), abs(t - want)))
    return sorted(near[:n])


TOMORROW = r"tomorrow|tommorow|tomorow|tomorrw|tmrw|tmrrw|tmrow|tmr|tmw|tomo|2moro|2morrow|2mrw|2mro"  # how people type it


MONTH = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?:[a-z]*)\.?"
COUNTS = r"(?!\s*(?:bed|br|bhk|room|million|m\b|k\b|sq|%|aed|year|min|am|pm|:))"  # "2 bed", "3 million", "4pm": not a date
NOT_THEN = r"\b(busy|not|can'?t|cannot|no|except|unless)\b[^.,;]{0,8}$"  # "busy Tuesday", "not on Tuesday"


def _ahead(d: int, m: int, y: int | None, today):
    """A day and month they wrote: this year, or next year once it has passed (a year they wrote is kept)."""
    from datetime import date
    try:
        x = date(y or today.year, m, d)
        return date(today.year + 1, m, d) if y is None and x < today else x
    except ValueError:
        return None


def _date(low: str, local: datetime):
    """A written date: '10 Nov', 'Nov 10th', '10th of November', '10/11' (day first, as in the UAE), 'the 10th'."""
    today = local.date()
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    if m := re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s+{MONTH}(?:\s+(\d{{4}}))?\b", low):
        return _ahead(int(m[1]), months.index(m[2]) + 1, int(m[3]) if m[3] else None, today)
    if m := re.search(rf"\b{MONTH}\s+(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\b{COUNTS}", low):
        return _ahead(int(m[2]), months.index(m[1]) + 1, None, today)
    if m := re.search(rf"\b(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{2,4}}))?\b{COUNTS}", low):
        y = int(m[3]) if m[3] else None
        return _ahead(int(m[1]), int(m[2]), y + 2000 if y and y < 100 else y, today)
    if m := re.search(r"\b(?:the|on)\s+(\d{1,2})(?:st|nd|rd|th)\b", low):  # "the 10th": this month, or next once it has passed
        x = _ahead(int(m[1]), today.month, today.year, today)
        if x is None or x < today:
            nxt = today.replace(day=1) + timedelta(days=32)
            x = _ahead(int(m[1]), nxt.month, nxt.year, today)
        return x
    return None


def _weekday(low: str):
    """The weekday they mean: the first one said, skipping one they can't do ("busy Tuesday, Wednesday works")."""
    hits = []
    for i, d in enumerate(DAYS):
        short = {"tuesday": "|tues", "wednesday": "|weds", "thursday": "|thur|thurs"}.get(d, "")
        for m in re.finditer(rf"\b(?:{d}s?|{d[:3]}{short})\b", low):
            after = low[m.end():m.end() + 20]
            if re.search(NOT_THEN, low[max(0, m.start() - 20):m.start()]) or re.match(r"\W*(?:is |'s )?(?:not|no good|busy|bad|doesn'?t|won'?t)\b", after):
                continue
            hits.append((m.start(), i))
    return min(hits)[1] if hits else None


def _day(low: str, local: datetime):
    if (written := _date(low, local)) is not None:  # a date they wrote wins over a weekday
        return written
    if "today" in low or "tonight" in low or "this evening" in low:
        return local.date()
    if re.search(rf"\b(?:{TOMORROW})\b", low):
        return local.date() + timedelta(days=1)
    if (i := _weekday(low)) is not None:
        return local.date() + timedelta(days=(i - local.weekday()) % 7 or 7)
    if re.search(r"\bweekend\b", low):  # the UAE weekend: Saturday and Sunday
        return local.date() + timedelta(days=(5 - local.weekday()) % 7 if local.weekday() != 6 else 0)
    if re.search(r"\bnext week\b", low):
        return local.date() + timedelta(days=7 - local.weekday())
    return None


def say_day(d) -> str:
    return f"{d:%A} {d.day} {d:%b}"


def which_day(text: str, now: datetime) -> list | None:
    """When their words could mean two days, the two (Rania asks rather than guesses): a weekday that isn't the date's
    ("Wednesday 10 Nov"), "next Tuesday", or today's weekday said today ("Monday at 4" on a Monday)."""
    low, local = text.lower(), now.astimezone(DUBAI)
    today, w = local.date(), _weekday(low)
    if w is None:
        return None
    if (d := _date(low, local)) is not None:
        if w == d.weekday():
            return None
        step = (w - d.weekday()) % 7
        other = d + timedelta(days=step if step <= 3 else step - 7)
        return sorted([d, other if other >= today else other + timedelta(days=7)])
    if "today" in low or "tonight" in low or re.search(rf"\b(?:{TOMORROW})\b", low) or re.search(rf"\bthis\s+{DAYS[w][:3]}", low):
        return None
    coming = today + timedelta(days=(w - today.weekday()) % 7)
    if re.search(rf"\bnext\s+{DAYS[w][:3]}", low):
        coming = coming if coming > today else coming + timedelta(days=7)
        return [coming, coming + timedelta(days=7)]
    return [today, today + timedelta(days=7)] if coming == today else None


def with_day(text: str, d) -> str:
    """Their words with the day they confirmed in place of the words that could mean two days."""
    for rx in (rf"\b\d{{1,2}}(?:st|nd|rd|th)?(?:\s+of)?\s+{MONTH}(?:\s+\d{{4}})?\b", rf"\b{MONTH}\s+(?:the\s+)?\d{{1,2}}(?:st|nd|rd|th)?\b(?!\s*(?:am|pm|:))",
               r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", r"\b(?:the|on)\s+\d{1,2}(?:st|nd|rd|th)\b", r"\b(?:next|this|coming)\s+(?=[a-z]*day|tue|wed|thu|fri|sat|sun|mon)",
               rf"\b(?:{'|'.join(DAYS)})s?\b|\b(?:mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)\b"):
        text = re.sub(rx, " ", text, flags=re.I)
    return re.sub(r"\s{2,}", " ", f"{text.strip()} on {say_day(d)}")


def answer_day(text: str, options: list, now: datetime):
    """Their answer to "do you mean A or B?": one of the two, or a date they wrote instead. None if it isn't an answer."""
    from datetime import date
    low, local = text.lower(), now.astimezone(DUBAI)
    opts = [o if isinstance(o, date) else date.fromisoformat(o) for o in options]
    if re.search(r"\b(first|1st|former|earlier|sooner|this one|the coming)\b", low):
        return opts[0]
    if re.search(r"\b(second|2nd|latter|later one|the other|week after|following)\b", low):
        return opts[-1]
    if (d := _date(low, local)) is not None:
        return d
    if "today" in low and local.date() in opts:
        return local.date()
    if (w := _weekday(low)) is not None:
        same = [o for o in opts if o.weekday() == w]
        return same[0] if len(same) == 1 else None
    return None


ZONES = {r"\b(london|uk|british|gmt|bst)\s+time\b": "Europe/London", r"\b(india|indian|ist)\s+time\b": "Asia/Kolkata", r"\b(moscow|russia)\s+time\b": "Europe/Moscow",
         r"\b(riyadh|saudi|ksa)\s+time\b": "Asia/Riyadh", r"\b(paris|berlin|cet)\s+time\b": "Europe/Paris", r"\b(new york|eastern|est|edt)\s+time\b": "America/New_York"}


def in_their_time(text: str, at: datetime) -> tuple[datetime, str | None]:
    """"Call me at 4, London time": the clock they mean, as Dubai time for the calendar. Only when they name it."""
    from zoneinfo import ZoneInfo
    low = text.lower()
    for rx, zone in ZONES.items():
        if m := re.search(rx, low):
            return at.replace(tzinfo=ZoneInfo(zone)).astimezone(DUBAI), m.group(0)
    return at, None


def parse_day(text: str, now: datetime) -> datetime | None:
    """'Saturday morning', 'Thursday': the start of that day or part of it, in Dubai, for offering its free times."""
    low, local = text.lower(), now.astimezone(DUBAI)
    day = _day(low, local)
    if day is None:
        return None
    hour = 12 if "afternoon" in low else 16 if "evening" in low else 0
    return datetime(day.year, day.month, day.day, hour, tzinfo=DUBAI)


def parse(text: str, now: datetime) -> datetime | None:
    """'tomorrow 4pm', 'Thursday at 11', 'today 17:00' -> a Dubai time, or None if no day and hour are said."""
    low, local = text.lower(), now.astimezone(DUBAI)
    day = _day(low, local)
    # the hour: said with am/pm or a colon first, then after "at", never a number that counts something ("2 bed", "3 million")
    unit = r"(?!\s*(?:bed|br|bhk|room|million|m\b|k\b|sq|%|aed|year|min))"
    m = (re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low) or re.search(r"\b(\d{1,2}):(\d{2})()", low)
         or re.search(rf"\b(\d{{1,2}})()()\s+(?:{TOMORROW}|today|tonight)\b", low)  # "10 tmrw"
         or re.search(rf"\b(?:{TOMORROW}|today|tonight)\s+(?:at\s+)?(\d{{1,2}})()()(?!:){unit}\b", low)  # "tmrw 10"
         or re.search(r"\b(?:at|around|by)\s+(\d{1,2})()()\b(?!\s*(?:bed|br|bhk|room|million|m\b|k\b|sq|%|aed|year|min))", low))
    nums = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
    n_ = rf"(\d{{1,2}}|{'|'.join(nums)})"
    words = re.search(rf"\b(noon|midday)\b|\b(half|quarter)\s+(past|to)\s+{n_}\b|\b{n_}\s*o'?\s*clock\b", low)  # the clock in words
    if day is None or not (m or words):
        return None
    hour = lambda w: int(w) if w.isdigit() else nums.index(w) + 1  # noqa: E731
    if words and not (m and m.group(3)):
        if words[1]:
            h, mi, ampm = 12, 0, "pm"
        elif words[2]:
            h, mi, ampm = hour(words[4]), 30 if words[2] == "half" else 15, None
            if words[3] == "to":
                h, mi = h - 1, 45 if words[2] == "quarter" else 30
        else:
            h, mi, ampm = hour(words[5]), 0, None
    else:
        h, mi, ampm = int(m.group(1)), int(m.group(2)) if m.group(2) else 0, m.group(3)
    if ampm == "pm" and h < 12:
        h += 12
    elif not ampm and h < 9:
        h += 12  # "at 4" means the afternoon in an office day
    if not 0 <= h < 24:
        return None
    return datetime(day.year, day.month, day.day, h, mi, tzinfo=DUBAI)


def say(t: datetime) -> str:
    t = t.astimezone(DUBAI)
    return t.strftime("%A %d %b, %I:%M %p").replace(" 0", " ")


def week(g: Graph, start, *, person: str, broker: str | None = None, now: datetime | None = None, n: int = 7) -> dict:
    """The calendar page: seven days from `start`, each broker's bookable hours per day, and their appointments. The
    owner sees every broker (and can filter to one); a broker sees only their own."""
    from diwan import leads, qualify
    from diwan.people import PEOPLE, name
    owner = person in qualify.owner_ids() or PEOPLE.get(person, {}).get("role") == "Sales manager"  # both see every broker
    team = leads.brokers()
    if not owner:
        if person not in team:
            raise PermissionError("Only the owner and brokers see the calendar")
        broker = person
    shown = [b for b in team if not broker or b == broker]
    if not 1 <= n <= 92:
        raise ValueError("Show 1 to 92 days at a time")
    days = [start + timedelta(days=i) for i in range(n)]
    appts = []
    for v in g.of("viewing"):
        p = v.props
        at = datetime.fromisoformat(p["at"]).astimezone(DUBAI)
        if p["broker"] in shown and days[0] <= at.date() <= days[-1]:
            k = kind(g, p.get("kind"))
            appts.append({"id": v.id, "broker": p["broker"], "at": at.isoformat(), "minutes": int(p.get("minutes") or k["minutes"]),
                          "kind": p.get("kind_name") or k["name"], "where": p.get("where") or k["where"], "customer": p.get("customer"),
                          "listing": p.get("listing"), "chat": p.get("chat"), "status": v.status, "moved_from": p.get("moved_from"),
                          "reminded": [r for r in p.get("reminded") or []], "deal": v.deal, "by_hand": p.get("by_hand"), "link": p.get("link"), "phone": p.get("chat"),
                          "visit": (g.nodes[f"deal:{v.deal}"].props.get("visit") or {}) if v.deal and (g.nodes.get(f"deal:{v.deal}").props.get("visit") or {}).get("appointment") == v.id else None})
    lo = datetime(days[0].year, days[0].month, days[0].day, tzinfo=DUBAI)
    busy_ = [{"id": b.id, "broker": b.props["broker"], "kind": b.props["kind"], "start": s.astimezone(DUBAI).isoformat(),
              "end": e.astimezone(DUBAI).isoformat(), "repeat": b.props.get("repeat"), "until": b.props.get("until"),
              "first": b.props["start"], "last": b.props["end"],
              "reason": b.props.get("reason") if owner or person == b.props["broker"] else None,  # colleagues see "Busy" only
              "can": owner or person == b.props["broker"]}
             for b in g.of("block", status="active") if b.props["broker"] in shown
             for s, e in occurrences(b, lo, lo + timedelta(days=n))]
    return {"days": [d.isoformat() for d in days], "owner": owner, "broker": broker, "blocks": busy_,
            "brokers": [{"id": b, "name": name(b), "days": {d.isoformat(): window(g, b, d) for d in days}} for b in shown],
            "all_brokers": [{"id": b, "name": name(b)} for b in team] if owner else [],
            "viewers": [{"id": p, "name": name(p), "owner": p in qualify.owner_ids()} for p in sorted(qualify.owner_ids()) + team],
            "appointments": sorted(appts, key=lambda a: a["at"]), "hours": hours(g), "kinds": appointments(g), "where": WHERE,
            "insights": insights(g, shown, days, now or datetime.now(DUBAI))}


def _open_minutes(g: Graph, b: str, d) -> int:
    """Bookable minutes on day `d`: the broker's window less their busy time and days off."""
    w = window(g, b, d)
    if not w:
        return 0
    lo = datetime(d.year, d.month, d.day, tzinfo=DUBAI) + timedelta(minutes=w[0])
    hi = lo + timedelta(minutes=w[1] - w[0])
    cut = sum((min(e, hi) - max(s, lo)).total_seconds() / 60 for x in blocks(g, b) for s, e in occurrences(x, lo, hi))
    return max(0, int(w[1] - w[0] - cut))


def insights(g: Graph, shown: list[str], days: list, now: datetime) -> dict:
    """The week at a glance, all counted from the log: appointments by kind against last week, how much of each
    broker's bookable time is booked, what needs someone (past and not marked, now outside the broker's hours), and
    the next appointment."""
    from diwan.people import name
    lo = datetime(days[0].year, days[0].month, days[0].day, tzinfo=DUBAI)
    hi, prev = lo + timedelta(days=len(days)), lo - timedelta(days=len(days))
    vs = [v for v in g.of("viewing") if v.props["broker"] in shown and v.status != "cancelled"]
    at = lambda v: datetime.fromisoformat(v.props["at"])  # noqa: E731
    this = [v for v in vs if lo <= at(v) < hi]
    by_kind: dict[str, int] = {}
    for v in this:
        k = v.props.get("kind_name") or kind(g, v.props.get("kind"))["name"]
        by_kind[k] = by_kind.get(k, 0) + 1
    load = []
    for b in shown:
        mine = [v for v in this if v.props["broker"] == b]
        open_ = sum(_open_minutes(g, b, d) for d in days)
        used = sum(int(v.props.get("minutes") or 60) for v in mine)
        off = [d.isoformat() for d in days if window(g, b, d) and _open_minutes(g, b, d) == 0]
        load.append({"broker": b, "name": name(b), "booked": len(mine), "minutes": used, "open": open_,
                     "pct": min(100, round(100 * used / open_)) if open_ else None, "off": off})
    attention = []
    for v in sorted(vs, key=at):
        p, t = v.props, at(v)
        if v.status == "booked" and t + timedelta(minutes=int(p.get("minutes") or 60)) < now:
            attention.append({"id": v.id, "why": "Past, not marked Done or No-show", "text": f"{p.get('customer')} · {say(t)}", "broker": p["broker"], "at": p["at"]})
        elif v.status == "booked" and t > now:
            w = window(g, p["broker"], t.astimezone(DUBAI).date())
            m = t.astimezone(DUBAI).hour * 60 + t.astimezone(DUBAI).minute
            if not w or m < w[0] or m + int(p.get("minutes") or 60) > w[1] or blocked(g, p["broker"], t, t + timedelta(minutes=int(p.get("minutes") or 60))):
                attention.append({"id": v.id, "why": f"Now outside {name(p['broker'])}'s hours", "text": f"{p.get('customer')} · {say(t)}", "broker": p["broker"], "at": p["at"]})
    nxt = next((v for v in sorted(vs, key=at) if v.status == "booked" and at(v) > now), None)
    return {"total": len(this), "last_week": len([v for v in vs if prev <= at(v) < lo]), "by_kind": by_kind, "load": load,
            "attention": attention[:8], "attention_more": max(0, len(attention) - 8),
            "next": {"id": nxt.id, "at": nxt.props["at"], "customer": nxt.props.get("customer"), "listing": nxt.props.get("listing"),
                     "kind": nxt.props.get("kind_name"), "broker": nxt.props["broker"]} if nxt else None}


def search(g: Graph, q: str, *, person: str, limit: int = 30) -> list[dict]:
    """Appointments of any date and status whose client name, phone or property matches; the owner searches every
    broker, a broker their own."""
    from diwan import leads, qualify
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    owner = person in qualify.owner_ids()
    if not owner and person not in leads.brokers():
        raise PermissionError("Only the owner and brokers see the calendar")
    digits = re.sub(r"\D", "", q)
    out = []
    for v in g.of("viewing"):
        p = v.props
        if not owner and p["broker"] != person:
            continue
        hay = " ".join(str(p.get(k) or "") for k in ("customer", "listing", "kind_name")).lower()
        if q in hay or (len(digits) >= 4 and digits in (p.get("chat") or "")):
            out.append({"id": v.id, "at": p["at"], "customer": p.get("customer"), "kind": p.get("kind_name") or kind(g, p.get("kind"))["name"],
                        "listing": p.get("listing"), "broker": p["broker"], "status": v.status})
    return sorted(out, key=lambda a: a["at"], reverse=True)[:limit]


def _ics_text(v: str) -> str:
    return (v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics(g: Graph, view: dict) -> str:
    """The calendar range as iCalendar: one event per appointment (not cancelled) and each busy time as "Busy"."""
    from diwan.people import name
    utc = lambda iso: datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")  # noqa: E731
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Diwan//Calendar//EN", "CALSCALE:GREGORIAN"]
    for a in view["appointments"]:
        if a["status"] == "cancelled":
            continue
        end = (datetime.fromisoformat(a["at"]) + timedelta(minutes=a["minutes"])).isoformat()
        lst = g.nodes.get(f"listing:{a['listing']}") if a.get("listing") else None
        where = f"{lst.props['title']}, {lst.props['community']}" if lst else WHERE.get(a["where"], "")
        link = (a.get("link") or {}).get("url")
        desc = "\n".join(x for x in (f"Client: {a['customer']}", f"Phone: +{a['phone']}" if a.get("phone") else "",
                                       f"Property: {a['listing']}" if a.get("listing") else "", f"Broker: {name(a['broker'])}",
                                       f"Join: {link}" if link else "") if x)
        out += ["BEGIN:VEVENT", f"UID:{a['id']}@diwan", f"DTSTAMP:{stamp}", f"DTSTART:{utc(a['at'])}", f"DTEND:{utc(end)}",
                f"SUMMARY:{_ics_text(a['kind'] + ' · ' + str(a['customer']))}", f"LOCATION:{_ics_text(link or where)}",
                f"DESCRIPTION:{_ics_text(desc)}"] + ([f"URL:{link}"] if link else []) + ["END:VEVENT"]
    for b in view["blocks"]:
        out += ["BEGIN:VEVENT", f"UID:{b['id']}-{utc(b['start'])}@diwan", f"DTSTAMP:{stamp}", f"DTSTART:{utc(b['start'])}",
                f"DTEND:{utc(b['end'])}", f"SUMMARY:{'Day off' if b['kind'] == 'off' else 'Busy'}", "TRANSP:OPAQUE", "END:VEVENT"]
    return "\r\n".join(out + ["END:VCALENDAR"]) + "\r\n"
