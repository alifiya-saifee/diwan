"""The Marketing room's own loop, around the studio that makes the content. See docs/marketing-complete-spec.md.

  stages     one stage per piece of content, folded from the log: idea, briefed, scripted, in_production, ready,
             scheduled, live, paused, withdrawn, archived
  the facts  a post rests on what its listing said. When that changes, the piece is paused or withdrawn, whatever stage it is in
  tracing    every post carries a code word; a lead that says it, or comments on the post, is attributed to it
  results    leads, qualified, viewings, deals and commission per post, not only likes
  the day    a morning list, an end-of-day list, and each Monday what brought deals
  campaigns  a person launches and pays; Diwan drafts, caps, and flags what costs too much

Marketing reads the log and never calls into Sales or Finance.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from diwan import business
from diwan.agents import approvers, rhythm, studio
from diwan.office import Office
from diwan.providers import ads

STAGES = ("idea", "briefed", "scripted", "in_production", "ready", "scheduled", "live", "paused", "withdrawn", "archived")
LABELS = {"idea": "Idea", "briefed": "Briefed", "scripted": "Scripts waiting", "in_production": "In production", "ready": "Ready", "scheduled": "Scheduled",
          "live": "Live", "paused": "Paused", "withdrawn": "Withdrawn", "archived": "Archived"}
FINAL = ("withdrawn", "archived")
GONE = ("sold", "let", "withdrawn", "retired", "off-market")
MAKING = ("film list", "slides", "cut")
GENERIC = {"unit", "apartment", "villa", "townhouse", "flat", "dubai", "with", "this", "that", "from", "meet", "post"}


def person(office: Office) -> str:
    """Who hears about Marketing's work: the person who approves publishing, else the owner."""
    from diwan import access
    return approvers.get(office)["publish"] or access.owner_id()


def _today(office: Office, now: datetime | None = None) -> date:
    return business.local(now or datetime.now(timezone.utc), office).date()


def _once(office: Office, key: str, **content) -> bool:
    """True the first time this key is seen: what stops a daily list going out every minute."""
    return not office.log.append("content.made", actor="mkt", agent="mkt", key=key, content={"id": key, "kind": "reminder", **content}).get("duplicate")


# ---------- stages ----------

def pieces(office: Office) -> dict[str, dict]:
    """{ref: its latest piece of content}. A new idea for the same subject starts a new piece."""
    out: dict[str, dict] = {}
    for e in office.log.list():
        t, c = e["type"], e["content"]
        ref = c.get("ref")
        if not ref:
            continue
        if t == "content.idea":
            out[ref] = {"ref": ref, "stage": "idea", "since": e["at"], "title": c.get("title", ""), "why": ""}
        p = out.get(ref)
        if not p:
            continue
        if t == "content.briefed":
            p.update(stage="briefed", since=e["at"])
        elif t == "content.scripted":
            p.update(stage="scripted", since=e["at"], why="")
        elif t == "content.made" and c.get("kind") in MAKING and p["stage"] in ("briefed", "scripted"):
            p.update(stage="in_production", since=e["at"])
        elif t == "content.made" and c.get("kind") == "unscheduled" and p["stage"] == "scheduled":
            p.update(stage="ready", since=e["at"], why=c.get("why", ""))
        elif t == "content.ready":
            p.update(stage="ready", since=e["at"], why="")
        elif t == "post.approved":
            p.update(stage="scheduled", since=e["at"], at=c.get("at"), why="")
        elif t == "post.live":
            p.update(stage="live", since=e["at"], instagram_id=c.get("instagram_id"), why="")
        elif t == "post.paused":
            p.update(stage="paused", since=e["at"], was=c.get("was"), why=c.get("why", ""))
        elif t == "post.withdrawn":
            p.update(stage="archived" if c.get("archived") else "withdrawn", since=e["at"], why=c.get("why", ""))
    return out


