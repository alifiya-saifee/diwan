"""The lead desk: who owns each lead, what needs a person and by when, and who is told.

The rules a busy sales floor runs on:
- A new lead goes to the agent of the listing it is about; otherwise round-robin among brokers who are on shift and
  not away, fewest leads today first. Nobody on shift: the least busy broker who is not away.
- Anything Rania hands to a person becomes an Attention card with a due time: 15 minutes when the customer asked for a
  call or came from a portal, 30 minutes otherwise.
- A card leaves Attention only with a recorded action: called, messaged, no answer, or not needed with a reason.
  A person replying in the chat counts as "messaged".
- Past due: the card is marked overdue and the owner hears. An hour after it was raised with nothing done, the lead
  goes to the Pool, where any broker on shift can claim it.
- Every assignment, card, overdue and pool move is a notice to the person on their screen, and on their own WhatsApp
  when a notify template is set (WhatsApp only lets a business start a conversation with an approved template).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.config import env
from diwan.graph import Graph
from diwan.office import Office
from diwan.people import PEOPLE, name
from diwan.slots import DUBAI

CALL = r"\b(call|phone|ring|speak to|talk to)\b|اتصل|كلمني"
ACTIONS = {"called": "Called", "messaged": "Messaged", "no_answer": "No answer", "not_needed": "Not needed"}
DEFAULT_SHIFT = "09:00-21:00"


def due_minutes(kind: str) -> int:
    return int(env("DIWAN_CALL_MINUTES", "15")) if kind == "call" else int(env("DIWAN_REPLY_MINUTES", "30"))


def pool_minutes() -> int:
    return int(env("DIWAN_POOL_MINUTES", "60"))


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


# ---------- the team ----------

def brokers() -> list[str]:
    return [p for p, v in PEOPLE.items() if v["role"] == "Broker"]


def setting(g: Graph, person: str, key: str, default=None):
    return g.settings.get(person, {}).get(key, default)


def set_agent(office: Office, person: str, key: str, value, *, by: str) -> None:
    """A broker's shift ("10:00-19:00"), working days (0 = Monday), whether they are away today, and the WhatsApp number
    notices go to."""
    if person not in brokers():
        raise ValueError(f"{person} is not a broker")
    if key == "days":
        try:
            value = sorted({int(d) for d in value or []})
        except (TypeError, ValueError):
            raise ValueError("Working days: numbers 0 (Monday) to 6 (Sunday)") from None
        if not value or not all(0 <= d <= 6 for d in value):
            raise ValueError("Pick at least one working day")
    if key == "shift" and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d", value or ""):
        raise ValueError("Use a shift like 10:00-19:00")
    if key == "phone":
        value = re.sub(r"\D", "", value or "")
    if key not in ("shift", "days", "away", "phone"):
        raise ValueError(f"not a team setting: {key}")
    office.log.append("setting.changed", actor=by, content={"person": person, "key": key, "value": value})


def on_shift(g: Graph, person: str, now: datetime) -> bool:
    if setting(g, person, "away"):
        return False
    if (days := setting(g, person, "days")) is not None and now.astimezone(DUBAI).weekday() not in days:
        return False  # a day off
    start, end = setting(g, person, "shift", DEFAULT_SHIFT).split("-")
    t = now.astimezone(DUBAI).strftime("%H:%M")
    return start <= t < end if start <= end else (t >= start or t < end)


def load_today(g: Graph, person: str, now: datetime) -> int:
    day = now.astimezone(DUBAI).date()
    return sum(1 for d in g.deals() if d.props.get("broker") == person and d.props.get("assigned_at")
               and _at(d.props["assigned_at"]).astimezone(DUBAI).date() == day)


def team(g: Graph, now: datetime) -> list[dict]:
    return [{"id": p, "name": name(p), "shift": setting(g, p, "shift", DEFAULT_SHIFT), "away": bool(setting(g, p, "away")),
             "days": setting(g, p, "days"), "phone": bool(setting(g, p, "phone")), "on_shift": on_shift(g, p, now), "leads_today": load_today(g, p, now)}
            for p in brokers()]


def pick(g: Graph, now: datetime, listing: str | None = None, exclude: str | None = None,
         among: list[str] | None = None) -> tuple[str, str]:
    """(broker, why). The listing's own agent first, then round-robin among brokers on shift. `among`: only these
    brokers (a deal kind's)."""
    team_ = [p for p in brokers() if not among or p in among] or brokers()
    if listing and (n := g.nodes.get(f"listing:{listing}")) and (agent := n.props.get("agent")) in team_:
        if on_shift(g, agent, now) and agent != exclude:
            return agent, f"agent of listing {listing}"
    pool = [p for p in team_ if p != exclude and on_shift(g, p, now)]
    why = "round-robin, on shift"
    if not pool:
        pool, why = [p for p in team_ if p != exclude and not setting(g, p, "away")] or team_, "nobody on shift: least busy"
    order = brokers()
    return min(pool, key=lambda p: (load_today(g, p, now), order.index(p))), why


def assign(office: Office, deal: str, to: str, *, by: str, why: str, cause: int | None = None, chat: str | None = None,
           now: datetime | None = None) -> dict:
    """`now` is the moment the decision was made: today's lead counts per broker are read from it, not the clock."""
    ev = office.log.append("lead.assigned", actor=by, agent="rania" if by == "rania" else None, deal=deal, caused_by=cause,
                           content={"to": to, "why": why, "chat": chat, "at": (now or datetime.now(timezone.utc)).isoformat()})
    who = office.graph().nodes[f"deal:{deal}"].props.get("customer", deal)
    notify(office, to, f"New lead: {who} ({why}).", chat=chat, kind="lead", cause=ev["id"])
    return ev


# ---------- attention ----------

def open_card(g: Graph, chat: str) -> object | None:
    return next((n for n in g.of("attention", status="open") if n.props["chat"] == chat), None)


def raise_card(office: Office, chat: str, *, reason: str, text: str = "", to: str | None = None, kind: str | None = None,
               cause: int | None = None, now: datetime | None = None, replace: bool = False, due: datetime | None = None) -> str | None:
    """One open card per conversation. A call request on a conversation that already has a card makes it a call;
    replace=True puts a new reason in place of the open card (a lead that has just qualified)."""
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    ch = g.nodes[f"chat:{chat}"]
    kind = kind or ("call" if re.search(CALL, text.lower()) else "reply")
    if kind == "call" and no_calls(g, ch.deal):  # they asked not to be called: the broker replies in the chat instead
        kind, reason = "reply", f"No calls (they asked): {reason}"
    to = to or g.nodes[f"deal:{ch.deal}"].props["broker"]
    if (cur := open_card(g, chat)) and not replace and not (kind == "call" and cur.props["kind"] != "call"):
        return None
    due = due or now + timedelta(minutes=due_minutes(kind))  # a call the client asked for at a time is due then
    ev = office.log.append("attention.raised", actor="rania", agent="rania", deal=ch.deal, caused_by=cause,
                           content={"chat": chat, "kind": kind, "reason": reason, "who": to, "raised": now.isoformat(),
                                    "due": due.isoformat(), "replaces": cur.id if cur else None})
    what = "wants a call" if kind == "call" else "needs a reply"
    notify(office, to, f"{ch.label} {what}: {reason}. Due {due.astimezone(DUBAI):%H:%M}.", chat=chat, kind=kind, cause=ev["id"])
    return f"AT{ev['id']}"


def clear(office: Office, card: str, action: str, *, by: str, note: str = "") -> dict:
    """Nothing leaves Attention without a recorded action."""
    if action not in ACTIONS:
        raise ValueError(f"Say what was done: {', '.join(ACTIONS)}")
    if action == "not_needed" and not note.strip():
        raise ValueError("Say why it is not needed")
    n = office.graph().nodes.get(card)
    if not n or n.type != "attention":
        raise KeyError(card)
    if n.status != "open":
        raise ValueError(f"{card} is already {n.status}")
    return office.log.append("attention.cleared", actor=by, deal=n.deal, key=f"clear:{card}",
                             content={"id": card, "chat": n.props["chat"], "action": action, "note": note.strip()})


def replied(office: Office, chat: str, *, by: str, cause: int | None = None) -> None:
    """A person answered in the chat: their card is done."""
    if card := open_card(office.graph(), chat):
        office.log.append("attention.cleared", actor=by, deal=card.deal, caused_by=cause, key=f"clear:{card.id}",
                          content={"id": card.id, "chat": chat, "action": "messaged", "note": ""})


def sweep(office: Office, now: datetime | None = None) -> list[str]:
    """Run every minute. Past due: overdue, and the owner hears. An hour with nothing done: the lead goes to the Pool."""
    now = now or datetime.now(timezone.utc)
    out = []
    for c in office.graph().of("attention", status="open"):
        p, g = c.props, office.graph()
        label = g.nodes[f"chat:{p['chat']}"].label
        if not p.get("pooled") and now >= _at(p.get("raised") or c.at) + timedelta(minutes=pool_minutes()):
            ev = office.log.append("lead.pooled", actor="rania", agent="rania", deal=c.deal, key=f"pool:{c.id}",
                                   content={"id": c.id, "chat": p["chat"], "from": p["who"]})
            for b in brokers():
                if b != p["who"] and on_shift(g, b, now):
                    notify(office, b, f"Lead available to claim: {label} ({p['reason']}). {name(p['who'])} has not acted in "
                                      f"{pool_minutes()} minutes.", chat=p["chat"], kind="pool", cause=ev["id"])
            out.append(f"pooled {c.id}")
        elif not p.get("overdue") and now >= _at(p["due"]):
            ev = office.log.append("attention.overdue", actor="rania", agent="rania", deal=c.deal, key=f"overdue:{c.id}",
                                   content={"id": c.id, "chat": p["chat"]})
            notify(office, p["who"], f"Overdue: {label} ({p['reason']}).", chat=p["chat"], kind="overdue", cause=ev["id"])
            notify(office, "layla", f"{name(p['who'])} is late on {label}: {p['reason']}.", chat=p["chat"], kind="overdue", cause=ev["id"])
            out.append(f"overdue {c.id}")
    return out


def claim(office: Office, chat: str, *, by: str) -> dict:
    g = office.graph()
    card = open_card(g, chat)
    if not card or not card.props.get("pooled"):
        raise ValueError("This lead is not in the Pool")
    if by not in brokers():
        raise ValueError(f"{name(by)} is not a broker")
    ev = office.log.append("lead.claimed", actor=by, deal=card.deal, key=f"claim:{card.id}",
                           content={"id": card.id, "chat": chat, "to": by, "from": card.props["who"]})
    notify(office, card.props["who"], f"{name(by)} claimed {g.nodes[f'chat:{chat}'].label} from the Pool.", chat=chat, kind="pool", cause=ev["id"])
    return ev


def reassign(office: Office, chat: str, to: str, *, by: str) -> dict:
    """A manager moves a lead, or a broker covers for a colleague. Its open card goes with it (the graph moves it)."""
    if to not in brokers():
        raise ValueError(f"{name(to)} is not a broker")
    ch = office.graph().nodes[f"chat:{chat}"]
    return assign(office, ch.deal, to, by=by, why=f"moved by {name(by)}", chat=chat)


def _may_act(g: Graph, deal: str, by: str) -> None:
    from diwan import qualify
    if by != g.nodes[f"deal:{deal}"].props.get("broker") and by not in qualify.owner_ids():
        raise PermissionError(f"Only {name(g.nodes[f'deal:{deal}'].props.get('broker'))} (the broker) or the owner does this")


def no_calls(g: Graph, deal: str | None) -> bool:
    return bool(deal and f"deal:{deal}" in g.nodes and g.nodes[f"deal:{deal}"].props.get("no_calls"))


def set_no_calls(office: Office, chat: str, *, on: bool, by: str, quote: str | None = None) -> None:
    """The client asked not to be called: Rania never offers or promises a call, and call cards become reply cards. Set by
    the broker (or the owner); turned off by Rania when the client asks for a call themselves."""
    g = office.graph()
    deal = g.nodes[f"chat:{chat}"].deal
    if by != "rania":
        _may_act(g, deal, by)
    if no_calls(g, deal) == on:
        return
    ev = office.log.append("lead.no_calls", actor=by, deal=deal, content={"on": on, "chat": chat, "quote": (quote or "")[:300] or None})
    broker = g.nodes[f"deal:{deal}"].props.get("broker")
    if by != broker:
        label = g.nodes[f"chat:{chat}"].label
        notify(office, broker, f"{label} asked for a call, so \u201cno calls\u201d is off: \u201c{(quote or '')[:120]}\u201d" if by == "rania" and not on
               else f"{name(by)} set \u201c{'no calls' if on else 'calls are fine'}\u201d for {label}.", chat=chat, kind="info", cause=ev["id"])


def merge(office: Office, into: str, other: str, *, by: str) -> dict:
    """The same person wrote on two numbers or accounts (Instagram and WhatsApp, say): one lead from now on. Both
    histories show in this lead's thread; answers this lead lacks are taken from the other; the other lead closes as
    merged, and anything they send there arrives here."""
    g = office.graph()
    if into == other:
        raise ValueError("Pick a different conversation")
    a, b = g.nodes.get(f"chat:{into}"), g.nodes.get(f"chat:{other}")
    if not a or not b:
        raise ValueError("No such conversation")
    if a.props.get("merged_into") or b.props.get("merged_into"):
        raise ValueError(f"{(b if b.props.get('merged_into') else a).label} is already merged into another lead")
    _may_act(g, a.deal, by)
    ev = office.log.append("chat.merged", actor=by, deal=a.deal, content={"into": into, "from": other, "from_deal": b.deal})
    da = g.nodes[f"deal:{a.deal}"].props
    db = g.nodes[f"deal:{b.deal}"].props if b.deal and f"deal:{b.deal}" in g.nodes else {}
    src = f"from {b.label}'s other conversation"
    if db.get("qtype") and not da.get("qtype"):
        office.log.append("qualify.type", actor=by, agent="rania", deal=a.deal, caused_by=ev["id"],
                          content={"type": db["qtype"], "quote": db.get("qtype_quote"), "source": src})
    for k, v in (db.get("answers") or {}).items():
        if k not in (da.get("answers") or {}):
            office.log.append("qualify.answer", actor=by, agent="rania", deal=a.deal, caused_by=ev["id"],
                              content={"field": k, "value": v["value"], "quote": v.get("quote"), "unsure": v.get("unsure"), "source": src})
    if b.deal and b.deal != a.deal:
        office.log.append("stage.changed", actor=by, deal=b.deal, caused_by=ev["id"],
                          content={"stage": "Lost", "auto": True, "reason": f"merged into {a.label} ({into})"})
        if (card := open_card(office.graph(), other)) is not None:
            clear(office, card.id, "not_needed", by=by, note=f"merged into {a.label}")
        if db.get("broker") and db["broker"] not in (by, da.get("broker")):
            notify(office, db["broker"], f"{name(by)} merged {b.label}'s conversation into {a.label}'s lead ({name(da.get('broker'))}).",
                   chat=into, kind="info", cause=ev["id"])
    from diwan import inbox
    inbox.auto_stage(office, a.deal, cause=ev["id"])  # their answers may move this lead on (Qualifying, Qualified)
    return {"into": into, "from": other}


def mark_hot(office: Office, chat: str, *, on: bool, by: str, note: str = "") -> None:
    """The broker marks a lead hot, or not; the broker hears when someone else does."""
    g = office.graph()
    deal = g.nodes[f"chat:{chat}"].deal
    _may_act(g, deal, by)
    d = g.nodes[f"deal:{deal}"].props
    if on:
        ev = office.log.append("lead.hot", actor=by, deal=deal, content={"listing": (d.get("hot") or {}).get("listing"), "why": f"marked by {name(by)}",
                                                                          "quote": note.strip()[:300] or None, "chat": chat})
    else:
        ev = office.log.append("lead.unhot", actor=by, deal=deal, content={"note": note.strip()[:300] or None, "chat": chat})
    if by != d.get("broker"):
        notify(office, d["broker"], f"{name(by)} marked {g.nodes[f'chat:{chat}'].label} {'hot' if on else 'not hot'}.", chat=chat, kind="info", cause=ev["id"])


def follow_up_on(office: Office, chat: str, *, by: str, at: datetime, kind: str, note: str, now: datetime) -> str:
    """Follow up on a date: a card for the broker due then (overdue and the Pool like any card). Nothing reaches the client."""
    from diwan import slots
    g = office.graph()
    deal = g.nodes[f"chat:{chat}"].deal
    _may_act(g, deal, by)
    if kind not in ("call", "reply"):
        raise ValueError("A call or a message")
    if at <= now:
        raise ValueError("Pick a day and time ahead")
    if cur := open_card(g, chat):
        raise ValueError(f"This lead already has an open card: {cur.props['reason'][:80]} (due "
                         f"{datetime.fromisoformat(cur.props['due']).astimezone(DUBAI):%a %d %b %H:%M}). Clear it first.")
    to = g.nodes[f"deal:{deal}"].props["broker"]
    ev = office.log.append("attention.raised", actor=by, deal=deal,
                           content={"chat": chat, "kind": kind, "reason": f"Follow up {slots.say(at)}" + (f": {note.strip()[:200]}" if note.strip() else ""),
                                    "who": to, "raised": now.isoformat(), "due": at.isoformat(), "replaces": None, "set_by": by})
    if by != to:
        notify(office, to, f"{name(by)} set a follow-up for {g.nodes[f'chat:{chat}'].label}, {slots.say(at)}.", chat=chat, kind="info", cause=ev["id"])
    return f"AT{ev['id']}"


# ---------- the catalog and portal enquiries ----------

def _agent(item: dict) -> str | None:
    from diwan.people import pid
    for v in (item.get("agent_name"), (item.get("agent_email") or "").split("@")[0].replace(".", " ")):
        if v and (p := pid(v.split()[0] if " " in v else v)) in brokers():
            return p
    return None


FEED_FIELDS = ("title", "community", "type", "beds", "price_aed", "permit", "agent", "offering")
MEDIA = ("photos", "lat", "lng", "description", "size_sqft", "completion", "project")  # nobody edits these here: the feed always wins


def sync_listings(office: Office, xml: bytes | str, *, by: str = "portal-feed") -> dict:
    """Bring the listings in line with the brokerage's portal feed (the feed is the truth for what is advertised), without
    undoing what people decided here:
    - a status a person set (reserved, sold, retired) is kept; a listing that left the feed is off-market, and back when it returns;
    - a change accepted here that the portal has not caught up with (e.g. a new price) is kept and marked "waiting for
      the portal", and the listing's agent gets a task to update the portal; it clears when the feed shows it;
    - if the portal itself moves a field to a new value, the feed wins.
    Each listing keeps a snapshot of what the feed last said, so "not caught up yet" and "changed on the portal" differ.
    Listings typed in by hand are never touched."""
    from diwan.providers import portals
    items = portals.parse_feed(xml)
    g = office.graph()
    seen, added, changed, waiting = set(), 0, 0, []
    for it in items:
        seen.add(it["ref"])
        feed = {"title": it["title"], "community": it["community"], "type": it["type"], "beds": it["beds"], "price_aed": it["price_aed"],
                "permit": it["permit"], "agent": _agent(it), "offering": it["offering"]}
        geo = it.get("geo") or (None, None)
        media = {k: v for k, v in {"photos": it.get("photos") or [], "lat": geo[0], "lng": geo[1], "description": it.get("description"),
                                   "size_sqft": it.get("size_sqft"), "completion": it.get("completion"), "project": it.get("project")}.items()
                 if v not in (None, [])}
        cur = g.nodes.get(f"listing:{it['ref']}")
        if cur is None:
            office.log.append("listing.added", actor=by, content={"ref": it["ref"], **feed, **media, "status": "available", "features": [],
                                                                  "source": "feed", "feed": feed})
            added += 1
            continue
        last = cur.props.get("feed") or {}
        rec, pending = {}, {}
        for k in FEED_FIELDS:
            ours = cur.props.get(k)
            if feed[k] == ours:
                continue
            if last and feed[k] == last.get(k) and cur.props.get("edited_at"):
                pending[k] = {"ours": ours, "portal": feed[k]}  # accepted here; the portal still shows the old value
            else:
                rec[k] = feed[k]  # the portal changed it (or there is nothing of ours to keep): the feed wins
        rec |= {k: v for k, v in media.items() if cur.props.get(k) != v}
        status = "available" if cur.status == "off-market" else None  # back in the feed; a person's status is kept
        if cur.status in ("reserved", "sold", "retired"):  # set here, but the portal still advertises it
            pending["status"] = {"ours": cur.status, "portal": "advertised"}
        was = cur.props.get("portal_pending") or {}
        if not rec and status is None and pending == was and feed == last:
            continue
        content = {"ref": it["ref"], **rec, "feed": feed, "portal_pending": pending}
        if status:
            content["status"] = status
        office.log.append("listing.added", actor=by, content=content)
        changed += bool(rec or status)
        new = {k: v for k, v in pending.items() if k not in was}
        if new:
            waiting.append(it["ref"])
            agent = cur.props.get("agent") or "omar"
            what = "; ".join(f"it is {v['ours']} here but still advertised: take it off the portals" if k == "status"
                             else f"{k.replace('_aed', '').replace('_', ' ')} AED {v['ours']:,} here, AED {v['portal']:,} on the portal" if k == "price_aed"
                             else f"{k} {v['ours']} here, {v['portal']} on the portal" for k, v in new.items())
            office.add_task(None, "sales", f"Update {it['ref']} on the portals: {what}", needs_person=agent, by=by)
            notify(office, agent, f"{it['ref']} is waiting for the portal: {what}.", kind="info")
    gone = [n for n in g.of("listing") if n.props.get("source") == "feed" and n.props["ref"] not in seen and n.status == "available"]
    for n in gone:
        office.log.append("listing.added", actor=by, content={"ref": n.props["ref"], "status": "off-market"})
    summary = {"in_feed": len(items), "added": added, "changed": changed, "off_market": len(gone),
               "without_permit": sum(1 for it in items if not it["permit"]), "waiting_for_portal": waiting}
    office.log.append("listings.synced", actor=by, content=summary)
    return summary


def portal_lead(office: Office, lead: dict, now: datetime | None = None) -> dict:
    """An enquiry from a portal. It joins the customer's conversation (or starts one), goes to the listing's agent, and
    becomes a call card: portal buyers expect a call. Rania does not message them first: WhatsApp allows a business to
    open a conversation only with an approved template, so the broker calls or sends one."""
    from diwan.agents import scribe
    from diwan.providers import portals
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    phone, label = lead["phone"], lead.get("name") or f"+{lead['phone']}"
    listing = g.nodes.get(f"listing:{lead['ref']}") if lead.get("ref") else None
    ch = g.nodes.get(f"chat:{phone}")
    deal = ch.deal if ch and ch.deal else None
    if not deal:
        to, why = pick(g, now, listing=lead.get("ref"))
        deal = f"lead-{phone[-8:]}"
        office.open_deal(deal, property=listing.label if listing else f"{portals.PORTALS[lead['portal']]} enquiry",
                         customer=label, broker=to, by=lead["portal"])
        assign(office, deal, to, by="rania", why=why, chat=phone, now=now)
    portal = portals.PORTALS[lead["portal"]]
    text = lead["message"] or f"Enquiry about {lead.get('ref') or 'a listing'}"
    got = office.log.append("chat.received", actor=f"customer:{phone}", deal=deal,
                            content={"chat": phone, "name": label, "text": text, "channel": lead["portal"], "ref": lead.get("ref"),
                                     "email": lead.get("email")})
    heard = scribe.hear(office, deal, office.graph().nodes[f"deal:{deal}"].props["customer"], text, got["id"])
    about = f" about {listing.label} ({lead['ref']})" if listing else f" about {lead['ref']}" if lead.get("ref") else ""
    filled = from_listing(office, deal, listing, text, cause=got["id"]) if listing else []
    card = raise_card(office, phone, reason=f"New {portal} enquiry{about}", text=text, kind="call", cause=got["id"], now=now)
    sent = _portal_hello(office, phone, deal, label, listing, got["id"])
    return {"deal": deal, "chat": phone, "card": card, "facts": heard["facts"], "filled": filled, "template": sent}


def from_listing(office: Office, deal: str, listing, text: str, *, cause: int | None = None) -> list[str]:
    """An enquiry about a listing already tells us what they are after: buying or renting, the area, the type and the
    bedrooms (never the budget: the asking price is not theirs). Each answer is marked as coming from the listing, and
    Rania then asks only what is still missing. Answers the customer gave themselves are never replaced."""
    from diwan import qualify
    g = office.graph()
    d, f, p = g.nodes[f"deal:{deal}"].props, qualify.form(g), listing.props
    src = f"from the listing they enquired about ({p['ref']})"
    qtype = d.get("qtype") or {"rent": "tenant", "sale": "buyer"}.get(p.get("offering") or "sale")
    if qtype not in f["types"]:
        return []
    if not d.get("qtype"):
        office.log.append("qualify.type", actor="portal", agent="rania", deal=deal, caused_by=cause, content={"type": qtype, "quote": text[:300], "source": src})
    keys = {x["key"] for x in qualify.fields_for(f, qtype)}
    values = {"areas": p.get("community"), "property_type": (p.get("type") or "").title() or None, "bedrooms": p.get("beds")}
    out = []
    for k, v in values.items():
        if k in keys and v not in (None, "") and k not in d.get("answers", {}):
            office.log.append("qualify.answer", actor="portal", agent="rania", deal=deal, caused_by=cause,
                              content={"field": k, "value": v, "quote": text[:300], "source": src})
            out.append(k)
    return out


def _portal_hello(office: Office, phone: str, deal: str, label: str, listing, cause: int) -> str | None:
    """The first message to a portal lead, when the owner picked an approved template (WhatsApp lets a business open
    a conversation only with one). Its variables are filled in order: first name, the property, the broker. The
    broker's call card stays: portal buyers expect a call."""
    from diwan import inbox
    from diwan.agents import reception
    g = office.graph()
    name_ = reception.front_settings(g)["portal_template"]
    t = next((t for t in inbox.templates() if t["name"] == name_), None) if name_ else None
    if not t or any(m["type"] == "sent" for m in g.nodes[f"chat:{phone}"].props["messages"]):
        return None
    vals = [reception.first_name(label) or "there", listing.props["title"] if listing else "your enquiry", name(g.nodes[f"deal:{deal}"].props["broker"])]
    params = vals[:int(t.get("params") or 0)]
    reception._send(office, phone, deal, inbox.render(t["body"], params), [listing.id] if listing else [], cause=cause,
                    template={"name": t["name"], "params": params, "language": t.get("language", "en")})
    return t["name"]


# ---------- notices ----------

def notify(office: Office, person: str, text: str, *, chat: str | None = None, kind: str = "info", cause: int | None = None) -> dict:
    """On screen always. On the person's own WhatsApp when they have a number and NOTIFY_TEMPLATE names an approved
    AiSensy template with one variable; the send result is kept on the notice, never retried silently."""
    from diwan.providers import aisensy
    via, status, err = "screen", "shown", None
    phone = setting(office.graph(), person, "phone")
    from diwan.config import sandbox_only
    if phone and env("NOTIFY_TEMPLATE") and aisensy.available() and not sandbox_only():
        via = "whatsapp"
        try:
            aisensy.send_template(phone, env("NOTIFY_TEMPLATE"), [text[:900]], "en")
            status = "sent"
        except Exception as e:
            status, err = "failed", str(e)[:200]
    return office.log.append("notify.sent", actor="rania", agent="rania", caused_by=cause,
                             content={"to": person, "text": text, "chat": chat, "kind": kind, "via": via, "status": status, "error": err})


def notices(g: Graph, person: str, limit: int = 30) -> list[dict]:
    ns = [n for n in g.of("notice") if n.props["to"] == person]
    return [{"id": n.id, "at": n.at, "read": n.status == "read"} | {k: n.props.get(k) for k in ("text", "chat", "kind", "via", "status")}
            for n in reversed(ns[-limit:])]


def read_all(office: Office, person: str) -> None:
    unread = [n.id for n in office.graph().of("notice", status="new") if n.props["to"] == person]
    if unread:
        office.log.append("notify.read", actor=person, content={"ids": unread})


def card_json(n, now: datetime) -> dict:
    p = n.props
    left = int((_at(p["due"]) - now).total_seconds() // 60)
    return {"id": n.id, "kind": p["kind"], "reason": p["reason"], "who": p["who"], "due": p["due"], "minutes_left": left,
            "overdue": left < 0, "pooled": bool(p.get("pooled")), "raised_at": p.get("raised") or n.at}
