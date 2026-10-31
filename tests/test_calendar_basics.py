"""Calendar basics and video links (docs/calendar-basics-spec.md): ranges, search, changing from the calendar with the
client told, the .ics file, and Zoom links made only by Zoom (a stand-in answers here)."""
import json
from datetime import datetime, timedelta

import httpx
import pytest

from diwan import demo, slots, video
from diwan.agents import reception, reminders
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import zoom

PH = "971501230000"
_t = datetime.now(slots.DUBAI)
MON = (_t + timedelta(days=7 - _t.weekday())).replace(hour=9, minute=0, second=0, microsecond=0)
TUE = MON + timedelta(days=1)
at = lambda d, h: d.replace(hour=h)  # noqa: E731


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


@pytest.fixture
def zoomed(monkeypatch):
    """Zoom keys present, and Zoom's API answered by a stand-in that records each request."""
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


def say(office, text, now=MON, ph=PH):
    return reception.message(office, ph, text, name_="Sara Khan", now=now)


def test_any_range_and_last_period(office):
    say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    v = slots.week(office.graph(), MON.date(), person="layla", n=31, now=MON)
    assert len(v["days"]) == 31 and v["insights"]["total"] == 1 and v["insights"]["last_week"] == 0
    with pytest.raises(ValueError):
        slots.week(office.graph(), MON.date(), person="layla", n=200)


def test_search_any_date_and_status_and_only_your_own(office):
    say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    say(office, "Actually cancel the viewing please")
    [r] = slots.search(office.graph(), "sara", person="layla")
    assert r["status"] == "cancelled" and slots.search(office.graph(), "50123", person="omar")
    assert not slots.search(office.graph(), "sara", person="hamza")


def test_moving_from_the_calendar_tells_the_client_in_one_message(office):
    say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    [v] = office.graph().of("viewing", status="booked")
    with pytest.raises(PermissionError):
        reception.change_from_calendar(office, v.id, by="hamza", when=at(TUE, 17), now=MON)
    with pytest.raises(ValueError, match="isn't free"):
        reception.change_from_calendar(office, v.id, by="omar", when=at(TUE, 21), now=MON)
    r = reception.change_from_calendar(office, v.id, by="layla", when=at(TUE, 17), now=datetime.now(slots.DUBAI))  # messages carry the real time
    assert r["told"] == "sent" and r["text"].startswith("Hi Sara, Omar has moved your site visit to Unit 1204, Marina Crest (MC-1204): it's now Tuesday")
    g = office.graph()
    assert g.nodes[v.id].props["at"].startswith(at(TUE, 17).isoformat()[:13])
    assert any("Layla moved" in n.props["text"] for n in g.of("notice"))  # the broker hears the owner moved it
    r = reception.change_from_calendar(office, v.id, by="omar", cancel=True, reason="Omar is sick", now=MON)
    assert r["text"].startswith("Hi Sara, your site visit to Unit 1204, Marina Crest (MC-1204) on") and "has been cancelled" in r["text"] and "sick" not in r["text"]  # the reason stays inside the office
    assert office.graph().nodes[v.id].status == "cancelled"


def test_outside_the_24_hour_window_the_client_gets_the_approved_template(office):
    say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    [v] = office.graph().of("viewing", status="booked")
    late = datetime.now(slots.DUBAI) + timedelta(hours=30)
    r = reception.change_from_calendar(office, v.id, by="omar", when=at(TUE, 17), now=late)
    assert r["told"] == "template" and r["text"].startswith("Hi Sara, your site visit to Unit 1204, Marina Crest (MC-1204) has been moved to")
    sent = [m for m in office.graph().nodes[f"chat:{PH}"].props["messages"] if m["type"] == "sent"][-1]
    assert sent["template"] == "appointment_changed" and not office.graph().of("attention", status="open")
    r = reception.change_from_calendar(office, v.id, by="omar", cancel=True, reason="private", now=late)
    assert r["told"] == "template" and "has been cancelled" in r["text"] and "private" not in r["text"]


def test_without_an_approved_template_the_broker_gets_a_card(office):
    reminders.set_settings(office, {"change_template": None, "cancel_template": None}, by="layla")
    say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    [v] = office.graph().of("viewing", status="booked")
    r = reception.change_from_calendar(office, v.id, by="omar", when=at(TUE, 17), now=datetime.now(slots.DUBAI) + timedelta(hours=30))
    assert r["told"] == "card" and any("Tell the client" in c.props["reason"] for c in office.graph().of("attention", status="open"))


