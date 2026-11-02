"""What the Inbox shows, built from the graph: each conversation's stage, what the buyer is after, how long they have
waited, whether WhatsApp's 24-hour window is open, and the deal behind it. Sending is in agents/reception.py.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.graph import OPEN, Graph
from diwan.office import Office
from diwan.people import name

def stage_names(g: Graph) -> list[str]:
    """Every stage a lead can be at: Sales' own, then each paperwork path's (the owner's settings on the Deal desk), Won and Lost."""
    from diwan import desk_rules
    out = list(desk_rules.SALES_STAGES)
    for p in desk_rules.rules(g)["paths"].values():
        out += [s for s in p["stages"] if s not in out]
    return out + [s for s in ("Won", "Lost") if s not in out]
WINDOW = timedelta(hours=24)

# used when no WhatsApp partner is connected, so the template flow can be shown; marked as samples on screen
SAMPLE_TEMPLATES = [
    {"name": "viewing_reminder", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 3,
     "body": "Hi {{1}}, a reminder of your viewing of {{2}} on {{3}}. Reply here if you need to change it."},
    {"name": "still_looking", "status": "SAMPLE", "language": "en", "category": "MARKETING", "params": 2,
     "body": "Hi {{1}}, are you still looking in {{2}}? We have new listings this week."},
    {"name": "gentle_follow_up", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 2,
     "body": "Hi {{1}}, are you still looking in {{2}}? Whenever you're ready, reply here and I'll pick up where we left off."},
    {"name": "portal_enquiry", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 3,
     "body": "Hi {{1}}, thank you for your enquiry about {{2}}. I'm {{3}} from Diwan Realty. When is a good time to call you?"},
    {"name": "documents_request", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 1,
     "body": "Hi {{1}}, to prepare your paperwork we need a copy of your passport and Emirates ID. You can send them here."},
    {"name": "appointment_changed", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 3,
     "body": "Hi {{1}}, your {{2}} has been moved to {{3}}. Reply here if that doesn't suit you."},
    {"name": "appointment_cancelled", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 3,
     "body": "Hi {{1}}, your {{2}} on {{3}} has been cancelled. Reply here if you'd like another time."},
    {"name": "after_viewing", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 1,
     "body": "Hi {{1}}, thank you for coming to the viewing. How did you find it? Reply here and I'll take it from there."},
]


def templates() -> list[dict]:
    """The approved WhatsApp templates: from AiSensy when connected, otherwise the samples (marked so)."""
    from diwan.providers import aisensy
    if aisensy.available():
        try:
            return [t for t in aisensy.templates() if t["status"] in ("APPROVED", "")]
        except aisensy.AiSensyError:
            return []
    return SAMPLE_TEMPLATES


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def interests(g: Graph, deal: str | None, messages: list[dict]) -> list[dict]:
    """Chips for what the buyer is after, each from their own words or a fact."""
    from diwan import knowledge
    said = " ".join(m["text"] for m in messages if m["type"] == "received").lower()
    chips = []
    if deal and (dk := g.nodes.get(f"deal:{deal}")) and dk.props.get("kind_name"):  # the deal kind decided when it qualified
        chips.append({"label": dk.props["kind_name"], "kind": "dk"})
    if re.search(r"\brent(al|ing)?\b|\blease\b", said):
        chips.append({"label": "Rent", "kind": "intent"})
    elif re.search(r"\bbuy|purchase|invest|own\b", said) or (deal and g.facts(deal, "deal_term")):
        chips.append({"label": "Buy", "kind": "intent"})
    if re.search(r"off.?plan|handover|payment plan", said):
        chips.append({"label": "Off-plan", "kind": "intent"})
    names = {n.props["community"].lower(): n.props["community"] for n in g.of("listing")}
    for comm in sorted(knowledge.areas_in(g, said)):  # whole names only: "villa" is not the community "The Villa"
        chips.append({"label": names.get(comm, comm.title()).replace("Dubai ", ""), "kind": "area"})
    if m := re.search(r"\b(\d|one|two|three|four|five|studio)\s*-?\s*(bed|br|bedroom)", said):
        chips.append({"label": f"{m.group(1)} bed".replace("studio bed", "Studio"), "kind": "size"})
    if deal and (terms := [f for f in g.facts(deal, "deal_term") if f.props.get("amount_aed")]):
        amt = terms[-1].props["amount_aed"]
        chips.append({"label": f"AED {amt / 1e6:.1f}M" if amt >= 1e6 else f"AED {amt / 1e3:.0f}K", "kind": "budget", "ref": terms[-1].id,
                      "quote": terms[-1].props.get("quote")})
    return chips


def conversation(g: Graph, c, now: datetime) -> dict:
    from diwan import leads
    from diwan.providers.portals import PORTALS
    msgs = c.props["messages"]
    deal = g.nodes.get(f"deal:{c.deal}") if c.deal else None
    last_in = next((m for m in reversed(msgs) if m["type"] == "received"), None)
    last_reply = next((m for m in reversed(msgs) if m["type"] == "sent"), None)
    waiting = None
    if last_in and (not last_reply or last_reply["event"] < last_in["event"]):
        waiting = int((now - _at(last_in["at"])).total_seconds() // 60)
    # only a message the customer sent us on WhatsApp or Instagram opens the 24-hour window; a portal enquiry does not
    last_wa = next((m for m in reversed(msgs) if m["type"] == "received" and m.get("channel") in (None, "whatsapp", "instagram")), None)
    window_open = bool(last_wa) and now - _at(last_wa["at"]) < WINDOW
    card = leads.open_card(g, c.props["phone"])
    source = next((m.get("channel") for m in msgs if m["type"] == "received" and m.get("channel")), None)
    viewings = [v for v in g.of("viewing", status="booked") if v.props.get("chat") == c.props["phone"] and v.props.get("where") != "phone"]
    return {
        "phone": c.props["phone"], "name": c.label, "deal": c.deal, "mode": c.props["mode"], "handled_by": c.props.get("handled_by"),
        "stage": (deal.props.get("stage") if deal else None) or "New", "broker": deal.props.get("broker") if deal else None,
        "property": deal.props.get("property") if deal else None, "linked": bool(c.deal and not c.deal.startswith("lead-")),
        "last": msgs[-1] if msgs else None, "last_at": c.props.get("last_at"), "waiting_min": waiting,
        "window_open": window_open, "window_closes": (_at(last_wa["at"]) + WINDOW).isoformat() if last_wa else None,
        "attention": leads.card_json(card, now) if card else None, "source": source or "whatsapp",
        "chips": interests(g, c.deal, msgs),
        "viewing": g.record(viewings[0].id).split(" · ", 1)[1] if viewings else None,
        "failed": sum(1 for m in msgs if m.get("status") == "failed"),
        "hot": _hot(deal),
        "heat": _heat(g, c.deal),
        "progress": _progress(g, c.deal),
        "no_calls": bool(deal and deal.props.get("no_calls")),
        "nurture": (deal.props.get("nurture") or ({"reason": "not a fit"} if deal.props.get("qualify_status") == "not_a_fit" else None))
                   if deal else None,
    }


def _heat(g: Graph, deal: str | None) -> dict | None:
    from diwan import sales
    return sales.heat(g, deal)


def _progress(g: Graph, deal: str | None) -> dict | None:
    from diwan import sales
    return sales.progress(g, deal)


def _hot(deal) -> str | None:
    """The property a hot lead picked, or "yes" when it is hot without one (it qualified, or asked for a call)."""
    h = (deal.props.get("hot") if deal else None) or {}
    return (h.get("listing") or "").replace("listing:", "") or ("yes" if h else None)


def _scoped(rows: list[dict]) -> list[dict]:
    """What the signed-in person may see: a broker their own leads and the Pool."""
    from diwan import access, sales
    return sales.scope(rows, access.USER.get())


def listing(office: Office, *, view: str = "all", person: str = "omar", stage: str | None = None, q: str = "",
            now: datetime | None = None) -> list[dict]:
    g = office.graph()
    now = now or datetime.now(timezone.utc)
    rows = _scoped([conversation(g, c, now) for c in g.of("chat") if not c.props.get("merged_into")])  # a merged chat shows in its lead
    if view == "mine":
        rows = [r for r in rows if r["handled_by"] == person or (r["mode"] == "human" and r["broker"] == person) or r["broker"] == person]
    elif view == "new":
        rows = [r for r in rows if r["stage"] == "New"]
    elif view == "waiting":
        rows = [r for r in rows if r["waiting_min"] is not None]
    elif view == "attention":  # this person's cards, plus every overdue one for the owner
        rows = [r for r in rows if r["attention"] and (r["attention"]["who"] == person or person == "layla")]
        rows.sort(key=lambda r: r["attention"]["minutes_left"])
        return rows
    elif view == "pool":
        rows = [r for r in rows if r["attention"] and r["attention"]["pooled"]]
    elif view == "nurture":
        rows = [r for r in rows if r["nurture"]]
    if stage:
        rows = [r for r in rows if r["stage"] == stage]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in r["phone"] or any(ql in ch["label"].lower() for ch in r["chips"])]
    return sorted(rows, key=lambda r: (r["waiting_min"] is None, -(r["waiting_min"] or 0), r["last_at"] or ""), reverse=False)


def counts(office: Office, person: str = "omar") -> dict:
    g, now = office.graph(), datetime.now(timezone.utc)
    rows = _scoped([conversation(g, c, now) for c in g.of("chat")])
    return {"all": len(rows), "mine": len([r for r in rows if r["broker"] == person or r["handled_by"] == person]),
            "new": len([r for r in rows if r["stage"] == "New"]), "waiting": len([r for r in rows if r["waiting_min"] is not None]),
            "attention": len([r for r in rows if r["attention"] and (r["attention"]["who"] == person or person == "layla")]),
            "pool": len([r for r in rows if r["attention"] and r["attention"]["pooled"]]),
            "nurture": len([r for r in rows if r["nurture"]]),
            "stages": {s: len([r for r in rows if r["stage"] == s]) for s in stage_names(g)}}


def detail(office: Office, phone: str, now: datetime | None = None) -> dict:
    g = office.graph()
    c = g.nodes[f"chat:{phone}"]
    now = now or datetime.now(timezone.utc)
    base = conversation(g, c, now)
    deal = c.deal
    from diwan import offers
    asked = next((e["content"] for e in reversed(office.log.list()) if e["type"] == "viewing.requested" and e["content"].get("chat") == phone), None)
    return base | {
        "offers": offers.rows(office.log, deal) if deal else [],
        "viewing_request": asked if asked and not g.of("viewing", deal, "booked") else None,
        "messages": c.props["messages"],
        "facts": [{"id": f.id, "text": g.record(f.id).split(" · ", 1)[1], "kind": f.props["kind"]} for f in g.facts(deal)] if deal else [],
        "replaced": [{"id": f.id, "quote": f.props["quote"], "by": f.props.get("superseded_by")} for f in g.of("fact", deal, "superseded")] if deal else [],
        "tasks": [{"id": t.id, "text": t.props["action"], "who": name(t.props.get("needs_person")) if t.props.get("needs_person") else t.props.get("agent_name")}
                  for t in g.of("task", deal, OPEN)] if deal else [],
        "cards": [{"id": n.id, "text": n.props["text"], "who": name(n.props.get("who"))}
                  for typ in ("check", "decision", "question") for n in g.of(typ, deal, "open")] if deal else [],
        "stages": _deal_stages(g, deal), "history": (g.nodes[f"deal:{deal}"].props.get("stages", []) if deal else []),
        "desk": _desk(g, deal),
        "qualify": _qualify_state(g, deal),
        "deck": _deck(g, deal),
        "followup": _followup(g, deal),
        "quiet": _quiet(g, c, now) if deal and f"deal:{deal}" in g.nodes else None,
        "visit": g.nodes[f"deal:{deal}"].props.get("visit") if deal and f"deal:{deal}" in g.nodes else None,
        "calls": _calls(g, c),
        "owner_wait": _owner_wait(g, c),
        "listing_hint": _listing_hint(g, deal),
        "needs_outcome": _needs_outcome(g, c),
        "outcome": g.nodes[f"deal:{deal}"].props.get("outcome") if deal and f"deal:{deal}" in g.nodes else None,
    }


def _needs_outcome(g: Graph, chat) -> dict | None:
    from diwan import sales
    return sales.needs_outcome(g, chat)


def _listing_hint(g: Graph, deal: str | None) -> dict | None:
    """Our listing this client chose or went to see: Convert offers it, so the broker isn't asked which property again."""
    if not deal or f"deal:{deal}" not in g.nodes:
        return None
    # what they did themselves comes first: the one they went to see, then the one they named, then the one they picked
    seen = sorted((v for v in g.of("viewing") if v.deal == deal and v.status in ("booked", "done") and v.props.get("listing")), key=lambda v: v.props["at"])
    lid = f"listing:{seen[-1].props['listing']}" if seen else None
    if not lid:  # the listing they last asked about by name ("is MC-1204 still available?")
        from diwan.agents import reception
        ch = next((c for c in g.of("chat") if c.deal == deal), None)
        asked = next((n for m in reversed(ch.props["messages"] if ch else []) if m["type"] == "received"
                      for n in [reception._listing_named(g, m["text"], None)] if n is not None), None)  # named by them, not "it"
        lid = asked.id if asked is not None else None
    lid = lid or (g.nodes[f"deal:{deal}"].props.get("hot") or {}).get("listing")
    n = g.nodes.get(lid) if lid else None
    return {"ref": n.props["ref"], "title": n.props["title"]} if n is not None and n.status == "available" else None


def _owner_wait(g: Graph, chat) -> dict | None:
    """A viewing held for this client while the broker checks with the owner or tenant (docs/viewing-access-spec.md)."""
    from diwan import viewings
    v = viewings.waiting(g, chat.props["phone"])
    if not v:
        return None
    lst = g.nodes.get(f"listing:{v.props.get('listing')}")
    return {"id": v.id, "at": v.props["at"], "listing": v.props.get("listing"), "title": lst.props["title"] if lst else v.props.get("listing"),
            "who": viewings.viewings_who(g, lst), "confirm": v.props.get("confirm")}


def _calls(g: Graph, chat) -> list[dict]:
    """This lead's calls: call cards (open and done) and phone calls on the calendar, newest first."""
    phone = chat.props["phone"]
    out = [{"what": n.props["reason"], "when": n.props["due"], "status": n.status, "who": name(n.props.get("who")),
            "done": n.props.get("action")}
           for n in g.of("attention") if n.props.get("chat") == phone and n.props.get("kind") == "call"]
    out += [{"what": v.props.get("kind_name") or "Phone call", "when": v.props["at"], "status": v.status, "who": name(v.props["broker"]), "done": None}
            for v in g.of("viewing") if v.props.get("chat") == phone and v.props.get("where") == "phone"]
    return sorted(out, key=lambda x: x["when"], reverse=True)


def _quiet(g: Graph, chat, now: datetime) -> dict:
    from diwan.agents import nudge
    return nudge.state(g, chat, now)


def _followup(g: Graph, deal: str | None) -> dict | None:
    from diwan.agents import followup
    return followup.current(g, deal) if deal else None


def _deck(g: Graph, deal: str | None) -> dict | None:
    from diwan.agents import deck
    d = deck.latest(g, deal) if deal else None
    return deck.view(g, d.id) if d else None


def _qualify_state(g: Graph, deal: str | None) -> dict | None:
    from diwan import qualify
    if not deal or f"deal:{deal}" not in g.nodes:
        return None
    st = qualify.state(g, deal)
    return {k: st.get(k) for k in ("verdict", "type", "type_label", "type_quote", "type_source", "answers", "missing", "reasons", "status", "version",
                                "open_questions", "stuck")} \
        | {"recommended": [r.replace("listing:", "") for r in g.nodes[f"deal:{deal}"].props.get("recommended", [])],
           "hot": g.nodes[f"deal:{deal}"].props.get("hot"), "nurture": g.nodes[f"deal:{deal}"].props.get("nurture"),
           "reopened": g.nodes[f"deal:{deal}"].props.get("reopened")} \
        | {"next": (st.get("next") or {}).get("label")}


def _deal_stages(g: Graph, deal: str | None) -> list[str]:
    from diwan import desk_stages
    return (desk_stages.stages(g, deal) + ["Lost"]) if deal and f"deal:{deal}" in g.nodes else stage_names(g)


def _desk(g: Graph, deal: str | None) -> dict | None:
    """The deal's stages as the Deal desk keeps them: who may move it, the agreed price, a discount waiting for the owner."""
    from diwan import desk_stages
    if not deal or f"deal:{deal}" not in g.nodes:
        return None
    return desk_stages.view(g, deal)


def set_stage(office: Office, phone: str, stage: str, *, by: str, reason: str = "", only_forward: bool = False) -> None:
    """A person moves the lead, under the Deal desk's rules (docs/lead-profile-spec.md): the deal's own stages, a reason for
    Lost or for moving back, Won only from closing, only the broker, the transactions officer or the owner.
    `only_forward`: from the calendar's Done, which never moves a deal back."""
    from diwan import desk_stages, sales
    g = office.graph()
    deal = g.nodes[f"chat:{phone}"].deal
    if (stage == "Qualified" and by in desk_stages.movers(g, deal) and g.nodes[f"deal:{deal}"].props.get("stage") in (None, "New", "Qualifying")
            and not sales.form_complete(g, deal)):
        p = sales.progress(g, deal)
        raise ValueError(f"Qualified means the owner's form is complete: {p['done']} of {p['of']} answered" if p else "Qualified means the owner's form is complete")
    if only_forward:
        order, cur = desk_stages.stages(g, deal), g.nodes[f"deal:{deal}"].props.get("stage") or "New"
        if cur == "Lost" or cur not in order or stage not in order or order.index(stage) <= order.index(cur):
            return
    desk_stages.move(office, deal, stage, by, reason)
    if stage == "Viewed":  # after the viewing: the follow-up waits for the broker
        from diwan.agents import followup
        followup.draft(office, deal, why="after the viewing")


def auto_stage(office: Office, deal: str, cause: int | None = None) -> None:
    """Moves only forward, from the owner's qualification form: New → Qualifying once we know what they want →
    Qualified when every required answer is in and the conditions hold → Viewing booked once a viewing is booked.
    A lead that is not a fit under the owner's conditions is closed as Lost, with the rule that decided it."""
    g = office.graph()
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        return
    cur = d.props.get("stage") or "New"
    if cur == "Lost":
        return
    want = cur
    if d.props.get("qualify_status") == "not_a_fit":
        office.log.append("stage.changed", actor="rania", agent="rania", deal=deal, caused_by=cause,
                          content={"stage": "Lost", "auto": True, "reason": d.props.get("qualify_reason")})
        return
    names = stage_names(g)
    ahead = lambda s: want in names and names.index(want) < names.index(s)  # noqa: E731
    if d.props.get("qtype") and ahead("Qualifying"):
        want = "Qualifying"
    if d.props.get("qualify_status") == "qualified" and ahead("Qualified"):
        want = "Qualified"
    if any(v.deal == deal and v.props.get("where") != "phone" for v in g.of("viewing", status="booked")) and ahead("Viewing booked"):  # a call is not a viewing
        want = "Viewing booked"
    if want != cur:
        office.log.append("stage.changed", actor="rania", agent="rania", deal=deal, caused_by=cause, content={"stage": want, "auto": True})


def quick_replies(g: Graph) -> list[dict]:
    out = [{"title": k.props["title"], "text": k.props["text"]} for k in g.of("knowledge", status="confirmed")]
    return out + [{"title": "Viewing confirmed", "text": "Your viewing is confirmed. Please bring a photo ID for the building lobby."},
                  {"title": "Send documents", "text": "Could you send a copy of your passport and Emirates ID here when you have a moment?"}]


def render(body: str, params: list[str]) -> str:
    return re.sub(r"\{\{(\d+)\}\}", lambda m: params[int(m.group(1)) - 1] if int(m.group(1)) - 1 < len(params) else m.group(0), body)
