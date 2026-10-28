"""The brand profile is used, not just shown: writers receive it, templates sign off in it, review enforces it."""
import json

import pytest

from diwan import brand, demo
from diwan.agents import qa, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import meta
from diwan.providers.chat import PROVIDERS
from tests.conftest import fake

PROFILE = {"name": "Diwan Realty", "positioning": "Straight answers on Dubai homes for families relocating here.",
           "voice": "warm, straight-talking, expert", "avoid": "luxury, once-in-a-lifetime", "never_claim": "guaranteed returns",
           "cta": "WhatsApp us to walk through it together.", "hashtags": "#DiwanRealty #DubaiHomes"}


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    return o


def test_unset_brand_tells_writers_not_to_invent_one(office):
    assert not brand.is_set(office) and "do not invent a tagline" in brand.brief(office)


def test_saving_keeps_who_and_only_records_changes(office):
    assert set(brand.save(office, PROFILE, by="maya")) == set(PROFILE)
    assert brand.save(office, PROFILE, by="maya") == []
    p = brand.profile(office)
    assert p["voice"]["value"] == "warm, straight-talking, expert" and p["voice"]["by"] == "maya"
    assert brand.hashtags(office) == ["#DiwanRealty", "#DubaiHomes"]


def test_the_script_writer_receives_the_brand(office, monkeypatch):
    brand.save(office, PROFILE, by="maya")
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("DIWAN_TAPE", "off")
    seen = []
    script = {"hook_en": "Sea views in Dubai Marina for AED 2,600,000", "hook_ar": "إطلالة بحرية في دبي مارينا",
              "lines_en": ["A 2 bed at Marina Crest.", "Sea view from the balcony.", "Two parking spaces.", "AED 2,600,000, permit SAMPLE-71204.",
                           "WhatsApp us to walk through it together."], "lines_ar": []}
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(script, seen))
    sc = studio.script(office, "MC-1204", {"pick": {"title": "Marina Crest tour"}}, None, None)
    sent = seen[0]["messages"][1]["content"]
    assert "warm, straight-talking, expert" in sent and "luxury" in sent and "WhatsApp us to walk through it together." in sent
    assert sc["via"] == "muse-spark"


def test_review_sends_back_a_script_or_post_using_a_never_word(office):
    brand.save(office, PROFILE, by="maya")
    bad = {"id": "C1", "hook_en": "Luxury living at Marina Crest", "hook_ar": "حياة", "lines_en": ["a.", "b.", "c.", "d.", "Message us."]}
    fails = qa.review(office, "script", "MC-1204", bad, cause=None, attempt=1)
    assert any(f["check"] == "script-brand" and f["found"] == "luxury" for f in fails)
    post = {"id": "C2", "text": "Guaranteed returns! Permit SAMPLE-71204"}
    assert any(f["check"] == "post-brand" for f in qa.review(office, "post text", "MC-1204", post, cause=None, attempt=1))


def test_templates_and_post_text_sign_off_in_the_brand(office):
    brand.save(office, PROFILE, by="maya")
    sc = studio.script(office, "MC-1204", {"pick": {"title": "x"}}, None, None)
    assert sc["via"] == "template" and sc["lines_en"][-1] == "WhatsApp us to walk through it together."
    text = studio.post_text(office, "MC-1204", sc, None)["text"]
    assert "WhatsApp us to walk through it together." in text and "#DiwanRealty" in text and "sea view" in text.lower()


def test_a_draft_needs_something_real_to_start_from():
    o = Office(EventLog())
    assert "needs" in brand.draft(o)
