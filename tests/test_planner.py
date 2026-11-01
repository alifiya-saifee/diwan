"""The Strategist chooses what goes on the plan; the code decides what may. Planning ahead keeps two weeks ready by itself."""
from datetime import date, datetime, timedelta, timezone

import pytest

from diwan import brand, business, demo
from diwan.agents import planner, rhythm, runner
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta
from diwan.providers.chat import Reply

TODAY = date(2026, 11, 2)


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "yes"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, by="maya")
    return o


def strategist(monkeypatch, pick):
    """A stand-in for the model. pick(dates, refs) -> the days it answers with."""
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: True)
    seen = {}

    def call(c, system, user, schema=None, **k):
        seen["user"] = user
        assert schema["name"] and schema["schema"]["required"] == ["days"]  # the shape the real client reads
        return Reply({"days": pick(seen)}, {})

    monkeypatch.setattr(runner, "call", call)
    return seen


def test_two_weeks_can_be_asked_for_even_on_a_daily_rhythm(office):
    p = rhythm.make_plan(office, TODAY, auto=False, days_ahead=14, think=True)
    assert len(p["days"]) == 14 and p["chosen_by"] == "rules"  # no model here: the plain plan stands


def test_the_strategist_chooses_the_days(office, monkeypatch):
    refs = list(planner.options(office, TODAY))
    strategist(monkeypatch, lambda s: [{"date": (TODAY + timedelta(days=i)).isoformat(), "ref": refs[-1 - i], "why": "Buyers ask about this most, so it goes first."} for i in range(3)])
    p = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3, think=True)
    assert p["chosen_by"] == "muse-spark" and [d["ref"] for d in p["days"]] == [refs[-1], refs[-2], refs[-3]]
    assert p["days"][0]["why"].startswith("Buyers ask")


def test_a_choice_that_does_not_hold_up_keeps_the_plain_day(office, monkeypatch):
    plain = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)["days"]
    real = next(r for r in planner.options(office, TODAY) if r not in {d["ref"] for d in plain})
    strategist(monkeypatch, lambda s: [
        {"date": plain[0]["date"], "ref": "MADE-UP", "why": "A listing that does not exist."},
        {"date": plain[1]["date"], "ref": real, "why": "Card K5 says so."},  # internal notes never reach the page
        {"date": plain[2]["date"], "ref": real, "why": "A plain reason."}])
    p = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3, think=True)
    assert [d["ref"] for d in p["days"]][:2] == [plain[0]["ref"], plain[1]["ref"]] and p["days"][2]["ref"] == real


def test_replanning_keeps_what_a_person_decided(office):
    first = rhythm.make_plan(office, TODAY, auto=False, days_ahead=7)
    keep, gone = first["days"][1], first["days"][2]
    rhythm.decide_day(office, keep["date"], "approve", by="maya")
    rhythm.decide_day(office, gone["date"], "reject", by="maya")
    again = rhythm.make_plan(office, TODAY, auto=False, days_ahead=14)
    day = next(d for d in again["days"] if d["date"] == keep["date"])
    assert day["ref"] == keep["ref"] and day["status"] == "approved"
    assert gone["ref"] not in {d.get("ref") for d in again["days"]}


def test_planning_ahead_renews_itself_and_writes_nothing(office):
    at = datetime(2026, 11, 2, 6, 0, tzinfo=timezone.utc)  # 10:00 in Dubai
    assert rhythm.plan_due(office, at) is False  # off until someone turns it on
    rhythm.save(office, {"plan_ahead": "on"}, by="maya")
    assert rhythm.plan_due(office, at) is False  # nobody has said how many: it does not guess
    rhythm.save(office, {"posts_per_week": "7"}, by="maya")
    assert rhythm.plan_due(office, at) is True
    assert len(rhythm.current(office, at.date())["days"]) == 7
    assert rhythm.plan_due(office, at + timedelta(days=2)) is False  # 5 days still ahead
    assert rhythm.plan_due(office, at + timedelta(days=5)) is True  # 2 left: the next week gets planned
    assert max(d["date"] for d in rhythm.current(office, at.date() + timedelta(days=5))["days"]) == "2026-11-13"
    assert not rhythm.started(office)


