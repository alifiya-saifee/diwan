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


def test_the_office_map_links_agents_seen_checked_and_reporting(office):
    demo.correction(office)
    links = custom.office_flow(office)["links"]
    seen = {(l["src"], l["dst"]): l for l in links if l["kind"] == "seen"}
    assert seen[("scribe", "comp")]["count"] >= 1 and seen[("scribe", "comp")]["types"]
    assert {"src": "deck", "dst": "factcheck", "kind": "checks", "what": "Fact checker checks its work"} in links
    assert any(l["src"] == "sof" and l["dst"] == "devil" and l["kind"] == "checks" for l in links)
    assert any(l["src"] == "devil" and l["dst"] == "person:priya" for l in links)  # a role held by one person is that person
    assert any(l["src"] == "scribe" and l["dst"] == "sales" and l["kind"] == "reports" for l in links)


def test_an_added_agent_keeps_its_role_and_deliverables(office):
    a = custom.add(office, SPEC | {"role": "Call reminder", "produces": "A call task for the broker with the lead's budget"}, by="layla")
    node = custom.office_flow(office)["agents"][a["id"]]
    assert node["props"]["role"] == "Call reminder" and node["props"]["out"] == "A call task for the broker with the lead's budget"
    plain = custom.add(office, SPEC | {"name": "Second caller"}, by="layla")
    assert custom.office_flow(office)["agents"][plain["id"]]["props"]["out"].startswith("A task for")


def test_the_map_has_the_offices_rooms_front_desk_apart_from_sales(office):
    f = custom.office_flow(office)
    where = {d["id"]: [a["label"] for a in d["agents"]] for d in f["departments"]}
    assert where["front"] == ["Rania"] and "Rania" not in where["sales"] and "Scribe" in where["sales"]
    heads = {d["id"]: (d["head"] or {}).get("label") for d in f["departments"]}
    assert heads["lobby"] == "Lobby host" and "Front desk rep" in where["lobby"] and heads["deal"] == "Deal manager"
    assert any(x["from"] == "customers" and x["to"] == "front" for x in f["flows"])


def test_an_agent_between_two_teams_hands_its_work_to_a_person_on_the_second(office):
    with pytest.raises(ValueError, match="person on the second team"):
        custom.add(office, SPEC | {"team": "sales>comp", "to": "omar"}, by="layla")
    with pytest.raises(ValueError, match="two different teams"):
        custom.add(office, SPEC | {"team": "sales>sales", "to": "priya"}, by="layla")
    a = custom.add(office, SPEC | {"name": "Pre-check", "team": "sales>comp", "to": "priya"}, by="layla")
    f = custom.office_flow(office)
    assert {"agent": a["id"], "from": "sales", "to": "comp"} in f["bridges"]
    assert not any(x["label"] == "Pre-check" for d in f["departments"] for x in d["agents"])  # on the arrow, not inside a team
    assert any(b["value"] == "sales>comp" for b in f["between"])


def test_scenarios_replay_real_runs_from_the_log(office):
    before = {s["id"]: s for s in custom.scenarios(office)}
    assert not before["correction"]["found"] and before["correction"]["how"]
    demo.correction(office)
    sc = {s["id"]: s for s in custom.scenarios(office)}["correction"]
    types = [s["event"]["type"] for s in sc["steps"]]
    assert sc["found"] and "fact.superseded" in types and "check.raised" in types
    assert any(s["to"] == "person:priya" for s in sc["steps"] if s["event"]["type"] == "check.raised")


def test_an_intern_reports_to_an_agent_in_its_team(office):
    a = custom.add(office, SPEC | {"name": "Scribe intern", "reports_to": "scribe"}, by="layla")
    f = custom.office_flow(office)
    assert f["agents"][a["id"]]["props"]["parent"] == "scribe" and f["agents"][a["id"]]["props"]["dept"] == "sales"
    assert {"src": a["id"], "dst": "scribe", "kind": "reports", "what": "reports to Scribe"} in f["links"]
    assert next(d for d in f["departments"] if d["id"] == "sales")["head"]["label"] == "Sales lead"
    with pytest.raises(ValueError, match="same team"):
        custom.add(office, SPEC | {"name": "Wrong boss", "reports_to": "screen"}, by="layla")  # the Screening analyst is in Compliance


def test_an_agent_without_ai_hands_over_the_record_and_calls_no_model(office, monkeypatch):
    from diwan.agents import runner
    called = []
    a = custom.add(office, SPEC | {"name": "Plain caller", "ai": False}, by="layla")
    assert custom.office_flow(office)["agents"][a["id"]]["props"]["runs_on"] == "rules"
    qualify(office)
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: called.append(1) or True)  # from here on, only the agent could call it
    assert custom.run_pending(office) >= 1 and not called
    t = [e for e in office.log.list() if e["type"] == "task.created" and e["agent"] == a["id"]][0]
    assert t["content"]["action"].startswith("Plain caller: a lead qualifies.") and t["content"]["needs_person"] == "rashid"


def test_work_counts_for_the_agent_who_did_it(office):
    from datetime import datetime
    from diwan import lobby_room, slots
    lobby_room.run_week(office, datetime(2026, 11, 2, 9, tzinfo=slots.DUBAI))
    nodes = {n["id"].split(":", 1)[1]: n for n in custom.connections(office)["nodes"]}
    assert nodes["lfront"]["props"]["actions"] >= 1 and nodes["lcomp"]["props"]["actions"] >= 1  # each rep's line in the week's thread