def _mark(office: Office, type_: str, ref: str, **content) -> None:
    office.log.append(type_, actor=content.pop("by", "mkt"), agent="mkt", content={"ref": ref, **content})


# ---------- posts follow the facts ----------

def _subject(office: Office, ref: str | None) -> dict | None:
    if not ref:  # a planned day with nothing on it
        return None
    try:
        return studio._listing(office, ref)
    except KeyError:
        return None


def check(office: Office, ref: str, now: datetime | None = None) -> tuple[str, list[str]]:
    """("ok", []), ("pause", reasons) or ("gone", reasons), from what the subject says today."""
    lst = _subject(office, ref)
    if lst is None:
        return "gone", ["it no longer exists, or its moment has passed"]
    if lst["item"] == "listing" and lst.get("status") in GONE:
        return "gone", [f"the listing is {lst['status']}"]
    why = []
    sc = studio.approved_script(office, ref) or studio.made(office, "script", ref)
    if sc:
        why += studio.stale(office, sc)
    if lst["item"] != "topic" and business.permit_needed(office) and not lst.get("permit"):
        why.append("It has no permit number.")
    until = lst.get("permit_until")
    if until and until < _today(office, now).isoformat():
        why.append(f"Its permit expired on {until}.")
    return ("pause", why) if why else ("ok", [])


def blocked(office: Office, ref: str) -> list[str]:
    """Why this post may not go out now; asked again at the moment of publishing."""
    return check(office, ref)[1]


def _close_cards(office: Office, ref: str, why: str) -> None:
    for n in office.graph().of("request", status="open"):
        if n.props.get("kind") in ("publish", "use_script", "approve_brief") and ref in n.props.get("text", ""):
            office.log.append("decision.made", actor="mkt", agent="mkt", content={"card": n.id, "answer": f"closed: {why}"})
    for n in office.graph().of("decision", status="open"):  # the question raised when its checks failed three times
        if ref in (n.props.get("refs") or []):
            office.log.append("decision.made", actor="mkt", agent="mkt", content={"card": n.id, "answer": f"closed: {why}"})


def _take_down(office: Office, ref: str, why: str) -> None:
    office.add_task(None, "mpub", f"Take the {ref} post down on Instagram: {why} Instagram does not let Diwan delete a post.", needs_person=person(office), by="mkt")


def pause(office: Office, ref: str, why: str) -> None:
    p = pieces(office).get(ref) or {}
    if ref in studio.scheduled(office):
        studio.unschedule(office, ref, by="mkt", why=why)
    _close_cards(office, ref, why)
    _mark(office, "post.paused", ref, why=why, was=p.get("stage"))
    from diwan import leads
    leads.notify(office, person(office), f"{ref} is paused: {why}", kind="info")
    if p.get("stage") == "live":
        _take_down(office, ref, why)
    studio._pack(office, "mpub", f"{ref} paused: {why}", kind=None)


def withdraw(office: Office, ref: str, why: str, *, archived: bool = False) -> None:
    p = pieces(office).get(ref) or {}
    if ref in studio.scheduled(office):
        studio.unschedule(office, ref, by="mkt", why=why)
    _close_cards(office, ref, why)
    _mark(office, "post.withdrawn", ref, why=why, archived=archived)
    if archived:
        return
    _clear(office, ref, why)
    rhythm.take_off(office, ref, by="mkt")
    from diwan import leads
    leads.notify(office, person(office), f"{ref} is withdrawn: {why}", kind="info")
    if p.get("stage") == "live" or p.get("was") == "live":
        _take_down(office, ref, why)
    studio._pack(office, "mpub", f"{ref} withdrawn: {why}", kind=None)


def _clear(office: Office, ref: str, why: str) -> None:
    """Nobody films, or answers for, a post that was stopped."""
    for t in office.graph().of("task", status="queued"):
        if t.props.get("agent") == "mshoot" and ref in t.props.get("action", ""):
            office.log.append("task.withdrawn", actor="mkt", agent="mkt", content={"id": t.id, "reason": why})
    _close_cards(office, ref, why)


