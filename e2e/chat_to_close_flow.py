"""A real chat all the way to a closed deal, in a window you can watch (WATCH=1). A client writes on WhatsApp, the broker
converts the chat with an amount, and every room does its part, with what goes wrong along the way: a discount refused, a
possible match, blurred and wrong uploads, a selfie, a proof that disagrees, a stranger paying, an undo. A second chat is
blocked, a third is lost. Run on a scratch server, never diwan.db:
WATCH=1 python e2e/chat_to_close_flow.py http://127.0.0.1:8062 <out dir>
AUTH=1: the same run with sign-in on, each person in a browser of their own, on a server whose passwords are all PASSWORD."""
import io
import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8062"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "chat"
OUT.mkdir(parents=True, exist_ok=True)
WATCH = bool(os.environ.get("WATCH"))
AUTH = os.environ.get("AUTH") == "1"
PASSWORD = "a good password"
PHONE, NAME = "971507771001", "Layth Mansour"
errors, results = [], []
BANNER = """(t) => { let b = document.getElementById('__step'); if (!b) { b = document.createElement('div'); b.id = '__step';
  b.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);bottom:14px;z-index:99999;background:#e8c77a;color:#14110a;font:600 16px system-ui;padding:10px 18px;border-radius:12px;box-shadow:0 8px 30px #0009;max-width:90vw';
  document.body.append(b); } b.textContent = t; }"""


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n} {name}{' · ' + str(note)[:170] if note else ''}", flush=True)


def card_image(seed):
    r = random.Random(seed)
    im = Image.new("RGB", (1000, 630), (214, 219, 226))
    d = ImageDraw.Draw(im)
    for y in range(40, 600, 26):
        d.rectangle([60, y, 60 + r.randrange(200, 800), y + 12], fill=(r.randrange(20, 90), 40, 70))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=92)
    return b.getvalue()


def blurred():
    from PIL import ImageFilter
    im = Image.open(io.BytesIO(card_image(7))).filter(ImageFilter.GaussianBlur(9))
    b = io.BytesIO()
    im.save(b, "JPEG")
    return b.getvalue()


def selfie():
    r = random.Random(3)
    im = Image.new("RGB", (600, 800), (200, 170, 150))
    d = ImageDraw.Draw(im)
    for _ in range(4000):
        x, y = r.randrange(600), r.randrange(800)
        d.ellipse([x, y, x + 30, y + 30], fill=(r.randrange(90, 230), r.randrange(60, 170), r.randrange(40, 140)))
    b = io.BytesIO()
    im.save(b, "JPEG")
    return b.getvalue()


