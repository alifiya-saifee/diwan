"""Front Desk: the day as a person meets it (docs/closed-loop-spec.md, Room 1 and "A PA for every staff member").

Nova is the owner's PA; every other signed-in person has their own, the same engine limited to what their role may see. A PA
greets, briefs, reminds and prepares. It never pays, signs, submits, approves or sends on its own: every errand ends in a draft,
and only that person's yes moves it on. Handoffs go through the board and tasks, never PA to PA.

The modes: normal, meeting ("Hey Pocket": silent, keeps the words, answers only to its wake phrase; afterwards a summary,
decisions and action items, each with the exact words) and do not disturb (only Now gets through).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan import leads, sales
from diwan.agents import nova, runner
from diwan.agents.charters import get
from diwan.graph import OPEN, Graph
from diwan.office import Office
from diwan.people import PEOPLE, name, pid
from diwan.slots import DUBAI

MODES = {"normal": "At your desk", "meeting": "In a meeting", "dnd": "Do not disturb"}
WAKE = r"^\W*(?:hey|hi|ok|okay)\s+pocket\b[\s,:.!-]*"
DEAL_STAFF = {"ops", "fin", "comp"}
PENDING: dict[str, dict] = {}  # session -> what the PA read back and waits on a yes for
YES = re.compile(r"^\s*(yes|yep|yeah|sure|ok(ay)?|confirm|go ahead|do it|send( it)?|correct|right)\b", re.I)
NO = re.compile(r"^\s*(no|nope|cancel|stop|don'?t|never mind|wait)\b", re.I)


def is_owner(person: str | None) -> bool:
    return PEOPLE.get(person or "", {}).get("role") == "Owner"


def pa_name(g: Graph, person: str) -> str:
    return "Nova" if is_owner(person) else (leads.setting(g, person, "pa_name") or f"{name(person)}'s PA")


def department(person: str) -> str | None:
    p = PEOPLE.get(person, {})
    return "sales" if p.get("role") == "Sales manager" else p.get("team")


def sees_deal(g: Graph, deal: str | None, person: str) -> bool:
    """The room table: the owner, the Sales manager and the deal staff see every deal; a broker their own; Marketing none."""
    if not deal or f"deal:{deal}" not in g.nodes:
        return False
    p = PEOPLE.get(person, {})
    if p.get("role") in ("Owner", "Sales manager") or department(person) in DEAL_STAFF:
        return True
    return p.get("role") == "Broker" and g.nodes[f"deal:{deal}"].props.get("broker") == person


# ---------- modes ----------

def mode(g: Graph, person: str) -> str:
    return leads.setting(g, person, "mode") or "normal"


def set_mode(office: Office, person: str, value: str) -> str:
    if value not in MODES:
        raise ValueError(f"A mode: {', '.join(MODES)}")
    office.log.append("setting.changed", actor=person, content={"person": person, "key": "mode", "value": value})
    return value


# ---------- the day ----------

def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def reminders(g: Graph, person: str) -> list:
    return [t for t in g.of("task", status=OPEN) if t.props.get("reminder") and t.props.get("needs_person") == person]


def day(office: Office, person: str, now: datetime | None = None) -> dict:
    """Everything this person's day needs, from the records, on one page: what is urgent, today, the pipeline, the money, the
    decisions waiting for them, and what is stuck. The numbers are read from the log, never stored."""
    from diwan import desk_rules, desk_stages, inbox
    from diwan.agents import finance
    now = now or datetime.now(DUBAI)
    g = office.graph()
    owner = is_owner(person)
    today = now.astimezone(DUBAI).date()
    since = (now - timedelta(days=1)).astimezone(timezone.utc).isoformat()
    events = office.log.list()
    seen = lambda deal: sees_deal(g, deal, person)  # noqa: E731
    mine = lambda who: owner or who == person  # noqa: E731
    urgent, decisions = [], []
    for n in g.of("attention", status="open"):
        late = _at(n.props["due"]) < now
        if seen(n.deal) and (mine(n.props.get("who")) or PEOPLE.get(person, {}).get("role") == "Sales manager") and (late or n.props["kind"] == "call"):
            chat = g.nodes.get(f"chat:{n.props['chat']}")
            urgent.append({"kind": "call" if n.props["kind"] == "call" else "reply", "late": late, "chat": n.props["chat"], "refs": [n.id],
                           "text": f"{chat.label if chat else n.props['chat']} {'is waiting for a call' if n.props['kind'] == 'call' else 'needs a reply'}"
                                   f"{', overdue' if late else ''} ({name(n.props.get('who'))})"})
    for t in g.of("task", status=OPEN):
        p = t.props
        if p.get("reminder"):
            if p.get("needs_person") == person and p.get("due") and _at(p["due"]) <= now + timedelta(hours=2):
                urgent.append({"kind": "reminder", "late": _at(p["due"]) < now, "refs": [t.id], "text": f"Reminder: {p['action']}"})
        elif p.get("fraud") and (owner or department(person) in ("comp", "fin")):
            urgent.append({"kind": "fraud", "late": True, "refs": [t.id], "chat": None, "text": p["action"]})
        elif p.get("agent") == "pay" and (owner or department(person) == "fin") and t.deal:
            e = finance.expected(g, t, today)
            if e.get("due") and e["due"] <= today.isoformat():
                urgent.append({"kind": "payment", "late": e["due"] < today.isoformat(), "refs": [t.id], "deal": t.deal,
                               "text": f"{p['action'].removeprefix('Expect ')}, due {e['due']}"})
    if owner or department(person) == "comp":
        for c in g.of("check", status="open"):
            urgent.append({"kind": "compliance", "late": False, "refs": [c.id], "deal": c.deal, "text": c.props.get("text") or c.label})
    for typ in ("check", "decision", "request", "question"):
        for n in g.of(typ, status="open"):
            if n.props.get("who") == person:
                decisions.append({"id": n.id, "type": typ, "text": n.props.get("text") or n.label, "deal": n.deal})
    for c in g.of("lobby", status={"open", "seen", "late"}):
        if c.props.get("to") == person:
            decisions.append({"id": c.id, "type": "lobby", "text": f"{name(c.props['by'])} asked for \"{c.props['text']}\", due {nova.lobby_due(c)}", "deal": None})
    today_list = []
    for v in g.of("viewing", status="booked"):
        at = datetime.fromisoformat(v.props["at"]).astimezone(DUBAI)
        if at.date() != today or not (seen(v.deal) and (owner or v.props["broker"] == person or PEOPLE.get(person, {}).get("role") == "Sales manager")):
            continue
        chat = g.nodes.get(f"chat:{v.props.get('chat')}")
        last = next((m for m in reversed(chat.props["messages"]) if m["type"] == "received"), None) if chat else None
        today_list.append({"at": v.props["at"], "what": v.props.get("kind_name") or "Viewing", "customer": v.props.get("customer"), "broker": name(v.props["broker"]),
                           "listing": v.props.get("listing"), "last": last["text"][:160] if last else None, "chat": v.props.get("chat"),
                           "cares": [c["label"] for c in inbox.interests(g, v.deal, chat.props["messages"])] if chat else []})
    today_list.sort(key=lambda x: x["at"])
    pipeline = money = None
    if owner or PEOPLE.get(person, {}).get("role") == "Sales manager":
        new = [e for e in events if e["type"] == "lead.assigned" and e["at"] >= since and e["content"].get("why") and "moved" not in e["content"]["why"]]
        moved = [e for e in events if e["type"] == "stage.changed" and e["at"] >= since and not e["content"].get("auto")]
        last_by_deal: dict[str, str] = {}
        for e in events:
            if e["deal"]:
                last_by_deal[e["deal"]] = e["at"]
        limit = desk_rules.rules(g)["stuck_days"]
        stuck = []
        for d in g.deals():
            if d.props.get("stage") in ("Won", "Lost") or not desk_stages.agreed(g, d.deal):
                continue
            idle = (now - _at(last_by_deal.get(d.deal, now.isoformat()))).days
            if idle >= limit:
                stuck.append({"deal": d.deal, "property": d.props.get("property"), "days": idle})
        pipeline = {"new": len(new), "hot": sum(1 for d in g.deals() if d.props.get("hot") and d.props.get("stage") not in ("Won", "Lost")),
                    "moved": [{"deal": e["deal"], "stage": e["content"]["stage"]} for e in moved][-5:], "stuck": sorted(stuck, key=lambda x: -x["days"]), "stuck_days": limit,
                    "by_stage": _by_stage(g), "escalated": [{"chat": e["content"]["chat"], "from": name(e["content"]["from"]), "to": name(e["content"]["to"])}
                                                            for e in events if e["type"] == "attention.moved" and e["at"] >= since]}
    if owner or department(person) == "fin":
        got = [e for e in events if e["type"] == "task.done" and e["at"] >= since and e["content"].get("result") == "received"]
        sent = [e for e in events if e["type"] == "task.done" and e["at"] >= since and e["agent"] == "inv"]
        due = [t for t in g.of("task", status=OPEN) if t.props.get("agent") == "inv"]
        money = {"received": len(got), "invoices": len(sent), "commission_due": [{"deal": t.deal, "text": t.props["action"], "id": t.id} for t in due][:5]}
    urgent.sort(key=lambda u: (not u["late"], {"fraud": 0, "compliance": 1, "call": 2, "payment": 3}.get(u["kind"], 4)))
    top = [{"text": u["text"], "refs": u["refs"]} for u in urgent[:3]] or [{"text": d["text"], "refs": [d["id"]]} for d in decisions[:3]]
    return {"person": person, "pa": pa_name(g, person), "mode": mode(g, person), "modes": MODES, "top": top, "urgent": urgent, "today": today_list,
            "pipeline": pipeline, "money": money, "decisions": decisions, "errands": errands(office, person),
            "reminders": [{"id": t.id, "text": t.props["action"], "due": t.props.get("due")} for t in reminders(g, person)],
            "idea": None, "pocket": pocket(office, person), "greeting": greeting(g, person, urgent, decisions, now),
            "wrap": wrap(g, events, person, urgent, decisions, pipeline, now)}


def wrap(g: Graph, events: list[dict], person: str, urgent: list, decisions: list, pipeline: dict | None, now: datetime) -> str | None:
    """After 5 PM, two lines: what closed, what's stuck, and the first thing tomorrow."""
    local = now.astimezone(DUBAI)
    if local.hour < 17:
        return None
    start = local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    closed = len([e for e in events if e["type"] == "sale.closed" and e["at"] >= start])
    stuck = len((pipeline or {}).get("stuck", []))
    first = (urgent or decisions or [{"text": "nothing waiting yet"}])[0]["text"]
    return f"Today: {closed} closed, {stuck} stuck.\nFirst thing tomorrow: {first}."