def new_listing(o, ref="NEW-1", actor="maya"):
    o.log.append("listing.added", actor=actor, content={"ref": ref, "title": "Apartment 1501, Creek Harbour", "community": "Creek Harbour", "type": "apartment",
                                                         "status": "available", "permit": "1234567", "price_aed": 2000000, "bedrooms": 2, "features": []})


def test_a_new_listing_is_recommended_first_with_the_reason(office):
    from diwan.agents import journey
    new_listing(office)
    first = journey.upcoming(office, 3, TODAY + timedelta(days=0))[0]
    assert first["ref"] == "NEW-1" and first["why"].startswith("Just added")
    assert rhythm.make_plan(office, TODAY, auto=False, days_ahead=7)["days"][0]["ref"] == "NEW-1"


def test_a_new_account_still_introduces_itself_before_a_new_listing(office):
    from diwan.agents import journey
    business.save(office, {"posted_before": "no"}, by="maya")
    new_listing(office)
    assert [s["job"] for s in journey.upcoming(office, 2, TODAY)] == ["introduce", "moment"]


def test_an_import_is_not_news(office):
    from diwan.agents import journey
    for i in range(4):
        new_listing(office, f"NEW-{i}", actor="feed")
    assert not [m for m in journey.moments(office) if m["ref"].startswith("NEW-")]


def test_the_strategist_can_not_bring_back_what_a_person_rejected(office, monkeypatch):
    first = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)
    gone = first["days"][1]
    rhythm.decide_day(office, gone["date"], "reject", by="maya")
    strategist(monkeypatch, lambda s: [{"date": d["date"], "ref": gone["ref"], "why": "It would do well."} for d in first["days"]])
    assert gone["ref"] not in {d.get("ref") for d in rhythm.make_plan(office, TODAY, auto=False, days_ahead=3, think=True)["days"]}


def test_it_plans_only_as_many_posts_as_a_person_said(office):
    rhythm.save(office, {"posts_per_week": "3"}, by="maya")
    days = rhythm.make_plan(office, TODAY, auto=False, days_ahead=14)["days"]
    assert len(days) == 6 and days[0]["date"] == TODAY.isoformat()
    gaps = [(date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days for a, b in zip(days, days[1:])]
    assert set(gaps) <= {2, 3}  # spread out, not three in a row
    assert len(rhythm.make_plan(office, TODAY, auto=False, days_ahead=1)["days"]) == 1  # just today


def test_an_automatic_run_rests_on_a_day_without_a_post(office):
    rhythm.save(office, {"posts_per_week": "3", "auto": "on"}, by="maya")
    rhythm.make_plan(office, TODAY, auto=False, days_ahead=14)
    assert rhythm.due(office, datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)) is None  # the second day of the plan: no post
    assert rhythm.due(office, datetime(2026, 11, 3, 6, 5, tzinfo=timezone.utc)) is None and not rhythm.started(office)


def test_moving_a_day_keeps_its_reason(office):
    days = rhythm.make_plan(office, TODAY, auto=False, days_ahead=2)["days"]
    moved = rhythm.move(office, days[0]["date"], 1, by="maya")["days"]
    assert (moved[1]["ref"], moved[1]["why"]) == (days[0]["ref"], days[0]["why"])


def test_the_plan_buttons_ask_first():
    from pathlib import Path
    page = Path("web/studio.html").read_text(encoding="utf-8")
    assert '$("planbtn").onclick = () => askPlan(' in page and '$("pl-make").onclick = () => askPlan(' in page
    assert "Just today" in page and "a week" in page


def test_a_person_can_put_something_else_on_a_day_and_a_new_plan_keeps_it(office):
    days = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)["days"]
    other = next(x["ref"] for x in rhythm.listings(office) if x["ref"] not in {d["ref"] for d in days})
    d = rhythm.change_day(office, days[1]["date"], other, by="maya")["days"][1]
    assert (d["ref"], d["why"], d["status"]) == (other, "You chose this", "approved")
    again = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)["days"]
    assert again[1]["ref"] == other


