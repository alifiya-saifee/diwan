"""The Deal desk's rules as the owner's settings (docs/deal-desk.md item 8)."""
import copy

import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo, desk_rules
from diwan.events import EventLog
from diwan.office import Office


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def edited(office, **change):
    r = copy.deepcopy(desk_rules.rules(office.graph()))
    for path, value in change.items():
        *keys, last = path.split("__")
        node = r
        for k in keys:
            node = node[k]
        node[last] = value
    return r


def test_defaults_are_dubai_practice_until_the_owner_changes_them(office):
    g = office.graph()
    assert desk_rules.rules(g)["cash_report_aed"] == 55_000 and not desk_rules.changed(g)
    assert desk_rules.path(g, "marina-1204")["id"] == "ready"


def test_only_the_owner_changes_the_rules_and_bad_ones_are_refused(office):
    with pytest.raises(PermissionError):
        desk_rules.save(office, edited(office, cash_report_aed=50_000), by="priya")
    with pytest.raises(ValueError, match="cash-report limit"):
        desk_rules.save(office, edited(office, cash_report_aed=-1), by="layla")
    with pytest.raises(ValueError, match="who it waits on"):
        desk_rules.save(office, edited(office, paths__rent__steps=[["Tenancy contract signed", ""]]), by="layla")
    with pytest.raises(ValueError, match="percentage"):
        desk_rules.save(office, edited(office, paths__ready__commission_pct=120), by="layla")
    with pytest.raises(ValueError, match="paid by"):
        desk_rules.save(office, edited(office, paths__offplan__commission_from="nobody"), by="layla")


def test_only_what_differs_is_stored_with_who_changed_it(office):
    desk_rules.save(office, edited(office, cash_report_aed=50_000), by="layla")
    e = [e for e in office.log.list() if e["type"] == "setting.changed" and e["content"]["key"] == "rules"][-1]
    assert e["actor"] == "layla" and e["content"]["value"] == {"cash_report_aed": 50_000}
    assert desk_rules.rules(office.graph())["paths"]["ready"]["commission_pct"] == 2


def test_a_lower_cash_limit_reports_a_cash_payment_it_did_not_before(office):
    office.record_fact("jvc-88", "payment_promise", "Fifty-two thousand in cash as the booking deposit.", "Sara Malik", amount_aed=52_000, method="cash")
    assert not [d for d in office.graph().of("draft", "jvc-88") if d.props["kind"] == "cash report"]
    desk_rules.save(office, edited(office, cash_report_aed=50_000), by="layla")
    office.record_fact("jvc-88", "payment_promise", "Actually fifty-three thousand cash.", "Sara Malik", amount_aed=53_000, method="cash")
    assert [d for d in office.graph().of("draft", "jvc-88") if d.props["kind"] == "cash report"]


