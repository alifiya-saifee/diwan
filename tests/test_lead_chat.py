"""The Marketing lead's chat: answers from the studio's data, searches posts by date, reads uploads (measured apart from
what the person said), and does a change only after a yes."""
import subprocess

import httpx
import pytest

from diwan import business, demo
from diwan.agents import lead_chat, runner, rhythm
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import instagram, meta
from diwan.providers.chat import Reply


@pytest.fixture
def office(monkeypatch, tmp_path):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "city": "Dubai"}, by="maya")
    return o


def model(monkeypatch, answers):
    """A stand-in for Muse Spark that answers in turn and keeps what it was asked."""
    asked = []
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: True)
    def call(c, system, user, schema=None, **k):
        asked.append(user)
        a = answers.pop(0)
        return Reply({"reply": "", "action": "none", **{x: "" for x in lead_chat.ARGS}, **a}, {})
    monkeypatch.setattr(runner, "call", call)
    return asked


def test_it_answers_from_the_studio_and_keeps_the_conversation(office, monkeypatch):
    asked = model(monkeypatch, [{"reply": "Price reveals are untested for us."}, {"reply": "Yes, still untested."}])
    assert lead_chat.say(office, "S1", "How are our angles doing?", by="maya")["reply"] == "Price reveals are untested for us."
    lead_chat.say(office, "S1", "Still?", by="maya")
    assert "Real estate brokerage" in asked[0] and "Angles:" in asked[0]  # the studio's own data
    assert "Manager: How are our angles doing?" in asked[1] and "You: Price reveals are untested for us." in asked[1]
    assert [m["who"] for m in lead_chat.history(office, "S1")] == ["person", "lead", "person", "lead"]


def test_a_change_waits_for_a_yes(office, monkeypatch):
    model(monkeypatch, [{"reply": "Shall I plan the next 7 days?", "action": "plan_week"}, {"reply": "Done.", "action": "confirm"}])
    rhythm.save(office, {"rhythm": "weekly", "posts_per_week": "7"}, by="maya")
    r = lead_chat.say(office, "S2", "Plan next week", by="maya")
    assert r["pending"] == {"action": "plan_week"} and not rhythm.plans(office)  # nothing done yet
    r = lead_chat.say(office, "S2", "yes", by="maya")
    assert len(rhythm.plans(office)[-1]["days"]) == 7 and r["reply"].startswith("Planned:")
    assert lead_chat.pending(office, "S2") is None


def test_it_searches_a_competitors_posts_between_two_dates(office, monkeypatch):
    monkeypatch.setenv("IG_ACCESS_TOKEN", "t"); monkeypatch.setenv("IG_USER_ID", "1")
    monkeypatch.setattr(instagram, "offline", lambda: False, raising=False)
    posts = [{"id": f"p{i}", "caption": f"Post {i}", "media_type": "REELS", "permalink": f"https://i/p{i}", "like_count": 100 * i, "comments_count": i,
              "timestamp": f"2026-10-{i:02d}T10:00:00+0000"} for i in range(1, 21)]
    def handle(req):
        return httpx.Response(200, json={"business_discovery": {"username": "rival", "followers_count": 5000, "media": {"data": posts[::-1]}}})
    monkeypatch.setattr(instagram, "TRANSPORT", httpx.MockTransport(handle))
    asked = model(monkeypatch, [{"reply": "", "action": "search_posts", "account": "@rival", "since": "2026-10-05", "until": "2026-10-09"},
                                {"reply": "Five posts; the best was on the 9th."}])
    r = lead_chat.say(office, "S3", "Search @rival's posts from 5 to 9 October", by="maya")
    assert r["found"].startswith("@rival: 5 posts between 2026-10-05 and 2026-10-09") and "[2026-10-09, REELS] 900 likes" in r["found"]
    assert "What the search returned" in asked[1] and r["reply"] == "Five posts; the best was on the 9th."


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="needs ffmpeg")
def test_an_uploaded_reel_is_measured_transcribed_and_read(office, monkeypatch, tmp_path):
    clip = tmp_path / "their.mp4"  # 6 seconds: 2 seconds each of three colours, so 2 cuts
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=red:s=320x568:d=2", "-f", "lavfi", "-i", "color=blue:s=320x568:d=2",
                    "-f", "lavfi", "-i", "color=green:s=320x568:d=2", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-filter_complex",
                    "[0:v][1:v][2:v]concat=n=3:v=1[v]", "-map", "[v]", "-map", "3:a", "-t", "6", "-pix_fmt", "yuv420p", str(clip)], check=True)
    monkeypatch.setattr(lead_chat.local_asr, "available", lambda: False)
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(meta, "transcribe", lambda wav: {"text": "Guess the price", "turns": []})
    seen = []
    monkeypatch.setattr(meta, "look", lambda system, text, images, schema, **k: seen.append(len(images)) or
                        {"what": "a reel", "topic": "price reveal", "hook": "a question", "on_screen": "text on images", "on_screen_text": "Guess the price",
                         "asks": "comment", "tone": "playful", "why_it_worked": ["a question in the first second"], "carries_over": True, "why_not": "", "for_us": "a price guess reel"})
    model(monkeypatch, [{"reply": "It's a price-guess reel with fast cuts. How many likes and comments did it get?"}])
    r = lead_chat.add_upload(office, "S4", clip, "their.mp4", "video/mp4", by="maya", facts={"whose": "@rival", "likes": "2400"})
    assert r["measured"]["seconds"] == 6.0 and r["measured"]["cuts"] == 2 and r["measured"]["seconds_per_cut"] == 2.0
    assert r["speech"] == "Guess the price" and r["speech_via"] == "Muse Voice Transcribe" and seen == [6]
    u = lead_chat.uploads(office, "S4")[0]
    assert u["likes"] == "2400" and u["analysis"]["read"]["hook"] == "a question"  # what was told and what was measured, apart
    assert lead_chat.say(office, "S4", "I uploaded their.mp4.", by="maya")["reply"].endswith("How many likes and comments did it get?")


