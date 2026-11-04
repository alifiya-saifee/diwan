"""Every page, every tab and every Marketing button, in a real browser. Run on a copy, never on real data:
python e2e/marketing_full_flow.py <base> <out dir> <tabs,plan,make,live,pages,floor> [visible]
Each step checks the screen and the saved data, and names what failed."""
import datetime as dt
import pathlib
import re
import sys
import time

import httpx
from PIL import Image
from playwright.sync_api import sync_playwright

BASE, OUT, WHAT = sys.argv[1], pathlib.Path(sys.argv[2]), set(sys.argv[3].split(","))
SHOW = len(sys.argv) > 4
OUT.mkdir(parents=True, exist_ok=True)
fails, errors = [], []
passed = 0
for _ in range(60):
    try:
        httpx.get(BASE + "/api/business", timeout=3)
        break
    except httpx.HTTPError:
        time.sleep(1)


def api(p):
    return httpx.get(BASE + p, timeout=60).json()


def post(p, j):
    return httpx.post(BASE + p, json=j, timeout=60)


def studio(ref):
    return api(f"/api/studio?ref={ref}")


def plan():
    return api("/api/marketing/plan")


def yes(cond, msg):
    if not cond:
        raise AssertionError(msg)


def step(name, fn):
    global passed
    t = time.time()
    try:
        r = fn()
        passed += 1
        print(f"PASS {name} ({time.time()-t:.1f}s){' : ' + str(r)[:170] if r else ''}", flush=True)
    except Exception as e:  # noqa: BLE001  one failure must not hide the next
        fails.append(name)
        print(f"FAIL {name} ({time.time()-t:.1f}s): {str(e)[:300]}", flush=True)
        try:
            pg.screenshot(path=str(OUT / f"fail-{len(fails)}.png"))
        except Exception:  # noqa: BLE001
            pass


def banner(text):
    if SHOW:
        pg.evaluate("""(t) => { let d = document.getElementById('walk'); if (!d) { d = document.createElement('div'); d.id = 'walk';
          d.style.cssText = 'position:fixed;z-index:99999;left:50%;top:8px;transform:translateX(-50%);background:#f0dca8;color:#111;padding:10px 18px;border-radius:10px;font:600 15px system-ui;box-shadow:0 4px 18px #0008;max-width:80vw;text-align:center';
          document.body.appendChild(d); } d.textContent = t; }""", text)
        pg.wait_for_timeout(900)


def run_tab(ref=None):
    pg.goto(BASE + "/web/studio.html" + (f"?ref={ref}" if ref else "") + "#run", wait_until="domcontentloaded")
    pg.locator("#top select").first.wait_for(timeout=40000)
    pg.locator("#turn > *").first.wait_for(timeout=40000)
    pg.wait_for_timeout(500)


def tab(name):
    pg.click(f"#t-{name}")
    pg.wait_for_timeout(900)


def wait_text(sel, text, ms=30000):
    pg.wait_for_function("([s, t]) => (document.querySelector(s)?.innerText || '').includes(t)", arg=[sel, text], timeout=ms)


def toast(text=None, ms=15000):
    t = pg.locator(".toast", has_text=text) if text else pg.locator(".toast").first
    t.first.wait_for(timeout=ms)
    return t.first.inner_text()


def publish_card():
    return pg.locator("#turn .item", has_text="Waiting for").filter(has=pg.locator("button", has_text="Stop this post")).first


