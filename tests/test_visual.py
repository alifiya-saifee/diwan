"""The script writer also writes the visual brief: what kind of post, and per frame the background, where the words go,
the logo's corner and the timing. The rules keep it honest; the makers follow it; an old script without one is made as before."""
import pytest
from PIL import Image

from diwan import demo
from diwan.agents import eventpost, studio, visual
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta

TOPIC = {"item": "topic", "title": "Meet Diwan Realty"}
LISTING = {"item": "listing", "title": "Villa 88"}
SCRIPT = {"hook_en": "New to Dubai?", "lines_en": ["We know Dubai Marina well.", "Message us today."]}


def frame(source="AI photo", text="New to Dubai?", position="top", logo="top-left", **k):
    return {"background": {"source": source, "place": "Dubai Marina", "subject": "The Marina canal with yachts", "camera": "promenade, 24mm", "light": "blue hour"},
            "words": {"text": text, "position": position, "size": "big", "style": "band"}, "logo": logo, "motion": "slow zoom in", "seconds": 3, **k}


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path)
    o = Office(EventLog())
    demo.seed(o)
    return o


def test_a_listing_is_only_ever_shown_in_its_own_photos():
    v = visual.clean({"why": "", "mood": "", "frames": [frame()]}, LISTING, "voice-over", SCRIPT)
    assert v["frames"][0]["background"]["source"] == "listing photo" and visual.shot(v["frames"][0]) is None


def test_words_on_screen_come_only_from_the_script():
    v = visual.clean({"why": "", "mood": "", "frames": [frame(text="Best prices in Dubai guaranteed"), frame(text="Dubai Marina")]}, TOPIC, "graphic", SCRIPT)
    assert [f["words"]["text"] for f in v["frames"]] == ["New to Dubai?", "Dubai Marina"]  # the made-up claim gives way to the frame's own line


def test_a_still_never_moves_and_the_logo_keeps_clear_of_the_words():
    v = visual.clean({"why": "w", "mood": "upbeat", "frames": [frame(position="top", logo="top-right")]}, TOPIC, "graphic", SCRIPT)
    f = v["frames"][0]
    assert f["motion"] == "none" and f["seconds"] == 0 and v["mood"] == "" and f["logo"] == "bottom-right"


def test_a_video_frame_holds_a_sensible_time_and_bad_values_fall_back():
    v = visual.clean({"why": "", "mood": "calm", "frames": [frame(seconds=60, motion="spin", logo="centre")]}, TOPIC, "to camera", SCRIPT)
    f = v["frames"][0]
    assert f["seconds"] == 8 and f["motion"] == "slow zoom in" and f["logo"] == "bottom-left"  # top-left by default, moved clear of the words at the top
    assert f["background"]["source"] in ("speaker", "AI photo")


def test_nothing_usable_is_no_brief():
    assert visual.clean(None, TOPIC, "graphic", SCRIPT) is None and visual.clean({"frames": []}, TOPIC, "graphic", SCRIPT) is None


def test_the_brief_reads_in_plain_words():
    v = visual.clean({"why": "", "mood": "", "frames": [frame()]}, TOPIC, "to camera", SCRIPT)
    line = visual.describe(v)[0]
    assert line.startswith("Frame 1 · AI photo of The Marina canal with yachts (blue hour)") and '"New to Dubai?", big, top on a band' in line and "3 s, slow zoom in" in line


def test_the_brief_frame_becomes_the_picture_prompt():
    s = visual.shot(frame())
    assert s["place"] == "Dubai Marina" and "canal" in s["looks"]


def test_the_writer_is_asked_for_the_brief_and_it_is_saved_with_the_script(office, monkeypatch):
    from diwan.agents import director
    from diwan.agents import runner as rn
    seen = {}
    data = {"hook_en": "Looking for a villa?", "hook_ar": "", "lines_en": ["Four bedrooms.", "A garden.", "Message us."], "lines_ar": [], "shots": [],
            "visual": {"why": "competitors' best posts open on the garden", "mood": "warm", "frames": [frame(text="Four bedrooms.")]}}
    monkeypatch.setattr(rn, "has_model", lambda *a, **k: True)
    monkeypatch.setattr(rn, "call", lambda c, system, user, schema=None: seen.update(system=system, schema=schema) or type("R", (), {"data": data})())
    monkeypatch.setattr(director, "script", lambda *a: None)
    monkeypatch.setattr(studio, "_best_hook", lambda *a, **k: None)
    sc = studio.script(office, "JVC-88", {"pick": {"title": "Villa 88"}}, None, None, angle="walkthrough")
    assert "visual" in seen["schema"]["schema"]["required"] and "visual brief" in seen["system"]
    assert sc["visual"]["frames"][0]["background"]["source"] == "listing photo" and sc["visual"]["frames"][0]["words"]["text"] == "Four bedrooms."


def test_old_painted_ai_frames_are_retired_but_uploads_and_photo_style_frames_stay(office):
    from diwan.agents import freevideo
    log = office.log.append
    log("photos.added", actor="maya", content={"ref": "JOB-introduce", "paths": ["painted.webp"], "made_by": "muse-image"})  # before the photo style
    log("photos.added", actor="maya", content={"ref": "JOB-introduce", "paths": ["team.jpg"]})  # a real upload
    log("photos.added", actor="maya", content={"ref": "JOB-introduce", "paths": ["marina.webp"], "made_by": "muse-image", "style": "photo"})
    assert freevideo.photos(office, "JOB-introduce")[-2:] == ["team.jpg", "marina.webp"] and "painted.webp" not in freevideo.photos(office, "JOB-introduce")


def test_words_and_logo_go_where_the_brief_says():
    def draw(fr):
        return eventpost._draw(Image.new("RGB", (eventpost.W, eventpost.H), (240, 240, 240)), "A garden on two sides", "Diwan", centre=True, frame=fr)
    house = draw(None)
    top = draw({"words": {"position": "top", "size": "medium", "style": "band"}, "logo": "bottom-right"})
    y = eventpost.SAFE + 60  # near the top: the brief's band is dark there; the house layout keeps the words in the middle
    assert sum(top.getpixel((eventpost.W // 2, y))) < 300 and sum(house.getpixel((eventpost.W // 2, y))) > 600
    corner = (eventpost.W - eventpost.SAFE - 10, eventpost.H - eventpost.SAFE - 10)  # the logo's plate, bottom-right
    assert sum(top.getpixel(corner)) < 300 and sum(house.getpixel(corner)) > 600
