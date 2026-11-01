"""The Lobby board: work people ask for, with who asked, which department, who it is for, and when it is due.

"Tell Priya I need the Karim review ready by this evening" becomes a draft that Nova reads back; only a yes posts it.
Posting hands it through the department's lead to the person (or the agent) who does it. An hour before it is due an
unfinished card is chased; past due it is marked late and the person who asked is told; done, they are told too.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from diwan import slots
from diwan.agents import runner
from diwan.agents.charters import get
from diwan.graph import Graph
from diwan.office import Office
from diwan.pack import Action, Pack
from diwan.people import name, pid

# who a department's work goes to when no one is named
TEAM_PERSON = {"comp": "priya", "fin": "ahmed", "ops": "joseph", "sales": "omar", "records": "layla"}
TEAM_WORDS = {"compliance": "comp", "finance": "fin", "accounts": "fin", "operations": "ops", "transactions": "ops",
              "sales": "sales", "brokers": "sales", "records": "records"}
PERSON_TEAM = {v: k for k, v in TEAM_PERSON.items() if v != "layla"}
DELEGATE = re.compile(r"^\s*(?:please\s+)?(?:(tell|ask|get|have|remind)\s+(\w+)(?:\s+team)?\s+(?:that\s+|to\s+)?|i\s+need\s+(?:from\s+(\w+)\s+)?)(.+)$", re.I)
DRAFTS: dict[str, dict] = {}   # session -> the card Nova read back and is waiting on a yes for
YES = re.compile(r"^\s*(yes|yep|yeah|sure|ok(ay)?|send( it)?|go ahead|confirm|do it|correct|right)\b", re.I)
NO = re.compile(r"^\s*(no|nope|cancel|stop|don'?t|never mind|wait)\b", re.I)


DAYWORDS = r"this evening|tonight|evening|eve|end of (?:the )?day|eod|close of business|cob|noon|lunch|today|tomorrow|(?:mon|tues|wednes|thurs|fri|satur|sun)day"
TIMEWORD = r"\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2}"


def due_from(text: str, now: datetime, *, bare: bool = False) -> tuple[datetime | None, str]:
    """The deadline said in words ("by this evening", "by Thursday 3pm", "by tomorrow morning"), and the words without it.
    `bare` accepts an answer with no "by", as in a reply to "by when?"."""
    local = now.astimezone(slots.DUBAI)
    lead = r"" if bare else r"\b(?:by|before|until|due)\s+"
    m = re.search(rf"\s*{lead}((?:{DAYWORDS})(?:\s+(?:at\s+)?(?:morning|evening|noon|{TIMEWORD}))?|(?:{TIMEWORD})(?:\s+(?:today|tomorrow))?|\d{{1,2}}\b)", text, re.I)
    if not m:
        return None, text
    w = m.group(1).lower()
    day, hour, minute = local.date(), 18, 0
    if "tomorrow" in w:
        day += timedelta(days=1)
    for i, d in enumerate(slots.DAYS):
        if d in w:
            day += timedelta(days=(i - local.weekday()) % 7 or 7)
    if "noon" in w or "lunch" in w:
        hour = 12
    elif "morning" in w:
        hour = 10
    timed = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", w)
    if timed:
        hour, minute = int(timed.group(1)), int(timed.group(2) or 0)
        if timed.group(3) == "pm" and hour < 12:
            hour += 12
        elif timed.group(3) == "am" and hour == 12:
            hour = 0
        elif not timed.group(3) and hour < 8:
            hour += 12
    if hour > 23:
        return None, text
    due = datetime(day.year, day.month, day.day, hour, minute, tzinfo=slots.DUBAI)
    if due <= local and not re.search(DAYWORDS, w):
        due += timedelta(days=1)
    return due, (text[:m.start()] + text[m.end():]).strip(" .,")


def parse(text: str, now: datetime) -> dict | None:
    """A request for a person or department, or None if the words are not one."""
    m = DELEGATE.match(text.strip())
    if not m:
        return None
    target = (m.group(2) or m.group(3) or "").lower()
    body = m.group(4).strip()
    to = pid(target)
    team = TEAM_WORDS.get(target) or (PERSON_TEAM.get(to) if to else None)
    if not to and not team:
        # "I need the deck by 5" names no one: look for a person or team inside the words
        for w in re.findall(r"[a-z]+", body.lower()):
            if pid(w) or w in TEAM_WORDS:
                to, team = pid(w), TEAM_WORDS.get(w) or PERSON_TEAM.get(pid(w) or "")
                break
    if not to and not team:
        return None
    to = to or TEAM_PERSON.get(team)
    due, body = due_from(body, now)
    body = re.sub(r"^(i need|i want|we need)\s+", "", body, flags=re.I)
    body = re.sub(r"\b(i need|i want)\b\s*", "", body, flags=re.I).strip()
    body = re.sub(rf"\s*\bfrom {re.escape(target)}\b", "", body, flags=re.I) if target else body
    body = re.sub(r"\s+(ready|done|finished|sorted)$", "", body, flags=re.I).strip()
    body = re.sub(r"^(for|about)\s+", "", body, flags=re.I)
    return {"to": to, "team": team or PERSON_TEAM.get(to, "sales"), "text": body[:1].upper() + body[1:], "due": due.isoformat() if due else None}


def say_due(iso: str | None) -> str:
    if not iso:
        return "no deadline"
    return slots.say(datetime.fromisoformat(iso))


def draft(text: str, person: str, session: str, now: datetime) -> dict | None:
    card = parse(text, now)
    if not card:
        return None
    card["by"] = person
    DRAFTS[session] = card
    due = f", due {say_due(card['due'])}" if card["due"] else ""  # a deadline only when one was said
    return {"kind": "confirm", "text": f"So: {name(card['to'])}, \"{card['text']}\"{due}. Shall I send it?", "options": ["Yes, send it", "Cancel"], "draft": card}


def follow_up(office: Office, text: str, person: str, session: str, now: datetime) -> dict | None:
    """The answer to a read-back: yes posts, no drops. "No, send this instead" drops it and carries on with the rest."""
    card = DRAFTS.get(session)
    if not card:
        return None
    if NO.match(text):
        DRAFTS.pop(session)
        other = re.match(r"(?i)\s*(?:cancel|stop|don'?t)\s+(?:my|the)\s+(?!message|draft|email|whatsapp|send)\w", text)  # about something else
        return None if other or len(text.split()) > 5 else {"kind": "answer", "text": "Cancelled. Nothing was sent."}
    if YES.match(text) and len(text.split()) <= 5:  # a yes is a short answer, not a sentence that starts with one
        DRAFTS.pop(session)
        lid = post(office, card)
        chase = "I'll chase it before it's due" if card["due"] else "I'll keep an eye on it"
        return {"kind": "done", "text": f"Sent. It's on the requests board as {lid}; the {get(card['team']).name} has it and {chase}.", "card": lid}
    return None


def post(office: Office, card: dict) -> str:
    g = office.graph()
    lid, tid = f"L{len(g.of('lobby')) + 1}", f"T{len(g.of('task')) + 1}"
    nova, lead = get("nova"), get(card["team"])
    ev = office.log.append("lobby.posted", actor=card["by"], agent="nova",
                           content={"id": lid, "by": card["by"], "to": card["to"], "team": card["team"], "text": card["text"],
                                    "due": card["due"], "task": tid})
    runner.submit(office.log, nova, Pack(lid, "nova", f"Posted {lid} for {name(card['to'])}.", actions=[Action("route", card["text"])]),
                  sources={}, caused_by=ev["id"])
    runner.submit(office.log, lead, Pack(lid, lead.id, f"{name(card['to'])}: {card['text']}", actions=[Action("assign", card["text"])]),
                  sources={}, caused_by=ev["id"])
    office.add_task(None, lead.id, f"{card['text']} (asked by {name(card['by'])}, due {say_due(card['due'])})", needs_person=card["to"],
                    by=lead.id, caused_by=ev["id"], request=lid)
    return lid


def done(office: Office, lid: str, *, by: str, note: str = "") -> dict:
    g = office.graph()
    card = g.nodes[lid]
    ev = office.log.append("lobby.done", actor=by, agent="nova", key=f"lobby-done:{lid}", content={"id": lid, "note": note})
    if (t := g.nodes.get(card.props.get("task"))) and t.status == "queued":
        office.finish_task(t.id, f"{name(by)} marked {lid} done", caused_by=ev["id"])
    return {"ok": True, "tell": card.props["by"]}


def seen(office: Office, lid: str, *, by: str) -> None:
    office.log.append("lobby.seen", actor=by, agent="nova", key=f"lobby-seen:{lid}", content={"id": lid})


def chase(office: Office, now: datetime) -> list[str]:
    """An hour before due: remind the person. Past due: mark late and tell whoever asked. Returns what was done."""
    out = []
    for c in office.graph().of("lobby", status={"open", "seen", "late"}):
        if not c.props.get("due"):
            continue
        due = datetime.fromisoformat(c.props["due"])
        if c.status != "late" and now >= due:
            office.log.append("lobby.late", actor="nova", agent="nova", key=f"lobby-late:{c.id}",
                              content={"id": c.id, "note": f"{name(c.props['to'])} has not marked it done; {name(c.props['by'])} is told."})
            out.append(f"late {c.id}")
        elif not c.props.get("reminded") and due - timedelta(hours=1) <= now < due:
            office.log.append("lobby.reminded", actor="nova", agent="nova", key=f"lobby-remind:{c.id}",
                              content={"id": c.id, "note": f"Due {say_due(c.props['due'])}"})
            out.append(f"reminded {c.id}")
    return out


def board(g: Graph) -> list[dict]:
    order = {"late": 0, "open": 1, "seen": 1, "done": 2, "cancelled": 3}
    cards = sorted(g.of("lobby"), key=lambda c: (order.get(c.status, 9), c.props.get("due") or "9999"))
    return [{"id": c.id, "status": c.status, "record": g.record(c.id), **c.props} for c in cards]

