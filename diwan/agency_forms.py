"""The agency forms a converted deal needs (docs/deal-desk.md item 11): Form A between the seller and our agency, Form B
between the buyer and our agency, Form I between our agency and another one. Which ones depends on who is on the other
side, which the broker says once at conversion unless the deal already says it. Each form is a draft filled from the
record (the price the client said, the deal's terms, the owner's agency settings), checked by Review like any draft;
what isn't on file is printed blank for the broker to fill by hand. The broker downloads it as a PDF, shares it with
the client or the other agent personally, and uploads the signed copy, which Records files. Until then Form F isn't
submitted and no commission invoice is drafted.
"""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from diwan import desk_rules, pdf, roles
from diwan.graph import OPEN, Graph
from diwan.people import PEOPLE, name

if TYPE_CHECKING:
    from diwan.office import Office

TITLES = {"A": "Form A: agreement between the seller and the broker", "B": "Form B: agreement between the buyer and the broker",
          "I": "Form I: agreement between the two brokers"}
FORM_OF = {v: k for k, v in TITLES.items()}  # a draft's kind says which form it is


def signed_file(deal: str, form: str, did: str) -> str:
    return f"deal-{deal}-form-{form}-{did}-signed.pdf"


def _deal(g: Graph, deal: str):
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        raise KeyError(deal)
    return d


def our_listing(g: Graph, deal: str):
    """The office's listing this deal is about, if it is one of ours."""
    prop = (_deal(g, deal).props.get("property") or "").lower()
    return next((n for n in g.of("listing") if n.label and n.label.lower() in prop), None)


def needed(g: Graph, deal: str) -> list[str] | None:
    """The forms this deal needs; None while nobody has said who is on the other side."""
    p, t = desk_rules.path(g, deal), desk_rules.terms(g, deal)
    if p.get("agency_forms"):
        return {"both": ["A", "B"], "seller": ["A", "I"], "buyer": ["B", "I"]}.get(t.get("sides"))
    if "sides" not in t:
        return None
    return ["I"] if t.get("other_agency") else []


def _sign_tasks(g: Graph, deal: str):
    return [t for t in g.of("task", deal) if t.props.get("agent") == "ops" and t.props.get("step") == "sign"]


def forms(g: Graph, deal: str) -> list[dict]:
    """Every agency form on the deal, newest version last, with whether it waits for a signature or is signed."""
    tasks = {t.props.get("draft"): t for t in _sign_tasks(g, deal)}
    out = []
    for d in g.of("draft", deal):
        form = FORM_OF.get(d.props.get("kind"))
        if not form:
            continue
        t = tasks.get(d.id)
        done = bool(t and t.props.get("result") == "signed")
        out.append({"form": form, "title": TITLES[form], "draft": d.id, "version": d.props.get("version"), "status": d.status,
                    "reason": d.props.get("reason"), "task": t.id if t else None, "signed": done,
                    "file": f"/media/{signed_file(deal, form, d.id)}" if done else None, "waiting": bool(t and t.status in OPEN)})
    return out


def unsigned(g: Graph, deal: str) -> list[str]:
    return [f"Form {t.props['form']}" for t in _sign_tasks(g, deal) if t.status in OPEN]


def signed_forms(g: Graph, deal: str) -> list[str]:
    return [f"Form {f['form']}" for f in forms(g, deal) if f["signed"]]


def converted(g: Graph, deal: str) -> bool:
    return any(t.props.get("agent") == "ops" and t.props.get("step") == "sides" for t in g.of("task", deal)) or bool(forms(g, deal))


def on_convert(office: Office, deal: str, by: str) -> None:
    """The deal reached its path's "converted at" stage: if nobody has said who is on the other side, the broker is
    asked once; then the forms it needs are drafted."""
    g = office.graph()
    if converted(g, deal):
        return
    d = _deal(g, deal).props
    if needed(g, deal) is None:
        li = our_listing(g, deal)
        hint = f"{li.label} is our listing ({li.props['ref']}): did another agent bring the buyer?" if li else \
            f"{d['property']} isn't one of our listings: which agency holds it?"
        office.add_task(deal, "ops", f"Say who is on the other side of {d['property']}. {hint}", needs_person=d["broker"], by=by,
                        props={"step": "sides"})
    else:  # the deal already says; the done task records that the question was settled
        tid = office.add_task(deal, "ops", f"Say who is on the other side of {d['property']}", needs_person=d["broker"], by=by, props={"step": "sides"})
        office.finish_task(tid, "Already on the deal's terms")
        make_forms(office, deal)


