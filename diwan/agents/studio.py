"""The content studio, for real. One listing goes through research, planning, scripting, editing and publishing.

Every step either does real work from real data or stops and says exactly what it needs (a `step.blocked` event with
the missing connection). Nothing is invented to keep the floor busy.

  research    Competitor watch   Instagram business discovery on the accounts set in Settings; outlier = likes+comments
                                 over that account's median. Our own posts and insights come the same way.
              Trend scout        Muse Spark web search, cited sources only.
              Transcript reader  The top outlier video, downloaded, transcribed by Muse Voice Transcribe.
  planning    Idea generator     Muse Spark from the listing and pinned cards (card ids checked); else one idea per card.
              Lane balancer      Our posts of the last 30 days sorted into lanes by their captions.
              Film list          Shots from the listing's features, booked with the broker's next viewing.
  scripting   Script writer      Muse Spark, English and Arabic; every amount must be on the listing. Else a template.
              Video check        The uploaded footage transcribed and compared line by line with the script.
              Playbook writer    Our own outliers: what they had in common.
  editing     Captions           Footage → Voice Transcribe → subtitles burned in with ffmpeg.
              Remix              The outlier's beats mapped onto our film list.
              Content writer     Post text per platform from the listing, with the permit number.
  publishing  Thumbnail          A frame of the footage, and a Muse Image cover when the key is set.
              Permit checker     Permit number present, price matches the listing, no banned promises.
              Scheduler          The hour our posts did best; without history, says so.
              Cross-publisher    The caption cut to each platform's limits.
              Publisher          Owner approval; then Instagram Content Publishing if connected and the cut is public.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from diwan import brand
from diwan import business, products, topics
from diwan.agents import runner
from diwan.agents.charters import get
from diwan.config import env
from diwan.graph import Graph
from diwan.office import Office
from diwan.pack import Action, Evidence, Pack
from diwan.people import name
from diwan.providers import instagram, local_asr, meta

LANES = {"listing": r"\b(bed|br|apartment|villa|unit|for sale|listing|aed|price|tour)\b",
         "area guide": r"\b(area|community|guide|living in|neighbou?rhood|marina|jvc|downtown|business bay)\b",
         "market update": r"\b(market|prices? (are|went)|rates?|report|q[1-4]|trend|data)\b",
         "behind the scenes": r"\b(team|office|day in|behind|bts|broker life)\b",
         "client story": r"\b(client|keys|handover|testimonial|happy|story|bought)\b"}
BANNED = r"\b(guaranteed?|risk.?free|assured returns?|best investment|will (double|rise|go up)|100% (safe|return)|free (golden )?visa|visa included|get (a|your) (golden )?visa)\b"
LIMITS = {"Instagram": 2200, "TikTok": 2200, "YouTube Shorts": 100, "Property Finder": 500}


# ---------- what the studio has already seen and made (all from the log) ----------

def posts(office: Office, source: str | None = None) -> list[dict]:
    seen: dict[str, dict] = {}
    for e in office.log.list():
        if e["type"] == "post.seen" and (source is None or e["content"]["source"] == source):
            seen[e["content"]["id"]] = e["content"]
    return list(seen.values())


def made(office: Office, kind: str, ref: str | None = None) -> dict | None:
    for e in reversed(office.log.list()):
        if e["type"] == "content.made" and e["content"]["kind"] == kind and (ref is None or e["content"].get("ref") == ref):
            return e["content"]
    return None


def board(office: Office) -> list[dict]:
    """The research board: every pinned card that has not been taken off since."""
    cards: dict[str, dict | None] = {}
    for e in office.log.list():  # the latest pin or removal of each card wins
        if e["type"] == "board.pinned":
            cards.pop(e["content"]["id"], None)
            cards[e["content"]["id"]] = e["content"]
        elif e["type"] == "board.unpinned":
            cards[e["content"]["id"]] = None
    return [c for c in cards.values() if c]


def ad_library_url(account: str, country: str = "") -> str:
    """Meta's Ad Library, searched for the account in our country (every country until one is set): a person looks at
    their ads there (no API returns them)."""
    from urllib.parse import quote
    return (f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={quote(country or 'ALL')}&q={quote(account)}"
            "&search_type=keyword_unordered")


def pin_ad(office: Office, *, account: str, url: str, started: str, text: str, ended: str | None = None, by: str) -> dict:
    """A competitor ad a person saw in the Ad Library, pinned on the research board like a post: its link, when it
    started (and ended, if it has), and its copy. There are no numbers: Meta gives none for other advertisers."""
    account, url, text = account.strip().lstrip("@").lower(), url.strip(), text.strip()
    if account not in [c.lower() for c in competitors(office.graph())]:
        raise ValueError(f"@{account} is not on the competitor list")
    if not re.match(r"https://(www\.)?facebook\.com/ads/library/?\?(.*&)?id=\d+", url):
        raise ValueError("Paste the ad's own Ad Library link: open the ad there, then See ad details, and copy the address (it has id=…)")
    try:
        start = datetime.fromisoformat(started).date()
        end = datetime.fromisoformat(ended).date() if ended else None
    except ValueError:
        raise ValueError("Give the start date as it shows in the Ad Library, e.g. 2026-10-02")
    if start > _now().date() or (end and (end < start or end > _now().date())):
        raise ValueError("The start date can't be in the future, and the end date must be between the start and today")
    if not text:
        raise ValueError("Paste the ad's text, so the writers can see what it says")
    card = {"id": _stable_id("B-ad", url), "kind": "ad", "account": account, "url": url, "started": start.isoformat(),
            "ended": end.isoformat() if end else None, "text": text[:2000], "title": text.splitlines()[0][:90],
            "why": f"@{account}'s ad, " + (f"ran {start.isoformat()} to {end.isoformat()}" if end else f"running since {start.isoformat()}"), "by": by}
    if any(b["id"] == card["id"] for b in board(office)):
        raise ValueError("This ad is already pinned")
    office.log.append("board.pinned", actor=by, agent="mrival", content=card)
    return card


def unpin(office: Office, card: str, *, by: str) -> None:
    if not any(b["id"] == card for b in board(office)):
        raise ValueError(f"{card} is not on the research board")
    office.log.append("board.unpinned", actor=by, agent="mrival", content={"id": card})


def footage(office: Office, ref: str) -> dict | None:
    return next((e["content"] for e in reversed(office.log.list()) if e["type"] == "footage.added" and e["content"]["ref"] == ref), None)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _posted(p: dict) -> datetime | None:
    try:
        return datetime.fromisoformat((p.get("at") or "").replace("+0000", "+00:00").replace("Z", "+00:00"))
    except ValueError:
        return None


def kind(p: dict) -> str:
    return "reel" if (p.get("type") or "").upper() in ("VIDEO", "REELS") else "post"


def scored(ps: list[dict]) -> list[dict]:
    """One account's posts, each with its likes + comments, the account's average for the same kind (reels with
    reels, other posts with other posts) and `score`, how many times that average it got. One rule for the table, the
    carousel, the board, why they win and the strategy: an outlier is a post above its average (score > 1)."""
    out = [p | {"engagement": p["likes"] + p["comments"], "kind": kind(p)} for p in ps]
    for k in ("reel", "post"):
        group = [q for q in out if q["kind"] == k]
        avg = statistics.mean(q["engagement"] for q in group) if len(group) >= 2 else None
        for q in group:
            q["avg"] = round(avg) if avg else None
            q["score"] = round(q["engagement"] / avg, 1) if avg else None  # for showing; `above` compares the exact numbers
            q["above"] = bool(avg) and q["engagement"] > avg
    return out


def is_outlier(p: dict) -> bool:
    return p["above"] if "above" in p else bool(p.get("score")) and p["score"] > 1


def clear_win(p: dict) -> bool:
    """Beat its kind's average by more than chance: twice the square root of that average, the same bar Why they win uses.
    6 against a usual 3 is noise; 900 against a usual 680 is not."""
    return bool(p.get("avg")) and p["engagement"] - p["avg"] > 2 * p["avg"] ** .5


def competitors(g: Graph) -> list[str]:
    raw = g.settings.get("studio", {}).get("competitors", "")
    return [u.strip().lstrip("@") for u in re.split(r"[,\s]+", raw) if u.strip()]


# ---------- logging helpers ----------

def _pack(office: Office, agent: str, verdict: str, *, cause: int | None = None, kind: str | None = "draft",
          evidence: list[Evidence] | None = None, sources: dict | None = None, next_: list[str] | None = None, usage: dict | None = None) -> int:
    pack = Pack("studio", agent, verdict, evidence=evidence or [], next=next_ or [], actions=[Action(kind, verdict)] if kind else [])
    return runner.submit(office.log, get(agent), pack, sources=sources or {}, caused_by=cause, usage=usage or {}).event["id"]


def _blocked(office: Office, agent: str, needs: str, *, cause: int | None = None) -> None:
    office.log.append("step.blocked", actor=agent, agent=agent, caused_by=cause, content={"needs": needs})


def _made(office: Office, agent: str, kind: str, ref: str, data: dict, cause: int | None) -> dict:
    n = 1 + sum(1 for e in office.log.list() if e["type"] == "content.made")
    c = {"id": f"C{n}", "kind": kind, "ref": ref, "by": agent, **data}
    office.log.append("content.made", actor=agent, agent=agent, caused_by=cause, content=c)
    return c


def _brief(office: Office, ref: str) -> str:
    """What a reel is for, as the writers see it: the record plus every feature, so a script has real things to say."""
    lst = _listing(office, ref)
    if lst["item"] == "topic":
        return topics.record(lst)
    if lst["item"] == "product":
        return products.record(lst)
    feats = "; ".join(lst.get("features") or []) or "none recorded"
    return office.graph().record(f"listing:{ref}") + f" · features: {feats}"


def _listing(office: Office, ref: str) -> dict:
    """What a reel is for: a listing from the CRM, or one of our confirmed products or services. Both come with `item`,
    `title`, `features`, `price_aed` (the price, in the item's own currency for a product) and `permit`."""
    n = office.graph().nodes.get(f"listing:{ref}")
    if n:
        return n.props | {"item": "listing", "currency": "AED"}
    p = products.get(office, ref)
    if p:
        return p | {"item": "product", "price_aed": p.get("price"), "permit": p.get("permit")}
    if t := topics.get(office, ref):  # a topic to explain: no price, no permit
        return t | {"item": "topic", "price_aed": None, "permit": None, "currency": ""}
    raise KeyError(f"no listing, product or topic {ref}")


def _key(office: Office, ref: str) -> str:
    """The source id writers cite: listing:REF or product:REF."""
    return f"{_listing(office, ref)['item']}:{ref}"


def _price(lst: dict) -> str:
    """The price as shown in a post ("AED 2,600,000"), or "" when it is not public."""
    v = lst.get("price_aed")
    return f"{lst.get('currency') or ''} {v:,}".strip() if isinstance(v, (int, float)) else ""


def _what(lst: dict) -> str:
    """A few words for what it is: "2 bed apartment", or the product's own description."""
    if lst["item"] == "listing":
        return f"{lst['beds']} bed {lst['type']}"
    if lst["item"] == "topic":
        return "a topic"
    return (lst.get("what") or lst.get("kind") or "product")[:60]


def _ffmpeg(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError(r.stderr[-300:] or "ffmpeg failed")


def _width(path: Path) -> int:
    return int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=p=0", str(path)],
                              capture_output=True, text=True).stdout.strip() or 720)


def _duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def can_transcribe() -> bool:
    return meta.ready() or local_asr.available()


def transcribe(wav: bytes) -> dict:
    """Muse Voice Transcribe; without the Meta key, local Whisper (labelled). Adds "via"."""
    if meta.ready():
        return meta.transcribe(wav) | {"via": "Muse Voice Transcribe"}
    if local_asr.available():
        return local_asr.transcribe(wav) | {"via": "local Whisper (no Meta key)"}
    raise meta.MetaError("needs META_API_KEY")


def _wav(src: Path) -> bytes:
    out = src.with_suffix(".wav")
    _ffmpeg("-i", str(src), "-ac", "1", "-ar", "16000", str(out))
    return out.read_bytes()


# ---------- posts brought in by hand (a spreadsheet), until Instagram is connected ----------

CSV_COLUMNS = ["source", "account", "followers", "url", "type", "caption", "likes", "comments", "posted_at"]
CSV_TEMPLATE = ",".join(CSV_COLUMNS) + "\ncompetitor,their.account,12000,https://www.instagram.com/p/XXXX/,REELS,\"The first line of the caption\",950,40,2026-10-20 19:30\n"


