"""Offers on a deal: each one, and each counter, with who made it, the amount and when, until one is accepted. Accepting agrees nothing by itself: the deal
converts when a person enters the price, which is what starts Compliance, the deposit and the forms."""
from __future__ import annotations

from diwan import desk_stages
from diwan.events import EventLog
from diwan.graph import Graph
from diwan.office import Office
from diwan.people import name

SIDES = {"client": "Client", "seller": "Seller or landlord"}


def rows(log: EventLog, deal: str) -> list[dict]:
    out: dict[str, dict] = {}
    for e in log.list():
        if e.get("deal") != deal:
            continue
        c = e["content"]
        if e["type"] == "offer.made":
            out[c["id"]] = {"id": c["id"], "side": c["side"], "side_label": SIDES[c["side"]], "amount": c["amount"], "note": c.get("note") or "", "by": e["actor"], "by_name": name(e["actor"]), "at": e["at"], "status": "open"}
        elif e["type"] in ("offer.accepted", "offer.declined") and c["id"] in out:
            out[c["id"]] |= {"status": e["type"].split(".")[1], "decided_by": name(e["actor"])}
    return list(out.values())


def _mover(g: Graph, deal: str, by: str) -> None:
    if by not in desk_stages.movers(g, deal):
        raise PermissionError("Only the deal's broker, the transactions officer or the owner records offers.")


def make(office: Office, deal: str, by: str, side: str, amount, note: str = "") -> dict:
    g = office.graph()
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    _mover(g, deal, by)
    if side not in SIDES:
        raise ValueError("Whose offer is it: the client's or the seller's?")
    try:
        amount = int(round(float(amount)))
    except (TypeError, ValueError):
        raise ValueError("Enter the offer in dirhams.") from None
    if amount <= 0:
        raise ValueError("Enter the offer in dirhams.")
    if g.nodes[f"deal:{deal}"].props.get("stage") in ("Won", "Lost") or g.settings.get(f"deal:{deal}", {}).get("agreed"):
        raise ValueError("The price on this deal is already agreed.")
    n = len(rows(office.log, deal)) + 1
    oid = f"O{n}"
    for o in rows(office.log, deal):  # a new figure answers the one before it
        if o["status"] == "open":
            office.log.append("offer.declined", actor=by, deal=deal, content={"id": o["id"], "countered": oid})
    ev = office.log.append("offer.made", actor=by, deal=deal, content={"id": oid, "side": side, "amount": amount, "note": note.strip()})
    order, now = desk_stages.stages(g, deal), g.nodes[f"deal:{deal}"].props.get("stage") or "New"
    if "Offer" in order and now in order and order.index(now) < order.index("Offer"):
        desk_stages.move(office, deal, "Offer", by, "")
    return {"id": oid, "event": ev["id"]}


def decide(office: Office, deal: str, oid: str, by: str, accept: bool) -> dict:
    _mover(office.graph(), deal, by)
    o = next((x for x in rows(office.log, deal) if x["id"] == oid), None)
    if not o:
        raise KeyError(oid)
    if o["status"] != "open":
        raise ValueError(f"That offer is already {o['status']}.")
    office.log.append("offer.accepted" if accept else "offer.declined", actor=by, deal=deal, content={"id": oid})
    return {"amount": o["amount"], "status": "accepted" if accept else "declined"}


def lines(office: Office, deals: list) -> list[str]:
    """For Nova: where each negotiation stands."""
    out = []
    for x in deals:
        if row := rows(office.log, x.deal):
            o = row[-1]
            out.append(f"Offers on {x.props.get('customer')}: {len(row)} so far, latest AED {o['amount']:,} from the {o['side_label'].lower()}, {o['status']}.")
    return out
