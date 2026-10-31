"""The broker's own time (docs/calendar-own-time-spec.md): busy blocks once or weekly, days off, appointments added by
hand, and who may change whose calendar."""
from datetime import datetime, timedelta

import pytest

from diwan import demo, slots
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office

PH = "971501230000"
_t = datetime.now(slots.DUBAI)
MON = (_t + timedelta(days=7 - _t.weekday())).replace(hour=9, minute=0, second=0, microsecond=0)  # next Monday, 09:00
TUE = MON + timedelta(days=1)
at = lambda d, h: d.replace(hour=h)  # noqa: E731


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def say(office, text, now=MON):
    return reception.message(office, PH, text, name_="Sara Khan", now=now)


def test_busy_time_is_never_offered_or_booked(office):
    slots.block(office, by="omar", broker="omar", start=at(TUE, 15), end=at(TUE, 17), reason="Dentist", now=MON)
    g = office.graph()
    assert not slots.is_open(g, "omar", at(TUE, 16)) and not slots.is_open(g, "omar", at(TUE, 14).replace(minute=30), 60)
    assert slots.is_open(g, "omar", at(TUE, 17))
    r = say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    assert "isn't available" in r["reply"] and not office.graph().of("viewing", status="booked")


def test_a_weekly_block_repeats_until_it_stops(office):
    slots.block(office, by="omar", broker="omar", start=at(MON, 11), end=at(MON, 12), repeat="weekly",
                until=(MON + timedelta(days=8)).date().isoformat(), now=MON)
    g = office.graph()
    assert not slots.is_open(g, "omar", at(MON, 11)) and not slots.is_open(g, "omar", at(MON, 11) + timedelta(days=7))
    assert slots.is_open(g, "omar", at(MON, 11) + timedelta(days=14))  # stopped repeating


def test_a_block_over_a_booking_is_refused_with_the_reason(office):
    say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    with pytest.raises(ValueError, match="Sara Khan .* move it first"):
        slots.block(office, by="omar", broker="omar", start=at(TUE, 15), end=at(TUE, 17), now=MON)
    with pytest.raises(ValueError, match="move it first"):
        slots.day_off(office, by="omar", broker="omar", first=MON.date().isoformat(), last=TUE.date().isoformat(), now=MON)
    with pytest.raises(ValueError, match="after the start"):
        slots.block(office, by="omar", broker="omar", start=at(TUE, 17), end=at(TUE, 15), now=MON)
    with pytest.raises(ValueError, match="already passed"):
        slots.block(office, by="omar", broker="omar", start=MON - timedelta(days=3), end=MON - timedelta(days=2, hours=22), now=MON)


def test_a_day_off_is_not_bookable(office):
    slots.day_off(office, by="omar", broker="omar", first=TUE.date().isoformat(), last=TUE.date().isoformat(), reason="Leave", now=MON)
    g = office.graph()
    assert not any(slots.is_open(g, "omar", at(TUE, h)) for h in range(10, 19)) and slots.is_open(g, "omar", at(MON, 12))


def test_only_the_broker_or_the_owner_changes_a_calendar_and_colleagues_see_busy_only(office):
    with pytest.raises(PermissionError):
        slots.block(office, by="hamza", broker="omar", start=at(TUE, 15), end=at(TUE, 16), now=MON)
    b = slots.block(office, by="layla", broker="omar", start=at(TUE, 15), end=at(TUE, 16), reason="School run", now=MON)
    g = office.graph()
    week = lambda p: slots.week(g, MON.date(), person=p)["blocks"]  # noqa: E731
    assert week("omar")[0]["reason"] == "School run" and week("layla")[0]["reason"] == "School run"
    with pytest.raises(PermissionError):
        slots.unblock(office, b["id"], by="hamza")
    slots.block(office, by="omar", broker="omar", start=at(TUE, 16), end=at(TUE, 17), reason="School run", bid=b["id"], now=MON)
    assert slots.is_open(office.graph(), "omar", at(TUE, 15)) and not slots.is_open(office.graph(), "omar", at(TUE, 16))
    slots.unblock(office, b["id"], by="omar")
    assert slots.is_open(office.graph(), "omar", at(TUE, 16)) and not slots.week(office.graph(), MON.date(), person="omar")["blocks"]


def test_colleagues_see_busy_without_the_reason(office):
    slots.block(office, by="omar", broker="omar", start=at(TUE, 15), end=at(TUE, 16), reason="Dentist", now=MON)
    g = office.graph()
    # the owner filtered to Omar sees it with the reason; Hamza's own calendar never shows Omar's time
    assert slots.week(g, MON.date(), person="layla", broker="omar")["blocks"][0]["reason"] == "Dentist"
    assert not slots.week(g, MON.date(), person="hamza")["blocks"]


