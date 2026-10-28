"""Broker calendars for viewings: 10:00 to 19:00 Dubai, Monday to Saturday, one hour each. A slot is free when no
booked viewing holds it."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.graph import Graph

DUBAI = timezone(timedelta(hours=4))
OPEN_HOUR, CLOSE_HOUR = 10, 19
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def busy(g: Graph, broker: str) -> set[str]:
    return {v.props["at"] for v in g.of("viewing", status="booked") if v.props["broker"] == broker}


def is_open(t: datetime) -> bool:
    return t.weekday() < 6 and OPEN_HOUR <= t.hour < CLOSE_HOUR


def free(g: Graph, broker: str, after: datetime, n: int = 3) -> list[datetime]:
    t = after.astimezone(DUBAI).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    taken, out = busy(g, broker), []
    while len(out) < n and t < after + timedelta(days=14):
        if is_open(t) and t.isoformat() not in taken:
            out.append(t)
        t += timedelta(hours=1)
    return out


def nearest(g: Graph, broker: str, want: datetime, now: datetime, n: int = 3) -> list[datetime]:
    """Free slots closest to the time asked for (same day first), never in the past: what a good receptionist offers."""
    near = sorted(free(g, broker, max(now, want - timedelta(days=2)), 40), key=lambda t: (t.date() != want.date(), abs(t - want)))
    return sorted(near[:n])


def parse(text: str, now: datetime) -> datetime | None:
    """'tomorrow 4pm', 'Thursday at 11', 'today 17:00' -> a Dubai time, or None if no day and hour are said."""
    low, local = text.lower(), now.astimezone(DUBAI)
    day = None
    if "today" in low:
        day = local.date()
    elif "tomorrow" in low:
        day = local.date() + timedelta(days=1)
    else:
        for i, d in enumerate(DAYS):
            if re.search(rf"\b{d}|\b{d[:3]}\b", low):
                day = local.date() + timedelta(days=(i - local.weekday()) % 7 or 7)
                break
    # the hour: said with am/pm or a colon first, then after "at", never a number that counts something ("2 bed", "3 million")
    m = (re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low) or re.search(r"\b(\d{1,2}):(\d{2})()", low)
         or re.search(r"\b(?:at|around|by)\s+(\d{1,2})()()\b(?!\s*(?:bed|br|bhk|room|million|m\b|k\b|sq|%|aed|year|min))", low))
    if day is None or not m:
        return None
    h = int(m.group(1))
    if m.group(3) == "pm" and h < 12:
        h += 12
    elif not m.group(3) and h < 9:
        h += 12  # "at 4" means the afternoon in an office day
    if not 0 <= h < 24:
        return None
    return datetime(day.year, day.month, day.day, h, 0, tzinfo=DUBAI)


def say(t: datetime) -> str:
    return t.strftime("%A %d %b, %I:%M %p").replace(" 0", " ")
