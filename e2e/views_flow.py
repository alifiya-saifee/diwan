"""Every camera view of the 3D office, at two window sizes: no label may overlap another label or a panel.
Visits HQ, every stop on the Marketing floor while a listing runs, and the room view of every other department.
python e2e/views_flow.py http://127.0.0.1:8031 <out dir>"""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "views"
OUT.mkdir(parents=True, exist_ok=True)
SIZES = [(1440, 900), (1280, 720)]
DEPTS = ["Front desk", "Sales", "Records", "Review", "Operations", "Finance", "Compliance"]
bad, errors, checked = [], [], 0


def measure(pg, name):
    global checked
    pg.wait_for_timeout(1900)  # the camera has finished flying
    r = pg.evaluate("window.__diwanOverlaps()")
    checked += 1
    pg.screenshot(path=str(OUT / f"{name}.png"))
    flag = "" if r["overlaps"] == 0 else "   <-- OVERLAP"
    print(f"  {name:38} labels shown {r['shown']:3}  overlaps {r['overlaps']}{flag}")
    if r["overlaps"]:
        bad.append(name)
        print("     ", r["pairs"])


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    for w, h in SIZES:
        print(f"== {w}x{h}")
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(f"{BASE}/web/office3d.html")
        pg.wait_for_timeout(3500)
        measure(pg, f"{w}-hq")
        pg.locator("#bar button", has_text="Marketing").first.click()
        expect(pg.locator("#title h1")).to_contain_text("Marketing", timeout=15_000)
        pg.get_by_role("button", name="Run a listing through marketing").click()
        stops = pg.locator("#bar button").all_inner_texts()
        for s in stops:
            if s in ("← HQ", "▶ Tour", "■ Stop tour"):
                continue
            pg.locator("#bar button", has_text=s).first.click()
            measure(pg, f"{w}-mkt-{s.lower().replace(' ', '-')}")
        for d in DEPTS:
            pg.locator("#bar button", has_text="← HQ").first.click()
            pg.wait_for_timeout(1500)
            pg.locator("#bar button", has_text=d).first.click()
            pg.wait_for_timeout(1800)
            measure(pg, f"{w}-{d.lower().replace(' ', '-')}")
        pg.close()
    b.close()
print(f"views checked: {checked}; with overlaps: {len(bad)} {bad}")
print("page errors:", errors or "none")
sys.exit(1 if bad or errors else 0)
