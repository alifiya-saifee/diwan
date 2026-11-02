"""Viewings by listing (docs/viewing-access-spec.md): a home someone lives in waits for the owner's yes; a vacant one with
keys books at once; off-plan is shown at the developer's gallery in its hours. The client is told either way."""
from datetime import datetime, timedelta

import pytest

from diwan import demo, leads, slots, viewings
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office

MON = datetime(2026, 11, 2, 11, tzinfo=slots.DUBAI)  # a Monday
PH = "971501238888"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)  # MC-1204 is vacant with keys at the office; JVC-88 is lived in (nobody set it: asks first)
    o.log.append("listing.added", actor="omar", content={"ref": "OP-7", "title": "Unit 7, Creek Rise", "community": "Dubai Creek Harbour",
                                                          "type": "apartment", "beds": 2, "price_aed": 1_900_000, "permit": "SAMPLE-77",
                                                          "status": "available", "agent": "omar", "completion": "off_plan", "project": "Creek Rise"})
    return o


def say(office, text, now=MON):
    return reception.message(office, PH, text, name_="Sara Khan", now=now)["reply"]


def node(office, ref):
    return office.graph().nodes[f"listing:{ref}"]


def held(office):
    return [v for v in office.graph().of("viewing") if v.props.get("chat") == PH]


def test_unset_listings_take_the_safe_choice():
    o = Office(EventLog())
    demo.company(o)
    g = o.graph()
    assert viewings.access(g, g.nodes["listing:MC-1204"])["mode"] == "instant"
    assert viewings.access(g, g.nodes["listing:JVC-88"]) | {} == {"mode": "ask", "default": True, "who": "owner", "notice_hours": 0, "label": "Ask the owner first"}


def test_a_lived_in_home_waits_for_the_owner_and_the_time_is_held(office):
    say(office, "Hi")
    r = say(office, "Can I see JVC-88 on Tuesday at 4pm?")
    assert r == "Thanks Sara. Villa 88 is lived in, so I'll check Tuesday 3 Nov, 4:00 PM with the owner and confirm here as soon as they reply."
    [v] = held(office)
    g = office.graph()
    assert v.status == "requested" and not slots.is_open(g, v.props["broker"], datetime(2026, 11, 3, 16, tzinfo=slots.DUBAI))
    card = leads.open_card(g, PH)
    assert card.props["reason"].startswith("Check with the owner: Sara Khan wants to view JVC-88") and card.props["due"] == (MON + timedelta(minutes=120)).isoformat()
    assert say(office, "Any news from the owner?").startswith("I'm still waiting for the owner to confirm Tuesday 3 Nov, 4:00 PM for Villa 88")


def test_the_owner_says_yes_and_the_client_is_told(office):
    say(office, "Hi")
    say(office, "Can I see JVC-88 on Tuesday at 4pm?")
    [v] = held(office)
    out = viewings.answer(office, v.id, by=v.props["broker"], said="yes", now=MON + timedelta(minutes=30))
    g = office.graph()
    assert out["told"] == "sent" and g.nodes[v.id].status == "booked" and not leads.open_card(g, PH)
    assert g.nodes[f"chat:{PH}"].props["messages"][-1]["text"] == "Good news, Sara: the owner confirmed. Booked: Villa 88 (JVC-88) with Omar, Tuesday 3 Nov, 4:00 PM."


def test_other_times_are_offered_and_the_one_picked_books_at_once(office):
    say(office, "Hi")
    say(office, "Can I see JVC-88 on Tuesday at 4pm?")
    [v] = held(office)
    t1, t2 = "2026-11-04T17:00:00+04:00", "2026-11-05T11:00:00+04:00"
    out = viewings.answer(office, v.id, by=v.props["broker"], said="other", times=[t2, t1], now=MON + timedelta(minutes=30))
    assert "Hi Sara, the owner can't do Tuesday 3 Nov, 4:00 PM, but Wednesday 4 Nov, 5:00 PM or Thursday 5 Nov, 11:00 AM works for them" in out["text"]
    assert office.graph().nodes[v.id].status == "offered"
    r = say(office, "Wednesday 4 Nov at 5pm please", now=MON + timedelta(hours=1))
    assert r == "Booked: your site visit to Villa 88 with Omar, Wednesday 4 Nov, 5:00 PM. The owner is expecting you." or r.startswith("Booked:"), r
    g = office.graph()
    assert g.nodes[v.id].status == "booked" and g.nodes[v.id].props["at"] == t1 and len(held(office)) == 1


