"""Compliance: the legal duties come first. Any change to who pays, how, or what the customer earns reaches the
compliance officer before any other room acts on it, with the old and new words side by side. Every party is put up
for screening, the money story is laid out with the proof still missing, and cash at the reporting threshold gets a
report draft. Nothing here decides suspicion, clears a name or files anything: the compliance officer does.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from diwan import desk_rules, roles
from diwan.graph import OPEN, Graph, Node

if TYPE_CHECKING:
    from diwan.office import Office

MONEY_KINDS = {"payer", "payment_promise", "income_claim"}


def money_changed(office: Office, deal: str, olds: list[Node], new: Node, cause: int) -> None:
    """Raised before anything else happens to the replaced statements (rooms.md rule 8)."""
    if new.props["kind"] not in MONEY_KINDS and not any(o.props["kind"] in MONEY_KINDS for o in olds):
        return
    before = " / ".join(f'"{o.props["quote"]}"' for o in olds)
    office.log.append("check.raised", actor="comp", agent="comp", deal=deal, caused_by=cause,
                      content={"who": roles.holder(office.graph(), "compliance"), "title": "Payment arrangement changed", "refs": [o.id for o in olds] + [new.id],
                               "text": f'Payment arrangement changed: {before} became "{new.props["quote"]}". Review before any money moves.'})


# ---------- screening ----------

def _same(a: str, b: str) -> bool:
    """"Tariq" and "Tariq Haddad" are the same person on one deal."""
    x, y = set(re.findall(r"\w+", a.lower())), set(re.findall(r"\w+", b.lower()))
    return bool(x and y) and (x <= y or y <= x)


def parties(g: Graph, deal: str) -> list[dict]:
    """Everyone the live facts make part of the money: the customer once money is discussed, anyone named, any payer."""
    d = g.nodes[f"deal:{deal}"].props
    customer, live = d["customer"], g.facts(deal)
    out: list[dict] = []

    def add(who: str, role: str, fact: Node | None):
        if p := next((p for p in out if _same(p["name"], who)), None):
            if fact and fact.id not in p["facts"]:
                p["facts"].append(fact.id)
            return
        out.append({"name": who, "role": role, "facts": [fact.id] if fact else []})

    if any(f.props["kind"] in MONEY_KINDS | {"deal_term"} for f in live):
        add(customer, "the buyer", None)
    payers_clash = len([f for f in live if f.props["kind"] == "payer"]) > 1  # the broker decides first; nobody new is screened
    for f in live:
        p = f.props
        if p["kind"] == "party" and p.get("party"):
            add(p["party"], f"{customer}'s {p['relation']}" if p.get("relation") else f"named by {customer}", f)
        elif p["kind"] == "payer" and p.get("payer") and not _same(p["payer"], customer) and not payers_clash:
            add(p["payer"], f"who will pay for {customer}", f)
    return out


def screen_parties(office: Office, deal: str, cause: int | None) -> None:
    """One screening per person while they are part of the deal. With no sanctions list connected the Screening analyst
    prepares the check and the compliance officer records the result; nobody is cleared by an agent."""
    g = office.graph()
    if f"deal:{deal}" not in g.nodes:
        return
    tasks = [t for t in g.of("task", deal) if t.props["agent"] == "screen" and (t.status in OPEN or t.status == "done")]
    for p in parties(g, deal):
        if any(_same(t.props.get("person") or t.props["action"][7:], p["name"]) for t in tasks):
            continue
        office.add_task(deal, "screen", f"Screen {p['name']}, {p['role']}", rests_on=p["facts"], needs_person=roles.holder(g, "compliance"),
                        caused_by=cause, props={"person": p["name"], "role": p["role"]})


def record_screening(office: Office, tid: str, by: str, result: str, note: str = "") -> None:
    roles.check(office.graph(), "compliance", by)
    t = office.graph().nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "screen":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if result not in ("clear", "possible match"):
        raise ValueError("The result is clear or possible match.")
    if result == "possible match" and not note.strip():
        raise ValueError("Say which list and entry it may match.")
    office.log.append("task.done", actor=by, agent="screen", deal=t.deal,
                      content={"id": tid, "reason": f"{result.capitalize()}{': ' + note.strip() if note.strip() else ''}", "result": result})


def record_filing(office: Office, tid: str, by: str, reference: str) -> None:
    """The compliance officer files the cash report on goAML and records its reference; the agent never files."""
    roles.check(office.graph(), "compliance", by)
    t = office.graph().nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "report":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if not reference.strip():
        raise ValueError("Give the goAML reference of the filed report.")
    office.log.append("task.done", actor=by, agent="report", deal=t.deal, content={"id": tid, "reason": f"Filed on goAML, reference {reference.strip()}"})


# ---------- source of funds ----------

def _aed(n: float) -> str:
    return f"AED {n:,.0f}"


def source_of_funds(g: Graph, deal: str, nodes: dict | None = None) -> dict:
    """The money story side by side with the words it rests on, and the proof still missing. Numbers, never a verdict.
    `nodes`: this deal's nodes by type, when the caller already grouped them (the Deal desk does, for hundreds of deals)."""
    if nodes is None:
        facts, docs = g.facts(deal), g.of("document", deal)
    else:
        facts = [f for f in nodes.get("fact", []) if f.status == "live" and f.props.get("stance", "asserted") == "asserted"]
        docs = nodes.get("document", [])
    one = lambda kind: ([f for f in facts if f.props["kind"] == kind] or [None])[-1]  # noqa: E731
    price, dep, income, payer = one("deal_term"), one("payment_promise"), one("income_claim"), one("payer")
    customer = g.nodes[f"deal:{deal}"].props["customer"]
    numbers = []
    if price:
        numbers.append({"what": "Price", "value": _aed(price.props["amount_aed"]), "fact": price.id, "quote": price.props["quote"]})
    if dep:
        numbers.append({"what": "Deposit", "value": _aed(dep.props["amount_aed"]) + (f" by {dep.props['method']}" if dep.props.get("method") else ""),
                        "fact": dep.id, "quote": dep.props["quote"]})
    if payer:
        numbers.append({"what": "Paid by", "value": payer.props["payer"], "fact": payer.id, "quote": payer.props["quote"]})
    if income:
        numbers.append({"what": "Stated income", "value": _aed(income.props["monthly_income_aed"]) + " a month", "fact": income.id,
                        "quote": income.props["quote"]})
    if price and income and income.props.get("monthly_income_aed"):
        years = price.props["amount_aed"] / (income.props["monthly_income_aed"] * 12)
        numbers.append({"what": "Price in years of stated income", "value": f"{years:.1f}", "fact": None, "quote": None})

    who = payer.props["payer"] if payer else customer
    needs = []
    if dep:
        needs.append(("bank statement", f"Bank statement of {who}'s account showing {_aed(dep.props['amount_aed'])}", [dep.id] + ([payer.id] if payer else [])))
    if payer and not _same(payer.props["payer"], customer):
        needs.append(("relationship proof", f"Proof of how {payer.props['payer']} is related to {customer}, and why they pay", [payer.id]))
    if income:
        needs.append(("salary certificate", f"Salary certificate or 6 months of statements for {customer}", [income.id]))
    elif price or dep:
        needs.append(("source of funds", f"{customer} has not said how the purchase is funded: ask, then the proof", []))
    if price and dep and price.props["amount_aed"] > dep.props["amount_aed"]:
        needs.append(("balance funding", f"How the balance of {_aed(price.props['amount_aed'] - dep.props['amount_aed'])} is paid "
                                          "(mortgage pre-approval or proof of funds)", [price.id, dep.id]))
    proof = []
    for kind, text, facts in needs:
        doc = next((d for d in docs if d.props["kind"] == kind), None)
        proof.append({"kind": kind, "text": text, "facts": facts, "have": doc.id if doc else None,
                      "have_title": doc.props["title"] if doc else None})
    return {"numbers": numbers, "proof": proof, "missing": sum(1 for p in proof if not p["have"])}


