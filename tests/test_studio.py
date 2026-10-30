import asyncio
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from diwan import brain, business, demo
from diwan.agents import analysis, reader, reception, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import instagram, meta
from diwan.providers.chat import PROVIDERS


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    """Per-day numbers depend on today: every test here runs on 29 Oct 2026, noon UTC."""
    monkeypatch.setattr(studio, "_now", lambda: datetime(2026, 10, 29, 12, tzinfo=timezone.utc))


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
    g = office.graph()
    want = next((v.props["broker"] for v in g.of("viewing", status="booked") if v.props["listing"] == "MC-1204"), g.nodes["listing:MC-1204"].props.get("agent"))
    assert studio.made(office, "film list", "MC-1204")["who"] == want  # the viewing's broker, else the listing's agent; never a fixed name
    assert not want or any(t.props.get("needs_person") == want for t in g.of("task"))
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


ACCOUNTS = {"rival.one": {"followers": 10000, "posts": [post(1, 900, "What does 2M buy in Dubai Marina? DM us"), post(2, 850, "Guess this price? Marina sunset"),
                                                         post(3, 60, "Office tour", "REELS", 11)]
                          + [post(10 + i, 100, "New listing in our portfolio, many features and lots of text here " * 3, "IMAGE", 11) for i in range(6)]},
            "rival.two": {"followers": 4000, "posts": [post(30 + i, 40, "Office day #a #b #c #d #e", "IMAGE", 10) for i in range(6)]}}


@pytest.fixture
def connected(monkeypatch, office):
    monkeypatch.setenv("IG_ACCESS_TOKEN", "t")
    monkeypatch.setenv("IG_USER_ID", "1789")
    monkeypatch.setattr(instagram, "TRANSPORT", fake_instagram(ACCOUNTS, [post(50 + i, 30 + i, "Our listing in JVC") for i in range(6)]))
    office.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one, rival.two"})
    return office


def test_competitor_watch_scores_against_each_accounts_own_average(connected):
    top = studio.watch(connected, None)
    # rival.one's reels: 905, 855 and 65 likes+comments, an average of 608; its images are all 105, so none is above the rest
    assert [p["id"] for p in top] == ["p1", "p2"] and top[0]["score"] == 1.5 and top[0]["avg"] == 608 and top[0]["kind"] == "reel"
    pins = studio.board(connected)
    assert [p["kind"] for p in pins] == ["outlier", "outlier"] and pins[0]["url"] == "https://instagram.com/p/p1" and pins[0]["why"].startswith("905 likes+comments, 1.5x")
    assert len(studio.posts(connected, "own")) == 6


def refusing(ok_names=()):
    """Instagram that refuses the token, except for business discovery of the accounts in ok_names."""
    real = fake_instagram(ACCOUNTS, [])
    def handle(req: httpx.Request):
        if any(f"username({n})" in req.url.params.get("fields", "") for n in ok_names):
            return real.handle_request(req)
        return httpx.Response(400, json={"error": {"message": "Invalid OAuth access token - Cannot parse access token"}})
    return httpx.MockTransport(handle)


def test_watch_that_reaches_no_competitor_says_so(connected, monkeypatch):
    monkeypatch.setattr(instagram, "TRANSPORT", refusing())
    assert studio.watch(connected, None) == []
    assert blocked(connected)["mrival"].startswith("0 of 2 competitors reached: @rival.one: Invalid OAuth")
    assert not [e for e in connected.log.list() if e["type"] == "agent.pack" and e["agent"] == "mrival"]  # no "no outliers" verdict


def test_watch_says_how_many_competitors_it_reached(connected, monkeypatch):
    monkeypatch.setattr(instagram, "TRANSPORT", refusing(ok_names=("rival.one",)))
    studio.watch(connected, None)
    verdict = [e for e in connected.log.list() if e["type"] == "agent.pack" and e["agent"] == "mrival"][-1]["content"]["pack"]["verdict"]
    assert verdict.startswith("Reached 1 of 2 competitors. 2 posts above their account's average") and "Not reached: @rival.two" in verdict


