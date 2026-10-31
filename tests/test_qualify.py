from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo, inbox, qualify
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)
PH = "971501230000"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def ans(**kw):
    return {k: {"value": v, "quote": str(v)} for k, v in kw.items()}


# ---------- the verdict, in code ----------

def test_verdicts_follow_the_form():
    f = qualify.form(Office(EventLog()).graph())
    assert f["version"] == 0 and set(f["types"]) == {"buyer", "tenant", "seller", "landlord"}
    assert qualify.evaluate(f, None, {})["verdict"] == "DISCOVERY"
    v = qualify.evaluate(f, "buyer", ans(areas="Dubai Marina"))
    assert v["verdict"] == "ASK_QUESTION" and v["next"]["key"] == "property_type"
    done = ans(areas="Dubai Marina", property_type="Apartment", bedrooms=2, budget_aed=2_700_000, finance="Cash", timeline="Now")
    assert qualify.evaluate(f, "buyer", done)["verdict"] == "PASS_TO_AGENT"


def test_ask_only_if_and_conditions():
    f = qualify.form(Office(EventLog()).graph())
    f["types"]["buyer"]["fields"][4]["required"] = True  # the owner makes "pre-approved?" required, but only for mortgages
    f["types"]["buyer"]["fields"] = [x | ({"required": True} if x["key"] == "mortgage_preapproved" else {}) for x in f["types"]["buyer"]["fields"]]
    base = dict(areas="Dubai Marina", property_type="Apartment", bedrooms=2, budget_aed=2_700_000, timeline="Now")
    assert qualify.evaluate(f, "buyer", ans(**base, finance="Cash"))["verdict"] == "PASS_TO_AGENT"
    v = qualify.evaluate(f, "buyer", ans(**base, finance="Mortgage"))
    assert v["verdict"] == "ASK_QUESTION" and v["next"]["key"] == "mortgage_preapproved"
    f["rules"]["buyer"] = {"qualify_when": [{"field": "budget_aed", "op": ">=", "value": "800000"}],
                           "not_fit_when": [{"field": "budget_aed", "op": "<", "value": "300000"}],
                           "not_fit_reply": "Thank you! Our listings start higher, but we'll keep your details."}
    assert qualify.evaluate(f, "buyer", ans(**base | {"budget_aed": 250_000}, finance="Cash"))["verdict"] == "NOT_A_FIT"
    held = qualify.evaluate(f, "buyer", ans(**base | {"budget_aed": 500_000}, finance="Cash"))
    assert held["verdict"] == "ASK_QUESTION" and held.get("hold") and "budget_aed >= 800000" in held["reasons"][0]
    assert qualify.holds({"field": "areas", "op": "in", "value": "Dubai Marina, JVC"}, ans(areas="Marina"))


def test_only_the_owner_changes_the_form_and_each_save_is_a_version(office):
    f = qualify.form(office.graph())
    f["types"]["buyer"]["fields"].append(qualify._f("golden_visa", "Golden visa", "Is a Golden Visa important to you?", "هل التأشيرة الذهبية مهمة؟",
                                                    "yesno", required=False))
    with pytest.raises(PermissionError):
        qualify.save_form(office, f, by="omar")
    bad = qualify.form(office.graph()) | {"types": {"buyer": {"label": "Buyer", "fields": [{"key": "x", "kind": "choice", "options": [],
                                                                                          "question_en": ""}]}}}
    with pytest.raises(ValueError):
        qualify.save_form(office, bad, by="layla")
    qualify.save_form(office, f, by="layla")
    g = office.graph()
    assert qualify.form(g)["version"] == 1 and any(x["key"] == "golden_visa" for x in qualify.form(g)["types"]["buyer"]["fields"])


# ---------- the conversation, by the rules (no model) ----------

