"""The Sales room: the owner's numbers, the heat score, what a broker records after a call, leads added by hand, people who
wrote twice, new listings for waiting buyers, and the daily rhythm (the broker's list, reminders before calls, the midday
summary). docs/closed-loop-spec.md, Room 2. Rania talks to clients in agents/reception.py; who owns a lead is in leads.py.

Every number here is the owner's setting. Nothing in this file writes to a client on its own except the one reschedule
message after a no-show; a new listing reaches a buyer only when their broker says yes.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.graph import Graph
from diwan.office import Office
from diwan.people import PEOPLE, name

DEFAULTS = {
    "call_minutes": 10, "reply_minutes": 30, "pool_minutes": 60,  # "call me": the promise to the client, and the broker's limit
    "brief_days": [0, 1, 2, 3, 4, 5],  # Monday to Saturday (the owner, 31 Oct)
    "call_reminder_minutes": 15, "sweep_time": "08:30", "outcome_nudge_hours": 2, "licence_warn_days": 30, "match_days": 14,
    "heat": {"budget_fits": True, "timeline_days": 60, "finance_ready": True},
    "budget_floor": {"buyer": 200_000, "tenant": 10_000},  # below this Rania asks the client to confirm the figure
    "not_lead_reply": "Thanks for getting in touch. This line is for property enquiries, so I've let the team know and they'll "
                      "point you to the right person if there's a fit.",
}
TIMELINE_DAYS = {"Now": 0, "1-3 months": 60, "3-6 months": 120, "Later": 365}
OUTCOMES = {"converted": "Converted", "follow_up": "Follow up on a date", "not_interested": "Not interested", "no_response": "No response"}
LOST_REASONS = {"price": "Price", "finance_refused": "Finance refused", "valuation": "Valuation", "found_elsewhere": "Found elsewhere",
                "changed_mind": "Changed their mind", "no_response": "No response", "compliance": "Compliance", "seller_withdrew": "Seller withdrew",
                "other": "Other"}
SOURCES = {"walk_in": "Walk-in", "phone": "Phone call", "referral": "Referral", "website": "Website form"}
# someone asking us to pay another account, or change one: never acted on by an agent, in any room
FRAUD = (r"\b(change|changed|new|different|updated?|another)\b.{0,40}\b(bank|iban|account)\b.{0,40}\b(details?|number|deposit|pay\w*|transfer\w*|send\w*)?"
         r"|\biban\b|\b(send|transfer|pay|wire|deposit)\b.{0,40}\b(this|new|different|another|my other)\s+(bank\s+)?account\b"
         r"|\b(urgent(ly)?)\b.{0,30}\b(send|transfer|wire|pay)\b.{0,30}\b(money|funds|deposit|aed)\b|حساب (بنكي )?جديد|غير(وا)? الحساب")
NOT_LEAD = (r"\b(job|vacanc\w+|hiring|internship|career|cv|resume)\b.{0,40}\b(apply|applying|looking|available|send|open|attached|opportunit\w+)\b"
            r"|\b(apply|applying|looking)\b.{0,20}\b(job|vacancy|internship|position)\b|\bare you hiring\b"
            r"|\b(we|i) (offer|provide|supply|sell)\b.{0,40}\b(seo|marketing|web ?design|software|services?|cleaning|leads)\b|\bsupplier\b|\bvendor\b")
IBAN = r"\bAE\d{2}[\s\d]{15,}"


def settings(g: Graph) -> dict:
    saved = g.settings.get("sales", {}).get("rules") or {}
    return DEFAULTS | saved | {"heat": DEFAULTS["heat"] | (saved.get("heat") or {}), "budget_floor": DEFAULTS["budget_floor"] | (saved.get("budget_floor") or {})}


def set_settings(office: Office, value: dict, *, by: str) -> dict:
    """Only the owner sets these. Each change is a new event, so the old numbers stay in the log."""
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes the Sales rules")
    v = settings(office.graph()) | {k: value[k] for k in DEFAULTS if k in value}
    try:
        for k, lo, hi in (("call_minutes", 1, 240), ("reply_minutes", 1, 1440), ("pool_minutes", 5, 1440), ("call_reminder_minutes", 1, 120),
                          ("outcome_nudge_hours", 1, 72), ("licence_warn_days", 1, 365), ("match_days", 1, 90)):
            v[k] = int(v[k])
            if not lo <= v[k] <= hi:
                raise ValueError(f"{k.replace('_', ' ').capitalize()}: from {lo} to {hi}")
        v["heat"] = {"budget_fits": bool(v["heat"].get("budget_fits")), "timeline_days": int(v["heat"].get("timeline_days") or 0),
                     "finance_ready": bool(v["heat"].get("finance_ready"))}
        v["budget_floor"] = {str(k): int(n) for k, n in v["budget_floor"].items()}
    except (TypeError, AttributeError):
        raise ValueError("Those Sales rules need numbers") from None
    try:
        v["brief_days"] = sorted({int(d) for d in v["brief_days"]})
    except (TypeError, ValueError):
        raise ValueError("Brief days: numbers 0 (Monday) to 6 (Sunday)") from None
    if not v["brief_days"] or not all(0 <= d <= 6 for d in v["brief_days"]):
        raise ValueError("Pick at least one day for the morning brief")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(v["sweep_time"])):
        raise ValueError("The broker's list: a time like 08:30")
    if v["pool_minutes"] <= v["call_minutes"]:
        raise ValueError("The Pool comes after the call limit: make it longer")
    v["not_lead_reply"] = str(v["not_lead_reply"]).strip()[:500] or DEFAULTS["not_lead_reply"]
    office.log.append("setting.changed", actor=by, content={"person": "sales", "key": "rules", "value": v})
    return v


def brief_day(g: Graph, now: datetime) -> bool:
    from diwan.slots import DUBAI
    return now.astimezone(DUBAI).weekday() in settings(g)["brief_days"]


# ---------- how far a lead has come, and how hot it is ----------

def progress(g: Graph, deal: str | None) -> dict | None:
    """Questions answered of those the owner's form requires for this client: "Qualifying 3/8"."""
    from diwan import qualify
    if not deal or f"deal:{deal}" not in g.nodes:
        return None
    d = g.nodes[f"deal:{deal}"].props
    if not d.get("qtype"):
        return None
    f, answers = qualify.form(g), d.get("answers", {})
    need = [x for x in qualify.fields_for(f, d["qtype"]) if x.get("required") and (not x.get("ask_if") or qualify.holds(x["ask_if"], answers))]
    done = [x for x in need if x["key"] in answers and not (answers[x["key"]].get("unsure") and x.get("strict"))]
    return {"done": len(done), "of": len(need), "complete": len(done) == len(need)}


