"""A client who asks about one of our listings (the plan, item 6): the listing answers what it can, so Rania never asks
"buy or rent?" for a home that's for sale; a one-word "Cash" while qualifying is an answer, not a question for a person;
and Convert already knows which property it is."""
import re
from datetime import datetime

import pytest

from diwan import demo, inbox
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOON = datetime(2026, 11, 2, 12, tzinfo=DUBAI)
PH = "971508886666"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def say(office, text):
    return reception.message(office, PH, text, name_="Mona Saleh", now=NOON)


def test_asking_about_a_listing_answers_buy_area_type_and_bedrooms(office):
    say(office, "Hi, is MC-1204 still available?")
    replies = [say(office, t)["reply"] for t in ("To live in", "Budget is 2.7 million")]
    d = office.graph().nodes[f"deal:{office.graph().nodes[f'chat:{PH}'].deal}"].props
    assert d["qtype"] == "buyer" and {"areas", "property_type", "bedrooms"} <= set(d["answers"])
    assert not any(re.search(r"buy, rent|which area|how many bedrooms|type of property", r.lower()) for r in replies)


def test_a_one_word_cash_while_qualifying_is_an_answer(office):
    say(office, "Hi, is MC-1204 still available?")
    say(office, "To live in")
    r = say(office, "Cash")
    assert r["mode"] == "ai" and "personally" not in (r["reply"] or "")
    assert office.graph().nodes[f"chat:{PH}"].props["mode"] == "ai"


def test_convert_knows_the_listing_they_asked_about(office):
    say(office, "Hi, is MC-1204 still available?")
    assert inbox.detail(office, PH, NOON)["listing_hint"] == {"ref": "MC-1204", "title": "Unit 1204, Marina Crest"}



