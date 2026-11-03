"""The PA runs the calendar (docs/pa-calendar-spec.md): what's on and who's free read from the calendar, time ranges read
right, meetings with colleagues on both calendars with one Zoom link, and calls with clients. Nothing happens without a yes."""
import json
from datetime import datetime

import httpx
import pytest

from diwan import demo, slots, video
from diwan.agents import frontdesk, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import zoom
from diwan.slots import DUBAI

NOW = datetime(2026, 11, 3, 9, tzinfo=DUBAI)  # a Tuesday
THU = datetime(2026, 11, 5, tzinfo=DUBAI)
PH = "971501230000"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    frontdesk.PENDING.clear()
    return o


@pytest.fixture
def zoomed(monkeypatch):
    calls = []

    def handle(req: httpx.Request):
        calls.append((req.method, req.url.path, json.loads(req.content) if req.content else None))
        if req.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        if req.method == "POST":
            return httpx.Response(201, json={"id": 8812345, "join_url": "https://zoom.us/j/8812345"})
        return httpx.Response(204)
    for k in zoom.KEYS:
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(zoom, "TRANSPORT", httpx.MockTransport(handle))
    zoom._token.clear()
    return calls


@pytest.fixture
def no_zoom(monkeypatch):
    for k in zoom.KEYS:
        monkeypatch.delenv(k, raising=False)


def say(office, text, who="omar"):
    return frontdesk.say(office, text, who, session=who, now=NOW)


def meetings(office, who):
    return [b for b in slots.blocks(office.graph(), who) if b.props.get("meeting")]


@pytest.mark.parametrize("words", ["Block Thursday 3 to 5pm", "Block Thursday 3-5pm", "Block Thursday from 3 until 5",
                                   "Block Thursday 3pm for 2 hours", "Block Thursday 3pm to 5pm for school pickup"])
def test_a_time_range_blocks_exactly_that_time(office, words):
    r = say(office, words)
    assert r["kind"] == "confirm" and "3:00 PM to 5:00 PM" in r["text"]
    say(office, "yes")
    [b] = slots.blocks(office.graph(), "omar")
    assert (b.props["start"], b.props["end"]) == (THU.replace(hour=15).isoformat(), THU.replace(hour=17).isoformat())


def test_morning_range_and_a_count_is_not_a_time(office):
    assert "11:00 AM to 1:00 PM" in say(office, "Block Thursday 11 to 1pm")["text"]
    frontdesk.PENDING.clear()
    assert frontdesk._range("show me 2 to 3 bed units on Thursday", NOW) is None


def test_whats_on_and_am_i_free_are_read_from_the_calendar(office):
    assert say(office, "What's on my calendar Thursday?")["text"] == "Nothing on your calendar on Thursday 5 Nov."
    say(office, "Block Thursday 3 to 5pm for the dentist")
    say(office, "yes")
    r = say(office, "What's on Thursday?")
    assert r["kind"] == "answer" and "3:00 PM–5:00 PM The dentist" in r["text"]
    r = say(office, "Am I free Thursday at 4?")
    assert r["text"].startswith("No, you have The dentist then.") and "Free nearby: " in r["text"]
    assert say(office, "Am I free Thursday at 12?")["text"] == "Yes, you're free Thursday 5 Nov, 12:00 PM."
    assert "Thursday 5 Nov: 3:00 PM–5:00 PM The dentist" in say(office, "What's on this week?")["text"]


def test_a_broker_sees_only_their_own_calendar_the_owner_sees_anyone(office):
    say(office, "Block Thursday 3 to 5pm for the dentist")
    say(office, "yes")
    assert "only your own calendar" in say(office, "What's Omar's day Thursday?", "hamza")["text"]
    assert say(office, "Is Omar free Thursday at 4?", "hamza")["text"].startswith("No, Omar is busy then.")  # free or busy, not why
    assert "The dentist" in say(office, "What's Omar's day Thursday?", "layla")["text"]
    assert say(office, "What's on my calendar today?", "ahmed")["text"] == "Only brokers and the owner keep a calendar here."


def test_a_meeting_goes_on_both_calendars_and_the_colleague_is_told(office, no_zoom):
    r = say(office, "Set up a meeting with Hamza Thursday at 2 about the payment plan on Zoom")
    assert r["kind"] == "confirm" and "both your calendars" in r["text"] and "Zoom isn't connected, so there's no link" in r["text"]
    assert not meetings(office, "omar")
    r = say(office, "yes")
    assert r["kind"] == "done" and "zoom.us" not in r["text"]
    [a], [b] = meetings(office, "omar"), meetings(office, "hamza")
    assert a.props["meeting"]["id"] == b.props["meeting"]["id"] and a.label == "Meeting with Hamza about the payment plan" and b.label == "Meeting with Omar about the payment plan"
    assert not slots.is_open(office.graph(), "hamza", THU.replace(hour=14))
    told = [e["content"] for e in office.log.list() if e["type"] == "notify.sent" and e["content"]["to"] == "hamza"]
    assert told and "Omar set up a meeting with you about the payment plan, Thursday 5 Nov, 2:00 PM" in told[-1]["text"]


