"""What each department's core remembers, for the brain you click on its floor. Every item is a record from the log
(with its id, so it opens in the memory graph); a section with nothing in it says so instead of showing a sample.
"""
from __future__ import annotations

from diwan.agents.charters import get
from diwan.graph import Graph
from diwan.office import Office

DEPTS = {"mkt", "sales", "records", "review", "ops", "fin", "comp", "front"}


def dept_of(agent: str) -> str | None:
    c = get(agent)
    while c:
        if c.id in DEPTS:
            return c.id
        if c.id == "nova":
            return "front"
        c = get(c.parent) if c.parent else None
    return None


def _items(g: Graph, nodes, sub=None, limit: int = 12) -> list[dict]:
    return [{"ref": n.id, "text": g.record(n.id).split(" · ", 1)[-1], "sub": sub(n) if sub else None} for n in list(nodes)[-limit:]]


def _section(title: str, note: str, items: list[dict], empty: str) -> dict:
    return {"title": title, "note": note, "items": items, "empty": empty}


def lessons(g: Graph, dept: str) -> dict:
    ls = [n for n in g.of("lesson", status="active") if dept_of(n.props["agent"]) == dept]
    return _section("Lessons people taught", "Every one goes into that agent's instructions; \"never\" lessons are enforced in code.",
                    [{"ref": n.id, "text": n.props["rule"], "sub": f"{get(n.props['agent']).name} · taught by {n.props.get('by')}"} for n in ls],
                    "None yet. Teach one on the Team page.")


def brain(office: Office, dept: str) -> dict:
    g = office.graph()
    if dept == "mkt":
        from diwan.agents import strategy, studio
        evs = [e["content"] for e in office.log.list() if e["type"] == "content.made"]
        approved = [s for s in (studio.approved_script(office, n.props["ref"]) for n in g.of("listing")) if s]
        plays = [c for c in evs if c["kind"] == "playbook"]
        st = strategy.report(office)
        comp = studio.competitors(g)
        brand = [n for n in g.of("knowledge", status="confirmed")]
        return {"title": "Brand brain", "about": "What the marketing team writes from: the brand, what works for us, what people taught it.", "sections": [
            _section("Company and brand knowledge", "Confirmed by a person; agents quote it, never invent it.", _items(g, brand), "Nothing confirmed yet. Add it on the Knowledge page."),
            lessons(g, "mkt"),
            _section("Script library", "Scripts a person approved for filming.",
                     [{"ref": s["id"], "text": s["hook_en"], "sub": f"{s['ref']} · {s.get('angle', 'price-reveal')} · {s.get('via')}"} for s in approved],
                     "No approved script yet."),
            _section("Playbook", "Structures that worked on our own posts, with the posts that prove it.",
                     [{"ref": p["id"], "text": p.get("structure") or p.get("text") or "entry", "sub": None} for p in plays],
                     "Empty until we have 5 or more posts of our own to learn from."),
            _section("What to post next", "Each angle on our own posts against our median.",
                     [{"ref": None, "text": f"{a['angle']}: {a['status']}", "sub": a["why"]} for a in st["angles"]], ""),
            _section("Who we compete with", "Accounts a person set; their posts are scored against their own usual.",
                     [{"ref": None, "text": "@" + c, "sub": None} for c in comp], "None set. Add them in the Studio."),
            _section("Listings we can advertise", "Only listings with a permit number.",
                     _items(g, [n for n in g.of("listing") if n.props.get("permit")]), "No permitted listing."),
        ]}
    facts = g.of("fact")
    live = [n for n in facts if n.status == "live"]
    replaced = [n for n in facts if n.status == "superseded"]
    work = [n for n in g.of("task", status="queued") if dept_of(n.props.get("agent") or "nova") == dept]
    common = [_section("Open work", "Tasks this department's agents are holding.", _items(g, work), "Nothing open."), lessons(g, dept)]
    if dept == "sales":
        secs = [_section("Deal memory: live facts", "Each one is a customer's exact words, with the meeting it came from.", _items(g, live), "Nothing heard yet."),
                _section("Replaced statements", "Kept, never deleted; anything built on them is withdrawn.", _items(g, replaced), "None.")]
    elif dept == "records":
        secs = [_section("Archive", "Filed documents.", _items(g, g.of("document")), "Nothing filed."),
                _section("Sales ledger", "Closed sales; every figure the analyst gives is counted from these.", _items(g, g.of("sale")), "No sales.")]
    elif dept == "review":
        secs = [_section("Live facts", "What review checks every draft against.", _items(g, live), "None."),
                _section("Replaced", "A draft citing one of these is sent back.", _items(g, replaced), "None.")]
    elif dept == "comp":
        secs = [_section("Checks raised", "Compliance hears every payment change first; it never decides suspicion.", _items(g, g.of("check")), "None raised."),
                _section("Payment facts", "What was said about who pays and how.",
                         _items(g, [n for n in live if n.props.get("kind") in ("payer", "payment_promise", "income_claim")]), "None.")]
    elif dept == "fin":
        secs = [_section("Ledger: expected payments", "Each rests on the exact words it came from.",
                         _items(g, [n for n in live if n.props.get("kind") in ("payment_promise", "payer", "price")]), "None.")]
    elif dept == "ops":
        secs = [_section("Deals in progress", "Form F is filled from live facts only and stops before Submit.", _items(g, g.of("deal")), "No deals.")]
    else:
        secs = [_section("Lobby board", "Jobs Nova handed to people, with read-back and deadlines.", _items(g, g.of("lobby")), "Empty."),
                _section("Company knowledge", "Confirmed by a person.", _items(g, g.of("knowledge", status="confirmed")), "None.")]
    names = {"sales": "Deal memory", "records": "Archive", "review": "Live facts", "comp": "Rule book", "fin": "Ledger", "ops": "Portal", "front": "Lobby board"}
    return {"title": names.get(dept, "Memory"), "about": "What this department remembers, straight from the office's log.", "sections": secs + common}
