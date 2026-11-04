"""Muse draws frames for posts about the brand or a topic, and never for a listing. They feed the free video like photos."""
import pytest
from PIL import Image

from diwan import brand, business, demo
from diwan.agents import freevideo, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "no"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, by="maya")
    return o


def scripted(monkeypatch, lines):
    monkeypatch.setattr(studio, "approved_script", lambda o, r: {"shots": [{"say": x} for x in lines]})


def drawn(monkeypatch, tmp_path, fail=()):
    asked = []
    monkeypatch.setattr(meta, "ready", lambda: True)

    def image(prompt, name, size="1024x1792", **k):
        asked.append(prompt)
        if len(asked) in fail:
            raise meta.MetaError("no")
        Image.new("RGB", (64, 64)).save(tmp_path / f"{name}.webp")
        return f"/media/{name}.webp"

    monkeypatch.setattr(meta, "image", image)
    monkeypatch.setattr(meta, "look", lambda s, t, imgs, sc, **k: {"images": [{"n": i, "score": 5, "problem": ""} for i in range(len(imgs))]})
    return asked


def test_a_listing_never_gets_drawn_pictures(office, monkeypatch, tmp_path):
    asked = drawn(monkeypatch, tmp_path)
    scripted(monkeypatch, ["A line."])
    r = freevideo.ai_frames(office, "MC-1204", by="maya")
    assert r["ok"] is False and "real photos" in r["needs"] and not asked and not freevideo.can_draw(office, "MC-1204")


def test_a_brand_post_gets_frames_from_its_script_that_the_video_can_use(office, monkeypatch, tmp_path):
    asked = drawn(monkeypatch, tmp_path)
    scripted(monkeypatch, [f"Line number {w}." for w in "one two three four five six seven eight nine".split()])
    r = freevideo.ai_frames(office, "JOB-introduce", by="maya")
    assert r["ok"] and r["frames"] == freevideo.AI_FRAMES and r["review"]["score"] == 5 and len(asked) == freevideo.AI_FRAMES
    assert all("property magazine" in a and "Not an illustration" in a and "No text or logos" in a for a in asked)
    pics = freevideo.photos(office, "JOB-introduce")
    assert len(pics) == freevideo.AI_FRAMES and freevideo._local(pics[0], tmp_path, 0).exists()


def test_it_does_not_pay_twice(office, monkeypatch, tmp_path):
    asked = drawn(monkeypatch, tmp_path)
    scripted(monkeypatch, ["One.", "Two.", "Three."])
    freevideo.ai_frames(office, "JOB-introduce", by="maya")
    n = len(asked)
    assert freevideo.ai_frames(office, "JOB-introduce", by="maya")["ok"] is False and len(asked) == n


def test_too_few_frames_says_so_and_keeps_nothing(office, monkeypatch, tmp_path):
    drawn(monkeypatch, tmp_path, fail=(1, 2, 3, 4))
    scripted(monkeypatch, [f"Line {i}." for i in range(6)])
    r = freevideo.ai_frames(office, "JOB-introduce", by="maya")
    assert r["ok"] is False and "Try again" in r["needs"] and not freevideo.photos(office, "JOB-introduce")


def test_captions_end_where_a_person_would_pause():
    parts = [" ".join(p) for p in studio._caption_parts("From selling and valuation to management and holiday homes, it's all under one roof.".split())]
    assert all(not p.split()[-1].lower().strip(",.") in studio.HANGING for p in parts) and all(len(p.split()) <= studio.CAPTION_WORDS + 1 for p in parts)
    assert " ".join(parts).split() == "From selling and valuation to management and holiday homes, it's all under one roof.".split()


def test_a_post_with_no_word_of_its_own_gets_a_code_a_person_would_say(office):
    from diwan.agents import marketing
    assert marketing.code_for(office, "JOB-introduce") != "POST"


def test_posts_of_an_account_no_longer_followed_do_not_count(office):
    from diwan.agents import strategy
    office.log.append("post.seen", actor="mrival", content={"id": "x1", "source": "competitor", "account": "robots_r_us", "caption": "Price drop on a robot rental", "score": 99, "avg": 1, "kind": "reel"})
    assert "robots_r_us" not in str(strategy.report(office))


def test_a_long_or_brochure_script_goes_back_to_the_writer(office):
    from diwan.agents import qa
    check = {c.id: c for c in qa.CHECKS["script"]}
    long = {"hook_en": "Moving to Dubai?", "lines_en": ["word " * 70]}
    assert check["script-short"].test(office, "JOB-introduce", long)[0] is False
    sales = {"hook_en": "We provide premier real estate solutions.", "lines_en": []}
    assert check["script-plain"].test(office, "JOB-introduce", sales)[0] is False
    fine = {"hook_en": "Moving to Dubai?", "lines_en": ["We tell you the whole cost first."]}
    assert check["script-short"].test(office, "JOB-introduce", fine)[0] and check["script-plain"].test(office, "JOB-introduce", fine)[0]


