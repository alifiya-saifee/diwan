"""Follow-ups when a client goes quiet (docs/quiet-clients-spec.md): the owner's schedule, useful words, quiet hours,
the 24-hour rule, "stop", and the last step."""
from datetime import datetime, timedelta

import pytest

from diwan import demo, inbox
from diwan.agents import nudge, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

PH = "971501230000"
QUAL = ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now")


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    # these tests start from the real clock: no quiet hours or Friday prayer, so they pass at any hour on any weekday;
    # test_never_in_quiet_hours_or_friday_prayer turns them back on
    nudge.set_settings(o, {"quiet_from": "00:00", "quiet_to": "00:00", "friday_prayer": False}, by="layla")
    return o


def say(office, text, ph=PH):
    return reception.message(office, ph, text, name_="Sara Khan")


def at(office, hours):
    """A time `hours` after now, moved to the next time the owner allows messages."""
    return nudge.next_allowed(nudge.settings(office.graph()), datetime.now(DUBAI) + timedelta(hours=hours))


def sent(office, ph=PH):
    return [m for m in office.graph().nodes[f"chat:{ph}"].props["messages"] if m["type"] == "sent"]


def test_a_quiet_client_gets_one_useful_follow_up_on_the_owners_schedule(office):
    say(office, "I want to buy")
    say(office, "Dubai Marina")
    assert nudge.sweep(office, at(office, 2)) == []  # too soon
    assert nudge.sweep(office, at(office, 20.5)) == [f"nudged {PH} #1"]
    m = sent(office)[-1]
    assert m["nudge"] == 1 and m["text"].startswith("Hi Sara, no rush: ") and "type of property" in m["text"]
    assert nudge.sweep(office, at(office, 21)) == []  # never twice
    st = nudge.state(office.graph(), office.graph().nodes[f"chat:{PH}"], datetime.now(DUBAI))
    assert st["sent"] == 1 and st["of"] == 3 and st["next"]


def test_after_24_hours_only_a_template_and_none_picked_means_skipped(office):
    say(office, "I want to buy")
    nudge.sweep(office, at(office, 20.5))
    assert nudge.sweep(office, at(office, 73)) == [f"skipped {PH} #2"]
    assert len(sent(office)) == 2  # the greeting and follow-up 1 only
    nudge.set_settings(office, {"template": "gentle_follow_up"}, by="layla")
    nudge.sweep(office, at(office, 169))
    m = sent(office)[-1]
    assert m["template"] == "gentle_follow_up" and m["nudge"] == 3  # follow-up 2 was skipped, so this is not a repeat and m["text"].startswith("Hi Sara, are you still looking in")


def test_a_follow_up_never_repeats_an_earlier_one_word_for_word(office):
    nudge.set_settings(office, {"template": "gentle_follow_up"}, by="layla")
    say(office, "I want to buy")
    nudge.sweep(office, at(office, 20.5))
    assert nudge.sweep(office, at(office, 73)) == [f"nudged {PH} #2"]
    assert nudge.sweep(office, at(office, 169)) == [f"skipped {PH} #3"]
    g = office.graph()
    st = nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))
    assert st["delivered"] == 2 and "word for word" in st["last"]["why"]


def test_a_reply_starts_the_count_again(office):
    say(office, "I want to buy")
    nudge.sweep(office, at(office, 20.5))
    say(office, "Sorry, busy week. Dubai Marina")
    g = office.graph()
    assert nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))["sent"] == 0


def test_never_in_quiet_hours_or_friday_prayer(office):
    s = nudge.set_settings(office, {"quiet_from": "21:00", "quiet_to": "09:00", "friday_prayer": True}, by="layla")
    night = datetime(2026, 11, 2, 23, 0, tzinfo=DUBAI)
    prayer = datetime(2026, 11, 6, 12, 0, tzinfo=DUBAI)  # a Friday
    assert not nudge.allowed(s, night) and not nudge.allowed(s, prayer) and nudge.allowed(s, prayer.replace(hour=15))
    assert nudge.next_allowed(s, night) == datetime(2026, 11, 3, 9, 0, tzinfo=DUBAI)
    assert nudge.next_allowed(s, night.replace(hour=8, minute=49)) == datetime(2026, 11, 2, 9, 0, tzinfo=DUBAI)
    assert nudge.next_allowed(s, prayer) == prayer.replace(hour=13, minute=30)
    say(office, "I want to buy")
    assert nudge.sweep(office, datetime.now(DUBAI).replace(hour=23) + timedelta(days=1)) == []


def test_stop_means_stop(office):
    say(office, "I want to buy")
    r = say(office, "Please stop messaging me")
    assert r["reply"].startswith("Understood. I won't message you again")
    g = office.graph()
    st = nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))
    assert st["why_not"].startswith("stopped") and nudge.sweep(office, at(office, 30)) == []
    assert not reception.nurture_list(g)