def test_a_new_step_reaches_new_paperwork_and_deals_past_it_keep_theirs(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    demo.correction(office)
    c.post("/api/desk/deals/marina-1204/formf", json={"by": "joseph"})
    sub = next(t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "formf" and t.props.get("draft") and t.status == "queued")
    steps = desk_rules.rules(office.graph())["paths"]["ready"]["steps"]
    r = c.post("/api/desk/rules", json={"by": "layla", "rules": edited(office, paths__ready__steps=steps + [["Keys and access cards handed over", "the seller"]])})
    assert r.status_code == 200 and r.json()["changed_by"] == "Layla"
    assert c.post("/api/desk/rules", json={"by": "omar", "rules": r.json()["rules"]}).status_code == 403
    c.post(f"/api/desk/tasks/{sub.id}/submitted", json={"by": "joseph", "reference": "DLD-1"})
    got = [t.props["action"] for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "transfer"]
    assert got[-1] == "Keys and access cards handed over" and len(got) == len(steps) + 1


def test_a_deals_path_comes_from_its_sales_desk(office):
    office.log.append("setting.changed", actor="layla", content={"person": "sales", "key": "kinds", "value": [
        {"id": "leasing", "name": "Leasing", "listings": {"offering": "rent"}}, {"id": "off_plan", "name": "Off-plan", "listings": {"offering": "sale", "completion": "off_plan"}}]})
    g = office.graph()
    g.nodes["deal:jvc-88"].props["kind"] = "leasing"
    g.nodes["deal:marina-1204"].props["kind"] = "off_plan"
    assert desk_rules.path_of(g, "jvc-88") == "rent" and desk_rules.path_of(g, "marina-1204") == "offplan"
    assert desk_rules.path(g, "jvc-88")["commission_from"] == "tenant"


# ---------- commission: worked out, invoiced, collected (plan R15, O8, L5) ----------

def test_commission_is_worked_out_from_the_clients_price_and_the_owners_rate(office):
    from diwan.agents import finance
    c = finance.commission(office.graph(), "marina-1204")
    assert (c["base"], c["fact"], c["pct"], c["amount"], c["vat"], c["total"], c["payer"]) == (2_600_000, "F1", 2, 52_000, 2_600, 54_600, "buyer")
    desk_rules.save(office, edited(office, paths__ready__commission_pct=1.5, vat_pct=5), by="layla")
    assert finance.commission(office.graph(), "marina-1204")["total"] == 40_950
    office.open_deal("d-x", property="Apt 1, Bay Square", customer="Noor Saleh", broker="omar")
    assert "No price" in finance.commission(office.graph(), "d-x")["missing"]


def test_an_invoice_is_drafted_sent_and_collected_by_finance_only(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    assert c.post("/api/desk/deals/marina-1204/invoice", json={"by": "omar"}).status_code == 403
    did = c.post("/api/desk/deals/marina-1204/invoice", json={"by": "ahmed"}).json()["draft"]
    assert office.graph().nodes[did].status == "live"  # Review passed it: it rests on the live price
    assert c.post("/api/desk/deals/marina-1204/invoice", json={"by": "ahmed"}).status_code == 400
    send = next(t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "inv")
    collect = c.post(f"/api/desk/tasks/{send.id}/invoiced", json={"by": "ahmed", "number": "INV-0042"}).json()["task"]
    assert "invoice INV-0042" in office.graph().nodes[collect].props["action"]
    q = c.get("/api/desk/work?person=ahmed").json()["items"]
    assert any(x["id"] == collect and x["act"] == "commission" for x in q)
    doc = c.post(f"/api/desk/tasks/{collect}/commission", json={"by": "ahmed", "reference": "ENBD 9001"}).json()["document"]
    g = office.graph()
    assert g.nodes[collect].props["result"] == "received" and g.nodes[doc].props["amount_aed"] == 54_600


def test_a_changed_price_sends_the_invoice_back_and_stops_it_being_sent(office, monkeypatch):
    from diwan.agents import finance
    did = finance.draft_invoice(office, "marina-1204", "ahmed")
    send = next(t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "inv")
    office.record_fact("marina-1204", "deal_term", "We agreed two point five in the end.", "Karim Haddad", amount_aed=2_500_000, replaces="F1")
    g = office.graph()
    assert g.nodes[did].status == "sent_back" and g.nodes[send.id].status == "withdrawn"
    assert finance.commission(g, "marina-1204")["total"] == 52_500
    assert finance.draft_invoice(office, "marina-1204", "ahmed") != did


# ---------- the rental path (plan L2-L8) ----------

def test_the_broker_sets_the_path_once_before_the_paperwork_starts(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    assert c.post("/api/desk/deals/jvc-88/path", json={"by": "priya", "path": "rent"}).status_code == 403
    assert c.post("/api/desk/deals/jvc-88/path", json={"by": "omar", "path": "lease"}).status_code == 400
    assert c.post("/api/desk/deals/jvc-88/path", json={"by": "omar", "path": "rent"}).json()["path"] == "rent"
    v = c.get("/api/desk/deals/jvc-88").json()
    assert v["path"] == {"id": "rent", "name": "Rental", "chosen": True, "from_desk": False}
    assert v["commission"]["base_label"] == "Yearly rent" and v["commission"]["payer"] == "tenant" and v["commission"]["pct"] == 5
    assert c.post("/api/desk/deals/jvc-88/paperwork", json={"by": "omar"}).status_code == 403
    tids = c.post("/api/desk/deals/jvc-88/paperwork", json={"by": "joseph"}).json()["tasks"]
    g = office.graph()
    assert [g.nodes[t].props["action"] for t in tids] == [s for s, _ in desk_rules.DEFAULTS["paths"]["rent"]["steps"]]
    dep = next(t for t in g.of("task", "jvc-88") if t.props["agent"] == "pay")
    assert dep.props["amount_aed"] == 95_000 and "security deposit" in dep.props["action"]  # 5% of 1.9M said as the rent
    assert c.post("/api/desk/deals/jvc-88/paperwork", json={"by": "joseph"}).status_code == 400
    assert c.post("/api/desk/deals/jvc-88/path", json={"by": "omar", "path": "ready"}).status_code == 400  # fixed once started
    assert c.post("/api/desk/deals/marina-1204/paperwork", json={"by": "joseph"}).status_code == 400  # ready: Form F instead


# ---------- closing, then Records (spec item 9) ----------

def _to_closing(office):
    from diwan.agents import compliance, operations
    desk_rules.set_path(office, "jvc-88", "rent", by="omar")
    desk_rules.set_terms(office, "jvc-88", {"start": "2026-11-01", "end": "2027-10-31"}, by="omar")
    tids = operations.start_paperwork(office, "jvc-88", "joseph")
    for t in tids:
        operations.tick(office, t, "joseph")
    for t in office.graph().of("task", "jvc-88"):
        if t.props["agent"] == "screen" and t.status in ("queued", "open"):
            compliance.record_screening(office, t.id, "priya", "clear", "UN list")
    return {t.props["step"]: t.id for t in office.graph().of("task", "jvc-88") if t.props.get("closing")}


def test_the_last_step_starts_closing_and_the_deal_closes_only_when_all_four_are_done(office, monkeypatch):
    from datetime import date
    from diwan.agents import finance, operations
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    assert operations.closing(office.graph(), "jvc-88") is None
    steps = _to_closing(office)
    cl = operations.closing(office.graph(), "jvc-88")
    assert [i["key"] for i in cl["items"]] == ["figures", "invoice", "compliance", "docs"] and not cl["ready"]
    assert {i["key"]: i["done"] for i in cl["items"]} == {"figures": False, "invoice": False, "compliance": True, "docs": False}
    r = c.post("/api/desk/deals/jvc-88/close", json={"by": "joseph"})
    assert r.status_code == 400 and "Not yet" in r.json()["detail"]
    assert c.post(f"/api/desk/tasks/{steps['figures']}/confirm", json={"by": "priya"}).status_code == 403
    assert c.post(f"/api/desk/tasks/{steps['figures']}/confirm", json={"by": "omar"}).json()["ok"]
    assert c.post(f"/api/desk/tasks/{steps['docs']}/docs", json={"by": "joseph"}).json()["ok"]
    finance.draft_invoice(office, "jvc-88", "ahmed")
    send = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "inv")
    collect = finance.invoice_sent(office, send.id, "ahmed", "INV-7")
    finance.commission_received(office, collect, "ahmed", "ENBD 1", today=date.today())
    assert operations.closing(office.graph(), "jvc-88")["ready"]
    assert c.post("/api/desk/deals/jvc-88/close", json={"by": "omar"}).status_code == 403
    sid = c.post("/api/desk/deals/jvc-88/close", json={"by": "joseph"}).json()["sale"]
    g = office.graph()
    sale = g.nodes[sid].props
    assert (sale["deal"], sale["price_aed"], sale["commission_aed"], sale["broker"]) == ("jvc-88", 1_900_000, 95_000, "omar")
    assert g.nodes["deal:jvc-88"].props["stage"] == "Won"
    assert c.post("/api/desk/deals/jvc-88/close", json={"by": "joseph"}).status_code == 400
    assert "jvc-88" not in [d["deal"] for d in c.get("/api/desk/deals").json()["rows"]]
    assert [d["deal"] for d in c.get("/api/desk/deals?filter=closed").json()["rows"]] == ["jvc-88"]
    assert c.get("/api/desk/overview").json()["after"]["closed30"] == 1


def test_a_price_changed_after_confirmation_must_be_confirmed_again(office):
    from datetime import date
    from diwan.agents import finance, operations
    steps = _to_closing(office)
    operations.confirm_figures(office, steps["figures"], "omar")
    operations.docs_filed(office, steps["docs"], "joseph")
    finance.draft_invoice(office, "jvc-88", "ahmed")
    send = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "inv")
    finance.commission_received(office, finance.invoice_sent(office, send.id, "ahmed", "INV-8"), "ahmed", "ENBD 2", today=date.today())
    office.record_fact("jvc-88", "deal_term", "We settled at one point eight.", "Sara Malik", amount_aed=1_800_000, replaces="F6")
    with pytest.raises(ValueError, match="confirm the final figures again"):
        operations.close(office, "jvc-88", "joseph", today=date.today())



# ---------- what the signed documents say: rate, Form I split, developer, tenancy (plan R1-R3, O1, L2) ----------

def _dev(office, **kw):
    desk_rules.save(office, edited(office, developers=[{"name": "Emaar", "commission_pct": 4, "payable_after_pct": 20, **kw}]), by="layla")


def test_terms_set_the_rate_and_the_other_agencys_share(office):
    from diwan.agents import finance
    with pytest.raises(PermissionError):
        desk_rules.set_terms(office, "marina-1204", {"rate_pct": 1.5}, by="priya")
    with pytest.raises(ValueError, match="together"):
        desk_rules.set_terms(office, "marina-1204", {"other_agency": "Bayut Homes"}, by="omar")
    desk_rules.set_terms(office, "marina-1204", {"agreement": "Form B 2026-118", "rate_pct": 1.5, "other_agency": "Bayut Homes", "other_share_pct": 50}, by="omar")
    c = finance.commission(office.graph(), "marina-1204")
    assert (c["pct"], c["rate_from"], c["amount"], c["share"], c["ours"]) == (1.5, "Form B 2026-118", 39_000, 19_500, 19_500)
    assert c["fees"][0]["aed"] == 104_000  # the DLD fee, 4% of the price the client said
    finance.draft_invoice(office, "marina-1204", "ahmed")
    with pytest.raises(ValueError, match="fixed"):
        desk_rules.set_terms(office, "marina-1204", {"rate_pct": 2}, by="omar")


def test_the_split_is_paid_out_before_the_commission_item_is_done(office):
    from datetime import date
    from diwan.agents import finance, operations
    desk_rules.set_terms(office, "jvc-88", {"other_agency": "Bayut Homes", "other_share_pct": 40}, by="omar")
    steps = _to_closing(office)
    finance.draft_invoice(office, "jvc-88", "ahmed")
    send = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "inv")
    finance.commission_received(office, finance.invoice_sent(office, send.id, "ahmed", "INV-9"), "ahmed", "ENBD 3", today=date.today())
    item = lambda: next(i for i in operations.closing(office.graph(), "jvc-88")["items"] if i["key"] == "invoice")  # noqa: E731
    assert not item()["done"] and "Bayut Homes" in item()["note"]
    split = next(t for t in office.graph().of("task", "jvc-88") if t.props.get("step") == "split")
    assert split.props["amount_aed"] == 38_000  # 40% of 95,000
    with pytest.raises(ValueError, match="reference"):
        finance.split_paid(office, split.id, "ahmed", " ")
    finance.split_paid(office, split.id, "ahmed", "ENBD 4")
    assert item()["done"]
    operations.confirm_figures(office, steps["figures"], "omar")
    operations.docs_filed(office, steps["docs"], "joseph")
    sid = operations.close(office, "jvc-88", "joseph", today=date.today())
    assert office.graph().nodes[sid].props["commission_aed"] == 57_000  # what we keep is what Records records


