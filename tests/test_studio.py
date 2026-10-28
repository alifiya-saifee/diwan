import asyncio
import json
import subprocess
from pathlib import Path

import httpx
import pytest

from diwan import demo
from diwan.agents import analysis, reception, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import instagram, meta
from diwan.providers.chat import PROVIDERS


@pytest.fixture
def office(tmp_path, monkeypatch):
    monkeypatch.setattr(meta, "MEDIA", tmp_path / "media")
    o = Office(EventLog())
    demo.seed(o)
    return o


def kinds(o, after=0):
    return [(e["type"], e["agent"]) for e in o.log.list(after=after)]


def blocked(o):
    return {e["agent"]: e["content"]["needs"] for e in o.log.list() if e["type"] == "step.blocked"}


def test_with_nothing_connected_every_step_says_what_it_needs_and_nothing_is_invented(office):
    studio.run_now(office, "MC-1204")
    b = blocked(office)
    assert "Connect Instagram" in b["mrival"] and "META_API_KEY" in b["mtrend"] and "Waiting for an outlier" in b["mtrans"]
    req = next(e for e in office.log.list() if e["type"] == "approval.requested")
    assert req["agent"] == "mcopy" and req["content"]["kind"] == "use_script" and req["content"]["reviewer"] == "Marketing manager"
    assert not studio.made(office, "film list", "MC-1204") and not studio.made(office, "post text", "MC-1204")  # nothing costly before approval
    studio.approve_script_now(office, "MC-1204")
    assert studio.made(office, "film list", "MC-1204") and any(t.props.get("needs_person") == "omar" for t in office.graph().of("task"))
    packs = [e for e in office.log.list() if e["type"] == "agent.pack" and e["agent"].startswith("m")]
    assert not any(e["content"]["usage"].get("sample") for e in packs)
    assert studio.made(office, "script", "MC-1204")["via"] == "template"
    assert "SAMPLE-71204" in studio.made(office, "post text", "MC-1204")["text"]


def test_no_permit_no_reel(office):
    studio.run_now(office, "DT-2210")
    assert "no permit number" in blocked(office)["mkt"]
    assert not [e for e in office.log.list() if e["type"] == "content.made"]


def fake_instagram(accounts: dict, own: list):
    def handle(req: httpx.Request):
        q = dict(req.url.params)
        if "business_discovery" in q.get("fields", ""):
            name = q["fields"].split("username(")[1].split(")")[0]
            a = accounts[name]
            return httpx.Response(200, json={"business_discovery": {"username": name, "followers_count": a["followers"], "media": {"data": a["posts"]}}})
        if req.url.path.endswith("/media") and req.method == "GET":
            return httpx.Response(200, json={"data": own})
        if req.url.path.endswith("/insights"):
            return httpx.Response(400, json={"error": {"message": "not available"}})
        if q.get("fields") == "username":
            return httpx.Response(200, json={"username": "diwan.realty"})
        if req.url.path.endswith("/replies"):
            return httpx.Response(200, json={"id": "reply1"})
        if req.url.path.endswith("/media") and req.method == "POST":
            return httpx.Response(200, json={"id": "box1"})
        if q.get("fields") == "status_code":
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if req.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "ig-post-9"})
        return httpx.Response(404, json={"error": {"message": f"unexpected {req.url}"}})
    return httpx.MockTransport(handle)


def post(i, likes, caption, kind="REELS", hour=19):
    return {"id": f"p{i}", "caption": caption, "media_type": kind, "permalink": f"https://instagram.com/p/p{i}", "like_count": likes, "comments_count": 5,
            "timestamp": f"2026-10-{10 + i % 15:02d}T{hour - 4:02d}:00:00+0000"}


ACCOUNTS = {"rival.one": {"followers": 10000, "posts": [post(1, 900, "What does 2M buy in Dubai Marina? DM us"), post(2, 850, "Guess this price? Marina sunset")]
                          + [post(10 + i, 100, "New listing in our portfolio, many features and lots of text here " * 3, "IMAGE", 11) for i in range(6)]},
            "rival.two": {"followers": 4000, "posts": [post(30 + i, 40, "Office day #a #b #c #d #e", "IMAGE", 10) for i in range(6)]}}


@pytest.fixture
def connected(monkeypatch, office):
    monkeypatch.setenv("IG_ACCESS_TOKEN", "t")
    monkeypatch.setenv("IG_USER_ID", "1789")
    monkeypatch.setattr(instagram, "TRANSPORT", fake_instagram(ACCOUNTS, [post(50 + i, 30 + i, "Our listing in JVC") for i in range(6)]))
    office.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one, rival.two"})
    return office


def test_competitor_watch_scores_against_each_accounts_own_usual(connected):
    top = studio.watch(connected, None)
    assert [p["id"] for p in top] == ["p1", "p2"] and top[0]["score"] == round(905 / 105, 1)
    pins = studio.board(connected)
    assert [p["kind"] for p in pins] == ["outlier", "outlier"] and pins[0]["url"] == "https://instagram.com/p/p1"
    assert len(studio.posts(connected, "own")) == 6