def _by_stage(g: Graph) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in g.deals():
        s = d.props.get("stage") or "New"
        if s not in ("Won", "Lost"):
            out[s] = out.get(s, 0) + 1
    return out


def greeting(g: Graph, person: str, urgent: list, decisions: list, now: datetime) -> str:
    hour = now.astimezone(DUBAI).hour
    hello = "Morning" if hour < 12 else "Afternoon" if hour < 17 else "Evening"
    n = len(urgent) + len(decisions)
    words = {1: "One thing needs", 2: "Two things need", 3: "Three things need"}.get(n, f"{n} things need")
    return f"{hello}, {name(person)}. " + (f"{words} you." if n else "Nothing needs you right now.")


def arrive(office: Office, person: str, now: datetime | None = None) -> dict:
    """The first open of the day: a greeting and the top three. Later opens are quiet."""
    now = now or datetime.now(DUBAI)
    d = day(office, person, now)
    ev = office.log.append("nova.arrived", actor=person, agent="nova", key=f"arrived:{person}:{now.astimezone(DUBAI).date()}", content={"person": person})
    return d | {"first": not ev.get("duplicate")}


# ---------- reminders ----------

REMIND = re.compile(r"^\s*(?:please\s+)?remind me\s+(.+)$", re.I)


def add_reminder(office: Office, person: str, text: str, now: datetime) -> dict | None:
    """"Remind me Thursday to call Sara": a task with a due time, not a note. A day with no hour means 9 in the morning."""
    from diwan.agents import lobby
    m = REMIND.match(text)
    if not m:
        return None
    due, rest = lobby.due_from(m.group(1), now, bare=True)
    if not due:
        return {"kind": "question", "text": "When should I remind you? For example \"Thursday 10am\".", "options": ["Tomorrow 10 AM", "Today 6 PM"]}
    if not re.search(r"\d", m.group(1)):
        due = due.replace(hour=9, minute=0)
    what = re.sub(r"^\s*(?:on|at|to|about|that)\s+", "", rest, flags=re.I).strip(" .,") or m.group(1)
    tid = office.add_task(None, "nova", what[:1].upper() + what[1:], needs_person=person, by="nova", props={"due": due.isoformat(), "reminder": True})
    return {"kind": "done", "text": f"I'll remind you {due.astimezone(DUBAI):%A %d %b at %H:%M}: {what}.", "task": tid}


