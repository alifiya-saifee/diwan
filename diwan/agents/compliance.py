"""Compliance: the legal duties come first. Any change to who pays, how, or what the customer earns reaches the
compliance officer before any other room acts on it, with the old and new words side by side. Every party is put up
for screening, the money story is laid out with the proof still missing, and cash at the reporting threshold gets a
report draft. Nothing here decides suspicion, clears a name or files anything: the compliance officer does.

Her clearance is what the deal waits for (docs/deal-desk.md item 18): it is pinned to the live money and party facts, so a
replaced one makes it stale, and nothing binding happens without it. A possible match stays open as a hold until she
resolves it. A client is never told about a check: they only hear that more information is needed.
"""
from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING

from diwan import desk_rules, roles
from diwan.graph import OPEN, Graph, Node

if TYPE_CHECKING:
    from diwan.office import Office

MONEY_KINDS = {"payer", "payment_promise", "income_claim"}
WATCHED = MONEY_KINDS | {"deal_term"}  # a change to one of these reaches the compliance officer before anyone else acts on it
RISKS = ("low", "medium", "high")


def money_changed(office: Office, deal: str, olds: list[Node], new: Node, cause: int) -> None:
    """Raised before anything else happens to the replaced statements (rooms.md rule 8)."""
    if not started(office.graph(), deal):
        return
    if new.props["kind"] not in WATCHED and not any(o.props["kind"] in WATCHED for o in olds):
        return
    priced = new.props["kind"] == "deal_term"
    before = " / ".join(f'"{o.props["quote"]}"' for o in olds)
    office.log.append("check.raised", actor="comp", agent="comp", deal=deal, caused_by=cause,
                      content={"who": roles.holder(office.graph(), "compliance"), "title": "Price changed" if priced else "Payment arrangement changed", "refs": [o.id for o in olds] + [new.id],
                               "text": f'{"Price" if priced else "Payment arrangement"} changed: {before} became "{new.props["quote"]}". Review before any money moves.'})


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
            add(p["party"], f"{customer}'s {p['relation']}" if p.get("relation") else f"named in {f.id}", f)
        elif p["kind"] == "payer" and p.get("payer") and not _same(p["payer"], customer) and not payers_clash:
            add(p["payer"], f"who will pay for {customer}", f)
    return out


def started(g: Graph, deal: str) -> bool:
    """A lead is Sales' until the deal is agreed: no screening, funding questions or reports for someone who only asked about a flat."""
    if f"deal:{deal}" not in g.nodes:
        return False
    return bool(g.settings.get(f"deal:{deal}", {}).get("agreed")) or not any(c.deal == deal for c in g.of("chat"))


def begin(office: Office, deal: str, cause: int | None = None) -> None:
    """The deal is agreed: everything said so far gets the checks it would have had."""
    from diwan.agents import finance
    screen_parties(office, deal, cause)
    cash_rules(office, deal, cause)
    ask_funding(office, deal, cause)
    finance.payment_rules(office, deal, cause)


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
    if t.props.get("result") == "possible match":
        raise ValueError(f"{t.props.get('person')} is a possible match: resolve it, don't record it again.")
    if result == "possible match":  # a hit is never closed by recording it: it holds the deal until she resolves it
        office.log.append("screening.hit", actor=by, agent="screen", deal=t.deal, content={"id": tid, "note": note.strip()})
        return
    office.log.append("task.done", actor=by, agent="screen", deal=t.deal,
                      content={"id": tid, "reason": f"{result.capitalize()}{': ' + note.strip() if note.strip() else ''}", "result": result})


