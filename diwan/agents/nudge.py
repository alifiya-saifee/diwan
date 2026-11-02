"""Follow-ups when a client goes quiet (docs/quiet-clients-spec.md). Space to think, and a nudge only when it brings
something useful: a new listing that fits, the one question still open, or the door left open. Never daily, never in
quiet hours or Friday prayer, never after "stop", and at most the owner's number of them. After the last one the lead
goes to Nurture (or the broker hears once), so nobody is chased.

The owner sets it all (`setting.changed` person "rania", key "quiet"). The sweep runs every minute with the other
sweeps (app.morning_loop); each follow-up is a `followup.nudged` event, whether it was sent or skipped and why.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.graph import Graph
from diwan.office import Office
from diwan.people import name
from diwan.slots import DUBAI

QUIET = {"after_hours": [20, 72, 168], "after_visit_hours": [24, 72, 144, 216], "quiet_from": "21:00", "quiet_to": "09:00", "friday_prayer": True,
         "template": None, "then": "nurture", "then_after_hours": 72}
THEN = {"nurture": "Move them to Nurture (Marketing)", "broker": "Give the broker one \"gone quiet\" card", "nothing": "Nothing more"}
PRAYER = ((11, 30), (13, 30))  # Friday, Dubai time
WINDOW = timedelta(hours=24)
STOP = (r"^\W*(stop|unsubscribe|opt out|remove me|leave me alone|"
        r"(please )?(don'?t|do not|stop) (message|messaging|text|texting|contact|contacting|send(ing)?)( me)?( any ?more| again)?)\W*$"
        r"|^\W*(توقف|لا ترسل|لا تراسلني|стоп|хватит|отписаться|बंद करो|रोकें|停止|退订)\W*$")
CLOSED = {"Won", "Lost"}


def settings(g: Graph) -> dict:
    return QUIET | (g.settings.get("rania", {}).get("quiet") or {})


def _hhmm(v: str) -> tuple[int, int]:
    m = re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", v or "")
    if not m:
        raise ValueError("Use a time like 21:00")
    return int(m[1]), int(m[2])


def set_settings(office: Office, value: dict, *, by: str) -> dict:
    """Only the owner sets when follow-ups go out, how many, the quiet hours, the template, and what happens after."""
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes follow-ups")
    v = settings(office.graph()) | {k: value[k] for k in QUIET if k in value}
    try:
        hours = [float(h) for h in v["after_hours"]]
    except (TypeError, ValueError):
        raise ValueError("Follow-ups: times like 20h, 3d, 7d") from None
    if not 1 <= len(hours) <= 5 or any(h <= 0 for h in hours) or hours != sorted(set(hours)):
        raise ValueError("Follow-ups: one to five times, each later than the one before")
    v["after_hours"] = [int(h) if h == int(h) else h for h in hours]
    try:
        visit = [float(h) for h in v["after_visit_hours"]]
    except (TypeError, ValueError):
        raise ValueError("After a visit: times like 1d, 3d, 6d, 9d") from None
    if not 1 <= len(visit) <= 5 or any(h <= 0 for h in visit) or visit != sorted(set(visit)):
        raise ValueError("After a visit: one to five times, each later than the one before")
    v["after_visit_hours"] = [int(h) if h == int(h) else h for h in visit]
    _hhmm(v["quiet_from"]), _hhmm(v["quiet_to"])
    if v["then"] not in THEN:
        raise ValueError("Pick what happens after the last follow-up")
    v["then_after_hours"] = float(v["then_after_hours"])
    if v["then_after_hours"] <= 0:
        raise ValueError("After the last follow-up: a time after it")
    v["friday_prayer"], v["template"] = bool(v["friday_prayer"]), v["template"] or None
    office.log.append("setting.changed", actor=by, content={"person": "rania", "key": "quiet", "value": v})
    return v


def allowed(s: dict, t: datetime) -> bool:
    """Not in the owner's quiet hours, and not during Friday prayer when the owner ticks it."""
    t = t.astimezone(DUBAI)
    m = t.hour * 60 + t.minute
    a, b = (h * 60 + mi for h, mi in (_hhmm(s["quiet_from"]), _hhmm(s["quiet_to"])))
    if (a <= m or m < b) if a > b else (a <= m < b):
        return False
    if s["friday_prayer"] and t.weekday() == 4:
        (h1, m1), (h2, m2) = PRAYER
        return not (h1 * 60 + m1 <= m < h2 * 60 + m2)
    return True


