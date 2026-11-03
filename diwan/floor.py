"""The feed behind the 3D office (Part 7): the one stream the floor draws from, so nothing moves without a real cause.

Each event in the log becomes a message: which room it left, which rooms take it, what kind of card it is and the record
it opens. Agent steps the log doesn't hold (reading, the model writing, checking) are pulses: real, kept in memory only,
and never written to the log. What a person may see is cut here, on the server, never in the browser.
"""
from __future__ import annotations

import asyncio
import itertools
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from diwan import access
from diwan.agents.charters import get
from diwan.events import TYPES
from diwan.graph import Graph

router = APIRouter()

ROOMS = ("front", "mkt", "sales", "records", "review", "ops", "fin", "deal", "comp", "lobby")
LEADS = {"nova": "front", "rania": "front", "mkt": "mkt", "sales": "sales", "records": "records", "review": "review",
         "ops": "ops", "fin": "fin", "deal": "deal", "comp": "comp", "lhost": "lobby"}
PEOPLE_ROOM = {access.SALES: "sales", access.MKT: "mkt", access.OPS: "ops", access.FIN: "fin", access.COMP: "comp"}
STACK = 5   # more cards than this on one path at once fly as one stack with a count
TICK = .2

# Who takes each event. "self": it stays in the room that made it. "out": it leaves the office by the door. "in": it comes
# in by the door to the room that handles it. An empty tuple would be an event nobody takes, which is what the Stuck pile is for.
ROUTES: dict[str, tuple[str, tuple[str, ...]]] = {}
QUIET: set[str] = {"viewing.requested", "offer.made", "offer.accepted", "offer.declined"}  # deliberately not animated: settings, reads and bookkeeping with no work to show


def _r(card: str, to: tuple[str, ...], types: str) -> None:
    for t in types.split():
        ROUTES[t] = (card, to)


_r("quote", ("self",), "fact.created fact.confirmed qualify.answer utterance knowledge.added knowledge.confirmed")
_r("quote", ("comp",), "fact.superseded")
_r("envelope", ("in",), "chat.received docs.received sign.signed docs.opened sign.opened post.seen post.read competitors.refreshed "
                        "competitor.checked listings.found footage.added photos.added lead.attributed")
_r("envelope", ("out",), "chat.sent email.sent followup.sent sign.link docs.requested docs.reminded docs.renewed sign.renewed "
                         "appointment.reminded appointment.link client.released post.live form.sent post.approved")
_r("task", ("self",), "task.created task.done task.withdrawn task.reopened plan.made plan.started instruction.given note.added note.done "
                      "question.asked question.answered step.blocked errand.drafted errand.confirmed errand.cancelled "
                      "lobby.posted lobby.done lobby.cancelled lobby.late lobby.reminded nova.headsup rounds.started")
_r("task", ("sales",), "lead.assigned lead.claimed lead.pooled lead.hot lead.unhot lead.recommended lead.reopened lead.went_quiet "
                       "lead.nudged lead.outcome lead.nurture lead.optout lead.kind lead.followups followup.drafted followup.nudged "
                       "qualify.passed qualify.not_fit qualify.open chat.handover chat.suggested visit.summarized")
_r("task", ("front",), "briefing.ready nova.arrived experiment.proposed change.proposed")
_r("task", ("lobby",), "thread.posted experiment.approved experiment.refused experiment.ended experiment.reported experiment.switched playbook.added")
_r("doc", ("review",), "draft.made portal.drafted")
_r("doc", ("deal",), "docs.confirmed docs.rejected")
_r("doc", ("records",), "document.filed document.voided sale.closed")
_r("doc", ("self",), "form.recalled portal.submitted")
_r("money", ("fin",), "payment.reminded invoice.written_off")
_r("money", ("deal",), "payment.marked_received payment.undone")
_r("compliance", ("comp",), "check.raised screening.hit screening.resolved payment.flagged compliance.needs_info")
_r("compliance", ("deal", "front"), "compliance.blocked")
_r("compliance", ("deal", "fin"), "compliance.cleared compliance.rated")
_r("stamp", ("self",), "approval.given approval.refused decision.made review.passed qa.passed execution.done")
_r("stamp", ("front",), "approval.requested decision.needed")
_r("task", ("deal",), "review.returned qa.failed qa.escalated")
_r("folder", ("deal",), "case.converted deal.opened")
_r("folder", ("ops",), "deal.ready_for_transfer")
_r("folder", ("records",), "case.closed case.lost transfer.completed")
_r("folder", ("self",), "stage.changed transfer.booked")
_r("phone", ("sales",), "attention.raised attention.moved attention.cleared lead.no_calls")
_r("phone", ("self",), "appointment.booked appointment.moved appointment.cancelled appointment.done appointment.noshow "
                         "appointment.requested appointment.confirmed appointment.offered")