def test_a_buyer_is_asked_one_question_at_a_time_and_qualifies(office):
    say = lambda t: reception.message(office, PH, t, name_="Sara Khan", now=NOON)  # noqa: E731
    r = say("Hi")
    assert "buy, rent, or sell" in r["reply"] and r["qualify"]["verdict"] == "DISCOVERY"
    r = say("I want to buy")
    assert r["qualify"]["type"] == "buyer" and r["reply"].endswith("Which area are you looking at?")
    r = say("Dubai Marina")
    assert r["qualify"]["next"]["key"] == "property_type"
    say("An apartment")
    r = say("2 bed")
    assert r["qualify"]["next"]["key"] == "budget_aed"
    r = say("Budget is 2.7 million")
    assert r["qualify"]["next"]["key"] == "finance"
    r = say("Cash")  # an answer to her own question, not a compliance topic
    assert r["by"] != "policy" and r["mode"] == "ai" and r["qualify"]["next"]["key"] == "timeline"
    r = say("Now")  # qualified: Rania recommends what fits (the owner's default: up to 3), and asks which one
    assert r["qualify"]["verdict"] == "PASS_TO_AGENT" and r["refs"] == ["listing:MC-1204"] and r["reply"].endswith("Which one interests you?")
    g = office.graph()
    deal = g.nodes[f"chat:{PH}"].deal
    assert g.nodes[f"deal:{deal}"].props["stage"] == "Qualified"
    assert not g.of("attention", status="open")  # the broker is told, not called in yet
    assert any("qualified" in n.label and "Rania sent 1 options" in n.label for n in g.of("notice"))
    r = say("The first one looks great")  # they pick one: a hot lead for the broker
    assert r["reply"].startswith("Great choice! Unit 1204, Marina Crest (MC-1204)") and "Would you like to see it?" in r["reply"]
    g = office.graph()
    card = g.of("attention", status="open")[0]
    assert card.props["kind"] == "call" and "Hot lead, ready to close: picked it MC-1204" in card.props["reason"]
    assert "The first one looks great" in card.props["reason"] and "Budget (AED): 2700000" in card.props["reason"]
    assert g.nodes[f"deal:{deal}"].props["hot"]["listing"] == "listing:MC-1204"
    answers = {a["key"]: a for a in qualify.state(g, deal)["answers"]}
    assert answers["budget_aed"]["quote"] == "Budget is 2.7 million"  # each answer keeps the customer's words


def test_not_a_fit_gets_the_owners_reply_and_closes(office):
    f = qualify.form(office.graph())
    f["rules"]["buyer"] = {"qualify_when": [], "not_fit_when": [{"field": "budget_aed", "op": "<", "value": "300000"}],
                           "not_fit_reply": "Thank you! Our homes start above that budget, but we'll keep your details."}
    qualify.save_form(office, f, by="layla")
    reception.message(office, PH, "I want to buy", name_="Ali", now=NOON)
    r = reception.message(office, PH, "My budget is 200k", now=NOON)
    assert r["qualify"]["verdict"] == "NOT_A_FIT" and r["reply"].startswith("Thank you! Our homes start above")
    g = office.graph()
    assert g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["stage"] == "Lost"


def test_a_quote_the_customer_never_wrote_is_dropped(office):
    reception.message(office, PH, "I want to buy", name_="Ali", now=NOON)
    deal = office.graph().nodes[f"chat:{PH}"].deal
    kept = qualify.record(office, deal, qtype=None, type_quote=None, said="I want to buy",
                          answers=[{"field": "budget_aed", "value": "5000000", "quote": "my budget is 5 million"}], by="rania", cause=None)
    assert kept == [] and "budget_aed" not in office.graph().nodes[f"deal:{deal}"].props.get("answers", {})


def test_api_form_is_owner_only(monkeypatch):
    monkeypatch.setattr(appmod.S, "office", Office(EventLog()))
    demo.seed(appmod.S.office)
    c = TestClient(appmod.app)
    f = c.get("/api/qualify/form").json()
    assert f["version"] == 0 and "buyer" in f["types"] and f["can_edit"] == ["layla"]
    assert c.post("/api/qualify/form", json={"form": f, "by": "omar"}).status_code == 403
    r = c.post("/api/qualify/form", json={"form": f, "by": "layla"})
    assert r.status_code == 200 and c.get("/api/qualify/form").json()["version"] == 1
    assert "Qualifying" in inbox.stage_names(appmod.S.office.graph())


