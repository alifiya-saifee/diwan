"""A real meeting through the real microphone path: a spoken conversation is fed to Edge as its microphone, goes through Muse Voice Transcribe, and the record is read after.

    CASE_ARGS="--use-fake-ui-for-media-stream|--use-fake-device-for-media-stream|--use-file-for-fake-audio-capture=<wav>%noloop" python e2e/case/mic.py http://127.0.0.1:8040 <out dir> <seconds>
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run, Stop  # noqa: E402

BASE, OUT, SECS = sys.argv[1], sys.argv[2], int(sys.argv[3])
r = Run(BASE, OUT, "mic", slow=150)
PHONE, NAME = "971507775001", "Hana Sabry"


def go():
    r.be("layla", "inbox.html")
    r.step("A client to meet")
    for t in ("Hi, I'm looking to buy a flat in JVC", "Buying, to live in", "A 2 bed flat", "Budget is about 2 million"):
        r.client_says(PHONE, NAME, t, secs=45)
    c = r.chat(PHONE)
    start = {x["key"]: x["value"] for x in c["qualify"]["answers"]}
    r.be(c["broker"], f"meeting.html?deal={c['deal']}&title=Viewing")
    r.pg.wait_for_timeout(900)
    r.step("Recorded through the microphone: broker and client talking")
    r.pg.click("#start")
    r.pg.wait_for_timeout(500)
    r.pg.click("#consent")
    r.pg.wait_for_timeout(500)
    r.pg.click("#mic")
    r.pg.wait_for_timeout(1500)
    r.check("the microphone starts listening", "Stop" in r.pg.inner_text("#mic"), r.pg.inner_text("#micstate"))
    r.pg.wait_for_timeout(SECS * 1000)
    turns = r.pg.locator("#turns .turn").all_inner_texts()
    print("TURNS", turns, flush=True)
    r.check("what was said reaches the screen", len(turns) >= 2, turns[:6])
    r.check("speakers are told apart", {"Client", "Broker"} <= {t.split(":")[0] for t in turns}, sorted({t.split(":")[0] for t in turns}))
    r.pg.click("#mic")
    r.pg.wait_for_timeout(2500)
    r.pg.click("#end")
    r.pg.wait_for_timeout(9000)
    c = r.chat(PHONE)
    now = {x["key"]: x["value"] for x in c["qualify"]["answers"]}
    print("BEFORE", start, "\nAFTER", now, "\nFACTS", [f["text"] for f in c["facts"]], "\nTASKS", [t["text"] for t in c["tasks"]], flush=True)
    r.check("the client's new bedrooms changed the record", now.get("bedrooms") == 3, now.get("bedrooms"))
    r.check("the client's new budget changed the record", now.get("budget_aed") == 3000000, now.get("budget_aed"))
    r.check("the football isn't a fact", not any(re.search("football", f["text"], re.I) for f in c["facts"]))
    r.check("the broker's promise isn't the client's fact", not any(re.search("floor plans", f["text"], re.I) for f in c["facts"]))
    page = r.pg.evaluate("document.body.innerText")
    r.check("a follow-up was written", re.search("Follow-up drafter|Send it from the Inbox", page), page[-200:])
    heard = [e["content"] for e in r.owner.get(f"{BASE}/api/events?deal={c['deal']}").json() if e["type"] == "utterance"]
    print("HEARD", [(e.get("speaker"), e.get("text")) for e in heard], flush=True)
    r.check("at least 4 of the 5 things said were heard", len(heard) >= 4, len(heard))
    r.check("the property type stayed what the client said", now.get("property_type") == "Apartment", now.get("property_type"))
    v = r.ask_nova(f"What did {NAME.split()[0]} say in the meeting?")
    r.check("Nova knows what was said", re.search("3 bed|three bed|3 million|3,000,000|three million", v, re.I) and not re.search("don't have a meeting|no meeting|don't have any meeting", v), v[:220])


try:
    r.part("microphone meeting", go)
except Stop as e:
    print("STOPPED:", e, flush=True)
good, bad, errors = r.finish()
print(f"RESULT {good} passed, {bad} failed")
