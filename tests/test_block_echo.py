"""Talking to Nova about the calendar: one day is blocked once, a known day asks only for the time, and a plain yes
with nothing waiting is never turned into work for a team."""
import re
from datetime import datetime

import pytest

from diwan import demo
from diwan.agents import nova
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOW = datetime(2026, 11, 3, 22, 0, tzinfo=DUBAI)


@pytest.fixture
def office(monkeypatch):
    monkeypatch.setenv("DIWAN_OFFLINE", "1")
    o = Office(EventLog(":memory:"))
    demo.seed(o)
    return o


def say(o, text, session="cal"):
    return nova.converse(o, text, "layla", session=session, now=NOW)


def days_off(o):
    return [b for b in o.graph().of("block", status="active") if b.props.get("kind") == "off"]


def test_tomorrow_asks_only_for_the_time(office):
    r = say(office, "Could you please block my calendar for tomorrow?")
    assert r["kind"] == "question" and "Wednesday 4 Nov" in r["text"] and "which day" not in r["text"].lower()
    assert say(office, "The whole day")["kind"] == "confirm"
    assert say(office, "Yes")["text"].startswith("Done.")
    assert len(days_off(office)) == 1


def test_a_day_is_never_blocked_twice(office):
    say(office, "Block all of Wednesday 4 Nov on your calendar as a day off")
    say(office, "Yes")
    again = say(office, "Block all of Wednesday 4 Nov on your calendar as a day off")
    assert "already blocked" in again["text"]
    say(office, "Yes")
    assert len(days_off(office)) == 1


@pytest.mark.parametrize("reply", ["Yes", "Yes, that's right", "No, never mind.", "ok"])
def test_a_plain_answer_with_nothing_waiting_is_not_work(office, reply):
    n = len(office.log.list())
    r = say(office, reply, session=f"s-{reply}")
    assert "nothing waiting" in r["text"]
    assert not [e for e in office.log.list()[n:] if e["type"] in ("lobby.posted", "task.created", "instruction.given")]


def test_a_real_request_after_yes_still_works(office):
    assert re.match(nova.BARE_REPLY, "Yes, I wanted to ask about Karim") is None
    r = say(office, "Tell Priya I need the Karim review tonight")
    assert r["kind"] == "confirm"
    assert say(office, "Yes")["kind"] == "done"
