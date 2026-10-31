import asyncio
import random
from pathlib import Path

import pytest
from PIL import Image, ImageEnhance, ImageFilter

from diwan import brand, business, demo, topics
from diwan.agents import eventpost, journey, qa, rhythm, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import instagram, meta


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "no"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, by="maya")
    return o


def picture(folder, name, *, blur=False, dark=False, size=(1200, 900)):
    r = random.Random(name)
    img = Image.new("RGB", (60, 45))
    img.putdata([(r.randint(0, 80), r.randint(0, 80), r.randint(0, 80)) if dark else (r.randint(40, 255), r.randint(40, 255), r.randint(40, 255)) for _ in range(60 * 45)])
    img = img.resize(size, Image.NEAREST)
    if blur:
        img = img.resize(size, Image.BICUBIC).filter(ImageFilter.GaussianBlur(40))
    path = folder / name
    img.save(path, "JPEG")
    return str(path)


def moment(o, folder, n=0, **kw):
    ref = topics.save_moment(o, {"title": "Cityscape Global stand", "what": "We showed three new towers at Cityscape Global this week, and met buyers at our stand."}, by="maya")
    paths = [picture(folder, f"p{i}.jpg", **kw) for i in range(n)]
    if paths:
        o.log.append("photos.added", actor="maya", content={"ref": ref, "paths": paths})
    return ref


def approve(o, ref):
    studio.run_now(o, ref)
    req = studio.script_request(o, ref)
    sc = studio.script_options(o, req.props["text"])[0]
    studio.approve_script_now(o, ref, choice=sc["id"])
    return sc


@pytest.mark.parametrize("n,fmt", [(0, "graphic"), (1, "image"), (3, "image"), (4, "carousel"), (9, "carousel")])
def test_the_format_follows_what_exists(office, tmp_path, n, fmt):
    s = eventpost.suggest(office, moment(office, tmp_path, n))
    assert s["format"] == fmt and s["usable"] == n and s["why"]


def test_a_clip_makes_it_a_reel(office, tmp_path, monkeypatch):
    ref = moment(office, tmp_path, 5)
    monkeypatch.setattr(studio, "footage", lambda o, r: {"id": "F1"})
    assert eventpost.suggest(office, ref)["format"] == "reel"


def test_reels_win_only_on_our_own_numbers(office, tmp_path):
    ref = moment(office, tmp_path, 5)
    for i in range(6):
        office.log.append("post.seen", actor="mrival", agent="mrival", content={"id": f"o{i}", "source": "own", "account": "us", "type": "REELS" if i < 3 else "IMAGE", "likes": 300 if i < 3 else 100, "comments": 0, "engagement": 300 if i < 3 else 100})
    s = eventpost.suggest(office, ref)
    assert s["format"] == "reel" and "300" in s["why"]


def test_poor_photos_are_set_aside_and_say_why(office, tmp_path):
    ref = topics.save_moment(office, {"title": "Our stand", "what": "We met buyers at our stand this week at the show."}, by="maya")
    real = Image.open(Path(__file__).parent.parent / "web/img/demo/creek.jpg").convert("RGB")  # measured on a real photograph
    real.filter(ImageFilter.GaussianBlur(real.width / 170)).save(tmp_path / "b.jpg")
    ImageEnhance.Brightness(real).enhance(.15).save(tmp_path / "d.jpg")
    paths = [str(tmp_path / "b.jpg"), str(tmp_path / "d.jpg"), picture(tmp_path, "s.jpg", size=(300, 200)), str(tmp_path / "gone.jpg")]
    office.log.append("photos.added", actor="maya", content={"ref": ref, "paths": paths})
    s = eventpost.suggest(office, ref)
    assert s["usable"] == 0 and s["format"] == "graphic" and len(s["unusable"]) == 4
    assert any("blurred" in x for x in s["unusable"]) and any("too dark" in x for x in s["unusable"]) and any("too small" in x for x in s["unusable"])


