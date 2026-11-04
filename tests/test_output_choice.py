"""After a script is picked, the person chooses how the post goes out: pictures (a carousel from the script's own
frame-by-frame brief), a voice-over (the free video: the computer's voice over the frames) or a video (filmed, or the AI
presenter). Code suggests one, with a reason. Only paths that already exist; voice and video are off where the server
can't make video safely. Nothing posts without the publish approver."""
import threading
import time

import pytest
from PIL import Image

from diwan.agents import eventpost, marketing, studio
from diwan.app import app  # noqa: F401  the routes are registered

from .test_eventpost import approve, greeting, moment, office, picture  # noqa: F401  the same studio office and helpers

REF = "MC-1204"


def photos_of(o, folder, n=5):
    paths = [picture(folder, f"l{i}.jpg") for i in range(n)]
    o.log.append("photos.added", actor="maya", content={"ref": REF, "paths": paths})
    return paths


def listing_video(o, folder, n=5):
    """Marina Crest, written as a reel (the person chose a reel), then picked."""
    paths = photos_of(o, folder, n)
    eventpost.choose(o, REF, "reel", by="maya")
    sc = approve(o, REF)
    assert not sc.get("slides") and sc.get("shots"), "the picked script is a video script"
    return sc, paths


def as_pictures(o):
    return studio.choose_output_now(o, REF, "pictures", by="maya")


# 1. the suggestion, decided by code
def test_a_listing_with_good_photos_is_suggested_as_pictures(office, tmp_path, monkeypatch):
    monkeypatch.delenv("DIWAN_VIDEO", raising=False)
    photos_of(office, tmp_path, 5)
    s = studio.suggest_output(office, REF)
    assert s["pick"] == "pictures" and "photos" in s["why"]


def test_meet_diwan_realty_is_suggested_as_a_voice_or_a_video(office, monkeypatch):
    monkeypatch.delenv("DIWAN_VIDEO", raising=False)
    monkeypatch.setattr(studio, "_can_render", lambda: (True, True, ""))
    s = studio.suggest_output(office, "JOB-introduce")
    assert s["pick"] in ("voice", "video") and "people" in s["why"].lower()


def test_a_greeting_is_suggested_as_pictures(office, tmp_path):
    s = studio.suggest_output(office, greeting(office, tmp_path))
    assert s["pick"] == "pictures" and "greeting" in s["why"].lower()


def test_a_server_that_cannot_make_video_never_suggests_it(office, tmp_path, monkeypatch):
    monkeypatch.setenv("DIWAN_VIDEO", "off")
    listing_video(office, tmp_path)
    o = studio.output_options(office, REF)
    assert o["suggest"]["pick"] == "pictures" and "full server" in o["suggest"]["why"]
    assert o["can"] == {"pictures": True, "voice": False, "video": False} and o["video_mode"] == "off"
    for out in ("voice", "video"):
        with pytest.raises(studio.OutputRefused, match="full server"):
            studio.choose_output_now(office, REF, out, by="maya")


def test_no_ffmpeg_means_no_voice_or_video_either(office, tmp_path, monkeypatch):
    from diwan.agents import freevideo
    monkeypatch.delenv("DIWAN_VIDEO", raising=False)
    monkeypatch.setattr(freevideo, "missing", lambda: ["ffmpeg"])
    listing_video(office, tmp_path)
    assert studio.output_options(office, REF)["can"] == {"pictures": True, "voice": False, "video": False}


def test_light_video_still_counts_as_able(office, tmp_path, monkeypatch):
    monkeypatch.setenv("DIWAN_VIDEO", "light")
    monkeypatch.setattr(studio, "_can_render", lambda: (True, True, ""))
    listing_video(office, tmp_path)
    o = studio.output_options(office, REF)
    assert o["video_mode"] == "light" and o["can"]["voice"] and o["can"]["video"]


# 2. pictures from the brief: a listing's own photos, once each, the call to action last, the permit drawn
def test_a_video_script_becomes_a_carousel_of_the_listings_own_photos(office, tmp_path, monkeypatch):
    sc, paths = listing_video(office, tmp_path, 5)
    permits, real = [], eventpost._draw
    monkeypatch.setattr(eventpost, "_draw", lambda *a, **k: permits.append(k.get("permit", "")) or real(*a, **k))
    v = as_pictures(office)
    slides = v["slides"]
    assert v["format"] == "carousel" and 2 <= len(slides) <= eventpost.MAX_SLIDES
    used = [s["photo"] for s in slides]
    assert all(p in paths for p in used) and len(set(used)) == len(used)  # its own photos, each once
    assert slides[-1]["text"] == sc["lines_en"][-1]  # the call to action stays last
    made = studio.made(office, "slides", REF)
    assert made and len(made["images"]) == len(slides) and all(Image.open(x["path"]).size == (1080, 1350) for x in made["images"])
    assert permits and set(permits) == {"SAMPLE-71204"}
    assert [c["step"] for c in studio.chain(office, REF)][1] == "Make the images"


