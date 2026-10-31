"""One way out to a client for the Deal desk. Every message passes the same rules (the spec's rule 6, and "stop means stop
everywhere"): a client who said stop gets nothing automated; quiet hours and Friday prayer hold a message until they end;
inside WhatsApp's 24 hours it goes as plain text; outside them it goes as the owner's approved template, and with none
picked the broker gets a task to tell them instead. Nothing here ever mentions a compliance check.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from diwan.graph import Graph

if TYPE_CHECKING:
    from diwan.office import Office

WINDOW = timedelta(hours=24)


def chat_of(g: Graph, deal: str):
    return next((c for c in g.of("chat") if c.deal == deal and not c.props.get("merged_into")), None)


def _window_open(chat, now: datetime) -> bool:
    last = next((m for m in reversed(chat.props["messages"]) if m["type"] == "received"), None)
    return bool(last) and now - datetime.fromisoformat(last["at"]) < WINDOW


def _call_task(office: Office, deal: str, g: Graph, what: str, why: str) -> str:
    broker = g.nodes[f"deal:{deal}"].props.get("broker")
    return office.add_task(deal, "ops", f"Tell the client yourself ({why}): {what}", needs_person=broker, props={"step": "docs_call", "token": None})


def tell(office: Office, deal: str, text: str, *, what: str, now: datetime | None = None, cause: int | None = None) -> str:
    """Says `text` to the deal's client, or says why it couldn't. `what` is the short form for a broker's task and the log.
    Returns sent, held (quiet hours), task (the broker tells them), stopped or none (no chat on file)."""
    from diwan.agents import nudge, reception
    from diwan import inbox
    now = now or datetime.now(timezone.utc)
    g = office.graph()
    d = g.nodes[f"deal:{deal}"].props
    if d.get("optout"):
        return "stopped"
    chat = chat_of(g, deal)
    if not chat:
        return "none"
    if not nudge.allowed(nudge.settings(g), now):
        office.log.append("client.queued", actor="ops", agent="ops", deal=deal, content={"text": text, "what": what})
        return "held"
    phone = chat.props["phone"]
    if _window_open(chat, now):
        sent = reception._send(office, phone, deal, text, refs=[], cause=cause)
    else:
        name_ = nudge.settings(g).get("template")
        t = next((x for x in inbox.templates() if x["name"] == name_), None) if name_ else None
        if not t:
            _call_task(office, deal, g, what, "more than 24 hours since they wrote, and no template is picked")
            return "task"
        params = nudge._template_params(g, deal, chat, t)
        sent = reception._send(office, phone, deal, inbox.render(t["body"], params), refs=[], cause=cause,
                               template={"name": t["name"], "params": params, "language": t.get("language", "en")})
    if sent["content"].get("status") == "failed":  # the spec: a message that can't be delivered becomes a call
        _call_task(office, deal, g, what, "the message could not be delivered")
        return "task"
    return "sent"


def sweep(office: Office, now: datetime) -> int:
    """Run every minute: what quiet hours held goes out when they end, unless the client has since said stop."""
    from diwan.agents import nudge
    g = office.graph()
    if not nudge.allowed(nudge.settings(g), now):
        return 0
    events = office.log.list()
    done = {e["content"].get("event") for e in events if e["type"] == "client.released"}
    n = 0
    for e in events:
        if e["type"] == "client.queued" and e["id"] not in done and f"deal:{e['deal']}" in g.nodes:
            result = tell(office, e["deal"], e["content"]["text"], what=e["content"]["what"], now=now)
            office.log.append("client.released", actor="ops", agent="ops", deal=e["deal"], content={"event": e["id"], "result": result})
            n += 1
    return n
