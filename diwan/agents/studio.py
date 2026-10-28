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
import re
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

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
BANNED = r"\b(guaranteed?|risk.?free|assured returns?|best investment|will (double|rise)|100% (safe|return))\b"
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
    return [e["content"] for e in office.log.list() if e["type"] == "board.pinned"]


def footage(office: Office, ref: str) -> dict | None:
    return next((e["content"] for e in reversed(office.log.list()) if e["type"] == "footage.added" and e["content"]["ref"] == ref), None)


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


def _listing(office: Office, ref: str) -> dict:
    return office.graph().nodes[f"listing:{ref}"].props


def _ffmpeg(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError(r.stderr[-300:] or "ffmpeg failed")


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
CSV_TEMPLATE = ",".join(CSV_COLUMNS) + "\ncompetitor,brokerage.one,12000,https://www.instagram.com/p/XXXX/,REELS,\"What does 2M buy in Dubai Marina?\",950,40,2026-10-20 19:30\n"


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
                iso = (dt if dt.tzinfo else dt.replace(tzinfo=timezone(timedelta(hours=4)))).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
            url = (r.get("url") or "").strip()
            clean.append({"id": url or f"{acc}-{i}", "account": acc, "source": "own" if (r.get("source") or "").strip().lower() == "own" else "competitor",
                          "followers": int(float(r["followers"])) if (r.get("followers") or "").strip() else None, "permalink": url,
                          "type": (r.get("type") or "").strip().upper() or None, "caption": (r.get("caption") or "")[:600],
                          "likes": int(float(r.get("likes") or 0)), "comments": int(float(r.get("comments") or 0)), "at": iso})
        except (ValueError, KeyError) as e:
            errors.append(f"row {i}: {e}")
    by_acc: dict[str, list] = {}
    for p in clean:
        by_acc.setdefault((p["source"], p["account"]), []).append(p)
    outliers = []
    for (_, _acc), ps in by_acc.items():
        eng = [p["likes"] + p["comments"] for p in ps]
        med = statistics.median(eng) if len(eng) >= 5 else None
        for p, v in zip(ps, eng):
            p.update(engagement=v, score=round(v / med, 1) if med else None)
            office.log.append("post.seen", actor=by, agent="mrival", key=f"import:{p['id']}:{v}", content=p | {"imported": True})
            if p["source"] == "competitor" and p["score"] and p["score"] >= 2:
                outliers.append(p)
    outliers.sort(key=lambda p: -p["score"])
    for p in outliers[:3]:
        office.log.append("board.pinned", actor="mrival", agent="mrival", key=f"pin:{p['id']}",
                          content={"id": f"B-{abs(hash(p['id'])) % 10**8}", "kind": "outlier", "title": (p["caption"] or "(no caption)")[:90], "account": p["account"],
                                   "why": f"{p['score']}x @{p['account']}'s usual likes+comments", "url": p["permalink"], "post": p["id"], "type": p["type"]})
    comp = [p for p in clean if p["source"] == "competitor"]
    _pack(office, "mrival", f"Imported {len(clean)} posts ({len(comp)} from {len({p['account'] for p in comp})} competitors): {len(outliers)} outliers at 2x or more their account's usual."
          + (f" Skipped: {'; '.join(errors[:3])}" if errors else ""), kind="draft")
    return {"imported": len(clean), "outliers": len(outliers), "errors": errors}


# ---------- research ----------

def watch(office: Office, cause: int | None) -> list[dict]:
    """Competitor watch: score every competitor post against its own account's median; pin the outliers."""
    names = competitors(office.graph())
    if not instagram.ready():
        pinned = [b for b in board(office) if b["kind"] == "outlier"]
        if pinned:
            _pack(office, "mrival", f"Using imported posts: {len(pinned)} outliers pinned. Connect Instagram to fetch them automatically.", cause=cause)
            return [{"id": b["post"], "account": b["account"], "score": None, "permalink": b["url"], "type": b.get("type")} for b in pinned]
        _blocked(office, "mrival", "Connect Instagram in Settings, or import posts from a spreadsheet in the Studio", cause=cause)
        return []
    if not names:
        _blocked(office, "mrival", "Add competitor accounts in Settings → Content studio", cause=cause)
        return []
    outliers, errors = [], []
    for u in names:
        try:
            acc = instagram.competitor_posts(u)
        except instagram.InstagramError as e:
            errors.append(f"@{u}: {e}")
            continue
        eng = [p["likes"] + p["comments"] for p in acc["posts"]]
        med = statistics.median(eng) if len(eng) >= 5 else None
        for p, v in zip(acc["posts"], eng):
            score = round(v / med, 1) if med else None
            office.log.append("post.seen", actor="mrival", agent="mrival", key=f"post:{p['id']}:{v}",
                              content={**p, "source": "competitor", "engagement": v, "score": score, "followers": acc.get("followers")})
            if score and score >= 2:
                outliers.append({**p, "score": score, "engagement": v})
    outliers.sort(key=lambda p: -p["score"])
    try:
        for p in instagram.own_posts():
            office.log.append("post.seen", actor="mrival", agent="mrival", key=f"own:{p['id']}:{p['likes']}:{p['comments']}",
                              content={**p, "source": "own", "engagement": p["likes"] + p["comments"]})
    except instagram.InstagramError as e:
        errors.append(f"our account: {e}")
    top = outliers[:3]
    for p in top:
        office.log.append("board.pinned", actor="mrival", agent="mrival", key=f"pin:{p['id']}",
                          content={"id": f"B-{p['id']}", "kind": "outlier", "title": (p["caption"] or "(no caption)")[:90], "account": p["account"],
                                   "why": f"{p['score']}x @{p['account']}'s usual likes+comments", "url": p["permalink"], "post": p["id"], "media_url": p.get("media_url"),
                                   "type": p.get("type")})
    verdict = (f"{len(outliers)} outliers across {len(names)} accounts. Top: @{top[0]['account']} at {top[0]['score']}x their usual." if top
               else f"No post above 2x its account's usual across {len(names)} accounts.")
    _pack(office, "mrival", verdict + (f" Not reached: {'; '.join(errors)}" if errors else ""), cause=cause,
          evidence=[Evidence(p["permalink"], f"post:{p['id']}") for p in top if p.get("permalink")],
          sources={f"post:{p['id']}": p["permalink"] for p in top if p.get("permalink")})
    return top


def trends(office: Office, cause: int | None) -> list[dict]:
    if not meta.ready():
        _blocked(office, "mtrend", "Trend research needs Muse Spark web search (META_API_KEY)", cause=cause)
        return []
    try:
        r = meta.search("What short-form video formats and hooks are performing for Dubai real-estate brokers on Instagram and TikTok "
                        "in the last month? Give three, one line each, each with the source you saw it in.")
    except meta.MetaError as e:
        _blocked(office, "mtrend", f"Web search failed: {e}", cause=cause)
        return []
    cited = [c for c in r["cited"] if c.get("url")] or [s for s in r["sources"] if s.get("url")][:3]
    if not cited:
        _blocked(office, "mtrend", "Web search returned no sources, so nothing is pinned", cause=cause)
        return []
    lines = [ln.strip("-• ").strip() for ln in r["text"].splitlines() if ln.strip()][:3]
    cards = []
    for i, src in enumerate(cited[:3]):
        c = {"id": f"B-trend-{abs(hash(src['url'])) % 10**8}", "kind": "trend", "title": (lines[i] if i < len(lines) else src.get("title") or "")[:120],
             "why": src.get("title") or "", "url": src["url"]}
        office.log.append("board.pinned", actor="mtrend", agent="mtrend", key=f"pin:{c['id']}", content=c)
        cards.append(c)
    _pack(office, "mtrend", f"{len(cards)} rising formats pinned, each with its source.", cause=cause,
          evidence=[Evidence(c["url"], c["id"]) for c in cards], sources={c["id"]: c["url"] for c in cards}, usage={"queries": r["queries"]})
    return cards


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

IDEAS_SCHEMA = {"name": "ideas", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["ideas"],
                "properties": {"ideas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                                    "required": ["title", "angle", "cards"],
                                                                    "properties": {"title": {"type": "string"}, "angle": {"type": "string"},
                                                                                   "cards": {"type": "array", "items": {"type": "string"}}}}}}}}


