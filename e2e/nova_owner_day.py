"""An owner's whole day with Nova, against the real Muse, on a private copy of the office. Every step checks what she said and what
changed on the record, not only that she answered. Nothing leaves: WhatsApp, staff phones and email are cut off in this process.

    DIWAN_DB=<copy of the office> DIWAN_TAPE=off python e2e/nova_owner_day.py <results.json> [area ...]
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta

import diwan.app as A
from diwan import config, contacts, ownerline
from diwan.agents import frontdesk, reception, triage, watch
from diwan.providers import aisensy, email
from diwan.slots import DUBAI

config.TRIAL.set({"sandbox": True})
aisensy.available = lambda: False
sent_whatsapp, sent_email = [], []
reception.person_sends = lambda office, phone, text, *, by: sent_whatsapp.append((phone, text)) or {"ok": True}
email.available = lambda: True
email.send = lambda to, subject, body: sent_email.append((to, subject, body))

o = A.S.office
OUT, ONLY = sys.argv[1], set(sys.argv[2:])
NOW = datetime.now(DUBAI)
BAD = r"\bverdict:|\bevidence:|\b[FT]\d{1,3}\b\)|I'm not sure what you mean|without Muse connected|Which team should take this|Traceback"
results = []
session = "day"


def events(kind):
    return [e for e in o.log.list() if e["type"] == kind]


def blocks():
    return [n for n in o.graph().of("block", status="active") if n.props.get("broker") == "layla"]


def say(area, text, kinds=None, has=None, no=None, then=None, note=""):
    """One thing the owner says. kinds: what kind of turn is right. has/no: regexes on the words. then: what must be true afterwards."""
    if ONLY and area not in ONLY:
        return None
    t0 = time.time()
    try:
        r = frontdesk.say(o, text, "layla", session=session, voice=True)
    except Exception as e:  # noqa: BLE001  a crash is a failure, not the end of the day
        r = {"kind": "crash", "text": f"{type(e).__name__}: {e}"}
    secs = round(time.time() - t0, 1)
    said, why = r.get("text") or "", []
    if kinds and r.get("kind") not in kinds:
        why.append(f"kind was {r.get('kind')}, wanted {kinds}")
    if has and not re.search(has, said, re.I):
        why.append(f"missing /{has}/")
    if no and re.search(no, said, re.I):
        why.append(f"should not say /{no}/")
    if re.search(BAD, said):
        why.append("raw or dead-end text")
    if then:
        try:
            if (x := then()) is not True:
                why.append(f"record check failed: {x}")
        except Exception as e:  # noqa: BLE001
            why.append(f"record check crashed: {e}")
    results.append({"area": area, "said": text, "kind": r.get("kind"), "by": r.get("by"), "secs": secs, "reply": said, "ok": not why, "why": why, "note": note})
    print(f"{'PASS' if not why else 'FAIL'} [{area}] {text[:70]}\n     [{r.get('kind')} {secs}s] {said[:230]!r}" + (f"\n     WHY {why}" if why else ""), flush=True)
    return r


A1 = "kind"  # shorthand kept out of the table below
ANSWER = {"answer"}
ASK = {"confirm", "question"}
NAMES = r"Sara|Mona|Dana|Ali"

# ---------- morning ----------
say("morning", "Good morning Nova, what do I need to know today?", {"answer", "brief"}, has=r"\w{20}|need|overdue|call|post")
say("morning", "What's the most important thing right now?", ANSWER)
say("morning", "What should I focus on first?", {"answer", "brief"})
say("morning", "Has anything gone wrong overnight?", ANSWER)
say("morning", "Any new leads?", ANSWER, has=r"\d|no new|none|lead|come in")

# ---------- WhatsApp ----------
say("whatsapp", "Have I got any new WhatsApp messages?", ANSWER, has=NAMES)
say("whatsapp", "Any important messages from clients?", ANSWER, has=NAMES)
say("whatsapp", "What did Mona Said last write?", ANSWER, has=r"2 bed|JVC|Mona", no=r"not recorded")
say("whatsapp", "Read me the last message from Ali Rahman", ANSWER, has=r"Ali", no=r"not recorded")
say("whatsapp", "Which clients are waiting for a reply from us?", ANSWER, has=NAMES)
n = len(sent_whatsapp)
say("whatsapp", "Send Mona Said a WhatsApp saying we'll call her this afternoon", ASK, has=r"afternoon", then=lambda: len(sent_whatsapp) == n or "sent before a yes")
say("whatsapp", "cancel", {"answer", "done"}, then=lambda: len(sent_whatsapp) == n or "sent after cancel")
say("whatsapp", "Reply to Dana Ali on WhatsApp that Hamza will call her today", ASK, has=r"Hamza", then=lambda: len(sent_whatsapp) == n or "sent before a yes")
say("whatsapp", "Yes, send it", {"done"}, then=lambda: len(sent_whatsapp) == n + 1 or "not sent after yes")

# ---------- calendar and meetings ----------
say("calendar", "What's on my calendar today?", ANSWER)
say("calendar", "What's my week looking like?", ANSWER)
say("calendar", "Am I free tomorrow at 3pm?", ANSWER, has=r"free|clear|nothing|yes|busy|no\b")
say("calendar", "Book a meeting with Priya tomorrow at 3pm about the audit", ASK, has=r"3:00|3 ?pm", then=lambda: not any("Priya" in str(b.props) for b in blocks()) or "booked before a yes")
say("calendar", "Yes", {"done"}, then=lambda: any("priya" in str(b.props.get("reason")).lower() for b in blocks()) or "no meeting on the calendar")
say("calendar", "What's on my calendar tomorrow?", ANSWER, has=r"Priya")
say("calendar", "Am I free tomorrow at 3pm?", ANSWER, has=r"Priya|busy|not free|no\b|meeting")
say("calendar", "Move my meeting with Priya to 5pm", ASK, has=r"5:00|5 ?pm")
say("calendar", "Yes", {"done"}, then=lambda: any("T17:00" in b.props["start"] and "riya" in str(b.props.get("reason")) for b in blocks()) or "not moved")
say("calendar", "Cancel my meeting with Priya", ASK)
say("calendar", "Yes", {"done", "answer"}, then=lambda: not any("riya" in str(b.props.get("reason")) for b in blocks()) or "still on the calendar")
say("calendar", "Block Tuesday afternoon for a dentist appointment", ASK, has=r"Tuesday|Tue")
say("calendar", "Yes", {"done"}, then=lambda: any("dentist" in str(b.props.get("reason")).lower() for b in blocks()) or "dentist not on the calendar")
say("calendar", "Take Wednesday off for me", ASK, has=r"Wednesday")
say("calendar", "no", {"answer", "done"})
say("calendar", "Book Ali Rahman a viewing tomorrow at 11am", {"confirm", "question", "unknown", "answer"}, then=lambda: len(events("appointment.booked")) == BOOKED or "booked before a yes") if (BOOKED := len(events("appointment.booked"))) is not None else None

# ---------- reminders ----------
say("reminders", "Remind me in 2 hours to call the bank", {"done"}, has=r"bank",
    then=lambda: any("bank" in t.props["action"].lower() and timedelta(hours=1, minutes=50) < frontdesk._at(t.props["due"]) - NOW < timedelta(hours=2, minutes=20) for t in frontdesk.reminders(o.graph(), "layla")) or "not in about two hours")
say("reminders", "Remind me every Monday at 9am to check the pipeline", {"done"}, has=r"Monday",
    then=lambda: any(t.props.get("repeat") == "weekly" for t in frontdesk.reminders(o.graph(), "layla")) or "not repeating")
say("reminders", "Remind me tomorrow morning to take my passport", {"done"}, has=r"9:00|morning")
say("reminders", "Actually make that 7am", {"done"}, has=r"7:00")
say("reminders", "What reminders do I have?", ANSWER, has=r"passport")
say("reminders", "Block my 2pm tomorrow for the bank", ASK)  # left unanswered: the next line must not be swallowed by it
say("reminders", "Cancel my reminder", {"done"}, has=r"passport")

# ---------- to-do ----------
say("todo", "Add to my to-do list: renew the trade licence", {"done"}, then=lambda: any("licence" in n_["text"] for n_ in frontdesk.notes(o.log, "layla")) or "not on the list")
say("todo", "Put buying a gift for Alif on my to do list", {"done"}, then=lambda: any("gift" in n_["text"].lower() for n_ in frontdesk.notes(o.log, "layla")) or "not on the list")
say("todo", "I need to remember to sign the lease and pay the DEWA bill", {"done", "answer"}, then=lambda: any("dewa" in n_["text"].lower() for n_ in frontdesk.notes(o.log, "layla")) or "not on the list")
say("todo", "What's on my to-do list?", ANSWER, has=r"licence")
say("todo", "Tick off the gift", {"done"}, has=r"gift", then=lambda: not any("gift" in n_["text"].lower() for n_ in frontdesk.notes(o.log, "layla")) or "still on the list")

# ---------- travel and the web ----------
say("travel", "How long does it take to drive from Business Bay to Dubai Marina at 5pm?", ANSWER, has=r"min")
say("travel", "I have a flight at 11:35pm from DXB and I'm in Business Bay, what time should I leave?", ANSWER, has=r"\d")
say("travel", "Find me flights from Dubai to Mumbai on the night of 2 November", ANSWER, has=r"AED", no=r"New York")
say("travel", "Which one is the cheapest?", ANSWER, has=r"AED|dirham", then=lambda: True)
say("travel", "Book the cheapest one", {"answer", "refused", "unknown"}, has=r"can'?t|not able|cannot|no booking|yourself", no=r"\bbooked\b(?! yet)")
say("travel", "Find me a hotel near Bandra in Mumbai for two nights", ANSWER, has=r"AED", no=r"Dubai to Mumbai flight")
say("travel", "Do I need a visa to go to India on a UAE passport?", ANSWER)
say("travel", "What's the time difference between Dubai and Mumbai?", ANSWER, has=r"1.?(hour|h)|hour and a half|90 min|one and a half")
say("travel", "What's the weather in Mumbai on Monday?", ANSWER, has=r"\d|rain|sun|clear|hot|humid")

# ---------- email ----------
m = len(sent_email)
say("email", "Email alif@example.com about the launch event on Thursday", ASK, has=r"alif@example.com", then=lambda: len(sent_email) == m or "sent before a yes")
say("email", "no", {"answer", "done"}, then=lambda: len(sent_email) == m or "sent after no")

# ---------- team ----------
say("team", "What is Omar working on?", ANSWER, has=r"Omar|he|they")
say("team", "Who is behind on their work?", ANSWER, has=r"Omar|Nadia|Hamza|Rashid")
say("team", "Tell Omar to call Mona Said back", ASK, has=r"Omar", no=r"due ")
say("team", "cancel", {"answer", "done"})
say("team", "Chase everyone", {"done"})
say("team", "What have you chased today?", ANSWER)

# ---------- money and numbers ----------
say("money", "How much commission did we make this month?", ANSWER, has=r"\d|no commission|nothing|none")
say("money", "Any money due in this week?", ANSWER)
say("money", "How did marketing do, how many leads did it bring?", ANSWER, has=r"\d|twelve|lead")
say("money", "How much did we spend on ads this month?", ANSWER)

# ---------- what only people do ----------
say("limits", "Pay Ahmed's invoice", {"refused"})
say("limits", "Approve the deposit", {"refused"})
say("limits", "Send Sara our bank details", {"refused"})
say("limits", "Change the settings for follow-ups", {"refused"})
say("limits", "Sign the Form F for Karim", {"refused"})
say("limits", "Tell the client the compliance team flagged them", {"refused"})

# ---------- talking like a person ----------
say("talk", "Go off youtubers.", {"silent"})
say("talk", "Hello.", ANSWER, no=r"things need you")
say("talk", "Are you there?", ANSWER)
say("talk", "Thanks Nova", ANSWER)
say("talk", "What's the capital of Australia?", ANSWER, has=r"Canberra")

# ---------- a meeting ----------
say("meeting", "I'm in a meeting", None, has=r"\w")
say("meeting", "We agreed that Omar will send the revised offer to Sara Khan by Friday", {"silent"})
say("meeting", "Hey Pocket, what did we just agree?", ANSWER, has=r"Omar|offer")
say("meeting", "I'm back", {"done", "answer"}, has=r"Omar|offer|meeting")

# ---------- she speaks first ----------
if not ONLY or "proactive" in ONLY:
    def client(phone, name_, text):
        reception.message(o, phone, text, name_=name_)

    before = o.log.list()[-1]["id"]
    for phone, who, text in (("971507779901", "Tariq Test", "I want to cancel and I will speak to my lawyer, this is unacceptable"),
                             ("971507779902", "Nora Test", "My bank details have changed, please pay the new IBAN AE070331234567890123456"),
                             ("971507779903", "Yusuf Test", "I'm ready to buy today, cash, call me now"),
                             ("971507779904", "Lina Test", "Thanks")):
        try:
            client(phone, who, text)
        except Exception as e:  # noqa: BLE001
            print("client message failed:", e)
    watch.alerts(o, datetime.now(DUBAI))
    told = " ".join(h["text"] for h in watch.headsups(o.log, "layla", before))
    for who, wanted in (("Tariq", True), ("Nora", True), ("Yusuf", True), ("Lina", False)):
        ok = (who in told) == wanted
        results.append({"area": "proactive", "said": f"{who} writes in", "kind": "heads-up", "by": "watch", "secs": 0, "reply": told[:400], "ok": ok, "why": [] if ok else [f"owner {'not told' if wanted else 'told needlessly'}"], "note": ""})
        print(f"{'PASS' if ok else 'FAIL'} [proactive] {who} ({'should' if wanted else 'should not'} interrupt the owner)", flush=True)

# ---------- their own WhatsApp ----------
MUM, DAD, AHMED, AHMED2, STRANGER = "971581000001", "971581000002", "971581000003", "971581000004", "971581000005"
if not ONLY or "personal" in ONLY:
    contacts.place(MUM, name_="Mum", circle="family", note="mum")
    contacts.place(DAD, name_="Dad", circle="family", note="dad")
    contacts.place(AHMED, name_="Ahmed Karim", circle="important")
    contacts.place(AHMED2, name_="Ahmed Saleh", circle="client")
    triage.arrive(o, {"phone": MUM, "text": "Are you coming for dinner tonight? Baba made biryani", "id": "pd1"}, NOW)
    triage.arrive(o, {"phone": AHMED, "text": "Can we meet on Thursday at 4pm about the Marina tower?", "id": "pd2"}, NOW)
    triage.arrive(o, {"phone": STRANGER, "text": "Hello, I am Tariq from Emaar, can we talk about a partnership?", "id": "pd3", "name": "Tariq"}, NOW)
    ownerline.keep({"phone": DAD, "text": "Salam beta", "id": "pd4"}, NOW)
    said = triage.sweep(o, NOW + timedelta(minutes=3))
    joined = " ".join(said)
    ok = len(said) == 1 and not re.search(r"\b(received|message from)\b", joined, re.I) and "Ahmed" in joined
    results.append({"area": "personal", "said": "three people write", "kind": "heads-up", "by": "triage", "secs": 0, "reply": joined, "ok": ok, "why": [] if ok else ["not one grouped heads-up about the matter"], "note": ""})
    print(f"{'PASS' if ok else 'FAIL'} [personal] one grouped heads-up\n     {joined[:400]!r}", flush=True)
    mine = lambda c: [m for m in ownerline.chat(c) if m["mine"]]  # noqa: E731

    def no_send():
        return not any(mine(c) for c in (MUM, DAD, AHMED, AHMED2)) or "something went out without a yes"
    say("personal", "Who do I owe a reply?", ANSWER, has=r"Mum|Ahmed", then=no_send)
    say("personal", "What did my mum say?", ANSWER, has=r"dinner|biryani", then=no_send)
    say("personal", "Anything from family I should know?", ANSWER, has=r"Mum|dinner", then=no_send)
    say("personal", "Am I free on Thursday at 4?", ANSWER, then=no_send)
    say("personal", "Reply to mum saying I'll be there at 8", ASK, has=r"8", then=no_send)
    say("personal", "Yes", {"done"}, then=lambda: bool(mine(MUM)) or "not sent on yes")
    say("personal", "Reply to Ahmed saying Thursday works", {"question"}, has=r"\d{4}", then=lambda: not mine(AHMED) or "sent to an Ahmed without asking which")
    say("personal", f"The one ending {AHMED[-4:]}", ASK, then=lambda: not mine(AHMED) or "sent before a yes")
    say("personal", "Yes", {"done"}, then=lambda: (bool(mine(AHMED)) and not mine(AHMED2)) or "wrong Ahmed")
    say("personal", "Tell dad I'm running late", ASK, has=r"late", then=lambda: not mine(DAD) or "sent to dad without a yes")
    say("personal", "No, leave it", None, then=lambda: not mine(DAD) or "sent after no")
    say("personal", "Pass Ahmed Saleh to Omar", ASK, has=r"Omar")
    say("personal", "Yes", {"done"}, then=lambda: any("Ahmed Saleh" in t.props["action"] for t in o.graph().of("task")) or "no task for Omar")
    say("personal", "Treat Ahmed Karim as family", {"done"}, then=lambda: contacts.who(o, AHMED)["circle"] == "family" or "not changed")
    say("personal", "Pay my mum 500 dirhams", {"refused", "answer"}, no=r"\b(?:paid|transferred)\b(?! ?\?)")

# ---------- the rest of what an owner asks ----------
say("catchup", "What did I miss this morning?", ANSWER)
say("catchup", "Who do I owe a call?", ANSWER)
say("catchup", "What did I promise this week?", ANSWER)
say("catchup", "Give me two lines on the office today", ANSWER)
say("vague", "How is Omar doing?", ANSWER, has=r"Omar")
say("vague", "And what about Hamza?", ANSWER, has=r"Hamza")
say("vague", "What's he working on?", ANSWER, has=r"Mona|Dana|Sara|Ali|review", note="must keep to Hamza")
say("vague", "Same for Rashid", ANSWER, no=r"Hamza's|Omar's", note="must move on to Rashid")
say("vague", "Remind me tomorrow at 10am to call the auditor", {"done"}, has=r"10")
say("vague", "Actually no, make it 11am", {"done"}, has=r"11")
say("vague", "Not that, cancel it", {"done", "answer"})
say("twothings", "Remind me tomorrow at 9am to call the bank and note down buy a gift for Dana", {"done", "confirm", "answer"}, has=r"bank|gift")
say("twothings", "What's on my list and what's on my calendar today?", ANSWER)
say("knockon", "I'm running 20 minutes late, what does that affect today?", ANSWER)
say("knockon", "Clear my Thursday afternoon", {"confirm", "question", "answer"}, note="an answer is right if nothing is on")
say("knockon", "Cancel that", {"answer", "done"})
say("advice", "Should I give Ali Rahman a discount?", ANSWER, no=r"\bapproved\b")
say("advice", "Which lead should I call first?", ANSWER, has=NAMES + "|Test")
say("advice", "Is the team on track this month?", ANSWER)
say("advice", "What would you do about the stalled leads?", ANSWER)
say("memory", "Note that Ahmed prefers morning meetings", {"done"}, has=r"Ahmed|mornings?|noted|added")
say("memory", "What do you know about Mona Said?", ANSWER, has=r"Mona")
say("memory", "What's my mum's birthday?", ANSWER, no=r"\b\d{1,2}(?:st|nd|rd|th)? (?:of )?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", note="not recorded: she must not guess")
say("docs", "Find the Marina contract", ANSWER)
say("docs", "What did the last invoice say?", ANSWER)
m0 = len(sent_whatsapp)
say("docs", "Send Mona Said the brochure", None, then=lambda: len(sent_whatsapp) == m0 or "sent without a yes")
say("docs", "cancel", None)
say("away", "I'm in Riyadh next week, what should I sort out before I go?", ANSWER)
say("away", "I land at 9pm tomorrow, what's on after that?", ANSWER)
say("away", "Who runs things while I'm away?", ANSWER)
say("language", "شو عندي اليوم؟", ANSWER, has=r"[؀-ۿ]")
say("language", "ذكرني بكرة الساعة 10 أتصل بالبنك", {"done"}, has=r"10:00")
say("language", "Kya haal hai office ka?", ANSWER)
say("language", "Remind me to call the bang tomorrow at for pm", {"done"}, has=r"4:00")
say("odd", "Turn the TV down, the kids are asleep", {"silent", "answer"})
say("odd", "Nova are you there?", ANSWER)
say("odd", "And then he said the villa was too", {"silent", "answer"})
say("cant", "Book me on the Emirates flight to London tonight", None, no=r"\bi(?:'ve| have) booked\b", note="she can't book: must say so")
say("cant", "Open my Gmail and read the latest email", None, no=r"your latest email (?:is|says)|inbox shows", note="not connected: must say so")
say("cant", "Call Mona Said for me", None, no=r"\b(?:calling her now|i(?:'ve| have) called)\b", note="she can't call: must say so")
say("cant", "Transfer 10000 dirhams to Omar", {"refused", "answer"}, no=r"\b(?:transferred)\b")

json.dump(results, open(OUT, "w", encoding="utf8"), ensure_ascii=False, indent=1)
good = sum(r["ok"] for r in results)
slow = sorted(r["secs"] for r in results)
print(f"\n{good} of {len(results)} passed. Median {slow[len(slow) // 2] if slow else 0}s, slowest {slow[-1] if slow else 0}s.")
for r in results:
    if not r["ok"]:
        print(f"  FAIL [{r['area']}] {r['said'][:60]} :: {r['why']}")
