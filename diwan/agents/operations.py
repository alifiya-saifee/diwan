"""Operations: turns agreed terms into the paperwork and tracks it to transfer. The Form F clerk fills the form from
live facts only and stops before Submit; Joseph submits.
"""
from __future__ import annotations

from diwan.agents import runner
from diwan.agents.charters import get
from diwan.graph import Graph
from diwan.office import Office
from diwan.pack import Action, Evidence, Pack


def _evidence(g: Graph, ids: list[str]) -> list[Evidence]:
    return [Evidence(g.nodes[i].props["quote"], i) for i in ids if g.nodes[i].type == "fact"]


def formf_plan(office: Office, deal: str, tid: str, req: str) -> str:
    """The Form F clerk's plan: every field from a live fact or the deal record, or left for Joseph with the reason."""
    g, c = office.graph(), get("formf")
    d = g.nodes[f"deal:{deal}"].props
    one = lambda kind: (g.facts(deal, kind) or [None])[-1]  # noqa: E731
    price, dep, payer = one("deal_term"), one("payment_promise"), one("payer")
    fields = [("Buyer", d["customer"], f"deal:{deal}"), ("Property", d["property"], f"deal:{deal}"),
              ("Price", price and f"AED {price.props['amount_aed']:,}", price and price.id),
              ("Deposit", dep and f"AED {dep.props['amount_aed']:,}", dep and dep.id),
              ("Deposit paid by", payer and payer.props["payer"], payer and payer.id),
              ("Seller", None, None), ("Buyer passport number", None, None)]
    filled = [f"{k}: {v} ({src})" for k, v, src in fields if v]
    empty = [f"{k}: not said in the meeting; Joseph fills it" for k, v, _ in fields if not v]
    used = [src for _, v, src in fields if v and src and src in g.nodes and g.nodes[src].type == "fact"]
    pack = Pack(req, c.id, f"Form F plan: {len(filled)} of {len(fields)} fields from live facts, {len(empty)} left for Joseph.",
                evidence=_evidence(g, used), missing=empty, next=filled,
                actions=[Action("fill_form", "Type the planned fields into the portal"), Action("submit", "Submit Form F")])
    runner.submit(office.log, c, pack, sources={i: g.record(i) for i in used}, deal=deal)
    office.finish_task(tid, "Field plan ready; Submit waits for Joseph")
    return f"{pack.verdict} Submit waits for Joseph."
