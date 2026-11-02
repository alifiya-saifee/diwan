"""Finance: what money is expected, from whom, resting on which words. An expectation is withdrawn when the words it
rests on are replaced; nothing here moves money. No bank is connected, so a person marks what they saw arrive: amount, day,
method, reference, payer and an optional proof. A proof that disagrees is flagged before saving, part payments keep the
balance open, a mark can be undone with a reason and never deleted, and cash at the limit or a third-party payer goes to
Compliance before any receipt.
"""
from __future__ import annotations

import secrets
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
                                  content={"to": g.nodes[f"deal:{deal}"].props["broker"], "refs": [p.id], "text": f'Who pays this: "{p.props["quote"]}"?'})
            continue
        who = payer.props["payer"]
        office.add_task(deal, "pay", f"Expect AED {p.props['amount_aed']:,} by {p.props.get('method') or 'a method not yet stated'} from {who}",
                        rests_on=rests, caused_by=cause)
        g = office.graph()
    expect_deposit(office, deal, cause)


def expect_deposit(office: Office, deal: str, cause: int | None = None) -> None:
    """A converted ready sale always has a deposit to expect, even if the client never said one: the owner's percentage of the
    agreed price. Without it Finance has nothing to mark and the gate could never pass. It rests on the price, so a changed price
    makes it again. Words the client said about a deposit take its place."""
    g = office.graph()
    if not g.settings.get(f"deal:{deal}", {}).get("agreed"):
        return
    p = desk_rules.path(g, deal)
    price = (g.facts(deal, "deal_term") or [None])[-1]
    if p["id"] != "ready" or not price or not price.props.get("amount_aed") or g.facts(deal, "payment_promise"):
        return
    if any(t.props["agent"] == "pay" and t.status in OPEN | {"done"} for t in g.of("task", deal)):
        return
    pct, d = p["deposit_pct"], g.nodes[f"deal:{deal}"].props
    amount = round(price.props["amount_aed"] * pct / 100)
    office.add_task(deal, "pay", f"Expect the deposit AED {amount:,} ({pct}% of the agreed price) from {d['customer']}", rests_on=[price.id], caused_by=cause,
                    props={"amount_aed": amount, "deposit": True})


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
    if (day := next((i for i, d in enumerate(DAYS) if d in w), None)) is not None:
        return said + timedelta(days=(day - said.weekday() - 1) % 7 + 1)
    return None


def expected(g: Graph, task: Node, today: date) -> dict:
    """What the Payment tracker shows for one expectation: the promise, the day, and whether it is late. `kind` is what
    the money is: a payment the client promised, a security deposit, an SPA instalment or a rent cheque."""
    if task.props.get("due"):  # from a signed document's schedule (the SPA's payment plan, the tenancy's cheques)
        return {"amount_aed": task.props.get("amount_aed"), "due": task.props["due"], "due_words": None, "kind": task.props.get("schedule"), "paid": paid(task), "payments": task.props.get("payments", []),
                "from": task.props.get("document"), "payee": task.props.get("payee"), "overdue": task.props["due"] < today.isoformat() and task.status in OPEN}
    promise = next((g.nodes[f] for f in task.props.get("rests_on", []) if f in g.nodes and g.nodes[f].props.get("kind") == "payment_promise"), None)
    if not promise:  # worked out from the rules (a rental's deposit), not promised in words: no day was said
        return {"amount_aed": task.props.get("amount_aed"), "due": None, "due_words": None, "kind": "deposit" if task.props.get("deposit") else "security deposit", "overdue": False, "paid": paid(task), "payments": task.props.get("payments", [])} if task.props.get("amount_aed") else {}
    said = datetime.fromisoformat(promise.at).astimezone(DUBAI).date()
    due = due_date(promise.props.get("due"), said)
    return {"amount_aed": promise.props.get("amount_aed"), "due": due.isoformat() if due else None, "due_words": promise.props.get("due"),
            "kind": "promised payment", "overdue": bool(due and due < today and task.status in OPEN), "paid": paid(task), "payments": task.props.get("payments", [])}


METHODS = ("transfer", "cheque", "manager's cheque", "cash", "card", "crypto")


class ProofMismatch(ValueError):
    """The proof doesn't say what was typed: shown to the person before anything is saved."""


def paid(t: Node) -> int:
    return sum(p["amount"] for p in t.props.get("payments", []))