# ---------- cash ----------

def cash_rules(office: Office, deal: str, cause: int | None) -> None:
    """A live cash promise at or above the threshold has one report draft and one filing task for the compliance officer, both resting
    on the words; replaced words send the draft back and withdraw the task."""
    g = office.graph()
    payer = (g.facts(deal, "payer") or [None])[-1]
    customer = g.nodes[f"deal:{deal}"].props["customer"]
    for p in g.facts(deal, "payment_promise"):
        if (p.props.get("method") or "") != "cash" or (p.props.get("amount_aed") or 0) < desk_rules.rules(g)["cash_report_aed"]:
            continue
        if any(t.props["agent"] == "report" and p.id in t.props.get("rests_on", []) and t.status in OPEN | {"done"} for t in g.of("task", deal)):
            continue
        rests = [p.id] + ([payer.id] if payer else [])
        slides = [{"n": 1, "text": f"Cash {_aed(p.props['amount_aed'])}, said: \"{p.props['quote']}\"", "facts": [p.id]},
                  {"n": 2, "text": f"Paid by {payer.props['payer'] if payer else 'not said yet'}", "facts": [payer.id] if payer else []},
                  {"n": 3, "text": f"Buyer {customer}; property {g.nodes[f'deal:{deal}'].props['property']}", "facts": []}]
        did = office.make_draft(deal, "cash report", slides, by="report")
        office.add_task(deal, "report", f"File the cash report {did} on goAML once the cash is received", rests_on=rests,
                        needs_person=roles.holder(g, "compliance"), caused_by=cause, props={"draft": did})
        g = office.graph()


# ---------- what nobody has said yet, and deals from before these rules ----------

def ask_funding(office: Office, deal: str, cause: int | None) -> None:
    """A price or deposit is on the table and the customer has not said how it is funded: one question to the broker,
    once (Compliance may ask; it never guesses)."""
    g = office.graph()
    live = g.facts(deal)
    money = [f for f in live if f.props["kind"] in ("deal_term", "payment_promise")]
    if income := next((f for f in live if f.props["kind"] == "income_claim"), None):
        for q in g.of("question", deal, "open"):  # the customer's own words answered it
            if q.props.get("kind") == "funding":
                office.log.append("question.answered", actor="comp", agent="comp", deal=deal, caused_by=cause,
                                  content={"card": q.id, "answer": f'{income.props.get("speaker")} said: "{income.props["quote"]}" ({income.id})'})
        return
    if not money:
        return
    if any(q.props.get("kind") == "funding" for q in g.of("question", deal)):
        return
    d = g.nodes[f"deal:{deal}"].props
    office.log.append("question.asked", actor="comp", agent="comp", deal=deal, caused_by=cause,
                      content={"to": d["broker"], "refs": [money[0].id], "kind": "funding",
                               "text": f"How is {d['customer']} funding the purchase? Compliance needs it before any money moves."})


def catch_up(office: Office) -> int:
    """Run the Compliance rules over every open deal, for deals whose facts were recorded before a rule existed.
    Each rule only adds what is missing, so running it twice changes nothing. Returns how many events it added."""
    before = len(office.log.list())
    for d in office.graph().deals():
        screen_parties(office, d.deal, None)
        ask_funding(office, d.deal, None)
        cash_rules(office, d.deal, None)
    return len(office.log.list()) - before
