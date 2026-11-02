"""Nova's watch: the chief of staff walks the office every half hour and moves what has stopped. Whoever holds a stalled lead, a
decision or an approval hears from her once a day; what is still stuck after a second chase goes to the owner. She only ever talks
to staff here: nothing reaches a client, and no money, signature or filing moves.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta

from diwan.agents.frontdesk import _tracks, is_owner
from diwan.events import EventLog
from diwan.office import Office
from diwan.people import PEOPLE, name
from diwan.slots import DUBAI

DAY = timedelta(hours=24)
HOLDS = ("decision", "question", "request", "approval")  # work that waits on one person
CLOSED = ("Won", "Lost")
MAX = 6  # what one chase lists; the rest wait for the next one


def _since(at: str, now: datetime) -> timedelta:
    return now - datetime.fromisoformat(at)


def holder(n) -> str | None:
    p = n.props
    if p.get("agent") == "nova":  # her own questions and reminders belong to the chat, not to anyone's desk
        return None
    return next((x for x in (p.get("who"), p.get("approver"), p.get("needs_person"), p.get("to")) if x in PEOPLE), None)


def findings(office: Office, now: datetime) -> list[dict]:
    """What has stopped, and whose it is."""
    g = office.graph()
    tracks = _tracks(office)
    chats = {c.deal for c in g.of("chat") if not c.props.get("merged_into")}
    out = []
    for x in g.deals():
        b, who = x.props.get("broker"), x.props.get("customer")
        t = tracks.get(x.deal, {})
        if x.props.get("stage") in CLOSED or b not in PEOPLE or t.get("outcome"):
            continue
        if t.get("qualified") and not t.get("viewing") and _since(t["qualified"], now) >= DAY:
            out.append({"key": f"viewing:{x.deal}", "to": b, "text": f"{who} is qualified with no viewing booked"})
        elif x.deal in chats and not t.get("person") and not t.get("qualified") and _since(x.at, now) >= DAY:
            out.append({"key": f"contact:{x.deal}", "to": b, "text": f"{who} has had no first contact from a person"})
    for kind in HOLDS:
        for n in g.of(kind, status="open"):
            if (who := holder(n)) and _since(n.at, now) >= DAY:
                out.append({"key": f"waiting:{n.id}", "to": who, "text": re.sub(r"\s*\([A-Z]{1,2}\d+\)", "", n.props.get("text") or n.label)})
    return out


def chased(log: EventLog) -> dict[str, list[str]]:
    """Each item, and the days it has been chased."""
    out: dict[str, list[str]] = {}
    for e in log.list():
        if e["type"] == "nova.watched":
            for i in e["content"]["items"]:
                out.setdefault(i["key"], []).append(e["content"]["day"])
    return out


def walk(office: Office, now: datetime) -> dict:
    """One walk round: a chase per person, one heads-up for the owner. An item is chased once a day however often she walks."""
    from diwan import leads
    today = now.astimezone(DUBAI).date().isoformat()
    done = chased(office.log)
    owners = [p for p in PEOPLE if is_owner(p)]
    fresh = [f for f in findings(office, now) if today not in done.get(f["key"], [])]
    byperson: dict[str, list[dict]] = {}
    for f in fresh:
        byperson.setdefault(f["to"], []).append(f)
    told: Counter = Counter()
    stuck = []
    for person, items in byperson.items():
        items = items[:MAX]
        ev = office.log.append("nova.watched", actor="nova", agent="nova", key=f"watch:{person}:{today}:{items[0]['key']}",
                               content={"to": person, "day": today, "items": items})
        if ev.get("duplicate"):
            continue
        text = f"{name(person)}, {len(items)} thing{'' if len(items) == 1 else 's'} to move: " + "; ".join(i["text"] for i in items) + "."
        leads.notify(office, person, f"Nova: {text}", kind="info", cause=ev["id"])
        office.log.append("nova.headsup", actor="nova", agent="nova", content={"to": person, "text": text}, caused_by=ev["id"])
        told[person] = len(items)
        stuck += [f"{i['text']} ({name(person)})" for i in items if done.get(i["key"]) and person not in owners]
    if told:
        said = " and ".join(f"{name(p)} on {n} thing{'' if n == 1 else 's'}" for p, n in told.items() if p not in owners)
        text = (f"I've chased {said}." if said else "") + (f" Still stuck after a second chase: {'; '.join(stuck[:4])}." if stuck else "")
        for o in owners:
            if text:
                office.log.append("nova.headsup", actor="nova", agent="nova", content={"to": o, "text": text.strip()})
                if stuck and not leads.resting(office.graph(), o):
                    deliver(office, o, [text.strip()], False, now)
    return {"chased": dict(told), "stuck": stuck}


def sweep(office: Office, now: datetime | None = None) -> dict | None:
    """On working days, in hours the owner allows messages."""
    from diwan import sales
    from diwan.agents import nudge
    now = now or datetime.now(DUBAI)
    g = office.graph()
    if not sales.brief_day(g, now) or not nudge.allowed(nudge.settings(g), now):
        return None
    return walk(office, now)


SERIOUS = r"\b(lawyer|legal action|sue|court|police|rera|complain\w*|refund|scam|cheat\w*|fraud|unacceptable|disgusted|furious|terrible service)\b"
BUYING = r"\b(ready to (?:buy|sign|pay|book|reserve)|buy (?:it )?(?:today|now)|pay (?:today|now)|deposit (?:today|now)|take it|i'?ll take)\b"
LOOKBACK = timedelta(hours=2)
CAN_WAIT = ("payment.flagged", "payment.marked_received", "sale.closed")


def _alert(office: Office, e: dict) -> str | None:
    from diwan import sales
    g, c, t = office.graph(), e["content"], e["type"]
    if t == "chat.received":
        text = c.get("text") or ""
        who = c.get("name") or (g.nodes[f"chat:{c['chat']}"].label if f"chat:{c['chat']}" in g.nodes else c["chat"])
        if re.search(sales.FRAUD, text, re.I):
            return f"Careful: {who} wrote about changing bank details. Nothing moves until someone confirms by phone."
        if re.search(SERIOUS, text, re.I):
            return f"{who} is unhappy and needs a person now. They wrote: {text[:140]}"
        if re.search(BUYING, text, re.I):
            return f"{who} is ready to go ahead. They wrote: {text[:140]}"
    elif t == "lead.hot" and e.get("deal") and f"deal:{e['deal']}" in g.nodes:
        d = g.nodes[f"deal:{e['deal']}"].props
        lst = g.nodes.get(c.get("listing") or "")
        said = {"picked it": "picked", "asked to view it": "asked to view"}.get(c.get("why") or "")
        what = f": {said} {lst.props['title']} ({lst.props['ref']})" if lst and said else f" ({c['why']})" if c.get("why") else ""
        return f"{d.get('customer') or 'A client'} is a hot lead{what}. {name(d.get('broker'))} has it."
    elif t == "notify.sent" and c.get("level") == "now" and is_owner(c.get("to") or ""):
        return c["text"]  # the owner's own urgent notices: a call nobody made, a lead gone to the Pool
    elif t == "screening.hit":
        return f"Compliance: a screening came back with a possible match on {c.get('name') or 'a party'}. Priya has it."
    elif t == "payment.flagged":
        return f"Finance flagged a payment: {c.get('note') or c.get('reason') or 'see the deal'}."
    elif t == "payment.marked_received":
        return f"Money in: AED {c.get('amount') or c.get('amount_aed') or ''} marked received.".replace("AED  ", "")
    elif t == "sale.closed":
        return f"A sale closed: {c.get('listing')}, commission AED {c.get('commission_aed') or 0:,}, {name(c.get('broker'))}."
    return None


ALERTS = ("chat.received", "screening.hit", "payment.flagged", "payment.marked_received", "sale.closed", "lead.hot", "notify.sent")
TROUBLE = ("screening.hit", "payment.flagged")  # with a bank-details change or an unhappy client: goes at once, whatever they're doing
HELD_FOR = timedelta(hours=16)  # what waited for a meeting or the night still goes when it's over
GOOD = ("chat.received", "payment.marked_received", "sale.closed", "lead.hot")  # what may have waited (trouble never waits)


def trouble(e: dict) -> bool:
    from diwan import sales
    text = e["content"].get("text") or ""
    return e["type"] in TROUBLE or (e["type"] == "chat.received" and bool(re.search(sales.FRAUD, text, re.I) or re.search(SERIOUS, text, re.I)))


def unconfirmed(office: Office, now: datetime) -> list[tuple[str, str]]:
    """Viewings held for the broker past the owner's time for an answer, still ahead (docs/nova-office-alerts-spec.md)."""
    from diwan import slots, viewings
    g, wait = office.graph(), timedelta(minutes=viewings.settings(office.graph())["owner_minutes"])
    out = []
    for v in g.of("viewing", status="requested"):
        p = v.props
        asked = datetime.fromisoformat(p.get("moved_at") or v.at)
        if viewings.by_broker(v) and datetime.fromisoformat(p["at"]) > now and now - asked >= wait:
            hours = int((now - asked).total_seconds() // 3600)
            out.append((f"held:{v.id}:{p['at']}", f"{name(p['broker'])} hasn't confirmed {p.get('customer') or 'a client'}'s viewing of {p.get('listing')}, "
                        f"{slots.say(datetime.fromisoformat(p['at']))}. They asked {hours} hour{'' if hours == 1 else 's'} ago."))
    return out


def deliver(office: Office, owner: str, texts: list[str], urgent: bool, now: datetime) -> bool:
    """To the owner's WhatsApp on Nova's own line, only when they're away from the app; together as one message."""
    from diwan import novaline
    if not texts:
        return False
    words = {2: "Two", 3: "Three", 4: "Four", 5: "Five"}.get(len(texts), str(len(texts)))
    body = texts[0] if len(texts) == 1 else f"{words} things. " + " ".join(f"{i}. {t}" for i, t in enumerate(texts, 1))
    return novaline.push(office, body, "now" if urgent else "soon", now)


def alerts(office: Office, now: datetime | None = None) -> int:
    """Every minute: what the owner would want to hear the moment it happens. Once each; a thanks or a question doesn't interrupt
    them. Trouble goes at once; good news waits while they're in a meeting and outside the hours the owner allows messages. Away
    from the app, it reaches their WhatsApp on Nova's line (docs/nova-office-alerts-spec.md)."""
    now = now or datetime.now(DUBAI)
    from diwan import leads
    from diwan.agents import nudge
    told = 0
    g = office.graph()
    quiet = not nudge.allowed(nudge.settings(g), now)
    found = [(e, text, f"alert:{{o}}:{e['id']}") for e in office.log.list()
             if e["type"] in ALERTS and _since(e["at"], now) <= (HELD_FOR if e["type"] in GOOD and not trouble(e) else LOOKBACK) and (text := _alert(office, e))]
    said = {e["content"].get("chat") for e, _, _ in found if e["type"] != "notify.sent"}
    found = [f for f in found if not (f[0]["type"] == "notify.sent" and f[0]["content"].get("chat") in said)]  # one matter, one message
    found += [(None, text, f"alert:{{o}}:{key}") for key, text in unconfirmed(office, now)]
    for o in (p for p in PEOPLE if is_owner(p)):
        new, urgent = [], False
        for e, text, key in found:
            hard = e is not None and trouble(e)
            if not hard and (leads.resting(g, o) or quiet):
                continue  # good news keeps until they're out of the meeting, or the morning; trouble doesn't
            if e is not None and e["type"] == "notify.sent" and e["content"].get("to") != o:
                continue
            ev = office.log.append("nova.headsup", actor="nova", agent="nova", key=key.format(o=o), caused_by=e["id"] if e else None,
                                   content={"to": o, "text": text, "from_event": e["id"] if e else None})
            if not ev.get("duplicate"):
                told += 1
                new.append(text)
                urgent = urgent or hard
        deliver(office, o, new, urgent, now)
    return told


def headsups(log: EventLog, person: str, after: int) -> list[dict]:
    return [{"id": e["id"], "text": e["content"]["text"]} for e in log.list(after=after) if e["type"] == "nova.headsup" and e["content"]["to"] == person]


def lines(log: EventLog, person: str, now: datetime) -> list[str]:
    """What she has already done about it, so she can say so."""
    today = now.astimezone(DUBAI).date().isoformat()
    return [f"You chased {name(c['to'])} today by on-screen notice: {i['text']}" for e in log.list() if e["type"] == "nova.watched" and (c := e["content"])["day"] == today
            and (is_owner(person) or c["to"] == person) for i in c["items"]]
