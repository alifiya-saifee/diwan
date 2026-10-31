from datetime import datetime
from pathlib import Path

import pytest

from diwan import deal_kinds, demo, leads
from diwan.agents import reception
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
    return o


def talk(o, phone, *msgs):
    r = None
    for t in msgs:
        r = reception.message(o, phone, t, name_="Test Lead", now=NOON)
    return r


def test_only_the_owner_edits_the_deal_kinds_and_bad_ones_are_refused(office):
    ks = deal_kinds.kinds(office.graph())
    assert [k["name"] for k in ks] == ["Off-plan", "Ready sales", "Leasing"]
    with pytest.raises(PermissionError):
        deal_kinds.save(office, ks, by="omar")
    with pytest.raises(ValueError, match="not brokers"):
        deal_kinds.save(office, [ks[0] | {"brokers": ["priya"]}], by="layla")
    with pytest.raises(ValueError, match="not a customer type"):
        deal_kinds.save(office, [ks[0] | {"serves": [{"type": "investor"}]}], by="layla")
    deal_kinds.save(office, ks + [{"id": "pm", "name": "Property management", "brokers": ["nadia"], "listings": {},
                                   "serves": [{"type": "landlord"}]}], by="layla")
    assert deal_kinds.kinds(office.graph())[-1]["name"] == "Property management"


def test_an_off_plan_buyer_goes_to_the_off_plan_desk_and_sees_off_plan_units_only(office):
    r = talk(office, "971500006001", "I want to buy off-plan", "Dubai Creek Harbour", "An apartment", "2 bed",
             "Budget is 2 million", "Cash", "1-3 months")
    g = office.graph()
    d = g.nodes[f"deal:{g.nodes['chat:971500006001'].deal}"].props
    assert d["kind_name"] == "Off-plan" and d["broker"] == "hamza"  # moved to the off-plan desk's broker, logged
    assert d["assigned_why"].startswith("Off-plan:")
    assert r["refs"] == ["listing:DR-134"]  # off-plan, Creek Harbour, 2 bed, in budget


def test_a_ready_buyer_sees_ready_units_only(office):
    r = talk(office, "971500006002", "I want to buy", "Dubai Creek Harbour", "An apartment", "2 bed", "Budget is 2.5 million", "Cash", "Now")
    g = office.graph()
    d = g.nodes[f"deal:{g.nodes['chat:971500006002'].deal}"].props
    assert d["kind_name"] == "Ready sales" and d["broker"] in ("omar", "nadia")
    assert "listing:DR-134" not in r["refs"] and all(g.nodes[x].props.get("completion") == "ready" for x in r["refs"])


def test_without_deal_kinds_nothing_changes():
    o = Office(EventLog())
    demo.seed(o)
    r = talk(o, "971500006003", "I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now")
    assert r["refs"] == ["listing:MC-1204"] and not o.graph().nodes[f"deal:{o.graph().nodes['chat:971500006003'].deal}"].props.get("kind")