def next_allowed(s: dict, t: datetime) -> datetime:
    """`t`, or the moment the quiet hours (or Friday prayer) end."""
    t = t.astimezone(DUBAI).replace(second=0, microsecond=0)
    for _ in range(4):
        if allowed(s, t):
            return t
        h, m = _hhmm(s["quiet_to"])
        if s["friday_prayer"] and t.weekday() == 4 and PRAYER[0] <= (t.hour, t.minute) < PRAYER[1]:
            h, m = PRAYER[1]
        nxt = t.replace(hour=h, minute=m)
        t = nxt if nxt > t else nxt + timedelta(days=1)
    return t


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _chat(g: Graph, deal: str):
    return next((c for c in g.of("chat") if c.deal == deal), None)


def lead_settings(g: Graph, deal: str | None) -> dict:
    """The office's schedule, or this lead's own when the broker set one (docs/lead-profile-spec.md)."""
    s = settings(g)
    own = (g.nodes[f"deal:{deal}"].props.get("followups") or {}) if deal and f"deal:{deal}" in g.nodes else {}
    return s | {"after_hours": own["after_hours"]} if own.get("after_hours") else s


def set_for_lead(office: Office, chat: str, *, by: str, after_hours: list | None = None, stopped: bool = False) -> dict | None:
    """The broker (or the owner) gives one lead its own schedule, stops its follow-ups (a person can still write to them),
    or puts it back on the office's schedule (neither given)."""
    from diwan import leads
    g = office.graph()
    deal = g.nodes[f"chat:{chat}"].deal
    leads._may_act(g, deal, by)
    if after_hours:
        try:
            hours = [float(h) for h in after_hours]
        except (TypeError, ValueError):
            raise ValueError("Follow-ups: times like 1d, 3d, 7d") from None
        if not 1 <= len(hours) <= 5 or any(h <= 0 for h in hours) or hours != sorted(set(hours)):
            raise ValueError("Follow-ups: one to five times, each later than the one before")
        after_hours = [int(h) if h == int(h) else h for h in hours]
    office.log.append("lead.followups", actor=by, deal=deal, content={"chat": chat, "after_hours": after_hours or None, "stopped": stopped})
    return office.graph().nodes[f"deal:{deal}"].props.get("followups")


def opted_out(g: Graph, chat) -> bool:
    """They said stop and have not written since. If they write again the door is open: a person may answer them."""
    d = g.nodes.get(f"deal:{chat.deal}")
    op = d.props.get("optout") if d else None
    return bool(op) and not any(m["type"] == "received" and m["event"] > op["event"] for m in chat.props["messages"])  # log order: the clock can tie


def after_visit(g: Graph, chat):
    """Their last appointment that took place, while they have not written since: the follow-ups count from it."""
    vs = [v for v in g.of("viewing", status="done") if v.props.get("chat") == chat.props["phone"]]
    if not vs:
        return None
    v = max(vs, key=lambda x: _at(x.props["at"]))
    last_in = next((m for m in reversed(chat.props["messages"]) if m["type"] == "received"), None)
    return None if last_in and last_in["event"] > v.props.get("closed_event", 0) else v


def why_not(g: Graph, chat, now: datetime) -> str | None:
    """Why this conversation gets no follow-up, in words a broker understands, or None when it is in the schedule."""
    d = g.nodes.get(f"deal:{chat.deal}")
    p = d.props if d else {}
    msgs = [m for m in chat.props["messages"] if m["type"] in ("received", "sent")]
    if p.get("optout"):
        return f"stopped: they said “{p['optout']['quote']}”"
    if (p.get("followups") or {}).get("stopped"):
        from diwan.people import name
        return f"stopped for this lead by {name(p['followups']['by'])}"
    if chat.props["mode"] != "ai":
        return "a person has the chat"
    if p.get("nurture"):
        return "in Nurture"
    if p.get("stage") in CLOSED or p.get("qualify_status") == "not_a_fit":
        return "closed"
    if not any(m["type"] == "received" and m.get("channel") not in ("propertyfinder", "bayut", "dubizzle") for m in msgs):
        return "they haven't written on WhatsApp yet"
    if msgs[-1]["type"] == "received":
        return "waiting for our reply"
    if any(v.props.get("chat") == chat.props["phone"] and _at(v.props["at"]) > now for v in g.of("viewing", status="booked")):
        return "a viewing is coming up"
    if any(v.props.get("chat") == chat.props["phone"] for v in g.of("viewing", status={"requested", "offered"})):
        return "a viewing is waiting for the owner"
    if any(t.deal == chat.deal and t.props.get("fraud") for t in g.of("task")):
        return "a message about payment details: a person handles it"
    if any(a.props["chat"] == chat.props["phone"] for a in g.of("attention", status="open")) and not after_visit(g, chat):
        return "the broker has it (an open card)"
    return None


