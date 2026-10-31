"""A deal's stages on the Deal desk (docs/deal-desk.md item 11): Sales' stages up to Viewed, then the stages of the
deal's paperwork path from the owner's settings, then Closing (read from the closing checklist) and Won. The broker,
the transactions officer and the owner move a deal; moving back and Lost need a reason; Won comes only from closing the
deal. A move is the same `stage.changed` the Inbox writes. Reaching the path's "converted at" stage starts the agency
forms.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan import agency_forms, deal_property, desk_rules, roles
from diwan.graph import Graph
from diwan.people import PEOPLE, name

if TYPE_CHECKING:
    from diwan.office import Office


def stages(g: Graph, deal: str) -> list[str]:
    return desk_rules.SALES_STAGES + desk_rules.path(g, deal)["stages"]


def stages_for_path(g: Graph, path_id: str) -> list[str]:
    """For the Inbox: a path's whole stage list (Front desk & Sales' item B)."""
    return desk_rules.SALES_STAGES + desk_rules.rules(g)["paths"][path_id]["stages"]


def movers(g: Graph, deal: str) -> set[str]:
    d = g.nodes[f"deal:{deal}"].props
    owner = {p for p, v in PEOPLE.items() if v.get("role") == "Owner"}
    return {x for x in {d.get("broker"), roles.holder(g, "transactions")} | owner if x}


def view(g: Graph, deal: str) -> dict:
    from diwan.agents import operations
    d = g.nodes[f"deal:{deal}"].props
    cl = operations.closing(g, deal)
    return {"list": stages(g, deal), "current": d.get("stage") or "New", "converted_at": desk_rules.path(g, deal)["converted_at"],
            "closing": {"done": sum(i["done"] for i in cl["items"]), "of": len(cl["items"]),
                        "waiting": [i["text"] for i in cl["items"] if not i["done"]]} if cl and not cl["sale"] else None,
            "closed": bool(cl and cl["sale"]), "movers": sorted(movers(g, deal)), "agreed": agreed(g, deal),
            "listing_aed": compare(g, deal, 1)["listing_aed"], "limit": desk_rules.rules(g)["discount_approval_pct"],
            "pending": {"task": p.id, "text": p.props["action"], "pct": p.props.get("pct")} if (p := pending(g, deal)) else None,
            "property": deal_property.view(g, deal), "lost_reasons": desk_rules.rules(g)["lost_reasons"]}


def move(office: Office, deal: str, stage: str, by: str, reason: str = "") -> None:
    g = office.graph()
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        raise KeyError(deal)
    if by not in movers(g, deal):
        raise PermissionError(f"Only {name(d.props.get('broker'))} (the broker), the transactions officer or the owner moves this deal.")
    from diwan.agents import operations
    cl = operations.closing(g, deal)
    if cl and cl["sale"]:
        raise ValueError(f"The deal is closed ({cl['sale']}); a closed deal is corrected only by a new entry.")
    if stage == "Won":
        raise ValueError("Won comes from closing the deal, once its closing checklist is done.")
    order, now = stages(g, deal), d.props.get("stage") or "New"
    if stage != "Lost" and stage not in order:
        raise ValueError(f"{stage!r} isn't one of this deal's stages: {', '.join(order)}.")
    if stage == now:
        raise ValueError(f"The deal is already at {stage}.")
    back = now == "Lost" or (stage != "Lost" and now in order and order.index(stage) < order.index(now))
    conv = desk_rules.path(g, deal)["converted_at"]
    if stage != "Lost" and order.index(stage) >= order.index(conv) and not agreed(g, deal):
        raise ValueError("Enter the agreed price to convert the deal.")
    if (back or stage == "Lost") and not reason.strip():
        raise ValueError("Say why: marking a deal lost or moving it back needs a reason.")
    returning = now == "Lost" and stage != "Lost" and bool(agreed(g, deal))
    if returning:
        deal_property.back_from_lost(g, deal)
    office.log.append("stage.changed", actor=by, deal=deal, content={"stage": stage, **({"why": reason.strip()} if reason.strip() else {}), "back": back})
    if stage == "Lost":
        office.log.append("case.lost", actor=by, agent="ops", deal=deal, content={"reason": reason.strip()})
        deal_property.lost(office, deal, by)
        _money_on_lost(office, deal)
    elif returning:
        deal_property.reserve(office, deal, by)
    if stage != "Lost" and order.index(stage) >= order.index(conv):
        agency_forms.on_convert(office, deal, by)


def _money_on_lost(office: Office, deal: str) -> None:
    """A lost deal with money marked in: what happens to it is the owner's call with the lawyer, never an agent's. Open expectations end."""
    from diwan.agents import finance
    from diwan.graph import OPEN
    g = office.graph()
    for t in g.of("task", deal):
        if t.props["agent"] == "pay" and t.status in OPEN and not finance.paid(t):
            office.log.append("task.withdrawn", actor="pay", agent="pay", deal=deal, content={"id": t.id, "reason": "The deal was lost"})
    if (held := finance.paid_in(g, deal)):
        owner = next((p for p, v in PEOPLE.items() if v.get("role") == "Owner"), None)
        office.log.append("question.asked", actor="pay", agent="pay", deal=deal, content={"to": owner, "refs": [], "kind": "deposit",
                          "text": f"This deal was lost with AED {held:,} marked received. Decide with the lawyer what the signed terms say: keep it, return it, or pass it on. Nothing moves until you do."})


# ---------- converting: the agreed price, against the listing's ----------

def agreed(g: Graph, deal: str) -> dict | None:
    return g.settings.get(f"deal:{deal}", {}).get("agreed")


def compare(g: Graph, deal: str, amount: int, li=None) -> dict:
    """The agreed price against our listing's (`li`, or the deal's own): a discount (below) or a premium (above), and
    whether the owner approves it."""
    li = li or agency_forms.our_listing(g, deal)
    if not li or not li.props.get("price_aed"):
        return {"listing_aed": None, "amount": amount, "pct": None, "diff": None, "needs_owner": False}
    base = li.props["price_aed"]
    pct = round((amount - base) * 100 / base, 1)
    return {"listing_aed": base, "listing": li.props["ref"], "amount": amount, "pct": pct, "diff": amount - base,
            "needs_owner": -pct > desk_rules.rules(g)["discount_approval_pct"]}


def pending(g: Graph, deal: str):
    return next((t for t in g.of("task", deal) if t.props.get("step") == "discount" and t.status in ("queued", "open", "working", "waiting")), None)


def convert(office: Office, deal: str, by: str, amount, prop: dict | None = None) -> dict:
    """The client said yes: the broker (or the transactions officer, or the owner) enters the agreed price and says which
    property it is. Within the owner's discount limit the deal converts at once; further below the listing it waits for
    the owner's approval."""
    g = office.graph()
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        raise KeyError(deal)
    if by not in movers(g, deal):
        raise PermissionError(f"Only {name(d.props.get('broker'))} (the broker), the transactions officer or the owner converts this deal.")
    try:
        amount = int(round(float(amount)))
    except (TypeError, ValueError):
        raise ValueError("Enter the agreed price in dirhams.") from None
    if amount <= 0:
        raise ValueError("Enter the agreed price in dirhams.")
    if agreed(g, deal):
        raise ValueError("The deal is already converted; a new price is recorded as a correction.")
    if pending(g, deal):
        raise ValueError("A discount on this deal is waiting for the owner.")
    if prop:
        deal_property.save(office, deal, prop, by)
    elif deal_property.needed(g, deal):
        raise ValueError("Say which property it is to convert the deal.")
    g = office.graph()
    c = compare(g, deal, amount)
    if c["needs_owner"]:
        owner = next((p for p, v in PEOPLE.items() if v.get("role") == "Owner"), None)
        office.add_task(deal, "ops", f"Approve a {-c['pct']}% discount on {d.props['property']}: AED {amount:,} against the listing's AED {c['listing_aed']:,}",
                        needs_person=owner, by=by, props={"step": "discount", "amount_aed": amount, "asked_by": by, "pct": c["pct"]})
        return c | {"waiting": name(owner)}
    _record(office, deal, by, amount, c, approved_by=None)
    return c | {"waiting": None}


