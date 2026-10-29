"""The Deal desk (docs/deal-desk.md): what a person does after the correction, over HTTP."""
import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo
from diwan.events import EventLog
from diwan.office import Office


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
    assert [c["dept"] for c in v["cards"]][:2] == ["comp", "review"]
    assert {t["id"]: t["status"] for t in v["tasks"]} == {"T1": "withdrawn", "T2": "withdrawn", "T3": "queued"}
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
    assert [d["deal"] for d in client.get("/api/desk/deals?needs=true").json()["rows"]] == ["marina-1204"]
    assert client.get("/api/desk/deals?q=nobody").json()["total"] == 0
