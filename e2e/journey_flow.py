"""Run: python e2e/journey_flow.py <out dir> http://127.0.0.1:8031, on a scratch server (DIWAN_OFFLINE=1, DIWAN_AUTH=off) with Instagram not connected, fresh database. BROWSER=msedge where Playwright has no browser of its own. Browser check of docs/content-journey-spec.md, on a scratch server."""
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


for _ in range(60):
    try:
        httpx.get(BASE + "/api/business", timeout=2)
        break
    except httpx.HTTPError:
        time.sleep(1)

r = httpx.post(BASE + "/api/business", json={"values": {"industry": "Real estate brokerage", "country": "AE", "city": "Dubai"}, "by": "maya"}, timeout=20)
ok("Setup saves a country on Windows", r.json().get("ok"), r.text[:200])

with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("BROWSER") or None)
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/web/studio.html")
    pg.wait_for_selector("#jfold")
    pg.evaluate("document.getElementById('jfold').open = true")  # Your next post is folded to one line on Make; it stays open after a reload
    pg.wait_for_selector("#jbody p")
    body = pg.inner_text("#jpanel")
    ok("unknown account: it asks, and assumes nothing", "Have you posted on this account before?" in body and "Write this post" not in body, body[:200])
    pg.screenshot(path=str(OUT / "1-asks.png"))
    pg.get_by_role("button", name="No, it is new").click()
    pg.wait_for_function("document.querySelector('#jstage').textContent.includes('Introduce')")
    body = pg.inner_text("#jpanel")
    ok("no brand yet: it says what it needs and offers no button", "Who we are" in body and pg.locator("#jmake").count() == 0, body[:300])
    ok("the nine steps are shown", pg.locator("ol.chain.nine li").count() == 9)

    httpx.post(BASE + "/api/brand", json={"values": {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit.",
                                                     "audience": "first-time buyers in Dubai", "voice": "warm, straight-talking"}, "by": "maya"}, timeout=20)
    pg.reload()
    pg.wait_for_selector("#jmake")
    body = pg.inner_text("#jpanel")
    ok("the next post is the introduction", "Introduce us: Meet Diwan Realty" in body, body[:300])
    pg.screenshot(path=str(OUT / "2-introduce.png"), full_page=True)

    pg.locator("#jm-add").scroll_into_view_if_needed() if False else None
    pg.locator("#jmoment summary").click()
    pg.fill("#jm-title", "Big news")
    pg.fill("#jm-what", "short")
    pg.click("#jm-add")
    pg.wait_for_function("document.querySelector('#jm-msg').textContent.length > 0")
    ok("a moment without facts is refused", "facts" in pg.inner_text("#jm-msg"), pg.inner_text("#jm-msg"))
    pg.fill("#jm-title", "New golden visa rule")
    pg.fill("#jm-what", "The minimum property value for the golden visa changed this week, so more buyers now qualify.")
    pg.click("#jm-add")
    pg.wait_for_function("document.querySelector('#jpanel').innerText.includes('New golden visa rule')")
    ok("a moment goes first", "New golden visa rule" in pg.inner_text("#jpanel"))
    pg.screenshot(path=str(OUT / "3-moment.png"), full_page=True)

    pg.click("#jmake")
    pg.wait_for_function("document.body.innerText.includes('Use this one')", timeout=60000)
    txt = pg.inner_text("body")
    ok("the moment's scripts wait for a person", "Use this one" in txt)
    pg.locator("button", has_text="Use this one").first.click()
    pg.wait_for_function("document.querySelector('#jpanel').innerText.includes('Meet Diwan Realty')", timeout=30000)
    ok("once approved, the plan returns to the introduction", "Introduce us" in pg.inner_text("#jpanel"))
    pg.wait_for_timeout(2500)
    ok("the card just decided is gone from the screen", "new golden visa rule, in plain" not in pg.inner_text("#turn").lower() and "Use this one" not in pg.inner_text("#turn"), pg.inner_text("#turn")[:200])

    pg.click("#jmake")
    pg.wait_for_function("document.querySelector('#turn').innerText.includes('Use this one') && document.querySelector('#turn').innerText.includes('Meet Diwan Realty')", timeout=60000)
    txt = pg.inner_text("body")
    ok("the introduction scripts are about us", "Meet Diwan Realty" in txt and "tells buyers the whole cost" in txt, txt[:300])
    pg.screenshot(path=str(OUT / "4-scripts.png"), full_page=True)

    ok("no sideways scroll at 1280", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.wait_for_timeout(300)
    ok("no sideways scroll on a phone", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), str(pg.evaluate("document.documentElement.scrollWidth")))
    pg.screenshot(path=str(OUT / "5-phone.png"))
    ok("no script errors on the page", not errors, "; ".join(errors)[:300])
    ok("no 'undefined' or 'null' on the panel", "undefined" not in pg.inner_text("#jpanel") and "null" not in pg.inner_text("#jpanel"))
    b.close()
print(f"{sum(res)}/{len(res)}")
