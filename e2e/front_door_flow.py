"""The front door (docs/front-door-spec.md), checked as a person would: the owner's settings, a client who is only
looking, coming back ready, "call me", hot on qualifying, and a portal lead that starts from its listing.
Run against a fresh demo server (rules mode) with PORTAL_SECRET_PROPERTYFINDER set:
python e2e/front_door_flow.py http://127.0.0.1:8052 <out dir> <portal secret>"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8052"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "e2e/shots") / "front_door"
SECRET = sys.argv[3] if len(sys.argv) > 3 else ""
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

    def shot(name, full=False):
        path = OUT / f"{name}.png"
        pg.screenshot(path=str(path), full_page=full)
        return path.name

    def customer(phone, text, name="Mona Saleh"):
        """Message the office from the Inbox's sandbox phone, as the customer; return Rania's newest reply."""
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
            new = (r.json()["messages"] if r.ok else [])[before:]
            sent = [m for m in new if m["type"] == "sent"]
            if sent:
                break
            pg.wait_for_timeout(150)
        pg.goto(f"{BASE}/web/inbox.html?chat={phone}&as=layla")
        pg.wait_for_timeout(700)
        return sent[-1]["text"] if sent else ""

    def row(phone):
        return pg.locator(".conv", has=pg.locator(".nm")).filter(has_text=re.compile(r".")).nth(
            [r["phone"] for r in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"]].index(phone))

    # 1. The owner's front-door settings; a broker can't change them
    pg.goto(f"{BASE}/web/qualify.html")
    pg.select_option("#as", "omar")
    pg.wait_for_timeout(500)
    box = pg.locator("#frontbox")
    box.scroll_into_view_if_needed()
    check(1, "A broker sees the front door but can't change it", pg.locator("#fsave").is_disabled()
          and "Only the owner" in pg.locator("#fnote").inner_text(), shot("01-broker-locked"))
    pg.select_option("#as", "layla")
    pg.wait_for_timeout(400)
    opts = pg.locator("#fnur option").all_inner_texts()
    pg.select_option("#ftpl", "portal_enquiry")
    body = pg.locator("#ftplbody").inner_text()
    pg.locator("#rhot input[value=qualified]").check()
    pg.click("#rsave")
    pg.wait_for_timeout(400)
    pg.click("#fsave")
    pg.wait_for_timeout(600)
    fr = api.get(f"{BASE}/api/rania/front").json()
    rec = api.get(f"{BASE}/api/rania/recommend").json()
    check(2, "The owner picks who nurtures, the portal template, and 'They qualify' as hot",
          opts == ["Marketing nurtures them", "Their broker keeps them", "Nobody: park the chat"] and fr["portal_template"] == "portal_enquiry"
          and "filled in order" in body and "qualified" in rec["hot_on"], shot("02-owner-saves"), f"hot_on={rec['hot_on']}")

    # 2. Only looking: a warm reply, nurtured, no card
    A = "971502220001"
    customer(A, "Hi, do you have anything in Dubai Hills?")
    reply = customer(A, "Thanks, I'm just looking for now")
    rows = api.get(f"{BASE}/api/chats?view=all&person=layla").json()
    ra = next(r for r in rows["rows"] if r["phone"] == A)
    check(3, "'Just looking' gets a warm reply with no question", "take your time" in reply and "?" not in reply, shot("03-just-looking"), reply)
    lst = pg.locator(".conv").filter(has_text="Mona Saleh")
    check(4, "The lead shows 🌱 nurture and has no card for the broker", lst.locator(".tg.nur").count() == 1 and not ra["attention"],
          shot("04-nurture-chip"))
    prof = pg.locator("#prof").inner_text()
    check(5, "The lead says it's nurtured by Marketing, with their words, and Rania asks nothing next",
          "Not ready yet, nurtured by Marketing" in prof and "just looking for now" in prof and "Rania asks next" not in prof, shot("05-profile"))
    pg.locator("#tabs button", has_text="Nurture").click()
    pg.wait_for_timeout(500)
    names = pg.locator("#rows .conv .nm").all_inner_texts()
    check(6, "The Nurture tab lists them, and Marketing's list has them", names == ["Mona Saleh"]
          and [x["customer"] for x in api.get(f"{BASE}/api/leads/nurture").json()["leads"]] == ["Mona Saleh"], shot("06-nurture-tab"))
    reply = customer(A, "Thank you!")
    check(7, "A nurtured client gets a short, friendly reply, no chasing", reply == "Anytime! I'm here whenever you're ready.", shot("07-anytime"), reply)

    # 3. Coming back ready
    reply = customer(A, "OK, I'm ready now. I want to buy a villa in Dubai Hills")
    prof = pg.locator("#prof").inner_text()
    lst = pg.locator(".conv").filter(has_text="Mona Saleh")
    pg.goto(f"{BASE}/web/inbox.html?chat={A}&as=omar")
    pg.wait_for_timeout(600)
    pg.click("#bell")
    pg.wait_for_timeout(400)
    bell = pg.locator("body").inner_text()
    check(8, "Coming back ready reopens the lead, tells the broker, and qualifying goes on",
          "Came back ready" in prof and "is back and ready" in bell and "?" in reply, shot("08-back-ready"), reply)

    # 4. "Can someone call me?"
    B = "971502220002"
    customer(B, "Hello", name="Yousef Ali")
    reply = customer(B, "Can someone call me please?", name="Yousef Ali")
    rb = next(r for r in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"] if r["phone"] == B)
    check(9, "'Call me' gets 'our team will call you' and the broker a call card; Rania keeps the chat",
          "will call you shortly" in reply and rb["attention"] and rb["attention"]["kind"] == "call" and rb["mode"] == "ai",
          shot("09-call-me"), f"{reply} · {rb['attention'] and rb['attention']['reason']}")

    # 5. Qualifying makes it hot (the owner ticked it)
    C = "971502220003"
    for t in ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now"):
        reply = customer(C, t, name="Huda Karim")
    rc = next(r for r in api.get(f"{BASE}/api/chats?view=all&person=layla").json()["rows"] if r["phone"] == C)
    lst = pg.locator(".conv").filter(has_text="Huda Karim")
    prof = pg.locator("#prof").inner_text()
    check(10, "Once qualified, the lead is 🔥 hot at once, with the options Rania sent",
          rc["hot"] == "yes" and lst.locator(".tg.hot", has_text="🔥 hot").count() == 1 and "Hot lead: qualified" in prof
          and rc["attention"]["reason"].startswith("🔥 Hot lead, ready to close: qualified") and "\n1. " in reply, shot("10-hot-qualified"))

    # 6. A portal lead starts from the listing
    D = "971502220004"
    lead = {"data": {"name": "Farah Haddad", "phone": f"+{D}", "message": "Is this still available?", "listing": {"reference": "MC-1204"}}}
    r = api.post(f"{BASE}/api/portals/propertyfinder/lead?token={SECRET}", data=lead)
    pg.goto(f"{BASE}/web/inbox.html?chat={D}&as=layla")
    pg.wait_for_timeout(800)
    chat = pg.locator("#chat").inner_text()
    prof = pg.locator("#prof").inner_text()
    check(11, "A Property Finder enquiry gets the owner's template and keeps the broker's call card",
          r.ok and "thank you for your enquiry about" in chat and "Farah" in chat and pg.locator(".conv").filter(has_text="Farah Haddad").locator(".att").count() >= 1,
          shot("11-portal-template"), r.text()[:120])
    check(12, "What the listing tells us is filled in: buying, area, type, bedrooms (not the budget)",
          "Buyer" in prof and "Dubai Marina" in prof and "Apartment" in prof and "Budget" not in prof.split("Rania asks next")[0], shot("12-portal-filled"))
    reply = customer(D, "Yes, still interested", name="Farah Haddad")
    check(13, "When they write on WhatsApp, Rania asks only what's missing (the budget)",
          "budget" in reply.lower() and "area" not in reply.lower(), shot("13-asks-missing"), reply)

    # 7. Phone width
    pg.set_viewport_size({"width": 390, "height": 844})
    over = []
    for page in ("inbox.html?as=layla", "qualify.html"):
        pg.goto(f"{BASE}/web/{page}")
        pg.wait_for_timeout(700)
        if pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"):
            over.append(page)
    pg.goto(f"{BASE}/web/qualify.html")
    pg.wait_for_timeout(500)
    pg.locator("#frontbox").scroll_into_view_if_needed()
    check(14, "Inbox and Qualification fit a phone, no sideways scroll", not over, shot("14-phone"), ", ".join(over))
    b.close()

passed = sum(1 for r in results if r[2])
print(f"\n{passed}/{len(results)} passed · page errors: {errors or 'none'}")
