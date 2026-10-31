"""The Front Desk (docs/closed-loop-spec.md, Room 1): the day from the records, the arrival, the modes, meeting notes, errands that
wait for a yes, reminders, and a PA for each person that sees only what their role may see."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diwan import demo, leads
from diwan.agents import frontdesk, nova, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)
PH = "971501230000"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    leads.sync_listings(o, (Path(demo.__file__).parent / "demo_feed.xml").read_bytes(), by="demo-feed")
    frontdesk.PENDING.clear()
    return o


def client(office, text="call me", ph=PH, who="Sara Khan"):
    return reception.message(office, ph, text, name_=who, now=NOON)


def talk(office, text, person="layla", session="s"):
    return nova.converse(office, text, person, session=session, now=NOON)


def test_the_day_leads_with_what_is_urgent(office):
    client(office)
    d = frontdesk.day(office, "layla", NOON + timedelta(minutes=20))
    assert d["greeting"].startswith("Afternoon, Layla" if NOON.hour >= 12 else "Morning, Layla")
    u = d["urgent"][0]
    assert u["kind"] == "call" and u["late"] and "Sara Khan" in u["text"] and d["top"][0]["text"] == u["text"]
    assert set(d) >= {"today", "pipeline", "money", "decisions", "errands", "reminders", "mode"}


def test_today_shows_the_clients_last_words_and_what_they_care_about(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Cash", "Now", "To live in", "UAE resident", "I like it. Can I see it today at 5pm?"):
        client(office, t)
    d = frontdesk.day(office, "layla", NOON)
    assert d["today"] and "Can I see it" in d["today"][0]["last"] and "Marina" in d["today"][0]["cares"]


def test_the_day_ends_with_two_lines(office):
    client(office)
    assert frontdesk.day(office, "layla", NOON)["wrap"] is None
    w = frontdesk.day(office, "layla", NOON.replace(hour=18))["wrap"]
    assert w.startswith("Today: 0 closed") and "First thing tomorrow: Sara Khan" in w


def test_arrival_happens_once_a_day(office):
    assert frontdesk.arrive(office, "layla", NOON)["first"]
    assert not frontdesk.arrive(office, "layla", NOON + timedelta(hours=1))["first"]
    assert frontdesk.arrive(office, "layla", NOON + timedelta(days=1))["first"]


def test_the_owner_sees_the_pipeline_a_broker_does_not(office):
    assert frontdesk.day(office, "layla", NOON)["pipeline"]
    assert frontdesk.day(office, "omar", NOON)["pipeline"] is None and frontdesk.day(office, "omar", NOON)["money"] is None
    assert frontdesk.day(office, "ahmed", NOON)["money"]


def test_remind_me_is_a_task_with_a_time_and_reaches_the_person_once(office):
    r = talk(office, "Remind me Thursday to call Sara")
    assert r["kind"] == "done" and "Thursday" in r["text"]
    t = frontdesk.reminders(office.graph(), "layla")[0]
    assert t.props["action"] == "Call Sara" and datetime.fromisoformat(t.props["due"]).hour == 9
    at = datetime.fromisoformat(t.props["due"]) + timedelta(minutes=1)
    assert frontdesk.sweep(office, at - timedelta(hours=1)) == []
    assert frontdesk.sweep(office, at) == [f"reminded {t.id}"]
    assert frontdesk.sweep(office, at + timedelta(minutes=1)) == []
    frontdesk.finish_reminder(office, t.id, by="layla")
    assert not frontdesk.reminders(office.graph(), "layla")


def test_someone_elses_reminder_is_not_yours_to_finish(office):
    talk(office, "Remind me tomorrow at 10am to call Sara", person="omar")
    t = frontdesk.reminders(office.graph(), "omar")[0]
    with pytest.raises(PermissionError):
        frontdesk.finish_reminder(office, t.id, by="hamza")


def test_a_draft_waits_for_a_yes_and_nothing_is_sent(office):
    n = len(office.log.list())
    r = talk(office, "Draft a reply to Ahmed about the invoice")
    assert r["kind"] == "confirm" and "Ahmed" in r["text"] and frontdesk.errands(office, "layla")
    assert not [e for e in office.log.list()[n:] if e["type"] in ("chat.sent", "notify.sent")]
    assert talk(office, "yes")["text"].startswith("Approved.")
    assert not frontdesk.errands(office, "layla")


def test_a_draft_cancelled_is_gone(office):
    talk(office, "Email Karim about the viewing")
    assert "Cancelled" in talk(office, "no")["text"] and not frontdesk.errands(office, "layla")


def test_someone_elses_errand_cannot_be_confirmed(office):
    eid = talk(office, "Email Karim about the viewing")["errand"]
    with pytest.raises(KeyError):
        frontdesk.decide_errand(office, eid, by="omar", yes=True)


def test_travel_without_a_connection_says_so_and_books_nothing(office):
    r = talk(office, "Check ticket prices to London")
    assert r["kind"] == "unknown" and "Nothing was booked" in r["text"] and not frontdesk.errands(office, "layla")


@pytest.mark.parametrize("text,kind", [("Mark AED 50,000 received from Sara", "mark_received"), ("Clear the screening match for Karim", "clear_hit"),
                                       ("Send Sara our bank details", "send_bank_details"), ("Change the settings for follow-ups", "change_settings"),
                                       ("Sign the Form F for Karim", "sign")])
def test_what_only_a_person_may_do_is_refused_and_logged(office, text, kind):
    r = talk(office, text)
    assert r["kind"] == "refused"
    assert any(e["type"] == "agent.refused" and e["content"]["kind"] == kind for e in office.log.list())


def test_a_pa_never_changes_how_an_agent_runs(office):
    assert talk(office, "Set Rania to autopilot")["kind"] == "refused"


def test_who_has_not_called_back(office):
    client(office)
    r = talk(office, "Who hasn't called Sara back?")
    assert "owes Sara a call" in r["text"] and r["cites"]
    assert "Nobody owes" in talk(office, "Who hasn't called Ali back?")["text"]


def test_what_the_owner_relays_goes_on_the_file_after_a_yes(office):
    client(office, "I want to buy, 2 bed in Dubai Marina")
    r = talk(office, "Sara now wants 3 beds, not 2")
    assert r["kind"] == "confirm" and "Sara Khan" in r["text"]
    g = office.graph()
    deal = g.nodes[f"chat:{PH}"].deal
    assert g.nodes[f"deal:{deal}"].props["answers"]["bedrooms"]["value"] == 2  # nothing yet
    talk(office, "yes")
    assert office.graph().nodes[f"deal:{deal}"].props["answers"]["bedrooms"]["value"] == 3


def test_do_not_disturb_and_back(office):
    assert "Do not disturb is on" in talk(office, "Do not disturb")["text"]
    assert frontdesk.mode(office.graph(), "layla") == "dnd"
    talk(office, "I'm back")
    assert frontdesk.mode(office.graph(), "layla") == "normal"


def test_meeting_mode_is_silent_and_answers_only_to_its_name(office):
    client(office)
    assert "Listening" in talk(office, "Hey Pocket")["text"]
    assert talk(office, "We agreed to reduce the fee.")["kind"] == "silent"
    r = talk(office, "Hey Pocket, who hasn't called Sara back?")
    assert r["kind"] != "silent" and r["text"]


def test_after_the_meeting_decisions_and_action_items_with_the_exact_words(office):
    client(office, "I want to buy, 2 bed in Dubai Marina")
    talk(office, "I'm in a meeting")
    for t in ("We agreed to run the Marina campaign in November.", "Omar will call the developer by Thursday.", "Sara now wants 3 beds, not 2."):
        talk(office, t)
    r = talk(office, "Meeting is over")
    assert r["decisions"] == ["We agreed to run the Marina campaign in November."]
    assert r["actions"][0]["who"] == "Omar" and r["actions"][0]["quote"] == "Omar will call the developer by Thursday."
    g = office.graph()
    assert [c for c in g.of("lobby") if c.props["to"] == "omar"]  # a task in the right room
    assert frontdesk.mode(g, "layla") == "normal"
    deal = g.nodes[f"chat:{PH}"].deal
    assert g.nodes[f"deal:{deal}"].props["answers"]["bedrooms"]["value"] == 3  # what a client said goes on their file


def test_a_brokers_pa_sees_only_their_own_clients(office):
    client(office)
    client(office, "Hello", ph="971501230001", who="Ali Rahman")
    g = office.graph()
    mine = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    r = frontdesk.say(office, "What did Ali say?", mine, session="b", now=NOON)
    assert r["kind"] == "unknown" and "Not recorded" in r["text"] and r["pa"].endswith("'s PA")
    assert "Nobody owes" in frontdesk.say(office, "Who hasn't called Ali back?", mine, session="b", now=NOON)["text"]  # another broker's card stays out of it


def test_a_staff_pa_says_whats_waiting_on_them(office):
    client(office)
    g = office.graph()
    mine = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    r = frontdesk.say(office, "What's waiting on me?", mine, session="b", now=NOON)
    assert "Sara Khan" in r["text"]


def test_marketing_sees_no_deals(office):
    client(office)
    r = frontdesk.say(office, "Tell me about Sara", "maya", session="m", now=NOON)
    assert r["kind"] == "unknown"


def test_a_staff_pa_refuses_too_and_hands_work_through_the_board(office):
    assert frontdesk.say(office, "Mark AED 50,000 received", "omar", session="o", now=NOON)["kind"] == "refused"
    r = frontdesk.say(office, "Tell Finance the deposit came in by tomorrow", "omar", session="o", now=NOON)
    assert r["kind"] == "confirm"
    frontdesk.say(office, "yes", "omar", session="o", now=NOON)
    assert [c for c in office.graph().of("lobby") if c.props["to"] == "ahmed"]


def test_a_brokers_pa_books_and_sends_only_on_a_yes(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Cash", "Now", "To live in", "UAE resident"):
        client(office, t)
    g = office.graph()
    broker = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    n = len(office.graph().nodes[f"chat:{PH}"].props["messages"])
    r = frontdesk.say(office, "Send Sara the 3 closest options", broker, session="b", now=NOON)
    assert r["kind"] == "confirm" and len(office.graph().nodes[f"chat:{PH}"].props["messages"]) == n
    assert frontdesk.say(office, "yes", broker, session="b", now=NOON)["text"] == "Sent."
    assert len(office.graph().nodes[f"chat:{PH}"].props["messages"]) == n + 1


def test_the_sales_manager_can_ask_about_the_team(office):
    client(office)
    assert "Not recorded" in frontdesk.say(office, "Who's slowest to call back this week?", "rashid", session="r", now=NOON)["text"]
    r = frontdesk.say(office, "Give Omar's leads to Hamza", "rashid", session="r", now=NOON)
    assert r["kind"] == "confirm"
