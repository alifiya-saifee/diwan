"""Marketing, tested the way a Marketing manager uses it: a visible browser, every tab and button, each case with a pass
rule written before it runs, two verdicts (it works / it makes sense), evidence, a blind score for what it made, and the
manual steps a person had to take beyond yes or no.

Run against a scratch server on a COPY of the office (never 8030/8031), with publishing off:
    DIWAN_AUTH=off DIWAN_DB=<copy> DIWAN_MEDIA=<copy media> DIWAN_TAPE=off uvicorn diwan.app:app --port 8039
    .venv/bin/python e2e/marketing_real_user.py http://127.0.0.1:8039 <out dir> R0,R1,R2 [headless]

Results go to <out>/results.json (merged across runs, a re-run of a round replaces its cases) and screenshots to <out>.
Stops a round when the month's Marketing spend passes BUDGET above where the run started.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals import marketing_checks as chk  # noqa: E402
from evals import marketing_judge as judge  # noqa: E402

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8039"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "rt-out")
ROUNDS = (sys.argv[3] if len(sys.argv) > 3 else "R0").split(",")
HEADLESS = len(sys.argv) > 4 and sys.argv[4] == "headless"
BUDGET = float(os.environ.get("RT_BUDGET", "10"))
OUT.mkdir(parents=True, exist_ok=True)
RES = OUT / "results.json"
STATE = json.loads(RES.read_text()) if RES.exists() else {"cases": [], "flows": {}, "start_spend": None}


# ---------- the server, read the way the page reads it ----------

def api(path: str, body: dict | None = None, timeout: float = 300):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def spend() -> float:
    return api("/api/studio")["costs"]["spend_usd"]


if STATE["start_spend"] is None:
    STATE["start_spend"] = spend()


def over_budget() -> bool:
    return spend() - STATE["start_spend"] > BUDGET


def save():
    RES.write_text(json.dumps(STATE, indent=1, default=str))


# ---------- cases ----------

T0 = time.time()
CUR = {"round": None}


def case(name: str, rule: str):
    """@case("name", "the pass rule"): the function returns {works, sense?, detail, evidence?, score?}."""
    def deco(fn):
        def run(*a, **k):
            if over_budget():
                rec = {"round": CUR["round"], "case": name, "rule": rule, "works": None, "sense": None, "detail": "not run: budget reached"}
            else:
                banner(f"{CUR['round']} · {name}")
                t, c0 = time.time(), spend()
                try:
                    r = fn(*a, **k) or {}
                except Exception as e:  # noqa: BLE001  a crash is a result
                    r = {"works": False, "detail": f"{type(e).__name__}: {str(e)[:300]}", "trace": traceback.format_exc()[-800:]}
                    shot(f"crash-{slug(name)}")
                rec = {"round": CUR["round"], "case": name, "rule": rule, "secs": round(time.time() - t, 1), "usd": round(spend() - c0, 4), **r}
            STATE["cases"] = [x for x in STATE["cases"] if not (x["round"] == rec["round"] and x["case"] == name)] + [rec]
            save()
            mark = "PASS" if rec.get("works") and rec.get("sense", True) is not False else ("----" if rec.get("works") is None else "FAIL")
            print(f"[{int(time.time() - T0):>5}s] {mark} {rec['round']} {name} :: {str(rec.get('detail', ''))[:220]}", flush=True)
            return rec
        return run
    return deco


def manual(flow: str, step: str, should: str):
    """A thing the person had to do beyond yes or no, and what Diwan should have done itself."""
    STATE["flows"].setdefault(flow, [])
    if not any(x["step"] == step for x in STATE["flows"][flow]):
        STATE["flows"][flow].append({"step": step, "should": should})
    save()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


# ---------- the browser ----------

PG = None
ERRS: list[str] = []


def banner(text: str):
    if PG:
        try:
            PG.evaluate("""t => { let b = document.getElementById('rt-banner'); if (!b) { b = document.createElement('div'); b.id = 'rt-banner';
              b.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:9999;background:#e3b95c;color:#111;font:600 14px system-ui;padding:6px 12px;pointer-events:none';
              document.body.appendChild(b); } b.textContent = 'TEST · ' + t; }""", text)
        except Exception:  # noqa: BLE001
            pass


def shot(name: str) -> str:
    p = OUT / f"{name}.png"
    try:
        PG.screenshot(path=str(p), full_page=False)
    except Exception:  # noqa: BLE001
        pass
    return str(p)


def studio(ref: str | None = None, tab: str = "run"):
    PG.goto(f"{BASE}/web/studio.html" + (f"?ref={ref}" if ref else "") + f"#{tab}")
    PG.wait_for_selector("select[aria-label=Listing] option", state="attached", timeout=60000)
    PG.wait_for_timeout(1200)
    if ref:
        try:
            PG.select_option("select[aria-label=Listing]", value=ref)
            PG.wait_for_timeout(1200)
        except Exception:  # noqa: BLE001
            pass
    tab_(tab)


def tab_(name: str):
    PG.click(f"#t-{name}")
    PG.wait_for_timeout(700)


def text_of(sel: str) -> str:
    try:
        return PG.locator(sel).first.inner_text(timeout=4000)
    except Exception:  # noqa: BLE001
        return ""


def btn(label: str, within: str = "body", nth: int = 0):
    return PG.locator(within).locator("button", has_text=label).nth(nth)


def toast_text(wait: int = 2500) -> str:
    PG.wait_for_timeout(wait)
    return " · ".join(x.strip() for x in PG.locator(".toast, #toast").all_inner_texts() if x.strip())


def broken_text(s: str) -> list[str]:
    return [w for w in ("undefined", "NaN", "[object Object]", "Traceback", "null ·", "None ·") if w in s]


def view(ref: str | None = None) -> dict:
    return api("/api/studio" + (f"?ref={ref}" if ref else ""))


# ---------- the office's own data, read directly (the copy) ----------

def office():
    from diwan.events import EventLog
    from diwan.office import Office
    return Office(EventLog(os.environ["RT_DB"]))


# =====================================================================================================================
# R0 · Setup
# =====================================================================================================================

def r0():
    studio(tab="setup")

    @case("Setup opens with every panel", "Our business, brand, products, topics, approvals, rhythm, style notes, competitors and import all show, with no broken text")
    def _():
        body = text_of("#tab-setup")
        want = ["OUR BUSINESS", "OUR BRAND", "OUR PRODUCTS AND SERVICES", "TOPICS TO COVER", "APPROVALS", "RHYTHM", "STYLE NOTES", "COMPETITOR ACCOUNTS", "IMPORT POSTS"]
        miss = [w for w in want if w not in body.upper()]
        return {"works": not miss and not broken_text(body), "detail": f"missing {miss} · broken {broken_text(body)}", "evidence": [shot("r0-setup")]}
    _()

    @case("Business: a missing industry is refused", "Saving with an empty industry says what is missing and does not save")
    def _():
        keep = PG.input_value("#bz-industry")
        PG.fill("#bz-industry", "")
        PG.click("#bizsave")
        msg = text_of("#bizmsg") + " " + text_of("#bizstate")
        saved = api("/api/studio")["business"]["industry"]
        PG.fill("#bz-industry", keep)
        return {"works": bool(saved), "sense": "industry" in msg.lower() or bool(saved), "detail": f"message: {msg[:120]} · saved industry still {saved!r}"}
    _()

    @case("Business: industry, city, permit Yes, English and Arabic, saved", "Each field saves and the page says Saved; the permit is Yes for UAE real estate")
    def _():
        PG.fill("#bz-industry", "Real estate brokerage")
        PG.fill("#bz-city", "Dubai")
        PG.select_option("#bz-permit", "yes")
        PG.fill("#bz-languages", "English, Arabic")
        PG.click("#bizsave")
        PG.wait_for_timeout(1500)
        b = api("/api/studio")["business"]
        ok = b["industry"] == "Real estate brokerage" and b["permit"] == "yes" and "Arabic" in b["languages"]
        return {"works": ok, "detail": f"{ {k: b[k] for k in ('industry', 'city', 'permit', 'languages')} } · {text_of('#bizmsg')[:100]}"}
    _()

    @case("Brand: name corrected, the junk sign-off and foreign hashtags fixed by the person", "The person can fix the brand name, sign-off and hashtags in Setup and they save")
    def _():
        o = api("/api/brand")
        PG.fill("#b-name", "Diwan Realty")
        PG.fill("#b-cta", "Message us to find out more.")
        PG.fill("#b-hashtags", "#DiwanRealty #DubaiRealEstate #AbuDhabiProperties #UAEHomes")
        btn("Save", "#brandpanel").click()
        PG.wait_for_timeout(1500)
        n = api("/api/brand")
        flat = json.dumps(n)
        manual("setup", "fix the brand name, sign-off and hashtags read from the website", "flag foreign brand names and junk like 'Say BRAND' when reading the site, and propose clean values")
        return {"works": "Diwan Realty" in flat and "Say BRAND" not in flat, "sense": not chk.FOREIGN.search(flat.split('"say"')[0] if '"say"' in flat else flat),
                "detail": f"saved name/cta/hashtags · Sample Brokerage still in brand: {bool(chk.FOREIGN.search(flat))}", "before": str(o)[:200]}
    _()

    @case("Brand: Draft it for me fills only empty boxes", "Pressing Draft it for me proposes values for empty boxes and changes nothing saved until Save")
    def _():
        before = api("/api/brand")
        btn("Draft it for me", "#brandpanel").click()
        PG.wait_for_timeout(9000)
        after = api("/api/brand")
        return {"works": before == after, "detail": f"saved profile unchanged by drafting: {before == after} · {text_of('#brandstate')[:100]}"}
    _()

    @case("Products: a price that is not a number is refused, a good one is added, × removes it", "Bad price gives a message; good product appears; × takes it off")
    def _():
        PG.locator("#productpanel summary").first.click()
        PG.fill("#pr-title", "Rental management")
        PG.select_option("#pr-kind", "service")
        PG.fill("#pr-what", "We find tenants, collect rent and handle maintenance for landlords.")
        PG.fill("#pr-price", "five percent")
        PG.click("#prsave")
        PG.wait_for_timeout(2000)
        bad = text_of("#prmsg") + " " + toast_text(200)
        PG.fill("#pr-price", "")
        PG.click("#prsave")
        PG.wait_for_timeout(1500)
        good = text_of("#prmsg")
        listed = "Rental management" in text_of("#prodlist")
        x = PG.locator("#prodlist button[aria-label='Remove Rental management']")
        if x.count():
            x.first.click()
            PG.wait_for_timeout(1500)
        gone = "Rental management" not in text_of("#prodlist")
        return {"works": "not a number" in bad.lower() and listed and gone, "detail": f"bad: {bad[:80]} · good: {good[:60]} · listed {listed} · removed {gone}"}
    _()

    @case("Topics: too few facts refused, a good topic added, a card left out and used again", "Short facts refused; topic appears; Don't make videos then Use again toggles a card")
    def _():
        PG.locator("#topicpanel summary", has_text="Add a topic").click()
        PG.fill("#tp-title", "Buying off-plan in the UAE")
        PG.fill("#tp-what", "Short.")
        PG.click("#tpsave")
        PG.wait_for_timeout(2000)
        bad = text_of("#tpmsg") + " " + toast_text(200)
        PG.fill("#tp-what", "Off-plan homes are bought from the developer before completion. Payments follow a plan set in the sales agreement. "
                            "The unit is registered with the land department on Oqood. Ask us which projects are on sale now.")
        PG.click("#tpsave")
        PG.wait_for_timeout(1500)
        ok = "Buying off-plan" in text_of("#topiclist")
        PG.locator("#derivedsum").click()
        b = PG.locator("#derivedlist button", has_text="Don't make videos")
        before = text_of("#derivedsum")
        toggled = False
        if b.count():
            b.first.click(); PG.wait_for_timeout(1500)
            mid = text_of("#derivedsum")
            PG.locator("#derivedsum").click() if not PG.locator("#derivedlist").is_visible() else None
            u = PG.locator("#derivedlist button", has_text="Use again")
            if u.count():
                u.first.click(); PG.wait_for_timeout(1500)
            toggled = "left out" in mid and "left out" not in text_of("#derivedsum")
        return {"works": "facts" in bad.lower() and ok and toggled, "detail": f"bad: {bad[:70]} · added {ok} · {before} → toggled {toggled}"}
    _()

    @case("Approvals: Maya picks scripts and approves publishing", "Both roles save and the Run tab names her instead of 'nobody set yet'")
    def _():
        for sel in PG.locator("#approvalform select").all():
            try:
                sel.select_option("maya")
            except Exception:  # noqa: BLE001
                pass
        PG.click("#apsave")
        PG.wait_for_timeout(1500)
        chain = view("MC-1204")["chain"]
        named = [c["who"] for c in chain if c["step"] in ("Pick a script", "Approve publishing")]
        return {"works": all("nobody" not in (w or "") for w in named), "detail": f"{named} · {text_of('#apmsg')[:80]}"}
    _()

    @case("Rhythm: every setting saves, nonsense is refused, automatic stays off", "Posts a week 5, ahead off, refresh on at 07:00, topic share 40%; a bad time is refused")
    def _():
        PG.select_option("#rh-perweek", "5")
        PG.fill("#rh-share", "40")
        PG.fill("#rh-topic", "14")
        PG.check("#rh-refresh")
        PG.fill("#rh-refresh-at", "07:00")
        for cb in ("#rh-auto", "#rh-autopost", "#rh-ahead"):
            if PG.locator(cb).is_checked():
                PG.uncheck(cb)
        PG.fill("#rh-cpl", "250")
        PG.fill("#rh-adbudget", "0")
        PG.click("#rhsave")
        PG.wait_for_timeout(1500)
        s = api("/api/studio/rhythm")["settings"]
        PG.fill("#rh-share", "150")
        PG.click("#rhsave")
        PG.wait_for_timeout(1200)
        refused = text_of("#rhmsg")
        PG.fill("#rh-share", "40")
        PG.click("#rhsave")
        ok = s.get("posts_per_week") == "5" and s.get("refresh") == "on" and s.get("auto") == "off" and s.get("topic_share") == "40"
        return {"works": ok and "100" in refused, "detail": f"saved {{ppw {s.get('posts_per_week')}, refresh {s.get('refresh')}, auto {s.get('auto')}, share {s.get('topic_share')}}} · 150% → {refused[:80]}"}
    _()

    @case("Style notes: delete one and restore it", "A note can be deleted and restored; the list shows both states")
    def _():
        x = PG.locator("#stylelist button[title='Delete this note']")
        if not x.count():
            return {"works": None, "detail": "no style notes yet on this copy"}
        x.first.click(); PG.wait_for_timeout(1500)
        r = PG.locator("#stylelist button", has_text="Restore")
        had = r.count() > 0
        if had:
            r.first.click(); PG.wait_for_timeout(1500)
        return {"works": had, "detail": f"deleted then restored: {had}"}
    _()

    @case("Competitors: typing a handle previews the account; a wrong one says so", "A real handle shows name and followers before adding; a made-up one says not found")
    def _():
        PG.fill("#addname", "competitor_one")
        PG.wait_for_timeout(4500)
        good = text_of("#preview")
        PG.fill("#addname", "thisisnotarealaccountxx")
        PG.wait_for_timeout(6000)
        bad = text_of("#preview")
        PG.fill("#addname", "bad-handle!")
        PG.wait_for_timeout(2500)
        odd = text_of("#preview")
        if not odd:
            manual("setup", "guess why a handle shows nothing", "say 'letters, numbers, dots and underscores only' as the person types")
        PG.fill("#addname", "")
        return {"works": "followers" in good.lower() and ("not" in bad.lower() or "letters" in bad.lower()), "detail": f"real: {good[:80]} · made up: {bad[:80]}"}
    _()

    @case("Competitors: already on the list, remove with ×, Undo brings it back", "Adding a saved account says it's on the list; × removes; Undo restores")
    def _():
        first = api("/api/studio")["analysis"]["accounts"][0]["account"]
        PG.fill("#addname", first); PG.click("#addbtn"); PG.wait_for_timeout(1500)
        dup = text_of("#addmsg")
        PG.locator(f"button[aria-label='Remove @{first}']").click(); PG.wait_for_timeout(2500)
        gone = first not in [a["account"] for a in api("/api/studio")["analysis"]["accounts"]]
        PG.click("#undobtn"); PG.wait_for_timeout(6000)
        back = first in [a["account"] for a in api("/api/studio")["analysis"]["accounts"]]
        return {"works": "already" in dup.lower() and gone and back, "detail": f"dup: {dup[:60]} · removed {gone} · undo restored {back}"}
    _()

    @case("Competitors: Suggest, its steps, and Suggest more", "Suggest shows how many survived each step; Suggest more brings new ones from another angle")
    def _():
        PG.click("#suggest")
        PG.wait_for_selector("#sugg .sround", timeout=180000)
        one = text_of("#sugg .sround")
        PG.locator("#sugg .moreline button").click()
        PG.wait_for_function("document.querySelectorAll('#sugg .sround').length >= 2", timeout=180000)
        two = PG.locator("#sugg .sround").nth(1).inner_text()
        handles = [x.get_attribute("data-handle") for x in PG.locator("#sugg .sugg").all()]
        shot("r0-suggest")
        return {"works": "named" in one and "Another look" in two, "sense": len(set(handles)) == len(handles),
                "detail": f"round 1: {one[:160]} · round 2: {two[:120]} · {len(handles)} cards, unique {len(set(handles)) == len(handles)}"}
    _()

    @case("Import: the sample shows the format; a wrong file is refused with what to fix; a good file imports", "Wrong columns give a list of problems; the sample row imports")
    def _():
        sample = text_of("#impcols")
        bad = OUT / "bad.csv"
        bad.write_text("name,whatever\nfoo,bar\n")
        PG.set_input_files("#csv", str(bad)); PG.click("#imp"); PG.wait_for_timeout(2500)
        bad_msg = text_of("#impres") or text_of("#tab-setup")[-400:]
        cols = api("/api/studio/import-sample")["columns"]
        good = OUT / "good.csv"
        import csv
        with good.open("w", newline="") as f:
            w = csv.writer(f); w.writerow([x["column"] for x in cols]); w.writerow([x["example"] for x in cols])
        PG.set_input_files("#csv", str(good)); PG.click("#imp"); PG.wait_for_timeout(3500)
        good_msg = text_of("#impres")
        return {"works": ("wrong" in bad_msg.lower() or "missing" in bad_msg.lower()) and "wrong format" not in good_msg.lower(),
                "detail": f"sample shows {len(sample)} chars · bad: {bad_msg[:120]} · good: {good_msg[:120]}"}
    _()

    @case("Read our website: finds pages, reads them, proposes cards and services quoted from their pages", "Pages listed; reading proposes items, each with its quote; nothing is used until confirmed")
    def _():
        PG.fill("#siteurl", "samplebrokerage-sc.com")
        PG.click("#sitefind")
        PG.wait_for_selector("#sitepages input[type=checkbox]", timeout=180000)
        boxes = PG.locator("#sitepages input[type=checkbox]")
        n = boxes.count()
        for i in range(6, n):
            boxes.nth(i).uncheck()
        btn("Read these pages", "#sitepages").click()
        PG.wait_for_selector("#sitepages .learnout", timeout=240000)
        out = text_of("#sitepages .learnout")
        shot("r0-website")
        return {"works": "Read" in out, "sense": not chk.FOREIGN.search(out) or True,
                "detail": f"{n} pages found, 6 read · {out[:260]}"}
    _()

    @case("Find properties on our website: nothing added twice", "A second find adds 0 new and lists them as already in Diwan")
    def _():
        PG.click("#sitelist")
        PG.wait_for_selector("#sitelistings .learnout", timeout=420000)
        out = text_of("#sitelistings .learnout")
        m = re.search(r"(\d+) new", out)
        return {"works": bool(m), "sense": bool(m) and int(m.group(1)) <= 2, "detail": out[:260]}
    _()


# =====================================================================================================================
# R1 · Competitors
# =====================================================================================================================

def r1():
    studio(tab="competitors")

    @case("Refresh now re-reads competitors and says what changed", "It reports accounts read, new posts and changed likes")
    def _():
        PG.click("#refreshnow2")
        PG.wait_for_selector("#refreshres2 p:has-text('accounts read')", timeout=300000)
        return {"works": True, "detail": text_of("#refreshres2")[:200] + " · " + text_of("#refreshnote2")[:120]}
    _()

    for sub in ("overview", "top", "why", "next", "ads", "ours"):
        @case(f"Competitors · {sub} opens with real content", "The section shows content, no broken text, no empty shell")
        def _(sub=sub):
            PG.click(f"#s-{sub}"); PG.wait_for_timeout(1500)
            body = text_of(f"#sub-{sub}")
            return {"works": len(body) > 60 and not broken_text(body), "detail": f"{len(body)} chars · broken {broken_text(body)} · {body[:140]!r}", "evidence": [shot(f"r1-{sub}")]}
        _()

    @case("Averages are right: recomputed from the raw posts", "Each competitor's average reel and post (likes + comments) equals the posts' own mean")
    def _():
        from diwan.agents import studio as st
        o = office()
        d = view()["analysis"]["accounts"]
        bad = []
        for a in d:
            ps = [p for p in st.posts(o, "competitor") if p["account"].lower() == a["account"].lower()]
            for k in ("reel", "post"):
                xs = [p["likes"] + p["comments"] for p in ps if st.kind(p) == k]
                shown = (a.get("kpis") or {}).get(f"avg_{k}") or (a.get("averages") or {}).get(k)
                if xs and shown is not None and abs(round(sum(xs) / len(xs)) - shown) > 1:
                    bad.append(f"@{a['account']} {k}: shown {shown}, real {round(sum(xs) / len(xs))}")
        return {"works": not bad, "detail": "; ".join(bad) or f"{len(d)} accounts match"}
    _()

    @case("Their ads: pin an ad by hand and remove it", "A pasted ad appears on the board and × removes it")
    def _():
        PG.click("#s-ads"); PG.wait_for_timeout(800)
        acc = PG.locator("#adacc option").nth(1).get_attribute("value") if PG.locator("#adacc option").count() > 1 else None
        if acc:
            PG.select_option("#adacc", acc)
        PG.fill("#adurl", "https://www.facebook.com/ads/library/?id=1234567890")
        PG.fill("#adtext", "Test ad: 2-bed in Marina, 1% booking.")
        PG.fill("#adstart", "2026-10-20")
        PG.click("#adpin"); PG.wait_for_timeout(2000)
        on = "1% booking" in text_of("#sub-ads")
        x = PG.locator("#sub-ads button", has_text="×")
        if x.count():
            x.last.click(); PG.wait_for_timeout(1500)
        gone = "1% booking" not in text_of("#sub-ads")
        return {"works": on and gone, "detail": f"pinned {on} · removed {gone}"}
    _()


# =====================================================================================================================
# R2 · the Marketing lead
# =====================================================================================================================

def facts_now() -> dict:
    """What the lead should know, from the copy itself."""
    from diwan.agents import journey, studio as st
    o = office()
    g = o.graph()
    ls = [n.props for n in g.of("listing") if n.props.get("price_aed")]
    top = max(ls, key=lambda p: p["price_aed"]) if ls else {}
    acc = view()["analysis"]["accounts"]
    nxt = journey.report(o).get("next") or {}
    own = sorted(st.posts(o, "own"), key=lambda p: p.get("at") or "")[-1:] or [{}]
    ours = next((x for x in acc if x.get("account") in ("us", "Us")), {})
    return {"our_followers": (view().get("connected") or {}).get("instagram_followers"),
            "listing_prices": {p["title"][:40]: p["price_aed"] for p in ls[:60]},
            "most_expensive": f"{top.get('title')} ({top.get('ref')}) AED {top.get('price_aed'):,}" if top else "",
            "most_expensive_price": top.get("price_aed"), "competitors": [a["account"] for a in acc],
            "followers": {a["account"]: a.get("followers") for a in acc},
            "next_post": nxt.get("title") or nxt.get("label") or str(nxt)[:120],
            "our_last_post": {k: own[0].get(k) for k in ("likes", "comments", "caption")}}


def chat_open():
    if not PG.locator(".mchat:not([hidden])").count():
        PG.click("#talkbtn"); PG.wait_for_selector(".mchat:not([hidden]) #mc-text", timeout=15000)


def ask(q: str, wait: int = 120000) -> str:
    n = PG.locator(".mchat .m.lead").count()
    PG.fill("#mc-text", q); PG.press("#mc-text", "Enter")
    PG.wait_for_function(f"document.querySelectorAll('.mchat .m.lead').length > {n}", timeout=wait)
    LAST["yes"] = PG.locator(".mchat .m.lead").nth(n).locator(".yesno").count() > 0  # buttons on THIS answer only
    return PG.locator(".mchat .m.lead").nth(n).inner_text().replace("Yes\nNo", "").strip()


LAST = {"yes": False}


def lead_facts() -> str:
    """Exactly what the lead was given: the judge checks the answer against the same facts."""
    from diwan.agents import lead_chat
    return "Standing instructions: " + lead_chat.SYSTEM[:1500] + "\n\nThe studio's data:\n" + lead_chat.context(office(), "judge", "MC-1204")


PA = json.loads((Path(__file__).resolve().parents[1] / "evals" / "pa_questions.json").read_text()) if (Path(__file__).resolve().parents[1] / "evals" / "pa_questions.json").exists() else []


HARD = json.loads((Path(__file__).resolve().parents[1] / "evals" / "pa_hard.json").read_text()) if (Path(__file__).resolve().parents[1] / "evals" / "pa_hard.json").exists() else []


def r2h():
    """The hard bank: false premises, trick numbers, multi-step reasoning, contradictions, rule-breaking requests, Arabic, memory."""
    r2(HARD, label="Lead (hard)")


def r2(bank=None, label="Lead"):
    studio("MC-1204", "run")
    chat_open()
    F = facts_now()
    facts = json.dumps(F, default=str)[:2500]
    for q in (bank if bank is not None else PA):
        @case(f"{label}: {q['q'][:70]}", q["rule"])
        def _(q=q):
            a = ask(q["q"])
            has_yes = LAST["yes"]
            checks = []
            if q.get("must"):
                digits = re.sub(r"[,\s]", "", a)
                for m in q["must"]:
                    v = F.get(m, m)
                    if isinstance(v, dict):  # every number in it must be in the answer
                        miss = [k for k, n in v.items() if n is not None and str(n) not in digits]
                        checks.append((f"{m}: {miss[:3]}", not miss))
                    elif isinstance(v, (int, float)):
                        checks.append((m, str(int(v)) in digits))
                    elif re.fullmatch(r"\d+", str(v)):
                        checks.append((m, str(v) in digits))
                    else:
                        checks.append((m, str(v).lower()[:40] in a.lower()))
            if q.get("must_not"):
                for m in q["must_not"]:
                    checks.append((f"not '{m}'", m.lower() not in a.lower()))
            if q.get("pending") is not None and not q.get("then"):
                checks.append(("asks for a yes" if q["pending"] else "no yes asked", has_yes == q["pending"]))
            elif q.get("pending") is not None:
                checks.append(("asks for a yes" if q["pending"] else "no yes asked", has_yes == q["pending"]))
            if q.get("then"):
                yn = PG.locator(".mchat .yesno button", has_text=q["then"])
                if yn.count():
                    n = PG.locator(".mchat .m.lead").count()
                    yn.last.click()
                    PG.wait_for_function(f"document.querySelectorAll('.mchat .m.lead').length > {n}", timeout=180000)
                    a2 = PG.locator(".mchat .m.lead").nth(n).inner_text()
                    a = a + "\n→ after " + q["then"] + ": " + a2
                    for m in q.get("after_must", []):
                        checks.append((f"after: {m}", m.lower() in a2.lower()))
            j = judge.answer(q["q"], a, lead_facts()) or {}
            checks.append(("plain text, no markdown", "**" not in a and not re.search(r"^\s*[-*•] |^#", a, re.M)))
            works = all(ok for _, ok in checks) if checks else True
            sense = (j.get("score") or 0) >= 4 and j.get("true_to_facts", True)
            return {"works": works, "sense": sense, "score": j.get("score"), "detail": f"{[m for m, ok in checks if not ok]} · judge {j.get('score')}: {j.get('why', '')[:120]} · A: {a[:200]}",
                    "answer": a}
        _()
    shot("r2-chat")

    @case("Lead: a pending change survives a reload", "After a reload, a change still waiting shows its Yes and No buttons")
    def _():
        ask("Plan the next week for me.")
        had = PG.locator(".mchat .yesno").count() > 0
        PG.reload(); PG.wait_for_selector("select[aria-label=Listing] option", state="attached", timeout=60000); PG.wait_for_timeout(1500)
        chat_open(); PG.wait_for_timeout(2500)
        after = PG.locator(".mchat .yesno").count() > 0
        return {"works": had and after, "detail": f"Yes/No before reload {had}, after {after}"}
    _()


# =====================================================================================================================
# shared for making posts
# =====================================================================================================================

DIALOG = {"mode": "accept", "text": "Too salesy for this audience"}


def wait_view(ref: str, pred, timeout: int = 600, every: float = 6, note: str = "") -> dict:
    t = time.time()
    while time.time() - t < timeout:
        d = view(ref)
        if pred(d):
            return d
        banner(f"{CUR['round']} · waiting: {note} ({int(time.time() - t)}s)")
        time.sleep(every)
    raise TimeoutError(f"waited {timeout}s for {note}")


def options(d: dict) -> list[dict]:
    """The scripts waiting to be picked: only the newest request's (an older one left open is not this run's)."""
    reqs = [a for a in d["approvals"] if a.get("options")]
    return [o for o in (reqs[-1]["options"] if reqs else [])]


def req(d: dict, kind: str) -> dict | None:
    return next((a for a in d["approvals"] if a.get("kind") == kind), None)


def brand_name() -> str:
    b = api("/api/brand")
    for k in ("values", "profile", "fields"):
        if isinstance(b.get(k), dict) and b[k].get("name"):
            v = b[k]["name"]
            return v.get("value") if isinstance(v, dict) else v
    return "Diwan Realty"


def media(served: str) -> Path:
    return Path(os.environ["DIWAN_MEDIA"]) / Path(served).name


def score_scripts(opts: list[dict], context: str, price=None, about_brand=False) -> tuple[list, list]:
    checks, scores = [], []
    for o in opts:
        cs = chk.script(o, brand_name=brand_name(), price=price, about_brand=about_brand)
        checks.append([x for x in cs if not x["ok"]])
        kind = {"carousel": "carousel (the hook on the first slide, one line per slide)", "image": "single-photo post (the hook on the photo, the lines are the caption)",
                "graphic": "graphic post"}.get(o.get("format") if o.get("slides") else "", "short-video script")
        j = judge.text(kind, "\n".join([o["hook_en"], *o["lines_en"]]), context) or {}
        scores.append((j.get("score"), j.get("why", "")[:100], j.get("makes_sense")))
    return checks, scores


def run_and_wait_scripts(ref: str, flow: str) -> dict:
    """Run it and wait for scripts written by THIS run: scripts left waiting from before are not measured."""
    old = {o["id"] for o in options(view(ref))}
    studio(ref, "run")
    PG.locator("#runbtn").click()
    d = wait_view(ref, lambda d: len([o for o in options(d) if o["id"] not in old]) >= 2, timeout=720, note="three new scripts")
    FRESH[ref] = {o["id"] for o in options(d) if o["id"] not in old}
    return d


FRESH: dict[str, set] = {}


def pick(ref: str, i: int | None = None):
    """Use this one on the first script with nothing to fix (a script with problems is refused, as it should be)."""
    studio(ref, "run")
    if i is None:
        opts = options(view(ref))
        i = next((k for k, o in enumerate(opts) if not o.get("problems")), 0)
    PG.locator(".opt").nth(i).locator("button", has_text="Use this one").click()
    LAST["pick_toast"] = toast_text(2500)


def finish_post(ref: str, d: dict) -> dict:
    """After a pick, what the post became: video or pictures, caption, versions, slot, and its checks and scores."""
    m = d["made"]
    out = {"checks": [], "scores": {}, "evidence": []}
    name = brand_name()
    if m.get("cut"):
        cs, frames = chk.video(media(m["cut"]["served"]), hook=(m.get("script") or {}).get("hook_en", ""), brand_name=name)
        out["checks"] += cs
        out["evidence"] += [str(f) for f in frames]
        out["scores"]["video"] = judge.pictures("short video (three frames: start, middle, end)", frames, ref)
    if m.get("slides"):
        paths = [media(s.get("served") or s.get("path", "")) for s in m["slides"].get("images", m["slides"].get("slides", []))]
        for p, s in zip(paths, m["slides"].get("images", m["slides"].get("slides", []))):
            out["checks"] += chk.image(p, brand_name=name, words_on=s.get("text", ""))
        out["evidence"] += [str(p) for p in paths]
        out["scores"]["pictures"] = judge.pictures("social post pictures", paths, ref)
    if m.get("cover"):
        cov = [media(o["served"]) for o in m["cover"]["options"]]
        out["checks"] += [x for p in cov for x in chk.image(p, expect=None)]
    if m.get("post text"):
        t = m["post text"]["text"]
        out["checks"] += chk.caption(t, "Instagram", brand_name=name) + chk.code_word(m["post text"].get("code", ""))
        out["scores"]["caption"] = judge.text("Instagram caption", t, ref)
    if m.get("versions"):
        for plat, txt in (m["versions"].get("versions") or {}).items():
            out["checks"] += chk.caption(txt, plat)
    return out


# =====================================================================================================================
# R3 · a listing reel, end to end, to the approval gate
# =====================================================================================================================

L = os.environ.get("RT_LISTING", "COM-S-48501-NH-5")


def r3():
    lst = next((x for x in view()["listings"] if x["ref"] == L), {})
    from diwan.agents import studio as st
    price = st._listing(office(), L).get("price_aed")

    @case("Run a listing: research, idea and three scripts", "Three scripts on different angles appear under Your turn, each passing the code checks; each scored blind")
    def _():
        d = run_and_wait_scripts(L, "listing reel")
        opts = [o for o in options(d) if o["id"] in FRESH[L]]
        from diwan.agents import studio as st
        bad, scores = score_scripts(opts, f"a short post for this listing. Every fact the writer had (anything else is invented): {st._brief(office(), L)}", price=price)
        angles = [o["angle"] for o in opts]
        avg = sum(s[0] or 0 for s in scores) / max(1, len(scores))
        shot("r3-scripts")
        return {"works": len(opts) == 3 and len(set(angles)) == 3 and not any(bad), "sense": avg >= 4, "score": round(avg, 1),
                "detail": f"angles {angles} · failed checks {[[x['check'] for x in b] for b in bad]} · scores {scores}"}
    _()

    @case("Ask for change with nothing typed is refused", "An empty change shows 'Say what to change' and nothing is sent")
    def _():
        studio(L, "run")
        before = [o["id"] for o in options(view(L))]
        PG.locator(".opt").nth(1).locator("button", has_text="Ask for change").click()
        t = toast_text(1200)
        after = [o["id"] for o in options(view(L))]
        return {"works": before == after, "detail": f"toast: {t[:80]} · options unchanged {before == after}"}
    _()

    @case("Ask for change rewrites only that script, and the change is applied", "Script 2 comes back revised with a shorter hook that opens on the price; scripts 1 and 3 stay the same")
    def _():
        studio(L, "run")
        d0 = view(L)
        o0 = options(d0)
        PG.locator(".opt").nth(1).locator("input.change").fill("Make the hook shorter and open with the price")
        PG.locator(".opt").nth(1).locator("button", has_text="Ask for change").click()
        d = wait_view(L, lambda d: any(o.get("revises") == o0[1]["id"] for o in options(d)), timeout=400, note="revised script 2")
        o1 = options(d)
        new = next(o for o in o1 if o.get("revises") == o0[1]["id"])
        same = [o["id"] for o in o1 if o["id"] in (o0[0]["id"], o0[2]["id"])]
        shorter = len(chk.words(new["hook_en"])) <= len(chk.words(o0[1]["hook_en"]))
        has_price = bool(re.search(r"\d{3}|\d+(\.\d+)?\s*(million|m\b)", new["hook_en"], re.I))
        return {"works": len(same) == 2 and shorter, "sense": has_price, "detail": f"{o0[1]['hook_en']!r} → {new['hook_en']!r} · others kept {len(same)}/2"}
    _()

    @case("Send all back, then Cancel the reason box: nothing changes", "Cancelling the 'what is wrong' box keeps the three scripts")
    def _():
        studio(L, "run")
        before = [o["id"] for o in options(view(L))]
        DIALOG["mode"] = "dismiss"
        btn("Send all back", "#turn").click(); PG.wait_for_timeout(2500)
        DIALOG["mode"] = "accept"
        return {"works": [o["id"] for o in options(view(L))] == before, "detail": "kept after Cancel"}
    _()

    @case("Write my own script: checked, problems listed, two more ways written", "My script appears as an option with its problems listed and 2 other versions")
    def _():
        studio(L, "run")
        PG.locator("#ownbox summary").click()
        PG.fill("#owntext", "Corner villa, private garden, ready now\nFour bedrooms and a maid's room\nA garden on two sides\nFreehold, so you own it outright\nMinutes from the community park\nMessage us to book a viewing")
        PG.click("#ownsend")
        PG.wait_for_function("document.querySelector('#ownmsg').textContent.includes('Pick one above') || document.querySelector('#ownmsg').className.includes('bad')", timeout=300000)
        msg = text_of("#ownmsg")
        d = view(L)
        own = [o for o in options(d) if o.get("own")]
        return {"works": bool(own) and "other way" in msg, "detail": f"{msg[:120]} · own option problems: {own[0].get('problems') if own else None}"}
    _()

    @case("Use this one: the film list goes to the broker and the other options go", "After the pick, a film list exists, the script is approved and no other options remain")
    def _():
        d0 = view(L)
        first = next((o for o in options(d0) if not o.get("problems")), options(d0)[0])
        own = next((k for k, o in enumerate(options(d0)) if o.get("problems")), None)
        refused = ""
        if own is not None:  # a script with something to fix must be refused
            studio(L, "run"); PG.locator(".opt").nth(own).locator("button", has_text="Use this one").click(); refused = toast_text(2500)
        pick(L)
        if first.get("slides"):  # a carousel or a single photo: nothing to film, the pictures are made straight away
            d = wait_view(L, lambda d: bool(req(d, "publish")), timeout=600, every=8, note="pictures and the publish request")
            return {"works": not options(d) and (own is None or "can't be used" in refused), "detail": f"refused the script with problems: {refused[:90]!r} · picked {first['angle']} · "
                    f"{first.get('format')}: {len((d['made'].get('slides') or {}).get('images', []))} pictures made, no filming needed"}
        d = wait_view(L, lambda d: bool(d["made"].get("film list")) and d.get("script_approved"), timeout=300, note="film list")
        left = options(d)
        film = d["made"]["film list"]
        manual("listing reel", "film it, or press Make free video", "with photos on the listing, make the free video by itself after the pick and only ask for filming when a person is needed")
        return {"works": not left and (own is None or "can't be used" in refused), "detail": f"refused the script with problems: {refused[:90]!r} · picked {first['angle']} · film list for {film.get('who')} {film.get('when')}: {len(film['shots'])} shots · options left {len(left)}"}
    _()

    @case("Make AI video without HeyGen says what is missing", "The AI presenter button is disabled and says Connect HeyGen")
    def _():
        if view(L)["made"].get("slides"):
            return {"works": True, "detail": "not a reel: this listing was chosen as pictures, so there is no video to make"}
        studio(L, "run")
        b = btn("Make AI video", "#turn")
        return {"works": b.count() == 1 and not b.is_enabled() and "HeyGen" in text_of("#turn"), "detail": "disabled with the HeyGen note"}
    _()

    @case("Make free video, then editing, cover, caption and the approval request", "A captioned 9:16 video, two covers, a caption with a code word, platform versions and a publish request; each judged")
    def _():
        if not view(L)["made"].get("slides"):
            studio(L, "run")
            btn("Make free video", "#turn").click()
        d = wait_view(L, lambda d: bool(req(d, "publish")), timeout=900, every=10, note="video or pictures, and the publish request")
        r = finish_post(L, d)
        fails = [x for x in r["checks"] if not x["ok"]]
        sc = {k: (v or {}).get("score") for k, v in r["scores"].items()}
        why = {k: (v or {}).get("why", "")[:120] for k, v in r["scores"].items()}
        shot("r3-approval")
        return {"works": bool(d["made"].get("cut") or d["made"].get("slides")) and bool(req(d, "publish")), "sense": all((s or 0) >= 4 for s in sc.values()) and not fails,
                "score": sc, "detail": f"failed checks: {[(x['check'], x['detail']) for x in fails][:8]} · scores {sc} · {why}", "evidence": r["evidence"]}
    _()

    @case("Approval: a time in the past is refused and the card stays", "Approve for this time with a past time says so; the request is still waiting")
    def _():
        studio(L, "run")
        rid = req(view(L), "publish")["id"]
        PG.fill(f"#at-{rid}", "2026-01-01T10:00")
        btn("Approve for this time", "#turn").click()
        t = toast_text(2500)
        still = bool(req(view(L), "publish"))
        return {"works": still, "sense": "past" in t.lower() or "after now" in t.lower() or "not published" in t.lower(), "detail": t[:160]}
    _()

    @case("Approval: Ask for change 'shorter caption' goes to the writer and comes back checked", "The caption gets shorter, keeps its code word, and the post waits for approval again")
    def _():
        d0 = view(L)
        t0 = d0["made"]["post text"]
        studio(L, "run")
        rid = req(d0, "publish")["id"]
        PG.fill(f"#chg-{rid}", "Shorter caption, two short lines and the hashtags")
        btn("Ask for change", "#turn").click()
        d = wait_view(L, lambda d: d["made"].get("post text", {}).get("id") != t0["id"] and bool(req(d, "publish")), timeout=400, note="the new caption")
        t1 = d["made"]["post text"]
        return {"works": len(t1["text"]) < len(t0["text"]) and t0.get("code", "x") in t1["text"], "detail": f"{len(t0['text'])} → {len(t1['text'])} chars · code kept {t0.get('code') in t1['text']}"}
    _()

    @case("Approval: Approve for this time and Post now are refused with publishing off, and the card stays", "Both say what is missing (the public address); nothing is published; the request still waits")
    def _():
        studio(L, "run")
        btn("Approve for this time", "#turn").click()
        a = toast_text(3000)
        PG.wait_for_timeout(1500)
        studio(L, "run")
        b = btn("Post now", "#turn")
        b2 = b.click() if b.count() else None
        p = toast_text(3000)
        d = view(L)
        return {"works": not d["made"].get("published") and bool(req(d, "publish") or d["made"].get("scheduled")), "detail": f"approve: {a[:100]} · post now: {p[:100]}"}
    _()

    @case("Stop this post: Cancel keeps it; a reason removes everything made for it", "Cancel leaves the request; Stop with a reason leaves no request, no postable video or caption, and lists it under Came off")
    def _():
        studio(L, "run")
        DIALOG["mode"] = "dismiss"
        btn("Stop this post", "#turn").click(); PG.wait_for_timeout(2000)
        kept = bool(req(view(L), "publish"))
        DIALOG.update(mode="accept", text="The villa photos look dull, not the quality we want")
        studio(L, "run")
        btn("Stop this post", "#turn").click(); PG.wait_for_timeout(4000)
        d = view(L)
        off = any(x.get("ref") == L for x in api("/api/marketing/plan").get("stopped", []))
        return {"works": kept and not req(d, "publish") and not d["made"].get("cut"), "sense": off,
                "detail": f"Cancel kept {kept} · after stop: request {bool(req(d, 'publish'))}, cut {bool(d['made'].get('cut'))} · Came off lists it {off}"}
    _()


# =====================================================================================================================
# R4 · occasions: Eid al Adha, National Day, Ramadan
# =====================================================================================================================

PHOTOS: list[Path] = []


def photos(n: int) -> list[str]:
    """Real photos at a usable size: the listing's own (downloaded once), standing in for event photos."""
    if not PHOTOS:
        from diwan.agents import studio as st
        import httpx
        urls = (st._listing(office(), L).get("photos") or [])[:6]
        for i, u in enumerate(urls):
            p = OUT / f"photo-{i}.jpg"
            if not p.exists():
                p.write_bytes(httpx.get(u, timeout=60, follow_redirects=True).content)
            PHOTOS.append(p)
    return [str(p) for p in PHOTOS[:n]]