def finish_reminder(office: Office, tid: str, *, by: str) -> None:
    t = office.graph().nodes.get(tid)
    if not t or not t.props.get("reminder"):
        raise KeyError(tid)
    if t.props.get("needs_person") != by and not is_owner(by):
        raise PermissionError("That reminder is someone else's")
    office.finish_task(tid, f"{name(by)} marked it done")


def sweep(office: Office, now: datetime | None = None) -> list[str]:
    """A reminder reaches its person at its time, once, outside quiet hours (Now gets through anyway)."""
    from diwan.agents import nudge
    now = now or datetime.now(DUBAI)
    g = office.graph()
    out = []
    if not nudge.allowed(nudge.settings(g), now):
        return out
    for t in g.of("task", status=OPEN):
        if t.props.get("reminder") and t.props.get("due") and _at(t.props["due"]) <= now:
            ev = office.log.append("lead.nudged", actor="nova", agent="nova", key=f"remind:{t.id}", content={"to": t.props["needs_person"], "task": t.id})
            if not ev.get("duplicate"):
                leads.notify(office, t.props["needs_person"], f"Reminder: {t.props['action']}", kind="now", cause=ev["id"])
                out.append(f"reminded {t.id}")
    return out


# ---------- errands: each ends in a draft that waits for a yes ----------

