"""Knowledge and catalog, checked as a person would (docs/knowledge.md §6). One screenshot per definition-of-done item.
Run against a server whose database has the demo plus 1,000 feed listings; Rania replies through the sandbox phone.
python e2e/knowledge_flow.py http://127.0.0.1:8061 <out dir>"""
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8061"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "knowledge"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
YESTERDAY, LATER = (date.today() - timedelta(days=1)).isoformat(), (date.today() + timedelta(days=120)).isoformat()


def check(n, name, ok, shot, note=""):
    results.append((n, name, bool(ok), shot, note))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + note if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept("Sold off-market"))
    api = pg.request

    def shot(name, full=False):
        path = OUT / f"{name}.png"
        pg.screenshot(path=str(path), full_page=full)
        return path.name

    def as_(who):
        pg.select_option("#as", who)
        pg.wait_for_timeout(400)

    def item(title):
        return pg.locator(".item", has=pg.locator("h3", has_text=re.compile(f"^{re.escape(title)}$")))

    def tab(k):
        pg.click(f"#tabs [data-tab={k}]")
        pg.wait_for_timeout(400)

    def add(kind, title, text, audience="customer", review="", until="", applies=""):
        pg.select_option("#akind", kind)
        pg.select_option("#aaud", audience)
        pg.fill("#atitle", title)
        pg.fill("#atext", text)
        pg.fill("#areview", review)
        pg.fill("#auntil", until)
        if applies:
            pg.select_option("#aapplies", applies)
        pg.click("#aadd")
        expect(item(title)).to_be_visible()

    def rania(phone, text, name="Test Customer"):
        """Message the office as a customer from the Inbox's sandbox phone; return Rania's reply (or the handover)."""
        r0 = api.get(f"{BASE}/api/chats/{phone}")
        before = len(r0.json()["messages"]) if r0.ok else 0
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as=layla")
        pg.click("#phonebtn")
        pg.fill("#pname", name)
        pg.fill("#pnum", phone)
        pg.fill("#ptext", text)
        pg.click("#psend")
        for i in range(90):  # Rania replies, or hands the chat to a person (which may send no reply at all)
            r = api.get(f"{BASE}/api/chats/{phone}")
            d = r.json() if r.ok else {"messages": []}
            new = d["messages"][before:]
            if any(m["type"] == "sent" for m in new) or (d.get("mode") == "human" and i >= 5):
                break
            time.sleep(1)
        new = d.get("messages", [])[before:]
        sent = [m for m in new if m["type"] == "sent"]
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as=layla")
        pg.wait_for_timeout(1200)
        return {"text": sent[-1]["text"] if sent else "", "refs": sent[-1].get("refs", []) if sent else [], "mode": d.get("mode"), "messages": new}

    # ---------------- Knowledge page ----------------
    pg.goto(f"{BASE}/web/knowledge.html?tab=company")
    pg.evaluate("localStorage.clear()")
    pg.goto(f"{BASE}/web/knowledge.html?tab=company")
    as_("layla")
    tabs = pg.locator("#tabs").inner_text()
    check(1, "Tabs for each kind, with counts", all(k in tabs for k in ["Company", "Approved answers", "Projects", "Areas", "People", "Brand", "Listings catalog"])
          and re.search(r"Company\s*4", tabs) and "1004" in tabs, shot("01-tabs"), tabs.replace("\n", " "))

    # 4. add items (any kind) with audience and review date
    add("company", "Parking for viewings", "Visitor parking is on level B1 of every tower we list.", review=LATER)
    add("company", "Commission split", "Brokers keep 50% of the commission on their own deals.", audience="internal", review=LATER)
    add("company", "Ramadan hours", "During Ramadan we open 10am to 4pm.", review=LATER)
    tab("area")
    add("area", "Dubai Marina", "Metro: DMCC and Sobha Realty stations. Service charges run about AED 18 to 24 per sq ft.", review=YESTERDAY)
    p_ok = item("Dubai Marina").locator(".chip", has_text="stale").count() == 1
    tab("company")
    park = item("Parking for viewings")
    check(4, "Add an item (any kind) with audience and review date",
          park.locator(".chip", has_text="customer-facing").count() and item("Commission split").locator(".chip", has_text="internal only").count()
          and park.locator(".chip", has_text="review by").count() and p_ok, shot("04-add", True))

    # 2. one search across knowledge and the catalog
    pg.fill(".hsearch input", "parking")
    expect(pg.locator(".hresults")).to_contain_text("Parking for viewings")
    s1 = shot("02a-search-word")
    pg.fill(".hsearch input", "SX-0042")
    expect(pg.locator(".hresults")).to_contain_text("SX-0042")
    pg.fill(".hsearch input", "Burj Vista")
    expect(pg.locator(".hresults")).to_contain_text("Listing")
    s2 = shot("02b-search-catalog")
    pg.fill(".hsearch input", "lobby")  # a word only in the Viewings item's text
    expect(pg.locator(".hresults")).to_contain_text("Viewings")
    check(2, "Search finds an item by any word in its title or text, across knowledge and the catalog", True, f"{s1}, {s2}")
    pg.click("h1")

    # 3. filters
    pg.select_option("#faudience", "internal")
    pg.wait_for_timeout(400)
    only_internal = pg.locator("#list .item").count() == 1 and item("Commission split").count() == 1
    s1 = shot("03a-filter-internal")
    pg.select_option("#faudience", "")
    tab("area")
    pg.check("#fstale")
    pg.wait_for_timeout(400)
    stale_ok = item("Dubai Marina").count() == 1
    pg.uncheck("#fstale")
    tab("company")
    pg.select_option("#farea", "Dubai Marina")
    pg.wait_for_timeout(400)
    area_empty = pg.locator("#list").inner_text()
    pg.select_option("#farea", "")
    pg.select_option("#fstatus", "proposed")
    pg.wait_for_timeout(400)
    s2 = shot("03b-filter-status")
    status_ok = "Nothing matches" in pg.locator("#list").inner_text()
    pg.select_option("#fstatus", "")
    check(3, "Filters: status, audience, stale, area", only_internal and stale_ok and status_ok and "Nothing matches" in area_empty, f"{s1}, {s2}")

    # 10. usage, and the agents: Rania answers from the item, then from its edit
    r1 = rania("971500000101", "Hi, where can I park when I come for a viewing?")
    pg.goto(f"{BASE}/web/knowledge.html?tab=company")
    park = item("Parking for viewings")
    pid = park.get_attribute("data-id")
    used = park.locator(".usage").inner_text()
    check(10, "Usage: \"used in N replies\" on each item", pg.locator("#list .item .usage").count() == pg.locator("#list .item").count()
          and ("used in 1 reply" in used if pid in r1["refs"] else True), shot("10-usage", True), f"Parking: {used!r}; Rania cited {r1['refs']}: {r1['text'][:160]!r}")

    # 5. edit: new text, old version in history
    park.get_by_role("button", name="Edit").click()
    park.locator("[name=text]").fill("Visitor parking is on level B2 of every tower we list.")
    park.locator("[name=why]").fill("the towers moved visitor parking")
    park.get_by_role("button", name="Save").click()
    park = item("Parking for viewings")
    expect(park.locator(".text")).to_have_text(re.compile("level B2"))
    park.get_by_role("button", name="History").click()
    expect(park.locator(".hist")).to_contain_text("version 2")
    hist = park.locator(".hist").inner_text()
    check(5, "Edit an item: the new text shows, the old version is in its history", "B1" in hist and "level B2" in park.locator(".text").inner_text(),
          shot("05-edit-history", True), hist.replace("\n", " | ")[:300])

    r2 = rania("971500000102", "Where do visitors park for a viewing?")
    check(17, "After an edit, Rania's next answer uses the new text (sandbox line)", "B2" in r2["text"] and "B1" not in r2["text"], shot("17-rania-after-edit"),
          f"before: {r1['text'][:140]!r} · after: {r2['text'][:140]!r} · cited {r2['refs']}")

    # 6. retire, show retired, restore (on Ramadan hours), and retire Parking for the agent check
    pg.goto(f"{BASE}/web/knowledge.html?tab=company")
    ram = item("Ramadan hours")
    ram.get_by_role("button", name="Retire").click()
    ram.locator("[name=why]").fill("Ramadan is over")
    ram.get_by_role("button", name="Retire").last.click()
    expect(item("Ramadan hours")).to_have_count(0)
    s1 = shot("06a-retired-gone")
    pg.check("#fretired")
    expect(item("Ramadan hours")).to_be_visible()
    shown = item("Ramadan hours").inner_text()
    s2 = shot("06b-show-retired")
    item("Ramadan hours").get_by_role("button", name="Restore").click()
    pg.wait_for_timeout(500)
    pg.uncheck("#fretired")
    pg.wait_for_timeout(400)
    restored = item("Ramadan hours").locator(".chip", has_text="confirmed").count() == 1
    s3 = shot("06c-restored")
    check(6, "Retire with a reason; disappears; show retired brings it back; restore works", "Ramadan is over" in shown and restored, f"{s1}, {s2}, {s3}")

    park = item("Parking for viewings")
    park.get_by_role("button", name="Retire").click()
    park.locator("[name=why]").fill("visitor parking closed for works")
    park.get_by_role("button", name="Retire").last.click()
    expect(item("Parking for viewings")).to_have_count(0)
    r3 = rania("971500000103", "Where can I park for a viewing?")
    cited = [x for x in r3["refs"] if x == pid]
    check(18, "After a retire, no agent cites the item", not cited and "B2" not in r3["text"] and "B1" not in r3["text"], shot("18-rania-after-retire"),
          f"{r3['text'][:200]!r} · cited {r3['refs']} · chat mode {r3['mode']}")

    r4 = rania("971500000104", "What share of the commission do your brokers keep?")
    check(19, "An internal-only item is never said to a customer", "50%" not in r4["text"], shot("19-rania-internal"), f"{r4['text'][:200]!r} · cited {r4['refs']}")

    r5 = rania("971500000105", "Do you also sell yachts or boat moorings?")
    check(20, "A question with no matching item is handed to a person", r5["mode"] == "human" or not r5["text"], shot("20-rania-no-match"),
          f"{r5['text'][:200]!r} · chat mode {r5['mode']}")

    # 7. a non-owner's edit is a proposal the owner accepts or rejects
    pg.goto(f"{BASE}/web/knowledge.html?tab=company")
    as_("omar")
    hrs = item("Office hours")
    hrs.get_by_role("button", name="Propose a change").click()
    hrs.locator("[name=text]").fill("We're open Monday to Saturday, 9am to 8pm. Viewings run in the same hours.")
    hrs.locator("[name=why]").fill("we open earlier now")
    hrs.get_by_role("button", name="Propose", exact=True).click()
    pg.wait_for_timeout(600)
    unchanged = "10am to 7pm" in item("Office hours").locator(".text").inner_text()
    s1 = shot("07a-proposed-by-omar")
    as_("layla")
    prop = pg.locator("[data-proposal]").first
    prop.get_by_role("button", name="Accept").click()
    expect(item("Office hours").locator(".text")).to_contain_text("9am to 8pm")
    s2 = shot("07b-accepted-by-layla")
    as_("omar")
    item("Viewings").get_by_role("button", name="Propose a change").click()
    item("Viewings").locator("[name=text]").fill("Viewings need no ID.")
    item("Viewings").get_by_role("button", name="Propose", exact=True).click()
    pg.wait_for_timeout(500)
    as_("layla")
    pg.locator("[data-proposal]").first.get_by_role("button", name="Reject").click()
    pg.wait_for_timeout(500)
    rejected = "photo ID" in item("Viewings").locator(".text").inner_text()
    check(7, "A non-owner's edit becomes a proposal the owner can accept or reject", unchanged and rejected, f"{s1}, {s2}, {shot('07c-rejected')}")

    # 8. stale, one-click re-confirm
    tab("area")
    marina = item("Dubai Marina")
    s1 = shot("08a-stale")
    marina.get_by_role("button", name="Re-confirm").click()
    pg.wait_for_timeout(500)
    ok = item("Dubai Marina").locator(".chip", has_text="stale").count() == 0
    check(8, "Stale items are marked, with a one-click re-confirm", ok, f"{s1}, {shot('08b-reconfirmed')}")

    # 9. empty states
    msgs = {}
    for k in ["answer", "project", "people", "brand"]:
        tab(k)
        msgs[k] = pg.locator("#empty").inner_text() if pg.locator("#empty").count() else ""
    tab("project")
    check(9, "Empty state for each tab says what to add and how", all("Add an item" in m for m in msgs.values()), shot("09-empty-project"),
          " | ".join(m.split("\n")[0] for m in msgs.values()))

    # ---------------- Catalog ----------------
    pg.goto(f"{BASE}/web/knowledge.html")
    pg.click("text=Listings catalog")
    expect(pg.locator("#count")).to_contain_text("1,004")
    cards = pg.locator(".card").count()
    ms = pg.evaluate("window.__catalogMs")
    t0 = time.time()
    pg.mouse.wheel(0, 6000)
    pg.wait_for_timeout(300)
    s1 = shot("11a-catalog")
    pg.click("#next")
    expect(pg.locator("#count")).to_contain_text("51–100")
    ms2 = pg.evaluate("window.__catalogMs")
    check(11, "1,000 listings load and scroll without lag (paged, 50 at a time)", cards == 50 and ms < 1000 and ms2 < 1000, f"{s1}, {shot('11b-page2')}",
          f"{cards} cards on a page; page 1 in {ms:.0f} ms, page 2 in {ms2:.0f} ms")

    pg.click("#clear")
    pg.select_option("#area", "Dubai Marina")
    pg.select_option("#beds", "2")
    pg.fill("#min", "1000000")
    pg.fill("#max", "2500000")
    pg.select_option("#status", "available")
    pg.select_option("#agent", "nadia")
    pg.select_option("#permit", "yes")
    pg.wait_for_timeout(800)
    rows = api.get(f"{BASE}/api/catalog?area=Dubai%20Marina&beds=2&min_price=1000000&max_price=2500000&status=available&agent=nadia&permit=yes").json()["rows"]
    good = rows and all(r["listing"]["community"] == "Dubai Marina" and r["listing"]["beds"] == 2 and 1e6 <= r["listing"]["price_aed"] <= 2.5e6
                        and r["status"] == "available" and r["listing"]["agent"] == "nadia" and r["listing"]["permit"] for r in rows)
    check(12, "Filters: area, beds, price range, status, agent, has permit", good and pg.locator(".card").count() == len(rows), shot("12-filters"),
          pg.locator("#count").inner_text())

    pg.click("#clear")
    found = {}
    for q in ["SX-0042", "Burj Vista", "Villa"]:
        pg.fill(".hsearch input", q)
        pg.wait_for_timeout(700)
        found[q] = pg.locator("#count").inner_text().split(" of")[0]
        if q == "SX-0042":
            one = pg.locator(".card").count() == 1 and pg.locator(".card[data-ref='SX-0042']").count() == 1
    check(13, "Search by reference, building or title", one and all(v != "0" for v in found.values()), shot("13-search-building"), str(found))

    pg.click("#clear")
    pg.wait_for_timeout(600)
    c = pg.locator(".card").first
    has = [c.locator(".ph").count(), c.locator(".price").count()]
    with_img = pg.locator(".card .ph img").count()
    placeholders = pg.locator(".card .ph", has_text="No photo").count()
    check(14, "Each listing shows a photo (from the feed) or a clear placeholder, price, permit, status and agent",
          all(has) and with_img + placeholders == 50 and with_img and placeholders, shot("14-cards"), f"{with_img} with a feed photo, {placeholders} with the placeholder")

    pg.select_option("#permit", "no")
    pg.wait_for_timeout(700)
    np_ref = pg.locator(".card").first.get_attribute("data-ref")
    marked = pg.locator(".card").first.locator(".chip", has_text="not advertised").count() == 1
    s1 = shot("15a-no-permit")
    r6 = rania("971500000106", f"Hi, is {np_ref} still available? What's the price?")
    check(15, "A listing without a permit is marked \"not advertised\" and never offered by Rania or the studio",
          marked and np_ref not in r6["text"] and not any(np_ref in x for x in r6["refs"]), f"{s1}, {shot('15b-rania-no-permit')}",
          f"{np_ref}: Rania said {r6['text'][:160]!r} (cited {r6['refs']}); studio: code test only (test_no_permit_no_reel)")

    # 16. a broker's price change is a proposal; the owner accepts; Rania quotes the new price at once
    pg.goto(f"{BASE}/web/catalog.html?q=MC-1204")
    as_("omar")
    pg.locator(".card[data-ref='MC-1204']").click()
    old = pg.locator("#newprice").input_value()
    pg.fill("#newprice", "2350000")
    pg.fill("#pricewhy", "the seller agreed to drop")
    pg.click("#pricego")
    pg.wait_for_timeout(800)
    s1 = shot("16a-broker-proposes")
    still = api.get(f"{BASE}/api/catalog?q=MC-1204").json()["rows"][0]["listing"]["price_aed"]
    as_("layla")
    pg.locator("[data-proposal]").first.get_by_role("button", name="Accept").click()
    pg.wait_for_timeout(900)
    pg.locator(".card[data-ref='MC-1204']").click()
    expect(pg.locator("#detail .hist")).to_contain_text("version 2")
    s2 = shot("16b-owner-accepts")
    r7 = rania("971500000107", "How much is MC-1204?")
    check(16, "A broker's price change is a proposal; once accepted it is a new version and Rania quotes the new price at once",
          still == int(old) and "2,350,000" in r7["text"], f"{s1}, {s2}, {shot('16c-rania-new-price')}", f"old {int(old):,}; Rania: {r7['text'][:160]!r}")

    # 17b. a price agreed with one customer stays in that deal
    rania("971500000108", "Hi, I'm interested in MC-1204", name="Customer A")
    pg.goto(f"{BASE}/web/inbox.html?chat=971500000108&as=omar")
    api.post(f"{BASE}/api/chats/971500000108/send", data=json.dumps({"text": "For you only: MC-1204 at AED 2,100,000 if you sign this week.", "by": "omar"}),
             headers={"Content-Type": "application/json"})
    pg.reload()
    pg.wait_for_timeout(1000)
    s1 = shot("16d-agreed-with-A")
    r8 = rania("971500000109", "What's the best price on MC-1204?", name="Customer B")
    check(161, "A price agreed with one customer stays in that deal: Rania never offers it to another", "2,100,000" not in r8["text"] and "2.1" not in r8["text"],
          f"{s1}, {shot('16e-customer-B')}", f"Customer B heard: {r8['text'][:180]!r}")

    # ---------------- Memory graph ----------------
    pg.goto(f"{BASE}/web/graph.html?view=knowledge")
    pg.wait_for_timeout(2500)
    labels = pg.locator("svg .node text").evaluate_all("els => els.map(e => e.textContent)")
    v2 = [l for l in labels if "Parking for viewings" in l]
    pg.locator("svg .node", has_text="Parking for viewings v1").first.locator("circle").click()
    rec1 = pg.locator("#record").inner_text()
    s1 = shot("21a-graph-version")
    pg.locator("svg .node", has_text="(retired)").first.locator("circle").click()
    rec2 = pg.locator("#record").inner_text()
    check(21, "Memory graph: an edit shows as version 2 replacing version 1; a retire shows the item dimmed with its reason",
          any(l.endswith("v1 ✕") for l in v2) and any("v2" in l for l in v2) and "retired:" in rec2, f"{s1}, {shot('21b-graph-retired')}",
          f"{v2} · v1: {rec1[:120]!r} · retired: {rec2[:160]!r}")
    b.close()

print("\npage errors:", errors or "none")
print(f"{sum(r[2] for r in results)}/{len(results)} passed")
(OUT / "results.json").write_text(json.dumps(results, indent=1))
