"""Operations: turns agreed terms into the paperwork and tracks it to transfer. The Form F clerk fills the form from
live facts only and stops before Submit; the transactions officer submits. A plan resting on replaced words is sent back by Review and a
new one is made from what stands now; the submit step rests on the same words, so it is withdrawn with them.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import TYPE_CHECKING

from diwan import desk_rules, roles
from diwan.agents import compliance, runner
from diwan.agents.charters import get
from diwan.graph import OPEN, Graph
from diwan.pack import Action, Evidence, Pack
from diwan.people import PEOPLE, name

if TYPE_CHECKING:
    from diwan.office import Office

def _evidence(g: Graph, ids: list[str]) -> list[Evidence]:
    return [Evidence(g.nodes[i].props["quote"], i) for i in ids if g.nodes[i].type == "fact"]


def fields(g: Graph, deal: str) -> list[tuple[str, str | None, str | None]]:
    """(field, value, the fact or record it comes from); no value means nobody said it."""
    d = g.nodes[f"deal:{deal}"].props
    one = lambda kind: (g.facts(deal, kind) or [None])[-1]  # noqa: E731
    price, dep, payer = one("deal_term"), one("payment_promise"), one("payer")
    return [("Buyer", d["customer"], f"deal:{deal}"), ("Property", d["property"], f"deal:{deal}"),
            ("Price", price and f"AED {price.props['amount_aed']:,}", price and price.id),
            ("Deposit", dep and f"AED {dep.props['amount_aed']:,}", dep and dep.id),
            ("Deposit paid by", payer and payer.props["payer"], payer and payer.id),
            ("Seller", desk_rules.terms(g, deal).get("other_party"), None), ("Buyer passport number", None, None)]


def make_plan(office: Office, deal: str, cause: int | None = None) -> str:
    """The plan as a draft: one line per field, each using the fact it came from, and the transactions officer's submit step resting on
    the same facts."""
    g = office.graph()
    fs = fields(g, deal)
    joseph = roles.who(g, "transactions")
    slides = [{"n": i, "text": f"{k}: {v}" if v else f"{k}: not said; {joseph} fills it",
               "facts": [src] if v and src and g.nodes.get(src) and g.nodes[src].type == "fact" else []}
              for i, (k, v, src) in enumerate(fs, 1)]
    did = office.make_draft(deal, "Form F", slides, by="formf")
    used = [f for s in slides for f in s["facts"]]
    office.add_task(deal, "formf", f"Submit Form F {did} on the DLD portal", rests_on=used, needs_person=roles.holder(g, "transactions"),
                    caused_by=cause, props={"draft": did})
    return did


def replan(office: Office, deal: str, sent_back: set, cause: int) -> None:
    """After a correction: every Form F plan Review sent back gets a new one from the live facts."""
    from diwan import agency_forms
    g = office.graph()
    for did in sent_back:
        if g.nodes[did].props["kind"] == "Form F":
            make_plan(office, deal, cause)
    if any(g.nodes[did].props["kind"] in agency_forms.FORM_OF for did in sent_back):  # the agency forms are drafted again too
        agency_forms.make_forms(office, deal)
    recall_sent(office, deal)


def recall_sent(office: Office, deal: str) -> None:
    """A form that went out and was then replaced is recalled in a short message, so nobody signs the old one."""
    from diwan import client_msgs, signing
    g = office.graph()
    for d in g.of("draft", deal):
        s = d.props.get("sent")
        if d.status == "sent_back" and s and not d.props.get("recalled"):
            at = signing.when(s["at"]).split(", ")[1].split(" ")[0]
            office.log.append("form.recalled", actor="ops", agent="ops", deal=deal, content={"draft": d.id, "form": s.get("form"), "version": d.props.get("version"), "reason": d.props.get("reason")})
            client_msgs.tell(office, deal, f"Please ignore the {d.props['kind'].split(':')[0]} sent at {at}; a corrected one follows.", what=f"tell them to ignore the {d.props['kind']} sent earlier; a corrected one follows")


def formf_plan(office: Office, deal: str, tid: str, req: str) -> str:
    """The Form F clerk's plan: every field from a live fact or the deal record, or left for the transactions officer with the reason."""
    g, c = office.graph(), get("formf")
    fs = fields(g, deal)
    filled = [f"{k}: {v} ({src})" for k, v, src in fs if v]
    joseph = roles.who(g, "transactions")
    empty = [f"{k}: not said in the meeting; {joseph} fills it" for k, v, _ in fs if not v]
    used = [src for _, v, src in fs if v and src and src in g.nodes and g.nodes[src].type == "fact"]
    pack = Pack(req, c.id, f"Form F plan: {len(filled)} of {len(fs)} fields from live facts, {len(empty)} left for {joseph}.",
                evidence=_evidence(g, used), missing=empty, next=filled,
                actions=[Action("fill_form", "Type the planned fields into the portal"), Action("submit", "Submit Form F")])
    runner.submit(office.log, c, pack, sources={i: g.record(i) for i in used}, deal=deal)
    did = make_plan(office, deal)
    office.finish_task(tid, f"Field plan {did} ready; Submit waits for {joseph}")
    return f"{pack.verdict} Submit waits for {joseph}."