def ideas(office: Office, ref: str, cards: list[dict], cause: int | None, feedback: str | None = None) -> dict:
    lst = _listing(office, ref)
    ids = {c["id"] for c in cards}
    c = get("midea")
    system = runner.instructions(c, office.log)
    user = runner.user_message(f"Three short-video ideas for listing {ref}. Each idea names the listing and the card ids it builds on (or none)."
                               + (f"\n\n{feedback}" if feedback else ""),
                               {f"listing:{ref}": office.graph().record(f"listing:{ref}"), **{x["id"]: f"{x['title']} ({x['why']})" for x in cards}})
    out, by = [], "rules"
    if runner.has_model(c, system, user, schema=IDEAS_SCHEMA):
        try:
            out = runner.call(c, system, user, schema=IDEAS_SCHEMA).data["ideas"]
            out = [i | {"cards": [x for x in i["cards"] if x in ids]} for i in out]  # a card the model invented is dropped
            by = "muse-spark"
        except Exception as e:
            _blocked(office, "midea", f"Muse Spark failed, using plain ideas: {str(e)[:120]}", cause=cause)
    if not out:
        feats = ", ".join(lst.get("features") or []) or f"{lst['beds']} bed {lst['type']}"
        out = [{"title": f"{lst['title']}: {feats}, price at the end", "angle": "walk-through ending on the price", "cards": []}]
        out += [{"title": f"{lst['title']} in the structure of @{x.get('account', 'a source')}'s {x['kind']}", "angle": x["title"], "cards": [x["id"]]} for x in cards[:2]]
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


