"""A busy day in the fictional demo office, for a public demo that starts fresh (docs/demo-day-spec.md): clients writing on
WhatsApp, viewings and calls on the brokers' calendars, the owner's own day, and work moving in every room. Run through the
real code with the model and every outside service switched off, so it costs nothing, sends nothing and takes seconds.

Karim's deal is left before his correction, so a visitor can still play it in the Meeting room. Times are set from `now`, so
the calendar always looks current.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

from diwan import config
from diwan.office import Office
from diwan.slots import DUBAI

# (phone, name, what they write): all fictional; the numbers are the 000 block no one is given
LEADS = [
    ("971500000101", "Fatima Al Mansoori", ["Hello, is Villa 88 in JVC still available?", "We're a family of five, buying to live in. Budget up to 2 million",
                                            "Can we see it tomorrow at 11am?"]),
    ("971500000102", "Daniel Brooks", ["Hi, I saw the Mallowby Square apartment on Property Finder. Is it still on the market?", "Investment, I'd rent it out. Cash buyer"]),
    ("971500000103", "Aisha Rahman", ["Looking for a 1 bed in Downtown under 1.5M", "Please call me, I prefer to talk"]),
    ("971500000104", "Omar Farouk", ["مرحبا، أبحث عن شقة بغرفتين في دبي مارينا"]),
    ("971500000105", "Elena Petrova", ["Do you have anything with a sea view in the Marina?"]),
    ("971500000106", "Rohan Mehta", ["Is the 1 bed in Business Bay still free? Budget 1.2M, mortgage pre-approved"]),
]


def run(office: Office, now: datetime | None = None) -> list[str]:
    """Play the day. Returns what didn't happen and why (a part that fails never stops the rest). Inside a running server
    (uvicorn imports the app in its event loop) it plays on a thread of its own, where the studio can run its own loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _play(office, now)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(1) as pool:
        return pool.submit(_play, office, now).result()


def _play(office: Office, now: datetime | None) -> list[str]:
    now = (now or datetime.now(DUBAI)).astimezone(DUBAI)
    token = config.TRIAL.set({"offline": True, "sandbox": True, "tape": "off"})
    missed = []
    try:
        for name, part in _parts(office, now):
            try:
                part()
            except Exception as e:  # noqa: BLE001
                missed.append(f"{name}: {type(e).__name__}: {e}"[:200])
    finally:
        config.TRIAL.reset(token)
    return missed


def _next_open(now: datetime, days: int, hour: int) -> datetime:
    """`days` working days on (the office is shut on Sunday), at `hour`."""
    d, left = now, days
    while left:
        d += timedelta(days=1)
        if d.weekday() != 6:
            left -= 1
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