def test_a_step_that_does_not_apply_is_marked_not_needed_with_the_reason(office):
    from diwan.agents import operations
    demo.correction(office)
    operations.formf_plan(office, "marina-1204", office.add_task("marina-1204", "formf", "Prepare Form F"), "r1")
    sub = next(t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "formf" and t.props.get("draft"))
    operations.submitted(office, sub.id, "joseph", "DLD-2")
    mort = next(t for t in office.graph().of("task", "marina-1204") if t.props["action"].startswith("Buyer's mortgage"))
    with pytest.raises(ValueError, match="why"):
        operations.not_needed(office, mort.id, "joseph", "")
    operations.not_needed(office, mort.id, "joseph", "Karim pays cash")
    t = office.graph().nodes[mort.id]
    assert t.status == "done" and t.props["result"] == "not needed" and "Karim pays cash" in t.props["reason"]


# ---------- off-plan: the developer's agreement, the SPA's instalments, the commission trigger (plan O1-O11) ----------

def _offplan(office):
    _dev(office)
    desk_rules.set_path(office, "marina-1204", "offplan", by="omar")
    desk_rules.set_terms(office, "marina-1204", {"developer": "Emaar"}, by="omar")
    from diwan.agents import operations
    return operations.start_paperwork(office, "marina-1204", "joseph")


def test_a_developer_needs_an_agreement_and_its_rate_is_used(office):
    from diwan.agents import finance
    with pytest.raises(ValueError, match="no agreement with Emaar"):
        desk_rules.set_terms(office, "marina-1204", {"developer": "Emaar"}, by="omar")
    with pytest.raises(ValueError, match="percentage"):
        desk_rules.save(office, edited(office, developers=[{"name": "Emaar", "commission_pct": 400, "payable_after_pct": 20}]), by="layla")
    _offplan(office)
    c = finance.commission(office.graph(), "marina-1204")
    assert (c["pct"], c["payer"], c["developer"], c["amount"]) == (4, "developer", "Emaar", 104_000)
    assert c["trigger"] == {"pct": 20, "paid": 0, "paid_pct": 0.0, "met": False}


