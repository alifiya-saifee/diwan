"""The calendar (docs/calendar-spec.md), checked as a person would. Run against a fresh demo server in rules mode:
python e2e/calendar_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "calendar"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
now = datetime.now(DUBAI)
TUE = (now + timedelta(days=(1 - now.weekday()) % 7 or 7)).replace(hour=16, minute=0, second=0, microsecond=0)
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

    def customer(phone, text, name="Sara Khan"):
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
            new = r.json()["messages"][before:] if r.ok else []
            if any(m["type"] == "sent" for m in new):
                return [m for m in new if m["type"] == "sent"][-1]["text"]
            pg.wait_for_timeout(150)
        return ""

    def cal(person="layla", who=None):
        pg.goto(f"{BASE}/web/calendar.html?as={person}&start={WEEK}")  # the week of the bookings
        pg.wait_for_timeout(700)
        if who is not None:
            pg.select_option("#who", who)
            pg.wait_for_timeout(500)

    def blocks():
        return pg.locator(".ev:not(.blk)").all_inner_texts()

    A = "971504440001"
    customer(A, "Hi")
    r = customer(A, "Can I see MC-1204 on Tuesday at 4pm?")
    check(1, "The client books a site visit in the chat", r.startswith("Booked: Unit 1204") and "Tuesday" in r, shot("01-booked"), r)

    pg.goto(f"{BASE}/web/inbox.html?as=layla")
    pg.wait_for_timeout(500)
    has_link = pg.locator(".bar a", has_text="Calendar").count() == 1
    cal()
    check(2, "Calendar opens from the Inbox; the owner sees the visit in the week, with every broker in the legend",
          has_link and any("Site visit" in x and "Sara Khan" in x for x in blocks()) and pg.locator("#legend span").count() >= 4, shot("02-week"))
    pg.locator(".ev:not(.blk)", has_text="Sara Khan").first.click()
    pg.wait_for_timeout(300)
    det = pg.locator("#detail").inner_text()
    check(3, "Clicking it shows the client, broker, place and status; Done waits until after the time",
          "Sara Khan" in det and "At the property · MC-1204" in det and "Booked" in det and pg.locator("#detail button", has_text="Done").is_disabled(),
          shot("03-detail"))

    r = customer(A, "Could we also do a video call on Tuesday at 11am?")
    cal()
    check(4, "A video call is booked as its own kind, 30 minutes, and shows on the calendar",
          "by video (30 min)" in r and any("Video call" in x for x in blocks()), shot("04-video"), r)

    r = customer(A, "Can we move the viewing to Thursday at 5pm instead?")
    view = [v for v in api.get(f"{BASE}/api/calendar?person=layla&start={WEEK}").json()["appointments"] if v["kind"] == "Site visit"]
    bell = [n["text"] for n in api.get(f"{BASE}/api/notices/omar").json()["items"]]
    check(5, "Moving it in the chat moves it on the calendar and tells the broker",
          r.startswith("Done:") and view and view[0]["at"][11:16] == "17:00" and any("moved" in t for t in bell), shot("05-moved"), r)

    cal(who="hamza")
    hz = blocks()
    cal(who="omar")
    om = blocks()
    check(6, "The owner filters to one broker: Omar's two appointments, Hamza's none", len(om) == 2 and not hz, shot("06-filter"))

    cal(person="omar")
    check(7, "A broker sees only their own calendar and can't change the hours",
          pg.locator("#who").is_hidden() and pg.locator("#openSet").is_hidden(), shot("07-broker"))

    # the owner opens later; Rania follows it
    cal()
    pg.click("#openSet")
    pg.fill("#hopen", "12:00")
    pg.click("#ssave")
    pg.wait_for_timeout(600)
    B = "971504440002"
    customer(B, "Hi", name="Ali Noor")
    r = customer(B, "Can I see MC-1204 on Tuesday at 10am?", name="Ali Noor")
    hrs = [int(x.split(":")[0]) + (12 if "PM" in x and not x.startswith("12") else 0) for x in __import__("re").findall(r"(\d{1,2}:\d{2} [AP]M)", r)]
    check(8, "The owner opens at 12:00: a 10am request gets only times from 12:00", "isn't available" in r and hrs and min(hrs) >= 12, shot("08-hours"), r)

    # a broker's day off (Settings → Team)
    pg.goto(f"{BASE}/web/settings.html#team")
    pg.wait_for_timeout(800)
    row = pg.locator("#team > div", has_text="Omar")
    row.locator(".days button").nth(TUE.weekday()).click()
    pg.wait_for_timeout(700)
    team = api.get(f"{BASE}/api/team").json()
    omar_days = next(t["days"] for t in team if t["id"] == "omar")
    shot("09a-days")
    C = "971504440003"
    customer(C, "Hi", name="Mina Saad")
    r = customer(C, "Can I see MC-1204 on Tuesday at 2pm?", name="Mina Saad")
    check(9, "Omar's day off (set on Settings) is never offered", TUE.weekday() not in omar_days and "isn't available" in r
          and TUE.strftime("%A") not in r.split("on ", 1)[-1], shot("09-day-off"), r)

    # kinds: the owner adds one
    cal()
    pg.click("#openSet")
    pg.click("#kadd")
    rows = pg.locator("#kinds .krow")
    last = rows.nth(rows.count() - 1)
    last.locator("input").first.fill("Handover")
    last.locator("input").nth(1).fill("45")
    last.locator("select").select_option("office")
    pg.click("#ssave")
    pg.wait_for_timeout(600)
    kinds = api.get(f"{BASE}/api/calendar?person=layla").json()["kinds"]
    check(10, "The owner adds a kind of appointment (Handover, 45 min, at the office)",
          any(k["name"] == "Handover" and k["minutes"] == 45 and k["where"] == "office" for k in kinds), shot("10-kinds"))

    # reminders (the clock moved with the sandbox-only sweep)
    v = next(x for x in api.get(f"{BASE}/api/calendar?person=layla&start={WEEK}").json()["appointments"] if x["kind"] == "Site visit")
    at = datetime.fromisoformat(v["at"])
    api.post(f"{BASE}/api/nudges/run", data={"at": (at - timedelta(hours=23)).isoformat()})
    api.post(f"{BASE}/api/nudges/run", data={"at": (at - timedelta(hours=1, minutes=50)).isoformat()})
    msgs = [m for m in api.get(f"{BASE}/api/chats/{A}").json()["messages"] if m.get("reminder")]
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as=layla")
    pg.wait_for_timeout(700)
    check(11, "The client gets two reminders, the day before and two hours before (as the approved template: their window is shut)",
          [m["reminder"] for m in msgs] == ["24h", "2h"] and all(m["template"] == "viewing_reminder" for m in msgs), shot("11-reminders"),
          msgs[0]["text"] if msgs else "")

    pg.set_viewport_size({"width": 390, "height": 844})
    cal()
    over = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
    check(12, "The calendar fits a phone: the week scrolls inside its box", not over, shot("12-phone"))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