def film_list(office: Office, ref: str, idea: dict, cause: int | None, feedback: str | None = None) -> dict:
    g = office.graph()
    lst = _listing(office, ref)
    feats = lst.get("features") or []
    shots = [f"Open on the strongest view{(': ' + feats[0]) if feats else ''}"] + [f"Show the {f}" for f in feats[1:3]] + \
            [f"Walk the {lst['beds']} bedroom{'s' if lst['beds'] != 1 else ''}", "End on the price card with the permit number"]
    viewing = next((v for v in g.of("viewing", status="booked") if v.props["listing"] == ref), None)
    when = f"at the viewing {g.record(viewing.id).split(', ', 1)[1]}" if viewing else "at the next daylight visit (no viewing booked yet)"
    broker = viewing.props["broker"] if viewing else "omar"
    m = _made(office, "mfilm", "film list", ref, {"shots": shots, "who": broker, "when": when}, cause)
    _pack(office, "mfilm", f"Film list for {name(broker)} {when}: {len(shots)} shots, ending on the price and permit.", cause=cause)
    return m


# ---------- scripting ----------

SCRIPT_SCHEMA = {"name": "script", "strict": True, "schema": {"type": "object", "additionalProperties": False,
                 "required": ["hook_en", "hook_ar", "lines_en", "lines_ar"],
                 "properties": {"hook_en": {"type": "string"}, "hook_ar": {"type": "string"},
                                "lines_en": {"type": "array", "items": {"type": "string"}}, "lines_ar": {"type": "array", "items": {"type": "string"}}}}}


MONEY = re.compile(r"(?:aed|dhs?|dirhams?|درهم)\s*[\d.,]+(?:\s*(?:k|m|mn|million|thousand))?|[\d.,]+\s*(?:k|m|mn|million|thousand|aed|dirhams?|درهم)\b"
                   r"|(?:one|two|three|four|five|six|seven|eight|nine|ten|[a-z-]+ty)(?:[ -][a-z]+)*\s+(?:million|thousand)", re.I)


def _amounts(text: str) -> set[int]:
    """Money in the text: only amounts said as money (AED, dirhams, million, thousand), not unit or permit numbers."""
    from diwan.agents import scribe
    return {int(a) for m in MONEY.finditer(text) for a in scribe.amounts(m.group(0))}


def script(office: Office, ref: str, idea: dict, hook_card: dict | None, cause: int | None, feedback: str | None = None) -> dict:
    lst = _listing(office, ref)
    rec = office.graph().record(f"listing:{ref}")
    c = get("mscript")
    system = runner.instructions(c, office.log) + "\nWrite in the `script` format. Only facts and amounts from the listing. 30 seconds, 5 to 7 lines."
    user = runner.user_message(f"Script for: {idea['pick']['title']}. Borrow the structure, never the words, of the hook card if given."
                               + (f"\n\n{feedback}" if feedback else ""),
                               {f"listing:{ref}": rec, **({"hook": hook_card["hook"]} if hook_card else {})})
    data, by = None, "template"
    if runner.has_model(c, system, user, schema=SCRIPT_SCHEMA):
        try:
            data = runner.call(c, system, user, schema=SCRIPT_SCHEMA).data
            by = "muse-spark"
            stray = (_amounts(" ".join([data["hook_en"], *data["lines_en"]])) - _amounts(rec)) - {0}
            if stray:
                _blocked(office, "mscript", f"Muse Spark's script named amounts not on the listing ({', '.join(f'{a:,}' for a in stray)}); using the template", cause=cause)
                data, by = None, "template"
        except Exception as e:
            _blocked(office, "mscript", f"Muse Spark failed, using the template: {str(e)[:120]}", cause=cause)
    if not data:
        price = f"AED {lst['price_aed']:,}"
        feats = lst.get("features") or []
        data = {"hook_en": f"What does {price} buy in {lst['community']}?",
                "hook_ar": f"ماذا تشتري {lst['price_aed']:,} درهم في {lst['community']}؟",
                "lines_en": [f"This is {lst['title']}.", *[f"{f[:1].upper()}{f[1:]}." for f in feats[:3]],
                             f"{lst['beds']} bedroom {lst['type']}.", f"{price}. Permit {lst.get('permit')}.", "Message us to book a viewing."],
                "lines_ar": []}
    m = _made(office, "mscript", "script", ref, data | {"via": by}, cause)
    _pack(office, "mscript", f"Hook: \"{data['hook_en']}\" / \"{data['hook_ar']}\" · {len(data['lines_en'])} lines ({by}).", cause=cause, usage={"provider": by})
    return m


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

