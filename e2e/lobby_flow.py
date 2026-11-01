"""The Lobby room in a real browser, as the owner and the staff would use it (docs/closed-loop-spec.md L569-582). Run on a scratch
server, never diwan.db: python e2e/lobby_flow.py http://127.0.0.1:8066 <out dir>. WATCH=1 opens a window to watch."""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8066"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "lobby"
OUT.mkdir(parents=True, exist_ok=True)
WATCH = os.environ.get("WATCH") == "1"
errors, results = [], []


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n} {name}{' · ' + str(note)[:150] if note else ''}", flush=True)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=not WATCH, slow_mo=250 if WATCH else 0)
    pg = b.new_page(viewport={"width": 1400, "height": 950})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 500 else None)
    api = pg.request

    pg.goto(f"{BASE}/web/lobby.html")
    pg.wait_for_selector("h1:has-text('Lobby')")
    check("1a", "the Lobby is a page, in the top bar", pg.locator("nav a:has-text('Lobby')").count() == 1)
    check("1b", "it starts empty and says so", pg.locator("text=No experiment is running").count() == 1 and pg.locator("text=No threads yet").count() == 1)
    pg.screenshot(path=OUT / "1-empty.png")

    # a playbook from outside, with where it was seen and the evidence
    pg.click("summary:has-text('Add a playbook')")
    form = pg.locator("details[open] form")
    form.locator("select").first.select_option("sales")
    form.locator("input[placeholder^='The pattern']").fill("Follow up on day 3 with a floor plan")
    form.locator("input[placeholder^='Where']").fill("A public property talk")
    form.locator("input[placeholder^='The evidence']").fill("The speaker reported twice the replies")
    form.locator("button:has-text('Add')").click()
    pg.wait_for_selector("h3:has-text('Follow up on day 3')")
    check("2a", "a playbook card shows the pattern, where seen and the evidence", pg.locator("text=The speaker reported twice the replies").count() == 1)

    # a client's phone number is refused, on the screen
    pg.reload()
    pg.wait_for_selector("h1:has-text('Lobby')")
    pg.click("summary:has-text('Add a playbook')")
    form = pg.locator("details[open] form")
    form.locator("input[placeholder^='The pattern']").fill("Call +971 50 123 4567 again")
    form.locator("input[placeholder^='Where']").fill("A chat")
    form.locator("input[placeholder^='The evidence']").fill("It worked")
    form.locator("button:has-text('Add')").click()
    pg.wait_for_timeout(700)
    check("2b", "client details are refused and the reason is shown", pg.locator("text=client details stay out").count() >= 1, pg.locator("body").inner_text()[-90:])

    # the guardrail, through the form a person would use
    pg.reload()
    pg.wait_for_selector("h1:has-text('Lobby')")
    pg.click("summary:has-text('Propose an experiment')")
    form = pg.locator("details[open] form")
    form.locator("input[placeholder^='The change']").fill("Fewer checks")
    form.locator("textarea").fill("Drop screening on small deals")
    form.locator("button:has-text('Propose')").click()
    pg.wait_for_timeout(700)
    check("3a", "a compliance rule can't be proposed", pg.locator("text=can't be changed from the Lobby").count() >= 1)

    # a good proposal, by the form
    pg.reload()
    pg.wait_for_selector("h1:has-text('Lobby')")
    pg.click("summary:has-text('Propose an experiment')")
    form = pg.locator("details[open] form")
    form.locator("input[placeholder^='The change']").fill("Ask if they're still looking")
    form.locator("textarea").fill("Hi {name}, a quick one so I don't chase you: are you still looking?")
    form.locator("input[placeholder^='Why']").fill("Too many leads go silent")
    form.locator("button:has-text('Propose')").click()
    pg.wait_for_selector("h3:has-text('still looking')")
    card = pg.locator(".card", has=pg.locator("h3:has-text('still looking')"))
    text = card.inner_text()
    check("4a", "the proposal shows change, audience, period and metric", all(w in text for w in ("A new follow-up message", "For whom", "14 days", "Clients who reply")), text[:120])
    check("4b", "it is the day's idea too", pg.locator(".idea").count() == 1)
    pg.screenshot(path=OUT / "2-proposed.png", full_page=True)

    # the owner edits it first, then approves
    card.locator("button:has-text('Edit first')").click()
    pg.locator("textarea").first.fill("Hi {name}, are you still looking, or shall I pause for now?")
    pg.locator("input[type=number]").first.fill("7")
    pg.click("button:has-text('Approve as edited')")
    pg.wait_for_selector("h2:has-text('Running') >> .n")
    card = pg.locator(".card", has=pg.locator("h3:has-text('still looking')"))
    text = card.inner_text()
    check("5a", "it runs with the owner's words and period", "shall I pause" in text and "With it" in text and "Without" in text, text[:140])
    check("5b", "half is the comparison and Records already reads it", "50% are the comparison" in text and "From Records".lower() in text.lower())
    pg.screenshot(path=OUT / "3-running.png", full_page=True)

    # a second one on the same thing for the same people is refused
    r = api.post(f"{BASE}/api/lobby-room/propose", data={"by": "rashid", "draft": {"kind": "followup", "title": "Other words", "text": "Hi {name}, anything new?", "metric": "reply_rate", "days": 7}})
    other = r.json()["id"]
    pg.reload()
    pg.wait_for_selector(f"h3:has-text('{other}')")
    pg.locator(".card", has=pg.locator(f"h3:has-text('{other}')")).locator("button:has-text('Approve')").first.click()
    pg.wait_for_timeout(700)
    check("5c", "two experiments can't change the same thing for the same people", pg.locator("text=already changes this").count() >= 1)
    pg.locator(".card", has=pg.locator(f"h3:has-text('{other}')")).locator("input[placeholder^='Why not']").fill("One at a time")
    pg.locator(".card", has=pg.locator(f"h3:has-text('{other}')")).locator("button:has-text('Refuse')").click()
    pg.wait_for_selector("h2:has-text('Refused')")
    check("5d", "the owner refuses with a reason, and it is kept on the page", pg.locator("text=One at a time").count() == 1)

    # the week's threads
    pg.click("button:has-text('Write this week')")
    pg.wait_for_selector("h2:has-text('This week') >> .n")
    threads = pg.locator("section:has(h2:has-text('This week')) .card")
    check("6a", "a thread for every room", threads.count() == 9, threads.count())
    comp = pg.locator(".card", has=pg.locator("h3:text-is('Compliance')")).inner_text()
    check("6b", "Compliance only listens", "don't change from the Lobby" in comp, comp[:120])
    sales = pg.locator(".card", has=pg.locator("h3:text-is('Sales')")).inner_text()
    check("6c", "the Sales rep discusses the playbook and the host answers", "Seen elsewhere" in sales and "Lobby host" in sales, sales[:160])
    pg.screenshot(path=OUT / "4-threads.png", full_page=True)

    # stop early and roll back: Records still reports
    pg.click("button:has-text('Stop and roll back')")
    pg.wait_for_selector("h2:has-text('Rolled back') >> .n")
    text = pg.locator("section:has(h2:has-text('Rolled back'))").inner_text()
    check("7a", "rolled back, with who and why and Records' line", "Layla" in text and "Stopped early" in text and "Clients who reply" in text, text[:150])
    check("7b", "nothing runs now", pg.locator("text=No experiment is running").count() == 1)

    # the owner's brief
    pg.goto(f"{BASE}/web/index.html")
    pg.wait_for_selector("#day")
    pg.wait_for_timeout(1500)
    check("8a", "the idea of the day is on Nova's page", pg.locator("text=Lobby idea of the day").count() == 1 and pg.locator("#day a:has-text('Open the Lobby')").count() == 1)
    pg.screenshot(path=OUT / "5-nova.png", full_page=True)

    # the requests board keeps working under its own name, and the floor has the room
    pg.goto(f"{BASE}/web/office3d.html")
    try:
        pg.wait_for_selector("button:has-text('Lobby')", timeout=45_000, state="attached")  # the 3D floor is slow without a window
    except Exception:  # noqa: BLE001  the check below reports it
        pass
    check("9a", "the Lobby is on the floor list", pg.locator("button:has-text('Lobby')").count() >= 1)
    if pg.locator("button:has-text('Lobby')").count():
        pg.locator("button:has-text('Lobby')").first.click(force=True)
        pg.wait_for_timeout(3500)
        pg.screenshot(path=OUT / "6-floor.png")
        check("9b", "entering the room shows the host and a way into the page", pg.locator("a:has-text('Open the Lobby room')").count() >= 1)
    if WATCH:
        pg.goto(f"{BASE}/web/lobby.html")
        pg.wait_for_timeout(2000)
    b.close()

bad = [r for r in results if not r[2]]
print(f"{len(results) - len(bad)} of {len(results)} passed; page errors: {errors[:5]}")
sys.exit(1 if bad or errors else 0)