def test_the_spa_payment_plan_becomes_instalments_into_escrow_and_must_add_up(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    _offplan(office)
    plan = [{"what": "On SPA signing", "pct": 10, "due": "2026-11-15"}, {"what": "On 50% construction", "pct": 30, "due": "2027-06-01"},
            {"what": "On handover", "pct": 50, "due": "2028-03-01"}]
    assert c.post("/api/desk/deals/marina-1204/schedule", json={"by": "ahmed", "document": "SPA-1", "rows": plan}).status_code == 403
    r = c.post("/api/desk/deals/marina-1204/schedule", json={"by": "joseph", "document": "SPA-1", "rows": plan[:2]})
    assert r.status_code == 400 and "add up" in r.json()["detail"] and "260,000 already expected" in r.json()["detail"]
    tids = c.post("/api/desk/deals/marina-1204/schedule", json={"by": "joseph", "document": "SPA-1", "rows": plan}).json()["tasks"]
    g = office.graph()
    assert [g.nodes[t].props["amount_aed"] for t in tids] == [260_000, 780_000, 1_300_000]
    assert all(g.nodes[t].props["payee"] == "the project's escrow account" for t in tids)
    assert c.post("/api/desk/deals/marina-1204/schedule", json={"by": "joseph", "document": "SPA-1", "rows": plan}).status_code == 400
    v = c.get("/api/desk/deals/marina-1204").json()
    assert v["schedule"]["kind"] == "instalment" and [t["due"] for t in v["tasks"] if t["id"] in tids] == ["2026-11-15", "2027-06-01", "2028-03-01"]
    assert c.post(f"/api/desk/tasks/{tids[0]}/received", json={"by": "ahmed", "reference": "EMR-55"}).status_code == 200
    assert office.graph().nodes[tids[0]].props["reason"] == "Paid into the project's escrow account, receipt EMR-55"
    assert c.post(f"/api/desk/tasks/{tids[0]}/release", json={"by": "ahmed"}).status_code == 400  # never ours to hold


def test_the_developer_owes_commission_only_once_its_share_is_paid(office):
    from datetime import date
    from diwan.agents import finance
    _offplan(office)
    tids = finance.schedule(office, "marina-1204", [{"pct": 40, "due": "2026-11-15"}, {"pct": 50, "due": "2028-03-01"}], "joseph", document="SPA-2")
    with pytest.raises(ValueError, match="once 20% of the price is paid; 0.0% is paid"):
        finance.draft_invoice(office, "marina-1204", "ahmed")
    finance.mark_received(office, tids[0], "ahmed", "EMR-1", today=date.today())
    assert finance.commission(office.graph(), "marina-1204")["trigger"]["met"]
    assert finance.draft_invoice(office, "marina-1204", "ahmed")


def test_an_offplan_deal_closes_before_handover_and_the_instalments_keep_running(office):
    from diwan.agents import operations
    tids = _offplan(office)
    g = office.graph()
    assert [g.nodes[t].props.get("after", False) for t in tids] == [False, False, False, True, True]
    for t in tids[:3]:
        operations.tick(office, t, "joseph")
    assert operations.closing(office.graph(), "marina-1204")  # closing started with the handover still ahead
    assert all(office.graph().nodes[t].status == "queued" for t in tids[3:])


# ---------- a rental after closing: cheques, renewal, move-out (plan L2, after closing) ----------

def test_the_tenancy_cheques_are_spread_over_the_year_from_the_start_date(office):
    from diwan.agents import finance
    desk_rules.set_path(office, "jvc-88", "rent", by="omar")
    with pytest.raises(ValueError, match="start date"):
        finance.cheques(office.graph(), "jvc-88", 4)
    with pytest.raises(ValueError, match="ends after"):
        desk_rules.set_terms(office, "jvc-88", {"start": "2026-11-01", "end": "2026-10-01"}, by="omar")
    desk_rules.set_terms(office, "jvc-88", {"start": "2026-11-30", "end": "2027-11-29"}, by="omar")
    rows = finance.cheques(office.graph(), "jvc-88", 4)
    assert [(r["amount_aed"], r["due"]) for r in rows] == [(475_000, "2026-11-30"), (475_000, "2027-02-28"), (475_000, "2027-05-30"), (475_000, "2027-08-30")]
    tids = finance.schedule(office, "jvc-88", rows, "joseph", document="TC-77")
    assert office.graph().nodes[tids[0]].props["payee"] == "the landlord"


def test_closing_a_rental_dates_the_renewal_question_and_the_move_out(office, monkeypatch):
    from datetime import date
    from diwan.agents import finance, operations
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    steps = _to_closing(office)
    operations.confirm_figures(office, steps["figures"], "omar")
    operations.docs_filed(office, steps["docs"], "joseph")
    finance.draft_invoice(office, "jvc-88", "ahmed")
    send = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "inv")
    finance.commission_received(office, finance.invoice_sent(office, send.id, "ahmed", "INV-10"), "ahmed", "ENBD 5", today=date.today())
    operations.close(office, "jvc-88", "joseph", today=date.today())
    after = {t.props["step"]: t for t in office.graph().of("task", "jvc-88") if t.props.get("after_close")}
    assert after["renewal"].props["due"] == "2027-08-02" and after["renewal"].props["needs_person"] == "omar"  # 90 days before 31 Oct
    assert after["moveout"].props["due"] == "2027-10-31"
    work = c.get("/api/desk/work?person=joseph").json()["items"]
    assert any(x["id"] == after["moveout"].id and x["act"] == "after" for x in work)
    assert c.post(f"/api/desk/tasks/{after['renewal'].id}/after", json={"by": "joseph", "note": "x"}).status_code == 403
    assert c.post(f"/api/desk/tasks/{after['renewal'].id}/after", json={"by": "omar", "note": ""}).status_code == 400
    assert c.post(f"/api/desk/tasks/{after['renewal'].id}/after", json={"by": "omar", "note": "Sara renews at the same rent"}).json()["ok"]


def test_a_rental_cannot_close_without_its_tenancy_dates(office):
    from datetime import date
    from diwan.agents import finance, operations
    steps = _to_closing(office)
    desk_rules.set_terms(office, "jvc-88", {"start": "", "end": ""}, by="omar")
    operations.confirm_figures(office, steps["figures"], "omar")
    operations.docs_filed(office, steps["docs"], "joseph")
    finance.draft_invoice(office, "jvc-88", "ahmed")
    send = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "inv")
    finance.commission_received(office, finance.invoice_sent(office, send.id, "ahmed", "INV-11"), "ahmed", "ENBD 6", today=date.today())
    with pytest.raises(ValueError, match="start and end dates"):
        operations.close(office, "jvc-88", "joseph", today=date.today())


# ---------- the KPIs, counted from the log (plan: KPIs) ----------

def test_kpis_are_counted_from_the_log_with_the_deals_behind_them(office, monkeypatch):
    from datetime import date, timedelta
    from diwan.agents import finance, operations
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    k = c.get("/api/desk/kpis").json()
    assert k["to_close"]["median"] is None and k["fall"]["pct"] is None and k["stuck"]["deals"] == []
    steps = _to_closing(office)
    operations.confirm_figures(office, steps["figures"], "omar")
    operations.docs_filed(office, steps["docs"], "joseph")
    finance.draft_invoice(office, "jvc-88", "ahmed")
    send = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "inv")
    finance.commission_received(office, finance.invoice_sent(office, send.id, "ahmed", "INV-12"), "ahmed", "ENBD 7", today=date.today())
    dep = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "pay")
    finance.mark_received(office, dep.id, "ahmed", "ENBD 8", today=date.today())
    operations.close(office, "jvc-88", "joseph", today=date.today())
    k = c.get("/api/desk/kpis").json()
    assert k["to_close"]["n"] == 1 and k["to_close"]["paths"]["rent"]["n"] == 1 and k["to_close"]["deals"][0]["deal"] == "jvc-88"
    assert k["compliance"] == {"pct": 100, "n": 1, "deals": []}  # Sara was screened before the deposit arrived
    assert k["commission"]["billed"] == k["commission"]["collected"] == 99_750 and k["commission"]["payers"]["tenant"]["billed"] == 99_750
    assert {t["step"] for t in k["touchpoints"]} >= {"Ejari registered"}
    from diwan import desk_kpis
    office.add_task("marina-1204", "transfer", "Form F signed", needs_person="joseph", props={"waiting_on": "the buyer"})
    later = desk_kpis.kpis(office.graph(), office.log.list(), date.today() + timedelta(days=10))
    assert [(x["deal"], x["days"], x["waiting_on"]) for x in later["stuck"]["deals"]] == [("marina-1204", 10, "the buyer")]
    office.log.append("stage.changed", actor="omar", deal="marina-1204", content={"stage": "Lost", "why": "the bank refused the mortgage"})
    k = desk_kpis.kpis(office.graph(), office.log.list(), date.today())
    assert k["fall"]["pct"] == 50 and k["fall"]["deals"][0]["why"] == "the bank refused the mortgage"
    later = desk_kpis.kpis(office.graph(), office.log.list(), date.today() + timedelta(days=10))
    assert later["stuck"]["deals"] == []  # the stuck deal was lost, the other closed


