"""Calendar basics and video links (docs/calendar-basics-spec.md), checked as a person would. Fresh demo server, rules
mode, no Zoom keys (so the "not connected" path is what a person sees; Zoom itself is checked in code with a stand-in).
Never saves keys from the Settings page: that writes the real .env.
python e2e/basics_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "basics"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
NOW = datetime.now(DUBAI)
MON = (NOW + timedelta(days=7 - NOW.weekday())).date()
TUE, WED = MON + timedelta(days=1), MON + timedelta(days=2)


def check(n, name, ok, shot, note=""):
    results.append((n, name, bool(ok), shot, note))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + note if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    api = pg.request

    def shot(name):
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        return f"{name}.png"

    def cal(person="omar", view="week", start=MON.isoformat()):
        pg.goto(f"{BASE}/web/calendar.html?as={person}&start={start}&view={view}")
        pg.wait_for_selector(".kpi")
        pg.wait_for_timeout(400)

    def customer(phone, text, name):
        r0 = api.get(f"{BASE}/api/chats/{phone}")
        before = len(r0.json()["messages"]) if r0.ok else 0
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": name})
        return next((m["text"] for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"][before:] if m["type"] == "sent"), "")

    def sent(phone):
        return [m["text"] for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"] if m["type"] == "sent"]

    S, A, V = "971506680001", "971506680002", "971506680003"
    customer(S, f"Can I see MC-1204 on Tuesday {TUE.day} {TUE:%b} at 4pm?", "Sara Khan")
    customer(A, f"Can I see MC-1204 on Wednesday {WED.day} {WED:%b} at 11am?", "Ali Noor")
    r = customer(V, f"Could we do a video call on Tuesday {TUE.day} {TUE:%b} at 11am?", "Vera Lopez")
    assert r.startswith("Booked"), r

    cal(view="month")
    cell = pg.locator(".mc", has_text="Sara Khan")
    check(1, "Month view: the month with each day's appointments; busy and closed days shaded",
          pg.locator(".mc").count() == 42 and cell.count() == 1 and pg.locator(".mc.closed").count() >= 4, shot("01-month"))
    cell.click()
    pg.wait_for_timeout(600)
    check(2, "Clicking a day opens it in Day view", pg.locator(".seg button.on").inner_text() == "Day" and "Tuesday" in pg.locator("#range").inner_text()
          and pg.locator(".ev", has_text="Sara Khan").count() == 1, shot("02-day"))

    later = (MON + timedelta(days=63)).isoformat()
    pg.locator(".seg button[data-v=week]").click()
    pg.wait_for_timeout(400)
    pg.fill("#jump", later)
    pg.dispatch_event("#jump", "change")
    pg.wait_for_timeout(600)
    wk = pg.locator("#range").inner_text()
    target = datetime.fromisoformat(later)
    check(3, "The date picker jumps to any day (the week holding it)", str(target.day) in pg.locator(".dh").all_inner_texts().__str__() and "–" in wk, shot("03-jump"), wk)

    cal(person="layla", view="list")
    pg.fill("#lfrom", MON.isoformat()); pg.dispatch_event("#lfrom", "change"); pg.wait_for_timeout(300)
    pg.fill("#lto", (MON + timedelta(days=20)).isoformat()); pg.dispatch_event("#lto", "change"); pg.wait_for_timeout(700)
    ls = pg.locator(".agenda").inner_text()
    check(4, "A custom range (3 weeks) is shown as a list with its numbers", "21 days" in pg.locator("#legend").inner_text()
          and "Sara Khan" in ls and "Ali Noor" in ls and "3" in pg.locator(".kpi").first.inner_text(), shot("04-range"))

    cal(person="layla")  # leads are shared out between brokers: the owner sees whoever has Ali
    pg.fill("#q", "ali")
    pg.wait_for_selector("#results:not([hidden]) button")
    res = pg.locator("#results").inner_text()
    pg.locator("#results button").first.click()
    pg.wait_for_timeout(700)
    check(5, "Search finds a client and opens the appointment", "Ali Noor" in res and "Ali Noor" in pg.locator("#detail").inner_text(), shot("05-search"), res.replace("\n", " ")[:120])

    cal(person="layla")
    pg.select_option("#fkind", "Video call")
    pg.wait_for_timeout(300)
    evs = pg.locator(".ev:not(.blk)").all_inner_texts()
    kp = pg.locator(".kpi").first.inner_text()
    check(6, "Filter by kind: only the video call, and the numbers follow", len(evs) == 1 and "Vera Lopez" in evs[0] and "with the filters shown" in kp, shot("06-filter"))
    pg.select_option("#fkind", "")

    cal(person="omar")
    pg.locator(".ev", has_text="Sara Khan").click()
    pg.locator("#detail button", has_text="Move").click()
    pg.fill("#mdate", WED.isoformat()); pg.fill("#mtime", "11:00")  # Ali Noor's time with Omar
    pg.locator("#detail button", has_text="Move and tell").click()
    pg.wait_for_timeout(500)
    err = pg.locator("#cerr").inner_text()
    check(7, "Moving into a taken time is refused with the free times", "isn't free" in err and "Free:" in err, shot("07-move-refused"), err[:120])
    pg.fill("#mdate", TUE.isoformat()); pg.fill("#mtime", "17:00")
    pg.locator("#detail button", has_text="Move and tell").click()
    pg.wait_for_timeout(800)
    msg = sent(S)[-1]
    check(8, "Moved from the calendar: on the grid at 17:00, and Sara gets one plain message",
          pg.locator(".ev", has_text="17:00 Sara Khan").count() == 1 and msg.startswith("Hi Sara, Omar has moved your site visit to Unit 1204, Marina Crest (MC-1204): it's now"), shot("08-moved"), msg[:120])

    cal(person="layla")  # Ali may be another broker's: leads are shared out
    pg.locator(".ev", has_text="Ali Noor").click()
    pg.locator("#detail button", has_text="Cancel").first.click()
    pg.fill("#creason", "Omar double-booked a valuation")
    pg.locator("#detail button", has_text="Cancel and tell").click()
    pg.wait_for_timeout(800)
    msg = sent(A)[-1]
    gone = pg.locator(".ev", has_text="Ali Noor").count() == 0
    pg.select_option("#fstatus", "cancelled")
    pg.wait_for_timeout(300)
    check(9, "Cancelled from the calendar: Ali is told without the office's reason; hidden unless 'Cancelled' is picked",
          msg.startswith("Hi Ali, your site visit to Unit 1204, Marina Crest (MC-1204) on") and "has been cancelled" in msg and "valuation" not in msg and gone and pg.locator(".ev.cancelled", has_text="Ali Noor").count() == 1, shot("09-cancelled"), msg[:110])
    pg.select_option("#fstatus", "active")

    with pg.expect_download() as dl:
        pg.click("#ics")
    body = Path(dl.value.path()).read_text()
    check(10, "Download the shown range as a calendar file", body.startswith("BEGIN:VCALENDAR") and "Sara Khan" in body and "Ali Noor" not in body
          and dl.value.suggested_filename.endswith(".ics"), shot("10-ics"), dl.value.suggested_filename)

    pg.evaluate("window.print = () => { window.__printed = true; }")
    pg.click("#printBtn")
    pg.wait_for_timeout(600)
    sheet = pg.locator("#print").inner_text()
    pg.emulate_media(media="print")
    shot("11-print")
    pg.emulate_media(media="screen")
    check(11, "Print: a clean sheet with time, client, phone, property and address", pg.evaluate("window.__printed === true") and "+971506680001" in sheet
          and "Marina Crest, Dubai Marina" in sheet and "17:00–18:00" in sheet, "11-print.png", sheet.replace("\n", " ")[:140])

    cal(person="omar")
    check(12, "A broker has no ⚙ (only the owner sets hours, kinds and video)", pg.locator("#openSet").is_hidden(), shot("12-broker"))
    cal(person="layla")
    pg.click("#openSet")
    pg.select_option("#vprov", "zoom")
    state = pg.locator("#vstate").inner_text()
    pg.check("#vauto")
    pg.click("#ssave")
    pg.wait_for_timeout(700)
    vs = api.get(f"{BASE}/api/calendar?person=layla").json()["video"]
    check(13, "The owner picks Zoom and turns on links at confirmation; it says Zoom isn't connected and where to add the keys",
          "Not connected" in state and "ZOOM_ACCOUNT_ID" in state and vs == {"provider": "zoom", "auto": True}, shot("13-video-settings"), state)

    r2 = customer("971506680004", f"Can we do a video call on Wednesday {WED.day} {WED:%b} at 3pm?", "Maya Chen")
    cal(person="omar")
    pg.locator(".ev", has_text="Maya Chen").click()
    det = pg.locator("#detail").inner_text()
    check(14, "Not connected: no link is invented; the client hears the broker will send it, and the reason shows on the appointment",
          "will send the link" in r2 and "zoom.us" not in r2 and "Zoom is not connected" in det and "Not made yet" in det, shot("14-no-link"), r2[:120])
    pg.locator("#detail button", has_text="Create link").click()
    pg.wait_for_timeout(600)
    toast = pg.locator(".toast").last.inner_text() if pg.locator(".toast").count() else ""
    check(15, "'Create link' says why it can't, instead of a fake link", "not connected" in toast, shot("15-create-link"), toast)

    pg.goto(f"{BASE}/web/settings.html")
    pg.wait_for_timeout(800)
    card = pg.locator("section", has_text="Zoom · links for video calls")
    check(16, "Settings has the Zoom card for the three keys (not saved here: that writes the real .env)",
          card.count() == 1 and card.locator("#ZOOM_CLIENT_SECRET").get_attribute("type") == "password", shot("16-settings-zoom"))

    pg.set_viewport_size({"width": 390, "height": 844})
    over = []
    for v in ("day", "week", "month", "list"):
        cal("layla", v)
        if pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
            over.append(v)
    check(17, "Day, Week, Month and List fit a phone", not over, shot("17-phone"), ", ".join(over))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
