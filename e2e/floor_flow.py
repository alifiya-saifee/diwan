"""The 3D office, watched in a real browser while marketing runs: enter the Marketing floor, run a listing, and record
what a person sees: agents working, walking work to each other, bubbles, the walls, the Production set. Saves a video
and screenshots. python e2e/floor_flow.py http://127.0.0.1:8031 <out dir>   (WATCH=1 for a visible window)"""
import os
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots")
OUT.mkdir(parents=True, exist_ok=True)
errors = []

with sync_playwright() as p:
    watch = os.environ.get("WATCH") == "1"
    b = p.chromium.launch(headless=not watch, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, record_video_dir=str(OUT / "video"), record_video_size={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text else None)

    pg.goto(f"{BASE}/web/office3d.html?enter=mkt")
    expect(pg.locator("#title h1")).to_contain_text("Marketing", timeout=20_000)   # the Studio's "Watch on the floor" link lands on the floor
    pg.wait_for_timeout(2500)
    pg.screenshot(path=str(OUT / "f1-floor.png"))
    print("· entered the Marketing floor from a link")

    pg.get_by_role("button", name="Run a listing through marketing").click()
    t0 = time.time()
    shots = 0
    far, caught = 0.0, False
    while time.time() - t0 < 20:
        pg.wait_for_timeout(250)
        # how far is the furthest robot from its own desk right now (in floor units; a desk is about 2.5 apart)
        away = pg.evaluate("""() => { const f = window.__diwan.floor; let best = [0, null];
            for (const st of Object.values(f.stations)) { const d = st.g.position.distanceTo(st.home); if (d > best[0]) best = [d, st.id]; } return best; }""")
        far = max(far, away[0])
        if away[0] > 2 and not caught:
            caught = True
            pg.screenshot(path=str(OUT / "f2-walking.png"))
            print(f"· caught {away[1]} {away[0]:.1f} units from its desk")
        if int((time.time() - t0) / 2.5) > shots:
            shots += 1
            pg.screenshot(path=str(OUT / f"f2-running-{shots}.png"))
    print(f"· furthest any robot got from its desk: {far:.1f}")
    assert far > 2, "no robot left its desk"
    walked = pg.evaluate("window.__diwan && window.__diwan.walks")
    print(f"· hand-offs walked while running: {walked}")
    assert walked and walked > 0, "no agent walked work to another"
    pg.locator("#bar button", has_text="Brand brain").first.click()
    expect(pg.locator("#ztitle")).to_have_text("Brand brain", timeout=10_000)
    expect(pg.locator("#zbody")).to_contain_text("Company and brand knowledge")
    expect(pg.locator("#zbody")).to_contain_text("Listings we can advertise")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(OUT / "f2b-brain.png"))
    print("· Brand brain opened: " + " | ".join(pg.locator("#zbody .team .tn").all_inner_texts()).replace("\n", " "))
    for stop in ["Research", "Scripting", "Production", "Walls"]:
        btn = pg.locator("#bar button", has_text=stop)
        if btn.count():
            btn.first.click()
            pg.wait_for_timeout(1800)
            pg.screenshot(path=str(OUT / f"f3-{stop.lower()}.png"))
            print(f"· looked at {stop}")
    # approve the first script, so Production and Editing run on the floor too
    req = next(r for r in httpx.get(f"{BASE}/api/studio?ref=MC-1204").json()["approvals"] if r["kind"] == "use_script")
    httpx.post(f"{BASE}/api/requests/{req['id']}/decide", json={"decision": "approve", "by": "maya", "choice": req["options"][0]["id"]})
    pg.locator("#bar button", has_text="Production").first.click()
    pg.wait_for_timeout(4000)
    pg.screenshot(path=str(OUT / "f4-production-after-approval.png"))
    print("· script approved; Production looked at")
    walked2 = pg.evaluate("window.__diwan && window.__diwan.walks")
    print(f"· hand-offs walked in total: {walked2}")
    ctx.close()
    b.close()
print("video:", sorted((OUT / "video").glob("*.webm"))[-1])
print("console errors:", errors or "none")