# ---------- stages on the Deal desk, and the agency forms at conversion (spec item 11) ----------

def test_who_moves_a_stage_and_what_needs_a_reason(office, monkeypatch):
    from diwan import desk_stages
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    assert desk_stages.stages(office.graph(), "marina-1204")[-4:] == ["Offer", "Offer accepted", "Form F", "Transfer"]
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "priya", "stage": "Offer"}).status_code == 403
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "omar", "stage": "Offer"}).json()["current"] == "Offer"
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "joseph", "stage": "Viewed"}).status_code == 400  # back needs a reason
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "joseph", "stage": "Viewed", "reason": "the seller withdrew the offer"}).status_code == 200
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "omar", "stage": "Won"}).status_code == 400
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "omar", "stage": "Lost"}).status_code == 400
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "layla", "stage": "Lost", "reason": "bought elsewhere"}).json()["current"] == "Lost"
    e = [e for e in office.log.list() if e["type"] == "stage.changed"][-1]
    assert e["content"] == {"stage": "Lost", "why": "bought elsewhere", "back": False}
    assert c.post("/api/desk/deals/marina-1204/stage", json={"by": "omar", "stage": "Offer"}).status_code == 400  # reopening needs a reason too


def _convert(office, c):
    c.post("/api/desk/deals/marina-1204/convert", json={"by": "omar", "amount": 2_600_000})
    return next(t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "sides")


def test_conversion_on_our_listing_asks_who_brought_the_buyer_once(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    ask = _convert(office, c)
    assert "MC-1204" in ask.props["action"] and "did another agent bring the buyer" in ask.props["action"] and ask.props["needs_person"] == "omar"
    c.post("/api/desk/deals/marina-1204/stage", json={"by": "omar", "stage": "Form F"})
    assert len([t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "sides"]) == 1
    assert any(x["id"] == ask.id for x in c.get("/api/desk/work?person=omar").json()["items"])


def test_seller_side_with_another_agency_drafts_form_a_and_form_i_as_pdfs(office, monkeypatch):
    from diwan import agency_forms
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    desk_rules.save(office, edited(office, agency={"name": "Diwan Realty", "orn": "ORN-12345"}, brns={"omar": "BRN-55501"}), by="layla")
    _convert(office, c)
    assert c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "seller", "other": {}}).status_code == 400  # name them
    r = c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "seller", "other": {
        "other_agency": "Bayut Homes", "other_orn": "ORN-777", "other_agent": "Rami Aziz", "other_brn": "BRN-9", "other_share_pct": 50}})
    drafts = r.json()["drafts"]
    fs = agency_forms.forms(office.graph(), "marina-1204")
    assert [f["form"] for f in fs] == ["A", "I"] and all(f["waiting"] and f["status"] == "live" for f in fs)
    pdf = c.get(f"/api/desk/forms/{drafts[1]}.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    text = pdf.content.decode("latin-1")
    for want in ("Bayut Homes", "ORN-777", "ORN-12345", "BRN-55501", "AED 2,600,000", "50%"):
        assert want in text, want
    a = c.get(f"/api/desk/forms/{drafts[0]}.pdf").content.decode("latin-1")
    assert "Title deed number" in a and "\\(to fill\\)" in a


def test_form_f_waits_for_the_signatures_and_the_upload_files_them(office, monkeypatch, tmp_path):
    from diwan import agency_forms
    from diwan.agents import operations
    from diwan.providers import meta
    monkeypatch.setattr(appmod.S, "office", office)
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    c = TestClient(appmod.app)
    _convert(office, c)
    c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "both"})
    assert [f["form"] for f in agency_forms.forms(office.graph(), "marina-1204")] == ["A", "B"]
    operations.formf_plan(office, "marina-1204", office.add_task("marina-1204", "formf", "Prepare Form F"), "r1")
    sub = next(t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "formf" and t.props.get("draft"))
    with pytest.raises(ValueError, match="Form A and Form B wait for a signature"):
        operations.submitted(office, sub.id, "joseph", "DLD-9")
    signs = [t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "sign"]
    assert c.post(f"/api/desk/tasks/{signs[0].id}/signed", data={"by": "omar"}, files={"file": ("a.txt", b"hello")}).status_code == 400
    assert c.post(f"/api/desk/tasks/{signs[0].id}/signed", data={"by": "priya"}, files={"file": ("a.pdf", b"%PDF-1.4 x")}).status_code == 403
    for t in signs:
        assert c.post(f"/api/desk/tasks/{t.id}/signed", data={"by": "omar"}, files={"file": ("signed.pdf", b"%PDF-1.4 signed")}).status_code == 200
    g = office.graph()
    assert [d.props["kind"] for d in g.of("document") if d.deal == "marina-1204" and d.props["kind"].startswith("Form ")] == ["Form A", "Form B"]
    assert (tmp_path / agency_forms.signed_file("marina-1204", "A", signs[0].props["draft"])).read_bytes() == b"%PDF-1.4 signed"
    with pytest.raises(ValueError, match="signed with these terms"):
        desk_rules.set_terms(office, "marina-1204", {"rate_pct": 1}, by="omar")
    operations.submitted(office, sub.id, "joseph", "DLD-9")


def test_a_changed_price_sends_the_forms_back_and_new_ones_are_drafted(office, monkeypatch):
    from diwan import agency_forms
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    _convert(office, c)
    c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "both"})
    office.record_fact("marina-1204", "deal_term", "We agreed two point five in the end.", "Karim Haddad", amount_aed=2_500_000, replaces="F1")
    fs = agency_forms.forms(office.graph(), "marina-1204")
    assert [(f["form"], f["status"]) for f in fs] == [("A", "sent_back"), ("B", "sent_back"), ("A", "live"), ("B", "live")]
    assert len(agency_forms.unsigned(office.graph(), "marina-1204")) == 2
    assert "2,500,000" in c.get(f"/api/desk/forms/{fs[2]['draft']}.pdf").content.decode("latin-1")
    c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "buyer", "other": {"other_agency": "Rival Homes", "other_share_pct": 50}})
    live = [f["form"] for f in agency_forms.forms(office.graph(), "marina-1204") if f["status"] == "live"]
    assert live == ["B", "I"]  # changed terms send the unsigned forms back; the buyer's side needs Form B and Form I



# ---------- converting: the agreed price against the listing's (spec item 12) ----------