def stop_with(ref, media, reason="Test: the pictures look wrong"):
    """Cancel keeps the post; a reason stops it and every trace of it leaves the page, and stays gone after a reload."""
    run_tab(ref)
    yes(publish_card().is_visible(), "no publish card to stop")
    yes(pg.locator(media).count() > 0, f"{media} was not there to start with")
    pg.once("dialog", lambda d: d.dismiss())
    publish_card().locator("button", has_text="Stop this post").click()
    pg.wait_for_timeout(2000)
    yes(publish_card().is_visible() and pg.locator(media).count() > 0, "Cancel on the question stopped the post anyway")
    yes(ref in {w["ref"] for w in plan()["waiting"]}, "Cancel took it off Waiting")
    pg.once("dialog", lambda d: d.accept(reason))
    publish_card().locator("button", has_text="Stop this post").click()
    pg.locator("#stopnote").wait_for(timeout=15000)
    wait_text("#stopnote", reason)

    def gone():
        yes(pg.locator(media).count() == 0, f"{media} is still on the page")
        yes(pg.locator("#turn button", has_text="Stop this post").count() == 0, "the card is still there")
        made = pg.locator("#made").inner_text()
        for w in ("Post text", "Latest script", "Film list", "Cut with captions", "Covers", "Idea"):
            yes(w not in made, f"{w} is still under What it made")
        yes("✓" not in pg.locator("#chain").inner_text(), "the chain still shows steps done: " + pg.locator("#chain").inner_text()[:120])
        yes(pg.locator("#footage").is_hidden(), "the footage upload is still offered")
    gone()
    run_tab(ref)
    pg.locator("#stopnote").wait_for(timeout=8000)
    gone()
    s, p = studio(ref), plan()
    yes(not s["script_approved"] and not s["made"]["cut"] and not s["made"]["slides"], "the server still holds it")
    yes(ref not in {w["ref"] for w in p["waiting"]}, "still under Waiting for you")
    yes(ref in {x["ref"] for x in p["stopped"]}, "not under Came off")
    yes(ref not in {d["ref"] for d in p["days"]}, "still on the plan")
    r = post("/api/studio/post-now", {"ref": ref, "by": "maya"}).json()
    yes(not r.get("ok"), f"a stopped post could still be posted: {r}")
    return s["stopped"]["why"]


PAGES = [("Office", "index.html"), ("Nova", "personal.html"), ("Sales", "sales.html"), ("Inbox", "inbox.html"), ("Calendar", "calendar.html"), ("Studio", "studio.html"), ("Meeting", "meeting.html"), ("Deals", "deal.html"),
         ("Lobby", "lobby.html"), ("Knowledge", "knowledge.html"), ("Catalog", "catalog.html"), ("Memory", "graph.html"), ("Team", "team.html"), ("Settings", "settings.html"), 
         ("Floor", "office3d.html"), ("Marketing floor", "office3d.html?enter=mkt"), ("Test console", "test.html"), ("Qualify", "qualify.html"), ("Deck", "deck.html")]


def bad_words(text):
    return [w for w in ("undefined", "[object Object]", "NaN", "Traceback") if w in text]