def _srt(turns: list[dict], text: str, dur: float) -> str:
    rows = [t for t in turns if t.get("start") is not None and t.get("end") is not None]
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
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(f, max(18, width // 20))
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
    if check and check["said"].strip():
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
    w = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width", "-of", "csv=p=0", str(src)],
                           capture_output=True, text=True).stdout.strip() or 720)
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
    base = f"{sc['hook_en']}\n\n{lst['title']}, {lst['community']} · {lst['beds']} bed {lst['type']} · AED {lst['price_aed']:,}\nPermit {lst.get('permit')}"
    ar = f"\n\n{sc['hook_ar']}" if sc.get("hook_ar") else ""
    tags = " #DubaiRealEstate #" + re.sub(r"\W", "", lst["community"])
    m = _made(office, "mwriter", "post text", ref, {"text": base + ar + tags}, cause)
    _pack(office, "mwriter", f"Post text ready with permit {lst.get('permit')} ({len(m['text'])} characters).", cause=cause,
          evidence=[Evidence(str(lst.get("permit")), f"listing:{ref}")], sources={f"listing:{ref}": office.graph().record(f"listing:{ref}")})
    return m


# ---------- publishing ----------

def cover(office: Office, ref: str, sc: dict, cause: int | None) -> dict | None:
    f = footage(office, ref)
    out = {}
    if f:
        src = Path(f["path"])
        meta.MEDIA.mkdir(parents=True, exist_ok=True)
        frame = meta.MEDIA / f"frame-{ref}-{f['id']}.jpg"
        try:
            _ffmpeg("-ss", f"{max(0.5, _duration(src) * .3):.1f}", "-i", str(src), "-frames:v", "1", str(frame))
            out["frame"] = f"/media/{frame.name}"
        except Exception:
            pass
    if meta.ready():
        lst = _listing(office, ref)
        try:
            out["generated"] = meta.image(f"Vertical cover for a property reel: {lst['title']} in {lst['community']}, {', '.join(lst.get('features') or [])}. "
                                          f"Clean, bright, real-estate photography style, space at the top for the words \"{sc['hook_en']}\". No people, no text.",
                                          f"cover-{ref}")
        except meta.MetaError as e:
            _blocked(office, "mthumb", f"Muse Image failed: {e}", cause=cause)
    if not out:
        _blocked(office, "mthumb", "A cover needs footage (a frame) or Muse Image (META_API_KEY)", cause=cause)
        return None
    m = _made(office, "mthumb", "cover", ref, out, cause)
    _pack(office, "mthumb", f"{len(out)} cover option{'s' if len(out) > 1 else ''}: {', '.join(out)}.", cause=cause)
    return m


def permit_check(office: Office, ref: str, text: dict, cause: int | None, findings: list | None = None) -> bool:
    lst = _listing(office, ref)
    t = text["text"]
    fails = []
    if not lst.get("permit") or lst["permit"] not in t:
        fails.append("permit number missing")
    stray = _amounts(t) - {lst["price_aed"]} - {0}
    if stray:
        fails.append(f"amounts not on the listing: {', '.join(f'{a:,}' for a in stray)}")
    if m := re.search(BANNED, t, re.I):
        fails.append(f"banned promise \"{m.group(0)}\"")
    _pack(office, "mpermit", f"Pass: permit {lst['permit']}, price matches {ref}, no banned promises." if not fails else "Held: " + "; ".join(fails) + ".",
          cause=cause, kind=None if not fails else "hold")
    if findings is not None:
        findings.extend(fails)
    return not fails


