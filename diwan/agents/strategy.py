"""Which angles to script next, the way a strong marketing lead decides it: from what our own posts did, measured
against our own usual, and what is winning for competitors right now.

Every post is put in one angle (how the reel sells the listing). For each angle, from our own posts, oldest first:

  winning   the last 2 posts both reached 1.2x our median engagement or more -> keep making it
  fading    it was working, but each of the last 3 posts did worse than the one before and the latest is below our
            median -> the audience is tiring of it: shift to another angle
  retired   the last 2 posts were both under 0.8x our median -> stop it for 30 days, then it may be tested again
  steady    in between -> keep it in rotation
  untested  fewer than 2 posts of ours -> a candidate for the explore slot

A run asks for up to 3 scripts: up to 2 from the angles that are working (ours first, then the competitors' outliers),
and always 1 explore slot for an angle we have not proven, so the account never runs only on one idea until it dies.
Each choice comes with the numbers behind it.
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime, timedelta, timezone

from diwan.office import Office

ANGLES = {  # id: (what it is, how a caption shows it)
    "price-reveal": ("Open on the price as a question, answer with the home", r"what does .{0,40}\bbuy\b|\bguess the price\b|\bhow much\b|ماذا تشتري"),
    "walkthrough": ("A tour: strongest room first, price at the end", r"\b(tour|walk ?through|step inside|inside this|come inside|walk with me)\b"),
    "lifestyle": ("A day living here: the view, the morning, the community", r"\b(morning|sunset|weekend|wake up|life in|living in|imagine)\b"),
    "investor": ("The facts an investor asks first (no promised returns)", r"\b(investor|investment|rental|tenant|handover|payment plan|off.?plan)\b"),
    "market-check": ("What this budget buys here versus nearby", r"\b(vs\.?|versus|compare|compared|same budget|market)\b"),
}
WIN, FADE, RETIRE = 1.2, 1.0, 0.8
REST_DAYS = 30


def angle_of(caption: str) -> str | None:
    low = (caption or "").lower()
    return next((a for a, (_, rx) in ANGLES.items() if re.search(rx, low)), None)


def _when(p: dict) -> datetime:
    try:
        return datetime.fromisoformat((p.get("at") or "").replace("+0000", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _eng(p: dict) -> int:
    return p.get("engagement") if p.get("engagement") is not None else (p.get("likes") or 0) + (p.get("comments") or 0)


def _ours(office: Office) -> list[dict]:
    from diwan.agents import studio
    published = {e["content"].get("instagram_id"): e["content"].get("angle") for e in office.log.list()
                 if e["type"] == "content.made" and e["content"]["kind"] == "published"}
    out = []
    for p in studio.posts(office, "own"):
        a = published.get(p.get("id")) or angle_of(p.get("caption") or "")
        if a:
            out.append(p | {"angle": a})
    return sorted(out, key=_when)


def status(ratios: list[float], last_at: datetime | None, now: datetime) -> str:
    if len(ratios) < 2:
        return "untested"
    a, b = ratios[-2:]
    if a < RETIRE and b < RETIRE:
        return "retired" if last_at and now - last_at < timedelta(days=REST_DAYS) else "untested"
    if len(ratios) >= 3 and ratios[-3] > ratios[-2] > ratios[-1] and ratios[-1] < FADE and max(ratios[:-1]) >= WIN:
        return "fading"
    if a >= WIN and b >= WIN:
        return "winning"
    return "steady"


def report(office: Office, now: datetime | None = None) -> dict:
    """Every angle with its posts, its numbers and what to do with it."""
    from diwan.agents import studio
    now = now or datetime.now(timezone.utc)
    ours = _ours(office)
    med = statistics.median([_eng(p) for p in ours]) if len(ours) >= 3 else None
    from diwan.agents import marketing
    enquiries = marketing.leads_by_angle(office)  # what brought people in counts for more than what got likes
    market: dict[str, list[float]] = {}
    big: dict[str, int] = {}  # outliers per angle: above their account's average
    for p in studio.posts(office, "competitor"):
        a = angle_of(p.get("caption") or "")
        if a and p.get("score"):
            market.setdefault(a, []).append(p["score"])
            if studio.is_outlier(p):  # above its account's average, for its kind
                big[a] = big.get(a, 0) + 1
    rows = []
    for a, (what, _) in ANGLES.items():
        mine = [p for p in ours if p["angle"] == a]
        ratios = [round(_eng(p) / med, 2) for p in mine] if med else []
        st = status(ratios, _when(mine[-1]) if mine else None, now) if med else "untested"
        m = market.get(a, [])
        rows.append({"angle": a, "what": what, "status": st, "posts": len(mine), "last": ratios[-3:],
                     "market_posts": len(m), "market_score": round(statistics.median(m), 1) if m else None,
                     "market_outliers": big.get(a, 0), "leads": enquiries.get(a, 0), "why": _why(st, ratios, m)})
    return {"median": med, "own_posts": len(ours), "angles": rows,
            "note": None if med else "Fewer than 3 of our own posts are classified, so angles are chosen from the competitors' outliers and tested."}


def _why(st: str, ratios: list[float], market: list[float]) -> str:
    last = ", ".join(f"{r}x" for r in ratios[-3:])
    mk = f"; competitors' median {round(statistics.median(market), 1)}x their average on {len(market)} posts" if market else ""
    return {"winning": f"our last two did {last} our median: keep it",
            "fading": f"down each time ({last}), now under our median: shift away",
            "retired": f"our last two did {last}, both under {RETIRE}x: rest it for {REST_DAYS} days",
            "steady": f"recent posts at {last} our median: keep in rotation",
            "untested": "not proven on our account yet"}[st] + mk


def pick(office: Office, n: int = 3, now: datetime | None = None, avoid: set[str] | None = None) -> list[dict]:
    """The angles to script this run: up to n-1 proven ones, then one to explore. Never a retired or fading one.
    `avoid` holds angles used too recently (the no-repeat setting); they are skipped while enough others are left."""
    r = report(office, now)
    rows = {x["angle"]: x for x in r["angles"]}
    if avoid:
        left = {k: v for k, v in rows.items() if k not in avoid}
        if sum(1 for v in left.values() if v["status"] not in ("fading", "retired")) >= n:
            rows = left
    mk = lambda x: (x["market_score"] or 0) * (1 + x["market_outliers"])  # noqa: E731
    proven = sorted([x for x in rows.values() if x["status"] == "winning"], key=lambda x: (-x["leads"], -x["last"][-1]))
    proven += sorted([x for x in rows.values() if x["status"] == "steady"], key=lambda x: (-x["leads"], -(sum(x["last"]) / len(x["last"]))))
    explore = sorted([x for x in rows.values() if x["status"] == "untested"], key=lambda x: -mk(x))
    if not r["median"]:  # nothing of ours to go on: lead with what wins in the market
        proven, explore = explore[:n - 1], explore[n - 1:]
    chosen = [x | {"slot": "proven" if r["median"] else "market" if x["market_posts"] else "explore"} for x in proven[:n - 1]]
    rest = [x for x in explore if x["angle"] not in {c["angle"] for c in chosen}]
    if rest:
        chosen.append(rest[0] | {"slot": "explore"})
    for x in proven[n - 1:] + rest[1:]:  # fill up to n when there is little to explore
        if len(chosen) >= n:
            break
        if x["angle"] not in {c["angle"] for c in chosen}:
            chosen.append(x | {"slot": "proven" if x["status"] in ("winning", "steady") else "explore"})
    if not chosen:  # everything is fading or resting: the least tired angle
        chosen = [min(rows.values(), key=lambda x: x["status"] == "retired") | {"slot": "explore"}]
    return chosen[:n]