def test_not_possible_frees_the_time_and_tells_the_client_kindly(office):
    say(office, "Hi")
    say(office, "Can I see JVC-88 on Tuesday at 4pm?")
    [v] = held(office)
    out = viewings.answer(office, v.id, by=v.props["broker"], said="no", now=MON + timedelta(minutes=30))
    g = office.graph()
    assert g.nodes[v.id].status == "cancelled" and slots.is_open(g, v.props["broker"], datetime(2026, 11, 3, 16, tzinfo=slots.DUBAI))
    assert "can't be shown Tuesday 3 Nov, 4:00 PM" in out["text"] and "will suggest other options" in out["text"] and "owner" not in out["text"].split("shown")[0].lower()


def test_a_tenant_gets_their_notice(office):
    viewings.set_access(office, "JVC-88", {"mode": "ask", "who": "tenant", "notice_hours": 24}, by="omar")
    say(office, "Hi")
    r = say(office, "Can I see JVC-88 today at 5pm?")
    assert r.startswith("That time isn't available") and "Monday 2 Nov" not in r and not held(office)


def test_off_plan_is_shown_at_the_gallery_in_its_hours(office):
    viewings.set_access(office, "OP-7", {"mode": "developer", "place": "the Creek Rise sales gallery, Creek Marina", "open": "10:00", "close": "16:00",
                                         "days": [5, 6]}, by="omar")
    say(office, "Hi")
    r = say(office, "Can I see OP-7 on Tuesday at 11am?")
    assert r.startswith("That time isn't available") and "Saturday 7 Nov" in r  # the gallery is open at the weekend only
    r = say(office, "Can I see OP-7 on Saturday at 11am?")
    assert r.startswith("Booked: ") and "at the Creek Rise sales gallery, Creek Marina" in r
    from diwan.agents import reminders
    v = next(v for v in office.graph().of("viewing", status="booked"))
    assert reminders._where(office.graph(), v) == "At the Creek Rise sales gallery, Creek Marina."


def test_a_vacant_home_with_keys_books_at_once(office):
    say(office, "Hi")
    assert say(office, "Can I see MC-1204 on Tuesday at 4pm?").startswith("Booked: Unit 1204")


def test_only_the_listings_broker_a_manager_or_the_owner_change_it(office):
    with pytest.raises(PermissionError):
        viewings.set_access(office, "JVC-88", {"mode": "instant"}, by="hamza")
    assert viewings.set_access(office, "JVC-88", {"mode": "instant"}, by="rashid")["mode"] == "instant"
    with pytest.raises(ValueError, match="Pick one"):
        viewings.set_access(office, "JVC-88", {"mode": "sometimes"}, by="layla")
    with pytest.raises(ValueError, match="gallery"):
        viewings.set_access(office, "OP-7", {"mode": "developer", "place": " ", "open": "10:00", "close": "16:00", "days": [5]}, by="layla")


# ---------- a viewing before a property is chosen, and the booking bugs (item 3) ----------

QUAL = ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now", "To live in", "UAE resident")


@pytest.fixture
def feed():
    from pathlib import Path
    o = Office(EventLog())
    demo.company(o)
    leads.sync_listings(o, (Path(demo.__file__).parent / "demo_feed.xml").read_bytes(), by="demo-feed")
    for li in o.graph().of("listing"):  # vacant, keys at the office: these book at once
        o.log.append("listing.access", actor="layla", content={"ref": li.props["ref"], "mode": "instant", "by": "layla"})
    return o


def test_the_day_they_want_is_kept_until_they_choose_a_property(feed):
    say(feed, "Hi")
    r = say(feed, "I'd like to see some flats in Dubai Marina on Saturday")
    assert r.startswith("Noted: Saturday 7 Nov for the viewing.")
    for t in QUAL:
        say(feed, t)
    r = say(feed, "The second one")
    assert r.startswith("I can book") and r.count("Saturday 7 Nov") == 3  # that day's times, not the next free ones


def test_the_listing_they_name_wins_over_the_one_picked_before(feed):
    for t in QUAL:
        say(feed, t)
    say(feed, "The first one")  # picked: a hot lead on that listing
    r = say(feed, "Actually can I see JVC-88 on Tuesday at 4pm?")
    assert "Villa 88" in r and "JVC-88" in r


def test_a_home_that_is_gone_is_never_booked(feed):
    for t in QUAL:
        say(feed, t)
    say(feed, "The first one")
    hot = feed.graph().nodes[f"deal:{feed.graph().nodes[f'chat:{PH}'].deal}"].props["hot"]["listing"]
    ref = feed.graph().nodes[hot].props["ref"]
    feed.log.append("listing.added", actor="omar", content={"ref": ref, "status": "sold"})
    r = say(feed, "Can I come on Tuesday at 4pm?")
    assert "isn't available any more" in r and not feed.graph().of("viewing")
