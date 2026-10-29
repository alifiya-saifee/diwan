"""The Deal desk, checked as a person would (docs/deal-desk.md). One screenshot per step.
Run against an offline test server with its own database, never diwan.db:
python e2e/deal_flow.py http://127.0.0.1:8041 <out dir>"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8041"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "deal"
OUT.mkdir(parents=True, exist_ok=True)
SAY = "Actually, forget my brother. I'll pay it all myself."
errors, results = [], []


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n} {name}{' · ' + note if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    api = pg.request
    api.post(f"{BASE}/api/demo/reset")

    def shot(name, full=True):
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full)

    def clear():
        pg.evaluate("document.querySelectorAll('.toast').forEach((t) => t.remove())")

    def toast():
        t = pg.locator(".toast").last
        t.wait_for(timeout=4000)
        return t.inner_text()

    def acting(who):
        pg.select_option("#as", who)
        pg.wait_for_timeout(300)

    # before: the deal as it stands, an approval and a deck on "Tariq will send the deposit"
    pg.goto(f"{BASE}/web/deal.html?deal=marina-1204")
    pg.wait_for_selector("#dept-fin .card")
    acting("ahmed")
    shot("1-before")
    check("1a", "before: A1 given, deck ready, Tariq's payment expected", pg.locator("#dept-fin").inner_text().count("given") >= 1
          and "Expect AED 260,000 by bank transfer from Tariq Haddad" in pg.locator("#dept-fin").inner_text())

    # the correction, typed at the meeting table
    pg.goto(f"{BASE}/web/meeting.html")
    pg.select_option("#deal", "marina-1204")
    pg.fill("#title", "Second meeting")
    pg.click("#start")
    pg.click("#consent")
    pg.select_option("#speaker", "customer")
    pg.fill("#text", SAY)
    pg.click("#say")
    pg.wait_for_function("document.querySelectorAll('#heard .ev').length >= 6", timeout=6000)
    shot("2-meeting")
    heard = pg.locator("#heard").inner_text()
    check("1b", "meeting: Compliance raised, tasks withdrawn, card, deck sent back",
          all(s in heard for s in ("Payment arrangement changed", "withdrew T1", "withdrew T2", "sent back D1")))

    # the Deal desk after: order of events, the replaced words, each department
    pg.goto(f"{BASE}/web/deal.html?deal=marina-1204")
    pg.wait_for_selector("#dept-comp .card")
    acting("ahmed")
    shot("3-after")
    evs = [e for e in api.get(f"{BASE}/api/events?deal=marina-1204").json() if e["id"] > 0]
    fact = max(i for i, e in enumerate(evs) if e["type"] == "fact.created")
    after = [e["type"] for e in evs[fact + 1:]]
    check("1c", "Compliance hears first (check.raised is the next event after the fact)", after[0] == "check.raised", ", ".join(after[:4]))
    said = pg.locator(".said").inner_text()
    check("1d", "history kept: F2 and F3 shown replaced by F7", said.count("replaced by F7") == 2 and ("replaces F2, F3" in said or "replaces F3, F2" in said))
    fin, rev, comp = (pg.locator(f"#dept-{k}").inner_text() for k in ("fin", "review", "comp"))
    check("1e", "Tariq's payment and screening withdrawn; Karim's expected", "WITHDRAWN" in fin.upper() and "from Karim Haddad" in fin
          and "Screen Tariq Haddad" in comp)
    check("1f", "deck sent back naming slide 3 and both quotes", "Slide 3 still says what F3 said" in rev)

    # Ahmed tries to carry out the stale approval
    clear()
    pg.locator("#dept-fin .card", has_text="A1").get_by_role("button", name="Carry it out").click()
    msg = toast()
    shot("4-blocked", full=False)
    check("1g", "executing A1 blocked with the reason", msg.startswith("Blocked") and "F3" in msg, msg)

    # someone else cannot answer his card
    acting("layla")
    check("1h", "Layla sees the card but cannot answer it", "Only Ahmed can answer this" in pg.locator("#dept-review").inner_text())

    # Ahmed re-approves: the old wording is refused, his own words are kept
    acting("ahmed")
    c = pg.locator("#dept-review .card.open", has_text="Your approval")
    clear()
    c.get_by_role("button", name="Re-approve on the new facts").click()
    msg = toast()
    check("1i", "the old wording is refused", "old wording" in msg, msg)
    c.locator("input").fill("Accept the AED 260,000 deposit from Karim Haddad")
    clear()
    c.get_by_role("button", name="Re-approve on the new facts").click()
    pg.wait_for_timeout(800)
    fin = pg.locator("#dept-fin").inner_text()
    check("1j", "A2 rests on F7 and F4", 'F7 "' in fin and 'F4 "' in fin.split('A2')[1] and "A2" in fin)
    clear()
    pg.locator("#dept-fin .card", has_text="A2").get_by_role("button", name="Carry it out").click()
    msg = toast()
    pg.wait_for_timeout(600)
    shot("5-reapproved")
    check("1k", "A2 carried out", "carried out" in msg, msg)

    # Priya marks the compliance check reviewed
    acting("priya")
    cc = pg.locator("#dept-comp .card.open", has_text="Payment arrangement changed")
    cc.locator("input").fill("Karim's own account; ask for the statement")
    cc.get_by_role("button", name="Reviewed").click()
    pg.wait_for_timeout(800)
    check("1l", "Priya's check closed with her answer", "Answered: Reviewed" in pg.locator("#dept-comp").inner_text())

    # Nova explains who pays, citing the live words
    pg.goto(f"{BASE}/web/index.html")
    pg.fill("#say", "Who is paying for Karim?")
    pg.click("#go")
    pg.wait_for_selector(".answer")
    shot("6-nova", full=False)
    ans = pg.locator(".answer").inner_text()
    check("1m", "Nova: Karim pays, citing F7 and F3 since replaced", "(F7)" in ans and "(F3), since replaced" in ans)

    # widths: no sideways scroll at 1280 or on a phone
    for w, hgt in ((1280, 900), (390, 844)):
        pg.set_viewport_size({"width": w, "height": hgt})
        pg.goto(f"{BASE}/web/deal.html?deal=marina-1204")
        pg.wait_for_selector("#dept-comp .card")
        sw = pg.evaluate("document.documentElement.scrollWidth")
        shot(f"7-width-{w}")
        check("7", f"no sideways scroll at {w}", sw <= w, f"scrollWidth {sw}")
    b.close()

print("page errors:", errors or "none")
print(f"{sum(r[2] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[2] for r in results) and not errors else 1)
