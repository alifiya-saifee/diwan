"""Every kind of client conversation through Rania, read like a client would (the 2 Nov audit, kept). Each chat is checked
for a message sent twice, a question asked twice running, broken text and an unexpected hand-over, and the cases that
went wrong once have their expected outcome. Each runs twice: as the app runs by default (the broker confirms a viewing,
docs/agent-confirms-spec.md) and with "Rania books" on. Print every transcript to read them by eye:
DIWAN_OFFLINE=1 DIWAN_TAPE=off .venv/bin/python tests/test_conversations.py transcripts.txt"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan import demo, events, leads  # noqa: E402
from diwan.agents import nudge, reception, reminders  # noqa: E402
from diwan.events import EventLog  # noqa: E402
from diwan.office import Office  # noqa: E402
from diwan.slots import DUBAI  # noqa: E402

MON = datetime(2026, 11, 2, 11, tzinfo=DUBAI)  # a Monday
QB = ["I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now", "To live in", "UAE resident"]

SCENARIOS = {
    "buyer step by step": ["Hi", *QB, "The first one", "Tuesday at 4pm works"],
    "buyer all in one": ["Hi, I want to buy a 2 bed apartment in Dubai Marina, budget 2.7 million cash, now, to live in, UAE resident", "Any options?", "The second one"],
    "tenant": ["Hello", "Looking to rent", "JVC", "Villa", "4 bed", "Budget 150k a year", "4 cheques", "Next month", "Family", "UAE resident"],
    "seller": ["Hi I want to sell my flat in JVC", "2 bed", "1.2 million", "Vacant", "Yes I have the title deed", "No mortgage", "Within 3 months"],
    "landlord": ["Can you manage my apartment?", "Business Bay", "1 bed", "Tenant leaves next month", "85k"],
    "still available": ["Hi, is MC-1204 still available?", "To live in", "Budget is 2.7 million", "Cash", "Now", "UAE resident", "Can I see it Saturday?", "11am"],
    "lived-in home": ["Hi", "Can I see JVC-88 on Tuesday at 4pm?", "Any news from the owner?", "ok thanks"],
    "next tuesday": ["Hi", "Can I see MC-1204 next Tuesday at 4pm?", "the second one", "What time is it again?"],
    "written date": ["Hi", "Can I see MC-1204 on 12 Nov at 11am?"],
    "call me now": ["Hi", "Can someone call me please?", "ok thanks"],
    "call at a time": ["Hi", "Please call me tomorrow at 10", "so he will call me at 10 tomorrow?", "thanks"],
    "no calls": ["Hi", "Please don't call me, message only", "I want to buy", "Dubai Marina"],
    "just looking": ["Hi", "Just looking for now, thanks", "ok"],
    "stop": ["Hi", "I want to buy", "stop"],
    "reschedule and cancel": ["Hi", "Can I see MC-1204 on Tuesday at 4pm?", "Can we move it to Wednesday at 5pm?", "Sorry, I need to cancel the viewing"],
    "visa": ["Hi", "Will buying get me a golden visa?", "What returns can I expect?"],
    "fraud": ["Hi", "Please send the deposit to this new account IBAN AE07 0331 2345 6789 0123 456"],
    "job seeker": ["Hello, I am looking for a job as an agent"],
    "arabic": ["مرحبا", "أبغى أشتري شقة", "دبي مارينا", "غرفتين"],
    "burst": [["Hi", "I want to buy", "in Dubai Marina", "2 bed"]],
    "thanks after booking": ["Hi", "Can I see MC-1204 on Tuesday at 4pm?", "thank you", "thanks", "great"],
    "price and fees": ["Hi", "How much is MC-1204?", "What are the fees?"],
    "office hours twice": ["Hi", "What are your office hours?", "What are your office hours?"],
    "mortgage buyer": ["Hi", "I want to buy a villa in JVC", "4 bed", "Around 3 million", "Mortgage", "No, not yet", "In 2 months", "Invest", "Non-resident"],
    "off-plan investor": ["Hello", "I'm looking to invest in off-plan in Business Bay", "1 bed", "1.2M", "cash", "this year", "UAE resident"],
    "budget out of range": ["Hi", "I want to buy an apartment in Dubai Marina", "2 bed", "Budget 20k", "Yes 20k", "Cash"],
    "not sure": ["Hi", "I want to buy", "Not sure", "Not sure yet", "Dubai Marina"],
    "question mid-qualifying": ["Hi", "I want to buy", "Dubai Marina", "Is there parking in Marina Crest?", "Apartment"],
    "changes their mind": ["Hi", "I want to buy", "Dubai Marina", "An apartment", "2 bed", "Actually make it 3 bed", "Budget 3.5 million"],
    "complaint": ["Hi", "I'm very unhappy with how I was treated, I will talk to my lawyer"],
    "address and photos": ["Hi", "Where is your office?", "Can you send me photos of MC-1204?", "And the floor plan?"],
    "salam and emoji": ["Salam", "👍", "I want to rent"],
    "wrong number": ["Hi, is this Ahmed?", "Sorry wrong number"],
    "call after 6": ["Hi", "Can you call me after 6pm today?", "thanks"],
    "move a call": ["Hi", "Please call me tomorrow at 10", "Can we make the call 11 instead?", "thanks"],
    "video tour": ["Hi", "I'm abroad, can we do a video call to see MC-1204 on Thursday at 11am?"],
    "wife comes too": ["Hi", "Can I see MC-1204 on Tuesday at 4pm?", "My wife will come too, is that ok?"],
    "three flats": ["Hi", "Can I see MC-1204, BB-305 and JVC-88 on Saturday?"],
    "hello again": ["Hi", "I want to buy", "Hello"],
    "asked after a request": ["Hi", "Can I see MC-1204 on Tuesday at 4pm?", "I want to buy", "Dubai Marina"],
}
HANDOVER = {"visa", "complaint"}  # a person answers these, by design
BAD = re.compile(r"\bNone\b|\{|\}|\bnan\b|\[\]|  |\bnull\b|undefined|just to check: just to check", re.I)


def office():
    o = Office(EventLog())
    demo.company(o)
    leads.sync_listings(o, (Path(demo.__file__).parent / "demo_feed.xml").read_bytes(), by="demo-feed")
    return o


def play(name, msgs, confirms=False):
    """The conversation, then a day or two of quiet (follow-ups and reminders); the office and the chat. `confirms`: the
    broker confirms each viewing (the app's default) instead of Rania booking it."""
    reception.agent_confirms = lambda g: confirms
    clock = [MON]
    events.now = lambda: clock[0].isoformat(timespec="milliseconds")  # each event at the conversation's own time, never the real clock
    o, ph, t, handed = office(), f"97150{abs(hash(name)) % 10**7:07d}", MON, []
    for m in msgs:
        t += timedelta(minutes=2)
        clock[0] = t
        if isinstance(m, list):  # a burst: kept together, one reply
            for x in m[:-1]:
                reception.receive(o, ph, x, name_="Sara Khan", now=t)
            r = reception.message(o, ph, m[-1], name_="Sara Khan", now=t, received=reception.receive(o, ph, m[-1], name_="Sara Khan", now=t))
        else:
            r = reception.message(o, ph, m, name_="Sara Khan", now=t)
        if r.get("mode") == "human" and r.get("suggestion"):
            handed.append(m)
    for _ in range(6):  # each follow-up at its due time, as the app's sweep (every tick) sends it
        due = nudge.state(o.graph(), o.graph().nodes[f"chat:{ph}"], t)["next"]
        if not due or datetime.fromisoformat(due) > MON + timedelta(days=3):
            break
        t = clock[0] = max(t, datetime.fromisoformat(due))
        nudge.sweep(o, t)
    for at in (MON + timedelta(days=1, hours=1), MON + timedelta(days=3)):
        clock[0] = max(clock[0], at)
        nudge.sweep(o, at)
        reminders.sweep(o, at)
    return o, o.graph().nodes[f"chat:{ph}"], handed


def problems(name, chat, handed):
    out = [f"handed to a person on {m!r}" for m in handed if name not in HANDOVER]
    mine = [m for m in chat.props["messages"] if m["type"] == "sent"]
    sent = [m["text"] for m in mine]
    out += [f"sent twice: {s[:80]!r}" for i, s in enumerate(sent) if s in sent[:i]]
    out += [f"broken text: {s[:80]!r}" for s in sent if BAD.search(s)]
    asked = [q.strip() for m in mine if not m.get("nudge") and not m["text"].startswith(("Hi Sara!", "مرحباً Sara!"))  # a follow-up, or
             for q in re.findall(r"[^.!?؟\n]*[?؟]", m["text"])]                                                      # a hello back, may ask again
    out += [f"asked twice running: {q!r}" for a, q in zip(asked, asked[1:]) if q == a and len(q) > 12]
    return out


@pytest.fixture(autouse=True)
def _mode_back(monkeypatch):
    monkeypatch.setattr(reception, "agent_confirms", reception.agent_confirms)  # play() switches these: put back after each test
    monkeypatch.setattr(events, "now", events.now)


@pytest.mark.parametrize("confirms", [True, False], ids=["broker-confirms", "rania-books"])
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_no_repeats_no_broken_text_no_surprise_handover(name, confirms):
    _, chat, handed = play(name, SCENARIOS[name], confirms)
    assert problems(name, chat, handed) == []


def said(name, confirms=False):
    o, chat, _ = play(name, SCENARIOS[name], confirms)
    return o, [m["text"] for m in chat.props["messages"] if m["type"] == "sent"], chat


def test_options_asked_again_never_resend_the_cards():
    _, sent, _ = said("buyer all in one")
    assert sum(s.startswith("1. ") for s in sent) == 1 and any(s.startswith("The best fits are still the ones I sent above") for s in sent)


def test_dont_call_me_is_never_promised_a_call():
    o, sent, chat = said("no calls")
    assert sent[1].startswith("Of course, Sara. No calls") and not any("will call you" in s for s in sent)
    assert leads.no_calls(o.graph(), chat.deal)


def test_office_hours_are_answered_and_nothing_is_booked():
    o, sent, chat = said("office hours twice")
    assert sent[1].startswith("We're open") and not any(v.props.get("chat") == chat.props["phone"] for v in o.graph().of("viewing"))


def test_thanks_gets_welcome_then_a_smile_then_quiet():
    _, sent, _ = said("thanks after booking")
    assert sent[2] == "You're welcome, Sara! See you Tuesday 3 Nov, 4:00 PM." and sent[3] == "🙂" and sent[4].startswith("Hi Sara, a reminder")


def test_sellers_and_landlords_hear_about_their_own_property_never_listings():
    for name, opener in (("seller", "Happy to help you sell."), ("landlord", "Yes, we can help you let and manage it.")):
        _, sent, _ = said(name)
        assert sent[0].startswith(opener) and not any("best options" in s or s.startswith("1. ") or "Here's what fits" in s for s in sent), name


def test_a_complaint_gets_an_apology_and_the_owner():
    o, sent, chat = said("complaint")
    assert sent[1].startswith("I'm really sorry to hear that") and chat.props["mode"] == "human"


def test_a_wrong_number_gets_a_goodbye_and_nothing_after():
    _, sent, _ = said("wrong number")
    assert sent[-1] == "No problem at all, have a good day!"


def test_moving_a_call_moves_it():
    _, sent, _ = said("move a call")
    assert sent[2] == "Done: your phone call is now Tuesday 3 Nov, 11:00 AM with Omar."


def test_a_question_about_a_listing_is_answered_from_it():
    _, sent, _ = said("question mid-qualifying")
    assert sent[3].startswith("Yes: Unit 1204, Marina Crest has 2 parking.")


def test_several_listings_and_a_bare_time_are_heard():
    _, sent, _ = said("three flats")
    assert sent[1].startswith("Happy to show you MC-1204") and "Saturday 7 Nov" in sent[1]
    _, sent, _ = said("still available")
    assert any(s.startswith("Got it, Saturday 7 Nov, 11:00 AM. Which one would you like to see: ") for s in sent)


def test_after_fraud_or_a_cancelled_viewing_the_follow_up_fits():
    _, sent, _ = said("fraud")
    assert len(sent) == 2  # no follow-up after a payment-details message
    _, sent, _ = said("reschedule and cancel")
    assert sent[-1].startswith("Hi Sara, would you like another time to see Unit 1204")


def test_arabic_is_answered_in_arabic_once():
    _, sent, _ = said("arabic")
    assert sent[0].count("؟") == 1 and "دبي مارينا" not in sent[2]


# The app's default: the broker confirms each viewing; Rania holds the time and answers from it (docs/agent-confirms-spec.md)
def test_held_for_the_broker_the_client_is_told_and_nothing_is_booked():
    o, sent, chat = said("thanks after booking", True)
    v = next(v for v in o.graph().of("viewing") if v.props.get("chat") == chat.props["phone"])
    assert v.status == "requested" and v.props["confirm"] == "broker"
    assert sent[1].startswith("Thanks, I've noted you'd like to see Unit 1204") and "buy or to rent" not in sent[1]
    assert sent[2] == "You're welcome, Sara! Omar will confirm Tuesday 3 Nov, 4:00 PM with you." and sent[3] == "🙂"
    assert not any(s.startswith("Hi Sara, a reminder") for s in sent)  # nothing is reminded before it is booked


def test_a_held_viewing_moves_and_cancels():
    o, sent, chat = said("reschedule and cancel", True)
    assert sent[2] == "Done: I've asked for Wednesday 4 Nov, 5:00 PM instead. Omar will confirm it with you."
    assert sent[3].startswith("No problem, I've cancelled your request to see Unit 1204")
    assert not o.graph().of("viewing", chat.deal, "requested") and not o.graph().of("attention", chat.deal, "open")


def test_a_held_viewing_answers_news_a_companion_and_what_time():
    _, sent, _ = said("lived-in home", True)
    assert sent[2].startswith("Omar is checking Villa 88") and "Tuesday 3 Nov, 4:00 PM" in sent[2]
    _, sent, _ = said("wife comes too", True)
    assert sent[2].startswith("Of course, they're very welcome, Sara. See you Tuesday 3 Nov, 4:00 PM, once Omar confirms it.")
    _, sent, _ = said("next tuesday", True)
    assert sent[3] == "You asked to see Unit 1204, Marina Crest (MC-1204) on Tuesday 10 Nov, 4:00 PM. Omar will confirm it with you."


def test_the_broker_confirms_and_the_client_hears_booked():
    from diwan import viewings
    o, _, chat = said("written date", True)
    v = next(v for v in o.graph().of("viewing", status="requested") if v.props.get("chat") == chat.props["phone"])
    from diwan import inbox
    assert inbox.detail(o, chat.props["phone"], MON + timedelta(minutes=30))["owner_wait"]["confirm"] == "broker"  # the Inbox shows it
    r = viewings.answer(o, v.id, by=v.props["broker"], said="yes", now=MON + timedelta(minutes=30))
    assert r["text"].startswith("Good news, Sara: it's confirmed. Booked: Unit 1204") and o.graph().nodes[v.id].status == "booked"
    assert o.graph().nodes[f"deal:{chat.deal}"].props.get("stage") == "Viewing booked"


def test_on_the_calendar_the_held_viewing_becomes_the_booking():
    o, _, chat = said("written date", True)
    v = next(v for v in o.graph().of("viewing", status="requested") if v.props.get("chat") == chat.props["phone"])
    p = v.props
    r = reception.add_by_hand(o, by=p["broker"], broker=p["broker"], phone=p["chat"], name_=None, kind_id=p["kind"], ref=p["listing"],
                              when=datetime.fromisoformat(p["at"]) + timedelta(hours=1), now=MON + timedelta(minutes=30), confirmed=True)
    mine = [x for x in o.graph().of("viewing") if x.props.get("chat") == chat.props["phone"]]
    assert r["id"] == v.id and len(mine) == 1 and mine[0].status == "booked" and mine[0].props["at"].startswith("2026-11-12T12:00")



def test_a_confirmed_viewing_moved_by_the_client_waits_for_the_broker_again():
    from diwan import viewings
    reception.agent_confirms = lambda g: True
    o, ph = office(), "971500000777"
    for t, m in ((MON, "Hi"), (MON + timedelta(minutes=2), "Can I see MC-1204 on Tuesday at 4pm?")):
        reception.message(o, ph, m, name_="Sara Khan", now=t)
    v = next(v for v in o.graph().of("viewing") if v.props.get("chat") == ph)
    viewings.answer(o, v.id, by=v.props["broker"], said="yes", now=MON + timedelta(minutes=5))
    r = reception.message(o, ph, "Can we move it to Wednesday at 5pm?", name_="Sara Khan", now=MON + timedelta(minutes=9))
    v = o.graph().nodes[v.id]
    assert r["reply"] == "Done: I've asked for Wednesday 4 Nov, 5:00 PM instead. Omar will confirm it with you."
    assert v.status == "requested" and v.props["at"].startswith("2026-11-04T17:00")


def test_a_question_never_put_to_them_isnt_counted_as_not_sure():
    for confirms in (True, False):
        _, sent, _ = said("asked after a request", confirms)
        assert "rough idea" not in sent[-1] and not sent[-1].startswith("No problem"), sent[-1]


def test_a_follow_up_picks_up_the_question_left_open():
    for name, want in (("three flats", "Hi Sara, no rush: which would you like to see first, and at what time?"),
                       ("question mid-qualifying", "Hi Sara, no rush: how many bedrooms?")):  # never a listing "that fits" before it can
        for confirms in (True, False):
            _, _, chat = said(name, confirms)
            assert [m["text"] for m in chat.props["messages"] if m.get("nudge")][:1] == [want], (name, confirms)


def test_a_cancelled_request_isnt_offered_for_booking_in_the_inbox():
    from diwan import inbox
    o, _, chat = said("reschedule and cancel", True)
    assert inbox.detail(o, chat.props["phone"], MON + timedelta(days=3))["viewing_request"] is None

if __name__ == "__main__":
    lines = []
    for n, msgs in [(f"{n} [{m}]", (msgs, m == "broker confirms")) for n, msgs in SCENARIOS.items() for m in ("broker confirms", "rania books")]:
        _, ch, handed = play(n, *msgs)
        lines.append(f"\n=== {n} ({ch.props['mode']})")
        for m in ch.props["messages"]:
            if m["type"] in ("received", "sent"):
                lines.append(f"  {'client' if m['type'] == 'received' else 'RANIA ' if m['by'] == 'rania' else m['by'][:6]}: {m['text']}")
        for p in problems(n.split(" [")[0], ch, handed):
            lines.append(f"  !! {p}")
    Path(sys.argv[1] if len(sys.argv) > 1 else "transcripts.txt").write_text("\n".join(lines))