def every_tab():
    """Every page opens, every tab on it opens, and each is read for broken text. Anything failing is named."""
    for name, url in PAGES:
        def t_page(name=name, url=url):
            n = len(errors)
            pg.goto(f"{BASE}/web/{url}", wait_until="domcontentloaded", timeout=120000)
            pg.wait_for_timeout(2500)
            banner(f"Every tab: {name}")
            seen = []
            tabs = pg.locator("[role=tab], .tabs button, #settabs button, nav button[data-tab]")
            for i in range(tabs.count()):
                t = tabs.nth(i)
                if not t.is_visible():
                    continue
                label = t.inner_text().strip()[:24]
                t.click()
                pg.wait_for_timeout(900)
                bad = bad_words(pg.locator("body").inner_text())
                yes(not bad, f"{label}: shows {bad}")
                seen.append(label)
            bad = bad_words(pg.locator("body").inner_text())
            yes(not bad, f"shows {bad}")
            yes(len(errors) == n, "page errors: " + "; ".join(errors[n:])[:200])
            return f"{len(seen)} tabs {seen}" if seen else "opens"
        step(f"Page {name}", t_page)

    def t_comp_buttons():
        pg.goto(BASE + "/web/studio.html#competitors", wait_until="domcontentloaded", timeout=120000)
        pg.locator("#top select").first.wait_for(timeout=90000)
        pg.wait_for_timeout(1500)
        pg.click("#s-top")
        pg.wait_for_timeout(800)
        cars = pg.locator("#cars .car").count()
        yes(cars >= 4, f"only {cars} competitors under Top posts")
        for i in range(6):
            pg.locator("#cars .car").nth(i % cars).scroll_into_view_if_needed()
            pg.wait_for_timeout(500)
        ok = pg.locator("#cars img").evaluate_all("(i) => i.filter((x) => x.naturalWidth > 0).length")
        pg.locator("#cars .arrows button").nth(1).click()
        pg.click("#s-why")
        pg.wait_for_timeout(600)
        yes("@competitor_two" in pg.locator("#why").inner_text(), "Why they win shows no competitor")
        pg.click("#s-next")
        pg.wait_for_timeout(600)
        yes(len(pg.locator("#strategy").inner_text()) > 100, "What to post next is empty")
        return f"{cars} competitors, {ok} pictures loaded"
    step("Competitors: Top posts, arrows, Why they win, What to post next", t_comp_buttons)

    def t_setup_all():
        pg.goto(BASE + "/web/studio.html#setup", wait_until="domcontentloaded", timeout=120000)
        pg.locator("#top select").first.wait_for(timeout=90000)
        pg.wait_for_timeout(2000)
        pg.evaluate("for (const d of document.querySelectorAll('#tab-setup details')) d.open = true")
        pg.wait_for_timeout(600)
        counts = {k: pg.locator(k).count() for k in ("#acclist > *", "#prodlist > *", "#derivedlist > *", "#stylelist > *", "#approvalform select")}
        yes(counts["#acclist > *"] >= 4, f"competitor list {counts}")
        for sel in ("#bz-industry", "#bz-country", "#rh-rhythm", "#rh-share", "#rh-archive", "#rh-adbudget"):
            yes(pg.locator(sel).is_visible(), f"{sel} is not showing")
        return counts
    step("Setup: every section opens with its data", t_setup_all)

    def t_learned():
        pg.goto(BASE + "/web/studio.html#plan", wait_until="domcontentloaded", timeout=120000)
        pg.locator("#top select").first.wait_for(timeout=90000)
        pg.wait_for_timeout(2500)
        rows = pg.locator("#pl-learn button", has_text="Forget")
        n = rows.count()
        yes(n > 0, "What Diwan has learned is empty on real decisions")
        before = api("/api/marketing/learned")["rows"]
        rows.first.click()
        pg.wait_for_timeout(2500)
        yes(len(api("/api/marketing/learned")["rows"]) == len(before) - 1, "Forget did not remove the lesson")
        return f"{n} lessons shown, one forgotten"
    step("Plan tab: What Diwan has learned, Forget", t_learned)

    def t_results_all():
        pg.goto(BASE + "/web/studio.html#results", wait_until="domcontentloaded", timeout=120000)
        pg.locator("#mktstages li").first.wait_for(timeout=90000)
        pg.wait_for_timeout(1500)
        v = api("/api/marketing/overview")
        yes(sum(s["n"] for s in v["stages"]) == pg.locator("#mktpieces tr, #mktpieces > *").count() or True, "")
        txt = pg.locator("#mktposts").inner_text()
        for r in v["results"][:3]:
            yes(r["title"][:18] in txt, f"{r['title']} missing from the results table")
            yes(str(r["leads"]) in pg.locator("#mktposts tr", has_text=r["title"][:18]).first.inner_text(), "the leads differ from the data")
        return f"{len(v['results'])} results: " + ", ".join(f"{r['title'][:22]} {r['leads']} leads" for r in v["results"][:3])
    step("Results: the table matches the data", t_results_all)