def test_talking_says_so_when_the_listening_drops(monkeypatch):
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from diwan import app as server
    from diwan.providers import voice

    async def gone(audio, on_turn):
        on_turn({"partial": "Uh yes I wanted to ask"})
        raise voice.VoiceError("connection lost")

    monkeypatch.setattr(voice, "available", lambda: True)
    monkeypatch.setattr(voice, "stream", gone)
    with TestClient(server.app) as c, c.websocket_connect("/api/marketing/chat/audio?session=s") as ws:
        assert ws.receive_json() == {"partial": "Uh yes I wanted to ask"}
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == 4002 and "Press Talk" in closed.value.reason


def _office():
    from diwan import brand, business, demo
    from diwan.events import EventLog
    from diwan.office import Office
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "posted_before": "no"}, by="maya")
    brand.save(o, {"name": "Diwan Realty", "positioning": "A Dubai brokerage.", "cta": "Guiding you home"}, by="maya")
    return o


def test_the_lead_knows_the_next_post_prices_and_what_each_post_brought():
    from diwan.agents import lead_chat
    o = _office()
    text = lead_chat.context(o, "s", None)
    assert "The next post is JOB-introduce" in text and "AED 2,600,000" in text and "JOB-why-us" in text
    o.log.append("lead.attributed", actor="mkt", deal="D9", content={"ref": "MC-1204", "via": "code word"})
    assert "Traced to Unit 1204, Marina Crest: 1 leads" in lead_chat.context(o, "s", None)


def test_a_yes_reports_what_really_happened_not_what_the_model_said(monkeypatch):
    from diwan.agents import lead_chat, rhythm
    o = _office()
    rhythm.save(o, {"posts_per_week": "3"}, by="maya")
    o.log.append("mchat.said", actor="mkt", agent="mkt", content={"session": "s", "who": "lead", "text": "Shall I?", "action": "plan_week", "pending": {"action": "plan_week"}})
    monkeypatch.setattr(lead_chat, "_model_turn", lambda *a, **k: {"reply": "Locked K4, K10 and K19.", "action": "confirm"})
    r = lead_chat.say(o, "s", "yes", by="maya")
    assert "K4" not in r["reply"] and r["reply"].startswith("Planned:") and "Meet Diwan Realty" in r["reply"]
    assert len(rhythm.current(o)["days"]) >= 3


def test_the_lead_can_run_a_post_about_the_brand():
    from diwan.agents import lead_chat
    o = _office()
    assert "Started a run for JOB-introduce" in lead_chat._do(o, {"action": "run_listing", "ref": "JOB-introduce"}, "maya")
    assert "can't find" in lead_chat._do(o, {"action": "run_listing", "ref": "NOPE"}, "maya")
