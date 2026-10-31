import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest

from diwan import brand, business, demo, topics
from diwan.agents import marketing, qa, reception, rhythm, strategy, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import ads, instagram, meta


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "no"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, by="maya")
    return o


def stage(o, ref):
    return marketing.pieces(o)[ref]["stage"]


def approve(o, ref):
    studio.run_now(o, ref)
    req = studio.script_request(o, ref)
    sc = studio.script_options(o, req.props["text"])[0]
    studio.approve_script_now(o, ref, choice=sc["id"])
    return sc


def price(o, ref, value):
    o.log.append("listing.added", actor="layla", content={"ref": ref, "price_aed": value})


def ready(o, monkeypatch, ref="MC-1204"):
    """A carousel-free route to a publishable post: the stages a filmed post reaches."""
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://x.example")
    monkeypatch.setattr(instagram, "ready", lambda: True)
    monkeypatch.setattr(instagram, "publish_reel", lambda url, cap: "IG1")
    approve(o, ref)
    studio._made(o, "mcap", "cut", ref, {"path": "x.mp4", "served": "/media/x.mp4", "lines": 3}, None)
    text = studio.made(o, "post text", ref)
    studio.ask_to_publish(o, ref, studio.made(o, "cut", ref), text, studio.schedule(o, None), None)


def test_a_piece_of_content_walks_the_spec_stages(office, monkeypatch):
    studio.run_now(office, "MC-1204")
    assert stage(office, "MC-1204") == "scripted"
    ready(office, monkeypatch)
    assert stage(office, "MC-1204") == "ready"
    assert studio.approve_post(office, "MC-1204", by="layla")["ok"]
    assert stage(office, "MC-1204") == "scheduled"
    assert studio.publish(office, "MC-1204", by="layla")["ok"]
    assert stage(office, "MC-1204") == "live"
    assert marketing.pieces(office)["MC-1204"]["instagram_id"] == "IG1"


def test_every_stage_name_is_the_specs():
    assert marketing.STAGES == ("idea", "briefed", "scripted", "in_production", "ready", "scheduled", "live", "paused", "withdrawn", "archived")


def test_an_automatic_run_waits_for_a_yes_on_the_brief(office):
    asyncio.run(studio.run(office, "MC-1204", pause=0, auto=True))
    assert stage(office, "MC-1204") == "idea" and not studio.made(office, "script", "MC-1204")
    req = [n for n in office.graph().of("request", status="open") if n.props.get("kind") == "approve_brief"]
    assert req and "MC-1204" in req[0].props["text"]
    asyncio.run(studio.after_brief(office, "MC-1204", pause=0))
    assert stage(office, "MC-1204") == "scripted" and studio.made(office, "script", "MC-1204")


def test_the_owner_can_turn_the_brief_gate_off(office):
    rhythm.save(office, {"approve_brief": "off"}, by="layla")
    asyncio.run(studio.run(office, "MC-1204", pause=0, auto=True))
    assert stage(office, "MC-1204") == "scripted"


def test_a_price_change_pauses_a_scheduled_post_and_closes_its_cards(office, monkeypatch):
    ready(office, monkeypatch)
    studio.approve_post(office, "MC-1204", by="layla")
    price(office, "MC-1204", 2_450_000)
    assert marketing.watch(office) == ["MC-1204"]
    assert stage(office, "MC-1204") == "paused" and "MC-1204" not in studio.scheduled(office)
    assert "AED 2,450,000" in marketing.pieces(office)["MC-1204"]["why"]
    assert not [n for n in office.graph().of("request", status="open") if "MC-1204" in n.props.get("text", "") and n.props.get("kind") == "publish"]


def test_a_live_post_that_goes_stale_gives_a_person_the_takedown(office, monkeypatch):
    ready(office, monkeypatch)
    studio.publish(office, "MC-1204", by="layla")
    price(office, "MC-1204", 2_450_000)
    marketing.watch(office)
    assert stage(office, "MC-1204") == "paused"
    assert [t for t in office.graph().of("task") if "Take the MC-1204 post down" in t.props["action"]]


def test_a_stale_post_can_not_be_published(office, monkeypatch):
    ready(office, monkeypatch)
    price(office, "MC-1204", 2_450_000)
    r = studio.publish(office, "MC-1204", by="layla")
    assert not r["ok"] and any("2,450,000" in x for x in r["needs"]) and not studio.made(office, "published", "MC-1204")


def test_a_sold_listing_withdraws_the_post(office, monkeypatch):
    ready(office, monkeypatch)
    office.log.append("listing.added", actor="layla", content={"ref": "MC-1204", "status": "sold"})
    marketing.watch(office)
    assert stage(office, "MC-1204") == "withdrawn"