def test_converting_records_the_agreed_price_and_compares_it_with_the_listing(office, monkeypatch):
    from diwan.agents import finance
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    r = c.post("/api/desk/deals/marina-1204/stage", json={"by": "omar", "stage": "Offer accepted"})
    assert r.status_code == 400 and "agreed price" in r.json()["detail"]
    assert c.post("/api/desk/deals/marina-1204/convert", json={"by": "priya", "amount": 2_500_000}).status_code == 403
    r = c.post("/api/desk/deals/marina-1204/convert", json={"by": "omar", "amount": 2_500_000}).json()
    assert (r["listing_aed"], r["pct"], r["diff"], r["needs_owner"], r["waiting"]) == (2_600_000, -3.8, -100_000, False, None)
    g = office.graph()
    assert g.nodes["deal:marina-1204"].props["stage"] == "Offer accepted"
    price = finance.commission(g, "marina-1204")
    assert price["base"] == 2_500_000 and g.nodes[price["fact"]].props["replaces"] == ["F1"]
    assert c.post("/api/desk/deals/marina-1204/convert", json={"by": "omar", "amount": 2_400_000}).status_code == 400
    assert c.get("/api/desk/kpis").json()["pricing"]["brokers"]["Omar"] == {"avg_pct": -3.8, "n": 1}


def test_a_discount_above_the_limit_waits_for_the_owner(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    r = c.post("/api/desk/deals/marina-1204/convert", json={"by": "omar", "amount": 2_400_000}).json()
    assert r["needs_owner"] and r["waiting"] == "Layla" and r["pct"] == -7.7
    g = office.graph()
    assert (g.nodes["deal:marina-1204"].props.get("stage") or "New") != "Offer accepted"
    ask = next(x for x in c.get("/api/desk/work?person=layla").json()["items"] if x["act"] == "discount")
    assert c.post(f"/api/desk/tasks/{ask['id']}/discount", json={"by": "omar", "approve": True}).status_code == 403
    assert c.post(f"/api/desk/tasks/{ask['id']}/discount", json={"by": "layla", "approve": False}).status_code == 400  # say why
    assert c.post(f"/api/desk/tasks/{ask['id']}/discount", json={"by": "layla", "approve": True}).json()["ok"]
    g = office.graph()
    assert g.nodes["deal:marina-1204"].props["stage"] == "Offer accepted" and g.settings["deal:marina-1204"]["agreed"]["approved_by"] == "layla"


def test_a_refused_discount_goes_back_to_the_broker_and_nothing_moves(office):
    from diwan import desk_stages
    desk_stages.convert(office, "marina-1204", "omar", 2_300_000)
    t = next(t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "discount")
    desk_stages.decide_discount(office, t.id, "layla", False, "The seller won't go under 2.45M")
    g = office.graph()
    assert not desk_stages.agreed(g, "marina-1204")
    assert any(q.props.get("kind") == "discount" and "2.45M" in q.props["text"] for q in g.of("question", "marina-1204", "open"))
    assert desk_stages.convert(office, "marina-1204", "omar", 2_480_000)["waiting"] is None  # 4.6%: within the limit


# ---------- signing a form online (spec item 13) ----------

def _png(w=400, h=120):
    import io
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).line([(20, 90), (120, 30), (200, 95), (380, 25)], fill="navy", width=6)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _form_b(office, c):
    _convert(office, c)
    c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "both"})
    return next(f for f in __import__("diwan.agency_forms", fromlist=["x"]).forms(office.graph(), "marina-1204") if f["form"] == "B")


def test_each_signer_gets_a_link_and_the_form_is_filed_when_all_have_signed(office, monkeypatch, tmp_path):
    from diwan.providers import meta
    monkeypatch.setattr(appmod.S, "office", office)
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    c = TestClient(appmod.app)
    b = _form_b(office, c)
    assert c.post(f"/api/desk/forms/{b['draft']}/links", json={"by": "priya"}).status_code == 403
    links = c.post(f"/api/desk/forms/{b['draft']}/links", json={"by": "omar"}).json()["links"]
    assert [(x["signer"], x["name"], x["status"]) for x in links] == [("buyer", "Karim Haddad", "open"), ("broker", "Omar", "open")]
    t = [x["url"].split("t=")[1] for x in links]
    page = c.get(f"/api/sign/{t[0]}").json()
    assert page["status"] == "open" and page["as"] == "The buyer" and any(r["value"] and "2,600,000" in r["value"] for r in page["rows"])
    form = {"full_name": "Karim Haddad", "id_no": "784-1990-1234567-1", "consent": "1"}
    assert c.post(f"/api/sign/{t[0]}", data=form | {"consent": ""}, files={"image": ("s.png", _png())}).status_code == 400
    assert c.post(f"/api/sign/{t[0]}", data=form, files={"image": ("s.txt", b"not an image")}).status_code == 400
    assert c.post(f"/api/sign/{t[0]}", data=form, files={"image": ("s.png", _png(60, 20))}).status_code == 400  # too small to show
    assert c.post(f"/api/sign/{t[0]}", data=form, files={"image": ("s.png", _png())}).json() == {"status": "signed", "complete": False}
    assert c.post(f"/api/sign/{t[0]}", data=form, files={"image": ("s.png", _png())}).status_code == 400  # once
    assert c.post(f"/api/sign/{t[1]}", data=form | {"full_name": "Omar Saeed"}, files={"image": ("s.png", _png())}).json()["complete"]
    g = office.graph()
    task = g.nodes[b["task"]]
    assert task.status == "done" and task.props["result"] == "signed"
    from diwan import agency_forms
    pdf = (tmp_path / agency_forms.signed_file("marina-1204", "B", b["draft"])).read_bytes()
    assert pdf.startswith(b"%PDF") and b"/DCTDecode" in pdf and b"Signing record" in pdf and b"784-1990-1234567-1" in pdf
    assert c.get("/api/sign/nope").status_code == 404


def test_a_replaced_or_expired_link_cannot_be_signed(office, monkeypatch, tmp_path):
    from datetime import date, timedelta
    from diwan import signing
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    b = _form_b(office, c)
    tok = [x["url"].split("t=")[1] for x in c.post(f"/api/desk/forms/{b['draft']}/links", json={"by": "omar"}).json()["links"]]
    late = date.today() + timedelta(days=15)
    with pytest.raises(ValueError, match="expired"):
        signing.sign(office, tok[0], full_name="K", id_no="1", consent=True, image=_png(), ip="", device="", media=tmp_path, today=late)
    live = office.graph().facts("marina-1204", "deal_term")[-1].id
    office.record_fact("marina-1204", "deal_term", "We agreed two point five in the end.", "Karim Haddad", amount_aed=2_500_000, replaces=live)
    assert c.get(f"/api/sign/{tok[0]}").json()["status"] == "replaced"
    with pytest.raises(ValueError, match="replaced"):
        signing.sign(office, tok[0], full_name="K", id_no="1", consent=True, image=_png(), ip="", device="", media=tmp_path, today=date.today())


# ---------- the documents a client sends (spec item 14) ----------