def state(g: Graph, chat, now: datetime) -> dict:
    """Where this conversation is in the owner's schedule: how many follow-ups since the client last wrote, when the
    next one is due, or why there is none."""
    s = lead_settings(g, chat.deal)
    p = (g.nodes.get(f"deal:{chat.deal}") or chat).props
    last_in = next((m for m in reversed(chat.props["messages"]) if m["type"] == "received"), None)
    since = last_in["event"] if last_in else 0
    done = [n for n in p.get("nudges", []) if n["event"] > since]
    visit = after_visit(g, chat)
    own = bool((p.get("followups") or {}).get("after_hours"))
    hours = s["after_hours"] if own or not visit else s["after_visit_hours"]
    if visit:
        done = [n for n in done if _at(n["at"]) > _at(visit.props["at"])]
    out = {"sent": len(done), "delivered": sum(1 for n in done if n.get("sent") is not False),
           "of": len(hours), "last": done[-1] if done else None, "next": None, "then": None, "visit": visit.id if visit else None,
           "why_not": why_not(g, chat, now), "own": p.get("followups"), "after_hours": hours,
           "steps": [{"n": n["n"], "at": n["at"], "status": "sent" if n.get("sent") is not False else "skipped", "why": n.get("why"),
                      "text": next((m["text"] for m in chat.props["messages"] if m.get("nudge") == n["n"] and m["event"] > since), None)} for n in done]}
    if out["why_not"] or not last_in:
        return out
    base = _at(visit.props["at"]) if visit else _at(last_in["at"])
    out["steps"] += [{"n": i + 1, "at": next_allowed(s, base + timedelta(hours=h)).isoformat(), "status": "planned"}
                     for i, h in enumerate(hours) if i >= len(done)]
    if len(done) < len(hours):
        out["next"] = next_allowed(s, base + timedelta(hours=hours[len(done)])).isoformat()
    elif s["then"] != "nothing" and not p.get("went_quiet", 0) > since:
        out["then"] = next_allowed(s, _at(done[-1]["at"]) + timedelta(hours=s["then_after_hours"])).isoformat() if done else None
    return out


VISIT_TEXT = ["{hi}, thank you for coming to see {what}. What did you think?",
              "{hi}, any thoughts on {what}? If something didn't fit, tell me and I'll look for better options.",
              "{hi}, would you like to see {what} again, or shall I look for something else?",
              "{hi}, no rush at all. I'm here whenever you'd like to pick this up."]
VISIT_TEXT_AR = ["{hi}، شكراً لزيارتك {what}. ما رأيك؟",
                 "{hi}، هل لديك أي ملاحظات على {what}؟ إذا لم يناسبك شيء، أخبرني وسأبحث عن خيارات أفضل.",
                 "{hi}، هل تود رؤية {what} مرة أخرى، أم أبحث لك عن خيار آخر؟",
                 "{hi}، لا عجلة أبداً. أنا هنا متى ما أردت المتابعة."]


