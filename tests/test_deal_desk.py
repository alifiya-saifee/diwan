"""The Deal desk (docs/deal-desk.md): what a person does after the correction, over HTTP."""
import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo
from diwan.events import EventLog
from diwan.office import Office
from tests.helpers import clear_deal, sign_form_f


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(appmod.S, "office", Office(EventLog()))
    demo.seed(appmod.S.office)
    demo.correction(appmod.S.office)
    return TestClient(appmod.app)


def card(c, deal="marina-1204", agent="factcheck"):
    return next(x for x in c.get(f"/api/desk/deals/{deal}").json()["cards"] if x["agent"] == agent and x["status"] == "open")


def test_one_deal_shows_each_department_and_the_replaced_words(client):
    v = client.get("/api/desk/deals/marina-1204").json()
    f = {x["id"]: x for x in v["said"]}
    assert f["F3"]["status"] == "superseded" and f["F3"]["replaced_by"] == "F7" and f["F7"]["replaces"] == ["F2", "F3"]
    assert [c["dept"] for c in v["cards"] if c["status"] == "open"] == ["comp", "review"]
    assert {t["id"]: t["status"] for t in v["tasks"]} == {"T1": "queued", "T2": "withdrawn", "T3": "withdrawn", "T5": "queued"}
    assert v["approvals"][0]["stale"] == ["F3"] and v["drafts"][0]["status"] == "sent_back"
    assert client.get("/api/desk/deals/nope").status_code == 404


def test_stale_approval_cannot_run_and_only_its_approver_may_try(client):
    assert client.post("/api/desk/approvals/A1/execute", json={"by": "omar"}).status_code == 403
    r = client.post("/api/desk/approvals/A1/execute", json={"by": "ahmed"}).json()
    assert not r["ok"] and "F3" in r["because"]


def test_reapprove_rests_on_the_words_that_stand_now_and_runs_once(client):
    c = card(client)
    assert client.post(f"/api/desk/cards/{c['id']}/answer", json={"by": "layla", "choice": "Cancel"}).status_code == 403
    old = client.post(f"/api/desk/cards/{c['id']}/answer", json={"by": "ahmed", "choice": "Re-approve on the new facts", "action": c["approval"]})
    assert old.status_code == 400 and "old wording" in old.json()["detail"]
    r = client.post(f"/api/desk/cards/{c['id']}/answer",
                    json={"by": "ahmed", "choice": "Re-approve on the new facts", "action": "Accept the AED 260,000 deposit from Karim Haddad"})
    aid = r.json()["approval"]
    a = {x["id"]: x for x in client.get("/api/desk/deals/marina-1204").json()["approvals"]}
    assert [f["id"] for f in a[aid]["rests_on"]] == ["F7", "F4"] and a["A1"]["status"] == "refused"
    assert client.post(f"/api/desk/approvals/{aid}/execute", json={"by": "ahmed"}).json()["ok"]
    assert client.post(f"/api/desk/approvals/{aid}/execute", json={"by": "ahmed"}).json()["duplicate"]
    assert client.post(f"/api/desk/cards/{c['id']}/answer", json={"by": "ahmed", "choice": "Cancel"}).status_code == 409


def test_compliance_check_is_marked_reviewed_by_the_officer_only(client):
    c = card(client, agent="comp")
    assert client.post(f"/api/desk/cards/{c['id']}/answer", json={"by": "ahmed", "choice": "Reviewed"}).status_code == 403
    assert client.post(f"/api/desk/cards/{c['id']}/answer", json={"by": "priya", "choice": "Reviewed", "note": "Karim's own account"}).json()["ok"]


def test_deals_list_searches_filters_and_pages(client):
    o = appmod.S.office
    for i in range(120):
        o.open_deal(f"bulk-{i}", property=f"Unit {i}, Test Tower", customer=f"Buyer {i}", broker="hamza")
    r = client.get("/api/desk/deals").json()
    assert r["total"] == 122 and r["pages"] == 3 and len(r["rows"]) == 50
    assert [d["deal"] for d in client.get("/api/desk/deals?q=karim").json()["rows"]] == ["marina-1204"]
    assert {d["deal"] for d in client.get("/api/desk/deals?needs=true").json()["rows"]} == {"marina-1204", "jvc-88"}
    assert client.get("/api/desk/deals?q=nobody").json()["total"] == 0


# ---------- Compliance ----------

@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def screens(o, deal="marina-1204"):
    return {t.props["person"]: t.status for t in o.graph().of("task", deal) if t.props["agent"] == "screen"}


def test_every_party_is_put_up_for_screening_once_and_withdrawn_with_the_words(office):
    assert screens(office) == {"Karim Haddad": "queued", "Tariq Haddad": "queued"}
    assert screens(office, "jvc-88") == {"Sara Malik": "queued"}
    demo.correction(office)
    assert screens(office) == {"Karim Haddad": "queued", "Tariq Haddad": "withdrawn"}