def schedule(office: Office, cause: int | None) -> dict:
    ours = [p for p in posts(office, "own") if p.get("at")]
    if len(ours) >= 5:
        by_hour: dict[int, list[int]] = {}
        for p in ours:
            hr = (datetime.fromisoformat(p["at"].replace("+0000", "+00:00")) + timedelta(hours=4)).hour
            by_hour.setdefault(hr, []).append(p["engagement"])
        hour = max(by_hour, key=lambda k: statistics.mean(by_hour[k]))
        why = f"our posts at {hour}:00 Dubai did best ({len(ours)} posts)"
    else:
        hour, why = 19, f"not enough history ({len(ours)} posts), so the evening default"
    now = datetime.now(timezone(timedelta(hours=4)))
    when = (now + timedelta(days=1)).replace(hour=hour, minute=30, second=0, microsecond=0)
    m = _made(office, "msched", "slot", "next", {"at": when.isoformat(), "why": why}, cause)
    _pack(office, "msched", f"Slot: {when.strftime('%A %I:%M %p').replace(' 0', ' ')}, because {why}.", cause=cause)
    return m


def cross(office: Office, ref: str, text: dict, cause: int | None) -> dict:
    t = text["text"]
    versions = {p: (t if len(t) <= n else t[:n - 1] + "…") for p, n in LIMITS.items()}
    versions["YouTube Shorts"] = t.split("\n")[0][:100]
    m = _made(office, "mcross", "versions", ref, {"versions": versions}, cause)
    _pack(office, "mcross", f"Versions for {', '.join(versions)}, each within its limit.", cause=cause)
    return m


def ask_to_publish(office: Office, ref: str, cut: dict | None, text: dict, slot: dict, cause: int | None) -> int:
    """One open publish request per listing: an older one is answered as replaced before the new one is asked."""
    for n in office.graph().of("request", status="open"):
        if n.props.get("agent") == "mpub" and ref in n.props.get("text", ""):
            office.log.append("decision.made", actor="mpub", agent="mpub", content={"card": n.id, "answer": "replaced by a newer request"})
    what = f"Publish the {ref} reel {datetime.fromisoformat(slot['at']).strftime('%a %I:%M %p').replace(' 0', ' ')}" + ("" if cut else " (no cut yet: footage needed)")
    _pack(office, "mpub", what, cause=cause, kind="publish")
    return 0


def publish(office: Office, ref: str, *, by: str) -> dict:
    """After the owner approves: post to Instagram when everything needed is there; otherwise say what is missing."""
    cut, text = made(office, "cut", ref), made(office, "post text", ref)
    base = env("PUBLIC_BASE_URL")
    needs = [x for x, ok in (("the captioned cut (upload footage)", cut), ("post text", text), ("Instagram connected", instagram.ready()),
                             ("PUBLIC_BASE_URL (a public https address for the video)", base)) if not ok]
    if needs:
        _pack(office, "mpub", f"Approved by {name(by)}; not posted yet. Needs: {', '.join(needs)}.", kind=None)
        return {"ok": False, "needs": needs}
    try:
        pid = instagram.publish_reel(f"{base.rstrip('/')}{cut['served']}", text["text"])
    except instagram.InstagramError as e:
        _pack(office, "mpub", f"Instagram refused the post: {e}", kind=None)
        return {"ok": False, "error": str(e)}
    _made(office, "mpub", "published", ref, {"instagram_id": pid, "approved_by": by}, None)
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

async def run(office: Office, ref: str, pause: float = .6) -> None:
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    lst = _listing(office, ref)
    start = _pack(office, "mkt", f"New reel for {lst['title']} ({ref}): permit {lst.get('permit') or 'MISSING'}.", kind="assign")
    if not lst.get("permit"):
        _blocked(office, "mkt", f"{ref} has no permit number: nothing is made for it", cause=start)
        return
    top = await step(watch, office, start); await asyncio.sleep(pause)
    tr_cards = await step(trends, office, start); await asyncio.sleep(pause)
    tr = await step(transcript_of, office, top[0] | {"post": top[0]["id"]} if top else None, start); await asyncio.sleep(pause)
    pins = board(office)
    _pack(office, "research", f"Board: {len(pins)} card{'s' if len(pins) != 1 else ''} pinned, each with its source." if pins else "Board empty: see what research is waiting for.",
          cause=start, kind="assign")
    idea = await step(reviewed, office, "ideas", ref, lambda fb: ideas(office, ref, pins, start, fb), start); await asyncio.sleep(pause)
    if not idea:
        return
    await step(lanes, office, start); await asyncio.sleep(pause)
    sc = await step(reviewed, office, "script", ref, lambda fb: script(office, ref, idea, tr, start, fb), start); await asyncio.sleep(pause)
    if not sc:
        return
    await step(playbook, office, start)
    ask_script_approval(office, ref, sc, start)  # nothing that costs filming, editing or model time starts before a person says yes


