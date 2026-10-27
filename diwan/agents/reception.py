"""Rania, the receptionist on WhatsApp. Every message is heard by the Scribe first, so what a buyer types at midnight is
the same quoted fact as what they say in a meeting. Then Rania replies from confirmed company knowledge and permitted
listings only, books viewings in a broker's free slot, and hands the chat to a person whenever asked or whenever the
question is not hers to answer. While a person has the chat, Rania only suggests replies.

A model reply that names an amount not found in the listings or knowledge it was given is not sent: the chat goes to
the broker instead. That is how "never quote a price that is not on a listing" is enforced, not just asked for.
"""
from __future__ import annotations

import re
from datetime import datetime

from diwan import slots
from diwan.agents import runner, scribe
from diwan.agents.charters import get
from diwan.graph import Graph, Node
from diwan.office import Office
from diwan.pack import Action, Pack
from diwan.people import name
from diwan.providers import whatsapp

RANIA = "rania"
COMPANY = "Diwan Realty"

HANDOVER = r"\b(agent|human|real person|someone|call me|speak to|talk to|broker|manager)\b"
NOT_MINE = (r"\b(cash|crypto|bitcoin|usdt|source of (funds|wealth)|aml|sanction\w*|anonymous|without (id|documents|kyc)|"
            r"no (id|documents)|third party|offshore|negotiat\w*|discount|lower (the )?price|best price|commission split)\b")
RETURNS = r"\b(roi|returns?|yield|guarantee\w*|rental income|appreciat\w*)\b"
BOOK = r"\b(view|viewing|visit|see|book|appointment|come (by|over)|show me)\b"
SEARCH = r"\b(bed|br|bedroom|studio|villa|apartment|flat|townhouse|looking for|budget|available|listings?|options?)\b"

RECEPTION_SCHEMA = {"name": "reception", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["reply", "listing_refs", "knowledge_refs", "book_listing", "book_when", "handover"],
    "properties": {"reply": {"type": "string"}, "listing_refs": {"type": "array", "items": {"type": "string"}},
                   "knowledge_refs": {"type": "array", "items": {"type": "string"}},
                   "book_listing": {"type": ["string", "null"]}, "book_when": {"type": ["string", "null"]},
                   "handover": {"type": "boolean"}}}}

GUIDE = f"""
You are on WhatsApp for {COMPANY}. Reply in the customer's language (Arabic or English), warmly, in at most three short
sentences, in the `reception` format, not agent_pack.
- Facts about listings and the company come only from the sources; name the listing ref you mean.
- To book a viewing, set book_listing to the ref and book_when to the day and time the customer asked for, in their words.
- Set handover to true when the customer asks for a person, or asks about payment methods, discounts, negotiation,
  returns, documents, checks, or anything the sources do not answer. Never explain why."""


def advertisable(g: Graph) -> list[Node]:
    return [n for n in g.of("listing", status="available") if n.props.get("permit")]


def _lead(office: Office, phone: str, who: str | None) -> str:
    g = office.graph()
    ch = g.nodes.get(f"chat:{phone}")
    if ch and ch.deal:
        return ch.deal
    deal = f"lead-{re.sub(r'\\D', '', phone)[-6:]}"
    office.open_deal(deal, property="WhatsApp enquiry", customer=who or phone, broker="omar", by=RANIA)
    return deal


def _send(office: Office, phone: str, deal: str, text: str, refs: list[str], by: str = RANIA, cause: int | None = None) -> dict:
    ev = office.log.append("chat.sent", actor=by, agent=RANIA if by == RANIA else None, deal=deal, caused_by=cause,
                           content={"chat": phone, "text": text, "refs": refs})
    if whatsapp.available():
        try:
            whatsapp.send(phone, text)
        except RuntimeError as e:
            office.log.append("agent.failed", actor=by, agent=RANIA, deal=deal, caused_by=ev["id"], content={"error": str(e)[:300]})
    return ev