# ---------- how strict each question is (the owner's choice) ----------

def test_not_sure_counts_only_where_the_owner_allows_it():
    f = qualify.form(None) if False else qualify.DEFAULT_FORM | {"version": 0}
    base = dict(areas="Dubai Marina", property_type="Apartment", bedrooms=2, finance="Cash")
    vague = lambda times=1: {"value": qualify.NOT_SURE, "quote": "not sure", "unsure": True, "times": times}  # noqa: E731
    # the budget is "must answer": not sure is asked again once, then a person follows up
    v = qualify.evaluate(f, "buyer", ans(**base, timeline="Now") | {"budget_aed": vague()})
    assert v["verdict"] == "ASK_QUESTION" and v["next"]["key"] == "budget_aed" and v["retry"] == "budget_aed"
    v = qualify.evaluate(f, "buyer", ans(**base, timeline="Now") | {"budget_aed": vague(2)})
    assert v["verdict"] == "ASK_QUESTION" and v["hold"] and v["stuck"] == ["budget_aed"] and v["next"] is None
    # the timeline allows "not sure": it counts, and the reason says so
    v = qualify.evaluate(f, "buyer", ans(**base, budget_aed=2_000_000) | {"timeline": vague()})
    assert v["verdict"] == "PASS_TO_AGENT" and "not sure, which the owner allows: When" in v["reasons"][1]
    # a condition on a not-sure answer is skipped, never failed or met
    f2 = f | {"rules": {"buyer": {"qualify_when": [{"field": "timeline", "op": "=", "value": "Now"}],
                                  "not_fit_when": [{"field": "timeline", "op": "!=", "value": "Now"}], "not_fit_reply": "x"}}}
    assert qualify.evaluate(f2, "buyer", ans(**base, budget_aed=2_000_000) | {"timeline": vague()})["verdict"] == "PASS_TO_AGENT"


def test_rania_asks_a_must_answer_question_again_then_the_broker_helps(office):
    say = lambda t: reception.message(office, PH, t, name_="Sara Khan", now=NOON)  # noqa: E731
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed"):
        say(t)
    r = say("Honestly I'm not sure")
    assert r["reply"].startswith("No problem, a rough idea is fine.") and r["qualify"]["next"]["key"] == "budget_aed"
    r = say("I don't know yet")
    assert "Omar will give you a call to help" in r["reply"] and r["qualify"]["stuck"] == ["budget_aed"]
    g = office.graph()
    card = g.of("attention", status="open")[0]
    assert card.props["kind"] == "call" and "Not sure about Budget (AED)" in card.props["reason"]
    r = say("Cash")  # she carries on with the other questions
    assert r["qualify"]["next"]["key"] == "timeline"
    r = say("Not sure yet")  # the timeline allows it, but the budget still holds the lead
    assert r["qualify"]["verdict"] == "ASK_QUESTION" and r["qualify"]["stuck"] == ["budget_aed"]
    r = say("About 2 million actually")  # a real answer later replaces "not sure", and the lead qualifies
    assert r["qualify"]["verdict"] == "PASS_TO_AGENT" and r["qualify"]["stuck"] == []
    open_ = office.graph().of("attention", status="open")  # the qualified card replaces the "help with the budget" one
    assert len(open_) == 1 and open_[0].props["reason"].startswith("Qualified lead:") and "When: Not sure" in open_[0].props["reason"]


def test_not_sure_is_fine_where_allowed_and_never_replaces_a_real_answer(office):
    reception.set_recommend(office, {"when": "never"}, by="layla")  # the qualified-lead card itself, without recommendations
    say = lambda t: reception.message(office, PH, t, name_="Sara Khan", now=NOON)  # noqa: E731
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash"):
        say(t)
    r = say("Not sure yet")  # the timeline allows it
    assert r["qualify"]["verdict"] == "PASS_TO_AGENT"
    answers = {a["key"]: a for a in r["qualify"]["answers"]}
    assert answers["timeline"]["value"] == qualify.NOT_SURE and answers["budget_aed"]["value"] == 2_700_000
    card = office.graph().of("attention", status="open")[0]
    assert "When: Not sure" in card.props["reason"]


