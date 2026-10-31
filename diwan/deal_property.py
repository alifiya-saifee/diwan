"""Which property a deal is on (docs/deal-desk.md item 17). A deal opened from a message only has a placeholder ("WhatsApp
enquiry"); at conversion the broker says whose property it is: one of our listings, another agency's, or a developer's unit.
That answer also settles who is on the other side, so it fills the deal's terms and the broker isn't asked twice.

It is a `setting.changed` (person "deal:<id>", key "property"), so a change keeps who made it and when, and the graph puts
its label on the deal, so every screen, form and sale reads the real property. Our listing follows the deal: reserved at
conversion, released if the deal is lost or moves to another property, sold or let at closing.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan import agency_forms, desk_rules
from diwan.graph import OPEN, Graph
from diwan.people import PEOPLE

if TYPE_CHECKING:
    from diwan.office import Office

SOURCES = {"developer": "From a developer", "listing": "Our listing", "agency": "Another agency's listing"}
OTHER = ("other_agency", "other_orn", "other_agent", "other_brn", "other_share_pct")


def get(g: Graph, deal: str) -> dict | None:
    return g.settings.get(f"deal:{deal}", {}).get("property")


def needed(g: Graph, deal: str) -> bool:
    """True while the deal only has a placeholder: nobody has said the property, and its name isn't one of our listings."""
    return not get(g, deal) and not agency_forms.our_listing(g, deal)


def sources(g: Graph, deal: str) -> list[str]:
    """What this deal's path can be: only off-plan is bought from a developer, and it is offered first."""
    return list(SOURCES) if desk_rules.path(g, deal)["id"] == "offplan" else ["listing", "agency"]


def _closed(g: Graph, deal: str) -> bool:
    return any(n.props.get("deal") == deal for n in g.of("sale"))


def locked(g: Graph, deal: str) -> str | None:
    """Why the property can't change any more, if it can't."""
    if _closed(g, deal):
        return "The deal is closed; a closed deal is corrected only by a new entry."
    if signed := agency_forms.signed_forms(g, deal):
        return f"{' and '.join(signed)} {'is' if len(signed) == 1 else 'are'} signed for this property, so it is fixed now."
    if any(n.props.get("kind") == "Form F" for n in g.of("document", deal)):
        return "Form F is signed for this property, so it is fixed now."
    if any(t.props.get("agent") == "formf" and t.props.get("result") == "submitted" for t in g.of("task", deal)):
        return "Form F is submitted for this property, so it is fixed now."
    if any(d.props["kind"] == "commission invoice" and d.status != "sent_back" for d in g.of("draft", deal)):
        return "The commission invoice is drafted for this property, so it is fixed now."
    return None


def view(g: Graph, deal: str) -> dict:
    li, pr, rules = agency_forms.our_listing(g, deal), get(g, deal), desk_rules.rules(g)
    return {"value": pr, "needed": needed(g, deal), "sources": {k: SOURCES[k] for k in sources(g, deal)}, "locked": locked(g, deal),
            "developers": [d["name"] for d in rules["developers"]],
            "listing": _row(li) if li else None}


def _row(n) -> dict:
    p = n.props
    return {"ref": p.get("ref"), "label": n.label, "community": p.get("community"), "type": p.get("type"), "beds": p.get("beds"),
            "price_aed": p.get("price_aed"), "status": n.status}


def _holder(g: Graph, ref: str, deal: str) -> str | None:
    """Another live deal that has said it is on this listing."""
    for person, s in g.settings.items():
        other = person[5:] if person.startswith("deal:") else None
        if not other or other == deal or (s.get("property") or {}).get("ref") != ref:
            continue
        d = g.nodes.get(person)
        if d and d.props.get("stage") != "Lost" and not _closed(g, other):
            return d.props.get("customer") or other
    return None


def search(g: Graph, deal: str, q: str = "", limit: int = 20) -> dict:
    """Our listings this deal can pick, by ref, name or area: free ones of the right offering, and the one it already has."""
    mine = agency_forms.our_listing(g, deal)
    wrong = "sale" if desk_rules.path(g, deal)["id"] == "rent" else "rent"
    words = q.lower().split()
    hits = []
    for n in g.of("listing"):
        if not (n is mine or n.status == "available") or n.props.get("offering") == wrong or _holder(g, n.props.get("ref"), deal):
            continue
        text = " ".join(str(n.props.get(k) or "") for k in ("ref", "community", "type")).lower() + " " + (n.label or "").lower()
        if all(w in text for w in words):
            hits.append(n)
    hits.sort(key=lambda n: (n is not mine, (n.label or "").lower()))
    return {"total": len(hits), "rows": [_row(n) for n in hits[:limit]]}


def agencies(g: Graph) -> list[dict]:
    """Every other agency this office has worked with, newest details kept, so it is offered next time."""
    out = {}
    for person, s in g.settings.items():
        t = s.get("terms") or {} if person.startswith("deal:") else {}
        if t.get("other_agency"):
            out[t["other_agency"].lower()] = {"other_agency": t["other_agency"], "other_orn": t.get("other_orn", ""),
                                              "other_agent": t.get("other_agent", ""), "other_brn": t.get("other_brn", "")}
    return sorted(out.values(), key=lambda a: a["other_agency"].lower())


