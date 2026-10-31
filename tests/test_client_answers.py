"""How Rania reads what a client really says (the product owner's test chat, 30 Oct): "off plan" with a "don't" about
ready made, a timing that depends on finding the right project, a question asked twice without a clear answer, a finance
question that is not a search, and an honest reply when nothing fits exactly."""
from datetime import datetime

import pytest

from diwan import demo, qualify
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOW = datetime(2026, 10, 30, 12, tzinfo=DUBAI)
PH = "971501112233"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    demo.catalog(o)
    return o


def say(office, text):
    return reception.message(office, PH, text, name_="Ali Rahman", now=NOW)


def answers(office):
    g = office.graph()
    return {k: v["value"] for k, v in g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props.get("answers", {}).items()}


def test_off_plan_with_a_dont_about_ready_is_off_plan():
    low = "i am looking for off plan mostly because of my budget i don't think ready made will be under this"
    assert [o for o in ("Ready", "Off-plan") if qualify.option_said(o, low)] == ["Off-plan"]
    assert qualify.option_said("Now", "as soon as possible") and not qualify.option_said("Ready", "not ready yet")


def test_timing_that_depends_on_the_project_is_not_sure_not_a_question_again(office):
    for t in ("I wanted to buy a property", "Dubai Marina", "Apartment", "2 bed", "Budget 2 million", "Mortgage"):
        say(office, t)
    r = say(office, "when I see nice project with good roi I can plan")
    assert answers(office)["timeline"] == "Not sure" and "When are you looking" not in r["reply"]
    assert "can't promise returns" not in r["reply"]  # a project with good ROI is what they want, not a guarantee asked for


def test_never_asked_a_third_time(office):
    for t in ("I wanted to buy a property", "Dubai Marina", "Apartment", "2 bed", "Budget 2 million", "Mortgage"):
        say(office, t)
    asks = sum("When are you looking" in say(office, t)["reply"] for t in ("do you have mortgage option?", "ok thanks", "hmm"))
    assert asks <= 1 and answers(office)["timeline"] == "Not sure"


def test_a_mortgage_question_is_not_a_property_search(office):
    for t in ("I wanted to buy a property", "Dubai Marina"):
        say(office, t)
    r = say(office, "do you have mortgage option?")
    assert "AED" not in r["reply"] and "Here's what fits" not in r["reply"]


def test_nothing_fits_exactly_she_says_so_and_shows_the_closest(office):
    for t in ("I wanted to buy a property", "I am not sure about the area yet", "Villa", "2 bedroom, budget 2 million", "Cash", "Now"):
        r = say(office, t)
    assert r["reply"].startswith("Thank you Ali! Omar will contact you shortly with options for a 2-bed villa around AED 2,000,000. "
                                 "Meanwhile, a few close ones you might like:") and "don't have" not in r["reply"]
    assert "(an apartment, not a villa)" in r["reply"]
    r = say(office, "I am looking for off plan mostly, I don't think ready made will fit my budget")
    assert answers(office)["ready_or_offplan"] == "Off-plan" and "DR-134" in r["reply"] and "DR-131" not in r["reply"]  # off-plan only now


def test_a_named_area_we_have_nothing_in_matches_nothing(office):
    for t in ("I want to buy", "Palm Jumeirah", "A villa", "4 bed", "Budget is 2 million", "Cash", "Now"):
        r = say(office, t)
    assert "in Palm Jumeirah" in r["reply"] and "JVC-88" not in r["reply"]


def test_a_mis_encoded_emoji_never_reaches_the_client():
    assert reception.clean_text("Perfect, happy to help you buy ð Which area?") == "Perfect, happy to help you buy Which area?"
    assert reception.clean_text("Hi ð\x9f\x98\x8a there") == "Hi 😊 there"
    assert reception.clean_text("مرحباً علي 😊 Café") == "مرحباً علي 😊 Café"


def test_a_call_at_a_time_they_choose_is_said_back_and_due_then(office):
    say(office, "I want to buy")
    r = reception.message(office, PH, "Could you please ask him to call me tomorrow at 10:00 instead I am busy now", name_="Ali Rahman",
                          now=datetime(2026, 10, 30, 20, 44, tzinfo=DUBAI))
    assert r["reply"] == "Of course Ali. I've booked a call with Omar for Saturday 31 Oct, 10:00 AM."
    [card] = office.graph().of("attention", status="open")
    assert card.props["due"].startswith("2026-10-31T10:00") and card.props["reason"].startswith("Call Saturday 31 Oct, 10:00 AM")
    r = reception.message(office, "971501112299", "can someone call me at 11pm tonight?", name_="Mona", now=datetime(2026, 10, 30, 17, tzinfo=DUBAI))
    assert "outside Hamza's working hours" in r["reply"] or "outside Omar's working hours" in r["reply"]


