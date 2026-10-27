from datetime import date

import pytest

from diwan import demo
from diwan.agents import nova, records
from diwan.events import EventLog
from diwan.office import Office

TODAY = date(2026, 10, 27)


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def test_periods():
    assert records.period("last month", TODAY)[:2] == (date(2026, 9, 1), date(2026, 9, 30))
    assert records.period("in Q3", TODAY)[:2] == (date(2026, 7, 1), date(2026, 9, 30))
    assert records.period("sales in August", TODAY)[2] == "August 2026"
    assert records.period("December", TODAY)[2] == "December 2025"
    assert records.period("how are we doing", TODAY) is None


def test_nova_hands_numbers_to_the_analyst_who_counts_records(office):
    n = office.log.list()[-1]["id"]
    r = nova.ask(office, "What were last month's sales?", today=TODAY)
    assert r["delegated_to"] == "analyst" and r["cites"] == ["S4", "S5", "S6"]
    assert "3 closed, AED 7,850,000 in value, AED 157,000 commission" in r["text"]
    assert [(e["type"], e["agent"]) for e in office.log.list(after=n)] == [
        ("agent.pack", "nova"), ("agent.pack", "records"), ("agent.started", "analyst"), ("agent.pack", "analyst")]
    pack = office.log.list()[-1]["content"]["pack"]
    assert [e["source"] for e in pack["evidence"]] == ["S4", "S5", "S6"] and not pack["rejected_quotes"]


def test_spending_and_documents_come_from_the_archive(office):
    assert "AED 42,680 across 4" in nova.ask(office, "What did we spend last month?", today=TODAY)["text"]
    r = nova.ask(office, "Find the contract for the JVC villa", today=TODAY)
    assert r["delegated_to"] == "archivist" and "MOU (Form F), Villa 31" in r["text"]
    assert "no receipts" in nova.ask(office, "Any receipts for July?", today=TODAY)["text"]


def test_no_period_means_a_question_not_a_guess(office):
    r = nova.ask(office, "How were sales?", today=TODAY)
    assert r["kind"] == "question" and "Which period" in r["text"]


def test_follow_up_questions_stay_on_the_deal_just_discussed(office):
    demo.correction(office)
    nova.ask(office, "Who is paying for Karim?", session="s")
    r = nova.ask(office, "And what changed?", session="s")
    assert "(F3) became" in r["text"]
    assert nova.ask(office, "And what changed?", session="other")["kind"] == "question"