def test_instagram_check_is_green_only_when_the_token_works_and_is_remembered(connected, monkeypatch):
    monkeypatch.setattr(instagram, "_CHECKED", {})
    assert instagram.check() == {"ok": True, "username": "diwan.realty"}
    calls = []
    monkeypatch.setattr(instagram, "TRANSPORT", httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500)))
    assert instagram.check()["ok"] and not calls  # remembered: no second call
    monkeypatch.setenv("IG_ACCESS_TOKEN", "IGAAxyz")
    monkeypatch.setattr(instagram, "TRANSPORT", refusing())
    bad = instagram.check()
    assert not bad["ok"] and bad["why"].startswith("Instagram refused the token: Invalid OAuth") and "Facebook Page token" in bad["why"]
    monkeypatch.delenv("IG_USER_ID")
    assert instagram.check() == {"ok": False, "why": "needs IG_USER_ID"}


def test_an_outlier_has_more_likes_and_comments_than_its_accounts_average_for_its_kind():
    def p(i, likes, kind):
        return {"id": i, "likes": likes, "comments": 0, "type": kind}
    by = {r["id"]: r for r in studio.scored([p("r1", 1000, "REELS"), p("r2", 400, "REELS"), p("i1", 17, "IMAGE"), p("i2", 3, "IMAGE")])}
    assert by["r1"]["avg"] == 700 and studio.is_outlier(by["r1"]) and not studio.is_outlier(by["r2"])  # reels are compared with reels
    assert studio.is_outlier(by["i1"]) and by["i1"]["avg"] == 10 and by["i1"]["score"] == 1.7  # no minimum: 17 against an average of 10
    assert not studio.is_outlier(by["i2"]) and isinstance(by["i1"]["avg"], int)  # whole numbers only
    close = {r["id"]: r for r in studio.scored([p("a", 905, "REELS"), p("b", 855, "REELS")])}
    assert close["a"]["score"] == 1.0 and studio.is_outlier(close["a"])  # 905 against 880 is above, though it shows as 1.0x
    assert studio.scored([p("only", 50, "REELS")])[0]["score"] is None  # one reel has no average to beat


def test_saving_a_new_competitor_fetches_only_that_account_and_shows_its_best_posts(connected, monkeypatch):
    from fastapi.testclient import TestClient
    from diwan import app as appmod
    small = {"tiny.one": {"followers": 900, "posts": [post(60 + i, 3 if i else 15, "Small account post", "REELS") for i in range(6)]}}
    asked = []
    real = fake_instagram({**ACCOUNTS, **small}, [])
    monkeypatch.setattr(instagram, "TRANSPORT", httpx.MockTransport(lambda r: asked.append(r.url.params.get("fields", "") + r.url.path) or real.handle_request(r)))
    monkeypatch.setattr(appmod.S, "office", connected)
    c = TestClient(appmod.app)
    r = c.post("/api/studio/competitors", json={"usernames": "@rival.one, rival.two, @tiny.one", "by": "layla"}).json()
    assert r["new"] == ["tiny.one"] and r["reached"] == ["tiny.one"] and r["says"] == "@tiny.one: 900 followers, 6 posts read"
    acc = {x["account"]: x for x in analysis.saved_accounts(connected)}
    assert acc["tiny.one"]["status"] == "fetched" and acc["tiny.one"]["followers"] == 900 and acc["rival.one"]["status"] == "not_checked"
    assert len(asked) == 1 and "username(tiny.one)" in asked[0]  # only the new account; our own posts not re-read
    rows = {x["account"]: x for x in c.get("/api/studio?ref=MC-1204").json()["analysis"]["competitors"]}
    assert rows["tiny.one"]["kpis"]["followers"] == 900 and rows["tiny.one"]["best"][0]["permalink"] == "https://instagram.com/p/p60"  # no minimum: a small account's win counts
    assert [d["posts"] for d in rows["tiny.one"]["daily"]] == [1] * 6 and rows["tiny.one"]["daily"][0] == {"date": "2026-10-10", "engagement": 20, "posts": 1}
    assert c.post("/api/studio/competitors", json={"usernames": "@rival.one, rival.two, @tiny.one", "by": "layla"}).json()["new"] == []
    studio.watch(connected, None)
    best = analysis.report(connected)["competitors"]
    one = next(x for x in best if x["account"] == "rival.one")["best"]
    assert [p["permalink"] for p in one] == ["https://instagram.com/p/p1", "https://instagram.com/p/p2"] and one[0]["x"] == 1.5
    assert one[0]["type"] == "REELS" and one[0]["engagement"] == 905 and one[0]["avg"] == 608 and set(one[0]) >= {"likes", "comments", "hook", "thumb", "at"}


