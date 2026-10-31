"""The front door (docs/front-door-spec.md): not ready yet is nurtured, not chased; coming back ready reopens the lead;
"call me" always reaches a person; what makes a lead hot is the owner's choice; a portal lead starts from its listing."""
from datetime import datetime

import pytest

from diwan import demo, inbox, leads
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import portals
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)
PH = "971501230000"
QUAL = ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now")


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def say(office, text, ph=PH):
    return reception.message(office, ph, text, name_="Sara Khan", now=NOON)


def deal_props(office, ph=PH):
    g = office.graph()
    return g.nodes[f"deal:{g.nodes[f'chat:{ph}'].deal}"].props


def test_only_looking_is_nurtured_not_chased(office):
    say(office, "Hi, is the Marina Crest unit still available?")
    r = say(office, "Thanks, I'm just looking for now")
    assert "take your time" in r["reply"] and "?" not in r["reply"]
    d = deal_props(office)
    assert d["nurture"]["to"] == "marketing" and d["nurture"]["quote"].startswith("Thanks, I'm just looking")
    assert not office.graph().of("attention", status="open")  # no broker time spent, nothing to go overdue
    [row] = inbox.listing(office, view="nurture")
    assert row["nurture"]["reason"] == "not ready yet" and inbox.counts(office)["nurture"] == 1
    [n] = reception.nurture_list(office.graph())
    assert n["why"] == "Not ready yet" and n["chat"] == PH


def test_a_preference_is_not_only_looking(office):
    say(office, "I want to buy")
    r = say(office, "Not interested in villas, an apartment please")
    assert not deal_props(office).get("nurture") and "take your time" not in r["reply"]


def test_nurtured_client_still_gets_answers_but_no_questions(office):
    say(office, "Hello")
    say(office, "Just browsing")
    r = say(office, "Thanks!")
    assert r["reply"] == "Anytime! I'm here whenever you're ready."
    r = say(office, "What are your office hours?")  # a question is answered, without a qualification question
    assert deal_props(office).get("nurture") and "buy, rent" not in r["reply"]


def test_a_question_rania_cant_answer_in_nurture_is_kept_without_a_handover(office):
    say(office, "Hello")
    say(office, "Just browsing")
    r = say(office, "Is the pool heated in winter?")
    g = office.graph()
    assert r["mode"] == "ai" and not g.of("attention", status="open") and deal_props(office).get("nurture")
    assert "Is the pool heated" in deal_props(office)["open_questions"][0]
    assert any("(in Nurture) asked" in n.props["text"] for n in g.of("notice"))


def test_coming_back_ready_reopens_even_while_a_person_has_the_chat(office):
    say(office, "Hello")
    say(office, "Just browsing")
    reception.person_sends(office, PH, "Hi, Omar here", by="omar")
    say(office, "I'm ready now, budget 2.7 million")
    assert not deal_props(office).get("nurture")


def test_coming_back_ready_reopens_and_tells_the_broker(office):
    say(office, "Hello")
    say(office, "Not now, maybe next year")
    r = say(office, "OK I'm ready now, I want to buy in Dubai Marina")
    d = deal_props(office)
    assert not d.get("nurture") and d["reopened"]["quote"].startswith("OK I'm ready now")
    assert any("is back and ready" in n.props["text"] for n in office.graph().of("notice"))
    assert r["qualify"]["type"] == "buyer"  # the same message is handled normally


def test_call_me_always_reaches_the_broker_and_rania_keeps_the_chat(office):
    say(office, "Hello")
    r = say(office, "Can someone call me please?")
    assert "will call you shortly" in r["reply"] and r["mode"] == "ai"
    [card] = office.graph().of("attention", status="open")
    assert card.props["kind"] == "call" and card.props["reason"].startswith("Asked for a call")
    assert not deal_props(office).get("hot")  # not qualified yet: a call, not a hot lead


def test_call_once_qualified_is_hot_when_the_owner_says_so(office):
    reception.set_recommend(office, {"hot_on": ["pick", "call"]}, by="layla")
    for t in QUAL:
        say(office, t)
    say(office, "Could you call me tonight?")
    assert deal_props(office)["hot"]["why"] == "asked for a call"
    [card] = office.graph().of("attention", status="open")
    assert card.props["reason"].startswith("🔥 Hot lead, ready to close: asked for a call")


def test_qualifying_can_make_a_lead_hot(office):
    reception.set_recommend(office, {"hot_on": ["qualified", "pick"]}, by="layla")
    for t in QUAL:
        r = say(office, t)
    assert deal_props(office)["hot"]["why"] == "qualified" and "\n1. " in r["reply"]
    [card] = office.graph().of("attention", status="open")
    assert card.props["reason"].startswith("🔥 Hot lead, ready to close: qualified")
    r = say(office, "The first one")  # picking one after that still records the property
    assert deal_props(office)["hot"]["listing"].startswith("listing:")
    assert [x for x in inbox.listing(office) if x["phone"] == PH][0]["hot"] != "yes"


