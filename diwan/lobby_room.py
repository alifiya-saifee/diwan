"""Room 9, the Lobby (docs/closed-loop-spec.md L279-295): where the agents read what works elsewhere and what went wrong here,
and propose changes to their own office. Not to be confused with agents/lobby.py, the requests board, which kept the old
event names (D10).

Weekly, each room's rep writes a thread from the log. It ends in at most one proposal. A proposal is an experiment: what
changes, for whom, for how long, and the number Records will watch. Nothing changes until the owner approves. While it runs,
half of its audience gets the change and the other half is the comparison. When the period ends the change stops by itself,
the Data analyst reports, and the owner keeps it or rolls it back.

An experiment is an overlay read where the work happens, never a setting: nothing here writes `setting.changed` for anything
but the Lobby's own rules, so rolling back leaves the office exactly as it was. Rules-only: no model is called.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from diwan import roles
from diwan.agents.charters import BY_ID
from diwan.graph import Graph
from diwan.office import Office
from diwan.people import PEOPLE, name

HOST = "lhost"
ROOMS = {"front": ("Front desk", "lfront"), "sales": ("Sales", "lsales"), "mkt": ("Marketing", "lmkt"), "deal": ("Deal", "ldeal"), "ops": ("Operations", "lops"),
         "fin": ("Finance", "lfin"), "comp": ("Compliance", "lcomp"), "review": ("Review", "lreview"), "records": ("Records", "lrecords")}
DEFAULTS = {"thread_day": 0, "thread_hour": 7, "period_days": 14, "control_pct": 50, "min_signal": 2, "min_sample": 20, "playbooks_opt_in": False}

KINDS = {"followup": {"label": "A new follow-up message", "room": "sales", "metrics": ["reply_rate", "viewing_rate"]},
         "question": {"label": "A qualifying question", "room": "sales", "metrics": ["qualified_rate", "viewing_rate", "converted_rate"]},
         "step": {"label": "A checklist step", "room": "deal", "metrics": ["sent_back_rate", "flagged_rate"]},
         "content": {"label": "A content idea", "room": "mkt", "metrics": ["leads_per_post"]},
         "instruction": {"label": "A change to an agent's instructions", "room": "review", "metrics": ["send_backs"]}}
METRICS = {"reply_rate": ("Clients who reply to a follow-up", True), "viewing_rate": ("New leads who book a viewing", True),
           "qualified_rate": ("New leads who qualify", True), "converted_rate": ("New leads who convert", True),
           "sent_back_rate": ("Converted deals with work sent back", False), "flagged_rate": ("Converted deals with a flagged payment", False), "leads_per_post": ("Leads per post", True),
           "send_backs": ("Work sent back from this agent", False)}
AUDIENCE = ("language", "channel", "qtype", "broker")

# what can never change from here, whoever asks and however it is put (L295)
RULE_WORDS = (r"\b(compliance|complian\w+|screen(ing|ed)?|sanctions?|peps?|kyc|aml|goaml|source of funds|permits?|thresholds?|clearance|"
              r"bypass|settings?|gates?|commission rates?|quiet hours)\b")
PROTECTED = {"comp", "screen", "sof", "report", "devil", "review", "factcheck", "mpermit"}


class Guardrail(ValueError):
    """The Lobby may not do this."""


def settings(g: Graph) -> dict:
    return DEFAULTS | (g.settings.get("lobby", {}).get("rules") or {})


def set_settings(office: Office, value: dict, *, by: str) -> dict:
    """The Lobby's own rules: only the owner, and they change nothing outside this room."""
    _owner(by)
    v = settings(office.graph()) | {k: value[k] for k in DEFAULTS if k in value}
    try:
        for k in ("thread_day", "thread_hour", "period_days", "control_pct", "min_signal", "min_sample"):
            v[k] = int(v[k])
    except (TypeError, ValueError):
        raise ValueError("The Lobby's rules are whole numbers") from None
    if not (0 <= v["thread_day"] <= 6 and 0 <= v["thread_hour"] <= 23 and 3 <= v["period_days"] <= 90 and 0 <= v["control_pct"] <= 90 and v["min_signal"] >= 1 and v["min_sample"] >= 1):
        raise ValueError("Check the numbers: a day 0 to 6, an hour 0 to 23, 3 to 90 days, a comparison group of at most 90%")
    v["playbooks_opt_in"] = bool(v["playbooks_opt_in"])
    office.log.append("setting.changed", actor=by, content={"person": "lobby", "key": "rules", "value": v})
    return v


def _owner(by: str) -> None:
    if PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError("Only the owner decides this")


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)  # the log's clock, so times compare as text


def _owner_id() -> str:
    return next(k for k, p in PEOPLE.items() if p["role"] == "Owner")


def _named(who: str | None) -> str | None:
    return BY_ID[who].name if who in BY_ID else name(who) if who else None


# ---------- never client data (L285) ----------

def _client_words(g: Graph) -> set[str]:
    out = set()
    for n in g.of("chat"):
        out |= {w.lower() for w in re.findall(r"[^\W\d_]{3,}", n.label or "")}
    for d in g.deals():
        out |= {w.lower() for w in re.findall(r"[^\W\d_]{3,}", d.props.get("customer") or "")}
    return out - {w.lower() for p in PEOPLE.values() for w in p["name"].split()} - {"client", "customer", "lead", "new", "the", "buyer", "tenant", "seller", "whatsapp", "unknown"}