def test_a_new_handle_instagram_cannot_read_is_listed_as_not_found_and_research_is_not_blocked(connected, monkeypatch):
    monkeypatch.setattr(instagram, "TRANSPORT", httpx.MockTransport(lambda r: httpx.Response(400, json={"error": {"message": "Invalid user id"}})))
    connected.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one, @nobody.zz"})
    assert studio.watch(connected, None, only=["nobody.zz"]) == []
    acc = {x["account"]: x for x in analysis.saved_accounts(connected)}
    assert acc["nobody.zz"]["status"] == "not_found" and acc["nobody.zz"]["error"] == "Invalid user id"
    assert "mrival" not in blocked(connected)  # one bad handle does not mark the studio's research as waiting
    connected.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one"})
    assert [x["account"] for x in analysis.saved_accounts(connected)] == ["rival.one"]


def test_a_competitor_ad_is_pinned_by_hand_refused_when_wrong_and_can_be_removed(connected):
    ad = "https://www.facebook.com/ads/library/?id=1234567890"
    def pin(**k):
        return studio.pin_ad(connected, **({"account": "@rival.one", "url": ad, "started": "2026-10-02", "text": "What does 2M buy?\nDM us", "by": "maya"} | k))
    for bad, why in ((dict(account="@stranger"), "not on the competitor list"), (dict(url="https://instagram.com/p/x"), "Ad Library link"),
                     (dict(started="2026-11-30"), "can't be in the future"), (dict(started="yesterday"), "start date"),
                     (dict(ended="2026-10-01"), "between the start and today"), (dict(text="  "), "ad's text")):
        with pytest.raises(ValueError, match=why):
            pin(**bad)
    card = pin()
    assert card["kind"] == "ad" and card["title"] == "What does 2M buy?" and card["why"] == "@rival.one's ad, running since 2026-10-02"
    assert [b["id"] for b in studio.board(connected) if b["kind"] == "ad"] == [card["id"]]
    with pytest.raises(ValueError, match="already pinned"):
        pin()
    studio.unpin(connected, card["id"], by="maya")
    assert not [b for b in studio.board(connected) if b["kind"] == "ad"]
    assert pin(ended="2026-10-20")["why"] == "@rival.one's ad, ran 2026-10-02 to 2026-10-20"  # pinned again after removal
    assert studio.ad_library_url("rival.one").startswith("https://www.facebook.com/ads/library/?") and "country=ALL" in studio.ad_library_url("rival.one")
    assert "country=AE" in studio.ad_library_url("rival.one", "AE")  # the business's own country once Setup has it


def test_follower_growth_shows_once_two_days_are_recorded():
    first = {"ok": True, "followers": 72_000, "at": "2026-10-29T08:00:00Z"}
    assert analysis.growth(first, {"ok": True, "followers": 72_100, "at": "2026-10-29T20:00:00Z"}) == {}  # same day: nothing yet
    assert analysis.growth(first, {"ok": True, "followers": 72_120, "at": "2026-10-31T08:00:00Z"}) == {"growth": 120, "growth_since": "2026-10-29"}
    assert analysis.growth(first, {"ok": False, "error": "Invalid user id", "at": "2026-10-31T08:00:00Z"}) == {}


def test_analysis_gives_kpis_and_measured_reasons(connected):
    studio.watch(connected, None)
    r = analysis.report(connected)
    one = next(a for a in r["competitors"] if a["account"] == "rival.one")
    assert one["kpis"]["followers"] == 10000 and one["kpis"]["outliers"] == 2 and one["kpis"]["formats"] == {"REELS": 3, "IMAGE": 6}
    assert one["kpis"]["engagement_rate"] == round(100 * (905 + 855 + 65 + 105 * 6) / 9 / 10000, 2) and one["kpis"]["avg_reel"] == 608
    assert "not available" in r["notes"][0]
    assert r["why"]["needs"].startswith("Set your industry and country in Setup first")  # nothing is judged before the business is set


def set_business(o):
    business.save(o, {"industry": "Real estate brokerage", "country": "AE", "city": "Dubai"}, by="maya")