def decide_discount(office: Office, tid: str, by: str, approve: bool, note: str = "") -> None:
    g = office.graph()
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("step") != "discount":
        raise KeyError(tid)
    if PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError("Only the owner approves a discount above the limit.")
    if t.status not in ("queued", "open", "working", "waiting"):
        raise ValueError(f"{tid} is {t.status}.")
    if not approve and not note.strip():
        raise ValueError("Say why, so the broker can tell the client.")
    office.log.append("task.done", actor=by, agent="ops", deal=t.deal,
                      content={"id": tid, "reason": ("Approved" if approve else "Refused") + (f": {note.strip()}" if note.strip() else ""),
                               "result": "approved" if approve else "refused"})
    if approve:
        _record(office, t.deal, t.props["asked_by"], t.props["amount_aed"], compare(office.graph(), t.deal, t.props["amount_aed"]), approved_by=by)
    else:
        d = g.nodes[f"deal:{t.deal}"].props
        office.log.append("question.asked", actor=by, deal=t.deal, content={"to": d["broker"], "refs": [], "kind": "discount",
                          "text": f"{name(by)} didn't approve AED {t.props['amount_aed']:,} for {d['property']}: {note.strip()}"})


def _record(office: Office, deal: str, by: str, amount: int, c: dict, *, approved_by: str | None) -> None:
    """The agreed price becomes the deal's price (a fact, so commission, forms and Form F rest on it and a later change
    sends them back), the comparison is kept for the KPIs, and the deal moves to its conversion stage."""
    g = office.graph()
    live = (g.facts(deal, "deal_term") or [None])[-1]
    if not live or live.props.get("amount_aed") != amount:
        office.record_fact(deal, "deal_term", f"Agreed price, entered by {name(by)} at conversion: AED {amount:,}", name(by), actor=by,
                           replaces=live.id if live else None, amount_aed=amount)
    office.log.append("setting.changed", actor=by, deal=deal, content={"person": f"deal:{deal}", "key": "agreed",
                      "value": {k: c.get(k) for k in ("listing_aed", "amount", "pct", "diff")} | {"by": by, "approved_by": approved_by}})
    conv = desk_rules.path(office.graph(), deal)["converted_at"]
    if (office.graph().nodes[f"deal:{deal}"].props.get("stage") or "New") != conv:
        move(office, deal, conv, by, "converted" if _is_back(office.graph(), deal, conv) else "")
    deal_property.reserve(office, deal, by)
    g = office.graph()
    office.log.append("case.converted", actor=by, agent="ops", deal=deal, content={"amount": amount, "path": desk_rules.path_of(g, deal), "facts": [f.id for f in g.facts(deal)]})


def _is_back(g: Graph, deal: str, stage: str) -> bool:
    order, now = stages(g, deal), g.nodes[f"deal:{deal}"].props.get("stage") or "New"
    return now == "Lost" or (now in order and order.index(stage) < order.index(now))
