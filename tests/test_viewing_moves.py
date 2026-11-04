"""What a fresh review of 2 Nov found, kept as tests: a home asked for twice is one viewing, a move keeps every check, a held
viewing whose time has passed stops waiting, Arabic stays Arabic, and "Marina" or "may 2 of us" are never dates."""
from datetime import datetime, timedelta

import pytest

from diwan import slots, viewings
from diwan.agents import nudge, reception
from diwan.agents.scribe import amounts
from tests.test_conversations import MON, office

PH = "971500001234"


@pytest.fixture
def broker_confirms(monkeypatch):
    monkeypatch.setattr(reception, "agent_confirms", lambda g: True)


def chat(o, *msgs, start=MON):
    t, out = start, []
    for m in msgs:
        t += timedelta(minutes=2)
        out.append(reception.message(o, PH, m, name_="Sara Khan", now=t)["reply"])
    return out


def mine(o):
    return [v for v in o.graph().of("viewing") if v.props.get("chat") == PH]


def test_marina_and_may_are_not_months():
    assert slots.parse("Can I see the Marina 3 apartment tomorrow at 4pm?", MON).date() == (MON + timedelta(days=1)).date()
    assert slots.parse("Can I see 2 marina flats tomorrow at 4pm?", MON).date() == (MON + timedelta(days=1)).date()
    assert slots.parse("Tuesday at 4pm, may 2 of us come?", MON).date() == (MON + timedelta(days=1)).date()
    assert slots.parse("Can I see it on 3 May at 4pm?", MON).month == 5 and slots.parse("march 3 at 4pm", MON).month == 3


def test_a_listing_ref_is_never_an_amount():
    assert amounts("Can I see MC-1204 on Wednesday?") == [] and amounts("JVC-88 for 1.9M") == [1_900_000]


def test_the_same_home_again_moves_the_request(broker_confirms):
    o = office()
    r = chat(o, "Hi", "Can I see MC-1204 on Tuesday at 4pm?", "Can I see MC-1204 on Thursday at 5pm instead?", "thanks")
    assert len(mine(o)) == 1 and mine(o)[0].props["at"].startswith("2026-11-05T17:00")
    assert r[2] == "Done: I've asked for Thursday 5 Nov, 5:00 PM instead. Omar will confirm it with you."
    assert r[3] == "You're welcome, Sara! Omar will confirm Thursday 5 Nov, 5:00 PM with you."


def test_the_same_home_again_when_rania_books_moves_it_and_never_asks_the_budget():
    o = office()
    r = chat(o, "Hi", "Can I see MC-1204 on Tuesday at 4pm?", "Can I see MC-1204 on Wednesday at 11am?")
    assert len(mine(o)) == 1 and r[2].startswith("Done: your site visit to Unit 1204") and "budget" not in r[2]


def test_two_homes_held_are_both_on_the_brokers_card(broker_confirms):
    o = office()
    chat(o, "Hi", "Can I see MC-1204 on Tuesday at 4pm?", "Can I also see BB-305 on Wednesday at 11am?")
    card = next(a for a in o.graph().of("attention", status="open") if a.props["chat"] == PH)
    assert len(mine(o)) == 2 and "MC-1204" in card.props["reason"] and "BB-305" in card.props["reason"]


def test_moving_a_confirmed_viewing_keeps_the_gallery_hours(broker_confirms):
    o = office()
    viewings.set_access(o, "BB-305", {"mode": "developer", "place": "the Mallowby Square gallery", "open": "10:00", "close": "13:00",
                                      "days": [0, 1, 2, 3, 4, 5, 6]}, by="layla")
    chat(o, "Hi", "Can I see BB-305 on Tuesday at 11am?")
    v = mine(o)[0]
    viewings.answer(o, v.id, by=v.props["broker"], said="yes", now=MON + timedelta(minutes=10))
    r = chat(o, "Can we move it to Tuesday at 4pm?", start=MON + timedelta(minutes=20))[0]
    assert r.startswith("That time isn't free.") and o.graph().nodes[v.id].props["at"].startswith("2026-11-03T11:00")


def test_moving_a_lived_in_home_when_rania_books_asks_the_tenant_again():
    o = office()
    viewings.set_access(o, "JVC-88", {"mode": "ask", "who": "tenant", "notice_hours": 24}, by="layla")
    chat(o, "Hi", "Can I see JVC-88 on Wednesday at 4pm?")
    v = mine(o)[0]
    viewings.answer(o, v.id, by=v.props["broker"], said="yes", now=MON + timedelta(minutes=10))
    r = chat(o, "Can we move it to Thursday at 5pm?", start=MON + timedelta(minutes=20))[0]
    v = o.graph().nodes[v.id]
    assert v.status == "requested" and v.props["confirm"] == "tenant" and r.startswith("Done: I've asked for Thursday 5 Nov, 5:00 PM")


def test_a_held_viewing_whose_time_passed_stops_waiting(broker_confirms):
    o = office()
    chat(o, "Hi", "Can I see MC-1204 on Tuesday at 4pm?")
    g, later = o.graph(), datetime(2026, 11, 4, 11, tzinfo=slots.DUBAI)
    assert viewings.waiting(g, PH, later) is None
    assert nudge.why_not(g, g.nodes[f"chat:{PH}"], later) != "a viewing is waiting to be confirmed"
    r = chat(o, "Any news?", start=later)[0]
    assert "Tuesday 3 Nov" not in r


def test_arabic_thanks_and_a_companion_stay_arabic(broker_confirms):
    o = office()
    r = chat(o, "مرحبا", "Can I see MC-1204 on Tuesday at 4pm?", "شكرا")
    assert r[2].startswith("العفو!") and not any(w in r[2] for w in ("will", "confirm", "with you"))