def form_complete(g: Graph, deal: str) -> bool:
    p = progress(g, deal)
    return bool(p and p["complete"])


def heat(g: Graph, deal: str | None) -> dict | None:
    """The owner's rules, the same for Rania, the brief and Records: does the budget fit a listing, is it soon enough, is the
    money ready. A second no-show takes a point off. None when the client is not a buyer or tenant."""
    from diwan.agents import reception
    if not deal or f"deal:{deal}" not in g.nodes:
        return None
    d = g.nodes[f"deal:{deal}"].props
    if d.get("qtype") not in ("buyer", "tenant"):
        return None
    rules, a, parts = settings(g)["heat"], d.get("answers", {}), []
    if rules["budget_fits"]:
        parts.append({"name": "Budget fits a listing", "ok": "budget_aed" in a and bool(reception.recommend(g, deal, 1))})
    if rules["timeline_days"] and (when := a.get("timeline")) and when["value"] in TIMELINE_DAYS:
        parts.append({"name": f"Within {rules['timeline_days']} days", "ok": TIMELINE_DAYS[when["value"]] <= rules["timeline_days"]})
    elif rules["timeline_days"]:
        parts.append({"name": f"Within {rules['timeline_days']} days", "ok": False})
    if rules["finance_ready"] and d["qtype"] == "buyer":
        fin = (a.get("finance") or {}).get("value")
        parts.append({"name": "Finance ready", "ok": fin == "Cash" or (fin == "Mortgage" and (a.get("mortgage_preapproved") or {}).get("value") == "Yes")})
    noshows = len([v for v in g.of("viewing", deal, "no_show")])
    score = max(0, sum(p["ok"] for p in parts) - (1 if noshows >= 2 else 0))
    return {"score": score, "of": len(parts), "parts": parts, "noshows": noshows, "hot": bool(parts) and score == len(parts)}


