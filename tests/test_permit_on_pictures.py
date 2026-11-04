"""An ad for a listing carries its advertising permit on every picture (Dubai's rule for property ads); a topic or a
greeting has no permit and shows none."""
from PIL import Image, ImageChops

from diwan.agents import eventpost, studio

from .test_eventpost import approve, moment, office, picture  # noqa: F401  the same studio office and helpers


def _margin(img):
    return img.crop((eventpost.W // 2, eventpost.H - eventpost.SAFE, eventpost.W, eventpost.H))


def test_the_permit_sits_small_in_the_bottom_margin():
    blank = Image.new("RGB", (eventpost.W, eventpost.H), (90, 110, 130))
    plain = eventpost._draw(blank, "A garden on two sides", "Diwan Realty", centre=False)
    marked = eventpost._draw(blank, "A garden on two sides", "Diwan Realty", centre=False, permit="SAMPLE-71204")
    assert ImageChops.difference(_margin(plain), _margin(marked)).getbbox()  # something is written there
    above = (0, 0, eventpost.W, eventpost.H - eventpost.SAFE)
    assert not ImageChops.difference(plain.crop(above), marked.crop(above)).getbbox()  # and nothing else moved


def _permits(monkeypatch):
    seen, real = [], eventpost._draw
    def spy(*a, **k):
        seen.append(k.get("permit", ""))
        return real(*a, **k)
    monkeypatch.setattr(eventpost, "_draw", spy)
    return seen


def test_every_picture_of_a_listing_carries_its_permit(office, tmp_path, monkeypatch):
    office.log.append("photos.added", actor="maya", content={"ref": "MC-1204", "paths": [picture(tmp_path, f"l{i}.jpg") for i in range(5)]})
    eventpost.choose(office, "MC-1204", "carousel", by="maya")
    seen = _permits(monkeypatch)
    approve(office, "MC-1204")
    assert studio.made(office, "slides", "MC-1204") and seen and set(seen) == {"SAMPLE-71204"}


def test_a_topic_shows_no_permit(office, tmp_path, monkeypatch):
    seen = _permits(monkeypatch)
    approve(office, moment(office, tmp_path, 4))
    assert seen and set(seen) == {""}