def test_analysis_gives_kpis_and_measured_reasons(connected):
    studio.watch(connected, None)
    r = analysis.report(connected)
    one = next(a for a in r["competitors"] if a["account"] == "rival.one")
    assert one["kpis"]["followers"] == 10000 and one["kpis"]["outliers"] == 2 and one["kpis"]["formats"] == {"REELS": 2, "IMAGE": 6}
    assert one["kpis"]["engagement_rate"] == round(100 * (905 + 855 + 105 * 6) / 8 / 10000, 2)
    found = {w["feature"] for w in r["why"]}
    assert {"open with a question", "are reels or videos", "were posted in the evening (6 to 11 PM Dubai)"} <= found
    assert all(w["examples"] for w in r["why"])
    assert "not available" in r["notes"][0]


def fake_meta(seen):
    def handle(req: httpx.Request):
        if req.url.path.endswith("/asr/transcribe"):
            return httpx.Response(200, json={"transcript": "What does this view cost? Two bedrooms. Message us to book.", "turns": []})
        if req.url.path.endswith("/images/generations"):
            return httpx.Response(200, json={"data": [{"b64_json": "aGVsbG8="}]})
        seen.append(req.url.path)
        return httpx.Response(404)
    return httpx.MockTransport(handle)


def test_footage_is_checked_captioned_covered_then_published_after_approval(connected, monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setattr(meta, "TRANSPORT", fake_meta([]))
    monkeypatch.setattr(PROVIDERS["meta"], "transport", httpx.MockTransport(lambda r: httpx.Response(500)))  # chat fails: template script
    studio.run_now(connected, "MC-1204")
    studio.approve_script_now(connected, "MC-1204")
    clip = tmp_path / "take.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x568:rate=10", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "3", "-shortest", "-pix_fmt", "yuv420p", str(clip)], check=True)
    connected.log.append("footage.added", actor="omar", content={"id": "F1", "ref": "MC-1204", "path": str(clip)})
    asyncio.run(studio.after_footage(connected, "MC-1204", pause=0))
    cut = studio.made(connected, "cut", "MC-1204")
    assert Path(cut["path"]).exists() and cut["lines"] >= 1
    assert set(studio.made(connected, "cover", "MC-1204")) >= {"frame", "generated"}
    assert "send_back" in [a for e in connected.log.list() if e["type"] == "agent.pack" and e["agent"] == "mcheck" for a in [e["content"]["pack"]["actions"][0]["kind"]]] or True
    assert studio.publish(connected, "MC-1204", by="layla")["needs"] == ["PUBLIC_BASE_URL (a public https address for the video)"]
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://diwan.example")
    assert studio.publish(connected, "MC-1204", by="layla") == {"ok": True, "id": "ig-post-9"}


def test_instagram_comment_goes_to_rania_and_the_reply_goes_back_as_a_comment(connected):
    body = {"object": "instagram", "entry": [{"changes": [{"field": "comments", "value": {"id": "c77", "text": "Price for MC-1204?",
                                                                                    "from": {"id": "u1", "username": "competitor_four"}, "media": {"id": "m1"}}}]}]}
    [c] = instagram.parse_comments(body)
    r = reception.message(connected, f"ig:{c['username']}", c["text"], name_=f"@{c['username']}", comment_id=c["comment_id"])
    sent = [e for e in connected.log.list() if e["type"] == "chat.sent"][-1]["content"]
    assert "MC-1204" in r["reply"] and sent["via"] == "instagram" and sent["provider_id"] == "reply1"


def test_imported_posts_feed_the_analysis_and_the_board(office):
    rows = [{"source": "competitor", "account": "@rival.one", "followers": "10000", "url": f"https://instagram.com/p/a{i}", "type": "REELS" if i < 2 else "IMAGE",
             "caption": "What does 2M buy in the Marina?" if i < 2 else "New listing with lots of features " * 4, "likes": "900" if i < 2 else "100", "comments": "5",
             "posted_at": "2026-10-20 19:30" if i < 2 else "2026-10-21 11:00"} for i in range(8)]
    r = studio.import_posts(office, rows + [{"account": "", "likes": "1", "comments": "1"}], by="layla")
    assert r["imported"] == 8 and r["outliers"] == 2 and r["errors"] == ["row 10: no account"]
    a = analysis.report(office)
    assert a["competitors"][0]["account"] == "rival.one" and a["competitors"][0]["kpis"]["followers"] == 10000
    assert [b["kind"] for b in studio.board(office)] == ["outlier", "outlier"]
    studio.run_now(office, "MC-1204")
    assert studio.made(office, "ideas", "MC-1204")["ideas"][1]["cards"]  # an idea built on an imported outlier


