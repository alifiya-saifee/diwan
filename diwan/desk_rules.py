"""The Deal desk's rules, as the owner's settings: the cash-report limit, VAT, and for each paperwork path (a ready home
bought from its owner, an off-plan unit bought from a developer, a rental) its steps and who each waits on, its usual
deposit and commission, and its closing checklist. Dubai's usual practice is filled in as the defaults, so a new office
works at once and the owner changes only what differs; every change is a `setting.changed` (person "desk", key
"rules") with who made it.

Which path a deal follows comes from its sales desk (the owner's deal kinds, person "sales", key "kinds"): a desk for
rent is the rental path, a desk for off-plan sales the off-plan path, anything else the ready path.

A step marked "after" keeps running once the deal has closed (an off-plan handover can be years after our commission is
paid). The developers we sell for are the owner's too: each agreement's rate, and how much of the price the buyer must
have paid before the developer owes it. What one deal's signed documents say (the agency form and its rate, another
agency's share, the developer, the tenancy dates) is that deal's terms: person "deal:<id>", key "terms".
"""
from __future__ import annotations

import copy
from datetime import date

from diwan import roles
from diwan.graph import Graph
from diwan.people import PEOPLE

ROLES = {"broker": "the deal's broker", "finance": "Finance", "compliance": "Compliance", "transactions": "the transactions officer"}