def test_the_price_put_back_brings_the_post_back_for_a_new_yes(office, monkeypatch):
    ready(office, monkeypatch)
    old = office.graph().nodes["listing:MC-1204"].props["price_aed"]
    price(office, "MC-1204", 1)
    marketing.watch(office)
    price(office, "MC-1204", old)
    marketing.watch(office)
    assert stage(office, "MC-1204") == "ready"
    assert [n for n in office.graph().of("request", status="open") if n.props.get("kind") == "publish" and "MC-1204" in n.props["text"]]


def test_a_permit_warns_then_pauses_on_the_day(office, monkeypatch):
    ready(office, monkeypatch)
    today = marketing._today(office)
    office.log.append("listing.added", actor="layla", content={"ref": "MC-1204", "permit_until": (today + timedelta(days=10)).isoformat()})
    marketing.watch(office)
    assert stage(office, "MC-1204") == "ready"
    assert [e for e in office.log.list() if e["type"] == "notify.sent" and "expires on" in e["content"].get("text", "")]
    later = datetime.now(timezone.utc) + timedelta(days=11)
    marketing.watch(office, later)
    assert stage(office, "MC-1204") == "paused" and "expired" in marketing.pieces(office)["MC-1204"]["why"]


def test_a_new_listing_is_suggested_and_nothing_is_written(office):
    office.log.append("listing.added", actor="layla", content={"ref": "NEW-1", "title": "Unit 9, Creek Tower", "community": "Dubai Creek", "type": "apartment", "beds": 2, "price_aed": 1500000, "permit": "P-9", "status": "available", "features": []})
    assert [x["ref"] for x in marketing.waiting_ideas(office)] == ["NEW-1"]
    assert "NEW-1" not in marketing.pieces(office)


def test_each_post_gets_its_own_code_word_in_the_caption(office):
    approve(office, "MC-1204")
    text = studio.made(office, "post text", "MC-1204")
    assert text["code"] == "MARINA" and "Say MARINA." in text["text"]
    assert marketing.code_for(office, "MC-1204") == "MARINA"
    office.log.append("listing.added", actor="layla", content={"ref": "MG-2", "title": "Unit 7, Marina Heights", "community": "Dubai Marina", "type": "apartment", "beds": 1, "price_aed": 900000, "permit": "P", "status": "available", "features": []})
    assert marketing.code_for(office, "MG-2") == "MARINA2"


def test_a_lead_that_says_the_code_is_traced_to_the_post(office):
    approve(office, "MC-1204")
    reception.receive(office, "+971500000123", "hi, MARINA please", name_="Sara")
    assert marketing.attribute(office) == 1 and marketing.attribute(office) == 0
    [row] = [r for r in marketing.results(office) if r["ref"] == "MC-1204"]
    assert row["leads"] == 1 and row["angle"]


def test_the_first_source_wins(office):
    approve(office, "MC-1204")
    reception.receive(office, "+971500000124", "MARINA", name_="Sara")
    marketing.attribute(office)
    reception.receive(office, "+971500000124", "MARINA again", name_="Sara")
    assert marketing.attribute(office) == 0


def test_a_comment_keeps_its_post(office, monkeypatch):
    ready(office, monkeypatch)
    studio.publish(office, "MC-1204", by="layla")
    reception.receive(office, "ig:sara", "how much?", name_="@sara")
    marketing.comment(office, "ig:sara", "IG1")
    [row] = [r for r in marketing.results(office) if r["ref"] == "MC-1204"]
    assert row["leads"] == 1
    assert [e for e in office.log.list() if e["type"] == "lead.attributed"][0]["content"]["via"] == "comment"


def test_results_count_what_a_post_brought_through_to_commission(office):
    approve(office, "MC-1204")
    got = reception.receive(office, "+971500000125", "MARINA", name_="Sara")
    marketing.attribute(office)
    office.log.append("qualify.passed", actor="rania", deal=got["deal"], content={})
    office.log.append("appointment.booked", actor="rania", deal=got["deal"], content={"id": "V9", "broker": "omar", "listing": "MC-1204", "chat": "+971500000125", "start": "2026-11-05T10:00:00+04:00",
                                                                                      "end": "2026-11-05T11:00:00+04:00", "at": "2026-11-05T10:00:00+04:00", "kind": "viewing", "customer": "Sara"})
    office.close_sale(listing="MC-1204", price_aed=2_600_000, commission_aed=52_000, broker="omar", date="2026-10-30", deal=got["deal"])
    [row] = [r for r in marketing.results(office) if r["ref"] == "MC-1204"]
    assert (row["leads"], row["qualified"], row["viewings"], row["deals"], row["commission_aed"]) == (1, 1, 1, 1, 52_000)
    assert "AED 52,000 commission" in marketing.weekly(office)["lines"][0]