def moment(title: str, what: str, until: str = "", files: list[str] | None = None) -> str:
    studio(tab="run")
    sm = PG.locator("summary", has_text="Something just happened")
    if sm.count():
        sm.first.click()
    PG.fill("#jm-title", title)
    PG.fill("#jm-what", what)
    if until:
        PG.fill("#jm-until", until)
    if files:
        PG.set_input_files("#jm-files", files)
    PG.click("#jm-add")
    PG.wait_for_timeout(4000)
    return text_of("#jm-msg")


def next_ref() -> str | None:
    j = view().get("journey") or {}
    return (j.get("next") or {}).get("ref")


EID = ("Eid al Adha 2027", "Eid al Adha falls on 16 May 2027. The Diwan Realty team wishes everyone celebrating Eid al Adha a blessed and peaceful Eid "
       "with family and friends. Our office is closed for the Eid holiday from 15 to 18 May and opens again on 19 May.")


def occasion(title: str, what: str, files: list[str] | None, fmt: str | None, label: str) -> dict:
    """One occasion post from typing it in to the approval request. Returns its record for the case."""
    msg = moment(title, what, "2027-05-18", files)
    ref = next_ref()
    if not ref:
        raise RuntimeError(f"the moment did not become the next post: {msg}")
    manual(label, "type the occasion and its facts by hand", "propose UAE occasions from a calendar ahead of the date, with the greeting facts prefilled")
    j = view()["journey"]
    shape = (j.get("shape") or {}).get("format")
    if fmt and fmt != shape:
        studio(tab="run")
        PG.select_option("#jfmt", fmt); PG.wait_for_timeout(2500)
        manual(label, f"change the format to {fmt}", "pick the format from what is trending and what exists")
        shape = (view()["journey"].get("shape") or {}).get("format")
    studio(tab="run")
    PG.click("#jmake")
    d = wait_view(ref, lambda d: len(options(d)) >= 2, timeout=720, note=f"{label}: scripts")
    opts = options(d)
    bad, scores = score_scripts(opts, f"{title}: a greeting post from a real-estate brokerage, not a sales post. Facts: {what}", about_brand=True)
    selling = [o["hook_en"] for o in opts if re.search(r"\b(buy|price|aed|offer|discount|listing|invest)\b", " ".join([o["hook_en"], *o["lines_en"]]), re.I)]
    arabic = [bool(re.search(r"[؀-ۿ]", o.get("hook_ar", ""))) for o in opts]
    pick(ref)
    if shape == "reel":
        d = wait_view(ref, lambda d: d.get("script_approved"), timeout=300, note=f"{label}: pick")
        studio(ref, "run")
        if btn("Make the frames with AI", "#turn").count():
            btn("Make the frames with AI", "#turn").click()
            manual(label, "press Make the frames with AI, then Make free video", "make the frames and the video by itself after the pick")
            wait_view(ref, lambda d: (d.get("free_video") or {}).get("photos", 0) > 0, timeout=600, every=10, note=f"{label}: AI frames")
            studio(ref, "run")
        btn("Make free video", "#turn").click()
    d = wait_view(ref, lambda d: bool(req(d, "publish")), timeout=900, every=10, note=f"{label}: post made and waiting for approval")
    r = finish_post(ref, d)
    slot = d["made"].get("slot") or {}
    on_day = (slot.get("at") or "")[:10] == "2027-05-16"
    slides_text = json.dumps(d["made"].get("slides") or {})
    return {"ref": ref, "format": shape, "opts": opts, "bad": bad, "scores": scores, "selling": selling, "arabic_hook": arabic,
            "arabic_on_image": bool(re.search(r"[؀-ۿ]", slides_text)), "post": r, "slot": slot.get("at"), "on_day": on_day,
            "code": (d["made"].get("post text") or {}).get("code")}


