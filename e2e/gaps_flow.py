"""The items parts 1 to 3 had tested in code only, now checked in the browser: Arabic, cancelling in the chat, the
broker's morning list, a plain-text reminder inside WhatsApp's 24-hour window. Fresh demo server, rules mode:
python e2e/gaps_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan.agents import nudge  # noqa: E402
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "gaps"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
NOW = datetime.now(DUBAI)
TUE = (NOW + timedelta(days=(1 - NOW.weekday()) % 7 or 7)).replace(hour=16, minute=0, second=0, microsecond=0)


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
                break
            pg.wait_for_timeout(150)
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as=layla")
        pg.wait_for_timeout(700)
        sent = [m for m in api.get(f"{BASE}/api/chats/{phone}").json()["messages"][before:] if m["type"] == "sent"]
        return sent[-1]["text"] if sent else ""

    # these steps move the clock in hours from the real time of day: run them with the owner's quiet hours and Friday prayer off
    # (the rule has its own exact test in tests/test_nudge.py), so they pass at any hour
    OPEN = nudge.QUIET | {"quiet_from": "00:00", "quiet_to": "00:00", "friday_prayer": False}
    cur = api.get(f"{BASE}/api/rania/quiet").json()
    api.post(f"{BASE}/api/rania/quiet", data={"by": "layla", "quiet_from": "00:00", "quiet_to": "00:00", "friday_prayer": False,
                                              **{k: cur[k] for k in ("after_hours", "template", "then", "then_after_hours")}})

    def run(at):
        return api.post(f"{BASE}/api/nudges/run", data={"at": nudge.next_allowed(OPEN, at).isoformat()}).json()

    # 1. Arabic: only looking, in Arabic
    A = "971505550001"
    customer(A, "مرحبا", name="Huda Saeed")
    r = customer(A, "شكراً، مجرد أتفرج حالياً", name="Huda Saeed")
    prof = pg.locator("#prof").inner_text()
    check(1, "Arabic 'just looking': a warm Arabic reply and 🌱 Nurture", "خذ وقتك" in r and "nurtured" in prof, shot("01-arabic-nurture"), r)

    # 2. Arabic follow-up while quiet
    B = "971505550002"
    customer(B, "أبغى أشتري شقة", name="Faisal Omar")
    run(NOW + timedelta(hours=20.5))
    msgs = [m for m in api.get(f"{BASE}/api/chats/{B}").json()["messages"] if m.get("nudge")]
    pg.goto(f"{BASE}/web/inbox.html?chat={B}&as=layla")
    pg.wait_for_timeout(700)
    check(2, "A quiet Arabic client gets the follow-up in Arabic", msgs and "لا عجلة" in msgs[0]["text"], shot("02-arabic-follow-up"),
          msgs[0]["text"] if msgs else "")

    # 3. Cancelling in the chat
    C = "971505550003"
    customer(C, "Hi", name="Ali Noor")
    customer(C, "Can I see MC-1204 on Tuesday at 4pm?", name="Ali Noor")
    r = customer(C, "Sorry, I need to cancel the viewing", name="Ali Noor")
    week = (TUE - timedelta(days=1)).date().isoformat()
    left = [a for a in api.get(f"{BASE}/api/calendar?person=layla&start={week}").json()["appointments"] if a["customer"] == "Ali Noor" and a["status"] != "cancelled"]
    pg.goto(f"{BASE}/web/calendar.html?as=layla&start={week}")
    pg.wait_for_timeout(700)
    blocks = pg.locator(".ev:not(.blk)").all_inner_texts()  # cancelled ones are hidden unless the filter asks
    broker = next(c["broker"] for c in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"] if c["phone"] == C)  # leads are shared out
    bell = [n["text"] for n in api.get(f"{BASE}/api/notices/{broker}").json()["items"]]
    check(3, "Cancelling in the chat: confirmed, gone from the calendar, the broker told",
          "cancelled" in r and not left and not any("Ali Noor" in x for x in blocks) and any("cancelled" in t for t in bell), shot("03-cancelled"), r)

    # 4. The broker's morning list
    D = "971505550004"
    customer(D, "Hi", name="Mona Saleh")
    customer(D, "Can I see MC-1204 on Tuesday at 11am?", name="Mona Saleh")
    run(TUE.replace(hour=9, minute=5))
    pg.goto(f"{BASE}/web/inbox.html?as=omar")
    pg.wait_for_timeout(700)
    pg.click("#bell")
    pg.wait_for_timeout(400)
    body = pg.locator("body").inner_text()
    check(4, "Omar's bell shows the day's list in the morning", "Today, 1 appointment" in body and "Mona Saleh" in body, shot("04-morning"))

    # 5. A plain-text reminder inside the 24-hour window
    E = "971505550005"
    tomorrow = (NOW + timedelta(days=1))
    # "tomorrow" may be a closed day (Sunday): the owner's days are a setting, so open every day for this step, which is about
    # the 24-hour window, not about which days the office is open
    api.post(f"{BASE}/api/calendar/settings", data={"by": "layla", "hours": {"days": [0, 1, 2, 3, 4, 5, 6]}})
    day = "tomorrow" if (tomorrow - NOW).days < 2 and tomorrow.date() == (NOW + timedelta(days=1)).date() else tomorrow.strftime("%A")
    customer(E, "Hi", name="Omar Faris")
    r = customer(E, f"Can I see MC-1204 {day} at 4pm?", name="Omar Faris")
    at = tomorrow.replace(hour=16, minute=0, second=0, microsecond=0)
    run(at - timedelta(hours=23))
    msgs = [m for m in api.get(f"{BASE}/api/chats/{E}").json()["messages"] if m.get("reminder")]
    pg.goto(f"{BASE}/web/inbox.html?chat={E}&as=layla")
    pg.wait_for_timeout(700)
    ok = msgs and not msgs[0]["template"] and "a reminder of your site visit to Unit 1204" in msgs[0]["text"] and "maps.google.com" in msgs[0]["text"]
    check(5, "Inside 24 hours the reminder is plain text with where to go (map link) and what to bring", ok, shot("05-reminder-text"),
          msgs[0]["text"] if msgs else r)
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
