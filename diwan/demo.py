"""A fictional office to work against until the Scribe records live meetings: two deals, Karim's payment story, an
approval and a deck that rest on it. `correction()` is the moment Karim takes back what he said; everything after that
is the engine's own work, not part of the script.
"""
from __future__ import annotations

from diwan.office import Office


def seed(office: Office) -> None:
    office.open_deal("marina-1204", property="Unit 1204, Marina Crest", customer="Karim Haddad", broker="omar")
    office.open_deal("jvc-88", property="Villa 88, JVC", customer="Sara Malik", broker="omar")
    m = "marina-1204"
    f1 = office.record_fact(m, "deal_term", "We're looking at two point six million for the Marina unit.", "Karim Haddad", amount_aed=2_600_000)
    office.record_fact(m, "party", "My brother Tariq is helping with the deposit.", "Karim Haddad", party="Tariq Haddad", relation="brother")
    f3 = office.record_fact(m, "payer", "Tariq will send the deposit from his account.", "Karim Haddad", payer="Tariq Haddad")
    f4 = office.record_fact(m, "payment_promise", "Two hundred sixty thousand deposit, by bank transfer, next week.", "Karim Haddad",
                            amount_aed=260_000, method="bank transfer", due="next week")
    office.record_fact(m, "income_claim", "I earn about forty-five thousand a month.", "Karim Haddad", monthly_income_aed=45_000)
    office.approve(m, "ahmed", "Accept the AED 260,000 deposit from Tariq Haddad", [f3, f4])
    office.make_draft(m, "deck", [
        {"n": 1, "text": "Unit 1204, Marina Crest: AED 2.6M", "facts": [f1]},
        {"n": 2, "text": "Deposit AED 260,000 by bank transfer, next week", "facts": [f4]},
        {"n": 3, "text": "Deposit paid by Tariq Haddad (brother)", "facts": [f3]},
    ])
    office.record_fact("jvc-88", "deal_term", "One point nine for the villa if the garden is included.", "Sara Malik", amount_aed=1_900_000)


def correction(office: Office) -> str:
    g = office.graph()
    old = next(f.id for f in g.facts("marina-1204", "payer"))
    return office.record_fact("marina-1204", "payer", "Actually, forget my brother. I'll pay it all myself.", "Karim Haddad",
                              payer="Karim Haddad", replaces=old)
