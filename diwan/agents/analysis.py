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
from datetime import datetime, timedelta

from diwan.agents import studio
from diwan.office import Office
from diwan.providers import meta

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
AREAS = r"\b(marina|jvc|downtown|business bay|palm|creek|hills|jbr|meydan|arabian ranches|dubai south)\b"

FEATURES = {
    "is a reel or video": lambda p: p.get("type") in ("VIDEO", "REELS"),
    "is a carousel": lambda p: p.get("type") == "CAROUSEL_ALBUM",
    "opens with a question": lambda p: "?" in _hook(p) or "؟" in _hook(p),
    "puts a price or number in the first line": lambda p: bool(re.search(r"\d|aed|million|\bm\b|k\b", _hook(p).lower())),
    "names an area": lambda p: bool(re.search(AREAS, (p.get("caption") or "").lower())),
    "has Arabic in the caption": lambda p: bool(re.search(r"[؀-ۿ]", p.get("caption") or "")),
    "asks people to DM, comment or call": lambda p: bool(re.search(r"\b(dm|comment|call|whatsapp|link in bio|book|message us)\b", (p.get("caption") or "").lower())),
    "has a short caption (under 150 characters)": lambda p: len(p.get("caption") or "") < 150,
    "was posted in the evening (6 to 11 PM Dubai)": lambda p: 18 <= _hour(p) <= 23,
    "uses 5 or more hashtags": lambda p: (p.get("caption") or "").count("#") >= 5,
}


def _hook(p: dict) -> str:
    return (p.get("caption") or "").strip().split("\n")[0][:120]


def _at(p: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(p["at"].replace("+0000", "+00:00")) + timedelta(hours=4)
    except (KeyError, TypeError, ValueError):
        return None


def _hour(p: dict) -> int:
    t = _at(p)
    return t.hour if t else -1


def kpis(ps: list[dict], followers: int | None = None) -> dict:
    """The numbers for one account, from its posts."""
    if not ps:
        return {"posts": 0}
    eng = [p["likes"] + p["comments"] for p in ps]
    med = statistics.median(eng)
    times = sorted(t for t in (_at(p) for p in ps) if t)
    weeks = max(1, (times[-1] - times[0]).days / 7) if len(times) > 1 else 1
    by_hour, by_day = {}, {}
    for p, e in zip(ps, eng):
        if (t := _at(p)):
            by_hour.setdefault(t.hour, []).append(e)
            by_day.setdefault(DAYS[t.weekday()], []).append(e)
    out = {
        "posts": len(ps), "per_week": round(len(ps) / weeks, 1),
        "avg_likes": round(statistics.mean(p["likes"] for p in ps)), "avg_comments": round(statistics.mean(p["comments"] for p in ps), 1),
        "median_engagement": med,
        "formats": dict(Counter((p.get("type") or "?").replace("CAROUSEL_ALBUM", "CAROUSEL") for p in ps)),
        "best_hour": max(by_hour, key=lambda h: statistics.mean(by_hour[h])) if by_hour else None,
        "best_day": max(by_day, key=lambda d: statistics.mean(by_day[d])) if by_day else None,
        "outliers": sum(1 for e in eng if med and e >= 2 * med),
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


def why(ps: list[dict]) -> list[dict]:
    """What outliers (2x their account's median or more) have that the other posts do not, as measured shares."""
    by_acc: dict[str, list] = {}
    for p in ps:
        by_acc.setdefault(p["account"], []).append(p)
    wins, rest = [], []
    for acc, rows in by_acc.items():
        if len(rows) < 5:
            continue
        med = statistics.median(r["likes"] + r["comments"] for r in rows)
        for r in rows:
            (wins if med and r["likes"] + r["comments"] >= 2 * med else rest).append(r)
    if len(wins) < 2 or not rest:
        return []
    out = []
    for label, f in FEATURES.items():
        a = sum(1 for p in wins if f(p)) / len(wins)
        b = sum(1 for p in rest if f(p)) / len(rest)
        if abs(a - b) >= .25:
            out.append({"finding": f"Outliers {'more' if a > b else 'less'} often {label}: {round(a * 100)}% of {len(wins)} outliers vs {round(b * 100)}% of {len(rest)} other posts.",
                        "feature": label, "outliers": round(a * 100), "others": round(b * 100),
                        "examples": [p["permalink"] for p in wins if f(p) == (a > b)][:3]})
    return sorted(out, key=lambda x: -abs(x["outliers"] - x["others"]))


def report(office: Office) -> dict:
    comp = studio.posts(office, "competitor")
    ours = studio.posts(office, "own")
    followers = {}
    for p in comp:
        if p.get("followers"):
            followers[p["account"]] = p["followers"]
    accounts = {}
    for p in comp:
        accounts.setdefault(p["account"], []).append(p)
    rows = []
    for acc, ps in accounts.items():
        med = statistics.median(p["likes"] + p["comments"] for p in ps)
        top = sorted(ps, key=lambda p: -(p["likes"] + p["comments"]))[:3]
        rows.append({"account": acc, "kpis": kpis(ps, followers.get(acc)),
                     "top": [{"permalink": p["permalink"], "hook": _hook(p), "type": p.get("type"), "likes": p["likes"], "comments": p["comments"],
                              "x": round((p["likes"] + p["comments"]) / med, 1) if med else None} for p in top]})
    rows.sort(key=lambda r: -(r["kpis"].get("engagement_rate") or r["kpis"].get("median_engagement") or 0))
    notes = ["Competitors' views, reach and stories are not available from Instagram's API; their numbers here are likes and comments.",
             "Our stories are only readable for 24 hours after posting, so story numbers appear only for recent stories."]
    return {"competitors": rows, "ours": {"kpis": kpis(ours), "posts": len(ours)}, "why": why(comp), "why_ours": why(ours), "notes": notes,
            "names": studio.competitors(office.graph())}


def suggest(office: Office) -> dict:
    """Candidate competitors from a web search, for a person to confirm. Nothing is watched until they do."""
    if not meta.ready():
        return {"ok": False, "needs": "Suggestions need Muse Spark web search (META_API_KEY). You can type the accounts yourself."}
    areas = sorted({n.props["community"] for n in office.graph().of("listing")})
    r = meta.search(f"Which real-estate brokerages in Dubai post the most on Instagram about {', '.join(areas)}? "
                    "List their Instagram usernames (the @handle), with the page where you found each.")
    handles = re.findall(r"instagram\.com/([A-Za-z0-9_.]{3,30})", " ".join([r["text"], *[s.get("url") or "" for s in r["sources"]]]))
    handles += re.findall(r"@([A-Za-z0-9_.]{3,30})", r["text"])
    skip = {"p", "reel", "reels", "explore", "stories", "accounts", "tv"}
    seen = []
    for h in handles:
        h = h.strip(".").lower()
        if h not in skip and h not in seen:
            seen.append(h)
    return {"ok": True, "suggestions": seen[:10], "sources": [c["url"] for c in r["cited"]][:5]}
