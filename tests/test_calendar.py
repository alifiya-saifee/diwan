"""The calendar (docs/calendar-spec.md): hours, days and kinds from settings; booking the kind asked for; moving and
cancelling in the chat; reminders; the week view; Done and No-show."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo, leads, slots
from diwan.agents import reception, reminders
from diwan.events import EventLog
from diwan.office import Office

PH = "971501230000"
_t = datetime.now(slots.DUBAI)
MON = (_t + timedelta(days=7 - _t.weekday())).replace(hour=9, minute=0, second=0, microsecond=0)  # next Monday, 09:00
TUE, WED, THU = (MON + timedelta(days=i) for i in (1, 2, 3))


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def say(office, text, now=MON, ph=PH):
    return reception.message(office, ph, text, name_="Sara Khan", now=now)


def booked(office):
    return office.graph().of("viewing", status="booked")


def test_hours_come_from_the_owners_setting_and_the_brokers_own_shift_and_days(office):
    g = office.graph()
    assert slots.window(g, "omar", TUE.date()) == (600, 1140)  # the demo office: 10:00 to 19:00
    assert slots.window(g, "omar", (MON + timedelta(days=6)).date()) is None  # Sunday: closed
    slots.set_hours(office, {"open": "12:00"}, by="layla")
    leads.set_agent(office, "omar", "shift", "13:00-21:00", by="layla")
    leads.set_agent(office, "omar", "days", [0, 1, 3, 4], by="layla")  # no Wednesday
    g = office.graph()
    assert slots.window(g, "omar", TUE.date()) == (780, 1140) and slots.window(g, "omar", WED.date()) is None
    with pytest.raises(PermissionError):
        slots.set_hours(office, {"open": "08:00"}, by="omar")
    with pytest.raises(ValueError):
        slots.set_hours(office, {"open": "20:00"}, by="layla")


def test_rania_never_offers_a_day_off_or_a_time_outside_the_shift(office):
    leads.set_agent(office, "omar", "days", [0, 1, 3, 4, 5], by="layla")
    say(office, "Hi")
    r = say(office, "Can I see MC-1204 on Wednesday at 4pm?")
    assert "isn't available" in r["reply"] and "Wednesday" not in r["reply"].split("on ", 1)[1] and not booked(office)


def test_a_video_call_is_booked_as_its_own_kind_with_the_leads_broker(office):
    say(office, "Hi")
    r = say(office, "Could we do a video call on Tuesday at 3pm?")
    [v] = booked(office)
    assert v.props["kind"] == "video" and v.props["minutes"] == 30 and v.props["broker"] == "omar"
    assert "by video (30 min)" in r["reply"] and "send the link" in r["reply"]


def test_appointments_never_overlap(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    g = office.graph()
    assert not slots.is_open(g, "omar", TUE.replace(hour=16, minute=30), 30) and slots.is_open(g, "omar", TUE.replace(hour=17), 30)
    r = say(office, "And a video call Tuesday at 4:30pm?")  # the same client, the same broker
    assert len(booked(office)) == 1 and "isn't available" in r["reply"]


def test_moving_and_cancelling_in_the_chat_tell_the_broker(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    r = say(office, "Can we move it to Thursday at 5pm instead?")
    [v] = booked(office)
    assert r["reply"].startswith("Done:") and datetime.fromisoformat(v.props["at"]) == THU.replace(hour=17)
    r = say(office, "Sorry, I need to cancel")
    assert "cancelled" in r["reply"] and not booked(office)
    texts = [n.props["text"] for n in office.graph().of("notice") if n.props["to"] == "omar"]
    assert any("moved" in t for t in texts) and any("cancelled" in t for t in texts)


def test_moving_the_viewing_moves_the_viewing_not_the_earlier_video_call(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    say(office, "Could we also do a video call on Tuesday at 11am?")
    say(office, "Can we move the viewing to Thursday at 5pm instead?")
    at = {v.props["kind"]: v.props["at"][5:16] for v in booked(office)}
    assert at["viewing"][6:] == "17:00" and at["video"][6:] == "11:00"


def test_a_busy_new_time_offers_others_and_keeps_the_old_one(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    say(office, "Can I see MC-1204 Thursday at 5pm?", ph="971509999999")
    r = say(office, "Can we move it to Thursday at 5pm?")
    assert "isn't free" in r["reply"] and "stays booked" in r["reply"]
    assert sorted(v.props["at"][11:16] for v in booked(office)) == ["16:00", "17:00"]


def test_the_owner_sets_the_kinds_of_appointment(office):
    with pytest.raises(ValueError, match="at the property"):
        slots.set_appointments(office, [{"name": "Video call", "minutes": 30, "where": "video"}], by="layla")
    with pytest.raises(ValueError, match="steps of 15"):
        slots.set_appointments(office, [{"name": "Site visit", "minutes": 50, "where": "property"}], by="layla")
    ks = slots.set_appointments(office, [{"id": "viewing", "name": "Site visit", "minutes": 90, "where": "property"}], by="layla")
    assert slots.appointments(office.graph())[:len(ks)] == ks and slots.appointments(office.graph())[-1]["where"] == "phone"  # a call is always bookable
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    assert booked(office)[0].props["minutes"] == 90


def test_reminders_the_day_before_and_two_hours_before_once_each(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    at = TUE.replace(hour=16)
    assert reminders.sweep(office, at - timedelta(hours=30)) == []
    assert reminders.sweep(office, at - timedelta(hours=23)) == ["reminded V1 24h"]
    assert reminders.sweep(office, at - timedelta(hours=22)) == []
    out = reminders.sweep(office, at - timedelta(hours=1, minutes=50))
    assert "reminded V1 2h" in out
    sent = [m for m in office.graph().nodes[f"chat:{PH}"].props["messages"] if m.get("reminder")]
    # their last message was days ago, so WhatsApp's window is shut: the approved reminder template
    assert [m["reminder"] for m in sent] == ["24h", "2h"] and sent[0]["template"] == "viewing_reminder" and "Tuesday" in sent[0]["text"]
    g = office.graph()
    text = reminders.text(g, g.nodes["V1"], "Sara")  # inside the window: where to go and what to bring
    assert text.startswith("Hi Sara, a reminder of your site visit to Unit 1204") and "photo ID" in text and "Reply here" in text


def test_the_broker_gets_the_days_list_once_each_morning(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    assert "morning omar" in reminders.sweep(office, TUE.replace(hour=9, minute=5))
    assert "morning omar" not in reminders.sweep(office, TUE.replace(hour=9, minute=30))
    [n] = [n for n in office.graph().of("notice") if n.props["text"].startswith("Today, 1 appointment")]
    assert "16:00 Site visit of MC-1204 with Sara Khan" in n.props["text"]


def test_the_week_the_owner_sees_all_a_broker_their_own(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 Tuesday at 4pm?")
    g = office.graph()
    w = slots.week(g, MON.date(), person="layla")
    assert w["owner"] and len(w["brokers"]) == len(leads.brokers()) and [a["id"] for a in w["appointments"]] == ["V1"]
    assert slots.week(g, MON.date(), person="hamza")["appointments"] == []
    assert slots.week(g, MON.date(), person="omar", broker="hamza")["broker"] == "omar"  # a broker can't look at another's
    with pytest.raises(PermissionError):
        slots.week(g, MON.date(), person="priya")


def test_done_and_no_show_only_after_the_time_by_the_broker_or_owner(monkeypatch):
    o = Office(EventLog())
    demo.company(o)
    monkeypatch.setattr(appmod.S, "office", o)
    c = TestClient(appmod.app)
    reception.message(o, PH, "Hi", name_="Sara Khan", now=MON - timedelta(days=14))
    reception.message(o, PH, "Can I see MC-1204 Tuesday at 4pm?", name_="Sara Khan", now=MON - timedelta(days=14))
    vid = booked(o)[0].id
    assert c.post(f"/api/appointments/{vid}/done", json={"by": "hamza"}).status_code == 403
    assert c.post(f"/api/appointments/{vid}/done", json={"by": "omar"}).json()["ok"] is True
    assert o.graph().nodes[vid].status == "done" and o.graph().nodes[f"deal:{o.graph().nodes[f'chat:{PH}'].deal}"].props["stage"] == "Viewed"
    assert c.post(f"/api/appointments/{vid}/noshow", json={"by": "omar"}).status_code == 409


def test_done_with_notes_makes_the_visit_summary_before_the_follow_up(monkeypatch):
    o = Office(EventLog())
    demo.company(o)
    monkeypatch.setattr(appmod.S, "office", o)
    c = TestClient(appmod.app)
    reception.message(o, PH, "Hi", name_="Sara Khan", now=MON - timedelta(days=14))
    reception.message(o, PH, "Can I see MC-1204 Tuesday at 4pm?", name_="Sara Khan", now=MON - timedelta(days=14))
    vid = booked(o)[0].id
    r = c.post(f"/api/appointments/{vid}/done", json={"by": "omar", "notes": "Loved the view. Kitchen too small. Will talk to his wife."}).json()
    assert r["visit"]["interest"] == "thinking" and r["visit"]["worries"] == ["Kitchen too small."] and r["visit"]["source"] == "notes"
    deal = o.graph().nodes[f"chat:{PH}"].deal
    f = o.graph().nodes[f"deal:{deal}"].props["followup"]
    assert "I've noted what didn't quite work for you" in f["text"] and "Take your time" in f["text"]
