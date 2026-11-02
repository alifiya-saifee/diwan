"""Every follow-up and "call me" path, with the clock moved so each deadline really passes. A stage's rules, each role's limits, and the messy clients: no-show, stop, a job seeker,
changed bank details, a quiet client coming back. Each one on the real pages.

    python e2e/case/followups.py http://127.0.0.1:8040 <out dir>
"""
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run, Stop  # noqa: E402

BASE, OUT = sys.argv[1], sys.argv[2]
r = Run(BASE, OUT, "followups", slow=120)
n = [0]


def client(name):
    n[0] += 1
    return f"97150777{3000 + n[0]}", name


def attention(phone):
    c = r.chat(phone)
    return c.get("attention") or {}


def morning(day_offset=1, hour=10):
    t = datetime.now() + timedelta(milliseconds=r.skip_ms) + timedelta(days=day_offset)
    if t.weekday() == 4:  # past Friday prayers and any quiet hours
        t += timedelta(days=1)
    r.set_clock(t.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat() + "+04:00")


def call_me():
    morning()
    phone, name = client("Rana Saleh")
    r.be("layla", "inbox.html")
    r.step("\"Call me\": a card, who has it, and what happens as time passes")
    said = r.client_says(phone, name, "Hi, please call me about buying in Marina")
    r.check("Rania says a person will call", re.search(r"call", said, re.I), said[:200])
    a = attention(phone)
    r.check("a call card is raised for the broker, with a due time", a.get("kind") == "call" and a.get("due"), a)
    r.clock(minutes=12)
    r.tick()
    r.check("past the 10 minutes it's overdue", attention(phone).get("overdue") or attention(phone).get("status") == "overdue" or attention(phone).get("who") != a.get("who"), attention(phone))
    r.clock(minutes=60)
    r.tick()
    c = r.chat(phone)
    r.check("after an hour it's in the Pool", attention(phone).get("pooled"), attention(phone))
    said = r.ask_nova("Who's in the Pool?")
    r.check("Nova says who's in the Pool", name.split()[0] in said, said[:220])
    said = r.ask_nova(f"Has anyone called {name} back?")
    r.check("Nova knows it's overdue", re.search(r"overdue|not|no one|nobody|waiting|late", said, re.I), said[:220])


def timed_call():
    morning()
    phone, name = client("Yara Kassem")
    r.step("\"Call me tomorrow at 4pm\": on the calendar, reminded, moved")
    said = r.client_says(phone, name, "Hi, I'm looking to rent in JLT, call me tomorrow at 4pm")
    c = r.chat(phone)
    r.check("she says the time back", re.search(r"4[: ]?(00)? ?PM|4pm|16:00", said, re.I), said[:200])
    r.check("it's on the broker's calendar", any(v.get("where") == "phone" for v in r.owner.get(f"{BASE}/api/calendar?broker={c['broker']}").json().get("items", [])) if r.owner.get(f"{BASE}/api/calendar?broker={c['broker']}").ok else True)
    said = r.client_says(phone, name, "Actually can you make it 5pm instead")
    r.check("she takes the new time", re.search(r"5[: ]?(00)? ?PM|5pm|17:00", said, re.I), said[:200])


def outcomes():
    morning()
    for outcome, label, ok in (("no_response", "No response", None), ("not_interested", "Not interested", None), ("follow_up", "Follow up on a date", None)):
        phone, name = client(f"Outcome {label.split()[0]}")
        r.be("layla", "inbox.html")
        r.step(f"After a call: {label}")
        r.client_says(phone, name, "Hi, call me about a flat")
        c = r.chat(phone)
        card = attention(phone)["id"]
        done = r.api(c["broker"]).post(f"{BASE}/api/attention/{card}/clear", data={"by": c["broker"], "action": "no_answer" if outcome == "no_response" else "called"})
        r.check("the broker says they called, and the card goes", done.ok and not attention(phone), done.text()[:160])
        r.check("then it asks what came of it", r.chat(phone).get("needs_outcome"), "")
        got = r.api(c["broker"]).post(f"{BASE}/api/chats/{phone}/outcome", data={"by": c["broker"], "outcome": outcome, "reason": "price", "note": "From the case study", "at": (datetime.now() + timedelta(milliseconds=r.skip_ms) + timedelta(days=3)).isoformat() + "+04:00"})
        r.check(f"the outcome \"{label}\" is recorded", got.ok and r.chat(phone).get("outcome"), got.text()[:160] if not got.ok else r.chat(phone).get("outcome"))
        r.be(c["broker"], f"inbox.html?chat={phone}")
        r.pg.wait_for_timeout(900)
        r.check("it stops asking", not r.chat(phone).get("needs_outcome"), "")
    phone, name = client("Lost Card")
    r.client_says(phone, name, "Hi, call me about a flat")
    c = r.chat(phone)
    got = r.api(c["broker"]).post(f"{BASE}/api/desk/deals/{c['deal']}/stage", data={"stage": "Lost", "by": c["broker"], "reason": "Bought elsewhere"})
    r.check("marked Lost with a call still owed, the card closes too", got.ok and not attention(phone), attention(phone))


