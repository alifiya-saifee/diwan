"""Viewings by listing (docs/viewing-access-spec.md), as the broker and the client see them. Fresh demo server, rules mode:
python e2e/viewing_access_flow.py http://127.0.0.1:8093 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan import slots  # noqa: E402
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8093"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "viewing_access"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
NOW = datetime.now(DUBAI)
DAY = (NOW + timedelta(days=3)).date()
while DAY.weekday() in (4, 6):  # a working day for the office
    DAY += timedelta(days=1)
SAID = f"{DAY.day} {DAY:%b}"
SAT = DAY + timedelta(days=(5 - DAY.weekday()) % 7 or 7)


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
        return next((m["text"] for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"][before:] if m["type"] == "sent"), "")

    def last(phone):
        return [m["text"] for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"] if m["type"] == "sent"][-1]

    def broker_of(phone):
        return next(c["broker"] for c in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"] if c["phone"] == phone)

    def catalog(ref, person):
        pg.goto(f"{BASE}/web/catalog.html")
        pg.select_option("#as", person)
        pg.locator(f'[data-ref="{ref}"]').first.click()
        pg.wait_for_selector("#access h2")

    # 1. the listing says how it's viewed: nobody set JVC-88, so it asks the owner first
    catalog("JVC-88", "omar")
    box = pg.locator("#access").inner_text()
    check(1, "A listing nobody set says it asks the owner first, and its broker can change it",
          "Ask the owner first" in box and "not set yet" in box and pg.locator("#asave").count() == 1, shot("01-listing"), box.replace("\n", " ")[:120])

    # 2. a client asks to view it: Rania says she'll check with the owner; the time is held
    A = "971509880001"
    customer(A, "Hi", "Sara Khan")
    r = customer(A, f"Can I see JVC-88 on {SAID} at 4pm?", "Sara Khan")
    ab = broker_of(A)
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as={ab}")
    pg.wait_for_selector(".banner.owner")
    check(2, "Rania says she'll check with the owner and confirm; the broker's card has the three answers",
          "I'll check" in r and "with the owner" in r and pg.locator(".banner.owner button", has_text="Owner said yes").count() == 1, shot("02-asked"), r[:120])

    pg.goto(f"{BASE}/web/calendar.html?as={ab}&start={DAY.isoformat()}")
    pg.wait_for_timeout(800)
    pg.locator(".ev.requested", has_text="Sara Khan").first.click()
    det = pg.locator("#detail").inner_text()
    check(3, "The calendar holds the time as waiting for the owner, with the same answers", "Waiting for the owner" in det and "Owner said yes" in det, shot("03-calendar-held"))

    r = customer(A, "Any news from the owner?", "Sara Khan")
    check(4, "'Any news?' is answered honestly", r.startswith("I'm still waiting for the owner to confirm"), shot("04-news"), r[:100])

    # 3. the broker says yes on the card: the client is told
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as={ab}")
    pg.wait_for_selector(".banner.owner")
    pg.locator(".banner.owner button", has_text="Owner said yes").click()
    pg.wait_for_timeout(900)
    msg = last(A)
    check(5, "Owner said yes: the client gets the confirmed time, and the card is gone",
          msg.startswith("Good news, Sara: the owner confirmed. Booked:") and pg.locator(".banner.owner").count() == 0, shot("05-yes"), msg[:110])

    # 4. another client: the owner offers other times from the calendar, and the one picked books at once
    B = "971509880002"
    customer(B, "Hi", "Ali Noor")
    customer(B, f"Can I see JVC-88 on {SAID} at 6pm?", "Ali Noor")
    bb = broker_of(B)
    pg.goto(f"{BASE}/web/calendar.html?as={bb}&start={DAY.isoformat()}")
    pg.wait_for_timeout(800)
    pg.locator(".ev.requested", has_text="Ali Noor").first.click()
    pg.locator("#detail button", has_text="Other times").click()
    pg.locator("#detail input[type=datetime-local]").first.fill(f"{(DAY + timedelta(days=1)).isoformat()}T11:00")
    pg.locator("#detail button", has_text="Offer these to the client").click()
    pg.wait_for_timeout(900)
    msg = last(B)
    nxt = DAY + timedelta(days=1)
    check(6, "Other times: the client is offered the owner's time", "the owner can't do" in msg and slots.say_day(nxt) in msg, shot("06-offered"), msg[:120])
    r = customer(B, f"{nxt.day} {nxt:%b} at 11am works", "Ali Noor")
    check(7, "The time they pick books at once: the owner already agreed", r.startswith("Booked:") and "The owner is expecting you" in r, shot("07-picked"), r[:120])

    # 5. off-plan shown at the developer's gallery, in its hours
    catalog("BB-305", "layla")
    pg.select_option("#amode", "developer")
    pg.fill("#aplace", "the Bay Square sales gallery, Business Bay")
    pg.fill("#aopen", "10:00"); pg.fill("#aclose", "16:00")
    for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]:  # the gallery opens at the weekend only
        btn = pg.locator("#access .row button", has_text=d)
        if "on" in (btn.get_attribute("class") or ""):
            btn.click()
    pg.click("#asave")
    pg.wait_for_timeout(700)
    box = pg.locator("#access").inner_text()
    C = "971509880003"
    customer(C, "Hi", "Mona Saleh")
    r = customer(C, f"Can I see BB-305 on {SAID} at 11am?", "Mona Saleh")
    r2 = customer(C, f"OK, {SAT.day} {SAT:%b} at 11am then", "Mona Saleh")
    check(8, "The gallery's hours decide: a weekday is refused with weekend times, and the weekend books at the gallery",
          "Developer's gallery" in box and r.startswith("That time isn't available") and slots.say_day(SAT).split()[0] in r
          and r2.startswith("Booked:") and "at the Bay Square sales gallery" in r2, shot("08-gallery"), r2[:120])

    pg.set_viewport_size({"width": 390, "height": 844})
    pg.goto(f"{BASE}/web/inbox.html?chat={B}&as={bb}")
    pg.wait_for_timeout(800)
    check(9, "On a phone the Inbox reads without sideways scrolling", not pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"), shot("09-phone"))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