def submitted(office: Office, tid: str, by: str, reference: str) -> None:
    """The transactions officer pressed Submit on the portal; the transfer checklist starts."""
    g = office.graph()
    roles.check(g, "transactions", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "formf" or not t.props.get("draft"):
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}" + (f": {t.props['reason']}" if t.props.get("reason") else "."))
    if g.nodes[t.props["draft"]].status == "sent_back" or g.stale(tid):
        raise ValueError(f"{t.props['draft']} rests on words the customer replaced; submit the new plan.")
    if not reference.strip():
        raise ValueError("Give the portal reference of the submitted Form F.")
    from diwan import agency_forms, deal_gates
    if waiting := agency_forms.unsigned(g, t.deal):
        raise ValueError(f"{' and '.join(waiting)} {'waits' if len(waiting) == 1 else 'wait'} for a signature: the broker uploads the signed copy first.")
    compliance.require(g, t.deal, "Submitting Form F")
    if not deal_gates.formf_signed(g, t.deal):
        raise ValueError("Form F isn't signed yet: every signature comes before it is submitted.")
    office.log.append("task.done", actor=by, agent="formf", deal=t.deal,
                      content={"id": tid, "reason": f"Submitted on the DLD portal, reference {reference.strip()}", "result": "submitted"})
    for r in g.of("request", t.deal, "open"):  # the clerk's "only a person submits" request is answered by this
        if r.props.get("kind") == "submit" and r.props.get("agent") == "formf":
            office.log.append("decision.made", actor=by, deal=t.deal, content={"card": r.id, "answer": f"Submitted, reference {reference.strip()}"})
    add_steps(office, t.deal, desk_rules.path(g, t.deal)["steps"])
    for x in office.graph().of("task", t.deal):  # signed before it was submitted: its step is already done
        if x.props.get("agent") == "transfer" and x.status in OPEN and x.props["action"].lower().startswith("form f signed"):
            office.log.append("task.done", actor="ops", agent="transfer", deal=t.deal, content={"id": x.id, "reason": "Signed before it was submitted"})


def form_f_done(office: Office, deal: str) -> None:
    """Form F is signed by everyone: its paperwork step ticks itself, and Finance's draft follows if that's the owner's trigger."""
    from diwan.agents import finance
    for t in office.graph().of("task", deal):
        if t.props.get("agent") == "transfer" and t.status in OPEN and t.props["action"].lower().startswith("form f signed"):
            office.log.append("task.done", actor="ops", agent="transfer", deal=deal, content={"id": t.id, "reason": "Signed by everyone"})
            start_closing(office, deal)
    finance.auto_invoice(office, deal, "form_f_signed")


def applies(flag: str | None, terms: dict) -> bool:
    """A step marked for a mortgage is left out of a cash deal, and one for the seller's mortgage when they have none. Until
    someone says, it stays on the list: a person can mark it not needed."""
    return not ((flag == "mortgage" and terms.get("finance") == "cash") or (flag == "seller_mortgage" and terms.get("seller_mortgage") is False))