def set_sides(office: Office, deal: str, by: str, sides: str, other: dict) -> list[str]:
    """The broker (or the transactions officer, or the owner) says who is on the other side."""
    g = office.graph()
    d = _deal(g, deal).props
    if by != d.get("broker") and by != roles.holder(g, "transactions") and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError("Only the deal's broker, the transactions officer or the owner says who is on the other side.")
    keys = ("other_agency", "other_orn", "other_agent", "other_brn", "other_share_pct")
    new = {"sides": sides} | ({k: other.get(k, "") for k in keys} if sides != "both" else {k: "" for k in keys})
    desk_rules.set_terms(office, deal, new, by=by)
    for t in office.graph().of("task", deal):
        if t.props.get("step") == "sides" and t.status in OPEN:
            office.log.append("task.done", actor=by, agent="ops", deal=deal, content={"id": t.id, "reason": desk_rules.SIDES[sides].capitalize()})
    make_forms(office, deal)  # changed terms have usually drafted them already
    return [f["draft"] for f in forms(office.graph(), deal) if f["status"] != "sent_back"]


def terms_changed(office: Office, deal: str, by: str, keys: list[str]) -> None:
    """Changed terms send every unsigned form back (its signature task is withdrawn) and new ones are drafted."""
    g = office.graph()
    for f in forms(g, deal):
        if f["status"] != "sent_back" and not f["signed"]:
            office.log.append("review.returned", actor="factcheck", agent="factcheck", deal=deal,
                              content={"draft": f["draft"], "reason": f"The deal's terms changed ({', '.join(k.replace('_', ' ') for k in keys)}); a new form is drafted."})
            if f["task"] and f["waiting"]:
                office.log.append("task.withdrawn", actor=by, agent="ops", deal=deal, content={"id": f["task"], "reason": "The terms on the form changed"})
    if converted(office.graph(), deal):
        make_forms(office, deal)


def make_forms(office: Office, deal: str) -> list[str]:
    """Each form the deal needs and doesn't have yet (a sent-back one doesn't count) is drafted, with a task for the
    broker to share it and upload the signed copy."""
    g = office.graph()
    want = needed(g, deal) or []
    have = {f["form"] for f in forms(g, deal) if f["status"] != "sent_back"}
    d = _deal(g, deal).props
    t = desk_rules.terms(g, deal)
    made = []
    for form in want:
        if form in have:
            continue
        rows = fields(g, deal, form)
        slides = [{"n": i, "text": f"{label}: {value if value is not None else 'not on file'}", "facts": [fact] if fact else []}
                  for i, (_, label, value, fact) in enumerate(rows, 1)]
        did = office.make_draft(deal, TITLES[form], slides, by="ops")
        g = office.graph()
        who = {"A": "the seller", "B": d["customer"], "I": t.get("other_agent") or t.get("other_agency") or "the other agency"}[form]
        price = (g.facts(deal, "deal_term") or [None])[-1]
        office.add_task(deal, "ops", f"Share Form {form} ({did}) with {who} for signature, then upload the signed copy",
                        rests_on=[price.id] if price else [], needs_person=d["broker"], props={"step": "sign", "form": form, "draft": did})
        made.append(did)
    from diwan import documents
    documents.request_all(office, deal, "ops")  # the documents each party on our side sends, one link each
    return made


def _blank(v):
    return v if v not in (None, "") else None


