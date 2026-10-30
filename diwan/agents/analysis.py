"""Who our competitors are, how each is doing, which of their posts won, and why. Computed from the posts the
Competitor watch fetched (Instagram business discovery) and our own (Instagram insights); every number below is counted
from those posts and every "why" is a measured difference between outliers and the rest, with the posts behind it.

What Instagram does not give, we say instead of guessing: other accounts' views, reach and stories are not available
through the API (business discovery returns likes and comments only; stories are visible to their owner for 24 hours).
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from datetime import datetime, timezone, tzinfo

from diwan import business
from diwan.agents import reader, studio
from diwan.office import Office
from diwan.providers import meta

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _hook(p: dict) -> str:
    return (p.get("caption") or "").strip().split("\n")[0][:120]


def _at(p: dict, tz: tzinfo = timezone.utc) -> datetime | None:
    """When it was posted, in the business's time zone."""
    try:
        return datetime.fromisoformat(p["at"].replace("+0000", "+00:00")).astimezone(tz)
    except (KeyError, TypeError, ValueError):
        return None


def kpis(ps: list[dict], followers: int | None = None, tz: tzinfo = timezone.utc) -> dict:
    """The numbers for one account, from its posts; hours and days in `tz`."""
    if not ps:
        return {"posts": 0}
    eng = [p["likes"] + p["comments"] for p in ps]
    med = statistics.median(eng)
    times = sorted(t for t in (_at(p, tz) for p in ps) if t)
    weeks = max(1, (times[-1] - times[0]).days / 7) if len(times) > 1 else 1
    by_hour, by_day = {}, {}
    for p, e in zip(ps, eng):
        if (t := _at(p, tz)):
            by_hour.setdefault(t.hour, []).append(e)
            by_day.setdefault(DAYS[t.weekday()], []).append(e)
    out = {
        "posts": len(ps), "per_week": round(len(ps) / weeks, 1),
        "avg_likes": round(statistics.mean(p["likes"] for p in ps)), "avg_comments": round(statistics.mean(p["comments"] for p in ps), 1),
        "median_engagement": med,
        "formats": dict(Counter((p.get("type") or "?").replace("CAROUSEL_ALBUM", "CAROUSEL") for p in ps)),
        "best_hour": max(by_hour, key=lambda h: statistics.mean(by_hour[h])) if by_hour else None,
        "best_day": max(by_day, key=lambda d: statistics.mean(by_day[d])) if by_day else None,
        "outliers": sum(1 for q in studio.scored(ps) if studio.is_outlier(q)),
        "avg_reel": next((q["avg"] for q in studio.scored(ps) if q["kind"] == "reel" and q["avg"]), None),
        "avg_post": next((q["avg"] for q in studio.scored(ps) if q["kind"] == "post" and q["avg"]), None),
    }
    if followers:
        out["followers"] = followers
        out["engagement_rate"] = round(100 * statistics.mean(eng) / followers, 2)  # % of followers who like or comment, per post
    views = [p.get("views") for p in ps if isinstance(p.get("views"), (int, float))]
    if views:
        out["avg_views"] = round(statistics.mean(views))
        reach = [p.get("reach") for p in ps if isinstance(p.get("reach"), (int, float)) and p.get("reach")]
        if reach:
            out["engagement_rate_by_reach"] = round(100 * statistics.mean((p["likes"] + p["comments"] + (p.get("saved") or 0) + (p.get("shares") or 0)) / p["reach"]
                                                                          for p in ps if p.get("reach")), 2)
    return out


def best(ps: list[dict], n: int = 8) -> list[dict]:
    """One account's posts above its average (reels against reels, other posts against other posts), ranked by how
    far above; fair to small accounts."""
    wins = sorted((p for p in studio.scored(ps) if studio.is_outlier(p)), key=lambda p: -p["score"])
    return [{"permalink": p.get("permalink"), "hook": _hook(p), "type": (p.get("type") or "").replace("CAROUSEL_ALBUM", "CAROUSEL"), "likes": p["likes"],
             "comments": p["comments"], "x": p["score"], "engagement": p["engagement"], "avg": p["avg"], "kind": p["kind"], "at": (p.get("at") or "")[:10],
             "thumb": p.get("thumb") or (p.get("media_url") if p.get("type") not in ("VIDEO", "REELS") else None)} for p in wins[:n]]


def daily(ps: list[dict], days: int = 30) -> list[dict]:
    """What an account received on each day it posted, over the last `days` days: likes + comments of that day's posts."""
    today = studio._now().date()
    by: dict[str, dict] = {}
    for p in ps:
        t = studio._posted(p)
        if t and (today - t.date()).days < days:
            d = by.setdefault(t.date().isoformat(), {"date": t.date().isoformat(), "engagement": 0, "posts": 0})
            d["engagement"] += p["likes"] + p["comments"]; d["posts"] += 1
    return sorted(by.values(), key=lambda d: d["date"])


