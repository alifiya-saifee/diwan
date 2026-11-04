"""The demo feed lists its photos as the app's own addresses (/web/img/demo/...): they open as files, so a feed listing
gets its carousel and its free video from its own photos."""
from diwan.agents import eventpost, freevideo

from .test_eventpost import office  # noqa: F401  the same studio office


def test_a_feed_photo_opens_from_the_apps_own_folder():
    assert freevideo.on_disk("/web/img/demo/marina.jpg").endswith("web/img/demo/marina.jpg")
    assert eventpost._load("/web/img/demo/marina.jpg") is not None
    assert freevideo.on_disk("/tmp/x.jpg") == "/tmp/x.jpg" and freevideo.on_disk("https://x/y.jpg") == "https://x/y.jpg"


def test_a_feed_listings_own_photos_are_usable_for_pictures_and_the_free_video(office, tmp_path):
    from diwan import demo
    demo.catalog(office)
    pics = eventpost.photos(office, "DR-101", fetch=True)
    assert len(pics) >= 3 and all(p["usable"] for p in pics), pics
    assert all(freevideo._local(p, tmp_path, i) for i, p in enumerate(freevideo.photos(office, "DR-101")))


def test_a_number_in_arabic_has_no_separator_the_font_cannot_draw():
    for said in ("ماذا تشتري بـ ١٬٣٥٠٬٠٠٠ درهم؟", "ماذا تشتري بـ 1,350,000 درهم؟"):
        out = eventpost.arabic_text(said)
        assert "١٬٣٥٠٬٠٠٠" in out and "," not in out, out  # the Arabic separator: drawn, and the number stays in order
    assert eventpost.arabic_text("دبي، مارينا") == "دبي، مارينا"  # the Arabic comma between words stays


def test_a_server_with_no_computer_voice_uses_espeak(monkeypatch, tmp_path):
    which = {"say": None, "espeak-ng": "/usr/bin/espeak-ng", "ffmpeg": "/usr/bin/ffmpeg"}
    monkeypatch.setattr(freevideo, "WINDOWS", False)
    monkeypatch.setattr(freevideo.shutil, "which", lambda n: which.get(n))
    ran = []
    monkeypatch.setattr(freevideo, "_run", lambda *a: ran.append(a))
    assert freevideo.missing() == [] and freevideo.voice() == "the server's voice"
    out = freevideo._speak("Two bedrooms, sea view.", tmp_path / "line0")
    assert out.suffix == ".wav" and ran[0][0] == "/usr/bin/espeak-ng" and "-w" in ran[0]
    assert "Two bedrooms" not in " ".join(ran[0])  # the words go through a file, never the command line
    which["espeak-ng"] = None
    assert freevideo.missing() == ["the computer's voice"]