CSV_SAMPLE = [  # what each column takes, and one filled-in row, shown on the Setup tab
    {"column": "source", "takes": "competitor or own", "example": "competitor"},
    {"column": "account", "takes": "their Instagram handle (required)", "example": "their.account"},
    {"column": "followers", "takes": "a whole number, or empty", "example": "12000"},
    {"column": "url", "takes": "the post's Instagram link, or empty", "example": "https://www.instagram.com/p/XXXX/"},
    {"column": "type", "takes": "REELS, VIDEO, IMAGE or CAROUSEL_ALBUM, or empty", "example": "REELS"},
    {"column": "caption", "takes": "the caption, in quotes if it has commas", "example": "\"The first line of the caption\""},
    {"column": "likes", "takes": "a whole number (required)", "example": "950"},
    {"column": "comments", "takes": "a whole number (required)", "example": "40"},
    {"column": "posted_at", "takes": "YYYY-MM-DD HH:MM in your time zone, or empty", "example": "2026-10-20 19:30"},
]
TYPES = {"REELS": "REELS", "REEL": "REELS", "VIDEO": "VIDEO", "IMAGE": "IMAGE", "PHOTO": "IMAGE", "CAROUSEL_ALBUM": "CAROUSEL_ALBUM", "CAROUSEL": "CAROUSEL_ALBUM"}


def check_import(header: list[str], rows: list[dict]) -> list[str]:
    """Everything wrong with a filled-in template, each with its row and column, so the person can fix the file.
    Empty when it can be imported."""
    head = [h.strip().lower() for h in header or []]
    if not head:
        return ["The file is empty, or not a CSV. Save the spreadsheet as CSV (comma separated) and try again."]
    missing = [c for c in ("account", "likes", "comments") if c not in head]
    unknown = [h for h in head if h and h not in CSV_COLUMNS]
    out = []
    if missing:
        out.append(f"The first row must be the column names. Missing: {', '.join(missing)}. Expected: {','.join(CSV_COLUMNS)}")
    if unknown:
        out.append(f"Columns not in the template: {', '.join(unknown)}.")
    if out:
        return out
    if not rows:
        return ["There are no posts under the column names."]
    whole = lambda v: re.fullmatch(r"\d+", (v or "").replace(",", "").strip() or "0")  # noqa: E731
    for i, r in enumerate(rows, 2):
        r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
        if not r["account"]:
            out.append(f"Row {i}, account: empty. Put the Instagram handle, e.g. their.account.")
        elif not re.fullmatch(r"@?[A-Za-z0-9_.]{1,30}", r["account"]):
            out.append(f"Row {i}, account: \"{r['account']}\" is not an Instagram handle (letters, numbers, dots, underscores).")
        for c in ("likes", "comments", "followers"):
            if c in r and not whole(r[c]):
                out.append(f"Row {i}, {c}: \"{r[c]}\" is not a whole number.")
        if r.get("source") and r["source"].lower() not in ("competitor", "own"):
            out.append(f"Row {i}, source: \"{r['source']}\" must be competitor or own.")
        if r.get("type") and r["type"].upper() not in TYPES:
            out.append(f"Row {i}, type: \"{r['type']}\" must be REELS, VIDEO, IMAGE or CAROUSEL_ALBUM.")
        if r.get("url") and not re.match(r"https?://(www\.)?instagram\.com/", r["url"]):
            out.append(f"Row {i}, url: not an Instagram link.")
        if r.get("posted_at"):
            try:
                datetime.fromisoformat(r["posted_at"].replace(" ", "T"))
            except ValueError:
                out.append(f"Row {i}, posted_at: \"{r['posted_at']}\" must look like 2026-10-20 19:30.")
    return out


def import_posts(office: Office, rows: list[dict], *, by: str) -> dict:
    """Real posts someone copied from Instagram into the template. Scored against each account's own median, the
    same as fetched posts, and the outliers are pinned on the research board with their links."""
    clean, errors = [], []
    for i, r in enumerate(rows, 2):
        try:
            acc = (r.get("account") or "").strip().lstrip("@")
            if not acc:
                raise ValueError("no account")
            at = (r.get("posted_at") or "").strip()
            iso = None
            if at:
                dt = datetime.fromisoformat(at.replace(" ", "T"))
                iso = (dt if dt.tzinfo else dt.replace(tzinfo=business.tz(office))).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
            url = (r.get("url") or "").strip()
            clean.append({"id": url or f"{acc}-{i}", "account": acc, "source": "own" if (r.get("source") or "").strip().lower() == "own" else "competitor",
                          "followers": int(r["followers"].replace(",", "").strip()) if (r.get("followers") or "").strip() else None, "permalink": url,
                          "type": TYPES.get((r.get("type") or "").strip().upper()) or None, "caption": (r.get("caption") or "")[:600],
                          "likes": int((r.get("likes") or "0").replace(",", "")), "comments": int((r.get("comments") or "0").replace(",", "")), "at": iso})
        except (ValueError, KeyError) as e:
            errors.append(f"row {i}: {e}")
    by_acc: dict[str, list] = {}
    for p in clean:
        by_acc.setdefault((p["source"], p["account"]), []).append(p)
    outliers = []
    for (_, _acc), ps in by_acc.items():
        for p in scored(ps):
            office.log.append("post.seen", actor=by, agent="mrival", key=f"import:{p['id']}:{p['engagement']}", content=p | {"imported": True})
            if p["source"] == "competitor" and is_outlier(p):
                outliers.append(p)
    outliers.sort(key=lambda p: -p["score"])
    for p in [p for p in outliers if clear_win(p)][:3]:
        office.log.append("board.pinned", actor="mrival", agent="mrival", key=f"pin:{p['id']}",
                          content={"id": _stable_id("B", p["id"]), "kind": "outlier", "title": (p["caption"] or "(no caption)")[:90], "account": p["account"],
                                   "why": f"{p['engagement']:,} likes+comments, {p['score']}x @{p['account']}'s average {p['kind']}", "url": p["permalink"], "post": p["id"], "type": p["type"]})
    comp = [p for p in clean if p["source"] == "competitor"]
    _pack(office, "mrival", f"Imported {len(clean)} posts ({len(comp)} from {len({p['account'] for p in comp})} competitors): {len(outliers)} above their account's average."
          + (f" Skipped: {'; '.join(errors[:3])}" if errors else ""), kind="draft")
    return {"imported": len(clean), "outliers": len(outliers), "errors": errors}


# ---------- research ----------

def watch(office: Office, cause: int | None, only: list[str] | None = None) -> list[dict]:
    """Competitor watch: score every competitor post against its own account's median; pin the outliers. `only`
    fetches just those accounts (a competitor that was just saved), without re-reading our own posts."""
    names = only or competitors(office.graph())
    if not instagram.ready():
        pinned = [b for b in board(office) if b["kind"] == "outlier"]
        if pinned:
            _pack(office, "mrival", f"Using imported posts: {len(pinned)} outliers pinned. Connect Instagram to fetch them automatically.", cause=cause)
            return [{"id": b["post"], "account": b["account"], "score": None, "permalink": b["url"], "type": b.get("type")} for b in pinned]
        _blocked(office, "mrival", "Connect Instagram in Settings, or import posts from a spreadsheet in the Studio", cause=cause)
        return []
    if not names:
        _blocked(office, "mrival", "Add competitor accounts in the Studio (Setup → Competitor accounts)", cause=cause)
        return []
    outliers, errors = [], []
    for u in names:
        try:
            acc = instagram.competitor_posts(u)
        except instagram.InstagramError as e:
            errors.append(f"@{u}: {e}")
            office.log.append("competitor.checked", actor="mrival", agent="mrival", caused_by=cause, content={"account": u, "ok": False, "error": str(e)[:200]})
            continue
        fit = {}
        if only:  # a just-added account: does it look like our industry? (a warning only; it is never refused)
            from diwan.agents import reader
            fit = reader.fits(office, acc)
        office.log.append("competitor.checked", actor="mrival", agent="mrival", caused_by=cause,
                          content={"account": u, "ok": True, "username": acc["username"], "followers": acc.get("followers"),
                                   "media_count": acc.get("media_count"), "avatar": acc.get("avatar"), "posts_read": len(acc["posts"]), **fit})
        for p in scored(acc["posts"]):
            office.log.append("post.seen", actor="mrival", agent="mrival", key=f"post:{p['id']}:{p['engagement']}",
                              content={**p, "source": "competitor", "followers": acc.get("followers")})
            if is_outlier(p):
                outliers.append(p)
    reached = len(names) - len(errors)
    if not reached and only:  # a just-added account that can't be read: its check says why; the studio's research is not blocked
        return []
    if not reached:  # nothing was read: say so, never "no outliers"
        _blocked(office, "mrival", f"0 of {len(names)} competitors reached: {'; '.join(errors)}", cause=cause)
        return []
    outliers.sort(key=lambda p: -p["score"])
    try:
        for p in ([] if only else instagram.own_posts()):
            office.log.append("post.seen", actor="mrival", agent="mrival", key=f"own:{p['id']}:{p['likes']}:{p['comments']}",
                              content={**p, "source": "own", "engagement": p["likes"] + p["comments"]})
    except instagram.InstagramError as e:
        errors.append(f"our account: {e}")
    top = [p for p in outliers if clear_win(p)][:3]  # every post above average is counted; only clear wins are pinned
    for p in top:
        office.log.append("board.pinned", actor="mrival", agent="mrival", key=f"pin:{p['id']}",
                          content={"id": f"B-{p['id']}", "kind": "outlier", "title": (p["caption"] or "(no caption)")[:90], "account": p["account"],
                                   "why": f"{p['engagement']:,} likes+comments, {p['score']}x @{p['account']}'s average {p['kind']}", "url": p["permalink"], "post": p["id"], "media_url": p.get("media_url"),
                                   "type": p.get("type")})
    verdict = f"Reached {reached} of {len(names)} competitors. " + (f"{len(outliers)} posts above their account's average. Top: @{top[0]['account']} at {top[0]['score']}x their average." if top
               else f"{len(outliers)} posts above their account's average, none by more than chance." if outliers else "No post above its account's average.")
    _pack(office, "mrival", verdict + (f" Not reached: {'; '.join(errors)}" if errors else ""), cause=cause,
          evidence=[Evidence(p["permalink"], f"post:{p['id']}") for p in top if p.get("permalink")],
          sources={f"post:{p['id']}": p["permalink"] for p in top if p.get("permalink")})
    return top


def _stable_id(prefix: str, key: str) -> str:
    """The same source always gets the same card id (Python's hash() changes on every restart)."""
    return f"{prefix}-{hashlib.sha1(key.encode()).hexdigest()[:8]}"


def trends(office: Office, cause: int | None) -> list[dict]:
    # trends move by the week, not the minute: one search per rhythm (Setup: daily, every 2 days, weekly) is enough
    from diwan.agents import rhythm
    since = datetime.now(timezone.utc) - rhythm.every(office)
    recent = [e["content"] for e in office.log.list() if e["type"] == "board.pinned" and e["content"].get("kind") == "trend"
              and datetime.fromisoformat(e["at"]) >= since]
    if recent:
        _pack(office, "mtrend", f"Using the {len(recent)} trend card{'s' if len(recent) != 1 else ''} already found ({rhythm.settings(office)['rhythm']} search).", cause=cause)
        return recent
    if not meta.ready():
        _blocked(office, "mtrend", "Trend research needs Muse Spark web search (META_API_KEY)", cause=cause)
        return []
    if (why := business.needs(office, "the trend search is about your market")):
        _blocked(office, "mtrend", why, cause=cause)
        return []
    b = business.get(office)
    try:
        r = meta.search(f"What short-form video formats and hooks are performing for {b['industry']} businesses in {business.place(office)} "
                        "on Instagram and TikTok in the last month? Use at most two searches. Answer with exactly three lines and nothing else, each in the form:\n"
                        "1. <the format or hook, under 12 words> | <why it works, under 15 words> | <the URL of the page you saw it on>", country=b["country"])
    except meta.MetaError as e:
        _blocked(office, "mtrend", f"Web search failed: {e}", cause=cause)
        return []
    seen = {s["url"].rstrip("/") for s in [*r["sources"], *r["cited"]] if s.get("url")}
    cards = []
    for ln in r["text"].splitlines():
        m = re.match(r"\s*\d+[.)]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(https?://\S+)", ln)
        if not m or m.group(3).rstrip("/.)") not in {u.rstrip("/.)") for u in seen}:
            continue  # only a trend whose link is one the search actually opened is pinned
        c = {"id": _stable_id("B-trend", m.group(3)), "kind": "trend", "title": m.group(1)[:120], "why": m.group(2)[:160], "url": m.group(3).rstrip(".)")}
        office.log.append("board.pinned", actor="mtrend", agent="mtrend", key=f"pin:{c['id']}", content=c)
        cards.append(c)
    if not cards:
        _blocked(office, "mtrend", "Web search gave no trend tied to a page it opened, so nothing is pinned", cause=cause)
        return []
    _pack(office, "mtrend", f"{len(cards)} rising formats pinned, each with the page it came from.", cause=cause,
          evidence=[Evidence(c["url"], c["id"]) for c in cards], sources={c["id"]: c["url"] for c in cards}, usage={"queries": r["queries"]})
    return cards


