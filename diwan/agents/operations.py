"""Operations: turns agreed terms into the paperwork and tracks it to transfer. The Form F clerk fills the form from
live facts only and stops before Submit; the transactions officer submits. A plan resting on replaced words is sent back by Review and a
new one is made from what stands now; the submit step rests on the same words, so it is withdrawn with them.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan import desk_rules, roles
from diwan.agents import runner
from diwan.agents.charters import get
from diwan.graph import OPEN, Graph
from diwan.pack import Action, Evidence, Pack

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
