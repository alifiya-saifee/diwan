"""What the Inbox shows, built from the graph: each conversation's stage, what the buyer is after, how long they have
waited, whether WhatsApp's 24-hour window is open, and the deal behind it. Sending is in agents/reception.py.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.graph import OPEN, Graph
from diwan.office import Office
from diwan.people import name

STAGES = ["New", "Qualified", "Viewing booked", "Viewed", "Offer", "Form F", "Transfer", "Won", "Lost"]
WINDOW = timedelta(hours=24)

# used when no WhatsApp partner is connected, so the template flow can be shown; marked as samples on screen
SAMPLE_TEMPLATES = [
    {"name": "viewing_reminder", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 3,
     "body": "Hi {{1}}, a reminder of your viewing of {{2}} on {{3}}. Reply here if you need to change it."},
    {"name": "still_looking", "status": "SAMPLE", "language": "en", "category": "MARKETING", "params": 2,
     "body": "Hi {{1}}, are you still looking in {{2}}? We have new listings this week."},
    {"name": "documents_request", "status": "SAMPLE", "language": "en", "category": "UTILITY", "params": 1,
     "body": "Hi {{1}}, to prepare your paperwork we need a copy of your passport and Emirates ID. You can send them here."},
]


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def interests(g: Graph, deal: str | None, messages: list[dict]) -> list[dict]:
    """Chips for what the buyer is after, each from their own words or a fact."""
    said = " ".join(m["text"] for m in messages if m["type"] == "received").lower()
    chips = []
    if re.search(r"\brent(al|ing)?\b|\blease\b", said):
        chips.append({"label": "Rent", "kind": "intent"})
    elif re.search(r"\bbuy|purchase|invest|own\b", said) or (deal and g.facts(deal, "deal_term")):
        chips.append({"label": "Buy", "kind": "intent"})
    if re.search(r"off.?plan|handover|payment plan", said):
        chips.append({"label": "Off-plan", "kind": "intent"})
    for comm in sorted({n.props["community"] for n in g.of("listing")}):
        words = [w for w in re.findall(r"[a-z]{4,}", comm.lower()) if w != "dubai"]
        if any(w in said for w in words):
            chips.append({"label": comm.replace("Dubai ", ""), "kind": "area"})
    if m := re.search(r"\b(\d|one|two|three|four|five|studio)\s*-?\s*(bed|br|bedroom)", said):
        chips.append({"label": f"{m.group(1)} bed".replace("studio bed", "Studio"), "kind": "size"})
    if deal and (terms := g.facts(deal, "deal_term")):
        amt = terms[-1].props.get("amount_aed") or 0
        chips.append({"label": f"AED {amt / 1e6:.1f}M" if amt >= 1e6 else f"AED {amt / 1e3:.0f}K", "kind": "budget", "ref": terms[-1].id})
    return chips


def conversation(g: Graph, c, now: datetime) -> dict:
    msgs = c.props["messages"]
    deal = g.nodes.get(f"deal:{c.deal}") if c.deal else None
    last_in = next((m for m in reversed(msgs) if m["type"] == "received"), None)
    last_reply = next((m for m in reversed(msgs) if m["type"] == "sent"), None)
    waiting = None
    if last_in and (not last_reply or last_reply["event"] < last_in["event"]):
        waiting = int((now - _at(last_in["at"])).total_seconds() // 60)
    window_open = bool(last_in) and now - _at(last_in["at"]) < WINDOW
    viewings = [v for v in g.of("viewing", status="booked") if v.props.get("chat") == c.props["phone"]]
    return {
        "phone": c.props["phone"], "name": c.label, "deal": c.deal, "mode": c.props["mode"], "handled_by": c.props.get("handled_by"),
        "stage": (deal.props.get("stage") if deal else None) or "New", "broker": deal.props.get("broker") if deal else None,
        "property": deal.props.get("property") if deal else None, "linked": bool(c.deal and not c.deal.startswith("lead-")),
        "last": msgs[-1] if msgs else None, "last_at": c.props.get("last_at"), "waiting_min": waiting,
        "window_open": window_open, "window_closes": (_at(last_in["at"]) + WINDOW).isoformat() if last_in else None,
        "chips": interests(g, c.deal, msgs),
        "viewing": g.record(viewings[0].id).split(" · ", 1)[1] if viewings else None,
        "failed": sum(1 for m in msgs if m.get("status") == "failed"),
    }


def listing(office: Office, *, view: str = "all", person: str = "omar", stage: str | None = None, q: str = "",
            now: datetime | None = None) -> list[dict]:
    g = office.graph()
    now = now or datetime.now(timezone.utc)
    rows = [conversation(g, c, now) for c in g.of("chat")]
    if view == "mine":
        rows = [r for r in rows if r["handled_by"] == person or (r["mode"] == "human" and r["broker"] == person) or r["broker"] == person]
    elif view == "new":
        rows = [r for r in rows if r["stage"] == "New"]
    elif view == "waiting":
        rows = [r for r in rows if r["waiting_min"] is not None]
    if stage:
        rows = [r for r in rows if r["stage"] == stage]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in r["name"].lower() or ql in r["phone"] or any(ql in ch["label"].lower() for ch in r["chips"])]
    return sorted(rows, key=lambda r: (r["waiting_min"] is None, -(r["waiting_min"] or 0), r["last_at"] or ""), reverse=False)


def counts(office: Office, person: str = "omar") -> dict:
    g, now = office.graph(), datetime.now(timezone.utc)
    rows = [conversation(g, c, now) for c in g.of("chat")]
    return {"all": len(rows), "mine": len([r for r in rows if r["broker"] == person or r["handled_by"] == person]),
            "new": len([r for r in rows if r["stage"] == "New"]), "waiting": len([r for r in rows if r["waiting_min"] is not None]),
            "stages": {s: len([r for r in rows if r["stage"] == s]) for s in STAGES}}


def detail(office: Office, phone: str, now: datetime | None = None) -> dict:
    g = office.graph()
    c = g.nodes[f"chat:{phone}"]
    now = now or datetime.now(timezone.utc)
    base = conversation(g, c, now)
    deal = c.deal
    return base | {
        "messages": c.props["messages"],
        "facts": [{"id": f.id, "text": g.record(f.id).split(" · ", 1)[1], "kind": f.props["kind"]} for f in g.facts(deal)] if deal else [],
        "replaced": [{"id": f.id, "quote": f.props["quote"], "by": f.props.get("superseded_by")} for f in g.of("fact", deal, "superseded")] if deal else [],
        "tasks": [{"id": t.id, "text": t.props["action"], "who": name(t.props.get("needs_person")) if t.props.get("needs_person") else t.props.get("agent_name")}
                  for t in g.of("task", deal, OPEN)] if deal else [],
        "cards": [{"id": n.id, "text": n.props["text"], "who": name(n.props.get("who"))}
                  for typ in ("check", "decision", "question") for n in g.of(typ, deal, "open")] if deal else [],
        "stages": STAGES, "history": (g.nodes[f"deal:{deal}"].props.get("stages", []) if deal else []),
    }


def set_stage(office: Office, phone: str, stage: str, *, by: str) -> None:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    deal = office.graph().nodes[f"chat:{phone}"].deal
    office.log.append("stage.changed", actor=by, deal=deal, content={"stage": stage})


def auto_stage(office: Office, deal: str, cause: int | None = None) -> None:
    """New → Qualified once a budget is stated; → Viewing booked once a viewing is booked. Never moves a deal backwards."""
    g = office.graph()
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        return
    cur = d.props.get("stage") or "New"
    want = cur
    if g.facts(deal, "deal_term") and STAGES.index(cur) < STAGES.index("Qualified"):
        want = "Qualified"
    if any(v.deal == deal for v in g.of("viewing", status="booked")) and STAGES.index(want) < STAGES.index("Viewing booked"):
        want = "Viewing booked"
    if want != cur:
        office.log.append("stage.changed", actor="rania", agent="rania", deal=deal, caused_by=cause, content={"stage": want, "auto": True})


def quick_replies(g: Graph) -> list[dict]:
    out = [{"title": k.props["title"], "text": k.props["text"]} for k in g.of("knowledge", status="confirmed")]
    return out + [{"title": "Viewing confirmed", "text": "Your viewing is confirmed. Please bring a photo ID for the building lobby."},
                  {"title": "Send documents", "text": "Could you send a copy of your passport and Emirates ID here when you have a moment?"}]


def render(body: str, params: list[str]) -> str:
    return re.sub(r"\{\{(\d+)\}\}", lambda m: params[int(m.group(1)) - 1] if int(m.group(1)) - 1 < len(params) else m.group(0), body)