def fields(g: Graph, deal: str, form: str) -> list[tuple[str, str, str | None, str | None]]:
    """(section, label, value, the fact it uses); no value means it isn't on file and is filled by hand."""
    from diwan.agents import finance
    r, t, d = desk_rules.rules(g), desk_rules.terms(g, deal), _deal(g, deal).props
    price = (g.facts(deal, "deal_term") or [None])[-1]
    c = finance.commission(g, deal)
    li = our_listing(g, deal)
    us = [("Our agency", "Agency", _blank(r["agency"]["name"]), None), ("Our agency", "Office number (ORN)", _blank(r["agency"]["orn"]), None),
          ("Our agency", "Broker", name(d["broker"]), None), ("Our agency", "Broker's card number (BRN)", _blank(r["brns"].get(d["broker"])), None)]
    prop = [("The property", "Property", d["property"], None),
            ("The property", "Listing ref and permit", f"{li.props['ref']}, permit {li.props.get('permit') or 'not on file'}" if li else None, None)]
    money = ("The price", f"{c.get('base_label', 'Price')}", f"AED {price.props['amount_aed']:,} (said: \"{price.props['quote']}\")" if price else None,
             price.id if price else None)
    rate = f"{c['pct']}% + VAT {c['vat_pct']}% (from {c['rate_from']})"
    if form == "A":
        return us + [("The seller", "Seller's name, as on the title deed", None, None), ("The seller", "Seller's ID or passport number", None, None)] + prop + \
            [("The property", "Title deed number", None, None), money,
             ("Commission", "Paid by the seller", rate if c["payer"] == "seller" else None, None)]
    if form == "B":
        return us + [("The buyer", "Buyer", d["customer"], None), ("The buyer", "Buyer's ID or passport number", None, None)] + prop + \
            [money, ("Commission", f"Paid by the {c['payer']}", rate if c["payer"] == "buyer" else None, None)]
    ours = "the seller" if t.get("sides") == "seller" else "the buyer"
    theirs = "the buyer" if ours == "the seller" else "the seller"
    return us + [("Our agency", "Acts for", ours, None),
                 ("The other agency", "Agency", _blank(t.get("other_agency")), None), ("The other agency", "Office number (ORN)", _blank(t.get("other_orn")), None),
                 ("The other agency", "Agent", _blank(t.get("other_agent")), None), ("The other agency", "Agent's card number (BRN)", _blank(t.get("other_brn")), None),
                 ("The other agency", "Acts for", theirs, None)] + prop + \
        [money, ("Commission", "Their share of the commission",
                 f"{t['other_share_pct']}%" + (f": AED {c['share']:,} of AED {c['amount']:,}" if c.get("share") is not None else "") if "other_share_pct" in t else None, None)]


SIGNERS = {"A": ["The seller", "The broker"], "B": ["The buyer", "The broker"], "I": ["Our broker", "The other broker"],
           "F": ["The buyer", "The seller", "Our broker", "The other broker"]}


TITLES_ALL = TITLES | {"F": "Form F: memorandum of understanding between the buyer and the seller"}


def form_of(g: Graph, did: str) -> str:
    d = g.nodes.get(did)
    if not d or d.type != "draft" or (d.props.get("kind") not in FORM_OF and d.props.get("kind") != "Form F"):
        raise KeyError(did)
    return FORM_OF.get(d.props["kind"], "F")


def rows(g: Graph, did: str, form: str) -> list[tuple[str, str, str | None, str | None]]:
    """The form's lines: Form F's from its plan (each line from a live fact), the agency forms' from the record."""
    if form != "F":
        return fields(g, g.nodes[did].deal, form)
    out = []
    for s in sorted(g.into(did, "part_of"), key=lambda s: s.props["n"]):
        label, _, value = s.props["text"].partition(": ")
        out.append(("The memorandum", label, None if value.startswith("not said") else value, None))
    p = desk_rules.path(g, g.nodes[did].deal)
    out.append(("The deposit", "Held by", desk_rules.rules(g)["deposit_held_by"], None))
    out.append(("The deposit", "Usual deposit", f"{p['deposit_pct']}% of the price", None))
    return out