def _resume(office: Office, ref: str, p: dict) -> None:
    """The problem went away (a permit renewed, a price put back): back where it was, and a person approves again."""
    was = p.get("was")
    if was == "live":
        _mark(office, "post.live", ref, instagram_id=p.get("instagram_id"), back=True)
        return
    sc = studio.approved_script(office, ref)
    media = (studio.made(office, "slides", ref) if sc and sc.get("slides") else studio.made(office, "cut", ref)) if sc else None
    text = studio.made(office, "post text", ref)
    if not (media and text):
        _mark(office, "content.scripted", ref)
        return
    slot = studio.schedule(office, None)
    word = sc["format"] if sc.get("slides") else "reel"
    studio.ask_to_publish(office, ref, media, text, slot, None, word)


def watch(office: Office, now: datetime | None = None) -> list[str]:
    """Every piece that is not finished, checked against the facts. Returns the refs that moved."""
    moved = []
    today = _today(office, now)
    days = int(rhythm.settings(office)["archive_days"])
    for ref, p in pieces(office).items():
        if p["stage"] == "withdrawn":
            _clear(office, ref, p.get("why") or "it was stopped")  # also what a post stopped before this was built left behind
        if p["stage"] in FINAL or p["stage"] in ("idea", "briefed"):
            continue
        state, why = check(office, ref, now)
        if state == "gone":
            withdraw(office, ref, " ".join(why))
            moved.append(ref)
        elif state == "pause" and p["stage"] != "paused":
            pause(office, ref, " ".join(why))
            moved.append(ref)
        elif state == "ok" and p["stage"] == "paused":
            _resume(office, ref, p)
            moved.append(ref)
        elif p["stage"] == "live" and days and (today - date.fromisoformat(p["since"][:10])).days >= days:
            withdraw(office, ref, f"archived after {days} days", archived=True)
    _permits(office, today)
    return moved


def _permits(office: Office, today: date) -> None:
    from diwan import leads
    for n in office.graph().of("listing"):
        until = n.props.get("permit_until")
        if not until or n.status in GONE:
            continue
        left = (date.fromisoformat(until) - today).days
        for mark in (14, 3):
            if 0 <= left <= mark and _once(office, f"permit:{n.props['ref']}:{until}:{mark}"):
                who = n.props.get("agent") or person(office)
                leads.notify(office, who, f"The permit for {n.props['ref']} expires on {until}: renew it, or its posts pause that day.", kind="info")


def waiting_ideas(office: Office, days: int = 14, now: datetime | None = None) -> list[dict]:
    """What is worth a post: new listings nobody has made anything for, and pieces stopped by a change. Suggestions only:
    nothing is written or paid for until a person presses."""
    today = _today(office, now)
    have = pieces(office)
    out = []
    first: dict[str, tuple[str, int]] = {}
    begun = None  # listings that were already here when the business was set up are not news
    for e in office.log.list():
        if e["type"] == "listing.added":
            first.setdefault(e["content"].get("ref"), (e["at"][:10], e["id"]))
        elif begun is None and e["type"] == "setting.changed" and e["content"].get("person") == "business":
            begun = e["id"]
    for n in office.graph().of("listing"):
        ref = n.props["ref"]
        at, eid = first.get(ref, ("", 0))
        fresh = begun is not None and eid > begun and at and (today - date.fromisoformat(at)).days <= days
        if fresh and ref not in have and n.status == "available" and (n.props.get("permit") or not business.permit_needed(office)):
            out.append({"ref": ref, "title": n.props.get("title"), "why": f"new listing, added {at}"})
    out = out[-5:]
    for ref, p in have.items():
        if p["stage"] == "paused":
            out.append({"ref": ref, "title": p.get("title") or ref, "why": p["why"]})
    return out


# ---------- tracing ----------

