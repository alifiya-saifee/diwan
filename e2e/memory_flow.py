"""The marketing memory graph in a browser: it draws the brand, the scripts and how they connect; clicking a node shows
its record; rewinding to before the brand removes it. python e2e/memory_flow.py http://127.0.0.1:8031 <out dir>"""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "memory"
OUT.mkdir(parents=True, exist_ok=True)
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 950})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{BASE}/web/graph.html?view=marketing")
    expect(pg.locator("#deal")).to_have_value("__marketing", timeout=10_000)
    expect(pg.locator("#sub")).to_contain_text("marketing team's memory")
    pg.wait_for_timeout(1200)
    labels = pg.locator("svg .node text").evaluate_all("els => els.map(e => e.textContent)")
    print(f"· {len(labels)} nodes drawn:", ", ".join(sorted(labels))[:400])
    assert "profile" in labels and "cta" in labels, labels
    pg.screenshot(path=str(OUT / "1-graph.png"))
    pg.locator("svg .node", has_text="profile").first.locator("circle").click()
    rec = pg.locator("#record").inner_text()
    print("· clicked brand profile:", rec[:160])
    print("  links:", pg.locator("#links").inner_text().replace("\n", " | ")[:300])
    approved = [l for l in labels if l.endswith("✓")]
    if approved:
        pg.locator("svg .node", has_text=approved[0]).first.locator("circle").click()
        print("· clicked the picked script:", pg.locator("#record").inner_text()[:220])
    pg.screenshot(path=str(OUT / "2-clicked.png"))
    pg.locator("#upto").fill("40")
    pg.locator("#upto").dispatch_event("input")
    pg.wait_for_timeout(800)
    early = pg.locator("svg .node text").evaluate_all("els => els.map(e => e.textContent)")
    print(f"· rewound to event 40: {len(early)} nodes; brand present: {'profile' in early}")
    assert "profile" not in early
    b.close()
print("page errors:", errors or "none")