def resolve_hit(office: Office, tid: str, by: str, match: bool, note: str) -> None:
    """The compliance officer decides a possible match, in her own words. A true match stops the deal; only she can lift it."""
    g = office.graph()
    roles.check(g, "compliance", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "screen" or t.props.get("result") != "possible match":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if not note.strip():
        raise ValueError("Say what you checked to decide it.")
    office.log.append("screening.resolved", actor=by, agent="screen", deal=t.deal, content={"id": tid, "match": match, "note": note.strip()})
    office.log.append("task.done", actor=by, agent="screen", deal=t.deal,
                      content={"id": tid, "reason": f"{'Match confirmed' if match else 'False positive'}: {note.strip()}", "result": "match" if match else "false positive"})
    if match:
        block(office, t.deal, by, f"Screening match on {t.props.get('person')}: {note.strip()}")


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


# ---------- risk and clearance: what the deal waits for ----------

def watched(g: Graph, deal: str) -> list[str]:
    """The live statements a clearance rests on: the money and who is in it."""
    return sorted(f.id for f in g.facts(deal) if f.props["kind"] in WATCHED | {"party"})


def _open_screens(g: Graph, deal: str) -> list[Node]:
    return [t for t in g.of("task", deal) if t.props["agent"] == "screen" and t.status in OPEN]


def _open_checks(g: Graph, deal: str) -> list[Node]:
    return [c for c in g.of("check", deal, "open") if c.props.get("agent") == "comp"]


def state(g: Graph, deal: str) -> dict:
    """Where the deal stands with Compliance now. `ok` is the only thing the other rooms read."""
    d = g.nodes[f"deal:{deal}"].props
    c, who = d.get("compliance"), roles.who(g, "compliance")
    if not c:
        return {"state": "not cleared", "ok": False, "reason": f"{who} hasn't cleared this deal yet"}
    if c["state"] != "cleared":
        return {"state": c["state"], "ok": False, "reason": c.get("reason") or "", "at": c["at"], "by": c["by"], "hold": c["state"] == "blocked"}
    now, then = set(watched(g, deal)), set(c.get("facts") or [])
    if now != then:
        return {"state": "stale", "ok": False, "reason": f"The client's words changed since {who} cleared it ({', '.join(sorted(now ^ then))}): clear it again", "at": c["at"], "by": c["by"]}
    if (open_ := _open_screens(g, deal)):
        return {"state": "stale", "ok": False, "reason": f"{open_[0].props.get('person')} is waiting to be screened", "at": c["at"], "by": c["by"]}
    return {"state": "cleared", "ok": True, "reason": c.get("note") or "", "at": c["at"], "by": c["by"]}


def public_reason(s: dict) -> str:
    """What anyone outside Compliance may read: why a hold is on stays with the officer, or a broker could tip a client off."""
    return s["reason"] if s["state"] in ("not cleared", "stale") else "Waiting for Compliance" if s["state"] != "cleared" else ""


def require(g: Graph, deal: str, what: str) -> None:
    """Called before anything binding. Refuses without the reason, which stays with Compliance; the client is never told."""
    s = state(g, deal)
    if not s["ok"]:
        raise ValueError(f"{what} waits for Compliance: {public_reason(s)}.")


def rate(office: Office, deal: str, by: str, risk: str, *, pep: bool = False, note: str = "") -> None:
    g = office.graph()
    roles.check(g, "compliance", by)
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    if risk not in RISKS:
        raise ValueError(f"The risk is one of {', '.join(RISKS)}.")
    if (risk == "high" or pep) and not note.strip():
        raise ValueError("Say why: high risk and a PEP are explained on the file.")
    office.log.append("compliance.rated", actor=by, agent="comp", deal=deal, content={"risk": risk, "pep": bool(pep), "note": note.strip()})


def needs_senior(risk: dict) -> bool:
    return risk.get("risk") == "high" or bool(risk.get("pep"))


def sign_off(office: Office, deal: str, by: str) -> None:
    """Enhanced due diligence: a high-risk deal or a PEP needs the owner's own sign-off as well as the officer's clearance."""
    g = office.graph()
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    if not roles.is_owner(by):
        raise PermissionError("Only the owner signs off a high-risk deal.")
    risk = g.nodes[f"deal:{deal}"].props.get("risk") or {}
    if not needs_senior(risk):
        raise ValueError("Only a high-risk deal or a PEP needs the owner's sign-off.")
    office.log.append("compliance.rated", actor=by, agent="comp", deal=deal, content={k: risk.get(k) for k in ("risk", "pep", "note")} | {"senior": by, "rated_by": risk.get("by")})


def sof_needed(g: Graph, deal: str) -> bool:
    """Source of funds is asked above the owner's threshold, on high risk, or for a PEP."""
    risk = g.nodes[f"deal:{deal}"].props.get("risk") or {}
    price = (g.facts(deal, "deal_term") or [None])[-1]
    if needs_senior(risk):
        return True
    return bool(price) and (price.props.get("amount_aed") or 0) >= desk_rules.rules(g)["sof_threshold_aed"]


def blockers(office: Office, deal: str, today: date | None = None) -> list[str]:
    """Everything that must be settled before the officer can clear the deal."""
    from diwan import documents
    g, out = office.graph(), []
    risk = g.nodes[f"deal:{deal}"].props.get("risk")
    if not risk:
        out.append("Rate the risk: low, medium or high")
    elif needs_senior(risk) and not risk.get("senior"):
        out.append("The owner signs off this high-risk deal")
    out += [f"{t.props.get('person')} is a possible match: resolve it" if t.props.get("result") == "possible match" else f"Screen {t.props.get('person')}" for t in _open_screens(g, deal)]
    out += [f"Review the check: {c.props.get('title') or c.props['text']}" for c in _open_checks(g, deal)]
    if not any(t.props["agent"] == "screen" for t in g.of("task", deal)):
        out.append("Nobody on this deal has been screened yet: the client hasn't said anything about money")
    if any(q.props.get("kind") == "funding" for q in g.of("question", deal, "open")):
        out.append("How the purchase is funded is still unanswered")
    events = office.log.list(deal=deal)
    if g.settings.get(f"deal:{deal}", {}).get("agreed") and not documents.requests(events, deal):
        out.append("No identity documents have been asked for yet: say who is on the other side of the deal")
    for r in documents.requests(events, deal):
        out += [f"{r['name']}: {documents.KINDS[k].lower()} not confirmed" for k in r["kinds"] if k not in r["confirmed"]]
    out += documents.expired(events, deal, today or date.today())
    return out


def clear(office: Office, deal: str, by: str, note: str = "") -> None:
    """The officer's clearance, on the facts that stand now. Missing proof above the threshold needs her reason on the file."""
    g = office.graph()
    roles.check(g, "compliance", by)
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    if left := blockers(office, deal):
        raise ValueError("Not yet: " + "; ".join(left) + ".")
    missing = [p for p in source_of_funds(g, deal)["proof"] if not p["have"]]
    if missing and sof_needed(g, deal) and not note.strip():
        raise ValueError(f"{len(missing)} source-of-funds proof{'s are' if len(missing) > 1 else ' is'} missing: get them, or say why you accept the deal without them.")
    office.log.append("compliance.cleared", actor=by, agent="comp", deal=deal, content={"facts": watched(g, deal), "note": note.strip(), "waived": [p["kind"] for p in missing]})


def needs_info(office: Office, deal: str, by: str, kinds: list[str], note: str = "") -> str | None:
    """More is needed: the client is asked through their own link, and hears only that more information is needed."""
    from diwan import client_msgs, documents
    g = office.graph()
    roles.check(g, "compliance", by)
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    if not note.strip() and not kinds:
        raise ValueError("Choose what is needed, or say what.")
    token = documents.ask(office, deal, kinds, by) if kinds else None
    office.log.append("compliance.needs_info", actor=by, agent="comp", deal=deal,
                      content={"reason": note.strip() or ", ".join(documents.KINDS[k] for k in kinds), "kinds": kinds, "token": token})
    if token:
        client_msgs.tell(office, deal, f"We need a little more information to complete your file: {documents.link(token)}",
                         what=f"send them their documents link for {', '.join(documents.KINDS[k].lower() for k in kinds)}")
    return token


def block(office: Office, deal: str, by: str, reason: str) -> None:
    """The deal stops and the owner is told. The client hears nothing about why."""
    from diwan.people import PEOPLE
    g = office.graph()
    roles.check(g, "compliance", by)
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    if not reason.strip():
        raise ValueError("Say why the deal is blocked.")
    office.log.append("compliance.blocked", actor=by, agent="comp", deal=deal, content={"reason": reason.strip()})
    owner = next((p for p, v in PEOPLE.items() if v.get("role") == "Owner"), None)
    d = g.nodes[f"deal:{deal}"].props
    office.log.append("question.asked", actor="comp", agent="comp", deal=deal, content={"to": owner, "refs": [], "kind": "blocked",
                      "text": f"Compliance stopped {d['customer']}'s deal on {d['property']}. Nothing binding happens on it now. Don't discuss the reason with the client."})


def draft_str(office: Office, deal: str, by: str, why: str) -> str:
    """A suspicious transaction report for the officer to file on goAML. Only she starts one; the agent writes the file, never decides."""
    g = office.graph()
    roles.check(g, "compliance", by)
    if f"deal:{deal}" not in g.nodes:
        raise KeyError(deal)
    if not why.strip():
        raise ValueError("Say what you find suspicious, in your own words.")
    d = g.nodes[f"deal:{deal}"].props
    facts = [f for f in g.facts(deal) if f.props["kind"] in WATCHED | {"party"}]
    slides = [{"n": 1, "text": f"The officer's grounds: {why.strip()}", "facts": []},
              {"n": 2, "text": f"Customer {d['customer']}; property {d['property']}", "facts": []}]
    slides += [{"n": i, "text": f'{f.label}: "{f.props["quote"]}"', "facts": [f.id]} for i, f in enumerate(facts, 3)]
    did = office.make_draft(deal, "suspicious transaction report", slides, by="report")
    office.add_task(deal, "report", f"File the suspicious transaction report {did} on goAML", rests_on=[f.id for f in facts],
                    needs_person=roles.holder(g, "compliance"), props={"draft": did})
    return did


def payment_pattern(g: Graph, deal: str, pay: dict) -> list[str]:
    """What the Payment tracker sees in a marked payment that the officer should look at before any receipt goes out."""
    d = g.nodes[f"deal:{deal}"].props
    flags = []
    method, amount, who = pay.get("method") or "", pay.get("amount") or 0, (pay.get("payer") or "").strip()
    if method == "cash" and amount >= desk_rules.rules(g)["cash_report_aed"]:
        flags.append(f"cash of AED {amount:,}, at or above the reporting limit")
    if method == "crypto":
        flags.append("paid in crypto")
    if who and not _same(who, d["customer"]):
        said = any(_same(who, f.props["payer"]) for f in g.facts(deal, "payer"))
        flags.append(f"paid by {who}, not {d['customer']}" + ("" if said else ", and nobody said so"))
    promise = (g.facts(deal, "payment_promise") or [None])[-1]
    said_how = (promise.props.get("method") or "") if promise else ""
    if said_how and method and method.lower() not in said_how.lower() and said_how.lower() not in method.lower():
        flags.append(f'they said "{said_how}", it came by {method}')
    if pay.get("parts", 1) >= 3:
        flags.append(f"split into {pay['parts']} part payments")
    return flags


def room(g: Graph, today: date) -> dict:
    """The Compliance room: corrections side by side, the screening queue and hits, source-of-funds files, risk per deal,
    holds, report drafts and the rules in force."""
    rows, corrections, screens, hits, holds, reports = [], [], [], [], [], []
    r = desk_rules.rules(g)
    for n in g.deals():
        deal, d = n.deal, n.props
        s, risk = state(g, deal), d.get("risk") or {}
        funds = source_of_funds(g, deal)
        base = {"deal": deal, "customer": d.get("customer"), "property": d.get("property")}
        if funds["numbers"] or d.get("compliance") or risk:
            rows.append(base | {"state": s["state"], "ok": s["ok"], "reason": s["reason"], "risk": risk.get("risk"), "pep": bool(risk.get("pep")), "senior": risk.get("senior"),
                                "proof_missing": funds["missing"], "proof": [p["text"] for p in funds["proof"] if not p["have"]], "numbers": funds["numbers"], "sof_needed": sof_needed(g, deal)})
        if s["state"] in ("blocked", "needs_info", "stale"):
            holds.append(base | {"state": s["state"], "reason": s["reason"], "at": s.get("at")})
        for t in g.of("task", deal):
            if t.props["agent"] == "screen" and t.status in OPEN:
                (hits if t.props.get("result") == "possible match" else screens).append(base | {"id": t.id, "person": t.props.get("person"), "role": t.props.get("role"), "at": t.at, "note": t.props.get("hit")})
            if t.props["agent"] == "report":
                reports.append(base | {"id": t.id, "action": t.props["action"], "status": t.status, "draft": t.props.get("draft"), "reason": t.props.get("reason")})
    for f in g.of("fact"):
        if f.props.get("replaces") and f.deal and f"deal:{f.deal}" in g.nodes:
            d = g.nodes[f"deal:{f.deal}"].props
            corrections.append({"deal": f.deal, "customer": d.get("customer"), "fact": f.id, "new": f.props["quote"], "kind": f.label, "at": f.at,
                                "old": [{"id": o, "quote": g.nodes[o].props["quote"]} for o in f.props["replaces"] if o in g.nodes]})
    corrections.sort(key=lambda c: c["at"], reverse=True)
    return {"corrections": corrections[:30], "screens": screens, "hits": hits, "holds": holds, "reports": reports, "deals": rows,
            "rules": {"cash_report_aed": r["cash_report_aed"], "sof_threshold_aed": r["sof_threshold_aed"]}, "today": today.isoformat()}


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
    # the model also files terms with no figure ("Dubai Marina", "my brother will help with the deposit"): only a figure is a number here
    one = lambda kind: ([f for f in facts if f.props["kind"] == kind and (kind not in ("deal_term", "payment_promise") or f.props.get("amount_aed"))]  # noqa: E731
                        or [None])[-1]
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