def test_any_options_once_qualified_never_says_we_dont_have_it(office):
    for t in ("I wanted to buy a property", "I am not sure about the area yet", "Villa", "2 bedroom, budget 2 million", "Mortgage", "Now",
              "I am looking for off plan mostly"):
        say(office, t)
    r = say(office, "do you have any options currently available")
    assert "will contact you shortly with options" in r["reply"] and "DR-134" in r["reply"] and "don't have" not in r["reply"]
    assert "say we have nothing listed" not in reception.GUIDE and "never say we don't have it" in reception.GUIDE


def test_texting_spellings_of_tomorrow_and_a_confirmation_of_the_call(office):
    from diwan import slots
    now = datetime(2026, 10, 30, 20, 58, tzinfo=DUBAI)
    want = datetime(2026, 10, 31, 10, tzinfo=DUBAI)
    for t in ("call me at 10 tmrw", "call me tmrw at 10", "call me 2moro at 10am", "call me tmr 10am", "tmrw 10", "tomorow at 10"):
        assert slots.parse(t, now) == want, t
    assert slots.parse("2 bed tomorrow", now) is None and slots.parse("budget 2 million tmrw", now) is None  # a count is not an hour
    say(office, "I want to buy")
    reception.message(office, PH, "Could you please ask him to call me tomorrow at 10:00 instead I am busy now", name_="Ali Rahman", now=now)
    r = reception.message(office, PH, "so he will call me at 10 tmrw?", name_="Ali Rahman", now=now)
    assert r["reply"] == "Yes Ali, Omar will call you Saturday 31 Oct, 10:00 AM."
    assert len(office.graph().of("attention", status="open")) == 1  # confirmed, not a second card


def test_a_call_asked_for_at_a_time_blocks_the_brokers_calendar(office):
    from diwan import slots
    now = datetime(2026, 10, 30, 20, 58, tzinfo=DUBAI)
    at = datetime(2026, 10, 31, 10, tzinfo=DUBAI)
    say(office, "I want to buy")
    reception.message(office, PH, "call me tmrw at 10", name_="Ali Rahman", now=now)
    g = office.graph()
    [v] = g.of("viewing", status="booked")
    assert v.props["kind_name"] == "Phone call" and v.props["where"] == "phone" and v.props["at"].startswith("2026-10-31T10:00") and v.props["broker"] == "omar"
    assert not slots.is_open(g, "omar", at, 15) and slots.is_open(g, "omar", at.replace(hour=11), 15)  # nothing else is booked over it
    assert g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props.get("stage") != "Viewing booked"  # a call is not a viewing
    assert [a["kind"] for a in slots.week(g, datetime(2026, 10, 26).date(), person="omar", now=now)["appointments"]] == ["Phone call"]
    r = reception.message(office, PH, "sorry, make it 12 instead", name_="Ali Rahman", now=now)  # a time alone: the same day
    assert "is now Saturday 31 Oct, 12:00 PM" in r["reply"]
    r = reception.message(office, PH, "sorry, make it tmrw at 11", name_="Ali Rahman", now=now)  # moves it, and the broker's card
    assert "is now Saturday 31 Oct, 11:00 AM" in r["reply"]
    [card] = office.graph().of("attention", status="open")
    assert card.props["due"].startswith("2026-10-31T11:00")
    r = reception.message(office, PH, "actually cancel the call please", name_="Ali Rahman", now=now)
    assert "cancelled your phone call" in r["reply"] and not office.graph().of("attention", status="open")


def test_a_call_when_the_broker_is_busy_offers_free_times_and_still_alerts_a_person(office):
    from diwan import slots
    now = datetime(2026, 10, 30, 20, 58, tzinfo=DUBAI)
    say(office, "I want to buy")
    slots.block(office, by="layla", broker="omar", start=datetime(2026, 10, 31, 10, tzinfo=DUBAI), end=datetime(2026, 10, 31, 12, tzinfo=DUBAI), reason="Dentist", now=now)
    r = reception.message(office, PH, "call me tmrw at 10", name_="Ali Rahman", now=now)
    assert "Omar isn't free then; Omar could call you Saturday 31 Oct, 12:00 PM" in r["reply"] and "Which suits you?" in r["reply"]
    assert not office.graph().of("viewing")  # nothing is booked in the busy time
    [card] = office.graph().of("attention", status="open")
    assert card.props["kind"] == "call" and not card.props["due"].startswith("2026-10-31T10:00")  # a person is still alerted, for as soon as possible


