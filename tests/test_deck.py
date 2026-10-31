from datetime import datetime

import pytest

from diwan import demo
from diwan.agents import deck, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    demo.catalog(o)
    demo.kinds(o)
    demo.projects(o)
    return o


def hot(o, phone, *msgs):
    for t in msgs:
        reception.message(o, phone, t, name_="Amal Haddad", now=NOON)
    g = o.graph()
    return g.nodes[f"chat:{phone}"].deal


OFF_PLAN = ("I want to buy off-plan", "Dubai Creek Harbour", "An apartment", "2 bed", "Budget is 2 million", "Cash", "1-3 months", "The first one")


def test_a_hot_off_plan_lead_gets_a_deck_from_the_project_and_the_archive(office):
    deal = hot(office, "971500008001", *OFF_PLAN)
    g = office.graph()
    d = deck.view(g, deck.latest(g, deal).id)
    titles = [s["title"] for s in d["slides"]]
    assert titles == ["The property", "Why it fits", "Creek Vista Heights: payment plan and handover", "Documents"]
    assert "DR-134" in d["slides"][0]["text"] and d["slides"][0]["photo"]
    assert "Budget: AED 2,000,000 (“Budget is 2 million”)" in d["slides"][1]["text"]
    assert "10% on booking" in d["slides"][2]["text"] and d["slides"][2]["sources"][0].startswith("K")
    assert "brochure" in d["slides"][3]["text"] and d["slides"][3]["sources"][0].startswith("DOC")
    assert d["status"] == "live" and not [t for t in g.of("task", deal) if t.props.get("agent") == "deck"]  # nothing missing


def test_what_is_missing_becomes_a_task_for_the_broker_never_a_guess(office):
    deal = hot(office, "971500008002", "I want to buy off-plan", "Business Bay", "An apartment", "2 bed", "Budget is 2.4 million", "Cash", "1-3 months",
               "The first one")
    g = office.graph()
    d = deck.view(g, deck.latest(g, deal).id)
    assert "Bayline Residences" in d["slides"][2]["title"] and "No brochure or floor plan for Bayline Residences" in d["slides"][3]["text"]
    tasks = [t for t in g.of("task", deal) if t.props.get("agent") == "deck"]
    assert len(tasks) == 1 and "Ask the developer for the brochure and floor plan for Bayline Residences" in tasks[0].label
    assert tasks[0].props["needs_person"] == g.nodes[f"deal:{deal}"].props["broker"] == "hamza"
    deck.build(office, deal)  # remade: the task is not asked twice
    assert len([t for t in office.graph().of("task", deal) if t.props.get("agent") == "deck"]) == 1


def test_a_ready_deck_shows_price_and_viewing(office):
    deal = hot(office, "971500008003", "I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now",
               "The second one, Saturday at 11am")
    g = office.graph()
    d = deck.view(g, deck.latest(g, deal).id)
    assert d["slides"][2]["title"] == "Price and viewing" and "ready to move in" in d["slides"][2]["text"]


def test_only_the_broker_or_owner_approves_and_a_changed_budget_sends_it_back(office):
    deal = hot(office, "971500008004", *OFF_PLAN)
    did = deck.latest(office.graph(), deal).id
    with pytest.raises(PermissionError):
        deck.approve(office, did, by="omar")
    deck.approve(office, did, by="hamza")
    assert deck.view(office.graph(), did)["approved"][0]["by"] == "Hamza"
    reception.message(office, "971500008004", "Actually, my budget is 1.8 million", now=NOON)
    g = office.graph()
    v = deck.view(g, did)
    assert v["status"] == "sent_back" and v["slides"][1]["stale"] and v["approved"][0]["stale"]
    with pytest.raises(ValueError, match="sent back"):
        deck.approve(office, did, by="hamza")
