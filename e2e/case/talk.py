"""Does talk change the right things? The same kinds of sentence go in through WhatsApp, the recorded meeting, Nova and Pocket. The client's record is read before and after each one,
so what changed, and what must not have, is on the record, and the routes can be compared.

    python e2e/case/talk.py http://127.0.0.1:8040 <out dir>
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run, Stop  # noqa: E402

BASE, OUT = sys.argv[1], sys.argv[2]
r = Run(BASE, OUT, "talk", slow=120)
LEADS = {"whatsapp": ("971507772001", "Mona Haddad"), "meeting": ("971507772002", "Sami Nasser"), "nova": ("971507772003", "Dina Fares"), "pocket": ("971507772004", "Tarek Aziz")}
SET_UP = ("Hi, I'm looking to buy a flat in JVC", "Buying, to live in", "A 2 bed flat", "Budget is about 2 million")


def snap(phone):
    c = r.chat(phone)
    a = {x["key"]: x["value"] for x in c["qualify"]["answers"]}
    return {"budget": a.get("budget_aed"), "beds": a.get("bedrooms"), "finance": a.get("finance"), "facts": [f["text"] for f in c["facts"]], "cards": [x["text"] for x in c["cards"]], "stage": c["stage"], "tasks": [t["text"] for t in c["tasks"]]}


# what was said; {n} is the client's first name, for those who speak about them; what must be true of before and after
SAME = lambda a, b: a["budget"] == b["budget"] and a["beds"] == b["beds"] and a["stage"] == b["stage"]  # noqa: E731
LINES = [
    ("a real change", "I now want 3 bedrooms", "{n} now wants 3 bedrooms", lambda a, b: b["beds"] == 3),
    ("a new budget", "My budget is now 3 million", "{n}'s budget is now 3 million", lambda a, b: b["budget"] == 3000000),
    ("a correction", "Sorry, I meant 4 million, not 3", "{n} said sorry, it's 4 million, not 3", lambda a, b: b["budget"] == 4000000),
    ("only a maybe", "Maybe we could go up to 6 million, I don't know", "{n} might maybe go up to 6 million", SAME),
    ("someone else's price", "My neighbour bought his flat for 9 million", "{n}'s neighbour paid 9 million for his flat", SAME),
    ("random talk", "The football last night was amazing", "The football last night was amazing", SAME),
    ("the weather", "It's so hot in Dubai today", "It's so hot in Dubai today", SAME),
    ("a joke", "Ha, for that price I'd want a helicopter pad", "Ha, for that price I'd want a helicopter pad", SAME),
]


def line_whatsapp(phone, name, said):
    r.client_says(phone, name, said, secs=45)


def line_meeting(phone, name, said):
    if r.pg.url.find("meeting.html") < 0 or not r.pg.locator("#live").is_visible():
        c = r.chat(phone)
        r.be(c["broker"], f"meeting.html?deal={c['deal']}&title=Meeting")
        r.pg.wait_for_timeout(800)
        r.pg.click("#start")
        r.pg.wait_for_timeout(400)
        r.pg.click("#consent")
        r.pg.wait_for_timeout(400)
    r.pg.select_option("#speaker", "customer")
    r.pg.fill("#text", said)
    r.pg.click("#say")
    r.pg.wait_for_timeout(13000)


def line_nova(phone, name, said):
    out = r.ask_nova(said)
    if re.search(r"Yes", out) and re.search(r"Cancel", out):
        out = r.ask_nova("Yes")
    return out


def run(route, fn, speak_as_client):
    phone, name = LEADS[route]
    r.be("layla", "inbox.html")
    r.step(f"{route}: a client to talk about")
    for t in SET_UP:
        r.client_says(phone, name, t, secs=45)
    for kind, client, owner, ok in LINES:
        said = client if speak_as_client else owner.format(n=name.split()[0])
        a = snap(phone)
        r.step(f"{route}, {kind}: {said}", 300)
        fn(phone, name, said)
        r.pg.wait_for_timeout(600)
        b = snap(phone)
        changed = {k: (a[k], b[k]) for k in ("budget", "beds", "stage", "finance") if a[k] != b[k]}
        r.check(f"{route}: {kind}", ok(a, b), f"changed: {changed or 'nothing'}; new facts: {[f[:60] for f in b['facts'] if f not in a['facts']]}; new cards: {[c[:70] for c in b['cards'] if c not in a['cards']]}")


def pocket():
    phone, name = LEADS["pocket"]
    n = name.split()[0]
    r.be("layla", "inbox.html")
    r.step("Pocket: a client to talk about")
    for t in SET_UP:
        r.client_says(phone, name, t, secs=45)
    a = snap(phone)
    r.ask_nova("I'm in a meeting")
    for t in (f"{n} now wants 3 bedrooms.", "Omar will send the floor plans by Thursday.", "We agreed to hold the price this month.", "The football last night was amazing."):
        r.ask_nova(t, secs=8)
    out = r.ask_nova("Meeting is over")
    r.check("the minutes keep the decision", "hold the price" in out, out[:300])
    r.check("the minutes keep the action, with its owner", re.search("Omar", out) and "floor plans" in out, out[:300])
    r.check("random talk isn't an action or a decision", "football" not in out.split("Decisions")[-1] if "Decisions" in out else True, out[:200])
    b = snap(phone)
    r.check("nothing goes on the client's file before a yes", b["beds"] == a["beds"], (a["beds"], b["beds"]))
    r.ask_nova("Yes")
    r.check("on a yes it does", snap(phone)["beds"] == 3, snap(phone)["beds"])
    r.check("the action reached Omar's board", any("floor plans" in str(c) for c in r.owner.get(f"{BASE}/api/lobby").json()) if r.owner.get(f"{BASE}/api/lobby").ok else None)


def stage_talk():
    phone, name = LEADS["nova"]
    n = name.split()[0]
    r.step("Nova is told to do things only people do")
    before = snap(phone)
    for said, must in ((f"Move {n} to Viewed", r"can't|cannot|can not|isn't|not something|from the|inbox|broker"), (f"{n} is lost", r"\?|record|sure|broker|can't"),
                       (f"Mark the deposit received for {n}", r"Finance|Ahmed|can't|person"), ("Approve the discount", r"you|owner|Deal|can't|person|which"), (f"Sign the contract for {n}", r"can't|sign|people|by")):
        out = r.ask_nova(said)
        r.check(f"Nova, told \"{said}\"", re.search(must, out, re.I) and not re.search(r"\bdone\b|\bmoved\b|\bmarked\b", out, re.I), out[:220])
    r.check("none of that moved the client", snap(phone)["stage"] == before["stage"], snap(phone)["stage"])


try:
    r.be("layla", "index.html")
    r.part("whatsapp", lambda: run("whatsapp", line_whatsapp, True))
    r.part("meeting", lambda: run("meeting", line_meeting, True))
    r.part("nova", lambda: run("nova", line_nova, False))
    r.part("stage talk", stage_talk)
    r.part("pocket", pocket)
except Stop as e:
    print("STOPPED:", e, flush=True)
good, bad, errors = r.finish()
print(f"RESULT {good} passed, {bad} failed")
