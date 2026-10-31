from datetime import date, timedelta

import pytest

from diwan import demo, knowledge as kn
from diwan.events import EventLog
from diwan.office import Office


def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def test_owner_edit_is_a_new_version_and_agents_read_the_new_text():
    o = office()
    k = kn.add(o, "company", "Parking", "Visitor parking is on level B1.", by="layla")["id"]
    kn.edit(o, k, {"text": "Visitor parking is on level B2."}, by="layla", why="moved")
    g = o.graph()
    assert g.nodes[k].props["text"].endswith("B2.") and g.nodes[k].props["version"] == 2
    assert g.nodes[f"{k}~v1"].status == "replaced" and g.nodes[f"{k}~v1"].props["text"].endswith("B1.")
    assert [x.id for x in g.out(k, "replaces")] == [f"{k}~v1"]
    hit = kn.search(g, "where do I park? parking")
    assert hit[0]["id"] == k and "B2" in hit[0]["text"]
    assert [h["what"] for h in kn.history(o, k)] == ["added (typed)", "version 2"]


def test_retire_hides_from_agents_and_restore_brings_it_back():
    o = office()
    k = kn.add(o, "company", "Parking", "Visitor parking is on level B1.", by="layla")["id"]
    with pytest.raises(kn.NotAllowed):
        kn.retire(o, k, by="omar", why="x")
    with pytest.raises(ValueError):
        kn.retire(o, k, by="layla", why=" ")
    kn.retire(o, k, by="layla", why="the building closed the visitor parking")
    g = o.graph()
    assert g.nodes[k].status == "retired" and not kn.search(g, "parking")
    assert kn.search(g, "parking", for_customer=False, include_retired=True)[0]["retired"]["why"].startswith("the building")
    kn.restore(o, k, by="layla")
    assert o.graph().nodes[k].status == "confirmed" and kn.search(o.graph(), "parking")


def test_non_owner_proposes_and_the_owner_decides():
    o = office()
    k = kn.add(o, "company", "Parking", "Level B1.", by="layla")["id"]
    r = kn.edit(o, k, {"text": "Level B3."}, by="omar", why="I parked there")
    assert r["proposal"] == "P1" and o.graph().nodes[k].props["text"] == "Level B1."
    with pytest.raises(kn.NotAllowed):
        kn.decide(o, "P1", accept=True, by="omar")
    kn.decide(o, "P1", accept=True, by="layla")
    assert o.graph().nodes[k].props["text"] == "Level B3."
    kn.edit(o, k, {"text": "Level B4."}, by="omar")
    kn.decide(o, "P2", accept=False, by="layla", why="wrong")
    assert o.graph().nodes[k].props["text"] == "Level B3." and o.graph().nodes["P2"].status == "rejected"


def test_a_brokers_price_change_waits_then_agents_quote_the_new_price():
    o = office()
    r = kn.edit(o, "listing:MC-1204", {"price_aed": 2_400_000}, by="omar", why="seller dropped")
    assert "proposal" in r
    old = o.graph().nodes["listing:MC-1204"].props["price_aed"]
    assert old != 2_400_000
    kn.decide(o, r["proposal"], accept=True, by="layla")
    g = o.graph()
    assert g.nodes["listing:MC-1204"].props["price_aed"] == 2_400_000 and "2,400,000" in g.record("listing:MC-1204")
    assert g.nodes["listing:MC-1204~v1"].props["price_aed"] == old


def test_customer_search_skips_internal_proposed_expired_and_unpermitted():
    o = office()
    kn.add(o, "company", "Commission split", "Brokers keep 50% of commission.", by="layla", audience="internal")
    kn.add(o, "company", "Commission discount", "We give 1% commission to friends.", by="omar")  # proposed
    kn.add(o, "project", "Harbour offer", "Commission waived on Harbour units.", by="layla",
           valid_until=(date.today() - timedelta(days=1)).isoformat())
    o.add_listing(ref="NP-1", title="No permit flat", community="Dubai Marina", type="apartment", beds=2, price_aed=1, permit=None)
    g = o.graph()
    assert {h["title"] for h in kn.search(g, "commission")} == {"Buyer fees"}
    assert {h["title"] for h in kn.search(g, "commission", for_customer=False)} >= {"Commission split", "Commission discount", "Harbour offer"}
    assert "listing:NP-1" not in {h["id"] for h in kn.search(g, "2 bed in Dubai Marina")}
    assert kn.search(g, "do you sell yachts") == []


def test_listing_search_by_beds_area_budget_and_ref():
    o = office()
    g = o.graph()
    assert kn.search(g, "2 bed in Dubai Marina")[0]["id"] == "listing:MC-1204"
    assert all(h["listing"]["beds"] == 1 for h in kn.search(g, "1 bedroom apartment") if "listing" in h)
    assert not [h for h in kn.search(g, "4 bed villa under 100k") if "listing" in h]
    assert kn.search(g, "MC-1204", for_customer=False)[0]["id"] == "listing:MC-1204"


def test_stale_by_review_date_and_reconfirm():
    o = office()
    k = kn.add(o, "area", "Dubai Marina", "Metro: DMCC and Sobha Realty stations.", by="maya",
               review_by=(date.today() - timedelta(days=1)).isoformat())["id"]
    g = o.graph()
    assert kn.stale(g.nodes[k]) and [x.id for x in kn.area_of(g, g.nodes[k])] == ["listing:MC-1204"]
    assert [x.id for x in kn.area_of(g, g.nodes["listing:MC-1204"])] == [k]
    kn.reconfirm(o, k, by="maya")
    assert not kn.stale(o.graph().nodes[k]) and o.graph().nodes[k].props["review_by"] == (date.today() + timedelta(days=90)).isoformat()


def test_broker_reply_becomes_a_proposed_answer_and_usage_counts_citations():
    o = office()
    r = kn.propose_answer(o, "Do you allow pets?", "Most Marina towers allow cats and small dogs.", by="omar", chat="+971500000001")
    assert r["status"] == "proposed" and o.graph().nodes[r["id"]].props["source"] == "chat:+971500000001"
    o.log.append("chat.received", actor="customer:+9715", content={"chat": "+9715", "text": "hours?"})
    o.log.append("chat.sent", actor="rania", content={"chat": "+9715", "text": "10 to 7", "refs": ["K1"]})
    u = kn.usage(o.graph())
    assert u["K1"]["week"] == 1 and u["K1"]["last_chat"] == "+9715"
