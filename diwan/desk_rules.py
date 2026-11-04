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
    "discount_approval_pct": 5,
    "sign_link_days": 14,
    "transfer_chase_days": 3,  # a transfer step that has waited this long on its party gets a chase drafted  # how long a signing or documents link works
    "documents": {"buyer": ["eid_front", "eid_back", "passport", "visa"], "seller": ["eid_front", "eid_back", "passport", "title_deed"],
                  "tenant": ["eid_front", "eid_back", "passport", "visa"], "landlord": ["eid_front", "eid_back", "passport", "title_deed"]},  # what each party sends
    # who the party is changes what they send (common Dubai practice: the conveyancer confirms these lists)
    "docs_by_party": {"resident": [], "non_resident": ["passport", "proof_of_address"], "gcc": ["passport"],
                      "company": ["trade_licence", "moa", "board_resolution", "signatory_id", "ownership_declaration"],
                      "offshore": ["trade_licence", "moa", "board_resolution", "signatory_id", "ownership_declaration", "incorporation", "good_standing", "registers"],
                      "poa": ["poa", "attorney_id", "passport"]},
    "docs_ladder_hours": [24, 48, 72],  # missing documents: Rania nudges, then the broker calls, then the owner hears
    "doc_expiry_warn_days": 30, "good_standing_days": 180,
    "sof_threshold_aed": 0,  # source of funds is asked from this price up, on high risk, or for a PEP (the compliance officer sets it)
    "broker_share_pct": 50,  # what the broker keeps of our commission (the owner sets it)
    "invoice_due_days": 30, "invoice_reminder_days": [1, 7, 14],  # days after the due date
    "payment_reminder_days": [14, 3],  # days before an instalment or a rent cheque
    "transfer_bring": ["Emirates ID and passport (originals)", "Manager's cheques, as listed by Finance", "Signed Form F"],  # what the client brings to the trustee
    "lost_reasons": ["Price", "Finance refused", "Valuation", "Found elsewhere", "Changed mind", "No response", "Compliance", "Seller withdrew", "Sold elsewhere", "Other"],
    "close_days_target": 60,  # the owner's target from "yes" to closed
    "developers": [],  # [{"name", "commission_pct", "payable_after_pct"}], one per developer agency agreement
    "agency": {"name": "", "orn": "", "address": "", "trn": ""},  # our office on forms and invoices: name, RERA number, address, VAT number
    "invoice_prefix": "INV-",
    "deposit_held_by": "the seller's agency, in trust",  # who holds a ready sale's Form F deposit cheque  # invoices Diwan issues are numbered prefix, year, running number
    "brns": {},  # each broker's RERA card number (BRN), by person
    "paths": {
        "ready": {
            "name": "Ready home, bought from its owner",
            "deposit_pct": 10, "commission_pct": 2, "commission_from": "buyer", "dld_fee_pct": 4,
            "stages": ["Offer", "Offer accepted", "Form F", "Transfer"], "converted_at": "Offer accepted", "agency_forms": True, "invoice_trigger": "transfer_completed",
            "fees": [["Trustee office fee (price AED 500,000 or more), plus VAT", 4000, "buyer"]],  # usual amounts: the transactions officer confirms
            "steps": [["Form F signed by buyer, seller and both brokers", "the buyer and the seller"],
                      ["Buyer's mortgage: valuation and the bank's final offer", "the buyer's bank", "mortgage"],
                      ["Seller's mortgage cleared: liability and clearance letters", "the seller's bank", "seller_mortgage"],
                      ["Developer NOC for the transfer", "the seller and the developer"],
                      ["Manager's cheques for the seller and the DLD fee", "the buyer"],
                      ["Trustee office appointment booked", "the transactions officer", "gate"],
                      ["Title deed issued to the buyer", "the Dubai Land Department"],
                      ["Handover: keys, access cards and utilities moved", "the seller"]],
            "closing": [["figures", "Final price and commission confirmed", "broker"], ["invoice", "Commission invoiced and paid", "finance"],
                        ["compliance", "Every compliance item closed", "compliance"], ["docs", "Title deed copy, Form F and receipts filed", "transactions"]],
        },
        "offplan": {
            "name": "Off-plan unit, bought from a developer",
            "deposit_pct": 10, "commission_pct": 2, "commission_from": "developer", "dld_fee_pct": 4,
            "stages": ["Reservation", "SPA", "Oqood"], "converted_at": "Reservation", "agency_forms": False, "invoice_trigger": "by_hand",
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
            "stages": ["Offer", "Offer accepted", "Contract", "Ejari", "Move-in"], "converted_at": "Offer accepted", "agency_forms": False, "invoice_trigger": "tenancy_signed",
            "fees": [["Ejari registration", 220, "tenant"]],
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
SALES_STAGES = ["New", "Qualifying", "Qualified", "Viewing booked", "Viewed"]  # Sales' own, before any path
NUMBERS = ("deposit_pct", "deposit_pct_furnished", "commission_pct", "dld_fee_pct")
STEP_FLAGS = ("after", "mortgage", "seller_mortgage", "gate")  # after closing; only with a mortgage; only if the seller has one; waits for ready-for-transfer
TRIGGERS = ("form_f_signed", "transfer_completed", "tenancy_signed", "by_hand")
PARTY_TYPES = {"resident": "UAE resident", "non_resident": "Non-resident", "gcc": "GCC national", "company": "Company (onshore or free zone)",
               "offshore": "Company (offshore or foreign)", "poa": "Acting under a power of attorney"}
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
    if not isinstance(r.get("discount_approval_pct"), (int, float)) or not 0 <= r["discount_approval_pct"] <= 100:
        errs.append("The discount the owner approves above is a percentage between 0 and 100")
    for key, label, top in (("stuck_days", "A deal is stuck after", 365), ("close_days_target", "The target from yes to closed", 3650),
                            ("sign_link_days", "A link to a client works for", 90),
                            ("invoice_due_days", "An invoice is due after", 365), ("doc_expiry_warn_days", "A document's expiry warning comes", 365),
                            ("good_standing_days", "A certificate of good standing is good for", 3650)):
        if not isinstance(r.get(key), int) or not 0 < r[key] <= top:
            errs.append(f"{label} is a whole number of days between 1 and {top}")
    if not isinstance(r.get("sof_threshold_aed"), int) or r["sof_threshold_aed"] < 0:
        errs.append("The source-of-funds threshold is a whole number of dirhams")
    if not isinstance(r.get("broker_share_pct"), (int, float)) or not 0 <= r["broker_share_pct"] <= 100:
        errs.append("The broker's share is a percentage between 0 and 100")
    ladder = r.get("docs_ladder_hours")
    if not isinstance(ladder, list) or len(ladder) != 3 or any(not isinstance(x, int) or x <= 0 for x in ladder) or ladder != sorted(ladder):
        errs.append("The follow-up ladder is three rising numbers of hours")
    if not isinstance(r.get("invoice_reminder_days"), list) or any(not isinstance(x, int) or x < 0 for x in r["invoice_reminder_days"]):
        errs.append("Invoice reminders are a list of days after the due date")
    if not isinstance(r.get("lost_reasons"), list) or not [x for x in r["lost_reasons"] if str(x).strip()]:
        errs.append("There is at least one reason a deal is lost")
    from diwan.documents import KINDS
    if not isinstance(r.get("documents"), dict) or any(not isinstance(v, list) or not set(v) <= set(KINDS) for v in r["documents"].values()):
        errs.append(f"Each party's documents are some of: {', '.join(KINDS)}")
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
                                 and (len(s) == 2 or s[2] in STEP_FLAGS)) for s in steps):
            errs.append(f"{p['name']}: every step needs what it is and who it waits on")
        if all(s[2:] == ["after"] for s in steps):
            errs.append(f"{p['name']}: at least one step comes before closing")
        if p.get("invoice_trigger", "by_hand") not in TRIGGERS:
            errs.append(f"{p['name']}: the invoice is drafted at one of {', '.join(TRIGGERS)}")
        st = p.get("stages") or []
        if not st or any(not isinstance(x, str) or not x.strip() for x in st) or len(set(x.lower() for x in st)) != len(st) \
                or any(x.strip().lower() in [y.lower() for y in SALES_STAGES + ["Won", "Lost", "Closing"]] for x in st):
            errs.append(f"{p['name']}: each stage after Viewed has a name, once, and isn't one of Sales' stages, Closing, Won or Lost")
        elif p.get("converted_at") not in st:
            errs.append(f"{p['name']}: the deal counts as converted at one of its own stages")
        if any(not (isinstance(f, list) and len(f) == 3 and str(f[0]).strip() and isinstance(f[1], (int, float)) and f[1] >= 0 and f[2] in PAYERS)
               for f in p.get("fees") or []):
            errs.append(f"{p['name']}: each fee has what it is, an amount in AED and who pays it")
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
    for k in ("cash_report_aed", "stuck_days", "close_days_target", "sign_link_days", "invoice_due_days", "doc_expiry_warn_days", "good_standing_days", "sof_threshold_aed"):
        r[k] = int(r[k]) if str(r.get(k, "")).isdigit() else r.get(k)
    r["agency"] = {k: str((r.get("agency") or {}).get(k, "")).strip() for k in ("name", "orn", "address", "trn")}
    r["invoice_prefix"] = str(r.get("invoice_prefix") or "INV-").strip()
    r["brns"] = {k: str(v).strip() for k, v in (r.get("brns") or {}).items() if str(v).strip()}
    r["developers"] = [{"name": str(d.get("name", "")).strip(), "commission_pct": d.get("commission_pct"), "payable_after_pct": d.get("payable_after_pct")}
                       for d in r.get("developers") or []]
    for pid in PATHS:
        p = r["paths"][pid]
        p["steps"] = [[str(s[0]).strip(), str(s[1]).strip()] + ([s[2]] if len(s) > 2 and s[2] in STEP_FLAGS else []) for s in p.get("steps") or [] if len(s) >= 2]
        p["stages"] = [str(x).strip() for x in p.get("stages") or [] if str(x).strip()]
        p["agency_forms"] = bool(p.get("agency_forms"))
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
         "sides": "which side we act for", "payer_trn": "the VAT number of whoever pays the commission", "other_orn": "the other agency's ORN", "other_agent": "the other agent", "other_brn": "the other agent's BRN",
         "developer": "the developer", "start": "the tenancy start", "end": "the tenancy end", "furnished": "furnished",
         "finance": "how the buyer pays: cash or mortgage", "seller_mortgage": "the seller has a mortgage on the unit", "party_type": "who the client is",
         "other_party": "the seller's or landlord's name", "other_phone": "their phone", "other_party_type": "who they are", "unit": "the unit number, as on the title deed"}