def test_an_appointment_added_by_hand_counts_like_ranias(office):
    r = reception.add_by_hand(office, by="omar", broker="omar", phone="+971 50 999 0001", name_="Ali Noor", kind_id="viewing",
                              ref="MC-1204", when=at(TUE, 16), now=MON)
    g = office.graph()
    v = g.nodes[r["id"]]
    assert v.props["by_hand"] == "omar" and v.props["chat"] == "971509990001" and g.nodes["chat:971509990001"].label == "Ali Noor"
    assert g.nodes[f"deal:{r['deal']}"].props["stage"] == "Viewing booked"
    assert not [m for m in g.nodes["chat:971509990001"].props["messages"] if m["type"] == "sent"]  # nothing sent now
    with pytest.raises(ValueError, match="isn't free"):
        reception.add_by_hand(office, by="omar", broker="omar", phone="971509990002", name_="Mona", kind_id="video",
                              ref=None, when=at(TUE, 16), now=MON)
    # Rania knows about it: the client can move it in the chat
    out = reception.message(office, "971509990001", "Can we move the viewing to 5pm on Tuesday?", now=MON)
    assert "is now" in out["reply"] and office.graph().nodes[r["id"]].props["at"].startswith(at(TUE, 17).isoformat()[:13])


def test_adding_by_hand_checks_what_it_needs(office):
    with pytest.raises(PermissionError):
        reception.add_by_hand(office, by="hamza", broker="omar", phone="971509990001", name_="Ali", kind_id="viewing", ref="MC-1204", when=at(TUE, 16), now=MON)
    with pytest.raises(ValueError, match="which property"):
        reception.add_by_hand(office, by="omar", broker="omar", phone="971509990001", name_="Ali", kind_id="viewing", ref=None, when=at(TUE, 16), now=MON)
    with pytest.raises(ValueError, match="name"):
        reception.add_by_hand(office, by="omar", broker="omar", phone="971509990001", name_="", kind_id="video", ref=None, when=at(TUE, 16), now=MON)
    with pytest.raises(ValueError, match="country code"):
        reception.add_by_hand(office, by="omar", broker="omar", phone="12", name_="Ali", kind_id="video", ref=None, when=at(TUE, 16), now=MON)
    r = reception.add_by_hand(office, by="layla", broker="omar", phone="971509990003", name_="Huda", kind_id="video", ref=None, when=at(TUE, 11), now=MON)
    assert any("Layla added a video call with Huda" in n.props["text"] for n in office.graph().of("notice"))
    assert r["id"].startswith("V")


def test_the_week_at_a_glance(office):
    reception.add_by_hand(office, by="omar", broker="omar", phone="971509990001", name_="Ali Noor", kind_id="viewing", ref="MC-1204", when=at(TUE, 16), now=MON)
    slots.day_off(office, by="omar", broker="omar", first=(MON + timedelta(days=3)).date().isoformat(), last=(MON + timedelta(days=3)).date().isoformat(), now=MON)
    i = slots.week(office.graph(), MON.date(), person="layla", broker="omar", now=MON)["insights"]
    [o] = i["load"]
    assert i["total"] == 1 and i["by_kind"] == {"Site visit": 1} and i["next"]["customer"] == "Ali Noor"
    assert o["open"] == 5 * 9 * 60 - 0 and o["pct"] == round(100 * 60 / o["open"]) and o["off"] == [(MON + timedelta(days=3)).date().isoformat()]
    later = slots.week(office.graph(), MON.date(), person="layla", now=at(TUE, 18))["insights"]
    assert later["attention"][0]["why"].startswith("Past, not marked") and later["next"] is None


def test_an_appointment_now_outside_the_brokers_hours_needs_attention(office):
    reception.add_by_hand(office, by="omar", broker="omar", phone="971509990001", name_="Ali Noor", kind_id="video", ref=None, when=at(TUE, 17), now=MON)
    slots.set_hours(office, {"close": "17:00"}, by="layla")  # the owner shortens the day after it was booked
    [a] = slots.week(office.graph(), MON.date(), person="omar", now=MON)["insights"]["attention"]
    assert a["why"] == "Now outside Omar's hours" and "Ali Noor" in a["text"]


def test_the_client_asks_when_their_appointment_is(office):
    reception.add_by_hand(office, by="omar", broker="omar", phone="971509990001", name_="Ali Noor", kind_id="viewing", ref="MC-1204", when=at(TUE, 16), now=MON)
    r = reception.message(office, "971509990001", "When is my viewing?", now=MON)
    assert r["reply"].startswith("Your site visit to Unit 1204, Marina Crest (MC-1204) is Tuesday") and "4:00 PM with Omar" in r["reply"]
    r = reception.message(office, "971509990001", "Is the viewing still on?", now=MON)
    assert r["reply"].startswith("Yes, your site visit") and len(office.graph().of("viewing", status="booked")) == 1
