"""The Deal desk as the people themselves, signed in, each in their own browser (DIWAN_AUTH on), for what e2e/chat_to_close_flow.py
AUTH=1 doesn't reach: Finance's money cases, Compliance's confidentiality, and each person trying what isn't theirs. A fresh offline
server whose passwords are all PASSWORD, never diwan.db: WATCH=1 python e2e/people_flow.py http://127.0.0.1:8075 <out dir>"""
import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8075"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "people"
OUT.mkdir(parents=True, exist_ok=True)
WATCH = os.environ.get("WATCH") == "1"
PASSWORD = "a good password"
SECRET = "UN list entry 4411 for the audit"  # the words of a possible match: only Compliance and the owner may ever read them
errors, results = [], []


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n} {name}{' · ' + str(note)[:170] if note else ''}", flush=True)


with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "msedge"), headless=not WATCH, slow_mo=200 if WATCH else 0)
    people, expected_403 = {}, [False]

    def who(person):
        if person not in people:
            c = b.new_context(viewport={"width": 1400, "height": 900})
            r = c.request.post(f"{BASE}/api/auth/login", data={"person": person, "password": PASSWORD})
            assert r.ok, r.text()
            pg = c.new_page()
            pg.set_default_timeout(12000)
            pg.on("pageerror", lambda e, w=person: errors.append(f"{w}: {e}"))
            pg.on("response", lambda r, w=person: errors.append(f"{w}: {r.status} {r.url}") if r.status >= 500 or (r.status == 403 and not expected_403[0]) else None)
            pg.on("dialog", lambda d: d.accept(answers.pop(0) if d.type == "prompt" and answers else None) if d.type == "prompt" else (d.accept() if confirm[0] else d.dismiss()))
            people[person] = (c, pg)
        return people[person]

    answers, confirm = [], [True]
    owner = who("layla")[0].request
    owner.post(f"{BASE}/api/demo/reset")

    def view(deal):
        return owner.get(f"{BASE}/api/desk/deals/{deal}").json()

    def desk(person, deal):
        pg = who(person)[1]
        pg.bring_to_front()
        pg.goto(f"{BASE}/web/deal.html?deal={deal}")
        pg.wait_for_selector("#dept-comp")
        pg.wait_for_timeout(500)
        return pg

    def toast(pg):
        t = pg.locator(".toast").last
        t.wait_for(timeout=6000)
        return t.inner_text()

    def clear(pg):
        pg.evaluate("document.querySelectorAll('.toast').forEach((t) => t.remove())")

    def stage(name, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001  one fault doesn't hide the rest
            check(name, "stage stopped", False, str(e).split("\n")[0])
            for per, (_, pg) in people.items():
                pg.screenshot(path=str(OUT / f"broke-{name}-{per}.png"))

    def new_deal(phone, name_, amount):
        """A converted deal through the broker's own login."""
        for m in (f"Hi, I want to buy a villa in JVC", "Buying, to live in", "Budget is about 2 million"):
            owner.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": m, "name": name_})
        d = owner.get(f"{BASE}/api/desk/deals?q={name_.split()[0]}").json()["rows"][0]["deal"]
        br = view(d)["broker"]
        r = who(br)[0].request.post(f"{BASE}/api/desk/deals/{d}/convert", data={"by": br, "amount": amount, "property": {"source": "agency", "label": f"Villa {phone[-2:]}, JVC", "other_agency": "Acme Homes", "other_share_pct": 50}})
        assert r.ok, r.text()
        return d, br

    D, BR = None, None
    OTHER = None

    def setup():
        global D, BR, OTHER
        D, BR = new_deal("971507772001", "Nabil Fictional", 2_000_000)
        OTHER = next(x for x in ("omar", "hamza", "nadia") if x != BR)
        check("0a", "a deal converted by the broker's own login", view(D)["stages"]["agreed"]["amount"] == 2_000_000, BR)

    stage("0", setup)

    def my_work():
        pg = who("ahmed")[1]
        pg.bring_to_front()
        pg.goto(f"{BASE}/web/deal.html#my-work")
        pg.wait_for_selector("#view")
        pg.wait_for_timeout(1200)
        check("1a", "Ahmed's My work has no one-press Received", pg.get_by_role("button", name="Received", exact=True).count() == 0)
        btn = pg.get_by_role("button", name="Mark what arrived…").first
        check("1b", "it opens the deal's payment form instead", btn.count() == 1)
        btn.click()
        pg.wait_for_selector("#dept-fin .card")
        pay = pg.locator("#dept-fin .card", has_text="Expect").first
        for label in ("Amount received (AED)", "Method", "Day it arrived", "Paid by", "Amount on the proof", "Payment reference"):
            check(f"1c {label}", f"the form asks: {label}", pay.get_by_label(label).count() == 1)
        check("1d", "the acting-as control is hidden for staff", not pg.locator("#as").is_visible())
        pg.screenshot(path=str(OUT / "1-ahmed-payment.png"), full_page=True)

    stage("1", my_work)

    def money():
        pg = desk("ahmed", D)
        pay = pg.locator("#dept-fin .card", has_text="Expect").first
        want = int(float(pay.get_by_label("Amount received (AED)").input_value()))
        check("2a", "the deposit is prefilled", want == 200_000, want)
        pay.get_by_label("Payment reference").fill("")
        clear(pg)
        pay.get_by_role("button", name="Received").click()
        check("2b", "no reference, no mark", "reference" in toast(pg).lower())
        confirm[0] = False
        pay.get_by_label("Payment reference").fill("ENBD 1")
        pay.get_by_label("Amount received (AED)").fill("250000")
        clear(pg)
        pay.get_by_role("button", name="Received").click()
        check("2c", "more than expected asks first and saves nothing", "more than" in toast(pg), toast(pg))
        check("2d", "nothing was saved", not next(t for t in view(D)["tasks"] if t["agent"] == "pay").get("payments"))
        pay.get_by_label("Amount received (AED)").fill("60000")
        pay.get_by_label("Method").select_option("cash")
        clear(pg)
        pay.get_by_role("button", name="Received").click()
        said = toast(pg)
        check("2e", "cash reaches Compliance before any receipt", "With Compliance" in said, said)
        pg.wait_for_timeout(800)
        v = view(D)
        t = next(x for x in v["tasks"] if x["agent"] == "pay")
        evs = owner.get(f"{BASE}/api/events?deal={D}").json()
        check("2f", "the payment is held and the client isn't told", t["payments"][0]["held"] and "We've received" not in json.dumps(evs))
        check("2g", "no receipt document yet", not any(e["type"] == "document.filed" and e["content"].get("kind") == "receipt" for e in evs))
        pg = desk("priya", D)
        check("2h", "Priya has it to review", pg.locator("#dept-comp").get_by_role("button", name="Reviewed").count() >= 1)
        pg.locator("#dept-comp").get_by_role("button", name="Reviewed").first.click()
        pg.wait_for_timeout(900)
        msgs = json.dumps(owner.get(f"{BASE}/api/events?deal={D}").json())
        check("2i", "after she looks, the receipt goes and the client hears", "We've received AED 60,000" in msgs)
        pg = desk("ahmed", D)
        pay = pg.locator("#dept-fin .card", has_text="Expect").first
        check("2j", "the balance is what's left", int(float(pay.get_by_label("Amount received (AED)").input_value())) == 140_000)
        pay.get_by_label("Payment reference").fill("ENBD 2")
        clear(pg)
        pay.get_by_role("button", name="Received").click()
        pg.wait_for_timeout(900)
        pg = desk("ahmed", D)
        pay = pg.locator("#dept-fin .card", has_text="Expect").first
        answers.append("Bank reversed it")
        pay.get_by_role("button", name="Undo").last.click()
        pg.wait_for_timeout(900)
        t = next(x for x in view(D)["tasks"] if x["agent"] == "pay")
        check("2k", "undo with a reason reopens it and the log keeps both", t.get("paid") == 60_000 and t["status"] != "done", t.get("paid"))
        pg.screenshot(path=str(OUT / "2-ahmed-money.png"), full_page=True)

    stage("2", money)

    def confidential():
        pg = desk("priya", D)
        card = pg.locator("#dept-comp .card:not(#clearance)", has_text="Screen").first
        card.get_by_label("Screening note").fill(SECRET)
        card.get_by_role("button", name="Possible match").click()
        pg.wait_for_timeout(900)
        pg = desk("priya", D)
        check("3a", "Priya sees the words of the match", SECRET in pg.inner_text("#dept-comp"))
        pg.screenshot(path=str(OUT / "3-priya-hit.png"), full_page=True)
        paths = [f"/api/desk/deals/{D}", "/api/desk/deals", "/api/desk/overview", "/api/desk/board", "/api/desk/work", f"/api/events?deal={D}", f"/api/search?q=4411", "/api/events"]
        for person in (BR, "ahmed", "joseph", "rashid"):
            seen = [x for x in paths if SECRET in who(person)[0].request.get(f"{BASE}{x}").text()]
            check(f"3b {person}", f"{person.capitalize()} can't read it in any list or log", not seen, seen)
            pg = desk(person, D)
            text = pg.inner_text("body")
            check(f"3c {person}", f"{person.capitalize()}'s screen shows status only", SECRET not in text and "Possible match" not in text.replace("Possible match recorded", "") and "possible match" not in text)
            pg.screenshot(path=str(OUT / f"3-{person}-status.png"), full_page=True)
        expected_403[0] = True
        for person, room, ok in ((BR, "compliance", False), ("ahmed", "compliance", False), ("joseph", "compliance", False), ("priya", "compliance", True), ("ahmed", "finance", True), (BR, "finance", False), ("joseph", "finance", False), ("joseph", "operations", True), ("ahmed", "operations", False)):
            s = who(person)[0].request.get(f"{BASE}/api/desk/rooms/{room}").status
            check(f"3d {person} {room}", f"{person.capitalize()} {'opens' if ok else 'cannot open'} the {room} room", (s == 200) == ok, s)
        expected_403[0] = False
        pa = who(BR)[0].request.post(f"{BASE}/api/pa/say", data={"text": f"Is there a screening match on {view(D)['customer']}?", "person": BR, "session": "people-flow"})
        check("3e", "asking the PA doesn't reveal it", SECRET not in pa.text(), pa.status)

    stage("3", confidential)

    def wrong_person():
        expected_403[0] = True
        task = lambda agent: next(t["id"] for t in view(D)["tasks"] if t["agent"] == agent)  # noqa: E731
        pay, scr = task("pay"), task("screen")
        tries = [("hamza" if BR != "hamza" else "omar", f"/api/desk/tasks/{pay}/received", {"reference": "X"}, "a broker marks money"),
                 ("priya", f"/api/desk/tasks/{pay}/received", {"reference": "X"}, "Compliance marks money"),
                 ("joseph", f"/api/desk/tasks/{pay}/received", {"reference": "X"}, "Operations marks money"),
                 ("layla", f"/api/desk/tasks/{pay}/received", {"by": "ahmed", "reference": "X"}, "the owner marks money in Ahmed's name"),
                 ("ahmed", f"/api/desk/deals/{D}/compliance/clear", {"note": "x"}, "Finance clears a deal"),
                 ("layla", f"/api/desk/deals/{D}/compliance/clear", {"by": "priya", "note": "x"}, "the owner clears in Priya's name"),
                 (BR, f"/api/desk/tasks/{scr}/screen", {"result": "clear"}, "a broker records a screening"),
                 (BR, f"/api/desk/tasks/{scr}/hit", {"ok": True, "note": "x"}, "a broker resolves a match"),
                 (BR, f"/api/desk/deals/{D}/transfer/approve", {}, "a broker approves the transfer"),
                 ("priya", f"/api/desk/deals/{D}/formf", {}, "Compliance prepares Form F"),
                 ("ahmed", f"/api/desk/deals/{D}/formf", {}, "Finance prepares Form F"),
                 (OTHER, f"/api/desk/deals/{D}/formf", {}, "another broker prepares Form F"),
                 ("ahmed", f"/api/desk/rules", {"rules": {}}, "Finance changes the rules"),
                 ("joseph", f"/api/desk/roles", {"role": "finance", "person": "joseph"}, "Operations takes a role"),
                 ("maya", f"/api/desk/deals/{D}", None, "Marketing reads a deal"),
                 ("maya", f"/api/desk/tasks/{pay}/received", {"reference": "X"}, "Marketing marks money")]
        for i, (person, path, body, name_) in enumerate(tries):
            r = who(person)[0].request
            res = r.get(f"{BASE}{path}") if body is None else r.post(f"{BASE}{path}", data=body)
            check(f"4{chr(97 + i)}", f"refused: {name_}", res.status in (401, 403), f"{res.status} {res.text()[:90]}")
        expected_403[0] = False
        check("4z", "none of that left a mark", not next(t for t in view(D)["tasks"] if t["agent"] == "screen").get("result") == "clear" and view(D)["compliance"]["state"] != "cleared")
        expected_403[0] = True
        pg = who("maya")[1]
        pg.goto(f"{BASE}/web/deal.html")
        pg.wait_for_timeout(1000)
        check("4y", "Marketing is sent away from the Deal desk", "deal.html" not in pg.url, pg.url)
        expected_403[0] = False

    stage("4", wrong_person)

    def owner_side():
        pg = desk("layla", D)
        check("5a", "Layla sees the words of the match", SECRET in pg.inner_text("#dept-comp"))
        check("5b", "Layla has no clear button on Priya's behalf", pg.locator("#clearance").get_by_role("button", name="Clear this deal").count() == 0)
        pg.goto(f"{BASE}/web/lobby.html")
        pg.wait_for_selector("h1:has-text('Lobby')")
        check("5c", "the Lobby opens for the owner", pg.get_by_role("button", name="Write this week's threads now").count() == 1)
        r = who("rashid")[0].request.post(f"{BASE}/api/lobby-room/propose", data={"by": "rashid", "draft": {"kind": "followup", "title": "Ask if they're still looking", "text": "Hi {name}, are you still looking?", "metric": "reply_rate", "days": 7}})
        check("5d", "Rashid proposes signed in", r.ok, r.text()[:90])
        expected_403[0] = True
        for person in ("omar", "priya"):
            s = who(person)[0].request.post(f"{BASE}/api/lobby-room/propose", data={"by": person, "draft": {"kind": "followup", "title": "x", "text": "y", "metric": "reply_rate", "days": 7}}).status
            check(f"5e {person}", f"{person.capitalize()} can read the Lobby but not propose", s == 403, s)
        expected_403[0] = False
        pg2 = who("ahmed")[1]
        pg2.goto(f"{BASE}/web/lobby.html")
        pg2.wait_for_selector("h3:has-text('still looking')")
        check("5f", "Ahmed reads it with no decision buttons", pg2.get_by_role("button", name="Approve", exact=True).count() == 0)
        pg.reload()
        pg.wait_for_selector("h3:has-text('still looking')")
        pg.get_by_role("button", name="Approve", exact=True).first.click()
        pg.wait_for_selector("h2:has-text('Running') >> .n")
        check("5g", "the owner approves signed in", True)

    stage("5", owner_side)

    def typing():
        phone = "971507772009"
        owner.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": "Hi, I want to rent in JLT", "name": "Dalia Fictional"})
        br = owner.get(f"{BASE}/api/desk/deals?q=Dalia").json()["rows"][0]["broker"]
        pg = who(br)[1]
        pg.bring_to_front()
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}")
        pg.wait_for_selector("#box")
        pg.locator("#box").click()
        pg.keyboard.type("Hi Dalia, I'm checking what")
        owner.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": "Also, is parking included?", "name": "Dalia Fictional"})
        pg.wait_for_timeout(2500)
        check("6a", "a new message doesn't wipe what the broker is typing", pg.input_value("#box") == "Hi Dalia, I'm checking what", pg.input_value("#box"))
        pg.keyboard.type(" we have")
        check("6b", "they can carry on typing", pg.input_value("#box") == "Hi Dalia, I'm checking what we have", pg.input_value("#box"))

    stage("6", typing)
    b.close()

bad = [r for r in results if not r[2]]
print(f"\n{len(results) - len(bad)}/{len(results)} passed; errors: {errors[:6]}")
for r in bad:
    print("FAILED", r[0], r[1])
sys.exit(1 if bad or errors else 0)