with sync_playwright() as p:
    b = p.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "msedge"), headless=not WATCH, slow_mo=220 if WATCH else 0, args=["--window-position=0,0"])
    answers = []
    people = {}

    def on_dialog(d):
        if d.type == "prompt":
            d.accept(answers.pop(0) if answers else "A reason")
        elif answers:
            d.accept() if answers.pop(0) else d.dismiss()
        else:
            d.accept()

    def person(who):
        """Their own browser: signed in as them, or the one shared window when sign-in is off."""
        key = who if AUTH else "all"
        if key not in people:
            c = b.new_context(viewport={"width": 1400, "height": 900})
            if AUTH:
                r = c.request.post(f"{BASE}/api/auth/login", data={"person": who, "password": PASSWORD})
                assert r.ok, r.text()
            page = c.new_page()
            page.on("pageerror", lambda e, w=who: errors.append(f"{w}: {e}"))
            page.on("response", lambda r, w=who: errors.append(f"{w}: {r.status} {r.url}") if r.status >= 500 or (AUTH and r.status == 403) else None)
            page.on("dialog", on_dialog)
            page.set_default_timeout(12000)
            people[key] = (c, page)
        return people[key]

    def be(who):
        global pg
        pg = person(who)[1]
        pg.bring_to_front()

    be("layla")
    api = person("layla")[0].request
    GOING_ON = os.environ.get("CONTINUE") == "1"  # the case study brought this client this far through the real journey
    if not GOING_ON:
        api.post(f"{BASE}/api/demo/reset")
    step_text = ""

    def say(t):
        global step_text
        step_text = t
        print(f"\n--- {t}", flush=True)
        try:
            pg.evaluate(BANNER, t)
        except Exception:
            pass
        pg.wait_for_timeout(900 if WATCH else 0)

    def shot(n):
        pg.screenshot(path=str(OUT / f"{n}.png"), full_page=True)

    def toast():
        t = pg.locator(".toast").last
        t.wait_for(timeout=6000)
        return t.inner_text()

    def clear():
        pg.evaluate("document.querySelectorAll('.toast').forEach((t) => t.remove())")

    def client(text, phone=PHONE, name=NAME):
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": text, "name": name})

    def deal_of(name=NAME):
        rows = api.get(f"{BASE}/api/desk/deals?q={name.split()[0]}").json()["rows"]
        return rows[0]["deal"] if rows else None

    def view(deal=None):
        return api.get(f"{BASE}/api/desk/deals/{deal or D}").json()

    def desk(who, deal=None):
        be(who)
        pg.goto(f"{BASE}/web/deal.html?deal={deal or D}")
        pg.wait_for_selector("#dept-comp")
        if not AUTH:
            pg.select_option("#as", who)
        pg.wait_for_timeout(600)
        pg.evaluate(BANNER, f"{step_text}  ·  acting as {who.capitalize()}")

    def stage(name, fn):
        """A stage that breaks is reported and the run goes on, so one fault doesn't hide the rest."""
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            check(name, f"stage stopped: {step_text}", False, str(e).split("\n")[0])
            shot(f"broke-{name}")

    D = None

    def chat():
        global D
        if GOING_ON:
            D = deal_of()
            check("1a", "the same client carries on", bool(D), D)
            be(view()["broker"])
            pg.goto(f"{BASE}/web/inbox.html?chat={PHONE}&as={view()['broker']}", timeout=40000)
            pg.wait_for_selector(".thread .b")
            return
        say("A client writes on WhatsApp")
        pg.goto(f"{BASE}/web/inbox.html?as=layla")
        pg.wait_for_timeout(800)
        for m in ("Hi, I'm looking to buy a villa in JVC", "Buying, to live in", "A 4 bed villa", "Budget is about 2 million", "Cash", "Within the next month"):
            client(m)
            pg.wait_for_timeout(350)
        D = deal_of()
        check("1a", "the chat became a lead with one record", bool(D), D)
        v = view()
        be(v["broker"])
        pg.goto(f"{BASE}/web/inbox.html?chat={PHONE}&as={v['broker']}")
        pg.wait_for_selector(".thread .b")
        say("The broker opens the chat")
        n = pg.locator(".thread .b").count()
        check("1b", "the conversation shows in the Inbox", n >= 6, f"{n} messages")
        shot("1-chat")

    stage("1", chat)

    def convert():
        v = view()
        broker = v["broker"]
        say("Convert the chat: a discount above the limit waits for the owner")
        pg.get_by_role("button", name="Convert").first.click()
        pg.wait_for_selector("#convert")
        box = pg.locator("#convert")
        box.get_by_role("radio", name="Our listing").check()
        box.get_by_label("Search our listings").fill("Villa 88")
        pg.wait_for_timeout(900)
        r = pg.locator("#propresults button", has_text="Villa 88").first
        label = r.inner_text()
        r.click()
        pg.wait_for_timeout(500)
        amount = box.get_by_label("Agreed price (AED)")
        listed = int(float(amount.input_value() or 0))
        check("2a", "picking the listing fills its price, not the client's budget", f"{listed:,}" in label, label)
        amount.fill(str(round(listed * 0.9)))
        pg.wait_for_timeout(500)
        check("2b", "the discount shows before saving", "Discount" in box.inner_text())
        shot("2-convert-box")
        clear()
        box.get_by_role("button", name="Save and convert").click()
        check("2c", "the owner must approve it", "approve" in toast().lower())
        say("The owner refuses the discount")
        pg.wait_for_timeout(600)
        desk("layla")
        pg.locator("#stagebar").get_by_label("Why", exact=True).fill("Too low for this villa")
        pg.locator("#stagebar").get_by_role("button", name="Refuse").click()
        pg.wait_for_timeout(800)
        check("2d", "nothing converted", not view()["stages"]["agreed"])
        say("The broker converts at the agreed amount")
        be(broker)
        pg.goto(f"{BASE}/web/deal.html?deal={D}&as={broker}&convert=1")
        pg.wait_for_selector("#convert")
        box = pg.locator("#convert")
        box.get_by_role("radio", name="Our listing").check()
        box.get_by_label("Search our listings").fill("Villa 88")
        pg.wait_for_timeout(900)
        pg.locator("#propresults button", has_text="Villa 88").first.click()
        pg.wait_for_timeout(400)
        box.get_by_label("Agreed price (AED)").fill(str(listed))
        clear()
        box.get_by_role("button", name="Save and convert").click()
        toast()
        pg.wait_for_timeout(900)
        v = view()
        check("2e", "converted at the amount, with the property", v["stages"]["agreed"] and v["stages"]["agreed"]["amount"] == listed and "Villa 88" in v["property"], v["property"])
        evs = api.get(f"{BASE}/api/events?deal={D}").json()
        check("2f", "case.converted carries the facts", any(e["type"] == "case.converted" and e["content"]["facts"] for e in evs))
        check("2g", "Finance expects the deposit, with no words from the client needed", any(t["agent"] == "pay" and t["status"] == "queued" for t in v["tasks"]), [t["action"] for t in v["tasks"] if t["agent"] == "pay"])
        check("2h", "documents are asked for at once", bool(v["documents"]["requests"]) or bool(v["agency"]["asking"]))
        shot("3-converted")
        pg.goto(f"{BASE}/web/inbox.html?chat={PHONE}&as={broker}")
        pg.wait_for_selector("#converted")
        check("2i", "the Inbox shows the big Converted card", f"{listed:,}" in pg.inner_text("#converted"))
        shot("4-inbox-converted")
        pg.wait_for_timeout(1500 if WATCH else 0)

    stage("2", convert)

    def setup():
        say("The broker records how the deal is paid and who the seller is")
        v = view()
        desk(v["broker"])
        if pg.locator("#savesides").count():
            pg.locator("#savesides").click()
            pg.wait_for_timeout(800)
            desk(v["broker"])
        t = pg.locator("#terms")
        t.get_by_label("How the buyer pays").select_option("cash")
        t.get_by_label("The seller has a mortgage").select_option("false")
        t.get_by_label("The seller's name").fill("Huda Al Mansoori")
        t.get_by_label("Unit number, as on the title deed").fill("88")
        t.locator("#saveterms").click()
        pg.wait_for_timeout(900)
        v = view()
        check("3a", "the forms are drafted", [f["form"] for f in v["agency"]["forms"]], [f["form"] for f in v["agency"]["forms"]])
        check("3b", "the seller's link uses their name", any(r["name"] == "Huda Al Mansoori" for r in v["documents"]["requests"]), [r["name"] for r in v["documents"]["requests"]])
        say("Joseph prepares Form F; its signatures wait for Compliance")
        desk("joseph")
        pg.locator("#dept-ops").get_by_role("button", name="Prepare Form F").click()
        pg.wait_for_timeout(900)
        check("3c", "Form F waits for Compliance", "wait for Compliance" in pg.locator("#formf").inner_text())
        check("3d", "the gates show on the deal", "COMPLIANCE" in pg.locator("#gates").inner_text().upper())
        shot("5-gates")

    stage("3", setup)

    phone = b.new_context(viewport={"width": 390, "height": 760}, has_touch=True)
    cp = phone.new_page()
    cp.on("pageerror", lambda e: errors.append(str(e)))

    def documents():
        say("The client sends documents from a phone: a blurry one is refused")
        r = next(x for x in view()["documents"]["requests"] if x["party"] == "buyer")
        cp.goto(r["url"].replace("http://testserver", BASE))
        cp.wait_for_selector("section[data-kind]")
        sec = cp.locator("section[data-kind=eid_front]")
        fields = {"number": "784-1990-1234567-6", "name": NAME, "expiry": "2031-01-01"}
        for k, x in fields.items():
            sec.locator(f"[data-f={k}]").fill(x)
        sec.locator("input[type=file]").set_input_files({"name": "id.jpg", "mimeType": "image/jpeg", "buffer": blurred()})
        sec.get_by_role("button", name="Send").click()
        sec.locator(".err:not([hidden])").wait_for(timeout=6000)
        check("4a", "a blurry photo is turned away with the reason", "blurry" in sec.inner_text().lower(), sec.locator(".err").inner_text())
        for k, x in fields.items():
            sec.locator(f"[data-f={k}]").fill(x)
        sec.locator("input[type=file]").set_input_files({"name": "id.jpg", "mimeType": "image/jpeg", "buffer": card_image(1)})
        sec.get_by_role("button", name="Send").click()
        cp.wait_for_selector("section[data-kind=eid_front] .st.ok", timeout=8000)
        check("4b", "a clear one is received", True)
        for i, x in enumerate(view()["documents"]["requests"]):
            tok = x["url"].split("t=")[1]
            for j, d in enumerate(x["docs"]):
                if d["status"] != "needed":
                    continue
                f = {"eid_front": {"number": "784-1990-1234567-6", "name": x["name"], "expiry": "2031-01-01"}, "passport": {"number": f"P{i}", "expiry": "2031-01-01"},
                     "visa": {"expiry": "2029-01-01"}, "title_deed": {"number": "TD-1", "unit": "1204"}}.get(d["kind"], {})
                got = api.post(f"{BASE}/api/docs/{tok}", multipart={"kind": d["kind"], "fields": json.dumps(f), "file": {"name": "c.jpg", "mimeType": "image/jpeg", "buffer": card_image(i * 10 + j + 2)}})
                if d["kind"] == "title_deed":
                    check("4c", "a deed with the wrong unit is refused", got.status == 400 and "doesn't match" in got.text(), got.text()[:120])
                    f["unit"] = "88"
                    got = api.post(f"{BASE}/api/docs/{tok}", multipart={"kind": d["kind"], "fields": json.dumps(f), "file": {"name": "c.jpg", "mimeType": "image/jpeg", "buffer": card_image(i * 10 + j + 2)}})
                    check("4d", "the right deed passes", got.ok, got.text()[:100])

    stage("4", documents)

    def compliance():
        say("Priya: too early to clear, she sees what's left")
        desk("priya")
        c = pg.locator("#clearance")
        clear()
        c.get_by_role("button", name="Clear this deal").click()
        check("5a", "clearing early is refused with what's left", "Not yet" in toast())
        shot("6-blockers")
        say("A possible match holds the deal until she resolves it")
        card = pg.locator("#dept-comp .card:not(#clearance)", has_text=f"Screen {NAME}")
        card.get_by_label("Screening note").fill("UN list, entry 4411")
        card.get_by_role("button", name="Possible match").click()
        pg.wait_for_timeout(800)
        desk("priya")
        card = pg.locator("#dept-comp .card:not(#clearance)", has_text=f"Screen {NAME}")
        check("5b", "the hit holds the deal", "holds the deal" in card.inner_text())
        card.get_by_label("How it was decided").fill("Different date of birth")
        card.get_by_role("button", name="False positive").click()
        pg.wait_for_timeout(800)
        say("She compares each document with what was typed")
        desk("priya")
        n = 0
        while pg.get_by_role("button", name="It matches").count() and n < 16:
            pg.get_by_role("button", name="It matches").first.click()
            pg.wait_for_timeout(500)
            n += 1
        check("5c", "each document confirmed", n >= 5, n)
        desk("priya")
        for card_ in view()["cards"]:
            if card_["status"] == "open" and card_["can"] == "answer":
                person(card_["who"])[0].request.post(f"{BASE}/api/desk/cards/{card_['id']}/answer", data={"by": card_["who"], "choice": "Answered", "note": "Own savings, from the sale of a flat"})
            if card_["status"] == "open" and card_["can"] == "reviewed":
                person("priya")[0].request.post(f"{BASE}/api/desk/cards/{card_['id']}/answer", data={"by": "priya", "choice": "Reviewed"})
        desk("priya")
        c = pg.locator("#clearance")
        c.get_by_label("Risk", exact=True).select_option("low")
        c.get_by_role("button", name="Rate").click()
        pg.wait_for_timeout(700)
        desk("priya")
        c = pg.locator("#clearance")
        print("  blockers:", view()["compliance"]["blockers"], flush=True)
        c.get_by_label("Clearance note").fill("Bank letter seen in person")
        c.get_by_role("button", name="Clear this deal").click()
        pg.wait_for_timeout(900)
        s = view()["compliance"]
        check("5d", "cleared on the current facts", s["ok"], s.get("reason"))
        shot("7-cleared")

    stage("5", compliance)

    def draw(page, strokes):
        box = page.locator("#pad").bounding_box()
        for s in range(strokes):
            page.mouse.move(box["x"] + 30 + s * 60, box["y"] + 40)
            page.mouse.down()
            for k in range(1, 7):
                page.mouse.move(box["x"] + 30 + s * 60 + k * 18, box["y"] + 40 + (k % 2) * 60)
            page.mouse.up()

    def signing():
        say("Omar sends Form F; the client signs on a phone: a selfie is refused")
        global cp
        cp = b.new_context(viewport={"width": 390, "height": 760}, has_touch=True).new_page()  # a phone of their own for signing
        cp.on("pageerror", lambda e: errors.append(str(e)))
        v = view()
        desk(v["broker"])
        pg.locator("#formf").get_by_role("button", name="Make the signing links").click()
        pg.wait_for_timeout(900)
        links = view()["agency"]["formf"][-1]["links"]
        buyer = next(x for x in links if x["signer"] == "buyer")
        cp.goto(buyer["url"].replace("http://testserver", BASE))
        cp.wait_for_selector("#pad")
        cp.fill("#name", NAME)
        cp.fill("#id", "784-1990-1234567-6")
        cp.check("#consent")
        cp.click("#tabphoto")
        cp.set_input_files("#img", {"name": "me.jpg", "mimeType": "image/jpeg", "buffer": selfie()})
        cp.click("#sign")
        cp.wait_for_selector("#err:not([hidden])")
        check("6a", "a selfie is refused", "photo of a person" in cp.inner_text("#err"), cp.inner_text("#err"))
        cp.click("#tabdraw")
        cp.wait_for_timeout(300)
        draw(cp, 3)
        cp.click("#sign")
        cp.wait_for_selector(".msg.ok", timeout=8000)
        check("6b", "a drawn signature is accepted", True)
        for x in links:
            if x["signer"] != "buyer":
                cp.goto(x["url"].replace("http://testserver", BASE))
                cp.wait_for_selector("#pad")
                cp.fill("#name", "Huda Al Mansoori" if x["signer"] == "seller" else "Omar Saeed")
                cp.fill("#id", "ID-1")
                cp.check("#consent")
                draw(cp, 3)
                cp.click("#sign")
                cp.wait_for_selector(".msg.ok", timeout=8000)
        say("Forms A and B come back signed")
        desk(v["broker"])
        for f in view()["agency"]["forms"]:
            if f["waiting"]:
                file = pg.get_by_label(f"Signed Form {f['form']} (PDF)")
                real = api.get(f"{BASE}/api/desk/forms/{f['draft']}.pdf").body()  # what comes back from the printer: a real PDF
                file.set_input_files({"name": "s.pdf", "mimeType": "application/pdf", "buffer": real})
                pg.locator("#agency .card", has_text=f"v{f['version']}").filter(has=file).get_by_role("button", name="Upload the signed copy").click()
                pg.wait_for_timeout(800)
        g = {x["key"]: x for x in view()["gates"]["gates"]}
        check("6c", "the paperwork gate passes", g["paperwork"]["ok"], g["paperwork"]["note"])

    stage("6", signing)

    def operations():
        say("Joseph submits Form F; a cash deal has no mortgage steps")
        desk("joseph")
        card = pg.locator("#dept-ops .card", has_text="Submit Form F").last
        card.locator("input").fill("DLD-1001")
        card.get_by_role("button", name="I submitted it").click()
        pg.wait_for_timeout(900)
        names = [t["action"] for t in view()["tasks"] if t["agent"] == "transfer"]
        check("7a", "no mortgage steps on a cash deal", names and not any("mortgage" in x.lower() for x in names), names)
        say("The NOC: Diwan lists what to type; Joseph submits it himself")
        desk("joseph")
        noc = pg.locator("#dept-ops .card", has_text="Developer NOC")
        noc.get_by_role("button", name="Draft for the").click()
        pg.wait_for_timeout(800)
        desk("joseph")
        noc = pg.locator("#dept-ops .card", has_text="Developer NOC")
        check("7b", "the draft comes from the record", NAME in noc.inner_text())
        noc.get_by_label("Portal reference").fill("NOC-77")
        noc.get_by_role("button", name="I submitted it").click()
        pg.wait_for_timeout(800)
        desk("joseph")
        pg.locator("#dept-ops .card", has_text="Manager's cheques").get_by_role("button", name="Done").click()
        pg.wait_for_timeout(800)
        say("The trustee can't be booked before the gates pass")
        desk("joseph")
        bk = pg.locator("#dept-ops .card", has_text="Trustee office appointment")
        bk.get_by_label("Appointment date and time").fill((date.today() + timedelta(days=5)).isoformat() + "T10:00")
        bk.get_by_label("Trustee office").fill("Trustee Marina")
        clear()
        bk.get_by_role("button", name="Book the transfer").click()
        check("7c", "refused until ready for transfer", "ready-for-transfer" in toast())

    stage("7", operations)

    def money():
        say("Ahmed marks the deposit: a proof that disagrees is flagged")
        desk("ahmed")
        pay = pg.locator("#dept-fin .card", has_text="Expect")
        deposit = int(float(pay.get_by_label("Amount received (AED)").input_value()))
        check("8a", "the deposit is the owner's 10%", deposit == round(view()["stages"]["agreed"]["amount"] * .1), deposit)
        pay.get_by_label("Amount received (AED)").fill(str(deposit // 2))
        pay.get_by_label("Amount on the proof").fill("1000")
        pay.get_by_label("Payment reference").fill("ENBD 1")
        answers.append(False)
        clear()
        pay.get_by_role("button", name="Received").click()
        check("8b", "the mismatch is flagged and nothing saved", "Proof shows" in toast())
        say("A stranger pays half: it goes to Compliance before any receipt")
        pay.get_by_label("Amount on the proof").fill("")
        pay.get_by_label("Paid by").fill("Hassan Ali")
        clear()
        pay.get_by_role("button", name="Received").click()
        check("8c", "a third party goes to Compliance first", "With Compliance" in toast())
        pg.wait_for_timeout(900)
        say("Ahmed undoes a mistaken mark, with a reason")
        desk("ahmed")
        pay = pg.locator("#dept-fin .card", has_text="Expect")
        check("8d", "the balance stays open", int(float(pay.get_by_label("Amount received (AED)").input_value())) == deposit - deposit // 2)
        pay.get_by_label("Payment reference").fill("ENBD 2")
        pay.get_by_label("Amount received (AED)").fill("1000")
        pay.get_by_role("button", name="Received").click()
        pg.wait_for_timeout(900)
        desk("ahmed")
        pay = pg.locator("#dept-fin .card", has_text="Expect")
        answers.append("Typed the wrong amount")
        pay.get_by_role("button", name="Undo").last.click()
        pg.wait_for_timeout(900)
        v = view()
        t = next(x for x in v["tasks"] if x["agent"] == "pay")
        check("8e", "the mark is undone and the log keeps it", (t.get("paid") or 0) == deposit // 2, t.get("paid"))
        say("The rest arrives; Priya looks at the stranger's payment")
        desk("ahmed")
        pay = pg.locator("#dept-fin .card", has_text="Expect")
        pay.get_by_label("Payment reference").fill("ENBD 3")
        pay.get_by_role("button", name="Received").click()
        pg.wait_for_timeout(900)
        desk("priya")
        n = 0
        while pg.locator("#dept-comp").get_by_role("button", name="Reviewed").count() and n < 6:
            pg.locator("#dept-comp").get_by_role("button", name="Reviewed").first.click()
            pg.wait_for_timeout(600)
            n += 1
        g = {x["key"]: x for x in view()["gates"]["gates"]}
        check("8f", "the deposit counts once she has looked", g["finance"]["ok"], g["finance"]["note"])
        be("ahmed")
        pg.goto(f"{BASE}/web/deal.html#finance")
        pg.wait_for_selector("#cashin")
        check("8g", "the Finance room counts the cash", f"{deposit:,}" in pg.inner_text("#cashin"), pg.inner_text("#cashin"))
        shot("8-finance-room")

    stage("8", money)

    def transfer():
        say("Layla approves on the current facts")
        if not view()["compliance"]["ok"]:
            desk("priya")
            c = pg.locator("#clearance")
            c.get_by_label("Clearance note").fill("Looked at the payments")
            c.get_by_role("button", name="Clear this deal").click()
            pg.wait_for_timeout(800)
        desk("layla")
        g = view()["gates"]
        check("9a", "every other gate has passed", g["can_approve"], [x["note"] for x in g["gates"] if not x["ok"]])
        shot("9-gates")
        pg.locator("#approvegate").click()
        pg.wait_for_timeout(900)
        check("9b", "ready for transfer", view()["gates"]["ready"])
        say("Joseph books the trustee; the client hears what to bring")
        desk("joseph")
        bk = pg.locator("#dept-ops .card", has_text="Trustee office appointment")
        bk.get_by_label("Appointment date and time").fill((date.today() + timedelta(days=5)).isoformat() + "T10:00")
        bk.get_by_label("Trustee office").fill("Trustee Marina")
        bk.get_by_role("button", name="Book the transfer").click()
        pg.wait_for_timeout(900)
        say("The title deed is issued: a person marks it")
        desk("joseph")
        pg.locator("#dept-ops .card", has_text="Title deed issued").get_by_role("button", name="Done").click()
        pg.wait_for_timeout(900)
        desk("joseph")
        pg.locator("#dept-ops .card", has_text="Handover").get_by_role("button", name="Done").click()
        pg.wait_for_timeout(900)
        v = view()
        check("9c", "the invoice drafted itself at the transfer", any(d["kind"] == "commission invoice" for d in v["drafts"]))

    stage("9", transfer)

    def closing():
        say("Ahmed sends the invoice and collects it in two parts")
        desk("ahmed")
        inv = pg.locator("#dept-fin .card", has_text="Send commission invoice")
        inv.get_by_role("button", name="I sent it").click()
        pg.wait_for_timeout(900)
        desk("ahmed")
        col = pg.locator("#dept-fin .card", has_text="Collect commission")
        check("10a", "the invoice has a due date", "Due " in col.inner_text())
        col.get_by_label("Bank reference").fill("ENBD 9")
        col.get_by_role("button", name="Received").click()
        pg.wait_for_timeout(900)
        desk("ahmed")
        pay = pg.locator("#dept-fin .card", has_text="their commission")
        check("10b", "the broker's commission goes on the payout list", pay.count() == 1)
        pay.get_by_label("Bank reference").fill("ENBD 10")
        pay.get_by_role("button", name="Paid").click()
        pg.wait_for_timeout(900)
        say("The broker confirms the figures; Joseph files and closes")
        v = view()
        desk(v["broker"])
        pg.locator("#closing").get_by_role("button", name="Confirm the final figures").click()
        pg.wait_for_timeout(800)
        desk("joseph")
        pg.locator("#closing").get_by_role("button", name="Documents filed").click()
        pg.wait_for_timeout(800)
        desk("joseph")
        print("  closing left:", [i["text"] for i in view()["closing"]["items"] if not i["done"]], flush=True)
        pg.locator("#closing").get_by_role("button", name="Close the deal").click()
        pg.wait_for_timeout(1000)
        v = view()
        check("10c", "the deal closes and goes to Records", v["closing"]["sale"] and v["stage"] == "Won", v["closing"]["sale"])
        evs = {e["type"] for e in api.get(f"{BASE}/api/events?deal={D}").json()}
        want = {"case.converted", "compliance.cleared", "payment.marked_received", "payment.undone", "deal.ready_for_transfer", "transfer.booked", "transfer.completed", "case.closed"}
        check("10d", "the whole loop is on the log", want <= evs, want - evs)
        shot("10-closed")
        be(v["broker"])
        pg.goto(f"{BASE}/web/inbox.html?chat={PHONE}&as={v['broker']}")
        pg.wait_for_selector(".thread .b")
        t = pg.locator(".thread").inner_text()
        for n, w, name in (("10e", "We've received", "the client got the receipt"), ("10f", "Trustee Marina", "the client was told where and what to bring"), ("10g", "Congratulations", "the client heard the transfer is done")):
            check(n, name, w in t)
        low = t.lower()
        check("10h", "the client never hears about a check", not any(w in low for w in ("screening", "possible match", "compliance")))
        shot("11-client-thread")
        pg.wait_for_timeout(2000 if WATCH else 0)

    stage("10", closing)

    def other_chats():
        say("A second chat: Compliance blocks it, and nothing binding can happen")
        for m in ("Hi, I want to buy a flat in Dubai Marina", "Budget is 2 million"):
            client(m, "971507771002", "Rima Saleh")
            pg.wait_for_timeout(300)
        d2 = deal_of("Rima Saleh")
        r = person(view(d2)["broker"])[0].request.post(f"{BASE}/api/desk/deals/{d2}/convert", data={"by": view(d2)["broker"], "amount": 1500000, "property": {"source": "agency", "label": "Unit 901, Marina Crest", "other_agency": "Bayut Homes", "other_share_pct": 50}})
        check("11a", "the second chat converts", r.ok, r.text()[:100])
        desk("priya", d2)
        c = pg.locator("#clearance")
        c.get_by_label("Clearance note").fill("Screening match confirmed by the officer")
        c.get_by_role("button", name="Block it").click()
        pg.wait_for_timeout(900)
        v = view(d2)
        check("11b", "the deal is blocked and the owner told", v["compliance"]["state"] == "blocked" and any(c_["who"] == "layla" and c_["status"] == "open" for c_ in v["cards"]))
        shot("12-blocked")
        say("A third chat: the broker marks it lost, with a reason")
        client("Hi, I'm looking to rent a flat in JLT", "971507771003", "Omar Stranger")
        pg.wait_for_timeout(400)
        d3 = deal_of("Omar Stranger")
        v = view(d3)
        desk(v["broker"], d3)
        pg.get_by_role("button", name="Mark lost").click()
        pg.wait_for_timeout(500)
        pg.get_by_label("Why it was lost").select_option("Found elsewhere")
        pg.locator("#stagebar .acts").get_by_role("button", name="Mark lost").click()
        pg.wait_for_timeout(900)
        check("11c", "lost, with its reason on the log", any(e["type"] == "case.lost" and "Found elsewhere" in e["content"]["reason"] for e in api.get(f"{BASE}/api/events?deal={d3}").json()))

    stage("11", other_chats)

    def rooms():
        say("Every room, one last look")
        be("layla")
        for room in ("compliance", "finance", "operations", "board", "deals", "my-work"):
            pg.goto(f"{BASE}/web/deal.html#{room}")
            pg.wait_for_timeout(1500 if WATCH else 700)
            check(f"12-{room}", f"the {room} view loads", "didn't load" not in pg.inner_text("#view"))
        check("12z", "no page or server errors in the whole run", not errors, errors[:3])

    stage("12", rooms)
    say(f"Finished: {sum(r[2] for r in results)} of {len(results)} checks passed")
    pg.wait_for_timeout(6000 if WATCH else 0)
    b.close()

bad = [r for r in results if not r[2]]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
for r in bad:
    print("FAILED", r[0], r[1])
sys.exit(1 if bad else 0)