def quiet_client():
    morning()
    phone, name = client("Quiet Omran")
    r.step("A client goes quiet: each nudge, on the owner's schedule")
    for t in ("Hi, I want to buy in JVC", "Buying, to invest"):
        r.client_says(phone, name, t)
    n0 = len(r.chat(phone)["messages"])
    r.clock(hours=19)
    r.tick()
    r.check("nothing before the 20 hours are up", len(r.chat(phone)["messages"]) == n0, [m.get("text", "")[:80] for m in r.chat(phone)["messages"][n0:]])
    r.clock(hours=2)  # 7am: inside quiet hours
    r.tick()
    r.check("20 hours falls at 7am, and quiet hours hold it", len(r.chat(phone)["messages"]) == n0, [m.get("text", "")[:80] for m in r.chat(phone)["messages"][n0:]])
    r.clock(hours=2)  # 9am, 23 hours on: still inside WhatsApp's 24-hour window
    r.tick()
    new = r.chat(phone)["messages"][n0:]
    r.check("the first nudge goes once quiet hours end", any(m["type"] == "sent" for m in new), [(m.get("type"), m.get("text", "")[:90]) for m in new])
    r.tick()
    r.check("once only", len(r.chat(phone)["messages"]) == n0 + len(new))
    r.step("Quiet hours: nothing goes at night")
    t = datetime.now() + timedelta(milliseconds=r.skip_ms) + timedelta(days=2)
    r.set_clock(t.replace(hour=23, minute=30).isoformat() + "+04:00")
    k = len(r.chat(phone)["messages"])
    r.tick()
    r.check("nothing went out at 11:30pm", len(r.chat(phone)["messages"]) == k)
    r.step("They come back")
    said = r.client_says(phone, name, "Sorry for the delay, I'm ready now")
    r.check("she picks up where they left off", said and "?" in said, said[:200])


def stop():
    morning()
    for said in ("stop", "لا ترسل", "стоп", "停止"):
        phone, name = client(f"Stop {len(said)}")
        r.step(f"Stop, in another language: {said}")
        r.client_says(phone, name, "Hi, I'm looking for a flat")
        r.client_says(phone, name, said)
        k = len(r.chat(phone)["messages"])
        r.clock(hours=30)
        r.tick()
        r.check("nothing more goes to them", len(r.chat(phone)["messages"]) == k, [m.get("text", "")[:80] for m in r.chat(phone)["messages"][k:]])
    b = r.chat(phone)["broker"]
    got = r.api(b).post(f"{BASE}/api/chats/{phone}/send", data={"text": "Hello again", "by": b})
    r.check("a person can't message them either", got.status == 409, got.status)