def ask_script_approval(office: Office, ref: str, sc: dict, cause: int | None) -> None:
    """The Copywriter asks the Marketing manager to approve the script. An older open request for this listing is replaced."""
    for n in office.graph().of("request", status="open"):
        if n.props.get("kind") == "use_script" and ref in n.props.get("text", ""):
            office.log.append("decision.made", actor="mcopy", agent="mcopy", content={"card": n.id, "answer": "replaced by a newer draft"})
    _pack(office, "mcopy", f"Use script {sc['id']} for {ref}: \"{sc['hook_en']}\" ({len(sc['lines_en'])} lines, checked by the Copywriter)",
          cause=cause, kind="use_script")


def approved_script(office: Office, ref: str) -> dict | None:
    """The script a person approved for filming, if any."""
    g = office.graph()
    for e in reversed(office.log.list()):
        if e["type"] == "decision.made" and e["content"].get("answer") == "approve":
            n = g.nodes.get(e["content"]["card"])
            if n and n.props.get("kind") == "use_script" and ref in n.props.get("text", ""):
                sid = re.search(r"script (C\d+)", n.props["text"])
                return next((x["content"] for x in office.log.list() if x["type"] == "content.made" and sid and x["content"]["id"] == sid.group(1)), None)
    return None


async def after_script(office: Office, ref: str, pause: float = .6) -> None:
    """The script is approved: the broker gets the film list, the post text is written. Editing waits for footage."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    sc = approved_script(office, ref)
    if not sc:
        return
    idea = made(office, "ideas", ref)
    start = _pack(office, "mkt", f"Script {sc['id']} for {ref} approved: filming can start.", kind="assign")
    film = await step(reviewed, office, "film list", ref, lambda fb: film_list(office, ref, idea, start, fb), start); await asyncio.sleep(pause)
    if film:
        office.add_task(None, "mfilm", f"Film {ref}: " + "; ".join(film["shots"]) + f" ({film['when']})", needs_person=film["who"], by="mfilm", caused_by=start)
    await step(reviewed, office, "post text", ref, lambda fb: post_text(office, ref, sc, start, fb), start)


async def script_rejected(office: Office, ref: str, note: str, pause: float = .6) -> None:
    """A person sent the script back: the note goes to the Script writer, the new draft is checked and asked again."""
    step = lambda fn, *a: asyncio.to_thread(fn, *a)  # noqa: E731
    idea, tr = made(office, "ideas", ref), made(office, "transcript")
    start = _pack(office, "mcopy", f"Script for {ref} sent back by the Marketing manager: {note or 'no reason given'}", kind="assign")
    fb = f"The Marketing manager sent your script back: {note}" if note else None
    sc = await step(reviewed, office, "script", ref, lambda f: script(office, ref, idea, tr, start, "\n".join(x for x in (fb, f) if x) or None), start)
    if sc:
        ask_script_approval(office, ref, sc, start)


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
    text = made(office, "post text", ref) or await step(post_text, office, ref, sc, start)
    await step(cover, office, ref, sc, start); await asyncio.sleep(pause)
    await step(remix, office, ref, made(office, "transcript"), made(office, "film list", ref) or {"shots": ["our own shots"]}, start)
    ok, sc, text = await step(permit_gate, office, ref, sc, text, start)
    if ok:
        await step(reviewed, office, "versions", ref, lambda fb: cross(office, ref, text, start), start)
        slot = made(office, "slot", "next") or await step(schedule, office, start)
        await step(ask_to_publish, office, ref, cut, text, slot, start)


def run_now(office: Office, ref: str) -> None:
    asyncio.run(run(office, ref, pause=0))


def approve_script_now(office: Office, ref: str, by: str = "maya") -> None:
    """For tests and the evaluation: a person approves the open script request, then the approved steps run."""
    n = next(n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script" and ref in n.props["text"])
    office.log.append("decision.made", actor=by, content={"card": n.id, "answer": "approve"})
    asyncio.run(after_script(office, ref, pause=0))
