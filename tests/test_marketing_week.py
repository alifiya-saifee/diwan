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


def test_the_posting_hour_comes_from_the_best_source_and_says_which(office, monkeypatch):
    from diwan.providers import instagram
    monkeypatch.setattr(instagram, "ready", lambda: True)
    monkeypatch.setattr(instagram, "online_followers", lambda: {})
    s = studio.schedule(office, None)
    assert datetime.fromisoformat(s["at"]).hour == 19 and "default" in s["why"]  # nothing to go on: said so
    monkeypatch.setattr(instagram, "online_followers", lambda: {h: (900 if h == 8 else 100) for h in range(24)})  # 08:00 Pacific
    s = studio.schedule(office, None)
    assert datetime.fromisoformat(s["at"]).hour in (19, 20) and "Instagram" in s["why"]  # 08:00 in Los Angeles is 19:00 or 20:00 in Dubai (summer or winter time)
    for i in range(8):
        hour = 9 if i < 3 else 20
        office.log.append("post.seen", actor="mrival", content={"id": f"own{i}", "source": "own", "at": f"2026-10-{10 + i}T{hour - 4:02d}:00:00+0000", "likes": 500 if hour == 9 else 5, "comments": 0, "engagement": 500 if hour == 9 else 5})
    s = studio.schedule(office, None)
    assert datetime.fromisoformat(s["at"]).hour == 9 and "our posts" in s["why"]  # our own results beat everything else


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


def test_a_planned_day_is_written_that_morning_even_with_automatic_off(office):
    """The manager made a plan: today's scripts should be waiting, not only when Automatic is on."""
    from datetime import datetime, timezone
    from diwan.agents import rhythm
    rhythm.save(office, {"auto": "off", "at": "09:00", "posts_per_week": "7"}, by="maya")
    today = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)  # 14:00 in Dubai, after the start hour
    assert rhythm.due(office, today) is None  # no plan: nothing is made up by itself while Automatic is off
    plan = rhythm.make_plan(office, today.date(), auto=False, by="maya", days_ahead=7)
    first = next(d for d in plan["days"] if d["date"] == "2026-11-02" and d.get("ref"))
    assert rhythm.due(office, today) == first["ref"]
    assert rhythm.due(office, today) is None  # once a day


def test_posts_go_only_on_the_days_the_person_chose(office):
    rhythm.save(office, {"post_days": "sun, tue thu"}, by="maya")
    assert rhythm.settings(office)["post_days"] == "Tue,Thu,Sun"
    plan = rhythm.make_plan(office, date(2026, 11, 2), auto=False, days_ahead=14)
    days = {date.fromisoformat(d["date"]).strftime("%a") for d in plan["days"] if d.get("ref")}
    assert days and days <= {"Tue", "Thu", "Sun"}
    with pytest.raises(rhythm.Invalid):
        rhythm.save(office, {"post_days": "Funday"}, by="maya")


def test_a_competitor_taken_off_setup_leaves_the_research_board(office):
    for acc in ("rival", "robots"):
        office.log.append("board.pinned", actor="mrival", content={"id": f"pin-{acc}", "kind": "outlier", "account": acc, "title": f"{acc} best post"})
    office.log.append("board.pinned", actor="mtrend", content={"id": "pin-trend", "kind": "trend", "account": "trend", "title": "Eid greetings"})
    office.log.append("setting.changed", actor="maya", content={"person": "studio", "key": "competitors", "value": "rival"})
    assert {c["id"] for c in studio.board(office)} == {"pin-rival", "pin-trend"}


def test_a_planned_post_moves_to_another_day_or_swaps_with_the_one_there(office):
    rhythm.save(office, {"posts_per_week": "3"}, by="maya")
    plan = rhythm.make_plan(office, date(2026, 11, 2), auto=False, days_ahead=7)
    full = [d for d in plan["days"] if d.get("ref")]
    a, b = full[0], full[1]
    p = rhythm.reschedule(office, a["date"], b["date"], by="maya", today=date(2026, 11, 2))  # onto a planned day: they swap
    on = {d["date"]: d.get("ref") for d in p["days"]}
    assert on[a["date"]] == b["ref"] and on[b["date"]] == a["ref"]
    free = next(d for d in (date(2026, 11, 2) + timedelta(days=i) for i in range(7, 14)))
    p = rhythm.reschedule(office, a["date"], free.isoformat(), by="maya", today=date(2026, 11, 2))  # onto an empty day: it moves
    on = {d["date"]: d.get("ref") for d in p["days"]}
    assert on[free.isoformat()] == b["ref"] and not on[a["date"]]
    with pytest.raises(rhythm.Invalid, match="passed"):
        rhythm.reschedule(office, free.isoformat(), "2026-10-01", by="maya", today=date(2026, 11, 2))


def test_an_approved_post_goes_out_at_the_new_time_and_never_in_the_past(office):
    office.log.append("content.made", actor="mpub", content={"id": "S1", "kind": "scheduled", "ref": "MC-1204", "at": "2099-01-01T19:30:00+04:00", "approved_by": "layla"})
    assert not studio.reschedule(office, "MC-1204", "2020-01-01T10:00", by="maya")["ok"]
    r = studio.reschedule(office, "MC-1204", "2099-01-03T09:00", by="maya")
    assert r["ok"] and studio.scheduled(office)["MC-1204"]["at"].startswith("2099-01-03T09:00") and studio.scheduled(office)["MC-1204"]["approved_by"] == "layla"
    assert not studio.reschedule(office, "NOT-WAITING", "2099-01-03T09:00", by="maya")["ok"]
