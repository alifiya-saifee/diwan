from datetime import date, datetime, timedelta, timezone

import pytest

from diwan import brand, business, demo, knowledge, topics
from diwan.agents import journey, qa, rhythm, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import instagram, meta

TODAY = date(2026, 10, 29)


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    monkeypatch.setattr(studio, "_now", lambda: datetime(2026, 10, 29, 12, tzinfo=timezone.utc))


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE"}, by="maya")
    return o


def branded(o):
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit.",
                   "audience": "first-time buyers in Dubai"}, by="maya")
    return o


def own_posts(o, n, day="2026-10-20"):
    for i in range(n):
        o.log.append("post.seen", actor="mrival", agent="mrival", content={"id": f"p{i}", "source": "own", "account": "us", "likes": 10, "comments": 1,
                                                                            "engagement": 11, "at": f"{day}T10:00:00+0000", "caption": "x"})


def approve(o, ref):
    studio.run_now(o, ref)
    studio.approve_script_now(o, ref, choice=studio.made(o, "script", ref)["id"])


def test_no_posts_in_sight_is_not_the_same_as_a_new_account(office):
    assert journey.stage(office) == "unknown" and journey.report(office)["ask"]
    assert journey.upcoming(office, 3) == []


def test_a_new_account_starts_with_an_introduction_not_a_listing(office):
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    r = journey.report(office)
    assert r["stage"] == "introduce" and r["next"]["ref"] == "JOB-introduce" and r["next"]["title"] == "Meet Diwan Realty"
    assert [s["job"] for s in r["steps"]][:4] == ["introduce", "why-us", "educate", "offer"]


@pytest.fixture
def connected(monkeypatch):
    monkeypatch.setattr(journey, "_TRIED", {"at": 0.0})
    monkeypatch.setattr(instagram, "ready", lambda: True)


def test_a_connected_account_is_read_before_it_is_called_new(office, connected, monkeypatch):
    branded(office)
    assert journey.stage(office) == "unknown"  # connected, but nobody has looked yet
    monkeypatch.setattr(instagram, "own_posts", lambda: [])
    assert journey.report(office)["stage"] == "introduce"


def test_a_connected_account_with_posts_is_not_treated_as_new(office, connected, monkeypatch):
    rows = [{"id": f"p{i}", "account": "us", "likes": 5, "comments": 1, "at": "2026-10-20T10:00:00+0000", "caption": "x"} for i in range(12)]
    monkeypatch.setattr(instagram, "own_posts", lambda: rows)
    r = journey.report(office)
    assert r["stage"] == "build" and r["posts"] == 12 and r["next"] is None


def test_instagram_failing_to_answer_leaves_the_account_unknown(office, connected, monkeypatch):
    def fail():
        raise instagram.InstagramError("token expired")
    monkeypatch.setattr(instagram, "own_posts", fail)
    r = journey.report(office)
    assert r["stage"] == "unknown" and r["ask"]


def test_saying_we_already_post_does_not_pretend_to_know_the_posts(office):
    business.save(office, {"posted_before": "yes"}, by="maya")
    r = journey.report(office)
    assert r["stage"] == "build" and "can't be seen" in r["why"] and r["next"] is None


def test_without_the_brand_the_first_post_asks_for_it_and_nothing_jumps_ahead(office):
    business.save(office, {"posted_before": "no"}, by="maya")
    s = journey.upcoming(office, 3)
    assert len(s) == 1 and s[0]["ref"] is None and "Who we are" in s[0]["why"]


def test_the_introduction_is_written_from_the_brand_and_ticks_the_first_step(office):
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    studio.run_now(office, "JOB-introduce")
    sc = studio.made(office, "script", "JOB-introduce")
    assert sc["job"] == "introduce" and sc["hook_en"].startswith("Meet Diwan Realty") and sc["angle"] in journey.ANGLES
    assert any("tells buyers the whole cost" in x for x in sc["lines_en"])
    studio.approve_script_now(office, "JOB-introduce", choice=sc["id"])
    r = journey.report(office)
    assert r["steps"][0]["state"] == "done" and r["next"]["ref"] == "JOB-why-us" and r["waiting"] == 1


def test_the_plan_follows_the_first_nine_then_the_usual_mix(office):
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    rhythm.save(office, {"rhythm": "weekly"}, by="maya")
    days = rhythm.make_plan(office, TODAY, auto=False)["days"]
    assert [d["job"] for d in days[:4]] == ["introduce", "why-us", "educate", "offer"]
    assert days[0]["ref"] == "JOB-introduce" and len({d["ref"] for d in days if d["ref"]}) == len([d for d in days if d["ref"]])


def test_proof_with_no_numbers_is_skipped_and_says_why(office):
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    assert journey.item(office, "JOB-team") is None
    assert any("People tab" in s for s in journey.report(office)["skipped"])


