from datetime import datetime, timezone

import pytest

from diwan import demo
from diwan.agents import nova
from diwan.events import EventLog
from diwan.graph import build
from diwan.office import Office
from diwan.providers.chat import PROVIDERS
from tests.conftest import fake


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


@pytest.fixture
def corrected(office):
    demo.correction(office)
    return office


def types(o: Office, after: int) -> list[str]:
    return [e["type"] for e in o.log.list(after=after)]


# ---------- the graph and the engine ----------

def test_graph_links_who_said_what_and_who_pays(office):
    g = office.graph()
    assert [n.id for n in g.out("person:karim-haddad", "said")] == ["F1", "F2", "F3", "F4", "F5"]
    assert g.out("person:karim-haddad", "brother")[0].label == "Tariq Haddad"
    assert {n.id for n in g.impact("F3")} == {"T3", "A1", "D1/3", "D1"} and [n.id for n in g.impact("F2")] == ["T2"]
    assert g.impact("F1") == [g.nodes["D1/1"], g.nodes["D1"]]


def test_correction_tells_compliance_first_and_touches_only_what_rested_on_it(office):
    n = office.log.list()[-1]["id"]
    demo.correction(office)
    assert types(office, n) == ["fact.created", "check.raised", "fact.superseded", "task.withdrawn", "fact.superseded",
                                "task.withdrawn", "decision.needed", "review.returned", "task.created"]
    g = office.graph()
    assert g.nodes["T2"].status == g.nodes["T3"].status == "withdrawn" and g.nodes["T1"].status == "queued"
    assert g.nodes["T5"].props["action"] == "Expect AED 260,000 by bank transfer from Karim Haddad"
    assert g.nodes["D1"].status == "sent_back" and not g.stale("D1/1")
    assert g.history("F7") == [g.nodes["F7"], g.nodes["F2"], g.nodes["F3"]]


def test_graph_rewinds_to_any_event(corrected):
    before = next(e["id"] for e in corrected.log.list() if e["type"] == "fact.superseded") - 1
    assert build(corrected.log.list(), upto=before).nodes["F3"].status == "live"
    assert corrected.graph().nodes["F3"].status == "superseded"


def test_stale_approval_is_refused_and_a_live_one_runs_once(corrected):
    out = corrected.execute("A1", "k1")
    assert not out["ok"] and "F3" in out["because"]
    a2 = corrected.approve("marina-1204", "ahmed", "Accept the AED 260,000 deposit from Karim Haddad", ["F7", "F4"])
    assert corrected.execute(a2, "k2")["ok"]
    assert corrected.execute(a2, "k2")["duplicate"]
    assert types(corrected, 0).count("execution.done") == 1


def test_contradiction_goes_to_the_broker_and_money_work_waits(office):
    office.record_fact("marina-1204", "payer", "My cousin covers it.", "Karim Haddad", payer="Sami")
    g = office.graph()
    card = g.of("decision", "marina-1204", "open")[-1]
    assert card.props["who"] == "omar" and set(card.props["refs"]) == {"F3", "F7"}
    assert not any("Sami" in t.props["action"] for t in g.of("task"))


# ---------- ask ----------

def test_answer_cites_the_exact_words_and_the_history(corrected):
    r = nova.ask(corrected, "Who is paying the deposit for Karim?")
    assert r["kind"] == "answer" and r["by"] == "rules"
    assert '"Actually, forget my brother. I\'ll pay it all myself." (F7)' in r["text"] and "(F3), since replaced" in r["text"]
    assert {"F7", "F3", "T5"} <= set(r["cites"])
    pack = [e for e in corrected.log.list() if e["type"] == "agent.pack"][-1]["content"]["pack"]
    assert [e["source"] for e in pack["evidence"]] == ["F7", "F2", "F3", "F4"] and not pack["rejected_quotes"]


def test_what_changed_follows_the_graph_to_everything_it_touched(corrected):
    r = nova.ask(corrected, "What changed on the Marina deal?")
    assert {"F3", "F7", "T2", "T3", "A1", "D1/3"} <= set(r["cites"])


def test_business_words_find_facts_that_never_use_them(corrected):
    assert "(F1)" in nova.ask(corrected, "What did Karim say about the Marina price?")["text"]
    assert "(F5)" in nova.ask(corrected, "How much does Karim earn?")["text"]


def test_no_record_means_no_answer_and_who_would_know(corrected):
    r = nova.ask(corrected, "What is the seller's name on the Marina unit?")
    assert r["kind"] == "unknown" and r["cites"] == [] and "Omar was in the meeting" in r["text"]


def test_unclear_deal_becomes_one_question_back(corrected):
    r = nova.ask(corrected, "Who pays the deposit?")
    assert r["kind"] == "question" and len(r["options"]) == 2
    assert corrected.graph().nodes[r["card"]].props["who"] == "layla"


def test_model_answer_with_an_invented_quote_is_not_shown(corrected, monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(
        {"verdict": "Tariq still pays.", "evidence": [{"quote": "Tariq confirmed by email.", "source": "F3"}],
         "missing": [], "next": [], "actions": []}))
    r = nova.ask(corrected, "Who is paying for Karim?", tape_root=tmp_path)
    assert r["kind"] == "unsupported" and "won't guess" in r["text"]


