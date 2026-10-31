"""The Deck builder: a pitch deck for the meeting with a hot lead, built from records only.

Four slides, each naming its sources:
1. The property: from the catalog (price, size, permit, photo, map).
2. Why it fits: the customer's own answers, in their words. The slide rests on the customer's statements, so if one is
   replaced, the Fact checker sends the deck back (docs/deal-desk.md).
3. What this deal kind needs: an off-plan unit's project (developer, payment plan, handover) from Knowledge → Projects;
   a rental's yearly rent and move-in; a ready unit's price and viewing.
4. Documents already in the archive (brochure, floor plan, payment plan), found through the Records team's search.

What it cannot find becomes a task for the broker ("ask the developer for the payment plan"), never a guess. The broker
approves the deck for the meeting; the approval rests on the same statements, so it goes stale with them.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from diwan.office import Office
from diwan.people import name


def _project(g, title: str):
    from diwan import knowledge
    return next((n for n in g.of("knowledge") if knowledge.tab(n) == "project" and knowledge.usable(n)
                 and (n.props.get("title") or "").lower() == title.lower()), None)


def _documents(g, about: str) -> list:
    """The archive's documents that name this project or building (Records' own search, then only exact matches)."""
    from diwan.agents import records
    _, ids, _ = records.find_documents(g, about, date.today())
    words = set(re.findall(r"[a-z0-9]{4,}", about.lower()))
    return [g.nodes[i] for i in ids if words & set(re.findall(r"[a-z0-9]{4,}", f"{g.nodes[i].props['title']} {g.nodes[i].props.get('party') or ''}".lower()))]


def build(office: Office, deal: str, *, by: str = "deck", cause: int | None = None, listing: str | None = None) -> str | None:
    """Make (or remake) the pitch deck for this deal's chosen property. None when no property is chosen yet."""
    from diwan import deal_kinds, qualify
    g = office.graph()
    d = g.nodes[f"deal:{deal}"].props
    lid = listing or (d.get("hot") or {}).get("listing") or next(iter(d.get("recommended") or []), None)
    if not lid or lid not in g.nodes:
        return None
    p = g.nodes[lid].props
    rent = p.get("offering") == "rent"
    price = f"AED {p['price_aed']:,}{' a year' if rent else ''}"
    size = f", {p['size_sqft']:,} sq ft" if p.get("size_sqft") else ""
    beds = "studio" if p["beds"] == 0 else f"{p['beds']} bed"
    slides = [{"n": 1, "title": "The property", "photo": (p.get("photos") or [None])[0], "sources": [lid], "facts": [],
               "text": f"{p['title']}, {p['community']} (ref {p['ref']}): {beds} {p['type']}{size}. {price}. Permit {p.get('permit')}."
                       + (f" {p['description']}" if p.get("description") else "")}]
    # 2. why it fits: the customer's answers in their words, and the statements the Scribe kept
    st = qualify.state(g, deal)
    money = {x["key"] for x in qualify.fields_for(qualify.form(g), st.get("type")) if x["kind"] == "money"}
    val = lambda a: f"AED {qualify.number(a['value']):,.0f}" if a["key"] in money and qualify.number(a["value"]) else a["value"]  # noqa: E731
    said = [f"{a['label'].replace(' (AED)', '')}: {val(a)} (“{a['quote']}”)" for a in st["answers"] if a.get("quote")]
    facts = [f.id for f in g.facts(deal) if f.props.get("kind") in ("deal_term", "payer", "payment_promise")]
    slides.append({"n": 2, "title": "Why it fits", "sources": [], "facts": facts,
                   "text": "; ".join(said) or "The customer's answers are not recorded yet."})
    # 3. what this kind of deal needs
    missing, k = [], deal_kinds.kind_for(g, deal)
    if p.get("completion") == "off_plan":
        proj = _project(g, p.get("project") or "")
        if proj:
            slides.append({"n": 3, "title": f"{proj.props['title']}: payment plan and handover", "sources": [proj.id], "facts": [],
                           "text": proj.props["text"]})
        else:
            slides.append({"n": 3, "title": "Payment plan and handover", "sources": [], "facts": [],
                           "text": f"The payment plan for {p.get('project') or 'this project'} is not in our records yet."})
            missing.append(("the payment plan and handover date", p.get("project") or p["title"]))
    elif rent:
        move = next((a for a in st["answers"] if a["key"] == "move_in"), None)
        slides.append({"n": 3, "title": "Rent and move-in", "sources": [lid], "facts": [],
                       "text": f"Yearly rent {price}." + (f" Move-in: {move['value']} (“{move['quote']}”)." if move else "")})
    else:
        v = next((n for n in g.of("viewing", status="booked") if n.props.get("listing") == p["ref"] or n.props.get("listing") == lid), None)
        slides.append({"n": 3, "title": "Price and viewing", "sources": [lid] + ([v.id] if v else []), "facts": [],
                       "text": f"{price}, ready to move in." + (f" {g.record(v.id).split(' · ', 1)[1]}." if v else " Viewing to be booked.")})
    # 4. documents already in the archive
    about = p.get("project") or p["title"]
    docs = _documents(g, about)
    if docs:
        slides.append({"n": 4, "title": "Documents", "sources": [x.id for x in docs], "facts": [],
                       "text": "; ".join(f"{x.props['title']} ({x.props['date']})" for x in docs)})
    else:
        slides.append({"n": 4, "title": "Documents", "sources": [], "facts": [], "text": f"No brochure or floor plan for {about} in the archive yet."})
        missing.append(("the brochure and floor plan", about))
    did = office.make_draft(deal, "pitch", slides, by=by)
    broker = d["broker"]
    open_tasks = {t.props["action"] for t in g.of("task", deal) if t.status == "queued"}
    for what, of in missing:
        action = f"Ask the developer for {what} for {of}, for {d.get('customer', 'the customer')}'s pitch deck"
        if action not in open_tasks:
            office.add_task(deal, "deck", action, needs_person=broker, by=by, caused_by=cause)
    return did


