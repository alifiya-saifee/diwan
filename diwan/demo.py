"""A fictional office to work against until the Scribe records live meetings: two deals, Karim's payment story, an
approval and a deck that rest on it. `correction()` is the moment Karim takes back what he said; everything after that
is the engine's own work, not part of the script.
"""
from __future__ import annotations

from diwan.office import Office


def company(office: Office) -> None:
    """What a brokerage tells the office once: listings (sample permit numbers) and the few facts customers ask about."""
    office.add_listing(ref="MC-1204", title="Unit 1204, Marina Crest", community="Dubai Marina", type="apartment", beds=2,
                       price_aed=2_600_000, permit="SAMPLE-71204", features=["sea view", "balcony", "2 parking"])
    office.add_listing(ref="JVC-88", title="Villa 88", community="Jumeirah Village Circle", type="villa", beds=4,
                       price_aed=1_900_000, permit="SAMPLE-60088", features=["garden", "maid's room"])
    office.add_listing(ref="BB-305", title="Apartment 305, Bay Square", community="Business Bay", type="apartment", beds=1,
                       price_aed=1_150_000, permit="SAMPLE-30305", features=["canal view"])
    office.add_listing(ref="DT-2210", title="Apartment 2210, Burj Vista", community="Downtown Dubai", type="apartment", beds=1,
                       price_aed=1_450_000, permit=None)  # no permit yet: kept, never advertised
    office.add_knowledge("hours", "Office hours", "We're open Monday to Saturday, 10am to 7pm. Viewings run in the same hours.", by="layla")
    office.add_knowledge("policy", "Viewings", "Viewings are with one of our brokers. Please bring a photo ID for the building lobby.", by="layla")
    office.add_knowledge("fees", "Buyer fees", "Our buyer commission is 2% of the price plus VAT. The Dubai Land Department transfer fee is 4%.", by="layla")
    office.add_knowledge("company", "About us", "Diwan Realty is a Dubai brokerage for Marina, JVC, Business Bay and Downtown.", by="layla")


def seed(office: Office) -> None:
    company(office)
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
