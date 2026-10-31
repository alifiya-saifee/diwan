from datetime import datetime

import pytest

from diwan import demo, slots
from diwan.agents import lessons, nova, reception, runner
from diwan.agents.charters import get
from diwan.events import EventLog
from diwan.office import Office
from diwan.pack import Action, Pack
from diwan.providers.chat import PROVIDERS
from tests.conftest import fake

NOW = datetime(2026, 10, 27, 23, 40, tzinfo=slots.DUBAI)
PH = "971500000009"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def talk(o, t):
    return nova.converse(o, t, "layla", session="s")


@pytest.mark.parametrize("text, agent, phrase", [("Rania, never mention the transfer fee", "rania", "transfer fee"),
                                                 ("Nova: don't quote service charges.", "nova", "service charges"),
                                                 ("Everyone, never promise returns", "all", "returns"),
                                                 ("Deck builder, always put the price on slide one", "deck", None)])
def test_lessons_are_understood(text, agent, phrase):
    ls = lessons.parse(text)
    assert ls["agent"] == agent and ls["phrase"] == phrase


def test_never_mind_is_not_a_lesson():
    assert lessons.parse("Never mind") is None and lessons.parse("I never said that") is None


def test_a_lesson_is_read_back_saved_and_enforced(office):
    assert talk(office, "Rania, never mention the transfer fee")["kind"] == "confirm"
    assert talk(office, "yes")["text"].startswith("Saved as LS1")
    reception.message(office, PH, "Hi", name_="Ali", now=NOW)
    r = reception.message(office, PH, "What are your fees?", now=NOW)
    assert "transfer fee" not in r["reply"].lower() and r["handover"].startswith("held by lesson LS1")


def test_lessons_reach_the_models_instructions(office, monkeypatch, tmp_path):
    lessons.add(office.log, {"agent": "all", "kind": "always", "rule": "Always reply in the customer's language", "phrase": None}, by="layla")
    seen = []
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake({"verdict": "ok", "evidence": [], "missing": [], "next": [], "actions": []}, seen))
    runner.run(office.log, "nova", request="r", task="t", sources={}, tape_root=tmp_path)
    assert "Always reply in the customer's language (LS1)" in seen[0]["messages"][0]["content"]


def test_review_turns_rania_into_suggestions_and_books_nothing(office):
    assert talk(office, "Rania to review key actions")["kind"] == "refused"  # a PA never changes how agents run
    lessons.set_level(office.log, "rania", "review_key", by="layla")
    reception.message(office, PH, "Hi", name_="Ali", now=NOW)
    r = reception.message(office, PH, "Can I see MC-1204 Saturday at 4pm?", now=NOW)
    assert r["mode"] == "review" and r["suggestion"].endswith("Shall I confirm it?")
    g = office.graph()
    assert not g.of("viewing") and not [m for m in g.nodes[f"chat:{PH}"].props["messages"] if m["type"] == "sent"]
    assert [m["type"] for m in g.nodes[f"chat:{PH}"].props["messages"]][-1] == "suggested"


def test_autonomy_only_takes_authority_away(office):
    c = get("rania")
    lessons.set_level(office.log, "rania", "review_all", by="layla")
    res = runner.submit(office.log, c, Pack("r", "rania", "x", actions=[Action("record_fact", "a"), Action("reply", "b"), Action("approve", "c")]), sources={})
    assert res.event["content"]["allowed"] == ["record_fact"]
    assert [a["content"]["kind"] for a in res.approvals] == ["reply"] and [a["content"]["kind"] for a in res.refused] == ["approve"]
    lessons.set_level(office.log, "rania", "autopilot", by="layla")
    res = runner.submit(office.log, c, Pack("r", "rania", "x", actions=[Action("reply", "b")]), sources={})
    assert res.event["content"]["allowed"] == ["reply"]