def latest(g, deal: str):
    ds = [x for x in g.of("draft", deal) if x.props.get("kind") == "pitch"]
    return max(ds, key=lambda x: x.event) if ds else None


def view(g, did: str) -> dict:
    """A deck for the screens: its slides, its review, and whether the broker approved it for the meeting."""
    dr = g.nodes[did]
    slides = sorted(g.into(did, "part_of"), key=lambda s: s.props["n"])
    approvals = [a for a in g.of("approval", dr.deal) if a.props.get("action", "").startswith(f"Show pitch deck {did}")]
    return {"id": did, "deal": dr.deal, "version": dr.props.get("version", 1), "status": dr.status, "reason": dr.props.get("reason"),
            "slides": [{"n": s.props["n"], "title": s.props.get("title"), "text": s.props.get("text") or s.label, "photo": s.props.get("photo"),
                        "sources": s.props.get("sources", []), "stale": bool(g.stale(s.id))} for s in slides],
            "approved": [{"id": a.id, "by": name(a.props["approver"]), "status": a.status, "stale": bool(g.stale(a.id))} for a in approvals]}


def approve(office: Office, did: str, *, by: str) -> str:
    """The broker approves the deck for the meeting. Only the deal's broker or the owner; never a deck that was sent back."""
    from diwan import qualify
    g = office.graph()
    dr = g.nodes[did]
    broker = g.nodes[f"deal:{dr.deal}"].props["broker"]
    if by != broker and by not in qualify.owner_ids():
        raise PermissionError(f"Only {name(broker)}, the deal's broker, or the owner approves the deck")
    if dr.status == "sent_back":
        raise ValueError("This deck was sent back: remake it from what stands now first")
    facts = sorted({f for s in g.into(did, "part_of") for f in s.props.get("facts", [])})
    return office.approve(dr.deal, by, f"Show pitch deck {did} in the meeting", facts)
