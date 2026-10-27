import json
import sqlite3

import httpx
import pytest

from diwan.agents import runner
from diwan.agents.charters import ROSTER, get
from diwan.events import EventLog
from diwan.pack import ACTIONS, Action, Evidence, Pack, check_evidence
from diwan.providers.chat import PROVIDERS, ProviderError, for_tier, parse_json

MEETING = "Omar: What's the budget? Karim: Two point six million. Actually, forget my brother. I'll pay it all myself."
KEYS = ["META_API_KEY", "MODEL_API_KEY", "BASETEN_API_KEY", "FIREWORKS_API_KEY", "FIREWORKS_MODEL", "MODAL_ENDPOINT_URL",
        "MODAL_MODEL", "MODAL_API_KEY", "DIWAN_OFFLINE", "DIWAN_TAPE", "DIWAN_OPEN_ORDER", "DIWAN_OPEN_FALLBACK"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Tests never see the developer's .env or real keys."""
    monkeypatch.setattr("diwan.config.ROOT", tmp_path)
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for p in PROVIDERS.values():
        monkeypatch.setattr(p, "transport", None)


def fake(reply: dict, seen: list | None = None):
    def handle(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    return httpx.MockTransport(handle)


GOOD = {"verdict": "The payer changed from the brother to Karim.",
        "evidence": [{"quote": "Actually, forget my brother. I'll pay it all myself.", "source": "meeting:M1"},
                     {"quote": "My brother sends it from Lagos.", "source": "meeting:M1"}],
        "missing": ["Source of Karim's funds"], "next": ["Compliance lead reviews first"],
        "actions": [{"kind": "record_fact", "summary": "Payer: Karim"}, {"kind": "decide_suspicion", "summary": "Mark as suspicious"}]}


# the roster

def test_every_charter_is_complete_and_wired():
    ids = {c.id for c in ROSTER}
    assert len(ids) == len(ROSTER)
    for c in ROSTER:
        assert c.parent is None or c.parent in ids, c.id
        assert c.never and c.job and c.reviewer, c.id
        assert set(c.alone) | set(c.person) <= set(ACTIONS), c.id
        assert not set(c.alone) & set(c.person), c.id
    assert [c.id for c in ROSTER if c.parent is None] == ["nova"]


def test_no_agent_may_do_what_only_people_do():
    for c in ROSTER:
        assert not {"approve", "release_money", "decide_suspicion"} & set(c.alone), c.id
        assert "submit" not in c.alone and "file_report" not in c.alone, c.id


def test_review_agents_report_to_no_team():
    for c in ROSTER:
        if c.review:
            assert c.parent in ("nova", "review")


# the pack

def test_invented_quotes_are_removed_not_shown():
    p = Pack("R1", "scribe", "x", evidence=[Evidence("forget my brother", "meeting:M1"), Evidence("I own three villas", "meeting:M1"),
                                            Evidence("forget my brother", "meeting:M9")])
    check_evidence(p, {"meeting:M1": MEETING})
    assert [e.quote for e in p.evidence] == ["forget my brother"]
    assert len(p.rejected_quotes) == 2


def test_quote_check_ignores_curly_quotes_and_spacing():
    p = Pack("R1", "scribe", "x", evidence=[Evidence("I’ll  pay it all\nmyself", "m")])
    check_evidence(p, {"m": MEETING})
    assert p.evidence


# authority

def test_charter_decides_what_happens_to_each_action():
    log = EventLog()
    pack = Pack("R1", "pay", "Expect AED 1,170,000 from Karim", actions=[
        Action("expect_payment", "Expect from Karim"), Action("approve", "Accept the payment"), Action("release_money", "Pay seller")])
    res = runner.submit(log, get("pay"), pack, sources={})
    assert [e["content"]["kind"] for e in res.approvals] == ["approve"]
    assert [e["content"]["kind"] for e in res.refused] == ["release_money"]
    assert res.event["content"]["allowed"] == ["expect_payment"]
    assert all(e["agent"] == "pay" for e in log.list())


# events

def test_log_is_append_only_and_idempotent():
    log = EventLog()
    a = log.append("agent.started", actor="scribe", agent="scribe", key="k1")
    assert log.append("agent.started", actor="scribe", agent="scribe", key="k1")["duplicate"]
    with pytest.raises(sqlite3.DatabaseError):
        log.db.execute("update events set actor='x' where id=?", (a["id"],))
    with pytest.raises(ValueError):
        log.append("made.up", actor="x")


# providers

def test_providers_are_off_until_keys_exist(monkeypatch):
    assert for_tier("spark") is None and for_tier("open") is None
    monkeypatch.setenv("META_API_KEY", "k")
    assert for_tier("spark") is PROVIDERS["meta"]
    monkeypatch.setenv("DIWAN_OFFLINE", "1")
    assert for_tier("spark") is None


def test_missing_names_settings_never_values(monkeypatch):
    assert PROVIDERS["fireworks"].missing() == ["FIREWORKS_API_KEY", "FIREWORKS_MODEL"]
    assert PROVIDERS["modal"].missing() == ["MODAL_ENDPOINT_URL", "MODAL_MODEL"]
    monkeypatch.setenv("BASETEN_API_KEY", "secret-value")
    assert PROVIDERS["baseten"].missing() == [] and "secret-value" not in repr(PROVIDERS["baseten"])


def test_open_tier_follows_the_chosen_order(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "k")
    monkeypatch.setenv("FIREWORKS_API_KEY", "k")
    monkeypatch.setenv("FIREWORKS_MODEL", "m")
    assert for_tier("open").id == "baseten"
    monkeypatch.setenv("DIWAN_OPEN_ORDER", "fireworks,baseten")
    assert for_tier("open").id == "fireworks"


def test_compliance_never_quietly_moves_to_metas_api(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    assert runner.provider_for(get("sof")) is None
    monkeypatch.setenv("DIWAN_OPEN_FALLBACK", "spark")
    assert runner.provider_for(get("sof")).id == "meta"


def test_fenced_json_is_read():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ProviderError):
        parse_json("sorry, I can't")


# a whole turn

def test_live_turn_records_a_tape_and_replays_it_offline(monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("DIWAN_TAPE", "record")
    seen = []
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(GOOD, seen))
    log = EventLog()
    res = runner.run(log, "scribe", request="R1", task="Record facts from this turn.", sources={"meeting:M1": MEETING},
                     deal="marina-1204", tape_root=tmp_path / "tapes")
    body = seen[0]
    assert body["model"] == "muse-spark-1.3" and body["response_format"]["json_schema"]["name"] == "agent_pack"
    assert "You never: Guess" in body["messages"][0]["content"]
    assert [e.quote for e in res.pack.evidence] == ["Actually, forget my brother. I'll pay it all myself."]
    assert [e.quote for e in res.pack.rejected_quotes] == ["My brother sends it from Lagos."]
    assert [e["content"]["kind"] for e in res.refused] == ["decide_suspicion"]
    assert res.usage["provider"] == "meta"
    assert [e["type"] for e in log.list()] == ["agent.started", "agent.pack", "agent.refused"]

    monkeypatch.setenv("DIWAN_OFFLINE", "1")
    again = runner.run(EventLog(), "scribe", request="R1", task="Record facts from this turn.", sources={"meeting:M1": MEETING},
                       tape_root=tmp_path / "tapes")
    assert again.usage["provider"] == "tape" and again.usage["recorded_from"] == "meta"
    assert again.pack.verdict == res.pack.verdict


def test_no_model_and_no_tape_fails_loudly_and_is_logged(tmp_path):
    log = EventLog()
    with pytest.raises(runner.NotSetUp, match="META_API_KEY"):
        runner.run(log, "scribe", request="R1", task="t", sources={}, tape_root=tmp_path)
    assert [e["type"] for e in log.list()] == ["agent.started", "agent.failed"]


def test_rules_agents_cannot_be_sent_to_a_model():
    with pytest.raises(ValueError, match="submit"):
        runner.provider_for(get("screen"))


def test_tape_is_not_reused_when_the_prompt_changes(monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("DIWAN_TAPE", "record")
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(GOOD))
    runner.run(EventLog(), "scribe", request="R1", task="t1", sources={"meeting:M1": MEETING}, tape_root=tmp_path)
    monkeypatch.setenv("DIWAN_OFFLINE", "1")
    with pytest.raises(runner.NotSetUp):
        runner.run(EventLog(), "scribe", request="R1", task="t2", sources={"meeting:M1": MEETING}, tape_root=tmp_path)