def test_moving_or_cancelling_a_phone_call_on_the_calendar_moves_the_card_and_tells_the_client(office):
    now = datetime.now(slots.DUBAI).replace(hour=20, minute=58, second=0, microsecond=0)
    reception.message(office, PH, "I want to buy", name_="Sara Khan", now=now)
    reception.message(office, PH, f"call me {TUE:%A} at 10", name_="Sara Khan", now=now)
    [v] = office.graph().of("viewing", status="booked")
    r = reception.change_from_calendar(office, v.id, by="layla", when=at(TUE, 14), now=datetime.now(slots.DUBAI))
    assert r["told"] == "sent" and "has moved your phone call" in r["text"]
    [card] = office.graph().of("attention", status="open")
    assert card.props["due"].startswith(at(TUE, 14).isoformat()[:13]) and "moved by Layla" in card.props["reason"]
    reception.change_from_calendar(office, v.id, by="omar", cancel=True, now=datetime.now(slots.DUBAI))
    assert not office.graph().of("attention", status="open")


def test_ics_has_the_appointments_and_busy_time(office):
    say(office, "Can I see MC-1204 on Tuesday at 4pm?")
    slots.block(office, by="omar", broker="omar", start=at(TUE, 11), end=at(TUE, 12), reason="Dentist", now=MON)
    body = slots.ics(office.graph(), slots.week(office.graph(), MON.date(), person="omar"))
    assert body.startswith("BEGIN:VCALENDAR") and "SUMMARY:Site visit · Sara Khan" in body and "LOCATION:Unit 1204\\, Marina Crest" in body
    assert "SUMMARY:Busy" in body and "Dentist" not in body and body.count("BEGIN:VEVENT") == 2


def test_only_the_owner_sets_video_and_auto_is_off_by_default(office):
    assert video.settings(office.graph()) == {"provider": None, "auto": False}
    with pytest.raises(PermissionError):
        video.set_settings(office, {"provider": "zoom"}, by="omar")
    with pytest.raises(ValueError):
        video.set_settings(office, {"provider": "teams"}, by="layla")
    assert video.set_settings(office, {"provider": None, "auto": True}, by="layla")["auto"] is False  # nothing to make it with


def test_auto_link_when_rania_confirms_a_video_call(office, zoomed):
    video.set_settings(office, {"provider": "zoom", "auto": True}, by="layla")
    r = say(office, "Could we do a video call on Tuesday at 11am?")
    assert "Join here at that time: https://zoom.us/j/8812345" in r["reply"]
    [v] = office.graph().of("viewing", status="booked")
    assert v.props["link"]["url"] == "https://zoom.us/j/8812345" and v.props["link"]["meeting_id"] == "8812345"
    post = next(c for c in zoomed if c[0] == "POST" and c[1].endswith("/meetings"))
    assert post[2]["duration"] == 30 and post[2]["start_time"] == at(TUE, 11).astimezone(slots.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert "Join here: https://zoom.us/j/8812345" in reminders.text(office.graph(), office.graph().nodes[v.id], "Sara")
    reception.change_from_calendar(office, v.id, by="omar", when=at(TUE, 12), now=MON)
    assert any(c[0] == "PATCH" for c in zoomed)
    say(office, "Please cancel the video call")
    assert any(c[0] == "DELETE" for c in zoomed) and not office.graph().nodes[v.id].props.get("link")


def test_auto_off_means_no_link_until_the_broker_makes_one(office, zoomed):
    video.set_settings(office, {"provider": "zoom", "auto": False}, by="layla")
    r = say(office, "Could we do a video call on Tuesday at 11am?")
    assert "will send the link" in r["reply"] and not [c for c in zoomed if c[1].endswith("/meetings")]
    [v] = office.graph().of("viewing", status="booked")
    out = reception.send_link(office, v.id, by="omar", now=datetime.now(slots.DUBAI))
    assert out["told"] == "sent" and out["text"].startswith("Hi Sara, here is the link for your video call with Omar")


def test_no_keys_no_invented_link_and_the_broker_is_told(office):
    video.set_settings(office, {"provider": "zoom", "auto": True}, by="layla")
    r = say(office, "Could we do a video call on Tuesday at 11am?")
    [v] = office.graph().of("viewing", status="booked")
    assert "will send the link" in r["reply"] and "zoom.us" not in r["reply"]
    assert "Zoom is not connected" in v.props["link"]["error"] and not v.props["link"]["url"]
    assert any("Send the video link" in c.props["reason"] for c in office.graph().of("attention", status="open"))
    with pytest.raises(ValueError, match="not connected"):
        reception.send_link(office, v.id, by="omar", now=MON)