def hand_over(office: Office, phone: str, *, to: str = "omar", by: str = RANIA, reason: str = "", cause: int | None = None) -> None:
    g = office.graph()
    deal = g.nodes[f"chat:{phone}"].deal
    office.log.append("chat.handover", actor=by, agent=RANIA, deal=deal, caused_by=cause, content={"chat": phone, "mode": "human", "by": to, "reason": reason})
    who = g.nodes[f"chat:{phone}"].label
    office.add_task(deal, RANIA, f"Reply to {who} on WhatsApp{f': {reason}' if reason else ''}", needs_person=to, by=RANIA, caused_by=cause)


def give_back(office: Office, phone: str, *, by: str) -> None:
    deal = office.graph().nodes[f"chat:{phone}"].deal
    office.log.append("chat.handover", actor=by, deal=deal, content={"chat": phone, "mode": "ai", "by": by})


def person_sends(office: Office, phone: str, text: str, *, by: str) -> dict:
    """A person replying from the Inbox. Taking the chat is implied: Rania goes quiet."""
    g = office.graph()
    ch = g.nodes[f"chat:{phone}"]
    if ch.props["mode"] != "human":
        office.log.append("chat.handover", actor=by, deal=ch.deal, content={"chat": phone, "mode": "human", "by": by})
    ev = _send(office, phone, ch.deal, text, [], by=by)
    for t in g.of("task", ch.deal, {"queued"}):
        if t.props["agent"] == RANIA and t.props["action"].startswith(f"Reply to {ch.label} on WhatsApp"):
            office.finish_task(t.id, f"{name(by)} replied", caused_by=ev["id"])
    return ev


def _listing_named(g: Graph, text: str, chat: Node | None) -> Node | None:
    low = text.lower()
    for n in advertisable(g):
        words = {n.props["ref"].lower()} | set(re.findall(r"[a-z]{4,}", f"{n.props['title']} {n.props['community']}".lower()))
        if any(w in low for w in words):
            return n
    for m in reversed(chat.props["messages"] if chat else []):
        refs = [r for r in m.get("refs", []) if r.startswith("listing:") and r in g.nodes]
        if len(refs) == 1:
            return g.nodes[refs[0]]
    return None


def matches(g: Graph, deal: str, text: str) -> list[Node]:
    low = text.lower()
    want_beds = None
    if m := re.search(r"\b(\d|one|two|three|four|five)\s*-?\s*(bed|br|bedroom)", low):
        want_beds = int(m.group(1)) if m.group(1).isdigit() else ["one", "two", "three", "four", "five"].index(m.group(1)) + 1
    elif "studio" in low:
        want_beds = 0
    budgets = scribe.amounts(text) or [f.props["amount_aed"] for f in g.facts(deal, "deal_term")]
    budget = max(budgets) if budgets else None
    kind = next((k for k in ("villa", "apartment", "townhouse") if k in low or (k == "apartment" and "flat" in low)), None)
    every = {w for n in g.of("listing") for w in re.findall(r"[a-z]{4,}", n.props["community"].lower())} - {"dubai"}
    asked = {w for w in every if w in low}
    out = []
    for n in advertisable(g):
        p = n.props
        if want_beds is not None and p["beds"] != want_beds:
            continue
        if budget and p["price_aed"] > budget * 1.1:
            continue
        if kind and p["type"] != kind:
            continue
        if not asked or asked & set(re.findall(r"[a-z]{4,}", p["community"].lower())):
            out.append(n)
    return out[:3]