def test_only_the_owner_sets_the_front_door(office):
    with pytest.raises(PermissionError):
        reception.set_front(office, {"nurture_to": "broker"}, by="omar")
    with pytest.raises(ValueError):
        reception.set_front(office, {"nurture_to": "nobody"}, by="layla")
    v = reception.set_front(office, {"nurture_to": "broker", "portal_template": "portal_enquiry"}, by="layla")
    assert reception.front_settings(office.graph()) == v


LEAD = {"data": {"name": "Fatima Noor", "phone": "+971 55 123 4567", "message": "Is this still available?",
                 "listing": {"reference": "MC-1204"}}}


def test_a_portal_lead_starts_from_the_listing_and_rania_asks_only_whats_missing(office):
    reception.set_front(office, {"portal_template": "portal_enquiry"}, by="layla")
    r = leads.portal_lead(office, portals.parse_lead("propertyfinder", LEAD), now=NOON)
    assert set(r["filled"]) == {"areas", "property_type", "bedrooms"} and r["template"] == "portal_enquiry"
    g = office.graph()
    a = g.nodes[f"deal:{r['deal']}"].props["answers"]
    assert a["areas"]["value"] == "Dubai Marina" and "MC-1204" in a["areas"]["source"] and "budget_aed" not in a
    sent = [m for m in g.nodes[f"chat:{r['chat']}"].props["messages"] if m["type"] == "sent"]
    assert sent[0]["text"].startswith("Hi Fatima, thank you for your enquiry about") and sent[0]["template"] == "portal_enquiry"
    assert g.of("attention", status="open")[0].props["kind"] == "call"  # the broker's call card stays
    q = reception.message(office, r["chat"], "Yes, still interested", now=NOON)["qualify"]
    assert q["type"] == "buyer" and q["next"]["key"] == "budget_aed"  # area, type and bedrooms are not asked again


def test_without_a_template_rania_does_not_message_a_portal_lead_first(office):
    r = leads.portal_lead(office, portals.parse_lead("propertyfinder", LEAD), now=NOON)
    assert r["template"] is None
    assert not [m for m in office.graph().nodes[f"chat:{r['chat']}"].props["messages"] if m["type"] == "sent"]


def test_a_building_named_in_full_is_found_among_many_listings(office):
    demo.catalog(office)  # 39 listings: "Gate" and "Marina" are shared words, "Marina Crest" is not
    r = reception.message(office, PH, "Hi, is the Marina Crest 2 bed still available? Can I see it Saturday at 4pm?", name_="Sara Khan", now=NOON)
    assert r["reply"].startswith("Booked: Unit 1204, Marina Crest (MC-1204)")


# ---- the lead profile: acting on a lead (docs/lead-profile-spec.md) ----

def test_the_profile_moves_a_lead_under_the_deal_desks_rules(office):
    say(office, "Hello")
    deal = office.graph().nodes[f"chat:{PH}"].deal
    broker = office.graph().nodes[f"deal:{deal}"].props["broker"]
    d = inbox.detail(office, PH)
    assert d["stages"][:5] == ["New", "Qualifying", "Qualified", "Viewing booked", "Viewed"] and d["stages"][-1] == "Lost"
    assert broker in d["desk"]["movers"] and "Won" not in d["stages"]
    with pytest.raises(PermissionError):
        inbox.set_stage(office, PH, "Qualified", by="nadia" if broker != "nadia" else "hamza")
    with pytest.raises(ValueError, match="reason"):
        inbox.set_stage(office, PH, "Lost", by=broker)
    inbox.set_stage(office, PH, "Lost", by=broker, reason="bought elsewhere")
    assert office.graph().nodes[f"deal:{deal}"].props["stage"] == "Lost"


def test_hot_and_not_hot_by_hand_and_the_broker_hears_it(office):
    say(office, "Hello")
    deal = office.graph().nodes[f"chat:{PH}"].deal
    leads.mark_hot(office, PH, on=True, by="layla", note="ready this week")
    d = office.graph().nodes[f"deal:{deal}"].props
    assert d["hot"]["why"] == "marked by Layla" and d["hot"]["quote"] == "ready this week"
    assert any("Layla marked Sara Khan hot" in n.props["text"] for n in office.graph().of("notice"))
    leads.mark_hot(office, PH, on=False, by="layla")
    assert "hot" not in office.graph().nodes[f"deal:{deal}"].props
    with pytest.raises(PermissionError):
        leads.mark_hot(office, PH, on=True, by="priya")