def text_for(g: Graph, deal: str, chat, arabic: bool, visit=None, n: int = 1) -> tuple[str, list[str]]:
    """Something useful, picking up where they left off. After a visit, about that visit."""
    from diwan import qualify
    from diwan.agents import reception
    d = g.nodes[f"deal:{deal}"].props
    first = reception.first_name(chat.label)
    hi = f"Hi {first}" if first else "Hi"
    if visit:
        lst = g.nodes.get(f"listing:{visit.props.get('listing')}")
        what = lst.props["title"] if lst else ("العقار" if arabic else "the property")
        texts = VISIT_TEXT_AR if arabic else VISIT_TEXT
        return texts[min(n, len(texts)) - 1].format(hi=f"مرحباً{' ' + first if first else ''}" if arabic else hi, what=what), [lst.id] if lst else []
    # she asked which home to see (and when) and they went quiet: that question, kindly, never a new topic
    mine = next((m for m in reversed(chat.props["messages"]) if m["type"] == "sent" and not m.get("nudge")), None)
    which = next((q.strip() for q in re.findall(r"[^.!?\n]*\?", mine["text"]) if re.match(r"\s*which (one |of these )?would you like to see", q, re.I)), None) if mine else None
    if which and not arabic:
        return f"{hi}, no rush: {which[0].lower() + which[1:]}", []
    sent = set(d.get("recommended") or [])
    if sent and not (d.get("hot") or {}).get("listing") and d.get("qualify_status") == "qualified":  # "fits what you told me" only once it does
        shown = sent | {r for m in chat.props["messages"] if m["type"] == "sent" for r in m.get("refs", [])}  # never one they've had
        new = [n for n in reception.recommend(g, deal, 5) if n.id not in shown]
        if new:
            first_rec = min((m["event"] for m in chat.props["messages"] if m["type"] == "sent" and set(m.get("refs", [])) & sent), default=None)
            fresh = first_rec is not None and (new[0].event or 0) > first_rec  # listed after the first options went out
            if arabic:
                lead = "وصلنا عقار جديد يناسب ما ذكرته" if fresh else "وجدت عقاراً آخر يناسب ما ذكرته"
                return f"مرحباً{' ' + first if first else ''}، {lead}: {reception._listing_line(new[0])}. هل تود معاينته؟", [new[0].id]
            lead = "a new one came in that fits what you told me" if fresh else "here's another one that fits what you told me"
            return f"{hi}, {lead}: {reception._listing_line(new[0])}. Would you like to see it?", [new[0].id]
        if arabic:
            return f"مرحباً{' ' + first if first else ''}، هل أعجبك أحد الخيارات التي أرسلتها؟ إذا لم يناسبك أي منها، أخبرني ماذا أغير وسأبحث مجدداً.", []
        which = "the option" if len(sent) == 1 else f"any of the {len(sent)} options"
        return f"{hi}, did {which} I sent catch your eye? If not, tell me what to change and I'll look again.", []
    # they cancelled their viewing and said nothing since: another time, or something else
    gone = sorted((v for v in g.of("viewing", status="cancelled") if v.props.get("chat") == chat.props["phone"] and v.props.get("listing")),
                  key=lambda v: v.props["at"])
    if gone and not any(v.props.get("chat") == chat.props["phone"] for v in g.of("viewing", status="booked")):
        lst = g.nodes.get(f"listing:{gone[-1].props['listing']}")
        what = lst.props["title"] if lst else gone[-1].props["listing"]
        if arabic:
            return f"مرحباً{' ' + first if first else ''}، هل تود موعداً آخر لمعاينة {what}، أم أبحث لك عن شيء آخر؟", [lst.id] if lst else []
        return f"{hi}, would you like another time to see {what}, or shall I look for something else?", [lst.id] if lst else []
    q = qualify.state(g, deal)
    if q["verdict"] != "DISCOVERY" and q.get("type") in ("seller", "landlord") and q["verdict"] != "ASK_QUESTION":
        broker = name(d["broker"])  # their own home: its next step, never "options"
        if arabic:
            return f"مرحباً{' ' + first if first else ''}، {broker} يجهز الخطوة التالية لعقارك. هل تود إضافة أي شيء؟", []
        return f"{hi}, {broker} is preparing the next step for your property. Is there anything you'd like to add?", []
    if q["verdict"] == "DISCOVERY":
        if arabic:
            return f"مرحباً{' ' + first if first else ''}، هل تبحث عن شراء أو إيجار أو بيع؟ أنا هنا متى ما كنت جاهز.", []
        return f"{hi}, are you looking to buy, rent or sell? I'm here whenever you're ready.", []
    nxt = q.get("next")
    if q["verdict"] == "ASK_QUESTION" and nxt:
        ask = nxt["question_ar"] if arabic and nxt.get("question_ar") else nxt["question_en"]
        if ask[:1].isupper() and ask[1:2].islower():
            ask = ask[0].lower() + ask[1:]
        return (f"مرحباً{' ' + first if first else ''}، لا عجلة: {ask}" if arabic else f"{hi}, no rush: {ask}"), []
    broker = name(d["broker"])
    if arabic:
        return f"مرحباً{' ' + first if first else ''}، {broker} يبحث عن خيارات تناسبك. هل تود إضافة أي شيء؟", []
    return f"{hi}, {broker} is looking for options that fit your brief. Is there anything you'd like to add?", []


def _template_params(g: Graph, deal: str, chat, t: dict) -> list[str]:
    from diwan.agents import reception
    d = g.nodes[f"deal:{deal}"].props
    area = str(((d.get("answers") or {}).get("areas") or {}).get("value") or "Dubai")
    return [reception.first_name(chat.label) or "there", area, name(d["broker"])][:int(t.get("params") or 0)]