def errands(office: Office, person: str) -> list[dict]:
    live: dict[str, dict] = {}
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "errand.drafted" and c.get("by") == person:
            live[c["id"]] = dict(c) | {"at": e["at"], "status": "waiting for your yes"}
        elif e["type"] in ("errand.confirmed", "errand.cancelled") and c.get("id") in live:
            live.pop(c["id"])
    return list(live.values())


def _errand(office: Office, person: str, kind: str, title: str, draft: str, *, sources: list | None = None, facts: list | None = None, session: str = "") -> dict:
    eid = f"E{(office.log.list() or [{'id': 0}])[-1]['id'] + 1}"
    office.log.append("errand.drafted", actor="nova", agent="nova", content={"id": eid, "by": person, "kind": kind, "title": title, "draft": draft,
                                                                             "sources": sources or [], "facts": facts or []})
    PENDING[session] = {"errand": eid}
    return {"kind": "confirm", "text": f"{title}\n\n{draft}\n\nShall I keep this as approved? Nothing is sent, booked or paid by me.", "options": ["Yes", "Cancel"], "errand": eid,
            "sources": sources or []}


def decide_errand(office: Office, eid: str, *, by: str, yes: bool) -> dict:
    live = {e["id"]: e for e in errands(office, by)}
    if eid not in live:
        raise KeyError(eid)
    office.log.append("errand.confirmed" if yes else "errand.cancelled", actor=by, content={"id": eid, "kind": live[eid]["kind"]})
    return {"kind": "done", "text": ("Approved. No email or booking account is connected, so nothing went out by itself: send it from your own account."
                                     if yes else "Cancelled. Nothing was sent.")}


MESSAGE = {"name": "message", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["message"],
                                                         "properties": {"message": {"type": "string"}}}}


def _write(person: str, who: str, about: str) -> str:
    """A short draft in the person's name: from the model when one is connected, otherwise a plain opening they finish."""
    c = get("nova")
    system = (f"You draft a short message for {name(person)} at a Dubai real-estate brokerage to send themselves. Warm and plain, two or three sentences. "
              "You have no records here: never invent a fact, amount or date; leave [brackets] where they must fill something in.")
    user = f"To {who}" + (f", about {about}" if about else "") + "."
    if runner.has_model(c, system, user, schema=MESSAGE):
        try:
            return str(runner.call(c, system, user, schema=MESSAGE, timeout=runner.LIVE).data["message"]).strip()
        except Exception:  # noqa: BLE001
            pass
    return f"Hi {who},\n\n{('About ' + about + ': ') if about else ''}\n\nBest regards,\n{name(person)}"


def _search(prompt: str) -> dict | None:
    from diwan.providers import meta
    try:
        return meta.search(prompt, timeout=60, agent="nova")
    except Exception:  # noqa: BLE001
        return None


EMAIL = re.compile(r"^\s*(?:please\s+)?(?:(?:draft|write)(?:\s+(?:a|an|me a))?\s+(?:reply|message|email|note)\s+(?:to|for)\s+|email\s+|reply to\s+)(.+?)(?:\s+(?:about|on|re|saying)\s+(.+))?\s*$", re.I)
TRAVEL = r"\b(ticket prices?|flights?|hotels?|book (?:the|a|my) (?:vacation|trip|holiday|flight|hotel))\b"
RESEARCH = r"^\s*(?:please\s+)?(?:research|look up|find out|check)\b|\b(track record|news (?:on|about)|competitor listings?)\b"


# ---------- the broker's PA ----------

def _client(g: Graph, text: str, person: str):
    """The client this person means, by name, among the leads they may see."""
    low = set(re.findall(r"[a-z]+", text.lower()))
    hits = [c for c in g.of("chat") if not c.props.get("merged_into") and sees_deal(g, c.deal, person)
            and (set(re.findall(r"[a-z]+", c.label.lower())) & low)]
    return hits[0] if len(hits) == 1 else None


