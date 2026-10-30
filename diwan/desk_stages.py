"""A deal's stages on the Deal desk (docs/deal-desk.md item 11): Sales' stages up to Viewed, then the stages of the
deal's paperwork path from the owner's settings, then Closing (read from the closing checklist) and Won. The broker,
the transactions officer and the owner move a deal; moving back and Lost need a reason; Won comes only from closing the
deal. A move is the same `stage.changed` the Inbox writes. Reaching the path's "converted at" stage starts the agency
forms.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan import agency_forms, desk_rules, roles
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
            "closed": bool(cl and cl["sale"]), "movers": sorted(movers(g, deal))}


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
    if (back or stage == "Lost") and not reason.strip():
        raise ValueError("Say why: marking a deal lost or moving it back needs a reason.")
    office.log.append("stage.changed", actor=by, deal=deal, content={"stage": stage, **({"why": reason.strip()} if reason.strip() else {}), "back": back})
    conv = desk_rules.path(g, deal)["converted_at"]
    if stage != "Lost" and order.index(stage) >= order.index(conv):
        agency_forms.on_convert(office, deal, by)