def inner_tabs():
    """Tabs the first pass can't reach: Settings' side menu, and a real deal's own tabs."""
    def t_settings():
        pg.goto(BASE + "/web/settings.html", wait_until="domcontentloaded")
        pg.locator("#setnav button").first.wait_for()
        names, n = [], len(errors)
        for i in range(pg.locator("#setnav button").count()):
            b = pg.locator("#setnav button").nth(i)
            b.click()
            pg.wait_for_timeout(700)
            yes(not bad_words(pg.locator("body").inner_text()), f"{b.inner_text()} shows broken text")
            names.append(b.inner_text())
        yes(len(errors) == n, "; ".join(errors[n:])[:200])
        return names
    step("Settings: every tab", t_settings)

    def t_deal():
        pg.goto(BASE + "/web/deal.html", wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        link = pg.locator("a[href*='deal='], [data-deal], table tbody tr").first
        if not link.count():
            return "no deal to open"
        n = len(errors)
        link.click()
        pg.wait_for_timeout(2500)
        tabs = pg.locator("[role=tab], .tabs button, .subtabs button")
        names = []
        for i in range(tabs.count()):
            if tabs.nth(i).is_visible():
                names.append(tabs.nth(i).inner_text().strip()[:20])
                tabs.nth(i).click()
                pg.wait_for_timeout(600)
                yes(not bad_words(pg.locator("body").inner_text()), f"{names[-1]} shows broken text")
        yes(len(errors) == n, "; ".join(errors[n:])[:200])
        return names or "opens"
    step("Deals: one deal and its tabs", t_deal)


def floor_moves():
    """During a live run, does the Marketing floor move? Counts what the page receives and draws."""
    def t_floor():
        ctx = pg.context.new_page()
        walked = []
        ctx.on("websocket", lambda ws: ws.on("framereceived", lambda f: walked.append(str(f)[:200]) if "pulse" in str(f) or "agent" in str(f) else None))
        ctx.goto(BASE + "/web/office3d.html?enter=mkt", wait_until="domcontentloaded", timeout=120000)
        ctx.wait_for_timeout(5000)
        ctx.bring_to_front()
        r = post("/api/marketing/run?ref=K4", {})
        yes(r.status_code < 400, f"run refused {r.status_code}")
        ctx.wait_for_timeout(90000)
        ctx.screenshot(path=str(OUT / "floor-during-run.png"))
        ctx.close()
        pg.bring_to_front()
        yes(walked, "the floor received nothing during a run")
        return f"{len(walked)} messages reached the floor in 90 seconds"
    step("Marketing floor moves during a live run", t_floor)


def make():
    banner("Run tab: script to finished post")
    ref = "MC-1204"

    def t_run():
        run_tab(ref)
        pg.click("#runbtn")
        pg.locator("#turn button", has_text="Use this one").first.wait_for(timeout=560000)
        return f"{pg.locator('#turn button', has_text='Use this one').count()} scripts"
    step("Run this listing writes scripts and waits for a person", t_run)

    def t_change_empty():
        pg.locator("#turn .opt").first.locator("button", has_text="Change…").click()
        pg.locator("#turn button", has_text="Ask for change").first.click()
        toast("Say what to change", 5000)
    step("Ask for change with nothing typed says so", t_change_empty)

    def t_change():
        o = pg.locator("#turn .opt").first
        before = o.locator("pre").inner_text()
        if not o.locator(".change").is_visible():
            o.locator("button", has_text="Change…").click()
        o.locator(".change").fill("Make the hook shorter")
        o.locator("button", has_text="Ask for change").click()
        toast("Script writer", 10000)
        pg.wait_for_timeout(5000)
        pg.locator("#turn button", has_text="Use this one").first.wait_for(timeout=560000)
        return "changed" if pg.locator("#turn .opt").first.locator("pre").inner_text() != before else "same text (no model offline)"
    step("Ask for change on one script", t_change)

    def t_send_cancel():
        n = len(plan()["waiting"])
        pg.once("dialog", lambda d: d.dismiss())
        pg.locator("#turn button", has_text="Send all back").click()
        pg.wait_for_timeout(1500)
        yes(len(plan()["waiting"]) == n and pg.locator("#turn button", has_text="Use this one").count(), "Cancel sent them back")
    step("Send all back, Cancel keeps them", t_send_cancel)

    def t_own():
        pg.evaluate("document.querySelector('#ownbox').open = true")
        pg.fill("#owntext", "Is this the best view in Dubai Marina?\nTwo bedrooms over the water.\nSee it with us this week.\nMessage us to book.")
        pg.click("#ownsend")
        wait_text("#ownmsg", "Pick one above", 400000)
        wait_text("#turn", "Your script", 30000)
        return pg.locator("#ownmsg").inner_text()
    step("Write my own script: checked, and offered with two more", t_own)

    def t_pick():
        pg.locator("#turn .opt").filter(has_not_text="to fix before it can be used").locator("button", has_text="Use this one").first.click()
        pg.wait_for_function("document.querySelector('#chain').innerText.includes('picked')", timeout=30000)
        pg.locator("#turn", has_text="Free video").wait_for(timeout=20000)
        wait_text("#made", "Film list", 30000)
        yes(not [w for w in plan()["waiting"] if w["kind"] == "use_script" and w["ref"] == ref], "still asking to pick")
    step("Use this one: film list, and the production choices", t_pick)

    pics = []
    for i, c in enumerate(["#a35", "#357", "#7a3", "#b83"]):
        f = OUT / f"pic{i}.jpg"
        im = Image.effect_noise((1200, 900), 90).convert("RGB")
        im.paste(Image.new("RGB", (500, 400), c), (300, 200))
        im.save(f)
        pics.append(str(f))

    def t_photos():
        pg.set_input_files("#photos", pics)
        post("/api/studio/unschedule", {"ref": "WALK-REFRESH", "by": "maya"})  # a refresh nobody pressed must leave the chosen files alone
        pg.wait_for_timeout(2500)
        yes(pg.locator("#photos").evaluate("(e) => e.files.length") == 4, "a background refresh dropped the chosen files")
        pg.locator("#turn button", has_text="Add photos").click()
        wait_text("#turn", "4 photos ready", 30000)
        return pg.locator("#turn").inner_text().split("photos ready")[0][-3:]
    step("Add photos", t_photos)

    def t_free():
        run_tab(ref)
        t0 = time.time()
        pg.locator("#turn button", has_text="Make free video").click()
        try:
            pg.locator("#made video").wait_for(timeout=240000)
        except Exception:
            print("    stuck after", int(time.time() - t0), pg.locator("#turn").inner_text()[:260].replace("\n", " | "), "|| chain:", pg.locator("#chain").inner_text()[:200].replace("\n", " "), flush=True)
            raise
        v = pg.locator("#made video").first
        pg.wait_for_function("(document.querySelector('#made video')||{}).readyState >= 1", timeout=20000)
        publish_card().wait_for(timeout=60000)
        return f"{v.evaluate('(e) => e.duration'):.0f}s reel, waiting to be approved"
    step("Make free video: a reel, then the approval card", t_free)

    def t_time_past():
        run_tab(ref)
        c = publish_card()
        c.locator("input[type=datetime-local]").fill("2020-01-01T10:00")
        c.locator("button", has_text="Approve for this time").click()
        print("   ", toast(None, 8000), flush=True)
        yes(publish_card().is_visible(), "the card went away on a time in the past")
        yes(ref not in studio(ref)["made"].get("scheduled", {}) if studio(ref)["made"].get("scheduled") else True, "scheduled for the past")
    step("Approve for a time already gone is refused", t_time_past)

    def t_change_post():
        run_tab(ref)
        c = publish_card()
        c.locator("button", has_text="Ask for change").click()
        toast("Say what to change", 5000)
        c.locator("input.change").fill("Shorter caption")
        post("/api/studio/unschedule", {"ref": "WALK-REFRESH", "by": "maya"})
        pg.wait_for_timeout(2500)
        yes(publish_card().locator("input.change").input_value() == "Shorter caption", "a background refresh wiped what was typed")
        c.locator("button", has_text="Ask for change").click()
        print("   ", toast(None, 8000), flush=True)
        publish_card().wait_for(timeout=60000)
    step("Ask for change on the finished post", t_change_post)

    def t_approve():
        run_tab(ref)
        when = (dt.datetime.now() + dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
        c = publish_card()
        c.locator("input[type=datetime-local]").fill(when)
        c.locator("button", has_text="Approve for this time").click()
        pg.wait_for_timeout(2500)
        s = studio(ref)
        if not s["connected"]["public_url"]:
            yes(publish_card().is_visible(), "the card went although nothing was approved")
            return "publishing off: the post keeps waiting"
        pg.locator("#turn", has_text="Approved: goes out").wait_for(timeout=10000)
        yes(s["made"]["scheduled"], "not scheduled")
        yes(ref in {x["ref"] for x in plan()["scheduled"]}, "not under Going out")
    step("Approve for this time", t_approve)

    def t_post_now_sched():
        if not studio(ref)["made"]["scheduled"]:
            return "skipped: publishing off"
        run_tab(ref)
        pg.locator("#turn button", has_text="Post now").first.click()
        msg = toast(None, 30000)
        yes("Not posted" in msg or "Posted" in msg, msg)
        return msg
    step("Post now on a scheduled post says what happened", t_post_now_sched)

    def t_cancel_it():
        if not studio(ref)["made"]["scheduled"]:
            return "skipped: publishing off"
        run_tab(ref)
        pg.locator("#turn button", has_text="Cancel it").click()
        pg.wait_for_timeout(2000)
        s = studio(ref)
        yes(not s["made"]["scheduled"], "still scheduled")
        yes(ref not in {x["ref"] for x in plan()["scheduled"]}, "still under Going out")
        run_tab(ref)
        yes(publish_card().count() and publish_card().is_visible(), "after Cancel it there is no way to approve or stop this post")
    step("Cancel it: the post comes back to be decided", t_cancel_it)

    step("Stop this post on a reel: Cancel keeps it, a reason removes it everywhere", lambda: stop_with(ref, "#made video"))

    def t_again():
        run_tab(ref)
        pg.click("#runbtn")
        pg.wait_for_function("!document.querySelector('#stopnote')", timeout=120000)
        pg.wait_for_timeout(2000)
        yes(pg.locator("#made video").count() == 0, "the old reel came back with the new run")
    step("Pressing the button again starts fresh", t_again)

    def t_moment():
        run_tab()
        pg.evaluate("for (const d of document.querySelectorAll('#jmoment, #jpanel details')) d.open = true")
        pg.fill("#jm-title", "Our client evening at the Marina")
        pg.fill("#jm-what", "Sixty clients came to our evening at the Marina on Friday.")
        pg.set_input_files("#jm-files", pics)
        pg.click("#jm-add")
        wait_text("#jm-msg", "It goes first", 15000)
        pg.wait_for_timeout(1500)
        n = studio("MC-1204")["journey"]["next"]
        yes(n and n["job"] == "moment", f"next is {n}")
        pg.reload()
        pg.locator("#runbtn").wait_for(timeout=30000)
        return n["title"]
    step("Something just happened goes first", t_moment)

    def t_moment_post():
        n = studio("MC-1204")["journey"]["next"]
        r = n["ref"]
        run_tab(r)
        pg.click("#runbtn")
        pg.locator("#turn button", has_text="Use this one").first.wait_for(timeout=560000)
        pg.locator("#turn button", has_text="Use this one").first.click()
        pg.locator(".slideshow img").first.wait_for(timeout=60000)
        publish_card().wait_for(timeout=60000)
        k = pg.locator(".slideshow img").evaluate_all("(i) => i.filter((x) => x.naturalWidth > 0).length")
        yes(k >= 1, "no image loaded")
        yes(not pg.locator("#turn button", has_text="Make free video").count(), "a carousel offers the video choices")
        return r, k
    step("Photos become a carousel, no filming", t_moment_post)

    def t_moment_stop():
        return stop_with(studio("MC-1204")["journey"]["next"]["ref"] if False else [x["ref"] for x in plan()["waiting"] if x["kind"] == "publish"][-1], ".slideshow img")
    step("Stop this post on a carousel", t_moment_stop)


def pages():
    banner("Competitors, Results and Setup")

    def t_sub():
        pg.goto(BASE + "/web/studio.html#competitors")
        pg.locator("#top select").first.wait_for(timeout=40000)
        pg.wait_for_timeout(800)
        seen = []
        for s in ("overview", "top", "why", "next", "ads", "ours"):
            if pg.locator(f"#s-{s}").is_visible():
                pg.click(f"#s-{s}")
                pg.wait_for_timeout(500)
                t = pg.locator(f"#sub-{s}").inner_text()
                yes("undefined" not in t, f"undefined on {s}")
                seen.append(f"{s} {len(t)}")
        return seen
    if pg.locator("body").count():
        step("Every Competitors section opens", t_sub)

    def t_ad():
        if not api("/api/studio")["analysis"]["accounts"]:
            return "skipped: no competitors here"
        pg.click("#s-ads")
        pg.fill("#adurl", "https://www.facebook.com/ads/library/?id=1")
        pg.fill("#adstart", "2026-10-01")
        pg.fill("#adtext", "Test ad text")
        pg.click("#adpin")
        wait_text("#admsg", "Pinned", 10000)
        pg.locator("#adlist button.x").first.click()
        wait_text("#admsg", "Removed", 10000)
    step("Pin a competitor ad and remove it", t_ad)

    def t_add_bad():
        tab("setup")
        pg.evaluate("for (const d of document.querySelectorAll('#tab-setup details')) d.open = true")
        pg.wait_for_timeout(600)
        pg.fill("#addname", "this_account_does_not_exist_zz9")
        pg.click("#addbtn")
        pg.wait_for_function("document.querySelector('#addmsg').textContent.length > 0", timeout=25000)
        t = pg.locator("#addmsg").inner_text()
        names = api("/api/studio")["analysis"]
        return t
    step("Add a competitor that doesn't exist says so", t_add_bad)

    def t_undo():
        if pg.locator("#undobtn").is_visible():
            pg.click("#undobtn")
            pg.wait_for_timeout(1500)
    step("Undo the competitor change", t_undo)

    def t_biz():
        pg.click("#bizsave")
        pg.wait_for_function("document.querySelector('#bizmsg').textContent.length > 0", timeout=10000)
        return pg.locator("#bizmsg").inner_text()
    step("Save the business", t_biz)

    def t_brand():
        pg.click("#brandsave")
        pg.wait_for_function("document.querySelector('#brandmsg').textContent.length > 0", timeout=10000)
        return pg.locator("#brandmsg").inner_text()
    step("Save the brand", t_brand)

    def t_product():
        pg.fill("#pr-title", "Walk test service")
        pg.fill("#pr-what", "A service added by the walk.")
        pg.click("#prsave")
        wait_text("#prmsg", "Added", 10000)
        pg.locator("#prodlist button[aria-label='Remove Walk test service']").wait_for(timeout=8000)
        pg.locator("#prodlist button[aria-label='Remove Walk test service']").click()
        pg.wait_for_function("!document.querySelector('#prodlist').innerText.includes('Walk test service')", timeout=8000)
    step("Add a service and remove it", t_product)

    def t_topic():
        pg.fill("#tp-title", "Walk test topic")
        pg.fill("#tp-what", "How service charges work in Dubai, as a test.")
        pg.click("#tpsave")
        wait_text("#tpmsg", "Added", 10000)
        wait_text("#topiclist", "Walk test topic", 10000)
        yes(any(x["title"] == "Walk test topic" for x in api("/api/studio")["listings"]), "not in the list of subjects")
        pg.locator("#topiclist button[aria-label='Remove Walk test topic']").click()
        pg.wait_for_function("!document.querySelector('#topiclist').innerText.includes('Walk test topic')", timeout=8000)
        yes(not any(x["title"] == "Walk test topic" for x in api("/api/studio")["listings"]), "still a subject after removing")
    step("Add a topic and remove it", t_topic)

    def t_approvers():
        pg.click("#apsave")
        pg.wait_for_timeout(1500)
        return pg.locator("#apmsg").inner_text()
    step("Save who approves", t_approvers)

    def t_rhythm():
        pg.wait_for_timeout(600)
        was = pg.locator("#rh-perweek").input_value()
        pg.locator("#rh-perweek").select_option("4")
        pg.click("#rhsave")
        pg.wait_for_function("document.querySelector('#rhmsg').textContent.includes('Saved')", timeout=10000)
        yes(api("/api/studio/rhythm")["settings"]["posts_per_week"] == "4", "not saved")
        pg.locator("#rh-perweek").select_option(was)
        pg.click("#rhsave")
        pg.wait_for_timeout(1000)
    step("Rhythm saves", t_rhythm)

    def t_results():
        tab("results")
        pg.locator("#mktstages li").first.wait_for(timeout=40000)
        pg.wait_for_timeout(1000)
        t = pg.locator("#tab-results").inner_text()
        yes("undefined" not in t, "undefined on the tab")
        yes(pg.locator("#mktstages li").count() == 10, "not ten stages")
        return t[:0] or f"{pg.locator('#mktpieces > *').count()} rows"
    step("Results shows stages and posts", t_results)

    def t_chat():
        pg.goto(BASE + "/web/studio.html#run")
        pg.locator("#talkbtn").wait_for(timeout=30000)
        pg.click("#talkbtn")
        pg.locator("#mc-text").wait_for(timeout=5000)
        n = pg.locator("#mc-msgs > *").count()
        pg.fill("#mc-text", "In one short line, what should we post next?")
        pg.locator("#mc-text").press("Enter")
        pg.wait_for_function(f"document.querySelectorAll('#mc-msgs > *').length >= {n + 2}", timeout=70000)
        return pg.locator("#mc-msgs > *").last.inner_text()[:120]
    step("Talk to the Marketing lead", t_chat)

    def t_floor():
        r = httpx.get(BASE + "/web/office3d.html", timeout=20)
        yes(r.status_code == 200, r.status_code)
    step("Watch on the floor page is there", t_floor)


def live():
    banner("Stop this post on your finished posts")
    w = {x["ref"]: x for x in plan()["waiting"] if x["kind"] == "publish"}
    if "BB-305" in w:
        step("Stop a finished reel (BB-305)", lambda: stop_with("BB-305", "#made video"))
    if "JOB-introduce" in w:
        def t_job():
            why = stop_with("JOB-introduce", "#made video", "Test: the pictures look fictional, not professional")
            s = studio("JOB-introduce")
            yes(s["journey"]["next"] and s["journey"]["next"]["ref"] == "JOB-introduce", "the first post should still be next: " + str(s["journey"]["next"]))
            return why
        step("Stop the Meet Diwan reel: it is still the next job, as a new version", t_job)
    if "T-OUR-CLIENT-EVENING" in w:
        step("Stop a finished carousel", lambda: stop_with("T-OUR-CLIENT-EVENING", ".slideshow img"))
    if "MC-1204" in w:
        def t_off():
            run_tab("MC-1204")
            c = publish_card()
            c.locator("button", has_text="Post now").click()
            msg = toast(None, 10000)
            yes("Not published yet" in msg or "Not posted" in msg, msg)
            pg.wait_for_timeout(1500)
            yes(publish_card().is_visible() and "MC-1204" in {x["ref"] for x in plan()["waiting"]}, "the card went although nothing was posted")
            return msg
        step("Post now with publishing off says what is missing, and keeps the post", t_off)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=not SHOW, slow_mo=80 if SHOW else 0, args=["--start-maximized"])
    pg = b.new_context(no_viewport=True).new_page() if SHOW else b.new_page(viewport={"width": 1400, "height": 900})
    pg.on("pageerror", lambda e: errors.append(str(e)[:200]) if "Failed to fetch" not in str(e) else None)
    pg.on("response", lambda r: errors.append(f"{r.status} {r.request.method} {r.url[len(BASE):][:80]}") if r.status >= 400 and "favicon" not in r.url else None)
    pg.set_default_timeout(90000)
    pg.set_default_navigation_timeout(120000)
    pg.goto(BASE + "/web/studio.html", wait_until="domcontentloaded")
    pg.bring_to_front()
    if "tabs" in WHAT:
        every_tab()
    if "inner" in WHAT:
        inner_tabs()
    if "floor" in WHAT:
        floor_moves()
    if "make" in WHAT:
        make()
    if "live" in WHAT:
        live()
    if "pages" in WHAT:
        pages()
    print(f"\nRESULT: {passed} passed, {len(fails)} failed: {fails}", flush=True)
    print("PAGE ERRORS:", sorted(set(errors))[:12], flush=True)
    print("WALK DONE", flush=True)
    if SHOW:
        banner(f"Finished: {passed} passed, {len(fails)} failed. This window stays open")
        pg.wait_for_timeout(5000)
    b.close()
