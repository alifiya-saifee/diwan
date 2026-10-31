"""A fictional office to work against until the Scribe records live meetings: two deals, Karim's payment story, an
approval and a deck that rest on it. `correction()` is the moment Karim takes back what he said; everything after that
is the engine's own work, not part of the script.
"""
from __future__ import annotations

from diwan.office import Office


def company(office: Office) -> None:
    """What a brokerage tells the office once: listings (sample permit numbers) and the few facts customers ask about."""
    office.add_listing(ref="MC-1204", title="Unit 1204, Marina Crest", community="Dubai Marina", type="apartment", beds=2,
                       price_aed=2_600_000, permit="SAMPLE-71204", features=["sea view", "balcony", "2 parking"], agent="omar")
    office.add_listing(ref="JVC-88", title="Villa 88", community="Jumeirah Village Circle", type="villa", beds=4,
                       price_aed=1_900_000, permit="SAMPLE-60088", features=["garden", "maid's room"], agent="omar")
    office.add_listing(ref="BB-305", title="Apartment 305, Bay Square", community="Business Bay", type="apartment", beds=1,
                       price_aed=1_150_000, permit="SAMPLE-30305", features=["canal view"], agent="hamza")
    office.add_listing(ref="DT-2210", title="Apartment 2210, Burj Vista", community="Downtown Dubai", type="apartment", beds=1,
                       price_aed=1_450_000, permit=None, agent="nadia")  # no permit yet: kept, never advertised
    office.add_knowledge("hours", "Office hours", "We're open Monday to Saturday, 10am to 7pm. Viewings run in the same hours.", by="layla")
    office.add_knowledge("policy", "Viewings", "Viewings are with one of our brokers. Please bring a photo ID for the building lobby.", by="layla")
    office.add_knowledge("fees", "Buyer fees", "Our buyer commission is 2% of the price plus VAT. The Dubai Land Department transfer fee is 4%.", by="layla")
    office.add_knowledge("company", "About us", "Diwan Realty is a Dubai brokerage for Marina, JVC, Business Bay and Downtown.", by="layla")


def archive(office: Office) -> None:
    """Four months of a small brokerage's records, all fictional: closed sales and the paperwork around them."""
    for listing, price, comm, broker, day in [
            ("Villa 12, Arabian Ranches", 4_200_000, 84_000, "omar", "2026-07-14"),
            ("Apartment 1702, Marina Promenade", 2_150_000, 43_000, "omar", "2026-08-05"),
            ("Townhouse 7, Town Square", 1_650_000, 33_000, "omar", "2026-08-26"),
            ("Apartment 904, Bay Central", 1_380_000, 27_600, "omar", "2026-09-03"),
            ("Villa 31, JVC District 12", 2_900_000, 58_000, "omar", "2026-09-17"),
            ("Apartment 3105, Burj Crown", 3_570_000, 71_400, "omar", "2026-09-29"),
            ("Apartment 408, Bay Square", 1_120_000, 22_400, "omar", "2026-10-09")]:
        office.close_sale(listing=listing, price_aed=price, commission_aed=comm, broker=broker, date=day)
    for kind, title, day, amount, party in [
            ("invoice", "Office rent, September", "2026-09-01", 25_000, "Bay Square Offices LLC"),
            ("invoice", "Property Finder listings, September", "2026-09-02", 12_000, "Property Finder"),
            ("invoice", "Listing photography, 3 units", "2026-09-11", 3_500, "Lens & Light Studio"),
            ("bill", "DEWA electricity and water, September", "2026-09-20", 2_180, "DEWA"),
            ("contract", "MOU (Form F), Villa 31, JVC District 12", "2026-09-10", 2_900_000, "Buyer and seller"),
            ("receipt", "Deposit received, Apartment 3105, Burj Crown", "2026-09-22", 357_000, "Buyer"),
            ("invoice", "Office rent, October", "2026-10-01", 25_000, "Bay Square Offices LLC"),
            ("invoice", "Property Finder listings, October", "2026-10-02", 12_000, "Property Finder"),
            ("bill", "du internet and phones, October", "2026-10-15", 1_450, "du")]:
        office.file_document(kind=kind, title=title, date=day, amount_aed=amount, party=party)


def catalog(office: Office) -> None:
    """The demo catalog, arriving the way a brokerage's real one does: through its portal feed (diwan/demo_feed.xml:
    fictional units, sample permits, free-licence photos of the area or a similar home). Loaded once."""
    from pathlib import Path

    from diwan import leads
    if "listing:DR-135" not in office.graph().nodes:  # the newest demo listing: an office missing it reads the feed again
        leads.sync_listings(office, (Path(__file__).parent / "demo_feed.xml").read_bytes(), by="demo-feed")


def projects(office: Office) -> None:
    """Two fictional off-plan projects in Knowledge → Projects, and one developer brochure in the archive (the other is
    missing on purpose: the pitch deck asks the broker to get it). Loaded once."""
    from diwan import knowledge
    if any(n.props.get("title") == "Creek Vista Heights" for n in office.graph().of("knowledge")):
        return
    knowledge.add(office, "project", "Creek Vista Heights",
                  "Harbour Lane Developments (fictional). Payment plan: 10% on booking, 50% during construction in 5 instalments, "
                  "40% on handover. Handover Q4 2027. Dubai Land Department fee 4% on booking.", by="layla", valid_until="2027-12-31")
    knowledge.add(office, "project", "Bayline Residences",
                  "Canalside Developers (fictional). Payment plan: 20% on booking, 40% during construction, 40% on handover. "
                  "Handover Q2 2028.", by="layla", valid_until="2028-06-30")
    office.file_document(kind="brochure", title="Creek Vista Heights brochure, floor plans and payment plan", date="2026-09-20",
                         party="Harbour Lane Developments", text="Fictional developer brochure for the demo.")


def kinds(office: Office) -> None:
    """The demo brokerage's deal kinds (its sales desks), as data the owner edits on the Settings page. Loaded once."""
    from diwan import deal_kinds
    if deal_kinds.kinds(office.graph()):
        return
    deal_kinds.save(office, [
        {"id": "off_plan", "name": "Off-plan", "brokers": ["hamza"], "listings": {"offering": "sale", "completion": "off_plan"},
         "serves": [{"type": "buyer", "when": {"field": "ready_or_offplan", "op": "=", "value": "Off-plan"}}]},
        {"id": "ready_sales", "name": "Ready sales", "brokers": ["omar", "nadia"], "listings": {"offering": "sale", "completion": "ready"},
         "serves": [{"type": "buyer"}, {"type": "seller"}]},
        {"id": "leasing", "name": "Leasing", "brokers": ["nadia"], "listings": {"offering": "rent", "completion": ""},
         "serves": [{"type": "tenant"}, {"type": "landlord"}]},
    ], by="layla")


def seed(office: Office) -> None:
    company(office)
    archive(office)
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
    old = [f.id for f in g.facts("marina-1204", "party") + g.facts("marina-1204", "payer")]  # what "forget my brother" takes back
    return office.record_fact("marina-1204", "payer", "Actually, forget my brother. I'll pay it all myself.", "Karim Haddad",
                              payer="Karim Haddad", replaces=old)