def test_a_topic_draws_one_picture_a_slide_one_at_a_time(office, monkeypatch):
    monkeypatch.setattr(studio, "_can_render", lambda: (True, True, ""))
    ref = "JOB-introduce"
    sc = approve(office, ref)
    assert not sc.get("slides")
    calls, now, most, lock = [], [0], [0], threading.Lock()
    def bg(o, r, feedback=None, say="", frame=None):
        with lock:
            now[0] += 1
            most[0] = max(most[0], now[0])
        time.sleep(.01)
        calls.append(say)
        with lock:
            now[0] -= 1
        return Image.new("RGB", (eventpost.W, eventpost.H), (40, 60, 80)), "Muse Image"
    monkeypatch.setattr(eventpost, "_background", bg)
    v = studio.choose_output_now(office, ref, "pictures", by="maya")
    assert all(s["photo"] is None for s in v["slides"])  # nothing real to show: drawn
    assert len(calls) == len(v["slides"]) and most[0] == 1


# 3. the words come from the script only; an amount not on the listing is refused
def test_slide_words_come_from_the_script(office, tmp_path):
    sc, _ = listing_video(office, tmp_path)
    v = as_pictures(office)
    said = " ".join([sc["hook_en"], *sc["lines_en"], *[f["words"]["text"] for f in ((sc.get("visual") or {}).get("frames") or [])]])
    assert all(s["text"] in said for s in v["slides"])


def test_an_amount_not_on_the_listing_is_refused(office, tmp_path):
    sc, _ = listing_video(office, tmp_path)
    bad = sc | {"lines_en": [*sc["lines_en"][:-1], "Yours for AED 9,999,999.", sc["lines_en"][-1]]}
    with pytest.raises(studio.OutputRefused, match="not on the listing"):
        eventpost.from_brief(office, REF, bad)


# 4. the original stays as it was; a new version says where it came from; choosing twice makes nothing new
def test_the_original_script_is_unchanged_and_choosing_twice_is_the_same(office, tmp_path):
    sc, _ = listing_video(office, tmp_path)
    before = dict(studio._content(office, sc["id"]))
    v = as_pictures(office)
    assert studio._content(office, sc["id"]) == before
    assert v["revises"] == sc["id"] and v["via"] == "pictures from brief" and v["id"] != sc["id"]
    assert studio.approved_script(office, REF)["id"] == v["id"]  # what goes out from here on is the pictures version
    n = sum(1 for e in office.log.list() if e["type"] == "content.made" and e["content"]["kind"] == "slides")
    assert as_pictures(office)["id"] == v["id"]
    assert sum(1 for e in office.log.list() if e["type"] == "content.made" and e["content"]["kind"] == "slides") == n
    chosen = [e["content"] for e in office.log.list() if e["type"] == "post.output_chosen"]
    assert len(chosen) == 1 and chosen[0] | {} == {"ref": REF, "script": sc["id"], "output": "pictures", "by": "maya", "version": v["id"]}


# 5. it ends at the publish approver; nothing goes out by itself
def test_the_carousel_waits_for_the_publish_approver(office, tmp_path):
    listing_video(office, tmp_path)
    as_pictures(office)
    req = [n for n in office.graph().of("request", status="open") if n.props.get("agent") == "mpub"]
    assert req and f"Publish the {REF} carousel" in req[0].props["text"]
    assert not studio.made(office, "published", REF)


# 6. a price change pauses the carousel, and the price back resumes it
def test_a_price_change_pauses_the_carousel_and_the_old_price_resumes_it(office, tmp_path):
    listing_video(office, tmp_path)
    as_pictures(office)
    lst = office.graph().nodes[f"listing:{REF}"].props
    def price(p):
        office.add_listing(ref=REF, title=lst["title"], community=lst["community"], type=lst["type"], beds=lst["beds"], price_aed=p,
                           permit=lst.get("permit"), status=lst.get("status") or "available", features=lst.get("features") or [], agent=lst.get("agent"), by="omar")
        marketing.watch(office)
        return marketing.pieces(office)[REF]["stage"]
    was = lst["price_aed"]
    assert price(was + 100_000) == "paused"
    assert any(e["type"] == "post.paused" and e["content"].get("ref") == REF for e in office.log.list())
    assert price(was) != "paused"


# 7. a broker can't choose for Marketing
def test_a_broker_cannot_choose_how_a_post_goes_out(monkeypatch):
    from fastapi.testclient import TestClient
    from diwan import access
    monkeypatch.setenv("DIWAN_AUTH", "on")
    monkeypatch.setenv("DIWAN_DB", ":memory:")
    access._fails.clear()
    for who in ("omar", "maya"):
        access.set_password(who, "a good password")
    with TestClient(app, follow_redirects=False) as c:
        assert c.post("/api/auth/login", json={"person": "omar", "password": "a good password"}).status_code == 200
        assert c.get("/api/studio/output", params={"ref": REF}).status_code == 403
        assert c.post("/api/studio/output", json={"ref": REF, "output": "pictures"}).status_code == 403
        assert c.post("/api/auth/login", json={"person": "maya", "password": "a good password"}).status_code == 200
        assert c.get("/api/studio/output", params={"ref": REF}).status_code == 200