NOT_FOUND = re.compile(r"invalid user id|cannot find|does not exist|no user", re.I)


def growth(first: dict | None, last: dict | None) -> dict:
    """Followers gained or lost since the first check, once the two checks are on different days."""
    if not (first and last and last.get("ok") and last.get("followers") is not None and first["at"][:10] != last["at"][:10]):
        return {}
    return {"growth": last["followers"] - first["followers"], "growth_since": first["at"][:10]}


def saved_accounts(office: Office) -> list[dict]:
    """The saved competitor accounts, each with what the last check found: fetched, not found (or not a business or
    creator account: Instagram does not tell the two apart), an error, or not checked yet."""
    checks: dict[str, dict] = {}
    for e in office.log.list():
        if e["type"] == "competitor.checked":
            checks[e["content"]["account"].lower()] = e["content"] | {"at": e["at"]}
    out = []
    first: dict[str, dict] = {}
    for e in office.log.list():
        if e["type"] == "competitor.checked" and e["content"].get("ok") and e["content"].get("followers") is not None:
            first.setdefault(e["content"]["account"].lower(), e["content"] | {"at": e["at"]})
    for name in studio.competitors(office.graph()):
        c = checks.get(name.lower())
        status = "not_checked" if not c else "fetched" if c["ok"] else "not_found" if NOT_FOUND.search(c.get("error", "")) else "error"
        out.append({"account": name.lower(), "status": status, "checked_at": c and c["at"], "error": c and c.get("error"),
                    **({k: c.get(k) for k in ("followers", "media_count", "avatar", "posts_read", "fits", "fit_why")} if c else {}),
                    **growth(first.get(name.lower()), c)})
    return out


def report(office: Office) -> dict:
    saved = {n.lower() for n in studio.competitors(office.graph())}  # a removed account leaves the tables; its posts stay in the log
    comp = [p for p in studio.posts(office, "competitor") if p["account"].lower() in saved or p.get("imported")]
    ours = studio.posts(office, "own")
    followers = {}
    for p in comp:
        if p.get("followers"):
            followers[p["account"]] = p["followers"]
    accounts = {}
    for p in comp:
        accounts.setdefault(p["account"], []).append(p)
    rows, tz = [], business.tz(office)
    for acc, ps in accounts.items():
        med = statistics.median(p["likes"] + p["comments"] for p in ps)
        top = sorted(ps, key=lambda p: -(p["likes"] + p["comments"]))[:3]
        rows.append({"account": acc, "kpis": kpis(ps, followers.get(acc), tz), "best": best(ps), "daily": daily(ps),
                     "top": [{"permalink": p["permalink"], "hook": _hook(p), "type": p.get("type"), "likes": p["likes"], "comments": p["comments"],
                              "x": round((p["likes"] + p["comments"]) / med, 1) if med else None} for p in top]})
    rows.sort(key=lambda r: -(r["kpis"].get("engagement_rate") or r["kpis"].get("median_engagement") or 0))
    notes = ["Competitors' views, reach and stories are not available from Instagram's API; their numbers here are likes and comments.",
             "Our stories are only readable for 24 hours after posting, so story numbers appear only for recent stories."]
    return {"competitors": rows, "ours": {"kpis": kpis(ours, tz=tz), "posts": len(ours)}, "why": reader.patterns(office), "notes": notes,
            "names": studio.competitors(office.graph()), "accounts": saved_accounts(office)}


def suggest(office: Office) -> dict:
    """Candidate competitors from a web search, for a person to confirm. Nothing is watched until they do."""
    if not meta.ready():
        return {"ok": False, "needs": "Suggestions need Muse Spark web search (META_API_KEY). You can type the accounts yourself."}
    if (why := business.needs(office, "the suggestions are businesses like yours")):
        return {"ok": False, "needs": why}
    b, areas = business.get(office), sorted({n.props["community"] for n in office.graph().of("listing") if n.props.get("community")})
    r = meta.search(f"Which {b['industry']} businesses in {business.place(office)} post the most on Instagram"
                    + (f", especially about {', '.join(areas)}" if areas else "") + "? Use at most two searches. "
                    "List their Instagram usernames (the @handle), with the page where you found each.", country=b["country"], agent="mrival")
    handles = re.findall(r"instagram\.com/([A-Za-z0-9_.]{3,30})", " ".join([r["text"], *[s.get("url") or "" for s in r["sources"]]]))
    handles += re.findall(r"@([A-Za-z0-9_.]{3,30})", r["text"])
    skip = {"p", "reel", "reels", "explore", "stories", "accounts", "tv"}
    seen = []
    for h in handles:
        h = h.strip(".").lower()
        if h not in skip and h not in seen:
            seen.append(h)
    return {"ok": True, "suggestions": seen[:10], "sources": [c["url"] for c in r["cited"]][:5]}
