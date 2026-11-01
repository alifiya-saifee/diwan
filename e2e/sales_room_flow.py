"""The Front Desk and the Sales room as people use them (docs/closed-loop-spec.md, Rooms 1 and 2). A fresh offline server, DIWAN_AUTH=off:
python e2e/sales_room_flow.py http://127.0.0.1:8031 <out dir>"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8031"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "salesroom"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
# E2E_RUN gives new clients, so it can run in an office that already has earlier test clients
RUN = os.environ.get("E2E_RUN", "01")
PH, PH2, PH3, PH4 = (f"97150777{RUN}{n}" for n in ("01", "02", "03", "04"))
QUAL = ("I want to buy", "Dubai Marina", "An apartment", "1 bed", "Budget is 1.4 million", "Cash", "Now", "To live in", "UAE resident")


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + str(note)[:160] if note else ''}")


with sync_playwright() as p:
    watch = bool(os.environ.get("WATCH"))  # WATCH=1: a visible window, slowed down enough to follow
    b = p.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "chrome"), headless=not watch, slow_mo=350 if watch else 0)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 500 else None)
    api = pg.request

    def shot(name):
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)

    def customer(phone, text, who="Sara Khan"):
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": who}, timeout=120000)  # a live model can take a while
        return [m["text"] for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"] if m["type"] == "sent"]

    def pa(text):
        n = pg.locator(".pa-m").count()
        pg.locator(".pa-panel input").fill(text)
        pg.locator(".pa-panel input").press("Enter")
        pg.wait_for_function(f"document.querySelectorAll('.pa-m').length >= {n + 2}", timeout=60000)  # a live model can take a while
        return pg.locator(".pa-m").last.inner_text()

    # ---- a lead, in the Inbox ----
    customer(PH, "Hello")
    customer(PH, "I want to buy")
    customer(PH, "Dubai Marina")
    pg.goto(f"{BASE}/web/inbox.html?as=layla&chat={PH}")
    pg.wait_for_selector(".big")
    pg.wait_for_timeout(600)
    check(1, "The lead shows Qualifying 1/8, not 'step 3 of 8'", "Qualifying 1/8" in pg.locator("#prof").inner_text() and " of 8" not in pg.locator("#prof").inner_text().replace("Qualifying 1/8", ""))
    r = customer(PH, "Can someone call me please?")[-1]
    check(2, "Rania promises the owner's number of minutes", "in the next 10 minutes" in r or "shortly" in r, r)
    pg.reload()
    pg.wait_for_selector(".banner.att")
    t = pg.locator(".banner.att").inner_text()
    check(3, "The card has a Call now button and the client's words", "Call now" in t and "Client:" in t, t)
    shot("01-inbox-card")

    # ---- the Sales room ----
    pg.goto(f"{BASE}/web/sales.html")
    pg.wait_for_selector("h2:has-text('Call now')")
    pg.wait_for_timeout(500)
    body = pg.locator("#board").inner_text().lower()
    check(4, "Every block of the Sales room is on the page", all(x in body for x in ("call now", "outcome needed", "hot leads", "new leads", "qualifying", "follow-ups due today", "quiet clients", "broker's day")))
    check(5, "The queue has a one-tap call", pg.locator(f"a[href='tel:+{PH}']").count() == 1)
    shot("02-sales-room")
    pg.locator(".srow", has=pg.locator(f"a[href='tel:+{PH}']")).locator("button:has-text('Called')").click()
    pg.wait_for_selector(f"#out-{PH}", timeout=8000)
    check(6, "Called: the lead now needs an outcome", pg.locator(f"#out-{PH}").count() == 1)
    pg.locator(f"#out-{PH} button:has-text('Not interested')").click()
    pg.locator(f"#out-{PH} select").select_option("other")
    pg.locator(f"#out-{PH} button:has-text('Save')").click()
    pg.wait_for_timeout(500)
    check(7, "'Other' with no note is refused", pg.locator(f"#out-{PH}").count() == 1 and api.get(f"{BASE}/api/chats/{PH}").json()["stage"] != "Lost")
    pg.locator(f"#out-{PH} button:has-text('No response')").click()
    pg.wait_for_selector(f"#out-{PH}", state="detached", timeout=8000)
    check(8, "An outcome clears it", pg.locator(f"#out-{PH}").count() == 0)

    pg.locator("#addbtn").click()
    pg.locator("form.add input").nth(0).fill("Mona Said")
    pg.locator("form.add input").nth(1).fill(PH3)
    pg.locator("form.add select").select_option("walk_in")
    pg.locator("form.add textarea").fill("Came in about a 2 bed in JVC")
    shot("03-add-lead")
    pg.locator("form.add button[type=submit]").click()
    pg.wait_for_timeout(800)
    check(9, "A walk-in becomes a call in the queue", "Mona Said" in pg.locator("#board").inner_text())

    # ---- qualified, heat, a viewing ----
    for t in QUAL:
        customer(PH2, t, "Ali Rahman")
    d = api.get(f"{BASE}/api/chats/{PH2}").json()
    check(10, "Qualified only when the whole form is done, with a heat score", d["stage"] == "Qualified" and d["progress"]["complete"] and d["heat"]["score"] == 3, d["heat"])
    customer(PH2, "Is MC-1204 still available?", "Ali Rahman")

    # ---- Nova: the day ----
    pg.goto(f"{BASE}/web/index.html")
    pg.wait_for_selector("#day h2")
    pg.wait_for_timeout(600)
    text = pg.locator("#day").inner_text().lower()
    check(11, "Nova's day has its blocks", all(x in text for x in ("urgent", "today", "decisions", "pipeline", "money")))
    check(12, "The greeting is by name", "Layla" in pg.locator("#hello").inner_text(), pg.locator("#hello").inner_text())
    shot("04-nova-day")

    # ---- the PA box on any page ----
    pg.goto(f"{BASE}/web/calendar.html")
    pg.wait_for_selector(".pa-open")
    pg.locator(".pa-open").click()
    a = pa("Remind me tomorrow at 10am to call Sara")
    check(13, "'Remind me' from the box on another page", "I'll remind you" in a, a)
    a = pa("Mark AED 50,000 received from Sara")
    check(14, "A PA refuses what only a person does", "Only a person marks money received" in a, a)
    a = pa("Draft a reply to Ahmed about the invoice")
    check(15, "An errand ends in a draft", "Shall I keep this" in a, a)
    shot("05-pa-box")
    pg.goto(f"{BASE}/web/index.html")
    pg.wait_for_selector("#day h2")
    pg.wait_for_timeout(500)
    check(16, "The draft and the reminder are on the day", "Draft for Ahmed" in pg.locator("#day").inner_text() and "Call Sara" in pg.locator("#day").inner_text())
    pg.locator("button:has-text('Confirm')").first.click()
    pg.wait_for_function("() => !document.querySelector('#day').innerText.includes('Draft for Ahmed')", timeout=8000)
    check(17, "Confirm clears it, and it says nothing was sent", "Draft for Ahmed" not in pg.locator("#day").inner_text())

    # ---- meeting mode ----
    pg.locator("#modes button:has-text('Hey Pocket')").click()
    pg.wait_for_selector("textarea.pocket")
    for t in ("We agreed to run the Marina campaign in November.", "Omar will call the developer by Thursday."):
        pg.locator("textarea.pocket").fill(t)
        pg.locator("textarea.pocket").press("Enter")
        pg.wait_for_timeout(400)
    pg.wait_for_function("() => /2 lines kept/i.test(document.querySelector('#day').innerText)", timeout=8000)
    check(18, "It keeps the words and says nothing", "2 lines kept" in pg.locator("#day").inner_text().lower())
    shot("06-meeting")
    pg.locator("#modes button:has-text('At my desk')").click()
    pg.wait_for_function("() => document.querySelector('#answer').innerText.includes('Summary')", timeout=8000)
    check(19, "After: decisions and action items", "Omar: Call the developer" in pg.locator("#answer").inner_text(), pg.locator("#answer").inner_text())

    # ---- settings ----
    pg.goto(f"{BASE}/web/settings.html#sales")
    pg.wait_for_selector("#sr-call_minutes")
    pg.locator("#sr-call_minutes").fill("20")
    pg.locator("#salesbox button.primary").click()
    pg.wait_for_timeout(400)
    check(20, "The owner changes the call limit", api.get(f"{BASE}/api/sales/rules").json()["call_minutes"] == 20)
    shot("07-settings")
    r = customer(PH4, "call me", "Dana Ali")[-1]
    check(21, "Rania promises the new number at once", "20 minutes" in r or "shortly" in r, r)
    api.post(f"{BASE}/api/sales/rules", data={"by": "layla", "value": {"call_minutes": 10}})  # put it back
    b.close()

failed = [r for r in results if not r[2]]
print(f"\n{len(results) - len(failed)} of {len(results)} passed; page errors: {errors or 'none'}")
sys.exit(1 if failed or errors else 0)