import threading

_REFRESHING = threading.Lock()


def refresh_competitors(office: Office, *, by: str, auto: bool = False) -> dict:
    """Re-read every competitor's recent posts (new posts, and the likes and comments of the old ones), have Muse Spark
    read the new ones, and redo the patterns. Says what changed, and records it (competitors.refreshed). Instagram
    does not tell us when someone else posts, so this is a check on a schedule or on a button, not a notification."""
    from diwan.agents import reader
    if not _REFRESHING.acquire(blocking=False):
        return {"ok": False, "needs": "A refresh is already running."}
    try:
        names = competitors(office.graph())
        why = None if names and instagram.ready() else (
            "Add competitor accounts first." if not names else "Connect Instagram in Settings: competitor posts are read through it.")
        if why:
            if auto:
                office.log.append("competitors.refreshed", actor=by, content={"ok": False, "auto": True, "error": why, "accounts": len(names)})
            return {"ok": False, "needs": why}
        last = (office.log.list() or [{"id": 0}])[-1]["id"]
        before = {p["id"]: p["likes"] + p["comments"] for p in posts(office, "competitor")}
        watch(office, None)
        checked = [e["content"] for e in office.log.list() if e["id"] > last and e["type"] == "competitor.checked"]
        after = posts(office, "competitor")
        fresh = {p["id"] for p in after if p["id"] not in before}
        changed = [p for p in after if p["id"] in before and p["likes"] + p["comments"] != before[p["id"]]]
        read_posts(office, None)
        reader.pin(office)
        winners = [{"account": a, "hook": (p.get("caption") or "").strip().split("\n")[0][:100], "score": p["score"], "kind": p["kind"], "url": p.get("permalink"),
                    "engagement": p["engagement"]}
                   for a, ps in reader._saved_posts(office).items() for p in ps if p["id"] in fresh and is_outlier(p)]
        winners.sort(key=lambda w: -(w["score"] or 0))
        out = {"ok": True, "auto": auto, "accounts": len(names), "reached": sum(1 for c in checked if c.get("ok")), "new": len(fresh), "changed": len(changed),
               "winners": winners[:5], "errors": [f"@{c['account']}: {c.get('error')}" for c in checked if not c.get("ok")][:5]}
        office.log.append("competitors.refreshed", actor=by, agent="mrival", content=out)
        return out
    finally:
        _REFRESHING.release()


def read_posts(office: Office, cause: int | None) -> None:
    """Muse Spark reads the competitor posts not read yet, so "Why they win" and the board's patterns are current."""
    from diwan.agents import reader
    if not reader.unread(office)["posts"]:
        return
    r = reader.read(office, cause)
    if r.get("needs"):
        _blocked(office, "mrival", f"Why they win is waiting: {r['needs']}", cause=cause)
    elif r["read"] or r["errors"]:
        n = sum(len(a["patterns"]) for a in reader.patterns(office)["accounts"])
        _pack(office, "mrival", f"Read {r['read']} new competitor post{'s' if r['read'] != 1 else ''}; {n} pattern{'s' if n != 1 else ''} hold."
              + (f" Not read: {'; '.join(r['errors'])}" if r["errors"] else ""), cause=cause)


def transcript_of(office: Office, card: dict | None, cause: int | None) -> dict | None:
    if not card:
        _blocked(office, "mtrans", "Waiting for an outlier video from Competitor watch", cause=cause)
        return None
    if not can_transcribe():
        _blocked(office, "mtrans", "Transcribing needs Muse Voice Transcribe (META_API_KEY)", cause=cause)
        return None
    if card.get("type") not in ("VIDEO", "REELS") or not card.get("media_url"):
        _blocked(office, "mtrans", f"The top outlier from @{card.get('account')} is not a video Instagram lets us download", cause=cause)
        return None
    try:
        tmp = meta.MEDIA / f"outlier-{card['post']}.mp4"
        meta.MEDIA.mkdir(exist_ok=True)
        with httpx.stream("GET", card["media_url"], timeout=60, follow_redirects=True) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for i, chunk in enumerate(r.iter_bytes()):
                    f.write(chunk)
                    if i * 65536 > 80_000_000:
                        raise RuntimeError("video over 80 MB")
        t = transcribe(_wav(tmp))
    except Exception as e:  # download or transcription failed: say so, keep going without it
        _blocked(office, "mtrans", f"Could not transcribe @{card.get('account')}'s video: {str(e)[:160]}", cause=cause)
        return None
    sentences = [s.strip() for s in re.split(r"(?<=[.!?؟])\s+", t["text"]) if s.strip()]
    data = {"post": card["post"], "account": card["account"], "text": t["text"], "hook": sentences[0] if sentences else "", "beats": sentences[:6]}
    c = _made(office, "mtrans", "transcript", card["post"], data, cause)
    _pack(office, "mtrans", f"Hook in @{card['account']}'s outlier: \"{data['hook'][:120]}\". {len(data['beats'])} beats.", cause=cause,
          evidence=[Evidence(data["hook"], c["id"])] if data["hook"] else [], sources={c["id"]: t["text"]})
    return c


# ---------- planning ----------

def _post_read(office: Office, card: dict) -> tuple[dict | None, dict | None]:
    """The competitor post behind an outlier card, and how Muse Spark read it (None when not read yet)."""
    from diwan.agents import reader
    pid = card.get("post")
    post = next((p for p in posts(office, "competitor") if p["id"] == pid), None) if pid else None
    return post, reader.reads(office).get(pid) if pid else None


def usable(office: Office, cards: list[dict]) -> list[dict]:
    """The board cards a script may build on: a competitor post about their own moment (an event, an award, a signing)
    is left out, because it does not carry over to us."""
    out = []
    for c in cards:
        if c.get("kind") == "outlier":
            _, r = _post_read(office, c)
            if r and not r["carries_over"]:
                continue
        out.append(c)
    return out


def worked_because(r: dict | None) -> str:
    """Why a competitor post worked, from how it was read; never their numbers, words or claims."""
    if not r:
        return "the reason is not known yet (the post has not been read)"
    return f"it is a {r['topic']} that opens with {r['hook']} and shows {r['on_screen']}"


def built_like(office: Office, card_ids: list[str]) -> list[str]:
    """One line per competitor card a script builds on: whose post, its numbers, and why it worked."""
    on = {c["id"]: c for c in board(office)}
    out = []
    for cid in card_ids:
        c = on.get(cid)
        if not c:
            continue
        if c["kind"] == "outlier":
            p, r = _post_read(office, c)
            nums = f" ({p['engagement']:,} likes + comments, {p['score']}x their average {p['kind']})" if p else ""
            out.append(f"Built like @{c['account']}'s {'reel' if (p or {}).get('kind') == 'reel' else 'post'}{nums}: it worked because {worked_because(r)}.")
        elif c["kind"] == "pattern":
            out.append(f"Built on what wins for {'our own posts' if c['account'] == 'us' else '@' + c['account']}: {c['why'].split(': ', 1)[-1]}")
    return out

IDEAS_SCHEMA = {"name": "ideas", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["ideas"],
                "properties": {"ideas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                                    "required": ["title", "angle", "cards"],
                                                                    "properties": {"title": {"type": "string"}, "angle": {"type": "string"},
                                                                                   "cards": {"type": "array", "items": {"type": "string"}}}}}}}}


def ideas(office: Office, ref: str, cards: list[dict], cause: int | None, feedback: str | None = None) -> dict:
    lst = _listing(office, ref)
    cards = usable(office, cards)
    ids = {c["id"] for c in cards}
    c = get("midea")
    system = runner.instructions(c, office.log)
    what = "listing" if lst["item"] == "listing" else lst.get("kind") or "product"
    user = runner.user_message(f"Three short-video ideas for {what} {ref}. Each title is the hook a viewer would see, naming "
                               + ("the building or area" if lst["item"] == "listing" else "it") + (" and one real fact" if lst["item"] == "topic" else " and one real feature") + "; list the card ids an idea "
                               f"builds on (an empty list if none). When a card fits, at least one idea must build on it. Use only facts from the {what}." + (f"\n\n{feedback}" if feedback else ""),
                               {_key(office, ref): _brief(office, ref), "brand": brand.brief(office), **{x["id"]: f"{x['title']} ({x['why']})" for x in cards}})
    out, by = [], "rules"
    if runner.has_model(c, system, user, schema=IDEAS_SCHEMA):
        office.log.append("agent.started", actor="midea", agent="midea", caused_by=cause, content={"task": f"Writing ideas for {ref} with the model"})
        try:
            out = runner.call(c, system, user, schema=IDEAS_SCHEMA).data["ideas"]
            out = [i | {"cards": [x for x in i["cards"] if x in ids]} for i in out]  # a card the model invented is dropped
            by = "muse-spark"
        except Exception as e:
            _blocked(office, "midea", f"Muse Spark failed, using plain ideas: {str(e)[:120]}", cause=cause)
    if not out:
        feats = ", ".join(lst.get("features") or []) or _what(lst)
        out = [{"title": f"{lst['title']}: {feats}" + (", price at the end" if _price(lst) else ""), "angle": "walk-through ending on the price", "cards": []}]
        out += [{"title": f"{lst['title']} in the structure of @{x.get('account', 'a source')}'s {x['kind']}", "angle": x["title"], "cards": [x["id"]]} for x in cards[:2]]
    out = [i | {"from": i["cards"] or [_key(office, ref)]} for i in out]  # every idea names what it came from
    pick = out[0]
    m = _made(office, "midea", "ideas", ref, {"ideas": out, "pick": pick, "via": by}, cause)
    _pack(office, "midea", f"Idea: \"{pick['title']}\"" + (f" (from {', '.join(pick['cards'])})" if pick["cards"] else " (from the listing)"), cause=cause,
          usage={"provider": by})
    return m


def lanes(office: Office, cause: int | None) -> dict:
    ours = posts(office, "own")
    since = datetime.now(timezone.utc) - timedelta(days=30)
    recent = [p for p in ours if p.get("at") and datetime.fromisoformat(p["at"].replace("+0000", "+00:00")) >= since]
    count = Counter()
    for p in recent:
        lane = next((k for k, rx in LANES.items() if re.search(rx, (p.get("caption") or "").lower())), "other")
        count[lane] += 1
    gap = min(LANES, key=lambda k: count.get(k, 0))
    m = _made(office, "mlane", "lanes", "week", {"counts": dict(count), "gap": gap, "posts": len(recent)}, cause)
    if not ours:
        _pack(office, "mlane", f"No post history (Instagram not connected), so lanes start empty; suggest a {gap}.", cause=cause)
    else:
        _pack(office, "mlane", f"Last 30 days: {', '.join(f'{v} {k}' for k, v in count.most_common()) or 'no posts'}. Gap: {gap}.", cause=cause)
    return m


def _end_shot(office: Office, lst: dict) -> str:
    """The last shot: the price card (with the permit when the business needs one), or the end card when no price is public."""
    card = "End on the price card" if _price(lst) else "End on the end card"
    return card + (" with the permit number" if business.permit_needed(office) and lst["item"] != "topic" else "")