def test_only_a_listing_has_to_be_named_in_the_idea(office):
    from diwan.agents import qa
    assert qa._names_listing(office, "JOB-introduce", "Why people trust a straight answer")
    assert not qa._names_listing(office, "MC-1204", "Why people trust a straight answer")


def test_a_frame_the_director_rejects_is_redrawn_and_then_not_offered(office, monkeypatch, tmp_path):
    asked = drawn(monkeypatch, tmp_path)
    scripted(monkeypatch, [f"Line {i}." for i in range(6)])
    monkeypatch.setattr(meta, "look", lambda s, t, imgs, sc, **k: {"images": [{"n": i, "score": 2 if i == 0 else 5, "problem": "generic clip-art" if i == 0 else ""} for i in range(len(imgs))]})
    r = freevideo.ai_frames(office, "JOB-introduce", by="maya")
    assert r["ok"] and r["frames"] == 5 and r["review"]["checked"]
    assert len(asked) == 6 + freevideo.FRAME_ROUNDS and "turned down: generic clip-art" in asked[-1]


def test_when_every_frame_fails_nothing_is_offered_and_it_says_why(office, monkeypatch, tmp_path):
    drawn(monkeypatch, tmp_path)
    scripted(monkeypatch, [f"Line {i}." for i in range(6)])
    monkeypatch.setattr(meta, "look", lambda s, t, imgs, sc, **k: {"images": [{"n": i, "score": 1, "problem": "could be any company"} for i in range(len(imgs))]})
    r = freevideo.ai_frames(office, "JOB-introduce", by="maya")
    assert r["ok"] is False and "could be any company" in r["needs"] and not freevideo.photos(office, "JOB-introduce")


def test_frames_that_could_not_be_checked_say_so(office, monkeypatch, tmp_path):
    drawn(monkeypatch, tmp_path)
    scripted(monkeypatch, ["One.", "Two.", "Three."])
    def down(*a, **k):
        raise meta.MetaError("no")
    monkeypatch.setattr(meta, "look", down)
    r = freevideo.ai_frames(office, "JOB-introduce", by="maya")
    assert r["ok"] and r["review"] == {"checked": False} and freevideo.frame_review(office, "JOB-introduce") == {"checked": False}


def test_real_photos_are_not_held_back_by_the_director(office, monkeypatch):
    from diwan.agents import qa
    monkeypatch.setattr(meta, "look", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not look")))
    assert qa._creative(office, "JOB-introduce", {"images": [{"path": "x", "text": "t"}]})[0]


def test_every_recommendation_says_what_it_is_based_on(office):
    from diwan.agents import marketing, rhythm
    from datetime import date
    rhythm.make_plan(office, date.today(), auto=False, days_ahead=3)
    days = marketing.plan_view(office)["days"]
    assert days and all(d["evidence"] for d in days if d["ref"])


def test_a_stopped_post_loses_its_drawings_but_not_real_photos(office):
    from diwan.agents import marketing
    office.log.append("photos.added", actor="maya", content={"ref": "JOB-introduce", "paths": ["real.jpg"]})
    office.log.append("photos.added", actor="maya", content={"ref": "JOB-introduce", "paths": ["drawn.webp"], "made_by": "muse-image", "style": "photo", "review": {"checked": True, "score": 4}})
    assert freevideo.photos(office, "JOB-introduce") == ["real.jpg", "drawn.webp"] and freevideo.frame_review(office, "JOB-introduce")
    marketing.withdraw(office, "JOB-introduce", "the pictures look wrong")
    assert freevideo.photos(office, "JOB-introduce") == ["real.jpg"] and freevideo.frame_review(office, "JOB-introduce") is None


def test_what_a_person_said_about_pictures_reaches_the_next_drawing(office, monkeypatch, tmp_path):
    from diwan.agents import taste
    asked = drawn(monkeypatch, tmp_path)
    scripted(monkeypatch, ["One line.", "Two lines.", "Three lines."])
    office.log.append("taste.reason", actor="mkt", content={"ref": "JOB-introduce", "why": "looks fictional", "lessons": [{"dim": "picture", "value": "fictional", "sign": -1}]})
    assert taste.doubts_pictures(office)
    freevideo.ai_frames(office, "JOB-introduce", by="maya")
    assert asked and all("pictures: fictional" in p for p in asked)


def test_a_topic_posts_graphic_is_a_planned_photo_of_its_subject_not_an_abstract_pattern(office, monkeypatch, tmp_path):
    from diwan.agents import eventpost
    asked = drawn(monkeypatch, tmp_path)
    img, by = eventpost._background(office, "JOB-introduce", say="Sunset walks in Dubai Marina")
    assert by == "Muse Image" and len(asked) == 1
    assert "Place: Dubai Marina" in asked[0] and "property magazine" in asked[0] and "a caption" in asked[0]
