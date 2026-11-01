"""The gates a sale passes before anything goes to the trustee (docs/deal-desk.md item 18): Compliance cleared, the deposit
marked received, the paperwork signed, Review clean, and the owner's approval pinned to the facts that stand now. All of
it is read from the record, so a replaced fact reopens the gate by itself. A gate is never ticked by hand, except the
owner's, which is a real approval. When all pass the deal is `deal.ready_for_transfer` and Operations books the trustee.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan import agency_forms, desk_rules, roles
from diwan.agents import compliance, finance
from diwan.graph import Graph
from diwan.people import PEOPLE, name

if TYPE_CHECKING:
    from diwan.office import Office


def applies(g: Graph, deal: str) -> bool:
    """Only a path with a step waiting on the gate has one (a ready sale's trustee booking, unless the owner changed it)."""
    return any(s[2:] == ["gate"] for s in desk_rules.path(g, deal)["steps"])


def formf_signed(g: Graph, deal: str) -> bool:
    live = [d.id for d in g.of("draft", deal) if d.props["kind"] == "Form F" and d.status != "sent_back"]
    return any(x.props.get("kind") == "Form F" and x.status != "voided" and any(f"({d})" in x.props.get("title", "") for d in live) for x in g.of("document", deal))


def _approval(g: Graph, deal: str):
    return next((a for a in reversed(g.of("approval", deal)) if a.props["action"].startswith("Ready for transfer") and a.status in ("given", "executed") and not g.stale(a.id)), None)


def view(g: Graph, deal: str) -> dict:
    comp = compliance.state(g, deal)
    pays = [t for t in g.of("task", deal) if t.props["agent"] == "pay"]
    got = [t for t in pays if finance.settled(t)]
    held = [t for t in pays if t.props.get("result") == "received" and not finance.settled(t)]
    waiting = agency_forms.unsigned(g, deal)
    signed = formf_signed(g, deal)
    back = [d for d in g.of("draft", deal) if d.status == "sent_back" and d.props["kind"] in ("Form F", "commission invoice", *agency_forms.FORM_OF)
            and not any(x.props["kind"] == d.props["kind"] and x.status != "sent_back" for x in g.of("draft", deal))]
    a = _approval(g, deal)
    owner = next((p for p, v in PEOPLE.items() if v.get("role") == "Owner"), None)
    gates = [{"key": "compliance", "label": "Compliance", "ok": comp["ok"], "note": "Cleared on the current facts" if comp["ok"] else compliance.public_reason(comp), "who": roles.holder(g, "compliance")},
             {"key": "finance", "label": "Finance", "ok": bool(got), "note": f"{len(got)} payment{'s' if len(got) != 1 else ''} marked received" if got
              else "A payment is with Compliance before its receipt" if held else "No deposit marked received yet", "who": roles.holder(g, "finance")},
             {"key": "paperwork", "label": "Paperwork", "ok": not waiting and signed, "note": "Forms signed" if not waiting and signed else
              f"{' and '.join(waiting)} to sign" if waiting else "Form F to sign", "who": g.nodes[f"deal:{deal}"].props.get("broker")},
             {"key": "review", "label": "Review", "ok": not back, "note": "Nothing sent back" if not back else f"{back[0].props['kind']} was sent back: {back[0].props.get('reason') or 'redo it'}", "who": roles.holder(g, "transactions")},
             {"key": "owner", "label": "Owner", "ok": bool(a), "note": f"Approved as {a.id}" if a else f"{name(owner)} approves last, on the current facts", "who": owner}]
    ready = g.nodes[f"deal:{deal}"].props.get("ready")
    return {"applies": applies(g, deal), "gates": gates, "open": all(x["ok"] for x in gates), "can_approve": all(x["ok"] for x in gates if x["key"] != "owner") and not a,
            "ready": bool(ready and a), "ready_at": ready["at"] if ready and a else None}


def is_ready(g: Graph, deal: str) -> bool:
    return view(g, deal)["ready"]


def approve(office: Office, deal: str, by: str) -> str:
    """The owner's yes on the facts that stand now, the last gate. Run, it tells Operations the deal is ready."""
    g = office.graph()
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    if not roles.is_owner(by):
        raise PermissionError("Only the owner approves the transfer.")
    v = view(g, deal)
    if left := [x for x in v["gates"] if not x["ok"] and x["key"] != "owner"]:
        raise ValueError("Not yet: " + "; ".join(f"{x['label']}: {x['note']}" for x in left) + ".")
    if v["ready"]:
        raise ValueError("This deal is already ready for transfer.")
    facts = [f.id for f in g.facts(deal)]
    aid = office.approve(deal, by, f"Ready for transfer: {g.nodes[f'deal:{deal}'].props['property']}", facts)
    r = office.execute(aid, f"ready:{aid}")
    if not r["ok"]:
        raise ValueError(r["because"])
    office.log.append("deal.ready_for_transfer", actor=by, deal=deal, content={"approval": aid, "facts": facts})
    return aid