def test_after_the_last_follow_up_the_lead_goes_to_nurture_and_comes_back_when_they_write(office):
    nudge.set_settings(office, {"after_hours": [20], "then_after_hours": 48}, by="layla")
    say(office, "I want to buy")
    nudge.sweep(office, at(office, 20.5))
    assert nudge.sweep(office, at(office, 70)) == [f"quiet {PH}"]
    d = office.graph().nodes[f"deal:{office.graph().nodes[f'chat:{PH}'].deal}"].props
    assert d["nurture"]["reason"] == "went quiet after 1 follow-up"
    assert nudge.sweep(office, at(office, 200)) == []  # nobody is chased
    say(office, "Hi, sorry, still interested")
    d = office.graph().nodes[f"deal:{office.graph().nodes[f'chat:{PH}'].deal}"].props
    assert not d.get("nurture") and d["reopened"]


def test_the_owner_can_choose_a_gone_quiet_card_instead(office):
    nudge.set_settings(office, {"after_hours": [20], "then": "broker", "then_after_hours": 24}, by="layla")
    say(office, "I want to buy")
    nudge.sweep(office, at(office, 20.5))
    nudge.sweep(office, at(office, 46))
    [card] = office.graph().of("attention", status="open")
    assert card.props["reason"].startswith("Gone quiet: no reply to 1 follow-up")


def test_options_sent_and_none_picked_brings_a_new_fit_if_there_is_one(office):
    for t in QUAL:
        say(office, t)
    nudge.sweep(office, at(office, 20.5))
    assert "did the option I sent catch your eye?" in sent(office)[-1]["text"]
    office.add_listing(ref="MG-2201", title="Marina Crest 2201", community="Dubai Marina", type="apartment", beds=2,
                       price_aed=2_650_000, permit="P2201", agent="omar")
    say(office, "Hmm let me think")
    nudge.sweep(office, at(office, 20.5))
    assert "a new one came in that fits" in sent(office)[-1]["text"] and "MG-2201" in sent(office)[-1]["text"]


def test_no_follow_up_when_a_person_has_the_chat(office):
    say(office, "I want to buy")
    reception.person_sends(office, PH, "Hi Sara, Omar here", by="omar")
    g = office.graph()
    assert nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))["why_not"] == "a person has the chat"
    assert nudge.sweep(office, at(office, 30)) == []


def test_only_the_owner_sets_follow_ups_and_values_are_checked(office):
    with pytest.raises(PermissionError):
        nudge.set_settings(office, {"after_hours": [24]}, by="omar")
    for bad in ({"after_hours": [72, 20]}, {"after_hours": []}, {"quiet_from": "9pm"}, {"then": "spam"}):
        with pytest.raises(ValueError):
            nudge.set_settings(office, bad, by="layla")
    v = nudge.set_settings(office, {"after_hours": [12, 48], "friday_prayer": False}, by="layla")
    assert nudge.settings(office.graph()) == v and v["after_hours"] == [12, 48]


def test_the_inbox_shows_where_the_follow_ups_are(office):
    say(office, "I want to buy")
    nudge.sweep(office, at(office, 20.5))
    q = inbox.detail(office, PH)["quiet"]
    assert q["sent"] == 1 and q["of"] == 3 and q["next"]


def test_no_follow_up_while_the_broker_has_an_open_card(office):
    say(office, "Hi")
    say(office, "Can someone call me please?")
    g = office.graph()
    assert nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))["why_not"] == "the broker has it (an open card)"
    assert nudge.sweep(office, at(office, 30)) == []


def test_no_follow_up_before_a_booked_viewing(office):
    say(office, "Hi")
    say(office, "Can I see MC-1204 next Saturday at 4pm?")
    g = office.graph()
    assert g.of("viewing", status="booked")
    assert nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))["why_not"] == "a viewing is coming up"


def test_a_lead_can_have_its_own_schedule_or_be_stopped_and_shows_each_step(office):
    say(office, "I want to buy")
    deal = office.graph().nodes[f"chat:{PH}"].deal
    broker = office.graph().nodes[f"deal:{deal}"].props["broker"]
    nudge.set_for_lead(office, PH, by=broker, after_hours=[2, 48])
    g = office.graph()
    st = nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))
    assert st["of"] == 2 and [s["status"] for s in st["steps"]] == ["planned", "planned"] and st["own"]["after_hours"] == [2, 48]
    assert nudge.sweep(office, at(office, 2.5)) == [f"nudged {PH} #1"]  # this lead's 2 hours, not the office's 20
    g = office.graph()
    st = nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))
    assert st["steps"][0]["status"] == "sent" and st["steps"][0]["text"].startswith("Hi Sara") and st["steps"][1]["status"] == "planned"
    nudge.set_for_lead(office, PH, by=broker, stopped=True)
    g = office.graph()
    assert nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))["why_not"].startswith("stopped for this lead by")
    assert nudge.sweep(office, at(office, 49)) == []
    nudge.set_for_lead(office, PH, by=broker)  # back on the office's schedule
    g = office.graph()
    assert nudge.state(g, g.nodes[f"chat:{PH}"], datetime.now(DUBAI))["of"] == 3
    with pytest.raises(ValueError):
        nudge.set_for_lead(office, PH, by=broker, after_hours=[48, 2])
    with pytest.raises(PermissionError):
        nudge.set_for_lead(office, PH, by="priya", stopped=True)