def test_when_one_is_busy_the_times_both_are_free_are_offered(office):
    slots.block(office, by="hamza", broker="hamza", start=THU.replace(hour=14), end=THU.replace(hour=15), reason="Dentist", now=NOW)
    r = say(office, "Set up a meeting with Hamza Thursday at 2")
    assert r["kind"] == "question" and r["text"].startswith("Hamza is busy then.") and "Dentist" not in r["text"]
    r = say(office, "2")
    assert r["kind"] == "confirm"
    say(office, "yes")
    [m] = meetings(office, "hamza")
    assert m.props["start"] != THU.replace(hour=14).isoformat()


def test_a_meeting_on_zoom_has_one_link_moves_and_is_deleted_with_it(office, zoomed):
    say(office, "Set up a meeting with Hamza Thursday at 2 on Zoom")
    r = say(office, "yes")
    assert "https://zoom.us/j/8812345" in r["text"]
    assert len([c for c in zoomed if c[0] == "POST" and c[1].endswith("/meetings")]) == 1
    assert all(b.props["meeting"]["link"]["url"] == "https://zoom.us/j/8812345" for b in meetings(office, "omar") + meetings(office, "hamza"))
    assert "Zoom: https://zoom.us/j/8812345" in say(office, "What's on Thursday?", "hamza")["text"]
    r = say(office, "Move the meeting with Hamza to 4pm Thursday")
    assert r["kind"] == "confirm" and "every calendar" in r["text"]
    say(office, "yes")
    assert {b.props["start"] for b in meetings(office, "omar") + meetings(office, "hamza")} == {THU.replace(hour=16).isoformat()}
    patch = next(c for c in zoomed if c[0] == "PATCH")
    assert patch[1].endswith("/meetings/8812345") and patch[2]["start_time"] == "2026-11-05T12:00:00Z"
    say(office, "Cancel the meeting with Omar", "hamza")  # either of them can
    r = say(office, "yes", "hamza")
    assert "Zoom meeting is deleted" in r["text"]
    assert any(c[0] == "DELETE" and c[1].endswith("/meetings/8812345") for c in zoomed)
    assert not meetings(office, "omar") and not meetings(office, "hamza")
    assert any(e["type"] == "notify.sent" and e["content"]["to"] == "omar" and "cancelled" in e["content"]["text"] for e in office.log.list())


def test_a_colleague_without_a_calendar_is_told_and_only_yours_is_booked(office):
    r = say(office, "Set up a meeting with Ahmed Thursday at 11", "layla")
    assert "Ahmed doesn't keep a calendar here" in r["text"]
    say(office, "yes", "layla")
    assert meetings(office, "layla") and any(e["type"] == "notify.sent" and e["content"]["to"] == "ahmed" for e in office.log.list())


def test_no_yes_no_meeting(office):
    say(office, "Set up a meeting with Hamza Thursday at 2")
    assert say(office, "no")["text"] == "Cancelled. Nothing was done."
    assert not meetings(office, "omar") and not [e for e in office.log.list() if e["type"] == "notify.sent"]


def test_a_video_call_with_a_client_is_booked_with_its_zoom_link(office, zoomed):
    reception.message(office, PH, "Hi, I'm looking for a 2 bed in Marina", name_="Karim Haddad", now=NOW)
    video.set_settings(office, {"provider": "zoom"}, by="layla")
    r = say(office, "Book Karim Haddad a video call Thursday at 3pm")
    assert r["kind"] == "confirm" and "The Zoom link goes with their reminders" in r["text"]
    assert not office.graph().of("viewing", status="booked")
    r = say(office, "yes")
    [v] = office.graph().of("viewing", status="booked")
    assert v.props["where"] == "video" and v.props["at"] == THU.replace(hour=15).isoformat()
    assert v.props["link"]["url"] == "https://zoom.us/j/8812345" and "https://zoom.us/j/8812345" in r["text"]


def test_a_call_without_zoom_says_the_broker_sends_the_link(office, no_zoom):
    reception.message(office, PH, "Hi, I'm looking for a 2 bed in Marina", name_="Karim Haddad", now=NOW)
    r = say(office, "Book Karim Haddad a video call Thursday at 3pm")
    assert "so there's no link: you send one" in r["text"]
    r = say(office, "yes")
    assert "zoom.us" not in r["text"] and office.graph().of("viewing", status="booked")


def test_a_phone_call_and_a_client_with_no_conversation(office):
    reception.message(office, PH, "Hi, I'm looking for a 2 bed in Marina", name_="Karim Haddad", now=NOW)
    assert say(office, "Book Karim Haddad a phone call Thursday at 5pm")["kind"] == "confirm"
    say(office, "yes")
    [v] = office.graph().of("viewing", status="booked")
    assert v.props["where"] == "phone"
    assert "no WhatsApp conversation" in say(office, "Book Sara Malik a phone call Thursday at 5pm")["text"]