def book(office: Office, phone: str, deal: str, listing: Node, when: datetime | None, now: datetime, cause: int) -> tuple[str, list[str]]:
    g = office.graph()
    broker = g.nodes[f"deal:{deal}"].props["broker"]
    who = g.nodes[f"chat:{phone}"].label
    ref = listing.props["ref"]
    options = slots.free(g, broker, now, 3)
    if when is None or not slots.is_open(when) or when.isoformat() in slots.busy(g, broker) or when <= now:
        opts = ", ".join(slots.say(t) for t in options)
        lead = "That time isn't available. " if when else ""
        return f"{lead}I can book {listing.props['title']} ({ref}) with {name(broker)} on {opts}. Which suits you?", [listing.id]
    vid = f"V{len(g.of('viewing')) + 1}"
    office.log.append("appointment.booked", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause,
                      content={"id": vid, "listing": ref, "broker": broker, "at": when.isoformat(), "customer": who, "chat": phone})
    office.add_task(deal, RANIA, f"Viewing of {ref} with {who}, {slots.say(when)}", needs_person=broker, by=RANIA, caused_by=cause)
    return (f"Booked: {listing.props['title']} ({ref}) with {name(broker)}, {slots.say(when)}. Please bring a photo ID for the building lobby."
            if any("photo id" in k.props["text"].lower() for k in g.of("knowledge", status="confirmed"))
            else f"Booked: {listing.props['title']} ({ref}) with {name(broker)}, {slots.say(when)}."), [listing.id, vid]


def _listing_line(n: Node) -> str:
    p = n.props
    return f"{p['title']}, {p['community']}: {p['beds']} bed {p['type']}, AED {p['price_aed']:,} (ref {p['ref']}, permit {p['permit']})"


def answer_rules(office: Office, phone: str, deal: str, text: str, now: datetime, cause: int,
                 heard: list[str] = ()) -> tuple[str, list[str], list[Action], str | None]:
    """Reply, refs, actions, and a handover reason if the chat should go to a person."""
    g = office.graph()
    low = text.lower()
    chat = g.nodes.get(f"chat:{phone}")
    who = chat.label.split()[0] if chat else "there"
    broker = name(g.nodes[f"deal:{deal}"].props["broker"])
    if re.search(NOT_MINE, low):
        return f"That's one for {broker} personally, who will reply to you here.", [], [Action("assign", "Hand to broker")], "a question for a person"
    if re.search(RETURNS, low):
        return (f"I can't promise returns or yields. {broker} can share recent sales and rental data for the area and will reply here.",
                [], [Action("assign", "Hand to broker")], "asked about returns")
    if any(g.nodes[f].props["kind"] in ("payer", "payment_promise", "income_claim") for f in heard):
        # noted by the Scribe, so the office already acts on it; Rania does not discuss money
        return f"Thank you, noted. {broker} will go through the payment details with you personally.", list(heard), [Action("record_fact", "Noted")], None
    if re.search(HANDOVER, low):
        return f"Of course. I'm passing you to {broker}, who will reply here shortly.", [], [Action("assign", "Hand to broker")], "asked for a person"
    if re.search(BOOK, low) or slots.parse(text, now):
        listing = _listing_named(g, text, chat)
        if not listing:
            opts = "; ".join(_listing_line(n) for n in advertisable(g)[:3])
            return f"Happy to arrange a viewing. Which property would you like to see? {opts}", [n.id for n in advertisable(g)[:3]], [Action("reply", "Ask which listing")], None
        reply, refs = book(office, phone, deal, listing, slots.parse(text, now), now, cause)
        kind = "book_viewing" if any(r.startswith("V") for r in refs) else "reply"
        return reply, refs, [Action(kind, reply)], None
    communities = {w for n in g.of("listing") for w in re.findall(r"[a-z]{4,}", n.props["community"].lower())} - {"dubai"}
    if re.search(SEARCH, low) or scribe.amounts(text) or any(w in low for w in communities):
        found = matches(g, deal, text)
        if not found:
            return (f"I don't have a listing that fits that right now. {broker} hears about new ones first, so I've passed your brief on.",
                    [], [Action("assign", "Brief the broker")], "no listing fits the brief")
        lines = "\n".join(f"• {_listing_line(n)}" for n in found)
        return f"Here's what fits:\n{lines}\nWould you like to see one? Tell me a day and time.", [n.id for n in found], [Action("reply", "Listings")], None
    words = set(re.findall(r"[a-z]{4,}", low)) - {"what", "your", "have", "does", "about", "with", "there", "hello", "thanks"}
    best = max(g.of("knowledge", status="confirmed"), key=lambda k: len(words & set(re.findall(r"[a-z]{4,}", f"{k.props['title']} {k.props['text']}".lower()))), default=None)
    if best and words & set(re.findall(r"[a-z]{4,}", f"{best.props['title']} {best.props['text']}".lower())):
        return best.props["text"], [best.id], [Action("reply", best.props["title"])], None
    if not chat or len(chat.props["messages"]) <= 1:
        return (f"Hi {who}, I'm Rania from {COMPANY}. Are you looking to buy, and which area, size and budget do you have in mind?",
                [], [Action("reply", "Greet and ask the brief")], None)
    if re.search(r"\b(hi|hello|salam|marhaba|hey|thanks|thank you)\b|السلام|مرحبا|شكرا", low):
        return f"Hi {who}, how can I help?", [], [Action("reply", "Greet")], None
    return f"I'm not sure I can answer that well. I've asked {broker} to reply to you here.", [], [Action("assign", "Hand to broker")], "Rania couldn't answer"