def test_a_person_can_change_the_format_but_not_to_one_with_no_photos(office, tmp_path):
    ref = moment(office, tmp_path, 5)
    eventpost.choose(office, ref, "image", by="maya")
    s = eventpost.suggest(office, ref)
    assert s["format"] == "image" and "you chose" in s["why"]
    empty = topics.save_moment(office, {"title": "No photos here", "what": "Something happened and we have no pictures of it."}, by="maya")
    with pytest.raises(ValueError, match="photo"):
        eventpost.choose(office, empty, "carousel", by="maya")


def test_a_carousel_goes_from_photos_to_real_images_and_a_publish_request(office, tmp_path):
    ref = moment(office, tmp_path, 5)
    sc = approve(office, ref)
    assert sc["format"] == "carousel" and len(sc["slides"]) == 5 and not sc["shots"]
    assert sc["slides"][-1]["text"] == sc["lines_en"][-1]  # the call to action stays last
    assert len({s["photo"] for s in sc["slides"]}) == 5  # a photo is used once
    pics = studio.made(office, "slides", ref)
    assert len(pics["images"]) == 5 and all(Image.open(x["path"]).size == (1080, 1350) for x in pics["images"])
    assert not studio.made(office, "film list", ref)  # nothing to film
    text = studio.made(office, "post text", ref)["text"]
    assert sc["lines_en"][0] in text
    req = [n for n in office.graph().of("request", status="open") if n.props.get("agent") == "mpub"]
    assert req and f"Publish the {ref} carousel" in req[0].props["text"]
    assert [c["step"] for c in studio.chain(office, ref)][1] == "Make the images"


def test_the_words_are_on_the_photo_and_a_real_photo_is_not_replaced(office, tmp_path):
    ref = moment(office, tmp_path, 1)
    approve(office, ref)
    x = studio.made(office, "slides", ref)["images"][0]
    img = Image.open(x["path"]).convert("RGB")
    band = img.crop((100, 1250, 900, 1340)).resize((1, 1)).getpixel((0, 0))
    photo = img.crop((100, 300, 900, 600)).resize((1, 1)).getpixel((0, 0))
    assert sum(band) < sum(photo)  # the band is dark, the photo above it untouched


def test_a_graphic_without_a_model_is_plain_and_says_so(office, tmp_path):
    ref = moment(office, tmp_path, 0)
    approve(office, ref)
    assert studio.made(office, "slides", ref)["background"] == "plain"


def test_a_generated_background_is_asked_for_with_nothing_real_in_it(office, tmp_path, monkeypatch):
    seen = {}

    def fake(prompt, name, size):
        seen["p"] = prompt
        meta.MEDIA.mkdir(exist_ok=True)
        Image.new("RGB", (1024, 1792), (30, 30, 60)).save(meta.MEDIA / "bg.webp")
        return "/media/bg.webp"
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(meta, "image", fake)
    img, by = eventpost._background(office, "X")
    assert by == "Muse Image" and img.size == (1080, 1350) and all(w in seen["p"] for w in ("no text", "people", "buildings"))


def test_people_in_the_photos_are_flagged_for_the_person_who_approves(office, tmp_path, monkeypatch):
    ref = moment(office, tmp_path, 4)
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(meta, "look", lambda *a, **k: {"photos": [{"n": i, "what": f"a stand {i}", "people": i == 1, "strength": 5 - i} for i in range(1, 5)]})
    monkeypatch.setattr(meta, "search", lambda *a, **k: {"text": "", "sources": [], "cited": [], "queries": 1})
    eventpost.read(office, ref, None)
    assert eventpost.photos(office, ref)[0]["what"] == "a stand 1"
    monkeypatch.setattr(meta, "ready", lambda: False)
    approve(office, ref)
    assert studio.made(office, "slides", ref)["people"] == 1
    req = [n for n in office.graph().of("request", status="open") if n.props.get("agent") == "mpub"]
    assert "check they agreed" in req[0].props["text"]


