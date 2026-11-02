"""Everything anyone asks Nova, typed into her real chat box. A reply fails if it's empty, shows a record number, dead-ends, or promises what she can't do. Nothing is sent: WhatsApp
isn't connected and read-backs are cancelled.

    python e2e/case/asks.py http://127.0.0.1:8040 <out dir>
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from browser import Run, Stop  # noqa: E402

BASE, OUT = sys.argv[1], sys.argv[2]
r = Run(BASE, OUT, "asks", slow=60)
BAD = r"\[[A-Z]{1,2}\d+\]|\bverdict:|I'm not sure what you mean|Traceback|undefined|\bnull\b|: None\b|can't reach Muse"
Q = {
    "the day": ["Good morning Nova", "What do I need to know today?", "What's most urgent?", "What should I do first?", "Anything gone wrong overnight?", "What's the plan for tomorrow?", "What did I miss?", "Give me two lines on the office", "Is anything on fire?"],
    "people": ["How is Omar doing?", "What's Hamza working on?", "Who's behind?", "Who's the busiest broker?", "Is Nadia on shift?", "What does Priya have on?", "What's Ahmed waiting for?", "Who hasn't called their leads back?", "Is Rashid doing his job?", "Who should I talk to today?"],
    "leads": ["How many new leads today?", "Which lead should I call first?", "Who are my hot leads?", "Who's waiting for a reply?", "Any leads from Instagram?", "Which leads have gone quiet?", "What do we know about Sara?", "Where does Mona stand?", "Who's in the Pool?", "Which leads came from portals?", "Are any leads stuck?"],
    "deals and stages": ["Which deals are stuck?", "What's next on the Marina deal?", "Which deal is closest to closing?", "How many deals are at Form F?", "What's waiting on Compliance?", "What's waiting on Finance?", "What's waiting on me?", "Any deal with a problem?", "What stage is the Marina deal at?"],
    "money": ["How much commission is due?", "What's the pipeline worth?", "Any overdue invoices?", "How much did we make this month?", "How much did we spend on ads?", "What's our best lead source?", "Which broker made the most?"],
    "calendar": ["What's on my calendar today?", "Am I free tomorrow at 3pm?", "What's my week like?", "What viewings are on tomorrow?", "When's my next meeting?", "Any clashes this week?"],
    "follow-up talk": ["What about him?", "And the other one?", "Why?", "Tell me more", "Same for Nadia", "What do you mean?"],
    "advice": ["Should I give a discount on the Marina flat?", "Should I hire another broker?", "What would you do about the stalled leads?", "Is the team on track?", "What's the biggest risk right now?", "How can we close more this month?"],
    "the outside world": ["What's the weather in Dubai?", "How long is the drive to the Marina at 5pm?", "What's the time in London?", "Flights to Riyadh next Monday?", "What's the news on Dubai property?", "What's DLD's transfer fee?"],
    "language": ["شو عندي اليوم؟", "كيف الشغل اليوم؟", "Kya haal hai office ka?", "Aaj kitne leads aaye?", "Quel est le plan aujourd'hui?"],
    "can't do": ["Book me a flight to London", "Open my Gmail", "Call Mona for me", "Transfer 10000 dirhams to Omar", "Sign the Marina contract", "File the report", "Clear the screening", "Change Rania's settings", "Delete all the leads"],
    "odd": ["hello", "are you there", "thanks", "ok", "lol", "?", "asdfgh", "tell me a joke", "who are you", "what can you do", "do you love me", "shut up"],
}
STAFF = {"omar": ["What's on my plate?", "Who should I call first?", "What's my calendar today?", "What did the owner's mum say?", "What's Hamza's commission?"],
         "ahmed": ["What's waiting on me?", "Any overdue invoices?", "Which deal has a deposit due?", "What's the compliance status of the Marina deal?"],
         "priya": ["What needs clearing?", "Any screening hits?", "What's the owner's personal WhatsApp say?"],
         "maya": ["What's my plan this week?", "How are the posts doing?", "What's in the Marina deal?"], "joseph": ["What's waiting on me?", "Which Form F is next?"]}
NEVER_FOR_STAFF = {"What did the owner's mum say?", "What's the owner's personal WhatsApp say?", "What's Hamza's commission?", "What's in the Marina deal?"}
MUST = {"Delete all the leads": r"gets deleted", "Who hasn't called their leads back?": r"owes|Nobody owes a call", "Is Nadia on shift?": r"\b(yes|no|she is|she's|not on|on shift)\b(?!.*roster)",
        "Who's in the Pool?": r"Pool|nobody|no one", "Am I free tomorrow at 3pm?": r"free|you have"}


def pa(who, text):
    """Staff have her in the Ask your PA panel on every page."""
    r.be(who)
    if r.pg.locator(".pa-panel").is_hidden():
        r.pg.locator(".pa-open").click()
    box = r.pg.get_by_label("Ask your PA")
    n = r.pg.locator(".pa-log > *").count()
    box.fill(text)
    box.press("Enter")
    r.pg.wait_for_function(f"document.querySelectorAll('.pa-log > *').length >= {n + 2}", timeout=70000)
    r.pg.wait_for_timeout(600)
    return r.pg.locator(".pa-log > *").last.inner_text()


def judge(group, q, said):
    bad = re.search(BAD, said)
    empty = len(said.strip()) < 2
    rule = MUST.get(q)
    r.check(f"[{group}] {q}", not bad and not empty and (not rule or re.search(rule, said, re.I)), said[:300].replace("\n", " "))


try:
    r.be("layla", "index.html")
    for group, qs in Q.items():
        r.pg.goto(f"{BASE}/web/index.html")  # a fresh page each group: a person doesn't keep one tab for 100 questions either
        r.pg.wait_for_timeout(900)
        print("HEAP", r.pg.evaluate("Math.round((performance.memory || {usedJSHeapSize: 0}).usedJSHeapSize / 1e6)"), "MB, on the page:", r.pg.evaluate("document.querySelectorAll('*').length"), flush=True)
        r.step(f"Nova: {group}", 400)
        for q in qs:
            out = []
            r.part(q, lambda g=group, x=q: (out.append(r.ask_nova(x, secs=75)), judge(g, x, out[-1])))
            if out and "Cancel" in out[-1]:
                r.ask_nova("cancel", secs=30)
    home = {"omar": "sales.html", "ahmed": "deal.html", "priya": "deal.html", "maya": "studio.html", "joseph": "deal.html"}
    for who, qs in STAFF.items():
        r.be(who, home[who])
        r.step(f"{who}'s PA: only what their role may see", 400)
        for q in qs:
            def one(w=who, x=q):
                said = pa(w, x)
                r.check(f"[{w}] {x}", not re.search(BAD, said) and (x not in NEVER_FOR_STAFF or not re.search(r"\bAED\b|\d{3},\d{3}|Habibti", said)), said[:200].replace("\n", " "))
            r.part(q, one)
except Stop as e:
    print("STOPPED:", e, flush=True)
good, bad, errors = r.finish()
print(f"RESULT {good} passed, {bad} failed")
