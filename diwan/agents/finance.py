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
    """What the Payment tracker shows for one expectation: the promise, the day, and whether it is late."""
    promise = next((g.nodes[f] for f in task.props.get("rests_on", []) if f in g.nodes and g.nodes[f].props.get("kind") == "payment_promise"), None)
    if not promise:  # worked out from the rules (a rental's deposit), not promised in words: no day was said
        return {"amount_aed": task.props.get("amount_aed"), "due": None, "due_words": None, "overdue": False} if task.props.get("amount_aed") else {}
    said = datetime.fromisoformat(promise.at).astimezone(DUBAI).date()
    due = due_date(promise.props.get("due"), said)
    return {"amount_aed": promise.props.get("amount_aed"), "due": due.isoformat() if due else None, "due_words": promise.props.get("due"),
            "overdue": bool(due and due < today and task.status in OPEN)}


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
    office.log.append("task.done", actor=by, agent="pay", deal=t.deal,
                      content={"id": tid, "reason": f"Received, reference {reference.strip()}", "result": "received"})
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
    if any(a.props["action"].endswith(f"({tid})") and a.status in ("given", "executed") for a in g.of("approval", t.deal)):
        raise ValueError(f"The release of {tid} is already approved.")
    action = t.props["action"].replace("Expect ", "Release ") + f" to the seller's escrow ({tid})"
    return office.approve(t.deal, by, action, t.props.get("rests_on", []))


# ---------- commission: worked out from the price the client said and the owner's rate, invoiced, collected ----------

def commission(g: Graph, deal: str) -> dict:
    """Our commission on a deal, never estimated: the latest price the client said x the path's rate + VAT, owed by
    whoever the owner's settings say pays it. Says what is missing instead of guessing."""
    p, r = desk_rules.path(g, deal), desk_rules.rules(g)
    price = (g.facts(deal, "deal_term") or [None])[-1]
    out = {"path": p["id"], "pct": p["commission_pct"], "vat_pct": r["vat_pct"], "payer": p["commission_from"],
           "base_label": "Yearly rent" if p["id"] == "rent" else "Price"}
    if not price or not price.props.get("amount_aed"):
        return out | {"missing": "No price has been said yet, so there is nothing to work it out from."}
    base = price.props["amount_aed"]
    amount = round(base * p["commission_pct"] / 100)
    vat = round(amount * r["vat_pct"] / 100)
    return out | {"base": base, "fact": price.id, "quote": price.props["quote"], "amount": amount, "vat": vat, "total": amount + vat}


def draft_invoice(office: Office, deal: str, by: str) -> str:
    """The invoice is a draft whose lines rest on the price fact: if the client changes the price, Review sends it back."""
    g = office.graph()
    roles.check(g, "finance", by)
    c = commission(g, deal)
    if c.get("missing"):
        raise ValueError(c["missing"])
    if any(d.props["kind"] == "commission invoice" and d.status != "sent_back" for d in g.of("draft", deal)):
        raise ValueError("This deal already has a commission invoice; it is redrafted only if it is sent back.")
    slides = [{"n": 1, "text": f'{c["base_label"]} AED {c["base"]:,}, said: "{c["quote"]}"', "facts": [c["fact"]]},
              {"n": 2, "text": f'Commission {c["pct"]}%: AED {c["amount"]:,}', "facts": [c["fact"]]},
              {"n": 3, "text": f'VAT {c["vat_pct"]}%: AED {c["vat"]:,}', "facts": [c["fact"]]},
              {"n": 4, "text": f'Total due from the {c["payer"]}: AED {c["total"]:,}', "facts": [c["fact"]]}]
    did = office.make_draft(deal, "commission invoice", slides, by="inv")
    office.add_task(deal, "inv", f'Send commission invoice {did} to the {c["payer"]}: AED {c["total"]:,}', rests_on=[c["fact"]],
                    needs_person=roles.holder(g, "finance"), props={"draft": did, "amount_aed": c["total"], "step": "send"})
    return did


def _inv_task(g: Graph, tid: str, step: str) -> Node:
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "inv" or t.props.get("step") != step:
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}" + (f": {t.props['reason']}" if t.props.get("reason") else "."))
    return t


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
                           props={"draft": t.props["draft"], "amount_aed": t.props["amount_aed"], "step": "collect", "invoice": number.strip()})


def commission_received(office: Office, tid: str, by: str, reference: str, *, today: date) -> str:
    g = office.graph()
    roles.check(g, "finance", by)
    t = _inv_task(g, tid, "collect")
    if not reference.strip():
        raise ValueError("Give the bank reference you saw the commission under.")
    office.log.append("task.done", actor=by, agent="inv", deal=t.deal,
                      content={"id": tid, "reason": f"Received, reference {reference.strip()}", "result": "received"})
    return office.file_document(kind="receipt", title=f'Commission received, invoice {t.props["invoice"]}, reference {reference.strip()}',
                                date=today.isoformat(), by=by, deal=t.deal, amount_aed=t.props["amount_aed"],
                                party=g.nodes[f"deal:{t.deal}"].props.get("customer"))