def film_list(office: Office, ref: str, idea: dict, cause: int | None, feedback: str | None = None, sc: dict | None = None) -> dict:
    """What to film: the approved script's video plan, shot by shot, with the line said over each; else from the features."""
    g = office.graph()
    lst = _listing(office, ref)
    feats = lst.get("features") or []
    if sc and sc.get("shots"):
        shots = [f"{r['show']} (while saying: \"{r['say']}\")" for r in sc["shots"] if "price card" not in r["show"].lower() and "end card" not in r["show"].lower()]
        shots.append(_end_shot(office, lst) + " (added in editing)")
    elif lst["item"] == "topic":
        shots = ["You to camera, eye level, looking at the lens, a quiet well-lit spot", *[f"Say it again to camera, or cut away to show: {f[:60]}" for f in feats[:3]],
                 "A short cut-away that shows the point (optional)", _end_shot(office, lst)]
    else:
        shots = [f"Open on the strongest view{(': ' + feats[0]) if feats else ''}"] + [f"Show the {f}" for f in feats[1:3]] + \
                ([f"Walk the {lst['beds']} bedroom{'s' if lst['beds'] != 1 else ''}"] if lst["item"] == "listing" else [f"Show {lst['title']} at work"]) + [_end_shot(office, lst)]
    viewing = next((v for v in g.of("viewing", status="booked") if v.props["listing"] == ref), None)
    when = f"at the viewing {g.record(viewing.id).split(', ', 1)[1]}" if viewing else "at the next daylight visit (no viewing booked yet)"
    broker = viewing.props["broker"] if viewing else lst.get("agent")  # the viewing's broker, else the listing's own agent
    m = _made(office, "mfilm", "film list", ref, {"shots": shots, "who": broker, "when": when}, cause)
    _pack(office, "mfilm", f"Film list for {name(broker) if broker else 'nobody assigned yet'} {when}: {len(shots)} shots, ending on the price and permit.", cause=cause)
    return m


# ---------- scripting ----------

SCRIPT_SCHEMA = {"name": "script", "strict": True, "schema": {"type": "object", "additionalProperties": False,
                 "required": ["hook_en", "hook_ar", "lines_en", "lines_ar", "shots"],
                 "properties": {"hook_en": {"type": "string"}, "hook_ar": {"type": "string"},
                                "lines_en": {"type": "array", "items": {"type": "string"}}, "lines_ar": {"type": "array", "items": {"type": "string"}},
                                "shots": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["show", "text", "cut"],
                                                                     "properties": {"show": {"type": "string"}, "text": {"type": "string"}, "cut": {"type": "string"}}}}}}}


def _secs(line: str) -> float:
    """How long a line takes to say: about 2.5 words a second, never under 2 seconds."""
    return max(2.0, round(len(line.split()) / 2.5 + 0.5, 1))


def video_plan(data: dict, lst: dict) -> list[dict]:
    """The script as a video: one row per spoken line (the hook first) with when it starts, what is on screen, the words
    on screen and the cut into it. Rows the model gave are kept when there is one per line; else they are worked out
    from the line and the listing's features. Timing always comes from the words."""
    said = [data["hook_en"], *data["lines_en"]]
    given = data.get("shots") or []
    cam = lst.get("item") == "topic"  # a person talking to camera: the speaker is the picture, not the rooms
    feats = lst.get("features") or []
    rows, t = [], 0.0
    for i, line in enumerate(said):
        low = line.lower()
        if len(given) == len(said) and given[i].get("show"):
            g = given[i]
            show, text, cut = g["show"], g.get("text", ""), g.get("cut", "")
        elif cam:
            end = i == len(said) - 1 and re.search(r"\b(message|dm|call|whatsapp|book|contact|ask)\b", low)
            show = "You to camera, or the brand's end card" if end else "You to camera, eye level, looking at the lens" if i % 2 == 0 else "You to camera, or a short cut-away that shows the point"
            text = "Message us" if end else (" ".join(line.split()[:5]) if i == 0 else "")
            cut = "Fade to the end card" if end else "Open tight on the face, no intro" if i == 0 else "Jump cut on the beat"
        elif i == 0:
            show, text, cut = f"The strongest view{': ' + feats[0] if feats else ''}, moving", line, "Open on movement: a slow push-in"
        elif re.search(r"\bpermit\b|\blicen[cs]e\b|price", low) or (_price(lst) and str(lst.get("price_aed")) in low.replace(",", "")):
            show, text, cut = "The price card", " · ".join(x for x in (_price(lst), f"Permit {lst['permit']}" if lst.get("permit") else "") if x), "Hard cut, hold 2 seconds"
        elif re.search(r"\b(message|dm|call|whatsapp|book|contact)\b", low):
            show, text, cut = "You to camera, or the brand's end card", "Message us", "Fade to the end card"
        elif (f := next((f for f in feats if f.lower() in low or any(len(w) > 3 and re.search(rf"\b{re.escape(w)}\b", low) for w in f.lower().split())), None)):
            show, text, cut = f"Close-up of the {f}", f[:1].upper() + f[1:], "Cut on the move"
        else:
            show, text, cut = "A wide shot of the main room", "", "Cut on the move"
        rows.append({"at": round(t, 1), "say": line, "show": show, "text": text, "cut": cut})
        t += _secs(line)
    return rows


MONEY = re.compile(r"(?:aed|dhs?|dirhams?|درهم)\s*[\d.,]+(?:\s*(?:k|m|mn|million|thousand)\b)?|[\d.,]+\s*(?:k|m|mn|million|thousand|aed|dirhams?|درهم)\b"
                   r"|(?:one|two|three|four|five|six|seven|eight|nine|ten|[a-z-]+ty)(?:[ -][a-z]+)*\s+(?:million|thousand)", re.I)


def _amounts(text: str) -> set[int]:
    """Money in the text: only amounts said as money (AED, dirhams, million, thousand), not unit or permit numbers."""
    from diwan.agents import scribe
    return {int(a) for m in MONEY.finditer(text) for a in scribe.amounts(m.group(0))}


def _template(lst: dict, angle: str, sign_off: str = "Message us to find out more.") -> dict:
    """A plain script for each angle, from the listing's own facts, for when no model is connected or it fails."""
    if lst["item"] == "topic":
        return _topic_template(lst, angle, sign_off)
    if lst["item"] == "product":
        return _product_template(lst, angle, sign_off)
    price, feats = f"AED {lst['price_aed']:,}", lst.get("features") or []
    cap = lambda f: f"{f[:1].upper()}{f[1:]}."  # noqa: E731
    home = f"{lst['beds']} bedroom {lst['type']}"
    close = [f"{price}. Permit {lst.get('permit')}.", sign_off]
    if angle == "walkthrough":
        return {"hook_en": f"Step inside this {home} in {lst['community']}.", "hook_ar": f"ادخل معنا إلى هذا المنزل في {lst['community']}",
                "lines_en": [f"Start with the best part: {feats[0] if feats else 'the view'}.", *[cap(f) for f in feats[1:3]],
                             f"This is {lst['title']}.", *close]}
    if angle == "lifestyle":
        return {"hook_en": f"Imagine your mornings in {lst['community']}.", "hook_ar": f"تخيّل صباحك في {lst['community']}",
                "lines_en": [f"Wake up to {feats[0] if feats else 'the light'}.", *[cap(f) for f in feats[1:3]],
                             f"A {home} at {lst['title']}.", *close]}
    if angle == "investor":
        return {"hook_en": f"The facts investors ask first about {lst['title']}.", "hook_ar": f"الحقائق التي يسأل عنها المستثمرون أولاً",
                "lines_en": [f"{home} in {lst['community']}.", *[cap(f) for f in feats[:2]], "Ask us for the service charge and title deed.",
                             *close]}
    if angle == "market-check":
        return {"hook_en": f"What {price} gets you in {lst['community']} right now.", "hook_ar": f"ماذا يشتري {lst['price_aed']:,} درهم اليوم",
                "lines_en": [f"At {lst['title']}: a {home}.", *[cap(f) for f in feats[:3]], "Same budget elsewhere often means less space.",
                             *close]}
    return {"hook_en": f"What does {price} buy in {lst['community']}?", "hook_ar": f"ماذا تشتري {lst['price_aed']:,} درهم في {lst['community']}؟",
            "lines_en": [f"This is {lst['title']}.", *[cap(f) for f in feats[:3]], f"{home}.", *close]}


def _product_template(p: dict, angle: str, sign_off: str) -> dict:
    """The same, for a product or service: what it is, what it does, its features, its price if public, the sign-off."""
    feats, price, name = p.get("features") or [], _price(p), p["title"]
    cap = lambda f: f"{f[:1].upper()}{f[1:]}."  # noqa: E731
    close = [f"{price}." if price else "", f"Permit {p['permit']}." if p.get("permit") else "", sign_off]
    hooks = {"price-reveal": f"What does {price} get you?" if price else f"What can {name} do for you?",
             "walkthrough": f"See {name} at work.", "lifestyle": f"A day with {name}.",
             "investor": f"The facts buyers ask first about {name}.", "market-check": f"{name}, or doing it the old way?"}
    lines = [f"This is {name}" + (f": {p['what']}." if p.get("what") else "."), *[cap(f) for f in feats[:4]], *[c for c in close if c]]
    return {"hook_en": hooks.get(angle, f"Meet {name}."), "hook_ar": "", "lines_en": lines}


def _topic_template(t: dict, angle: str, sign_off: str) -> dict:
    """A plain script for a topic, spoken to camera: its own facts, one per line, then the sign-off. For when no model is connected."""
    cap = lambda f: f"{f[:1].upper()}{f[1:]}" if f.endswith((".", "!", "?")) else f"{f[:1].upper()}{f[1:]}."  # noqa: E731
    short = " ".join(t["title"].split()[:6])
    hooks = {"explainer": f"{short}, in plain words.", "myth-vs-fact": f"What people get wrong about {short.lower()}.", "question": f"Ever wondered about {short.lower()}?",
             "checklist": f"What to check about {short.lower()}.", "why-it-matters": f"Why {short.lower()} matters to you."}
    lines = [*[cap(f) for f in (t.get("features") or [])[:5]]]
    for pad in ("It is worth knowing before you decide.", "Ask us anything about it.", "We are happy to walk you through it."):
        if len(lines) >= 4:
            break
        lines.append(pad)
    return {"hook_en": hooks.get(angle, t.get("hook") or f"{short}, in plain words."), "hook_ar": "", "lines_en": [*lines, sign_off]}


def script(office: Office, ref: str, idea: dict, hook_card: dict | None, cause: int | None, feedback: str | None = None,
           angle: str = "price-reveal", why: str = "", base: dict | None = None) -> dict:
    """One script on one angle. `base` is a draft to revise (a person's change request or a supervisor's return): the
    model changes what was asked and keeps the rest; without a model the change is applied to the template where it can be."""
    from diwan.agents import eventpost, journey, strategy
    lst = _listing(office, ref)
    rec = _brief(office, ref)
    c = get("mscript")
    sh = eventpost.shape(office, lst)
    pictures = bool(sh) and sh["format"] in eventpost.SLIDES
    schema = SCRIPT_SCHEMA if not pictures else {**SCRIPT_SCHEMA, "schema": {**SCRIPT_SCHEMA["schema"], "required": [*SCRIPT_SCHEMA["schema"]["required"], "photos"],
                                                                             "properties": {**SCRIPT_SCHEMA["schema"]["properties"], "photos": {"type": "array", "items": {"type": "integer"}}}}}
    arabic = "Arabic" in business.languages(office)
    system = runner.instructions(c, office.log) + (f"\nWrite in the `script` format: about 30 seconds, 5 to 7 lines. Use only facts and amounts from "
                                                   f"the {lst['item']}, and build the lines from its features. Every line says something new; never repeat a "
                                                   "line or the name. No placeholders or brackets: if a fact is missing, leave it out. The last "
                                                   "line invites the viewer to get in touch, in the brand's own sign-off if it has one. "
                                                   "Write how a person really talks to a friend: short, natural spoken sentences that a viewer would keep watching. The first line stops the scroll "
                                                   "with a question or a surprising detail, about the viewer or the place, never about us. Never use a planning word such as an angle's name, "
                                                   "'facts first', 'investor facts' or 'price reveal'. Never say a permit number or a unit reference aloud: they are shown on screen. "
                                                   + ("hook_ar and lines_ar are the Arabic of hook_en and lines_en." if arabic else "hook_ar and lines_ar are empty.")
                                                   + (" This is an informational video about a topic, not an ad for a property: a person speaks it to camera. Write the hook and "
                                                      "lines as natural first-person speech, each short enough to say in one breath; no price, no permit, no property tour. In "
                                                      "shots, one per spoken line: `show` is what the viewer sees (the speaker, or a short cut-away that shows the point), "
                                                      "`text` a caption of 2 to 6 words or empty, `cut` how it moves." if lst["item"] == "topic" else ""))
    built = built_like(office, idea["pick"].get("cards", []))
    facts = "" if lst.get("job") else "\n".join(journey.company(office, f"{lst['title']} {rec}"))
    task = (f"Script for: {idea['pick']['title']}. Angle: {({**topics.ANGLES, **journey.ANGLES} if lst['item'] == 'topic' else {k: v[0] for k, v in strategy.ANGLES.items()}).get(angle, angle)}. Borrow the structure, never the words, of the hook card if given."
            + (" Some competitor posts below worked; borrow only why they worked (format, hook, who is on screen). Never use their words, "
               "numbers, awards, sales or partners, and claim nothing about us that the listing and the brand do not say." if built else "")
            + journey.brief(office, lst) + eventpost.brief(sh)
            + (" The company facts below are confirmed: use one when it helps this post, and claim nothing about us beyond them." if facts else "")
            + (f"\n\nRevise this draft; change only what is asked, keep everything else:\n{json.dumps({k: base[k] for k in ('hook_en', 'hook_ar', 'lines_en')}, ensure_ascii=False)}" if base else "")
            + (f"\n\n{feedback}" if feedback else ""))
    from diwan.agents import style
    notes = style.brief(office)
    user = runner.user_message(task, {_key(office, ref): rec, "brand": brand.brief(office), **({"company": facts} if facts else {}), **({"hook": hook_card["hook"]} if hook_card else {}),
                                      **{f"worked{i + 1}": b for i, b in enumerate(built)}, **({"style": notes} if notes else {})})
    data, by = None, "template"
    if runner.has_model(c, system, user, schema=schema):
        office.log.append("agent.started", actor="mscript", agent="mscript", caused_by=cause, content={"task": f"Writing the {angle} script for {ref} with the model"})
        try:
            data = runner.call(c, system, user, schema=schema).data
            by = "muse-spark"
            stray = (_amounts(" ".join([data["hook_en"], *data["lines_en"]])) - _amounts(rec)) - {0}
            if stray:
                _blocked(office, "mscript", f"Muse Spark's script named amounts not on the listing ({', '.join(f'{a:,}' for a in stray)}); using the template", cause=cause)
                data, by = None, "template"
        except Exception as e:
            _blocked(office, "mscript", f"Muse Spark failed, using the template: {str(e)[:120]}", cause=cause)
    if not data:
        data = {**_template(lst, angle, brand.cta(office)), "lines_ar": []}
        if base:
            data = {**{k: base[k] for k in ("hook_en", "hook_ar", "lines_en")}, "lines_ar": base.get("lines_ar", [])}
        data = _apply_rules(data, feedback or "", lst)
    data = data | ({"shots": [], "slides": eventpost.slides(data, sh)} if pictures else {"shots": video_plan(data, lst)})
    m = _made(office, "mscript", "script", ref, data | {"via": by, "angle": angle, "why": why, "idea": idea.get("id"), "cards": idea["pick"].get("cards", []),
                                                       "built_like": built, "listing_was": _facts(lst), "format": sh["format"] if pictures else topics.format_for(lst), "job": journey.job_of(lst), **({"revises": base["id"]} if base else {})}, cause)
    _pack(office, "mscript", f"{angle} script{' (revised from ' + base['id'] + ')' if base else ''}: \"{data['hook_en']}\" · {len(data['lines_en'])} lines ({by}).",
          cause=cause, usage={"provider": by})
    return m


