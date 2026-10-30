"""Finance: what money is expected, from whom, resting on which words. An expectation is withdrawn when the words it
rests on are replaced; nothing here moves money.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from diwan import roles
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
    if not promise:
        return {}
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