def client_free(g: Graph, *texts: str) -> None:
    """Refuses a phone number, an email or a client's name: the Lobby is read by every room and fed from outside."""
    words = _client_words(g)
    for text in texts:
        t = text or ""
        if re.search(r"(?<!\d)\+?\d[\d ()-]{7,}\d(?!\d)", t) or re.search(r"[\w.+-]+@[\w-]+\.\w+", t):
            raise Guardrail("Take out the phone number or email: client details stay out of the Lobby")
        if hit := next((w for w in re.findall(r"[^\W\d_]{3,}", t) if w.lower() in words), None):
            raise Guardrail(f"Take out \"{hit}\": client names stay out of the Lobby")


def clean_words(g: Graph, text: str) -> bool:
    try:
        client_free(g, text)
        return True
    except Guardrail:
        return False


def _safe(g: Graph, text: str, other: str = "Other") -> str:
    """A reason a person typed can name the client: the rep counts it under `other` instead."""
    return text if clean_words(g, text) else other


# ---------- what a proposal may be ----------

def check(office: Office, g: Graph, x: dict) -> None:
    """Every proposal, and again what the owner approves, whoever wrote it."""
    from diwan.agents import lessons
    from diwan.agents.studio import BANNED
    kind = KINDS.get(x.get("kind"))
    if not kind:
        raise Guardrail(f"The Lobby can propose: {', '.join(k['label'].lower() for k in KINDS.values())}. Nothing else changes from here")
    title, text = str(x.get("title") or "").strip(), str(x.get("text") or "").strip()
    if not title or not text:
        raise ValueError("Say what changes")
    if x.get("metric") not in kind["metrics"]:
        raise ValueError(f"Pick a number Records can watch: {', '.join(METRICS[m][0].lower() for m in kind['metrics'])}")
    if not 3 <= int(x.get("days") or 0) <= 90:
        raise ValueError("An experiment runs for 3 to 90 days")
    if not 0 <= int(x.get("control_pct", 50)) <= 90:
        raise ValueError("Keep at most 90% as the comparison")
    if bad := set(x.get("audience") or {}) - set(AUDIENCE):
        raise ValueError(f"Audience can't be set by {', '.join(sorted(bad))}")
    blob = " ".join([title, text])
    if re.search(RULE_WORDS, blob, re.I):
        raise Guardrail("Compliance rules and the owner's settings can't be changed from the Lobby")
    if re.search(BANNED, blob, re.I):
        raise Guardrail("That promises what the office can't: take the promise out")
    if lessons.broken(office.log, "rania", text):
        raise Guardrail("That breaks a lesson the team taught Rania")
    client_free(g, title, text, *(str(v) for k, v in (x.get("audience") or {}).items() if k != "broker"))
    if x["kind"] == "instruction" and (x.get("agent") not in BY_ID or x["agent"] in PROTECTED):
        raise Guardrail("Compliance and Review agents' instructions can't be changed from the Lobby" if x.get("agent") in PROTECTED else "Say which agent")
    if x["kind"] == "instruction" and not text.lower().startswith("always "):
        raise ValueError("An instruction starts with \"Always\": the Lobby adds to what an agent does, it never takes a rule away")
    if x["kind"] == "followup" and not 1 <= int(x.get("n") or 1) <= 5:
        raise ValueError("Say which follow-up it replaces, 1 to 5")
    if x["kind"] == "content" and len(text) < 30:
        raise ValueError("Write the facts a video may use: a script is written only from them")


def propose(office: Office, draft: dict, *, by: str, cause: int | None = None) -> str:
    """Agents and the Sales lead may propose (L404, L295). Proposing changes nothing."""
    if by not in BY_ID and PEOPLE.get(by, {}).get("role") not in ("Owner", "Sales manager"):
        raise PermissionError("Only the Sales lead and the owner propose in the Lobby")
    g = office.graph()
    s = settings(g)
    x = {"kind": draft.get("kind"), "room": draft.get("room") or KINDS.get(draft.get("kind"), {}).get("room"), "title": str(draft.get("title") or "").strip()[:120],
         "text": str(draft.get("text") or "").strip()[:800], "why": str(draft.get("why") or "").strip()[:400], "audience": {k: v for k, v in (draft.get("audience") or {}).items() if v},
         "days": int(draft.get("days") or s["period_days"]), "metric": draft.get("metric") or KINDS.get(draft.get("kind"), {"metrics": [None]})["metrics"][0],
         "control_pct": int(draft.get("control_pct", s["control_pct"])), "n": int(draft.get("n") or 1), "agent": draft.get("agent"), "template": draft.get("template") or None}
    check(office, g, x)
    xid = office._next(g, "experiment", "EX")
    office.log.append("experiment.proposed", actor=by, agent=HOST, caused_by=cause, content={"id": xid, **x})
    return xid


def _overlap(a: dict, b: dict) -> bool:
    return not any(a.get(k) and b.get(k) and a[k] != b[k] for k in AUDIENCE)