FACTS = {"price_aed": "the price", "permit": "the permit", "status": "the status", "beds": "the bedrooms", "features": "the features", "title": "the name",
         "what": "what it is"}


def _facts(lst: dict) -> dict:
    return {k: lst.get(k) for k in FACTS}


def stale(office: Office, sc: dict) -> list[str]:
    """What changed on the listing since the script was written, one sentence each; [] when it is still current
    (or the script is older than this check and has no record of the listing)."""
    was, ref = sc.get("listing_was"), sc.get("ref")
    try:
        now = _facts(_listing(office, ref)) if was else None
    except KeyError:
        return []  # the listing or product is gone
    if not now:
        return []
    show = lambda k, v: f"AED {v:,}" if k == "price_aed" and isinstance(v, int) else ", ".join(v) if isinstance(v, list) else str(v or "none")  # noqa: E731
    return [f"{FACTS[k].capitalize()} was {show(k, was[k])}, now {show(k, now[k])}." for k in FACTS if k in was and was.get(k) != now.get(k)]


def _shorter(hook: str) -> str:
    """A tighter hook that keeps the place: "2 bedroom apartment" becomes "2-bed", filler goes, and if it is still long
    the middle is cut, never the area at the end."""
    end = "?" if hook.rstrip().endswith("?") else "."
    h = re.sub(r"(\d) bedroom (apartment|flat|villa|townhouse|home)", r"\1-bed", hook.rstrip(" .?!"), flags=re.I)
    h = re.sub(r"\b(this|really|just|very|right now|the facts)\s+", "", h, flags=re.I)
    h = re.sub(r"^what does (.+?) buy in (.+)$", r"\1 in \2", h, flags=re.I)        # the price and the place, as a question
    h = re.sub(r"^imagine your (\w+) in (.+)$", lambda m: f"{m.group(1).capitalize()} in {m.group(2)}", h, flags=re.I)
    w = h.split()
    if len(w) >= len(hook.split()):
        w = w[1:]  # drop the opening word, keep the place at the end
    return " ".join(w)[:1].upper() + " ".join(w)[1:] + end


def _apply_rules(data: dict, note: str, lst: dict) -> dict:
    """Changes the template can make without a model: a shorter hook, a feature first, fewer lines, a line removed.
    Anything else waits for the model and says so."""
    d = {**data, "lines_en": list(data["lines_en"])}
    low = note.lower()
    if re.search(r"\b(short|shorter|cut|tighter|punchier)\b.*\bhook\b|\bhook\b.*\b(short|shorter|cut|tighter|punchier)\b|12 words", low):
        d["hook_en"] = _shorter(d["hook_en"])
    for f in lst.get("features") or []:
        if f.lower() in low and re.search(r"\b(first|lead|open|start)\b", low):
            line = f"{f[:1].upper()}{f[1:]}."
            d["lines_en"] = [line] + [x for x in d["lines_en"] if x.lower().rstrip(".") != f.lower()]
    m = re.search(r"\b(?:remove|drop|no|without)\b (?:the )?(?:line )?(?:about |mention of )?([a-z ]{3,30})", low)
    if m:
        w = m.group(1).strip().split()[0]
        d["lines_en"] = [x for x in d["lines_en"] if w not in x.lower() or "permit" in x.lower()] or d["lines_en"]
    if re.search(r"\b(shorter|fewer lines|too long)\b", low) and "hook" not in low and len(d["lines_en"]) > 5:
        keep = [x for x in d["lines_en"] if "permit" in x.lower() or "message us" in x.lower()]
        d["lines_en"] = [x for x in d["lines_en"] if x not in keep][:5 - len(keep)] + keep
    return d


def variants(office: Office, ref: str, idea: dict, tr: dict | None, cause: int | None, n: int = 3) -> list[dict]:
    """Up to n scripts on different angles, each checked by the Copywriter, chosen by the strategy."""
    from diwan.agents import journey, strategy
    from diwan.agents import rhythm
    avoid = rhythm.recent_angles(office, business.local(_now(), office).date())
    lst = _listing(office, ref)
    picks = (journey.pick_angles(journey.job_of(lst), n, avoid) if lst.get("job") or lst.get("moment") else topics.pick_angles(n, avoid) if lst["item"] == "topic"
             else strategy.pick(office, n, avoid=avoid))
    ways = idea.get("ideas") or [idea["pick"]]  # each script tells its own idea, when there are enough
    _pack(office, "mcopy", "Scripting " + "; ".join(f"{p['angle']} ({p['slot']}: {p['why']})" for p in picks), cause=cause, kind="assign")
    out = []
    for i, p in enumerate(picks):
        one = idea | {"pick": ways[i % len(ways)]}
        sc = reviewed(office, "script", ref, lambda fb, p=p, one=one: script(office, ref, one, tr, cause, fb, angle=p["angle"], why=f"{p['slot']}: {p['why']}"), cause)
        if sc and not any(sc["hook_en"] == x["hook_en"] and sc["lines_en"] == x["lines_en"] for x in out):  # without a model, topics can come out the same
            out.append(sc)
    return out


def video_check(office: Office, ref: str, sc: dict, cause: int | None) -> dict | None:
    f = footage(office, ref)
    if not f:
        _blocked(office, "mcheck", f"Waiting for footage of {ref} (upload it in the studio)", cause=cause)
        return None
    if not can_transcribe():
        _blocked(office, "mcheck", "Checking the take needs Muse Voice Transcribe (META_API_KEY)", cause=cause)
        return None
    try:
        t = transcribe(_wav(Path(f["path"])))
    except Exception as e:
        _blocked(office, "mcheck", f"Could not transcribe the footage: {str(e)[:160]}", cause=cause)
        return None
    words = lambda x: re.findall(r"[a-z\u0600-\u06ff]+|\d+", x.lower().replace(",", ""))  # noqa: E731
    heard = set(words(t["text"]))
    drift = [ln for ln in sc["lines_en"] if words(ln) and sum(w in heard for w in words(ln)) / len(words(ln)) < .6]
    m = _made(office, "mcheck", "take check", ref, {"said": t["text"], "turns": t["turns"], "drift": drift, "via": t["via"]}, cause)
    _pack(office, "mcheck", ("The take follows the script." if not drift else f"{len(drift)} line(s) drifted: \"{drift[0][:80]}\"") + f" (heard by {t['via']})", cause=cause,
          kind="draft" if not drift else "send_back")
    return m


def playbook(office: Office, cause: int | None) -> dict | None:
    ours = posts(office, "own")
    if len(ours) < 5:
        _pack(office, "mplay", f"Not enough of our own posts to learn from yet ({len(ours)}; need 5).", cause=cause, kind=None)
        return None
    med = statistics.median(p["engagement"] for p in ours)
    wins = [p for p in ours if med and p["engagement"] >= 2 * med]
    if not wins:
        _pack(office, "mplay", "None of our posts reached 2x our usual yet.", cause=cause, kind=None)
        return None
    entries = [{"post": p["id"], "type": p["type"], "opener": (p["caption"] or "").split("\n")[0][:80], "x": round(p["engagement"] / med, 1), "url": p["permalink"]} for p in wins]
    types = Counter(e["type"] for e in entries).most_common(1)[0][0]
    m = _made(office, "mplay", "playbook", "ours", {"entries": entries, "pattern": f"mostly {types.lower()}"}, cause)
    _pack(office, "mplay", f"{len(entries)} of our posts beat 2x our usual; mostly {types.lower()}. Added to the playbook.", cause=cause)
    return m


# ---------- editing ----------

CAPTION_WORDS = 6  # a caption is read in a glance: longer spoken turns are split, each part timed by its share of the words


