"""The Deal desk's rules, as the owner's settings: the cash-report limit, VAT, and for each paperwork path (a ready home
bought from its owner, an off-plan unit bought from a developer, a rental) its steps and who each waits on, its usual
deposit and commission, and its closing checklist. Dubai's usual practice is filled in as the defaults, so a new office
works at once and the owner changes only what differs; every change is a `setting.changed` (person "desk", key
"rules") with who made it.

Which path a deal follows comes from its sales desk (the owner's deal kinds, person "sales", key "kinds"): a desk for
rent is the rental path, a desk for off-plan sales the off-plan path, anything else the ready path.
"""
from __future__ import annotations

import copy

from diwan.graph import Graph
from diwan.people import PEOPLE

ROLES = {"broker": "the deal's broker", "finance": "Finance", "compliance": "Compliance", "transactions": "the transactions officer"}

DEFAULTS = {
    "cash_report_aed": 55_000,  # a real-estate cash payment at or above this is reported to the FIU (goAML)
    "vat_pct": 5,
    "paths": {
        "ready": {
            "name": "Ready home, bought from its owner",
            "deposit_pct": 10, "commission_pct": 2, "commission_from": "buyer",
            "steps": [["Form F signed by buyer, seller and both brokers", "the buyer and the seller"],
                      ["Developer NOC for the transfer", "the seller and the developer"],
                      ["Manager's cheques for the seller and the DLD fee", "the buyer"],
                      ["Trustee office appointment booked", "the transactions officer"],
                      ["Title deed issued to the buyer", "the Dubai Land Department"]],
            "closing": [["figures", "Final price and commission confirmed", "broker"], ["invoice", "Commission invoiced and paid", "finance"],
                        ["compliance", "Every compliance item closed", "compliance"], ["docs", "Title deed copy, Form F and receipts filed", "transactions"]],
        },
        "offplan": {
            "name": "Off-plan unit, bought from a developer",
            "deposit_pct": 10, "commission_pct": 2, "commission_from": "developer",
            "steps": [["Reservation form and booking amount", "the buyer"],
                      ["SPA signed with the developer", "the buyer and the developer"],
                      ["Oqood registered with the DLD", "the developer"],
                      ["Instalments paid on the plan", "the buyer"],
                      ["Handover and title deed", "the developer"]],
            "closing": [["figures", "Final price and the developer's commission confirmed", "broker"], ["invoice", "Commission invoiced to the developer and paid", "finance"],
                        ["compliance", "Every compliance item closed", "compliance"], ["docs", "SPA, Oqood certificate and receipts filed", "transactions"]],
        },
        "rent": {
            "name": "Rental",
            "deposit_pct": 5, "deposit_pct_furnished": 10, "commission_pct": 5, "commission_from": "tenant",
            "steps": [["Tenancy contract signed", "the tenant and the landlord"],
                      ["Security deposit and agency fee received", "the tenant"],
                      ["Rent cheques collected", "the tenant"],
                      ["Ejari registered", "the transactions officer"],
                      ["Move-in inspection and keys", "the tenant and the landlord"]],
            "closing": [["figures", "Final rent and agency fee confirmed", "broker"], ["invoice", "Agency fee received", "finance"],
                        ["compliance", "Tenant's ID and screening closed", "compliance"], ["docs", "Ejari certificate, contract and inventory filed", "transactions"]],
        },
    },
}
PATHS = tuple(DEFAULTS["paths"])
NUMBERS = ("deposit_pct", "deposit_pct_furnished", "commission_pct")
PAYERS = ("buyer", "seller", "developer", "tenant", "landlord")


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def rules(g: Graph) -> dict:
    """The defaults with the owner's changes on top."""
    return _merge(DEFAULTS, g.settings.get("desk", {}).get("rules") or {})


def changed(g: Graph) -> bool:
    return bool(g.settings.get("desk", {}).get("rules"))