def add_steps(office: Office, deal: str, steps: list) -> list[str]:
    """The owner's steps for the deal's path, each waiting on who the rules say and only if it applies to this deal. A step
    marked "after" runs on after closing; one marked "gate" waits for ready-for-transfer."""
    g = office.graph()
    who, terms, p = roles.holder(g, "transactions"), desk_rules.terms(g, deal), desk_rules.path(g, deal)
    out = []
    for i, s in enumerate(steps):
        flag = s[2] if len(s) > 2 else None
        if applies(flag, terms):
            out.append(office.add_task(deal, "transfer", s[0], needs_person=who, props={"waiting_on": s[1], "flag": flag, "before_gate": p["id"] == "offplan" and i == 0,
                                                                                        **({"after": True} if flag == "after" else {})}))
    return out


def rebuild(office: Office, deal: str, by: str) -> None:
    """The checklist follows the deal: a cash buyer's open mortgage step goes, and it comes back if they take a mortgage after
    all. Finished steps stay. Only for a deal whose paperwork has started."""
    g = office.graph()
    tasks = [t for t in g.of("task", deal) if t.props["agent"] == "transfer"]
    if not tasks:
        return
    terms = desk_rules.terms(g, deal)
    for t in tasks:
        if t.status in OPEN and not applies(t.props.get("flag"), terms):
            office.log.append("task.withdrawn", actor=by, agent="transfer", deal=deal, content={"id": t.id, "reason": "Doesn't apply to this deal now"})
    have = {t.props["action"] for t in tasks if t.status in OPEN | {"done"}}
    add_steps(office, deal, [s for s in desk_rules.path(g, deal)["steps"] if len(s) > 2 and s[2] in ("mortgage", "seller_mortgage") and s[0] not in have])
    start_closing(office, deal)


BRING = "Bring: "


def _gated(g: Graph, t, what: str) -> None:
    from diwan import deal_gates
    if t.props.get("before_gate"):
        return
    compliance.require(g, t.deal, what)
    if t.props.get("flag") == "gate" and not deal_gates.is_ready(g, t.deal):
        raise ValueError("This waits for ready-for-transfer: every gate passed and the owner's approval on the current facts.")


