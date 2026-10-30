"""The AI builds the company's knowledge graph, in a browser: load the demo profile, the Brand brain proposes cards with
quotes, a person confirms them, the brand draft is saved, and the memory graph shows it all with its source.
python e2e/learn_flow.py http://127.0.0.1:8031 <out dir>"""
import re
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "learn"
OUT.mkdir(parents=True, exist_ok=True)
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(f"{BASE}/web/studio.html?ref=MC-1204#setup")
    pg.locator("#learnbox summary").click()
    pg.click("#learndemo")
    expect(pg.locator("#learndoc")).to_have_value(re.compile("Diwan Realty"), timeout=10_000)
    pg.click("#learngo")
    expect(pg.locator("#learnres")).to_contain_text("knowledge cards proposed", timeout=180_000)
    print(pg.locator("#learnres").inner_text())
    pg.screenshot(path=str(OUT / "1-proposed.png"), full_page=True)
    filled = {t.get_attribute("id")[2:]: t.input_value() for t in pg.locator("#brandform textarea").all()}
    print("\n· brand draft filled in:")
    for k, v in filled.items():
        print(f"    {k:12} {v[:120]}")

    # a person confirms the proposed cards on the Knowledge page
    pg.goto(f"{BASE}/web/knowledge.html")
    n = pg.get_by_role("button", name="Confirm").count()
    for _ in range(n):
        pg.get_by_role("button", name="Confirm").first.click()
        pg.wait_for_timeout(250)
    print(f"\n· confirmed {n} cards on the Knowledge page")
    pg.screenshot(path=str(OUT / "2-knowledge.png"), full_page=True)

    # save the brand draft (back in the Studio the form is reloaded empty, so learn again is not needed: re-fill from the draft values)
    pg.goto(f"{BASE}/web/studio.html?ref=MC-1204")
    for k, v in filled.items():
        if v:
            pg.fill(f"#b-{k}", v)
    pg.click("#brandsave")
    expect(pg.locator("#brandmsg")).to_contain_text("Saved", timeout=10_000)
    print("· brand saved:", pg.locator("#brandmsg").inner_text())

    pg.goto(f"{BASE}/web/graph.html?view=marketing")
    pg.wait_for_timeout(1500)
    labels = pg.locator("svg .node text").evaluate_all("els => els.map(e => e.textContent)")
    print(f"\n· memory graph: {len(labels)} nodes")
    src = [l for l in labels if "profile" in l and l != "profile"]
    assert "profile" in labels and src, labels
    pg.locator("svg .node", has_text="profile").first.locator("circle").click()
    print("  brand profile links:", pg.locator("#links").inner_text().replace("\n", " | ")[:500])
    pg.screenshot(path=str(OUT / "3-graph.png"))
    b.close()
print("page errors:", errors or "none")
