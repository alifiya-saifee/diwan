"""Studio, end to end in a real browser: run a listing, see three scripts, ask for a change to one, pick one, upload a
take, and see the captioned cut and the publish request. Run against a server: python e2e/studio_flow.py http://127.0.0.1:8031"""
import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
SHOTS = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("e2e/shots")
TAKE = sys.argv[3] if len(sys.argv) > 3 else None
SHOTS.mkdir(parents=True, exist_ok=True)
errors = []

with sync_playwright() as p:
    watch = os.environ.get("WATCH") == "1"  # WATCH=1: a visible window, slowed down so a person can follow each click
    b = p.chromium.launch(headless=not watch, slow_mo=700 if watch else 0)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto(f"{BASE}/web/studio.html?ref=MC-1204")
    expect(pg.locator("#runbtn")).to_be_visible()
    pg.get_by_role("button", name="Run this listing").click()
    opts = pg.locator(".opt")
    expect(opts).to_have_count(3, timeout=60_000)
    angles = [opts.nth(i).locator(".tag").inner_text() for i in range(3)]
    print("offered:", angles)
    pg.screenshot(path=str(SHOTS / "1-three-scripts.png"), full_page=True)

    second = opts.nth(1)
    sid = second.get_attribute("data-script")
    before = second.locator("pre").inner_text().split("\n")[0]
    second.locator(".change").fill("make the hook shorter")
    second.get_by_role("button", name="Ask for change").click()
    revised = pg.locator(".opt").nth(1)
    expect(revised).not_to_have_attribute("data-script", sid, timeout=60_000)
    expect(revised).to_contain_text(f"revised from {sid}")
    after = revised.locator("pre").inner_text().split("\n")[0]
    print("hook before:", before, "| after:", after)
    assert len(after.split()) < len(before.split()), "the hook did not get shorter"
    assert pg.locator(".opt").nth(0).get_attribute("data-script") != sid
    pg.screenshot(path=str(SHOTS / "2-revised.png"), full_page=True)

    chosen = revised.get_attribute("data-script")
    revised.get_by_role("button", name="Use this one").click()
    expect(pg.locator("#made")).to_contain_text("Film list for", timeout=60_000)
    expect(pg.locator("#made")).to_contain_text("Post text", timeout=60_000)
    expect(pg.get_by_role("button", name="Make AI video")).to_be_visible()
    pg.screenshot(path=str(SHOTS / "3-approved.png"), full_page=True)
    print("approved", chosen)

    if TAKE:
        pg.set_input_files("#file", TAKE)
        pg.click("#up")
        expect(pg.locator("#upres")).to_contain_text("Uploaded", timeout=60_000)
        expect(pg.locator("#made video")).to_be_visible(timeout=240_000)
        expect(pg.get_by_role("button", name="Approve for this time")).to_be_visible(timeout=120_000)
        pg.screenshot(path=str(SHOTS / "4-cut-and-publish-request.png"), full_page=True)
        print("cut and publish request shown")
    b.close()

print("console errors:", errors or "none")
sys.exit(1 if errors else 0)
