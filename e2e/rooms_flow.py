"""One deal through the four rooms, as the people would do it (docs/deal-desk.md item 18). Run on a scratch server, never diwan.db:
python e2e/rooms_flow.py http://127.0.0.1:8050 <out dir>"""
import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8050"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "rooms"
OUT.mkdir(parents=True, exist_ok=True)
M = "marina-1204"
errors, results = [], []


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n} {name}{' · ' + str(note)[:150] if note else ''}")


def card_image(seed):
    r = random.Random(seed)
    im = Image.new("RGB", (1000, 630), (214, 219, 226))
    d = ImageDraw.Draw(im)
    for y in range(40, 600, 26):
        d.rectangle([60, y, 60 + r.randrange(200, 800), y + 12], fill=(r.randrange(20, 90), 40, 70))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=92)
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


def luhn_id(body="78419901234567"):
    def ok(ds):
        s = 0
        for i, ch in enumerate(reversed(ds)):
            n = int(ch) * (2 if i % 2 else 1)
            s += n - 9 if n > 9 else n
        return s % 10 == 0
    c = next(str(x) for x in range(10) if ok(body + str(x)))
    return f"{body[:3]}-{body[3:7]}-{body[7:14]}-{c}"


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(str(e)))
    answers = []  # what each browser dialog should answer, in order
    def on_dialog(d):
        if d.type == "prompt":
            d.accept(answers.pop(0) if answers else "A reason")
        elif answers:
            d.accept() if answers.pop(0) else d.dismiss()
        else:
            d.accept()
    pg.on("dialog", on_dialog)
    api = ctx.request
    api.post(f"{BASE}/api/demo/reset")

    def shot(name):
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)

    def clear():
        pg.evaluate("document.querySelectorAll('.toast').forEach((t) => t.remove())")

    def toast():
        t = pg.locator(".toast").last
        t.wait_for(timeout=5000)
        return t.inner_text()

    def desk(who, deal=M):
        pg.goto(f"{BASE}/web/deal.html?deal={deal}")
        pg.wait_for_selector("#dept-comp")
        pg.select_option("#as", who)
        pg.wait_for_timeout(500)

    def view():
        return api.get(f"{BASE}/api/desk/deals/{M}").json()

    # the broker converts; the forms and the client's links appear
    r = api.post(f"{BASE}/api/desk/deals/{M}/terms", data={"by": "omar", "terms": {"finance": "cash", "seller_mortgage": False, "other_party": "Huda Al Mansoori", "unit": "1204"}})
    api.post(f"{BASE}/api/desk/deals/{M}/convert", data={"by": "omar", "amount": 2_600_000})
    api.post(f"{BASE}/api/desk/deals/{M}/sides", data={"by": "omar", "sides": "both"})
    desk("joseph")
    pg.locator("#dept-ops").get_by_role("button", name="Prepare Form F").click()
    pg.wait_for_timeout(700)
    t = pg.locator("#gates").inner_text()
    shot("1-gates")
    check("1a", "the gates show on the deal: Compliance, Finance, Paperwork and the owner still open", "OWNER" in t.upper() and t.count("✓") == 1 and "✓ REVIEW" in t.upper(), t[:90])
    check("1b", "Form F's signatures wait for Compliance", "wait for Compliance" in pg.locator("#formf").inner_text())
    steps = [t["action"] for t in view()["tasks"] if t["agent"] == "transfer"]

    # Compliance: a possible match holds it
    desk("priya")
    c = pg.locator("#clearance")
    clear()
    c.get_by_role("button", name="Clear this deal").click()
    check("2a", "clearing too early says what's left", "Not yet" in toast())
    check("2b", "the blockers are listed", "Rate the risk" in c.inner_text() and "Screen Karim" in c.inner_text())
    t = next(x for x in view()["tasks"] if x["person"] == "Tariq Haddad" and x["status"] == "queued")
    card = pg.locator("#dept-comp .card:not(#clearance)", has_text="Screen Tariq")
    card.get_by_label("Screening note").fill("UN list, entry 4411")
    card.get_by_role("button", name="Possible match").click()
    pg.wait_for_timeout(700)
    desk("priya")
    card = pg.locator("#dept-comp .card:not(#clearance)", has_text="Screen Tariq")
    check("2c", "a possible match stays open and holds the deal", "holds the deal" in card.inner_text())
    shot("2-hit")
    pg.goto(f"{BASE}/web/deal.html#compliance")
    pg.wait_for_selector("#hits")
    check("2d", "the Compliance room shows the hit", "Tariq Haddad" in pg.locator("#hits").inner_text())
    shot("3-compliance-room")
    desk("priya")
    card = pg.locator("#dept-comp .card:not(#clearance)", has_text="Screen Tariq")
    card.get_by_label("How it was decided").fill("Different date of birth")
    card.get_by_role("button", name="False positive").click()
    pg.wait_for_timeout(600)
    desk("priya")
    card = pg.locator("#dept-comp .card:not(#clearance)", has_text="Screen Karim")
    card.get_by_label("Screening note").fill("UN, UAE, US, UK, EU")
    card.get_by_role("button", name="Clear", exact=True).click()
    pg.wait_for_timeout(600)

    # the documents arrive from a phone; the officer compares them
    phone = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
    cp = phone.new_page()
    cp.on("pageerror", lambda e: errors.append(str(e)))
    v = view()
    for i, r in enumerate(v["documents"]["requests"]):
        tok = r["url"].split("t=")[1]
        for j, d in enumerate(r["docs"]):
            fields = {"eid_front": {"number": luhn_id(), "name": r["name"], "expiry": "2030-01-01"}, "passport": {"number": f"P{i}", "expiry": "2031-01-01"},
                      "visa": {"expiry": "2029-01-01"}, "title_deed": {"number": "TD-1", "unit": "1204"}}.get(d["kind"], {})
            import json
            api.post(f"{BASE}/api/docs/{tok}", multipart={"kind": d["kind"], "fields": json.dumps(fields), "file": {"name": "c.jpg", "mimeType": "image/jpeg", "buffer": card_image(i * 10 + j)}})
    desk("priya")
    n = 0
    while (btn := pg.get_by_role("button", name="It matches").first).count():
        btn.click()
        pg.wait_for_timeout(450)
        n += 1
        if n > 12:
            break
    check("2e", "the officer confirmed each document", n == sum(len(r["docs"]) for r in v["documents"]["requests"]), n)
    desk("priya")
    c = pg.locator("#clearance")
    c.get_by_label("Risk", exact=True).select_option("low")
    c.get_by_role("button", name="Rate").click()
    pg.wait_for_timeout(600)
    # the payer's third-party question is the officer's to review too
    while (rv := pg.locator("#dept-comp").get_by_role("button", name="Reviewed").first).count():
        rv.click()
        pg.wait_for_timeout(450)
    desk("priya")
    c = pg.locator("#clearance")
    clear()
    c.get_by_role("button", name="Clear this deal").click()
    check("2f", "missing proof needs her reason", "source-of-funds" in toast())
    c.get_by_label("Clearance note").fill("Bank letter seen in person; a copy follows")
    clear()
    c.get_by_role("button", name="Clear this deal").click()
    toast()
    pg.wait_for_timeout(600)
    check("2g", "cleared on the current facts", view()["compliance"]["ok"], view()["compliance"].get("reason"))

    # signing on a phone: a selfie is refused, a drawn signature passes
    desk("omar")
    pg.locator("#formf").get_by_role("button", name="Make the signing links").click()
    pg.wait_for_timeout(700)
    v = view()
    links = v["agency"]["formf"][-1]["links"]
    check("3a", "each signer has a link", {x["signer"] for x in links} >= {"buyer", "seller", "broker"})
    buyer = next(x for x in links if x["signer"] == "buyer")
    cp.goto(buyer["url"].replace("http://testserver", BASE))
    cp.wait_for_selector("#pad")
    cp.fill("#name", "Karim Haddad")
    cp.fill("#id", luhn_id())
    cp.check("#consent")
    cp.click("#tabphoto")
    cp.set_input_files("#img", {"name": "me.jpg", "mimeType": "image/jpeg", "buffer": selfie()})
    cp.click("#sign")
    cp.wait_for_selector("#err:not([hidden])")
    err = cp.inner_text("#err")
    check("3b", "a selfie is refused on the spot, with the reason", "photo of a person" in err, err)
    cp.screenshot(path=str(OUT / "4-selfie-refused.png"), full_page=True)
    check("3c", "the phone page has no sideways scroll", cp.evaluate("document.documentElement.scrollWidth <= innerWidth"))
    cp.click("#tabdraw")
    cp.wait_for_timeout(200)

    def draw(page, strokes):
        box = page.locator("#pad").bounding_box()
        for s in range(strokes):
            page.mouse.move(box["x"] + 30 + s * 60, box["y"] + 40)
            page.mouse.down()
            for k in range(1, 7):
                page.mouse.move(box["x"] + 30 + s * 60 + k * 18, box["y"] + 40 + (k % 2) * 60)
            page.mouse.up()

    draw(cp, 1)
    cp.click("#sign")
    cp.wait_for_function("document.querySelector('#err').textContent.includes('usual signature')")
    check("3d", "one line isn't a signature", True)
    draw(cp, 2)
    cp.wait_for_timeout(100)
    cp.screenshot(path=str(OUT / "5-drawn.png"), full_page=True)
    cp.click("#sign")
    cp.wait_for_selector(".msg.ok")
    check("3e", "a drawn signature is accepted", "signed this form" in cp.inner_text("#main"))
    for x in links:
        if x["signer"] != "buyer":
            cp.goto(x["url"].replace("http://testserver", BASE))
            cp.wait_for_selector("#pad")
            cp.fill("#name", x["name"] if not x["name"].startswith("the ") else "Huda Al Mansoori")
            cp.fill("#id", "ID-1")
            cp.check("#consent")
            draw(cp, 3)
            cp.click("#sign")
            cp.wait_for_selector(".msg.ok")
    pdf = b"%PDF-1.4 signed"
    desk("omar")
    for f in view()["agency"]["forms"]:
        if f["waiting"]:
            answers.append(True)
            file = pg.get_by_label(f"Signed Form {f['form']} (PDF)")
            file.set_input_files({"name": "s.pdf", "mimeType": "application/pdf", "buffer": pdf})
            pg.locator("#agency .card", has_text=f"v{f['version']}").filter(has=file).get_by_role("button", name="Upload the signed copy").click()
            pg.wait_for_timeout(700)
    check("3f", "Forms A and B filed, Form F signed", not [f for f in view()["agency"]["forms"] if f["waiting"]] and "✓ PAPERWORK" in pg.locator("#gates").inner_text().upper())

    # Operations: submit, a cash buyer's checklist
    desk("joseph")
    card = pg.locator("#dept-ops .card", has_text="Submit Form F").last
    card.locator("input").fill("DLD-88123")
    card.get_by_role("button", name="I submitted it").click()
    pg.wait_for_timeout(800)
    steps = [t for t in view()["tasks"] if t["agent"] == "transfer"]
    names = [t["action"] for t in steps]
    check("4a", "a cash deal with no seller's mortgage has no mortgage steps", not any("mortgage" in x.lower() for x in names), names)
    check("4b", "Form F's step is already done", next(t for t in steps if t["action"].startswith("Form F"))["status"] == "done")
    desk("joseph")
    noc = pg.locator("#dept-ops .card", has_text="Developer NOC")
    noc.get_by_role("button", name="Draft for the").click()
    pg.wait_for_timeout(700)
    desk("joseph")
    noc = pg.locator("#dept-ops .card", has_text="Developer NOC")
    check("4c", "the NOC draft lists what to type, from the record", "Karim Haddad" in noc.inner_text() and "2,600,000" in noc.inner_text())
    shot("6-portal-draft")
    noc.get_by_label("Portal reference").fill("NOC-77")
    noc.get_by_role("button", name="I submitted it").click()
    pg.wait_for_timeout(700)
    check("4d", "submitted under its reference", next(t for t in view()["tasks"] if t["action"].startswith("Developer NOC"))["status"] == "done")
    desk("joseph")
    chq = pg.locator("#dept-ops .card", has_text="Manager's cheques")
    chq.get_by_role("button", name="Done").click()
    pg.wait_for_timeout(600)
    desk("joseph")
    bk = pg.locator("#dept-ops .card", has_text="Trustee office appointment")
    bk.get_by_label("Appointment date and time").fill((date.today() + timedelta(days=5)).isoformat() + "T10:00")
    bk.get_by_label("Trustee office").fill("Trustee Marina")
    clear()
    bk.get_by_role("button", name="Book the transfer").click()
    check("4e", "the trustee waits for ready-for-transfer", "ready-for-transfer" in toast())

    # Finance: proof, third party, part payment, undo, Compliance first
    desk("ahmed")
    pay = pg.locator("#dept-fin .card", has_text="Expect AED 260,000")
    pay.get_by_label("Amount received (AED)").fill("100000")
    pay.get_by_label("Amount on the proof").fill("90000")
    pay.get_by_label("Payment reference").fill("ENBD 1")
    answers.append(False)
    clear()
    pay.get_by_role("button", name="Received").click()
    check("5a", "a proof that disagrees is flagged and nothing is saved", "Proof shows AED 90,000" in toast())
    pay.get_by_label("Amount on the proof").fill("")
    clear()
    pay.get_by_role("button", name="Received").click()
    check("5b", "a third-party payer goes to Compliance before the receipt", "With Compliance" in toast())
    pg.wait_for_timeout(700)
    check("5c", "no receipt filed yet", not [d for d in api.get(f"{BASE}/api/desk/deals/{M}").json()["tasks"] if d.get("result") == "received"] )
    desk("ahmed")
    pay = pg.locator("#dept-fin .card", has_text="Expect AED 260,000")
    check("5d", "the balance stays open", pay.get_by_label("Amount received (AED)").input_value() == "160000")
    shot("7-part-payment")
    pay.get_by_label("Payment reference").fill("ENBD 2")
    pay.get_by_role("button", name="Received").click()
    pg.wait_for_timeout(800)
    desk("priya")
    n = 0
    while (rv := pg.locator("#dept-comp").get_by_role("button", name="Reviewed").first).count() and n < 6:
        rv.click()
        pg.wait_for_timeout(500)
        n += 1
    check("5e", "the officer looked: the deposit counts", next(x for x in view()["gates"]["gates"] if x["key"] == "finance")["ok"])
    pg.goto(f"{BASE}/web/deal.html#finance")
    pg.wait_for_selector("#cashin")
    check("5f", "the Finance room counts the cash", "260,000" in pg.inner_text("#cashin"), pg.inner_text("#cashin"))
    shot("8-finance-room")

    # the owner, then the transfer
    if not view()["compliance"]["ok"]:
        desk("priya")
        c = pg.locator("#clearance")
        c.get_by_label("Clearance note").fill("Looked at the payments")
        c.get_by_role("button", name="Clear this deal").click()
        pg.wait_for_timeout(700)
    desk("layla")
    g = view()["gates"]
    check("6a", "every gate but the owner's has passed", g["can_approve"], [x["note"] for x in g["gates"] if not x["ok"]])
    shot("9-gates-passed")
    pg.locator("#approvegate").click()
    pg.wait_for_timeout(800)
    check("6b", "ready for transfer", view()["gates"]["ready"])
    desk("joseph")
    bk = pg.locator("#dept-ops .card", has_text="Trustee office appointment")
    bk.get_by_label("Appointment date and time").fill((date.today() + timedelta(days=5)).isoformat() + "T10:00")
    bk.get_by_label("Trustee office").fill("Trustee Marina")
    bk.get_by_role("button", name="Book the transfer").click()
    pg.wait_for_timeout(800)
    desk("joseph")
    pg.locator("#dept-ops .card", has_text="Title deed issued").get_by_role("button", name="Done").click()
    pg.wait_for_timeout(800)
    v = view()
    check("6c", "the transfer done: the owner's trigger drafted the invoice", any(d["kind"] == "commission invoice" for d in v["drafts"]))
    desk("joseph")
    pg.locator("#dept-ops .card", has_text="Handover").get_by_role("button", name="Done").click()
    pg.wait_for_timeout(800)
    pg.goto(f"{BASE}/web/deal.html#operations")
    pg.wait_for_selector("#appointments")
    check("6d", "the Operations room shows the appointment", "Trustee Marina" in pg.locator("#appointments").inner_text())
    shot("10-operations-room")

    # the commission, then closing
    desk("ahmed")
    inv = pg.locator("#dept-fin .card", has_text="Send commission invoice")
    inv.get_by_role("button", name="I sent it").click()
    pg.wait_for_timeout(800)
    desk("ahmed")
    col = pg.locator("#dept-fin .card", has_text="Collect commission")
    check("7a", "the invoice has a due date", "Due " in col.inner_text())
    col.get_by_label("Bank reference").fill("ENBD 9")
    col.get_by_role("button", name="Received").click()
    pg.wait_for_timeout(800)
    desk("ahmed")
    pg.locator("#dept-fin .card", has_text="their commission").get_by_label("Bank reference").fill("ENBD 10")
    pg.locator("#dept-fin .card", has_text="their commission").get_by_role("button", name="Paid").click()
    pg.wait_for_timeout(800)
    desk("omar")
    pg.locator("#closing").get_by_role("button", name="Confirm the final figures").click()
    pg.wait_for_timeout(700)
    desk("joseph")
    pg.locator("#closing").get_by_role("button", name="Documents filed").click()
    pg.wait_for_timeout(700)
    desk("joseph")
    if pg.locator("#closing").get_by_role("button", name="Close the deal").is_disabled():
        print("  closing left:", [i for i in view()["closing"]["items"] if not i["done"]])
    pg.locator("#closing").get_by_role("button", name="Close the deal").click()
    pg.wait_for_timeout(900)
    v = view()
    check("7b", "the deal closes and goes to Records", v["closing"]["sale"] and v["stage"] == "Won")
    evs = {e["type"] for e in api.get(f"{BASE}/api/events?deal={M}").json()}
    check("7c", "the loop is on the log", {"case.converted", "compliance.cleared", "payment.marked_received", "deal.ready_for_transfer", "transfer.booked", "transfer.completed", "case.closed"} <= evs)

    # a client's thread with a correction: board and rooms at 1280 and phone width
    pg.goto(f"{BASE}/web/deal.html#board")
    pg.wait_for_selector("#board, .allclear")
    shot("11-board")
    check("8a", "the board shows the open deals by stage", pg.locator(".bcol").count() >= 1)
    ph = phone.new_page()
    ph.on("pageerror", lambda e: errors.append(str(e)))
    for room in ("compliance", "finance", "operations", "board"):
        ph.goto(f"{BASE}/web/deal.html#{room}")
        ph.wait_for_timeout(700)
        ph.screenshot(path=str(OUT / f"12-phone-{room}.png"), full_page=True)
    check("8b", "no page errors in any room", not errors, errors[:2])
    b.close()

bad = [r for r in results if not r[2]]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
for r in bad:
    print("FAILED", r[0], r[1])
sys.exit(1 if bad else 0)
