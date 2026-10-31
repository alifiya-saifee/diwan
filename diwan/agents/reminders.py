"""Reminders for booked appointments (docs/calendar-spec.md): the client the day before and two hours before (the owner's
times), with where to go and what to bring, never in quiet hours and never after "stop"; each broker, every working
morning, their appointments for the day. Runs with the other sweeps (app.morning_loop)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from diwan import slots
from diwan.graph import Graph
from diwan.office import Office
from diwan.people import name

REMIND = {"hours_before": [24, 2], "template": "viewing_reminder", "broker_morning": True,
          "change_template": "appointment_changed", "cancel_template": "appointment_cancelled"}  # for a move or cancel after the 24-hour window


def settings(g: Graph) -> dict:
    return REMIND | (g.settings.get("sales", {}).get("reminders") or {})


def set_settings(office: Office, value: dict, *, by: str) -> dict:
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes reminders")
    v = settings(office.graph()) | {k: value[k] for k in REMIND if k in value}
    try:
        hrs = sorted({float(h) for h in v["hours_before"]}, reverse=True)
    except (TypeError, ValueError):
        raise ValueError("Reminders: hours before, like 24, 2") from None
    if len(hrs) > 3 or any(h <= 0 or h > 72 for h in hrs):
        raise ValueError("Reminders: up to three, each 1 to 72 hours before")
    v["hours_before"] = [int(h) if h == int(h) else h for h in hrs]
    v["template"], v["broker_morning"] = v["template"] or None, bool(v["broker_morning"])
    v["change_template"], v["cancel_template"] = v["change_template"] or None, v["cancel_template"] or None
    office.log.append("setting.changed", actor=by, content={"person": "sales", "key": "reminders", "value": v})
    return v


def _where(g: Graph, v) -> str:
    p = v.props
    if p.get("where") == "phone":
        return f"{name(p['broker'])} will call you on this number."
    if p.get("where") == "video":
        url = (p.get("link") or {}).get("url")
        return f"Join here: {url}" if url else f"{name(p['broker'])} will send you the video link."
    if p.get("where") == "office":
        return "At our office."
    lst = g.nodes.get(f"listing:{p['listing']}") if p.get("listing") else None
    if not lst:
        return ""
    lp = lst.props
    pin = f" Map: https://maps.google.com/?q={lp['lat']},{lp['lng']}" if lp.get("lat") and lp.get("lng") else ""
    return f"At {lp['title']}, {lp['community']}.{pin}"


def text(g: Graph, v, first: str | None) -> str:
    from diwan.agents import reception
    p = v.props
    k = slots.kind(g, p.get("kind"))
    lst = g.nodes.get(f"listing:{p['listing']}") if p.get("listing") else None
    what = reception.yours(k, lst)
    bring = " Please bring a photo ID for the building lobby." if k["where"] == "property" and any(
        "photo id" in i["text"].lower() for i in reception.customer_knowledge(g, "viewing photo id lobby", k=6)) else ""
    return (f"Hi{' ' + first if first else ''}, a reminder of {what} with {name(p['broker'])}, {slots.say(datetime.fromisoformat(p['at']))}. "
            f"{_where(g, v)}{bring} Reply here if you need to change it.").replace("  ", " ")


def sweep(office: Office, now: datetime | None = None) -> list[str]:
    from diwan import inbox, leads
    from diwan.agents import nudge, reception
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    s, quiet = settings(g), nudge.settings(g)
    out = []
    if nudge.allowed(quiet, now):
        for v in g.of("viewing", status="booked"):
            p = v.props
            at = datetime.fromisoformat(p["at"])
            chat = g.nodes.get(f"chat:{p.get('chat')}")
            if at <= now or not chat or p.get("where") == "phone":  # a call-back isn't reminded: the broker's list has it
                continue
            due = [h for h in s["hours_before"] if now >= at - timedelta(hours=h) and f"{h}h" not in (p.get("reminded") or [])]
            if not due:
                continue
            which = f"{min(due)}h"  # the closest one; an earlier one that was missed is not sent late
            d = g.nodes.get(f"deal:{chat.deal}")
            if d and d.props.get("optout"):
                continue
            first = reception.first_name(chat.label)
            msg, template = text(g, v, first), None
            if not inbox.conversation(g, chat, now)["window_open"]:
                t = next((t for t in inbox.templates() if t["name"] == s["template"]), None) if s["template"] else None
                if not t:
                    office.log.append("appointment.reminded", actor="rania", agent="rania", deal=chat.deal,
                                      content={"id": v.id, "which": which, "sent": False, "why": "more than 24 hours: no template picked"})
                    out.append(f"skipped {v.id} {which}")
                    continue
                params = [first or "there", reception._what(g, slots.kind(g, p.get("kind")), g.nodes.get(f"listing:{p['listing']}") if p.get("listing") else None),
                          slots.say(at)][:int(t.get("params") or 0)]
                template, msg = {"name": t["name"], "params": params, "language": t.get("language", "en")}, inbox.render(t["body"], params)
            ev = reception._send(office, chat.props["phone"], chat.deal, msg, [v.id], template=template, extra={"reminder": which})
            office.log.append("appointment.reminded", actor="rania", agent="rania", deal=chat.deal, caused_by=ev["id"],
                              content={"id": v.id, "which": which, "sent": True, "template": template["name"] if template else None})
            for h in s["hours_before"]:  # the ones before it were missed: never sent late
                if h > float(which[:-1]) and f"{h}h" not in (p.get("reminded") or []):
                    office.log.append("appointment.reminded", actor="rania", agent="rania", deal=chat.deal,
                                      content={"id": v.id, "which": f"{h}h", "sent": False, "why": "booked after that time"})
            out.append(f"reminded {v.id} {which}")
    if s["broker_morning"]:
        local = now.astimezone(slots.DUBAI)
        for b in leads.brokers():
            w = slots.window(g, b, local.date())
            if not w or local.hour * 60 + local.minute < w[0] - 60:
                continue
            today = sorted((v for v in g.of("viewing", status="booked") if v.props["broker"] == b
                            and datetime.fromisoformat(v.props["at"]).astimezone(slots.DUBAI).date() == local.date()), key=lambda v: v.props["at"])
            if not today:
                continue
            ev = office.log.append("calendar.morning", actor="rania", agent="rania", key=f"morning:{b}:{local.date()}",
                                   content={"broker": b, "ids": [v.id for v in today]})
            if ev.get("duplicate"):
                continue
            lines = "; ".join(f"{datetime.fromisoformat(v.props['at']).astimezone(slots.DUBAI):%H:%M} {v.props.get('kind_name') or 'Viewing'}"
                              f"{' of ' + v.props['listing'] if v.props.get('listing') else ''} with {v.props.get('customer')}" for v in today)
            leads.notify(office, b, f"Today, {len(today)} appointment{'s' if len(today) != 1 else ''}: {lines}.", kind="info", cause=ev["id"])
            out.append(f"morning {b}")
    return out
