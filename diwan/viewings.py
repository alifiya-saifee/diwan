"""Viewings by listing (docs/viewing-access-spec.md): a home someone lives in is never booked without the owner or tenant
agreeing; a vacant unit with keys at the office books at once; an off-plan unit is shown at the developer's gallery in
its hours. Rania holds the time asked for and the broker answers for the owner; the client is told either way."""
from __future__ import annotations

from datetime import datetime, timedelta

from diwan import slots
from diwan.graph import Graph, Node
from diwan.office import Office
from diwan.people import PEOPLE, name

MODES = {"instant": "Book at once", "ask": "Ask the owner first", "developer": "Developer's gallery"}
DEFAULTS = {"owner_minutes": 120, "notice_hours": 24}  # the broker's time to get an answer; a tenant's notice


def settings(g: Graph) -> dict:
    return DEFAULTS | (g.settings.get("sales", {}).get("viewings") or {})


def access(g: Graph, listing: Node) -> dict:
    """How this listing is viewed. Unset: a ready or rental home asks the owner first; off-plan is the developer's gallery."""
    a = dict(listing.props.get("access") or {})
    if a.get("mode") not in MODES:
        a = {"mode": "developer" if listing.props.get("completion") == "off_plan" else "ask", "default": True}
    if a["mode"] == "ask":
        a.setdefault("who", "owner")
        a.setdefault("notice_hours", settings(g)["notice_hours"] if a["who"] == "tenant" else 0)
    if a["mode"] == "developer":
        h = slots.hours(g)
        a.setdefault("place", f"the developer's sales gallery for {listing.props.get('project') or listing.props.get('community') or listing.props['title']}")
        a.setdefault("open", h["open"])
        a.setdefault("close", h["close"])
        a.setdefault("days", h["days"])
    return a | {"label": MODES[a["mode"]]}


def may_change(g: Graph, listing: Node, by: str) -> bool:
    from diwan import qualify
    return by in qualify.owner_ids() or PEOPLE.get(by, {}).get("role") == "Sales manager" or by == listing.props.get("agent")


def set_access(office: Office, ref: str, value: dict, *, by: str) -> dict:
    g = office.graph()
    listing = g.nodes.get(f"listing:{(ref or '').strip().upper()}")
    if not listing:
        raise ValueError(f"No listing {ref}")
    if not may_change(g, listing, by):
        raise PermissionError(f"Only the listing's broker ({name(listing.props.get('agent')) if listing.props.get('agent') else 'none set'}), "
                              "the Sales manager or the owner changes how it's viewed")
    mode = value.get("mode")
    if mode not in MODES:
        raise ValueError(f"Pick one: {', '.join(MODES.values())}")
    out = {"ref": listing.props["ref"], "mode": mode, "by": by}
    if mode == "ask":
        who = value.get("who") or "owner"
        if who not in ("owner", "tenant"):
            raise ValueError("Who lives there: the owner or a tenant")
        hours = int(value.get("notice_hours") if value.get("notice_hours") not in (None, "") else settings(g)["notice_hours"] if who == "tenant" else 0)
        if not 0 <= hours <= 168:
            raise ValueError("Notice is 0 to 168 hours")
        out |= {"who": who, "notice_hours": hours}
    elif mode == "developer":
        place = str(value.get("place") or "").strip()
        if not place:
            raise ValueError("Where is the gallery?")
        if slots._hm(value.get("open") or "") >= slots._hm(value.get("close") or ""):
            raise ValueError("Opening must be before closing")
        days = sorted({int(d) for d in value.get("days") or [] if 0 <= int(d) <= 6})
        if not days:
            raise ValueError("Open at least one day")
        out |= {"place": place[:200], "open": value["open"], "close": value["close"], "days": days}
    office.log.append("listing.access", actor=by, content=out)
    return access(office.graph(), office.graph().nodes[listing.id])


def allowed(g: Graph, listing: Node | None, t: datetime, minutes: int, now: datetime) -> bool:
    """A time this listing can be shown at: after a tenant's notice, and inside the gallery's hours for off-plan."""
    if listing is None:
        return True
    a = access(g, listing)
    if a["mode"] == "ask" and t < now + timedelta(hours=a["notice_hours"]):
        return False
    if a["mode"] == "developer":
        local = t.astimezone(slots.DUBAI)
        start = local.hour * 60 + local.minute
        return local.weekday() in a["days"] and slots._hm(a["open"]) <= start and start + minutes <= slots._hm(a["close"])
    return True


def agreed(g: Graph, chat: str, ref: str | None, t: datetime):
    """A time the owner already offered for this client and listing: booked at once when the client picks it."""
    return next((v for v in g.of("viewing", status="offered") if v.props.get("chat") == chat and v.props.get("listing") == ref
                 and t.isoformat() in (v.props.get("owner_ok") or [])), None)


def waiting(g: Graph, chat: str):
    """The viewing this client is waiting on the owner for, if any."""
    return next((v for v in g.of("viewing", status="requested") if v.props.get("chat") == chat), None)