def test_a_payer_in_dispute_is_not_screened_until_the_broker_decides(office):
    office.record_fact("marina-1204", "payer", "My cousin covers it.", "Karim Haddad", payer="Sami")
    assert "Sami" not in screens(office)


def test_only_priya_records_a_result_and_a_possible_match_needs_its_entry(client):
    t = next(t for t in client.get("/api/desk/deals/marina-1204").json()["tasks"] if t["person"] == "Karim Haddad")
    assert client.post(f"/api/desk/tasks/{t['id']}/screen", json={"by": "ahmed", "result": "clear"}).status_code == 403
    assert client.post(f"/api/desk/tasks/{t['id']}/screen", json={"by": "priya", "result": "possible match"}).status_code == 400
    assert client.post(f"/api/desk/tasks/{t['id']}/screen", json={"by": "priya", "result": "clear", "note": "UN, UAE lists"}).json()["ok"]
    t = next(x for x in client.get("/api/desk/deals/marina-1204").json()["tasks"] if x["id"] == t["id"])
    assert t["status"] == "done" and t["result"] == "clear" and t["reason"] == "Clear: UN, UAE lists"
    assert client.post(f"/api/desk/tasks/{t['id']}/screen", json={"by": "priya", "result": "clear"}).status_code == 400


def test_source_of_funds_lays_out_the_numbers_and_the_missing_proof(client):
    f = client.get("/api/desk/deals/marina-1204").json()["funds"]
    assert [n["what"] for n in f["numbers"]] == ["Price", "Deposit", "Paid by", "Stated income", "Price in years of stated income"]
    assert f["numbers"][2]["value"] == "Karim Haddad" and f["numbers"][4]["value"] == "4.8"
    assert [p["kind"] for p in f["proof"]] == ["bank statement", "salary certificate", "balance funding"] and f["missing"] == 3
    pdf = {"file": ("s.pdf", b"%PDF-1.4 statement")}
    assert client.post("/api/desk/deals/marina-1204/proof", data={"by": "omar", "kind": "bank statement"}, files=pdf).status_code == 403
    assert client.post("/api/desk/deals/marina-1204/proof", data={"by": "priya", "kind": "bank statement"}, files={"file": ("s.txt", b"")}).status_code == 400  # a file is required
    doc = client.post("/api/desk/deals/marina-1204/proof", data={"by": "priya", "kind": "bank statement"}, files=pdf).json()["document"]
    f = client.get("/api/desk/deals/marina-1204").json()["funds"]
    assert f["proof"][0]["have"] == doc and f["missing"] == 2
    assert client.post("/api/desk/deals/marina-1204/proof", data={"by": "priya", "kind": "bank statement"}, files=pdf).status_code == 409


def test_cash_at_the_threshold_drafts_a_report_for_priya_and_a_correction_sends_it_back(office):
    m = "marina-1204"
    cash = office.record_fact(m, "payment_promise", "I'll bring the deposit in cash, two hundred sixty thousand.", "Karim Haddad",
                              amount_aed=260_000, method="cash", replaces="F4")
    g = office.graph()
    draft = next(d for d in g.of("draft", m) if d.props["kind"] == "cash report")
    task = next(t for t in g.of("task", m) if t.props["agent"] == "report")
    assert task.props["needs_person"] == "priya" and cash in task.props["rests_on"] and draft.status == "live"
    office.record_fact(m, "payment_promise", "No, the deposit goes by bank transfer after all.", "Karim Haddad",
                       amount_aed=260_000, method="bank transfer", replaces=cash)
    g = office.graph()
    assert g.nodes[draft.id].status == "sent_back" and g.nodes[task.id].status == "withdrawn"
    office.record_fact("jvc-88", "payment_promise", "Fifty thousand cash as the booking deposit.", "Sara Malik", amount_aed=50_000, method="cash")
    assert not [d for d in office.graph().of("draft", "jvc-88") if d.props["kind"] == "cash report"]


# ---------- Finance ----------

def test_due_dates_come_from_the_customers_words():
    from datetime import date
    from diwan.agents.finance import due_date
    thu = date(2026, 10, 29)
    assert due_date("next week", thu) == date(2026, 11, 5) and due_date("tomorrow", thu) == date(2026, 10, 30)
    assert due_date("on sunday", thu) == date(2026, 11, 1) and due_date("by thursday", thu) == date(2026, 11, 5)
    assert due_date(None, thu) is None and due_date("soon", thu) is None