def approve(office: Office, xid: str, *, by: str, edits: dict | None = None, now: datetime | None = None) -> dict:
    """The owner's yes, which may first change the words, the audience or the period. Two experiments on the same thing for the
    same people can't both run: nobody could say which one did it."""
    from diwan import leads
    _owner(by)
    now, g = _now(now), office.graph()
    n = g.nodes[xid]
    if n.status != "proposed":
        raise ValueError(f"This experiment is {n.status}")
    keep = ("kind", "room", "title", "text", "why", "audience", "days", "metric", "control_pct", "n", "agent", "template")
    x = {k: n.props.get(k) for k in keep} | {k: v for k, v in (edits or {}).items() if k in keep and k not in ("kind", "room")}
    x["audience"] = {k: v for k, v in (x.get("audience") or {}).items() if v}
    x["days"], x["control_pct"], x["n"] = int(x["days"]), int(x["control_pct"]), int(x["n"] or 1)
    check(office, g, x)
    for o in g.of("experiment", status={"running", "kept"}):
        same = o.props["kind"] == x["kind"] and o.props.get("n") == x["n"] and o.props.get("agent") == x.get("agent")
        if same and x["kind"] != "content" and _overlap(o.props.get("audience") or {}, x["audience"]):
            raise ValueError(f"{o.id} already changes this for these people: end it first")
    ev = office.log.append("experiment.approved", actor=by, agent=HOST, content={"id": xid, **x, "starts": now.isoformat(), "ends": (now + timedelta(days=x["days"])).isoformat()})
    _switch_on(office, xid, by, cause=ev["id"])
    leads.notify(office, roles_room(office.graph(), x["room"]), f"Experiment {xid} is running: {x['title']}. {x['days']} days, watching {METRICS[x['metric']][0].lower()}.", kind="info", cause=ev["id"])
    return view_of(office, office.graph().nodes[xid], now)


def roles_room(g: Graph, room: str) -> str:
    """Who hears about a change in their room."""
    role = {"deal": "transactions", "ops": "transactions", "fin": "finance", "comp": "compliance"}.get(room)
    title = {"sales": "Sales manager", "mkt": "Marketing manager"}.get(room)
    return (roles.holder(g, role) if role else next((k for k, p in PEOPLE.items() if p["role"] == title), None)) or _owner_id()


def refuse(office: Office, xid: str, *, by: str, reason: str = "") -> None:
    _owner(by)
    n = office.graph().nodes[xid]
    if n.status != "proposed":
        raise ValueError(f"This experiment is {n.status}")
    office.log.append("experiment.refused", actor=by, agent=HOST, content={"id": xid, "reason": reason.strip()[:300]})


def _switch_on(office: Office, xid: str, by: str, cause: int | None = None) -> None:
    """Two kinds act once rather than being read where the work happens: an agent's instruction is a dated lesson while it
    lasts, and a content idea reaches the Studio as an idea its people may write, or not."""
    from diwan import topics
    from diwan.agents import lessons
    n = office.graph().nodes[xid]
    p = n.props
    if p["kind"] == "instruction":
        lid = lessons.add(office.log, {"agent": p["agent"], "kind": "always", "rule": p["text"], "phrase": None}, by=by)
        office.log.append("experiment.switched", actor=HOST, agent=HOST, caused_by=cause, content={"id": xid, "lesson": lid})
    elif p["kind"] == "content" and not p.get("topic"):
        ref = topics.save(office, {"title": p["title"][:90], "what": p["text"]}, by=by)
        office.log.append("content.idea", actor="midea", agent="midea", caused_by=cause, content={"ref": ref, "title": p["title"], "experiment": xid})
        office.log.append("experiment.switched", actor=HOST, agent=HOST, caused_by=cause, content={"id": xid, "topic": ref})


def _switch_off(office: Office, xid: str, by: str, cause: int | None = None, *, forever: bool = False) -> None:
    from diwan import topics
    from diwan.agents import lessons
    p = office.graph().nodes[xid].props
    if p["kind"] == "instruction" and p.get("lesson"):
        lessons.remove(office.log, p["lesson"], by=by)
        office.log.append("experiment.switched", actor=HOST, agent=HOST, caused_by=cause, content={"id": xid, "lesson": None})
    elif p["kind"] == "content" and forever and p.get("topic"):
        topics.save(office, {"status": "removed"}, by=by, ref=p["topic"])  # what was already filmed or posted stays Marketing's to manage


def finish(office: Office, xid: str, outcome: str, *, by: str, reason: str = "", now: datetime | None = None) -> None:
    """Keep or roll back: the owner's, at the end or early. Rolled back, the office is as it was. Kept, the whole audience gets it."""
    from diwan import leads
    _owner(by)
    if outcome not in ("kept", "rolled back"):
        raise ValueError("Keep it or roll it back")
    now, n = _now(now), office.graph().nodes[xid]
    if n.status not in ("running", "reporting", "kept") or (n.status == "kept" and outcome == "kept"):
        raise ValueError(f"This experiment is {n.status}")
    if n.status == "running":
        report(office, xid, now=now, notify=False)
    ev = office.log.append("experiment.ended", actor=by, agent=HOST, content={"id": xid, "outcome": outcome, "reason": reason.strip()[:300], "at": now.isoformat()})
    if outcome == "kept":
        _switch_on(office, xid, by, cause=ev["id"])
    else:
        _switch_off(office, xid, by, cause=ev["id"], forever=True)
    leads.notify(office, roles_room(office.graph(), n.props["room"]), f"Experiment {xid} {outcome}: {n.props['title']}.", kind="info", cause=ev["id"])


def report(office: Office, xid: str, *, now: datetime | None = None, notify: bool = True) -> dict:
    """The period is over: the change stops, and Records says what the number did."""
    from diwan import leads
    now, g = _now(now), office.graph()
    n = g.nodes[xid]
    if n.status != "running":
        return n.props.get("result") or {}
    r = measure(office, g, n, now)
    ev = office.log.append("experiment.reported", actor="analyst", agent="analyst", key=f"experiment-report:{xid}", content={"id": xid, "result": r})
    _switch_off(office, xid, "analyst", cause=ev["id"])
    if notify:
        leads.notify(office, _owner_id(), f"Experiment {xid} has finished. {r['line']} Keep it or roll it back in the Lobby.", kind="info", cause=ev["id"])
    return r


# ---------- is this lead or deal in the experiment? ----------

