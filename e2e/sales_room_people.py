"""Signed in as the people themselves (DIWAN_AUTH on): a broker sees their own leads and their own PA, the Sales manager sees
everyone's, and the owner sees all. A fresh offline server with a scratch database; the passwords are set first:
python e2e/sales_room_people.py http://127.0.0.1:8032 <out dir>"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8032"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "salespeople"
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
PASSWORD = "a good password"


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n:>2} {name}{' · ' + str(note)[:180] if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "chrome"))

    def signed_in(person):
        ctx = b.new_context(viewport={"width": 1440, "height": 1000})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"{person}: {e}"))
        pg.on("response", lambda r: errors.append(f"{person}: {r.status} {r.url}") if r.status >= 500 or r.status == 403 else None)
        r = ctx.request.post(f"{BASE}/api/auth/login", data={"person": person, "password": PASSWORD})
        assert r.ok, r.text()
        return ctx, pg

    owner, opg = signed_in("layla")
    for phone, who in (("971507770201", "Sara Khan"), ("971507770202", "Ali Rahman"), ("971507770203", "Mona Said")):
        owner.request.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": "Hello, can someone call me please?", "name": who})
    brokers = {r["phone"]: r["broker"] for r in owner.request.get(f"{BASE}/api/chats?view=all").json()["rows"]}
    broker = brokers["971507770201"]
    theirs = [ph for ph, x in brokers.items() if x == broker]
    other = next(ph for ph, x in brokers.items() if x != broker)

    ctx, pg = signed_in(broker)
    pg.goto(f"{BASE}/")
    pg.wait_for_load_state("networkidle")
    check(1, "A broker lands in the Sales room", pg.url.endswith("/web/sales.html"), pg.url)
    pg.wait_for_selector("h2:has-text('Call now')")
    pg.wait_for_timeout(400)
    text = pg.locator("#board").inner_text()
    check(2, "They see their own lead, and no one else's", "Sara Khan" in text and not any(n in text for n in ("Ali Rahman", "Mona Said") if brokers[{"Ali Rahman": "971507770202", "Mona Said": "971507770203"}[n]] != broker), text[:120])
    pg.screenshot(path=str(OUT / "01-broker-room.png"), full_page=True)
    errors_before = len(errors)
    check(3, "Another broker's chat is refused", ctx.request.get(f"{BASE}/api/chats/{other}").status == 403)
    check(4, "The Inbox lists only their own", {r["phone"] for r in ctx.request.get(f"{BASE}/api/chats?view=all").json()["rows"]} == set(theirs))
    pg.locator(".pa-open").click()
    pg.locator(".pa-panel input").fill("What's waiting on me?")
    pg.locator(".pa-panel input").press("Enter")
    pg.wait_for_timeout(600)
    a = pg.locator(".pa-m").last.inner_text()
    check(5, "Their PA answers with their own work", "Sara Khan" in a, a)
    pg.locator(".pa-panel input").fill("Who pays for Karim?")
    pg.locator(".pa-panel input").press("Enter")
    pg.wait_for_timeout(600)
    check(6, "Their PA won't read a deal that isn't theirs", broker == "omar" or "Not recorded" in pg.locator(".pa-m").last.inner_text(), pg.locator(".pa-m").last.inner_text())
    pg.screenshot(path=str(OUT / "02-broker-pa.png"), full_page=True)
    check(7, "The owner's Nova page stays closed", ctx.request.post(f"{BASE}/api/nova/say", data={"text": "hi", "person": broker}).status == 403)
    check(8, "So do the Sales rules", ctx.request.post(f"{BASE}/api/sales/rules", data={"value": {"call_minutes": 5}}).status == 403)
    del errors[errors_before:]  # the refusals above were asked for

    ctx2, pg2 = signed_in("rashid")
    pg2.goto(f"{BASE}/web/sales.html")
    pg2.wait_for_selector("h2:has-text('Call now')")
    pg2.wait_for_timeout(400)
    t2 = pg2.locator("#board").inner_text()
    check(9, "The Sales manager sees everyone's", all(n in t2 for n in ("Sara Khan", "Ali Rahman", "Mona Said")) and "EACH BROKER'S DAY" in t2.upper())

    ctx3, pg3 = signed_in("maya")
    pg3.goto(f"{BASE}/web/studio.html")
    pg3.wait_for_load_state("domcontentloaded")
    pg3.wait_for_selector(".pa-open")
    check(10, "Marketing has a PA too", "PA" in pg3.locator(".pa-open").inner_text())
    check(11, "Marketing can't open the Sales room", ctx3.request.get(f"{BASE}/api/sales/board").status == 403)
    errors[:] = [e for e in errors if "/api/sales/board" not in e]

    ctx4, pg4 = signed_in("priya")
    r = ctx4.request.post(f"{BASE}/api/pa/say", data={"text": "Hi", "person": "layla"}).json()
    check(12, "A person can't speak as someone else", r.get("pa") == "Priya's PA", r)
    opg.goto(f"{BASE}/web/index.html")
    opg.wait_for_selector("#day h2")
    check(13, "The owner's Nova day still opens", "Layla" in opg.locator("#hello").inner_text())
    b.close()

failed = [r for r in results if not r[2]]
print(f"\n{len(results) - len(failed)} of {len(results)} passed; page errors: {errors or 'none'}")
sys.exit(1 if failed or errors else 0)