def test_older_accounts_are_past_the_first_nine(office):
    branded(office)
    own_posts(office, 12)
    assert journey.stage(office) == "build" and journey.report(office)["steps"] == []
    own_posts(office, 31)
    assert journey.stage(office) == "grow"


def test_a_silent_account_comes_back_first(office):
    branded(office)
    own_posts(office, 12, day="2026-08-01")
    assert journey.stage(office) == "comeback" and journey.upcoming(office, 1)[0]["ref"] == "JOB-comeback"
    approve(office, "JOB-comeback")
    assert journey.stage(office) == "build"


def test_a_moment_goes_before_everything_until_its_script_is_approved(office):
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    ref = topics.save_moment(office, {"title": "New golden visa rule", "what": "The minimum property value for the golden visa changed this week."}, by="maya")
    assert journey.upcoming(office, 2)[0]["ref"] == ref and journey.upcoming(office, 2)[1]["ref"] == "JOB-introduce"
    approve(office, ref)
    assert journey.upcoming(office, 1)[0]["ref"] == "JOB-introduce"


def test_a_moment_needs_facts_and_lapses(office):
    with pytest.raises(ValueError, match="facts"):
        topics.save_moment(office, {"title": "Big news", "what": "short"}, by="maya")
    ref = topics.save_moment(office, {"title": "Old news", "what": "Something happened that mattered for a while.", "until": "2020-01-01"}, by="maya")
    assert ref not in topics.items(office)


def test_a_new_project_is_a_moment_and_the_demos_are_not(office):
    assert journey.moments(office) == []
    k = knowledge.add(office, "project", "Marina Vista", "A new tower in the Marina with handover in 2028.", by="layla")["id"]
    assert [m["ref"] for m in journey.moments(office) if m["ref"] == k] == [k]


def test_a_listing_script_is_told_the_company_facts_and_who_is_speaking(office, monkeypatch):
    seen = {}
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    monkeypatch.setattr(studio.runner, "has_model", lambda c, s, u, schema=None: seen.update(user=u) or False)
    studio.run_now(office, "MC-1204")
    assert "About us" in seen["user"] and "The job of this post" in seen["user"] and "format only" in seen["user"]


def test_the_review_sends_back_a_track_record_nobody_confirmed(office):
    branded(office)
    bad = {"hook_en": "Trusted by 500 families", "lines_en": ["Over 15 years in Dubai."]}
    assert qa._stray_claims(office, "MC-1204", qa._script_text(bad)) == ["500 families", "15 years"]
    office.add_knowledge("track record", "Our record", "We have helped 500 families.", by="layla")
    assert qa._stray_claims(office, "MC-1204", qa._script_text(bad)) == ["15 years"]


def test_each_script_tells_its_own_idea(office, monkeypatch):
    ideas = [{"title": f"Idea {i}", "angle": "x", "cards": [], "from": []} for i in range(3)]
    seen = []
    real = studio.script
    monkeypatch.setattr(studio, "script", lambda o, r, idea, *a, **k: seen.append(idea["pick"]["title"]) or real(o, r, idea, *a, **k))
    studio.variants(office, "MC-1204", {"id": "I", "ideas": ideas, "pick": ideas[0]}, None, None)
    assert len(set(seen)) == 3


def test_only_a_clear_win_is_pinned(office):
    small = {"engagement": 6, "avg": 3}
    big = {"engagement": 900, "avg": 680}
    assert not studio.clear_win(small) and studio.clear_win(big)


def test_approving_a_topic_or_brand_script_on_the_page_counts_and_moves_on(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from diwan import app as appmod
    monkeypatch.setenv("DIWAN_DB", str(tmp_path / "t.db"))
    with TestClient(appmod.app) as c:
        o = appmod.S.office
        branded(o)
        business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "no"}, by="maya")
        studio.run_now(o, "JOB-introduce")
        req = studio.script_request(o, "JOB-introduce")
        choice = studio.script_options(o, req.props["text"])[0]["id"]
        r = c.post(f"/api/requests/{req.id}/decide", json={"decision": "approve", "by": "maya", "choice": choice})
        assert r.status_code == 200 and r.json()["ok"]
        assert [u["job"] for u in rhythm.used(o)] == ["introduce"]


def test_a_brand_post_leaves_out_hours_fees_and_paperwork_and_invents_no_story(office, monkeypatch):
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    facts = " ".join(journey.item(office, "JOB-introduce")["features"])
    assert "whole cost" in facts and not any(w in facts for w in ("10am", "2%", "photo ID"))
    assert "Never invent a memory" in journey.brief(office, studio._listing(office, "JOB-introduce"))


def test_identical_template_scripts_are_offered_once(office):
    branded(office)
    business.save(office, {"posted_before": "no"}, by="maya")
    studio.run_now(office, "JOB-introduce")
    idea = studio.made(office, "ideas", "JOB-introduce")
    assert len(studio.variants(office, "JOB-introduce", idea, None, None)) == 1