def language(g: Graph, deal: str) -> str:
    chat = next((c for c in g.of("chat") if c.deal == deal), None)
    said = [m["text"] for m in chat.props["messages"] if m["type"] == "received"] if chat else []
    return "ar" if any(re.search(r"[؀-ۿ]", t) for t in said) else "en"


def channel(g: Graph, deal: str) -> str:
    chat = next((c for c in g.of("chat") if c.deal == deal), None)
    first = next((m for m in chat.props["messages"] if m["type"] == "received"), None) if chat else None
    return (first or {}).get("channel") or "whatsapp"


def in_audience(g: Graph, deal: str, audience: dict) -> bool:
    d = g.nodes.get(f"deal:{deal}")
    if not d:
        return False
    a = audience or {}
    return ((not a.get("language") or language(g, deal) == a["language"]) and (not a.get("channel") or channel(g, deal) == a["channel"])
            and (not a.get("qtype") or d.props.get("qtype") == a["qtype"]) and (not a.get("broker") or d.props.get("broker") == a["broker"]))


def arm(xid: str, deal: str, control_pct: int) -> str:
    """Stable: the same lead is always on the same side, so the comparison can be recounted from the log."""
    return "control" if int(hashlib.sha256(f"{xid}:{deal}".encode()).hexdigest(), 16) % 100 < control_pct else "test"


def applies(g: Graph, x, deal: str, now: datetime | None = None) -> bool:
    """Only for its audience and only for its period. Kept, for all of its audience."""
    p = x.props
    if not in_audience(g, deal, p.get("audience") or {}):
        return False
    if x.status == "kept":
        return True
    return x.status == "running" and _at(p["starts"]) <= _now(now) < _at(p["ends"]) and arm(x.id, deal, p.get("control_pct", 0)) == "test"


def change(g: Graph, deal: str, kind: str, now: datetime | None = None, **match):
    return next((x for x in g.of("experiment", status={"running", "kept"}) if x.props["kind"] == kind and all(x.props.get(k) == v for k, v in match.items())
                 and applies(g, x, deal, now)), None)


def followup(g: Graph, deal: str, n: int, now: datetime, *, arabic: bool, first: str | None, broker: str) -> dict | None:
    """The experiment's words for this follow-up, or None for the usual one. A message written in English doesn't go to a client
    who writes Arabic, unless the audience says so."""
    x = change(g, deal, "followup", now, n=n)
    if not x or (arabic and (x.props.get("audience") or {}).get("language") != "ar"):
        return None
    return {"experiment": x.id, "template": x.props.get("template"),
            "text": x.props["text"].replace("{name}", first or "there").replace("{broker}", broker)}


def question_field(g: Graph, deal: str, now: datetime | None = None) -> dict | None:
    """One more question for new leads in the audience. "Not sure" is always accepted, and a lead already being asked keeps its form."""
    d = g.nodes.get(f"deal:{deal}")
    x = change(g, deal, "question", now)
    if not x or not d or d.event < x.props.get("started", 0) or (language(g, deal) == "ar" and (x.props.get("audience") or {}).get("language") != "ar"):
        return None
    return {"key": f"lobby_{x.id.lower()}", "label": x.props["title"], "question_en": x.props["text"], "question_ar": x.props["text"], "kind": "text", "options": [], "required": True,
            "ask_if": None, "strict": False, "experiment": x.id}


def on_convert(office: Office, deal: str, now: datetime | None = None) -> None:
    """A checklist step for converted deals in the audience. It sits beside the gates: nothing here can remove or pass one."""
    g = office.graph()
    x = change(g, deal, "step", now)
    if x and not any(t.props.get("experiment") == x.id for t in g.of("task", deal)):
        office.add_task(deal, "deal", x.props["text"], needs_person=roles.holder(g, "transactions"), by=HOST, props={"experiment": x.id})


# ---------- Records: the number, with the rows behind it ----------

def send_backs(office: Office, g: Graph, since: str | None = None, until: str | None = None) -> list[dict]:
    """Work a checker returned: whose it was, and why."""
    out = []
    for e in office.log.list():
        if (since and e["at"] < since) or (until and e["at"] >= until):
            continue
        c = e["content"]
        if e["type"] == "review.returned":
            dr = g.nodes.get(c.get("draft"))
            out.append({"agent": (dr.props.get("agent") if dr else None) or "deck", "why": c.get("reason") or "Sent back", "deal": e["deal"], "event": e["id"]})
        elif e["type"] == "qa.failed":
            for f in c.get("fails") or c.get("failures") or []:
                out.append({"agent": f.get("owner") or e["agent"], "why": f.get("rule") or "Failed a check", "deal": e["deal"], "event": e["id"]})
    return out


def _rate(hits: set, pool: set) -> dict:
    return {"n": len(hits), "of": len(pool), "rate": round(len(hits) / len(pool), 3) if pool else None, "refs": sorted(pool)[:50], "hits": sorted(hits)[:50]}