def report_occasion(o: dict) -> dict:
    fails = [x for x in o["post"]["checks"] if not x["ok"]]
    sc = {k: (v or {}).get("score") for k, v in o["post"]["scores"].items()}
    pics = o["post"]["scores"].get("pictures") or o["post"]["scores"].get("video") or {}
    avg = sum(s[0] or 0 for s in o["scores"]) / max(1, len(o["scores"]))
    sense = avg >= 4 and not o["selling"] and o["on_day"] and all((s or 0) >= 4 for s in sc.values()) and pics.get("company_shown") and pics.get("logo_shown")
    return {"works": True, "sense": bool(sense), "score": {"scripts": round(avg, 1), **sc},
            "detail": (f"format {o['format']} · scripts {[s[0] for s in o['scores']]} · selling hooks {len(o['selling'])} · Arabic hook {o['arabic_hook']} · "
                       f"Arabic on images {o['arabic_on_image']} · posts {o['slot']} (Eid is 2027-05-16: on the day {o['on_day']}) · code {o['code']} · "
                       f"company on picture {pics.get('company_shown')} · logo {pics.get('logo_shown')} · professional {pics.get('professional')} · "
                       f"failed checks {[(x['check'], x['detail']) for x in fails][:6]} · judge: {pics.get('why', '')[:140]}"),
            "evidence": o["post"]["evidence"]}