def render(g: Graph, did: str, signatures: list[dict] | None = None) -> bytes:
    """The form as a PDF; with `signatures` (from diwan/signing.py), signed, with the signing record at the end."""
    form = form_of(g, did)
    d, deal = g.nodes[did], g.nodes[did].deal
    filler = name(_deal(g, deal).props["broker"])
    blocks = [("title", TITLES_ALL[form]),
              ("p", f"Prepared by Diwan from deal {deal}, version {d.props.get('version', 1)} ({did}), on {date.today().isoformat()}. "
                    f"Every value comes from the deal record. A line marked 'to fill' is not on file and {filler} fills it by hand. "
                    "Check it against the current RERA form before anyone signs.")]
    if d.status == "sent_back":
        blocks.append(("p", f"SENT BACK, DO NOT SIGN: {d.props.get('reason') or 'a newer version replaces it'}"))
    by_as = {x["as"]: x for x in signatures or []}  # what each signer gave when signing fills their own blank lines
    given = {"Buyer's ID or passport number": by_as.get("The buyer", {}).get("id_no"), "Seller's ID or passport number": by_as.get("The seller", {}).get("id_no"),
             "Seller's name, as on the title deed": by_as.get("The seller", {}).get("name"),
             "Seller": by_as.get("The seller", {}).get("name"), "Buyer passport number": by_as.get("The buyer", {}).get("id_no")}
    section = None
    for sec, label, value, _ in rows(g, did, form):
        if sec != section:
            blocks.append(("h", sec))
            section = sec
        value = value if value is not None else given.get(label)
        blocks.append(("field", f"{label}|{value if value is not None else '____________________________  (to fill)'}"))
    blocks.append(("h", "Signatures"))
    if signatures:
        from diwan.signing import when
        for x in signatures:
            blocks += [("field", f"{x['as']}|{x['name']}"), ("image", "", x["jpeg"], x["w"], x["h"]), ("field", f"|Signed online {when(x['at'])}"), ("gap", "")]
        blocks.append(("h", "Signing record"))
        blocks.append(("p", "Each person signed with their own link from Diwan, after reading this form. The fingerprint is a SHA-256 of the "
                            "form's lines as drafted: the same fingerprint means the same words."))
        for x in signatures:
            blocks += [("field", f"{x['as']}|{x['name']}, ID {x['id_no']}"), ("field", f"|{when(x['at'])}, from {x['ip'] or 'unknown'}"),
                       ("field", f"|{x['device'] or 'device not given'}"), ("field", f"|Fingerprint {x['fingerprint'][:32]}"), ("gap", "")]
        return pdf.render(blocks)
    for who in SIGNERS[form]:
        blocks += [("field", f"{who}|Name ______________________"), ("field", "|Signature ______________________   Date __________"), ("gap", "")]
    return pdf.render(blocks)


def signed(office: Office, tid: str, by: str, data: bytes, filename: str, *, media, today: date) -> str:
    """The broker uploads the signed copy; Records files it against the deal and the form's terms are fixed."""
    g = office.graph()
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("step") != "sign":
        raise KeyError(tid)
    d = _deal(g, t.deal).props
    if by != d.get("broker") and by != roles.holder(g, "transactions") and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError(f"Only {name(d.get('broker'))}, the transactions officer or the owner uploads a signed form.")
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}" + (f": {t.props['reason']}" if t.props.get("reason") else "."))
    if g.nodes[t.props["draft"]].status == "sent_back":
        raise ValueError(f"{t.props['draft']} was sent back; share the new version.")
    if not data.startswith(b"%PDF"):
        raise ValueError("Upload the signed copy as a PDF.")
    media.mkdir(parents=True, exist_ok=True)
    path = media / signed_file(t.deal, t.props["form"], t.props["draft"])
    path.write_bytes(data)
    doc = office.file_document(kind=f"Form {t.props['form']}", title=f"Form {t.props['form']} ({t.props['draft']}) signed, from {filename or 'an upload'}",
                               date=today.isoformat(), by=by, deal=t.deal, party=d.get("customer"), text=f"/media/{path.name}")
    office.log.append("task.done", actor=by, agent="ops", deal=t.deal,
                      content={"id": tid, "reason": f"Signed copy filed with Records as {doc}", "result": "signed"})
    return doc
