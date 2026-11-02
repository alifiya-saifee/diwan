"""A promised call that nobody makes moves at most twice, never back to someone who missed it, then the Sales lead has it;
the client always hears who will call. A card due later than usual (a date the broker set, an owner to ask) only reaches
the Pool an hour after it is due (docs/viewing-access-spec.md, loop guard L1)."""
from datetime import datetime, timedelta

import pytest

from diwan import demo, leads, slots, viewings
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office

NOON = datetime(2026, 11, 2, 12, tzinfo=slots.DUBAI)  # a Monday
PH = "971501237777"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def card(office):
    return leads.open_card(office.graph(), PH)


def sent(office):
    return [m["text"] for m in office.graph().nodes[f"chat:{PH}"].props["messages"] if m["type"] == "sent"]


def test_a_missed_call_moves_twice_to_brokers_who_havent_missed_it_then_the_sales_lead(office):
    reception.message(office, PH, "Hi", name_="Ali Noor", now=NOON)
    reception.message(office, PH, "Can someone call me please?", now=NOON)
    first = card(office).props["who"]
    out = leads.sweep(office, NOON + timedelta(minutes=11))
    second = card(office).props["who"]
    assert out[-1] == f"moved {card(office).id} to {second}" and second != first
    assert sent(office)[-1] == f"Sorry for the wait, Ali. {second.capitalize()} will call you instead, in the next 10 minutes."
    leads.sweep(office, NOON + timedelta(minutes=22))
    third = card(office).props["who"]
    assert third not in (first, second)
    leads.sweep(office, NOON + timedelta(minutes=33))
    c = card(office)
    g = office.graph()
    assert c.props["who"] == "rashid" and c.props["to_lead"] and g.nodes[f"deal:{c.deal}"].props["broker"] == third  # the lead's broker stays
    assert sent(office)[-1].startswith("Sorry for the wait, Ali. Rashid will call you instead")
    assert leads.sweep(office, NOON + timedelta(minutes=44)) == [f"overdue {c.id}"]  # no further moves


def test_with_nobody_on_shift_it_waits_then_moves(office, monkeypatch):
    reception.message(office, PH, "Hi", name_="Ali Noor", now=NOON)
    reception.message(office, PH, "Can someone call me please?", now=NOON)
    first = card(office).props["who"]
    monkeypatch.setattr(leads, "on_shift", lambda g, b, now: b == first)  # only the one who is late is working
    assert leads.sweep(office, NOON + timedelta(minutes=11)) == [f"overdue {card(office).id}"]
    monkeypatch.undo()
    out = leads.sweep(office, NOON + timedelta(minutes=15))
    assert out and out[0].startswith(f"moved {card(office).id} to ") and card(office).props["who"] != first


def test_a_follow_up_date_reaches_the_pool_only_an_hour_after_it_is_due(office):
    reception.message(office, PH, "Hi", name_="Ali Noor", now=NOON)
    broker = office.graph().nodes[f"deal:{office.graph().nodes[f'chat:{PH}'].deal}"].props["broker"]
    at = NOON + timedelta(days=2)
    leads.follow_up_on(office, PH, by=broker, at=at, kind="call", note="after their trip", now=NOON)
    assert not any(x.startswith("pooled") for x in leads.sweep(office, NOON + timedelta(minutes=61)))
    assert not any(x.startswith("pooled") for x in leads.sweep(office, at + timedelta(minutes=30)))
    assert any(x.startswith("pooled") for x in leads.sweep(office, at + timedelta(minutes=61)))


def test_an_owner_check_is_not_pooled_before_it_is_due(office):
    reception.message(office, PH, "Hi", name_="Ali Noor", now=NOON)
    reception.message(office, PH, "Can I see JVC-88 on Tuesday at 4pm?", now=NOON)
    due = datetime.fromisoformat(card(office).props["due"])
    assert due == NOON + timedelta(minutes=viewings.settings(office.graph())["owner_minutes"])
    assert not any(x.startswith("pooled") for x in leads.sweep(office, NOON + timedelta(minutes=61)))