def test_the_event_search_runs_once_and_keeps_only_pages_it_opened(office, tmp_path, monkeypatch):
    ref = moment(office, tmp_path, 1)
    calls = []
    answer = "1. Show the stand | People trust real moments | https://a.example/x\n2. Made up | No page | https://never-opened.example/y"

    def search(prompt, **k):
        calls.append(prompt)
        return {"text": answer, "sources": [{"url": "https://a.example/x"}], "cited": [], "queries": 1}
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(meta, "search", search)
    assert [c["url"] for c in eventpost.search(office, ref, None)] == ["https://a.example/x"]
    assert eventpost.search(office, ref, None) == [] and len(calls) == 1 and "Cityscape" in calls[0]


def test_publishing_a_carousel_and_an_image_use_their_own_calls(office, tmp_path, monkeypatch):
    posted = {}
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://x.example")
    monkeypatch.setattr(instagram, "ready", lambda: True)
    monkeypatch.setattr(instagram, "publish_carousel", lambda urls, cap: posted.update(c=urls) or "1")
    monkeypatch.setattr(instagram, "publish_image", lambda url, cap: posted.update(i=url) or "2")
    two, one = moment(office, tmp_path, 4), None
    approve(office, two)
    assert studio.publish(office, two, by="layla")["ok"] and len(posted["c"]) == 4 and posted["c"][0].startswith("https://x.example/media/post-")
    one = topics.save_moment(office, {"title": "One photo day", "what": "We opened a new office in the Marina this week for buyers."}, by="maya")
    office.log.append("photos.added", actor="maya", content={"ref": one, "paths": [picture(tmp_path, "one.jpg")]})
    approve(office, one)
    assert studio.publish(office, one, by="layla")["ok"] and posted["i"].endswith(".jpg")


def test_without_a_public_address_it_says_what_is_missing(office, tmp_path):
    ref = moment(office, tmp_path, 4)
    approve(office, ref)
    r = studio.publish(office, ref, by="layla")
    assert not r["ok"] and any("PUBLIC_BASE_URL" in x for x in r["needs"]) and not studio.made(office, "published", ref)


def test_a_change_to_the_finished_post_goes_to_whoever_can_fix_it():
    pics, reel = {"slides": [{}]}, {"slides": None}
    assert studio.change_goes_to(pics, "shorter caption and fewer hashtags") == "mwriter"
    assert studio.change_goes_to(reel, "the caption is too long") == "mwriter"
    assert studio.change_goes_to(reel, "the lighting is bad, film it again") == "mshoot"
    assert studio.change_goes_to(pics, "the video feels wrong") == "mscript"  # nothing to film in a carousel
    assert studio.change_goes_to(pics, "use a different first photo") == "mscript"


def test_a_change_to_the_words_comes_back_for_a_new_pick_and_new_images(office, tmp_path):
    ref = moment(office, tmp_path, 4)
    first = approve(office, ref)
    asyncio.run(studio.change_post(office, ref, "make the hook shorter", pause=0))
    req = studio.script_request(office, ref)
    new = studio.script_options(office, req.props["text"])[0]
    assert new["revises"] == first["id"]
    studio.approve_script_now(office, ref, choice=new["id"])
    assert studio.made(office, "slides", ref)["images"][0]["served"].find(new["id"]) > 0


def test_a_caption_change_without_a_model_keeps_the_post_and_says_so(office, tmp_path):
    ref = moment(office, tmp_path, 4)
    approve(office, ref)
    before = studio.made(office, "post text", ref)["text"]
    asyncio.run(studio.change_post(office, ref, "shorter caption", pause=0))
    assert studio.made(office, "post text", ref)["text"] == before
    assert any(e["type"] == "step.blocked" and "unchanged" in e["content"]["needs"] for e in office.log.list())
    assert [n for n in office.graph().of("request", status="open") if n.props.get("agent") == "mpub"]  # still waiting for a person