def budget_doubt(g: Graph, deal: str) -> dict | None:
    """A budget too small for what they want, as read from their words (AED 20K to buy): Rania asks once before it counts."""
    d = g.nodes[f"deal:{deal}"].props
    a = d.get("answers", {}).get("budget_aed")
    floor = settings(g)["budget_floor"].get(d.get("qtype"))
    if not a or a.get("unsure") or not floor or d.get("budget_checked") == str(a["value"]):
        return None
    from diwan import qualify
    n = qualify.number(a["value"])
    return {"value": n, "quote": a.get("quote")} if n is not None and n < floor else None


# ---------- after a call: the outcome ----------

def needs_outcome(g: Graph, chat) -> dict | None:
    """The last call on this lead has no outcome yet. None when it has one, or the lead is converted or closed."""
    from diwan import desk_stages
    deal = chat.deal
    if not deal or f"deal:{deal}" not in g.nodes:
        return None
    d = g.nodes[f"deal:{deal}"].props
    if (d.get("stage") in ("Won", "Lost")) or desk_stages.agreed(g, deal):
        return None
    phone, last = chat.props["phone"], None
    for n in g.of("attention", status="cleared"):
        if n.props.get("chat") == phone and n.props.get("kind") == "call" and n.props.get("action") in ("called", "no_answer"):
            if not last or n.props.get("cleared_event", 0) > last["event"]:
                last = {"event": n.props.get("cleared_event", 0), "at": n.props.get("cleared_at"), "by": n.props.get("cleared_by"), "what": n.props.get("action")}
    for v in g.of("viewing", status="done"):
        if v.props.get("chat") == phone and v.props.get("where") == "phone" and (not last or v.props.get("closed_event", 0) > last["event"]):
            last = {"event": v.props.get("closed_event", 0), "at": v.props["at"], "by": v.props["broker"], "what": "called"}
    return last if last and last["event"] > (d.get("outcome") or {}).get("event", 0) else None


def record_outcome(office: Office, phone: str, outcome: str, *, by: str, reason: str = "", note: str = "", at: datetime | None = None,
                   kind: str = "call", now: datetime | None = None) -> dict:
    """What came of the call. "Converted" is the Convert step itself (it needs the agreed price), so it is not recorded here."""
    from diwan import inbox, leads
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    chat = g.nodes.get(f"chat:{phone}")
    if not chat or not chat.deal:
        raise KeyError(phone)
    leads._may_act(g, chat.deal, by)
    if outcome not in OUTCOMES:
        raise ValueError(f"Say what came of it: {', '.join(OUTCOMES.values())}")
    if outcome == "converted":
        raise ValueError("Use Convert: it asks for the agreed price and starts the paperwork")
    if outcome == "not_interested":
        if reason not in LOST_REASONS:
            raise ValueError("Pick the reason")
        if reason == "other" and not note.strip():
            raise ValueError("Say what the reason was")
    if outcome == "follow_up":
        if not at:
            raise ValueError("Say when to follow up")
        leads.follow_up_on(office, phone, by=by, at=at, kind=kind, note=note, now=now)
    ev = office.log.append("lead.outcome", actor=by, deal=chat.deal,
                           content={"chat": phone, "outcome": outcome, "reason": reason or None, "note": note.strip()[:300] or None,
                                    "at": at.isoformat() if at else None})
    if outcome == "not_interested":
        inbox.set_stage(office, phone, "Lost", by=by, reason=LOST_REASONS[reason] + (f": {note.strip()}" if note.strip() else ""))
    return {"ok": True, "event": ev["id"], "outcome": OUTCOMES[outcome]}


# ---------- leads that don't start on WhatsApp ----------