def codes(office: Office) -> dict[str, str]:
    """{ref: its code word}."""
    return {e["content"]["ref"]: e["content"]["code"] for e in office.log.list() if e["type"] == "content.made" and e["content"].get("kind") == "post text" and e["content"].get("code")}


def code_for(office: Office, ref: str) -> str:
    """A short word a person can say back: from the subject's name, and never another post's."""
    have = codes(office)
    if ref in have:
        return have[ref]
    lst = _subject(office, ref) or {"title": ref}
    from diwan import brand
    skip = GENERIC | {w.lower() for w in re.findall(r"[A-Za-z]+", brand.profile(office)["name"]["value"])}
    # the most distinctive word: the one used least across all our subjects' names and places ("Brand New" is on many listings, "Dahlias" on one)
    words = lambda x: re.findall(r"[A-Za-z]{4,}", f"{x.get('community') or ''} {x.get('title') or ''}")  # noqa: E731
    from diwan import topics
    every = [n.props for n in office.graph().of("listing")] + list(topics.items(office).values())
    seen = Counter(w.lower() for r in every for w in set(words(r)))
    mine = [w for w in words(lst) if w.lower() not in skip]
    word = (min(mine, key=lambda w: (seen[w.lower()], mine.index(w))) if mine else "HELLO").upper()
    taken = set(have.values())
    code, n = word, 1
    while code in taken:
        n += 1
        code = f"{word}{n}"
    return code


def _attribute(office: Office, deal: str, ref: str | None, via: str, *, post: str | None = None, code: str | None = None) -> None:
    sc = studio.approved_script(office, ref, past=True) if ref else None
    office.log.append("lead.attributed", actor="mkt", agent="mkt", deal=deal, key=f"attr:{deal}",
                      content={"ref": ref, "via": via, "post": post, "code": code, "angle": (sc or {}).get("angle")})


def comment(office: Office, chat: str, media_id: str | None) -> None:
    """A comment names its post: the lead came from it."""
    if not media_id:
        return
    n = office.graph().nodes.get(f"chat:{chat}")
    deal = n.deal if n else None
    if not deal:
        return
    ref = next((r for r, p in pieces(office).items() if p.get("instagram_id") == media_id), None)
    _attribute(office, deal, ref, "comment", post=media_id)


def attribute(office: Office) -> int:
    """Read what arrived, and trace what can be traced: a code word, or a portal enquiry on a listing. The first source wins."""
    done = {e["deal"] for e in office.log.list() if e["type"] == "lead.attributed"}
    words = {c: r for r, c in codes(office).items()}
    n = 0
    for e in office.log.list():
        if e["type"] != "chat.received" or not e["deal"] or e["deal"] in done:
            continue
        c = e["content"]
        said = set(re.findall(r"[A-Z0-9]{4,}", (c.get("text") or "").upper()))
        code = next((w for w in words if w in said), None)
        if code:
            _attribute(office, e["deal"], words[code], "code word", code=code)
        elif c.get("ref") and c.get("channel") not in (None, "whatsapp", "instagram"):
            _attribute(office, e["deal"], c["ref"], f"portal: {c['channel']}")
        else:
            continue
        done.add(e["deal"])
        n += 1
    return n


# ---------- results ----------

def _attributions(office: Office) -> list[dict]:
    return [{"deal": e["deal"], "at": e["at"], **e["content"]} for e in office.log.list() if e["type"] == "lead.attributed"]


