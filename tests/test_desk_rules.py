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
    assert got[-1] == "Keys and access cards handed over" and len(got) == 6


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
    assert c.post(f"/api/desk/tasks/{send.id}/invoiced", json={"by": "ahmed"}).status_code == 400
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
