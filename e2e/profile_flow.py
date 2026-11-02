"""The lead profile, part 1 (docs/lead-profile-spec.md): the stage under the Deal desk's rules and the quick actions,
used as a broker would. Fresh demo server, rules mode: python e2e/profile_flow.py http://127.0.0.1:8052 <out dir>"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "profile"
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

    def say(phone, text, name):
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": name})

    def lead(phone):
        return api.get(f"{BASE}/api/chats/{phone}").json()

    def open_as(phone, who):
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as={who}")
        pg.wait_for_selector("#pstage")
        pg.wait_for_timeout(400)

    def toast():
        return pg.locator(".toast").last.inner_text() if pg.locator(".toast").count() else ""

    A = "971508880001"
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now", "To live in", "UAE resident"):
        say(A, t, "Sara Khan")
    broker = lead(A)["broker"]
    other = next(t["id"] for t in api.get(f"{BASE}/api/team").json() if t["id"] != broker)
    open_as(A, broker)
    opts = pg.locator("#pstage option").all_inner_texts()
    check(1, "The profile shows the stage as a dropdown of the deal's own stages, with Won only from closing",
          pg.locator("#pstage").input_value() == "Qualified" and opts[:5] == ["New", "Qualifying", "Qualified", "Viewing booked", "Viewed"]
          and "Lost" in opts and "Won (comes from closing)" in opts and pg.locator("#pstage option", has_text="Won").is_disabled(), shot("01-stage"), " · ".join(opts))

    pg.locator(".stagebtn").click()
    pg.wait_for_timeout(300)
    check(2, "The stage button in the chat header takes you to the profile's stage", pg.evaluate("document.activeElement.id") == "pstage", shot("02-header"))

    pg.select_option("#pstage", "Viewed")
    pg.wait_for_timeout(700)
    check(3, "Moving forward is one click", lead(A)["stage"] == "Viewed", shot("03-forward"), toast())

    pg.select_option("#pstage", "Lost")
    pg.wait_for_timeout(300)
    asked = pg.locator("#preason").is_visible()
    pg.select_option("#plost", "Other")  # the owner's list of reasons; "Other" needs words
    pg.locator(".actform button", has_text="Save").click()
    pg.wait_for_timeout(500)
    refused = toast()
    pg.fill("#preason", "bought elsewhere")
    pg.locator(".actform button", has_text="Save").click()
    pg.wait_for_timeout(700)
    check(4, "Lost asks why, refuses without a reason, and saves with one", asked and "reason" in refused.lower() and lead(A)["stage"] == "Lost",
          shot("04-lost"), refused)

    open_as(A, other)
    check(5, "Another broker sees the stage but can't change it, and is told who can",
          pg.locator("#pstage").is_disabled() and "changes this lead" in pg.locator(".act").inner_text(), shot("05-not-yours"))

    B = "971508880002"
    say(B, "Hi, I want to buy", "Omar Faris")
    bb = lead(B)["broker"]
    open_as(B, bb)
    pg.locator(".qa button", has_text="Mark hot").click()
    pg.wait_for_timeout(700)
    hot = pg.locator(".conv", has_text="Omar Faris").locator(".tg.hot").count() == 1
    pg.locator(".qa button", has_text="Hot ✓").click()
    pg.wait_for_timeout(700)
    check(6, "Mark hot shows 🔥 in the list; clicking again takes it off", hot and pg.locator(".conv", has_text="Omar Faris").locator(".tg.hot").count() == 0, shot("06-hot"))

    pg.locator(".qa button", has_text="Follow up on").click()
    pg.fill("#pfnote", "after their trip")
    pg.locator(".actform button", has_text="Save").click()
    pg.wait_for_timeout(800)
    banner = pg.locator("#chat .banner.att").inner_text() if pg.locator("#chat .banner.att").count() else ""
    sent_after = [m for m in lead(B)["messages"] if m["type"] == "sent"]
    check(7, "Follow up on a date: a card due then, with the note, and nothing sent to the client",
          "Follow up" in banner and "Wants a call" not in banner and "after their trip" in banner and len(sent_after) == 1, shot("07-follow-up"), banner[:120])
    pg.locator(".qa button", has_text="Follow up on").click()
    pg.locator(".actform button", has_text="Save").click()
    pg.wait_for_timeout(600)
    check(8, "A second follow-up while one is open is refused, saying which", "already has an open card" in toast(), shot("08-refused"), toast()[:100])

    pg.locator(".qa button", has_text="Transfer").click()
    to = pg.locator("#pto option").first.get_attribute("value")
    pg.locator(".actform button", has_text="Transfer").click()
    pg.wait_for_timeout(800)
    d = lead(B)
    check(9, "Transfer moves the lead and its open card to the other broker", d["broker"] == to and d["attention"]["who"] == to, shot("09-transfer"), f"to {to}")

    C = "971508880003"
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now", "To live in", "UAE resident"):
        say(C, t, "Mona Saleh")
    cb = lead(C)["broker"]
    open_as(C, cb)
    pg.locator(".qa button", has_text="Convert").click()  # no property chosen yet: the Deal desk asks which, then the price
    pg.wait_for_url("**/web/deal.html**", timeout=8000)
    pg.wait_for_selector("#convert", timeout=8000)
    check(10, "Convert with no property chosen opens the Deal desk asking which property and the agreed price",
          "/web/deal.html" in pg.url and "which property" in pg.locator("#convert").inner_text(), shot("10-convert"), pg.url.split("/web/")[1][:80])

    # 2. Asked: no calls
    D = "971508880004"
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now", "To live in", "UAE resident"):
        say(D, t, "Huda Karim")
    db = lead(D)["broker"]
    for c in [lead(D)["attention"]] if lead(D)["attention"] else []:
        api.post(f"{BASE}/api/attention/{c['id']}/clear", data={"action": "messaged", "by": db})
    open_as(D, db)
    pg.locator(".act .nocall").click()
    pg.wait_for_timeout(700)
    tag = pg.locator(".conv", has_text="Huda Karim").locator(".tg", has_text="no calls").count() == 1
    say(D, "The first one", "Huda Karim")
    r = [m["text"] for m in lead(D)["messages"] if m["type"] == "sent"][-1]
    att = lead(D)["attention"]
    check(11, "Asked: no calls: the list shows it, Rania promises a reply here instead of a call, and the card is a message card",
          tag and "reply to you here" in r and "call you" not in r and att and att["kind"] == "reply", shot("12-no-calls"), r[:110])
    say(D, "Actually please call me tomorrow", "Huda Karim")
    open_as(D, db)
    check(12, "When the client asks for a call themselves, the switch turns off", "Off" in pg.locator(".act .nocall").inner_text() and not lead(D)["no_calls"],
          shot("13-asked-for-call"))
    pg.locator(".futabs button", has_text="Calls").click()
    pg.wait_for_timeout(300)
    calls = pg.locator(".quietsec").inner_text()
    check(13, "The Calls tab lists this lead's call cards and calls", "Calls · " in calls and "📞" in calls, shot("14-calls"), calls.replace("\n", " / ")[:140])

    # 3. This lead's follow-ups
    E = "971508880005"
    say(E, "I want to buy", "Rami Aziz")
    eb = lead(E)["broker"]
    open_as(E, eb)
    sec = pg.locator(".quietsec").inner_text()
    planned = pg.locator(".quietsec .step.planned").count()
    pg.locator(".quietsec button", has_text="Change").click()
    pg.fill("#fuafter", "2h, 2d")
    pg.locator(".quietsec .actform button", has_text="Save").click()
    pg.wait_for_timeout(700)
    own = pg.locator(".quietsec").inner_text()
    check(14, "Follow-ups lists each one planned, and Change gives this lead its own schedule",
          planned == 3 and "The office's schedule: 20h, 3d, 7d" in sec and "This lead's own schedule: 2h, 2d" in own and pg.locator(".quietsec .step.planned").count() == 2,
          shot("15-own-schedule"), own.replace("\n", " / ")[:160])
    pg.locator(".quietsec button", has_text="Stop for this lead").click()
    pg.wait_for_timeout(700)
    stopped = pg.locator(".quietsec").inner_text()
    pg.locator(".quietsec button", has_text="Resume").click()
    pg.wait_for_timeout(700)
    check(15, "Stop for this lead, then Resume", "No follow-ups: stopped for this lead by" in stopped and "Stop for this lead" in pg.locator(".quietsec").inner_text(),
          shot("16-stop-resume"))

    # 4. Merge: the same person on Instagram and WhatsApp
    F, IG = "971508880006", "ig:layan.m"
    say(IG, "Hi, I want to buy a 2 bed in Dubai Marina", "@layan.m")
    say(F, "Hello, this is Layan from Instagram", "Layan Mansour")
    open_as(F, "layla")  # leads are shared out, so the two may have different brokers: then only a manager or the owner merges
    pg.locator(".qa button", has_text="Merge").click()
    pg.fill("#pmerge", IG)
    pg.locator(".actform button", has_text="Merge").click()
    pg.wait_for_timeout(900)
    thread = pg.locator(".thread").inner_text()
    rows = [r["phone"] for r in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"]]
    check(16, "Merge: both histories in one thread, each marked; the Instagram lead leaves the list; its answers come over",
          "via Instagram @layan.m" in thread and "2 bed in Dubai Marina" in thread and IG not in rows
          and any(a["key"] == "areas" for a in lead(F)["qualify"]["answers"]) and lead(F)["stage"] == "Qualifying", shot("16-merge"))

    pg.set_viewport_size({"width": 390, "height": 844})
    pg.goto(f"{BASE}/web/inbox.html?chat={C}&as={cb}")
    pg.wait_for_selector("#pstage", state="attached")  # on a phone the profile opens from the chat
    pg.locator(".conv").first.click()
    pg.wait_for_timeout(400)
    pg.locator(".pbtn").click()
    pg.wait_for_timeout(400)
    check(17, "On a phone the profile opens with the stage and quick actions, and nothing scrolls sideways",
          pg.locator("#pstage").is_visible() and not pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"), shot("11-phone"))
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