def test_the_panel_shows_the_format_of_the_moment(office, tmp_path):
    moment(office, tmp_path, 5)
    r = journey.report(office)
    assert r["shape"]["format"] == "carousel" and r["next"]["job"] == "moment"


def test_a_broken_image_is_caught_by_the_review(office, tmp_path):
    bad = {"images": [{"path": str(tmp_path / "gone.jpg"), "served": "/media/gone.jpg"}]}
    fails = [c for c in qa.CHECKS["slides"] if not c.test(office, "X", bad)[0]]
    assert [c.id for c in fails] == ["slides-exist"]


def test_a_timeout_is_a_failure_to_report_not_a_crash(monkeypatch):
    import httpx

    class Slow:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(meta, "_client", lambda timeout: Slow())
    with pytest.raises(meta.MetaError, match="did not answer"):
        meta._send("/chat/completions", {}, 1)


def test_a_failed_batch_keeps_what_was_read_and_the_next_run_goes_on(office, monkeypatch):
    from diwan.agents import reader
    office.log.append("setting.changed", actor="maya", content={"person": "studio", "key": "competitors", "value": "rival"})
    for i in range(14):
        office.log.append("post.seen", actor="mrival", agent="mrival", content={"id": f"r{i}", "source": "competitor", "account": "rival", "type": "REELS", "likes": 100 + i * 50, "comments": 0,
                                                                                 "caption": f"post {i}", "at": "2026-10-20T10:00:00+0000"})
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(reader, "_cover", lambda u: None)
    calls = []

    def look(system, text, images, schema, **k):
        calls.append(text)
        if len(calls) == 2:
            raise meta.MetaError("timed out")
        n = text.count("[REELS")
        return {"topics": [], "posts": [{"n": i, "topic": "a tour", "hook": "a question", "on_screen": "a walkthrough or tour", "asks": "nothing", "tone": "warm", "offer": "no offer",
                                         "seasonal": "", "carries_over": True, "why_not": ""} for i in range(n)]}
    monkeypatch.setattr(meta, "look", look)
    first = reader.read(office)
    assert first["read"] == reader.BATCH and first["errors"] and len(calls) == 2  # stopped at the failure, the first batch kept
    assert "r13" in reader.reads(office) and "post 13" in calls[0]  # the strongest were read first
    assert reader.read(office)["read"] == 14 - reader.BATCH