def _resolve(g: Graph, deal: str, raw: dict) -> tuple[dict, dict]:
    """What was asked for, checked: (the property, the terms it means)."""
    source = raw.get("source")
    if source not in sources(g, deal):
        raise ValueError(f"The property is one of: {', '.join(SOURCES[k].lower() for k in sources(g, deal))}.")
    other = {k: raw.get(k, "") for k in OTHER}
    none = dict.fromkeys(OTHER, "")
    text = lambda k: str(raw.get(k) or "").strip()  # noqa: E731
    if source == "listing":
        n = g.nodes.get(f"listing:{text('ref')}")
        if not n or n.type != "listing":
            raise ValueError("Pick one of our listings.")
        if n is not agency_forms.our_listing(g, deal):
            if n.status != "available":
                raise ValueError(f"{n.label} is {n.status}, so it can't go on this deal.")
            if who := _holder(g, n.props["ref"], deal):
                raise ValueError(f"{n.label} is on {who}'s deal.")
        brought = bool(raw.get("brought"))
        return {"source": source, "ref": n.props["ref"], "label": n.label}, \
            {"sides": "seller" if brought else "both", "developer": ""} | (other if brought else none)
    if source == "agency":
        if not text("label"):
            raise ValueError("Say which property it is: the unit, the building and the area.")
        return {"source": source, "label": text("label")}, {"sides": "buyer", "developer": ""} | other
    if not text("developer"):
        raise ValueError("Choose the developer.")
    if not text("project") or not text("unit"):
        raise ValueError("Give the project and the unit.")
    return {"source": source, "label": f"{text('unit')}, {text('project')}", "project": text("project"), "unit": text("unit"), "developer": text("developer")}, \
        {"sides": "both", "developer": text("developer")} | none


def save(office: Office, deal: str, raw: dict, by: str) -> dict:
    """The broker, the transactions officer or the owner says which property it is, at conversion or after. Nothing is
    written unless all of it is good. Forms already drafted for another property go back and are drafted again."""
    from diwan import desk_stages
    g = office.graph()
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        raise KeyError(deal)
    if by not in desk_stages.movers(g, deal):
        raise PermissionError(f"Only {PEOPLE.get(d.props.get('broker'), {}).get('name', 'the broker')}, the transactions officer or the owner says which property it is.")
    if why := locked(g, deal):
        raise ValueError(why)
    if desk_stages.pending(g, deal):
        raise ValueError("A discount on this deal is waiting for the owner.")
    value, new = _resolve(g, deal, raw)
    before = desk_rules.terms(g, deal)
    after = desk_rules.check_terms(g, deal, new, by)
    old, label = agency_forms.our_listing(g, deal), d.props.get("property")
    li = g.nodes[f"listing:{value['ref']}"] if value.get("ref") else None
    agreed, c = desk_stages.agreed(g, deal), None
    if agreed:
        c = desk_stages.compare(g, deal, agreed["amount"], li) if li else {"listing_aed": None, "pct": None, "diff": None, "needs_owner": False}
        if li is not old and c["needs_owner"] and PEOPLE.get(by, {}).get("role") != "Owner":
            raise ValueError(f"AED {agreed['amount']:,} is {-c['pct']}% below {li.label}'s price of AED {c['listing_aed']:,}, above the owner's limit: only the owner can put this listing on the deal.")
    office.log.append("setting.changed", actor=by, deal=deal, content={"person": f"deal:{deal}", "key": "property", "value": value | {"by": by}})
    if agreed:
        office.log.append("setting.changed", actor=by, deal=deal, content={"person": f"deal:{deal}", "key": "agreed", "value": agreed | {
            k: c.get(k) for k in ("listing_aed", "pct", "diff")} | {"approved_by": by if li is not old and c["needs_owner"] else agreed.get("approved_by")}})
    had = any(f["status"] != "sent_back" for f in agency_forms.forms(g, deal))
    desk_rules.set_terms(office, deal, new, by=by)
    g = office.graph()
    for t in g.of("task", deal):
        if t.props.get("step") == "sides" and t.status in OPEN:
            office.log.append("task.done", actor=by, agent="ops", deal=deal, content={"id": t.id, "reason": f"{SOURCES[value['source']]}: {value['label']}"})
    if agency_forms.converted(office.graph(), deal):
        agency_forms.make_forms(office, deal)
    if value["label"] != label:
        redrafted = any(before.get(k) != after.get(k) for k in desk_rules.FORM_TERMS)
        agency_forms.property_changed(office, deal, by, forms=had and not redrafted)
    if agreed:
        if old and old is not li:
            release(office, old.props["ref"], by)
        reserve(office, deal, by)
    return value


def reserve(office: Office, deal: str, by: str) -> None:
    """A converted deal holds our listing, so Rania stops offering it."""
    g = office.graph()
    li = agency_forms.our_listing(g, deal)
    if li and li.status == "available":
        office.log.append("listing.added", actor=by, deal=deal, content={"ref": li.props["ref"], "status": "reserved"})


def release(office: Office, ref: str, by: str) -> None:
    n = office.graph().nodes.get(f"listing:{ref}")
    if n and n.status == "reserved":
        office.log.append("listing.added", actor=by, content={"ref": ref, "status": "available"})


def lost(office: Office, deal: str, by: str) -> None:
    if li := agency_forms.our_listing(office.graph(), deal):
        release(office, li.props["ref"], by)


def back_from_lost(g: Graph, deal: str) -> None:
    """A lost deal comes back only if its listing hasn't gone to someone else in the meantime."""
    li = agency_forms.our_listing(g, deal)
    if li and li.status != "available":
        raise ValueError(f"{li.label} is {li.status} now: choose another property first.")


def closed(office: Office, deal: str, by: str) -> None:
    g = office.graph()
    if li := agency_forms.our_listing(g, deal):
        office.log.append("listing.added", actor=by, deal=deal, content={"ref": li.props["ref"], "status": "let" if desk_rules.path(g, deal)["id"] == "rent" else "sold"})