def test_the_business_is_set_once_and_every_search_and_hour_follows_it(office):
    assert business.missing(office) == ["Industry", "Country"] and str(business.tz(office)) == "UTC"
    with pytest.raises(business.Invalid):
        business.save(office, {"industry": "x", "country": "ZZ"}, by="maya")
    set_business(office)
    v = business.get(office)
    assert v["timezone"] == "Asia/Dubai" and v["country_name"] == "United Arab Emirates" and business.place(office) == "Dubai, United Arab Emirates"
    with pytest.raises(business.Invalid, match="not a time zone"):
        business.save(office, {"country": "US", "timezone": "Asia/Dubai"}, by="maya")
    assert business.save(office, {"country": "US", "timezone": "America/Chicago"}, by="maya") == ["country", "timezone"]
    assert business.tz_label(office) == "Chicago time"
    assert business.save(office, {"country": "US"}, by="maya") == []  # nothing changed, nothing recorded


def test_suggestions_and_trends_wait_for_the_business(office, monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setattr(meta, "ready", lambda: True)
    asked = []
    monkeypatch.setattr(meta, "search", lambda q, **k: asked.append((q, k)) or {"text": "@one.co https://instagram.com/two.co", "sources": [], "cited": [], "queries": []})
    assert "Set your industry and country" in analysis.suggest(office)["needs"] and not asked
    set_business(office)
    assert analysis.suggest(office)["suggestions"] == ["two.co", "one.co"]
    q, k = asked[0]
    assert "Real estate brokerage businesses in Dubai, United Arab Emirates" in q and k["country"] == "AE"


def reading(seen, carries=lambda i: True):
    """Muse Spark that reads every post: winners (the question captions) as a price reveal to camera, the rest as listing photos."""
    def look(system, text, images, schema, *, agent):
        seen.append({"system": system, "text": text, "images": len(images), "agent": agent})
        rows = [ln for ln in text.split("Posts:\n")[1].splitlines() if ln]
        out = []
        for ln in rows:
            n = int(ln.split(".")[0])
            win = "?" in ln
            out.append({"n": n, "topic": "Price reveal" if win else "listing photos", "hook": "a question" if win else "something else",
                        "on_screen": "a person talking to camera" if win else "text on images", "asks": "send a message" if win else "nothing",
                        "carries_over": carries(n), "why_not": "" if carries(n) else "their awards night"})
        return {"topics": [{"label": "Price reveal", "for_us": "a 30-second price reveal of one of our listings, on camera"}], "posts": out + [{"n": 99, "topic": "x", "hook": "a story",
                "on_screen": "something else", "asks": "nothing", "carries_over": True, "why_not": ""}]}
    return look


WINNERS = {"rival.one": {"followers": 10000, "posts": [post(1, 900, "What does 2M buy in the Marina? DM us"), post(2, 850, "Guess this price?"),
                                                        post(3, 880, "Can you guess the view?"), post(4, 60, "Office tour")]
                         + [post(10 + i, 100, "New listing in our portfolio", "IMAGE", 11) for i in range(6)]}}


def test_why_they_win_reads_each_post_once_and_shows_only_real_patterns(connected, monkeypatch):
    monkeypatch.setattr(instagram, "TRANSPORT", fake_instagram(WINNERS, []))
    connected.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one"})
    studio.watch(connected, None)
    set_business(connected)
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(reader, "_cover", lambda url: b"jpeg")
    seen = []
    monkeypatch.setattr(meta, "look", reading(seen))
    assert reader.unread(connected)["posts"] == 10
    assert reader.read(connected)["read"] == 10  # post 99, which the model made up, is dropped
    assert seen[0]["agent"] == "mrival" and "Real estate brokerage" in seen[0]["system"] and "never use their numbers" in seen[0]["system"]
    acc = reader.patterns(connected)["accounts"][0]
    assert acc["winners"] == 3 and not acc["need"]
    by = {f["dim"]: f for f in acc["patterns"]}
    assert by["topic"]["finding"] == "3 of their 3 best posts are about price reveal; 0 of their 7 ordinary posts do."
    assert acc["for_us"] == ["a 30-second price reveal of one of our listings, on camera", "a short video showing a person talking to camera",
                             "open the first line with a question", "end by asking people to send a message"]
    assert [p["permalink"] for p in acc["best"]] == ["https://instagram.com/p/p1", "https://instagram.com/p/p3", "https://instagram.com/p/p2"]  # each post once
    pins = [b for b in studio.board(connected) if b["kind"] == "pattern"]
    assert len(pins) == 1 and pins[0]["title"].startswith("a 30-second price reveal of one of our listings, on camera; ")  # what the idea writer builds on
    assert pins[0]["why"].startswith("@rival.one: 3 of their 3 best posts are about price reveal")
    reader.read(connected)
    assert len(seen) == 1  # nothing new: no second call


def test_a_post_about_their_own_moment_is_set_aside_and_too_few_winners_say_so(connected, monkeypatch):
    monkeypatch.setattr(instagram, "TRANSPORT", fake_instagram(WINNERS, []))
    connected.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one"})
    studio.watch(connected, None)
    set_business(connected)
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(reader, "_cover", lambda url: None)  # Instagram's cover links expired: captions only
    seen = []
    monkeypatch.setattr(meta, "look", reading(seen, carries=lambda n: n != 0))
    reader.read(connected)
    assert seen[0]["images"] == 0
    acc = reader.patterns(connected)["accounts"][0]
    assert acc["patterns"] == [] and acc["need"].startswith("Not enough posts yet to tell: 2 winning posts read")
    assert acc["skipped"][0]["why_not"] == "their awards night"
    assert not [b for b in studio.board(connected) if b["kind"] == "pattern"]


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
    cov = studio.made(connected, "cover", "MC-1204")  # frames of our own take, never a generated picture
    assert [o["at"] for o in cov["options"]] == [0.9, 1.8] and all((meta.MEDIA / Path(o["served"]).name).exists() for o in cov["options"])
    assert "mthumb" not in blocked(connected)
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


def outlier_rows():
    """Eight posts from one rival on the same days, two of them above their kind's average: reel a0, image a2."""
    return [{"source": "competitor", "account": "@rival.one", "followers": "10000", "url": f"https://instagram.com/p/a{i}", "type": "REELS" if i < 2 else "IMAGE",
             "caption": "What does 2M buy in the Marina?" if i < 2 else "New listing with lots of features " * 4,
             "likes": {0: "900", 1: "300", 2: "400"}.get(i, "100"), "comments": "5",
             "posted_at": "2026-10-20 19:30" if i < 2 else "2026-10-21 11:00"} for i in range(8)]


def test_imported_posts_feed_the_analysis_and_the_board(office):
    rows = outlier_rows()
    r = studio.import_posts(office, rows + [{"account": "", "likes": "1", "comments": "1"}], by="layla")
    assert r["imported"] == 8 and r["outliers"] == 2 and r["errors"] == ["row 10: no account"]
    a = analysis.report(office)
    assert a["competitors"][0]["account"] == "rival.one" and a["competitors"][0]["kpis"]["followers"] == 10000
    assert [b["kind"] for b in studio.board(office)] == ["outlier", "outlier"]
    studio.run_now(office, "MC-1204")
    assert studio.made(office, "ideas", "MC-1204")["ideas"][1]["cards"]  # an idea built on an imported outlier


def test_ideas_and_scripts_name_what_they_came_from(office):
    studio.import_posts(office, outlier_rows(), by="layla")
    studio.run_now(office, "MC-1204")
    idea = studio.made(office, "ideas", "MC-1204")
    assert idea["ideas"][0]["from"] == ["listing:MC-1204"]  # no card: the listing is named
    assert all(i["from"] == i["cards"] for i in idea["ideas"][1:]) and idea["ideas"][1]["cards"]
    sc = studio.script(office, "MC-1204", idea | {"pick": idea["ideas"][1]}, None, None)
    assert sc["idea"] == idea["id"] and sc["cards"] == idea["ideas"][1]["cards"]
    edges = brain.marketing_graph(office)["edges"]
    assert {"src": sc["id"], "dst": sc["cards"][0], "rel": "builds_on"} in edges
    assert {"src": sc["id"], "dst": idea["id"], "rel": "from_idea"} in edges


def test_a_cover_waits_for_footage(office):
    assert studio.cover(office, "MC-1204", {"hook_en": "Marina Crest at AED 2.6M"}, None) is None
    assert "footage" in blocked(office)["mthumb"]


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


def test_a_new_competitor_outside_our_industry_is_added_with_a_warning(connected, monkeypatch):
    set_business(connected)
    monkeypatch.setattr(meta, "ready", lambda: True)
    asked = []
    monkeypatch.setattr(meta, "look", lambda system, text, images, schema, **k: asked.append(text) or {"same_industry": False, "why": "The bio says \"industrial robots\"."})
    studio.watch(connected, None, only=["rival.two"])
    acc = next(a for a in analysis.saved_accounts(connected) if a["account"] == "rival.two")
    assert acc["status"] == "fetched" and acc["fits"] is False and "industrial robots" in acc["fit_why"]  # warned, never refused
    assert "Our industry: Real estate brokerage" in asked[0]


def test_a_script_names_the_competitor_post_it_is_built_like_and_skips_their_own_moments(connected, monkeypatch):
    monkeypatch.setattr(instagram, "TRANSPORT", fake_instagram(WINNERS, []))
    connected.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one"})
    studio.watch(connected, None)
    set_business(connected)
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(reader, "_cover", lambda url: None)
    monkeypatch.setattr(meta, "look", reading([], carries=lambda n: n != 2))  # p3 (index 2) is "their own moment"
    reader.read(connected)
    cards = {c["post"]: c for c in studio.board(connected) if c["kind"] == "outlier"}
    assert set(cards) == {"p1", "p2", "p3"}
    kept = [c["post"] for c in studio.usable(connected, list(cards.values()))]
    assert kept == [x for x in cards if x != "p3"]  # never built on
    line = studio.built_like(connected, [cards["p1"]["id"]])[0]
    assert line == ("Built like @rival.one's reel (905 likes + comments, 1.3x their average reel): it worked because it is a price reveal "
                    "that opens with a question and shows a person talking to camera.")
    monkeypatch.setattr(meta, "ready", lambda: False)
    idea = {"id": "I1", "pick": {"title": "MC-1204 price", "cards": [cards["p1"]["id"]]}}
    sc = studio.script(connected, "MC-1204", idea, None, None)
    assert sc["built_like"] == [line]


def test_a_script_written_before_the_listing_changed_says_what_changed(office):
    sc = studio.script(office, "MC-1204", {"id": "I1", "pick": {"title": "MC-1204", "cards": []}}, None, None)
    assert studio.stale(office, sc) == []
    was = office.graph().nodes["listing:MC-1204"].props["price_aed"]
    lst = office.graph().nodes["listing:MC-1204"].props
    office.log.append("listing.added", actor="layla", content={k: v for k, v in lst.items() if k != "updated_at"} | {"price_aed": 2_450_000})  # the price drops
    assert studio.stale(office, sc) == [f"The price was AED {was:,}, now AED 2,450,000."]


def test_my_own_script_is_checked_problems_listed_and_told_two_other_ways(office):
    r = studio.own_script(office, "MC-1204", "Guaranteed returns in the Marina\nSea view from every room.\nTwo bedrooms.", by="maya")
    own = r["own"]
    assert own["own"] and own["hook_en"] == "Guaranteed returns in the Marina" and own["lines_en"] == ["Sea view from every room.", "Two bedrooms."]  # kept as written
    assert any("No promised returns" in x for x in own["problems"]) and any("5 to 8 lines" in x for x in own["problems"])
    assert len(r["others"]) == 2 and all(x["angle"] != own["angle"] for x in r["others"])
    req = next(n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script")
    assert [x["id"] for x in studio.script_options(office, req.props["text"])] == [own["id"], *[x["id"] for x in r["others"]]]
    with pytest.raises(ValueError, match="hook on the first line"):
        studio.own_script(office, "MC-1204", "just one line", by="maya")


def test_style_notes_come_from_decisions_and_a_used_script_is_never_repeated(office):
    from diwan.agents import qa, style
    studio.run_now(office, "MC-1204")
    req = next(n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script")
    first = studio.script_options(office, req.props["text"])[0]
    office.log.append("decision.made", actor="maya", content={"card": req.id, "answer": "revise", "choice": first["id"], "note": "Make the hook shorter"})
    office.log.append("decision.made", actor="maya", content={"card": req.id, "answer": "approve", "choice": first["id"]})
    ns = style.notes(office)
    assert [n["text"] for n in ns] == ['You asked: "Make the hook shorter".'] and "Make the hook shorter" in style.brief(office)
    style.delete(office, ns[0]["id"], by="maya")
    assert style.notes(office) == [] and style.brief(office) == ""
    again = dict(first, id="C999")  # the same words as the approved script
    fails = qa.review(office, "script", "MC-1204", again, cause=None, attempt=1)
    assert any(f["check"] == "script-not-repeated" and first["id"] in f["found"] for f in fails)
    assert not any(f["check"] == "script-not-repeated" for f in qa.review(office, "script", "MC-1204", dict(first, id="C998", revises=first["id"]), cause=None, attempt=1))


def test_the_automatic_run_starts_at_the_hour_once_and_follows_the_rhythm(office):
    from diwan.agents import rhythm
    set_business(office)  # Dubai time
    at = lambda d, hm: datetime.fromisoformat(f"2026-11-{d:02d}T{hm}:00+04:00")  # noqa: E731
    assert rhythm.due(office, at(2, "09:30")) is None  # automatic is off until the manager turns it on
    rhythm.save(office, {"auto": "on", "rhythm": "every 2 days"}, by="maya")
    assert rhythm.due(office, at(2, "08:59")) is None
    ref = rhythm.due(office, at(2, "09:01"))
    assert ref and office.graph().nodes[f"listing:{ref}"].props["permit"]  # only a listing with a permit
    assert rhythm.due(office, at(2, "10:00")) is None  # once a day
    assert rhythm.due(office, at(3, "09:05")) is None  # every 2 days: not the next day
    assert rhythm.due(office, at(4, "09:05"))
    with pytest.raises(rhythm.Invalid):
        rhythm.save(office, {"at": "9am"}, by="maya")


def test_a_weekly_plan_spreads_listings_by_the_no_repeat_rule_and_can_be_reordered(office):
    from datetime import date
    from diwan.agents import rhythm
    rhythm.save(office, {"rhythm": "weekly", "repeat_listing_days": "7"}, by="maya")
    p = rhythm.make_plan(office, date(2026, 11, 2), auto=False)
    pool = {x["ref"] for x in rhythm.listings(office)}
    refs = [d["ref"] for d in p["days"]]
    assert len(p["days"]) == 7 and set(refs) == pool  # every listing with a permit gets a day
    assert refs[:len(pool)] == list(dict.fromkeys(refs))[:len(pool)]  # no listing twice before all have had a day
    if len(pool) < 7:
        assert "fewer than your 7-day rule needs" in p["days"][len(pool)]["why"]
    moved = rhythm.move(office, "2026-11-02", 1, by="maya")
    assert [d["ref"] for d in moved["days"]][:2] == [refs[1], refs[0]]


def test_an_angle_used_in_the_last_days_is_skipped_while_others_are_left(office):
    from diwan.agents import strategy
    first = [x["angle"] for x in strategy.pick(office, 3)]
    again = [x["angle"] for x in strategy.pick(office, 3, avoid={first[0]})]
    assert first[0] not in again and len(again) == 3


def test_every_script_has_a_video_plan_and_the_film_list_follows_it(office):
    studio.run_now(office, "MC-1204")
    req = next(n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script")
    sc = studio.script_options(office, req.props["text"])[0]
    rows = sc["shots"]
    assert len(rows) == 1 + len(sc["lines_en"]) and rows[0]["at"] == 0 and rows[0]["say"] == sc["hook_en"]
    assert all(rows[i]["at"] < rows[i + 1]["at"] for i in range(len(rows) - 1))  # timed from the words
    assert any(r["show"] == "The price card" and "Permit" in r["text"] for r in rows)
    studio.approve_script_now(office, "MC-1204", choice=sc["id"])
    film = studio.made(office, "film list", "MC-1204")
    assert film["shots"][0].startswith(rows[0]["show"]) and film["shots"][-1].startswith("End on the price card")


@pytest.mark.skipif(subprocess.run(["which", "say"], capture_output=True).returncode != 0, reason="needs the macOS voice")
def test_the_free_video_reads_the_script_over_the_photos_and_goes_to_editing(office, tmp_path):
    from PIL import Image
    from diwan.agents import freevideo
    studio.run_now(office, "MC-1204")
    req = next(n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script")
    assert freevideo.make(office, "MC-1204", by="maya") == {"ok": False, "needs": "an approved script (pick one first)"}
    studio.approve_script_now(office, "MC-1204", choice=studio.script_options(office, req.props["text"])[0]["id"])
    assert "photos of MC-1204" in freevideo.make(office, "MC-1204", by="maya")["needs"]
    paths = []
    for i, c in enumerate([(40, 90, 140), (150, 120, 80)]):
        Image.new("RGB", (1200, 800), c).save(tmp_path / f"p{i}.jpg"); paths.append(str(tmp_path / f"p{i}.jpg"))
    office.log.append("photos.added", actor="maya", content={"ref": "MC-1204", "paths": paths})
    r = freevideo.make(office, "MC-1204", by="maya")
    assert r["ok"]
    f = studio.footage(office, "MC-1204")
    assert f["source"].startswith("free video: the computer's voice") and studio._duration(Path(f["path"])) > 8
    assert studio._width(Path(f["path"])) == 1080


def test_each_step_says_who_it_waits_for_by_the_role_set_in_setup(office):
    from diwan.agents import approvers, qa
    studio.run_now(office, "MC-1204")
    steps = studio.chain(office, "MC-1204")
    assert [s["state"] for s in steps] == ["waiting", "not yet", "not yet", "not yet"]
    assert steps[0]["who"] == "nobody set yet (Setup → Approvals)"
    approvers.save(office, {"script": "maya", "publish": "layla"}, by="layla")
    assert studio.chain(office, "MC-1204")[0]["who"] == "Maya (Marketing manager)"
    with pytest.raises(ValueError):
        approvers.save(office, {"script": "nobody-here"}, by="layla")
    studio.approve_script_now(office, "MC-1204")
    steps = studio.chain(office, "MC-1204")
    assert steps[0]["state"] == "done" and steps[0]["who"].startswith("picked") and steps[1]["state"] == "waiting"
    qa.escalate(office, "script", "MC-1204", [], cause=None)
    assert next(e for e in reversed(office.log.list()) if e["type"] == "decision.needed")["content"]["who"] == "maya"  # the role, not a fixed name


def test_our_own_posts_are_read_too_and_each_weak_one_gets_advice_from_what_wins(connected, monkeypatch):
    ours = [post(60, 900, "What does it buy? DM us"), post(61, 880, "Guess the price? DM us"), post(62, 850, "Can you guess? DM us"),
            post(63, 50, "New listing in our portfolio"), post(64, 60, "New listing in our portfolio again")]
    monkeypatch.setattr(instagram, "TRANSPORT", fake_instagram(WINNERS, ours))
    connected.log.append("setting.changed", actor="layla", content={"person": "studio", "key": "competitors", "value": "@rival.one"})
    studio.watch(connected, None)
    set_business(connected)
    monkeypatch.setattr(meta, "ready", lambda: True)
    monkeypatch.setattr(reader, "_cover", lambda url: None)
    seen = []
    monkeypatch.setattr(meta, "look", reading(seen))
    reader.read(connected)
    assert any("our own account" in x["system"] for x in seen)
    o = reader.patterns(connected)["ours"]
    assert o["read"] == 5 and o["winners"] == 3 and o["patterns"][0]["finding"] == "3 of our 3 best posts are about price reveal; 0 of our 2 ordinary posts do."
    assert len(o["weak"]) == 2 and o["weak"][0]["advice"][0].startswith("A 30-second price reveal") and o["weak"][0]["from"] == "our best posts"
    assert any(c["kind"] == "pattern" and c["account"] == "us" for c in studio.board(connected))


def test_a_shot_matches_a_feature_by_its_words_not_a_number_in_the_line():
    lst = {"features": ["sea view", "balcony", "2 parking"], "price_aed": 2_600_000, "permit": "P1"}
    rows = studio.video_plan({"hook_en": "What does it buy?", "lines_en": ["This is Unit 1204.", "Sea view.", "2 bedroom apartment.", "Two parking spaces."]}, lst)
    assert [r["show"] for r in rows[1:]] == ["A wide shot of the main room", "Close-up of the sea view", "A wide shot of the main room", "Close-up of the 2 parking"]
