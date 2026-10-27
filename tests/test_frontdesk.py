from datetime import datetime

import pytest

from diwan import demo, slots
from diwan.agents import lobby, nova
from diwan.events import EventLog
from diwan.office import Office

NOW = datetime(2026, 10, 28, 8, 45, tzinfo=slots.DUBAI)


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    demo.correction(o)
    return o


def talk(o, text, at=NOW):
    return nova.converse(o, text, "layla", session="s", now=at)


@pytest.mark.parametrize("words, when", [("by this evening", "2026-10-28T18:00"), ("by tomorrow at 10am", "2026-10-29T10:00"),
                                         ("by Thursday 3pm", "2026-10-29T15:00"), ("by noon", "2026-10-28T12:00"),
                                         ("by 4pm", "2026-10-28T16:00"), ("by tomorrow morning", "2026-10-29T10:00")])
def test_deadlines_in_words(words, when):
    assert lobby.due_from(f"Send it {words}", NOW)[0].isoformat().startswith(when)


def test_request_is_read_back_and_only_a_yes_posts_it(office):
    r = talk(office, "Tell Priya I need the Karim review ready by this evening")
    assert r["kind"] == "confirm" and r["text"] == 'So: Priya, "The Karim review", due Wednesday 28 Oct, 6:00 PM. Shall I send it?'
    assert not office.graph().of("lobby")
    r = talk(office, "yes")
    assert r["kind"] == "done" and r["card"] == "L1"
    g = office.graph()
    card = g.nodes["L1"]
    assert card.props["to"] == "priya" and card.props["team"] == "comp" and card.props["by"] == "layla"
    assert g.nodes[card.props["task"]].props["needs_person"] == "priya"
    evs = [(e["type"], e["agent"]) for e in office.log.list() if e["id"] >= card.event]
    assert evs[:4] == [("lobby.posted", "nova"), ("agent.pack", "nova"), ("agent.pack", "comp"), ("task.created", "comp")]


def test_no_deadline_asks_by_when_and_no_cancels(office):
    assert talk(office, "Ask Joseph to prepare Form F for Marina")["text"].startswith("By when should Joseph")
    assert "Thursday 29 Oct, 10:00 AM" in talk(office, "Tomorrow 10 AM")["text"]
    assert talk(office, "no")["text"] == "Cancelled. Nothing was sent."
    assert not office.graph().of("lobby")


def test_chased_before_due_late_after_and_the_asker_hears(office):
    talk(office, "Tell Priya I need the Karim review ready by this evening")
    talk(office, "yes")
    assert lobby.chase(office, NOW) == []
    assert lobby.chase(office, NOW.replace(hour=17, minute=5)) == ["reminded L1"]
    assert lobby.chase(office, NOW.replace(hour=17, minute=30)) == []
    assert lobby.chase(office, NOW.replace(hour=18, minute=1)) == ["late L1"]
    assert "Priya is late with" in nova.brief(office, "layla", now=NOW)["text"]
    assert "it is late" in nova.brief(office, "priya", now=NOW)["text"]


def test_done_closes_the_task_and_tells_whoever_asked(office):
    talk(office, "Get Ahmed to chase the deposit by 4pm")
    talk(office, "yes")
    lobby.done(office, "L1", by="ahmed")
    g = office.graph()
    assert g.nodes["L1"].status == "done" and g.nodes[g.nodes["L1"].props["task"]].status == "done"
    assert 'Ahmed finished "Chase the deposit"' in nova.brief(office, "layla", now=NOW)["text"]


def test_rounds_visit_every_lead_and_the_briefing_uses_their_reports(office):
    n = office.log.list()[-1]["id"]
    reports = nova.rounds(office, NOW)
    assert list(reports) == nova.LEADS
    evs = office.log.list(after=n)
    assert [e["agent"] for e in evs if e["type"] == "agent.pack"] == nova.LEADS
    assert all(e["caused_by"] == evs[0]["id"] for e in evs[1:])
    b = talk(office, "play the briefing")
    assert b["kind"] == "brief" and b["text"].startswith("Good morning, Layla.")
    assert "Compliance: Priya to review: payment arrangement changed." in b["text"]
    assert [d["lead"] for d in nova.brief(office, "priya", now=NOW)["departments"]] == ["comp"]


def test_briefing_time_is_set_by_talking_and_rounds_run_half_an_hour_before(office):
    assert "before 09:30" in talk(office, "Brief me at 9:30")["text"]
    assert nova.briefing_time(office.graph(), "layla") == "09:30"
    assert not nova.briefing_due(NOW.replace(hour=8, minute=59), None, "09:30", lead_minutes=30)
    assert nova.briefing_due(NOW.replace(hour=9, minute=0), None, "09:30", lead_minutes=30)
    assert not nova.briefing_due(NOW.replace(hour=9, minute=5), "2026-10-28", "09:30", lead_minutes=30)


def test_greeting_follows_the_clock(office):
    assert nova.brief(office, "omar", now=NOW.replace(hour=15))["text"].startswith("Good afternoon, Omar.")
    assert nova.brief(office, "omar", now=NOW.replace(hour=19))["text"].startswith("Good evening, Omar.")