def _parts(o: Office, now: datetime) -> list[tuple[str, callable]]:
    from diwan import brand, leads, lobby_room, slots
    from diwan.agents import compliance, finance, frontdesk, nova, operations, reception, scribe, steps, visit

    tomorrow, later = _next_open(now, 1, 11), _next_open(now, 2, 16)

    def clients():
        for i, (phone, who, said) in enumerate(LEADS):
            for k, text in enumerate(said):
                reception.message(o, phone, text, name_=who, now=now - timedelta(hours=6 - i, minutes=20 - 5 * k))

    def calendars():
        kinds = {k["where"]: k["id"] for k in slots.appointments(o.graph())}
        g = o.graph()
        for phone, ref, when, kind in (("971500000101", "JVC-88", tomorrow, "property"), ("971500000102", "BB-305", tomorrow.replace(hour=15), "property"),
                                       ("971500000106", None, later, "video"), ("971500000103", None, tomorrow.replace(hour=17), "phone")):
            chat = g.nodes.get(f"chat:{phone}")
            broker = g.nodes[f"deal:{chat.deal}"].props["broker"] if chat else "omar"
            reception.add_by_hand(o, by=broker, broker=broker, phone=phone, name_=chat.label if chat else None, kind_id=kinds[kind], ref=ref,
                                  when=when, now=now, confirmed=True)

    def owners_day():
        def say(text, who="layla"):
            return frontdesk.say(o, text, who, session=f"demo-{who}", now=now)
        say(f"Block {later:%A} 3 to 5pm for school pickup"), say("yes")
        say(f"Set up a meeting with Omar {_next_open(now, 3, 10):%A} at 10 about the Marina Crest launch"), say("yes")
        say("Remind me tomorrow at 9am to call the bank about the escrow account")
        say("Note down: ask Maya for the October numbers; renew the Property Finder plan")
        say("Tell Priya I need the Sara Malik screening done by Thursday"), say("yes")

    def sara_meeting():
        deal = "jvc-88"
        o.start_meeting(deal, "M-DEMO", title="Sara Malik, Villa 88")
        o.give_consent("M-DEMO", by="customer")
        scribe.turn(o, "M-DEMO", "broker", "Ahmed will send you the payment schedule by Thursday, and Joseph will book the trustee office.")
        scribe.turn(o, "M-DEMO", "customer", "Good. I'll pay the ten percent deposit by bank transfer from my own account next week.")
        ev = o.end_meeting("M-DEMO")
        visit.from_meeting(o, "M-DEMO", cause=ev["id"])
        s = steps.propose(o, "M-DEMO", cause=ev["id"])
        steps.approve(o, "M-DEMO", s["items"], by="omar")

    def compliance_work():
        g = o.graph()
        for t in g.of("task"):
            if t.props.get("agent") == "screen" and t.status in ("queued", "open", "running"):
                compliance.record_screening(o, t.id, "priya", "clear", "No match on the UN and UAE lists")
                break

    def money():
        o.file_document(kind="invoice", title="Brochures for the Villa 88 launch", date=now.date().isoformat(), amount_aed=4_200, party="Gulf Print LLC")
        finance.draft_invoice(o, "jvc-88", "ahmed")
        g = o.graph()
        t = next((t for t in g.of("task", "jvc-88") if t.props.get("agent") == "pay" and t.status in ("queued", "open", "running")), None)
        if t:
            finance.mark_received(o, t.id, "ahmed", "Bank transfer FT-88310", today=now.date(), amount=190_000, method="transfer")

    def operations_work():
        o.add_task("jvc-88", "transfer", "Developer NOC requested for Villa 88", needs_person="joseph", props={"waiting_on": "the developer", "before_gate": True})
        nova.route(o, "Prepare Form F for Sara's villa", "layla")

    def marketing():
        from diwan import business
        from diwan.agents import approvers, studio
        business.save(o, {"industry": "real estate brokerage", "country": "AE", "city": "Dubai", "permit": "yes", "languages": "English, Arabic",
                          "posted_before": "no"}, by="maya")
        approvers.save(o, {"script": "maya", "publish": "layla"}, by="layla")
        brand.save(o, {"name": "Diwan Realty", "positioning": "We help families buy their first home in Dubai.", "audience": "Families moving to Dubai",
                       "different": "We only sell homes we have visited ourselves.", "voice": "warm, straight-talking"}, by="maya")
        for ref in ("MC-1204", "JVC-88"):
            asyncio.run(studio.run(o, ref, pause=0))
        studio.approve_script_now(o, "MC-1204")  # Marina Crest's reel moves on to filming
        studio.approve_script_now(o, "JVC-88")
        lst = o.graph().nodes["listing:JVC-88"].props  # then the seller raises Villa 88's price: its post must not go out with the old one
        o.add_listing(ref="JVC-88", title=lst["title"], community=lst["community"], type=lst["type"], beds=lst["beds"], price_aed=1_950_000,
                      permit=lst.get("permit"), status=lst.get("status") or "available", features=lst.get("features") or [], agent=lst.get("agent"), by="omar")
        from diwan.agents import marketing as mk
        mk.watch(o, now)
        from diwan.agents import rhythm  # the week planned ahead, three posts, each going out only on a person's yes
        rhythm.save(o, {"auto": "on", "at": "09:00", "rhythm": "weekly", "posts_per_week": "3", "plan_ahead": "on", "auto_post": "off"}, by="maya")
        rhythm.make_plan(o, now.date(), auto=False, by="maya", days_ahead=7)
        studio.schedule(o, None)  # the best hour for the next post

    def lobby():
        lobby_room.run_week(o, now)

    return [("clients on WhatsApp", clients), ("the brokers' calendars", calendars), ("the owner's day", owners_day),
            ("Sara's meeting", sara_meeting), ("Compliance", compliance_work), ("Finance", money), ("Operations", operations_work),
            ("Marketing", marketing), ("the Lobby", lobby)]