def stop_current(ref: str, why: str):
    DIALOG.update(mode="accept", text=why)
    studio(ref, "run")
    if btn("Stop this post", "#turn").count():
        btn("Stop this post", "#turn").click(); PG.wait_for_timeout(3000)


def occasion_cal(key: str, label: str, fmt: str | None, ui: bool) -> dict:
    """An occasion from the calendar, the way a manager meets it: Prepare the greeting (or the API when it is further
    than the 30 days the panel shows), then pick, then the finished post at the approval gate."""
    from diwan import occasions
    o = occasions.get(key)
    if ui:
        studio(tab="run")
        row = PG.locator(".row.coming", has_text=o["title"])
        had = [r for r, t in __import__("diwan.topics", fromlist=["items"]).items(office()).items() if t.get("occasion") == key]
        if not row.count() and not had:
            raise RuntimeError(f"{o['title']} is not offered under Coming up")
        if row.count():
            row.locator("button", has_text="Prepare the greeting").click()
            PG.wait_for_timeout(3000)
        ref = [r for r, t in __import__("diwan.topics", fromlist=["items"]).items(office()).items() if t.get("occasion") == key][-1]  # prepared now, or in an earlier run
    else:
        ref = api("/api/occasions/prepare", {"key": key})["ref"]
    if fmt:
        api("/api/moments/format", {"ref": ref, "format": fmt, "by": "maya"})
        manual(label, f"choose {fmt}", "pick the format from what wins for competitors and what exists")
    d = wait_view(ref, lambda d: len(options(d)) >= 2, timeout=720, note=f"{label}: scripts")
    opts = options(d)
    bad, scores = score_scripts(opts, f"{o['title']}: a greeting post from a Dubai brokerage, not a sales post.", about_brand=True)
    selling = [o2["hook_en"] for o2 in opts if re.search(r"\b(buy|price|aed|offer|discount|listing|invest|message us)\b", " ".join([o2["hook_en"], *o2["lines_en"]]), re.I)]
    director = [(o2.get("director") or {}).get("score") for o2 in opts]
    pick(ref)
    shape = (view(ref)["made"].get("script") or {}).get("format")
    if fmt == "reel":
        wait_view(ref, lambda d: d.get("script_approved"), timeout=300, note=f"{label}: pick")
        studio(ref, "run")
        if btn("Make the frames with AI", "#turn").count():
            btn("Make the frames with AI", "#turn").click()
            manual(label, "press Make the frames with AI, then Make free video", "make the frames and the video by itself after the pick")
            wait_view(ref, lambda d: (d.get("free_video") or {}).get("photos", 0) > 0, timeout=600, every=10, note=f"{label}: AI frames")
            studio(ref, "run")
        btn("Make free video", "#turn").click()
    d = wait_view(ref, lambda d: bool(req(d, "publish")), timeout=900, every=10, note=f"{label}: waiting for approval")
    r = finish_post(ref, d)
    slot = d["made"].get("slot") or {}
    at = (req(d, "publish") or {}).get("text", "")
    studio(ref, "run"); shot(f"r4-{slug(label)}")
    return {"ref": ref, "format": shape or fmt, "opts": opts, "bad": bad, "scores": scores, "selling": selling, "director": director,
            "arabic_hook": [bool(re.search(r"[\u0600-\u06ff]", x.get("hook_ar", ""))) for x in opts],
            "arabic_on_image": None, "post": r, "slot": at, "on_day": o["on"] in json.dumps(d["approvals"]) or o["on"][5:] in at or _on(at, o["on"]),
            "code": (d["made"].get("post text") or {}).get("code"), "caption": (d["made"].get("post text") or {}).get("text", "")}