def test_expected_payment_shows_its_day_and_turns_overdue(office):
    from datetime import date, timedelta
    from diwan.deal_desk import deal_view
    g = office.graph()
    pay = lambda v: next(t for t in v["tasks"] if t["agent"] == "pay")  # noqa: E731
    v = deal_view(g, "marina-1204")
    assert pay(v)["due_words"] == "next week" and not pay(v)["overdue"]
    late = date.today() + timedelta(days=10)
    assert pay(deal_view(g, "marina-1204", today=late))["overdue"]


def test_received_needs_ahmed_and_a_reference_and_files_a_receipt(client):
    tid = next(t["id"] for t in client.get("/api/desk/deals/marina-1204").json()["tasks"] if t["agent"] == "pay" and t["status"] == "queued")
    assert client.post(f"/api/desk/tasks/{tid}/received", json={"by": "omar", "reference": "x"}).status_code == 403
    assert client.post(f"/api/desk/tasks/{tid}/received", json={"by": "ahmed", "reference": " "}).status_code == 400
    doc = client.post(f"/api/desk/tasks/{tid}/received", json={"by": "ahmed", "reference": "ENBD 4471"}).json()["document"]
    g = appmod.S.office.graph()
    assert g.nodes[tid].props["result"] == "received" and g.nodes[doc].props["kind"] == "receipt" and g.nodes[doc].deal == "marina-1204"
    assert client.post(f"/api/desk/tasks/{tid}/received", json={"by": "ahmed", "reference": "again"}).status_code == 400


def test_a_release_approved_before_a_correction_is_refused_after_it(office):
    from datetime import date
    from diwan.agents import finance
    finance.mark_received(office, "T3", "ahmed", "ENBD 4471", today=date.today())
    clear_deal(office, "marina-1204")
    aid = finance.approve_release(office, "T3", "ahmed")
    import pytest as _p
    with _p.raises(ValueError):
        finance.approve_release(office, "T3", "ahmed")
    demo.correction(office)
    out = office.execute(aid, aid)
    assert not out["ok"] and "F3" in out["because"]
    assert any(c.props["refs"][0] == aid for c in office.graph().of("decision", "marina-1204", "open"))


# ---------- Operations and Review ----------

def test_form_f_plan_is_sent_back_by_a_correction_and_remade_from_the_live_words(office, monkeypatch):
    from diwan import desk_rules
    monkeypatch.setattr(appmod.S, "office", office)
    c = TestClient(appmod.app)
    assert "5 of 7 fields" in c.post("/api/desk/deals/marina-1204/formf", json={"by": "joseph"}).json()["text"]
    assert c.post("/api/desk/deals/marina-1204/formf", json={"by": "joseph"}).status_code == 409
    g = office.graph()
    plan = next(d for d in g.of("draft", "marina-1204") if d.props["kind"] == "Form F")
    sub = next(t for t in g.of("task", "marina-1204") if t.props.get("draft") == plan.id)
    assert set(sub.props["rests_on"]) == {"F1", "F4", "F3"} and sub.props["needs_person"] == "joseph"
    demo.correction(office)
    g = office.graph()
    assert g.nodes[plan.id].status == "sent_back" and g.nodes[sub.id].status == "withdrawn"
    new = [d for d in g.of("draft", "marina-1204") if d.props["kind"] == "Form F"][-1]
    assert new.status == "live" and "Deposit paid by: Karim Haddad" in [s.props["text"] for s in g.into(new.id, "part_of")]
    r = c.post(f"/api/desk/tasks/{sub.id}/submitted", json={"by": "joseph", "reference": "X"})
    assert r.status_code == 400 and "withdrawn" in r.json()["detail"]
    sub2 = next(t for t in g.of("task", "marina-1204") if t.props.get("draft") == new.id)
    assert c.post(f"/api/desk/tasks/{sub2.id}/submitted", json={"by": "omar", "reference": "X"}).status_code == 403
    assert c.post(f"/api/desk/tasks/{sub2.id}/submitted", json={"by": "joseph"}).status_code == 400
    clear_deal(office, "marina-1204")
    sign_form_f(office, new.id)
    assert c.post(f"/api/desk/tasks/{sub2.id}/submitted", json={"by": "joseph", "reference": "DLD-88123"}).json()["ok"]
    assert not [r for r in office.graph().of("request", "marina-1204", "open") if r.props.get("kind") == "submit"]
    steps = [t for t in office.graph().of("task", "marina-1204") if t.props["agent"] == "transfer"]
    assert [t.props["action"] for t in steps] == [s[0] for s in desk_rules.DEFAULTS["paths"]["ready"]["steps"]] and all(t.props["needs_person"] == "joseph" for t in steps)
    assert office.graph().nodes[steps[0].id].status == "done"  # Form F was signed before it was submitted
    assert c.post(f"/api/desk/tasks/{steps[1].id}/tick", json={"by": "omar"}).status_code == 403
    assert c.post(f"/api/desk/tasks/{steps[1].id}/tick", json={"by": "joseph"}).json()["ok"]


