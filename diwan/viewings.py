"""Viewings by listing (docs/viewing-access-spec.md): a home someone lives in is never booked without the owner or tenant
agreeing; a vacant unit with keys at the office books at once; an off-plan unit is shown at the developer's gallery in
its hours. Rania holds the time asked for and the broker answers for the owner; the client is told either way."""
from __future__ import annotations

import re
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


def waiting(g: Graph, chat: str, now: datetime | None = None):
    """The next viewing this client is waiting on a confirmation for, if any; one whose time has passed isn't."""
    now = now or datetime.now(slots.DUBAI)
    return next(iter(sorted((v for v in g.of("viewing", status="requested") if v.props.get("chat") == chat and datetime.fromisoformat(v.props["at"]) > now),
                            key=lambda v: v.props["at"])), None)


def request(office: Office, phone: str, deal: str, listing: Node, when: datetime, k: dict, now: datetime, cause: int,
            broker_confirms: bool = False) -> tuple[str, list[str]]:
    """Hold the time on the broker's calendar until they confirm it with the client (the owner's rule), or check it with
    the owner when someone lives there; the client is told honestly (docs/agent-confirms-spec.md)."""
    from diwan import leads
    from diwan.agents import reception
    g = office.graph()
    broker = g.nodes[f"deal:{deal}"].props["broker"]
    chat = g.nodes[f"chat:{phone}"]
    vid = f"V{len(g.of('viewing')) + 1}"
    a = access(g, listing)
    title = f"{listing.props['title']} ({listing.props['ref']})"
    ev = office.log.append("appointment.requested", actor=reception.RANIA, agent=reception.RANIA, deal=deal, caused_by=cause,
                           content={"id": vid, "listing": listing.props["ref"], "broker": broker, "at": when.isoformat(), "customer": chat.label,
                                    "chat": phone, "kind": k["id"], "kind_name": k["name"], "minutes": k["minutes"], "where": k["where"],
                                    "confirm": "broker" if broker_confirms else a["who"]})
    if broker_confirms:
        office.log.append("viewing.requested", actor=reception.RANIA, agent=reception.RANIA, deal=deal, caused_by=ev["id"],
                          content={"chat": phone, "listing": listing.props["ref"], "at": when.isoformat(), "id": vid})
        lives = f" Someone lives there: check with the {a['who']} too." if a["mode"] == "ask" else ""
        also = [f"{x.props['listing']}, {slots.say(datetime.fromisoformat(x.props['at']))}" for x in office.graph().of("viewing", status="requested")
                if x.props.get("chat") == phone and x.id != vid and datetime.fromisoformat(x.props["at"]) > now]  # one card: every request open
        leads.raise_card(office, phone, kind="reply", to=broker, cause=ev["id"], now=now, replace=True,
                         reason=f"Viewing request: {title}, {slots.say(when)}{' (also asked: ' + '; '.join(also) + ')' if also else ''}. "
                                f"Talk to the client, confirm the place, then book.{lives}")
        if re.search(r"[\u0600-\u06ff]", next((m["text"] for m in reversed(chat.props["messages"]) if m["type"] == "received"), "")):
            return f"شكراً، سجلت رغبتك في رؤية {title} {slots.say(when)}. سيتحدث معك {name(broker)} ليؤكد العقار والموعد.", [listing.id, vid]
        return (f"Thanks, I've noted you'd like to see {title}, {slots.say(when)}. {name(broker)} will talk to you and confirm the "
                f"place and the time."), [listing.id, vid]
    due = now + timedelta(minutes=settings(g)["owner_minutes"])
    leads.raise_card(office, phone, kind="reply", to=broker, cause=ev["id"], now=now, replace=True, due=due,
                     reason=f"Check with the {a['who']}: {chat.label} wants to view {listing.props['ref']} {slots.say(when)}")
    first = reception.first_name(chat.label)
    return (f"Thanks{' ' + first if first else ''}. {listing.props['title']} is lived in, so I'll check {slots.say(when)} with the owner "
            f"and confirm here as soon as they reply."), [listing.id, vid]


def by_broker(v: Node) -> bool:
    """Held for the broker to confirm with the client (the owner's rule), not for an owner or tenant to agree."""
    return v.props.get("confirm") == "broker"


def held_line(g: Graph, v: Node, it: bool = False, arabic: bool = False) -> str:
    """What the client hears about a held viewing: who confirms it, and when they asked for (`it`: the time was just said)."""
    at = slots.say(datetime.fromisoformat(v.props["at"]))
    if arabic:
        return (f"سيؤكد {name(v.props['broker'])} الموعد معك" + ("" if it else f" ({at})") if by_broker(v) else
                "أنتظر تأكيد المالك" + ("" if it else f" للموعد ({at})"))
    at = "it" if it else at
    if by_broker(v):
        return f"{name(v.props['broker'])} will confirm {at} with you"
    return f"I'm waiting for the {v.props.get('confirm') or 'owner'} to confirm {at}"


def answer(office: Office, vid: str, *, by: str, said: str, times: list[str] | None = None, now: datetime | None = None) -> dict:
    """The broker's answer for the owner: yes (booked), other times (offered to the client), or not possible."""
    from diwan import inbox, leads
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
    broker_ = by_broker(v)
    who_ = name(p["broker"]) if broker_ else f"the {who}"
    if said == "yes":
        if when <= now:
            raise ValueError("That time has passed: offer other times instead")
        ev = office.log.append("appointment.confirmed", actor=by, deal=v.deal, content={"id": vid, "by": by})
        office.add_task(v.deal, reception.RANIA, f"Viewing of {p['listing']} with {p.get('customer')}, {slots.say(when)}", needs_person=p["broker"], by=by, caused_by=ev["id"])
        inbox.auto_stage(office, v.deal, cause=ev["id"])
        text = (f"Good news{', ' + first if first else ''}: " + ("it's confirmed. " if broker_ else f"the {who} confirmed. ")
                + f"Booked: {what} with {name(p['broker'])}, {slots.say(when)}{place(g, listing)}.")
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
        text = (f"{hi}{who_} can't do {slots.say(when)}, but {', '.join(slots.say(t) for t in got[:-1])}{' or ' if len(got) > 1 else ''}"
                f"{slots.say(got[-1])} works{'' if broker_ else ' for them'}. Which suits you?")
    elif said == "no":
        ev = office.log.append("appointment.cancelled", actor=by, deal=v.deal, content={"id": vid, "by": "broker" if broker_ else "owner",
                               "reason": "Not available to view then" if broker_ else "The owner can't host it then"})
        text = f"{hi}I'm sorry, {what} can't be shown {slots.say(when)}. {name(p['broker'])} will suggest other options for you here."
    else:
        raise ValueError("Answer yes, other times, or not possible")
    if card := leads.open_card(office.graph(), p["chat"]):
        leads.clear(office, card.id, "called", by=by, note={"yes": "The owner said yes", "other": "The owner offered other times", "no": "Not possible"}[said])
    return {"id": vid, "told": tell(office, p["chat"], text, vid, by, ev["id"], now), "text": text}


def place(g: Graph, listing: Node | None) -> str:
    """Where to meet, when it isn't the home itself: the developer's gallery for off-plan."""
    a = access(g, listing) if listing else {}
    return f" at {a['place']}" if a.get("mode") == "developer" else ""


def viewings_who(g: Graph, listing: Node | None) -> str:
    return access(g, listing).get("who", "owner") if listing else "owner"


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
