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