_r("stuck", ("self",), "attention.overdue agent.failed email.failed")
_r("task", ("self",), "agent.pack agent.started agent.refused content.idea content.briefed content.scripted content.ready content.made "
                      "post.paused post.withdrawn campaign.started campaign.ended mchat.analysed")
_r("note", ("self",), "meeting.started meeting.ended consent.given pocket.started pocket.ended")
_r("note", ("self",), "steps.proposed")
_r("task", ("owners",), "steps.approved")  # from the Meeting room to the room of each person given work

QUIET |= set("""listing.access agent.added agent.paused agent.removed agent.resumed autonomy.changed board.pinned board.unpinned calendar.blocked
calendar.morning calendar.unblocked chat.merged client.queued appointment.link_removed followup.dismissed item.edited item.reconfirmed
item.restored item.retired lead.sweep lesson.added lesson.removed listing.added listings.synced lobby.seen mchat.said mchat.upload
notify.digest notify.read notify.sent nova.watched photo.read playbook.removed pocket.line product.saved qualify.asked qualify.form
qualify.type setting.changed taste.forgotten taste.reason taste.signal tool.called topic.saved change.decided""".split())

# The floor's names for what the log already says about a run; the log itself keeps its own.
RENAMED = {"agent.started": "agent.run_started", "agent.pack": "agent.run_finished", "agent.failed": "agent.fallback",
           "approval.requested": "agent.waiting_for_person", "step.blocked": "agent.blocked", "agent.refused": "agent.blocked"}
TEXT_KEYS = ("quote", "text", "title", "action", "reason", "summary", "note", "task")
SALES_ONLY_HIDDEN = {"compliance"}


def room_of(agent: str | None) -> str | None:
    """The room an agent sits in, following its charter up to the lead."""
    seen = set()
    while agent and agent not in seen:
        if agent in LEADS:
            return LEADS[agent]
        seen.add(agent)
        try:
            agent = get(agent).parent
        except KeyError:
            return None
    return None


def _from(e: dict) -> str | None:
    if room := room_of(e.get("agent")) or room_of(e.get("actor")):
        return room
    actor = e.get("actor") or ""
    if actor in access.PEOPLE:
        return PEOPLE_ROOM.get(access.department(actor)) or "front"  # the owner works from the front desk
    return "sales" if actor.startswith("customer:") else None


def _words(e: dict) -> str:
    c = e.get("content") or {}
    if e["type"] == "agent.pack":
        return ((c.get("pack") or {}).get("verdict") or "")[:160]
    for k in TEXT_KEYS:
        if isinstance(c.get(k), str) and c[k]:
            return c[k][:160]
    return e["type"].replace(".", " ")


def _record(e: dict) -> str:
    c = e.get("content") or {}
    if phone := c.get("chat") or c.get("phone"):
        return f"inbox.html?chat={phone}"
    return f"deal.html?deal={e['deal']}" if e.get("deal") else "knowledge.html"