def add_lead(office: Office, *, by: str, name_: str, phone: str, source: str, note: str = "", email: str = "", ref: str = "",
             referred_by: str = "", now: datetime | None = None) -> dict:
    """A walk-in, a phone call, a referral or a website form: the same lead as any other, with where it came from. The
    person who adds it keeps it; a website form goes to a broker on shift. Rania writes nothing: WhatsApp needs them to write first."""
    from diwan import leads
    from diwan.agents import reception, scribe
    now = now or datetime.now(timezone.utc)
    phone = re.sub(r"\D", "", phone or "")
    if not 8 <= len(phone) <= 15:
        raise ValueError("A phone number with the country code, like 971501234567")
    if not (name_ or "").strip():
        raise ValueError("Their name")
    if source not in SOURCES:
        raise ValueError(f"Where did they come from: {', '.join(SOURCES.values())}")
    if source == "referral" and not referred_by.strip():
        raise ValueError("Who referred them?")
    g = office.graph()
    listing = g.nodes.get(f"listing:{ref.strip().upper()}") if ref.strip() else None
    if ref.strip() and not listing:
        raise ValueError(f"No listing {ref}")
    deal = reception._lead(office, phone, name_.strip(), now)
    if by in leads.brokers() and office.graph().nodes[f"deal:{deal}"].props.get("broker") != by:
        leads.assign(office, deal, by, by=by, why=f"added by {name(by)}", chat=phone, now=now)
    text = note.strip() or f"{SOURCES[source]} lead"
    got = office.log.append("chat.received", actor=by if source != "website" else f"customer:{phone}", deal=deal,
                            content={"chat": phone, "name": name_.strip(), "text": text, "channel": source, "email": email.strip() or None,
                                     "ref": listing.props["ref"] if listing else None, "referred_by": referred_by.strip() or None})
    heard = scribe.hear(office, deal, office.graph().nodes[f"deal:{deal}"].props["customer"], text, got["id"]) if source == "website" else {"facts": []}
    if listing:
        leads.from_listing(office, deal, listing, text, cause=got["id"])
    card = leads.raise_card(office, phone, kind="call", cause=got["id"], now=now,
                            reason=f"New {SOURCES[source].lower()} lead" + (f" from {referred_by.strip()}" if referred_by.strip() else "")
                                   + (f": {text[:160]}" if note.strip() else ""))
    return {"deal": deal, "chat": phone, "card": card, "facts": heard["facts"]}


# ---------- the same person twice, and a new listing for someone waiting ----------

def _norm(s: str | None) -> str:
    return " ".join(re.findall(r"[a-z]+", (s or "").lower()))


def duplicates(g: Graph) -> list[dict]:
    """Two conversations that look like one person: the same email or the same full name. A person merges them, never the
    code; when two brokers own them only the Sales manager or the owner may."""
    seen: dict[str, list] = {}
    for c in g.of("chat"):
        if c.props.get("merged_into") or not c.deal or f"deal:{c.deal}" not in g.nodes or g.nodes[f"deal:{c.deal}"].props.get("stage") == "Lost":
            continue
        emails = {m.get("email") for m in c.props["messages"] if m.get("email")}
        for key in {f"email:{e.lower()}" for e in emails} | ({f"name:{_norm(c.label)}"} if len(_norm(c.label).split()) >= 2 else set()):
            seen.setdefault(key, []).append(c)
    out, done = [], set()
    for key, chats in seen.items():
        for i, a in enumerate(chats):
            for b in chats[i + 1:]:
                pair = tuple(sorted((a.props["phone"], b.props["phone"])))
                if pair in done:
                    continue
                done.add(pair)
                ba, bb = g.nodes[f"deal:{a.deal}"].props.get("broker"), g.nodes[f"deal:{b.deal}"].props.get("broker")
                out.append({"a": a.props["phone"], "a_name": a.label, "b": b.props["phone"], "b_name": b.label, "why": key.split(":")[0],
                            "brokers": sorted({ba, bb}), "two_brokers": ba != bb})
    return out


def matches(g: Graph, now: datetime) -> list[dict]:
    """New listings that fit a qualified client who has not seen them. Only a list for the broker: the client hears only on
    the broker's yes."""
    from diwan.agents import reception
    since = now - timedelta(days=settings(g)["match_days"])
    out = []
    for c in g.of("chat"):
        if not c.deal or f"deal:{c.deal}" not in g.nodes or c.props.get("merged_into"):
            continue
        d = g.nodes[f"deal:{c.deal}"].props
        if d.get("qualify_status") != "qualified" or d.get("optout") or d.get("stage") in ("Won", "Lost"):
            continue
        for n in reception.recommend(g, c.deal, 5):
            if n.id in (d.get("recommended") or []) or n.id in (d.get("offered") or []):
                continue
            if datetime.fromisoformat(n.at.replace("Z", "+00:00")) >= since:
                out.append({"chat": c.props["phone"], "name": c.label, "broker": d.get("broker"), "ref": n.props["ref"], "title": n.props["title"],
                            "community": n.props["community"], "price_aed": n.props["price_aed"]})
    return out