def request(office: Office, phone: str, deal: str, listing: Node, when: datetime, k: dict, now: datetime, cause: int) -> tuple[str, list[str]]:
    """Hold the time on the broker's calendar and ask them to check with the owner; the client is told honestly."""
    from diwan import leads
    from diwan.agents import reception
    g = office.graph()
    broker = g.nodes[f"deal:{deal}"].props["broker"]
    chat = g.nodes[f"chat:{phone}"]
    vid = f"V{len(g.of('viewing')) + 1}"
    a = access(g, listing)
    ev = office.log.append("appointment.requested", actor=reception.RANIA, agent=reception.RANIA, deal=deal, caused_by=cause,
                           content={"id": vid, "listing": listing.props["ref"], "broker": broker, "at": when.isoformat(), "customer": chat.label,
                                    "chat": phone, "kind": k["id"], "kind_name": k["name"], "minutes": k["minutes"], "where": k["where"]})
    due = now + timedelta(minutes=settings(g)["owner_minutes"])
    leads.raise_card(office, phone, kind="reply", to=broker, cause=ev["id"], now=now, replace=True, due=due,
                     reason=f"Check with the {a['who']}: {chat.label} wants to view {listing.props['ref']} {slots.say(when)}")
    first = reception.first_name(chat.label)
    return (f"Thanks{' ' + first if first else ''}. {listing.props['title']} is lived in, so I'll check {slots.say(when)} with the owner "
            f"and confirm here as soon as they reply."), [listing.id, vid]


def answer(office: Office, vid: str, *, by: str, said: str, times: list[str] | None = None, now: datetime | None = None) -> dict:
    """The broker's answer for the owner: yes (booked), other times (offered to the client), or not possible."""
    from diwan import leads
    from diwan.agents import reception
    now = now or datetime.now(slots.DUBAI)
    g = office.graph()
    v = g.nodes.get(vid)
    if not v or v.type != "viewing":
        raise ValueError("No such viewing")
    if v.status != "requested":
        raise ValueError(f"It is already {v.status}")
    p = v.props
    slots._may(by, p["broker"])
    listing = g.nodes.get(f"listing:{p['listing']}")
    k = slots.kind(g, p.get("kind"))
    when = datetime.fromisoformat(p["at"])
    what = reception._what(g, k, listing)
    chat = g.nodes.get(f"chat:{p['chat']}")
    first = reception.first_name(chat.label) if chat else None
    hi, who = f"Hi {first}, " if first else "", viewings_who(g, listing)
    if said == "yes":
        if when <= now:
            raise ValueError("That time has passed: offer other times instead")
        ev = office.log.append("appointment.confirmed", actor=by, deal=v.deal, content={"id": vid, "by": by})
        office.add_task(v.deal, reception.RANIA, f"Viewing of {p['listing']} with {p.get('customer')}, {slots.say(when)}", needs_person=p["broker"], by=by, caused_by=ev["id"])
        text = f"Good news{', ' + first if first else ''}: the {who} confirmed. Booked: {what} with {name(p['broker'])}, {slots.say(when)}."
    elif said == "other":
        got = []
        for t in times or []:
            t = datetime.fromisoformat(t) if isinstance(t, str) else t
            if t.tzinfo is None:
                t = t.replace(tzinfo=slots.DUBAI)
            if t <= now:
                raise ValueError("Each time must be ahead")
            got.append(t)
        if not 1 <= len(got) <= 3:
            raise ValueError("Give one to three times the owner can do")
        got.sort()
        ev = office.log.append("appointment.offered", actor=by, deal=v.deal, content={"id": vid, "times": [t.isoformat() for t in got], "by": by})
        text = (f"{hi}the {who} can't do {slots.say(when)}, but {', '.join(slots.say(t) for t in got[:-1])}{' or ' if len(got) > 1 else ''}"
                f"{slots.say(got[-1])} works for them. Which suits you?")
    elif said == "no":
        ev = office.log.append("appointment.cancelled", actor=by, deal=v.deal, content={"id": vid, "by": "owner", "reason": "The owner can't host it then"})
        text = f"{hi}I'm sorry, {what} can't be shown {slots.say(when)}. {name(p['broker'])} will suggest other options for you here."
    else:
        raise ValueError("Answer yes, other times, or not possible")
    if card := leads.open_card(office.graph(), p["chat"]):
        leads.clear(office, card.id, "called", by=by, note={"yes": "The owner said yes", "other": "The owner offered other times", "no": "Not possible"}[said])
    return {"id": vid, "told": tell(office, p["chat"], text, vid, by, ev["id"], now), "text": text}


def viewings_who(g: Graph, listing: Node | None) -> str:
    return access(g, listing)["who"] if listing else "owner"


def tell(office: Office, phone: str, msg: str, vid: str, by: str, cause: int, now: datetime) -> str:
    """Inside their 24 hours a plain message; after it no template fits, so the broker is asked to tell them by phone."""
    from diwan import inbox, leads
    from diwan.agents import reception
    g = office.graph()
    chat = g.nodes.get(f"chat:{phone}")
    if not chat:
        return "no_chat"
    text = msg
    if not inbox.conversation(g, chat, now)["window_open"]:
        leads.raise_card(office, phone, kind="call", to=g.nodes[f"deal:{chat.deal}"].props["broker"], cause=cause, now=now,
                         reason=f"Tell the client by phone (more than 24 hours since they wrote): {msg[:160]}")
        return "card"
    reception._send(office, phone, chat.deal, text, [vid], by=by, cause=cause)
    return "sent"