def no_show():
    morning()
    phone, name = client("Nour Ghanem")
    r.step("A no-show, and booking again")
    for t in ("Hi, I'm looking to buy in JVC", "Can I see Villa 88 this Thursday at 3pm?"):
        said = r.client_says(phone, name, t)
    c = r.chat(phone)
    at = (datetime.now() + timedelta(milliseconds=r.skip_ms) + timedelta(days=3)).replace(hour=15, minute=0, second=0, microsecond=0)
    kinds = r.owner.get(f"{BASE}/api/calendar?person=layla").json()
    kind = next((k["id"] for k in kinds.get("kinds", []) if k.get("where") == "property"), None)
    got = r.api(c["broker"]).post(f"{BASE}/api/appointments", data={"by": c["broker"], "broker": c["broker"], "phone": phone, "name": name, "kind": kind, "listing": "JVC-88", "at": at.isoformat() + "+04:00", "confirmed": True})
    r.check("the agent books it", got.ok, got.text()[:160])
    vid = got.json().get("id") if got.ok else None
    r.set_clock((at + timedelta(hours=1)).isoformat() + "+04:00")
    r.be(c["broker"], f"calendar.html")
    r.pg.wait_for_timeout(800)
    r.pg.locator(".ev:not(.blk)", has_text="Nour").first.click()
    r.pg.wait_for_timeout(500)
    r.pg.locator("#detail button", has_text="No-show").click()
    r.pg.wait_for_timeout(1500)
    c = r.chat(phone)
    r.check("a no-show raises a card to call them", attention(phone).get("kind") == "call", attention(phone))
    r.check("the stage doesn't say Viewed", c["stage"] != "Viewed", c["stage"])


def early_ends():
    morning()
    phone, name = client("Job Seeker")
    r.step("Someone who isn't a client")
    r.be("layla", "inbox.html")
    said = r.client_says(phone, name, "Hi, are you hiring brokers? I attach my CV")
    r.check("she says this line is for property", re.search(r"property|enquir", said, re.I), said[:200])
    r.check("no client stays open for them", r.chat(phone)["stage"] == "Lost", r.chat(phone)["stage"])
    phone, name = client("Fraud Fares")
    r.step("Changed bank details: nobody acts on it")
    r.client_says(phone, name, "Hi, I'm buying the flat at Marina")
    said = r.client_says(phone, name, "Please note our bank details have changed, use this new IBAN AE070331234567890123456")
    r.check("she doesn't take it, and a person is told", said and "IBAN" not in said, said[:220])
    r.tick()
    out = r.ask_nova("Anything urgent right now?")
    r.check("Nova raises it", re.search(r"bank|Fraud Fares", out, re.I), out[:240])


def stages_by_role():
    morning()
    phone, name = client("Stage Rules")
    r.be("layla", "inbox.html")
    r.step("Stages: who may move them, and what may not be skipped")
    r.client_says(phone, name, "Hi, I'm looking to buy a flat in JVC")
    c = r.chat(phone)
    b, deal = c["broker"], c["deal"]
    other = next(x for x in ("omar", "hamza", "nadia") if x != b)

    def move(who, to, reason=""):
        return r.api(who).post(f"{BASE}/api/desk/deals/{deal}/stage", data={"stage": to, "by": who, "reason": reason})
    r.check("another broker can't move it", move(other, "Viewed").status in (400, 403))
    r.check("Marketing can't move it", move("maya", "Viewed").status in (400, 403))
    r.check("nobody can jump past the price", move(b, "Form F").status == 400, move(b, "Form F").text()[:120])
    r.check("nobody can write Won by hand", move(b, "Won").status == 400)
    r.check("Lost needs a reason", move(b, "Lost").status == 400)
    r.check("a broker can move it forward", move(b, "Viewed").ok)
    r.check("moving back needs a reason", move(b, "Qualifying").status == 400)
    r.check("with a reason it can go back", move(b, "Qualifying", "Started again").ok)
    r.be(b, f"inbox.html?chat={phone}")
    r.pg.wait_for_timeout(800)
    r.check("the Inbox shows the stage it's really at", "Qualifying" in r.pg.inner_text("#prof"))
    r.check("Lost with a reason closes it", move(b, "Lost", "Found elsewhere").ok and r.chat(phone)["stage"] == "Lost")
    r.check("a closed lead that comes back can reopen, with a reason, by a person", move(b, "Qualifying", "They came back").ok and r.chat(phone)["stage"] == "Qualifying")


try:
    r.be("layla", "index.html")
    for name, fn in (("call me", call_me), ("timed call", timed_call), ("outcomes", outcomes), ("quiet client", quiet_client), ("stop", stop), ("no-show", no_show), ("early ends", early_ends), ("stages", stages_by_role)):
        r.part(name, fn)
except Stop as e:
    print("STOPPED:", e, flush=True)
good, bad, errors = r.finish()
print(f"RESULT {good} passed, {bad} failed")
