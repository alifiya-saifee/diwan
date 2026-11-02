"""Small fixes from the 2 Nov review, as people use them. Fresh demo server, rules mode:
python e2e/fixes_flow.py http://127.0.0.1:8093 <out dir>"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8093"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "fixes"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []


def check(n, name, ok, shot, note=""):
    results.append((n, name, bool(ok), shot, note))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + note if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    api = pg.request

    def shot(name):
        pg.screenshot(path=str(OUT / f"{name}.png"))
        return f"{name}.png"

    def customer(phone, text, name):
        r0 = api.get(f"{BASE}/api/chats/{phone}")
        before = len(r0.json()["messages"]) if r0.ok else 0
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": name})
        return [m["text"] for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"][before:] if m["type"] == "sent"]

    # a client asks about a listing: the listing answers buy, area, type and bedrooms; "Cash" is an answer
    A = "971509770001"
    said = [customer(A, t, "Mona Saleh") for t in ("Hi, is MC-1204 still available?", "To live in", "Budget is 2.7 million", "Cash", "Now", "UAE resident")]
    flat = " ".join(x for r in said for x in r).lower()
    check(1, "Asking about a listing: never 'buy or rent?', area or bedrooms; 'Cash' is taken as an answer",
          "buy, rent" not in flat and "which area" not in flat and "how many bedrooms" not in flat and "personally" not in flat, shot("01-asked"), said[3][0][:80] if said[3] else "")

    broker = next(c["broker"] for c in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"] if c["phone"] == A)
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as={broker}&convert=1")  # the Sales room's "Converted…"
    pg.wait_for_selector("#pamount", timeout=8000)
    hint = pg.locator("#phint").inner_text()
    check(2, "'Converted…' opens Convert straight away, with the listing they asked about already there",
          "Unit 1204, Marina Crest (MC-1204)" in hint, shot("02-convert"), hint[:90])
    pg.fill("#pamount", "2600000")
    pg.locator(".actform button", has_text="Convert").click()
    pg.wait_for_timeout(1200)
    d = api.get(f"{BASE}/api/chats/{A}").json()
    check(3, "Convert saves the property and converts the deal", d["desk"]["agreed"] and not d["desk"]["property"]["needed"], shot("03-converted"), d["stage"])

    # owner-only links are hidden from a broker, shown to the owner; Rashid can view the Inbox
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as={broker}")
    pg.wait_for_timeout(900)
    broker_sees = pg.locator("#more a.owner-only:not([hidden])").count() + pg.locator("#prof a", has_text="Memory graph").count()
    options = pg.locator("#me option").all_inner_texts()
    pg.select_option("#me", "layla")
    pg.wait_for_timeout(900)
    owner_sees = pg.locator("#more a.owner-only:not([hidden])").count()
    check(4, "A broker isn't shown links to owner-only pages; the owner is; the Sales manager is in 'Viewing as'",
          broker_sees == 0 and owner_sees == 2 and any("Rashid" in o for o in options), shot("04-links"), f"broker {broker_sees}, owner {owner_sees}")

    pg.goto(f"{BASE}/web/calendar.html?as=layla")
    pg.wait_for_timeout(700)
    check(5, "The calendar never offers Google Meet, which can't connect yet", pg.locator("#vprov option", has_text="Google Meet").count() == 0, shot("05-video"))

    pg.goto(f"{BASE}/web/index.html")
    pg.wait_for_timeout(1200)
    asked = []
    pg.once("dialog", lambda dl: (asked.append(dl.message), dl.dismiss()))
    before = len(api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"])
    pg.click("details.more > summary")  # Reset sits under "Team briefings and live activity"
    pg.click("#reset")
    pg.wait_for_timeout(800)
    after = len(api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"])
    check(6, "Reset asks first, and 'Cancel' keeps the office as it is", asked and before == after and before > 0, shot("06-reset"), asked[0][:60] if asked else "no question")
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