def _card(w=1000, h=630, blur=0, dark=False, seed=1):
    import io
    import random
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(seed)
    im = Image.new("RGB", (w, h), (20, 20, 20) if dark else (232, 236, 240))
    d = ImageDraw.Draw(im)
    for i in range(14):
        y = 40 + i * 40
        d.rectangle([40, y, 40 + rnd.randint(200, 900), y + 14], fill=(30, 30, 60) if not dark else (35, 35, 35))
    d.rectangle([w - 260, 60, w - 60, 300], outline=(10, 10, 10), width=4)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=90)
    return b.getvalue()


def _eid(body="78419901234567"):
    from diwan.documents import _luhn
    d = next(str(c) for c in range(10) if _luhn(body + str(c)))
    return f"{body[:3]}-{body[3:7]}-{body[7:14]}-{d}"


def _docs(office, c):
    _convert(office, c)
    c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "both"})
    from diwan import documents
    return {r["party"]: r for r in documents.requests(office.log.list(), "marina-1204")}


def test_conversion_asks_each_party_on_our_side_for_their_documents(office, monkeypatch):
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    reqs = _docs(office, c)
    assert set(reqs) == {"buyer", "seller"} and reqs["buyer"]["kinds"] == ["eid_front", "eid_back", "passport", "visa"] and "title_deed" in reqs["seller"]["kinds"]
    p = c.get(f"/api/docs/{reqs['buyer']['token']}").json()
    assert p["name"] == "Karim Haddad" and [d["status"] for d in p["docs"]] == ["needed"] * 4 and not p["done"]


def test_a_bad_upload_is_turned_away_with_the_reason_and_never_kept(office, monkeypatch, tmp_path):
    from diwan.providers import meta
    monkeypatch.setattr(appmod.S, "office", office)
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    c = TestClient(appmod.app)
    tok = _docs(office, c)["buyer"]["token"]
    good = {"number": _eid(), "name": "Karim Haddad", "expiry": "2029-05-01"}
    up = lambda data, fields=good, kind="eid_front": c.post(f"/api/docs/{tok}", data={"kind": kind, "fields": __import__("json").dumps(fields)},  # noqa: E731
                                                          files={"file": ("id.jpg", data)})
    for data, fields, why in [(b"hello", good, "photo (JPEG or PNG) or a PDF"), (_card(300, 200), good, "too small"), (_card(blur=8), good, "blurry"),
                              (_card(dark=True), good, "too dark"), (_card(), good | {"number": "123"}, "starts with 784"),
                              (_card(), good | {"expiry": "2020-01-01"}, "expired")]:
        r = up(data, fields)
        assert r.status_code == 400 and why in r.json()["detail"], (why, r.json())
    assert not list(tmp_path.iterdir())  # nothing turned away was kept
    assert up(_card()).status_code == 200
    r = up(_card(), kind="eid_back", fields={})
    assert r.status_code == 400 and "same file as your emirates id, front" in r.json()["detail"]
    assert up(_card(seed=2), kind="eid_back", fields={}).json()["left"] == ["Passport photo page", "Residence visa"]


def test_the_compliance_officer_confirms_into_the_clients_file_and_the_archive(office, monkeypatch, tmp_path):
    from diwan import documents
    from diwan.providers import meta
    monkeypatch.setattr(appmod.S, "office", office)
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    c = TestClient(appmod.app)
    tok = _docs(office, c)["buyer"]["token"]
    c.post(f"/api/docs/{tok}", data={"kind": "eid_front", "fields": __import__("json").dumps({"number": _eid(), "name": "K. Haddad Sr", "expiry": "2029-05-01"})},
           files={"file": ("id.jpg", _card())})
    t = next(t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "doc")
    assert "the name on the card (K. Haddad Sr) differs from the deal's (Karim Haddad)" in t.props["action"]  # for Priya to look at, not a refusal
    assert any(x["id"] == t.id for x in c.get("/api/desk/work?person=priya").json()["items"])
    assert c.post(f"/api/desk/tasks/{t.id}/doc", json={"by": "omar", "ok": True}).status_code == 403
    assert c.post(f"/api/desk/tasks/{t.id}/doc", json={"by": "priya", "ok": False}).status_code == 400  # say what to fix
    doc = c.post(f"/api/desk/tasks/{t.id}/doc", json={"by": "priya", "ok": True}).json()["document"]
    g = office.graph()
    assert g.nodes[doc].props["kind"] == "Emirates ID, front" and g.nodes[doc].props["deal"] == "marina-1204"
    prof = documents.profile(office.log.list(), "marina-1204")
    assert prof["buyer"]["details"]["Emirates ID, front"]["number"] == _eid() and prof["buyer"]["details"]["Emirates ID, front"]["confirmed_by"] == "Priya"


def test_a_sent_back_document_shows_the_client_why_and_can_be_sent_again(office, monkeypatch, tmp_path):
    from diwan.providers import meta
    monkeypatch.setattr(appmod.S, "office", office)
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    c = TestClient(appmod.app)
    tok = _docs(office, c)["buyer"]["token"]
    c.post(f"/api/docs/{tok}", data={"kind": "passport", "fields": '{"number": "N1234567", "expiry": "2030-01-01"}'}, files={"file": ("p.jpg", _card())})
    t = next(t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "doc")
    c.post(f"/api/desk/tasks/{t.id}/doc", json={"by": "priya", "ok": False, "note": "The photo page is cut off at the bottom"})
    d = next(x for x in c.get(f"/api/docs/{tok}").json()["docs"] if x["kind"] == "passport")
    assert d["status"] == "again" and d["reason"] == "The photo page is cut off at the bottom"
    assert c.post(f"/api/docs/{tok}", data={"kind": "passport", "fields": '{"number": "N1234567", "expiry": "2030-01-01"}'},
                  files={"file": ("p.jpg", _card(seed=3))}).status_code == 200


