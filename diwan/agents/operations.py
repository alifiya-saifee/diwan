"""Operations: turns agreed terms into the paperwork and tracks it to transfer. The Form F clerk fills the form from
live facts only and stops before Submit; the transactions officer submits. A plan resting on replaced words is sent back by Review and a
new one is made from what stands now; the submit step rests on the same words, so it is withdrawn with them.
"""
from __future__ import annotations

import re

from typing import TYPE_CHECKING

from diwan import desk_rules, roles
from diwan.agents import runner
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
            ("Seller", None, None), ("Buyer passport number", None, None)]


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
    g = office.graph()
    for did in sent_back:
        if g.nodes[did].props["kind"] == "Form F":
            make_plan(office, deal, cause)


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
    office.log.append("task.done", actor=by, agent="formf", deal=t.deal,
                      content={"id": tid, "reason": f"Submitted on the DLD portal, reference {reference.strip()}", "result": "submitted"})
    for r in g.of("request", t.deal, "open"):  # the clerk's "only a person submits" request is answered by this
        if r.props.get("kind") == "submit" and r.props.get("agent") == "formf":
            office.log.append("decision.made", actor=by, deal=t.deal, content={"card": r.id, "answer": f"Submitted, reference {reference.strip()}"})
    for step, who in desk_rules.path(g, t.deal)["steps"]:  # the owner's steps for this deal's path
        office.add_task(t.deal, "transfer", step, needs_person=roles.holder(g, "transactions"), props={"waiting_on": who})


def tick(office: Office, tid: str, by: str, note: str = "") -> None:
    roles.check(office.graph(), "transactions", by)
    t = office.graph().nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "transfer":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    office.log.append("task.done", actor=by, agent="transfer", deal=t.deal, content={"id": tid, "reason": f"Done{': ' + note.strip() if note.strip() else ''}"})
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
    who = roles.holder(g, "transactions")
    tids = [office.add_task(deal, "transfer", step, needs_person=who, props={"waiting_on": waits}) for step, waits in p["steps"]]
    if p["id"] == "rent":
        rent = (g.facts(deal, "deal_term") or [None])[-1]
        if rent and rent.props.get("amount_aed"):
            amount = round(rent.props["amount_aed"] * p["deposit_pct"] / 100)
            office.add_task(deal, "pay", f"Expect the security deposit AED {amount:,} ({p['deposit_pct']}% of the yearly rent) from the tenant, held by the landlord",
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
    steps = [t for t in g.of("task", deal) if t.props["agent"] == "transfer"]
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
    paid = any(t.props["agent"] == "inv" and t.props.get("result") == "received" for t in g.of("task", deal))
    comp_open = [t for t in g.of("task", deal) if t.props["agent"] in ("screen", "report") and t.status in OPEN] + \
                [c for c in g.of("check", deal, "open") if c.props.get("agent") == "comp"]
    items = []
    for key, text, role in p["closing"]:
        if key in by:
            t = by[key]
            items.append({"key": key, "text": text, "done": t.status == "done", "task": t.id, "note": t.props.get("reason"),
                          "who": roles.current(g, t) if key == "figures" else roles.holder(g, "transactions")})
        elif key == "invoice":
            items.append({"key": key, "text": text, "done": paid, "who": roles.holder(g, "finance"),
                          "note": None if paid else "Draft, send and collect the commission invoice in Finance"})
        else:
            items.append({"key": key, "text": text, "done": not comp_open, "who": roles.holder(g, "compliance"),
                          "note": None if not comp_open else f"{len(comp_open)} compliance item(s) still open"})
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
    d = g.nodes[f"deal:{deal}"].props
    sid = office.close_sale(listing=d.get("property"), price_aed=com["base"], commission_aed=com["amount"],
                            broker=d["broker"], date=today.isoformat(), deal=deal)
    office.log.append("stage.changed", actor=by, deal=deal, content={"stage": "Won", "why": f"closed as {sid}"})
    return sid