def results(office: Office) -> list[dict]:
    """Per post: what it brought, then how it did. Sorted by deals, then leads."""
    log = office.log.list()
    qualified = {e["deal"] for e in log if e["type"] == "qualify.passed"}
    viewed = {e["deal"] for e in log if e["type"] == "appointment.booked"}
    sold = {e["deal"]: e["content"].get("commission_aed") or 0 for e in log if e["type"] == "sale.closed" and e["deal"]}
    seen = {p.get("id"): p for p in studio.posts(office, "own")}
    have = pieces(office)
    leads_by: dict[str, list[str]] = {}
    for a in _attributions(office):
        leads_by.setdefault(a["ref"] or a.get("post") or "unknown post", []).append(a["deal"])
    out = []
    for ref in {*leads_by, *(r for r, p in have.items() if p.get("instagram_id"))}:
        p = have.get(ref, {})
        deals = leads_by.get(ref, [])
        post = seen.get(p.get("instagram_id"), {})
        sc = studio.approved_script(office, ref, past=True) or {}
        out.append({"ref": ref, "title": (_subject(office, ref) or {}).get("title") or p.get("title") or ref, "stage": p.get("stage"), "angle": sc.get("angle"),
                    "leads": len(deals), "qualified": sum(d in qualified for d in deals), "viewings": sum(d in viewed for d in deals),
                    "deals": sum(d in sold for d in deals), "commission_aed": sum(sold.get(d, 0) for d in deals),
                    "likes": post.get("likes"), "comments": post.get("comments"), "reach": post.get("reach")})
    return sorted(out, key=lambda r: (-r["deals"], -r["leads"], r["ref"]))


def leads_by_angle(office: Office) -> Counter:
    return Counter(a["angle"] for a in _attributions(office) if a.get("angle"))


# ---------- the Marketing day ----------

def morning(office: Office, now: datetime | None = None) -> dict:
    """What the Marketing manager starts the day with."""
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    have = pieces(office)
    open_ = [n.props["text"] for n in g.of("request", status="open") if n.props.get("agent") in ("mpub", "mcopy")]
    need = [{"ref": x["ref"], "title": x.get("title")} for x in rhythm.listings(office) if x["ref"] not in have][:5]
    look = [{"title": b.get("title"), "why": b.get("why"), "url": b.get("url")} for b in studio.board(office) if b.get("kind") == "outlier"][-3:]
    y = (_today(office, now) - timedelta(days=1)).isoformat()
    source = Counter(a["via"] for a in _attributions(office) if a["at"][:10] == y)
    paused = [{"ref": r, "why": p["why"]} for r, p in have.items() if p["stage"] == "paused"]
    return {"to_approve": open_, "need_content": need, "worth_a_look": look, "leads_yesterday": dict(source), "paused": paused}


def evening(office: Office, now: datetime | None = None) -> dict:
    tomorrow = (_today(office, now) + timedelta(days=1)).isoformat()
    soon = [{"ref": r, "at": s["at"]} for r, s in studio.scheduled(office).items() if business.local(datetime.fromisoformat(s["at"]), office).date().isoformat() == tomorrow]
    return {"tomorrow": soon, "paused": [{"ref": r, "why": p["why"]} for r, p in pieces(office).items() if p["stage"] == "paused"]}


def weekly(office: Office, now: datetime | None = None) -> dict:
    """The last 7 days: what brought deals, not only views."""
    cut = (_today(office, now) - timedelta(days=7)).isoformat()
    recent = {a["ref"] for a in _attributions(office) if a["at"][:10] >= cut}
    rows = [r for r in results(office) if r["ref"] in recent]
    lines = [f"{r['title']}: {r['leads']} lead{'s' if r['leads'] != 1 else ''}, {r['qualified']} qualified, {r['viewings']} viewing{'s' if r['viewings'] != 1 else ''}, "
             f"{r['deals']} deal{'s' if r['deals'] != 1 else ''}" + (f", AED {r['commission_aed']:,} commission" if r["commission_aed"] else "") for r in rows]
    return {"since": cut, "rows": rows, "lines": lines or ["No lead has been traced to a post in the last 7 days."]}


