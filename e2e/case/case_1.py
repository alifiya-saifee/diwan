"""Case 1, a ready sale, the first half, on the owner's flow: Rania qualifies, an agent talks and confirms the place, the viewing happens, offers go back and forth.
Every step on the real pages, and each one judged as a real office would, not only that it ran. The same client goes on to closing in chat_to_close_flow.py.

    python e2e/case/case_1.py http://127.0.0.1:8040 <out dir>
"""
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run, Stop  # noqa: E402

BASE, OUT = sys.argv[1], sys.argv[2]
PHONE, NAME = "971507771001", "Layth Mansour"
r = Run(BASE, OUT, "case-1")


def stage():
    return (r.chat(PHONE) or {}).get("stage")


def no_compliance_yet():
    c = r.chat(PHONE)
    bad = [t["text"] for t in c["tasks"] if re.search(r"^Screen|report|funding", t["text"], re.I)] + [x["text"] for x in c["cards"] if "Compliance" in x["text"]]
    r.check("nothing has gone to Compliance or Finance yet: there's no deal", not bad, bad)


def nova_says(question, needle, must_not=r"\[[A-Z]{1,2}\d+\]|\b[TFQN]\d{1,3}\b"):
    said = r.ask_nova(question)
    r.check(f"Nova, asked \"{question}\"", re.search(needle, said, re.I) and not re.search(must_not, said), said[:260])


def first_contact():
    r.be("layla", "inbox.html")
    r.step("A new client writes on WhatsApp, on the sandbox phone")
    said = r.client_says(PHONE, NAME, "Hi, I'm looking to buy a villa in JVC")
    r.check("Rania answers the first message", said, said[:200])
    c = r.chat(PHONE)
    r.check("it became one chat and one lead with a broker", c and c.get("deal") and c.get("broker"), c.get("broker"))
    r.check("no record numbers or internal words reach the client", not re.search(r"\b[TF]\d+\b|complian|screening", said, re.I))
    no_compliance_yet()


def qualifying():
    r.step("She qualifies them, one answer at a time")
    last = ""
    for t in ("Buying, to live in", "A 4 bed villa", "Budget is about 5 million", "Cash", "Within the next month"):
        last = r.client_says(PHONE, NAME, t)
        r.check(f"she answers: {t}", last and "?" in last, last[:200])
    q = r.chat(PHONE)["qualify"]
    if q["verdict"] != "PASS_TO_AGENT":
        r.check("she asks what's still missing, instead of ending the chat", q.get("next") and "?" in last, (q.get("next"), last[:160]))
        last = r.client_says(PHONE, NAME, "I'm a UAE resident")
    q = r.chat(PHONE)["qualify"]
    r.check("every required answer is on the form", q["verdict"] == "PASS_TO_AGENT", q.get("missing"))
    area = next((a["value"] for a in q["answers"] if a["key"] == "areas"), None)
    r.check("the form says the right area", area and "JVC" in area.upper().replace("JUMEIRAH VILLAGE CIRCLE", "JVC"), area)
    r.check("the stage is Qualified", stage() == "Qualified", stage())
    c = r.chat(PHONE)
    r.check("no false 'these can't both be true' cards for the broker", not [x for x in c["cards"] if "can't both be true" in x["text"]], [x["text"][:90] for x in c["cards"]])
    no_compliance_yet()
    r.step("Nova is asked about the client")
    nova_says(f"Where does {NAME} stand?", r"Layth|villa|qualif")


def next_thursday():
    now = datetime.now() + timedelta(milliseconds=r.skip_ms)
    days = (3 - now.weekday()) % 7 or 7
    return (now + timedelta(days=days)).replace(hour=16, minute=0, second=0, microsecond=0)


def asks_to_view():
    r.step("The client asks to see a villa: Rania must not book it herself")
    said = r.client_says(PHONE, NAME, "Can I see the villa in JVC on Thursday at 4pm?")
    r.check("she promises a call back, not a booking", said and not re.search(r"\bbooked\b|see you|confirmed for", said, re.I), said[:240])
    r.check("nothing is on the calendar", stage() == "Qualified", stage())
    q = r.chat(PHONE)["qualify"]
    area = next((a["value"] for a in q["answers"] if a["key"] == "areas"), None)
    r.check("asking to see 'the villa' didn't overwrite the area", area and "the villa" not in area.lower(), area)
    r.check("the broker has it as a request", r.chat(PHONE).get("viewing_request"), r.chat(PHONE).get("viewing_request"))
    r.broker = r.chat(PHONE)["broker"]
    r.at = next_thursday()


