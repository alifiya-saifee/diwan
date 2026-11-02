"""Dates Rania understands (docs/dates-spec.md): a written date is never ignored, and words that could mean two days are
asked about, never guessed."""
from datetime import date, datetime

import pytest

from diwan import demo, slots
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office

MON = datetime(2026, 11, 2, 11, tzinfo=slots.DUBAI)  # a Monday


@pytest.mark.parametrize("said, when", [
    ("10 Nov at 4pm", (11, 10, 16, 0)), ("10th of November at 4pm", (11, 10, 16, 0)), ("Nov 10 at 4pm", (11, 10, 16, 0)),
    ("November 10th at 4pm", (11, 10, 16, 0)), ("10/11 at 4pm", (11, 10, 16, 0)), ("on the 10th at 4pm", (11, 10, 16, 0)),
    ("Tuesday 10 Nov at 4pm", (11, 10, 16, 0)), ("Tuesday at noon", (11, 3, 12, 0)), ("Tuesday half past four", (11, 3, 16, 30)),
    ("quarter past 3 on the 10th", (11, 10, 15, 15)), ("quarter to 5 tomorrow", (11, 3, 16, 45)), ("Thursday at eleven o clock", (11, 5, 11, 0)),
    ("this weekend at 4pm", (11, 7, 16, 0)), ("busy Tuesday, Wednesday at 4pm works", (11, 4, 16, 0)),
    ("2 bed, tomorrow at 4", (11, 3, 16, 0)), ("3 million budget, Thursday at 11", (11, 5, 11, 0)),
])
def test_written_dates_and_times_in_words(said, when):
    t = slots.parse(said, MON)
    assert (t.month, t.day, t.hour, t.minute) == when


def test_a_date_already_past_is_next_year_and_the_10th_next_month_once_gone():
    assert slots.parse("1 Nov at 4pm", MON).date() == date(2027, 11, 1)
    assert slots.parse_day("the 1st", MON).date() == date(2026, 12, 1)


def test_counts_are_never_dates():
    assert slots.parse("a 2/3 bed in Marina", MON) is None
    assert slots.parse("may I see it?", MON) is None


def test_what_could_mean_two_days_is_asked():
    assert slots.which_day("Can I see it next Tuesday at 4pm?", MON) == [date(2026, 11, 3), date(2026, 11, 10)]
    assert slots.which_day("Wednesday 10 Nov at 4pm", MON) == [date(2026, 11, 10), date(2026, 11, 11)]  # the 10th is a Tuesday
    assert slots.which_day("Monday at 4pm", MON) == [date(2026, 11, 2), date(2026, 11, 9)]  # said on a Monday
    for clear in ("this Tuesday at 4pm", "Tuesday 10 Nov at 4pm", "Tuesday at 4pm", "tomorrow at 4pm", "10 Nov at 4pm"):
        assert slots.which_day(clear, MON) is None, clear


def test_their_answer_picks_one():
    opts = ["2026-11-03", "2026-11-10"]
    assert slots.answer_day("the second one", opts, MON) == date(2026, 11, 10)
    assert slots.answer_day("10 Nov please", opts, MON) == date(2026, 11, 10)
    assert slots.answer_day("first", opts, MON) == date(2026, 11, 3)
    assert slots.answer_day("Tuesday", opts, MON) is None  # both are Tuesdays: not an answer
    assert slots.with_day("Can I see MC-1204 next Tuesday at 4pm?", date(2026, 11, 10)) == "Can I see MC-1204 at 4pm? on Tuesday 10 Nov"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def say(office, text, ph="971501239999"):
    return reception.message(office, ph, text, name_="Sara Khan", now=MON)["reply"]


def visits(office):
    return [v.props["at"][:16] for v in office.graph().of("viewing", status="booked")]


def test_next_tuesday_is_asked_then_booked_on_the_day_they_chose(office):
    say(office, "Hi")
    r = say(office, "Can I see MC-1204 next Tuesday at 4pm?")
    assert r == "Just to be sure: do you mean Tuesday 3 Nov or Tuesday 10 Nov?" and not visits(office)
    r = say(office, "The second one")
    assert r.startswith("Booked: Unit 1204") and "Tuesday 10 Nov, 4:00 PM" in r and visits(office) == ["2026-11-10T16:00"]


def test_a_call_on_a_day_that_could_be_two_is_asked_then_booked(office):
    say(office, "Hi")
    r = say(office, "Please call me next Tuesday at 11")
    assert r.startswith("Just to be sure")
    r = say(office, "10 Nov")
    assert "Tuesday 10 Nov, 11:00 AM" in r and "call" in r.lower()


def test_a_written_date_books_that_date(office):
    say(office, "Hi")
    r = say(office, "Can I see MC-1204 on Tuesday 10 Nov at 4pm?")
    assert "Tuesday 10 Nov, 4:00 PM" in r and visits(office) == ["2026-11-10T16:00"]


def test_arabic_clients_are_asked_in_arabic(office):
    say(office, "مرحبا")
    r = say(office, "Can I see MC-1204 next Tuesday at 4pm? شكرا")
    assert r.startswith("للتأكد فقط")
