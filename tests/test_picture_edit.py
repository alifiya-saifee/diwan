"""A person edits a post's picture in their own words: Muse Image gets the picture and the words, nothing in the post
changes until they use the result, and the result then takes the old picture's place."""
import pytest

from diwan import demo
from diwan.agents import freevideo, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    meta.MEDIA.mkdir()
    o = Office(EventLog())
    demo.seed(o)
    return o


@pytest.fixture
def muse(monkeypatch):
    """Muse Image, answered here: it records what it was sent and writes an 'edited' file."""
    sent = []

    def edit_image(picture, prompt, name, *, mime="image/png", agent="mart"):
        sent.append({"picture": picture, "prompt": prompt, "mime": mime})
        (meta.MEDIA / f"{name}.webp").write_bytes(b"edited")
        return f"/media/{name}.webp"
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(meta, "edit_image", edit_image)
    return sent


def slides(o, ref="MC-1204"):
    for i in (1, 2):
        (meta.MEDIA / f"post-{ref}-{i}.jpg").write_bytes(f"slide {i}".encode())
    studio._made(o, "mart", "slides", ref, {"format": "graphic", "images": [
        {"path": str(meta.MEDIA / f"post-{ref}-{i}.jpg"), "served": f"/media/post-{ref}-{i}.jpg", "text": f"Slide {i}"} for i in (1, 2)]}, None)


def test_the_picture_and_the_words_go_to_muse_image_and_the_post_waits(office, muse):
    slides(office)
    r = studio.edit_picture(office, "MC-1204", "/media/post-MC-1204-2.jpg", "make the sky brighter", by="layla")
    assert r["ok"] and r["before"] == "/media/post-MC-1204-2.jpg" and r["after"].startswith("/media/edit-MC-1204-")
    assert muse[0]["picture"] == b"slide 2" and muse[0]["mime"] == "image/jpeg" and "make the sky brighter" in muse[0]["prompt"]
    assert [x["served"] for x in studio.made(office, "slides", "MC-1204")["images"]] == ["/media/post-MC-1204-1.jpg", "/media/post-MC-1204-2.jpg"]


def test_using_the_edit_swaps_only_that_picture(office, muse):
    slides(office)
    r = studio.edit_picture(office, "MC-1204", "/media/post-MC-1204-1.jpg", "remove the logo", by="layla")
    u = studio.use_edit(office, "MC-1204", r["before"], r["after"], r["note"], by="layla")
    assert u["ok"]
    images = studio.made(office, "slides", "MC-1204")["images"]
    assert [x["served"] for x in images] == [r["after"], "/media/post-MC-1204-2.jpg"]
    assert images[0]["edited"] == "remove the logo" and images[0]["text"] == "Slide 1"


def test_a_free_video_picture_is_replaced_in_its_place(office, muse):
    for i in (1, 2):
        (meta.MEDIA / f"up-{i}.jpg").write_bytes(b"x")
    office.log.append("photos.added", actor="layla", content={"ref": "MC-1204", "paths": [str(meta.MEDIA / f"up-{i}.jpg") for i in (1, 2)]})
    before = [freevideo.served(p) for p in freevideo.photos(office, "MC-1204")]
    r = studio.edit_picture(office, "MC-1204", "/media/up-1.jpg", "warmer light", by="layla")
    assert studio.use_edit(office, "MC-1204", r["before"], r["after"], r["note"], by="layla")["ok"]
    after = [freevideo.served(p) for p in freevideo.photos(office, "MC-1204")]
    assert after == [r["after"] if u == "/media/up-1.jpg" else u for u in before]


def test_what_cannot_be_edited_says_why_and_nothing_is_paid(office, muse):
    slides(office)
    assert "Say what should change" in studio.edit_picture(office, "MC-1204", "/media/post-MC-1204-1.jpg", "  ", by="layla")["error"]
    assert "isn't part of this post" in studio.edit_picture(office, "MC-1204", "/media/../../secret.jpg", "x", by="layla")["error"]
    assert "isn't part of this post" in studio.edit_picture(office, "MC-1204", "/media/someone-else.jpg", "x", by="layla")["error"]
    assert not muse


def test_only_an_edit_made_for_this_post_can_be_used(office, muse):
    slides(office)
    (meta.MEDIA / "other.webp").write_bytes(b"x")
    assert not studio.use_edit(office, "MC-1204", "/media/post-MC-1204-1.jpg", "/media/other.webp", "x", by="layla")["ok"]
    assert not studio.use_edit(office, "MC-1204", "/media/post-MC-1204-1.jpg", "/media/edit-MC-1204-../x", "x", by="layla")["ok"]


def test_offline_or_without_a_key_it_says_so(office, monkeypatch):
    slides(office)
    monkeypatch.setattr(meta, "ready", lambda: False)
    assert "META_API_KEY" in studio.edit_picture(office, "MC-1204", "/media/post-MC-1204-1.jpg", "brighter", by="layla")["error"]
