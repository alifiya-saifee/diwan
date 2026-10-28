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


def test_the_marketing_memory_graph_shows_the_brand_and_what_follows_it(office):
    from diwan.brain import marketing_graph
    before = marketing_graph(office)
    assert not any(n["type"] == "brand" for n in before["nodes"])
    brand.save(office, PROFILE, by="maya")
    studio.run_now(office, "MC-1204")
    req = studio.script_request(office, "MC-1204")
    pick = studio.script_options(office, req.props["text"])[1]["id"]
    studio.approve_script_now(office, "MC-1204", choice=pick)
    g = marketing_graph(office)
    rels = {(e["src"], e["rel"], e["dst"]) for e in g["edges"]}
    assert ("person:maya", "set", "brand:voice") in rels and ("person:maya", "picked", pick) in rels
    assert all((s["id"], "follows", "brand:profile") in rels for s in g["nodes"] if s["type"] == "script")
    assert {n["id"]: n["status"] for n in g["nodes"]}[pick] == "approved"
    rewound = marketing_graph(office, upto=before["last_event"])
    assert not any(n["type"] == "brand" for n in rewound["nodes"])  # rewinding goes back to before the brand was set


def test_learning_keeps_only_cards_proven_by_a_quote(office, monkeypatch):
    """The AI proposes knowledge from a document; a card whose quote is not in the document is dropped, and every kept card waits for a person."""
    from diwan import learn
    from pathlib import Path
    doc = (Path(studio.__file__).parents[1] / "demo_profile.md").read_text()
    reply = {"company": "Diwan Realty", "brand": {k: "" for k in brand.FIELDS} | {"cta": "WhatsApp us and we'll walk you through it."},
             "cards": [{"topic": "about", "title": "Founded in 2016", "text": "Diwan Realty was founded in 2016 by Layla Mansour.",
                        "quote": "independent Dubai real estate brokerage founded in 2016 by Layla Mansour", "source": "company profile"},
                       {"topic": "track record", "title": "Award winner", "text": "Diwan won Broker of the Year.",
                        "quote": "Broker of the Year 2025", "source": "company profile"}]}
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("DIWAN_TAPE", "off")
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(reply))
    r = learn.learn(office, documents={"company profile": doc})
    assert [k["title"] for k in r["proposed"]] == ["Founded in 2016"]
    assert r["dropped"] == [{"title": "Award winner", "why": "its quote is not on the page it cites"}]
    k = office.graph().nodes[r["proposed"][0]["id"]]
    assert k.status == "proposed" and k.props["source"] == "company profile"
    assert r["brand"]["cta"] == "WhatsApp us and we'll walk you through it."


def test_list_fields_written_as_sentences_still_work(office):
    """The live draft wrote the never-use list as a sentence; the check must still catch each word."""
    brand.save(office, {"avoid": 'We never say "luxury", "once-in-a-lifetime", "hurry" or "best investment", and we never use more than one exclamation mark.',
                        "never_claim": "We never claim guaranteed returns, guaranteed rental income or that prices will rise.",
                        "hashtags": "#DiwanRealty and #HonestHomes", "voice": "Warm, plain and expert."}, by="maya")
    assert brand._split(brand.profile(office)["avoid"]["value"]) == ["luxury", "once-in-a-lifetime", "hurry", "best investment"]
    assert brand.broken(office, "A luxury home") == "luxury" and brand.broken(office, "Guaranteed returns for you") == "guaranteed returns"
    assert brand.broken(office, "prices will rise next year") == "prices will rise"
    assert brand.hashtags(office) == ["#DiwanRealty", "#HonestHomes"]