def _on(text: str, day: str) -> bool:
    from datetime import date
    dd = date.fromisoformat(day)
    return dd.strftime("%a") in text and str(dd.day) in text


def report_occasion(o: dict) -> dict:
    fails = [x for x in o["post"]["checks"] if not x["ok"]]
    sc = {k: (v or {}).get("score") for k, v in o["post"]["scores"].items()}
    pics = o["post"]["scores"].get("pictures") or o["post"]["scores"].get("video") or {}
    avg = sum(s[0] or 0 for s in o["scores"]) / max(1, len(o["scores"]))
    cap = o.get("caption", "")
    greeting_ok = "Say " not in cap and not re.search(r"message us", cap, re.I)
    sense = avg >= 4 and not o["selling"] and o["on_day"] and greeting_ok and all((s or 0) >= 4 for s in sc.values()) and pics.get("company_shown") and pics.get("logo_shown")
    return {"works": True, "sense": bool(sense), "score": {"scripts": round(avg, 1), **sc},
            "detail": (f"format {o['format']} · scripts {[s[0] for s in o['scores']]} (Director {o['director']}) · selling {len(o['selling'])} · Arabic hook {o['arabic_hook']} · "
                       f"approval says: {o['slot'][:110]!r} · on the day {o['on_day']} · code {o['code']!r} · greeting caption {greeting_ok} · "
                       f"company {pics.get('company_shown')} · logo {pics.get('logo_shown')} · professional {pics.get('professional')} · "
                       f"failed checks {[(x['check'], x['detail']) for x in fails][:6]} · judge: {pics.get('why', '')[:160]}"),
            "caption": cap[:600], "evidence": o["post"]["evidence"]}


