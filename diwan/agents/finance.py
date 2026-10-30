"""Finance: what money is expected, from whom, resting on which words. An expectation is withdrawn when the words it
rests on are replaced; nothing here moves money.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from diwan import desk_rules, roles
from diwan.graph import OPEN, Graph, Node

if TYPE_CHECKING:
    from diwan.office import Office


def payment_rules(office: Office, deal: str, cause: int) -> None:
    """The Payment tracker's rules: every live payment promise has one open expectation resting on the promise and
    on who pays (Compliance screens a third-party payer). Nobody named as payer: one question to the broker."""
    g = office.graph()
    payers = g.facts(deal, "payer")
    if len(payers) > 1:
        return  # a contradiction about who pays is open; nothing is expected from anyone until the broker decides
    for p in g.facts(deal, "payment_promise"):
        payer = payers[-1] if payers else None
        rests = [p.id] + ([payer.id] if payer else [])
        if any(t.props["agent"] == "pay" and t.status in OPEN and set(t.props.get("rests_on", [])) == set(rests) for t in g.of("task", deal)):
            continue
        if not payer:
            if not any(q.status == "open" and p.id in q.props.get("refs", []) for q in g.of("question", deal)):
                office.log.append("question.asked", actor="pay", agent="pay", deal=deal, caused_by=cause,
                                  content={"to": "omar", "refs": [p.id], "text": f'Who pays this: "{p.props["quote"]}"?'})
            continue
        who = payer.props["payer"]
        office.add_task(deal, "pay", f"Expect AED {p.props['amount_aed']:,} by {p.props.get('method') or 'a method not yet stated'} from {who}",
                        rests_on=rests, caused_by=cause)
        g = office.graph()


# ---------- when, received, overdue, release ----------

DUBAI = timezone(timedelta(hours=4))
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def due_date(words: str | None, said: date) -> date | None:
    """The day a payment was promised for, from the customer's own words; None when no day was said."""
    w = (words or "").lower()
    if not w:
        return None
    if "today" in w:
        return said
    if "tomorrow" in w:
        return said + timedelta(days=1)
    if "this week" in w:
        return said + timedelta(days=6 - said.weekday())
    if "next week" in w:
        return said + timedelta(days=7)
    if "next month" in w:
        return said + timedelta(days=30)
    if day := next((i for i, d in enumerate(DAYS) if d in w), None):
        return said + timedelta(days=(day - said.weekday() - 1) % 7 + 1)
    return None


def expected(g: Graph, task: Node, today: date) -> dict:
    """What the Payment tracker shows for one expectation: the promise, the day, and whether it is late. `kind` is what
    the money is: a payment the client promised, a security deposit, an SPA instalment or a rent cheque."""
    if task.props.get("due"):  # from a signed document's schedule (the SPA's payment plan, the tenancy's cheques)
        return {"amount_aed": task.props.get("amount_aed"), "due": task.props["due"], "due_words": None, "kind": task.props.get("schedule"),
                "from": task.props.get("document"), "payee": task.props.get("payee"), "overdue": task.props["due"] < today.isoformat() and task.status in OPEN}
    promise = next((g.nodes[f] for f in task.props.get("rests_on", []) if f in g.nodes and g.nodes[f].props.get("kind") == "payment_promise"), None)
    if not promise:  # worked out from the rules (a rental's deposit), not promised in words: no day was said
        return {"amount_aed": task.props.get("amount_aed"), "due": None, "due_words": None, "kind": "security deposit", "overdue": False} if task.props.get("amount_aed") else {}
    said = datetime.fromisoformat(promise.at).astimezone(DUBAI).date()
    due = due_date(promise.props.get("due"), said)
    return {"amount_aed": promise.props.get("amount_aed"), "due": due.isoformat() if due else None, "due_words": promise.props.get("due"),
            "kind": "promised payment", "overdue": bool(due and due < today and task.status in OPEN)}


