from datetime import datetime

import pytest

from diwan import demo, roles, slots
from diwan.agents import scribe, steps
from diwan.events import EventLog
from diwan.office import Office

MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=slots.DUBAI)
OMAR = "Ahmed will send you the payment plan by Thursday, and Joseph will book the trustee for next week."


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def meet(o, *turns, mid="M1"):
    o.start_meeting("marina-1204", mid, title="Deposit meeting")
    o.give_consent(mid, by="customer")
    for label, text in turns:
        scribe.turn(o, mid, label, text)
    o.end_meeting(mid)
    return steps.propose(o, mid, now=MONDAY)


def test_the_brokers_promises_become_tasks_with_owner_date_and_quote(office):
    s = meet(office, ("broker", OMAR))
    got = {i["owner"]: i for i in s["items"]}
    assert set(got) == {"ahmed", "joseph"}
    assert got["ahmed"]["action"] == "Send Karim the payment plan" and got["ahmed"]["due"] == "2026-11-05"
    assert got["joseph"]["action"] == "Book the trustee" and got["joseph"]["due"] == "2026-11-13"
    assert all(i["quote"] in OMAR and i["speaker"] == "Omar" for i in s["items"])


def test_nobody_named_is_listed_not_guessed(office):
    s = meet(office, ("broker", "Someone needs to check the parking."))
    assert s["items"] == [] and s["unclear"][0]["owner"] is None and "parking" in s["unclear"][0]["quote"]


def test_the_clients_promise_is_the_brokers_to_chase(office):
    s = meet(office, ("customer", "I'll send my passport tomorrow."))
    [i] = s["items"]
    assert i["owner"] == "omar" and i["action"] == "Check Karim does it: send my passport" and i["due"] == "2026-11-03"


def test_words_not_said_at_the_meeting_are_dropped_and_no_date_is_invented(office, monkeypatch):
    monkeypatch.setattr(steps, "rules", lambda turns: [{"action": "Send the plan", "owner_words": "Ahmed", "quote": "Ahmed will send the plan."},
                                                       {"action": "Book the trustee", "owner_words": "Joseph", "quote": "Joseph will book the trustee"}])
    s = meet(office, ("broker", "Joseph will book the trustee."))
    assert [(i["owner"], i["due"]) for i in s["items"]] == [("joseph", None)]


def test_work_withdrawn_during_the_meeting_is_listed(office):
    s = meet(office, ("broker", OMAR), ("customer", "Actually, forget my brother. I'll pay it all myself."))
    assert any("Tariq" in w["action"] for w in s["withdrawn"])


def test_approve_all_makes_each_task_once(office):
    s = meet(office, ("broker", OMAR))
    out = steps.approve(office, "M1", s["items"], by="omar")
    assert len(out["tasks"]) == 2
    again = steps.approve(office, "M1", s["items"], by="omar")
    assert again["duplicate"] and len([n for n in office.graph().of("task") if n.props["agent"] == "steps"]) == 2
    t = office.graph().nodes[out["tasks"][0]["id"]]
    assert t.props["needs_person"] == "ahmed" and t.props["quote"] and t.props["due"] == "2026-11-05" and t.props["meeting"] == "M1"


def test_edits_removals_additions_and_a_picked_owner_are_what_is_sent(office):
    s = meet(office, ("broker", OMAR + " Someone needs to check the parking."))
    rows = [s["items"][0] | {"action": "Email Karim the payment plan", "due": "2026-11-06"},  # edited; Joseph's removed
            {"action": "Ask the landlord about parking", "owner": "omar", "due": ""},       # added by hand
            s["unclear"][0] | {"owner": "joseph"}]                                            # unclear, given an owner
    out = steps.approve(office, "M1", rows, by="omar")
    assert [(t["owner"], t["action"]) for t in out["tasks"]] == [("ahmed", "Email Karim the payment plan"), ("omar", "Ask the landlord about parking"),
                                                                   ("joseph", s["unclear"][0]["action"])]
    with pytest.raises(KeyError):
        steps.approve(office, "M2", [], by="omar")  # no list for that meeting
    added = office.graph().nodes[out["tasks"][1]["id"]]
    assert added.props["added"] and added.props["due"] is None


def test_a_row_with_no_owner_is_refused(office):
    meet(office, ("broker", OMAR))
    with pytest.raises(ValueError, match="Choose who"):
        steps.approve(office, "M1", [{"action": "Do something", "owner": ""}], by="omar")


def test_the_owner_of_a_role_comes_from_the_team_settings(office):
    roles.assign(office, "finance", "joseph", by="layla")
    s = meet(office, ("broker", "Finance will send you the invoice by Thursday."))
    assert [i["owner"] for i in s["items"]] == ["joseph"]


def test_only_the_owner_or_the_office_owner_ticks_it(office):
    s = meet(office, ("broker", OMAR))
    tid = steps.approve(office, "M1", s["items"], by="omar")["tasks"][0]["id"]
    with pytest.raises(PermissionError):
        steps.done(office, tid, by="joseph")
    steps.done(office, tid, by="ahmed")
    assert office.graph().nodes[tid].status == "done"


def test_my_work_shows_the_task_to_its_owner_with_its_quote(office):
    from datetime import date
    from diwan.deal_desk import Ledger
    s = meet(office, ("broker", OMAR))
    steps.approve(office, "M1", s["items"], by="omar")
    mine = [w for w in Ledger(office.graph(), date(2026, 11, 2)).work() if w["kind"] == "From a meeting"]
    assert {(w["who"], w["act"]) for w in mine} == {("ahmed", "stepdone"), ("joseph", "stepdone")}
    assert all(w["text"].startswith('Omar: "') for w in mine)


def test_two_tasks_from_one_sentence_are_both_kept(office, monkeypatch):
    monkeypatch.setattr(steps, "rules", lambda turns: [{"action": "Send the payment plan by Thursday", "owner_words": "Ahmed", "quote": OMAR},
                                                       {"action": "Book the trustee for next week", "owner_words": "Joseph", "quote": OMAR}])
    s = meet(office, ("broker", OMAR))
    assert sorted(i["owner"] for i in s["items"]) == ["ahmed", "joseph"]


def test_money_the_client_said_is_left_to_the_payment_work(office):
    s = meet(office, ("broker", OMAR), ("customer", "Actually, forget my brother. I'll pay it all myself."))
    assert sorted(i["owner"] for i in s["items"]) == ["ahmed", "joseph"] and not s["unclear"]


def test_a_named_promise_the_model_left_out_is_still_listed(office, monkeypatch):
    from diwan.agents import runner
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: True)
    monkeypatch.setattr(runner, "call", lambda *a, **k: type("R", (), {"data": {"items": [{"action": "Book the trustee", "owner_words": "Joseph", "quote": OMAR}]},
                                                                       "usage": {"provider": "meta"}})())
    s = meet(office, ("broker", OMAR))
    assert sorted(i["owner"] for i in s["items"]) == ["ahmed", "joseph"] and s["by"] == "meta"
