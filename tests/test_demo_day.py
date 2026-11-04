"""The public demo's busy day (diwan/demo_day.py): every room has work, nothing calls a model or leaves the office, Karim's
correction is left for the visitor, and each person still sees only what their role may see."""
from datetime import datetime

import pytest

from diwan import demo, demo_day, slots
from diwan.agents import frontdesk, runner
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOW = datetime(2026, 11, 3, 17, 30, tzinfo=DUBAI)


@pytest.fixture
def office(monkeypatch):
    def never(*a, **k):
        raise AssertionError("the demo day called a model")
    monkeypatch.setattr(runner, "call", never)
    o = Office(EventLog())
    demo.seed(o); demo.catalog(o); demo.kinds(o); demo.projects(o)
    frontdesk.PENDING.clear()
    assert demo_day.run(o, NOW) == []
    return o


def test_every_room_has_work_and_nothing_left_the_office(office):
    kinds = {e["type"] for e in office.log.list()}
    assert {"chat.received", "appointment.booked", "calendar.blocked", "meeting.ended", "steps.approved", "document.filed",
            "content.made", "thread.posted"} <= kinds
    g = office.graph()
    assert len(g.of("chat")) == len(demo_day.LEADS) and len(g.of("viewing", status="booked")) >= 4
    assert not [e for e in office.log.list() if e["type"] == "notify.sent" and e["content"].get("via") != "screen"]
    assert not any((v.props.get("link") or {}).get("url") for v in g.of("viewing"))  # no Zoom meeting was made


def test_karims_correction_is_left_for_the_visitor(office):
    assert not [f for f in office.graph().facts("marina-1204") if f.status == "superseded"]


def test_the_calendar_is_ahead_of_now(office):
    g = office.graph()
    assert all(datetime.fromisoformat(v.props["at"]) > NOW for v in g.of("viewing", status="booked"))
    assert [b for b in slots.blocks(g, "layla") if (b.props.get("meeting") or {}).get("people") == ["layla", "omar"]]


def test_each_broker_sees_only_their_own_clients(office):
    g = office.graph()
    by = {c.label: g.nodes[f"deal:{c.deal}"].props["broker"] for c in g.of("chat")}
    assert len(set(by.values())) > 1
    for broker in set(by.values()):
        seen = {c.label for c in g.of("chat") if frontdesk.sees_deal(g, c.deal, broker)}
        assert seen == {n for n, b in by.items() if b == broker}


def test_the_server_plays_the_day_only_when_asked(monkeypatch):
    from diwan import app
    monkeypatch.setenv("DIWAN_DB", ":memory:")
    monkeypatch.delenv("DIWAN_DEMO_DAY", raising=False)
    assert not app.fresh().graph().of("chat")
    monkeypatch.setenv("DIWAN_DEMO_DAY", "1")
    assert app.fresh().graph().of("chat")


def test_marketing_has_a_week_planned_and_a_time_for_the_next_post(office):
    from diwan.agents import rhythm, studio
    days = (rhythm.current(office) or {}).get("days", [])
    assert len([d for d in days if d.get("ref")]) >= 3
    slot = studio.made(office, "slot", "next")
    assert slot and datetime.fromisoformat(slot["at"]) > NOW
    assert rhythm.settings(office)["auto_post"] == "off"  # nothing goes out without a person's yes


def test_the_day_also_plays_inside_a_running_server():
    import asyncio
    from diwan.agents import rhythm

    async def start():  # uvicorn imports the app inside its own event loop
        o = Office(EventLog())
        demo.seed(o); demo.catalog(o); demo.kinds(o); demo.projects(o)
        return o, demo_day.run(o, NOW)
    o, missed = asyncio.run(start())
    assert missed == [] and rhythm.current(o)


def test_a_price_change_pauses_the_post_that_said_the_old_price(office):
    paused = [e["content"] for e in office.log.list() if e["type"] == "post.paused"]
    assert paused and any("1,900,000" in p["why"] and "1,950,000" in p["why"] for p in paused)
