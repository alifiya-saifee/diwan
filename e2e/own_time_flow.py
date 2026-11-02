"""The broker's own time (docs/calendar-own-time-spec.md) and the calendar at a glance, checked as a person would:
busy time and days off from the calendar, Rania not booking them, an appointment added by hand, who sees what, and
the week's numbers. Fresh demo server, rules mode: python e2e/own_time_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "own_time"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
NOW = datetime.now(DUBAI)
MON = (NOW + timedelta(days=7 - NOW.weekday())).date()  # next week, so every time is ahead
TUE, WED, THU = (MON + timedelta(days=i) for i in (1, 2, 3))
WEEK = MON.isoformat()


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

    def cal(person, view="week", start=WEEK):
        pg.goto(f"{BASE}/web/calendar.html?as={person}&start={start}&view={view}")
        pg.wait_for_selector(".kpi")
        pg.wait_for_timeout(400)

    def form(mode):
        pg.click({"appt": "#addAppt", "busy": "#addBusy", "off": "#addOff"}[mode])
        pg.wait_for_selector("dialog#dlg[open]")

    def customer(phone, text, name):
        r0 = api.get(f"{BASE}/api/chats/{phone}")
        before = len(r0.json()["messages"]) if r0.ok else 0
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": name})
        msgs = api.get(f"{BASE}/api/chats/{phone}").json()["messages"][before:]
        return next((m["text"] for m in msgs if m["type"] == "sent"), "")

    cal("omar")
    check(1, "The calendar opens with the week's numbers, the broker's load and the grid",
          pg.locator(".kpi").count() == 5 and pg.locator(".lb").count() == 1 and pg.locator(".col").count() == 7
          and "Omar" in pg.locator("#load").inner_text(), shot("01-week"))

    form("busy")
    pg.fill("#fdate", TUE.isoformat()); pg.fill("#ffrom", "15:00"); pg.fill("#fto", "17:00"); pg.fill("#freason", "Dentist")
    pg.click("#fsave")
    pg.wait_for_timeout(700)
    blk = pg.locator(".ev.blk", has_text="Dentist")
    check(2, "Omar marks Tuesday 15:00-17:00 busy (Dentist): it shows on his grid at once",
          blk.count() == 1 and not pg.locator("dialog#dlg[open]").count(), shot("02-busy"))

    r = customer("971506670001", f"Hi, can I see MC-1204 on Tuesday {TUE.day} {TUE:%b} at 4pm?", "Sara Khan")
    check(3, "A client asks for Tuesday 4pm: Rania doesn't book the busy time and offers others",
          "isn't available" in r and "Booked" not in r, shot("03-rania"), r[:160])
    r2 = customer("971506670001", f"OK, Tuesday {TUE.day} {TUE:%b} at 5pm then", "Sara Khan")
    check(4, "Tuesday 5pm, just after the busy time, is booked", r2.startswith("Booked"), shot("04-booked"), r2[:120])

    cal("omar")
    form("busy")
    pg.fill("#fdate", TUE.isoformat()); pg.fill("#ffrom", "17:00"); pg.fill("#fto", "18:00")
    pg.click("#fsave")
    pg.wait_for_timeout(500)
    err = pg.locator("#ferr").inner_text()
    check(5, "Busy time over Sara's visit is refused with the reason", "Sara Khan" in err and "move it first" in err, shot("05-clash"), err)
    pg.locator("dialog#dlg button", has_text="Cancel").click()

    form("off")
    pg.fill("#ffirst", THU.isoformat()); pg.fill("#flast", THU.isoformat()); pg.fill("#freason", "Annual leave")
    pg.click("#fsave")
    pg.wait_for_timeout(700)
    r3 = api.post(f"{BASE}/api/chats/incoming", data={"phone": "971506670002", "text": f"Can I see MC-1204 on Thursday {THU.day} {THU:%b} at 11am?", "name": "Ali Noor"})
    reply = next((m["text"] for m in api.get(f"{BASE}/api/chats/971506670002").json()["messages"] if m["type"] == "sent"), "")
    check(6, "A day off on Thursday shows on the grid and in Omar's load, and Rania books nobody that day",
          pg.locator(".ev.blk", has_text="Day off").count() == 1 and "off Thu" in pg.locator("#load").inner_text()
          and "Thursday" not in reply.split("on", 1)[-1][:60] and r3.ok, shot("06-day-off"), reply[:140])

    form("appt")
    pg.fill("#fphone", "971506670003"); pg.fill("#fname", "Huda Saleh")
    pg.select_option("#fkindsel", "viewing"); pg.fill("#fprop", "MC-1204")
    pg.fill("#fdate", TUE.isoformat()); pg.fill("#ftime", "16:00")
    pg.click("#fsave")
    pg.wait_for_timeout(500)
    err = pg.locator("#ferr").inner_text()
    check(7, "Adding an appointment by hand in the busy time is refused, with the free times", "isn't free" in err and "Free:" in err, shot("07-hand-refused"), err[:140])
    pg.fill("#fdate", WED.isoformat()); pg.fill("#ftime", "11:00")
    pg.click("#fsave")
    pg.wait_for_timeout(800)
    det = pg.locator("#detail").inner_text()
    check(8, "Added by hand on Wednesday 11:00: on the grid, marked who booked it, nothing sent to the client",
          pg.locator(".ev", has_text="Huda Saleh").count() == 1 and "Omar, by hand" in det
          and not [m for m in api.get(f"{BASE}/api/chats/971506670003").json()["messages"] if m["type"] == "sent"], shot("08-hand"))
    pg.goto(f"{BASE}/web/inbox.html?chat=971506670003&as=omar")
    pg.wait_for_timeout(900)
    lead = pg.locator("body").inner_text()
    r5 = customer("971506670003", "When is my viewing?", "Huda Saleh")
    r4 = customer("971506670003", f"Can we move the viewing to 12pm on Wednesday {WED.day} {WED:%b}?", "Huda Saleh")
    check(9, "The hand-added client is a lead in the Inbox at Viewing booked; Rania tells them when it is and moves it",
          "Huda Saleh" in lead and "Viewing booked" in lead and r5.startswith("Your site visit to Unit 1204") and "11:00 AM" in r5 and "is now" in r4,
          shot("09-inbox"), f"{r5[:90]} / {r4[:80]}")

    cal("omar")
    pg.locator(".ev.blk", has_text="Dentist").click()
    pg.locator("#detail button", has_text="Change").click()
    pg.fill("#ffrom", "14:00"); pg.fill("#fto", "15:00")
    pg.click("#fsave")
    pg.wait_for_timeout(700)
    moved = pg.locator(".ev.blk", has_text="Dentist").inner_text()
    pg.locator(".ev.blk", has_text="Dentist").click()
    pg.locator("#detail button", has_text="Delete").click()
    pg.wait_for_timeout(700)
    check(10, "Omar changes the busy time to 14:00-15:00, then deletes it", "14:00–15:00" in moved and pg.locator(".ev.blk", has_text="Dentist").count() == 0,
          shot("10-change-delete"), moved.replace("\n", " "))

    form("busy")
    pg.fill("#fdate", MON.isoformat()); pg.fill("#ffrom", "10:00"); pg.fill("#fto", "11:00"); pg.fill("#freason", "Team meeting")
    pg.check("#frepeat")
    pg.click("#fsave")
    pg.wait_for_timeout(600)
    pg.click("#next")
    pg.wait_for_timeout(700)
    check(11, "A weekly busy time repeats the next week", pg.locator(".ev.blk", has_text="Team meeting").count() == 1, shot("11-weekly"))

    cal("hamza")
    form("busy")
    opts = pg.locator("#fbroker option").all_inner_texts()
    disabled = pg.locator("#fbroker").is_disabled()
    pg.locator("dialog#dlg button", has_text="Cancel").click()
    check(12, "Hamza sees only his own calendar, and can add busy time only for himself",
          opts == ["Hamza"] and disabled and pg.locator(".ev", has_text="Sara Khan").count() == 0 and pg.locator(".ev.blk").count() == 0, shot("12-hamza"))

    cal("layla")
    kp = pg.locator("#kpis").inner_text()
    reason = pg.locator(".ev.blk", has_text="Annual leave").count()
    check(13, "The owner sees every broker: the week's count, the kinds, time booked, the next appointment, and the reasons",
          pg.locator(".lb").count() >= 3 and "Site visit" in kp and "%" in kp and "sara khan" in kp.lower() and "next up" in kp.lower(), shot("13-owner"), kp.replace("\n", " · ")[:200])
    check(14, "The owner sees Omar's day off with its reason", reason == 1, shot("13-owner"))
    pg.locator(".seg button[data-v=day]").click()
    pg.wait_for_timeout(500)
    heads = pg.locator(".dh").all_inner_texts()
    check(15, "Day view: one column per broker, to see who is free", sum(1 for x in heads if any(n in x for n in ("Omar", "Hamza", "Nadia"))) >= 3, shot("15-day"))
    pg.locator(".seg button[data-v=list]").click()
    pg.wait_for_timeout(500)
    ag = pg.locator(".agenda").inner_text()
    check(16, "Agenda view lists the week day by day", "Sara Khan" in ag and "Huda Saleh" in ag and "Day off" in ag, shot("16-agenda"))
    pg.locator(".lb", has_text="Omar").click()
    pg.wait_for_timeout(600)
    check(17, "Clicking a broker's load filters the calendar to them", pg.locator("#who").input_value() == "omar", shot("17-filter"))

    pg.set_viewport_size({"width": 390, "height": 844})
    over = []
    for v in ("week", "day", "month", "list"):
        cal("layla", v)
        if pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
            over.append(v)
    form("appt")
    if pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
        over.append("form")
    check(18, "Week, Day, Agenda and the add form fit a phone", not over, shot("18-phone"), ", ".join(over))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