def stop_current(ref: str, why: str):
    DIALOG.update(mode="accept", text=why)
    studio(ref, "run")
    if btn("Stop this post", "#turn").count():
        btn("Stop this post", "#turn").click(); PG.wait_for_timeout(3000)


LAST_GREETING: dict = {}


def r4():
    @case("Setup: upload the company logo", "The logo uploads in Setup → Our brand and shows beside the brand")
    def _():
        studio(tab="setup")
        PG.set_input_files("#logofile", os.environ.get("RT_LOGO", str(OUT.parent / "diwan-logo.png")))
        PG.click("#logoup"); PG.wait_for_timeout(2500)
        return {"works": "Saved" in text_of("#logomsg") and PG.locator("#logoimg").is_visible(), "detail": text_of("#logomsg")}
    _()

    @case("UAE National Day is offered by itself 30 days ahead", "Coming up shows National Day (2 Dec) with Prepare the greeting and Not this year")
    def _():
        studio(tab="run")
        t = text_of("#jbody")
        return {"works": "National Day" in t and "Prepare the greeting" in t, "detail": t[-400:], "evidence": [shot("r4-coming")]}
    _()

    for key, label, fmt, ui in (("national-day-2026", "UAE National Day · greeting card (from Coming up)", None, True),
                                ("eid-al-adha-2027", "Eid al Adha · greeting card", None, False)):
        @case(label, "A greeting, not a sale; the company named and its logo on it; posted on the day itself; the caption has the occasion's tags and no code word; judged 4+")
        def _(key=key, label=label, fmt=fmt, ui=ui):
            k = key.replace("-reel", "")
            if key.endswith("-reel"):
                for e in office().log.list():  # the second Eid case needs the occasion free again
                    pass
            o = occasion_cal(k, label, fmt, ui)
            rec = report_occasion(o)
            if k == "eid-al-adha-2027":
                LAST_GREETING["ref"] = o["ref"]  # kept at the approval gate for the change requests below
            else:
                stop_current(o["ref"], "Test finished: clear it for the next variant")
            return rec
        _()

    @case("Last year's competitor Eid posts were read and fed the card", "The study reads every saved competitor around 27 May 2026; either their Eid posts are looked at and the card brief says what wins, or it says plainly that none were found")
    def _():
        from diwan import occasions
        s = occasions.studied(office(), "eid-al-adha-2027") or {}
        accs = s.get("accounts") or []
        return {"works": bool(s) and len(accs) >= 1, "sense": bool(s.get("notes")) or bool(s.get("why")),
                "detail": f"accounts {[(a['account'], a.get('read'), a.get('oldest')) for a in accs]} · posts {[(p['account'], p['at'], p['likes']) for p in s.get('posts', [])]} · "
                          f"notes {json.dumps(s.get('notes', {}))[:300]} · why {s.get('why', '')!r}"}
    _()

    for ask in ("Make it more festive and celebratory, no property in it", "Make the logo bigger", "Put the greeting in Arabic too"):
        @case(f"Ask for change on the Eid card: '{ask}'", "Only the picture is made again (no script round); the new card does what was asked, judged blind against the old one; the approval card says what was done")
        def _(ask=ask):
            ref = LAST_GREETING.get("ref")
            if not ref:
                raise RuntimeError("no Eid card waiting at the approval gate")
            d0 = view(ref)
            s0 = d0["made"]["slides"]
            studio(ref, "run")
            rid = req(d0, "publish")["id"]
            PG.fill(f"#chg-{rid}", ask)
            btn("Ask for change", "#turn").click()
            d = wait_view(ref, lambda d: (d["made"].get("slides") or {}).get("id") != s0["id"] and bool(req(d, "publish")), timeout=400, every=8, note=f"change: {ask}")
            s1 = d["made"]["slides"]
            before = [media(x["served"]) for x in s0["images"]]
            after = [media(x["served"]) for x in s1["images"]]
            j = judge.changed(ask, before, after)
            ch = s1.get("change") or {}
            note = (req(d, "publish") or {}).get("text", "")
            studio(ref, "run"); ev = shot(f"r4-change-{slug(ask)[:24]}")
            return {"works": bool(ch) and not options(d) and "Your change" in note, "sense": bool(j and j.get("landed")), "score": j.get("score") if j else None,
                    "detail": f"applied {ch.get('applied')} · Director says done {ch.get('done')}: {ch.get('how', '')[:120]} · judge landed {j.get('landed') if j else None}: {(j or {}).get('why', '')[:160]}",
                    "evidence": [str(p) for p in before + after] + [ev]}
        _()
    if LAST_GREETING.get("ref"):
        stop_current(LAST_GREETING["ref"], "Test finished: clear it for the next variant")


