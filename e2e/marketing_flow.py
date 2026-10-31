"""Run: python e2e/marketing_flow.py <out dir> http://127.0.0.1:8031, on a scratch server (DIWAN_OFFLINE=1, DIWAN_AUTH=off) with Instagram not connected, fresh database. BROWSER=msedge where Playwright has no browser of its own. The whole Marketing room in a real browser, on a scratch server: script to approval, a change of price, tracing, results, a campaign."""
import pathlib
import os
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

BASE = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("http") else "http://127.0.0.1:8031"
OUT = pathlib.Path(sys.argv[1])
res = []


def ok(name, cond, extra=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{extra}]" if extra and not cond else ""))


for _ in range(90):
    try:
        httpx.get(BASE + "/api/business", timeout=2)
        break
    except httpx.HTTPError:
        time.sleep(1)
post = lambda p, j: httpx.post(BASE + p, json=j, timeout=30).json()  # noqa: E731
post("/api/business", {"values": {"industry": "Real estate brokerage", "country": "AE", "posted_before": "no"}, "by": "maya"})
post("/api/brand", {"values": {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, "by": "maya"})
post("/api/rhythm", {"values": {"ad_budget": "1000", "cpl_limit": "200"}, "by": "layla"}) if False else None

with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("BROWSER") or None)
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/web/studio.html?ref=MC-1204")
    pg.wait_for_selector("#runbtn")
    pg.click("#runbtn")
    pg.wait_for_function("document.querySelector('#turn').innerText.includes('Use this one')", timeout=60000)
    pg.locator("button", has_text="Use this one").first.click()
    pg.wait_for_function("document.querySelector('#chain').innerText.includes('picked')", timeout=30000)

    pg.click("#t-results")
    pg.wait_for_function("document.querySelector('#mktpieces').innerText.includes('In production') || document.querySelector('#mktpieces').innerText.includes('Scripts waiting')", timeout=20000)
    txt = pg.inner_text("#tab-results")
    ok("the Results tab shows the stage by its plain name", "In production" in txt, txt[:300])
    ok("all ten stages are counted", pg.locator("#mktstages li").count() == 10)

    s = httpx.get(BASE + "/api/studio?ref=MC-1204", timeout=30).json()
    text = (s["made"]["post text"] or {})
    ok("the caption carries a code word", text.get("code") and f"Say {text['code']}." in text["text"], str(text)[:200])
    code = text.get("code")

    r = httpx.post(BASE + "/api/chats/incoming", json={"phone": "+971500000999", "text": f"Hi, {code} please", "name": "Sara"}, timeout=60)
    ok("a client can say the code", r.status_code < 400, str(r.status_code))
    pg.reload()
    pg.wait_for_selector("#t-results")
    pg.click("#t-results")
    pg.wait_for_function("document.querySelector('#mktposts').innerText.includes('Marina')", timeout=20000)
    row = pg.locator("#mktposts tr", has_text="Marina").first.inner_text()
    ok("the lead appears against the post", "\t1\t" in row or " 1 " in row, row)
    pg.screenshot(path=str(OUT / "m1-results.png"), full_page=True)

    pg.fill("#cp-goal", "Viewings") if pg.is_visible("#cp-goal") else (pg.locator("#cp-new summary").click(), pg.fill("#cp-goal", "Viewings"))
    pg.fill("#cp-aud", "First-time buyers")
    pg.fill("#cp-budget", "500")
    pg.fill("#cp-days", "7")
    pg.click("#cp-add")
    pg.wait_for_function("document.querySelector('#cp-msg').textContent.length > 0")
    ok("no campaign without a monthly budget", "monthly ad budget" in pg.inner_text("#cp-msg"), pg.inner_text("#cp-msg"))
    pg.click("#t-setup")
    pg.wait_for_timeout(800)
    pg.evaluate("for (const d of document.querySelectorAll('#tab-setup details')) d.open = true")
    ok("the brief switch loads ticked and auto-posting unticked", pg.is_checked("#rh-brief") and not pg.is_checked("#rh-autopost"))
    pg.fill("#rh-adbudget", "1000")
    pg.fill("#rh-cpl", "200")
    pg.click("#rhsave")
    pg.wait_for_function("document.querySelector('#rhmsg').textContent.includes('Saved')", timeout=10000)
    st = httpx.get(BASE + "/api/studio/rhythm", timeout=20).json()["settings"]
    ok("Save keeps the switches as they were and stores the budget", st["approve_brief"] == "on" and st["auto_post"] == "off" and st["ad_budget"] == "1000" and st["cpl_limit"] == "200", str(st))
    pg.click("#t-results")
    pg.wait_for_timeout(1200)
    pg.evaluate("document.querySelector('#cp-msg').textContent = ''")
    pg.click("#cp-add")
    pg.wait_for_function("document.querySelector('#cp-msg').textContent.length > 0", timeout=15000)
    ok("a campaign is drafted with the code word", code in pg.inner_text("#cp-msg"), pg.inner_text("#cp-msg"))
    pg.wait_for_function("document.querySelector('#mktcamps').innerText.includes('I launched it')", timeout=10000)
    pg.once("dialog", lambda d: d.accept("AD-1"))
    pg.get_by_role("button", name="I launched it").click()
    pg.wait_for_function("document.querySelector('#mktcamps').innerText.includes('running')", timeout=10000)
    ok("a person records the launch", True)

    ok("no script errors on the page", not errors, "; ".join(errors)[:300])
    ok("no sideways scroll at 1280", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.wait_for_timeout(300)
    ok("no sideways scroll on a phone", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), str(pg.evaluate("document.documentElement.scrollWidth")))
    ok("no 'undefined' or 'null' on the tab", "undefined" not in pg.inner_text("#tab-results") and "null" not in pg.inner_text("#tab-results"))
    b.close()
print(f"{sum(res)}/{len(res)}")