def test_a_list_saved_without_phone_calls_still_books_calls_as_appointments(office):
    from diwan import slots
    now = datetime(2026, 10, 30, 20, 58, tzinfo=DUBAI)
    slots.set_appointments(office, [k for k in slots.appointments(office.graph()) if k["where"] != "phone"], by="layla")  # the owner's old list
    assert [k["where"] for k in slots.appointments(office.graph())].count("phone") == 1
    say(office, "I want to buy")
    reception.message(office, PH, "call me tmrw at 10", name_="Ali Rahman", now=now)
    g = office.graph()
    [v] = g.of("viewing", status="booked")
    assert v.props["where"] == "phone" and v.props["chat"] == PH and not g.of("block")  # an appointment with its chat, not a busy block
    r = reception.message(office, PH, "so he will call me at 10 tmrw?", name_="Ali Rahman", now=now)
    assert r["reply"].startswith("Yes Ali") and len(g.of("viewing")) == 1


def test_what_time_did_we_book_is_answered_from_the_calendar(office):
    now = datetime(2026, 10, 30, 20, 58, tzinfo=DUBAI)
    say(office, "I want to buy")
    reception.message(office, PH, "call me tmrw at 10", name_="Ali Rahman", now=now)
    for q in ("what's the time we booked?", "what time did we book?", "when will he call me?", "which time did we agree", "when is he calling me"):
        r = reception.message(office, PH, q, name_="Ali Rahman", now=now)
        assert r["reply"] == "Omar will call you Saturday 31 Oct, 10:00 AM. If you need to change it, just tell me.", q


def test_a_time_said_is_checked_against_the_calendar_not_the_conversation(office):
    from datetime import timedelta
    now = datetime(2026, 10, 30, 20, 58, tzinfo=DUBAI)  # a fixed day: the checks name Saturday 31 Oct
    real = now
    say(office, "I want to buy")
    reception.message(office, PH, "call me tmrw at 10", name_="Ali Rahman", now=now)
    [v] = office.graph().of("viewing", status="booked")
    reception.change_from_calendar(office, v.id, by="layla", when=(now + timedelta(days=1)).replace(hour=10, minute=15), now=real)  # moved on the calendar
    r = reception.message(office, PH, "at 10 then", name_="Ali Rahman", now=now)
    assert r["reply"] == "Just to be clear: Omar will call you Saturday 31 Oct, 10:15 AM. If you'd like another time, tell me."
    r = reception.message(office, PH, "at 10:15 then?", name_="Ali Rahman", now=now)
    assert r["reply"].startswith("Yes, Omar will call you Saturday 31 Oct, 10:15 AM.")
    r = reception.message(office, PH, "what's the time we booked?", name_="Ali Rahman", now=now)
    assert "10:15 AM" in r["reply"] and "10:00" not in r["reply"]
    # the model is told too: the calendar is in its sources, and its instructions say the calendar wins
    g = office.graph()
    src = reception.prompt_sources(g, g.nodes[f"chat:{PH}"].deal, g.nodes[f"chat:{PH}"], "ok", listings=False)
    assert src[f"appt:{v.id}"] == "Booked for this customer, on the calendar: Phone call with Omar, Saturday 31 Oct, 10:15 AM"
    assert "the calendar\n  is right" in reception.GUIDE


def test_a_call_set_by_hand_moves_the_clients_call_card(office):
    from datetime import timedelta
    now = datetime(2026, 10, 30, 20, 58, tzinfo=DUBAI)
    say(office, "I want to buy")
    reception.message(office, PH, "call me tmrw at 10", name_="Ali Rahman", now=now)
    [v] = office.graph().of("viewing", status="booked")
    reception.change_from_calendar(office, v.id, by="layla", cancel=True, now=now)  # the call is cancelled, then arranged again by phone
    reception.message(office, PH, "call me tmrw at 10", name_="Ali Rahman", now=now)
    reception.add_by_hand(office, by="layla", broker="omar", phone=PH, name_=None, kind_id="call", ref=None,
                          when=(now + timedelta(days=1)).replace(hour=10, minute=15), now=now)
    assert [c.props["due"][11:16] for c in office.graph().of("attention", status="open")] == ["10:15"]