def preview(e: dict, g: Graph | None = None) -> dict | None:
    """What the desk's monitor shows for this event: the event's own content, never a placeholder."""
    t, c = e["type"], e.get("content") or {}
    if t == "agent.pack":
        pack = c.get("pack") or {}
        return {"kind": "typing", "title": e.get("request") or "", "lines": [pack.get("verdict") or ""][:6]}
    if t == "check.raised":
        return {"kind": "checklist", "title": c.get("title") or "Check", "lines": [c.get("text") or "", *(f"Rests on {r}" for r in (c.get("refs") or [])[:4])]}
    if t == "review.returned":
        return {"kind": "compare", "title": "Said vs slide", "old": c.get("old") or "", "new": c.get("new") or ""}
    if t == "fact.superseded" and g and c.get("id") in g.nodes and c.get("by") in g.nodes:
        return {"kind": "compare", "title": "Corrected", "old": g.nodes[c["id"]].props.get("quote", ""), "new": g.nodes[c["by"]].props.get("quote", "")}
    if t == "portal.drafted":
        return {"kind": "form", "title": c.get("portal") or "Portal", "fields": [[str(k), str(v)] for k, v in list((c.get("fields") or {}).items())[:6]]
                if isinstance(c.get("fields"), dict) else [[str(f.get("label", f.get("name", ""))), str(f.get("value", ""))] for f in (c.get("fields") or [])[:6]]}
    if t == "draft.made":
        return {"kind": "form" if "form" in (c.get("kind") or "").lower() else "typing", "title": f"{c.get('kind')} v{c.get('version')}",
                "lines": [s.get("text") or s.get("title") or "" for s in (c.get("slides") or [])[:6]],
                "fields": [[s.get("title") or s.get("field") or "", s.get("text") or s.get("value") or ""] for s in (c.get("slides") or [])[:6]]}
    return None


def message(e: dict, g: Graph | None = None) -> dict | None:
    """The event as the floor draws it, or None for one it deliberately doesn't. An event it has never heard of still
    moves: it falls to the Stuck pile, which is how a new event with no consumer gets noticed."""
    t = e["type"]
    if t in QUIET:
        return None
    card, to = ROUTES.get(t, ("stuck", ()))
    room = _from(e)
    takers = [r for r in (room if x == "self" else x for x in to) if r != "in"]
    src = None if "in" in to else room  # from outside: it arrives at the door of the room that handles it
    if "in" in to:
        takers = [room or "sales"]
    if "owners" in to:  # the meeting's tasks leave the Meeting room for the room of each person given one
        src, takers = "meet", sorted({r for x in (e.get("content") or {}).get("tasks", []) if (r := access.department(x["owner"])) in ROOMS}) or [room or "sales"]
    m = {"id": e["id"], "type": RENAMED.get(t, t), "source": t, "caused_by": e.get("caused_by") or e["id"], "at": e["at"], "deal": e.get("deal"),
         "agent": e.get("agent") or (e.get("actor") if room_of(e.get("actor")) else None), "from": src, "to": takers, "card": card, "text": _words(e),
         "record": _record(e), "count": 1, "stuck": card == "stuck"}
    if pv := preview(e, g):
        m["preview"] = pv
    return m


def mask(m: dict, person: str | None, g: Graph) -> dict:
    """Cut a message down to what this person may see. Compliance's reasons stay with the owner and Compliance; a broker
    doesn't see another broker's clients."""
    if person is None or access.is_owner(person):
        return m
    dept = access.department(person)
    out = dict(m)
    if m["card"] == "compliance" and dept != access.COMP:
        out.update(text="Compliance", record="", deal=None)
        out.pop("preview", None)
    if dept == access.SALES and m.get("deal"):
        d = g.nodes.get(f"deal:{m['deal']}")
        if d and d.props.get("broker") not in (person, None):
            out.update(text="Another broker's client", record="", deal=None)
            out.pop("preview", None)
    return out


class Chain:
    """Which events belong to a correction, across ticks: the ripple draws those, so they don't also fly as loose cards."""

    def __init__(self):
        self.members: dict[int, str] = {}

    def mark(self, e: dict, m: dict) -> None:
        c = e.get("content") or {}
        if e["type"] == "fact.created" and c.get("replaces"):
            self.members[e["id"]] = c["id"]
            m["ripple"] = c["id"]
        elif (root := self.members.get(e.get("caused_by"))) is not None:
            self.members[e["id"]] = root
            m["in_ripple"] = root