def _short(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        words = str(r.get("text") or "").split()
        parts = [words[i:i + CAPTION_WORDS] for i in range(0, len(words), CAPTION_WORDS)]
        at, each = r["start"], (r["end"] - r["start"]) / max(1, len(words))
        for p in parts:
            out.append({"start": at, "end": at + each * len(p), "text": " ".join(p)})
            at += each * len(p)
    return out


def _srt(turns: list[dict], text: str, dur: float) -> str:
    rows = _short([t for t in turns if t.get("start") is not None and t.get("end") is not None])
    if not rows:  # no timings from the API: spread the words evenly over the clip, five words a line
        words = text.split()
        chunks = [" ".join(words[i:i + 5]) for i in range(0, len(words), 5)] or [""]
        step = dur / len(chunks) if dur else 2.0
        rows = [{"start": i * step, "end": (i + 1) * step, "text": c} for i, c in enumerate(chunks)]
    ts = lambda s: f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{int(s % 60):02d},{int(s * 1000 % 1000):03d}"  # noqa: E731
    return "\n".join(f"{i}\n{ts(r['start'])} --> {ts(r['end'])}\n{r['text']}\n" for i, r in enumerate(rows, 1))


def _caption_png(text: str, path: Path, width: int) -> None:
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for f in ("C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(f, max(18, width // 15))
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    words, lines, line = text.split(), [], ""
    for w in words:
        t = f"{line} {w}".strip()
        if d.textlength(t, font=font) > width * .86 and line:
            lines.append(line)
            line = w
        else:
            line = t
    lines.append(line)
    lh = int(font.size * 1.3)
    img = Image.new("RGBA", (width, lh * len(lines) + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = (width - d.textlength(ln, font=font)) / 2
        d.text((x, 12 + i * lh), ln, font=font, fill="white", stroke_width=max(2, font.size // 10), stroke_fill="black")
    img.save(path)


def captions(office: Office, ref: str, check: dict | None, cause: int | None) -> dict | None:
    f = footage(office, ref)
    if not f:
        _blocked(office, "mcap", f"Waiting for footage of {ref}", cause=cause)
        return None
    src = Path(f["path"])
    dur = _duration(src)
    srt = src.with_suffix(".srt")
    if f.get("lines"):  # our own voice read our own script: its exact words, at the times they were spoken
        srt.write_text(_srt(f["lines"], "", dur))
        source = "the script, timed to the voice"
    elif check and check["said"].strip():
        srt.write_text(_srt(check["turns"], check["said"], dur))
        source = f"what was said ({check.get('via', 'transcribed')})"
    elif (sc := made(office, "script", ref)):
        lines = sc["lines_en"]
        step = dur / max(1, len(lines))
        srt.write_text(_srt([{"start": i * step, "end": (i + 1) * step, "text": ln} for i, ln in enumerate(lines)], "", dur))
        source = "the script (the audio could not be transcribed)"
    else:
        _blocked(office, "mcap", "Captions need a transcript of the take or a script", cause=cause)
        return None
    rows = [blk.split("\n") for blk in srt.read_text().strip().split("\n\n") if "-->" in blk]
    w = _width(src)
    inputs, chain, last = ["-i", str(src)], [], "[0:v]"
    secs = lambda t: sum(float(x) * m for x, m in zip(t.replace(",", ".").split(":"), (3600, 60, 1)))  # noqa: E731
    for i, r in enumerate(rows):
        a, b = (secs(x.strip()) for x in r[1].split("-->"))
        png = src.with_name(f"{src.stem}-cap{i}.png")
        _caption_png(" ".join(r[2:]), png, w)
        inputs += ["-i", str(png)]
        out = f"[v{i}]"
        chain.append(f"{last}[{i + 1}:v]overlay=(W-w)/2:H-h-H*0.12:enable='between(t,{a:.2f},{b:.2f})'{out}")
        last = out
    meta.MEDIA.mkdir(parents=True, exist_ok=True)
    out = meta.MEDIA / f"cut-{ref}-{f['id']}.mp4"
    try:
        _ffmpeg(*inputs, "-filter_complex", ";".join(chain), "-map", last, "-map", "0:a?", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(out))
    except Exception as e:
        _blocked(office, "mcap", f"ffmpeg could not put the captions on: {str(e)[:160]}", cause=cause)
        return None
    m = _made(office, "mcap", "cut", ref, {"path": str(out), "served": f"/media/{out.name}", "srt": str(srt), "lines": len(rows), "from": source}, cause)
    _pack(office, "mcap", f"Captions on the video: {len(rows)} lines from {source}. Cut ready.", cause=cause)
    return m


def remix(office: Office, ref: str, tr: dict | None, film: dict, cause: int | None) -> dict | None:
    if not tr:
        _pack(office, "mremix", "No outlier transcript to remix; the cut follows our own film list.", cause=cause, kind=None)
        return None
    beats = tr["beats"]
    plan = [{"beat": b[:90], "our_shot": film["shots"][i] if i < len(film["shots"]) else film["shots"][-1]} for i, b in enumerate(beats[:len(film["shots"])])]
    m = _made(office, "mremix", "remix plan", ref, {"from": tr["account"], "post": tr["post"], "plan": plan}, cause)
    _pack(office, "mremix", f"Using the structure of @{tr['account']}'s outlier ({len(plan)} beats), our own shots and words.", cause=cause)
    return m


def post_text(office: Office, ref: str, sc: dict, cause: int | None, feedback: str | None = None) -> dict:
    lst = _listing(office, ref)
    feats = ", ".join(lst.get("features") or [])
    where = f", {lst['community']}" if lst.get("community") else ""
    facts = " · ".join(x for x in (f"{lst['title']}{where}", _what(lst), feats, _price(lst)) if x) if lst["item"] != "topic" else \
        f"{lst['title']}: " + " ".join(f if f.endswith((".", "!", "?")) else f + "." for f in (lst.get("features") or [])[:2])
    permit = f"\nPermit {lst['permit']}" if business.permit_needed(office) and lst.get("permit") else ""
    if sc.get("slides"):  # read, not watched: the caption is the post's own words
        facts = "\n".join(x for x in sc["lines_en"] if x != brand.cta(office))
    from diwan.agents import marketing
    code = marketing.code_for(office, ref)  # how a lead is traced back to this post
    base = f"{sc['hook_en']}\n\n{facts}{permit}\n\n{brand.cta(office)} Say {code}."
    ar = f"\n\n{sc['hook_ar']}" if sc.get("hook_ar") else ""
    tags = " " + " ".join(dict.fromkeys(brand.hashtags(office) + (["#" + re.sub(r"\W", "", lst["community"])] if lst.get("community") else [])))
    m = _made(office, "mwriter", "post text", ref, {"text": base + ar + tags.rstrip(), "code": code}, cause)
    _pack(office, "mwriter", f"Post text ready{' with permit ' + str(lst.get('permit')) if permit else ''} ({len(m['text'])} characters).", cause=cause,
          evidence=[Evidence(str(lst.get("permit") or lst["title"]), _key(office, ref))], sources={_key(office, ref): _brief(office, ref)})
    return m


# ---------- publishing ----------

def cover(office: Office, ref: str, sc: dict, cause: int | None) -> dict | None:
    """Two cover options, each a frame of our own footage with the hook on it. Never a generated picture: it could show
    a view the property does not have."""
    f = footage(office, ref)
    if not f:
        _blocked(office, "mthumb", f"A cover needs footage of {ref}: the covers are frames of our own take", cause=cause)
        return None
    src = Path(f["path"])
    dur = _duration(src)
    meta.MEDIA.mkdir(parents=True, exist_ok=True)
    hook = src.with_name(f"{src.stem}-hook.png")
    _caption_png(sc["hook_en"], hook, _width(src))
    options = []
    for k, at in enumerate((.3, .6), 1):
        sec = round(max(.5, dur * at), 1)
        img = meta.MEDIA / f"cover-{ref}-{f['id']}-{k}.jpg"
        try:
            _ffmpeg("-ss", f"{sec}", "-i", str(src), "-i", str(hook), "-filter_complex", "[0:v][1:v]overlay=(W-w)/2:H*0.12", "-frames:v", "1", str(img))
            options.append({"served": f"/media/{img.name}", "at": sec})
        except Exception as e:
            _blocked(office, "mthumb", f"ffmpeg could not make a cover at {sec}s: {str(e)[:160]}", cause=cause)
    if not options:
        return None
    m = _made(office, "mthumb", "cover", ref, {"options": options, "footage": f["id"]}, cause)
    _pack(office, "mthumb", f"{len(options)} cover option{'s' if len(options) > 1 else ''} from {f['id']} at "
          + ", ".join(f"{o['at']}s" for o in options) + ", with the hook on them.", cause=cause)
    return m


def permit_check(office: Office, ref: str, text: dict, cause: int | None, findings: list | None = None) -> bool:
    lst = _listing(office, ref)
    t = text["text"]
    fails, needed = [], business.permit_needed(office) and lst["item"] != "topic"  # a topic sells no one thing, so it has no permit
    if needed and (not lst.get("permit") or lst["permit"] not in t):
        fails.append("permit number missing")
    stray = _amounts(t) - {lst["price_aed"]} - {0} - (_amounts(_brief(office, ref)) if lst["item"] == "topic" else set())
    if stray:
        fails.append(f"amounts not on the {lst['item']}: {', '.join(f'{a:,}' for a in stray)}")
    if m := re.search(BANNED, t, re.I):
        fails.append(f"banned promise \"{m.group(0)}\"")
    _pack(office, "mpermit", (f"Pass: {'permit ' + str(lst['permit']) + ', ' if needed else ''}price matches {ref}, no banned promises.") if not fails else "Held: " + "; ".join(fails) + ".",
          cause=cause, kind=None if not fails else "hold")
    if findings is not None:
        findings.extend(fails)
    return not fails


def schedule(office: Office, cause: int | None) -> dict:
    ours = [p for p in posts(office, "own") if p.get("at")]
    if len(ours) >= 5:
        by_hour: dict[int, list[int]] = {}
        for p in ours:
            hr = business.local(datetime.fromisoformat(p["at"].replace("+0000", "+00:00")), office).hour
            by_hour.setdefault(hr, []).append(p["engagement"])
        hour = max(by_hour, key=lambda k: statistics.mean(by_hour[k]))
        why = f"our posts at {hour}:00 {business.tz_label(office)} did best ({len(ours)} posts)"
    else:
        hour, why = 19, f"not enough history ({len(ours)} posts), so the evening default"
    now = datetime.now(business.tz(office))
    when = (now + timedelta(days=1)).replace(hour=hour, minute=30, second=0, microsecond=0)
    m = _made(office, "msched", "slot", "next", {"at": when.isoformat(), "why": why}, cause)
    _pack(office, "msched", f"Slot: {when.strftime('%A %I:%M %p').replace(' 0', ' ')}, because {why}.", cause=cause)
    return m


def cross(office: Office, ref: str, text: dict, cause: int | None) -> dict:
    t = text["text"]
    versions = {p: (t if len(t) <= n else t[:n - 1] + "…") for p, n in LIMITS.items() if p in (business.platforms(office) or LIMITS)}
    if "YouTube Shorts" in versions:
        versions["YouTube Shorts"] = t.split("\n")[0][:100]
    m = _made(office, "mcross", "versions", ref, {"versions": versions}, cause)
    _pack(office, "mcross", f"Versions for {', '.join(versions)}, each within its limit.", cause=cause)
    return m


def ask_to_publish(office: Office, ref: str, cut: dict | None, text: dict, slot: dict, cause: int | None, word: str = "reel", note: str = "") -> int:
    """One open publish request per listing: an older one is answered as replaced before the new one is asked."""
    for n in office.graph().of("request", status="open"):
        if n.props.get("agent") == "mpub" and ref in n.props.get("text", ""):
            office.log.append("decision.made", actor="mpub", agent="mpub", content={"card": n.id, "answer": "replaced by a newer request"})
    if cut:
        office.log.append("content.ready", actor="mpub", agent="mpub", caused_by=cause, content={"ref": ref})
    what = f"Publish the {ref} {word} {datetime.fromisoformat(slot['at']).strftime('%a %I:%M %p').replace(' 0', ' ')}" + ("" if cut else " (no cut yet: footage needed)") + note
    _pack(office, "mpub", what, cause=cause, kind="publish")
    return 0


def _missing(office: Office, ref: str) -> list[str]:
    """What must exist before this post can go out, and whatever about it has stopped being true."""
    from diwan.agents import marketing
    sc = approved_script(office, ref)
    pics = made(office, "slides", ref) if sc and sc.get("slides") else None
    return [x for x, ok in (("the images" if sc and sc.get("slides") else "the captioned cut (upload footage)", pics or made(office, "cut", ref)), ("post text", made(office, "post text", ref)),
                            ("Instagram connected", instagram.ready()), (f"PUBLIC_BASE_URL (a public https address for the {'images' if pics else 'video'})", env("PUBLIC_BASE_URL"))) if not ok] + marketing.blocked(office, ref)


def approve_post(office: Office, ref: str, *, by: str, at: str | None = None) -> dict:
    """Approved: it goes out at the time on the card (or the one the person chose), not before; a time already gone means now."""
    if (needs := _missing(office, ref)):
        _pack(office, "mpub", f"Approved by {name(by)}; not posted yet. Needs: {', '.join(needs)}.", kind=None)
        return {"ok": False, "needs": needs}
    slot = made(office, "slot", "next")
    when_at = slot["at"] if slot else None
    if at:
        try:
            chosen = datetime.fromisoformat(at)
        except ValueError:
            return {"ok": False, "needs": ["a time like 2026-11-02T19:30"]}
        chosen = chosen if chosen.tzinfo else chosen.replace(tzinfo=business.tz(office))
        if chosen <= datetime.now(timezone.utc):
            return {"ok": False, "needs": ["a time still ahead"]}
        when_at = chosen.isoformat()
    if not when_at or datetime.fromisoformat(when_at) <= datetime.now(timezone.utc):
        return publish(office, ref, by=by)
    _made(office, "mpub", "scheduled", ref, {"at": when_at, "approved_by": by}, None)
    office.log.append("post.approved", actor=by, agent="mpub", content={"ref": ref, "at": when_at})
    when = datetime.fromisoformat(when_at).strftime("%a %I:%M %p").replace(" 0", " ")
    _pack(office, "mpub", f"Approved by {name(by)}: {ref} goes out {when}.", kind=None)
    return {"ok": True, "next": f"it goes out {when}"}


def scheduled(office: Office) -> dict[str, dict]:
    """Posts approved and waiting for their time, by ref. Posting, or cancelling, ends the wait."""
    out: dict[str, dict] = {}
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "content.made" and c.get("kind") == "scheduled":
            out[c["ref"]] = c
        elif e["type"] == "content.made" and c.get("kind") in ("published", "unscheduled"):
            out.pop(c.get("ref"), None)
    return out


def unschedule(office: Office, ref: str, *, by: str, why: str = "cancelled") -> None:
    _made(office, "mpub", "unscheduled", ref, {"by": by, "why": why}, None)
    _pack(office, "mpub", f"{ref} will not go out: {why} ({name(by)}).", kind=None)


def publish_due(office: Office) -> list[str]:
    """Called every minute: what was approved goes out at its time, or, with auto-posting off (the default), the person who
    approved it is told it is time. A failure is said once, not retried for ever."""
    from diwan import leads
    from diwan.agents import marketing, rhythm
    done = []
    auto = rhythm.settings(office)["auto_post"] == "on"
    for ref, s in scheduled(office).items():
        if datetime.fromisoformat(s["at"]) <= datetime.now(timezone.utc):
            if not auto:
                if marketing._once(office, f"due:{ref}:{s['id']}", ref=ref):
                    leads.notify(office, s["approved_by"], f"It's time to post {ref}. Press Post now in the Studio.", kind="info")
                continue
            r = publish(office, ref, by=s["approved_by"])
            if r.get("ok"):
                done.append(ref)
            else:
                unschedule(office, ref, by="mpub", why=f"it could not be posted: {r.get('error') or ', '.join(r.get('needs', []))}")
    return done


def publish(office: Office, ref: str, *, by: str) -> dict:
    """Post to Instagram now, when everything needed is there; otherwise say what is missing."""
    sc = approved_script(office, ref)
    pics = made(office, "slides", ref) if sc and sc.get("slides") else None
    cut, text = pics or made(office, "cut", ref), made(office, "post text", ref)
    base = env("PUBLIC_BASE_URL")
    needs = _missing(office, ref)
    if needs:
        _pack(office, "mpub", f"Approved by {name(by)}; not posted yet. Needs: {', '.join(needs)}.", kind=None)
        return {"ok": False, "needs": needs}
    try:
        urls = [f"{base.rstrip('/')}{x['served']}" for x in pics["images"]] if pics else []
        pid = (instagram.publish_carousel(urls, text["text"]) if len(urls) > 1 else instagram.publish_image(urls[0], text["text"]) if urls
               else instagram.publish_reel(f"{base.rstrip('/')}{cut['served']}", text["text"]))
    except instagram.InstagramError as e:
        _pack(office, "mpub", f"Instagram refused the post: {e}", kind=None)
        return {"ok": False, "error": str(e)}
    _made(office, "mpub", "published", ref, {"instagram_id": pid, "approved_by": by}, None)
    office.log.append("post.live", actor=by, agent="mpub", content={"ref": ref, "instagram_id": pid})
    _pack(office, "mpub", f"Posted to Instagram (id {pid}), approved by {name(by)}.", kind=None)
    return {"ok": True, "id": pid}


# ---------- supervision: make, check, return with the fix, escalate ----------

def reviewed(office: Office, kind: str, ref: str, make, cause: int | None):
    """Make a piece of work and have the room lead check it; send it back with the reasons up to twice more; then
    the Marketing lead raises it to a person. Returns the accepted work, or None if it was escalated."""
    from diwan.agents import qa
    feedback, fails = None, []
    for attempt in range(1, qa.MAX_TRIES + 1):
        item = make(feedback)
        if item is None:
            return None  # the step itself is waiting for something (already said why)
        fails = qa.review(office, kind, ref, item, cause=cause, attempt=attempt)
        if not fails:
            return item
        feedback = qa.feedback_text(fails)
    qa.escalate(office, kind, ref, fails, cause=cause)
    return None


def permit_gate(office: Office, ref: str, sc: dict, text: dict, cause: int | None) -> tuple[bool, dict, dict]:
    """The last gate before publishing. A hold is traced to the agent who caused it, who fixes it; then it is checked again."""
    from diwan.agents import qa
    for attempt in range(1, qa.MAX_TRIES + 1):
        found: list = []
        if permit_check(office, ref, text, cause, found):
            return True, sc, text
        owner = qa.blame(office, ref, "; ".join(found), sc, text)
        fails = [{"check": "permit-gate", "rule": "Passes the permit check.", "found": f, "owner": owner, "fix": "Remove what the permit checker held."} for f in found]
        office.log.append("qa.failed", actor="mpub", agent="mpub", caused_by=cause,
                          content={"kind": "permit", "ref": ref, "attempt": attempt, "fails": fails, "returned_to": [owner]})
        if attempt == qa.MAX_TRIES:
            qa.escalate(office, "post", ref, fails, cause=cause)
            return False, sc, text
        fb = qa.feedback_text(fails)
        if owner == "mscript":
            sc = script(office, ref, {"pick": {"title": (made(office, "ideas", ref) or {}).get("pick", {}).get("title", ref)}}, None, cause, fb)
        text = post_text(office, ref, sc, cause, fb)
    return False, sc, text


# ---------- the run ----------

async def run(office: Office, ref: str, pause: float = .6, auto: bool = False) -> None:
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    lst = _listing(office, ref)
    needed = business.permit_needed(office) and lst["item"] != "topic"
    start = _pack(office, "mkt", f"New {'informational video' if lst['item'] == 'topic' else 'reel'} for {lst['title']} ({ref})" + (f": permit {lst.get('permit') or 'MISSING'}." if needed else "."), kind="assign")
    if needed and not lst.get("permit"):
        _blocked(office, "mkt", f"{ref} has no permit number: nothing is made for it", cause=start)
        return
    top = await step(watch, office, start); await asyncio.sleep(pause)
    await step(read_posts, office, start); await asyncio.sleep(pause)
    tr_cards = await step(trends, office, start); await asyncio.sleep(pause)
    tr = await step(transcript_of, office, top[0] | {"post": top[0]["id"]} if top else None, start); await asyncio.sleep(pause)
    if lst.get("moment"):  # something real happened: look at what we have of it, and search for it once
        from diwan.agents import eventpost
        await step(eventpost.read, office, ref, start)
        await step(eventpost.search, office, ref, start)
    pins = board(office)
    _pack(office, "research", f"Board: {len(pins)} card{'s' if len(pins) != 1 else ''} pinned, each with its source." if pins else "Board empty: see what research is waiting for.",
          cause=start, kind="assign")
    idea = await step(reviewed, office, "ideas", ref, lambda fb: ideas(office, ref, pins, start, fb), start); await asyncio.sleep(pause)
    if not idea:
        return
    office.log.append("content.idea", actor="midea", agent="midea", caused_by=start, content={"ref": ref, "title": idea["pick"]["title"]})
    from diwan.agents import rhythm
    if auto and rhythm.settings(office)["approve_brief"] == "on":  # nobody pressed anything: a person says yes before scripts are written
        _pack(office, "mcopy", f"Approve the brief for {ref}: \"{idea['pick']['title']}\"", cause=start, kind="approve_brief")
        return
    await write_scripts(office, ref, idea, tr, start, pause)


async def write_scripts(office: Office, ref: str, idea: dict, tr: dict | None, start: int | None, pause: float = .6) -> None:
    """The brief is approved (a person pressing Write approves it): the scripts."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    office.log.append("content.briefed", actor="mkt", agent="mkt", caused_by=start, content={"ref": ref})
    await step(lanes, office, start); await asyncio.sleep(pause)
    scs = await step(variants, office, ref, idea, tr, start); await asyncio.sleep(pause)
    if not scs:
        return
    await step(playbook, office, start)
    ask_script_approval(office, ref, scs, start)  # nothing that costs filming, editing or model time starts before a person says yes


async def after_brief(office: Office, ref: str, pause: float = .6) -> None:
    """An automatic run's brief got its yes."""
    idea = made(office, "ideas", ref)
    if idea:
        await write_scripts(office, ref, idea, made(office, "transcript"), None, pause)


def _content(office: Office, cid: str) -> dict | None:
    return next((e["content"] for e in office.log.list() if e["type"] == "content.made" and e["content"]["id"] == cid), None)


def ask_script_approval(office: Office, ref: str, scs: list[dict] | dict, cause: int | None) -> None:
    """The Copywriter asks the Marketing manager to pick one of the checked scripts (or ask for a change).
    An older open request for this listing is replaced."""
    scs = [scs] if isinstance(scs, dict) else scs
    for n in office.graph().of("request", status="open"):
        if n.props.get("kind") == "use_script" and ref in n.props.get("text", ""):
            office.log.append("decision.made", actor="mcopy", agent="mcopy", content={"card": n.id, "answer": "replaced by a newer draft"})
    office.log.append("content.scripted", actor="mcopy", agent="mcopy", caused_by=cause, content={"ref": ref})
    opts = " | ".join(f"script {x['id']} [{x.get('angle', 'price-reveal')}] \"{x['hook_en']}\"" for x in scs)
    _pack(office, "mcopy", f"Pick a script for {ref} ({len(scs)} checked by the Copywriter): {opts}", cause=cause, kind="use_script")


def own_script(office: Office, ref: str, text: str, *, by: str) -> dict:
    """A script the Marketing manager wrote: checked like the Script writer's, every problem listed (nothing is fixed
    behind their back), then told two other ways on angles the strategy picks. All three are offered to pick from."""
    from diwan.agents import qa, strategy
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if len(lines) < 2:
        raise ValueError("Write the hook on the first line and the script's lines below it.")
    hook_ar = next((x for x in lines if re.search(r"[\u0600-\u06ff]", x)), "")
    en = [x for x in lines if x != hook_ar]
    lst = _listing(office, ref)
    data = {"hook_en": en[0], "hook_ar": hook_ar, "lines_en": en[1:], "lines_ar": []}
    start = _pack(office, "mcopy", f"{name(by)} wrote a script for {ref}: checking it, then telling it two other ways.", kind="assign")
    fails = qa.review(office, "script", ref, data, cause=start, attempt=1)
    mine = strategy.angle_of(text)
    own = _made(office, "mcopy", "script", ref, data | {"shots": video_plan(data, lst), "via": f"written by {name(by)}", "angle": mine or "your own", "why": "your script", "own": True,
                                                        "written_by": by, "cards": [], "built_like": [], "listing_was": _facts(lst),
                                                        "problems": [f"{f['rule']} Found: {f['found']}. {f['fix']}" for f in fails]}, start)
    idea = {"id": None, "pick": {"title": en[0], "cards": []}}
    fb = (f"Tell the same message as this script, written by the Marketing manager, on this angle instead. Keep its facts and its point; "
          f"change the angle and the structure, never invent anything:\n{text}")
    alts = []
    for p in [x for x in (topics.pick_angles(3, set()) if lst["item"] == "topic" else strategy.pick(office, 3)) if x["angle"] != mine][:2]:
        sc = reviewed(office, "script", ref, lambda f, p=p: script(office, ref, idea, None, start, "\n".join(x for x in (fb, f) if x), angle=p["angle"],
                                                                   why=f"another way to tell your script ({p['angle']})"), start)
        if sc:
            alts.append(sc)
    ask_script_approval(office, ref, [own, *alts], start)
    return {"own": own, "others": alts}


def script_options(office: Office, text: str) -> list[dict]:
    """The scripts offered in a request, in order."""
    return [c for c in (_content(office, i) for i in re.findall(r"script (C\d+)", text)) if c]


def approved_script(office: Office, ref: str) -> dict | None:
    """The script a person approved for filming, if any: the one they picked, or the only one offered."""
    g = office.graph()
    for e in reversed(office.log.list()):
        if e["type"] == "decision.made" and e["content"].get("answer") == "approve":
            n = g.nodes.get(e["content"]["card"])
            if n and n.props.get("kind") == "use_script" and ref in n.props.get("text", ""):
                opts = script_options(office, n.props["text"])
                choice = e["content"].get("choice")
                return next((x for x in opts if x["id"] == choice), opts[0] if opts else None)
    return None


async def script_revise(office: Office, ref: str, sid: str, note: str, card: str | None = None, pause: float = .6) -> None:
    """The Marketing manager asked for a change to one script: the Script writer revises that one, the Copywriter checks
    it, and the choice is asked again with the revision in its place."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    base = _content(office, sid)
    if not base:
        return
    n = office.graph().nodes.get(card) if card else None
    others = script_options(office, n.props["text"]) if n else [base]
    idea, tr = made(office, "ideas", ref), made(office, "transcript")
    start = _pack(office, "mcopy", f"Change asked to {sid} for {ref}: \"{note}\". Back to the Script writer.", kind="assign")
    fb = f"The Marketing manager asked for this change: {note}"
    angle = base.get("angle", "price-reveal")
    sc = await step(reviewed, office, "script", ref,
                    lambda f: script(office, ref, idea, tr, start, "\n".join(x for x in (fb, f) if x), angle=angle, why=base.get("why", ""), base=base), start)
    if sc:
        ask_script_approval(office, ref, [sc if x["id"] == sid else x for x in others], start)


async def after_script(office: Office, ref: str, pause: float = .6) -> None:
    """The script is approved: the broker gets the film list, the post text is written. Editing waits for footage."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    sc = approved_script(office, ref)
    if not sc:
        return
    idea = made(office, "ideas", ref)
    if sc.get("slides"):
        await after_pictures(office, ref, sc, pause)
        return
    start = _pack(office, "mkt", f"Script {sc['id']} for {ref} approved: filming can start.", kind="assign")
    film = await step(reviewed, office, "film list", ref, lambda fb: film_list(office, ref, idea, start, fb, sc), start); await asyncio.sleep(pause)
    if film:
        office.add_task(None, "mshoot", f"Film {ref}: " + "; ".join(film["shots"]) + f" ({film['when']})", needs_person=film["who"], by="mshoot", caused_by=start)
        _pack(office, "mshoot", f"Film list sent to {name(film['who'])} {film['when']}. Or make an AI presenter video from the studio.", cause=start)
    await step(reviewed, office, "post text", ref, lambda fb: post_text(office, ref, sc, start, fb), start)


async def after_pictures(office: Office, ref: str, sc: dict, pause: float = .6) -> None:
    """A carousel, an image or a graphic is approved: nothing to film. The images, the caption, the checks, the request."""
    from diwan.agents import eventpost
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    start = _pack(office, "mkt", f"Script {sc['id']} for {ref} approved: making the images.", kind="assign")
    pics = await step(reviewed, office, "slides", ref, lambda fb: eventpost.render(office, ref, sc, start), start); await asyncio.sleep(pause)
    if not pics:
        return
    text = await step(reviewed, office, "post text", ref, lambda fb: post_text(office, ref, sc, start, fb), start)
    if not text:
        return
    await _to_approval(office, ref, sc, text, start)


async def _to_approval(office: Office, ref: str, sc: dict, text: dict, start: int | None) -> None:
    """The last gate, the platform versions, the time, and the request to the person who approves publishing."""
    from diwan.agents import eventpost
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    ok, sc, text = await step(permit_gate, office, ref, sc, text, start)
    if not ok:
        return
    await step(reviewed, office, "versions", ref, lambda fb: cross(office, ref, text, start), start)
    slot = made(office, "slot", "next")
    if not slot or datetime.fromisoformat(slot["at"]) <= datetime.now(timezone.utc):  # an old time is no use
        slot = await step(schedule, office, start)
    pics = made(office, "slides", ref) if sc.get("slides") else None
    if pics:
        note = f" · {pics['people']} of the images show people: check they agreed" if pics.get("people") else ""
        await step(ask_to_publish, office, ref, pics, text, slot, start, eventpost.FORMATS[sc["format"]].lower(), note)
    else:
        await step(ask_to_publish, office, ref, made(office, "cut", ref), text, slot, start, "reel", " · footage and music must be ours or licensed")


CAPTION = r"\b(caption|hashtags?|post text|description|sign.?off)\b"
REFILM = r"\b(video|footage|film|refilm|retake|reshoot|re-?shoot|clip|lighting|sound|audio)\b"
CAPTION_SCHEMA = {"name": "post", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {"text": {"type": "string"}}}}


def change_goes_to(sc: dict | None, note: str) -> str:
    """Who fixes a change asked on the finished post: the words under it, the footage, or the script (and so the images)."""
    low = note.lower()
    if re.search(CAPTION, low):
        return "mwriter"
    return "mshoot" if sc and not sc.get("slides") and re.search(REFILM, low) else "mscript"


def rewrite_caption(office: Office, ref: str, note: str, cause: int | None, feedback: str | None = None) -> dict:
    """Only the post's text changes. Without a model it stays as it was, and says so."""
    old, c = made(office, "post text", ref), get("mwriter")
    system = runner.instructions(c, office.log, pack=False) + "\nAnswer in the `post` format: `text` is the post exactly as the public will read it, and nothing else. Change only what is asked and keep the rest, including the code word after \"Say\"."
    user = runner.user_message(f"Change this post's text: {note}" + (f"\n\n{feedback}" if feedback else ""),
                               {"post": old["text"], _key(office, ref): _brief(office, ref), "brand": brand.brief(office)})
    if not runner.has_model(c, system, user, schema=CAPTION_SCHEMA):
        _blocked(office, "mwriter", "Rewriting the post text needs Muse Spark (META_API_KEY): it is unchanged", cause=cause)
        return old
    return _made(office, "mwriter", "post text", ref, {"text": runner.call(c, system, user, schema=CAPTION_SCHEMA).data["text"], "code": old.get("code")}, cause)


async def change_post(office: Office, ref: str, note: str, pause: float = .6) -> None:
    """A change asked at the last step goes to whoever can fix it, then comes back through the same checks."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    sc = approved_script(office, ref)
    if not sc:
        return
    who = change_goes_to(sc, note)
    start = _pack(office, "mkt", f"Change asked to the finished {ref} post: \"{note}\". Back to the {get(who).name}.", kind="assign")
    if who == "mwriter":
        text = await step(reviewed, office, "post text", ref, lambda fb: rewrite_caption(office, ref, note, start, fb), start)
        if text:
            await _to_approval(office, ref, sc, text, start)
    elif who == "mshoot":
        film = made(office, "film list", ref) or {}
        office.add_task(None, "mshoot", f"Film {ref} again: {note}", needs_person=film.get("who"), by="mshoot", caused_by=start)
        _pack(office, "mshoot", f"Asked {name(film.get('who') or '') or 'nobody assigned yet'} to film {ref} again. Editing starts when the new take is uploaded.", cause=start)
    else:
        await script_revise(office, ref, sc["id"], note, None, pause)


async def script_rejected(office: Office, ref: str, note: str, pause: float = .6) -> None:
    """A person sent all the scripts back: the note goes to the Script writer, new drafts are checked and asked again."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    idea, tr = made(office, "ideas", ref), made(office, "transcript")
    start = _pack(office, "mcopy", f"Scripts for {ref} sent back by the Marketing manager: {note or 'no reason given'}", kind="assign")
    fb = f"The Marketing manager sent your script back: {note}" if note else None
    sc = await step(reviewed, office, "script", ref, lambda f: script(office, ref, idea, tr, start, "\n".join(x for x in (fb, f) if x) or None), start)
    if sc:
        ask_script_approval(office, ref, [sc], start)


async def after_footage(office: Office, ref: str, pause: float = .6) -> None:
    """Footage arrived: check the take, caption it, cover it, re-check the permit and ask to publish."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    sc = approved_script(office, ref)
    if not sc:
        _blocked(office, "mcheck", f"Footage for {ref} is waiting: no approved script yet (the Marketing manager approves it first)")
        return
    start = _pack(office, "mart", f"Footage for {ref} arrived: checking, captioning and covering it.", kind="assign")
    chk = await step(video_check, office, ref, sc, start); await asyncio.sleep(pause)
    cut = await step(reviewed, office, "cut", ref, lambda fb: captions(office, ref, chk, start), start); await asyncio.sleep(pause)
    text = made(office, "post text", ref) or await step(reviewed, office, "post text", ref, lambda fb: post_text(office, ref, sc, start, fb), start)
    if not text:
        return
    await step(cover, office, ref, sc, start); await asyncio.sleep(pause)
    await step(remix, office, ref, made(office, "transcript"), made(office, "film list", ref) or {"shots": ["our own shots"]}, start)
    await _to_approval(office, ref, sc, text, start)


async def ai_video(office: Office, ref: str, *, by: str, consent: bool, poll: float = 10, wait: float = 900) -> dict:
    """An AI presenter reads the approved script (HeyGen). Started by a person, who confirms the avatar's consent."""
    from diwan.providers import heygen
    sc = approved_script(office, ref)
    if not sc:
        return {"ok": False, "needs": "an approved script (the Marketing manager approves it first)"}
    if not consent:
        return {"ok": False, "needs": "confirmation that the person in the avatar agreed to it"}
    if not heygen.ready():
        _blocked(office, "mvideo", "AI presenter video needs HeyGen in Settings: " + ", ".join(heygen.missing()))
        return {"ok": False, "needs": ", ".join(heygen.missing())}
    words = " ".join([sc["hook_en"], *sc["lines_en"]])
    start = _pack(office, "mvideo", f"Recording an AI presenter for {ref} ({len(words.split())} words); {name(by)} confirmed the avatar's consent.")
    try:
        vid = await asyncio.to_thread(heygen.generate, words, title=f"{ref} reel")
        t0, url = 0.0, None
        while t0 < wait:
            st, url = await asyncio.to_thread(heygen.status, vid)
            if st == "completed" and url:
                break
            if st == "failed":
                raise heygen.HeyGenError("HeyGen could not make the video")
            await asyncio.sleep(poll)
            t0 += poll
        if not url:
            raise heygen.HeyGenError("HeyGen is still rendering; try again later")
        meta.MEDIA.mkdir(parents=True, exist_ok=True)
        n = 1 + sum(1 for e in office.log.list() if e["type"] == "footage.added")
        path = meta.MEDIA / f"footage-{ref}-{n}-ai.mp4"
        path.write_bytes(await asyncio.to_thread(heygen.download, url))
    except Exception as e:
        _blocked(office, "mvideo", f"AI video failed: {str(e)[:160]}", cause=start)
        return {"ok": False, "error": str(e)[:200]}
    office.log.append("footage.added", actor="mvideo", agent="mvideo", caused_by=start,
                      content={"id": f"F{n}", "ref": ref, "path": str(path), "served": f"/media/{path.name}", "source": "AI presenter (HeyGen)", "consent_by": by})
    _pack(office, "mvideo", f"AI presenter video ready for {ref}: handed to editing.", cause=start)
    await after_footage(office, ref)
    return {"ok": True, "footage": f"F{n}"}


def chain(office: Office, ref: str) -> list[dict]:
    """Where this listing's reel is now, step by step, and who has it: [{step, state (done|waiting|working|not yet), who}]."""
    from diwan.agents import approvers
    g = office.graph()
    open_ = [n for n in g.of("request", status="open") if ref in n.props.get("text", "")]
    pick = next((n for n in open_ if n.props.get("kind") == "use_script"), None)
    pub = next((n for n in open_ if n.props.get("agent") == "mpub"), None)
    sc, film, foot, cut = approved_script(office, ref), made(office, "film list", ref), footage(office, ref), made(office, "cut", ref)
    decided = next((e["actor"] for e in reversed(office.log.list()) if e["type"] == "decision.made" and e["content"].get("answer") == "approve"
                    and sc and e["content"].get("choice") == sc["id"]), None)
    steps = [{"step": "Pick a script", "state": "waiting" if pick else "done" if sc else "not yet",
              "who": approvers.label(office, "script") if pick or not sc else f"picked by {name(decided)}" if decided else "picked"},
             *([{"step": "Make the images", "state": "done" if made(office, "slides", ref) else "working", "who": "the studio's agents"}] if sc and sc.get("slides") else [
                 {"step": "Film it, or make the video", "state": "done" if foot else "waiting" if film else "not yet",
                  "who": (foot.get("source") or f"uploaded by {name(foot.get('by') or '')}".strip()) if foot else name(film["who"]) if film and film.get("who") else "nobody assigned yet"},
                 {"step": "Editing: take check, captions, cover", "state": "done" if cut else "working" if foot else "not yet", "who": "the studio's agents"}]),
             {"step": "Approve publishing", "state": "done" if made(office, "published", ref) or ref in scheduled(office) else "waiting" if pub else "not yet",
              "who": f"goes out {datetime.fromisoformat(scheduled(office)[ref]['at']).strftime('%a %I:%M %p').replace(' 0', ' ')}" if ref in scheduled(office) else approvers.label(office, "publish")}]
    return steps


def run_now(office: Office, ref: str) -> None:
    asyncio.run(run(office, ref, pause=0))


def script_request(office: Office, ref: str):
    return next((n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script" and ref in n.props["text"]), None)


def approve_script_now(office: Office, ref: str, by: str = "maya", choice: str | None = None) -> None:
    """For tests and the evaluation: a person picks a script from the open request, then the approved steps run."""
    n = script_request(office, ref)
    office.log.append("decision.made", actor=by, content={"card": n.id, "answer": "approve", "choice": choice})
    asyncio.run(after_script(office, ref, pause=0))
