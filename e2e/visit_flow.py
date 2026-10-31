"""After the visit (docs/visit-summary-spec.md), checked as a person would: record the visit from the appointment, the
client agrees, what they say becomes the summary, and the follow-up answers their worry. Fresh demo server, rules mode:
python e2e/visit_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "visit"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
NOW = datetime.now(DUBAI)
TUE = (NOW + timedelta(days=(1 - NOW.weekday()) % 7 or 7)).replace(hour=16, minute=0, second=0, microsecond=0)
WEEK = (TUE - timedelta(days=1)).date().isoformat()


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
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as=layla")
        pg.click("#phonebtn")
        pg.fill("#pname", name)
        pg.fill("#pnum", phone)
        pg.fill("#ptext", text)
        pg.click("#psend")
        for _ in range(60):
            r = api.get(f"{BASE}/api/chats/{phone}")
            if r.ok and any(m["type"] == "sent" for m in r.json()["messages"][before:]):
                break
            pg.wait_for_timeout(150)

    def record(phone, name, turns):
        """From the appointment on the calendar: Record the visit, the client agrees, the words, End."""
        pg.goto(f"{BASE}/web/calendar.html?as=omar&start={WEEK}")
        pg.wait_for_timeout(700)
        pg.locator(".ev:not(.blk)", has_text=name).first.click()
        pg.wait_for_timeout(300)
        link = pg.locator("#detail a", has_text="Record the visit")
        has = link.count() == 1
        link.click()
        pg.wait_for_timeout(900)
        pre = pg.locator("#title").input_value()
        pg.click("#start")
        pg.wait_for_timeout(400)
        gate = pg.locator("#consentbox").is_visible() and pg.locator("#live").is_hidden()
        pg.click("#consent")
        pg.wait_for_timeout(300)
        for who, t in turns:
            pg.select_option("#speaker", who)
            pg.fill("#text", t)
            pg.click("#say")
            pg.wait_for_timeout(300)
        pg.click("#end")
        pg.wait_for_timeout(900)
        return has, pre, gate

    A = "971506660001"
    customer(A, "Hi", "Sara Khan")
    customer(A, "Can I see MC-1204 on Tuesday at 4pm?", "Sara Khan")
    pg.goto(f"{BASE}/web/calendar.html?as=omar&start={WEEK}")
    pg.wait_for_timeout(700)
    pg.locator(".ev:not(.blk)", has_text="Sara Khan").first.click()
    pg.wait_for_timeout(300)
    det = pg.locator("#detail")
    check(1, "The appointment offers 'Record the visit' and a notes box; Done waits until after the time",
          det.locator("a", has_text="Record the visit").count() == 1 and det.locator("#notes").count() == 1
          and det.locator("button", has_text="Done").is_disabled(), shot("01-appointment"))

    has, pre, gate = record(A, "Sara Khan", [("customer", "We love the view from the balcony."),
                                            ("customer", "But the kitchen is too small for us."),
                                            ("broker", "The kitchen wall can come down, it's not structural."),
                                            ("customer", "Let me talk to my wife and get back to you.")])
    check(2, "Record the visit opens the meeting page for that deal, and nothing is kept until the client agrees",
          has and pre == "Site visit" and gate, shot("02-meeting"))
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as=omar")
    pg.wait_for_timeout(900)
    prof = pg.locator("#prof").inner_text()
    check(3, "The lead shows the visit summary: thinking it over, what they liked, what worried them, in their words",
          "thinking it over" in prof.lower() and "We love the view from the balcony." in prof and "the kitchen is too small for us." in prof
          and "not structural" not in prof and "From the recorded visit" in prof, shot("03-summary"))
    f = api.get(f"{BASE}/api/chats/{A}").json()["followup"]
    check(4, "The follow-up answers their worry and gives them time, with nothing about checks",
          f and "You mentioned “the kitchen is too small for us”" in f["text"] and "Take your time" in f["text"]
          and "complian" not in f["text"].lower(), shot("04-follow-up"), f["text"].replace("\n", " / ") if f else "")

    B = "971506660002"
    customer(B, "Hi", "Ali Noor")
    customer(B, "Can I see MC-1204 on Tuesday at 11am?", "Ali Noor")
    record(B, "Ali Noor", [("customer", "Honestly it's not for us, too far from the school.")])
    pg.goto(f"{BASE}/web/inbox.html?chat={B}&as=omar")
    pg.wait_for_timeout(900)
    prof = pg.locator("#prof").inner_text()
    f = api.get(f"{BASE}/api/chats/{B}").json()["followup"]
    check(5, "'Not for us': the summary says so and the follow-up asks what to change, not pushing the same flat",
          "not for them" in prof.lower() and f and "What would you change" in f["text"] and "make an offer" not in f["text"], shot("05-not-for-them"),
          f["text"].replace("\n", " / ") if f else "")

    pg.goto(f"{BASE}/web/calendar.html?as=omar&start={WEEK}")
    pg.wait_for_timeout(700)
    pg.locator(".ev:not(.blk)", has_text="Sara Khan").first.click()
    pg.wait_for_timeout(300)
    check(6, "The calendar shows the summary on the appointment", "After the visit" in pg.locator("#detail").inner_text()
          and "Thinking it over" in pg.locator("#detail").inner_text(), shot("06-calendar-summary"))

    pg.set_viewport_size({"width": 390, "height": 844})
    over = []
    for page in (f"calendar.html?as=omar&start={WEEK}", f"inbox.html?chat={A}&as=omar", "meeting.html"):
        pg.goto(f"{BASE}/web/{page}")
        pg.wait_for_timeout(700)
        if pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
            over.append(page)
    check(7, "Calendar, Inbox and Meeting fit a phone", not over, shot("07-phone"), ", ".join(over))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
