"""When a client goes quiet (docs/quiet-clients-spec.md), checked as a person would. The clock is moved with the
sandbox-only /api/nudges/run (a connected WhatsApp line refuses it). Run against a fresh demo server in rules mode:
python e2e/quiet_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from diwan.agents import nudge  # noqa: E402
from diwan.slots import DUBAI  # noqa: E402

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "quiet"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
T0 = datetime.now(DUBAI)
S = nudge.QUIET | {"quiet_from": "00:00", "quiet_to": "00:00", "friday_prayer": False}  # see below


def check(n, name, ok, shot, note=""):
    results.append((n, name, bool(ok), shot, note))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + note if note else ''}")


def later(hours):
    return nudge.next_allowed(S, T0 + timedelta(hours=hours)).isoformat()


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    api = pg.request

    def shot(name):
        pg.screenshot(path=str(OUT / f"{name}.png"))
        return f"{name}.png"

    def customer(phone, text, name="Sara Khan"):
        before = len(api.get(f"{BASE}/api/chats/{phone}").json()["messages"]) if api.get(f"{BASE}/api/chats/{phone}").ok else 0
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as=layla")
        pg.click("#phonebtn")
        pg.fill("#pname", name)
        pg.fill("#pnum", phone)
        pg.fill("#ptext", text)
        pg.click("#psend")
        for _ in range(60):
            new = api.get(f"{BASE}/api/chats/{phone}").json()["messages"][before:] if api.get(f"{BASE}/api/chats/{phone}").ok else []
            if any(m["type"] == "sent" for m in new):
                break
            pg.wait_for_timeout(150)
        return open_chat(phone)

    def open_chat(phone):
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as=layla")
        pg.wait_for_timeout(700)
        return api.get(f"{BASE}/api/chats/{phone}").json()

    def run(hours):
        return api.post(f"{BASE}/api/nudges/run", data={"at": later(hours)}).json()

    # 1. The owner's schedule
    pg.goto(f"{BASE}/web/qualify.html")
    pg.select_option("#as", "omar")
    pg.wait_for_timeout(500)
    pg.locator("#quietbox").scroll_into_view_if_needed()
    check(1, "A broker sees the follow-up schedule but can't change it", pg.locator("#qsave").is_disabled()
          and pg.locator("#qafter").input_value() == "20h, 3d, 7d", shot("01-broker-locked"))
    pg.select_option("#as", "layla")
    pg.wait_for_timeout(400)
    pg.fill("#qafter", "3d, 1d")
    pg.click("#qsave")
    pg.wait_for_timeout(500)
    toast = pg.locator(".toast").last.inner_text() if pg.locator(".toast").count() else ""
    check(2, "A schedule out of order is refused with the reason", "each later than the one before" in toast, shot("02-refused"), toast)
    pg.fill("#qafter", "20h, 3d, 7d")
    pg.select_option("#qtpl", "gentle_follow_up")
    pg.fill("#qthenafter", "3d")
    pg.click("#qsave")
    pg.wait_for_timeout(600)
    qs = api.get(f"{BASE}/api/rania/quiet").json()
    check(3, "The owner saves the schedule, quiet hours, Friday prayer and the template",
          qs["after_hours"] == [20, 72, 168] and qs["template"] == "gentle_follow_up" and qs["friday_prayer"] and qs["quiet_from"] == "21:00",
          shot("03-saved"))

    # 2. A client goes quiet while qualifying
    A = "971503330001"
    customer(A, "Hi, I want to buy")
    customer(A, "Dubai Marina")
    prof = pg.locator("#prof").inner_text()
    check(4, "The lead shows its follow-ups: 0 of 3 sent and when the next is due", "follow-ups when quiet" in prof.lower() and "0 of 3 sent · next" in prof,
          shot("04-scheduled"))
    pg.goto(f"{BASE}/web/qualify.html")
    pg.wait_for_timeout(700)
    pg.locator("#quietbox").scroll_into_view_if_needed()
    check(5, "The owner sees who is due next", "Sara Khan" in pg.locator("#qnext").inner_text() and "follow-up 1 of 3" in pg.locator("#qnext").inner_text(),
          shot("05-due-next"))
    # The steps below move the clock in hours from the real time of day. With the owner's quiet hours on (21:00 to 09:00), a
    # follow-up due 20-24 hours after a 07:00 message could only go as a template, so they run with quiet hours and Friday
    # prayer off. The rule itself has its own exact test (tests/test_nudge.py).
    cur = api.get(f"{BASE}/api/rania/quiet").json()  # keep everything the owner saved, change only the quiet hours
    api.post(f"{BASE}/api/rania/quiet", data={"by": "layla", "quiet_from": "00:00", "quiet_to": "00:00", "friday_prayer": False,
                                              **{k: cur[k] for k in ("after_hours", "template", "then", "then_after_hours")}})
    r1 = run(2)
    r2 = run(20.5)
    d = open_chat(A)
    m = [x for x in d["messages"] if x.get("nudge")]
    check(6, "Nothing before 20 hours; then one follow-up that picks up where they left off",
          r1["done"] == [] and len(m) == 1 and "no rush" in m[0]["text"] and pg.locator(".chip", has_text="follow-up 1").count() == 1,
          shot("06-follow-up-1"), m[0]["text"] if m else str(r2))
    run(21)
    check(7, "Never twice for the same step", len([x for x in api.get(f"{BASE}/api/chats/{A}").json()["messages"] if x.get("nudge")]) == 1, shot("07-not-twice"))
    run(73)
    d = open_chat(A)
    m = [x for x in d["messages"] if x.get("nudge")]
    check(8, "After 24 hours the follow-up is the approved template",
          len(m) == 2 and m[1]["template"] == "gentle_follow_up" and "1 of 3" not in pg.locator("#prof").inner_text()
          and "2 of 3 sent" in pg.locator("#prof").inner_text(), shot("08-template"), m[-1]["text"] if m else "")
    run(169)
    run(169 + 73)
    d = open_chat(A)
    prof = pg.locator("#prof").inner_text()
    check(9, "Follow-up 3 would repeat follow-up 2 word for word, so it's skipped; 3 days later the lead goes to Nurture",
          "went quiet after 2 follow-ups" in prof.lower(), shot("09-nurture"))
    n_before = len([x for x in d["messages"] if x.get("nudge")])
    run(400)
    check(10, "Nothing more after that", len([x for x in api.get(f"{BASE}/api/chats/{A}").json()["messages"] if x.get("nudge")]) == n_before == 2, shot("10-nothing-more"))
    customer(A, "Hi, sorry, I was travelling")
    prof = pg.locator("#prof").inner_text()
    check(11, "When they write again the lead comes back and the count starts over",
          "Came back ready" in prof and "0 of 3 sent" in prof, shot("11-back"))

    # 3. Stop
    B = "971503330002"
    customer(B, "Hello", name="Omar Faris")
    d = customer(B, "Please stop messaging me", name="Omar Faris")
    run(30)
    prof = pg.locator("#prof").inner_text()
    check(12, "'Stop' gets one confirmation and no follow-up after it",
          d["messages"][-1]["text"].startswith("Understood. I won't message you again") and "🛑 No follow-ups: stopped" in prof
          and not [x for x in api.get(f"{BASE}/api/chats/{B}").json()["messages"] if x.get("nudge")], shot("12-stop"))

    # 4. Phone width
    pg.set_viewport_size({"width": 390, "height": 844})
    over = []
    for page in ("qualify.html", f"inbox.html?chat={A}&as=layla"):
        pg.goto(f"{BASE}/web/{page}")
        pg.wait_for_timeout(700)
        if pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
            over.append(page)
    pg.goto(f"{BASE}/web/qualify.html")
    pg.wait_for_timeout(600)
    pg.locator("#quietbox").scroll_into_view_if_needed()
    check(13, "The follow-up panel and the Inbox fit a phone", not over, shot("13-phone"), ", ".join(over))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