def agent_books():
    b = r.broker
    r.step("The agent opens the chat, talks to the client, confirms the place")
    r.be(b, f"inbox.html?chat={PHONE}")
    r.pg.wait_for_selector(".thread .b")
    r.pg.wait_for_timeout(800)
    r.check("the Inbox shows the request and a way to book it", r.pg.get_by_role("link", name=re.compile("Confirm and book")).count())
    box = r.pg.locator(".compose textarea").first
    box.fill("Hi Layth, this is your agent. Villa 88 is available. Shall we say Thursday at 4pm?")
    box.press("Enter")
    r.pg.wait_for_timeout(1500)
    r.check("the agent's message went to the client", r.chat(PHONE)["messages"][-1]["type"] == "sent", r.chat(PHONE)["messages"][-1].get("text", "")[:100])
    r.check("Rania goes quiet once a person has the chat", r.chat(PHONE).get("mode") == "human", r.chat(PHONE).get("mode"))
    r.client_says(PHONE, NAME, "Yes, Thursday 4pm works, thank you", wait_reply=False)
    r.pg.wait_for_timeout(2500)
    r.step("The agent books it from the Inbox")
    r.be(b, f"inbox.html?chat={PHONE}")
    r.pg.wait_for_timeout(1000)
    r.pg.get_by_role("link", name=re.compile("Confirm and book")).click()
    r.pg.wait_for_selector("#fconfirm", timeout=20000)
    r.pg.wait_for_timeout(1000)
    r.check("the form opens with the client and the place", r.pg.input_value("#fprop") and PHONE in r.pg.input_value("#fphone"), r.pg.input_value("#fprop"))
    r.pg.fill("#fdate", r.at.strftime("%Y-%m-%d"))
    r.pg.fill("#ftime", "16:00")
    r.pg.click("#fsave")
    r.pg.wait_for_timeout(1000)
    r.check("it refuses until the agent confirms the place", re.search("confirm", r.pg.inner_text("#ferr"), re.I), r.pg.inner_text("#ferr"))
    r.pg.check("#fconfirm")
    r.pg.click("#fsave")
    r.pg.wait_for_timeout(1500)
    r.check("the stage is Viewing booked", stage() == "Viewing booked", stage())
    r.be(b, "calendar.html")
    r.pg.wait_for_timeout(800)
    if not r.pg.locator(".ev:not(.blk)", has_text="Layth").count():
        r.pg.locator("button", has_text="›").first.click()
        r.pg.wait_for_timeout(800)
    r.check("the viewing is on the broker's calendar", r.pg.locator(".ev:not(.blk)", has_text="Layth").count())
    no_compliance_yet()


def reminders():
    r.step("A day before: the reminder goes to the client")
    r.be("layla", f"inbox.html?chat={PHONE}")
    n = len(r.chat(PHONE)["messages"])
    r.set_clock((r.at - timedelta(hours=23)).isoformat() + "+04:00")
    r.tick()
    new = r.chat(PHONE)["messages"][n:]
    r.check("the 24-hour reminder went", any(m["type"] == "sent" for m in new), [m.get("text", "")[:120] for m in new])
    r.tick()
    r.check("once only", len(r.chat(PHONE)["messages"]) == n + len(new))
    r.step("Two hours before: the second reminder")
    n = len(r.chat(PHONE)["messages"])
    r.set_clock((r.at - timedelta(minutes=100)).isoformat() + "+04:00")
    r.tick()
    new = r.chat(PHONE)["messages"][n:]
    r.check("the 2-hour reminder went", any(m["type"] == "sent" for m in new), [m.get("text", "")[:120] for m in new])
    r.set_clock((r.at + timedelta(minutes=5)).isoformat() + "+04:00")


def recorded_visit():
    r.step("At the villa: the broker records the visit from the calendar")
    b = r.broker
    r.be(b, "calendar.html")
    r.pg.wait_for_timeout(800)
    r.pg.locator(".ev:not(.blk)", has_text="Layth").first.click()
    r.pg.wait_for_timeout(500)
    r.check("the appointment links to the deal too", r.pg.locator("#detail a", has_text="Open the deal").count())
    r.pg.locator("#detail a", has_text="Record the visit").click()
    r.pg.wait_for_timeout(1000)
    r.pg.click("#start")
    r.pg.wait_for_timeout(500)
    r.check("nothing is kept until the client agrees", r.pg.locator("#consentbox").is_visible() and r.pg.locator("#live").is_hidden())
    r.check("the client can say no", r.pg.locator("#noconsent").count())
    r.pg.click("#consent")
    r.pg.wait_for_timeout(400)
    for who, t in (("customer", "We love the garden."), ("customer", "But the kitchen is too small for us."), ("broker", "The kitchen wall can come down, it isn't structural."),
                   ("broker", "I think you could pay a bit more for this one."), ("customer", "Maybe we'd go up a little, I don't know."), ("customer", "Let me talk to my wife and get back to you.")):
        r.pg.select_option("#speaker", who)
        r.pg.fill("#text", t)
        r.pg.click("#say")
        r.pg.wait_for_timeout(900)
    r.pg.click("#end")
    r.pg.wait_for_timeout(600)
    r.check("End shows it's working", re.search("Writing|ended", r.pg.inner_text("#end")), r.pg.inner_text("#end"))
    t0 = time.time()
    r.pg.wait_for_function("!document.querySelector('#fu').hidden", timeout=90000)
    r.check("the meeting ends with a follow-up to send", "Send it from the Inbox" in r.pg.inner_text("#fu"), f"took {time.time() - t0:.0f}s")
    r.step("Back on the calendar: the visit is over, so Done works")
    r.set_clock((r.at + timedelta(hours=1)).isoformat() + "+04:00")
    r.be(b, "calendar.html")
    r.pg.wait_for_timeout(800)
    r.pg.locator(".ev:not(.blk)", has_text="Layth").first.click()
    r.pg.wait_for_timeout(500)
    done = r.pg.locator("#detail button", has_text="Done")
    r.check("Done can be pressed after the time", done.is_enabled())
    done.click()
    r.pg.wait_for_timeout(1500)
    r.check("the stage is Viewed", stage() == "Viewed", stage())
    r.step("The lead shows what happened")
    r.be(b, f"inbox.html?chat={PHONE}")
    r.pg.wait_for_timeout(1200)
    prof = r.pg.locator("#prof").inner_text()
    r.check("the summary keeps the client's words", "kitchen is too small" in prof, prof[:200])
    r.check("the broker's words aren't taken as the client's", "structural" not in prof and "pay a bit more" not in prof)
    c = r.chat(PHONE)
    r.check("'maybe we'd go up' changed no figure", not any("go up" in f["text"] for f in c["facts"]), [f["text"][:70] for f in c["facts"]])
    f = c.get("followup")
    r.check("a follow-up is drafted, answering their worry", f and "kitchen" in f["text"].lower(), (f or {}).get("text", "")[:240])
    nova_says(f"How did {NAME}'s viewing go?", r"kitchen|garden|wife|visit|view")
    no_compliance_yet()


