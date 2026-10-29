"""The Deal desk, checked as a person would (docs/deal-desk.md). One screenshot per step.
Run against an offline test server with its own database, never diwan.db:
python e2e/deal_flow.py http://127.0.0.1:8041 <out dir> [--scale]"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8041"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "deal"
SCALE = "--scale" in sys.argv  # add 300 enquiries for the scale checks (about a minute)
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
          all(s in heard for s in ("Payment arrangement changed", "withdrew T2", "withdrew T3", "sent back D1")))

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

    # ---------- 3. Compliance, on a fresh demo office, as Priya ----------
    api.post(f"{BASE}/api/demo/reset")

    def meeting(*lines):
        pg.goto(f"{BASE}/web/meeting.html")
        pg.select_option("#deal", "marina-1204")
        pg.click("#start")
        pg.click("#consent")
        for t in lines:
            n = pg.locator("#heard .ev").count()
            pg.fill("#text", t)
            pg.click("#say")
            pg.wait_for_function(f"document.querySelectorAll('#heard .ev').length > {n}", timeout=6000)

    def desk(who="priya"):
        pg.goto(f"{BASE}/web/deal.html?deal=marina-1204")
        pg.wait_for_selector("#dept-comp .card")
        acting(who)
        return pg.locator("#dept-comp")

    comp = desk()
    shot("8-compliance")
    t = comp.inner_text()
    check("3a", "every party up for screening: Karim (buyer) and Tariq (brother)", "Screen Karim Haddad, the buyer" in t and "Screen Tariq Haddad, Karim Haddad's brother" in t)
    check("3b", "source of funds: numbers with quotes, 4 proof missing (Tariq still pays)", "4.8" in t and "4 proof missing" in t and "Bank statement of Tariq Haddad's account" in t)
    acting("ahmed")
    check("3c", "Ahmed cannot record a screening", "Only Priya records a screening result" in comp.inner_text())
    acting("priya")
    k = comp.locator(".card", has_text="Screen Karim Haddad")
    clear()
    k.get_by_role("button", name="Possible match").click()
    check("3d", "a possible match needs the entry", "Say which list" in toast())
    k.locator("input").fill("UN consolidated and UAE local lists: no entry")
    k.get_by_role("button", name="Clear").click()
    pg.wait_for_timeout(700)
    check("3e", "Karim recorded clear by Priya, with her note", "Clear: UN consolidated and UAE local lists: no entry" in comp.inner_text())
    comp.locator(".card", has_text="Source of funds").get_by_role("button", name="Received").first.click()
    pg.wait_for_timeout(700)
    t = comp.inner_text()
    check("3f", "bank statement received: filed with Records, 3 missing", "3 proof missing" in t and "Received: DOC" in t)

    meeting("Actually, I'll bring the deposit in cash, two hundred sixty thousand.")
    comp = desk()
    shot("9-cash-report")
    t = comp.inner_text()
    check("3g", "cash AED 260,000 → report draft and a filing task for Priya", "cash report v1" in t and "File the cash report" in t and "I filed it" in t)
    clear()
    comp.get_by_role("button", name="I filed it").click()
    check("3h", "filing needs the goAML reference", "goAML reference" in toast())
    meeting("Actually, the deposit of two hundred sixty thousand goes by bank transfer.")
    comp = desk()
    shot("10-cash-sent-back")
    t = comp.inner_text()
    check("3i", "a correction sends the report back and withdraws the filing task",
          "SENT BACK" in t.upper() and "still says what" in t and comp.locator(".card", has_text="File the cash report").get_by_text("withdrawn").count() == 1)

    # ---------- 4. Finance, on a fresh demo office, as Ahmed ----------
    api.post(f"{BASE}/api/demo/reset")
    desk("ahmed")
    fin = pg.locator("#dept-fin")
    p = fin.locator(".card", has_text="Expect AED 260,000 by bank transfer from Tariq Haddad")
    check("4a", "expected payment with its quote and due day", 'Due ' in p.inner_text() and '("next week")' in p.inner_text() and "F4" in p.inner_text())
    clear()
    p.get_by_role("button", name="Received").click()
    check("4b", "received needs a reference", "reference" in toast())
    p.locator("input").fill("ENBD 4471")
    p.get_by_role("button", name="Received").click()
    pg.wait_for_timeout(700)
    p = fin.locator(".card", has_text="Expect AED 260,000 by bank transfer from Tariq Haddad")
    check("4c", "marked received with the reference; receipt filed with Records",
          "Received, reference ENBD 4471" in p.inner_text() and any(e["type"] == "document.filed" and e["content"]["kind"] == "receipt"
                                                                    for e in api.get(f"{BASE}/api/events?deal=marina-1204").json()))
    p.get_by_role("button", name="Approve release").click()
    pg.wait_for_timeout(700)
    rel = fin.locator(".card", has_text="Release AED 260,000")
    check("4d", "release is Ahmed's approval resting on the payment's words", rel.count() == 1 and "F3" in rel.inner_text())
    shot("11-finance")
    meeting(SAY)
    desk("ahmed")
    clear()
    pg.locator("#dept-fin .card", has_text="Release AED 260,000").get_by_role("button", name="Carry it out").click()
    msg = toast()
    shot("12-release-refused")
    check("4e", "after the correction the release is refused with the reason", msg.startswith("Blocked") and "F3" in msg, msg)
    stray = re.findall(r"\b(null|undefined|NaN)\b", pg.locator("main").inner_text())
    check("4f", "no stray null / undefined / NaN on the screen", not stray, ", ".join(stray))

    # ---------- 5 and 6. Paperwork and Review, on a fresh demo office, as Joseph ----------
    api.post(f"{BASE}/api/demo/reset")
    desk("joseph")
    ops = pg.locator("#dept-ops")
    ops.get_by_role("button", name="Prepare Form F").click()
    pg.wait_for_timeout(800)
    t = ops.inner_text()
    shot("13-formf-plan")
    check("5a", "Form F plan from live facts, passed review, stops before Submit",
          "Form F v1" in t and "PASSED REVIEW" in t.upper() and "Deposit paid by: Tariq Haddad" in t and "Seller: not said; Joseph fills it" in t and "I submitted it" in t)
    acting("omar")
    check("5b", "only Joseph may mark it submitted", "Only Joseph submits portal forms" in ops.inner_text())
    meeting(SAY)
    desk("joseph")
    t = ops.inner_text()
    shot("14-formf-sent-back")
    check("5c", "the correction sends v1 back with the reason and withdraws its submit step",
          "still says what F3 said" in t and ops.locator(".card", has_text="Submit Form F D2").get_by_text("withdrawn").count() == 1)
    check("5d", "a new plan from the live words: Karim pays", "Form F v2" in t and "Deposit paid by: Karim Haddad" in t)
    card = ops.locator(".card", has_text="Submit Form F D3")
    clear()
    card.get_by_role("button", name="I submitted it").click()
    check("5e", "submitting needs the portal reference", "portal reference" in toast())
    card.locator("input").fill("DLD-88123")
    card.get_by_role("button", name="I submitted it").click()
    pg.wait_for_timeout(800)
    t = ops.inner_text()
    check("5f", "transfer checklist with who each step waits on", "Developer NOC for the transfer" in t and "waiting on the seller and the developer" in t)
    ops.locator(".card", has_text="Form F signed by buyer").get_by_role("button", name="Done").click()
    pg.wait_for_timeout(700)
    shot("15-transfer")
    check("5g", "Joseph ticks a step", ops.locator(".card", has_text="Form F signed by buyer").get_by_text("done").count() >= 1)
    rev = pg.locator("#dept-review").inner_text()
    check("6a", "Review: the deck sent back names the slide and the replacement", "Slide 3 still says what F3 said; the customer replaced it (F7)" in rev)

    # ---------- 7. the floors and the list at scale ----------
    for k in ("comp", "fin", "ops", "review"):
        pg.goto(f"{BASE}/web/office3d.html?enter={k}")
        pg.wait_for_function("window.__diwan && window.__diwan.floor", timeout=15000)
        pg.wait_for_timeout(2500)
        shot(f"16-floor-{k}", full=False)
        for i in (0, 1):
            url = pg.evaluate(f"window.__diwan.floor.walls[{i}].c.toDataURL('image/png')")
            (OUT / f"16-floor-{k}-wall{i}.png").write_bytes(__import__("base64").b64decode(url.split(",", 1)[1]))
    check("7a", "each Deal desk floor drew its walls (saved for review)", all((OUT / f"16-floor-{k}-wall1.png").exists() for k in ("comp", "fin", "ops", "review")))

    if SCALE:  # 300 more deals, arriving the way real ones do: an enquiry each on the sandbox WhatsApp line
        for i in range(300):
            api.post(f"{BASE}/api/chats/incoming", data={"phone": f"+97150{i:07d}", "text": "Hi, is the Marina unit still available?", "name": f"Buyer {i:03d}"})
        pg.set_viewport_size({"width": 1440, "height": 1000})
        pg.goto(f"{BASE}/web/deal.html#deals")
        pg.wait_for_selector(".tablebox tbody tr")
        rows = pg.locator(".tablebox tbody tr")
        check("7b", "302 deals in the table, 50 a page", "302 of 302 deals" in pg.locator("#pager").inner_text() and "1 / 7" in pg.locator("#pager").inner_text()
              and rows.count() == 50)
        pg.locator("#pager button", has_text="›").click()
        pg.wait_for_timeout(500)
        check("7c", "next page", "2 / 7" in pg.locator("#pager").inner_text())
        pg.fill("#q", "buyer 250")
        pg.wait_for_timeout(800)
        check("7d", "search finds one deal among 302", rows.count() == 1 and "Buyer 250" in rows.first.inner_text())
        pg.fill("#q", "zzz nobody")
        pg.wait_for_timeout(800)
        check("7e", "no match says so", "No deal matches" in pg.locator(".tablebox").inner_text())
        pg.fill("#q", "")
        pg.wait_for_timeout(800)
        pg.locator(".filters button", has_text="Waiting for someone").click()
        pg.wait_for_timeout(600)
        shot("17-table-waiting", full=False)
        check("7f", "waiting for someone: only the 2 demo deals", "2 of 302 deals" in pg.locator("#pager").inner_text())
        pg.locator(".tablebox th", has_text="Value").click()
        pg.wait_for_timeout(600)
        check("7h", "sorted by value, largest first", rows.first.inner_text().startswith("Karim Haddad"))
    pg.goto(f"{BASE}/web/deal.html?deal=nope")
    pg.wait_for_timeout(800)
    check("7g", "an unknown deal says so", "There is no deal 'nope'." in pg.locator("#main").inner_text())

    # ---------- 8. the three views: Overview, My work, Deals (fresh demo office, Karim has corrected himself) ----------
    api.post(f"{BASE}/api/demo/reset?correction=true")
    pg.set_viewport_size({"width": 1440, "height": 1000})
    pg.goto(f"{BASE}/web/deal.html#overview")
    pg.wait_for_selector(".tile")
    acting("priya")
    pg.wait_for_timeout(500)
    shot("18-overview")
    ov = pg.locator("#view").inner_text()
    comp_tile = pg.locator(".tile", has_text="Compliance").inner_text()
    check("8a", "overview: the latest correction, Compliance first, and what it set off",
          "Actually, forget my brother" in ov and "1st" in ov and "2\ntasks withdrawn" in ov and "1\ndraft sent back" in ov)
    check("8b", "each compliance count stands on its own (the open check is counted)", "Payer changed, to review\n1" in comp_tile and "Not screened\n2" in comp_tile, comp_tile.replace("\n", " | "))
    pg.locator(".tile .r", has_text="Not screened").click()
    pg.wait_for_selector(".tablebox tbody tr")
    pg.wait_for_timeout(400)
    check("8c", "a number opens exactly its deals", "#deals" in pg.url and "2 of 2 deals · Not screened" in pg.locator("#pager").inner_text())
    pg.locator(".tablebox tbody tr", has_text="Sara Malik").click()
    pg.wait_for_selector("#dept-comp .card")
    check("8d", "a row opens the deal in the side panel", "Sara Malik" in pg.locator("#main h1").inner_text() and pg.locator("aside.drawer").is_visible())
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(300)
    check("8e", "Escape closes the panel", not pg.locator("aside.drawer").is_visible())

    pg.goto(f"{BASE}/web/deal.html#my-work")
    pg.wait_for_selector(".q")
    acting("priya")
    pg.wait_for_timeout(600)
    q = pg.locator(".q")
    shot("19-my-work-priya", full=False)
    n0 = q.count()
    check("8f", "Priya's queue: the payer check first, then screenings and proof", n0 == 4 and "Payment arrangement changed" in q.first.inner_text(), f"{n0} rows")
    row = q.filter(has_text="Screen Karim Haddad")
    row.locator("input").fill("UN, UAE lists: no entry")
    row.get_by_role("button", name="Clear").click()
    pg.wait_for_timeout(1200)
    check("8g", "cleared inline: the row leaves the queue", q.count() == n0 - 1 and not q.filter(has_text="Screen Karim Haddad").count())
    pg.locator(".person", has_text="Omar").click()
    pg.wait_for_timeout(800)
    row = q.filter(has_text="How is Sara Malik funding")
    clear()
    row.get_by_role("button", name="Answer").click()
    check("8h", "an empty answer is refused", "Write the answer" in toast())
    row.locator("input").fill("Mortgage pre-approval with ENBD, 70%")
    row.get_by_role("button", name="Answer").click()
    pg.wait_for_timeout(1200)
    shot("20-my-work-omar-clear", full=False)
    check("8i", "Omar answered: all clear", "All clear" in pg.locator("#view").inner_text())
    pg.locator(".person", has_text="Ahmed").click()
    pg.wait_for_timeout(800)
    q.filter(has_text="Your approval").get_by_role("button", name="Re-approve…").click()
    pg.wait_for_selector("#dept-review .card")
    check("8j", "a decision opens the deal at the card that needs his words", "Karim Haddad" in pg.locator("#main h1").inner_text()
          and pg.locator("#dept-review .card.open", has_text="Your approval").count() == 1)

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