def mark_received(office: Office, tid: str, by: str, reference: str, *, today: date) -> str:
    """A person saw the money arrive; the agent never marks money received. The receipt is filed with Records."""
    g = office.graph()
    roles.check(g, "finance", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "pay":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if not reference.strip():
        raise ValueError("Give the bank or receipt reference you saw the money under.")
    e = expected(g, t, today)
    said = f"Paid into {t.props['payee']}, receipt {reference.strip()}" if t.props.get("payee") == ESCROW else f"Received, reference {reference.strip()}"
    office.log.append("task.done", actor=by, agent="pay", deal=t.deal, content={"id": tid, "reason": said, "result": "received"})
    deal = g.nodes[f"deal:{t.deal}"].props
    return office.file_document(kind="receipt", title=f"{t.props['action'].replace('Expect ', 'Received ')}, reference {reference.strip()}",
                                date=today.isoformat(), by=by, deal=t.deal, amount_aed=e.get("amount_aed"), party=deal["customer"])


def approve_release(office: Office, tid: str, by: str) -> str:
    """Releasing received money is the finance holder's approval, resting on the same words as the payment: if they are replaced
    before it runs, the guard refuses it."""
    g = office.graph()
    roles.check(g, "finance", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "pay":
        raise KeyError(tid)
    if t.props.get("result") != "received":
        raise ValueError("Only money already received can be released.")
    if t.props.get("payee") == ESCROW:
        raise ValueError("An instalment is paid straight into the project's escrow; we never hold it, so there is nothing to release.")
    if any(a.props["action"].endswith(f"({tid})") and a.status in ("given", "executed") for a in g.of("approval", t.deal)):
        raise ValueError(f"The release of {tid} is already approved.")
    action = t.props["action"].replace("Expect ", "Release ") + f" to {t.props.get('payee') or 'the seller' + chr(39) + 's escrow'} ({tid})"
    return office.approve(t.deal, by, action, t.props.get("rests_on", []))


# ---------- commission: worked out from the price the client said and the owner's rate, invoiced, collected ----------

def paid_in(g: Graph, deal: str) -> int:
    """What the buyer has paid on the deal so far, as marked received by a person."""
    return sum(t.props.get("amount_aed") or expected(g, t, date.today()).get("amount_aed") or 0
               for t in g.of("task", deal) if t.props["agent"] == "pay" and t.props.get("result") == "received")


def commission(g: Graph, deal: str) -> dict:
    """Our commission on a deal, never estimated: the latest price the client said x the rate + VAT, owed by whoever the
    owner's settings say pays it. The rate is the deal's signed agency agreement's, else the developer's agreement, else
    the owner's rate for the path; another agency's share under Form I comes off what we keep. A developer owes it once
    the buyer has paid the share of the price its agreement says. Says what is missing instead of guessing."""
    p, r, t = desk_rules.path(g, deal), desk_rules.rules(g), desk_rules.terms(g, deal)
    price = (g.facts(deal, "deal_term") or [None])[-1]
    pct, rate_from = p["commission_pct"], "the owner's rate for this path"
    dev = desk_rules.developer(g, t.get("developer")) if p["id"] == "offplan" else None
    if dev:
        pct, rate_from = dev["commission_pct"], f"the agency agreement with {dev['name']}"
    if "rate_pct" in t:
        pct, rate_from = t["rate_pct"], t.get("agreement") or "the signed agency agreement"
    out = {"path": p["id"], "pct": pct, "rate_from": rate_from, "vat_pct": r["vat_pct"], "payer": p["commission_from"],
           "base_label": "Yearly rent" if p["id"] == "rent" else "Price", "developer": dev["name"] if dev else None}
    if not price or not price.props.get("amount_aed"):
        return out | {"missing": "No price has been said yet, so there is nothing to work it out from."}
    base = price.props["amount_aed"]
    amount = round(base * pct / 100)
    vat = round(amount * r["vat_pct"] / 100)
    out |= {"base": base, "fact": price.id, "quote": price.props["quote"], "amount": amount, "vat": vat, "total": amount + vat}
    if t.get("other_agency"):
        share = round(amount * t["other_share_pct"] / 100)
        out |= {"other_agency": t["other_agency"], "share_pct": t["other_share_pct"], "share": share, "ours": amount - share}
    if p.get("dld_fee_pct"):
        out["fees"] = [{"what": f"DLD fee {p['dld_fee_pct']}%", "aed": round(base * p["dld_fee_pct"] / 100), "payer": "buyer"}]
    if dev:
        paid = paid_in(g, deal)
        out["trigger"] = {"pct": dev["payable_after_pct"], "paid": paid, "paid_pct": round(paid * 100 / base, 1),
                          "met": paid * 100 >= dev["payable_after_pct"] * base}
    return out


def draft_invoice(office: Office, deal: str, by: str) -> str:
    """The invoice is a draft whose lines rest on the price fact: if the client changes the price, Review sends it back."""
    g = office.graph()
    roles.check(g, "finance", by)
    c = commission(g, deal)
    if c.get("missing"):
        raise ValueError(c["missing"])
    if any(d.props["kind"] == "commission invoice" and d.status != "sent_back" for d in g.of("draft", deal)):
        raise ValueError("This deal already has a commission invoice; it is redrafted only if it is sent back.")
    from diwan import agency_forms
    if waiting := agency_forms.unsigned(g, deal):
        raise ValueError(f"{' and '.join(waiting)} {'waits' if len(waiting) == 1 else 'wait'} for a signature: the commission is invoiced once the agency forms are signed.")
    if (tr := c.get("trigger")) and not tr["met"]:
        raise ValueError(f"{c['developer']} owes our commission once {tr['pct']}% of the price is paid; {tr['paid_pct']}% is paid so far.")
    slides = [{"n": 1, "text": f'{c["base_label"]} AED {c["base"]:,}, said: "{c["quote"]}"', "facts": [c["fact"]]},
              {"n": 2, "text": f'Commission {c["pct"]}%: AED {c["amount"]:,}', "facts": [c["fact"]]},
              {"n": 3, "text": f'VAT {c["vat_pct"]}%: AED {c["vat"]:,}', "facts": [c["fact"]]},
              {"n": 4, "text": f'Total due from the {c["payer"]}: AED {c["total"]:,}', "facts": [c["fact"]]}]
    did = office.make_draft(deal, "commission invoice", slides, by="inv")
    office.add_task(deal, "inv", f'Send commission invoice {did} to the {c["payer"]}: AED {c["total"]:,}', rests_on=[c["fact"]],
                    needs_person=roles.holder(g, "finance"), props={"draft": did, "amount_aed": c["total"], "step": "send", "payer": c["payer"]})
    return did


def _inv_task(g: Graph, tid: str, step: str) -> Node:
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "inv" or t.props.get("step") != step:
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}" + (f": {t.props['reason']}" if t.props.get("reason") else "."))
    return t


def split_paid(office: Office, tid: str, by: str, reference: str) -> None:
    g = office.graph()
    roles.check(g, "finance", by)
    t = _inv_task(g, tid, "split")
    if not reference.strip():
        raise ValueError("Give the bank reference of the payment to the other agency.")
    office.log.append("task.done", actor=by, agent="inv", deal=t.deal, content={"id": tid, "reason": f"Paid, reference {reference.strip()}", "result": "paid"})


def invoice_sent(office: Office, tid: str, by: str, number: str) -> str:
    g = office.graph()
    roles.check(g, "finance", by)
    t = _inv_task(g, tid, "send")
    if g.stale(tid) or g.nodes[t.props["draft"]].status == "sent_back":
        raise ValueError(f"{t.props['draft']} rests on a price the client replaced; draft the invoice again.")
    if not number.strip():
        raise ValueError("Give the invoice number you sent it under.")
    office.log.append("task.done", actor=by, agent="inv", deal=t.deal, content={"id": tid, "reason": f"Sent as invoice {number.strip()}", "result": "sent"})
    payer = t.props["action"].split(" to the ")[1].split(":")[0]
    return office.add_task(t.deal, "inv", f'Collect commission AED {t.props["amount_aed"]:,} from the {payer} (invoice {number.strip()})',
                           rests_on=t.props.get("rests_on", []), needs_person=roles.holder(g, "finance"),
                           props={"draft": t.props["draft"], "amount_aed": t.props["amount_aed"], "step": "collect", "invoice": number.strip(), "payer": payer})


def commission_received(office: Office, tid: str, by: str, reference: str, *, today: date) -> str:
    g = office.graph()
    roles.check(g, "finance", by)
    t = _inv_task(g, tid, "collect")
    if not reference.strip():
        raise ValueError("Give the bank reference you saw the commission under.")
    office.log.append("task.done", actor=by, agent="inv", deal=t.deal,
                      content={"id": tid, "reason": f"Received, reference {reference.strip()}", "result": "received"})
    c = commission(office.graph(), t.deal)
    if c.get("share"):  # the other agency's share under Form I is ours to pay out
        office.add_task(t.deal, "inv", f'Pay {c["other_agency"]} their share of the commission: AED {c["share"]:,} ({c["share_pct"]}%, Form I)',
                        rests_on=t.props.get("rests_on", []), needs_person=roles.holder(g, "finance"),
                        props={"amount_aed": c["share"], "step": "split", "agency": c["other_agency"]})
    return office.file_document(kind="receipt", title=f'Commission received, invoice {t.props["invoice"]}, reference {reference.strip()}',
                                date=today.isoformat(), by=by, deal=t.deal, amount_aed=t.props["amount_aed"],
                                party=g.nodes[f"deal:{t.deal}"].props.get("customer"))


# ---------- a signed document's payment schedule: the SPA's instalments, the tenancy's cheques ----------

ESCROW = "the project's escrow account"
SCHEDULE = {"offplan": ("instalment", ESCROW, "SPA"), "rent": ("cheque", "the landlord", "tenancy contract")}


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    nd = [31, 29 if (d.year + y) % 4 == 0 and ((d.year + y) % 100 or (d.year + y) % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m]
    return date(d.year + y, m + 1, min(d.day, nd))


def cheques(g: Graph, deal: str, n: int) -> list[dict]:
    """A rental's cheques, equal and evenly spaced from the tenancy start in the deal's terms."""
    rent = (g.facts(deal, "deal_term") or [None])[-1]
    start = desk_rules.terms(g, deal).get("start")
    if not start:
        raise ValueError("Record the tenancy start date from the contract first.")
    if not rent:
        raise ValueError("No yearly rent has been said yet.")
    if n not in (1, 2, 3, 4, 6, 12):
        raise ValueError("A year's rent is paid in 1, 2, 3, 4, 6 or 12 cheques.")
    base, each = rent.props["amount_aed"], rent.props["amount_aed"] // n
    s = date.fromisoformat(start)
    return [{"what": f"Rent cheque {i + 1} of {n}", "amount_aed": each + (base - each * n if i == 0 else 0), "due": add_months(s, i * 12 // n).isoformat()}
            for i in range(n)]


def schedule(office: Office, deal: str, rows: list[dict], by: str, *, document: str) -> list[str]:
    """The transactions officer enters the schedule from the signed document; Finance then expects each payment on its
    day. Each rests on the price (or rent) the client said, so a changed price withdraws the schedule. Amounts can be
    given as a share of the price. They must add up: an off-plan plan to the price less what is already expected from
    the client's own words (the booking amount), a rental's cheques to the yearly rent."""
    g = office.graph()
    roles.check(g, "transactions", by)
    p = desk_rules.path(g, deal)
    if p["id"] not in SCHEDULE:
        raise ValueError("Only an off-plan purchase (the SPA's payment plan) or a rental (its cheques) has a payment schedule.")
    kind, payee, doc = SCHEDULE[p["id"]]
    base = (g.facts(deal, "deal_term") or [None])[-1]
    if not base or not base.props.get("amount_aed"):
        raise ValueError("No price has been said yet, so there is nothing to schedule against.")
    pays = [t for t in g.of("task", deal) if t.props["agent"] == "pay"]
    if any(t.props.get("schedule") and t.status in OPEN | {"done"} for t in pays):
        raise ValueError(f"The {doc}'s schedule is already entered; a changed price withdraws it and it is entered again.")
    if not document.strip():
        raise ValueError(f"Give the {doc}'s reference.")
    if not rows:
        raise ValueError(f"Enter at least one {kind}.")
    out = []
    for i, r in enumerate(rows, 1):
        amount = r.get("amount_aed")
        if amount in (None, "") and r.get("pct") not in (None, ""):
            amount = base.props["amount_aed"] * float(r["pct"]) / 100
        try:
            amount, due = round(float(amount)), date.fromisoformat(str(r.get("due")))
        except (TypeError, ValueError):
            raise ValueError(f"Line {i}: give an amount (or a share of the price) and a due date.") from None
        if amount <= 0:
            raise ValueError(f"Line {i}: the amount is above zero.")
        out.append((str(r.get("what") or "").strip() or f"{kind.capitalize()} {i}", amount, due))
    covered = sum(expected(g, t, date.today()).get("amount_aed") or 0 for t in pays if t.status in OPEN | {"done"}) \
        if p["id"] == "offplan" else 0
    want, total = base.props["amount_aed"] - covered, sum(a for _, a, _ in out)
    if abs(total - want) > len(out):
        also = f" less AED {covered:,} already expected from the client's words" if covered else ""
        raise ValueError(f"The {kind}s add up to AED {total:,}, but the {'yearly rent' if p['id'] == 'rent' else 'price'} the client said "
                         f"({base.id}) is AED {base.props['amount_aed']:,}{also}: AED {want:,}.")
    return [office.add_task(deal, "pay", f"Expect {what}: AED {amount:,} {'into' if payee == ESCROW else 'for'} {payee}", rests_on=[base.id],
                            props={"amount_aed": amount, "due": due.isoformat(), "schedule": kind, "payee": payee, "document": f"{doc} {document.strip()}"})
            for what, amount, due in out]
