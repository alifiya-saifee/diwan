"""Which property a deal is on (docs/deal-desk.md item 17), checked as a person would. Run against an offline test server
with its own database, never diwan.db. With a second address it also checks a copy of a real office, on a deal converted
before this was built:
python e2e/property_flow.py http://127.0.0.1:8041 <out dir> [http://127.0.0.1:8042 <deal id>]"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8041"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "property"
OLD, OLD_DEAL = (sys.argv[3], sys.argv[4]) if len(sys.argv) > 4 else (None, None)
OUT.mkdir(parents=True, exist_ok=True)
errors, results = [], []
AGREED = "input[aria-label='Agreed price (AED)']"


def check(n, name, ok, note=""):
    results.append((n, name, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'} {n} {name}{' · ' + note if note else ''}")


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    api = pg.request

    def shot(name):
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=True)

    def toast():
        t = pg.locator(".toast").last
        t.wait_for(timeout=20000)
        return t.inner_text()

    def clear():
        pg.evaluate("document.querySelectorAll('.toast').forEach((t) => t.remove())")

    def enquiry(phone, who):
        api.post(f"{BASE}/api/chats/incoming", data={"phone": phone, "text": "Hi, I want to buy a home", "name": who})
        return f"lead-{phone[-8:]}"

    def deal(d, who="layla", base=BASE):
        pg.goto(f"{base}/web/deal.html?deal={d}")
        pg.wait_for_selector("#stagebar")
        pg.select_option("#as", who)
        pg.wait_for_timeout(700)

    def convert_box(stage="Offer accepted"):
        pg.locator("#stagebar").get_by_role("button", name=stage).click()
        pg.wait_for_selector("#convert")
        pg.wait_for_timeout(400)
        return pg.locator("#convert")

    def save():
        clear()
        pg.locator("#convert").get_by_role("button", name="Save and convert").click()
        msg = toast()
        pg.wait_for_timeout(900)
        return msg

    def status(ref):
        return next(x for x in api.get(f"{BASE}/api/listings").json() if x["props"].get("ref") == ref)["status"]

    def fill_agency(root, share="50"):
        root.get_by_label("Agency", exact=True).fill("Bayut Homes")
        root.get_by_label("Their ORN").fill("ORN-777")
        root.get_by_label("Their agent").fill("Rami Aziz")
        root.get_by_label("Agent's BRN").fill("BRN-9")
        root.get_by_label("Their share of the commission (%)").fill(share)

    api.post(f"{BASE}/api/demo/reset")
    for i in range(120):
        api.post(f"{BASE}/api/listings", data={"ref": f"PT-{i}", "title": f"Palm Tower {i}", "community": "Palm Jumeirah", "beds": 2, "price_aed": 3_000_000 + i})
    one, two, three, four, five = (enquiry(f"97150000000{i}", n) for i, n in enumerate(("Ali Test", "Noor Test", "Sara Test", "Dana Test", "Rami Test")))

    # 1. nothing converts on a placeholder
    pg.goto(f"{BASE}/web/deal.html?deal={one}&as=layla&convert=1")  # where the Inbox's Convert lands on a deal with no property
    pg.wait_for_selector("#convert", timeout=8000)
    check("1a", "arriving from the Inbox's Convert opens the full box, as the same person", one in pg.url and pg.input_value("#as") == "layla" and "Whose property is it?" in pg.locator("#convert").inner_text())
    deal(one)
    conv = convert_box()
    conv.locator(AGREED).fill("1900000")
    msg = save()
    check("1", "a deal from a message can't convert without its property", "Pick one of our listings" in msg
          and "WhatsApp enquiry" in api.get(f"{BASE}/api/desk/deals/{one}").json()["property"], msg)

    # 2. our listing: search, pick, price, the name everywhere
    conv = pg.locator("#convert")
    conv.get_by_label("Search our listings").fill("jumeirah village")
    pg.wait_for_selector("#propresults button:has-text('Villa 88')")
    conv.locator(AGREED).fill("")
    pg.locator("#propresults button", has_text="Villa 88").click()
    pg.wait_for_timeout(400)
    filled, delta = conv.locator(AGREED).input_value(), pg.locator("#delta").inner_text()
    shot("2-our-listing")
    check("2a", "searching by area finds the listing; picking it fills its price and compares", filled == "1900000" and "At the listing price of AED 1,900,000" in delta, f"{filled} | {delta}")
    conv.locator(AGREED).fill("1850000")
    msg = save()
    v = api.get(f"{BASE}/api/desk/deals/{one}").json()
    bar = pg.locator("#stagebar").inner_text()
    shot("2b-converted")
    check("2b", "converted on the listing: the deal shows it, the price compares, it is reserved", v["property"] == "Villa 88" and "Property: Villa 88" in bar
          and "2.6% discount on the listing" in bar and status("JVC-88") == "reserved", msg)
    ag = pg.locator("#agency").inner_text()
    check("2c", "the forms are drafted with no second question", "Form A" in ag and "Form B" in ag and pg.locator("#savesides").count() == 0)
    href = pg.locator("#agency").get_by_role("link", name="Download PDF").last.get_attribute("href")
    pdf = api.get(f"{BASE}{href}").body().decode("latin-1")
    check("2d", "the form's PDF names the property and its ref", "Villa 88" in pdf and "JVC-88" in pdf)
    pg.goto(f"{BASE}/web/deal.html#deals")
    pg.wait_for_timeout(1200)
    pg.locator("input[type=search], #q").first.fill("Ali Test")
    pg.wait_for_timeout(900)
    check("2e", "the deal list shows the real property", "Villa 88" in pg.inner_text("main"))

    # 3-4. a held listing isn't offered; an empty search says so; a long list says how many
    deal(two)
    conv = convert_box()
    conv.get_by_label("Search our listings").fill("jumeirah village")
    pg.wait_for_timeout(700)
    empty = pg.locator("#propresults").inner_text()
    r = api.post(f"{BASE}/api/desk/deals/{two}/convert", data={"by": "layla", "amount": 1900000, "property": {"source": "listing", "ref": "JVC-88"}})
    check("3", "a listing on another deal isn't offered and is refused if sent", "Villa 88" not in empty and r.status == 400 and "reserved" in r.json()["detail"], r.json()["detail"])
    conv.get_by_label("Search our listings").fill("palm")
    pg.wait_for_timeout(700)
    more = pg.locator("#propresults").inner_text()
    check("4", "a long list shows the first ones and says how many", "20 of 122" in more, more[-60:])

    # 5. another agency's listing
    conv.get_by_label("Search our listings").fill("no such place")
    pg.wait_for_timeout(700)
    check("4b", "an empty search says so", "No free listing matches" in pg.locator("#propresults").inner_text())
    conv.get_by_label("Another agency's listing").check()
    conv.get_by_label("Property: unit, building, area").fill("Apt 901, Creek Tower, Dubai Creek")
    conv.locator(AGREED).fill("2200000")
    d = pg.locator("#delta").inner_text()
    msg = save()
    ok = "Name the agency" in msg
    fill_agency(pg.locator("#convert"), "")
    msg2 = save()
    check("5a", "a missing agency or share is refused; nothing to compare the price with", ok and "together" in msg2 and "nothing to compare" in d, f"{msg} | {msg2}")
    pg.locator("#convert").get_by_label("Their share of the commission (%)").fill("50")
    shot("5-agency")
    msg = save()
    v = api.get(f"{BASE}/api/desk/deals/{two}").json()
    ag = pg.locator("#agency").inner_text()
    bar = pg.locator("#stagebar").inner_text()
    check("5b", "another agency's listing: Form B and Form I, no second question, and we act for the buyer", v["property"].startswith("Apt 901") and "Form B" in ag and "Form I" in ag
          and "Form A" not in ag and pg.locator("#savesides").count() == 0 and "Another agency's listing" in bar, msg)
    href = pg.locator("#agency").get_by_role("link", name="Download PDF").last.get_attribute("href")
    pdf = api.get(f"{BASE}{href}").body().decode("latin-1")
    check("5c", "Form I carries the other agency and the property", "Bayut Homes" in pdf and "ORN-777" in pdf and "Apt 901" in pdf)

    # 6. the agency comes back with its details; our listing with an agency's buyer
    deal(three)
    conv = convert_box()
    conv.get_by_label("Search our listings").fill("Bay Square")
    pg.wait_for_selector("#propresults button:has-text('Apartment 305')")
    pg.locator("#propresults button", has_text="Apartment 305").click()
    conv.locator("#propbrought").check()
    pg.wait_for_timeout(500)
    name = conv.get_by_label("Agency", exact=True)
    name.fill("bayut homes")
    name.dispatch_event("change")
    orn, agent = conv.get_by_label("Their ORN").input_value(), conv.get_by_label("Their agent").input_value()
    conv.get_by_label("Their share of the commission (%)").fill("40")
    msg = save()
    ag = pg.locator("#agency").inner_text()
    check("6", "an agency used once fills its details; our listing with its buyer is Form A and Form I", orn == "ORN-777" and agent == "Rami Aziz" and "Form A" in ag and "Form I" in ag, msg)

    # 7. a developer's unit
    api.post(f"{BASE}/api/desk/deals/{four}/path", data={"by": "layla", "path": "offplan"})
    deal(four)
    conv = convert_box("Reservation")
    first = conv.locator("input[name=propsource]").first.get_attribute("value")
    none = conv.inner_text()
    r = api.get(f"{BASE}/api/desk/rules").json()["rules"]
    r["developers"] = [{"name": "Emaar", "commission_pct": 4, "payable_after_pct": 20}]
    api.post(f"{BASE}/api/desk/rules", data={"by": "layla", "rules": r})
    bad = api.post(f"{BASE}/api/desk/deals/{four}/convert", data={"by": "layla", "amount": 2000000, "property": {"source": "developer", "developer": "Nobody", "project": "P", "unit": "1"}})
    deal(four)
    conv = convert_box("Reservation")
    conv.get_by_label("Developer", exact=True).select_option("Emaar")
    conv.get_by_label("Project").fill("Creek Rise")
    conv.get_by_label("Unit").fill("1204")
    conv.locator(AGREED).fill("2000000")
    shot("7-developer")
    msg = save()
    v = api.get(f"{BASE}/api/desk/deals/{four}").json()
    check("7a", "off-plan offers the developer first; with no agreements it says the owner adds them", first == "developer" and "No developer agreements yet" in none)
    check("7b", "a developer's unit names the deal and uses its rate; an unknown developer is refused", v["property"] == "1204, Creek Rise" and "4%" in pg.inner_text("main")
          and bad.status == 400 and "no agreement with Nobody" in bad.json()["detail"], msg)

    # 8. a rental
    api.post(f"{BASE}/api/desk/deals/{five}/path", data={"by": "layla", "path": "rent"})
    deal(five)
    conv = convert_box()
    opts = [conv.locator("input[name=propsource]").nth(i).get_attribute("value") for i in range(conv.locator("input[name=propsource]").count())]
    check("8", "a rental offers our listing and another agency's, not a developer", opts == ["listing", "agency"], str(opts))

    # 12a. the phone, with the box open
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.wait_for_timeout(500)
    wide = pg.evaluate("[...document.querySelectorAll('#convert *')].filter(e => e.getBoundingClientRect().right > 392).length")
    shot("12-phone")
    check("12a", "the box fits a phone with no sideways scroll", wide == 0, f"{wide} wider")
    pg.set_viewport_size({"width": 1280, "height": 1000})

    # 10. changing it
    deal(one)
    pg.click("#propchange")
    pg.wait_for_selector("#propcard")
    card = pg.locator("#propcard")
    card.get_by_label("Search our listings").fill("Burj Vista")
    pg.wait_for_selector("#propresults button:has-text('Apartment 2210')")
    pg.locator("#propresults button", has_text="Apartment 2210").click()
    clear()
    started = time.time()
    pg.click("#propsave")
    msg = toast()
    print(f"saving the change took {time.time() - started:.1f}s")
    pg.wait_for_timeout(900)
    v = api.get(f"{BASE}/api/desk/deals/{one}").json()
    ag = pg.locator("#agency").inner_text()
    check("10a", "changing the property redrafts the forms and moves the reservation", v["property"].startswith("Apartment 2210") and "v2" in ag and status("JVC-88") == "available" and status("DT-2210") == "reserved", msg)
    task = next(t for t in v["tasks"] if t.get("step") == "sign" and t["status"] not in ("done", "withdrawn"))
    r = api.post(f"{BASE}/api/desk/tasks/{task['id']}/signed", multipart={"by": "omar", "checked": "1", "file": {"name": "s.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 signed"}})
    r = r if r.ok else api.post(f"{BASE}/api/desk/tasks/{task['id']}/signed", multipart={"by": "layla", "checked": "1", "file": {"name": "s.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4 signed"}})
    deal(one)
    bar = pg.locator("#stagebar").inner_text()
    refused = api.post(f"{BASE}/api/desk/deals/{one}/property", data={"by": "layla", "property": {"source": "listing", "ref": "BB-305"}})
    check("10b", "a signed form fixes the property: the button goes and a change is refused", pg.locator("#propchange").count() == 0 and "signed for this property" in bar and refused.status == 400, r.status_text)

    # 11. lost lets it go
    deal(three)
    bar = pg.locator("#stagebar")
    bar.get_by_role("button", name="Mark lost").click()
    pg.wait_for_timeout(300)
    bar.get_by_label("Why", exact=True).fill("The buyer's finance fell through")
    bar.get_by_role("button", name="Mark lost").last.click()
    pg.wait_for_timeout(900)
    check("11", "a lost deal releases our listing", status("BB-305") == "available", status("BB-305"))

    # 12b. someone else
    deal(five, "priya")
    r = api.post(f"{BASE}/api/desk/deals/{five}/property", data={"by": "priya", "property": {"source": "agency", "label": "X"}})
    check("12b", "someone who isn't the broker, the transactions officer or the owner can't say", r.status == 403 and pg.locator("#propform").count() == 0)

    # 9. a copy of a real office: a deal converted before this was built
    if OLD:
        v = api.get(f"{OLD}/api/desk/deals/{OLD_DEAL}").json()
        r = api.get(f"{OLD}/api/desk/rules").json()["rules"]
        r["developers"] = [{"name": "Emaar", "commission_pct": 4, "payable_after_pct": 20}]
        api.post(f"{OLD}/api/desk/rules", data={"by": "layla", "rules": r})
        deal(OLD_DEAL, "layla", OLD)
        card = pg.locator("#propcard")
        before = pg.locator("#agency").inner_text()
        shot("9a-old-deal")
        check("9a", "a deal converted before this gets the form, instead of the other-side question", card.count() == 1 and "Which property" in card.inner_text()
              and pg.locator("#savesides").count() == 0 and "Say which property this is above" in before)
        card.get_by_label("Developer", exact=True).select_option("Emaar")
        card.get_by_label("Project").fill("Creek Rise")
        card.get_by_label("Unit").fill("804")
        clear()
        pg.click("#propsave")
        msg = toast()
        pg.wait_for_timeout(1000)
        v = api.get(f"{OLD}/api/desk/deals/{OLD_DEAL}").json()
        shot("9b-old-deal-saved")
        check("9b", "saving it names the deal and closes the question", v["property"] == "804, Creek Rise" and pg.locator("#propcard").count() == 0
              and not [t for t in v["tasks"] if t.get("step") == "sides" and t["status"] not in ("done", "withdrawn")], msg)
    b.close()

print("page errors:", errors or "none")
print(f"{sum(r[2] for r in results)}/{len(results)} passed")
sys.exit(0 if all(r[2] for r in results) and not errors else 1)
