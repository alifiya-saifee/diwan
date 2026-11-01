"""Room 9, the Lobby (docs/closed-loop-spec.md L279-295, L569-582): threads from the office's own log, experiments the owner
approves, a change only for its audience and period, Records' number, keep or roll back, and the guardrails."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod, demo, desk_rules, lobby_room as lr, qualify
from diwan.agents import frontdesk, lessons, nova, nudge, reception
from diwan.agents.charters import BY_ID, ROSTER
from diwan.events import EventLog
from diwan.office import Office

OWNER, NOW = "layla", datetime.now(timezone.utc)
FOLLOW = {"kind": "followup", "title": "Ask if they're still looking", "text": "Hi {name}, are you still looking, or shall I pause for now?", "metric": "reply_rate", "days": 14, "control_pct": 0}


@pytest.fixture
def office(monkeypatch):
    o = Office(EventLog())
    demo.seed(o)
    monkeypatch.setattr(appmod.S, "office", o)
    return o


@pytest.fixture
def c(office):
    return TestClient(appmod.app)


def lead(office, name, phone, *, broker="omar", arabic=False, at=None):
    office.open_deal(f"lead-{phone}", property="Enquiry", customer=name, broker=broker)
    t = "مرحبا، أبحث عن شقة" if arabic else "Hello, I want a flat"
    office.log.append("chat.received", actor=f"customer:{phone}", deal=f"lead-{phone}", content={"chat": phone, "name": name, "text": t, "channel": "whatsapp"})
    return f"lead-{phone}"


def settings_events(office):
    return [e for e in office.log.list() if e["type"] == "setting.changed" and e["content"]["person"] != "lobby"]


# the room

def test_a_host_and_a_rep_from_every_room_and_none_may_apply_anything():
    reps = [c for c in ROSTER if c.parent == "lhost"]
    assert len(reps) == len(lr.ROOMS) and {r for _, r in lr.ROOMS.values()} == {c.id for c in reps}
    assert all(c.alone == ("draft",) and not c.person for c in reps + [BY_ID["lhost"]])


def test_nothing_changes_until_the_owner_approves(office):
    d = lead(office, "Tariq Noor", "9710001")
    xid = lr.propose(office, FOLLOW, by="lsales")
    g = office.graph()
    assert g.nodes[xid].status == "proposed" and not lr.change(g, d, "followup", NOW, n=1)
    with pytest.raises(PermissionError):
        lr.approve(office, xid, by="lsales")
    with pytest.raises(PermissionError):
        lr.approve(office, xid, by="rashid")


def test_only_the_sales_lead_and_the_owner_propose(office):
    assert lr.propose(office, FOLLOW, by="rashid")
    with pytest.raises(PermissionError):
        lr.propose(office, FOLLOW, by="omar")


# the spec's test: only for its audience and period

def test_an_approved_experiment_changes_a_follow_up_only_for_its_audience_and_period(office):
    inside, other = lead(office, "Tariq Noor", "9710001", broker="omar"), lead(office, "Dana Saleh", "9710002", broker="hamza")
    xid = lr.propose(office, FOLLOW | {"audience": {"broker": "omar"}}, by="lsales")
    lr.approve(office, xid, by=OWNER, now=NOW)
    g = office.graph()
    args = dict(arabic=False, first="Tariq", broker="Omar")
    assert "still looking" in lr.followup(g, inside, 1, NOW + timedelta(days=1), **args)["text"]
    assert lr.followup(g, other, 1, NOW + timedelta(days=1), **args) is None           # not its audience
    assert lr.followup(g, inside, 2, NOW + timedelta(days=1), **args) is None           # not that follow-up
    assert lr.followup(g, inside, 1, NOW + timedelta(days=15), **args) is None          # past its period, even before the report
    assert lr.followup(g, inside, 1, NOW - timedelta(days=1), **args) is None           # before it started


def test_the_real_sweep_sends_the_experiment_for_the_audience_and_the_usual_words_for_others(office):
    nudge.set_settings(office, {"quiet_from": "00:00", "quiet_to": "00:00", "friday_prayer": False}, by=OWNER)
    reception.message(office, "971501230001", "I want to buy", name_="Tariq Noor")
    reception.message(office, "971501230002", "I want to rent", name_="Dana Saleh")
    g = office.graph()
    inside, other = g.nodes["chat:971501230001"].deal, g.nodes["chat:971501230002"].deal
    xid = lr.propose(office, FOLLOW | {"audience": {"qtype": g.nodes[f"deal:{inside}"].props.get("qtype")}}, by="lsales")
    assert g.nodes[f"deal:{inside}"].props.get("qtype") != g.nodes[f"deal:{other}"].props.get("qtype")
    lr.approve(office, xid, by=OWNER)
    nudge.sweep(office, datetime.now(nudge.DUBAI) + timedelta(hours=20.5))
    sent = {e["deal"]: e["content"] for e in office.log.list() if e["type"] == "followup.nudged"}
    assert sent[inside]["text"] == "Hi Tariq, are you still looking, or shall I pause for now?" and sent[inside]["experiment"] == xid
    assert "still looking" not in sent[other]["text"] and sent[other]["experiment"] is None


def test_half_the_audience_is_the_comparison_and_stays_on_its_side(office):
    deals = [f"lead-{i}" for i in range(200)]
    arms = [lr.arm("EX1", d, 50) for d in deals]
    assert 70 < arms.count("test") < 130 and arms == [lr.arm("EX1", d, 50) for d in deals]


def test_english_words_never_reach_a_client_who_writes_arabic_unless_the_audience_says_so(office):
    d = lead(office, "Hala Omar", "9710003", arabic=True)
    lr.approve(office, lr.propose(office, FOLLOW, by="lsales"), by=OWNER, now=NOW)
    g = office.graph()
    assert lr.followup(g, d, 1, NOW, arabic=True, first="Hala", broker="Omar") is None


def test_a_qualifying_question_reaches_new_leads_in_the_audience_and_leaves_the_owners_form_alone(office):
    before = lead(office, "Early Lead", "9710004")
    xid = lr.propose(office, {"kind": "question", "title": "Ask about pre-approval", "text": "Has a bank already pre-approved you?", "metric": "viewing_rate", "days": 14, "control_pct": 0}, by="lsales")
    lr.approve(office, xid, by=OWNER)
    after = lead(office, "Later Lead", "9710005")
    g = office.graph()
    has = lambda d: any(x.get("experiment") == xid for x in qualify.form(g, d)["common"])  # noqa: E731
    assert has(after) and not has(before) and not any(x.get("experiment") for x in qualify.form(g)["common"])
    lr.finish(office, xid, "rolled back", by=OWNER)
    assert not any(x.get("experiment") for x in qualify.form(office.graph(), after)["common"])


def test_a_checklist_step_lands_on_a_converted_deal_and_touches_no_gate(office):
    xid = lr.propose(office, {"kind": "step", "title": "Photo guide", "text": "Send the client the one-line photo guide.", "metric": "sent_back_rate", "days": 14, "control_pct": 0}, by="ldeal")
    lr.approve(office, xid, by=OWNER)
    d = lead(office, "Sami Fares", "9710006")
    lr.on_convert(office, d)
    lr.on_convert(office, d)
    assert sum(t.props.get("experiment") == xid for t in office.graph().of("task", d)) == 1


def test_an_instruction_is_a_dated_lesson_that_goes_away(office):
    xid = lr.propose(office, {"kind": "instruction", "agent": "deck", "title": "Check the price", "text": "Always check the current price before the deck.", "metric": "send_backs", "days": 14, "control_pct": 0}, by="lreview")
    assert not [ls for ls in lessons.active_from_log(office.log, "deck") if "current price" in ls["rule"]]   # suggested, not applied
    lr.approve(office, xid, by=OWNER)
    assert [ls for ls in lessons.active_from_log(office.log, "deck") if "current price" in ls["rule"]]
    lr.report(office, xid)
    assert not [ls for ls in lessons.active_from_log(office.log, "deck") if "current price" in ls["rule"]]   # the period ended: it stopped
    lr.finish(office, xid, "kept", by=OWNER)
    assert [ls for ls in lessons.active_from_log(office.log, "deck") if "current price" in ls["rule"]]
    lr.finish(office, xid, "rolled back", by=OWNER)
    assert not [ls for ls in lessons.active_from_log(office.log, "deck") if "current price" in ls["rule"]]


def test_a_content_idea_reaches_the_studio_and_a_person_still_writes_it(office):
    from diwan.agents import marketing
    xid = lr.propose(office, {"kind": "content", "title": "A walk-through reel", "text": "Our own walk-through of one unit we know well, in our own words.", "metric": "leads_per_post", "days": 14}, by="lmkt")
    lr.approve(office, xid, by=OWNER)
    ref = office.graph().nodes[xid].props["topic"]
    assert marketing.pieces(office)[ref]["stage"] == "idea"


# Records, then keep or roll back

def test_finances_step_watches_flagged_payments_not_another_rooms_number(office):
    for i in range(2):
        office.log.append("payment.flagged", actor="ahmed", deal="marina-1204", content={"why": "A stranger paid"})
    lr.run_week(office)
    x = next(x for x in office.graph().of("experiment") if x.props.get("room") == "fin")
    assert x.props["metric"] == "flagged_rate"
    lr.approve(office, x.id, by=OWNER, now=NOW - timedelta(minutes=1))
    d = lead(office, "Sami Fares", "9710006")
    office.log.append("case.converted", actor="omar", deal=d, content={})
    office.log.append("payment.flagged", actor="ahmed", deal=d, content={"why": "A stranger paid"})
    g = office.graph()
    r = lr.measure(office, g, g.nodes[x.id], datetime.now(timezone.utc) + timedelta(minutes=1))
    assert r["test"]["n"] + r["control"]["n"] == 1


def test_records_counts_from_the_log_and_says_too_few_when_it_is(office):
    xid = lr.propose(office, FOLLOW | {"control_pct": 50}, by="lsales")
    lr.approve(office, xid, by=OWNER, now=NOW - timedelta(minutes=1))
    deals = [lead(office, f"Lead Number{i}x", f"97120{i:03}") for i in range(12)]
    for i, d in enumerate(deals):
        office.log.append("followup.nudged", actor="rania", agent="rania", deal=d, content={"chat": d[5:], "n": 1, "sent": True, "text": "x"})
    replied = [d for d in deals if lr.arm(xid, d, 50) == "test"][:2]
    for d in replied:
        office.log.append("chat.received", actor="customer", deal=d, content={"chat": d[5:], "text": "yes", "channel": "whatsapp"})
    g = office.graph()
    r = lr.measure(office, g, g.nodes[xid], datetime.now(timezone.utc) + timedelta(minutes=1))
    assert r["test"]["n"] == 2 and r["test"]["of"] == sum(lr.arm(xid, d, 50) == "test" for d in deals)
    assert r["verdict"] == "too few to say" and set(replied) <= set(r["test"]["refs"])


def test_the_verdict_is_a_real_test_not_any_gap():
    a, b = {"n": 15, "of": 30, "rate": .5}, {"n": 5, "of": 30, "rate": 5 / 30}
    assert lr._verdict("reply_rate", a, b, True, 20)["verdict"] == "better"
    assert lr._verdict("reply_rate", {"n": 12, "of": 30, "rate": .4}, {"n": 10, "of": 30, "rate": 1 / 3}, True, 20)["verdict"] == "no clear difference"
    assert lr._verdict("sent_back_rate", a, b, False, 20)["verdict"] == "worse"


def test_the_period_ends_by_itself_the_analyst_reports_and_the_owner_decides(office):
    d = lead(office, "Tariq Noor", "9710001")
    xid = lr.propose(office, FOLLOW, by="lsales")
    lr.approve(office, xid, by=OWNER)
    later = datetime.now(timezone.utc) + timedelta(days=15)
    assert f"reported {xid}" in lr.sweep(office, later)
    g = office.graph()
    assert g.nodes[xid].status == "reporting" and not lr.change(g, d, "followup", later, n=1)
    assert any(e["type"] == "experiment.reported" and e["actor"] == "analyst" for e in office.log.list())
    assert any(x["line"] for x in frontdesk.day(office, OWNER)["lobby_waiting"])
    lr.sweep(office, later)
    assert sum(e["type"] == "experiment.reported" for e in office.log.list()) == 1
    lr.finish(office, xid, "kept", by=OWNER)
    g = office.graph()
    assert lr.change(g, d, "followup", later + timedelta(days=99), n=1)                 # kept: for good
    lr.finish(office, xid, "rolled back", by=OWNER)
    assert not lr.change(office.graph(), d, "followup", later, n=1)


def test_rolling_back_leaves_the_office_as_it_was(office):
    before = len(settings_events(office)), str(qualify.form(office.graph())), str(desk_rules.rules(office.graph()))
    xid = lr.propose(office, FOLLOW, by="lsales")
    lr.approve(office, xid, by=OWNER)
    lr.finish(office, xid, "rolled back", by=OWNER)
    assert before == (len(settings_events(office)), str(qualify.form(office.graph())), str(desk_rules.rules(office.graph())))


def test_two_experiments_cant_change_the_same_thing_for_the_same_people(office):
    lr.approve(office, lr.propose(office, FOLLOW | {"audience": {"broker": "omar"}}, by="lsales"), by=OWNER)
    with pytest.raises(ValueError, match="already changes"):
        lr.approve(office, lr.propose(office, FOLLOW | {"title": "Other words"}, by="lsales"), by=OWNER)
    assert lr.approve(office, lr.propose(office, FOLLOW | {"title": "Hamza's", "audience": {"broker": "hamza"}}, by="lsales"), by=OWNER)


# guardrails

@pytest.mark.parametrize("text", ["Drop screening for small deals", "Raise the source of funds threshold", "Skip KYC for repeat clients", "Change the quiet hours setting", "Bypass the gate"])
def test_compliance_rules_and_settings_cant_be_changed_from_the_lobby(office, text):
    with pytest.raises(lr.Guardrail):
        lr.propose(office, FOLLOW | {"text": text}, by="lcomp")


def test_a_rule_cant_be_slipped_in_when_the_owner_edits_or_in_another_kind(office):
    xid = lr.propose(office, FOLLOW, by="lsales")
    with pytest.raises(lr.Guardrail):
        lr.approve(office, xid, by=OWNER, edits={"text": "Tell them compliance can be skipped"})
    with pytest.raises(lr.Guardrail):
        lr.propose(office, {"kind": "setting", "title": "x", "text": "y"}, by="lsales")
    assert office.graph().nodes[xid].status == "proposed"


@pytest.mark.parametrize("agent", ["comp", "screen", "sof", "report", "review", "factcheck", "mpermit"])
def test_compliance_and_review_agents_instructions_cant_be_changed(office, agent):
    with pytest.raises(lr.Guardrail):
        lr.propose(office, {"kind": "instruction", "agent": agent, "title": "Faster", "text": "Always finish faster.", "metric": "send_backs", "days": 14}, by="lreview")


def test_a_promise_or_a_broken_lesson_cant_be_proposed(office):
    with pytest.raises(lr.Guardrail):
        lr.propose(office, FOLLOW | {"text": "Guaranteed returns, {name}!"}, by="lsales")
    lessons.add(office.log, {"agent": "rania", "kind": "never", "rule": "Never mention service charges", "phrase": "service charges"}, by=OWNER)
    with pytest.raises(lr.Guardrail):
        lr.propose(office, FOLLOW | {"text": "Hi {name}, about the service charges"}, by="lsales")


@pytest.mark.parametrize("words", ["Call +971 50 123 4567 back", "Write to tariq@example.com", "Do what worked for Tariq"])
def test_no_client_data_gets_in(office, words):
    lead(office, "Tariq Noor", "9710001")
    with pytest.raises(lr.Guardrail):
        lr.propose(office, FOLLOW | {"text": words}, by="lsales")
    with pytest.raises(lr.Guardrail):
        lr.add_playbook(office, {"room": "sales", "pattern": words, "where": "A talk", "evidence": "They said so"}, by=OWNER)


def test_a_playbook_needs_evidence_and_another_offices_needs_the_opt_in(office):
    with pytest.raises(ValueError):
        lr.add_playbook(office, {"room": "sales", "pattern": "Day 3 floor plan"}, by=OWNER)
    other = {"room": "sales", "pattern": "Day 3 floor plan", "where": "Another office", "evidence": "2x replies", "source": "other office"}
    with pytest.raises(lr.Guardrail):
        lr.add_playbook(office, other, by=OWNER)
    lr.set_settings(office, {"playbooks_opt_in": True}, by=OWNER)
    assert lr.add_playbook(office, other, by=OWNER)
    with pytest.raises(PermissionError):
        lr.set_settings(office, {"playbooks_opt_in": False}, by="rashid")


# the week's threads

def lost(office, n, reason="no_response"):
    for i in range(n):
        d = lead(office, f"Gone Person{i}x", f"97130{i:03}")
        office.log.append("lead.outcome", actor="omar", deal=d, content={"chat": d[5:], "outcome": "not_interested", "reason": reason})


def test_a_thread_per_room_each_with_at_most_one_proposal(office):
    lost(office, 3)
    made = lr.run_week(office)
    g = office.graph()
    assert len(made) == len(lr.ROOMS)
    assert all(sum(1 for x in g.of("experiment") if x.id == g.nodes[t].props.get("experiment")) <= 1 for t in made)
    sales = next(g.nodes[t] for t in made if g.nodes[t].props["room"] == "sales")
    assert "No response 3" in sales.props["lines"][0]["text"]
    x = g.nodes[sales.props["experiment"]]
    assert x.status == "proposed" and x.props["kind"] == "followup" and x.props["metric"] == "reply_rate" and x.props["days"] == 14


def test_the_week_runs_once_and_doesnt_propose_the_same_thing_twice(office):
    lost(office, 3)
    lr.run_week(office)
    assert lr.run_week(office) == []
    n = len(office.graph().of("experiment"))
    assert n and lr.run_week(office, datetime.now(timezone.utc) + timedelta(days=6))   # next week, the same losses still in view
    assert len(office.graph().of("experiment")) == n


def test_compliance_only_listens(office):
    lost(office, 3)
    lr.run_week(office)
    g = office.graph()
    t = next(t for t in g.of("thread") if t.props["room"] == "comp")
    assert t.props["experiment"] is None and "don't change from the Lobby" in t.props["lines"][0]["text"]


def test_a_thread_holds_counts_never_a_clients_name_or_words(office):
    lost(office, 3)
    d = lead(office, "Karima Zayed", "9719999")
    office.log.append("case.lost", actor="omar", deal=d, content={"reason": "Karima Zayed went cold"})
    got = office.log.append("chat.received", actor="customer", deal=d, content={"chat": "9719999", "text": "What are the service charges for my villa, Karima here", "channel": "whatsapp"})
    office.log.append("chat.handover", actor="rania", deal=d, caused_by=got["id"], content={"chat": "9719999", "mode": "human", "by": "omar", "reason": "Rania handed over: the sources did not cover it"})
    lr.run_week(office)
    said = " ".join(ln["text"] for t in office.graph().of("thread") for ln in t.props["lines"])
    assert "Karima" not in said and "service charges 1" in said


def test_a_playbook_is_discussed_and_proposed_only_when_it_fits(office):
    pb = lr.add_playbook(office, {"room": "sales", "pattern": "Follow up on day 3 with a floor plan", "where": "A public talk", "evidence": "Twice the replies", "kind": "followup", "text": "Hi {name}, here's the floor plan I mentioned. Does the layout work for you?"}, by=OWNER)
    lr.run_week(office)
    g = office.graph()
    t = next(t for t in g.of("thread") if t.props["room"] == "sales")
    assert t.props["experiment"] is None and any("no change" in ln["text"] for ln in t.props["lines"])
    lost(office, 3)
    lr.run_week(office, datetime.now(timezone.utc) + timedelta(days=6))
    g = office.graph()
    x = g.of("experiment", status="proposed")[0]
    assert "floor plan" in x.props["text"] and pb in x.props["why"]


def test_review_send_back_patterns_become_a_suggestion_for_that_agent(office):
    for i in range(3):
        office.log.append("qa.failed", actor="mkt", agent="mkt", content={"kind": "script", "ref": "R1", "fails": [{"owner": "mscript", "rule": "Uses the listing's real price."}]})
    lr.run_week(office)
    g = office.graph()
    x = next(x for x in g.of("experiment") if x.props["kind"] == "instruction")
    assert x.props["agent"] == "mscript" and x.props["text"].startswith("Always") and x.status == "proposed"


def test_the_sweep_writes_on_the_owners_day_only(office):
    monday = datetime(2026, 11, 9, 8, 0, tzinfo=nudge.DUBAI)
    assert lr.sweep(office, monday - timedelta(days=1)) == []
    assert len([x for x in lr.sweep(office, monday) if x.startswith("TH")]) == len(lr.ROOMS)


def test_the_month_is_counted_once_on_the_first(office):
    xid = lr.propose(office, FOLLOW, by="lsales")
    lr.approve(office, xid, by=OWNER, now=datetime(2026, 10, 1, tzinfo=timezone.utc))
    lr.finish(office, xid, "kept", by=OWNER, now=datetime(2026, 10, 20, tzinfo=timezone.utc))
    first = datetime(2026, 11, 1, 9, 0, tzinfo=nudge.DUBAI)
    assert len(lr.sweep(office, first)) == 1 and lr.sweep(office, first) == []
    t = next(t for t in office.graph().of("thread") if t.props["room"] == "lobby")
    assert "1 experiment kept" in t.props["lines"][0]["text"]


# one idea a day

def test_one_idea_a_day_in_the_owners_brief_only(office):
    assert lr.idea(office.graph()) is None
    lr.propose(office, FOLLOW, by="lsales")
    lr.propose(office, FOLLOW | {"title": "Another"}, by="lsales")
    g = office.graph()
    assert lr.idea(g, NOW) == lr.idea(g, NOW) and lr.idea(g, NOW)["text"] != lr.idea(g, NOW + timedelta(days=1))["text"]
    assert any(ln.get("idea") for ln in nova.brief(office, OWNER)["lines"])
    assert not any(ln.get("idea") for ln in nova.brief(office, "omar")["lines"])
    assert frontdesk.day(office, OWNER)["idea"] and not frontdesk.day(office, "omar")["idea"]


# over HTTP: everyone reads, the owner decides

def test_the_whole_cycle_on_the_api(c, office):
    x = c.post("/api/lobby-room/propose", json={"by": "rashid", "draft": FOLLOW}).json()["id"]
    r = c.get("/api/lobby-room?by=layla").json()
    assert [p["id"] for p in r["proposed"]] == [x] and r["owner"] and r["may_propose"]
    assert c.post(f"/api/lobby-room/{x}/approve", json={"by": "omar"}).status_code == 403
    assert c.post(f"/api/lobby-room/{x}/approve", json={"by": "layla", "edits": {"text": "Hi {name}, shall I pause for now?", "days": 7}}).status_code == 200
    r = c.get("/api/lobby-room?by=omar").json()
    assert r["running"][0]["text"].startswith("Hi {name}, shall I") and r["running"][0]["days"] == 7 and r["running"][0]["result"]["verdict"] == "too few to say" and not r["owner"]
    assert c.post(f"/api/lobby-room/{x}/keep", json={"by": "layla"}).status_code == 200
    assert c.get("/api/lobby-room?by=layla").json()["kept"][0]["id"] == x
    assert c.post("/api/lobby-room/propose", json={"by": "layla", "draft": FOLLOW | {"text": "Change the compliance rule"}}).status_code == 400


def test_the_gate_lets_everyone_read_and_only_the_sales_lead_propose():
    from diwan import access
    assert access.may_open("priya", "lobby.html") and access.may_open("maya", "lobby.html")
    assert all(access.may_call(p, "GET", "/api/lobby-room") for p in ("omar", "rashid", "joseph", "ahmed", "priya", "maya"))
    assert access.may_call("omar", "POST", "/api/lobby-room/propose")  # the sales desk reaches it; the rule itself says who: test_only_the_sales_lead_and_the_owner_propose
    assert not access.may_call("ahmed", "POST", "/api/lobby-room/propose")
    for path in ("/api/lobby-room/EX1/approve", "/api/lobby-room/EX1/keep", "/api/lobby-room/EX1/rollback", "/api/lobby-room/rules", "/api/lobby-room/threads/run"):
        assert not any(access.may_call(p, "POST", path) for p in ("omar", "rashid", "priya", "ahmed"))