def measure(office: Office, g: Graph, x, now: datetime | None = None) -> dict:
    """What the number is so far. Test against the comparison group, from the log alone, so anyone can recount it."""
    p = x.props
    start, end = p["starts"], min(p["ends"], _now(now).isoformat())
    ev = [e for e in office.log.list() if start <= e["at"] < end]
    metric, higher = p["metric"], METRICS[p["metric"]][1]
    if metric == "leads_per_post":
        posts, rest = set(), set()
        for e in ev:
            if e["type"] == "post.live":
                (posts if e["content"].get("ref") == p.get("topic") else rest).add(e["content"].get("ref"))
        got, other = set(), set()
        for e in ev:
            if e["type"] == "lead.attributed" and e["deal"]:
                (got if e["content"].get("ref") == p.get("topic") else other).add(e["deal"])
        test, control = {"n": len(got), "of": len(posts), "rate": round(len(got) / len(posts), 2) if posts else None, "refs": sorted(got)[:50]}, \
                        {"n": len(other), "of": len(rest), "rate": round(len(other) / len(rest), 2) if rest else None, "refs": sorted(other)[:50]}
    elif metric == "send_backs":
        span = _at(end) - _at(start)
        now_ = [s for s in send_backs(office, g, start, end) if s["agent"] == p["agent"]]
        was = [s for s in send_backs(office, g, (_at(start) - span).isoformat(), start) if s["agent"] == p["agent"]]
        test = {"n": len(now_), "of": 1, "rate": len(now_), "refs": sorted({s["deal"] for s in now_ if s["deal"]})[:50]}
        control = {"n": len(was), "of": 1, "rate": len(was), "refs": sorted({s["deal"] for s in was if s["deal"]})[:50]}
    else:
        aud = p.get("audience") or {}
        if metric == "reply_rate":
            pool = {e["deal"] for e in ev if e["type"] == "followup.nudged" and e["content"].get("sent") and e["deal"]}
            first = {}
            for e in ev:
                if e["type"] == "followup.nudged" and e["content"].get("sent"):
                    first.setdefault(e["deal"], e["id"])
            hit = {e["deal"] for e in ev if e["type"] == "chat.received" and e["deal"] in first and e["id"] > first[e["deal"]]}
        elif metric in ("sent_back_rate", "flagged_rate"):
            pool = {e["deal"] for e in ev if e["type"] == "case.converted"}
            hit = {e["deal"] for e in ev if e["type"] == ("review.returned" if metric == "sent_back_rate" else "payment.flagged")}
        else:
            pool = {d.deal for d in g.deals() if start <= d.at < end}
            kinds = {"viewing_rate": {"appointment.booked"}, "qualified_rate": {"qualify.passed"}, "converted_rate": {"case.converted"}}[metric]
            hit = {e["deal"] for e in ev if e["type"] in kinds}
        pool = {d for d in pool if in_audience(g, d, aud)}
        ta = {d for d in pool if arm(x.id, d, p.get("control_pct", 0)) == "test"}
        test, control = _rate(hit & ta, ta), _rate(hit & (pool - ta), pool - ta)
    min_n = settings(g)["min_sample"]
    return {"metric": metric, "label": METRICS[metric][0], "higher_is_better": higher, "test": test, "control": control, "min_sample": min_n,
            "as_of": _now(now).isoformat(), **_verdict(metric, test, control, higher, min_n)}


def _verdict(metric: str, t: dict, c: dict, higher: bool, min_n: int) -> dict:
    label = METRICS[metric][0]
    if metric == "send_backs":
        said = f"{label}: {t['n']} in the period, {c['n']} in the same time before it."
        if t["n"] + c["n"] < min_n:
            return {"verdict": "too few to say", "line": said + " Too few to say."}
        return {"verdict": "better" if t["n"] < c["n"] else "worse" if t["n"] > c["n"] else "no clear difference", "line": said}
    show = (lambda r: "none yet" if r is None else f"{r:.2f}") if metric == "leads_per_post" else (lambda r: "none yet" if r is None else f"{r:.0%}")
    said = f"{label}: {show(t['rate'])} with the change ({t['n']} of {t['of']}), {show(c['rate'])} without it ({c['n']} of {c['of']})."
    if metric == "leads_per_post":
        if t["of"] < 1 or c["of"] < 1:
            return {"verdict": "too few to say", "line": said + " Too few to say."}
        return {"verdict": "better" if t["rate"] > c["rate"] else "no clear difference", "line": said}
    if min(t["of"], c["of"]) < min_n:
        return {"verdict": "too few to say", "line": said + f" Too few to say: it needs {min_n} on each side."}
    pooled = (t["n"] + c["n"]) / (t["of"] + c["of"])
    se = math.sqrt(pooled * (1 - pooled) * (1 / t["of"] + 1 / c["of"]))
    gap = t["rate"] - c["rate"]
    if not se or abs(gap) < 1.96 * se:
        return {"verdict": "no clear difference", "line": said + " No clear difference."}
    good = gap > 0 if higher else gap < 0
    return {"verdict": "better" if good else "worse", "line": said + (" Better with the change." if good else " Worse with the change.")}


# ---------- what the reps read ----------

TOPICS = {"service charges": r"service charge", "payment plans": r"payment plan|instal", "mortgages": r"mortgage|loan", "handover dates": r"handover|hand over|completion",
          "parking": r"parking", "pets": r"\bpets?\b", "schools": r"school", "visas": r"visa", "rental yield": r"yield|rental return|roi"}


