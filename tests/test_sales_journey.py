"""The client's journey in the client's own words, as found running it live on 31 Oct: stop reaches everyone, booking from
a day alone, the owner's first message, photos with the options, follow-ups counted from the appointment."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diwan import demo, leads
from diwan.agents import nudge, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)  # a Wednesday
PH = "971501230000"
QUAL = ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Cash", "Now", "To live in", "UAE resident")  # one listing fits


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    leads.sync_listings(o, (Path(demo.__file__).parent / "demo_feed.xml").read_bytes(), by="demo-feed")  # with its photos
    return o


def say(office, text, ph=PH, now=NOON):
    return reception.message(office, ph, text, name_="Sara Khan", now=now)


def deal(office, ph=PH):
    g = office.graph()
    return g.nodes[f"deal:{g.nodes[f'chat:{ph}'].deal}"].props


def qualified(office):
    for t in QUAL:
        r = say(office, t)
    assert deal(office)["qualify_status"] == "qualified"
    return r


def test_terms_with_no_figure_do_not_break_the_deal_desk(office):
    """Found on live data: the Scribe files "Dubai Marina" as a deal term, and the money check read a figure from it."""
    from diwan.agents import compliance
    say(office, "Hi")
    deal_id = office.graph().nodes[f"chat:{PH}"].deal
    office.record_fact(deal_id, "deal_term", "Dubai Marina", "Sara Khan")
    office.record_fact(deal_id, "payment_promise", "my brother will help with the deposit", "Sara Khan")
    assert compliance.source_of_funds(office.graph(), deal_id) is not None


def test_stop_reaches_a_person_who_has_the_chat_too(office):
    say(office, "Hi")
    say(office, "Can I speak to a person?")
    r = say(office, "stop")
    assert "won't message you again" in r["reply"] and deal(office)["optout"]
    with pytest.raises(reception.OptedOut):
        reception.person_sends(office, PH, "Hi Sara, still interested?", by="omar")


def test_after_stop_a_person_may_answer_if_they_write_again(office):
    say(office, "Hi")
    say(office, "stop")
    reception.receive(office, PH, "Actually I have a question", name_="Sara Khan")
    assert reception.person_sends(office, PH, "Of course, happy to help.", by="omar")


def test_a_question_mark_does_not_bring_listings_before_they_qualify(office):
    r = say(office, "We're looking to buy, budget around 2 million, Dubai Marina. Payment? Not sure yet.")
    assert "AED" not in r["reply"] and not deal(office).get("recommended")


def test_the_view_is_lovely_is_not_asking_to_view(office):
    qualified(office)
    r = say(office, "The view is lovely, but the kitchen is small. Is the price flexible?")
    assert not (deal(office).get("hot") or {}).get("listing") and "Great choice" not in (r["reply"] or "")


def test_asking_the_price_of_one_is_not_choosing_it(office):
    qualified(office)
    say(office, "How much is Marina Promenade?")
    assert not (deal(office).get("hot") or {}).get("listing")


def test_not_sure_i_am_buying_is_nurtured_not_a_buyer(office):
    r = say(office, "I saw a reel about Dubai Creek. I'm not sure I'm buying yet; I just want to know what's out there.")
    assert deal(office).get("nurture") and "take your time" in r["reply"] and not deal(office).get("qtype")


def test_ready_by_summer_is_when_not_what(office):
    say(office, "We want to buy, ready by summer")
    assert "ready_or_offplan" not in deal(office).get("answers", {})


def test_a_day_alone_offers_that_days_free_times(office):
    qualified(office)
    r = say(office, "Saturday morning works. Can my wife come too?")
    assert "Saturday 31 Oct" in r["reply"] and "Which suits you" in r["reply"]
    assert (deal(office).get("hot") or {}).get("listing")


def test_then_a_time_books_it_for_the_property_they_chose(office):
    qualified(office)
    say(office, "Saturday morning works")
    r = say(office, "Saturday at 11am")
    assert r["reply"].startswith("Booked:") and "Saturday 31 Oct" in r["reply"]
    assert [v.props["status"] if "status" in v.props else v.status for v in office.graph().of("viewing")] == ["booked"]


def test_can_we_do_thursday_instead_offers_thursday(office):
    qualified(office)
    say(office, "I like it. Can I see it on Saturday at 11am?")
    r = say(office, "can we do Thursday instead?")
    assert "Thursday 29 Oct" in r["reply"] and "stays booked" in r["reply"]


def test_do_i_need_anything_is_not_asking_for_options(office):
    qualified(office)
    r = say(office, "Do I need anything?")
    assert "fit best" not in (r["reply"] or "")


def test_the_owners_first_message_with_their_whatsapp_name(office):
    reception.set_front(office, {"greeting": "Welcome {name} to {company}! Buying, selling or renting?"}, by="layla")
    r = say(office, "Hello")
    assert r["reply"] == f"Welcome Sara to {reception.COMPANY}! Buying, selling or renting?"


def test_the_first_message_has_its_arabic_and_only_the_owner_sets_it(office):
    with pytest.raises(PermissionError):
        reception.set_front(office, {"greeting": "Hi"}, by="omar")
    reception.set_front(office, {"greeting": "Hi {name}", "greeting_ar": "أهلاً {name}"}, by="layla")
    assert say(office, "مرحبا")["reply"] == "أهلاً Sara"


def test_without_a_greeting_a_name_still_works_and_nothing_breaks(office):
    assert reception.front_settings(office.graph())["greeting"] is None
    assert "Rania" in say(office, "Hello")["reply"]


def test_they_said_what_they_want_so_she_does_not_ask_it_again(office):
    r = say(office, "Hi, I'm looking to buy")
    assert "buy, rent" not in r["reply"]


def test_options_come_with_a_photo_and_a_few_words(office):
    qualified(office)
    msgs = office.graph().nodes[f"chat:{PH}"].props["messages"]
    cards = [m for m in msgs if m.get("image")]
    assert cards and cards[0]["image"].startswith("/web/img/") and cards[0]["text"].startswith("1. ")


def test_the_second_one_means_the_list_she_showed(office):
    listed = say(office, "Any apartments available in Dubai Marina")
    assert len(listed["refs"]) >= 2
    r = say(office, "Oh, the second one looks nice. Can I see it?")
    assert r["reply"].count("AED") <= 1 or "Which property" not in r["reply"]
    assert deal(office)["recommended"][1] == listed["refs"][1]


def visited(office, when):
    qualified(office)
    say(office, "I like it. Can I see it on Saturday at 11am?")
    vid = office.graph().of("viewing")[0].id.split(":")[-1]
    office.log.append("appointment.done", actor="omar", deal=office.graph().nodes[f"chat:{PH}"].deal, content={"id": vid})
    return vid


def test_follow_ups_count_from_the_appointment_at_1_3_6_9_days(office):
    visited(office, NOON)
    g = office.graph()
    chat = g.nodes[f"chat:{PH}"]
    v = g.of("viewing")[0]
    st = nudge.state(g, chat, datetime.fromisoformat(v.props["at"]) + timedelta(hours=1))
    at = datetime.fromisoformat(v.props["at"])
    assert st["of"] == 4 and st["after_hours"] == [24, 72, 144, 216] and st["why_not"] is None
    assert datetime.fromisoformat(st["next"]) >= at + timedelta(days=1)


def test_the_owner_changes_the_pattern(office):
    v = nudge.set_settings(office, {"after_visit_hours": [48, 120]}, by="layla")
    assert v["after_visit_hours"] == [48, 120]
    with pytest.raises(ValueError):
        nudge.set_settings(office, {"after_visit_hours": [72, 24]}, by="layla")
    with pytest.raises(PermissionError):
        nudge.set_settings(office, {"after_visit_hours": [24]}, by="omar")


def test_a_reply_after_the_visit_goes_back_to_the_usual_schedule(office):
    visited(office, NOON)
    g = office.graph()
    v = g.of("viewing")[0]
    reception.message(office, PH, "Thanks, we are thinking about it", name_="Sara Khan", now=datetime.fromisoformat(v.props["at"]) + timedelta(hours=2))
    g = office.graph()
    assert nudge.after_visit(g, g.nodes[f"chat:{PH}"]) is None or g.nodes[f"chat:{PH}"].props["messages"][-1]["type"] == "sent"


def test_the_message_after_a_visit_is_about_that_visit(office):
    visited(office, NOON)
    g = office.graph()
    chat = g.nodes[f"chat:{PH}"]
    text, _ = nudge.text_for(g, chat.deal, chat, False, g.of("viewing")[0], 1)
    assert text.startswith("Hi Sara, thank you for coming to see")