def test_angles_that_bring_leads_rank_first(office):
    for i, a in enumerate(("walkthrough", "lifestyle")):
        for k in range(3):
            office.log.append("post.seen", actor="mrival", agent="mrival", content={"id": f"{a}{k}", "source": "own", "account": "us", "likes": 100, "comments": 0, "engagement": 100,
                                                                                     "caption": "step inside this tour" if a == "walkthrough" else "imagine your morning", "at": f"2026-10-{10 + k}T10:00:00+0000"})
    office.log.append("lead.attributed", actor="mkt", agent="mkt", deal="d", content={"ref": "x", "angle": "lifestyle", "via": "code word"})
    r = {x["angle"]: x for x in strategy.report(office)["angles"]}
    assert r["lifestyle"]["leads"] == 1 and strategy.pick(office, 2)[0]["angle"] == "lifestyle"


def test_the_day_has_a_morning_list_and_says_it_once(office):
    studio.run_now(office, "MC-1204")
    m = marketing.morning(office)
    assert m["to_approve"] and m["need_content"]
    noon = datetime(2026, 11, 2, 9, 30, tzinfo=timezone.utc)  # a Monday, 13:30 in Dubai
    marketing.tick(office, noon)
    marketing.tick(office, noon)
    sent = [e["content"]["text"] for e in office.log.list() if e["type"] == "notify.sent"]
    assert sum("Marketing today" in t for t in sent) == 1 and sum("This week's marketing" in t for t in sent) == 1


