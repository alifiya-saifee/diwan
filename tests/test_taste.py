"""The studio learns: decisions and leads move weights, and the weights change what it chooses next."""
from datetime import date, datetime, timedelta, timezone

import pytest

from diwan import brand, business, demo
from diwan.agents import eventpost, marketing, planner, reader, rhythm, studio, taste
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta

TODAY = date(2026, 11, 2)


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "yes"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, by="maya")
    return o


def no(o, feats, n=1):
    for _ in range(n):
        o.log.append("taste.signal", actor="maya", content={"ref": "X", "y": 0, "strength": 1.0, "features": feats, "source": "test", "why": ""})


def yes(o, feats, n=1):
    for _ in range(n):
        o.log.append("taste.signal", actor="maya", content={"ref": "X", "y": 1, "strength": 1.0, "features": feats, "source": "test", "why": ""})


def test_nothing_learned_changes_nothing(office):
    assert taste.weights(office) == {} and taste.score(office, "MC-1204") == 0 and not taste.ruled_out(office, "MC-1204")


def test_one_no_leans_but_repeated_nos_stop_it(office):
    f = "area:dubai marina"
    no(office, [f])
    assert -0.5 < taste.weight(office, f) < 0 and not taste.ruled_out(office, "MC-1204")
    no(office, [f], 3)
    assert taste.weight(office, f) <= taste.BLOCK


def test_yes_after_no_brings_it_back(office):
    f = "format:graphic"
    no(office, [f], 4)
    low = taste.weight(office, f)
    yes(office, [f], 3)
    assert taste.weight(office, f) > low + 0.5


def test_old_decisions_fade():
    from diwan.agents.taste import _age_gain
    now = datetime(2026, 11, 2, tzinfo=timezone.utc)
    assert _age_gain((now - timedelta(days=45)).isoformat(), now) == pytest.approx(0.5, abs=0.01)


def test_a_lead_counts_more_than_a_yes(office):
    a, b = "area:one", "area:two"
    yes(office, [a])
    office.log.append("taste.signal", actor="maya", content={"ref": "L1", "y": 1, "strength": 1.0, "features": [b], "source": "test", "why": ""})
    office.log.append("lead.attributed", actor="mkt", deal="D1", content={"ref": "L1"})
    assert taste.weight(office, b) > taste.weight(office, a) * 1.5


def test_removing_a_kind_of_post_changes_what_gets_planned(office):
    area = next(f for f in taste.features(office, "MC-1204") if f.startswith("area:"))
    first = {d["ref"] for d in rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)["days"]}
    no(office, [area], 5)
    same_area = {r for r in planner.options(office, TODAY) if area in taste.features(office, r)}
    assert not same_area  # nothing from that area is offered to the Strategist any more
    assert "MC-1204" not in {rhythm._pick(office, TODAY, {})[0]}
    assert first


def test_the_format_follows_this_business_over_competitors(office, monkeypatch):
    from diwan import topics
    monkeypatch.setattr(reader, "winning", lambda o: {"posts": 20, "on_screen": {"text on images": 15, "a person talking to camera": 2}, "line": "x"})
    t = next(x for x in topics.items(office).values() if not x.get("moment"))
    assert marketing.format_of(office, t["ref"]) == "Graphic"
    no(office, ["format:graphic"], 5)
    assert marketing.format_of(office, t["ref"]) == "Reel, to camera"


def test_a_reason_is_understood_and_counts_beyond_that_post(office, monkeypatch):
    monkeypatch.setattr(meta, "look", lambda s, t, i, sc, **k: {"lessons": [{"dim": "tone", "value": "Salesy", "sign": -1}, {"dim": "nonsense", "value": "x", "sign": 1}]})
    got = taste.understand(office, "MC-1204", "Too salesy", ["format:graphic"])
    assert got == [{"dim": "tone", "value": "salesy", "sign": -1}]
    assert taste.weight(office, "tone:salesy") == pytest.approx(-taste.REASON, abs=0.01)
    assert "salesy" in taste.brief(office)


def test_one_no_with_a_reason_only_leans_and_saying_it_again_stops_it(office, monkeypatch):
    f = "subject:homes for sale"
    monkeypatch.setattr(meta, "look", lambda s, t, i, sc, **k: {"lessons": [{"dim": "subject", "value": "homes for sale", "sign": -1}]})
    no(office, [f])
    taste.understand(office, None, "Too salesy", [f])
    assert taste.BLOCK < taste.weight(office, f) < 0
    no(office, [f])
    taste.understand(office, None, "Still too salesy", [f])
    assert taste.weight(office, f) <= taste.BLOCK


def test_what_was_learned_reaches_the_writers_the_strategist_and_the_director(office, monkeypatch, tmp_path):
    from PIL import Image
    from diwan.agents import director
    no(office, ["tone:salesy"], 3)
    assert "salesy" in str(planner._context(office))
    pic = tmp_path / "a.jpg"
    Image.new("RGB", (32, 32)).save(pic)
    asked = {}
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(meta, "look", lambda s, t, i, sc, **k: asked.update(s=s) or {"images": [{"n": 0, "score": 5, "problem": ""}]})
    director.review(office, "A post", "It says", [str(pic)])
    assert "salesy" in asked["s"]


def test_the_scripts_are_offered_best_first(office, monkeypatch):
    a, c = {"angle": "explainer", "hook_en": "Moving here?"}, {"angle": "price-reveal", "hook_en": "AED 2m buys this."}
    no(office, ["angle:explainer"], 3)
    assert taste.script_score(office, c) > taste.script_score(office, a)


def test_removing_on_the_plan_is_a_signal_and_forgetting_undoes_it(office):
    d = rhythm.make_plan(office, rhythm._local_today(office), auto=False, days_ahead=2)["days"][1]
    rhythm.decide_day(office, d["date"], "reject", by="maya")
    feats = taste.features(office, d["ref"])
    assert any(taste.weight(office, f) < 0 for f in feats)
    k = next(f for f in feats if taste.weight(office, f) < 0)
    taste.forget(office, k, by="maya")
    assert taste.weight(office, k) == 0


def test_what_it_learned_is_shown_plainly(office):
    no(office, ["format:graphic"], 5)
    yes(office, ["hook:a question"], 2)
    r = taste.learned(office)
    assert r["decisions"] == 7 and r["early"]
    row = next(x for x in r["rows"] if x["value"] == "graphic")
    assert row["lean"] == "less" and row["strong"] and row["what"] == "Format"


def test_the_page_never_waits_for_instagram(monkeypatch):
    import time
    from diwan.providers import instagram
    monkeypatch.setattr(instagram, "ready", lambda: True)
    monkeypatch.setattr(instagram, "_CHECKED", {})
    monkeypatch.setattr(instagram, "_get", lambda *a, **k: time.sleep(1) or {"username": "diwan"})
    t = time.time()
    r = instagram.check(wait=False)
    assert time.time() - t < 0.3 and r["ok"] is False and r["checking"]
    time.sleep(1.3)
    assert instagram.check(wait=False) == {"ok": True, "username": "diwan"}
