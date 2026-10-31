"""A call asked for at a time goes on the broker's calendar (not only said in the chat). Fresh demo server, rules mode:
python e2e/call_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "call"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
NOW = datetime.now(DUBAI)
TUE = (NOW + timedelta(days=(1 - NOW.weekday()) % 7 or 7)).date()
WEEK = (TUE - timedelta(days=1)).isoformat()
DAY = TUE.strftime("%A")


def check(n, name, ok, shot, note=""):
    results.append((n, name, bool(ok), shot, note))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + note if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    api = pg.request

    def shot(name):
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        return f"{name}.png"

    def customer(phone, text, name):
        r0 = api.get(f"{BASE}/api/chats/{phone}")
        before = len(r0.json()["messages"]) if r0.ok else 0
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": name})
        return next((m["text"] for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"][before:] if m["type"] == "sent"), "")

    # an owner whose saved list of appointment kinds was made before phone calls existed (no "Phone call" in it)
    kinds = [k for k in api.get(f"{BASE}/api/calendar?person=layla").json()["kinds"] if k["where"] != "phone"]
    api.post(f"{BASE}/api/calendar/settings", data={"by": "layla", "kinds": kinds})
    A = "971507770001"
    customer(A, "Hi", "Ali Rahman")
    r = customer(A, f"Could you please ask him to call me {DAY} at 10:00 instead, I am busy now", "Ali Rahman")
    check(1, "The client asks for a call at 10:00: Rania says it is booked, not 'shortly'", r.startswith("Of course Ali. I've booked a call with") and "10:00 AM" in r, "", r)

    pg.goto(f"{BASE}/web/calendar.html?as=layla&start={WEEK}&view=week")
    pg.wait_for_selector(".kpi")
    pg.wait_for_timeout(500)
    ev = pg.locator(".ev", has_text="Ali Rahman")
    ev.first.click()
    det = pg.locator("#detail").inner_text()
    check(2, "It is on the broker's calendar at 10:00 as a Phone call, with the client and a link to the chat",
          ev.count() == 1 and "Phone call" in det and "10:00" in det and pg.locator("#detail a", has_text="Open the chat").count() == 1, shot("02-calendar"))

    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as=layla")
    pg.wait_for_timeout(900)
    lead = pg.locator("#chat").inner_text() + pg.locator("#prof").inner_text()
    check(3, "The lead is not moved to 'Viewing booked' by a phone call, and the broker's card is due at 10:00",
          pg.locator("#chat select").first.input_value() != "Viewing booked" and "10:00" in pg.locator("#chat .banner.att").inner_text(), shot("03-lead"))

    r = customer(A, "so he will call me at 10 tmrw?" if False else f"so he will call me at 10 on {DAY}?", "Ali Rahman")
    check(4, "'So he will call me at 10?' is confirmed with a Yes, with no second card",
          r.startswith("Yes Ali,") and "10:00 AM" in r and len([c for c in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"] if c["attention"]]) == 1, shot("04-confirm"), r)

    B = "971507770002"
    customer(B, "Hi", "Mona Saleh")
    r = customer(B, f"Can I see MC-1204 on {DAY} at 10am?", "Mona Saleh")
    check(5, "Rania never books a viewing over that call: she offers other times", "10:00 AM" not in r.split("I can book")[0] and not r.startswith("Booked: Unit 1204, Marina Crest (MC-1204) with Omar, " + DAY + " " ), shot("05-no-clash"), r[:150])

    r = customer(A, "sorry, make it 11 instead", "Ali Rahman")
    pg.goto(f"{BASE}/web/calendar.html?as=layla&start={WEEK}&view=week")
    pg.wait_for_selector(".kpi")
    pg.wait_for_timeout(500)
    check(6, "'Make it 11' moves the call on the calendar", "now" in r and pg.locator(".ev", has_text="11:00 Ali Rahman").count() == 1, shot("06-moved"), r)

    # the broker moves it on the calendar: the client is messaged, and the broker's card follows
    pg.locator(".ev", has_text="11:00 Ali Rahman").click()
    pg.locator("#detail button", has_text="Move").first.click()
    pg.fill("#mtime", "15:00")
    pg.locator("#detail button", has_text="Move and tell").click()
    pg.wait_for_timeout(900)
    msgs = [m["text"] for m in api.get(f"{BASE}/api/chats/{A}").json()["messages"] if m["type"] == "sent"]
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as=layla")
    pg.wait_for_timeout(900)
    banner = pg.locator("#chat .banner.att").inner_text()
    check(7, "Moved on the calendar: Ali is messaged in the chat, and the broker's call card is due at 15:00",
          "has moved your phone call" in msgs[-1] and "3:00 PM" in msgs[-1] and "15:00" in banner and "11:00" not in banner.split("due")[-1],
          shot("07-moved-message"), msgs[-1][:110])
    r = customer(A, "what's the time we booked?", "Ali Rahman")
    check(8, "'What's the time we booked?' is answered from the calendar, with the new time",
          r.startswith("Omar will call you") and "3:00 PM" in r, shot("08-what-time"), r)
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
