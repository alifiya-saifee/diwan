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


def test_nvidia_free_endpoint_costs_nothing():
    assert costs.estimate("nvidia", 10_000, 10_000) == 0.0


def test_price_can_be_corrected(monkeypatch):
    monkeypatch.setenv("DIWAN_PRICE_META", "1,2")
    assert costs.estimate("meta", 1_000_000, 1_000_000) == 3.0