def sweep(office: Office, now: datetime | None = None) -> list[str]:
    """Every minute: send the follow-ups that are due, then the owner's last step for those that stayed quiet."""
    from diwan import inbox, leads, lobby_room
    from diwan.agents import reception
    now = now or datetime.now(timezone.utc)
    out = []
    g = office.graph()
    s = settings(g)
    if not allowed(s, now):
        return out
    for chat in g.of("chat"):
        if not chat.deal or f"deal:{chat.deal}" not in g.nodes:
            continue
        st = state(g, chat, now)
        phone, deal = chat.props["phone"], chat.deal
        if st["next"] and _at(st["next"]) <= now:
            n = st["sent"] + 1
            last_in = next(m for m in reversed(chat.props["messages"]) if m["type"] == "received")
            arabic = any(re.search(r"[؀-ۿ]", m["text"]) for m in chat.props["messages"] if m["type"] == "received")
            text, refs = text_for(g, deal, chat, arabic, g.nodes.get(f"viewing:{st['visit']}") if st["visit"] else None, n)
            trial = lobby_room.followup(g, deal, n, now, arabic=arabic, first=reception.first_name(chat.label), broker=name(g.nodes[f"deal:{deal}"].props["broker"]))  # an approved experiment
            if trial:
                text, refs = trial["text"], []
            template = None
            if now - _at(last_in["at"]) >= WINDOW:  # WhatsApp: an approved template only
                use = (trial or {}).get("template") or s["template"]
                t = next((t for t in inbox.templates() if t["name"] == use), None) if use else None
                if not t:
                    office.log.append("followup.nudged", actor="rania", agent="rania", deal=deal,
                                      content={"chat": phone, "n": n, "sent": False, "why": "more than 24 hours: no template picked"})
                    out.append(f"skipped {phone} #{n}")
                    continue
                params = _template_params(g, deal, chat, t)
                template, text, refs = {"name": t["name"], "params": params, "language": t.get("language", "en")}, inbox.render(t["body"], params), []
            if any(m.get("nudge") and m["text"] == text for m in chat.props["messages"] if m["event"] > last_in["event"]):
                office.log.append("followup.nudged", actor="rania", agent="rania", deal=deal,
                                  content={"chat": phone, "n": n, "sent": False, "why": "it would repeat an earlier follow-up word for word"})
                out.append(f"skipped {phone} #{n}")
                continue
            ev = reception._send(office, phone, deal, text, refs, template=template, extra={"nudge": n})
            office.log.append("followup.nudged", actor="rania", agent="rania", deal=deal, caused_by=ev["id"],
                              content={"chat": phone, "n": n, "sent": ev["content"]["status"] == "sent", "text": text,
                                       "template": template["name"] if template else None, "experiment": trial["experiment"] if trial else None})
            out.append(f"nudged {phone} #{n}")
        elif st["then"] and _at(st["then"]) <= now:
            office.log.append("lead.went_quiet", actor="rania", agent="rania", deal=deal, content={"chat": phone, "after": st["sent"]})
            k = st["delivered"]
            what = f"went quiet after {k} follow-up{'s' if k != 1 else ''}"
            if s["then"] == "nurture":
                ev = office.log.append("lead.nurture", actor="rania", agent="rania", deal=deal,
                                       content={"reason": what, "quote": None, "to": reception.front_settings(g)["nurture_to"], "chat": phone})
                leads.notify(office, g.nodes[f"deal:{deal}"].props["broker"], f"{chat.label} {what}: moved to Nurture. You'll hear if they come back.",
                             chat=phone, kind="info", cause=ev["id"])
            else:
                leads.raise_card(office, phone, kind="call", now=now, replace=True,
                                 reason=f"Gone quiet: no reply to {k} follow-up{'s' if k != 1 else ''}. Call once, or leave it")
            out.append(f"quiet {phone}")
    return out


def stop(office: Office, phone: str, deal: str, text: str, cause: int) -> None:
    """"Stop": no more follow-ups or nurture messages, ever. A person cannot switch it back on."""
    office.log.append("lead.optout", actor=f"customer:{phone}", deal=deal, caused_by=cause, content={"quote": text[:200], "chat": phone})


def upcoming(g: Graph, now: datetime, limit: int = 20) -> list[dict]:
    """For the owner: the next follow-ups due across the office."""
    out = []
    for chat in g.of("chat"):
        if not chat.deal or f"deal:{chat.deal}" not in g.nodes:
            continue
        st = state(g, chat, now)
        if st["next"] or st["then"]:
            out.append({"chat": chat.props["phone"], "name": chat.label, "n": st["sent"] + 1 if st["next"] else None, "of": st["of"],
                        "at": st["next"] or st["then"], "what": "follow-up" if st["next"] else settings(g)["then"]})
    return sorted(out, key=lambda r: r["at"])[:limit]