def follow_up_and_offers():
    b = r.broker
    r.step("The agent sends the follow-up")
    r.be(b, f"inbox.html?chat={PHONE}")
    r.pg.wait_for_timeout(1000)
    r.check("WhatsApp's 24 hours have passed, so she can't send free text", not r.chat(PHONE).get("window_open"), r.chat(PHONE).get("window_open"))
    r.pg.get_by_role("button", name="Send the after-viewing template").click()
    r.pg.wait_for_timeout(1500)
    r.check("the template went out", r.chat(PHONE)["messages"][-1].get("template") == "after_viewing", r.chat(PHONE)["messages"][-1].get("text", "")[:160])
    r.client_says(PHONE, NAME, "It was nice, the kitchen worries us a little", wait_reply=False)
    r.pg.wait_for_timeout(2500)
    r.be(b, f"inbox.html?chat={PHONE}")
    r.pg.wait_for_timeout(1200)
    r.pg.locator(".followsec button", has_text=re.compile("^Send on", re.I)).first.click()
    r.pg.wait_for_timeout(1500)
    r.check("their reply opens the chat, and the follow-up goes", any(m["type"] == "sent" and "kitchen" in m.get("text", "").lower() for m in r.chat(PHONE)["messages"][-3:]), r.chat(PHONE)["messages"][-1].get("text", "")[:160])
    r.client_says(PHONE, NAME, "We've talked. We'd offer 2.2 million.", wait_reply=False)
    r.pg.wait_for_timeout(2500)
    r.step("Offers: the client's, the seller's counter, and a yes")
    r.be(b, f"inbox.html?chat={PHONE}")
    r.pg.wait_for_timeout(1000)
    sec = r.pg.locator(".offersec")
    r.check("the Offers section is there after a viewing", sec.count())
    sec.get_by_label("Offer amount (AED)").fill("2200000")
    sec.get_by_role("button", name="Save offer").click()
    r.pg.wait_for_timeout(1500)
    r.check("the offer is saved and the stage is Offer", stage() == "Offer" and r.chat(PHONE)["offers"], stage())
    sec = r.pg.locator(".offersec")
    sec.get_by_label("Whose offer").select_option("seller")
    sec.get_by_label("Offer amount (AED)").fill("2350000")
    sec.get_by_role("button", name="Save offer").click()
    r.pg.wait_for_timeout(1500)
    o = r.chat(PHONE)["offers"]
    r.check("the counter replaces it, and both stay on the record", [x["status"] for x in o] == ["declined", "open"], o)
    nova_says(f"Where is the negotiation with {NAME}?", r"2,?350,?000|2\.35")
    r.be(b, f"inbox.html?chat={PHONE}")
    r.pg.wait_for_timeout(1000)
    r.pg.locator(".offersec").get_by_role("button", name="Accept").click()
    r.pg.wait_for_timeout(1500)
    r.check("accepted, with a way to convert at that price", r.pg.locator(".offersec a", has_text="Convert at AED").count())
    no_compliance_yet()


try:
    for name, fn in (("first contact", first_contact), ("qualifying", qualifying), ("asks to view", asks_to_view), ("agent books", agent_books), ("reminders", reminders),
                     ("recorded visit", recorded_visit), ("follow-up and offers", follow_up_and_offers)):
        r.part(name, fn)
except Stop as e:
    print("STOPPED:", e, flush=True)
good, bad, errors = r.finish()
print(f"RESULT {good} passed, {bad} failed")