def _options_text(g: Graph, chat, n: int) -> tuple[str, list]:
    from diwan.agents import reception
    recs = reception.recommend(g, chat.deal, n) or reception.nearest(g, chat.deal, n)[0]
    first = reception.first_name(chat.label)
    lines = "\n".join(f"{i}. {reception._listing_line(x)}" for i, x in enumerate(recs, 1))
    return f"Hi{' ' + first if first else ''}, here are the closest options for you:\n{lines}\nWhich one interests you?", recs


def _broker_asks(office: Office, text: str, person: str, session: str, now: datetime) -> dict | None:
    from diwan import slots
    g = office.graph()
    low = text.lower().strip()
    if m := re.match(r"^\s*(?:please\s+)?book\s+(.+?)\s+(?:a\s+)?(viewing|visit)\b", low):
        chat = _client(g, m.group(1), person)
        if not chat:
            return {"kind": "unknown", "text": f"I can't find one client called {m.group(1).title()} among your leads."}
        when = slots.parse(text, now)
        d = g.nodes[f"deal:{chat.deal}"].props
        ref = ((d.get("hot") or {}).get("listing") or next(iter(d.get("recommended") or []), "") or "").replace("listing:", "")
        if not when or not ref:
            return {"kind": "question", "text": f"{'Which property' if not ref else 'What day and time'} for {chat.label}?"}
        PENDING[session] = {"book": {"phone": chat.props["phone"], "name": chat.label, "ref": ref, "at": when.isoformat(), "broker": d["broker"]}}
        return {"kind": "confirm", "text": f"Book {chat.label} to view {ref} with {name(d['broker'])}, {slots.say(when)}?", "options": ["Yes", "Cancel"]}
    if m := re.match(r"^\s*(?:please\s+)?send\s+(.+?)\s+(?:the\s+)?(\d+|three|two|five)?\s*(?:closest\s+|best\s+)?options\b", low):
        chat = _client(g, m.group(1), person)
        if not chat:
            return {"kind": "unknown", "text": "Which client? I need a name I can find among your leads."}
        n = {"two": 2, "three": 3, "five": 5}.get(m.group(2) or "", int(m.group(2)) if (m.group(2) or "").isdigit() else 3)
        msg, recs = _options_text(g, chat, n)
        if not recs:
            return {"kind": "unknown", "text": f"Nothing is close to what {chat.label} asked for yet."}
        PENDING[session] = {"send": {"phone": chat.props["phone"], "text": msg, "refs": [x.id for x in recs]}}
        return {"kind": "confirm", "text": f"This goes to {chat.label}:\n\n{msg}\n\nSend it?", "options": ["Yes", "Cancel"]}
    if m := re.match(r"^\s*log[:\s]+(.+)$", text, re.I):
        from diwan.agents import visit
        chat = _client(g, m.group(1), person) or next(iter(sorted((c for c in g.of("chat") if sees_deal(g, c.deal, person) and g.of("viewing", c.deal, "done")),
                                                                  key=lambda c: c.props.get("last_at") or "", reverse=True)), None)
        if not chat:
            return {"kind": "question", "text": "Which client is this about?"}
        visit.summarize(office, chat.deal, said=m.group(1), source="notes", by=person)
        return {"kind": "done", "text": f"Logged on {chat.label}'s lead."}
    return None


def _manager_asks(office: Office, text: str, person: str, session: str, now: datetime) -> dict | None:
    from diwan import inbox
    if not (is_owner(person) or PEOPLE.get(person, {}).get("role") == "Sales manager"):
        return None
    g = office.graph()
    low = text.lower()
    if re.search(r"\bslowest\b.*\bcall|\bwho('s| is) slow", low):
        times: dict[str, list[float]] = {}
        week = now - timedelta(days=7)
        for n in g.of("attention", status="cleared"):
            if n.props.get("kind") == "call" and n.props.get("action") == "called" and _at(n.props["cleared_at"]) >= week and n.props.get("raised"):
                times.setdefault(n.props.get("cleared_by"), []).append((_at(n.props["cleared_at"]) - _at(n.props["raised"])).total_seconds() / 60)
        if not times:
            return {"kind": "answer", "text": "Not recorded: no calls were marked in the last 7 days.", "cites": []}
        rows = sorted(((sum(v) / len(v), k, len(v)) for k, v in times.items()), reverse=True)
        return {"kind": "answer", "text": "Average minutes to call back, last 7 days: " + "; ".join(f"{name(k)} {m:.0f} ({n} calls)" for m, k, n in rows) + ".", "cites": []}
    if re.search(r"\bhot leads?\b.*\bno viewing|\bno viewing\b.*\bhot", low):
        booked = {v.props.get("chat") for v in g.of("viewing", status="booked")}
        rows = [c.label for c in g.of("chat") if c.deal and f"deal:{c.deal}" in g.nodes and g.nodes[f"deal:{c.deal}"].props.get("hot") and c.props["phone"] not in booked]
        return {"kind": "answer", "text": ("Hot, with no viewing: " + ", ".join(rows) + ".") if rows else "Every hot lead has a viewing booked.", "cites": []}
    if m := re.search(r"\bgive\s+(\w+)'?s?\s+leads\s+to\s+(\w+)", low):
        a, b = pid(m.group(1)), pid(m.group(2))
        if a not in leads.brokers() or b not in leads.brokers():
            return {"kind": "unknown", "text": "I need two brokers' names."}
        chats = [r["phone"] for r in inbox.listing(office, view="all", person=person, now=now) if r["broker"] == a and r["stage"] not in ("Won", "Lost")]
        PENDING[session] = {"transfer": {"to": b, "chats": chats}}
        return {"kind": "confirm", "text": f"Move {len(chats)} open lead{'s' if len(chats) != 1 else ''} from {name(a)} to {name(b)}?", "options": ["Yes", "Cancel"]}
    return None