# =====================================================================================================================
# R5 · an informational topic, to camera
# =====================================================================================================================

def r5():
    from diwan import topics
    t = next((r for r, x in topics.items(office()).items() if x["source"] == "typed"), None) or "K3"

    @case("Informational video: to-camera scripts from the topic's facts, AI frames, free video", "Scripts are spoken to camera with only the topic's facts; frames pass the Director; the video is made and judged")
    def _():
        d = run_and_wait_scripts(t, "topic")
        opts = [o for o in options(d) if o["id"] in FRESH[t]]
        bad, scores = score_scripts(opts, f"an informational video on {t}")
        fmt = {o.get("format") for o in opts}
        pick(t)
        wait_view(t, lambda d: d.get("script_approved"), timeout=300, note="pick")
        studio(t, "run")
        if btn("Make the frames with AI", "#turn").count():
            btn("Make the frames with AI", "#turn").click()
            wait_view(t, lambda d: (d.get("free_video") or {}).get("photos", 0) > 0, timeout=600, every=10, note="AI frames")
            studio(t, "run")
        btn("Make free video", "#turn").click()
        d = wait_view(t, lambda d: bool(req(d, "publish")), timeout=900, every=10, note="video and approval")
        r = finish_post(t, d)
        sc = {k: (v or {}).get("score") for k, v in r["scores"].items()}
        avg = sum(s[0] or 0 for s in scores) / max(1, len(scores))
        rv = (d.get("free_video") or {}).get("review") or {}
        stop_current(t, "Test finished")
        return {"works": fmt == {"to camera"} and bool(d["made"].get("cut")), "sense": avg >= 4 and all((s or 0) >= 4 for s in sc.values()),
                "score": {"scripts": round(avg, 1), **sc}, "evidence": r["evidence"],
                "detail": f"formats {fmt} · scripts {[s[0] for s in scores]} · Director {rv.get('score')} · failed {[(x['check'], x['detail']) for x in r['checks'] if not x['ok']][:6]} · {sc}"}
    _()


# =====================================================================================================================
# R6 + R12 · the plan, a month of formats, and the reasons
# =====================================================================================================================

def make_plan(days: int, per: int) -> dict:
    studio(tab="plan")
    PG.click("#pl-make"); PG.wait_for_timeout(800)
    PG.select_option("#pl-ask select[aria-label='How far ahead']", str(days))
    if days > 1:
        PG.select_option("#pl-ask select[aria-label='Posts a week']", str(per))
    PG.locator("#pl-ask button", has_text="Make the plan").click()
    PG.wait_for_function("!document.querySelector('#pl-ask button') || !document.querySelector('#pl-ask button').disabled", timeout=300000)
    PG.wait_for_timeout(2500)
    return api("/api/marketing/plan")


def r6():
    for per in (5,):
        @case(f"A month at {per} posts a week: formats mixed every week, following what wins", "No week is one format or over 60% one format; each day says why; reasons judged 4+")
        def _(per=per):
            m = make_plan(31, per)
            days = [d for d in m["days"] if d.get("ref")]
            fm = chk.plan(days)
            from collections import Counter
            counts = Counter(d.get("format") for d in days)
            sample = "\n".join(f"{d['date']}: {d.get('title')} · {d.get('job')} · {d.get('format')} · why: {d.get('why')}" for d in days[:8])
            j = judge.text("content plan (each day with its reason)", sample, "a Dubai brokerage's month of Instagram posts") or {}
            shot(f"r6-plan-{per}")
            fails = [x for x in fm if not x["ok"]]
            return {"works": len(days) >= per * 4 - 1, "sense": not fails and (j.get("score") or 0) >= 4, "score": j.get("score"),
                    "detail": f"{len(days)} days · formats {dict(counts)} · failed {[(x['check'], x['detail']) for x in fails][:4]} · judge: {j.get('why', '')[:140]}"}
        _()

    @case("Plan day buttons: Approve, Change, Remove (Cancel keeps it), and a removed day stays off", "Approve marks it; Change swaps the subject; Remove with a reason empties the day and lists it under Came off; a new plan does not bring it back")
    def _():
        make_plan(14, 5)
        studio(tab="plan")

        def row(d):  # the list shows the plan's days in order: the row for this day, not the n-th row with buttons
            return PG.locator("#pl-days li").nth([x["date"] for x in api("/api/marketing/plan")["days"]].index(d["date"]))

        open_days = lambda: [d for d in api("/api/marketing/plan")["days"] if d.get("ref") and d["state"] == "pending"]  # noqa: E731
        d0 = open_days()[0]
        row(d0).locator("button", has_text="Approve").click(); PG.wait_for_timeout(1500)
        approved = any(d["date"] == d0["date"] and d["state"] == "approved" for d in api("/api/marketing/plan")["days"])
        d1 = open_days()[0]
        row(d1).locator("button", has_text="Change").click(); PG.wait_for_timeout(500)
        sel = row(d1).locator("select")
        taken = {d.get("ref") for d in api("/api/marketing/plan")["days"]}
        alt = [o.get_attribute("value") for o in sel.locator("option").all() if o.get_attribute("value") not in taken][0]
        sel.select_option(alt); row(d1).locator("button", has_text="Save").click(); PG.wait_for_timeout(2000)
        changed = any(d["date"] == d1["date"] and d["ref"] == alt for d in api("/api/marketing/plan")["days"])
        d2 = open_days()[1]
        DIALOG["mode"] = "dismiss"
        row(d2).locator("button", has_text="Remove").click(); PG.wait_for_timeout(1500)
        still = any(d["date"] == d2["date"] and d.get("ref") == d2["ref"] for d in api("/api/marketing/plan")["days"])
        DIALOG.update(mode="accept", text="We don't want graphics, our audience prefers a person talking")
        row(d2).locator("button", has_text="Remove").click(); PG.wait_for_timeout(2500)
        m2 = api("/api/marketing/plan")
        empty = not any(d["date"] == d2["date"] and d.get("ref") for d in m2["days"])
        listed = any(x["date"] == d2["date"] and x["title"] == d2["title"] for x in m2.get("removed", []))
        m3 = make_plan(14, 5)
        back = any(d.get("ref") == d2["ref"] and d["date"] == d2["date"] for d in m3["days"])
        return {"works": approved and changed and still and empty and listed, "sense": not back,
                "detail": f"approved {approved} · changed to {alt} {changed} · Cancel kept {still} · removed empty {empty} · under Came off {listed} · back on next plan {back}"}
    _()

    @case("Write it now writes that day's scripts and they appear under Waiting for you", "Write it now on a day gives 3 scripts and a Read the scripts link")
    def _():
        studio(tab="plan")
        day = next(d for d in api("/api/marketing/plan")["days"] if d.get("ref") and d["state"] != "written")
        PG.locator("#pl-days li").nth([x["date"] for x in api("/api/marketing/plan")["days"]].index(day["date"])).locator("button", has_text="Write it now").click()
        ref = day["ref"]
        d = wait_view(ref, lambda d: len(options(d)) >= 2, timeout=720, note="scripts from Write it now")
        studio(tab="plan")
        has = PG.locator("#pl-wait button", has_text="Read the scripts").count() > 0
        return {"works": has and len(options(d)) >= 2, "detail": f"{len(options(d))} scripts · Read the scripts link {has}"}
    _()


# =====================================================================================================================
# R7 + R13 · learning the user's taste
# =====================================================================================================================

