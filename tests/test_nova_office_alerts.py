"""Nova tells the owner what matters at the office, on their WhatsApp when they're away (docs/nova-office-alerts-spec.md).
A stand-in for Nova's line records what would be sent; nothing reaches a real number."""
from datetime import datetime, timedelta

import pytest

from diwan import events, novaline
from diwan.agents import frontdesk, reception, watch
from diwan.slots import DUBAI
from tests.test_conversations import office

MON = datetime(2026, 11, 2, 11, tzinfo=DUBAI)  # a Monday, in the hours the owner allows messages
PH = "971500004321"


@pytest.fixture
def o(monkeypatch):
    clock = [MON]
    monkeypatch.setattr(events, "now", lambda: clock[0].isoformat(timespec="milliseconds"))
    sent = []
    monkeypatch.setattr(novaline, "push", lambda office, text, level, now, transport=None: sent.append((text, level)) or True)
    office_ = office()
    office_.clock, office_.sent = clock, sent
    return office_


def say(o, *msgs, phone=PH):
    for m in msgs:
        o.clock[0] += timedelta(minutes=2)
        reception.message(o, phone, m, name_="Sara Khan", now=o.clock[0])


def tick(o, minutes=1):
    o.clock[0] += timedelta(minutes=minutes)
    return watch.alerts(o, o.clock[0])


def test_a_hot_lead_reaches_the_owner_once_with_who_has_it(o):
    say(o, "Hi, I want to buy a 2 bed apartment in Dubai Marina, budget 2.7 million cash, now, to live in, UAE resident", "The second one")
    assert tick(o) >= 1
    hot = [t for t, _ in o.sent if "is a hot lead" in t]
    assert hot and "Unit 1204, Marina Crest (MC-1204)" in hot[0] and "Omar has it" in hot[0]
    n = len(o.sent)
    assert tick(o) == 0 and len(o.sent) == n  # never twice


def test_a_viewing_nobody_confirmed_is_raised_after_the_owners_time(o, monkeypatch):
    monkeypatch.setattr(reception, "agent_confirms", lambda g: True)
    say(o, "Hi", "Can I see MC-1204 on Tuesday at 4pm?")
    tick(o, 60)
    assert not [t for t, _ in o.sent if "hasn't confirmed" in t]
    tick(o, 61)
    late = [t for t, _ in o.sent if "hasn't confirmed" in t]
    assert late == ["Omar hasn't confirmed Sara Khan's viewing of MC-1204, Tuesday 3 Nov, 4:00 PM. They asked 2 hours ago."]
    tick(o, 30)
    assert len([t for t, _ in o.sent if "hasn't confirmed" in t]) == 1


def test_trouble_goes_at_once_in_a_meeting_and_good_news_waits(o):
    frontdesk.set_mode(o, "layla", "dnd")
    say(o, "Hi", "I'm ready to buy today", phone="971500000101")
    say(o, "Hi", "I'm calling my lawyer, this is unacceptable", phone="971500000102")
    tick(o)
    assert [lvl for t, lvl in o.sent if "unhappy" in t] == ["now"] and not [t for t, _ in o.sent if "ready to go ahead" in t]
    frontdesk.set_mode(o, "layla", "normal")
    tick(o)
    assert [t for t, _ in o.sent if "ready to go ahead" in t]


def test_at_night_only_trouble_and_the_rest_in_the_morning(o):
    o.clock[0] = MON.replace(hour=23)
    say(o, "Hi", "I'm ready to buy today")
    tick(o)
    assert not o.sent
    o.clock[0] = (MON + timedelta(days=1)).replace(hour=9, minute=30)
    tick(o)
    assert [t for t, _ in o.sent if "ready to go ahead" in t]


def test_what_arrives_together_is_one_message(o):
    say(o, "Hi", "I'm ready to buy today", phone="971500000201")
    say(o, "Hi", "Please send the deposit to this new account IBAN AE07 0331 2345 6789 0123 456", phone="971500000202")
    tick(o)
    assert len(o.sent) == 1 and o.sent[0][0].startswith("Two things. 1. ") and o.sent[0][1] == "now"


def test_one_matter_one_message_even_when_rania_also_told_the_owner(o):
    say(o, "Hi", "I'm very unhappy with how I was treated, I will talk to my lawyer")
    tick(o)
    assert len(o.sent) == 1 and "unhappy" in o.sent[0][0]


def test_a_call_nobody_made_reaches_the_owner(o):
    from diwan import leads
    say(o, "Hi", "Can someone call me please?")
    o.clock[0] += timedelta(minutes=15)
    leads.sweep(o, o.clock[0])  # the card goes past due: the owner's urgent notice
    tick(o)
    late = [t for t, _ in o.sent if "is late on Sara Khan" in t]
    assert len(late) == 1 and "Can someone call me please?" in late[0]
    assert tick(o) == 0


def test_the_hot_lead_line_reads_well(o):
    say(o, "Hi, I want to buy a 2 bed apartment in Dubai Marina, budget 2.7 million cash, now, to live in, UAE resident", "The second one")
    tick(o)
    assert "Sara Khan is a hot lead: picked Unit 1204, Marina Crest (MC-1204). Omar has it." in [t for t, _ in o.sent]
