"""What business we are and where: the industry, the country, the city and the time zone. Set once at onboarding in the
studio's Setup; every search, link, hour and competitor check reads it instead of assuming one. Nothing has a default:
with it unset, the steps that need it say so.

It lives in the office's log (setting.changed, person "business"), like the brand profile. Countries and time zones come
from the system's time-zone database (iso3166.tab and zone.tab), so the list is whatever the IANA database holds.
"""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from diwan.office import Office

FIELDS = {  # key: (label, what to write)
    "industry": ("Industry", "What the business does, in a few words, e.g. real estate brokerage"),
    "country": ("Country", "Where it operates"),
    "city": ("City or market", "Optional: the city or region it serves"),
    "timezone": ("Time zone", "Set from the country; pick one if the country has several"),
    "platforms": ("Where we post", "The platforms the studio writes versions for; all of them until some are picked"),
    "permit": ("Do our posts need a permit or licence number?", "yes or no: when yes, every post shows it and is held without it"),
    "languages": ("Languages we post in", "e.g. English, Arabic: scripts carry the hook in each"),
    "website": ("Our website", "The home page; the studio reads it to learn the company and its products"),
}
NEEDED = ("industry", "country")
ZONEINFO = Path("/usr/share/zoneinfo")


@lru_cache(maxsize=1)
def countries() -> list[dict]:
    """[{code, name, zones}] for every country in the time-zone database, by name."""
    names, zones = {}, {}
    try:
        for line in (ZONEINFO / "iso3166.tab").read_text().splitlines():
            if line and not line.startswith("#"):
                code, name = line.split("\t")[:2]
                names[code] = name
        for line in (ZONEINFO / "zone.tab").read_text().splitlines():
            if line and not line.startswith("#"):
                parts = line.split("\t")
                zones.setdefault(parts[0], []).append(parts[2])
    except OSError:
        return []
    return sorted(({"code": c, "name": n, "zones": sorted(zones.get(c, []))} for c, n in names.items()), key=lambda x: x["name"])


def country(code: str | None) -> dict | None:
    return next((c for c in countries() if c["code"] == (code or "").upper()), None)


def profile(office: Office) -> dict:
    """Each field's value, who set it and when (the latest change wins)."""
    out = {k: {"value": "", "by": None, "at": None} for k in FIELDS}
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "setting.changed" and c.get("person") == "business" and c.get("key") in FIELDS:
            out[c["key"]] = {"value": str(c.get("value") or "").strip(), "by": e["actor"], "at": e["at"]}
    return out


def get(office: Office) -> dict:
    """The plain values, plus the country's name."""
    v = {k: f["value"] for k, f in profile(office).items()}
    c = country(v["country"])
    return v | {"country_name": c["name"] if c else ""}


def missing(office: Office) -> list[str]:
    """The labels of what must be set before a search or a check can run."""
    v = get(office)
    return [FIELDS[k][0] for k in NEEDED if not v[k]]


def needs(office: Office, what: str) -> str | None:
    """A sentence for a step that cannot run yet, or None."""
    m = missing(office)
    return f"Set your {' and '.join(m).lower()} in Setup first, so {what}." if m else None


class Invalid(ValueError):
    pass


def save(office: Office, values: dict, *, by: str) -> list[str]:
    """Record the fields that changed; the country must be known, and the time zone one of the country's."""
    cur = get(office)
    new = {k: str(values.get(k, cur[k]) or "").strip() for k in FIELDS}
    new["country"] = new["country"].upper()
    if new["permit"].lower() not in ("", "yes", "no"):
        raise Invalid("Answer the permit question with yes or no.")
    new["permit"] = new["permit"].lower()
    if new["country"]:
        c = country(new["country"])
        if not c:
            raise Invalid(f"Unknown country code {new['country']}.")
        if new["timezone"] not in c["zones"]:
            if len(c["zones"]) != 1 and new["timezone"]:
                raise Invalid(f"{new['timezone']} is not a time zone of {c['name']}.")
            new["timezone"] = c["zones"][0] if len(c["zones"]) == 1 else ""
    changed = []
    for k, v in new.items():
        if v != cur[k]:
            office.log.append("setting.changed", actor=by, content={"person": "business", "key": k, "value": v})
            changed.append(k)
    return changed


def languages(office: Office) -> list[str]:
    """The languages posts are written in, as set; [] when not set (then English only)."""
    import re
    return [x.strip().capitalize() for x in re.split(r"[,/;]| and ", get(office)["languages"]) if x.strip()]


def permit_needed(office: Office) -> bool:
    """Whether a post must carry a permit or licence number. Until the question is answered, yes (the safer choice)."""
    return get(office)["permit"].strip().lower() != "no"


def platforms(office: Office) -> list[str]:
    """The platforms picked in Setup, or [] when none are (then every platform the studio knows)."""
    return [x.strip() for x in get(office)["platforms"].split(",") if x.strip()]


def tz(office: Office) -> tzinfo:
    """The business's time zone; UTC until one is set (and the hour is then labelled UTC)."""
    name = get(office)["timezone"]
    try:
        return ZoneInfo(name) if name else timezone.utc
    except Exception:
        return timezone.utc


def tz_label(office: Office) -> str:
    """How an hour is labelled: the city of the time zone, e.g. "Dubai time", or "UTC"."""
    name = get(office)["timezone"]
    return f"{name.split('/')[-1].replace('_', ' ')} time" if name else "UTC"


def local(t: datetime, office: Office) -> datetime:
    return t.astimezone(tz(office))


def place(office: Office) -> str:
    """"Dubai, United Arab Emirates", or the country alone, or ""."""
    v = get(office)
    return ", ".join(x for x in (v["city"], v["country_name"]) if x)


def describe(office: Office) -> str:
    """One line for a model's instructions: what the business is and where."""
    v = get(office)
    return f"The business: {v['industry'] or 'industry not set'}, in {place(office) or 'a country not set'}." if any(v.values()) else ""
