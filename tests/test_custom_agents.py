from diwan import demo
from diwan.agents import custom, reception
from diwan.events import EventLog
from diwan.office import Office

import pytest


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


SPEC = {"name": "Welcome caller", "job": "When a lead qualifies, remind the broker to call within the hour and mention the budget.",
        "trigger": "qualify.passed", "team": "sales", "to": "rashid"}


def qualify(o, phone="971500000077"):
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now", "To live in", "UAE resident"):
        reception.message(o, phone, t, name_="Test Lead")


def test_only_the_owner_adds_and_the_spec_is_checked(office):
    with pytest.raises(PermissionError):
        custom.add(office, SPEC, by="omar")
    with pytest.raises(ValueError, match="Pick what it listens for"):
        custom.add(office, SPEC | {"trigger": "nothing"}, by="layla")
    a = custom.add(office, SPEC, by="layla")
    assert a["id"] == "x-welcome-caller" and a["status"] == "active"
    with pytest.raises(ValueError, match="exists"):
        custom.add(office, SPEC, by="layla")


def test_it_hands_each_trigger_to_its_person_once_and_never_acts_alone(office):
    custom.add(office, SPEC, by="layla")
    qualify(office)
    assert custom.run_pending(office) == 1 and custom.run_pending(office) == 0  # each trigger once
    t = [n for n in office.graph().of("task") if n.props.get("custom")][0]
    assert t.props["needs_person"] == "rashid" and t.props["agent"] == "x-welcome-caller" and t.label.startswith("Welcome caller:")
    assert "Test Lead" in t.label or "Qualified" in t.label or "lead qualifies" in t.label


def test_pause_resume_remove_and_built_ins_are_protected(office):
    custom.add(office, SPEC, by="layla")
    custom.change(office, "x-welcome-caller", "pause", by="layla")
    qualify(office)
    assert custom.run_pending(office) == 0  # paused: nothing
    custom.change(office, "x-welcome-caller", "resume", by="layla")
    assert custom.run_pending(office) == 0  # resumed from now, not from what it missed
    qualify(office, "971500000078")
    assert custom.run_pending(office) == 1
    custom.change(office, "x-welcome-caller", "remove", by="layla")
    assert office.graph().custom_agents["x-welcome-caller"]["status"] == "removed"  # history kept
    with pytest.raises(ValueError, match="Team page"):
        custom.change(office, "comp", "remove", by="layla")
    with pytest.raises(PermissionError):
        custom.change(office, "x-welcome-caller", "resume", by="omar")


def test_the_agents_map_shows_reporting_lines_and_real_handoffs(office):
    demo.correction(office)
    custom.add(office, SPEC, by="layla")
    m = custom.connections(office)
    ids = {n["id"] for n in m["nodes"]}
    assert {"agent:scribe", "agent:comp", "agent:x-welcome-caller"} <= ids
    rel = {(e["src"], e["rel"], e["dst"]) for e in m["edges"]}
    assert ("agent:scribe", "reports_to", "agent:sales") in rel and ("agent:x-welcome-caller", "reports_to", "agent:sales") in rel
    hand = {(e["src"], e["dst"]): e for e in m["edges"] if e["rel"] == "hands_to"}
    assert "check.raised" in hand[("agent:scribe", "agent:comp")]["types"]  # the correction reached Compliance through the log