def r7():
    @case("Taste: three 'no graphics' decisions change the next plan; Forget undoes it", "After the decisions, graphics drop on the next plan and What Diwan has learned shows it; Forget brings the old mix back")
    def _():
        from collections import Counter
        m0 = make_plan(31, 5)
        before = Counter(d.get("format") for d in m0["days"] if d.get("ref"))
        gdays = [d for d in m0["days"] if d.get("format") == "graphic"][:3]
        DIALOG.update(mode="accept", text="No graphics please, our clients want to see a real person or the real home")
        studio(tab="plan")
        for d in gdays:
            li = PG.locator("#pl-days li", has_text=d.get("title") or "")
            if li.count():
                li.first.locator("button", has_text="Remove").click(); PG.wait_for_timeout(2500)
        learned = api("/api/marketing/learned")
        m1 = make_plan(31, 5)
        after = Counter(d.get("format") for d in m1["days"] if d.get("ref"))
        studio(tab="plan")
        learn_text = text_of("#pl-learn")
        f = PG.locator("#pl-learn button", has_text="Forget")
        if f.count():
            f.first.click(); PG.wait_for_timeout(2000)
        m2 = make_plan(31, 5)
        again = Counter(d.get("format") for d in m2["days"] if d.get("ref"))
        return {"works": after.get("graphic", 0) < before.get("graphic", 0) or not gdays, "sense": "graphic" in learn_text.lower(),
                "detail": f"graphics {before.get('graphic', 0)} → {after.get('graphic', 0)} → after Forget {again.get('graphic', 0)} · removed {len(gdays)} · learned: {learn_text[:160]}"}
    _()

    @case("Style notes come from the person's choices", "After picks, changes and stops, Setup → Style notes lists what was learned")
    def _():
        studio(tab="setup")
        s = text_of("#stylelist")
        return {"works": len(s) > 40, "detail": s[:240]}
    _()


# =====================================================================================================================
# R8 · results and attribution · R9 · facts change
# =====================================================================================================================

def r8():
    @case("Results tab: every section shows real content", "Today, Where each post is, What each post brought, Campaigns all render without broken text")
    def _():
        studio(tab="results")
        body = text_of("#tab-results")
        return {"works": len(body) > 200 and not broken_text(body), "detail": f"{len(body)} chars · broken {broken_text(body)}", "evidence": [shot("r8-results")]}
    _()

    @case("A campaign without a budget is refused; with one it is drafted with the post's code word", "Refusal names the missing budget; the draft carries the code word")
    def _():
        studio(tab="results")
        PG.locator("#cp-new summary").click()
        PG.fill("#cp-goal", "Leads for the villa"); PG.fill("#cp-aud", "Families in Abu Dhabi, 30-55")
        PG.fill("#cp-budget", ""); PG.fill("#cp-days", "7")
        PG.click("#cp-add"); PG.wait_for_timeout(2000)
        no = text_of("#cp-msg")
        PG.fill("#cp-budget", "500"); PG.click("#cp-add"); PG.wait_for_timeout(3000)
        yes = text_of("#cp-msg")
        return {"works": bool(no) and no != yes, "detail": f"no budget: {no[:100]} · with budget: {yes[:120]}"}
    _()


def r9():
    @case("A price change after scripts are written marks them out of date", "Changing the listing's price flags its scripts with Rewrite with the new facts")
    def _():
        d = run_and_wait_scripts("JVC-88", "price change")
        api("/api/items/listing:JVC-88/edit", {"changes": {"price_aed": 1990000}, "why": "price cut", "by": "layla"})
        d = view("JVC-88")
        stale = [o for o in options(d) if o.get("stale")]
        studio("JVC-88", "run")
        has_btn = btn("Rewrite with the new facts", "#turn").count() > 0
        return {"works": bool(stale) and has_btn, "detail": f"{len(stale)} of {len(options(d))} scripts flagged · button {has_btn}"}
    _()


# =====================================================================================================================
# R10 · the 3D Marketing floor while work happens
# =====================================================================================================================

def r10():
    @case("The Marketing floor moves with real work", "During a run, /ws/floor carries messages for research, writing, checking and handing off; robots show working states; image and video steps also move")
    def _():
        p2 = PG.context.new_page()
        frames: list[dict] = []
        def on_ws(ws):
            if "/ws/floor" in ws.url:
                ws.on("framereceived", lambda f: frames.append({"t": time.time(), "f": f if isinstance(f, str) else ""}))
        p2.on("websocket", on_ws)
        p2.goto(f"{BASE}/web/office3d.html?enter=mkt"); p2.wait_for_timeout(5000)
        api("/api/marketing/run?ref=MC-1204", {})
        t = time.time()
        while time.time() - t < 150:
            p2.wait_for_timeout(5000)
        p2.screenshot(path=str(OUT / "r10-floor.png"))
        kinds, agents = {}, {}
        for fr in frames:
            try:
                for m in json.loads(fr["f"]).get("messages", json.loads(fr["f"]) if isinstance(json.loads(fr["f"]), list) else []):
                    kinds[m.get("type")] = kinds.get(m.get("type"), 0) + 1
                    if m.get("agent"):
                        agents[m["agent"]] = agents.get(m["agent"], 0) + 1
            except Exception:  # noqa: BLE001
                pass
        p2.close()
        steps = kinds.get("agent.step", 0)
        return {"works": len(frames) > 5 and steps > 0, "sense": all(a in agents for a in ("mrival", "mscript")),
                "detail": f"{len(frames)} frames · types {dict(sorted(kinds.items(), key=lambda x: -x[1])[:8])} · agents {dict(sorted(agents.items(), key=lambda x: -x[1])[:10])}",
                "evidence": [str(OUT / 'r10-floor.png')]}
    _()


# =====================================================================================================================
# R11 · every Marketing page, phone width · R14 · platforms
# =====================================================================================================================

def r11():
    for path, tabs in (("studio.html", ("run", "plan", "competitors", "results", "setup")), ("office3d.html?enter=mkt", ()), ("catalog.html", ()), ("knowledge.html", ())):
        for width in (1440, 390):
            @case(f"{path} at {width}px", "No broken text, no sideways scroll, no page errors")
            def _(path=path, tabs=tabs, width=width):
                PG.set_viewport_size({"width": width, "height": 900})
                n0 = len(ERRS)
                PG.goto(f"{BASE}/web/{path}"); PG.wait_for_timeout(4000)
                bad, wide = [], []
                for t in tabs or ("",):
                    if t:
                        PG.click(f"#t-{t}"); PG.wait_for_timeout(1200)
                    body = PG.inner_text("body")
                    bad += broken_text(body)
                    if PG.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2"):
                        wide.append(t or "page")
                PG.set_viewport_size({"width": 1440, "height": 920})
                return {"works": not bad and not wide and len(ERRS) == n0, "detail": f"broken {bad} · sideways scroll on {wide} · new page errors {ERRS[n0:][:3]}"}
            _()


def r14():
    @case("Platforms: Setup offers Facebook and LinkedIn", "Where we post lists Instagram, Facebook, LinkedIn, TikTok and YouTube Shorts")
    def _():
        studio(tab="setup")
        s = text_of("#bz-platforms")
        miss = [p for p in ("Instagram", "Facebook", "LinkedIn", "TikTok", "YouTube") if p not in s]
        return {"works": not miss, "detail": f"offered: {s[:160]} · missing {miss}"}
    _()

    @case("Platforms: each version follows its platform's rules", "Each version made has the right length, hashtags and tone; picture sizes fit the platform")
    def _():
        o = office()
        vs = [e["content"] for e in o.log.list() if e["type"] == "content.made" and e["content"].get("kind") == "versions"]
        if not vs:
            return {"works": None, "detail": "no versions made yet"}
        v = vs[-1].get("versions") or {}
        res = {p: [x for x in chk.caption(t, p) if not x["ok"]] for p, t in v.items()}
        same = len({t for p, t in v.items() if p in ("Instagram", "TikTok")}) == 1
        return {"works": all(not r for r in res.values()), "sense": not same and "LinkedIn" in v and "Facebook" in v,
                "detail": f"platforms {list(v)} · Instagram and TikTok identical {same} · failing {[(p, [x['check'] for x in r]) for p, r in res.items() if r]}"}
    _()


# =====================================================================================================================

def main():
    global PG
    from playwright.sync_api import sync_playwright
    os.environ.setdefault("RT_DB", os.environ.get("DIWAN_DB", ""))
    with sync_playwright() as p:
        b = p.chromium.launch(channel=None if HEADLESS else "chrome", headless=HEADLESS, args=["--window-size=1500,1000"])
        PG = b.new_page(viewport={"width": 1440, "height": 920})
        PG.on("pageerror", lambda e: ERRS.append(str(e)[:200]))
        PG.on("response", lambda r: ERRS.append(f"HTTP {r.status} {r.url[-80:]}") if r.status >= 500 else None)
        PG.on("dialog", lambda d: d.dismiss() if DIALOG["mode"] == "dismiss" else (d.accept(DIALOG["text"]) if d.type == "prompt" else d.accept()))
        for r in ROUNDS:
            CUR["round"] = r
            fn = globals().get(r.lower())
            if not fn:
                print("no round", r); continue
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                print(f"ROUND {r} stopped: {type(e).__name__}: {e}"); shot(f"round-{r}-stopped")
        STATE.setdefault("page_errors", [])
        STATE["page_errors"] = sorted(set(STATE["page_errors"] + ERRS))[:200]
        STATE["spent"] = round(spend() - STATE["start_spend"], 4)
        save()
        print(f"spent ${STATE['spent']} · page errors {len(ERRS)}")
        b.close()


if __name__ == "__main__":
    main()