def test_follow_up_on_a_date_is_a_card_due_then_and_nothing_reaches_the_client(office):
    from datetime import timedelta
    say(office, "Hello")
    deal = office.graph().nodes[f"chat:{PH}"].deal
    broker = office.graph().nodes[f"deal:{deal}"].props["broker"]
    sent = len([m for m in office.graph().nodes[f"chat:{PH}"].props["messages"] if m["type"] == "sent"])
    at = NOON + timedelta(days=2)
    leads.follow_up_on(office, PH, by=broker, at=at, kind="call", note="after their trip", now=NOON)
    [card] = office.graph().of("attention", status="open")
    assert card.props["due"] == at.isoformat() and card.props["reason"].endswith(": after their trip") and card.props["who"] == broker
    assert len([m for m in office.graph().nodes[f"chat:{PH}"].props["messages"] if m["type"] == "sent"]) == sent
    with pytest.raises(ValueError, match="already has an open card"):
        leads.follow_up_on(office, PH, by=broker, at=at, kind="reply", note="", now=NOON)
    with pytest.raises(ValueError, match="ahead"):
        leads.follow_up_on(office, PH, by=broker, at=NOON, kind="call", note="", now=NOON)


def test_a_transfer_takes_the_open_card_with_it(office):
    say(office, "Hello")
    say(office, "Can someone call me please?")
    [card] = office.graph().of("attention", status="open")
    to = "hamza" if card.props["who"] != "hamza" else "nadia"
    leads.reassign(office, PH, to, by="layla")
    [moved] = office.graph().of("attention", status="open")
    assert moved.props["who"] == to and moved.props["due"] == card.props["due"]


def test_asked_no_calls_means_no_call_cards_and_no_promised_calls(office):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now"):
        r = say(office, t)
    deal = office.graph().nodes[f"chat:{PH}"].deal
    broker = office.graph().nodes[f"deal:{deal}"].props["broker"]
    for c in office.graph().of("attention", status="open"):
        leads.clear(office, c.id, "messaged", by=broker)
    leads.set_no_calls(office, PH, on=True, by=broker)
    assert inbox.listing(office)[0]["no_calls"]
    r = say(office, "The first one")  # a pick: no promised call
    assert "who will reply to you here shortly" in r["reply"] and "call you" not in r["reply"]
    cards = office.graph().of("attention", status="open")
    assert all(c.props["kind"] == "reply" for c in cards)
    g = office.graph()
    assert "asked not to be called" in reception.prompt_sources(g, deal, g.nodes[f"chat:{PH}"], "ok", listings=False)["pref:no_calls"]


def test_the_client_asking_for_a_call_turns_no_calls_off_and_the_broker_hears(office):
    say(office, "Hello")
    deal = office.graph().nodes[f"chat:{PH}"].deal
    broker = office.graph().nodes[f"deal:{deal}"].props["broker"]
    leads.set_no_calls(office, PH, on=True, by=broker)
    say(office, "Actually can someone call me please?")
    g = office.graph()
    assert not g.nodes[f"deal:{deal}"].props.get("no_calls")
    assert [c.props["kind"] for c in g.of("attention", status="open")] == ["call"]
    assert any("asked for a call, so" in n.props["text"] for n in g.of("notice"))
    with pytest.raises(PermissionError):
        leads.set_no_calls(office, PH, on=True, by="priya")


def test_merging_two_conversations_of_the_same_person(office):
    IG = "ig:sara.k"
    reception.message(office, IG, "Hi! I want to buy in Dubai Marina", name_="@sara.k", now=NOON)
    say(office, "Hello, it's Sara again from WhatsApp")
    a = office.graph().nodes[f"chat:{PH}"].deal
    b = office.graph().nodes[f"chat:{IG}"].deal
    broker = office.graph().nodes[f"deal:{a}"].props["broker"]
    with pytest.raises(PermissionError):
        leads.merge(office, PH, IG, by="priya")
    leads.merge(office, PH, IG, by=broker)
    g = office.graph()
    msgs = g.nodes[f"chat:{PH}"].props["messages"]
    assert any(m.get("chat") == IG and "Dubai Marina" in m["text"] for m in msgs)  # both histories, each marked
    assert g.nodes[f"deal:{a}"].props["answers"]["areas"]["source"].startswith("from @sara.k's other conversation")
    assert g.nodes[f"deal:{b}"].props["stage"] == "Lost" and IG not in [r["phone"] for r in inbox.listing(office)]
    assert g.nodes[f"deal:{a}"].props["stage"] == "Qualifying"  # the answers that came over move it on
    reception.message(office, IG, "What's the budget range there?", now=NOON)  # a new message on Instagram arrives in this lead
    g = office.graph()
    assert g.nodes[f"chat:{IG}"].deal == a and any(m.get("chat") == IG and m["text"] == "What's the budget range there?"
                                                   for m in g.nodes[f"chat:{PH}"].props["messages"])
    with pytest.raises(ValueError, match="already merged"):
        leads.merge(office, PH, IG, by=broker)