def test_a_question_she_cannot_answer_reaches_the_broker_with_the_qualified_lead(office):
    reception.set_recommend(office, {"when": "never"}, by="layla")
    say = lambda t: reception.message(office, PH, t, name_="Sara Khan", now=NOON)  # noqa: E731
    say("I want to buy")
    r = say("Do you also sell yachts?")
    assert r["mode"] == "ai" and r["qualify"]["open_questions"] == ["Do you also sell yachts?"]
    for t in ("Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now"):
        r = say(t)
    assert r["qualify"]["verdict"] == "PASS_TO_AGENT"
    card = office.graph().of("attention", status="open")[0]
    assert "Asked, not answered yet: Do you also sell yachts?" in card.props["reason"]


# ---------- recommendations and the hot lead (the owner's setting) ----------

QUAL = ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now")


def test_only_the_owner_sets_recommendations_and_values_are_checked(office):
    with pytest.raises(PermissionError):
        reception.set_recommend(office, {"how_many": 2}, by="omar")
    with pytest.raises(ValueError, match="1 to 5"):
        reception.set_recommend(office, {"how_many": 9}, by="layla")
    v = reception.set_recommend(office, {"how_many": 2, "hot_on": ["viewing"]}, by="layla")
    assert reception.recommend_settings(office.graph()) == v == {"when": "after_qualified", "how_many": 2, "hot_on": ["viewing"]}


def test_no_listings_while_qualifying_unless_asked_and_never_more_than_the_limit(office):
    for i in range(5):
        office.add_listing(ref=f"M-{i}", title=f"Marina Tower {i}", community="Dubai Marina", type="apartment", beds=2,
                           price_aed=2_500_000 + i * 10_000, permit=f"P{i}", agent="omar")
    reception.set_recommend(office, {"how_many": 2}, by="layla")
    say = lambda t: reception.message(office, PH, t, name_="Sara Khan", now=NOON)  # noqa: E731
    say("I want to buy")
    r = say("Dubai Marina")  # an answer, not a request: no listings yet
    assert not [x for x in r["refs"] if x.startswith("listing:")] and r["reply"].count("?") == 1
    r = say("Do you have any 2 bed apartments?")  # asked: she answers, within the limit
    assert 0 < len([x for x in r["refs"] if x.startswith("listing:")]) <= 2
    for t in QUAL[2:]:
        r = say(t)
    assert r["qualify"]["verdict"] == "PASS_TO_AGENT" and len(r["refs"]) == 2 and r["reply"].count("\n1. ") == 1


def test_nothing_fits_goes_to_the_broker_and_a_viewing_request_is_hot_too(office):
    say = lambda t, ph=PH: reception.message(office, ph, t, name_="Sara Khan", now=NOON)  # noqa: E731
    for t in ("I want to buy", "Palm Jumeirah", "A villa", "6 bed", "Budget is 2 million", "Cash", "Now"):
        r = say(t)
    # nothing fits, even loosened (the area they named is kept): she says so plainly, and the broker finds options
    assert r["reply"] == "Thank you Sara! Omar will contact you shortly with options for a 6-bed villa in Palm Jumeirah around AED 2,000,000."
    card = office.graph().of("attention", status="open")[0]
    assert card.props["reason"].startswith("Qualified lead:")
    ph2 = "971501239999"
    for t in QUAL:
        say(t, ph2)
    r = say("Can I see it on Saturday at 11am?", ph2)  # one recommendation, and they ask to view it: hot, and booked
    g = office.graph()
    deal = g.nodes[f"chat:{ph2}"].deal
    assert g.nodes[f"deal:{deal}"].props["hot"]["why"] == "asked to view it" and g.of("viewing", status="booked")
