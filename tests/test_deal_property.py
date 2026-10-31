"""Which property a deal is on, and whose it is (docs/deal-desk.md item 17)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from diwan import agency_forms, app as appmod, deal_property, demo, desk_rules, desk_stages
from diwan.events import EventLog
from diwan.office import Office

AGENCY = {"other_agency": "Bayut Homes", "other_orn": "1122", "other_agent": "Sami", "other_brn": "3344", "other_share_pct": 50}


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    o.open_deal("lead-1", property="WhatsApp enquiry", customer="Ali Rahman", broker="omar")
    o.open_deal("lead-2", property="WhatsApp enquiry", customer="Noor Aziz", broker="omar")
    return o


@pytest.fixture
def c(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    return TestClient(appmod.app)


def _developer(office):
    r = desk_rules.rules(office.graph())
    r["developers"] = [{"name": "Emaar", "commission_pct": 4, "payable_after_pct": 20}]
    desk_rules.save(office, r, by="layla")


def _deal(office, deal="lead-1"):
    return office.graph().nodes[f"deal:{deal}"].props


def _status(office, ref):
    return office.graph().nodes[f"listing:{ref}"].status


def _live(office, deal="lead-1"):
    return sorted(f["form"] for f in agency_forms.forms(office.graph(), deal) if f["status"] != "sent_back")


def _convert(c, deal="lead-1", amount=1_900_000, prop=None):
    return c.post(f"/api/desk/deals/{deal}/convert", json={"by": "omar", "amount": amount, "property": prop})


def test_a_placeholder_deal_cant_convert_without_its_property(office, c):
    r = _convert(c)
    assert r.status_code == 400 and "which property" in r.json()["detail"]
    assert not desk_stages.agreed(office.graph(), "lead-1")
    assert _deal(office)["property"] == "WhatsApp enquiry"


def test_picking_our_listing_names_the_deal_compares_the_price_and_reserves_it(office, c):
    r = _convert(c, amount=1_850_000, prop={"source": "listing", "ref": "JVC-88"}).json()
    assert r["listing_aed"] == 1_900_000 and r["waiting"] is None
    assert _deal(office)["property"] == "Villa 88" and office.graph().nodes["property:lead-1"].label == "Villa 88"
    assert agency_forms.our_listing(office.graph(), "lead-1").props["ref"] == "JVC-88"
    assert _status(office, "JVC-88") == "reserved"
    assert _live(office) == ["A", "B"]  # no "other side" question: the answer said it
    assert not [t for t in office.graph().of("task", "lead-1") if t.props.get("step") == "sides" and t.status != "done"]
    assert "Villa 88" in c.get("/api/desk/deals/lead-1").json()["property"]
    fields = dict((label, value) for _, label, value, _ in agency_forms.fields(office.graph(), "lead-1", "B"))
    assert fields["Property"] == "Villa 88" and fields["Listing ref and permit"].startswith("JVC-88")


def test_a_big_discount_waits_for_the_owner_and_the_listing_is_held_only_then(office, c):
    r = _convert(c, amount=1_500_000, prop={"source": "listing", "ref": "JVC-88"}).json()
    assert r["waiting"] and _status(office, "JVC-88") == "available"
    assert "JVC-88" not in str(c.get("/api/desk/deals/lead-2/listings").json())  # another deal can't pick it meanwhile
    task = next(t for t in office.graph().of("task", "lead-1") if t.props.get("step") == "discount")
    desk_stages.decide_discount(office, task.id, "layla", True)
    assert _status(office, "JVC-88") == "reserved" and _deal(office)["stage"] == "Offer accepted"


def test_a_listing_on_another_deal_isnt_offered_and_is_refused(office, c):
    _convert(c, prop={"source": "listing", "ref": "JVC-88"})
    assert "JVC-88" not in str(c.get("/api/desk/deals/lead-2/listings").json())
    r = _convert(c, "lead-2", prop={"source": "listing", "ref": "JVC-88"})
    assert r.status_code == 400 and "reserved" in r.json()["detail"]
    assert _convert(c, "lead-2", prop={"source": "listing", "ref": "NOPE"}).status_code == 400
    assert "Ali" not in str(c.get("/api/desk/deals/lead-1/listings").json())


def test_search_finds_by_ref_name_or_area_and_says_how_many(office, c):
    for i in range(2000):
        office.log.append("listing.added", actor="layla", content={"ref": f"X-{i}", "title": f"Tower {i}", "community": "Palm", "type": "flat", "status": "available"})
    r = c.get("/api/desk/deals/lead-1/listings", params={"q": "palm tower"}).json()
    assert r["total"] == 2000 and len(r["rows"]) == 20
    assert c.get("/api/desk/deals/lead-1/listings", params={"q": "X-1999"}).json()["total"] == 1
    assert c.get("/api/desk/deals/lead-1/listings", params={"q": "jumeirah village"}).json()["rows"][0]["ref"] == "JVC-88"
    assert c.get("/api/desk/deals/lead-1/listings", params={"q": "no such place"}).json() == {"total": 0, "rows": []}
    assert c.get("/api/desk/deals/nope/listings").status_code == 404


def test_a_rental_only_sees_listings_to_rent_and_no_developer(office, c):
    office.log.append("listing.added", actor="layla", content={"ref": "R-1", "title": "Flat to let", "offering": "rent", "status": "available"})
    desk_rules.set_path(office, "lead-1", "rent", by="omar")
    assert "developer" not in c.get("/api/desk/deals/lead-1").json()["stages"]["property"]["sources"]
    assert "R-1" in str(c.get("/api/desk/deals/lead-1/listings").json())
    assert "R-1" not in str(c.get("/api/desk/deals/lead-2/listings").json())  # a sale doesn't see it
    assert _convert(c, prop={"source": "developer", "developer": "Emaar", "project": "P", "unit": "1"}).status_code == 400


def test_another_agencys_listing_drafts_b_and_i_and_needs_the_agency_and_its_share(office, c):
    prop = {"source": "agency", "label": "Apt 901, Creek Tower"}
    assert "property" in _convert(c, prop={"source": "agency"}).json()["detail"]
    assert _convert(c, prop=prop).status_code == 400  # no agency
    assert _convert(c, prop=prop | {"other_agency": "Bayut Homes"}).status_code == 400  # no share
    assert not desk_stages.agreed(office.graph(), "lead-1") and _deal(office)["property"] == "WhatsApp enquiry"  # a refusal writes nothing
    r = _convert(c, prop=prop | AGENCY).json()
    assert r["listing_aed"] is None and r["waiting"] is None
    assert _deal(office)["property"] == "Apt 901, Creek Tower" and _live(office) == ["B", "I"]
    assert desk_rules.terms(office.graph(), "lead-1")["sides"] == "buyer"
    assert agency_forms.our_listing(office.graph(), "lead-1") is None
    fields = dict((label, value) for _, label, value, _ in agency_forms.fields(office.graph(), "lead-1", "I"))
    assert fields["Property"] == "Apt 901, Creek Tower" and fields["Agency"] is not None


def test_our_listing_with_another_agencys_buyer_is_form_a_and_i(office, c):
    _convert(c, prop={"source": "listing", "ref": "JVC-88", "brought": True} | AGENCY)
    assert _live(office) == ["A", "I"] and desk_rules.terms(office.graph(), "lead-1")["sides"] == "seller"
    assert _status(office, "JVC-88") == "reserved"


def test_an_agency_used_once_is_offered_again_with_its_details(office, c):
    assert c.get("/api/desk/agencies").json() == []
    _convert(c, prop={"source": "agency", "label": "Apt 1"} | AGENCY)
    assert c.get("/api/desk/agencies").json() == [{k: v for k, v in AGENCY.items() if k != "other_share_pct"}]


def test_a_developers_unit_uses_its_agreement_and_an_unknown_one_is_refused(office, c):
    from diwan.agents import finance
    desk_rules.set_path(office, "lead-1", "offplan", by="omar")
    assert list(c.get("/api/desk/deals/lead-1").json()["stages"]["property"]["sources"])[0] == "developer"
    prop = {"source": "developer", "developer": "Emaar", "project": "Creek Rise", "unit": "1204"}
    r = _convert(c, prop=prop)
    assert r.status_code == 400 and "no agreement with Emaar" in r.json()["detail"]
    assert "project" in _convert(c, prop=prop | {"unit": ""}).json()["detail"]
    _developer(office)
    assert _convert(c, prop=prop).json()["waiting"] is None
    assert _deal(office)["property"] == "1204, Creek Rise" and _deal(office)["stage"] == "Reservation"
    com = finance.commission(office.graph(), "lead-1")
    assert com["pct"] == 4 and com["developer"] == "Emaar" and _live(office) == []


def test_a_deal_already_converted_gets_the_form_which_answers_its_open_question(office, c):
    """Deals converted before this was built: the agreed price is on them, a placeholder and an open question too."""
    office.log.append("setting.changed", actor="omar", deal="lead-1", content={"person": "deal:lead-1", "key": "agreed", "value": {"listing_aed": None, "amount": 1_900_000, "pct": None, "diff": None, "by": "omar", "approved_by": None}})
    office.log.append("stage.changed", actor="omar", deal="lead-1", content={"stage": "Offer accepted"})
    agency_forms.on_convert(office, "lead-1", "omar")
    ask = next(t for t in office.graph().of("task", "lead-1") if t.props.get("step") == "sides")
    assert ask.status in ("open", "queued", "working") and c.get("/api/desk/deals/lead-1").json()["stages"]["property"]["needed"]
    r = c.post("/api/desk/deals/lead-1/property", json={"by": "omar", "property": {"source": "listing", "ref": "JVC-88"}})
    assert r.status_code == 200
    g = office.graph()
    assert g.nodes[ask.id].status == "done" and "Villa 88" in g.nodes[ask.id].props["reason"]
    assert not c.get("/api/desk/deals/lead-1").json()["stages"]["property"]["needed"]
    assert _live(office) == ["A", "B"] and _status(office, "JVC-88") == "reserved"
    assert desk_stages.agreed(office.graph(), "lead-1")["listing_aed"] == 1_900_000


def test_putting_a_listing_far_above_the_agreed_price_on_a_converted_deal_needs_the_owner(office, c):
    _convert(c, amount=1_100_000, prop={"source": "agency", "label": "Apt 1"} | AGENCY)
    body = {"source": "listing", "ref": "JVC-88"}
    r = c.post("/api/desk/deals/lead-1/property", json={"by": "omar", "property": body})
    assert r.status_code == 400 and "only the owner" in r.json()["detail"]
    assert c.post("/api/desk/deals/lead-1/property", json={"by": "layla", "property": body}).status_code == 200
    a = desk_stages.agreed(office.graph(), "lead-1")
    assert a["pct"] < 0 and a["approved_by"] == "layla"


def test_changing_the_property_keeps_who_changed_it_and_redrafts_what_isnt_signed(office, c):
    _convert(c, prop={"source": "listing", "ref": "JVC-88"})
    first = {f["draft"] for f in agency_forms.forms(office.graph(), "lead-1")}
    c.post("/api/desk/deals/lead-1/property", json={"by": "joseph", "property": {"source": "listing", "ref": "BB-305"}})
    g = office.graph()
    assert _status(office, "JVC-88") == "available" and _status(office, "BB-305") == "reserved"
    assert all(g.nodes[d].status == "sent_back" for d in first) and _live(office) == ["A", "B"]
    assert "Apartment 305" in str(agency_forms.fields(g, "lead-1", "A"))
    assert [e["actor"] for e in office.log.list(deal="lead-1") if e["content"].get("key") == "property"] == ["omar", "joseph"]


def test_a_form_f_plan_goes_back_with_a_changed_property(office, c):
    from diwan.agents import operations
    _convert(c, prop={"source": "listing", "ref": "JVC-88"})
    plan = operations.make_plan(office, "lead-1")
    c.post("/api/desk/deals/lead-1/property", json={"by": "omar", "property": {"source": "listing", "ref": "BB-305"}})
    g = office.graph()
    plans = [d for d in g.of("draft", "lead-1") if d.props["kind"] == "Form F"]
    assert g.nodes[plan].status == "sent_back" and len(plans) == 2
    assert "Apartment 305" in " ".join(s.props["text"] for s in g.into(plans[-1].id, "part_of"))


def test_a_signed_form_fixes_the_property(office, c, tmp_path):
    _convert(c, prop={"source": "listing", "ref": "JVC-88"})
    t = next(x for x in office.graph().of("task", "lead-1") if x.props.get("step") == "sign")
    agency_forms.signed(office, t.id, "omar", b"%PDF-1.4", "s.pdf", media=tmp_path, today=date.today())
    r = c.post("/api/desk/deals/lead-1/property", json={"by": "omar", "property": {"source": "listing", "ref": "BB-305"}})
    assert r.status_code == 400 and "signed" in r.json()["detail"]
    assert deal_property.locked(office.graph(), "lead-1") and _status(office, "JVC-88") == "reserved"


def test_a_lost_deal_lets_the_listing_go_and_can_only_come_back_if_it_is_free(office, c):
    _convert(c, prop={"source": "listing", "ref": "JVC-88"})
    desk_stages.move(office, "lead-1", "Lost", "omar", "Finance refused")
    assert _status(office, "JVC-88") == "available"
    _convert(c, "lead-2", prop={"source": "listing", "ref": "JVC-88"})
    with pytest.raises(ValueError, match="reserved"):
        desk_stages.move(office, "lead-1", "Offer accepted", "omar", "Back on")
    desk_stages.move(office, "lead-2", "Lost", "omar", "Changed their mind")
    desk_stages.move(office, "lead-1", "Offer accepted", "omar", "Back on")
    assert _status(office, "JVC-88") == "reserved"


def test_closing_sells_or_lets_the_listing_and_records_the_real_property(office, monkeypatch):
    from diwan.agents import operations
    _closed = []
    desk_rules.set_path(office, "lead-1", "rent", by="omar")
    desk_stages.convert(office, "lead-1", "omar", 1_900_000, {"source": "listing", "ref": "JVC-88"})
    monkeypatch.setattr(operations, "closing", lambda g, d: {"sale": None, "ready": True, "items": []})
    monkeypatch.setattr(office, "close_sale", lambda **k: _closed.append(k) or "S9")
    fig = office.add_task("lead-1", "ops", "figures", by="omar", props={"step": "figures", "closing": True})
    fact = office.graph().facts("lead-1", "deal_term")[-1]
    office.finish_task(fig, f"Confirmed ({fact.id})")
    desk_rules.set_terms(office, "lead-1", {"start": "2026-11-01", "end": "2027-10-31"}, by="omar")
    operations.close(office, "lead-1", "joseph", today=date.today())
    assert _closed[0]["listing"] == "Villa 88" and _status(office, "JVC-88") == "let"


def test_a_placeholder_deal_cant_close(office, monkeypatch):
    from diwan.agents import operations
    monkeypatch.setattr(operations, "closing", lambda g, d: {"sale": None, "ready": True, "items": []})
    office.record_fact("lead-1", "deal_term", "Two million", "Ali Rahman", amount_aed=2_000_000)
    fig = office.add_task("lead-1", "ops", "figures", by="omar", props={"step": "figures", "closing": True})
    office.finish_task(fig, f"Confirmed ({office.graph().facts('lead-1', 'deal_term')[-1].id})")
    with pytest.raises(ValueError, match="which property"):
        operations.close(office, "lead-1", "joseph", today=date.today())


def test_only_the_broker_the_transactions_officer_or_the_owner_says(office, c):
    r = c.post("/api/desk/deals/lead-1/property", json={"by": "priya", "property": {"source": "listing", "ref": "JVC-88"}})
    assert r.status_code == 403
    assert c.post("/api/desk/deals/nope/property", json={"by": "omar", "property": {}}).status_code == 404


def test_a_deal_named_after_our_listing_converts_as_it_always_did(office, c):
    r = _convert(c, "marina-1204", 2_600_000)
    assert r.status_code == 200 and _status(office, "MC-1204") == "reserved"
    assert [t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "sides"]  # still asked, as before
