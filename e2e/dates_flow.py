"""Dates Rania understands (docs/dates-spec.md), as a client and the broker see them. Fresh demo server, rules mode:
python e2e/dates_flow.py http://127.0.0.1:8093 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from diwan import slots  # noqa: E402
from held import confirm  # noqa: E402
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8093"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "dates"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
NOW = datetime.now(DUBAI)
A1, A2 = slots.which_day("next Tuesday at 4pm", NOW)  # the coming Tuesday and the one after
LATER = (NOW + timedelta(days=12)).date()
while LATER.weekday() == 4:  # not a Friday: the office's own hours decide those
    LATER += timedelta(days=1)
WRONG = LATER + timedelta(days=1)  # a weekday that isn't the date's


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

    def booked(customer_name):
        start = (NOW - timedelta(days=NOW.weekday())).date().isoformat()
        return [a for a in api.get(f"{BASE}/api/calendar?person=layla&start={start}&days=28").json()["appointments"]
                if a["customer"] == customer_name and a["status"] == "booked"]

    S = "971509990001"
    customer(S, "Hi", "Sara Khan")
    r = customer(S, "Can I see MC-1204 next Tuesday at 4pm?", "Sara Khan")
    pg.goto(f"{BASE}/web/inbox.html?chat={S}&as=layla")
    pg.wait_for_timeout(900)
    thread = pg.locator(".thread").inner_text()
    check(1, "'Next Tuesday' is asked about, with both dates, and nothing is booked yet",
          r == f"Just to be sure: do you mean {slots.say_day(A1)} or {slots.say_day(A2)}?" and "Just to be sure" in thread and not booked("Sara Khan"),
          shot("01-asked"), r)

    r = customer(S, "The second one", "Sara Khan")
    held = r.startswith("Thanks, I've noted you'd like to see Unit 1204") and slots.say_day(A2) in r
    r2 = confirm(api, BASE, S, pg)  # the broker confirms it in the Inbox
    v = booked("Sara Khan")
    check(2, "'The second one' asks for that day at the time she first asked; once the broker confirms, it's booked then",
          held and r2.startswith("Good news, Sara: it's confirmed. Booked: Unit 1204") and v and v[0]["at"][:16] == f"{A2.isoformat()}T16:00", shot("02-booked-second"), r[:120])

    pg.goto(f"{BASE}/web/calendar.html?as=layla&start={A2.isoformat()}")
    pg.wait_for_timeout(800)
    check(3, "It is on the calendar on that day", pg.locator(".ev:not(.blk)", has_text="Sara Khan").count() == 1, shot("03-calendar"))

    B = "971509990002"
    customer(B, "Hi", "Ali Noor")
    written = f"{LATER.day} {LATER:%b}"
    r = customer(B, f"Can I see MC-1204 on {written} at 11am?", "Ali Noor")
    confirm(api, BASE, B)
    v = booked("Ali Noor")
    check(4, f"A written date ('{written}') books that date, not the nearest weekday",
          slots.say_day(LATER) in r and v and v[0]["at"][:10] == LATER.isoformat(), shot("04-written-date"), r[:120])

    C = "971509990003"
    customer(C, "Hi", "Mona Saleh")
    r = customer(C, f"Please call me {WRONG:%A} {LATER.day} {LATER:%b} at 11", "Mona Saleh")
    check(5, "A weekday that isn't the date's: she asks which, naming both",
          r == f"Just to be sure: do you mean {slots.say_day(LATER)} or {slots.say_day(WRONG)}?", shot("05-mismatch"), r)
    r = customer(C, "the first", "Mona Saleh")
    check(6, "Her answer books the call on the day she chose", slots.say_day(LATER) in r and "11:00 AM" in r and "call" in r.lower(), shot("06-call"), r[:120])

    pg.set_viewport_size({"width": 390, "height": 844})
    pg.goto(f"{BASE}/web/inbox.html?chat={S}&as=layla")
    pg.wait_for_timeout(800)
    check(7, "On a phone the chat with the question reads without sideways scrolling",
          not pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"), shot("07-phone"))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