def test_rania_reminds_every_two_days_in_the_daytime_then_the_broker_calls(office, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from diwan import documents
    sent = []
    monkeypatch.setattr("diwan.agents.reception._send", lambda office, phone, deal, text, refs, **kw: sent.append((phone, text)))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://diwan.example")
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    _docs(office, c)
    office.log.append("docs.requested", actor="ops", deal="jvc-88", content={"token": "tok-sara", "party": "tenant", "name": "Sara Malik",
                                                                           "kinds": ["eid_front"], "phone": "971500000088", "expires": "2099-01-01"})
    dubai = timezone(timedelta(hours=4))
    start = (datetime.now(dubai) + timedelta(days=1)).replace(hour=10)  # the morning after the links were made
    assert documents.sweep(office, start) == 0  # just asked
    assert documents.sweep(office, start.replace(hour=23) + timedelta(days=3)) == 0  # never at night
    for day in (2, 4, 6):
        documents.sweep(office, start + timedelta(days=day, minutes=1))
    sara = [t for _, t in sent if "Hi Sara" in t]
    assert len(sara) == 3 and "https://diwan.example/web/docs.html?t=tok-sara" in sara[0] and "screen" not in sara[0].lower()
    documents.sweep(office, start + timedelta(days=8, minutes=1))
    call = [t for t in office.graph().of("task", "jvc-88") if t.props.get("step") == "docs_call"]
    assert len(call) == 1 and call[0].props["needs_person"] == "omar" and "3 reminders" in call[0].props["action"]
    karim = [t for t in office.graph().of("task", "marina-1204") if t.props.get("step") == "docs_call"]
    assert len(karim) == 2 and all("no WhatsApp on file" in t.props["action"] for t in karim)  # the demo deal has no chat: the broker sends it



# ---------- tax invoices and receipts as PDFs (spec item 15) ----------

def test_diwan_numbers_its_invoices_in_one_sequence_and_prints_the_tax_invoice(office, monkeypatch):
    from datetime import date
    from diwan.agents import finance
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    desk_rules.save(office, edited(office, agency={"name": "Diwan Realty", "orn": "ORN-12345", "address": "Office 1204, Marina Plaza, Dubai", "trn": "100234567800003"}),
                    by="layla")
    finance.draft_invoice(office, "marina-1204", "ahmed")
    send = next(t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "inv")
    draft = c.get(f"/api/desk/invoices/{send.id}.pdf").content.decode("latin-1")
    assert "Tax invoice \\(draft: not issued\\)" in draft and "100234567800003" in draft
    collect = c.post(f"/api/desk/tasks/{send.id}/invoiced", json={"by": "ahmed"}).json()["task"]
    num = office.graph().nodes[collect].props["invoice"]
    assert num == f"INV-{date.today().year}-0001"
    pdf = c.get(f"/api/desk/invoices/{collect}.pdf")
    t = pdf.content.decode("latin-1")
    assert pdf.headers["content-type"] == "application/pdf" and num in t and "Karim Haddad" in t and "AED 52,000.00" in t and "AED 2,600.00" in t and "AED 54,600.00" in t
    finance.draft_invoice(office, "jvc-88", "ahmed")
    send2 = next(t for t in office.graph().of("task", "jvc-88") if t.props["agent"] == "inv")
    assert c.post(f"/api/desk/tasks/{send2.id}/invoiced", json={"by": "ahmed", "number": num}).status_code == 400  # never reused
    nxt = c.post(f"/api/desk/tasks/{send2.id}/invoiced", json={"by": "ahmed"}).json()["task"]
    assert office.graph().nodes[nxt].props["invoice"].endswith("-0002")
    assert c.get(f"/api/desk/receipts/{collect}.pdf").status_code == 404  # nothing received yet
    c.post(f"/api/desk/tasks/{collect}/commission", json={"by": "ahmed", "reference": "ENBD 9001"})
    r = c.get(f"/api/desk/receipts/{collect}.pdf").content.decode("latin-1")
    assert f"RCT-{collect}" in r and "ENBD 9001" in r and "AED 54,600.00" in r



# ---------- the IDs given at signing, fees, and Form F signed online ----------

def test_the_owners_fees_show_with_who_pays_them(office):
    from diwan.agents import finance
    c = finance.commission(office.graph(), "marina-1204")
    assert [(f["what"], f["aed"], f["payer"]) for f in c["fees"]] == [("DLD fee 4%", 104_000, "buyer"),
                                                                      ("Trustee office fee (price AED 500,000 or more), plus VAT", 4000, "buyer")]
    with pytest.raises(ValueError, match="each fee"):
        desk_rules.save(office, edited(office, paths__rent__fees=[["Ejari", -1, "tenant"]]), by="layla")


def test_form_f_is_signed_online_by_everyone_then_filed_and_its_step_ticks(office, monkeypatch, tmp_path):
    from diwan import agency_forms
    from diwan.agents import operations
    from diwan.providers import meta
    monkeypatch.setattr(appmod.S, "office", office)
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    c = TestClient(appmod.app)
    _convert(office, c)
    c.post("/api/desk/deals/marina-1204/sides", json={"by": "omar", "sides": "both"})
    for f in agency_forms.forms(office.graph(), "marina-1204"):  # A and B signed on paper
        c.post(f"/api/desk/tasks/{f['task']}/signed", data={"by": "omar"}, files={"file": ("s.pdf", b"%PDF-1.4 signed")})
    operations.formf_plan(office, "marina-1204", office.add_task("marina-1204", "formf", "Prepare Form F"), "r1")
    sub = next(t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "formf" and t.props.get("draft"))
    operations.submitted(office, sub.id, "joseph", "DLD-1")
    did = sub.props["draft"]
    links = c.post(f"/api/desk/forms/{did}/links", json={"by": "omar"}).json()["links"]
    assert [x["signer"] for x in links] == ["buyer", "seller", "broker"]  # no other agency on this deal
    assert c.get(f"/api/desk/forms/{did}.pdf").content.startswith(b"%PDF")
    form = {"consent": "1"}
    for x, (who, idn) in zip(links, [("Karim Haddad", "784-1990-1234567-6"), ("Huda Al Mansoori", "P9988776"), ("Omar Saeed", "BRN-1")]):
        r = c.post(f"/api/sign/{x['url'].split('t=')[1]}", data=form | {"full_name": who, "id_no": idn}, files={"image": ("s.png", _png())})
    assert r.json()["complete"]
    g = office.graph()
    step = next(t for t in g.of("task", "marina-1204") if t.props.get("agent") == "transfer" and t.props["action"].startswith("Form F signed"))
    assert step.status == "done" and step.props["reason"] == "Signed online by everyone"
    signed = (tmp_path / f"deal-marina-1204-form-F-{did}-signed.pdf").read_bytes()
    assert b"Huda Al Mansoori" in signed and b"784-1990-1234567-6" in signed
    assert any(d.props["kind"] == "Form F" for d in g.of("document") if d.deal == "marina-1204")


def test_a_signers_id_fills_their_line_on_the_signed_form(office, monkeypatch, tmp_path):
    from diwan.providers import meta
    monkeypatch.setattr(appmod.S, "office", office)
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    c = TestClient(appmod.app)
    b = _form_b(office, c)
    for x in c.post(f"/api/desk/forms/{b['draft']}/links", json={"by": "omar"}).json()["links"]:
        c.post(f"/api/sign/{x['url'].split('t=')[1]}", data={"full_name": "Karim Haddad", "id_no": "784-1990-1234567-6", "consent": "1"},
               files={"image": ("s.png", _png())})
    from diwan import agency_forms
    pdf = (tmp_path / agency_forms.signed_file("marina-1204", "B", b["draft"])).read_bytes().decode("latin-1")
    line = pdf[pdf.index("Buyer's ID or passport number"):][:200]
    assert "784-1990-1234567-6" in line and "to fill" not in line