MONEY_TERMS = ("rate_pct", "other_agency", "other_share_pct", "developer")
FORM_TERMS = ("rate_pct", "other_agency", "other_share_pct", "other_orn", "other_agent", "other_brn", "sides")  # what the agency forms carry
SIDES = {"both": "only us: our listing and our buyer", "seller": "we act for the seller; another agency brought the buyer",
         "buyer": "we act for the buyer; another agency holds the listing"}


def terms(g: Graph, deal: str) -> dict:
    return dict(g.settings.get(f"deal:{deal}", {}).get("terms") or {})


def check_terms(g: Graph, deal: str, new: dict, by: str) -> dict:
    """The deal's terms with `new` applied, refused if they aren't good or aren't this person's to change. Writes nothing."""
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
    if "sides" in t and t["sides"] not in SIDES:
        errs.append(f"The side is one of {', '.join(SIDES)}")
    if t.get("sides") in ("seller", "buyer") and "other_agency" not in t:
        errs.append("Name the agency on the other side")
    if "furnished" in t:
        t["furnished"] = t["furnished"] in (True, "true", "yes", 1)
    if "seller_mortgage" in t:
        t["seller_mortgage"] = t["seller_mortgage"] in (True, "true", "yes", 1)
    if "finance" in t and t["finance"] not in ("cash", "mortgage"):
        errs.append("The buyer pays by cash or mortgage")
    for k in ("party_type", "other_party_type"):
        if k in t and t[k] not in PARTY_TYPES:
            errs.append(f"{TERMS[k].capitalize()} is one of {', '.join(PARTY_TYPES)}")
    if errs:
        raise ValueError("; ".join(errs))
    old = terms(g, deal)
    if any(old.get(k) != t.get(k) for k in MONEY_TERMS) and \
            any(x.props["kind"] == "commission invoice" and x.status != "sent_back" for x in g.of("draft", deal)):
        raise ValueError("The commission invoice is already drafted on these terms; they are fixed now.")
    from diwan import agency_forms
    if any(old.get(k) != t.get(k) for k in FORM_TERMS) and (signed := agency_forms.signed_forms(g, deal)):
        raise ValueError(f"{' and '.join(signed)} {'is' if len(signed) == 1 else 'are'} signed with these terms; they are fixed now.")
    return t


def set_terms(office, deal: str, new: dict, *, by: str) -> dict:
    """The broker, the transactions officer or the owner records what the signed documents say. An empty value clears it.
    Once the commission invoice is drafted, the terms it was worked out from are fixed."""
    g = office.graph()
    t = check_terms(g, deal, new, by)
    old = terms(g, deal)
    changed = [k for k in FORM_TERMS if old.get(k) != t.get(k)]
    office.log.append("setting.changed", actor=by, deal=deal, content={"person": f"deal:{deal}", "key": "terms", "value": t})
    if changed:
        from diwan import agency_forms
        agency_forms.terms_changed(office, deal, by, changed)
    if any(old.get(k) != t.get(k) for k in ("finance", "seller_mortgage")):  # the checklist follows the deal: only what applies stays open
        from diwan.agents import operations
        operations.rebuild(office, deal, by)
    if any(old.get(k) != t.get(k) for k in ("finance", "seller_mortgage", "party_type", "other_party_type", "other_party", "other_phone")):
        from diwan import documents
        documents.refresh(office, deal, by)
    return t
