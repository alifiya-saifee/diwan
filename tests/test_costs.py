"""The same prompt is never paid for twice, every live call is on the ledger, and the monthly cap holds."""
import pytest

from diwan import costs
from diwan.agents import runner
from diwan.events import EventLog
from diwan.providers.chat import PROVIDERS
from tests.conftest import fake
from tests.test_infra import GOOD, MEETING


def _turn(tmp_path, task="Record facts from this turn."):
    return runner.run(EventLog(), "scribe", request="R1", task=task, sources={"meeting:M1": MEETING}, tape_root=tmp_path / "tapes")


def test_identical_request_is_answered_from_the_cache_without_a_call(monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    seen = []
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(GOOD, seen))
    first = _turn(tmp_path)
    second = _turn(tmp_path)
    assert len(seen) == 1
    assert first.usage["provider"] == "meta" and second.usage["provider"] == "tape"
    s = costs.summary()
    assert s["calls"] == 2 and s["cached_calls"] == 1
    assert s["spend_usd"] == costs.estimate("meta", 10, 5) and s["saved_usd"] == costs.estimate("meta", 10, 5)


def test_a_changed_prompt_is_a_new_paid_call(monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    seen = []
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(GOOD, seen))
    _turn(tmp_path, "t1")
    _turn(tmp_path, "t2")
    assert len(seen) == 2


def test_budget_reached_stops_live_calls(monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("DIWAN_BUDGET_USD", "0.0000001")
    seen = []
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(GOOD, seen))
    _turn(tmp_path, "t1")                     # the first call takes the spend past the cap
    assert costs.summary()["over"]
    from diwan.agents.charters import get
    assert not runner.has_model(get("scribe"), "s", "u")   # callers fall back to rules
    with pytest.raises(runner.NotSetUp, match="budget"):
        _turn(tmp_path, "t2")
    assert len(seen) == 1


def test_marketing_and_the_rest_of_the_office_have_separate_caps(monkeypatch, tmp_path):
    from diwan.agents.charters import get
    assert costs.part_of("mscript") == "marketing" and costs.part_of("mkt") == "marketing" and costs.part_of("rania") == "rest"
    assert costs.budget() == 25 and costs.budget("marketing") == 20 and costs.budget("rest") == 5  # the defaults
    costs.record("mscript", {"provider": "meta"}, extra_usd=20.5)  # Marketing spends past its 20
    assert not costs.allowed("mtrend") and costs.allowed("scribe")  # the studio stops; the front desk keeps working
    monkeypatch.setenv("META_API_KEY", "k")
    assert not runner.has_model(get("mscript"), "s", "u") and runner.has_model(get("scribe"), "s", "u")
    costs.record("scribe", {"provider": "meta"}, extra_usd=4.6)  # the whole office past 25: everyone stops
    assert not costs.allowed("scribe") and not costs.allowed()
    parts = costs.summary()["parts"]
    assert parts["marketing"] == {"budget_usd": 20, "spend_usd": 20.5, "left_usd": 0, "over": True} and parts["rest"]["spend_usd"] == 4.6
    monkeypatch.setenv("DIWAN_BUDGET_MARKETING_USD", "30")  # a Marketing cap above the total is held to the total
    assert costs.budget("marketing") == 25 and costs.budget("rest") == 0


def test_nvidia_free_endpoint_costs_nothing():
    assert costs.estimate("nvidia", 10_000, 10_000) == 0.0


def test_price_can_be_corrected(monkeypatch):
    monkeypatch.setenv("DIWAN_PRICE_META", "1,2")
    assert costs.estimate("meta", 1_000_000, 1_000_000) == 3.0


def _search_reply(final: str):
    import httpx
    body = {"model": "muse-spark-1.3", "usage": {"input_tokens": 100, "output_tokens": 50},
            "output": [{"type": "message", "content": [{"type": "output_text", "text": "I'll research what's performing for Dubai brokers."}]},
                       {"type": "web_search_call", "action": {"query": "dubai reels"},
                        "results": [{"title": "Reel guide", "url": "https://example.com/reels"}, {"title": "Hooks", "url": "https://example.com/hooks"}]},
                       {"type": "message", "content": [{"type": "output_text", "text": final}]}]}
    return httpx.MockTransport(lambda req: httpx.Response(200, json=body))


def test_trends_pin_only_the_final_answer_tied_to_pages_the_search_opened(monkeypatch, tmp_path):
    """The first live run pinned the model's narration ("I'll research...") as trends."""
    from diwan import business, demo
    from diwan.agents import studio
    from diwan.office import Office
    from diwan.providers import meta
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setattr(meta, "TRANSPORT", _search_reply(
        "1. Price-first hooks | stop the scroll | https://example.com/reels\n2. Walk with the broker | feels personal | https://example.com/hooks\n"
        "3. Invented trend | made up | https://nowhere.example/x"))
    o = Office(EventLog()); demo.seed(o)
    assert studio.trends(o, None) == []  # no search until the business is set
    assert any("Set your industry and country" in e["content"]["needs"] for e in o.log.list() if e["type"] == "step.blocked")
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "city": "Dubai"}, by="maya")
    cards = studio.trends(o, None)
    assert [c["title"] for c in cards] == ["Price-first hooks", "Walk with the broker"]          # the made-up link is dropped
    assert not any("research" in c["title"].lower() for c in cards)
    assert studio.trends(o, None) == cards                                                    # same day: no second search
    row = costs.rows()[-1]
    assert row["what"] == "web search x1" and row["cost_usd"] == round(costs.estimate("meta", 100, 50) + costs.fee("search", 0.01), 6)


def test_search_images_and_transcription_stop_at_the_budget(monkeypatch):
    from diwan.providers import meta
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("DIWAN_BUDGET_USD", "0")
    for call in (lambda: meta.search("x"), lambda: meta.image("x", "n"), lambda: meta.transcribe(b"0" * 100)):
        with pytest.raises(meta.MetaError, match="budget"):
            call()
