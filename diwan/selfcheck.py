"""Prove every agent works: a whole office day run through the real code, on a throwaway office in memory, then each agent
reported as worked, needs something outside Diwan (and what), or not reached. Nothing touches the office's own data.

    python -m diwan selfcheck [out.json]

Each scene is a thing that happens in a brokerage (a WhatsApp lead, a meeting where the client corrects himself, a cash
payment, the Lobby's week, a listing through the studio…). A scene that fails is recorded with its error; the others still run.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from diwan import demo
from diwan.events import EventLog
from diwan.office import Office

DEAL = "marina-1204"
NEEDS = {  # agents whose trigger needs something outside Diwan: reported as that, not as a failure, when they didn't run
    "mrival": "Instagram connected: competitors' posts to read",
    "mtrans": "Instagram connected: an outlier video to transcribe",
    "mremix": "Instagram connected: an outlier to remix",
    "mvideo": "HeyGen connected, and a person pressing Make AI video",
    "mpub": "Instagram connected, to publish",
    "mcross": "Instagram connected, to publish",
    "msched": "a post approved to go out on Instagram",
    "mpermit": "a post about to go out on Instagram",
    "mcheck": "a filmed take uploaded",
    "mcap": "a filmed take uploaded",
    "mart": "a filmed take uploaded",
    "mthumb": "a filmed take uploaded",
    "mprod": "a filmed take uploaded",
    "mwriter": "a cut ready, from a filmed take",
    "mplaybook": "Instagram connected: five of our own posts with their results",
}


def _scenes(o: Office) -> list[tuple[str, callable]]:
    from diwan import brand, desk_stages, lobby_room, slots
    from diwan.agents import compliance, finance, followup, nova, operations, reception, scribe, steps, visit

    def lead():
        for t in ("Hi, is unit 1204 in Marina Crest still available?", "Buying, to live in. Budget around 2.5 million", "Can I see it on Saturday at 4pm?"):
            reception.message(o, "971500009001", t, name_="Hamad Saleh")

    def meeting():
        o.start_meeting(DEAL, "SC1", title="Self-check meeting")
        o.give_consent("SC1", by="customer")
        scribe.turn(o, "SC1", "broker", "Ahmed will send you the payment plan by Thursday, and Joseph will book the trustee for next week.")
        scribe.turn(o, "SC1", "customer", "Actually, forget my brother. I'll pay it all myself.")
        ev = o.end_meeting("SC1")
        visit.from_meeting(o, "SC1", cause=ev["id"])
        followup.draft(o, DEAL, why="after the meeting", cause=ev["id"])
        s = steps.propose(o, "SC1", cause=ev["id"])
        steps.approve(o, "SC1", s["items"], by="omar")

    def money():
        g = o.graph()
        t = next(t for t in g.of("task", DEAL) if t.props["agent"] == "pay" and t.status in ("queued", "open", "running"))
        finance.mark_received(o, t.id, "ahmed", "Cash receipt SC-1", today=date.today(), amount=60000, method="cash")

    def compliance_work():
        g = o.graph()
        t = next((t for t in g.of("task", DEAL) if t.props["agent"] == "screen" and t.status in ("queued", "open", "running")), None)
        if t:
            compliance.record_screening(o, t.id, "priya", "possible match", "UN list: one name match, to check")
        compliance.draft_str(o, DEAL, "priya", "Income does not fit the price")

    def instructions():
        for text in ("Check the source of funds for Karim Haddad", "Process the invoice for Karim's Marina unit", "Prepare Form F for Karim's Marina unit",
                     "Rebuild the customer deck for Karim", "Track the NOC and transfer for Karim's Marina unit", "Draft the customer's follow-up for Karim",
                     "Fact-check the latest draft for Karim", "Screen the parties for Karim", "Draft the cash report for Karim",
                     "Track the expected payments for Karim"):
            nova.route(o, text, "layla")

    def records_work():
        o.file_document(kind="passport", title="Karim Haddad passport", date=date.today().isoformat(), deal=DEAL)
        nova.ask(o, "How much commission did we make this month?", "layla")
        nova.ask(o, "Find Karim Haddad's passport", "layla")

    def deal_converts():
        desk_stages.convert(o, DEAL, "omar", 2_600_000)

    def transfer():
        o.add_task(DEAL, "transfer", "Developer NOC issued", needs_person="joseph", props={"waiting_on": "the developer", "before_gate": True})
        operations.chase_late(o, datetime.now(timezone.utc) + timedelta(days=5))

    def supplier_invoice():
        finance.check_supplier_invoice(o, "Supplier: Gulf Print LLC\nTRN: 100234567800003\nInvoice no: SC-1\nNet: 4,000\nVAT: 200\nTotal: 4,200", by="ahmed")

    def marketing_setup():
        brand.save(o, {"name": "Diwan Realty", "positioning": "We help families buy their first home in Dubai Marina.", "audience": "Families moving to Dubai",
                       "different": "We only sell homes we have visited ourselves.", "voice": "warm, straight-talking"}, by="maya")
        brand.draft(o)

    def lobby_week():
        lobby_room.run_week(o, datetime.now(slots.DUBAI))
        lobby_room.add_playbook(o, {"room": "sales", "pattern": "A floor plan on day 3", "where": "seen at another office", "evidence": "replies doubled", "text": "Send the floor plan on day 3."}, by="layla")

    def studio():
        from diwan.agents import studio as st
        asyncio.run(st.run(o, "MC-1204", pause=0))
        st.approve_script_now(o, "MC-1204")

    return [("A WhatsApp lead", lead), ("A meeting where the client corrects himself", meeting), ("A cash payment", money),
            ("Compliance: a screening match and a report draft", compliance_work), ("The owner's instructions to Nova", instructions),
            ("Numbers and documents", records_work), ("The deal converts", deal_converts), ("A transfer step runs late", transfer),
            ("A supplier invoice", supplier_invoice), ("The brand and positioning", marketing_setup), ("The Lobby's week", lobby_week),
            ("A listing through the marketing studio", studio)]


def run() -> dict:
    from diwan.agents import custom
    started = time.time()
    o = Office(EventLog())
    demo.seed(o)
    scenes = []
    for title, fn in _scenes(o):
        t0, n0 = time.time(), len(o.log.list())
        try:
            fn()
            scenes.append({"title": title, "ok": True, "events": len(o.log.list()) - n0, "seconds": round(time.time() - t0, 1)})
        except Exception as e:  # noqa: BLE001  one scene failing must not hide the rest
            scenes.append({"title": title, "ok": False, "error": f"{type(e).__name__}: {e}"[:300], "events": len(o.log.list()) - n0,
                           "seconds": round(time.time() - t0, 1)})
    agents = []
    for n in custom.connections(o)["nodes"]:
        if n["type"] != "agent" or n["props"].get("custom") or n["props"].get("level") == "room":  # a room is a heading, not an agent
            continue
        aid, acts = n["id"].split(":", 1)[1], n["props"]["actions"]
        state = "worked" if acts else "needs" if aid in NEEDS else "not reached"
        agents.append({"id": aid, "name": n["label"], "dept": n["props"]["dept"], "actions": acts, "state": state, "needs": NEEDS.get(aid) if not acts else None})
    count = {s: sum(a["state"] == s for a in agents) for s in ("worked", "needs", "not reached")}
    return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seconds": round(time.time() - started, 1), "events": len(o.log.list()),
            "scenes": scenes, "agents": agents, "count": count}


if __name__ == "__main__":
    out = run()
    text = json.dumps(out, indent=1)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text)
    print(json.dumps(out["count"]), "·", sum(not s["ok"] for s in out["scenes"]), "scenes failed")