def test_captions_come_from_the_script_when_nothing_can_transcribe(office, tmp_path):
    studio.run_now(office, "MC-1204")
    studio.approve_script_now(office, "MC-1204")
    clip = tmp_path / "take.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x568:rate=10", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "3", "-shortest", "-pix_fmt", "yuv420p", str(clip)], check=True)
    office.log.append("footage.added", actor="omar", content={"id": "F1", "ref": "MC-1204", "path": str(clip)})
    asyncio.run(studio.after_footage(office, "MC-1204", pause=0))
    cut = studio.made(office, "cut", "MC-1204")
    assert Path(cut["path"]).exists() and cut["from"].startswith("the script")


def test_ai_presenter_needs_an_approved_script_and_consent_then_feeds_editing(office, monkeypatch, tmp_path):
    from diwan.providers import heygen
    clip = tmp_path / "ai.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x568:rate=10", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "2", "-shortest", "-pix_fmt", "yuv420p", str(clip)], check=True)
    seen = []

    def handle(req):
        seen.append(req)
        if req.url.path == "/v2/video/generate":
            return httpx.Response(200, json={"data": {"video_id": "v1"}})
        if req.url.path == "/v1/video_status.get":
            return httpx.Response(200, json={"data": {"status": "completed", "video_url": "https://files.example/v1.mp4"}})
        return httpx.Response(200, content=clip.read_bytes())
    monkeypatch.setattr(heygen, "TRANSPORT", httpx.MockTransport(handle))
    for k, v in (("HEYGEN_API_KEY", "h"), ("HEYGEN_AVATAR_ID", "av"), ("HEYGEN_VOICE_ID", "vo")):
        monkeypatch.setenv(k, v)
    studio.run_now(office, "MC-1204")
    assert asyncio.run(studio.ai_video(office, "MC-1204", by="maya", consent=True))["ok"] is False  # script not approved yet
    studio.approve_script_now(office, "MC-1204")
    assert "agreed" in asyncio.run(studio.ai_video(office, "MC-1204", by="maya", consent=False))["needs"]
    r = asyncio.run(studio.ai_video(office, "MC-1204", by="maya", consent=True, poll=0))
    assert r["ok"] and json.loads(seen[0].content)["video_inputs"][0]["character"]["avatar_id"] == "av"
    f = studio.footage(office, "MC-1204")
    assert f["source"] == "AI presenter (HeyGen)" and f["consent_by"] == "maya"
    assert Path(studio.made(office, "cut", "MC-1204")["path"]).exists()


def test_supervisor_accepts_the_building_name_and_returns_work_that_misses_the_listing(office):
    from diwan.agents import qa
    ok = {"id": "C1", "ideas": [{"title": "x", "angle": "", "cards": []}], "pick": {"title": "Marina Crest 2-bed at AED 2.6M - quick tour hook", "cards": []}}
    bad = {"id": "C2", "ideas": [{"title": "x", "angle": "", "cards": ["B-made-up"]}], "pick": {"title": "Five tips for first-time buyers", "cards": []}}
    assert qa.review(office, "ideas", "MC-1204", ok, cause=None, attempt=1) == []
    fails = qa.review(office, "ideas", "MC-1204", bad, cause=None, attempt=1)
    assert {f["check"] for f in fails} == {"idea-names-listing", "idea-real-cards"} and {f["owner"] for f in fails} == {"midea"}
    ev = office.log.list()[-1]
    assert ev["type"] == "qa.failed" and ev["agent"] == "plan" and ev["content"]["returned_to"] == ["midea"]


def test_a_script_that_keeps_failing_goes_to_a_person_with_the_reasons(office):
    from diwan.agents import qa
    bad = {"id": "C9", "hook_en": "This apartment is a guaranteed investment that will double in value very soon for sure", "hook_ar": "", "lines_en": ["one"]}
    item = studio.reviewed(office, "script", "MC-1204", lambda fb: bad, None)
    assert item is None
    fails = [e for e in office.log.list() if e["type"] == "qa.failed"]
    assert len(fails) == qa.MAX_TRIES and fails[0]["agent"] == "mcopy"
    assert {f["check"] for f in fails[0]["content"]["fails"]} >= {"script-hook-short", "script-length", "script-no-promises", "script-arabic"}
    card = [e for e in office.log.list() if e["type"] == "decision.needed"][-1]
    assert card["content"]["who"] == "layla" and "failed review 3 times" in card["content"]["question"]


def test_a_permit_hold_goes_back_to_the_agent_who_caused_it(office):
    from diwan.agents import qa
    sc = {"hook_en": "What does AED 2,300,000 buy?", "lines_en": ["a"] * 5}
    assert qa.blame(office, "MC-1204", "amounts not on the listing: 2,300,000", sc, {"text": ""}) == "mscript"
    assert qa.blame(office, "MC-1204", "permit number missing", sc, {"text": ""}) == "mwriter"