def send_match(office: Office, phone: str, ref: str, *, by: str) -> dict:
    """The broker's yes: this listing goes to this client, in the broker's name, inside WhatsApp's window."""
    from diwan import inbox, leads
    from diwan.agents import reception
    g = office.graph()
    chat, n = g.nodes.get(f"chat:{phone}"), g.nodes.get(f"listing:{ref}")
    if not chat or not n:
        raise KeyError(phone if not chat else ref)
    leads._may_act(g, chat.deal, by)
    if not inbox.conversation(g, chat, datetime.now(timezone.utc))["window_open"]:
        raise ValueError("More than 24 hours since they wrote: WhatsApp needs an approved template, so call them instead")
    first = reception.first_name(chat.label)
    text = f"Hi{' ' + first if first else ''}, something new that fits what you told us: {reception._listing_line(n)}. Would you like to see it?"
    ev = reception.person_sends(office, phone, text, by=by)
    office.log.append("lead.recommended", actor=by, deal=chat.deal, caused_by=ev.get("id"), content={"refs": [n.id], "chat": phone, "offered": True})
    return {"ok": True}


# ---------- fraud guard, and what is not a lead ----------

def fraud_guard(office: Office, phone: str, deal: str, text: str, cause: int) -> dict:
    """Any message asking to change bank details or pay another account: no agent acts on it. Finance and Compliance hear
    now, and a person confirms it by phone on a number we already have."""
    from diwan import leads, roles
    g = office.graph()
    label = g.nodes[f"chat:{phone}"].label
    broker = g.nodes[f"deal:{deal}"].props["broker"]
    tid = office.add_task(deal, "comp", f"Confirm by phone, on a number already on file: {label} wrote about payment details", needs_person=roles.holder(g, "compliance"),
                          by="rania", caused_by=cause, props={"fraud": True, "quote": text[:300]})
    for who in {roles.holder(g, "finance"), roles.holder(g, "compliance"), broker}:
        leads.notify(office, who, f"Possible payment fraud on {label}: “{text[:160]}”. Do not act on it: confirm by phone on a known number.",
                     chat=phone, kind="now", cause=cause)
    return {"task": tid}


# ---------- the Sales room board ----------

def sees_all(person: str | None) -> bool:
    return PEOPLE.get(person or "", {}).get("role") in ("Owner", "Sales manager")


def scope(rows: list[dict], person: str | None) -> list[dict]:
    """A broker sees their own leads and the Pool; the Sales manager and the owner see everyone's. Only a signed-in broker is
    limited: the owner's "Viewing as" looks through that person's work, not their walls."""
    if not person or sees_all(person) or PEOPLE.get(person, {}).get("role") != "Broker":
        return rows
    return [r for r in rows if r["broker"] == person or r["handled_by"] == person or (r["attention"] and r["attention"]["pooled"])]


def may_see(g: Graph, phone: str, person: str | None) -> bool:
    from diwan import inbox
    chat = g.nodes.get(f"chat:{phone}")
    if not chat:
        return False
    return bool(scope([inbox.conversation(g, chat, datetime.now(timezone.utc))], person))


