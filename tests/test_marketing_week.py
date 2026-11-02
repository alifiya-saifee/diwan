"""A simulated week, and a simulated month: what goes out when, in what shape, and whether the choices get better."""
from datetime import date, datetime, timedelta, timezone

import pytest

from diwan import brand, business, demo
from diwan.agents import journey, marketing, rhythm, studio, taste
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "yes"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, by="maya")
    return o


MONDAY = date(2026, 11, 2)


@pytest.mark.parametrize("per_week,posts", [(1, 1), (3, 3), (7, 7)])
def test_a_week_has_as_many_posts_as_asked_spread_through_it(office, per_week, posts):
    rhythm.save(office, {"posts_per_week": str(per_week)}, by="maya")
    days = rhythm.make_plan(office, MONDAY, auto=False, days_ahead=7)["days"]
    assert len(days) == posts
    gaps = [(date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days for a, b in zip(days, days[1:])]
    assert not gaps or max(gaps) - min(gaps) <= 1


def test_nothing_repeats_until_everything_has_had_its_turn(office):
    rhythm.save(office, {"posts_per_week": "7"}, by="maya")
    days = [d for d in rhythm.make_plan(office, MONDAY, auto=False, days_ahead=28)["days"] if d.get("ref")]
    refs = [d["ref"] for d in days]
    assert len(set(refs[:6])) == 6  # the demo has 3 listings and 4 topics, taken in turn
    seen = set()
    for d in days:
        assert d["ref"] not in seen or "used" in d["why"] or "covered" in d["why"]  # a repeat says why
        seen.add(d["ref"])


def test_offers_and_teaching_keep_the_share_set(office):
    rhythm.save(office, {"posts_per_week": "7", "topic_share": "50"}, by="maya")
    days = rhythm.make_plan(office, MONDAY, auto=False, days_ahead=14)["days"]
    share = sum(d["type"] == "topic" for d in days) / len(days)
    assert .3 <= share <= .7


def test_the_same_format_does_not_run_day_after_day_when_it_need_not(office, monkeypatch):
    kinds = {}
    def fake(o, ref):
        return kinds.setdefault(ref, ["Reel, voice-over", "Graphic", "Carousel"][len(kinds) % 3]) if ref else ""
    monkeypatch.setattr(marketing, "format_of", fake)
    days = [{"date": f"2026-11-0{i + 2}", "ref": r, "why": r, "type": "listing", "status": "pending"} for i, r in enumerate(["A", "D", "G", "B", "E", "C", "F"])]
    kinds.update(A="Reel", D="Reel", G="Reel", B="Graphic", E="Graphic", C="Carousel", F="Carousel")
    out = rhythm.spread_formats(office, days, set())
    seq = [kinds[d["ref"]] for d in out]
    assert all(a != b for a, b in zip(seq, seq[1:])) and sorted(d["ref"] for d in out) == sorted("ADGBECF")
    assert all(d["why"] == d["ref"] for d in out)


def test_a_day_a_person_fixed_keeps_its_place_in_the_mix(office, monkeypatch):
    monkeypatch.setattr(marketing, "format_of", lambda o, ref: "Reel" if ref in ("A", "B") else "Graphic")
    days = [{"date": "2026-11-02", "ref": "A", "why": "", "type": "listing"}, {"date": "2026-11-03", "ref": "B", "why": "", "type": "listing"}, {"date": "2026-11-04", "ref": "C", "why": "", "type": "listing"}]
    assert rhythm.spread_formats(office, days, {"2026-11-03"})[1]["ref"] == "B"


def test_a_post_on_the_plan_goes_out_on_its_day_not_tomorrow(office):
    far = (datetime.now(timezone.utc) + timedelta(days=5)).date()
    office.log.append("plan.made", actor="maya", agent="plan", content={"rhythm": "weekly", "auto": False, "days": [{"date": far.isoformat(), "ref": "MC-1204", "why": "", "type": "listing", "status": "approved"}], "removed": []})
    slot = studio.schedule(office, None)
    assert datetime.fromisoformat(studio.planned_at(office, "MC-1204", slot["at"])).date() == far
    assert studio.planned_at(office, "JVC-88", slot["at"]) == slot["at"]


def test_a_time_comes_from_our_own_best_hour_once_there_are_five_posts(office):
    assert datetime.fromisoformat(studio.schedule(office, None)["at"]).hour == 19
    for i in range(5):
        hour = 9 if i < 3 else 20
        office.log.append("post.seen", actor="mrival", content={"id": f"own{i}", "source": "own", "at": f"2026-10-{10 + i}T{hour - 4:02d}:00:00+0000", "likes": 500 if hour == 9 else 5, "comments": 0, "engagement": 500 if hour == 9 else 5})
    assert datetime.fromisoformat(studio.schedule(office, None)["at"]).hour == 9


def test_research_runs_once_a_day_by_itself(office):
    rhythm.save(office, {"refresh": "on", "refresh_at": "07:00"}, by="maya")
    morning = datetime(2026, 11, 3, 4, 0, tzinfo=timezone.utc)  # 08:00 in Dubai
    assert rhythm.refresh_due(office, datetime(2026, 11, 3, 2, 0, tzinfo=timezone.utc)) is False
    assert rhythm.refresh_due(office, morning) is True


def test_the_next_day_runs_the_planned_post_once(office):
    rhythm.save(office, {"auto": "on", "at": "07:00", "posts_per_week": "7"}, by="maya")
    rhythm.make_plan(office, date(2026, 11, 3), auto=False, days_ahead=7)
    t = datetime(2026, 11, 3, 4, 0, tzinfo=timezone.utc)
    ref = rhythm.due(office, t)
    assert ref and ref == rhythm.current(office, date(2026, 11, 3))["days"][0]["ref"]
    assert rhythm.due(office, t + timedelta(minutes=1)) is None


def test_planning_ahead_tops_itself_up(office):
    rhythm.save(office, {"plan_ahead": "on", "posts_per_week": "3", "at": "07:00"}, by="maya")
    t = datetime(2026, 11, 3, 4, 0, tzinfo=timezone.utc)
    assert rhythm.plan_due(office, t) is True and rhythm.plan_due(office, t) is False


def test_the_monday_report_counts_what_the_log_says(office):
    office.log.append("lead.attributed", actor="mkt", deal="D1", content={"ref": "MC-1204", "via": "code word", "at": "x"})
    rows = marketing.results(office)
    assert rows[0]["ref"] == "MC-1204" and rows[0]["leads"] == 1
    assert isinstance(marketing.weekly(office), dict | list)


def test_the_plan_gets_better_as_the_owner_says_no(office):
    """A simulated owner who never wants one area. Week by week, how much of the plan does the owner keep?"""
    rhythm.save(office, {"posts_per_week": "7", "topic_share": "0", "repeat_listing_days": "1"}, by="maya")
    pool = rhythm.listings(office)
    areas = [x.get("community") for x in pool if x.get("community")]
    disliked = max(set(areas), key=areas.count)
    kept = []
    for w in range(4):
        start = MONDAY + timedelta(days=7 * w)
        days = [d for d in rhythm.make_plan(office, start, auto=False, days_ahead=7)["days"] if d.get("ref")]
        ok = [d for d in days if (marketing._subject(office, d["ref"]) or {}).get("community") != disliked]
        kept.append(len(ok) / len(days))
        for d in days:
            taste.signal(office, d["ref"], 0 if d not in ok else 1, "plan", by="maya")
    assert kept[-1] > kept[0] and kept[-1] >= .9, kept


def test_teaching_posts_take_turns_through_the_week(office, monkeypatch):
    from diwan.agents import eventpost
    monkeypatch.setattr(eventpost, "_text_wins", lambda o: "winners lean to text")
    rhythm.save(office, {"posts_per_week": "7", "topic_share": "100"}, by="maya")
    days = [d for d in rhythm.make_plan(office, MONDAY + timedelta(days=30), auto=False, days_ahead=4)["days"] if d.get("format")]
    fmts = [d["format"] for d in days]
    assert len(set(fmts)) == 2 and all(a != b for a, b in zip(fmts, fmts[1:]))
    labels = {d["format"]: marketing.format_of(office, d["ref"]) for d in days}
    assert labels["camera"].startswith("Reel") and labels["graphic"] == "Graphic"


def test_a_format_turned_down_leaves_the_mix(office, monkeypatch):
    rhythm.save(office, {"posts_per_week": "7", "topic_share": "100"}, by="maya")
    for _ in range(3):
        office.log.append("taste.reason", actor="mkt", content={"ref": "K1", "why": "boring", "lessons": [{"dim": "format", "value": "graphic", "sign": -1}]})
    assert taste.weight(office, "format:graphic") <= taste.BLOCK
    days = rhythm.make_plan(office, MONDAY + timedelta(days=30), auto=False, days_ahead=4)["days"]
    assert {d.get("format") for d in days if d.get("format")} == {"camera"}


def test_a_post_about_the_company_must_name_it(office):
    from diwan.agents import qa
    bad = {"hook_en": "New to Dubai?", "lines_en": ["We help buyers.", "Thirteen years here.", "Clear advice.", "No pressure.", "Message us."], "hook_ar": "", "lines_ar": []}
    good = bad | {"lines_en": ["At Diwan Realty we help buyers.", *bad["lines_en"][1:]]}
    assert "script-names-us" in [f["check"] for f in qa.review(office, "script", "JOB-introduce", bad, cause=None, attempt=1)]
    assert "script-names-us" not in [f["check"] for f in qa.review(office, "script", "JOB-introduce", good, cause=None, attempt=1)]