def test_a_draft_using_replaced_words_is_sent_back_the_moment_it_is_made(office):
    demo.correction(office)
    stale = office.make_draft("marina-1204", "deck", [{"n": 1, "text": "Deposit from Tariq", "facts": ["F3"]}])
    fresh = office.make_draft("marina-1204", "deck", [{"n": 1, "text": "Deposit from Karim", "facts": ["F7"]}])
    g = office.graph()
    assert g.nodes[stale].status == "sent_back" and "uses what F3 said" in g.nodes[stale].props["reason"] and "(F7)" in g.nodes[stale].props["reason"]
    assert g.nodes[fresh].status == "live"
    assert [e["content"]["draft"] for e in office.log.list() if e["type"] == "review.passed"][-1] == fresh


def test_funding_question_goes_to_the_broker_once_and_closes_when_the_customer_answers(office):
    from diwan.agents import compliance
    q = [c for c in office.graph().of("question", "jvc-88") if c.props.get("kind") == "funding"]
    assert len(q) == 1 and q[0].status == "open" and q[0].props["who"] == "omar"
    karim = [c for c in office.graph().of("question", "marina-1204") if c.props.get("kind") == "funding"]
    assert karim[0].status == "closed" and "(F5)" in karim[0].props["answer"]
    assert compliance.catch_up(office) == 0  # nothing missing: running it adds nothing


def test_catch_up_screens_deals_recorded_before_the_rule(monkeypatch):
    from diwan.agents import compliance
    o = Office(EventLog())
    monkeypatch.setattr(compliance, "screen_parties", lambda *a: None)  # an office from before screening existed
    monkeypatch.setattr(compliance, "ask_funding", lambda *a: None)
    demo.seed(o)
    monkeypatch.undo()
    assert not [t for t in o.graph().of("task") if t.props["agent"] == "screen"]
    assert compliance.catch_up(o) > 0
    assert {t.props["person"] for t in o.graph().of("task") if t.props["agent"] == "screen"} == {"Karim Haddad", "Tariq Haddad", "Sara Malik"}
    assert compliance.catch_up(o) == 0


# ---------- roles: work goes to whoever holds the role ----------

def test_only_the_owner_assigns_a_role_and_new_work_follows_the_holder(client):
    assert client.post("/api/desk/roles", json={"by": "priya", "role": "compliance", "person": "maya"}).status_code == 403
    assert client.post("/api/desk/roles", json={"by": "layla", "role": "compliance", "person": "nobody"}).status_code == 400
    table = client.post("/api/desk/roles", json={"by": "layla", "role": "compliance", "person": "maya"}).json()
    assert next(r for r in table if r["role"] == "compliance")["holder"] == "maya"
    o = appmod.S.office
    o.open_deal("d-new", property="Apt 9, Bay Square", customer="Noor Saleh", broker="omar")
    o.record_fact("d-new", "deal_term", "One point two for the apartment.", "Noor Saleh", amount_aed=1_200_000)
    t = next(t for t in o.graph().of("task", "d-new") if t.props["agent"] == "screen")
    assert t.props["needs_person"] == "maya"
    r = client.post(f"/api/desk/tasks/{t.id}/screen", json={"by": "priya", "result": "clear"})
    assert r.status_code == 403 and "Maya" in r.json()["detail"]
    assert client.post(f"/api/desk/tasks/{t.id}/screen", json={"by": "maya", "result": "clear", "note": "UN list"}).json()["ok"]
    q = client.get("/api/desk/work?person=maya").json()["items"]  # Priya's open work moved to Maya with the role
    assert {"Payment arrangement changed", "Screen Karim Haddad, the buyer"} <= {x["title"] for x in q}
    assert not client.get("/api/desk/work?person=priya").json()["items"]
    omar = {x["title"] for x in client.get("/api/desk/work?person=omar").json()["items"]}  # questions to the broker stay his
    assert {"How is Sara Malik funding the purchase? Compliance needs it before any money moves.",
            "How is Noor Saleh funding the purchase? Compliance needs it before any money moves."} == omar


def test_a_role_nobody_holds_says_so_instead_of_guessing(office, monkeypatch):
    from diwan import roles
    monkeypatch.setattr(roles, "PEOPLE", {k: v for k, v in roles.PEOPLE.items() if v["role"] != "Finance"})
    g = office.graph()
    assert roles.holder(g, "finance") is None and "nobody assigned" in roles.who(g, "finance")
    with pytest.raises(PermissionError, match="Nobody is the finance"):
        roles.check(g, "finance", "ahmed")