def test_a_change_that_can_not_stand_says_why(office):
    days = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)["days"]
    with pytest.raises(rhythm.Invalid, match="already on"):
        rhythm.change_day(office, days[0]["date"], days[1]["ref"], by="maya")
    with pytest.raises(rhythm.Invalid, match="can't post|isn't something"):
        rhythm.change_day(office, days[0]["date"], "NOPE", by="maya")


def test_a_day_with_nothing_on_it_does_not_break_the_page(office):
    from diwan.agents import marketing
    office.log.append("plan.made", actor="maya", agent="plan", content={"rhythm": "daily", "auto": False, "days": [
        {"date": date.today().isoformat(), "ref": None, "why": "", "type": "listing", "status": "pending"}]})
    assert marketing.plan_view(office)["days"][0]["title"] == ""


def test_when_the_strategist_repeats_a_plain_day_no_day_is_blank_or_twice(office, monkeypatch):
    plain = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)["days"]
    strategist(monkeypatch, lambda s: [{"date": plain[0]["date"], "ref": plain[2]["ref"], "why": "It should go first."}])
    days = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3, think=True)["days"]
    refs = [d["ref"] for d in days]
    assert None not in refs and len(set(refs)) == len(refs)


def test_a_shorter_plan_keeps_a_day_approved_further_out(office):
    far = rhythm.make_plan(office, TODAY, auto=False, days_ahead=14)["days"][-1]
    rhythm.decide_day(office, far["date"], "approve", by="maya")
    days = rhythm.make_plan(office, TODAY, auto=False, days_ahead=7)["days"]
    assert days[-1]["date"] == far["date"] and days[-1]["ref"] == far["ref"] and days[-1]["status"] == "approved"


def test_a_removed_post_can_come_back_once_its_date_has_passed(office):
    day = rhythm.make_plan(office, TODAY, auto=False, days_ahead=3)["days"][1]
    rhythm.decide_day(office, day["date"], "reject", by="maya")
    later = date.fromisoformat(day["date"]) + timedelta(days=1)
    assert rhythm.make_plan(office, later, auto=False, days_ahead=2)["removed"] == []


def wins(monkeypatch, **shows):
    from diwan.agents import reader
    monkeypatch.setattr(reader, "winning", lambda o: {"posts": sum(shows.values()), "on_screen": {k.replace("_", " "): v for k, v in shows.items()}, "line": "x"})


def a_topic(office):
    from diwan import topics
    return next(t for t in topics.items(office).values() if not t.get("moment"))


def test_competitors_choose_the_format_of_a_teaching_post(office, monkeypatch):
    from diwan.agents import eventpost, marketing
    wins(monkeypatch, text_on_images=10, a_person_talking_to_camera=7)
    t = a_topic(office)
    assert eventpost.shape(office, t | {"item": "topic"})["format"] == "graphic"
    assert marketing.format_of(office, t["ref"]) == "Graphic"
    assert "10 of 17 winning" in eventpost.suggest(office, t["ref"])["why"]


def test_a_person_stays_when_they_win_or_when_there_is_too_little_to_say(office, monkeypatch):
    from diwan.agents import eventpost, marketing
    t = a_topic(office)
    wins(monkeypatch, text_on_images=2, a_person_talking_to_camera=9)
    assert marketing.format_of(office, t["ref"]) == "Reel, to camera"
    wins(monkeypatch, text_on_images=5, a_person_talking_to_camera=2)  # too few winners
    assert eventpost.shape(office, t | {"item": "topic"}) is None


def test_a_post_about_the_brand_stays_a_person_speaking(office, monkeypatch):
    from diwan.agents import marketing
    wins(monkeypatch, text_on_images=20, a_person_talking_to_camera=1)
    assert marketing.format_of(office, "JOB-why-us") == "Reel, to camera"


def test_real_footage_beats_the_pattern(office, monkeypatch):
    from diwan.agents import eventpost, studio
    wins(monkeypatch, text_on_images=20, a_person_talking_to_camera=1)
    monkeypatch.setattr(studio, "footage", lambda o, r: {"id": "F1"})
    t = a_topic(office)
    assert eventpost.shape(office, t | {"item": "topic"}) is None
