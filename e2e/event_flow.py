"""Run: python e2e/event_flow.py <out dir> http://127.0.0.1:8031 <folder of .jpg photos>, on a scratch server (DIWAN_OFFLINE=1, DIWAN_AUTH=off) with Instagram not connected, fresh database. BROWSER=msedge where Playwright has no browser of its own. Browser check of docs/event-post-spec.md: photos in, finished post out, a change at the last step. Sample pictures, not a real event."""
import glob
import pathlib
import os
import sys
import time

import httpx
from playwright.sync_api import sync_playwright

BASE = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("http") else "http://127.0.0.1:8031"
OUT = pathlib.Path(sys.argv[1])
PICS = sorted(glob.glob(sys.argv[3] + "/*.jpg"))[:5]
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
httpx.post(BASE + "/api/business", json={"values": {"industry": "Real estate brokerage", "country": "AE", "posted_before": "no"}, "by": "maya"}, timeout=20)
httpx.post(BASE + "/api/brand", json={"values": {"name": "Diwan Realty", "positioning": "A Dubai brokerage that tells buyers the whole cost before they commit."}, "by": "maya"}, timeout=20)

with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("BROWSER") or None)
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(BASE + "/web/studio.html")
    pg.wait_for_selector("#jmake")
    pg.locator("#jmoment summary").click()
    pg.fill("#jm-title", "Cityscape Global stand")
    pg.fill("#jm-what", "We showed three new towers at Cityscape Global this week, and met buyers at our stand.")
    pg.set_input_files("#jm-files", PICS)
    pg.click("#jm-add")
    pg.wait_for_function("document.querySelector('#jpanel').innerText.includes('Format: Carousel')", timeout=30000)
    body = pg.inner_text("#jpanel")
    ok("five photos: a carousel, with the reason", "5 usable photos" in body, body[:400])
    pg.select_option("#jfmt", "image")
    pg.wait_for_function("document.querySelector('#jpanel').innerText.includes('Format: Single image')", timeout=30000)
    ok("a person can change the format", "you chose this" in pg.inner_text("#jpanel"))
    pg.select_option("#jfmt", "carousel")
    pg.wait_for_function("document.querySelector('#jpanel').innerText.includes('Format: Carousel')", timeout=30000)
    pg.screenshot(path=str(OUT / "e1-moment.png"), full_page=True)

    pg.click("#jmake")
    pg.wait_for_function("document.querySelector('#turn').innerText.includes('Use this one')", timeout=60000)
    turn = pg.text_content("#turn")  # the plan sits in a closed tab on each card
    ok("each option shows which photo carries which words", "1. " in turn and ".jpg:" in turn, turn[:300])
    ok("no film or video plan on a carousel", "Video plan" not in turn)
    pg.locator("button", has_text="Use this one").first.click()
    pg.wait_for_function("document.querySelector('.slideshow img') && document.querySelector('#turn').innerText.includes('Publish the')", timeout=60000)
    ok("five real images are on screen", pg.locator(".slideshow img").count() == 5)
    ok("images load", pg.evaluate("[...document.querySelectorAll('.slideshow img')].every((i) => i.complete && i.naturalWidth === 1080)") or pg.wait_for_timeout(1500) or pg.evaluate("[...document.querySelectorAll('.slideshow img')].every((i) => i.naturalWidth === 1080)"))
    ok("the request names the format", "carousel" in pg.inner_text("#turn"), pg.inner_text("#turn")[:300])
    ok("no film step in the chain", "Make the images" in pg.inner_text("#chain") and "Film it" not in pg.inner_text("#chain"))
    pg.screenshot(path=str(OUT / "e2-finished.png"), full_page=True)

    chg = pg.locator("input[aria-label='Change this post']")
    chg.fill("make the hook shorter")
    pg.get_by_role("button", name="Ask for change").last.click()
    pg.wait_for_function("document.querySelector('#turn').innerText.includes('Use this one')", timeout=60000)
    ok("a change to the words comes back for a new pick", "Use this one" in pg.inner_text("#turn"))
    pg.locator("button", has_text="Use this one").first.click()
    pg.wait_for_function("document.querySelector('#turn').innerText.includes('Approve for this time')", timeout=60000)
    pg.get_by_role("button", name="Approve for this time").click()
    pg.wait_for_timeout(2000)
    ok("approving says what is missing and posts nothing", "published" not in str(httpx.get(BASE + "/api/studio", timeout=30).json().get("made", {}).get("published")).lower() and httpx.get(BASE + "/api/studio", timeout=30).json()["made"]["published"] is None)
    ok("no script errors on the page", not errors, "; ".join(errors)[:300])
    ok("no sideways scroll at 1280", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.wait_for_timeout(300)
    ok("no sideways scroll on a phone", pg.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    b.close()
print(f"{sum(res)}/{len(res)}")