def batch(msgs: list[dict]) -> list[dict]:
    """More than STACK cards on the same path in one tick travel as one stack with a count."""
    paths = defaultdict(list)
    for m in msgs:
        if not m.get("in_ripple") and not m.get("ripple"):
            paths[(m["card"], m["from"], tuple(m["to"]))].append(m)
    gone = set()
    for same in paths.values():
        if len(same) > STACK:
            same[-1] = dict(same[-1], count=len(same), stack=[x["id"] for x in same])
            gone |= {x["id"] for x in same[:-1]}
            msgs = [same[-1] if x["id"] == same[-1]["id"] else x for x in msgs]
    return [m for m in msgs if m["id"] not in gone]


# ---------- pulses: steps of a run, in memory only ----------

_pulses: deque = deque(maxlen=400)
_seq = itertools.count(1)


def step(agent: str, kind: str, title: str = "") -> None:
    """One real step of an agent's run. Called from the runner; nobody listening costs nothing."""
    n = next(_seq)
    _pulses.append({"seq": n, "type": "agent.step", "agent": agent, "step": kind, "title": title[:80], "caused_by": f"run:{agent}:{n}", "room": room_of(agent)})


def pulses(after: int) -> list[dict]:
    return [p for p in list(_pulses) if p["seq"] > after]


# ---------- what the floor asks for ----------

def _office():
    from diwan.app import S
    return S.office


def ripple(office, fact: str) -> dict:
    """One correction, from the same query as the Deal desk's "Latest correction" card, plus who it did not touch."""
    from diwan.deal_desk import Ledger
    g = office.graph()
    f = g.nodes.get(fact)
    if not f or f.type != "fact" or not f.props.get("replaces"):
        raise KeyError(fact)
    r = Ledger(g, date.today())._ripple(f)
    return r | {"untouched": [x for x in ROOMS if x not in r["rooms"] and x not in ("front", "lobby")]}


def stuck(office) -> list[dict]:
    """What the pile on the HQ floor stands for: overdue work still open, and agents that failed in the last day."""
    g = office.graph()
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    out, seen = [], set()
    for e in reversed(office.log.list()):
        c = e.get("content") or {}
        if e["type"] == "attention.overdue" and c.get("id") not in seen and (n := g.nodes.get(c.get("id"))) and n.status == "open":
            seen.add(c["id"])
            out.append({"id": e["id"], "text": n.props.get("text") or "Overdue", "record": _record(e), "at": e["at"]})
        elif e["type"] == "agent.failed" and e["at"] >= since:
            out.append({"id": e["id"], "text": f"{e.get('agent')}: {c.get('error', 'failed')[:120]}", "record": _record(e), "at": e["at"]})
    return out[:50]


@router.get("/api/floor/ripple/{fact}")
def get_ripple(fact: str):
    try:
        out = ripple(_office(), fact)
    except KeyError:
        raise HTTPException(404, "No correction with that id") from None
    person = access.USER.get()
    if person and not access.is_owner(person) and access.department(person) != access.COMP:
        for k in ("quote", "old", "customer", "deal"):  # the counts are the office's; the words are Compliance's and the deal's
            out.pop(k, None)
    return out


@router.get("/api/floor/stuck")
def get_stuck():
    return {"items": stuck(_office()) if access.is_owner(access.USER.get()) or access.USER.get() is None else []}


@router.websocket("/ws/floor")
async def feed(ws: WebSocket, after: int = 0):
    await ws.accept()
    log = _office().log
    tail = log.list()
    last, seq, chain = after or (tail[-1]["id"] if tail else 0), max((p["seq"] for p in _pulses), default=0), Chain()
    person = access.USER.get()
    try:
        while True:
            office = _office()
            if office.log is not log:  # the demo was reset: a new log, from its start
                log, last, chain = office.log, 0, Chain()
            new, msgs = log.list(after=last), []
            if new:
                last = new[-1]["id"]
                g = office.graph()
                for e in access.visible(new):
                    if m := message(e, g):
                        chain.mark(e, m)
                        msgs.append(mask(m, person, g))
            fresh = pulses(seq)
            if fresh:
                seq = fresh[-1]["seq"]
            if msgs or fresh:
                await ws.send_json({"messages": batch(msgs), "pulses": fresh, "last": last})
            await asyncio.sleep(TICK)
    except (WebSocketDisconnect, RuntimeError):
        return