def _follow_up(office: Office, text: str, person: str, session: str, now: datetime) -> dict | None:
    """The answer to a read-back: only a yes from this person does anything."""
    from diwan.agents import reception
    p = PENDING.get(session)
    if not p:
        return None
    if NO.match(text):
        PENDING.pop(session)
        if p.get("errand"):
            return decide_errand(office, p["errand"], by=person, yes=False)
        return {"kind": "answer", "text": "Cancelled. Nothing was done."}
    if not YES.match(text):
        return None
    PENDING.pop(session)
    if p.get("errand"):
        return decide_errand(office, p["errand"], by=person, yes=True)
    if b := p.get("book"):
        from diwan import slots
        kind = next(k for k in slots.appointments(office.graph()) if k["where"] == "property")
        reception.add_by_hand(office, by=person, broker=b["broker"], phone=b["phone"], name_=b["name"], kind_id=kind["id"], ref=b["ref"], when=datetime.fromisoformat(b["at"]), now=now)
        return {"kind": "done", "text": f"Booked on the calendar. Reminders go to {b['name']} on the usual schedule."}
    if s := p.get("send"):
        reception.person_sends(office, s["phone"], s["text"], by=person)
        office.log.append("lead.recommended", actor=person, deal=office.graph().nodes[f"chat:{s['phone']}"].deal, content={"refs": s["refs"], "chat": s["phone"]})
        return {"kind": "done", "text": "Sent."}
    if t := p.get("transfer"):
        for c in t["chats"]:
            leads.reassign(office, c, t["to"], by=person)
        return {"kind": "done", "text": f"Moved {len(t['chats'])} to {name(t['to'])}. They've been told."}
    if r := p.get("relay"):
        return _record_relay(office, r, person)
    return None


# ---------- what the owner heard ----------

RELAY = re.compile(r"^\s*(?P<who>[A-Z][a-z]+)\s+(?:now\s+|also\s+|actually\s+)?(?:wants|said|says|told me|changed|prefers|will pay|is paying|can only|decided)\b", re.U)


def _record_relay(office: Office, r: dict, person: str) -> dict:
    """Someone relays what a client said: their words become a Fact in that person's name, and can trigger the correction rule."""
    from diwan import qualify
    from diwan.agents import scribe
    ev = office.log.append("instruction.given", actor=person, agent="nova", deal=r["deal"], content={"text": r["text"], "relayed": True})
    heard = scribe.hear(office, r["deal"], name(person), r["text"], ev["id"])
    g = office.graph()
    d = g.nodes[f"deal:{r['deal']}"].props
    _, answers = qualify.read_rules(g, qualify.form(g), d.get("qtype"), r["text"], None)
    kept = qualify.record(office, r["deal"], qtype=None, type_quote=None, answers=answers, said=r["text"], by=person, cause=ev["id"])
    facts = heard["facts"] or ([] if kept else [office.record_fact(r["deal"], "commitment", r["text"], name(person), caused_by=ev["id"])])
    return {"kind": "done", "text": f"Recorded on {d.get('customer')}'s file, in your words" + (f" ({', '.join(facts)})" if facts else "") + ".", "cites": facts}


# ---------- what a PA hears before anything else ----------