def tick(office: Office, tid: str, by: str, note: str = "") -> None:
    g = office.graph()
    roles.check(g, "transactions", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "transfer":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    _gated(g, t, "This step")
    if t.props.get("flag") == "gate":
        raise ValueError("Book the trustee appointment with its date and place.")
    office.log.append("task.done", actor=by, agent="transfer", deal=t.deal, content={"id": tid, "reason": f"Done{': ' + note.strip() if note.strip() else ''}"})
    _after_step(office, t, by)
    start_closing(office, t.deal)


def _after_step(office: Office, t, by: str) -> None:
    """What an official step sets off: a person says the transfer or the tenancy is done; the client hears; Finance bills."""
    from diwan import client_msgs
    from diwan.agents import finance
    a = t.props["action"].lower()
    if "title deed issued" in a:
        office.log.append("transfer.completed", actor=by, agent="transfer", deal=t.deal, content={"task": t.id})
        client_msgs.tell(office, t.deal, "Congratulations, the transfer is done.", what="tell them the transfer is done")
        finance.auto_invoice(office, t.deal, "transfer_completed")
    elif a.startswith("handover"):
        client_msgs.tell(office, t.deal, "Welcome to your new home. If anything needs attention in the first weeks, your broker is a message away.", what="send the welcome note")
    elif "tenancy contract signed" in a:
        client_msgs.tell(office, t.deal, "Your tenancy contract is signed. Next: Ejari, then your move-in date.", what="tell them the contract is signed")
        finance.auto_invoice(office, t.deal, "tenancy_signed")
    elif "ejari registered" in a:
        client_msgs.tell(office, t.deal, "Your Ejari is registered.", what="tell them Ejari is registered")
    elif "oqood registered" in a:
        client_msgs.tell(office, t.deal, "Your unit is now registered.", what="tell them the unit is registered")


def book_transfer(office: Office, tid: str, by: str, when: str, place: str, *, today: date) -> None:
    """The transactions officer booked the trustee on the portal: the date, the place, and the client is told what to bring."""
    from diwan import client_msgs
    g = office.graph()
    roles.check(g, "transactions", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "transfer" or t.props.get("flag") != "gate":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    _gated(g, t, "Booking the trustee")
    try:
        day = date.fromisoformat((when or "")[:10])
    except ValueError:
        raise ValueError("Give the appointment's date.") from None
    if day < today:
        raise ValueError("The appointment can't be in the past.")
    if not place.strip():
        raise ValueError("Say which trustee office.")
    office.log.append("transfer.booked", actor=by, agent="transfer", deal=t.deal, content={"task": tid, "when": when, "place": place.strip()})
    office.log.append("task.done", actor=by, agent="transfer", deal=t.deal, content={"id": tid, "reason": f"Booked for {when} at {place.strip()}"})
    bring = "; ".join(desk_rules.rules(g)["transfer_bring"])
    client_msgs.tell(office, t.deal, f"Your transfer is booked for {when} at {place.strip()}. Please bring: {bring}.", what=f"tell them the transfer is on {when} at {place.strip()} and what to bring")
    start_closing(office, t.deal)


# ---------- portals: Diwan prepares exactly what to enter; a person types it in and presses Submit ----------

PORTALS = [("noc", r"\bnoc\b", "Developer NOC request"), ("trustee", r"trustee", "DLD trustee appointment"), ("ejari", r"ejari", "Ejari registration"),
           ("oqood", r"oqood", "Oqood registration"), ("spa", r"\bspa\b", "Developer SPA")]


def portal_of(action: str) -> tuple[str, str] | None:
    for key, pat, label in PORTALS:
        if re.search(pat, action, re.I):
            return key, label
    return None


def portal_fields(g: Graph, deal: str) -> list[list]:
    """What to type, from the record; a line with no value is not on file and the person fills it."""
    d, t = g.nodes[f"deal:{deal}"].props, desk_rules.terms(g, deal)
    price = (g.facts(deal, "deal_term") or [None])[-1]
    return [["Client", d.get("customer")], ["Other party", t.get("other_party")], ["Property", d.get("property")], ["Unit", t.get("unit")],
            ["Developer", t.get("developer")], ["Price" if desk_rules.path(g, deal)["id"] != "rent" else "Yearly rent", f"AED {price.props['amount_aed']:,}" if price else None],
            ["Tenancy", f"{t['start']} to {t['end']}" if t.get("start") and t.get("end") else None]]


def portal_draft(office: Office, tid: str, by: str) -> list[list]:
    g = office.graph()
    roles.check(g, "transactions", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "transfer":
        raise KeyError(tid)
    p = portal_of(t.props["action"])
    if not p:
        raise ValueError("This step isn't done on a portal.")
    fields = [x for x in portal_fields(g, t.deal) if x[1] or x[0] in ("Client", "Property", "Unit")]
    office.log.append("portal.drafted", actor="ops", agent="ops", deal=t.deal, content={"task": tid, "portal": p[1], "fields": fields})
    return fields


def portal_submitted(office: Office, tid: str, by: str, reference: str) -> None:
    """The person pressed Submit on the portal; the step is done under its reference."""
    g = office.graph()
    roles.check(g, "transactions", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "transfer" or not t.props.get("portal"):
        raise KeyError(tid)
    if not reference.strip():
        raise ValueError("Give the portal's reference.")
    _gated(g, t, "Submitting this")
    office.log.append("portal.submitted", actor=by, agent="ops", deal=t.deal, content={"task": tid, "reference": reference.strip()})
    if t.props.get("flag") != "gate":
        tick(office, tid, by, f"submitted, reference {reference.strip()}")


def not_needed(office: Office, tid: str, by: str, why: str) -> None:
    """A step that doesn't apply to this deal (a cash buyer has no mortgage), with the reason: it counts as done."""
    roles.check(office.graph(), "transactions", by)
    t = office.graph().nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "transfer":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if t.props.get("flag") == "gate":
        raise ValueError("The trustee appointment can't be skipped.")
    if not why.strip():
        raise ValueError("Say why this step isn't needed on this deal.")
    office.log.append("task.done", actor=by, agent="transfer", deal=t.deal, content={"id": tid, "reason": f"Not needed: {why.strip()}", "result": "not needed"})
    start_closing(office, t.deal)


def start_paperwork(office: Office, deal: str, by: str) -> list[str]:
    """A rental or off-plan deal's paperwork: the owner's steps for its path, each waiting on who the rules say. A rental
    also tells Finance to expect the security deposit (the owner's percentage of the yearly rent the client said).
    A ready sale starts with the Form F plan instead."""
    g = office.graph()
    roles.check(g, "transactions", by)
    p = desk_rules.path(g, deal)
    if p["id"] == "ready":
        raise ValueError("A ready sale's paperwork starts with the Form F plan.")
    if any(t.props["agent"] == "transfer" for t in g.of("task", deal)):
        raise ValueError("The paperwork has already started.")
    tids = add_steps(office, deal, p["steps"])
    if p["id"] == "rent":
        rent = (g.facts(deal, "deal_term") or [None])[-1]
        pct = p["deposit_pct_furnished"] if desk_rules.terms(g, deal).get("furnished") else p["deposit_pct"]
        if rent and rent.props.get("amount_aed"):
            amount = round(rent.props["amount_aed"] * pct / 100)
            office.add_task(deal, "pay", f"Expect the security deposit AED {amount:,} ({pct}% of the yearly rent) from the tenant, held by the landlord",
                            rests_on=[rent.id], props={"amount_aed": amount})
        else:
            office.log.append("question.asked", actor="pay", agent="pay", deal=deal,
                              content={"to": g.nodes[f"deal:{deal}"].props["broker"], "refs": [], "text": "What yearly rent did the tenant agree? The deposit and fee are worked out from it."})
    return tids


# ---------- closing: the last step is not the end; four items, then the sale goes to Records ----------

def is_closing(t) -> bool:
    """A closing task: the Operations lead's, marked for closing (figures or documents)."""
    return t.props.get("agent") == "ops" and bool(t.props.get("closing"))


def sale_of(g: Graph, deal: str):
    return next((n for n in g.of("sale") if n.props.get("deal") == deal), None)


def start_closing(office: Office, deal: str) -> None:
    """When every paperwork step is done, the broker confirms the final figures and the transactions officer files the
    closing documents; the other two items (commission paid, compliance closed) are read from the record."""
    g = office.graph()
    steps = [t for t in g.of("task", deal) if t.props["agent"] == "transfer" and not t.props.get("after")]
    if not steps or any(t.status != "done" for t in steps) or any(is_closing(t) for t in g.of("task", deal)):
        return
    p, d = desk_rules.path(g, deal), g.nodes[f"deal:{deal}"].props
    text = {k: t for k, t, _ in p["closing"]}
    office.add_task(deal, "ops", text["figures"], needs_person=d["broker"], props={"step": "figures", "closing": True})
    office.add_task(deal, "ops", text["docs"], needs_person=roles.holder(g, "transactions"), props={"step": "docs", "closing": True})


def closing(g: Graph, deal: str) -> dict | None:
    """The deal's closing checklist, each item done or waiting on whom; None before the paperwork is finished."""
    tasks = [t for t in g.of("task", deal) if is_closing(t)]
    if not tasks:
        return None
    p, by = desk_rules.path(g, deal), {t.props["step"]: t for t in tasks}
    inv = [t for t in g.of("task", deal) if t.props["agent"] == "inv"]
    split = [t for t in inv if t.props.get("step") == "split" and t.status in OPEN]
    paid = any(t.props.get("result") == "received" for t in inv) and not split
    comp_open = [t for t in g.of("task", deal) if t.props["agent"] in ("screen", "report") and t.status in OPEN] + \
                [c for c in g.of("check", deal, "open") if c.props.get("agent") == "comp"]
    comp_state = compliance.state(g, deal)
    items = []
    for key, text, role in p["closing"]:
        if key in by:
            t = by[key]
            items.append({"key": key, "text": text, "done": t.status == "done", "task": t.id, "note": t.props.get("reason"),
                          "who": roles.current(g, t) if key == "figures" else roles.holder(g, "transactions")})
        elif key == "invoice":
            items.append({"key": key, "text": text, "done": paid, "who": roles.holder(g, "finance"),
                          "note": None if paid else f"Pay {split[0].props['agency']} their share (Form I)" if split
                          else "Draft, send and collect the commission invoice in Finance"})
        else:
            items.append({"key": key, "text": text, "done": not comp_open and comp_state["ok"], "who": roles.holder(g, "compliance"),
                          "note": f"{len(comp_open)} compliance item(s) still open" if comp_open else None if comp_state["ok"] else comp_state["reason"]})
    sale = sale_of(g, deal)
    return {"items": items, "ready": all(i["done"] for i in items), "sale": sale.id if sale else None,
            "closed_on": sale.props.get("date") if sale else None}


def confirm_figures(office: Office, tid: str, by: str) -> None:
    """The broker confirms the final price and commission, as worked out from the client's words and the owner's rate."""
    from diwan.agents import finance
    g = office.graph()
    t = g.nodes.get(tid)
    if not t or t.type != "task" or not is_closing(t) or t.props.get("step") != "figures":
        raise KeyError(tid)
    if by not in (t.props.get("needs_person"),) and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError(f"Only {name(t.props.get('needs_person'))}, the deal's broker, confirms the final figures.")
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    c = finance.commission(g, t.deal)
    if c.get("missing"):
        raise ValueError(c["missing"])
    office.log.append("task.done", actor=by, agent="ops", deal=t.deal,
                      content={"id": tid, "reason": f"Confirmed: {c['base_label'].lower()} AED {c['base']:,} ({c['fact']}), commission AED {c['amount']:,}",
                               "result": "confirmed"})


def docs_filed(office: Office, tid: str, by: str) -> None:
    g = office.graph()
    roles.check(g, "transactions", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or not is_closing(t) or t.props.get("step") != "docs":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    office.log.append("task.done", actor=by, agent="ops", deal=t.deal, content={"id": tid, "reason": "Closing documents filed", "result": "filed"})


def close(office: Office, deal: str, by: str, *, today) -> str:
    """Every item done: the sale (or let) is recorded with Records, which feeds the owner page and Nova, and the deal
    moves to the archive. Records' own function writes it."""
    g = office.graph()
    roles.check(g, "transactions", by)
    c = closing(g, deal)
    if not c:
        raise ValueError("The paperwork isn't finished, so the deal isn't closing yet.")
    if c["sale"]:
        raise ValueError(f"Already closed as {c['sale']}.")
    if not c["ready"]:
        left = [i["text"] for i in c["items"] if not i["done"]]
        raise ValueError("Not yet: " + "; ".join(left) + ".")
    from diwan.agents import finance
    fig = next(t for t in g.of("task", deal) if is_closing(t) and t.props.get("step") == "figures")
    com = finance.commission(g, deal)
    confirmed = re.search(r"\((F\d+)\)", fig.props.get("reason") or "")
    if not confirmed or com.get("fact") != confirmed.group(1):
        raise ValueError(f"The price changed after {name(fig.props.get('needs_person'))} confirmed it: confirm the final figures again.")
    p, terms = desk_rules.path(g, deal), desk_rules.terms(g, deal)
    if p["id"] == "rent" and not (terms.get("start") and terms.get("end")):
        raise ValueError("Record the tenancy's start and end dates from the contract: the renewal and move-out are dated from them.")
    from diwan import deal_property
    if deal_property.needed(g, deal):
        raise ValueError("Say which property this deal is on: the sale is recorded against it.")
    d = g.nodes[f"deal:{deal}"].props
    sid = office.close_sale(listing=d.get("property"), price_aed=com["base"], commission_aed=com.get("ours", com["amount"]),
                            broker=d["broker"], date=today.isoformat(), deal=deal)
    office.log.append("stage.changed", actor=by, deal=deal, content={"stage": "Won", "why": f"closed as {sid}"})
    office.log.append("case.closed", actor=by, agent="ops", deal=deal, content={"outcome": "won", "sale": sid})
    deal_property.closed(office, deal, by)
    if p["id"] == "rent":  # what keeps running on a let: the renewal question, then the move-out
        end = date.fromisoformat(terms["end"])
        ask = end - timedelta(days=p["renewal_notice_days"])
        office.add_task(deal, "ops", f"Ask {d['customer']} and the landlord whether the tenancy renews; new terms need {p['renewal_notice_days']} days' notice, "
                        f"so by {ask.isoformat()}", needs_person=d["broker"], props={"step": "renewal", "after_close": True, "due": ask.isoformat()})
        office.add_task(deal, "ops", "Move-out: inspection, the security deposit refunded and Ejari cancelled", needs_person=roles.holder(g, "transactions"),
                        props={"step": "moveout", "after_close": True, "due": end.isoformat(), "desk_role": "transactions"})
    return sid


def is_after(t) -> bool:
    """Work that keeps running on a deal once it has closed: a step marked "after", or a rental's renewal and move-out."""
    return (t.props.get("agent") == "ops" and bool(t.props.get("after_close"))) or (t.props.get("agent") == "transfer" and bool(t.props.get("after")))


def after_done(office: Office, tid: str, by: str, note: str) -> None:
    """The broker asked about the renewal, or the transactions officer finished the move-out: what happened, in their words."""
    g = office.graph()
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("agent") != "ops" or not t.props.get("after_close"):
        raise KeyError(tid)
    if by != roles.current(g, t) and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError(f"This is {name(roles.current(g, t))}'s to do.")
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if not note.strip():
        raise ValueError("Say what happened (renewed, leaving, deposit refunded with its reference).")
    office.log.append("task.done", actor=by, agent="ops", deal=t.deal, content={"id": tid, "reason": note.strip(), "result": "done"})


def room(g: Graph, today: date) -> dict:
    """The Operations room: forms sent and to send, with their version; portal drafts waiting for a person; appointments;
    who we are waiting on and for how long; recalled forms; handovers."""
    from datetime import datetime
    forms, drafts, booked, waiting, recalled, handover = [], [], [], [], [], []
    for n in g.deals():
        deal, d = n.deal, n.props
        base = {"deal": deal, "customer": d.get("customer"), "property": d.get("property")}
        if d.get("transfer"):
            booked.append(base | {"when": d["transfer"]["when"], "place": d["transfer"]["place"], "done": bool(d.get("transferred"))})
        for x in g.of("draft", deal):
            kind = x.props["kind"]
            if kind == "Form F" or kind.startswith("Form "):
                s = x.props.get("sent")
                if x.props.get("recalled"):
                    recalled.append(base | {"kind": kind, "version": x.props.get("version"), "reason": x.props["recalled"].get("reason"), "at": x.props["recalled"]["at"]})
                elif x.status != "sent_back":
                    forms.append(base | {"id": x.id, "kind": kind, "version": x.props.get("version"), "sent": s["at"] if s else None})
        for t in g.of("task", deal):
            if t.props["agent"] != "transfer" or t.status not in OPEN:
                continue
            days = (today - datetime.fromisoformat(t.at).date()).days
            row = base | {"id": t.id, "step": t.props["action"], "waiting_on": t.props.get("waiting_on"), "days": days, "gate": t.props.get("flag") == "gate"}
            waiting.append(row)
            if (p := t.props.get("portal")) and p.get("state") == "drafted":
                drafts.append(row | {"portal": p.get("portal"), "fields": p.get("fields")})
            if t.props["action"].lower().startswith("handover"):
                handover.append(row)
    waiting.sort(key=lambda x: -x["days"])
    return {"forms": forms, "drafts": drafts, "appointments": booked, "waiting": waiting, "recalled": recalled, "handover": handover}
