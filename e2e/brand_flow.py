"""The brand, end to end in a browser, as the Marketing manager would use it: draft the profile, edit it, save it, run
a listing, and check the scripts follow it; then see it in the 3D Brand brain.
python e2e/brand_flow.py http://127.0.0.1:8031 <out dir>"""
import re
import sys
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "brand"
OUT.mkdir(parents=True, exist_ok=True)
errors = []

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{BASE}/web/studio.html?ref=MC-1204")
    expect(pg.locator("#brandnote")).to_contain_text("Not set yet")
    pg.click("#branddraft")
    expect(pg.locator("#brandmsg")).to_contain_text(re.compile("Draft filled|needs|failed"), timeout=120_000)
    print("· draft:", pg.locator("#brandmsg").inner_text())
    draft = {t.get_attribute("id")[2:]: t.input_value() for t in pg.locator("#brandform textarea").all()}
    for k, v in draft.items():
        print(f"    {k:12} {v[:110]}")
    pg.screenshot(path=str(OUT / "1-draft.png"), full_page=True)
    # the manager edits: adds words the brand never uses, and a sign-off of her own
    pg.fill("#b-avoid", ", ".join(x for x in [draft.get("avoid", ""), "luxury", "once-in-a-lifetime", "hurry"] if x))
    pg.fill("#b-cta", "WhatsApp us and we'll walk you through it.")
    pg.click("#brandsave")
    expect(pg.locator("#brandmsg")).to_contain_text("Saved", timeout=10_000)
    expect(pg.locator("#brandnote")).to_contain_text("The writers use this")
    print("· saved:", pg.locator("#brandmsg").inner_text())

    pg.get_by_role("button", name="Run this listing").click()
    expect(pg.locator(".opt")).to_have_count(3, timeout=240_000)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(OUT / "2-scripts.png"), full_page=True)
    texts = [pg.locator(".opt").nth(i).locator("pre").inner_text() for i in range(3)]
    tags = [pg.locator(".opt").nth(i).locator(".tag").inner_text() for i in range(3)]
    for t, tx in zip(tags, texts):
        print(f"\n· {t}\n" + "\n".join("    " + ln for ln in tx.splitlines()))
    banned = [w for w in ["luxury", "once-in-a-lifetime", "hurry"] if any(w in tx.lower() for tx in texts)]
    assert not banned, f"a never-use word got through: {banned}"
    signed = sum("walk you through" in tx.lower() or "whatsapp" in tx.lower() for tx in texts)
    print(f"\n· scripts ending in the brand's own sign-off: {signed} of 3")

    pg.goto(f"{BASE}/web/office3d.html?enter=mkt")
    expect(pg.locator("#title h1")).to_contain_text("Marketing", timeout=20_000)
    pg.locator("#bar button", has_text="Brand brain").first.click()
    expect(pg.locator("#zbody")).to_contain_text("Brand profile", timeout=10_000)
    expect(pg.locator("#zbody")).to_contain_text("walk you through")
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(OUT / "3-brain.png"))
    print("· the 3D Brand brain shows the saved profile")
    b.close()
print("page errors:", errors or "none")