DEFAULTS = {
    "cash_report_aed": 55_000,  # a real-estate cash payment at or above this is reported to the FIU (goAML)
    "vat_pct": 5,
    "stuck_days": 7,  # a deal with no step done in this many days counts as stuck
    "close_days_target": 60,  # the owner's target from "yes" to closed
    "developers": [],  # [{"name", "commission_pct", "payable_after_pct"}], one per developer agency agreement
    "paths": {
        "ready": {
            "name": "Ready home, bought from its owner",
            "deposit_pct": 10, "commission_pct": 2, "commission_from": "buyer", "dld_fee_pct": 4,
            "steps": [["Form F signed by buyer, seller and both brokers", "the buyer and the seller"],
                      ["Buyer's mortgage: valuation and the bank's final offer", "the buyer's bank"],
                      ["Seller's mortgage cleared: liability and clearance letters", "the seller's bank"],
                      ["Developer NOC for the transfer", "the seller and the developer"],
                      ["Manager's cheques for the seller and the DLD fee", "the buyer"],
                      ["Trustee office appointment booked", "the transactions officer"],
                      ["Title deed issued to the buyer", "the Dubai Land Department"],
                      ["Handover: keys, access cards and utilities moved", "the seller"]],
            "closing": [["figures", "Final price and commission confirmed", "broker"], ["invoice", "Commission invoiced and paid", "finance"],
                        ["compliance", "Every compliance item closed", "compliance"], ["docs", "Title deed copy, Form F and receipts filed", "transactions"]],
        },
        "offplan": {
            "name": "Off-plan unit, bought from a developer",
            "deposit_pct": 10, "commission_pct": 2, "commission_from": "developer", "dld_fee_pct": 4,
            "steps": [["Reservation form and the developer's KYC", "the buyer and the developer"],
                      ["SPA signed with the developer; the payment plan entered", "the buyer and the developer"],
                      ["Oqood registered with the DLD", "the developer"],
                      ["Handover: snagging, final payment and keys", "the developer", "after"],
                      ["Title deed replaces the Oqood registration", "the developer and the DLD", "after"]],
            "closing": [["figures", "Final price and the developer's commission confirmed", "broker"], ["invoice", "Commission invoiced to the developer and paid", "finance"],
                        ["compliance", "Every compliance item closed", "compliance"], ["docs", "SPA, Oqood certificate and receipts filed", "transactions"]],
        },
        "rent": {
            "name": "Rental",
            "deposit_pct": 5, "deposit_pct_furnished": 10, "commission_pct": 5, "commission_from": "tenant", "renewal_notice_days": 90,
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
NUMBERS = ("deposit_pct", "deposit_pct_furnished", "commission_pct", "dld_fee_pct")
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
    for key, label, top in (("stuck_days", "A deal is stuck after", 365), ("close_days_target", "The target from yes to closed", 3650)):
        if not isinstance(r.get(key), int) or not 0 < r[key] <= top:
            errs.append(f"{label} is a whole number of days between 1 and {top}")
    names = [str(d.get("name", "")).strip().lower() for d in r.get("developers") or []]
    for d in r.get("developers") or []:
        if not str(d.get("name", "")).strip():
            errs.append("Every developer agreement needs the developer's name")
        for n in ("commission_pct", "payable_after_pct"):
            if not isinstance(d.get(n), (int, float)) or not 0 <= d[n] <= 100:
                errs.append(f"{d.get('name') or 'A developer'}: {n.replace('_', ' ')} is a percentage between 0 and 100")
    if len(set(names)) != len(names):
        errs.append("Each developer has one agreement")
    for pid in PATHS:
        p = r["paths"][pid]
        for n in NUMBERS:
            if n in p and (not isinstance(p[n], (int, float)) or not 0 <= p[n] <= 100):
                errs.append(f"{p['name']}: {n.replace('_', ' ')} is a percentage between 0 and 100")
        if p.get("commission_from") not in PAYERS:
            errs.append(f"{p['name']}: commission is paid by one of {', '.join(PAYERS)}")
        steps = p.get("steps") or []
        if not steps or any(not (isinstance(s, list) and len(s) in (2, 3) and str(s[0]).strip() and str(s[1]).strip()
                                 and (len(s) == 2 or s[2] == "after")) for s in steps):
            errs.append(f"{p['name']}: every step needs what it is and who it waits on")
        if all(len(s) == 3 for s in steps):
            errs.append(f"{p['name']}: at least one step comes before closing")
        if "renewal_notice_days" in p and (not isinstance(p["renewal_notice_days"], int) or not 0 < p["renewal_notice_days"] <= 365):
            errs.append(f"{p['name']}: the renewal notice is a whole number of days between 1 and 365")
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
    for k in ("cash_report_aed", "stuck_days", "close_days_target"):
        r[k] = int(r[k]) if str(r.get(k, "")).isdigit() else r.get(k)
    r["developers"] = [{"name": str(d.get("name", "")).strip(), "commission_pct": d.get("commission_pct"), "payable_after_pct": d.get("payable_after_pct")}
                       for d in r.get("developers") or []]
    for pid in PATHS:
        p = r["paths"][pid]
        p["steps"] = [[str(s[0]).strip(), str(s[1]).strip()] + (["after"] if len(s) > 2 and s[2] == "after" else []) for s in p.get("steps") or [] if len(s) >= 2]
        if str(p.get("renewal_notice_days", "")).isdigit():
            p["renewal_notice_days"] = int(p["renewal_notice_days"])
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


def developer(g: Graph, name_: str | None) -> dict | None:
    """The owner's agreement with this developer, if there is one."""
    return next((d for d in rules(g)["developers"] if name_ and d["name"].lower() == name_.strip().lower()), None)


# ---------- one deal's terms, from its signed documents ----------

TERMS = {"agreement": "the signed agency agreement (Form A, Form B, the developer's or the listing agreement) and its number",
         "rate_pct": "the commission rate it says", "other_agency": "the other agency, under Form I", "other_share_pct": "their share of the commission",
         "developer": "the developer", "start": "the tenancy start", "end": "the tenancy end", "furnished": "furnished"}
MONEY_TERMS = ("rate_pct", "other_agency", "other_share_pct", "developer")


def terms(g: Graph, deal: str) -> dict:
    return dict(g.settings.get(f"deal:{deal}", {}).get("terms") or {})


def set_terms(office, deal: str, new: dict, *, by: str) -> dict:
    """The broker, the transactions officer or the owner records what the signed documents say. An empty value clears it.
    Once the commission invoice is drafted, the terms it was worked out from are fixed."""
    g = office.graph()
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        raise KeyError(deal)
    if by != d.props.get("broker") and by != roles.holder(g, "transactions") and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError("Only the deal's broker, the transactions officer or the owner records its terms.")
    if unknown := set(new) - set(TERMS):
        raise ValueError(f"Unknown terms: {', '.join(sorted(unknown))}.")
    t = terms(g, deal)
    for k, v in new.items():
        if v in ("", None):
            t.pop(k, None)
        else:
            t[k] = v.strip() if isinstance(v, str) else v
    errs = []
    for k in ("rate_pct", "other_share_pct"):
        if k in t:
            try:
                t[k] = float(t[k]) if not float(t[k]).is_integer() else int(float(t[k]))
            except (TypeError, ValueError):
                t[k] = -1
            if not 0 <= t[k] <= 100:
                errs.append(f"{TERMS[k].capitalize()} is a percentage between 0 and 100")
    if ("other_share_pct" in t) != ("other_agency" in t):
        errs.append("Name the other agency and its share together")
    if "developer" in t and not developer(g, t["developer"]):
        errs.append(f"There is no agreement with {t['developer']}: the owner adds it in the rules first")
    for k in ("start", "end"):
        if k in t:
            try:
                date.fromisoformat(t[k])
            except (TypeError, ValueError):
                errs.append(f"{TERMS[k].capitalize()} is a date (YYYY-MM-DD)")
    if not errs and "start" in t and "end" in t and t["end"] <= t["start"]:
        errs.append("The tenancy ends after it starts")
    if "furnished" in t:
        t["furnished"] = t["furnished"] in (True, "true", "yes", 1)
    if errs:
        raise ValueError("; ".join(errs))
    old = terms(g, deal)
    if any(old.get(k) != t.get(k) for k in MONEY_TERMS) and \
            any(x.props["kind"] == "commission invoice" and x.status != "sent_back" for x in g.of("draft", deal)):
        raise ValueError("The commission invoice is already drafted on these terms; they are fixed now.")
    office.log.append("setting.changed", actor=by, deal=deal, content={"person": f"deal:{deal}", "key": "terms", "value": t})
    return t