def handle(office: Office, text: str, person: str, session: str, now: datetime) -> dict | None:
    t = text.strip()
    low = t.lower()
    g = office.graph()
    if out := _follow_up(office, t, person, session, now):
        return out
    if re.search(r"^\W*(do not disturb|dnd)\b", low) or re.search(r"\bturn on do not disturb\b", low):
        set_mode(office, person, "dnd")
        return {"kind": "done", "text": "Do not disturb is on. Only urgent items get through."}
    if re.search(WAKE, low) or re.search(r"\bi'?m in a meeting\b", low):
        rest = re.sub(WAKE, "", t, flags=re.I).strip()
        if mode(g, person) == "meeting" and rest:
            return pocket_ask(office, rest, person)
        return start_pocket(office, person)
    if re.search(r"\b(i'?m back|meeting (is )?(over|done|finished)|end (the )?meeting|pocket off|disturb off)\b", low):
        if mode(g, person) == "meeting":
            return end_pocket(office, person, now)
        set_mode(office, person, "normal")
        return {"kind": "done", "text": "Welcome back. Anything held is in your notices."}
    if mode(g, person) == "meeting":  # silent: it keeps the words and says nothing
        line(office, person, t)
        return {"kind": "silent", "text": ""}
    if out := add_reminder(office, person, t, now):
        return out
    if m := re.search(r"\bwho (?:hasn'?t|has not|didn'?t)\s+called\s+(.+?)\s+back\b", low):
        who = m.group(1)
        cards = [n for n in g.of("attention", status="open") if n.props.get("kind") == "call" and sees_deal(g, n.deal, person)
                 and who in g.nodes[f"chat:{n.props['chat']}"].label.lower()]
        if not cards:
            return {"kind": "answer", "text": f"Nobody owes {who.title()} a call: no open call on record.", "cites": []}
        n = cards[0]
        return {"kind": "answer", "text": f"{name(n.props['who'])} owes {who.title()} a call, due {_at(n.props['due']).astimezone(DUBAI):%H:%M} ({n.props['reason'][:100]}).", "cites": [n.id]}
    if out := _manager_asks(office, t, person, session, now):
        return out
    if department(person) == "sales" or is_owner(person):
        if out := _broker_asks(office, t, person, session, now):
            return out
    if m := EMAIL.match(t):
        who, about = m.group(1).strip(" ."), (m.group(2) or "").strip(" .")
        return _errand(office, person, "message", f"Draft for {who}" + (f", about {about}" if about else ""), _write(person, who, about), session=session)
    if re.search(TRAVEL, low) or (re.search(RESEARCH, low) and not re.search(r"\b(screen|sanction|source of funds)\b", low)):
        found = _search(f"For a business owner in Dubai: {t}. Compare at most 3 options with prices and the source of each. Be brief.")
        if not found or not found.get("text"):
            return {"kind": "unknown", "text": "I can't search the web right now: it needs the Muse Spark connection. Nothing was booked."}
        return _errand(office, person, "research", t, found["text"], sources=[c.get("url") for c in found.get("cited", [])][:5], session=session)
    if is_owner(person) and (m := RELAY.match(t)):
        customers = [d for d in g.deals() if m.group("who").lower() in d.props.get("customer", "").lower().split() and d.props.get("stage") not in ("Won", "Lost")]
        if len(customers) == 1:
            d = customers[0]
            PENDING[session] = {"relay": {"deal": d.deal, "text": t}}
            return {"kind": "confirm", "text": f"Record this on {d.props['customer']}'s file ({d.props.get('property')}): \"{t}\"?", "options": ["Yes", "Cancel"]}
    return None


# ---------- meeting mode ("pocket") ----------

def pocket(office: Office, person: str) -> dict | None:
    """The meeting this person is in, or None."""
    cur = None
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "pocket.started" and c.get("by") == person:
            cur = {"id": c["id"], "lines": [], "at": e["at"]}
        elif e["type"] == "pocket.line" and cur and c.get("id") == cur["id"]:
            cur["lines"].append({"text": c["text"], "at": e["at"]})
        elif e["type"] == "pocket.ended" and cur and c.get("id") == cur["id"]:
            cur = None
    return cur


def start_pocket(office: Office, person: str) -> dict:
    if not pocket(office, person):
        office.log.append("pocket.started", actor=person, agent="nova", content={"id": f"P{(office.log.list() or [{'id': 0}])[-1]['id'] + 1}", "by": person})
    set_mode(office, person, "meeting")
    return {"kind": "done", "text": "Listening. I'll stay silent: say \"Hey Pocket\" if you need me. Tell everyone in the room this is being noted."}


def line(office: Office, person: str, text: str) -> dict | None:
    cur = pocket(office, person)
    if not cur or not text.strip():
        return None
    return office.log.append("pocket.line", actor=person, agent="nova", content={"id": cur["id"], "text": text.strip()[:2000]})


def pocket_ask(office: Office, question: str, person: str) -> dict:
    """Spoken to by its wake phrase: one short answer from the records, shown only to this person."""
    out = nova.ask(office, question, person, scoped=not is_owner(person))
    return {"kind": out.get("kind", "answer"), "text": out.get("text", ""), "cites": out.get("cites", [])}