def tick(office: Office, now: datetime | None = None) -> None:
    """Every minute: trace, follow the facts, and keep the day's rhythm."""
    from diwan import leads
    attribute(office)
    watch(office, now)
    local = business.local(now or datetime.now(timezone.utc), office)
    day, clock, who = local.date().isoformat(), local.strftime("%H:%M"), person(office)
    if clock >= "08:00" and _once(office, f"morning:{day}"):
        m = morning(office, now)
        leads.notify(office, who, f"Marketing today: {len(m['to_approve'])} waiting for you, {len(m['need_content'])} listings without content, {len(m['paused'])} paused.", kind="info")
    if clock >= "17:30" and _once(office, f"evening:{day}"):
        e = evening(office, now)
        leads.notify(office, who, f"Tomorrow: {len(e['tomorrow'])} post{'s' if len(e['tomorrow']) != 1 else ''} scheduled, {len(e['paused'])} paused.", kind="info")
    if local.weekday() == 0 and clock >= "09:00" and _once(office, f"weekly:{day}"):
        leads.notify(office, who, "This week's marketing: " + " ".join(weekly(office, now)["lines"][:3]), kind="info")
    _cost_flags(office)


# ---------- the plan and what waits for a person ----------

def stage_labels(office: Office) -> dict[str, str]:
    """{ref: where its post is now, in words}, for the plan."""
    return {r: LABELS.get(p["stage"], "") for r, p in pieces(office).items()}


def format_of(office: Office, ref: str | None) -> str:
    """The kind of post a subject will be, in words."""
    from diwan.agents import eventpost
    lst = _subject(office, ref) if ref else None
    if not lst:
        return ""
    if eventpost.shape(office, lst):
        return eventpost.suggest(office, ref)["label"]
    return "Reel, to camera" if lst["item"] == "topic" else "Reel, voice-over"


def waiting(office: Office) -> list[dict]:
    """Everything that needs a person, across every post, oldest first."""
    what = {"use_script": ("Pick a script", r"Pick a script for (\S+) "), "approve_brief": ("Approve the brief", r"Approve the brief for (\S+):"), "publish": ("Approve publishing", r"Publish the (\S+) ")}
    out = []
    for n in office.graph().of("request", status="open"):
        k = n.props.get("kind")
        if k not in what or n.props.get("agent") not in ("mpub", "mcopy"):
            continue
        m = re.match(what[k][1], n.props.get("text", ""))
        ref = m.group(1) if m else None
        out.append({"id": n.id, "kind": k, "label": what[k][0], "ref": ref, "title": (_subject(office, ref) or {}).get("title") or ref, "text": n.props.get("text", "")})
    return out


def plan_view(office: Office) -> dict:
    """The Plan tab: each day ahead, what is waiting for a person, and what came off."""
    from diwan.agents import journey
    p = rhythm.current(office)
    have, begun = pieces(office), rhythm.started(office)
    today = _today(office).isoformat()
    days = []
    for d in (p or {}).get("days", []):
        if d["date"] < today:
            continue
        ref, piece = d.get("ref"), have.get(d.get("ref")) or {}
        state = "written" if d["date"] in begun else d.get("status") or "pending"
        days.append({"date": d["date"], "ref": ref, "title": (_subject(office, ref) or {}).get("title") or ref or "", "why": d.get("why", ""), "borrows": d.get("borrows", ""), "format": format_of(office, ref),
                     "job": journey.JOBS[d["job"]]["label"] if d.get("job") in journey.JOBS else ("Teach something" if d.get("type") == "topic" else "Offer something"),
                     "state": state, "stage": LABELS.get(piece.get("stage"), "") if d["date"] in begun else ""})
    from diwan.agents import planner
    based = planner.evidence(office, [d["ref"] for d in days if d["ref"]])
    days = [d | {"evidence": "; ".join(x for x in (d.pop("borrows", ""), based.get(d["ref"], "")) if x)} for d in days]  # what the day builds on, then the facts behind it
    going = [{"ref": r, "title": (_subject(office, r) or {}).get("title") or r, "at": s["at"]} for r, s in studio.scheduled(office).items()]
    removed = [{"date": r["date"], "title": (_subject(office, r["ref"]) or {}).get("title") or r["ref"]} for r in (p or {}).get("removed") or []]
    stopped = [{"ref": r, "title": x.get("title") or r, "why": x.get("why", "")} for r, x in have.items() if x["stage"] == "withdrawn"]
    live = [{"ref": r, "title": x.get("title") or r, "since": x["since"][:10]} for r, x in have.items() if x["stage"] == "live"]
    asks = waiting(office)
    return {"days": days, "waiting": asks, "carry_on": carry_on(office, have, {w["ref"] for w in asks}), "scheduled": going, "removed": removed, "stopped": stopped, "live": live,
            "rhythm": rhythm.settings(office)["rhythm"], "automatic": rhythm.settings(office)["auto"] == "on", "next": rhythm.next_run(office),
            "chosen_by": (p or {}).get("chosen_by", "rules"), "plan_ahead": rhythm.settings(office)["plan_ahead"] == "on"}