def path_of(g: Graph, deal: str) -> str:
    """The paperwork path a deal follows: the one the broker set on the deal, else its sales desk's listing filter."""
    if (chosen := g.settings.get(f"deal:{deal}", {}).get("path")) in PATHS:
        return chosen
    d = g.nodes.get(f"deal:{deal}")
    desk = next((k for k in g.settings.get("sales", {}).get("kinds") or [] if d and k.get("id") == d.props.get("kind")), None)
    li = (desk or {}).get("listings") or {}
    if li.get("offering") == "rent":
        return "rent"
    if li.get("completion") == "off_plan":
        return "offplan"
    return "ready"


def path(g: Graph, deal: str) -> dict:
    return rules(g)["paths"][path_of(g, deal)] | {"id": path_of(g, deal)}


def validate(r: dict) -> list[str]:
    errs = []
    if not isinstance(r.get("cash_report_aed"), int) or r["cash_report_aed"] <= 0:
        errs.append("The cash-report limit is a whole number of dirhams above zero")
    if not isinstance(r.get("vat_pct"), (int, float)) or not 0 <= r["vat_pct"] <= 100:
        errs.append("VAT is a percentage between 0 and 100")
    for pid in PATHS:
        p = r["paths"][pid]
        for n in NUMBERS:
            if n in p and (not isinstance(p[n], (int, float)) or not 0 <= p[n] <= 100):
                errs.append(f"{p['name']}: {n.replace('_', ' ')} is a percentage between 0 and 100")
        if p.get("commission_from") not in PAYERS:
            errs.append(f"{p['name']}: commission is paid by one of {', '.join(PAYERS)}")
        steps = p.get("steps") or []
        if not steps or any(not (isinstance(s, list) and len(s) == 2 and str(s[0]).strip() and str(s[1]).strip()) for s in steps):
            errs.append(f"{p['name']}: every step needs what it is and who it waits on")
        if [c[0] for c in p.get("closing") or []] != ["figures", "invoice", "compliance", "docs"] or \
                any(c[2] not in ROLES or not str(c[1]).strip() for c in p["closing"]):
            errs.append(f"{p['name']}: the closing checklist keeps its four items, each with a role")
    return errs


def save(office, new: dict, *, by: str) -> dict:
    """The owner replaces the rules; what is stored is only what differs from the defaults, so a later default change
    still reaches an office that never touched that rule."""
    if PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError("Only the owner changes the Deal desk's rules.")
    r = _merge(DEFAULTS, new)
    r["cash_report_aed"] = int(r["cash_report_aed"]) if str(r.get("cash_report_aed", "")).isdigit() else r.get("cash_report_aed")
    for pid in PATHS:
        r["paths"][pid]["steps"] = [[str(a).strip(), str(b).strip()] for a, b in r["paths"][pid].get("steps") or []]
    if errs := validate(r):
        raise ValueError("; ".join(errs))
    office.log.append("setting.changed", actor=by, content={"person": "desk", "key": "rules", "value": _diff(DEFAULTS, r)})
    return r


def _diff(base: dict, new: dict) -> dict:
    out = {}
    for k, v in new.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            if d := _diff(base[k], v):
                out[k] = d
        elif base.get(k) != v:
            out[k] = v
    return out


def set_path(office, deal: str, path_id: str, *, by: str) -> None:
    """The broker (or the owner) says which path a deal follows when its sales desk doesn't, once, before paperwork starts."""
    g = office.graph()
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        raise KeyError(deal)
    if path_id not in PATHS:
        raise ValueError(f"The path is one of {', '.join(PATHS)}.")
    if by not in (d.props.get("broker"),) and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError("Only the deal's broker or the owner says which path it follows.")
    if any(t.props["agent"] in ("transfer", "formf") for t in g.of("task", deal)):
        raise ValueError("The paperwork has started, so the path is fixed.")
    office.log.append("setting.changed", actor=by, deal=deal, content={"person": f"deal:{deal}", "key": "path", "value": path_id})