def ready_to_post(o, folder, monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://x.example")
    monkeypatch.setattr(instagram, "ready", lambda: True)
    rhythm.save(o, {"auto_post": "on"}, by="layla")
    ref = moment(o, folder, 4)
    approve(o, ref)
    return ref


def test_an_approved_post_waits_for_its_time_and_goes_out_once(office, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    posted = []
    monkeypatch.setattr(instagram, "publish_carousel", lambda urls, cap: posted.append(urls) or "7")
    ref = ready_to_post(office, tmp_path, monkeypatch)
    assert studio.approve_post(office, ref, by="layla")["ok"] and not posted
    assert studio.publish_due(office) == [] and ref in studio.scheduled(office)  # the time has not come
    office.log.append("content.made", actor="mpub", agent="mpub", content={**studio.scheduled(office)[ref], "id": "S2", "at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()})
    assert studio.publish_due(office) == [ref] and len(posted) == 1
    assert ref not in studio.scheduled(office) and studio.publish_due(office) == [] and len(posted) == 1


def test_a_scheduled_post_can_be_cancelled(office, tmp_path, monkeypatch):
    ref = ready_to_post(office, tmp_path, monkeypatch)
    studio.approve_post(office, ref, by="layla")
    studio.unschedule(office, ref, by="maya")
    assert ref not in studio.scheduled(office) and studio.chain(office, ref)[-1]["state"] != "done"


def test_a_failed_post_is_said_once_and_not_retried_for_ever(office, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    ref = ready_to_post(office, tmp_path, monkeypatch)
    calls = []

    def refuse(urls, cap):
        calls.append(1)
        raise instagram.InstagramError("no")
    monkeypatch.setattr(instagram, "publish_carousel", refuse)
    studio.approve_post(office, ref, by="layla")
    office.log.append("content.made", actor="mpub", agent="mpub", content={**studio.scheduled(office)[ref], "id": "S2", "at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()})
    studio.publish_due(office)
    studio.publish_due(office)
    assert len(calls) == 1 and ref not in studio.scheduled(office)


def test_only_the_person_named_or_the_owner_can_approve(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from diwan import app as appmod
    from diwan.agents import approvers
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    with TestClient(appmod.app) as c:
        o = appmod.S.office
        business.save(o, {"industry": "Real estate brokerage", "country": "AE"}, by="maya")
        approvers.save(o, {"publish": "maya"}, by="layla")
        o.log.append("approval.requested", actor="mpub", agent="mpub", content={"id": "R900", "kind": "publish", "text": "Publish the MC-1204 reel Sat 7:30 PM", "reviewer": "x"}) if False else None
        studio._pack(o, "mpub", "Publish the MC-1204 reel Sat 7:30 PM", kind="publish")
        req = [n for n in o.graph().of("request", status="open") if n.props.get("agent") == "mpub"][-1]
        assert c.post(f"/api/requests/{req.id}/decide", json={"decision": "approve", "by": "omar"}).status_code == 403
        assert c.post(f"/api/requests/{req.id}/decide", json={"decision": "approve", "by": "maya"}).status_code == 200


def test_internal_notes_never_pass_as_a_post(office, tmp_path):
    ref = moment(office, tmp_path, 1)
    check = next(c for c in qa.CHECKS["post text"] if c.id == "post-no-notes")
    assert not check.test(office, ref, {"text": "verdict: Hold the post unchanged\nevidence:\n- post"})[0]
    assert check.test(office, ref, {"text": "We met buyers at our stand. Next week we are back."})[0]


def test_the_rewriter_is_not_asked_for_the_internal_format(office, tmp_path, monkeypatch):
    ref = moment(office, tmp_path, 4)
    approve(office, ref)
    seen = {}
    monkeypatch.setattr(studio.runner, "has_model", lambda c, s, u, schema=None: seen.update(s=s) or False)
    studio.rewrite_caption(office, ref, "shorter", None)
    assert "agent_pack" not in seen["s"]


def test_housekeeping_stays_out_of_every_post(office):
    facts = " ".join(journey.company(office, k=50))
    assert "About us" in facts and not any(w in facts for w in ("2%", "10am", "photo ID"))


def test_a_moment_is_told_not_to_invent_a_story(office, tmp_path):
    ref = moment(office, tmp_path, 1)
    assert "Never invent a memory" in journey.brief(office, studio._listing(office, ref))


@pytest.mark.parametrize("line", ["I thought the golden visa was out of reach", "I assumed it was not for me", "I kept seeing people commit too early",
                                  "Most first-time buyers think it's just the price", "We never thought this would happen"])
def test_a_made_up_memory_or_belief_goes_back(office, tmp_path, line):
    assert qa._made_up(office, moment(office, tmp_path, 0), line)


def test_a_plain_fact_passes_and_a_listing_may_paint_a_morning(office, tmp_path):
    assert not qa._made_up(office, moment(office, tmp_path, 0), "The minimum property value changed this week. We think this helps buyers?".split("We")[0])
    assert not qa._made_up(office, "MC-1204", "Mornings start on the balcony. I thought you would like it.")


def test_a_moment_has_its_own_angles_and_no_common_belief(office, tmp_path):
    ref = moment(office, tmp_path, 0)
    studio.run_now(office, ref)
    idea = studio.made(office, "ideas", ref)
    picks = {s["angle"] for s in studio.variants(office, ref, idea, None, None)}
    assert picks <= set(journey.JOBS["moment"]["angles"]) and "myth-vs-fact" not in picks
