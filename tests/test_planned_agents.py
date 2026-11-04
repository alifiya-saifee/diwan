from datetime import datetime, timedelta, timezone

import pytest

from diwan import brand, demo
from diwan.agents import custom, finance, operations
from diwan.agents.charters import ROSTER
from diwan.events import EventLog
from diwan.office import Office

CLEAN = "Supplier: Gulf Print LLC\nTRN: 100234567800003\nInvoice no: GP-2211\nDate: 2 Nov 2026\nNet: 4,000\nVAT: 200\nTotal: 4,200"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def acts(o, agent):
    return next(n for n in custom.connections(o)["nodes"] if n["id"] == f"agent:{agent}")["props"]["actions"]


def test_no_agent_is_planned_any_more():
    assert [c.name for c in ROSTER if c.status in ("planned", "parked")] == []


def test_positioning_keeps_the_sheet_when_the_owner_changes_it(office):
    brand.save(office, {"positioning": "We help families buy their first home in Dubai Marina.", "different": "We only sell homes we have visited ourselves."}, by="maya")
    ev = [e for e in office.log.list() if e["type"] == "positioning.updated"][-1]
    assert ev["agent"] == "mpos" and ev["content"]["different"].startswith("We only sell") and set(ev["content"]["changed"]) == {"positioning", "different"}
    assert "What makes us different: We only sell homes we have visited ourselves." in brand.brief(office)
    brand.save(office, {"voice": "warm"}, by="maya")  # not part of the sheet: no new sheet
    assert len([e for e in office.log.list() if e["type"] == "positioning.updated"]) == 1
    assert acts(office, "mpos") == 1


def _transfer_step(o, days_ago):
    tid = o.add_task("marina-1204", "transfer", "Developer NOC issued", needs_person="joseph", props={"waiting_on": "the developer", "before_gate": True})
    return tid, datetime.now(timezone.utc) + timedelta(days=days_ago)


def test_the_transfer_tracker_chases_a_late_step_once_a_day_and_sends_nothing(office):
    tid, later = _transfer_step(office, 4)
    assert operations.chase_late(office, later) == [tid]
    assert operations.chase_late(office, later) == []  # once a day
    ch = [e for e in office.log.list() if e["type"] == "transfer.chased"][0]
    assert ch["agent"] == "transfer" and ch["content"]["waiting_on"] == "the developer" and "Developer NOC issued" in ch["content"]["draft"]
    assert any(e["type"] == "nova.headsup" and e["content"]["to"] == "joseph" for e in office.log.list())
    assert not any(e["type"] in ("chat.sent", "email.sent") for e in office.log.list())
    assert operations.chase_late(office, later + timedelta(days=1)) == [tid]  # and again the next day


def test_a_step_not_yet_late_or_behind_the_gate_is_not_chased(office):
    _transfer_step(office, 1)
    assert operations.chase_late(office, datetime.now(timezone.utc) + timedelta(days=1)) == []
    gated = office.add_task("marina-1204", "transfer", "Trustee appointment booked", needs_person="joseph", props={"waiting_on": "the trustee office", "flag": "gate"})
    assert gated not in operations.chase_late(office, datetime.now(timezone.utc) + timedelta(days=9))  # behind the ready-for-transfer gate


def test_a_clean_supplier_invoice_goes_to_the_ledger(office):
    r = finance.check_supplier_invoice(office, CLEAN, by="ahmed")
    assert r["result"] == "ledger" and r["reasons"] == [] and r["trn"] == "100234567800003" and r["total"] == 4200
    assert acts(office, "inv") >= 1


@pytest.mark.parametrize("change, reason", [
    (("VAT: 200", "VAT: 300"), "isn't 5% of the net"),
    (("TRN: 100234567800003", "TRN: 1002345"), "isn't 15 digits"),
    (("Total: 4,200", "Total: 4,500"), "not the total"),
])
def test_a_wrong_supplier_invoice_is_held_with_its_reason(office, change, reason):
    r = finance.check_supplier_invoice(office, CLEAN.replace(*change), by="ahmed")
    assert r["result"] == "hold" and any(reason in x for x in r["reasons"])
    task = [e for e in office.log.list() if e["type"] == "task.created" and e["agent"] == "inv"][-1]
    assert task["content"]["needs_person"] == "ahmed" and "is held" in task["content"]["action"]


def test_the_same_supplier_invoice_twice_is_held_as_a_duplicate(office):
    finance.check_supplier_invoice(office, CLEAN, by="ahmed")
    r = finance.check_supplier_invoice(office, CLEAN, by="ahmed")
    assert r["result"] == "hold" and any("duplicate" in x for x in r["reasons"])
    with pytest.raises(ValueError):
        finance.check_supplier_invoice(office, "hi", by="ahmed")


def test_the_self_check_runs_every_scene_and_reaches_every_agent_that_needs_no_model():
    from diwan import selfcheck
    r = selfcheck.run()
    assert all(s["ok"] for s in r["scenes"]), [s for s in r["scenes"] if not s["ok"]]
    model_only = {"devil", "mbrand"}  # these two only act through a model; without one they rightly don't
    assert {a["id"] for a in r["agents"] if a["state"] == "not reached"} <= model_only, [a["name"] for a in r["agents"] if a["state"] == "not reached"]
    assert all(a["needs"] for a in r["agents"] if a["state"] == "needs")