def board(office: Office, person: str | None, now: datetime | None = None) -> dict:
    """The Sales room on one page, for this person: everything from the graph, nothing stored."""
    from diwan import inbox, leads
    from diwan.agents import nudge
    from diwan.slots import DUBAI
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    chats = {c.props["phone"]: c for c in g.of("chat") if not c.props.get("merged_into")}
    rows = scope([inbox.conversation(g, c, now) for c in chats.values()], person)
    mine = {r["phone"] for r in rows}
    today = now.astimezone(DUBAI).date()
    brief = lambda r: {"chat": r["phone"], "name": r["name"], "broker": r["broker"], "stage": r["stage"]}  # noqa: E731
    calls = sorted((r for r in rows if r["attention"] and r["attention"]["kind"] == "call"), key=lambda r: r["attention"]["minutes_left"])
    new = [r for r in rows if r["stage"] == "New" or (r["last_at"] and inbox._at(r["last_at"]) > now - timedelta(days=1) and r["stage"] == "New")]
    by_channel: dict[str, int] = {}
    for r in new:
        by_channel[r["source"]] = by_channel.get(r["source"], 0) + 1
    qualifying = [brief(r) | {"progress": progress(g, r["deal"])} for r in rows if r["stage"] == "Qualifying"]
    follow, quiet = [], []
    for r in rows:
        ch = chats[r["phone"]]
        if not ch.deal or f"deal:{ch.deal}" not in g.nodes:
            continue
        st = nudge.state(g, ch, now)
        if st.get("next") and datetime.fromisoformat(st["next"]).astimezone(DUBAI).date() == today:
            follow.append(brief(r) | {"at": st["next"], "n": st["sent"] + 1, "of": st["of"]})
        card = r["attention"]
        if card and card["due"] and inbox._at(card["due"]).astimezone(DUBAI).date() == today and "Follow up" in card["reason"]:
            follow.append(brief(r) | {"at": card["due"], "set": True})
        if g.nodes[f"deal:{ch.deal}"].props.get("went_quiet") and r["waiting_min"] is None:
            quiet.append(brief(r) | {"last": r["last_at"]})
    day = []
    for b in leads.brokers():
        if person and not sees_all(person) and PEOPLE.get(person, {}).get("role") == "Broker" and b != person:
            continue
        appts = sorted((v for v in g.of("viewing", status="booked") if v.props["broker"] == b
                        and datetime.fromisoformat(v.props["at"]).astimezone(DUBAI).date() == today), key=lambda v: v.props["at"])
        cards = [n for n in g.of("attention", status="open") if n.props.get("who") == b]
        day.append({"id": b, "name": name(b), "on_shift": leads.on_shift(g, b, now), "appointments": [
            {"at": v.props["at"], "what": v.props.get("kind_name") or "Viewing", "customer": v.props.get("customer"), "listing": v.props.get("listing")} for v in appts],
            "cards": len(cards), "overdue": sum(1 for n in cards if inbox._at(n.props["due"]) < now), "leads_today": leads.load_today(g, b, now)})
    outcome = []
    for r in rows:
        if last := needs_outcome(g, chats[r["phone"]]):
            outcome.append(brief(r) | {"last": last})
    return {"call_now": [brief(r) | {"attention": r["attention"], "tel": r["phone"] if not r["phone"].startswith("ig:") else None, "no_calls": r["no_calls"]} for r in calls],
            "hot": [brief(r) | {"hot": r["hot"], "heat": heat(g, r["deal"])} for r in rows if r["hot"]],
            "new": {"total": len(new), "by_channel": by_channel, "rows": [brief(r) | {"source": r["source"]} for r in new][:20]},
            "qualifying": qualifying, "followups": sorted(follow, key=lambda x: x["at"]), "quiet": quiet, "brokers": day, "outcome": outcome,
            "duplicates": [x for x in duplicates(g) if x["a"] in mine or x["b"] in mine],
            "matches": [m for m in matches(g, now) if m["chat"] in mine],
            "outcomes": OUTCOMES, "lost_reasons": LOST_REASONS, "sources": SOURCES, "sees_all": sees_all(person)}


# ---------- the daily rhythm ----------

def morning_list(g: Graph, broker: str, now: datetime) -> dict:
    """Who to call, who has gone quiet, who is waiting on options: what a broker's day starts with."""
    from diwan import inbox
    rows = [inbox.conversation(g, c, now) for c in g.of("chat") if not c.props.get("merged_into")]
    rows = [r for r in rows if r["broker"] == broker and r["stage"] not in ("Won", "Lost")]
    call = [r["name"] for r in rows if r["attention"] and r["attention"]["kind"] == "call"]
    quiet, options = [], []
    for r in rows:
        d = g.nodes[f"deal:{r['deal']}"].props if r["deal"] and f"deal:{r['deal']}" in g.nodes else {}
        if d.get("went_quiet") and r["waiting_min"] is None:
            quiet.append(r["name"])
        if d.get("qualify_status") == "qualified" and not d.get("recommended") and not d.get("hot"):
            options.append(r["name"])
    return {"call": call, "quiet": quiet, "options": options}