def signals(office: Office, g: Graph, since: str, until: str) -> dict:
    """Counts and categories only, never what a client said: their words stay in their chat."""
    events = [e for e in office.log.list() if since <= e["at"] < until]
    byid = {e["id"]: e for e in office.log.list()}
    s = {"lost": Counter(), "gaps": Counter(), "handovers": 0, "docs": Counter(), "recalled": 0, "reopened": 0, "flagged": 0, "reminded": 0, "held": 0,
         "backs": Counter(), "back_why": Counter(), "rival": None, "blocked": 0}
    from diwan import sales
    for e in events:
        t, c = e["type"], e["content"]
        if t == "lead.outcome" and c.get("outcome") == "not_interested":
            s["lost"][sales.LOST_REASONS.get(c.get("reason"), "Other")] += 1
        elif t == "lead.outcome" and c.get("outcome") == "no_response":
            s["lost"]["No response"] += 1
        elif t == "case.lost":
            s["lost"][_safe(g, (c.get("reason") or "Other").split(":")[0][:40])] += 1
        elif t == "chat.handover" and "sources did not cover" in (c.get("reason") or ""):
            s["handovers"] += 1
            said = (byid.get(e["caused_by"]) or {}).get("content", {}).get("text") or ""
            if topic := next((k for k, rx in TOPICS.items() if re.search(rx, said, re.I)), None):
                s["gaps"][topic] += 1
        elif t == "docs.rejected":
            s["docs"][_safe(g, (c.get("reason") or "Unclear").split(":")[0][:60], "Unclear")] += 1
        elif t == "form.recalled":
            s["recalled"] += 1
        elif t == "task.reopened":
            s["reopened"] += 1
        elif t == "payment.flagged":
            s["flagged"] += 1
        elif t == "payment.reminded":
            s["reminded"] += 1
        elif t in ("compliance.blocked", "compliance.needs_info", "screening.hit"):
            s["held"] += 1
        elif t == "step.blocked":
            s["blocked"] += 1
        elif t == "post.seen" and c.get("source") == "competitor" and (s["rival"] is None or (c.get("score") or 0) > (s["rival"].get("score") or 0)):
            s["rival"] = c
    for b in send_backs(office, g, since, until):
        s["backs"][b["agent"]] += 1
        s["back_why"][_safe(g, b["why"][:80], "Another reason")] += 1
    return s


PLAYS = {"No response": ("followup", "Ask if they're still looking", "Hi {name}, a quick one so I don't chase you: are you still looking, or shall I pause for now?", "reply_rate"),
         "Changed mind": ("followup", "Ask what changed", "Hi {name}, if your plans have changed, tell me what's different and I'll adjust what I look for.", "reply_rate"),
         "Found elsewhere": ("followup", "Offer to compare", "Hi {name}, if you've seen something you like elsewhere, send it over and {broker} will compare it honestly with what we have.", "reply_rate"),
         "Price": ("question", "Ask the most they'd go to", "What is the most you'd be comfortable going to, if the right place came up?", "viewing_rate"),
         "Finance refused": ("question", "Ask about mortgage approval early", "Has a bank already pre-approved you, or are you still looking into that?", "converted_rate"),
         "Valuation": ("question", "Ask about mortgage approval early", "Has a bank already pre-approved you, or are you still looking into that?", "converted_rate")}


def _thread(room: str, s: dict, g: Graph, min_n: int) -> tuple[str, dict | None]:
    """What this room's rep says about the office this week, and the change that would answer it, if any."""
    if room == "sales":
        if not s["lost"]:
            return "No leads lost with a reason this week.", None
        why, n = s["lost"].most_common(1)[0]
        line = "Lost this week: " + ", ".join(f"{k} {v}" for k, v in s["lost"].most_common(4)) + "."
        play = PLAYS.get(why) if n >= min_n else None
        if not play:
            return line, None
        kind, title, text, metric = play
        return line, {"kind": kind, "title": title, "text": text, "metric": metric, "why": f"{why} was the top reason, {n} times this week."}
    if room == "front":
        if not s["handovers"]:
            return "Rania answered everything she was asked this week.", None
        gaps = ", ".join(f"{k} {v}" for k, v in s["gaps"].most_common(3))
        return f"Rania handed over {s['handovers']} question{'s' if s['handovers'] != 1 else ''} she couldn't answer" + (f": {gaps}. A confirmed answer in Knowledge would close the gap." if gaps else "."), None
    if room == "mkt":
        r = s["rival"]
        if not r:
            return "No new competitor posts read this week.", None
        form = r.get("type") or r.get("kind") or r.get("media_type") or "post"
        who = r.get("username") or r.get("account") or "a competitor"
        line = f"Best competitor post this week: a {str(form).lower()} from {who}" + (f", at {r['score']:g} times their usual." if r.get("score") else ".")
        return line, {"kind": "content", "title": f"Try the {str(form).lower()} format that worked for {who}"[:100], "metric": "leads_per_post",
                      "text": f"Our own take on the format of a {str(form).lower()} that did well for {who}: our own footage, our own words, one listing or area we know well.",
                      "why": line}
    if room == "deal":
        if not s["docs"]:
            return "No client documents turned back this week.", None
        why, n = s["docs"].most_common(1)[0]
        line = f"{sum(s['docs'].values())} client documents turned back, mostly: {why.rstrip('.')}."
        return line, ({"kind": "step", "title": "Tell clients how to photograph a document", "metric": "sent_back_rate", "why": line,
                       "text": "Before asking for documents, send the client the one-line guide: flat, all four corners, no flash."} if n >= min_n else None)
    if room == "ops":
        n = s["recalled"] + s["reopened"]
        if not n:
            return "No forms recalled or steps reopened this week.", None
        line = f"{s['recalled']} forms recalled and {s['reopened']} steps reopened this week."
        return line, ({"kind": "step", "title": "Read names back before a form goes out", "metric": "sent_back_rate", "why": line,
                       "text": "Read the names, unit and price back to the client before the form goes out."} if n >= min_n else None)
    if room == "fin":
        n = s["flagged"] + s["reminded"]
        if not n:
            return "No payments flagged or chased this week.", None
        line = f"{s['flagged']} payments flagged and {s['reminded']} reminders sent this week."
        return line, ({"kind": "step", "title": "Confirm the paying account before the deposit", "metric": "flagged_rate", "why": line,
                       "text": "Ask the client whose account the deposit will come from before it is due."} if n >= min_n else None)
    if room == "comp":
        return f"{s['held']} compliance holds or checks this week. Listening only: compliance rules don't change from the Lobby.", None
    if room == "review":
        if not s["backs"]:
            return "Nothing sent back this week.", None
        who, n = s["backs"].most_common(1)[0]
        why = s["back_why"].most_common(1)[0][0]
        line = f"{sum(s['backs'].values())} sent back this week, most from {BY_ID[who].name if who in BY_ID else who}. The usual reason: {why}."
        if n < min_n or who not in BY_ID or who in PROTECTED or why == "Another reason" or re.search(RULE_WORDS, why, re.I):
            return line, None
        return line, {"kind": "instruction", "agent": who, "title": f"{BY_ID[who].name} checks this before handing work in", "metric": "send_backs", "why": line,
                      "text": f"Always check this before handing work in, because Review keeps returning it: {why}"[:300]}
    return f"{s['blocked']} steps blocked this week. Records reports each experiment when its period ends.", None