def test_model_answer_is_checked_and_cited(corrected, monkeypatch, tmp_path):
    seen = []
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(
        {"verdict": "Karim pays it all himself [F7].", "evidence": [{"quote": "I'll pay it all myself.", "source": "F7"}],
         "missing": [], "next": [], "actions": []}, seen))
    r = nova.ask(corrected, "Who is paying for Karim?", tape_root=tmp_path)
    assert r == {"kind": "answer", "text": "Karim pays it all himself [F7].", "cites": ["F7"], "by": "meta", "request": r["request"]}
    assert '<source id="F7">' in seen[0]["messages"][1]["content"]


# ---------- route ----------

def test_instruction_reaches_the_specialist_and_comes_back(corrected):
    n = corrected.log.list()[-1]["id"]
    r = nova.route(corrected, "Prepare Form F for Karim's Marina unit")
    assert r["kind"] == "done" and r["agent"] == "formf" and "5 of 7 fields" in r["text"]
    evs = corrected.log.list(after=n)
    assert [(e["type"], e["agent"]) for e in evs] == [
        ("instruction.given", "nova"), ("agent.pack", "nova"), ("agent.pack", "ops"), ("task.created", "formf"),
        ("agent.pack", "formf"), ("approval.requested", "formf"), ("draft.made", "formf"), ("review.passed", "factcheck"),
        ("task.created", "formf"), ("task.done", "formf")]
    plan = evs[4]["content"]["pack"]
    assert "Deposit paid by: Karim Haddad (F7)" in plan["next"] and any("Seller" in m for m in plan["missing"])
    assert evs[5]["content"] == {"kind": "submit", "summary": "Submit Form F", "reviewer": "Transactions officer"}


@pytest.mark.parametrize("text, who", [("Submit Form F for marina", "Joseph"), ("Release the deposit to the developer", "Ahmed"),
                                       ("File an STR on Karim", "Priya"), ("Tell Karim his file was flagged by compliance", "tip them off")])
def test_what_only_people_do_is_refused_and_logged(corrected, text, who):
    r = nova.route(corrected, text)
    assert r["kind"] == "refused" and who in r["text"]
    assert corrected.log.list()[-1]["type"] == "agent.refused"


def test_unclear_instructions_become_questions(corrected):
    assert nova.route(corrected, "Prepare form f")["options"] == ["Unit 1204, Marina Crest (Karim)", "Villa 88, JVC (Sara)"]
    assert nova.route(corrected, "Do the thing for Karim")["options"] == ["Sales", "Operations", "Finance", "Compliance"]
    assert nova.route(corrected, "Screen the parties and rebuild the deck for Karim")["kind"] == "question"


def test_unbuilt_specialist_keeps_the_task_and_says_so(corrected):
    r = nova.route(corrected, "Process the invoice for Karim's Marina unit")
    assert r["kind"] == "queued" and "not built yet" in r["text"]
    assert corrected.graph().nodes[r["task"]].status == "queued"


# ---------- brief ----------

def test_each_person_hears_what_needs_them_with_records(corrected):
    morning = datetime(2026, 10, 28, 9, 0, tzinfo=nova.DUBAI)
    priya, ahmed, omar = (nova.brief(corrected, p, now=morning) for p in ("priya", "ahmed", "omar"))
    assert priya["text"].startswith("Good morning, Priya. 3 things need you. Payment arrangement changed")
    assert {"A1", "F3", "F7"} <= set(ahmed["lines"][0]["refs"])
    assert omar["text"].startswith("Good morning, Omar. 1 thing needs you. How is Sara Malik funding the purchase?") and "took back" in omar["text"]


def test_briefing_runs_at_seven_dubai_once_a_day():
    assert not nova.briefing_due(datetime(2026, 10, 28, 2, 59, tzinfo=timezone.utc), None)
    assert nova.briefing_due(datetime(2026, 10, 28, 3, 0, tzinfo=timezone.utc), "2026-10-27")
    assert not nova.briefing_due(datetime(2026, 10, 28, 5, 0, tzinfo=timezone.utc), "2026-10-28")


@pytest.mark.parametrize("q, expect", [
    ("Hi Nova, how are you?", "All good here"),
    ("What should I focus on today?", "Waiting on others: Omar: How is Sara Malik funding the purchase?"),
    ("Is Karim a good customer?", "I don't judge people"),
    ("Which listing is the most expensive?", "Unit 1204, Marina Crest"),
    ("How many listings do we have?", "4 listings, 3 advertised"),
    ("Who is Tariq?", "Karim Haddad's brother"),
    ("Who is Priya?", "compliance officer"),
    ("Summarise the Marina deal for me", "Unit 1204, Marina Crest, customer Karim Haddad"),
    ("How many viewings do we have this week?", "No viewings are booked yet"),
    ("What's on the lobby board?", "The requests board is empty"),
])
def test_everyday_questions(corrected, q, expect):
    assert expect in nova.converse(corrected, q, "layla", session="e")["text"]


def test_deleting_the_records_is_refused():
    import re

    from diwan.agents import nova
    rule = next(rx for rx, k, _ in nova.REFUSE if k == "delete_records")
    assert re.search(rule, "delete all the leads") and not re.search(rule, "delete my 3pm")
