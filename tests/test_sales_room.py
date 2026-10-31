"""The Sales room (docs/closed-loop-spec.md, Room 2): the promise and the broker's limit are one number, a missed call moves on,
every call ends in an outcome, leads that don't start on WhatsApp, duplicates, new listings for waiting clients, the fraud guard."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from diwan import demo, inbox, leads, sales
from diwan.agents import nudge, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)  # a Wednesday
PH = "971501230000"
QUAL = ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Cash", "Now", "To live in", "UAE resident")


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    leads.sync_listings(o, (Path(demo.__file__).parent / "demo_feed.xml").read_bytes(), by="demo-feed")
    return o


def say(office, text, ph=PH, now=NOON, who="Sara Khan"):
    return reception.message(office, ph, text, name_=who, now=now)


def deal(office, ph=PH):
    g = office.graph()
    return g.nodes[f"deal:{g.nodes[f'chat:{ph}'].deal}"].props


def card(office, ph=PH):
    return leads.open_card(office.graph(), ph)


def test_the_promise_to_the_client_is_the_owners_number(office):
    sales.set_settings(office, {"call_minutes": 20, "pool_minutes": 90}, by="layla")
    r = say(office, "Can someone call me please?")
    assert "will call you in the next 20 minutes" in r["reply"]
    assert datetime.fromisoformat(card(office).props["due"]) == NOON + timedelta(minutes=20)


def test_off_shift_she_does_not_promise_minutes(office):
    r = say(office, "call me", now=NOON.replace(hour=23))
    assert "shortly" in r["reply"] and "minutes" not in r["reply"]


def test_the_rules_are_the_owners_and_stay_sensible(office):
    with pytest.raises(PermissionError):
        sales.set_settings(office, {"call_minutes": 5}, by="omar")
    with pytest.raises(ValueError):
        sales.set_settings(office, {"pool_minutes": 5, "call_minutes": 10}, by="layla")
    with pytest.raises(ValueError):
        sales.set_settings(office, {"sweep_time": "late"}, by="layla")


def test_the_broker_sees_the_last_three_messages(office):
    for t in ("Hello", "I saw the Marina one", "Is it near the metro?", "call me"):
        say(office, t)
    c = inbox.listing(office, view="attention", person=deal(office)["broker"], now=NOON)[0]["attention"]
    assert len(c["last"]) == 3 and {"who": "client", "text": "call me"} in c["last"]


def test_a_missed_call_moves_to_the_next_free_broker_and_keeps_the_client_covered(office):
    say(office, "call me")
    c, first = card(office), deal(office)["broker"]
    done = leads.sweep(office, NOON + timedelta(minutes=11))
    next_up = deal(office)["broker"]
    assert next_up != first and f"moved {c.id} to {next_up}" in done
    g = office.graph()
    assert g.nodes[c.id].props["who"] == next_up and g.nodes[c.id].props["moved_from"] == first and not g.nodes[c.id].props.get("overdue")


def test_a_follow_up_the_broker_set_does_not_move_when_it_runs_late(office):
    say(office, "Hello")
    leads.follow_up_on(office, PH, by=deal(office)["broker"], at=NOON + timedelta(hours=1), kind="call", note="", now=NOON)
    before = deal(office)["broker"]
    assert not any(x.startswith("moved") for x in leads.sweep(office, NOON + timedelta(hours=2)))
    assert deal(office)["broker"] == before


def test_after_a_call_the_lead_needs_an_outcome_until_there_is_one(office):
    say(office, "call me")
    broker = deal(office)["broker"]
    leads.clear(office, card(office).id, "called", by=broker)
    chat = office.graph().nodes[f"chat:{PH}"]
    assert sales.needs_outcome(office.graph(), chat)
    assert [r["chat"] for r in sales.board(office, broker, NOON)["outcome"]] == [PH]
    sales.record_outcome(office, PH, "no_response", by=broker, now=NOON)
    assert not sales.needs_outcome(office.graph(), office.graph().nodes[f"chat:{PH}"])


def test_not_interested_needs_a_reason_from_the_list_and_closes_the_lead(office):
    say(office, "call me")
    broker = deal(office)["broker"]
    with pytest.raises(ValueError):
        sales.record_outcome(office, PH, "not_interested", by=broker, reason="whatever")
    with pytest.raises(ValueError):
        sales.record_outcome(office, PH, "not_interested", by=broker, reason="other")
    sales.record_outcome(office, PH, "not_interested", by=broker, reason="found_elsewhere")
    d = deal(office)
    assert d["stage"] == "Lost" and d["outcome"]["reason"] == "found_elsewhere"


def test_follow_up_on_a_date_is_a_card_then_and_converted_is_the_convert_step(office):
    say(office, "Hello")
    broker = deal(office)["broker"]
    with pytest.raises(ValueError):
        sales.record_outcome(office, PH, "follow_up", by=broker)
    with pytest.raises(ValueError):
        sales.record_outcome(office, PH, "converted", by=broker)
    sales.record_outcome(office, PH, "follow_up", by=broker, at=NOON + timedelta(days=2), now=NOON)
    assert datetime.fromisoformat(card(office).props["due"]) == NOON + timedelta(days=2)


def test_only_their_broker_or_a_manager_records_it(office):
    say(office, "Hello")
    other = "nadia" if deal(office)["broker"] != "nadia" else "hamza"
    with pytest.raises(PermissionError):
        sales.record_outcome(office, PH, "no_response", by=other)
    sales.record_outcome(office, PH, "no_response", by="rashid")


def test_qualifying_three_of_eight_and_qualified_only_when_complete(office):
    for t in QUAL[:3]:
        say(office, t)
    p = sales.progress(office.graph(), office.graph().nodes[f"chat:{PH}"].deal)
    assert p["done"] == 2 and p["of"] == 8 and not p["complete"]
    with pytest.raises(ValueError, match="2 of 8"):
        inbox.set_stage(office, PH, "Qualified", by=deal(office)["broker"])


def test_a_budget_out_of_range_is_asked_once(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed"):
        say(office, t)
    r = say(office, "My budget is 20k")
    assert "AED 20,000" in r["reply"] and "full budget" in r["reply"]
    assert deal(office)["answers"]["budget_aed"]["quote"] == "My budget is 20k"
    r = say(office, "Sorry, 1.4 million")
    assert deal(office)["answers"]["budget_aed"]["value"] == 1_400_000 and "full budget" not in r["reply"]


def test_a_confirmed_small_budget_stands(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "My budget is 20k"):
        say(office, t)
    r = say(office, "Yes that's right")
    assert "full budget" not in r["reply"] and r["qualify"]["next"]["key"] == "finance"


def test_the_heat_score_is_the_owners_rule(office):
    for t in QUAL:
        say(office, t)
    h = sales.heat(office.graph(), office.graph().nodes[f"chat:{PH}"].deal)
    assert h["hot"] and h["score"] == h["of"] == 3
    assert not deal(office).get("hot")  # shown on the lead; it calls the broker in only if the owner ticks it


def test_when_the_owner_ticks_it_the_score_makes_the_lead_hot(office):
    reception.set_recommend(office, {"hot_on": ["pick", "score"]}, by="layla")
    for t in QUAL:
        r = say(office, t)
    assert deal(office)["hot"]["why"] == "met the heat rules" and card(office).props["reason"].startswith("🔥")


def test_a_mortgage_without_pre_approval_is_not_finance_ready(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Mortgage", "not yet", "Now"):
        say(office, t)
    parts = {p["name"]: p["ok"] for p in sales.heat(office.graph(), office.graph().nodes[f"chat:{PH}"].deal)["parts"]}
    assert parts["Finance ready"] is False


def test_spam_and_job_seekers_are_not_leads(office):
    r = say(office, "Hi, are you hiring? I'd like to send my CV")
    assert "property enquiries" in r["reply"] and deal(office)["stage"] == "Lost" and not card(office)


def test_can_you_manage_my_apartment_is_a_landlord(office):
    say(office, "Can you manage my apartment?")
    assert deal(office)["qtype"] == "landlord"


def test_is_it_still_available_confirms_then_asks_live_or_invest(office):
    r = say(office, "Is MC-1204 still available?")
    assert "is still available" in r["reply"] and "to live in, or to invest" in r["reply"]


def test_is_this_still_available_with_nothing_named_asks_which(office):
    assert "Which property do you mean" in say(office, "Is this still available?")["reply"]


def test_payment_details_are_flagged_while_a_person_has_the_chat_too(office):
    say(office, "Hello")
    reception.hand_over(office, PH, reason="asked for a person", now=NOON)
    say(office, "Please pay into my new account instead")
    assert [t for t in office.graph().of("task") if t.props.get("fraud")]


def test_cash_said_with_the_budget_is_an_answer_not_a_compliance_question(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "1 bed"):
        say(office, t)
    r = say(office, "Sorry, 1.4 million, cash")
    assert r["mode"] == "ai" and deal(office)["answers"]["finance"]["value"] == "Cash" and "personally" not in r["reply"]


def test_a_real_cash_question_still_goes_to_a_person(office):
    say(office, "I want to buy")
    assert "personally" in say(office, "Can I pay it all in cash?")["reply"]


def test_visas_and_tax_go_to_a_person(office):
    r = say(office, "Will I get a golden visa with this?")
    assert "personally" in r["reply"] and card(office)


def test_payment_details_are_never_acted_on(office):
    say(office, "Hello")
    r = say(office, "Please send the deposit to this new account instead")
    assert "never change payment details" in r["reply"]
    g = office.graph()
    t = next(t for t in g.of("task") if t.props.get("fraud"))
    assert t.props["needs_person"] == "priya"
    who = {n.props["to"] for n in g.of("notice") if "Possible payment fraud" in n.label}
    assert {"priya", "ahmed"} <= who and all(n.props["level"] == "now" for n in g.of("notice") if "Possible payment fraud" in n.label)


def test_rania_never_sends_bank_details_from_a_model(office):
    import re
    assert re.search(sales.IBAN, "Pay to AE070331234567890123456")


def test_after_stop_a_new_message_reaches_a_person_not_rania(office):
    say(office, "Hello")
    say(office, "stop")
    r = say(office, "What's the price of MC-1204?")
    assert r["mode"] == "stopped" and r["reply"] is None and "Wrote again" in card(office).props["reason"]
    assert reception.person_sends(office, PH, "Hi, happy to help", by=deal(office)["broker"])


@pytest.mark.parametrize("word", ["стоп", "停止", "बंद करो"])
def test_stop_in_other_languages(office, word):
    say(office, "Hello")
    say(office, word)
    assert deal(office)["optout"]


def test_a_walk_in_is_a_lead_with_where_it_came_from(office):
    r = sales.add_lead(office, by="hamza", name_="Mona Said", phone="971509990000", source="walk_in", note="Wants a 2 bed in JVC", ref="MC-1204", now=NOON)
    d = deal(office, r["chat"])
    assert d["broker"] == "hamza" and card(office, r["chat"]).props["kind"] == "call"
    row = inbox.detail(office, r["chat"], now=NOON)
    assert row["source"] == "walk_in" and not row["window_open"]  # WhatsApp's window opens only when they write


def test_a_referral_says_who_referred_them_and_bad_input_is_refused(office):
    with pytest.raises(ValueError, match="referred"):
        sales.add_lead(office, by="omar", name_="A B", phone="971509990001", source="referral")
    with pytest.raises(ValueError, match="phone"):
        sales.add_lead(office, by="omar", name_="A B", phone="12", source="phone")
    r = sales.add_lead(office, by="omar", name_="A B", phone="971509990001", source="referral", referred_by="Karim", now=NOON)
    assert "from Karim" in card(office, r["chat"]).props["reason"]


def test_two_conversations_with_one_email_are_proposed_not_merged(office):
    sales.add_lead(office, by="omar", name_="Dina One", phone="971509990002", source="phone", email="dina@example.com", now=NOON)
    sales.add_lead(office, by="hamza", name_="D Two", phone="971509990003", source="phone", email="dina@example.com", now=NOON)
    [x] = sales.duplicates(office.graph())
    assert x["why"] == "email" and x["two_brokers"]
    with pytest.raises(PermissionError):
        leads.merge(office, "971509990002", "971509990003", by="omar")
    leads.merge(office, "971509990002", "971509990003", by="rashid")
    assert not sales.duplicates(office.graph())


def test_a_new_listing_goes_to_a_waiting_client_only_on_the_brokers_yes(office):
    for t in QUAL:
        say(office, t)
    n0 = len(office.graph().nodes[f"chat:{PH}"].props["messages"])
    office.log.append("listing.added", actor="omar", content={"ref": "NEW-1", "title": "Unit 9", "community": "Dubai Marina", "type": "apartment", "beds": 1,
                                                              "price_aed": 1_300_000, "permit": "P1", "offering": "sale", "status": "available"})
    now = datetime.now(DUBAI)
    [m] = sales.matches(office.graph(), now)
    assert m["ref"] == "NEW-1" and len(office.graph().nodes[f"chat:{PH}"].props["messages"]) == n0
    reception.receive(office, PH, "Hi again", now=now)
    sales.send_match(office, PH, "NEW-1", by=deal(office)["broker"])
    assert "NEW-1" in office.graph().nodes[f"chat:{PH}"].props["messages"][-1]["text"]
    assert not sales.matches(office.graph(), now)


def test_an_expired_licence_takes_no_new_leads(office):
    for b in ("hamza", "nadia"):
        leads.set_agent(office, b, "licence_expiry", "2020-01-01", by="layla")
    assert leads.pick(office.graph(), NOON)[0] == "omar"


def test_a_licence_about_to_end_warns_once(office):
    leads.set_agent(office, "omar", "licence_expiry", "2026-11-10", by="layla")
    assert "licence omar" in sales.sweep(office, NOON)
    assert "licence omar" not in sales.sweep(office, NOON + timedelta(minutes=1))


def test_no_show_gets_one_message_and_a_second_is_the_brokers(office):
    for t in QUAL + ("I like it. Can I see it on Saturday at 11am?",):
        say(office, t)
    g = office.graph()
    v = g.of("viewing")[0]
    office.log.append("appointment.noshow", actor="omar", deal=v.deal, content={"id": v.id})
    assert sales.no_show(office, v.id, 1, NOON) == "sent"
    assert "sorry we missed you" in office.graph().nodes[f"chat:{PH}"].props["messages"][-1]["text"]
    office.log.append("appointment.booked", actor="rania", deal=v.deal, content={"id": "V9", "listing": None, "broker": v.props["broker"], "at": NOON.isoformat(),
                                                                                  "customer": "Sara", "chat": PH, "kind": "x", "kind_name": "Viewing", "minutes": 30, "where": "property"})
    office.log.append("appointment.noshow", actor="omar", deal=v.deal, content={"id": "V9"})
    assert sales.no_show(office, "V9", 1, NOON) == "second" and not deal(office).get("hot")


def test_the_morning_list_says_who_to_call_and_comes_once(office):
    say(office, "call me")
    b = deal(office)["broker"]
    at = NOON.replace(hour=8, minute=31)
    assert f"sweep {b}" in sales.sweep(office, at)
    assert f"sweep {b}" not in sales.sweep(office, at + timedelta(minutes=1))
    assert any("to call: Sara Khan" in n.label for n in office.graph().of("notice"))


def test_a_reminder_before_a_call_at_a_time_they_chose(office):
    say(office, "Hello", now=NOON)
    say(office, "Call me tomorrow at 3pm", now=NOON)
    at = NOON.replace(hour=15) + timedelta(days=1)
    assert sales.sweep(office, at - timedelta(minutes=30)).count("call reminder V1") == 0
    assert "call reminder V1" in sales.sweep(office, at - timedelta(minutes=14))
    assert "call reminder V1" not in sales.sweep(office, at - timedelta(minutes=13))


def test_a_call_in_the_clients_own_time_goes_on_the_calendar_in_dubai_time(office):
    say(office, "Hello")
    r = say(office, "Call me tomorrow at 2pm London time")
    v = office.graph().of("viewing")[0]
    assert datetime.fromisoformat(v.props["at"]).astimezone(DUBAI).hour == 18  # 2 PM in London in October is 5 or 6 PM here
    assert "Dubai time" in r["reply"]


def test_the_leads_broker_goes_on_the_visit_and_the_listings_agent_is_told(office):
    for t in QUAL:
        say(office, t)
    g = office.graph()
    ref = deal(office)["recommended"][0]
    broker = deal(office)["broker"]
    agent = "hamza" if broker != "hamza" else "nadia"
    office.log.append("listing.added", actor="omar", content={"ref": ref.replace("listing:", ""), "agent": agent})
    r = say(office, "I like it. Can I see it on Saturday at 11am?")
    assert r["reply"].startswith("Booked:") and f"with {broker.title()}" in r["reply"]
    assert office.graph().of("viewing")[0].props["broker"] == broker
    assert any("get them the keys" in n.label for n in office.graph().of("notice") if n.props["to"] == agent)


def test_the_morning_brief_runs_monday_to_saturday_and_the_owner_can_change_it(office):
    sat, sun = datetime(2026, 10, 31, 8, tzinfo=DUBAI), datetime(2026, 11, 1, 8, tzinfo=DUBAI)
    assert sales.brief_day(office.graph(), sat) and not sales.brief_day(office.graph(), sun)
    sales.set_settings(office, {"brief_days": [6]}, by="layla")
    assert sales.brief_day(office.graph(), sun) and not sales.brief_day(office.graph(), sat)
    with pytest.raises(ValueError):
        sales.set_settings(office, {"brief_days": []}, by="layla")


def test_a_missing_outcome_is_nudged_once(office):
    say(office, "call me")
    b = deal(office)["broker"]
    leads.clear(office, card(office).id, "called", by=b)
    later = datetime.now(DUBAI) + timedelta(hours=3)
    assert f"outcome {PH}" in sales.sweep(office, later)
    assert f"outcome {PH}" not in sales.sweep(office, later + timedelta(minutes=1))


def test_a_person_in_a_meeting_gets_only_now(office):
    office.log.append("setting.changed", actor="layla", content={"person": "layla", "key": "mode", "value": "dnd"})
    assert leads.notify(office, "layla", "Viewing booked", kind="info")["content"]["status"] == "held"
    assert leads.notify(office, "layla", "A call", kind="call")["content"]["status"] == "shown"


def test_the_board_has_every_block_and_a_broker_sees_only_their_own(office):
    say(office, "call me")
    say(office, "Hello", ph="971501230001", who="Ali Rahman")
    mine = deal(office)["broker"]
    other = deal(office, "971501230001")["broker"]
    assert mine != other  # round-robin
    all_ = sales.board(office, "rashid", NOON)
    assert {"call_now", "hot", "new", "qualifying", "followups", "quiet", "brokers", "outcome"} <= set(all_) and all_["sees_all"]
    b = sales.board(office, mine, NOON)
    assert [r["chat"] for r in b["call_now"]] == [PH] and PH in [r["chat"] for r in b["new"]["rows"]]
    assert "971501230001" not in [r["chat"] for r in b["new"]["rows"]] and [x["id"] for x in b["brokers"]] == [mine]
    assert not sales.may_see(office.graph(), "971501230001", mine) and sales.may_see(office.graph(), "971501230001", "rashid")


def test_a_pooled_lead_is_visible_to_every_broker(office):
    say(office, "call me")
    other = "nadia" if deal(office)["broker"] != "nadia" else "hamza"
    assert not sales.may_see(office.graph(), PH, other)
    c = card(office)
    office.log.append("lead.pooled", actor="rania", deal=c.deal, content={"id": c.id, "chat": PH, "from": c.props["who"]})
    assert sales.may_see(office.graph(), PH, other)


def test_regenerate_replaces_the_suggestion_on_screen(office):
    say(office, "Hello")
    ev = reception.suggest_again(office, PH, by=deal(office)["broker"], now=NOON)
    assert ev["type"] == "chat.suggested"
    assert nudge  # (the chat keeps every suggestion; the Inbox shows the newest for the last message)