def carry_on(office: Office, have: dict | None = None, asked: set | None = None) -> list[dict]:
    """Every post started and not yet scheduled, posted or stopped, whatever day it was planned for, newest first,
    with the next step in words. A post already waiting under Waiting for you isn't listed twice."""
    from diwan.agents import freevideo
    have = have if have is not None else pieces(office)
    out = []
    for ref, x in sorted(have.items(), key=lambda kv: kv[1]["since"], reverse=True):
        if x["stage"] not in ("idea", "briefed", "scripted", "in_production", "ready", "paused") or ref in (asked or set()):
            continue
        writing = ref in studio.RUNNING
        if studio.stuck(office, ref):
            out.append({"ref": ref, "title": (_subject(office, ref) or {}).get("title") or ref, "stage": LABELS[x["stage"]],
                        "next": "The scripts failed review 3 times: decide what to do", "since": x["since"], "writing": False})
            continue
        n = len(freevideo.photos(office, ref)) if x["stage"] == "in_production" else 0
        cut = studio.made(office, "cut", ref) if x["stage"] == "in_production" else None
        nxt = ("The scripts are being written now" if writing else
               {"idea": "Write the scripts", "briefed": "Write the scripts", "scripted": "Pick a script",
                "in_production": "Check the video and approve it" if cut else (f"Make the video: {n} picture{'s' if n != 1 else ''} ready" if n else "Film it, or make the video"),
                "ready": "Approve publishing", "paused": f"Paused: {x.get('why') or 'see why'}"}[x["stage"]])
        out.append({"ref": ref, "title": (_subject(office, ref) or {}).get("title") or ref, "stage": LABELS[x["stage"]], "next": nxt,
                    "since": x["since"], "writing": writing})
    return out


# ---------- campaigns ----------

def campaigns(office: Office) -> list[dict]:
    out: dict[str, dict] = {}
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "content.made" and c.get("kind") == "campaign":
            out[c["id"]] = dict(c) | {"state": "draft", "at": e["at"]}
        elif e["type"] == "campaign.started" and c.get("id") in out:
            out[c["id"]].update(state="running", ad_id=c.get("ad_id"), started=e["at"][:10], by=e["actor"])
        elif e["type"] == "campaign.ended" and c.get("id") in out:
            out[c["id"]].update(state="ended", ended=e["at"][:10], why=c.get("why"))
    return list(out.values())


def spent_cap(office: Office) -> dict:
    cap = int(rhythm.settings(office)["ad_budget"])
    month = _today(office).isoformat()[:7]
    used = sum(c["budget"] for c in campaigns(office) if c["at"][:7] == month and c["state"] != "ended")
    return {"cap": cap, "committed": used, "left": max(0, cap - used)}