def sweep(office: Office, now: datetime | None = None) -> list[str]:
    """Run every minute with the other sweeps: the broker's list, a reminder before each call, a nudge for a missing outcome,
    a licence about to expire, and the midday summary. Each once."""
    from diwan import leads
    from diwan.slots import DUBAI
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    s = settings(g)
    local, out = now.astimezone(DUBAI), []
    if local.strftime("%H:%M") >= s["sweep_time"]:
        for b in leads.brokers():
            if not leads.on_shift(g, b, now) and leads.setting(g, b, "away"):
                continue
            mine = morning_list(g, b, now)
            if not any(mine.values()):
                continue
            ev = office.log.append("lead.sweep", actor="sales", agent="sales", key=f"sweep:{b}:{local.date()}", content={"broker": b} | mine)
            if ev.get("duplicate"):
                continue
            bits = [f"{len(v)} {w}: {', '.join(v[:5])}" for v, w in ((mine["call"], "to call"), (mine["quiet"], "gone quiet"), (mine["options"], "waiting on options")) if v]
            leads.notify(office, b, "Your list today. " + "; ".join(bits) + ".", kind="info", cause=ev["id"])
            out.append(f"sweep {b}")
    for v in g.of("viewing", status="booked"):  # a call at a time the client chose: the broker hears before it
        p = v.props
        at = datetime.fromisoformat(p["at"])
        if p.get("where") != "phone" or "before" in (p.get("reminded") or []) or not at - timedelta(minutes=s["call_reminder_minutes"]) <= now < at:
            continue
        ev = office.log.append("appointment.reminded", actor="sales", agent="sales", deal=v.deal, key=f"call-before:{v.id}:{p['at']}",
                               content={"id": v.id, "which": "before", "sent": True})
        if not ev.get("duplicate"):
            leads.notify(office, p["broker"], f"Call {p.get('customer')} at {at.astimezone(DUBAI):%H:%M}, as they asked.", chat=p.get("chat"), kind="call", cause=ev["id"])
            out.append(f"call reminder {v.id}")
    for c in g.of("chat"):  # a call with no outcome: the broker is nudged, once
        last = needs_outcome(g, c)
        if last and last.get("at") and now >= datetime.fromisoformat(last["at"].replace("Z", "+00:00")) + timedelta(hours=s["outcome_nudge_hours"]):
            who = g.nodes[f"deal:{c.deal}"].props.get("broker")
            ev = office.log.append("lead.nudged", actor="sales", agent="sales", deal=c.deal, key=f"outcome:{c.props['phone']}:{last['event']}", content={"chat": c.props["phone"], "to": who})
            if not ev.get("duplicate"):
                leads.notify(office, who, f"What came of the call with {c.label}? Please record the outcome.", chat=c.props["phone"], kind="info", cause=ev["id"])
                out.append(f"outcome {c.props['phone']}")
    for b in leads.brokers():
        exp = leads.setting(g, b, "licence_expiry")
        if exp and 0 <= (datetime.fromisoformat(exp).date() - local.date()).days <= s["licence_warn_days"]:
            ev = office.log.append("lead.nudged", actor="sales", agent="sales", key=f"licence:{b}:{exp}", content={"to": b, "licence": exp})
            if not ev.get("duplicate"):
                for who in (b, next(p for p, v in PEOPLE.items() if v["role"] == "Owner")):
                    leads.notify(office, who, f"{name(b)}'s broker licence expires on {exp}. After that no new leads go to them.", kind="info", cause=ev["id"])
                out.append(f"licence {b}")
    if local.hour >= 12:
        out += leads.midday(office, now)
    return out


def no_show(office: Office, vid: str, cause: int, now: datetime | None = None) -> str:
    """A client did not come: one message offering another time; a second no-show takes the heat down and the broker decides."""
    from diwan import inbox, leads
    from diwan.agents import nudge, reception
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    v = g.nodes[vid]
    phone, chat = v.props.get("chat"), g.nodes.get(f"chat:{v.props.get('chat')}")
    if not chat or not chat.deal:
        return "no chat"
    d = g.nodes[f"deal:{chat.deal}"].props
    if len(g.of("viewing", chat.deal, "no_show")) >= 2:
        if d.get("hot"):
            office.log.append("lead.unhot", actor="sales", agent="sales", deal=chat.deal, caused_by=cause, content={"note": "second no-show", "chat": phone})
        leads.notify(office, d["broker"], f"{chat.label} missed a second appointment. Rania won't offer another: you decide.", chat=phone, kind="info", cause=cause)
        return "second"
    first = reception.first_name(chat.label)
    if d.get("optout") or not inbox.conversation(g, chat, now)["window_open"] or not nudge.allowed(nudge.settings(g), now):
        leads.raise_card(office, phone, kind="call", cause=cause, now=now, reason=f"Missed the appointment ({v.props.get('kind_name') or 'viewing'}): call to rearrange")
        return "broker"
    reception._send(office, phone, chat.deal, f"Hi{' ' + first if first else ''}, sorry we missed you today. Would another time suit you? Tell me a day and time.", [], cause=cause)
    return "sent"