def week_of(now: datetime) -> str:
    return now.astimezone(timezone(timedelta(hours=4))).strftime("%G-W%V")


def run_week(office: Office, now: datetime | None = None, by: str = HOST) -> list[str]:
    """This week's threads, once a week per room. Each ends in at most one proposal: a playbook that fits comes first, or the
    office's own problem, unless the same change is already being tried."""
    from diwan import leads
    now = _now(now)
    g, week = office.graph(), week_of(now)
    since, until = (now - timedelta(days=7)).isoformat(), now.isoformat()
    rules = settings(g)
    sig = signals(office, g, since, until)
    done, proposed = [], []
    for room, (label, rep) in ROOMS.items():
        key = f"lobby-thread:{week}:{room}"
        if any(e.get("key") == key for e in office.log.list()):
            continue
        said, play = _thread(room, sig, g, rules["min_signal"])
        lines = [{"who": rep, "text": said}]
        pb = next((b for b in g.of("playbook", status="live") if b.props["room"] == room), None)
        if pb:
            lines.append({"who": rep, "text": f"Seen elsewhere ({pb.props['where']}): {pb.props['pattern']}", "ref": pb.id})
            lines.append({"who": HOST, "text": "It fits what we saw here." if play else "Nothing here says we need this now. Noted, no change."})
            if play and pb.props.get("kind"):
                play = {"kind": pb.props["kind"], "title": pb.props["pattern"][:100], "text": pb.props["text"], "metric": KINDS[pb.props["kind"]]["metrics"][0],
                        "why": f"{said} Playbook {pb.id}: {pb.props['evidence']}"}
        tried = {(x.props["kind"], x.props["title"]) for x in g.of("experiment") if x.status in ("proposed", "running", "reporting", "kept", "rolled back")}
        xid = None
        if play and (play["kind"], play["title"]) in tried:
            lines.append({"who": HOST, "text": "We have already tried this or it is waiting for the owner, so no new proposal."})
        elif play:
            try:
                xid = propose(office, {**play, "room": room, "days": rules["period_days"], "control_pct": rules["control_pct"]}, by=rep)
            except ValueError as e:  # the guardrails hold for the reps too: the thread says so and the week goes on
                lines.append({"who": HOST, "text": f"Not proposed: {e}."})
            else:
                g = office.graph()
                lines.append({"who": HOST, "text": f"Proposed {xid} for the owner: {play['title']}."})
                proposed.append(xid)
        else:
            lines.append({"who": HOST, "text": "No proposal this week."})
        tid = office._next(g, "thread", "TH")
        ev = office.log.append("thread.posted", actor=rep, agent=HOST, key=key, content={"id": tid, "room": room, "label": label, "week": week, "title": f"{label}, {week}", "lines": lines, "experiment": xid})
        if not ev.get("duplicate"):
            done.append(tid)
        g = office.graph()
    if proposed:
        leads.notify(office, _owner_id(), f"The Lobby has {len(proposed)} experiment{'s' if len(proposed) != 1 else ''} for you to look at this week.", kind="info")
    return done


def add_playbook(office: Office, draft: dict, *, by: str) -> str:
    """A pattern from outside: the Sales lead or the owner files it, with where it was seen and the evidence. A pattern from another
    Diwan office needs the owner's opt-in, and nothing naming a client gets in. Offices don't share them by themselves yet."""
    if PEOPLE.get(by, {}).get("role") not in ("Owner", "Sales manager"):
        raise PermissionError("Only the Sales lead and the owner add to the Lobby")
    g = office.graph()
    p = {k: str(draft.get(k) or "").strip()[:400] for k in ("room", "pattern", "where", "evidence", "source", "kind", "text")}
    if p["room"] not in ROOMS or not p["pattern"] or not p["where"] or not p["evidence"]:
        raise ValueError("A playbook needs its room, the pattern, where it was seen and the evidence")
    p["source"] = p["source"] or "public"
    if p["source"] not in ("public", "other office"):
        raise ValueError("A playbook comes from a public source or another office")
    if p["source"] == "other office" and not settings(g)["playbooks_opt_in"]:
        raise Guardrail("Playbooks from other offices are off until the owner opts in")
    client_free(g, p["pattern"], p["where"], p["evidence"], p["text"])
    if p["kind"]:
        check(office, g, {"kind": p["kind"], "title": p["pattern"][:100], "text": p["text"], "metric": KINDS.get(p["kind"], {"metrics": [None]})["metrics"][0], "days": 14, "control_pct": 50, "agent": draft.get("agent")})
    pid_ = office._next(g, "playbook", "PB")
    office.log.append("playbook.added", actor=by, agent=HOST, content={"id": pid_, **p})
    return pid_