def _amounts_ok(reply: str, sources: dict[str, str]) -> bool:
    known = {a for s in sources.values() for a in scribe.amounts(s)}
    return all(a in known for a in scribe.amounts(reply))


def message(office: Office, phone: str, text: str, *, name_: str | None = None, now: datetime | None = None, tape_root=None) -> dict:
    now = now or datetime.now(slots.DUBAI)
    deal = _lead(office, phone, name_)
    got = office.log.append("chat.received", actor=f"customer:{phone}", deal=deal, content={"chat": phone, "name": name_, "text": text})
    heard = scribe.hear(office, deal, office.graph().nodes[f"deal:{deal}"].props["customer"], text, got["id"], tape_root=tape_root)
    g = office.graph()
    chat = g.nodes[f"chat:{phone}"]
    c = get(RANIA)
    sources = ({n.id: g.record(n.id) for n in advertisable(g)} | {k.id: g.record(k.id) for k in g.of("knowledge", status="confirmed")}
               | {f"msg:{m['event']}": f"{m['by']}: {m['text']}" for m in chat.props["messages"][-6:]})
    system, user = runner.instructions(c) + GUIDE, runner.user_message(f"New message from {chat.label}: {text}", sources)
    reason = None
    if runner.has_model(c, system, user, schema=RECEPTION_SCHEMA, tape_root=tape_root):
        out = runner.call(c, system, user, schema=RECEPTION_SCHEMA, tape_root=tape_root).data
        reply, refs = out["reply"], [r if r.startswith(("listing:", "K")) else f"listing:{r}" for r in out["listing_refs"]] + out["knowledge_refs"]
        actions = [Action("reply", reply)]
        if out["handover"] or not _amounts_ok(reply, sources):
            reason = "asked for a person" if out["handover"] else "reply named an amount not on any listing"
            reply = f"I've asked {name(g.nodes[f'deal:{deal}'].props['broker'])} to reply to you here personally."
            actions = [Action("assign", "Hand to broker")]
        elif out["book_listing"] and f"listing:{out['book_listing']}" in g.nodes:
            reply, refs = book(office, phone, deal, g.nodes[f"listing:{out['book_listing']}"], slots.parse(out["book_when"] or "", now), now, got["id"])
            actions = [Action("book_viewing", reply)]
        by = "model"
    else:
        reply, refs, actions, reason = answer_rules(office, phone, deal, text, now, got["id"], heard["facts"])
        by = "rules"
    if chat.props["mode"] == "human":
        office.log.append("chat.suggested", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"chat": phone, "text": reply, "refs": refs})
        return {"mode": "human", "suggestion": reply, "refs": refs, "facts": heard["facts"], "by": by}
    runner.submit(office.log, c, Pack(f"chat-{got['id']}", RANIA, reply, actions=actions), sources={}, deal=deal, caused_by=got["id"])
    _send(office, phone, deal, reply, refs, cause=got["id"])
    if reason:
        hand_over(office, phone, reason=reason, cause=got["id"])
    return {"mode": "human" if reason else "ai", "reply": reply, "refs": refs, "facts": heard["facts"], "handover": reason, "by": by}
