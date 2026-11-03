"""The Front Desk (docs/closed-loop-spec.md, Room 1): the day from the records, the arrival, the modes, meeting notes, errands that
wait for a yes, reminders, and a PA for each person that sees only what their role may see."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diwan import demo, leads
from diwan.agents import frontdesk, nova, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)
PH = "971501230000"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    leads.sync_listings(o, (Path(demo.__file__).parent / "demo_feed.xml").read_bytes(), by="demo-feed")
    for li in o.graph().of("listing"):  # vacant, keys at the office: these book at once (docs/viewing-access-spec.md)
        o.log.append("listing.access", actor="layla", content={"ref": li.props["ref"], "mode": "instant", "by": "layla"})
    frontdesk.PENDING.clear()
    return o


def client(office, text="call me", ph=PH, who="Sara Khan"):
    return reception.message(office, ph, text, name_=who, now=NOON)


def talk(office, text, person="layla", session="s"):
    return nova.converse(office, text, person, session=session, now=NOON)


def test_the_day_leads_with_what_is_urgent(office):
    client(office)
    d = frontdesk.day(office, "layla", NOON + timedelta(minutes=20))
    assert d["greeting"].startswith("Afternoon, Layla" if NOON.hour >= 12 else "Morning, Layla")
    u = d["urgent"][0]
    assert u["kind"] == "call" and u["late"] and "Sara Khan" in u["text"] and d["top"][0]["text"] == u["text"]
    assert set(d) >= {"today", "pipeline", "money", "decisions", "errands", "reminders", "mode"}


def test_today_shows_the_clients_last_words_and_what_they_care_about(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Cash", "Now", "To live in", "UAE resident", "I like it. Can I see it today at 5pm?"):
        client(office, t)
    d = frontdesk.day(office, "layla", NOON)
    assert d["today"] and "Can I see it" in d["today"][0]["last"] and "Marina" in d["today"][0]["cares"]


def test_the_day_ends_with_two_lines(office):
    client(office)
    assert frontdesk.day(office, "layla", NOON)["wrap"] is None
    w = frontdesk.day(office, "layla", NOON.replace(hour=18))["wrap"]
    assert w.startswith("Today: 0 closed") and "First thing tomorrow: Sara Khan" in w


@pytest.mark.parametrize("text", ["Can you hear me?", "are you there?", "testing"])
def test_can_you_hear_me_is_not_a_question_about_a_deal(office, text):
    client(office)
    r = talk(office, text)
    assert r["text"].startswith("Yes, I can hear you") and not r.get("options")


def test_a_question_naming_nothing_does_not_read_out_the_pipeline(office):
    for i in range(8):
        client(office, "Hello", ph=f"97150123000{i}", who=f"Client {i}")
    r = talk(office, "What's the latest?")
    assert not r.get("options") and "Which deal" not in r["text"]


def test_a_price_entered_at_conversion_takes_back_nothing_the_client_said(office):
    from diwan import desk_stages
    client(office, "Hello")
    deal = office.graph().nodes[f"chat:{PH}"].deal
    keep = office.record_fact(deal, "deal_term", "I am looking for off plan mostly", "Sara Khan")
    desk_stages._record(office, deal, office.graph().nodes[f"deal:{deal}"].props["broker"], 2_000_000, {}, approved_by=None)
    assert office.graph().nodes[keep].status != "superseded"


def test_the_owner_blocks_their_own_time_after_a_yes(office):
    r = talk(office, "Can you please block my slot for 3:00 PM today? I'll be out for a business meeting")
    assert r["kind"] == "confirm" and "3:00 PM" in r["text"]
    assert not frontdesk.day(office, "layla", NOON)["today"]
    assert "blocked" in talk(office, "yes")["text"]
    [b] = frontdesk.day(office, "layla", NOON)["today"]
    assert b["what"] == "Blocked" and b["cares"] == ["Business meeting"]


def test_a_broker_blocks_only_their_own_calendar(office):
    r = frontdesk.say(office, "Block my 4pm tomorrow for 2 hours", "omar", session="o", now=NOON)
    assert r["kind"] == "confirm" and "to 06:00 PM" in r["text"] or "to 6:00 PM" in r["text"]
    frontdesk.say(office, "yes", "omar", session="o", now=NOON)
    from diwan import slots
    assert slots.blocks(office.graph(), "omar") and not slots.blocks(office.graph(), "hamza")


def test_novas_own_questions_are_not_your_decisions(office):
    client(office)
    office.log.append("question.asked", actor="nova", agent="nova", content={"to": "layla", "text": "Which team should take this?", "options": []})
    assert not frontdesk.day(office, "layla", NOON)["decisions"]


def test_a_call_in_the_pool_stops_moving(office):
    client(office)
    c = office.graph().of("attention", status="open")[0]
    raised = datetime.fromisoformat(c.props["raised"])
    leads.sweep(office, raised + timedelta(minutes=11))
    leads.sweep(office, raised + timedelta(minutes=61))
    assert not [x for x in leads.sweep(office, raised + timedelta(minutes=90)) if x.startswith("moved")]


def SOON():
    from datetime import timedelta
    return datetime.now(DUBAI) + timedelta(days=3)  # leads carry the real clock


def muse(monkeypatch, reply, command=None, seen=None):
    from types import SimpleNamespace
    from diwan.agents import runner

    def call(c, system, user, **k):
        if seen is not None:
            seen.append(user)
        return SimpleNamespace(data={"reply": reply, "command": command}, usage={})
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: True)
    monkeypatch.setattr(runner, "call", call)


def test_with_muse_a_natural_question_gets_a_natural_answer_from_the_whole_office(office, monkeypatch):
    client(office)
    seen = []
    muse(monkeypatch, "Sales has one call waiting and marketing is quiet.", seen=seen)
    r = frontdesk.say(office, "Uh, could you please tell me what the departments are working on?", "layla", session="n", now=NOON)
    assert r["text"].startswith("Sales has one call") and r["kind"] == "answer"
    assert "Sara Khan" in seen[0] and "Department Sales" in seen[0] and "Uh," not in seen[0]


def test_she_remembers_the_conversation(office, monkeypatch):
    seen = []
    muse(monkeypatch, "Sure.", seen=seen)
    frontdesk.say(office, "Let's talk about the marketing budget", "layla", session="m", now=NOON)
    frontdesk.say(office, "And what about next week?", "layla", session="m", now=NOON)
    assert "Let's talk about the marketing budget" in seen[1].split("The conversation so far")[1]


def test_a_natural_request_reaches_the_same_read_back(office, monkeypatch):
    muse(monkeypatch, "Let me confirm.", command="Block my 4pm tomorrow for meeting")
    r = frontdesk.say(office, "I've got to step out tomorrow around four for a thing", "layla", session="b", now=NOON)
    assert r["kind"] == "confirm" and "4:00 PM" in r["text"]


def test_muse_cannot_talk_her_past_a_refusal(office, monkeypatch):
    muse(monkeypatch, "Done.", command="Mark AED 50,000 received from Sara")
    assert frontdesk.say(office, "Sara paid", "layla", session="b", now=NOON)["kind"] == "refused"


def test_a_brokers_pa_never_sees_another_brokers_clients(office, monkeypatch):
    client(office)
    client(office, "Hello", ph="971501230001", who="Ali Rahman")
    g = office.graph()
    mine = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    seen = []
    muse(monkeypatch, "Ok.", seen=seen)
    frontdesk.say(office, "What should I worry about with my leads?", mine, session="o", now=NOON)
    assert "Sara Khan" in seen[0] and "Ali Rahman" not in seen[0] and "Department " not in seen[0]


def test_paying_is_refused_but_asking_about_a_payment_is_not(office, monkeypatch):
    muse(monkeypatch, "Not recorded.")
    assert frontdesk.say(office, "Could you just pay Ali's invoice for me?", "layla", session="p", now=NOON)["kind"] == "refused"
    assert frontdesk.say(office, "Did Ali pay the commission?", "layla", session="p", now=NOON)["kind"] != "refused"


def test_a_polite_request_is_refused_like_a_plain_one(office, monkeypatch):
    muse(monkeypatch, "Done.")
    for t in ("Could you approve the deposit for me?", "Can you sign the MOU?", "Please mark the deposit as received"):
        assert frontdesk.say(office, t, "layla", session="p", now=NOON)["kind"] == "refused", t
    assert frontdesk.say(office, "Can you tell me who should approve the deposit?", "layla", session="p", now=NOON)["kind"] != "refused"


def test_the_whole_day_is_blocked_after_a_yes(office):
    r = talk(office, "Can you block my calendar for the whole day tomorrow? I'll be off", session="w")
    assert r["kind"] == "confirm" and "as a day off" in r["text"]
    assert talk(office, "Yes", session="w")["kind"] == "done"
    assert [e for e in office.log.list() if e["type"] == "calendar.blocked" and e["content"]["kind"] == "off"]


def test_a_one_word_answer_finishes_the_block(office):
    assert talk(office, "Block my slot for the whole day", session="w2")["text"] == "Which day should I block?"
    assert talk(office, "Tomorrow.", session="w2")["kind"] == "confirm"


def test_changing_the_subject_drops_the_question(office):
    talk(office, "Block my slot", session="w3")
    assert talk(office, "What needs me today?", session="w3")["kind"] != "confirm"
    assert "w3" not in frontdesk.PENDING


def test_she_never_promises_what_did_not_happen(office, monkeypatch):
    muse(monkeypatch, "I'm about to block it.", command="Frobnicate the diary")
    r = frontdesk.say(office, "Sort out my thing", "layla", session="f", now=NOON)
    assert "about to" not in r["text"] and "nothing has been done" in r["text"]


def test_two_things_in_one_breath(office, monkeypatch):
    muse(monkeypatch, "No sales closed today.", command="Block my 4pm tomorrow for meeting")
    r = frontdesk.say(office, "Block four tomorrow, and how many sales today?", "layla", session="t", now=NOON)
    assert r["kind"] == "confirm" and r["text"].startswith("No sales closed today. Block")


def test_she_can_see_whether_a_lead_was_contacted_and_what_sold(office, monkeypatch):
    client(office)
    seen = []
    muse(monkeypatch, "None yet.", seen=seen)
    frontdesk.say(office, "Has anyone spoken to the new leads?", "layla", session="c", now=NOON)
    assert "First contact by a person: none recorded" in seen[0] and "Viewing booked: no" in seen[0]
    assert "Sales closed today: 0" in seen[0] and "No daily or monthly closing target" in seen[0]


def test_the_watch_chases_a_stalled_lead_once_a_day_and_the_second_day_tells_the_owner(office):
    from datetime import timedelta
    from diwan.agents import watch
    client(office)
    g = office.graph()
    broker = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    later = SOON()
    assert watch.walk(office, later)["chased"][broker] >= 1
    assert watch.headsups(office.log, broker, 0)[0]["text"].count("no first contact") == 1
    assert "I've chased" in watch.headsups(office.log, "layla", 0)[0]["text"]
    assert not watch.walk(office, later)["chased"]  # once a day
    assert watch.walk(office, later + timedelta(days=1))["stuck"]
    said = watch.headsups(office.log, "layla", 0)[-1]["text"]
    assert "Still stuck after a second chase" in said and "Sara Khan" in said


def test_the_watch_only_ever_talks_to_staff(office):
    from datetime import timedelta
    from diwan.agents import watch
    client(office)
    before = sum(e["type"] == "chat.sent" for e in office.log.list())
    watch.walk(office, SOON())
    assert sum(e["type"] == "chat.sent" for e in office.log.list()) == before


def test_she_tells_the_owner_what_she_chased_and_sees_every_desk(office, monkeypatch):
    from datetime import timedelta
    from diwan.agents import watch
    client(office)
    later = SOON()
    watch.walk(office, later)
    seen = []
    muse(monkeypatch, "Ok.", seen=seen)
    frontdesk.say(office, "What have you been doing?", "layla", session="k", now=later)
    assert "You chased" in seen[0] and "Finance room:" in seen[0] and "Compliance room:" in seen[0] and "Operations room:" in seen[0]


def test_a_broker_sees_only_their_own_chases_and_no_department_rooms(office, monkeypatch):
    from datetime import timedelta
    from diwan.agents import watch
    client(office)
    g = office.graph()
    broker = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    other = next(b for b in ("omar", "hamza", "nadia") if b != broker)
    later = SOON()
    watch.walk(office, later)
    seen = []
    muse(monkeypatch, "Ok.", seen=seen)
    frontdesk.say(office, "What should I do next overall?", other, session="z", now=later)
    assert "You chased" not in seen[0] and "Finance room:" not in seen[0] and "Compliance room:" not in seen[0]


def test_chase_everyone_is_done_without_a_read_back(office):
    from datetime import timedelta
    client(office)
    r = frontdesk.say(office, "Chase everyone", "layla", session="c2", now=SOON())
    assert r["kind"] == "done" and "chased" in r["text"]


def test_a_trigger_word_inside_a_question_stays_a_conversation(office, monkeypatch):
    muse(monkeypatch, "Because it's due on the sixth.")
    for t in ("So the money comes in by 6 we can expect I suppose. Why are you following up?", "Who should approve the invoice?", "Why did Priya sign it?"):
        r = frontdesk.say(office, t, "layla", session="q", now=NOON)
        assert r["by"] == "muse", t


def test_an_order_with_a_trigger_word_still_goes_to_its_team(office, monkeypatch):
    muse(monkeypatch, "Nope.")
    assert frontdesk.say(office, "Approve the deposit", "layla", session="q2", now=NOON)["kind"] == "refused"


def test_off_the_open_mic_she_stays_silent_when_it_was_not_for_her(office, monkeypatch):
    muse(monkeypatch, "")
    r = frontdesk.say(office, "Go off youtubers", "layla", session="v", now=NOON, voice=True)
    assert r["kind"] == "silent" and not frontdesk.TURNS.get("v")


def test_typed_she_always_answers(office, monkeypatch):
    muse(monkeypatch, "")
    assert frontdesk.say(office, "Go off youtubers", "layla", session="v2", now=NOON)["text"] == "Okay."


def test_no_then_a_new_request_drops_the_old_one_and_carries_on(office, monkeypatch):
    from diwan.agents import lobby
    muse(monkeypatch, "Noted.", command="Tell Omar what's the update on the budget")
    r = frontdesk.say(office, "Ask Omar to check the budget", "layla", session="n2", now=NOON)
    assert r["kind"] == "confirm"
    r = frontdesk.say(office, "Don't send it, just ask him what the update is on the budget", "layla", session="n2", now=NOON)
    assert r["kind"] == "confirm" and "update on the budget" in r["text"] and "due" not in r["text"].split("Shall")[0]


def test_a_search_keeps_the_conversation_and_does_not_repeat_the_question(office, monkeypatch):
    seen = []
    monkeypatch.setattr(frontdesk, "_search", lambda p: seen.append(p) or {"text": "1. Emirates AED 900", "cited": []})
    muse(monkeypatch, "", command="Research flights from Dubai to Mumbai on the night of 2 November")
    frontdesk.TURNS["s1"] = [{"who": "Layla", "text": "Flights to Mumbai on 2 November"}]
    r = frontdesk.say(office, "These flight tickets in dirhams please", "layla", session="s1", now=NOON)
    assert "Mumbai" in seen[0] and "AED" in seen[0]
    assert r["text"].startswith("1. Emirates") and r["spoken"] and "*" not in r["spoken"]


def test_what_she_looked_up_needs_no_approval_and_leaves_nothing_waiting(office, monkeypatch):
    monkeypatch.setattr(frontdesk, "_search", lambda p: {"text": "1. Emirates AED 900", "cited": []})
    r = talk(office, "Research flights to Mumbai", session="s2")
    assert r["kind"] == "answer" and "approved" not in r["text"] and not frontdesk.errands(office, "layla")
    assert "s2" not in frontdesk.PENDING


def test_a_question_about_flights_is_not_a_new_search(office, monkeypatch):
    called = []
    monkeypatch.setattr(frontdesk, "_search", lambda p: called.append(p))
    muse(monkeypatch, "The cheapest was AED 791.")
    r = frontdesk.say(office, "Have you got the cheapest option of the flights?", "layla", session="s3", now=NOON)
    assert r["by"] == "muse" and not called


def test_a_sentence_that_starts_with_yes_approves_nothing(office, monkeypatch):
    from diwan.agents import lobby
    assert talk(office, "Ask Joseph to prepare Form F for Marina", session="e1")["kind"] == "confirm"
    assert frontdesk.say(office, "Yes, I can hear you, Layla.", "layla", session="e1", now=NOON)["kind"] != "done"
    assert not office.graph().of("lobby") and "e1" in lobby.DRAFTS
    assert frontdesk.say(office, "Yes, send it", "layla", session="e1", now=NOON)["kind"] == "done"


def test_a_restart_does_not_lose_the_conversation(office, monkeypatch):
    seen = []
    muse(monkeypatch, "Ok.", seen=seen)
    frontdesk.say(office, "How long is that flight?", "layla", session="r1", now=NOON, history=[{"who": "You", "text": "Flights to Mumbai please"}])
    assert "Flights to Mumbai" in seen[0]


def test_hello_mid_conversation_is_not_the_morning_greeting(office, monkeypatch):
    muse(monkeypatch, "Yes, go on.")
    frontdesk.TURNS["h1"] = [{"who": "Layla", "text": "About the sales team"}]
    assert frontdesk.say(office, "Hello.", "layla", session="h1", now=NOON)["text"] == "Yes, go on."


@pytest.fixture
def mailbox(monkeypatch):
    from diwan.providers import email
    sent = []
    monkeypatch.setattr(email, "available", lambda: True)
    monkeypatch.setattr(email, "send", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def test_an_email_is_read_back_in_full_and_goes_only_on_a_yes(office, mailbox):
    r = talk(office, "Send an email to alif@example.com about her upcoming event", session="m1")
    assert r["kind"] == "confirm" and "To: alif@example.com" in r["text"] and "Subject: Her upcoming event" in r["text"] and not mailbox
    assert talk(office, "Yes, send it", session="m1")["text"] == "Sent to alif@example.com."
    assert len(mailbox) == 1 and any(e["type"] == "email.sent" for e in office.log.list())


def test_no_means_no_email(office, mailbox):
    talk(office, "Email alif@example.com about the event", session="m2")
    assert "Cancelled" in talk(office, "no", session="m2")["text"] and not mailbox


def test_her_own_voice_cannot_send_an_email(office, mailbox):
    talk(office, "Email alif@example.com about the event", session="m3")
    frontdesk.say(office, "Yes, I can hear you, Layla.", "layla", session="m3", now=NOON)
    assert not mailbox


def test_she_asks_for_an_address_she_does_not_have_and_remembers_it(office, mailbox):
    assert talk(office, "Email Alif about the event", session="m4")["text"] == "What's Alif's email address?"
    assert "To: alif@example.com" in talk(office, "It's alif at example dot com", session="m4")["text"]
    talk(office, "Yes", session="m4")
    assert "To: alif@example.com" in talk(office, "Email Alif about the launch", session="m5")["text"]


def test_a_blank_in_the_draft_stops_the_send(office, mailbox, monkeypatch):
    monkeypatch.setattr(frontdesk, "_write", lambda *a: "Hi, the event is on [date].")
    talk(office, "Email alif@example.com about the event", session="m6")
    assert "brackets" in talk(office, "Yes", session="m6")["text"] and not mailbox


def test_bank_details_and_compliance_never_go_by_email(office, mailbox):
    assert talk(office, "Email alif@example.com about our bank details", session="m7")["kind"] == "refused"
    assert talk(office, "Email alif@example.com about the screening result", session="m8")["kind"] == "refused"
    assert not mailbox


def test_a_failed_send_is_said_and_kept(office, mailbox, monkeypatch):
    from diwan.providers import email

    def down(*a):
        raise OSError("mail server down")
    monkeypatch.setattr(email, "send", down)
    talk(office, "Email alif@example.com about the event", session="m9")
    assert "nothing was sent" in talk(office, "Yes", session="m9")["text"]
    assert any(e["type"] == "email.failed" for e in office.log.list())


def test_with_no_mailbox_she_says_so_and_drafts(office):
    r = talk(office, "Send an email to Alif about the event", session="m11")
    assert r["text"].startswith("No mailbox is connected yet") and r["kind"] == "confirm"


def test_a_general_question_is_answered_plainly_not_sold(office, monkeypatch):
    monkeypatch.setattr(frontdesk, "_search", lambda p: {"text": "Clear and 31 degrees tomorrow, says Meteoblue.", "cited": []})
    r = talk(office, "Research the weather in Dubai tomorrow", session="w9")
    assert r["text"] == "Clear and 31 degrees tomorrow, says Meteoblue."


def test_a_question_that_only_starts_like_the_briefing_is_not_the_briefing(office, monkeypatch):
    muse(monkeypatch, "Prices are up this week.")
    r = frontdesk.say(office, "What's happening in the Dubai property market this week?", "layla", session="b9", now=NOON)
    assert r["by"] == "muse"
    assert talk(office, "What's happening?", session="b10")["kind"] == "brief"


def test_a_staff_pa_drafts_but_does_not_send(office, mailbox):
    r = frontdesk.say(office, "Email alif@example.com about the event", "omar", session="m10", now=NOON)
    assert "To:" not in r["text"]
    frontdesk.say(office, "Yes", "omar", session="m10", now=NOON)
    assert not mailbox


def test_the_mail_goes_over_ssl_as_the_owner(monkeypatch):
    import smtplib
    from diwan.providers import email
    log = []

    class Fake:
        def __init__(self, host, port, timeout):
            log.append((host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, u, p):
            log.append(u)

        def send_message(self, m):
            log.append((m["From"], m["To"], m["Subject"]))
    for k, v in {"EMAIL_HOST": "smtp.example.com", "EMAIL_USER": "layla@example.com", "EMAIL_PASSWORD": "x"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(smtplib, "SMTP_SSL", Fake)
    email.send("alif@example.com", "Hello", "Body")
    assert log == [("smtp.example.com", 465), "layla@example.com", ("layla@example.com", "alif@example.com", "Hello")]


def test_a_reminder_keeps_the_time_it_was_given(office):
    assert "8:00 AM" in talk(office, "Remind me tomorrow early morning to review the script", session="r2")["text"]
    assert "Thursday 29 Oct, 8:00 AM: Check the notes" in talk(office, "Remind me Thursday 29 Oct at 08:00: check the notes", session="r3")["text"]
    assert "7:30 PM" in talk(office, "Remind me tomorrow at 7:30 pm to call Sara", session="r4")["text"]
    assert "9:00 AM" in talk(office, "Remind me Thursday to call Ali", session="r5")["text"]


def test_a_correction_moves_the_reminder_it_does_not_set_a_second(office):
    talk(office, "Remind me tomorrow evening to review the script", session="r6")
    r = talk(office, "Move my reminder to tomorrow early morning", session="r6")
    assert "8:00 AM" in r["text"]
    assert [x["text"] for x in frontdesk.day(office, "layla", NOON)["reminders"]] == ["Review the script"]


def test_the_same_reminder_is_not_set_twice(office):
    talk(office, "Remind me tomorrow at 9am to call Ali", session="r7")
    assert talk(office, "Remind me tomorrow at 9am to call Ali", session="r7")["text"] == "That reminder is already set."


def test_cancel_my_reminder(office):
    talk(office, "Remind me tomorrow to call Ali", session="r8")
    assert "Cancelled" in talk(office, "Cancel my reminder", session="r8")["text"]
    assert not frontdesk.day(office, "layla", NOON)["reminders"]


def test_the_notebook_keeps_what_was_said_and_crosses_it_off(office):
    assert talk(office, "Note down call the bank; renew the licence", session="n3")["text"] == "Noted 2 things in your notebook."
    assert talk(office, "Note renew the licence", session="n3")["text"] == "That's already in your notebook."
    assert [n["text"] for n in frontdesk.day(office, "layla", NOON)["notes"]] == ["Call the bank", "Renew the licence"]
    assert "Crossed off: Call the bank" in talk(office, "Cross off the bank from my notebook", session="n3")["text"]
    assert "Cleared 1" in talk(office, "Clear my notebook", session="n3")["text"]


def test_a_natural_sentence_reaches_the_notebook_and_she_can_read_it_back(office, monkeypatch):
    seen = []
    muse(monkeypatch, "", command="Note review the script; call Priya", seen=seen)
    assert "Noted 2" in frontdesk.say(office, "Keep these for me please, the script and Priya", "layla", session="n4", now=NOON)["text"]
    muse(monkeypatch, "Two things.", seen=seen)
    frontdesk.say(office, "What's in my notebook?", "layla", session="n5", now=NOON)
    assert "Their notebook: Review the script" in seen[-1]


def test_note_down_in_the_middle_of_a_sentence_splits_into_items(office, monkeypatch):
    muse(monkeypatch, "Nope.")
    r = frontdesk.say(office, "We are writing a notebook of points. Please note down: call the bank, review the villa script, and renew the licence.", "layla", session="n7", now=NOON)
    assert r["text"] == "Noted 3 things in your notebook."
    assert [n["text"] for n in frontdesk.notes(office.log, "layla")] == ["Call the bank", "Review the villa script", "Renew the licence"]


def test_a_long_sentence_that_names_a_deal_still_reaches_muse(office, monkeypatch):
    muse(monkeypatch, "Sure.")
    r = frontdesk.say(office, "I was thinking about the villa on the palm and whether the client who asked about it last week ever got an answer", "layla", session="n8", now=NOON)
    assert r["by"] == "muse"


def test_remind_me_of_those_things_means_the_notebook(office):
    assert talk(office, "Remind me tomorrow of those things", session="n9")["text"] == "What should I remind you about?"
    frontdesk.add_notes(office, "layla", "Call the bank")
    assert "Go through your notebook" in talk(office, "Remind me tomorrow of those things", session="n9")["text"]


def test_one_persons_notebook_is_not_anothers(office):
    frontdesk.add_notes(office, "layla", "Private thing")
    assert not frontdesk.notes(office.log, "omar")
    with pytest.raises(KeyError):
        frontdesk.finish_note(office, "N1", by="omar")


def test_a_reminder_about_the_notebook_reads_it_out_on_a_live_call(office):
    from datetime import timedelta
    from diwan.agents import watch
    frontdesk.add_notes(office, "layla", "Call the bank")
    talk(office, "Remind me tomorrow at 10am to check my notebook", session="n6")
    frontdesk.sweep(office, NOON + timedelta(days=1))
    said = watch.headsups(office.log, "layla", 0)[-1]["text"]
    assert "From your notebook: Call the bank" in said


def test_her_own_questions_are_not_on_anyones_desk(office, monkeypatch):
    from diwan.agents import nova
    nova._ask_back(office, "r", "layla", "Which deal do you mean?", [], "why")
    seen = []
    muse(monkeypatch, "Ok.", seen=seen)
    frontdesk.say(office, "What's on my desk overall?", "layla", session="d1", now=NOON)
    assert "Which deal do you mean" not in seen[0]


def test_a_whatsapp_to_a_client_is_read_back_and_goes_on_a_yes(office, monkeypatch):
    from diwan.agents import reception
    client(office)
    sent = []
    monkeypatch.setattr(reception, "person_sends", lambda o, phone, text, *, by: sent.append((phone, text)))
    r = talk(office, "Send Sara Khan a WhatsApp saying we will call you this afternoon", session="wa1")
    assert r["kind"] == "confirm" and "Sara Khan" in r["text"] and "afternoon" in r["text"] and not sent
    assert talk(office, "Yes, send it", session="wa1")["text"] == "Sent."
    assert sent == [(PH, "We will call you this afternoon")]


def test_a_whatsapp_never_carries_bank_or_compliance_words(office):
    client(office)
    assert talk(office, "Send Sara Khan a WhatsApp saying our IBAN is below", session="wa2")["kind"] == "refused"
    assert talk(office, "Message Sara Khan saying the screening is done", session="wa3")["kind"] == "refused"


def test_a_meeting_keeps_who_it_is_with_and_can_move_and_be_cancelled(office):
    r = talk(office, "Book a meeting with Priya tomorrow at 3pm about the audit", session="c1")
    assert r["kind"] == "confirm" and "Meeting with Priya" in r["text"] and "about the audit" in r["text"]
    talk(office, "Yes", session="c1")
    assert "Meeting with Priya" in talk(office, "Move my meeting with Priya to 5pm", session="c1")["text"]
    talk(office, "Yes", session="c1")
    b = office.graph().of("block", status="active")[0]
    assert "T17:00" in b.props["start"] and b.props["reason"] == "Meeting with Priya about the audit"
    assert talk(office, "Cancel my meeting with Priya", session="c1")["kind"] == "confirm"
    talk(office, "Yes", session="c1")
    assert not office.graph().of("block", status="active")


def test_part_of_a_day_is_blocked_with_the_reason(office):
    r = talk(office, "Block Tuesday afternoon for a dentist appointment", session="c2")
    assert r["kind"] == "confirm" and "2:00 PM to 6:00 PM" in r["text"] and "Dentist appointment" in r["text"]


def test_she_warns_of_a_double_booking(office):
    talk(office, "Block my 3pm tomorrow for the bank", session="c3")
    talk(office, "Yes", session="c3")
    assert talk(office, "Book a meeting with Omar tomorrow at 3pm", session="c4")["text"].startswith("You're busy then.")


def test_she_can_read_the_calendar(office, monkeypatch):
    talk(office, "Block my 3pm tomorrow for the bank", session="c5")
    talk(office, "Yes", session="c5")
    seen = []
    muse(monkeypatch, "You're busy then.", seen=seen)
    assert "The bank" in frontdesk.say(office, "Am I free tomorrow afternoon around three?", "layla", session="c6", now=NOON)["text"]  # read by rules
    frontdesk.say(office, "Should I move the bank thing, given tomorrow?", "layla", session="c6", now=NOON)
    assert "Their calendar:" in seen[0] and "The bank" in seen[0]


def test_in_two_hours_and_every_monday(office):
    from datetime import timedelta
    assert "2:00 PM" in talk(office, "Remind me in 2 hours to call the bank", session="r9")["text"]
    r = talk(office, "Remind me every Monday at 9am to check the pipeline", session="r10")
    assert "then every week: Check the pipeline" in r["text"]
    t = next(x for x in frontdesk.reminders(office.graph(), "layla") if x.props.get("repeat"))
    frontdesk.sweep(office, frontdesk._at(t.props["due"]) + timedelta(minutes=1))
    again = [x for x in frontdesk.reminders(office.graph(), "layla") if x.props.get("repeat")]
    assert len(again) == 1 and frontdesk._at(again[0].props["due"]) == frontdesk._at(t.props["due"]) + timedelta(days=7)


def test_remembering_a_bill_is_not_paying_it(office, monkeypatch):
    muse(monkeypatch, "", command="Note sign the lease; pay the DEWA bill")
    r = frontdesk.say(office, "I need to remember to sign the lease and pay the DEWA bill", "layla", session="t1", now=NOON)
    assert r["kind"] == "done" and len(frontdesk.notes(office.log, "layla")) == 2
    assert frontdesk.say(office, "Sign the lease", "layla", session="t1b", now=NOON)["kind"] == "refused"


def test_crossing_off_ignores_little_words(office):
    frontdesk.add_notes(office, "layla", "Renew the trade licence; Buy a gift for Alif")
    assert "gift" in talk(office, "Tick off the gift", session="t2")["text"]


def test_a_real_question_is_never_silence(office, monkeypatch):
    monkeypatch.setattr(frontdesk, "_search", lambda p: {"text": "About 30 minutes.", "cited": []})
    muse(monkeypatch, "")
    assert frontdesk.say(office, "How long does it take to drive to the Marina?", "layla", session="q9", now=NOON, voice=True)["text"] == "About 30 minutes."


@pytest.mark.parametrize("text,told", [("I'm calling my lawyer, this is unacceptable", True), ("Please pay the new IBAN AE07 0331", True),
                                       ("I'm ready to buy today", True), ("Thanks", False), ("Is it still available?", False)])
def test_what_the_owner_hears_the_moment_it_happens(office, text, told, monkeypatch):
    from diwan import events
    from diwan.agents import watch
    monkeypatch.setattr(events, "now", lambda: NOON.isoformat())  # at noon: at night good news waits for the morning
    client(office, text)
    assert watch.alerts(office, NOON + timedelta(minutes=1)) == (1 if told else 0)
    assert bool(watch.headsups(office.log, "layla", 0)) == told
    assert watch.alerts(office, NOON + timedelta(minutes=2)) == 0  # once


def test_old_messages_do_not_set_off_alerts(office, monkeypatch):
    from diwan import events
    from diwan.agents import watch
    monkeypatch.setattr(events, "now", lambda: NOON.isoformat())
    client(office, "I'm calling my lawyer")
    assert watch.alerts(office, NOON + timedelta(hours=3)) == 0


def test_cancel_my_reminder_is_not_swallowed_by_a_waiting_read_back(office):
    talk(office, "Remind me tomorrow to call Ali", session="p1")
    talk(office, "Block my 3pm tomorrow for the bank", session="p1")
    assert "Call Ali" in talk(office, "Cancel my reminder", session="p1")["text"]
    assert "p1" not in frontdesk.PENDING


def test_hey_pocket_answers_from_what_was_said_in_the_meeting(office, monkeypatch):
    seen = []
    muse(monkeypatch, "Omar sends the offer by Friday.", seen=seen)
    frontdesk.start_pocket(office, "layla")
    frontdesk.line(office, "layla", "We agreed that Omar will send the offer by Friday")
    assert frontdesk.pocket_ask(office, "What did we just agree?", "layla")["text"] == "Omar sends the offer by Friday."
    assert "Omar will send the offer" in seen[0]


@pytest.mark.parametrize("text", ["Did you know if you come to Dubai Science?", "So did you listen to them or did you open the door?"])
def test_overheard_talk_on_the_open_mic_is_not_looked_up(office, monkeypatch, text):
    muse(monkeypatch, "", command=None)
    monkeypatch.setattr(frontdesk, "_search", lambda p: pytest.fail("she searched the web for something overheard"))
    assert frontdesk.say(office, text, "layla", session="v1", now=NOON, voice=True)["kind"] == "silent"


def test_a_plain_hour_keeps_the_hour_people_mean(office):
    assert "10:00 AM" in talk(office, "Remind me tomorrow at 10 to call the bank")["text"]
    assert "4:00 PM" in talk(office, "Remind me tomorrow at 4 to see the auditor")["text"]


def test_a_misheard_hour_is_read_as_the_hour(office):
    r = talk(office, "Remind me to call the bank tomorrow at for pm")
    assert "4:00 PM" in r["text"]


def test_a_reminder_and_a_note_in_one_breath_are_both_kept(office):
    r = talk(office, "Remind me tomorrow at 9am to call the bank and note down buy a gift for Dana")
    assert r["kind"] == "done" and "gift" in r["text"]
    assert [n for n in frontdesk.notes(office.log, "layla") if "gift" in n["text"]]
    assert [t for t in frontdesk.reminders(office.graph(), "layla") if t.props["action"] == "Call the bank"]


def test_without_muse_she_still_gives_each_departments_position(office):
    r = talk(office, "What are the departments working on?")
    assert "Here's where each department stands" in r["text"] and "Marketing" not in r.get("error", "")


def test_arrival_happens_once_a_day(office):
    assert frontdesk.arrive(office, "layla", NOON)["first"]
    assert not frontdesk.arrive(office, "layla", NOON + timedelta(hours=1))["first"]
    assert frontdesk.arrive(office, "layla", NOON + timedelta(days=1))["first"]


def test_the_owner_sees_the_pipeline_a_broker_does_not(office):
    assert frontdesk.day(office, "layla", NOON)["pipeline"]
    assert frontdesk.day(office, "omar", NOON)["pipeline"] is None and frontdesk.day(office, "omar", NOON)["money"] is None
    assert frontdesk.day(office, "ahmed", NOON)["money"]


def test_remind_me_is_a_task_with_a_time_and_reaches_the_person_once(office):
    r = talk(office, "Remind me Thursday to call Sara")
    assert r["kind"] == "done" and "Thursday" in r["text"]
    t = frontdesk.reminders(office.graph(), "layla")[0]
    assert t.props["action"] == "Call Sara" and datetime.fromisoformat(t.props["due"]).hour == 9
    at = datetime.fromisoformat(t.props["due"]) + timedelta(minutes=1)
    assert frontdesk.sweep(office, at - timedelta(hours=1)) == []
    assert frontdesk.sweep(office, at) == [f"reminded {t.id}"]
    assert frontdesk.sweep(office, at + timedelta(minutes=1)) == []
    frontdesk.finish_reminder(office, t.id, by="layla")
    assert not frontdesk.reminders(office.graph(), "layla")


def test_someone_elses_reminder_is_not_yours_to_finish(office):
    talk(office, "Remind me tomorrow at 10am to call Sara", person="omar")
    t = frontdesk.reminders(office.graph(), "omar")[0]
    with pytest.raises(PermissionError):
        frontdesk.finish_reminder(office, t.id, by="hamza")


def test_a_draft_waits_for_a_yes_and_nothing_is_sent(office):
    n = len(office.log.list())
    r = talk(office, "Draft a reply to Ahmed about the invoice")
    assert r["kind"] == "confirm" and "Ahmed" in r["text"] and frontdesk.errands(office, "layla")
    assert not [e for e in office.log.list()[n:] if e["type"] in ("chat.sent", "notify.sent")]
    assert talk(office, "yes")["text"].startswith("Approved.")
    assert not frontdesk.errands(office, "layla")


def test_a_draft_cancelled_is_gone(office):
    talk(office, "Email Karim about the viewing")
    assert "Cancelled" in talk(office, "no")["text"] and not frontdesk.errands(office, "layla")


def test_someone_elses_errand_cannot_be_confirmed(office):
    eid = talk(office, "Email Karim about the viewing")["errand"]
    with pytest.raises(KeyError):
        frontdesk.decide_errand(office, eid, by="omar", yes=True)


def test_travel_without_a_connection_says_so_and_books_nothing(office):
    r = talk(office, "Check ticket prices to London")
    assert r["kind"] == "unknown" and "Nothing was booked" in r["text"] and not frontdesk.errands(office, "layla")


@pytest.mark.parametrize("text,kind", [("Mark AED 50,000 received from Sara", "mark_received"), ("Clear the screening match for Karim", "clear_hit"),
                                       ("Send Sara our bank details", "send_bank_details"), ("Change the settings for follow-ups", "change_settings"),
                                       ("Sign the Form F for Karim", "sign")])
def test_what_only_a_person_may_do_is_refused_and_logged(office, text, kind):
    r = talk(office, text)
    assert r["kind"] == "refused"
    assert any(e["type"] == "agent.refused" and e["content"]["kind"] == kind for e in office.log.list())


def test_a_pa_never_changes_how_an_agent_runs(office):
    assert talk(office, "Set Rania to autopilot")["kind"] == "refused"


def test_who_has_not_called_back(office):
    client(office)
    r = talk(office, "Who hasn't called Sara back?")
    assert "owes Sara a call" in r["text"] and r["cites"]
    assert "Nobody owes" in talk(office, "Who hasn't called Ali back?")["text"]


def test_what_the_owner_relays_goes_on_the_file_after_a_yes(office):
    client(office, "I want to buy, 2 bed in Dubai Marina")
    r = talk(office, "Sara now wants 3 beds, not 2")
    assert r["kind"] == "confirm" and "Sara Khan" in r["text"]
    g = office.graph()
    deal = g.nodes[f"chat:{PH}"].deal
    assert g.nodes[f"deal:{deal}"].props["answers"]["bedrooms"]["value"] == 2  # nothing yet
    talk(office, "yes")
    assert office.graph().nodes[f"deal:{deal}"].props["answers"]["bedrooms"]["value"] == 3


def test_do_not_disturb_and_back(office):
    assert "Do not disturb is on" in talk(office, "Do not disturb")["text"]
    assert frontdesk.mode(office.graph(), "layla") == "dnd"
    talk(office, "I'm back")
    assert frontdesk.mode(office.graph(), "layla") == "normal"


def test_meeting_mode_is_silent_and_answers_only_to_its_name(office):
    client(office)
    assert "Listening" in talk(office, "Hey Pocket")["text"]
    assert talk(office, "We agreed to reduce the fee.")["kind"] == "silent"
    r = talk(office, "Hey Pocket, who hasn't called Sara back?")
    assert r["kind"] != "silent" and r["text"]


def test_after_the_meeting_decisions_and_action_items_with_the_exact_words(office):
    client(office, "I want to buy, 2 bed in Dubai Marina")
    talk(office, "I'm in a meeting")
    for t in ("We agreed to run the Marina campaign in November.", "Omar will call the developer by Thursday.", "Sara now wants 3 beds, not 2."):
        talk(office, t)
    r = talk(office, "Meeting is over")
    assert r["decisions"] == ["We agreed to run the Marina campaign in November."]
    assert r["actions"][0]["who"] == "Omar" and r["actions"][0]["quote"] == "Omar will call the developer by Thursday."
    g = office.graph()
    assert [c for c in g.of("lobby") if c.props["to"] == "omar"]  # a task in the right room
    assert frontdesk.mode(g, "layla") == "normal"
    deal = g.nodes[f"chat:{PH}"].deal
    assert g.nodes[f"deal:{deal}"].props["answers"].get("bedrooms", {}).get("value") != 3 and "Sara now wants 3 beds" in r["text"]  # nothing goes on a file without a yes
    talk(office, "Yes")
    assert office.graph().nodes[f"deal:{deal}"].props["answers"]["bedrooms"]["value"] == 3


def test_a_brokers_pa_sees_only_their_own_clients(office):
    client(office)
    client(office, "Hello", ph="971501230001", who="Ali Rahman")
    g = office.graph()
    mine = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    r = frontdesk.say(office, "What did Ali say?", mine, session="b", now=NOON)
    assert r["kind"] == "unknown" and "Not recorded" in r["text"] and r["pa"].endswith("'s PA")
    assert "Nobody owes" in frontdesk.say(office, "Who hasn't called Ali back?", mine, session="b", now=NOON)["text"]  # another broker's card stays out of it


def test_a_staff_pa_says_whats_waiting_on_them(office):
    client(office)
    g = office.graph()
    mine = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    r = frontdesk.say(office, "What's waiting on me?", mine, session="b", now=NOON)
    assert "Sara Khan" in r["text"]


def test_marketing_sees_no_deals(office):
    client(office)
    r = frontdesk.say(office, "Tell me about Sara", "maya", session="m", now=NOON)
    assert r["kind"] == "unknown"


def test_a_staff_pa_refuses_too_and_hands_work_through_the_board(office):
    assert frontdesk.say(office, "Mark AED 50,000 received", "omar", session="o", now=NOON)["kind"] == "refused"
    r = frontdesk.say(office, "Tell Finance the deposit came in by tomorrow", "omar", session="o", now=NOON)
    assert r["kind"] == "confirm"
    frontdesk.say(office, "yes", "omar", session="o", now=NOON)
    assert [c for c in office.graph().of("lobby") if c.props["to"] == "ahmed"]


def test_a_brokers_pa_books_and_sends_only_on_a_yes(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Cash", "Now", "To live in", "UAE resident"):
        client(office, t)
    g = office.graph()
    broker = g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"]
    n = len(office.graph().nodes[f"chat:{PH}"].props["messages"])
    r = frontdesk.say(office, "Send Sara the 3 closest options", broker, session="b", now=NOON)
    assert r["kind"] == "confirm" and len(office.graph().nodes[f"chat:{PH}"].props["messages"]) == n
    assert frontdesk.say(office, "yes", broker, session="b", now=NOON)["text"] == "Sent."
    assert len(office.graph().nodes[f"chat:{PH}"].props["messages"]) == n + 1


def test_the_sales_manager_can_ask_about_the_team(office):
    client(office)
    assert "Not recorded" in frontdesk.say(office, "Who's slowest to call back this week?", "rashid", session="r", now=NOON)["text"]
    r = frontdesk.say(office, "Give Omar's leads to Hamza", "rashid", session="r", now=NOON)
    assert r["kind"] == "confirm"