def remove_playbook(office: Office, pb: str, *, by: str) -> None:
    if PEOPLE.get(by, {}).get("role") not in ("Owner", "Sales manager"):
        raise PermissionError("Only the Sales lead and the owner change the Lobby")
    office.log.append("playbook.removed", actor=by, agent=HOST, key=f"playbook-removed:{pb}", content={"id": pb})


def sweep(office: Office, now: datetime | None = None) -> list[str]:
    """Every few minutes: this week's threads on the owner's day, reports for what has finished, last month's tally on the 1st."""
    now, out = _now(now), []
    g = office.graph()
    s, local = settings(g), now.astimezone(timezone(timedelta(hours=4)))
    if local.weekday() == s["thread_day"] and local.hour >= s["thread_hour"]:
        out += run_week(office, now)
    for x in g.of("experiment", status="running"):
        if now >= _at(x.props["ends"]):
            report(office, x.id, now=now)
            out.append(f"reported {x.id}")
    if local.day == 1:
        out += _month(office, now)
    return out


def _month(office: Office, now: datetime) -> list[str]:
    from diwan import leads
    local = now.astimezone(timezone(timedelta(hours=4)))
    last = (local.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    g, key = office.graph(), f"lobby-month:{last}"
    if any(e.get("key") == key for e in office.log.list()):
        return []
    ended = [x for x in g.of("experiment") if x.status in ("kept", "rolled back") and (x.props.get("ended_at") or "").startswith(last)]
    kept = sum(x.status == "kept" for x in ended)
    text = f"Last month: {kept} experiment{'s' if kept != 1 else ''} kept, {len(ended) - kept} rolled back."
    tid = office._next(g, "thread", "TH")
    ev = office.log.append("thread.posted", actor=HOST, agent=HOST, key=key, content={"id": tid, "room": "lobby", "label": "The month", "week": last, "title": f"The month, {last}", "lines": [{"who": HOST, "text": text}], "experiment": None})
    leads.notify(office, _owner_id(), text, kind="info", cause=ev["id"])
    return [tid]


def idea(g: Graph, now: datetime | None = None) -> dict | None:
    """One idea a day, the same all day: something waiting for the owner, or a pattern from outside."""
    pool = [(x.props["title"], x.props.get("why") or "", x.id) for x in g.of("experiment", status="proposed")]
    pool += [(b.props["pattern"], f"Seen: {b.props['where']}", b.id) for b in g.of("playbook", status="live")]
    if not pool:
        return None
    title, why, ref = pool[_now(now).astimezone(timezone(timedelta(hours=4))).toordinal() % len(pool)]
    return {"text": title, "why": why, "refs": [ref]}


def waiting(g: Graph) -> list:
    """Finished experiments the owner hasn't decided."""
    return g.of("experiment", status="reporting")


# ---------- the room's screen ----------

def view_of(office: Office, x, now: datetime | None = None) -> dict:
    g = office.graph()
    p = x.props
    aud = p.get("audience") or {}
    who = ", ".join(f"{k}: {name(v) if k == 'broker' else v}" for k, v in aud.items()) or "everyone it applies to"
    out = {"id": x.id, "status": x.status, "kind": p["kind"], "kind_label": KINDS[p["kind"]]["label"], "room": ROOMS.get(p.get("room"), (p.get("room"),))[0], "title": p["title"], "text": p["text"], "why": p.get("why"),
           "audience": aud, "who": who, "days": p["days"], "metric": p["metric"], "metric_label": METRICS[p["metric"]][0], "control_pct": p.get("control_pct"), "n": p.get("n"), "agent": p.get("agent"), "template": p.get("template"),
           "starts": p.get("starts"), "ends": p.get("ends"), "by": _named(p.get("by")), "reason": p.get("reason"), "decided_by": _named(p.get("decided_by")), "ended_at": p.get("ended_at")}
    out["result"] = p.get("result") or (measure(office, g, x, now) if x.status == "running" else None)
    return out


def room(office: Office, person: str, now: datetime | None = None) -> dict:
    now, g = _now(now), office.graph()
    role = PEOPLE.get(person, {}).get("role")
    threads = sorted(g.of("thread"), key=lambda t: t.event, reverse=True)
    latest = threads[0].props["week"] if threads else None
    xs = sorted(g.of("experiment"), key=lambda x: x.event, reverse=True)
    pick = lambda *st: [view_of(office, x, now) for x in xs if x.status in st]  # noqa: E731
    return {"person": person, "owner": role == "Owner", "may_propose": role in ("Owner", "Sales manager"), "idea": idea(g, now), "week": latest,
            "threads": [{"id": t.id, "room": t.props["label"], "lines": [{**ln, "name": _named(ln["who"])} for ln in t.props["lines"]],
                         "experiment": t.props.get("experiment")} for t in reversed(threads) if t.props["week"] == latest],
            "playbooks": [{"id": b.id, "room": ROOMS[b.props["room"]][0], "pattern": b.props["pattern"], "where": b.props["where"], "evidence": b.props["evidence"], "source": b.props["source"]}
                          for b in g.of("playbook", status="live")],
            "proposed": pick("proposed"), "running": pick("running"), "waiting": pick("reporting"), "kept": pick("kept"), "rolled_back": pick("rolled back"), "refused": pick("refused"),
            "kinds": {k: {"label": v["label"], "metrics": {m: METRICS[m][0] for m in v["metrics"]}} for k, v in KINDS.items()}, "rooms": {k: v[0] for k, v in ROOMS.items()},
            "rules": settings(g), "agents": {c.id: c.name for c in BY_ID.values() if c.id not in PROTECTED and c.parent != HOST and c.id != HOST}}