def draft(office: Office, ref: str, values: dict, *, by: str) -> dict:
    """A campaign, with its ad drafted from the post. Nothing is launched: a person does that in Ads Manager and pays."""
    goal, audience = str(values.get("goal", "")).strip(), str(values.get("audience", "")).strip()
    if not goal or not audience:
        raise ValueError("Say the goal and the audience.")
    try:
        budget, days = int(values.get("budget", 0)), int(values.get("days", 0))
    except (TypeError, ValueError):
        raise ValueError("Budget and days are whole numbers.") from None
    if budget <= 0 or days <= 0:
        raise ValueError("Budget and days must be above zero.")
    cap = spent_cap(office)
    if not cap["cap"]:
        raise ValueError("Set the monthly ad budget in Setup → Rhythm first.")
    if budget > cap["left"]:
        raise ValueError(f"That is over the monthly cap: AED {cap['left']:,} left of AED {cap['cap']:,}.")
    sc = studio.approved_script(office, ref)
    if not sc:
        raise ValueError("Pick a script for this first: the ad is drafted from it.")
    state, why = check(office, ref)
    if state != "ok":
        raise ValueError("This post can't be advertised: " + " ".join(why))
    copy = " ".join([sc["hook_en"], *sc["lines_en"][:2]])
    text = f"{copy} Say {code_for(office, ref)}."
    return studio._made(office, "mkt", "campaign", ref, {"goal": goal, "audience": audience, "budget": budget, "days": days, "copy": text, "written_by": by}, None)


def start(office: Office, cid: str, *, ad_id: str, by: str) -> None:
    if not (ad_id or "").strip():
        raise ValueError("Give the ad's id from Ads Manager: it is how its spend is read.")
    office.log.append("campaign.started", actor=by, agent="mkt", content={"id": cid, "ad_id": ad_id.strip()})


def end(office: Office, cid: str, *, by: str, why: str = "") -> None:
    office.log.append("campaign.ended", actor=by, agent="mkt", content={"id": cid, "why": why})


def campaign_report(office: Office, *, spend: bool = False) -> list[dict]:
    """Each campaign with its traced leads; spend is read from the ad account only when asked (a network call)."""
    log = office.log.list()
    qualified = {e["deal"] for e in log if e["type"] == "qualify.passed"}
    ads_rows = {}
    note = None
    if spend:
        try:
            ads_rows = {a["id"]: a for a in ads.report()["ads"]} if ads.ready() else {}
            note = None if ads.ready() else "Connect the ad account in Settings to read spend."
        except ads.AdsError as e:
            note = str(e)[:160]
    limit = int(rhythm.settings(office)["cpl_limit"])
    out = []
    for c in campaigns(office):
        came = [a for a in _attributions(office) if a["ref"] == c.get("ref") and c.get("started") and a["at"][:10] >= c["started"]]
        q = sum(a["deal"] in qualified for a in came)
        paid = (ads_rows.get(c.get("ad_id")) or {}).get("spend")
        cost = round(float(paid) / q) if paid is not None and q else None
        out.append(c | {"leads": len(came), "qualified": q, "spend": paid, "cost_per_qualified": cost, "over_limit": bool(limit and cost and cost > limit), "note": note})
    return out


def _cost_flags(office: Office) -> None:
    from diwan import leads
    for c in campaign_report(office):
        if c["over_limit"] and _once(office, f"overlimit:{c['id']}"):
            leads.notify(office, person(office), f"Campaign for {c['ref']} costs AED {c['cost_per_qualified']:,} per qualified lead, over your limit.", kind="info")


def overview(office: Office) -> dict:
    """Everything the Results tab shows."""
    attribute(office)
    have = pieces(office)
    return {"stages": [{"id": s, "label": LABELS[s], "n": sum(p["stage"] == s for p in have.values())} for s in STAGES],
            "pieces": sorted(have.values(), key=lambda p: p["since"], reverse=True)[:30], "results": results(office), "morning": morning(office), "evening": evening(office),
            "weekly": weekly(office), "ideas": waiting_ideas(office), "campaigns": campaign_report(office), "cap": spent_cap(office),
            "settings": {k: rhythm.settings(office)[k] for k in ("auto_post", "approve_brief", "ad_budget", "cpl_limit")}}
