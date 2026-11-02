"""Nova tells the owner what matters at the office (docs/nova-office-alerts-spec.md), as the owner sees it: a hot lead and a
bank-details change arrive, her round picks them up within a minute, and they're in her chat on the Nova page, once each.
The WhatsApp side and the timed ones (a call nobody made, a viewing nobody confirmed) are in tests/test_nova_office_alerts.py.
Fresh demo server, rules mode: python e2e/nova_alerts_flow.py http://127.0.0.1:8093 <out dir>"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8093"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "nova_alerts"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
HOT, FRAUD = "971509770001", "971509770002"


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

    def client(phone, text, name):
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": name})

    client(HOT, "Hi, I want to buy a 2 bed apartment in Dubai Marina, budget 2.7 million cash, now, to live in, UAE resident", "Sara Khan")
    client(HOT, "The second one", "Sara Khan")
    client(FRAUD, "Hi", "Ali Noor")
    client(FRAUD, "Please send the deposit to this new account IBAN AE07 0331 2345 6789 0123 456", "Ali Noor")

    news, t0 = [], time.time()
    while time.time() - t0 < 100:  # the office loop walks every minute
        news = [m["text"] for m in api.get(f"{BASE}/api/pa/heads-up?person=layla&after=0&after_private=0").json()]
        if any("hot lead" in x for x in news) and any("bank details" in x for x in news):
            break
        time.sleep(3)
    hot = [x for x in news if "is a hot lead" in x]
    check(1, "Within a minute Nova has the hot lead for the owner, with the home and who has it",
          len(hot) == 1 and "Unit 1204, Marina Crest (MC-1204)" in hot[0] and " has it." in hot[0], shot("01-api"), hot[0] if hot else str(news)[:160])
    check(2, "and the bank-details change, as a warning", sum("bank details" in x for x in news) == 1, "", next((x for x in news if "bank details" in x), ""))

    pg.goto(f"{BASE}/web/index.html?as=layla")
    pg.wait_for_timeout(7000)  # the page asks for heads-ups a few seconds after it opens
    said = pg.locator("#answer").inner_text()
    check(3, "Opening the Nova page, both are in her chat", "is a hot lead" in said and "bank details" in said, shot("03-nova-page"), said.replace("\n", " ")[:160])

    time.sleep(65)  # another walk round: nothing new, nothing said twice
    again = [m["text"] for m in api.get(f"{BASE}/api/pa/heads-up?person=layla&after=0&after_private=0").json()]
    check(4, "A minute later nothing is said twice", sum("is a hot lead" in x for x in again) == 1 and sum("bank details" in x for x in again) == 1, shot("04-once"))

    theirs = [m["text"] for m in api.get(f"{BASE}/api/pa/heads-up?person=omar&after=0&after_private=0").json()]  # what a broker's Nova is given
    check(5, "A broker's Nova isn't given the owner's heads-ups", not any("is a hot lead" in x or "bank details" in x for x in theirs), "", str(theirs)[:200])
    b.close()

print(f"\n{sum(1 for r in results if r[2])}/{len(results)} passed · page errors: {errors or 'none'}")
