"""Script variants on different angles, a person's change request, and when to keep, shift or rest an angle."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from diwan import demo
from diwan.agents import qa, strategy, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    return o


NOW = datetime(2026, 10, 28, tzinfo=timezone.utc)


def own(o, rows):
    """rows: (caption, engagement) oldest first, a day apart, ending yesterday."""
    out = []
    for i, (cap, eng) in enumerate(rows):
        at = (NOW - timedelta(days=len(rows) - i)).strftime("%Y-%m-%dT%H:%M:%S+0000")
        out.append({"source": "own", "account": "us", "url": f"https://instagram.com/p/{i}", "type": "REELS", "caption": cap,
                    "likes": str(eng), "comments": "0", "posted_at": at[:19].replace("T", " ")})
    studio.import_posts(o, out, by="maya")


PRICE, TOUR, LIFE = "What does AED 2M buy in Marina?", "Step inside this Marina home", "Imagine your mornings by the water"


def test_three_checked_scripts_on_different_angles_are_offered(office):
    studio.run_now(office, "MC-1204")
    req = studio.script_request(office, "MC-1204")
    opts = studio.script_options(office, req.props["text"])
    assert len(opts) == 3 and len({o["angle"] for o in opts}) == 3
    passed = [e for e in office.log.list() if e["type"] == "qa.passed" and e["content"]["kind"] == "script"]
    assert {e["content"]["item"] for e in passed} >= {o["id"] for o in opts}  # each one checked before it is offered
    assert not studio.made(office, "film list", "MC-1204")


def test_the_picked_script_is_the_one_filmed(office):
    studio.run_now(office, "MC-1204")
    second = studio.script_options(office, studio.script_request(office, "MC-1204").props["text"])[1]
    studio.approve_script_now(office, "MC-1204", choice=second["id"])
    assert studio.approved_script(office, "MC-1204")["id"] == second["id"]
    assert studio.made(office, "film list", "MC-1204")


def test_a_change_request_revises_only_that_script_and_asks_again(office):
    studio.run_now(office, "MC-1204")
    req = studio.script_request(office, "MC-1204")
    a, b, c = studio.script_options(office, req.props["text"])
    office.log.append("decision.made", actor="maya", content={"card": req.id, "answer": "revise", "choice": b["id"], "note": "make the hook shorter"})
    asyncio.run(studio.script_revise(office, "MC-1204", b["id"], "make the hook shorter", req.id, pause=0))
    new = studio.script_options(office, studio.script_request(office, "MC-1204").props["text"])
    assert [x["id"] for x in new][0] == a["id"] and [x["id"] for x in new][2] == c["id"]
    assert new[1]["revises"] == b["id"] and new[1]["angle"] == b["angle"]
    assert len(new[1]["hook_en"].split()) <= min(8, len(b["hook_en"].split()))


def test_a_feature_first_change_without_a_model(office):
    lst = office.graph().nodes["listing:MC-1204"].props
    f = lst["features"][-1]
    d = studio._apply_rules({"hook_en": "h", "hook_ar": "x", "lines_en": ["a.", f"{f}.", "b."]}, f"put the {f} first", lst)
    assert d["lines_en"][0].lower().startswith(f.lower())


def test_angles_are_read_from_captions():
    assert strategy.angle_of(PRICE) == "price-reveal" and strategy.angle_of(TOUR) == "walkthrough" and strategy.angle_of(LIFE) == "lifestyle"


def test_status_rules():
    now = NOW
    assert strategy.status([1.0], now, now) == "untested"
    assert strategy.status([1.3, 1.5], now, now) == "winning"
    assert strategy.status([1.6, 1.2, 0.9], now, now) == "fading"
    assert strategy.status([0.6, 0.7], now - timedelta(days=3), now) == "retired"
    assert strategy.status([0.6, 0.7], now - timedelta(days=40), now) == "untested"   # rested long enough: test again
    assert strategy.status([1.0, 1.1], now, now) == "steady"


def test_keep_what_wins_shift_from_what_fades_and_always_explore(office):
    own(office, [(PRICE, 100), (TOUR, 300), (LIFE, 100), (TOUR, 280), (PRICE, 260), (LIFE, 60), (PRICE, 200), (LIFE, 50), (PRICE, 90)])
    r = {x["angle"]: x for x in strategy.report(office, NOW)["angles"]}
    assert r["walkthrough"]["status"] == "winning"
    assert r["price-reveal"]["status"] == "fading"
    assert r["lifestyle"]["status"] == "retired"
    picks = strategy.pick(office, 3, NOW)
    angles = [p["angle"] for p in picks]
    assert angles[0] == "walkthrough" and "price-reveal" not in angles and "lifestyle" not in angles
    assert picks[-1]["slot"] == "explore"


def test_without_our_history_lead_with_what_wins_in_the_market(office):
    rows = [{"source": "competitor", "account": "rival", "url": f"u{i}", "type": "REELS", "caption": cap, "likes": str(v), "comments": "0", "posted_at": ""}
            for i, (cap, v) in enumerate([(TOUR, 900), (TOUR, 800), ("hello", 100), ("hi", 100), ("hey", 100), (PRICE, 120)])]
    studio.import_posts(office, rows, by="maya")
    picks = strategy.pick(office, 3, NOW)
    assert picks[0]["angle"] == "walkthrough" and picks[0]["slot"] == "market"


def test_the_review_catches_what_the_live_model_got_wrong(office):
    """The first live Studio run (28 Oct) passed review with placeholders, repeated lines and no call to action."""
    bad = {"id": "C5", "hook_en": "A day in Unit 1204, Marina Crest, Dubai Marina", "hook_ar": "يوم في الوحدة 1204",
           "lines_en": ["This is Unit 1204, Marina Crest, Dubai Marina.", "A 2 bed apartment.", "Morning here: [detail not in listing]",
                        "This is Unit 1204, Marina Crest, Dubai Marina.", "Priced at AED 2,600,000."]}
    rules = {f["check"] for f in qa.review(office, "script", "MC-1204", bad, cause=None, attempt=1)}
    assert {"script-no-placeholders", "script-no-repeats", "script-call-to-action"} <= rules
    idea = {"ideas": [], "pick": {"title": "MC-1204 Unit 1204 tour - no cards", "cards": []}}
    assert "idea-no-notes" in {f["check"] for f in qa.review(office, "ideas", "MC-1204", idea, cause=None, attempt=1)}


def test_the_writers_see_the_listing_features(office):
    assert "features: sea view" in studio._brief(office, "MC-1204").lower()


def test_a_word_after_the_price_is_not_a_multiplier():
    """Found on the live run: "AED 2,600,000 m..." was read as 2.6 trillion and a good script was thrown out."""
    assert studio._amounts("AED 2,600,000 makes it yours") == {2_600_000}
    assert studio._amounts("AED 2.6M") == {2_600_000} and studio._amounts("AED 950k") == {950_000}
