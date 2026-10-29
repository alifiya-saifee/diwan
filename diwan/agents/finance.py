"""Finance: what money is expected, from whom, resting on which words. An expectation is withdrawn when the words it
rests on are replaced; nothing here moves money.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan.graph import OPEN

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