ACTION = re.compile(r"^\s*(?P<who>[A-Z][a-z]+)\s+(?:will|to|should|needs to|must|has to)\s+(?P<what>.+)$")
DECIDED = re.compile(r"\b(we (?:agreed|decided)|decision|agreed that|let'?s go with|we'?ll go with)\b", re.I)


def end_pocket(office: Office, person: str, now: datetime | None = None) -> dict:
    """After the meeting: a summary, the decisions and the action items, each with the exact words said. Action items become
    work on the board for the person named. Facts about a named client go on their file."""
    from diwan.agents import lobby
    now = now or datetime.now(DUBAI)
    cur = pocket(office, person)
    if not cur:
        set_mode(office, person, "normal")
        return {"kind": "done", "text": "There was no meeting running."}
    sentences = [s.strip() for ln in cur["lines"] for s in re.split(r"(?<=[.!?])\s+", ln["text"]) if s.strip()]
    decisions = [s for s in sentences if DECIDED.search(s)]
    actions, posted = [], []
    for s in sentences:
        m = ACTION.match(s)
        if m and pid(m.group("who")):
            due, what = lobby.due_from(m.group("what"), now)
            to = pid(m.group("who"))
            card = {"to": to, "team": lobby.PERSON_TEAM.get(to, "sales"), "text": what[:1].upper() + what[1:].rstrip("."), "due": due.isoformat() if due else None, "by": person}
            posted.append(lobby.post(office, card))
            actions.append({"who": name(to), "what": card["text"], "quote": s, "card": posted[-1]})
    facts = []
    g = office.graph()
    for s in sentences:
        if m := RELAY.match(s):
            hits = [d for d in g.deals() if m.group("who").lower() in d.props.get("customer", "").lower().split() and d.props.get("stage") not in ("Won", "Lost")]
            if len(hits) == 1:
                facts += _record_relay(office, {"deal": hits[0].deal, "text": s}, person).get("cites", [])
    summary = " ".join(sentences[:3]) if sentences else "Nothing was noted."
    office.log.append("pocket.ended", actor=person, agent="nova", content={"id": cur["id"], "summary": summary, "decisions": decisions, "actions": actions, "facts": facts})
    set_mode(office, person, "normal")
    parts = [f"Summary: {summary}"] + ([f"Decisions: {'; '.join(decisions)}"] if decisions else []) + (
        [f"Action items: {'; '.join(a['who'] + ': ' + a['what'] for a in actions)}"] if actions else [])
    return {"kind": "done", "text": "\n".join(parts), "summary": summary, "decisions": decisions, "actions": actions, "facts": facts, "cites": posted + facts}


# ---------- a personal PA for every signed-in person ----------

def say(office: Office, text: str, person: str, *, session: str | None = None, now: datetime | None = None) -> dict:
    """One turn with the signed-in person's PA. The owner's is Nova, with the whole office. Everyone else's sees only what
    their role may see, and hands work on through the board, never to another PA."""
    from diwan.agents import lobby
    now = now or datetime.now(DUBAI)
    person = pid(person) or person
    session = session or person
    g = office.graph()
    who = pa_name(g, person)
    if is_owner(person):
        return nova.converse(office, text, person, session=session, now=now) | {"pa": who}
    t = text.strip()
    if out := lobby.follow_up(office, t, person, session, now):
        return out | {"pa": who}
    if any(re.search(rx, t.lower()) for rx, _, _ in nova.REFUSE):
        return nova.route(office, t, person) | {"pa": who}
    if out := handle(office, t, person, session, now):
        return out | {"pa": who}
    if out := lobby.draft(t, person, session, now):
        return out | {"pa": who}
    if re.search(r"\b(waiting on me|what'?s waiting|my day|on my plate|what do i have|for me today|brief me|what needs me|good morning|hello|hi)\b", t.lower()):
        d = day(office, person, now)
        items = [u["text"] for u in d["urgent"]] + [x["text"] for x in d["decisions"]] + [f"{hhmm(v['at'])} {v['what']} with {v['customer']}" for v in d["today"]]
        extra = "; ".join(items[:5]) + (f"; and {len(items) - 5} more" if len(items) > 5 else "")
        return {"kind": "answer", "text": d["greeting"] + (f" {extra}." if extra else ""), "cites": [], "pa": who}
    deal, _ = nova.resolve_deal(g, t, person)
    if deal and sees_deal(g, deal, person):
        return nova.ask(office, t, person, scoped=True, today=now.date()) | {"pa": who}
    return {"kind": "unknown", "text": "Not recorded, or not something your role can see. Ask me about your own work, or name a client of yours.", "cites": [], "pa": who}


def hhmm(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(DUBAI).strftime("%H:%M")