def test_auto_posting_is_off_until_the_owner_turns_it_on(office, monkeypatch):
    ready(office, monkeypatch)
    soon = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    studio.approve_post(office, "MC-1204", by="layla", at=soon)
    office.log.append("content.made", actor="mpub", agent="mpub", content={**studio.scheduled(office)["MC-1204"], "id": "S9", "at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()})
    assert studio.publish_due(office) == [] and "MC-1204" in studio.scheduled(office)
    assert [e for e in office.log.list() if e["type"] == "notify.sent" and "time to post" in e["content"].get("text", "")]
    rhythm.save(office, {"auto_post": "on"}, by="layla")
    assert studio.publish_due(office) == ["MC-1204"]


def test_a_person_can_choose_the_time_but_not_one_gone_by(office, monkeypatch):
    ready(office, monkeypatch)
    assert not studio.approve_post(office, "MC-1204", by="layla", at="2020-01-01T10:00")["ok"]
    assert not studio.approve_post(office, "MC-1204", by="layla", at="soon")["ok"]
    at = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    assert studio.approve_post(office, "MC-1204", by="layla", at=at)["ok"]
    assert studio.scheduled(office)["MC-1204"]["at"].startswith(at)


def test_visa_and_price_promises_go_back():
    import re
    for line in ("Buy now and get your golden visa", "Prices will go up", "Free visa with every unit"):
        assert re.search(qa.BANNED, line, re.I)
    assert not re.search(qa.BANNED, "The minimum value for the golden visa changed this week")


def test_a_campaign_needs_a_cap_and_stays_inside_it(office):
    approve(office, "MC-1204")
    v = {"goal": "Viewings", "audience": "First-time buyers", "budget": 500, "days": 7}
    with pytest.raises(ValueError, match="monthly ad budget"):
        marketing.draft(office, "MC-1204", v, by="maya")
    rhythm.save(office, {"ad_budget": "800"}, by="layla")
    c = marketing.draft(office, "MC-1204", v, by="maya")
    assert "Say MARINA." in c["copy"]
    with pytest.raises(ValueError, match="over the monthly cap"):
        marketing.draft(office, "MC-1204", v, by="maya")


def test_a_campaign_is_launched_by_a_person_and_costs_are_flagged(office, monkeypatch):
    approve(office, "MC-1204")
    rhythm.save(office, {"ad_budget": "800", "cpl_limit": "100"}, by="layla")
    c = marketing.draft(office, "MC-1204", {"goal": "Viewings", "audience": "Buyers", "budget": 500, "days": 7}, by="maya")
    with pytest.raises(ValueError, match="id"):
        marketing.start(office, c["id"], ad_id=" ", by="maya")
    marketing.start(office, c["id"], ad_id="AD1", by="maya")
    got = reception.receive(office, "+971500000126", "MARINA", name_="Sara")
    marketing.attribute(office)
    office.log.append("qualify.passed", actor="rania", deal=got["deal"], content={})
    monkeypatch.setattr(ads, "ready", lambda: True)
    monkeypatch.setattr(ads, "report", lambda: {"ads": [{"id": "AD1", "spend": "350"}]})
    [row] = marketing.campaign_report(office, spend=True)
    assert row["state"] == "running" and row["qualified"] == 1 and row["cost_per_qualified"] == 350 and row["over_limit"]
    marketing.end(office, c["id"], by="maya")
    assert marketing.campaigns(office)[0]["state"] == "ended"


def test_a_passed_moment_is_withdrawn(office, tmp_path):
    ref = topics.save_moment(office, {"title": "Short lived", "what": "Something happened that mattered for a while this week.", "until": "2099-01-01"}, by="maya")
    studio.run_now(office, ref)
    office.log.append("topic.saved", actor="maya", content={"ref": ref, "until": "2020-01-01"})
    marketing.watch(office)
    assert stage(office, ref) == "withdrawn"


def test_the_overview_has_every_block(office):
    studio.run_now(office, "MC-1204")
    o = marketing.overview(office)
    assert [s["id"] for s in o["stages"]] == list(marketing.STAGES) and o["pieces"][0]["ref"] == "MC-1204"
    assert set(o) >= {"results", "morning", "evening", "weekly", "ideas", "campaigns", "cap", "settings"}


def test_a_failed_own_script_can_not_be_picked_on_the_page(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from diwan import app as appmod
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    with TestClient(appmod.app) as c:
        o = appmod.S.office
        studio.own_script(o, "MC-1204", "Guaranteed returns here\\nOne\\nTwo".replace("\\n", "\n"), by="maya")
        req = studio.script_request(o, "MC-1204")
        own = next(x for x in studio.script_options(o, req.props["text"]) if x.get("problems"))
        r = c.post(f"/api/requests/{req.id}/decide", json={"decision": "approve", "by": "maya", "choice": own["id"]}).json()
        assert not r["ok"] and r["needs"]


def test_marketing_reaches_its_new_screens_and_a_broker_does_not():
    from diwan import access
    for path, how in (("/api/marketing/overview", "GET"), ("/api/marketing/campaigns", "POST"), ("/api/studio/post-now", "POST"), ("/api/moments", "POST"), ("/api/studio/unschedule", "POST")):
        assert access.may_call("maya", how, path), path
        assert not access.may_call("omar", how, path), path


def test_the_setup_form_loads_every_switch_as_a_tick():
    from pathlib import Path
    page = (Path(__file__).parent.parent / "web/studio.html").read_text(encoding="utf-8")
    assert 'RH_SWITCH = ["auto", "refresh", "auto_post", "approve_brief"]' in page and "RH_SWITCH.includes(k)) $(id).checked" in page


def test_a_long_spoken_turn_becomes_short_captions_in_order():
    rows = studio._short([{"start": 0.0, "end": 12.0, "text": " ".join(f"w{i}" for i in range(12))}])
    assert len(rows) == 2 and all(len(r["text"].split()) <= studio.CAPTION_WORDS for r in rows)
    assert rows[0]["start"] == 0 and rows[1]["start"] == 6 and rows[1]["end"] == 12


def test_a_free_video_is_captioned_with_the_scripts_own_words(office, tmp_path, monkeypatch):
    approve(office, "MC-1204")
    src = tmp_path / "take.mp4"
    src.write_bytes(b"x")
    office.log.append("footage.added", actor="maya", agent="mvideo", content={"id": "F1", "ref": "MC-1204", "path": str(src), "served": "/media/take.mp4", "source": "free video",
                                                                              "lines": [{"start": 0, "end": 3, "text": "We are Diwan Realty"}]})
    monkeypatch.setattr(studio, "_duration", lambda p: 3.0)
    monkeypatch.setattr(studio, "_width", lambda p: 1080)
    monkeypatch.setattr(studio, "_ffmpeg", lambda *a: None)
    cut = studio.captions(office, "MC-1204", {"said": "We are Devon Realty", "turns": []}, None)
    assert cut["from"] == "the script, timed to the voice"
    assert "Diwan" in src.with_suffix(".srt").read_text() and "Devon" not in src.with_suffix(".srt").read_text()


def test_captions_are_large_enough_to_read_on_a_phone(tmp_path):
    from PIL import Image
    p = tmp_path / "c.png"
    studio._caption_png("We are Diwan Realty", p, 1080)
    img = Image.open(p)
    assert img.getbbox() and img.getbbox()[3] - img.getbbox()[1] >= 60 and img.height >= 90


def week(o, n=7):
    return rhythm.make_plan(o, marketing._today(o), auto=False, days_ahead=n)


def test_a_plan_can_be_made_for_any_number_of_days(office):
    assert len(week(office)["days"]) == 7
    assert len(week(office, 31)["days"]) == 31
    assert all(d["status"] == "pending" for d in rhythm.current(office)["days"])


def test_the_plan_shows_each_day_with_its_format_and_reason(office):
    business.save(office, {"posted_before": "no"}, by="maya")
    week(office)
    v = marketing.plan_view(office)
    assert len(v["days"]) == 7 and v["days"][0]["title"] == "Meet Diwan Realty" and v["days"][0]["format"] == "Reel, to camera" and v["days"][0]["state"] == "pending" and v["days"][0]["why"]


def test_approved_stays_on_its_day_and_needs_no_second_yes(office):
    p = week(office)
    day, ref = p["days"][0]["date"], p["days"][0]["ref"]
    rhythm.decide_day(office, day, "approve", by="maya")
    v = marketing.plan_view(office)["days"][0]
    assert v["state"] == "approved" and v["ref"] == ref and rhythm.approved(office, ref)


def test_rejected_comes_off_and_the_day_takes_the_next_best(office):
    p = week(office)
    day, ref = p["days"][1]["date"], p["days"][1]["ref"]
    rhythm.decide_day(office, day, "reject", by="maya")
    v = marketing.plan_view(office)
    assert v["days"][1]["ref"] != ref and v["days"][1]["state"] == "pending"
    assert [r["date"] for r in v["removed"]] == [day]
    assert len({d["ref"] for d in v["days"] if d["ref"]}) == len([d for d in v["days"] if d["ref"]])


def test_everything_waiting_is_in_one_list(office, monkeypatch):
    studio.run_now(office, "MC-1204")
    other = next(y["ref"] for y in rhythm.listings(office) if y["ref"] != "MC-1204")
    asyncio.run(studio.run(office, other, pause=0, auto=True))
    kinds = {w["kind"]: w for w in marketing.waiting(office)}
    assert kinds["use_script"]["ref"] == "MC-1204" and kinds["approve_brief"]["ref"] == other


def test_a_rejected_post_on_the_page_comes_off_every_list(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from diwan import app as appmod
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    with TestClient(appmod.app) as c:
        o = appmod.S.office
        other = next(y["ref"] for y in rhythm.listings(o) if y["ref"] != "MC-1204")
        asyncio.run(studio.run(o, other, pause=0, auto=True))
        w = next(x for x in marketing.waiting(o) if x["ref"] == other)
        assert c.post(f"/api/requests/{w['id']}/decide", json={"decision": "reject", "by": "maya"}).json()["ok"]
        assert not [x for x in marketing.waiting(o) if x["ref"] == other] and stage(o, other) == "withdrawn"
        assert [x for x in marketing.plan_view(o)["stopped"] if x["ref"] == other]


def test_a_day_that_started_can_not_be_changed(office):
    p = week(office)
    day = p["days"][0]["date"]
    assert rhythm.start_day(office, day, by="maya") == p["days"][0]["ref"]
    with pytest.raises(rhythm.Invalid):
        rhythm.decide_day(office, day, "reject", by="maya")
    with pytest.raises(rhythm.Invalid):
        rhythm.start_day(office, day, by="maya")


def test_a_line_is_read_the_way_a_person_says_it():
    from diwan.agents import freevideo
    assert freevideo.spoken("Permit number is SAMPLE-71204.") == ""
    assert freevideo.spoken("It is AED 2,600,000. Permit SAMPLE-71204. Message us.") == "It is 2.6 million dirhams. Message us."
    assert freevideo.spoken("A 2-bed for AED 950,000") == "A 2 bedroom for 950 thousand dirhams"


def test_planning_words_never_reach_the_viewer(office):
    check = next(c for c in qa.CHECKS["script"] if c.id == "script-natural")
    assert not check.test(office, "MC-1204", {"hook_en": "2-bed sea view: investor facts first.", "lines_en": []})[0]
    assert check.test(office, "MC-1204", {"hook_en": "Would you wake up to this view?", "lines_en": []})[0]


def test_a_floor_nobody_gave_is_a_made_up_claim():
    from diwan.agents import qa
    assert [m.group(1) for m in qa.CLAIM.finditer("You are on the 12th floor, 15 years of trust, 3-storey villa")] == ["12", "15", "3"]
    assert not qa.CLAIM.search("One bedroom on a high floor")