def settled(t: Node) -> bool:
    """Received, and with no payment still waiting on Compliance."""
    return t.props.get("result") == "received" and not any(p.get("held") for p in t.props.get("payments", []))


def _receipt(office: Office, t: Node, p: dict, by: str, today: date) -> str:
    g = office.graph()
    d = g.nodes[f"deal:{t.deal}"].props
    return office.file_document(kind="receipt", title=f"{t.props['action'].replace('Expect ', 'Received ')}, AED {p['amount']:,} by {p['method']}, reference {p['reference']}",
                                date=today.isoformat(), by=by, deal=t.deal, amount_aed=p["amount"], party=p.get("payer") or d["customer"], text=f"payment:{p['id']}")


def _tell_received(office: Office, deal: str, amount: int) -> None:
    from diwan import client_msgs
    g = office.graph()
    client_msgs.tell(office, deal, f"We've received AED {amount:,} for {g.nodes[f'deal:{deal}'].props['property']}. Thank you.", what=f"confirm AED {amount:,} was received")


def mark_received(office: Office, tid: str, by: str, reference: str, *, today: date, amount=None, method: str = "transfer", on: str = "",
                  payer: str = "", proof_amount=None, confirm: bool = False) -> dict:
    """A person saw the money arrive; the agent never marks money received. The receipt is filed with Records and the client
    told, unless the pattern needs the compliance officer first; then both wait for her."""
    from diwan.agents import compliance
    g = office.graph()
    roles.check(g, "finance", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "pay":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if not reference.strip():
        raise ValueError("Give the bank or receipt reference you saw the money under.")
    if any(c.deal == t.deal for c in g.of("chat")) and not compliance.state(g, t.deal)["ok"]:
        raise ValueError("Compliance hasn't cleared this deal yet, so no deposit is taken.")
    e = expected(g, t, today)
    want = (e.get("amount_aed") or 0) - paid(t)
    try:
        amount = round(float(amount)) if amount not in (None, "") else want
    except (TypeError, ValueError):
        raise ValueError("Enter the amount received in dirhams.") from None
    if amount <= 0:
        raise ValueError("Enter the amount received in dirhams.")
    if method not in METHODS:
        raise ValueError(f"The method is one of {', '.join(METHODS)}.")
    day = (on or today.isoformat()).strip()
    try:
        if date.fromisoformat(day) > today:
            raise ValueError("Money can't be marked received on a day still to come.")
    except TypeError:
        raise ValueError("Give the day it arrived.") from None
    who = payer.strip() or next((g.nodes[f].props["payer"] for f in t.props.get("rests_on", []) if f in g.nodes and g.nodes[f].props.get("kind") == "payer"), "")
    if want > 0 and amount > want and not confirm:
        raise ProofMismatch(f"That is AED {amount - want:,} more than the AED {want:,} still expected. Check it, or save it anyway.")
    if proof_amount not in (None, ""):
        seen = round(float(proof_amount))
        if seen != amount and not confirm:
            office.log.append("payment.flagged", actor="pay", agent="pay", deal=t.deal, content={"task": tid, "why": f"Proof shows AED {seen:,}; entered AED {amount:,}"})
            raise ProofMismatch(f"Proof shows AED {seen:,}; you entered AED {amount:,}. Check it, or save it anyway.")
    parts = 1 + len(t.props.get("payments", []))
    flags = compliance.payment_pattern(g, t.deal, {"method": method, "amount": amount, "payer": who, "parts": parts})
    held = bool(flags) and t.props.get("payee") != ESCROW
    pay = {"task": tid, "id": secrets.token_hex(4), "amount": amount, "method": method, "on": day, "reference": reference.strip(), "payer": who, "proof_amount": proof_amount, "held": held}
    ev = office.log.append("payment.marked_received", actor=by, agent="pay", deal=t.deal, content=pay)
    full = amount + paid(t) >= want + paid(t) if want > 0 else True
    if full:
        said = f"Paid into {t.props['payee']}, receipt {reference.strip()}" if t.props.get("payee") == ESCROW else f"Received, reference {reference.strip()}"
        office.log.append("task.done", actor=by, agent="pay", deal=t.deal, content={"id": tid, "reason": said, "result": "received"})
    if held:
        office.log.append("payment.flagged", actor="pay", agent="pay", deal=t.deal, caused_by=ev["id"], content={"task": tid, "payment": pay["id"], "why": "; ".join(flags)})
        office.log.append("check.raised", actor="comp", agent="comp", deal=t.deal, caused_by=ev["id"],
                          content={"who": roles.holder(g, "compliance"), "title": "A payment to look at before the receipt", "refs": [], "task": tid, "payment": pay["id"],
                                   "text": f"AED {amount:,} marked received, reference {reference.strip()}: {'; '.join(flags)}. The receipt waits for you."})
        compliance.cash_rules(office, t.deal, ev["id"])
        return {"document": None, "held": True, "flags": flags, "balance": max(want - amount, 0)}
    doc = _receipt(office, office.graph().nodes[tid], pay, by, today)
    _tell_received(office, t.deal, amount)
    return {"document": doc, "held": False, "flags": [], "balance": max(want - amount, 0)}


def release_held(office: Office, card: Node, by: str, today: date) -> str | None:
    """The compliance officer looked at the payment: its receipt is filed and the client told."""
    t = office.graph().nodes.get(card.props.get("task"))
    if not t:
        return None
    p = next((x for x in t.props.get("payments", []) if x["id"] == card.props.get("payment")), None)
    if not p:
        return None
    office.log.append("payment.undone", actor=by, agent="pay", deal=t.deal, content={"task": t.id, "payment": p["id"], "why": "released", "released": True})
    office.log.append("payment.marked_received", actor=by, agent="pay", deal=t.deal, content={k: v for k, v in p.items() if k not in ("at", "by")} | {"held": False, "released_by": by})
    doc = _receipt(office, office.graph().nodes[t.id], p, by, today)
    _tell_received(office, t.deal, p["amount"])
    return doc


def undo_received(office: Office, tid: str, by: str, payment: str, why: str) -> None:
    """A mistaken mark is undone with a reason, never deleted: the log keeps both, the receipt is voided, the payment is open again."""
    g = office.graph()
    roles.check(g, "finance", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("agent") != "pay":
        raise KeyError(tid)
    p = next((x for x in t.props.get("payments", []) if x["id"] == payment), None)
    if not p:
        raise KeyError(payment)
    if not why.strip():
        raise ValueError("Say why this mark is being undone.")
    if any(a.props["action"].endswith(f"({tid})") and a.status in ("given", "executed") for a in g.of("approval", t.deal)):
        raise ValueError("This money's release is approved: it can't be undone here.")
    office.log.append("payment.undone", actor=by, agent="pay", deal=t.deal, content={"task": tid, "payment": payment, "why": why.strip()})
    if t.status == "done":
        office.log.append("task.reopened", actor=by, agent="pay", deal=t.deal, content={"id": tid, "reason": f"Undone: {why.strip()}"})
    for d in g.of("document", t.deal):
        if d.props.get("text") == f"payment:{payment}" and d.status != "voided":
            office.log.append("document.voided", actor=by, agent="archivist", deal=t.deal, content={"id": d.id, "reason": why.strip()})


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
    if not settled(t):
        raise ValueError("Compliance is still looking at this payment.")
    from diwan.agents import compliance
    compliance.require(g, t.deal, "Releasing money")
    if t.props.get("payee") == ESCROW:
        raise ValueError("An instalment is paid straight into the project's escrow; we never hold it, so there is nothing to release.")
    if any(a.props["action"].endswith(f"({tid})") and a.status in ("given", "executed") for a in g.of("approval", t.deal)):
        raise ValueError(f"The release of {tid} is already approved.")
    action = t.props["action"].replace("Expect ", "Release ") + f" to {t.props.get('payee') or 'the seller' + chr(39) + 's escrow'} ({tid})"
    return office.approve(t.deal, by, action, t.props.get("rests_on", []))


# ---------- commission: worked out from the price the client said and the owner's rate, invoiced, collected ----------

def paid_in(g: Graph, deal: str) -> int:
    """What the buyer has paid on the deal so far, as marked received by a person."""
    return sum(paid(t) or (t.props.get("amount_aed") or expected(g, t, date.today()).get("amount_aed") or 0 if t.props.get("result") == "received" else 0)
               for t in g.of("task", deal) if t.props["agent"] == "pay")


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
    out["fees"] = ([{"what": f"DLD fee {p['dld_fee_pct']}%", "aed": round(base * p["dld_fee_pct"] / 100), "payer": "buyer"}] if p.get("dld_fee_pct") else []) + \
        [{"what": w, "aed": a, "payer": who} for w, a, who in p.get("fees") or []]  # the owner's usual fees, each with who pays it
    if dev:
        paid = paid_in(g, deal)
        out["trigger"] = {"pct": dev["payable_after_pct"], "paid": paid, "paid_pct": round(paid * 100 / base, 1),
                          "met": paid * 100 >= dev["payable_after_pct"] * base}
    return out


def draft_invoice(office: Office, deal: str, by: str) -> str:
    """The invoice is a draft whose lines rest on the price fact: if the client changes the price, Review sends it back."""
    g = office.graph()
    roles.check(g, "finance", by)
    return _draft(office, deal)


def auto_invoice(office: Office, deal: str, trigger: str) -> str | None:
    """The owner's trigger came: the draft is made for a person to approve. Quietly nothing if it can't be yet."""
    g = office.graph()
    if desk_rules.path(g, deal).get("invoice_trigger") != trigger:
        return None
    try:
        return _draft(office, deal)
    except ValueError:
        return None


def _draft(office: Office, deal: str) -> str:
    g = office.graph()
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


def _inv_task(g: Graph, tid: str, *steps: str) -> Node:
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "inv" or t.props.get("step") not in steps:
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}" + (f": {t.props['reason']}" if t.props.get("reason") else "."))
    return t


def split_paid(office: Office, tid: str, by: str, reference: str) -> None:
    g = office.graph()
    roles.check(g, "finance", by)
    t = _inv_task(g, tid, "split", "payout")
    if not reference.strip():
        raise ValueError("Give the bank reference of the payment.")
    office.log.append("task.done", actor=by, agent="inv", deal=t.deal, content={"id": tid, "reason": f"Paid, reference {reference.strip()}", "result": "paid"})


def invoice_sent(office: Office, tid: str, by: str, number: str = "", *, today: date | None = None) -> str:
    """Finance sends the invoice: under Diwan's next number in the owner's sequence, or under the number their own
    accounting system gave it."""
    from diwan import invoices
    g = office.graph()
    roles.check(g, "finance", by)
    t = _inv_task(g, tid, "send")
    if g.stale(tid) or g.nodes[t.props["draft"]].status == "sent_back":
        raise ValueError(f"{t.props['draft']} rests on a price the client replaced; draft the invoice again.")
    number = number.strip() or invoices.next_number(g, today or date.today())
    if any(x.props.get("agent") == "inv" and x.props.get("invoice") == number for x in g.of("task")):
        raise ValueError(f"Invoice {number} is already used; every invoice has its own number.")
    office.log.append("task.done", actor=by, agent="inv", deal=t.deal, content={"id": tid, "reason": f"Sent as invoice {number.strip()}", "result": "sent"})
    payer = t.props["action"].split(" to the ")[1].split(":")[0]
    due = (today or date.today()) + timedelta(days=desk_rules.rules(g)["invoice_due_days"])
    return office.add_task(t.deal, "inv", f'Collect commission AED {t.props["amount_aed"]:,} from the {payer} (invoice {number.strip()})',
                           rests_on=t.props.get("rests_on", []), needs_person=roles.holder(g, "finance"),
                           props={"draft": t.props["draft"], "amount_aed": t.props["amount_aed"], "step": "collect", "invoice": number.strip(), "payer": payer, "due": due.isoformat()})


def commission_received(office: Office, tid: str, by: str, reference: str, *, today: date, amount=None) -> str:
    """Part of the commission keeps the invoice open with its balance; the rest of the deal's money follows when it is all in."""
    g = office.graph()
    roles.check(g, "finance", by)
    t = _inv_task(g, tid, "collect")
    if not reference.strip():
        raise ValueError("Give the bank reference you saw the commission under.")
    left = t.props["amount_aed"] - paid(t)
    try:
        amount = round(float(amount)) if amount not in (None, "") else left
    except (TypeError, ValueError):
        raise ValueError("Enter the amount received in dirhams.") from None
    if not 0 < amount <= left:
        raise ValueError(f"Enter an amount up to the AED {left:,} still due.")
    pay = {"task": tid, "id": secrets.token_hex(4), "amount": amount, "method": "transfer", "on": today.isoformat(), "reference": reference.strip(), "payer": t.props.get("payer"), "held": False}
    office.log.append("payment.marked_received", actor=by, agent="inv", deal=t.deal, content=pay)
    if amount < left:
        return office.file_document(kind="receipt", title=f'Part of commission received, invoice {t.props["invoice"]}, reference {reference.strip()}',
                                    date=today.isoformat(), by=by, deal=t.deal, amount_aed=amount, party=g.nodes[f"deal:{t.deal}"].props.get("customer"), text=f"payment:{pay['id']}")
    office.log.append("task.done", actor=by, agent="inv", deal=t.deal,
                      content={"id": tid, "reason": f"Received, reference {reference.strip()}", "result": "received"})
    c = commission(office.graph(), t.deal)
    d = g.nodes[f"deal:{t.deal}"].props
    ours, share = c.get("ours", c.get("amount") or 0), desk_rules.rules(g)["broker_share_pct"]
    if d.get("broker") and ours:
        from diwan.people import name
        pct = share
        office.add_task(t.deal, "inv", f"Pay {name(d['broker'])} their commission: AED {round(ours * pct / 100):,} ({pct}% of what we keep)",
                        rests_on=t.props.get("rests_on", []), needs_person=roles.holder(g, "finance"),
                        props={"amount_aed": round(ours * pct / 100), "step": "payout", "broker": d["broker"]})
    if c.get("share"):  # the other agency's share under Form I is ours to pay out
        office.add_task(t.deal, "inv", f'Pay {c["other_agency"]} their share of the commission: AED {c["share"]:,} ({c["share_pct"]}%, Form I)',
                        rests_on=t.props.get("rests_on", []), needs_person=roles.holder(g, "finance"),
                        props={"amount_aed": c["share"], "step": "split", "agency": c["other_agency"]})
    return office.file_document(kind="receipt", title=f'Commission received, invoice {t.props["invoice"]}, reference {reference.strip()}',
                                date=today.isoformat(), by=by, deal=t.deal, amount_aed=t.props["amount_aed"],
                                party=g.nodes[f"deal:{t.deal}"].props.get("customer"))


def write_off(office: Office, tid: str, by: str, why: str) -> None:
    """Giving up on an invoice is the owner's call, with the reason."""
    g = office.graph()
    if not roles.is_owner(by):
        raise PermissionError("Only the owner writes off an invoice.")
    t = _inv_task(g, tid, "collect")
    if not why.strip():
        raise ValueError("Say why it is written off.")
    office.log.append("invoice.written_off", actor=by, agent="inv", deal=t.deal, content={"id": tid, "reason": why.strip(), "amount_aed": t.props["amount_aed"] - paid(t)})


def invoice_status(t: Node, today: date) -> str:
    if t.props.get("step") == "send":
        return {"withdrawn": "sent back", "done": "sent"}.get(t.status, "draft")
    if t.props.get("result") == "written off":
        return "written off"
    if t.props.get("result") == "received":
        return "received"
    if t.status == "withdrawn":
        return "sent back"
    if paid(t):
        return "part paid"
    due = t.props.get("due")
    return "overdue" if due and due < today.isoformat() else "due" if due == today.isoformat() else "sent"


def sweep(office: Office, now: datetime) -> int:
    """Reminders on the owner's schedule: overdue invoices after their due date, instalments and rent cheques before theirs.
    Each goes once. A client hears it politely; a developer's overdue commission goes to the owner."""
    from diwan import client_msgs
    from diwan.people import PEOPLE
    g, today = office.graph(), now.date()
    rules = desk_rules.rules(g)
    sent = {(e["content"].get("task"), e["content"].get("day")) for e in office.log.list() if e["type"] == "payment.reminded"}
    owner = next((p for p, v in PEOPLE.items() if v.get("role") == "Owner"), None)
    n = 0
    for t in g.of("task"):
        if t.status not in OPEN or not t.props.get("due") or not t.deal or f"deal:{t.deal}" not in g.nodes:
            continue
        due, d = date.fromisoformat(t.props["due"]), g.nodes[f"deal:{t.deal}"].props
        if t.props.get("agent") == "inv" and t.props.get("step") == "collect":
            for day in [x for x in rules["invoice_reminder_days"] if (today - due).days >= x and (t.id, x) not in sent][:1]:
                office.log.append("payment.reminded", actor="pay", agent="pay", deal=t.deal, content={"task": t.id, "day": day, "invoice": t.props.get("invoice")})
                left = t.props["amount_aed"] - paid(t)
                if t.props.get("payer") in ("buyer", "tenant"):
                    client_msgs.tell(office, t.deal, f"A reminder that invoice {t.props.get('invoice')} for AED {left:,} was due on {due.isoformat()}. Thank you.", what=f"remind them about invoice {t.props.get('invoice')}", now=now)
                else:
                    office.log.append("question.asked", actor="pay", agent="pay", deal=t.deal, content={"to": owner, "refs": [], "kind": "overdue",
                                      "text": f"Commission invoice {t.props.get('invoice')} for AED {left:,} from the {t.props.get('payer')} on {d['property']} is {(today - due).days} days overdue."})
                n += 1
        elif t.props.get("agent") == "pay" and t.props.get("schedule"):
            for day in [x for x in rules["payment_reminder_days"] if 0 <= (due - today).days <= x and (t.id, x) not in sent][:1]:
                office.log.append("payment.reminded", actor="pay", agent="pay", deal=t.deal, content={"task": t.id, "day": day})
                client_msgs.tell(office, t.deal, f"A reminder: your {t.props['schedule']} of AED {t.props['amount_aed']:,} is due on {due.isoformat()}.", what=f"remind them about the {t.props['schedule']} due {due.isoformat()}", now=now)
                n += 1
    return n


def room(g: Graph, today: date) -> dict:
    """The Finance room: invoices by status, what is expected, commissions to pay out, cash and flags. Counted from the record."""
    from diwan.people import name
    month, soon = today.isoformat()[:7], (today + timedelta(days=30)).isoformat()
    invoices, expected_rows, payouts, flags = [], [], [], []
    cash_in, by_broker = 0, {}
    outstanding, next30 = 0, 0
    for n in g.deals():
        deal, d = n.deal, n.props
        base = {"deal": deal, "customer": d.get("customer"), "property": d.get("property")}
        for t in g.of("task", deal):
            a = t.props["agent"]
            for p in t.props.get("payments", []):
                if p.get("on", "")[:7] == month and a in ("pay", "inv") and not p.get("held"):
                    cash_in += p["amount"]
            if a == "inv" and t.props.get("step") in ("send", "collect") and not (t.props.get("step") == "send" and t.status == "done"):
                st = invoice_status(t, today)
                left = (t.props.get("amount_aed") or 0) - paid(t)
                invoices.append(base | {"id": t.id, "number": t.props.get("invoice"), "status": st, "amount": t.props.get("amount_aed"), "left": left, "due": t.props.get("due"), "payer": t.props.get("payer")})
                if st in ("sent", "due", "overdue", "part paid"):
                    outstanding += left
                    if (t.props.get("due") or "9") <= soon:
                        next30 += left
                    b = by_broker.setdefault(d.get("broker"), {"name": name(d.get("broker")), "outstanding": 0, "collected": 0})
                    b["outstanding"] += left
                if st == "received":
                    by_broker.setdefault(d.get("broker"), {"name": name(d.get("broker")), "outstanding": 0, "collected": 0})["collected"] += t.props.get("amount_aed") or 0
            if a == "pay" and t.status in OPEN:
                e = expected(g, t, today)
                left = (e.get("amount_aed") or 0) - paid(t)
                outstanding += left
                if e.get("due") and e["due"] <= soon:
                    next30 += left
                facts = [g.nodes[f].props["quote"] for f in t.props.get("rests_on", []) if f in g.nodes and g.nodes[f].type == "fact"]
                expected_rows.append(base | {"id": t.id, "action": t.props["action"], "amount": e.get("amount_aed"), "left": left, "due": e.get("due"), "overdue": e.get("overdue"), "quote": facts[0] if facts else None, "paid": paid(t)})
            if a == "inv" and t.props.get("step") in ("split", "payout") and t.status in OPEN:
                payouts.append(base | {"id": t.id, "action": t.props["action"], "amount": t.props.get("amount_aed"), "kind": t.props["step"]})
        for c in g.of("check", deal, "open"):
            if c.props.get("payment"):
                flags.append(base | {"id": c.id, "text": c.props["text"], "at": c.at})
    invoices.sort(key=lambda x: (x["status"] != "overdue", x.get("due") or "9"))
    expected_rows.sort(key=lambda x: (not x["overdue"], x["due"] or "9"))
    return {"cash_month": cash_in, "outstanding": outstanding, "next30": next30, "invoices": invoices, "expected": expected_rows, "payouts": payouts, "flags": flags,
            "brokers": sorted(by_broker.values(), key=lambda b: -(b["outstanding"] + b["collected"]))}


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
