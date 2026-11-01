"""The office's memory: a graph rebuilt from the event log, so it always agrees with the log and can be rewound to any
event. Nodes are people, deals, properties, facts (each holding the speaker's exact words), tasks, approvals, drafts and
their slides, and the open cards waiting for people. Edges say who said what, who pays, what rests on which fact, and
which fact replaced which.

Every node has a short id an answer can cite (F3, T2, A1, D1/3, N14...) and `record()` turns it into the one line an
agent is allowed to quote.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from diwan.people import PEOPLE, name, pid

DUBAI = timezone(timedelta(hours=4))

KIND = {"deal_term": "Deal terms", "payer": "Who pays", "payment_promise": "Payment promise", "income_claim": "Stated income",
        "party": "Who is involved", "document_shown": "Document shown", "commitment": "Next step"}
OPEN = {"open", "queued", "working", "waiting"}


@dataclass
class Node:
    id: str
    type: str
    label: str
    deal: str | None = None
    props: dict = field(default_factory=dict)
    status: str = "live"
    event: int = 0
    at: str = ""


@dataclass(frozen=True)
class Edge:
    src: str
    rel: str
    dst: str
    event: int
    via: str | None = None  # the fact that says so


class Graph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.last_event = 0
        self.settings: dict[str, dict] = {}
        self.autonomy: dict[str, str] = {}
        self.rounds: dict | None = None  # the latest round: {"event", "at", "reports": {lead: pack}}
        self.qualify_form: dict | None = None  # the owner's latest qualification form (diwan/qualify.py)
        self.custom_agents: dict[str, dict] = {}  # agents the owner added (diwan/agents/custom.py)

    # building
    def add(self, nid: str, type: str, label: str, e: dict, **kw) -> Node:
        if nid in self.nodes:
            n = self.nodes[nid]
            n.props.update(kw.pop("props", {}))
            for k, v in kw.items():
                setattr(n, k, v)
            return n
        n = self.nodes[nid] = Node(nid, type, label, event=e["id"], at=e["at"], **kw)
        return n

    def link(self, src: str, rel: str, dst: str, e: dict, via: str | None = None) -> None:
        edge = Edge(src, rel, dst, e["id"], via)
        if not any(x.src == src and x.rel == rel and x.dst == dst and x.via == via for x in self.edges):
            self.edges.append(edge)

    def person(self, who: str, e: dict, deal: str | None = None, role: str | None = None) -> str:
        k = pid(who) or re.sub(r"\W+", "-", who.strip().lower())
        nid = f"person:{k}"
        n = self.add(nid, "person", PEOPLE[k]["name"] if k in PEOPLE else who.strip(), e)
        if k in PEOPLE:
            n.props.setdefault("role", PEOPLE[k]["role"])
        if role:
            n.props.setdefault("role", role)
        return nid

    # reading
    def out(self, nid: str, rel: str | None = None) -> list[Node]:
        return [self.nodes[x.dst] for x in self.edges if x.src == nid and (rel is None or x.rel == rel) and x.dst in self.nodes]

    def into(self, nid: str, rel: str | None = None) -> list[Node]:
        return [self.nodes[x.src] for x in self.edges if x.dst == nid and (rel is None or x.rel == rel) and x.src in self.nodes]

    def of(self, type: str, deal: str | None = None, status: set | str | None = None) -> list[Node]:
        st = {status} if isinstance(status, str) else status
        return [n for n in self.nodes.values() if n.type == type and (deal is None or n.deal == deal) and (st is None or n.status in st)]

    def facts(self, deal: str, kind: str | None = None, live: bool = True) -> list[Node]:
        """Live facts are asserted and not replaced; hypothetical and negated statements are kept but never live."""
        return [n for n in self.of("fact", deal) if (kind is None or n.props.get("kind") == kind)
                and (not live or (n.status == "live" and n.props.get("stance", "asserted") == "asserted"))]

    def deals(self) -> list[Node]:
        return self.of("deal")

    def stale(self, nid: str) -> list[Node]:
        """The replaced facts this task, approval or slide still rests on."""
        return [f for f in self.out(nid, "rests_on") + self.out(nid, "uses") if f.status == "superseded"]

    def impact(self, fact_id: str) -> list[Node]:
        """Everything that rests on this fact: tasks, approvals, and slides (with their drafts)."""
        hit = []
        for n in self.into(fact_id, "rests_on") + self.into(fact_id, "uses"):
            hit.append(n)
            hit += [d for d in self.out(n.id, "part_of") if d not in hit]
        return hit

    def history(self, fact_id: str) -> list[Node]:
        """The chain of statements this one replaced, newest first."""
        chain, todo = [self.nodes[fact_id]], [fact_id]
        while todo:
            for older in self.out(todo.pop(0), "replaces"):
                if older not in chain:
                    chain.append(older)
                    todo.append(older.id)
        return chain

    def record(self, nid: str) -> str:
        """The one line about a node an agent may quote. Facts carry the speaker's exact words."""
        n = self.nodes[nid]
        p, tag = n.props, "" if n.status in ("live", "open") else f" [{n.status}]"
        if n.type == "fact":
            extra = f" (replaced by {p['superseded_by']})" if n.status == "superseded" else ""
            if p.get("replaces"):
                extra += f" (replaces {', '.join(p['replaces']) if isinstance(p['replaces'], list) else p['replaces']})"
            return f'{n.id} · {name(p.get("speaker"))} said: "{p["quote"]}" · {KIND.get(p["kind"], p["kind"])}{extra}'
        if n.type == "task":
            who = f", waits for {name(p['needs_person'])}" if p.get("needs_person") else ""
            return f"{n.id} · task for {p.get('agent_name', p.get('agent'))}: {p['action']}{who}{tag}"
        if n.type == "approval":
            s = " [rests on a replaced statement]" if self.stale(nid) and n.status == "given" else tag
            return f"{n.id} · {name(p['approver'])} approved: {p['action']}{s}"
        if n.type == "slide":
            return f"{n.id} · slide {p['n']} of the {p['kind']}: {p['text']}{' [uses a replaced statement]' if self.stale(nid) else ''}"
        if n.type == "draft":
            return f"{n.id} · {p['kind']} v{p.get('version', 1)}{tag}"
        if n.type in ("decision", "question", "check", "request"):
            return f"{n.id} · for {name(p.get('who'))}: {p['text']}{tag}"
        if n.type == "knowledge":
            return f"{n.id} · {p['title']}: {p['text']}{'' if n.status == 'confirmed' else ' [retired]' if n.status == 'retired' else ' [not confirmed]'}"
        if n.type == "listing":
            return (f"{p['ref']} · {p['title']}, {p['community']} · {p['beds']} bed {p['type']} · AED {p['price_aed']:,} · "
                    f"permit {p.get('permit') or 'MISSING'} · {n.status}")
        if n.type == "experiment":
            return f"{n.id} · experiment: {n.label} · {n.status}"
        if n.type == "playbook":
            return f"{n.id} · playbook: {p['pattern']} · seen: {p['where']} · evidence: {p['evidence']}"
        if n.type == "lobby":
            due = datetime.fromisoformat(p["due"]).strftime("%a %I:%M %p").replace(" 0", " ") if p.get("due") else "no deadline"
            return f"{n.id} · for {name(p.get('to') or p['team'])}: {p['text']} · due {due} · asked by {name(p['by'])} · {n.status}"
        if n.type == "document":
            amt = f" · AED {p['amount_aed']:,}" if p.get("amount_aed") else ""
            return f"{n.id} · {p['kind']}: {p['title']} · {p['date']}{amt}{' · ' + p['party'] if p.get('party') else ''}"
        if n.type == "sale":
            return (f"{n.id} · sold {p['listing']} on {p['date']} for AED {p['price_aed']:,} · commission AED {p['commission_aed']:,} · "
                    f"broker {name(p['broker'])}")
        if n.type == "viewing":
            when = datetime.fromisoformat(p["at"]).strftime("%a %d %b, %I:%M %p").replace(" 0", " ")
            what = (f"viewing of {p['listing']}" if p.get("where", "property") == "property" and p.get("listing")
                    else f"{(p.get('kind_name') or 'meeting').lower()}" + (f" about {p['listing']}" if p.get("listing") else ""))
            return f"{n.id} · {what} with {name(p['broker'])}, {when}, for {p.get('customer')}{tag if n.status != 'booked' else ''}"
        if n.type == "deal":
            return f"{n.id.split(':', 1)[1]} · {p.get('property')} · customer {p.get('customer')} · broker {name(p.get('broker'))}"
        if n.type == "attention":
            due = datetime.fromisoformat(p["due"]).astimezone(DUBAI).strftime("%H:%M")
            state = "in the Pool" if p.get("pooled") else "overdue" if p.get("overdue") and n.status == "open" else n.status
            return f"{n.id} · for {name(p['who'])}: {p['reason']} ({'call' if p['kind'] == 'call' else 'reply'}) · due {due} · {state}"
        return f"{n.id} · {n.label}"

    def search(self, text: str, deal: str | None = None, types: set | None = None, k: int = 8) -> list[Node]:
        words = {w for w in re.findall(r"[a-z؀-ۿ0-9]+", text.lower()) if len(w) > 2} - STOP
        scored = []
        for n in self.nodes.values():
            if (deal and n.deal not in (deal, None)) or (types and n.type not in types) or n.type == "person":
                continue
            hay = set(re.findall(r"[a-z؀-ۿ0-9]+", self.record(n.id).lower()))
            s = len(words & hay)
            if s:
                scored.append((s + (0.5 if n.status in ("live", "open", "given") else 0), n.event, n))
        return [n for *_, n in sorted(scored, key=lambda x: (-x[0], -x[1]))[:k]]


STOP = {"the", "and", "who", "what", "when", "where", "which", "does", "did", "for", "with", "this", "that", "are", "was",
        "has", "have", "about", "from", "will", "there", "any", "how", "now", "deal", "tell", "please"}


def build(events: list[dict], upto: int | None = None) -> Graph:
    g = Graph()
    for e in events:
        if upto is not None and e["id"] > upto:
            break
        g.last_event = e["id"]
        t, c, deal = e["type"], e["content"], e.get("deal")
        if t == "deal.opened":
            d = g.add(f"deal:{deal}", "deal", c["property"], e, deal=deal, props=dict(c))
            prop = g.add(f"property:{deal}", "property", c["property"], e, deal=deal)
            g.link(d.id, "for", prop.id, e)
            g.link(g.person(c["customer"], e, role="Customer"), "customer_of", d.id, e)
            g.link(g.person(c["broker"], e), "broker_on", d.id, e)
        elif t == "fact.created":
            f = g.add(c["id"], "fact", KIND.get(c["kind"], c["kind"]), e, deal=deal, props=dict(c))
            g.link(f.id, "about", f"deal:{deal}", e)
            if c.get("speaker"):
                g.link(g.person(c["speaker"], e), "said", f.id, e)
            if c.get("payer"):
                g.link(g.person(c["payer"], e), "pays_for", f"deal:{deal}", e, via=f.id)
            if c.get("party") and c.get("relation") and c.get("speaker"):
                g.link(g.person(c["speaker"], e), c["relation"], g.person(c["party"], e), e, via=f.id)
        elif t == "fact.superseded":
            g.nodes[c["id"]].status = "superseded"
            g.nodes[c["id"]].props["superseded_by"] = c["by"]
            g.link(c["by"], "replaces", c["id"], e)
        elif t == "fact.confirmed":
            g.nodes[c["id"]].props["confirmed_by"] = e["actor"]
        elif t == "task.created":
            n = g.add(c["id"], "task", c["action"], e, deal=deal, status="queued", props=dict(c))
            for f in c.get("rests_on", []):
                g.link(n.id, "rests_on", f, e)
            g.link(n.id, "assigned_to", f"agent:{c['agent']}", e)
            if c.get("custom") and c["agent"] in g.custom_agents:
                ca = g.custom_agents[c["agent"]]
                ca.update(done_upto=max(ca["done_upto"], c.get("trigger_event") or 0), runs=ca["runs"] + 1)
        elif t in ("task.withdrawn", "task.done") and c.get("id") in g.nodes:
            n = g.nodes[c["id"]]
            n.status = t.split(".")[1]
            n.props["reason"] = c.get("reason")
            if c.get("result"):
                n.props["result"] = c["result"]
        elif t == "task.reopened" and c.get("id") in g.nodes:  # a person undid it: it is open again, and why is kept
            n = g.nodes[c["id"]]
            n.status = "queued"
            n.props["reason"] = c.get("reason")
            n.props.pop("result", None)
        elif t == "screening.hit" and c.get("id") in g.nodes:  # stays open: a hold until the officer resolves it
            g.nodes[c["id"]].props |= {"result": "possible match", "hit": c.get("note")}
        elif t == "payment.marked_received" and c.get("task") in g.nodes:
            g.nodes[c["task"]].props.setdefault("payments", []).append(dict(c) | {"at": e["at"], "by": e["actor"]})
        elif t == "payment.undone" and c.get("task") in g.nodes:
            n = g.nodes[c["task"]]
            n.props["payments"] = [p for p in n.props.get("payments", []) if p["id"] != c["payment"]]
            n.props.setdefault("undone", []).append(dict(c) | {"at": e["at"], "by": e["actor"]})
        elif t in ("compliance.cleared", "compliance.needs_info", "compliance.blocked") and f"deal:{deal}" in g.nodes:
            g.nodes[f"deal:{deal}"].props["compliance"] = dict(c) | {"state": t.split(".")[1], "by": e["actor"], "at": e["at"]}
        elif t == "compliance.rated" and f"deal:{deal}" in g.nodes:
            g.nodes[f"deal:{deal}"].props["risk"] = dict(c) | {"by": e["actor"], "at": e["at"]}
        elif t == "deal.ready_for_transfer" and f"deal:{deal}" in g.nodes:
            g.nodes[f"deal:{deal}"].props["ready"] = dict(c) | {"by": e["actor"], "at": e["at"]}
        elif t == "transfer.booked" and f"deal:{deal}" in g.nodes:
            g.nodes[f"deal:{deal}"].props["transfer"] = dict(c) | {"by": e["actor"], "at": e["at"]}
        elif t == "transfer.completed" and f"deal:{deal}" in g.nodes:
            g.nodes[f"deal:{deal}"].props["transferred"] = dict(c) | {"by": e["actor"], "at": e["at"]}
        elif t in ("form.sent", "form.recalled") and c.get("draft") in g.nodes:
            g.nodes[c["draft"]].props["sent" if t == "form.sent" else "recalled"] = dict(c) | {"at": e["at"], "by": e["actor"]}
        elif t in ("portal.drafted", "portal.submitted") and c.get("task") in g.nodes:
            g.nodes[c["task"]].props["portal"] = (g.nodes[c["task"]].props.get("portal") or {}) | dict(c) | {"state": t.split(".")[1], "at": e["at"], "by": e["actor"]}
        elif t == "invoice.written_off" and c.get("id") in g.nodes:
            n = g.nodes[c["id"]]
            n.status, n.props["result"], n.props["reason"] = "done", "written off", c.get("reason")
        elif t == "document.voided" and c.get("id") in g.nodes:
            n = g.nodes[c["id"]]
            n.status, n.props["voided"] = "voided", c.get("reason")
        elif t == "approval.given":
            n = g.add(c["id"], "approval", c["action"], e, deal=deal, status="given", props=dict(c))
            for f in c.get("rests_on", []):
                g.link(n.id, "rests_on", f, e)
        elif t == "approval.refused" and c.get("id") in g.nodes:
            g.nodes[c["id"]].status = "refused"
            g.nodes[c["id"]].props["because"] = c.get("because")
        elif t == "execution.done" and c.get("approval") in g.nodes:
            g.nodes[c["approval"]].status = "executed"
        elif t == "draft.made":
            d = g.add(c["id"], "draft", c["kind"], e, deal=deal, props={k: v for k, v in c.items() if k != "slides"})
            for s in c.get("slides", []):
                sl = g.add(f"{c['id']}/{s['n']}", "slide", s["text"], e, deal=deal, props={**s, "kind": c["kind"]})
                g.link(sl.id, "part_of", d.id, e)
                for f in s.get("facts", []):
                    g.link(sl.id, "uses", f, e)
        elif t == "review.returned" and c.get("draft") in g.nodes:
            g.nodes[c["draft"]].status = "sent_back"
            g.nodes[c["draft"]].props["reason"] = c.get("reason")
        elif t in ("decision.needed", "question.asked", "check.raised", "approval.requested"):
            typ, prefix = {"decision.needed": ("decision", "N"), "question.asked": ("question", "Q"), "check.raised": ("check", "C"),
                           "approval.requested": ("request", "R")}[t]
            who = c.get("who") or c.get("to") or c.get("reviewer")
            text = c.get("text") or c.get("question") or c.get("title") or c.get("summary")
            n = g.add(f"{prefix}{e['id']}", typ, text, e, deal=deal, status="open",
                      props={**c, "who": pid(who) or who, "text": text, "agent": e.get("agent")})
            for r in c.get("refs", []):
                g.link(n.id, "about", r, e)
        elif t == "knowledge.added":
            g.add(c["id"], "knowledge", c["title"], e, status="confirmed" if c.get("confirmed") else "proposed", props=dict(c))
        elif t == "knowledge.confirmed" and c.get("id") in g.nodes:
            g.nodes[c["id"]].status = "confirmed"
            g.nodes[c["id"]].props["confirmed_by"] = e["actor"]
        elif t == "listing.added":  # a later one updates only the fields it carries; no status means the status is kept
            old = g.nodes.get(f"listing:{c['ref']}")
            g.add(f"listing:{c['ref']}", "listing", c.get("title") or (old.label if old else c["ref"]), e,
                  status=c.get("status") or (old.status if old else "available"), props=dict(c) | {"updated_at": e["at"]})
        elif t.startswith("item.") or t.startswith("change."):
            from diwan import knowledge
            knowledge.apply(g, e)
        elif t in ("chat.received", "chat.sent", "chat.suggested", "chat.handover"):
            ch = g.nodes.get(f"chat:{c['chat']}") or g.add(f"chat:{c['chat']}", "chat", c.get("name") or c["chat"], e, deal=deal,
                                                            props={"phone": c["chat"], "mode": "ai", "messages": []})
            if deal:
                ch.deal = deal
            if c.get("name"):
                ch.label = c["name"]
            if t == "chat.handover":
                ch.props["mode"] = c["mode"]
                ch.props["handled_by"] = c.get("by")
            else:
                ch.props["messages"].append({"event": e["id"], "at": e["at"], "type": t.split(".")[1], "by": e["actor"],
                                             "text": c["text"], "refs": c.get("refs", []), "via": c.get("via"),
                                             "status": c.get("status"), "error": c.get("error"), "template": c.get("template"),
                                             "comment_id": c.get("comment_id"), "channel": c.get("channel"), "nudge": c.get("nudge"),
                                             "reminder": c.get("reminder"), "image": c.get("image"), "email": c.get("email"),
                                             "media_id": c.get("media_id"), "referred_by": c.get("referred_by")})
                ch.props["last_at"] = e["at"]
                if (into := g.nodes.get(f"chat:{ch.props.get('merged_into')}")) is not None:  # merged: it shows in that lead's thread too
                    into.props["messages"].append(ch.props["messages"][-1] | {"chat": ch.props["phone"]})
                    into.props["last_at"] = e["at"]
        elif t == "chat.merged" and f"chat:{c['into']}" in g.nodes and f"chat:{c['from']}" in g.nodes:
            into, frm = g.nodes[f"chat:{c['into']}"], g.nodes[f"chat:{c['from']}"]  # the same person on two numbers or accounts
            frm.props["merged_into"], frm.deal = c["into"], into.deal
            into.props.setdefault("merged", []).append(c["from"])
            into.props["messages"] = sorted(into.props["messages"] + [m | {"chat": c["from"]} for m in frm.props["messages"]], key=lambda m: m["event"])
            into.props["last_at"] = max(into.props.get("last_at") or "", frm.props.get("last_at") or "")
        elif t == "stage.changed" and f"deal:{deal}" in g.nodes:
            g.nodes[f"deal:{deal}"].props["stage"] = c["stage"]
            g.nodes[f"deal:{deal}"].props.setdefault("stages", []).append({"stage": c["stage"], "at": e["at"], "by": e["actor"]})
        elif t == "autonomy.changed":
            g.autonomy[c["agent"]] = c["level"]
        elif t == "lesson.added":
            g.add(c["id"], "lesson", c["rule"], e, status="active", props=dict(c) | {"by": e["actor"]})
        elif t == "lesson.removed" and c.get("id") in g.nodes:
            g.nodes[c["id"]].status = "removed"
        elif t == "setting.changed":
            g.settings.setdefault(c["person"], {})[c["key"]] = c["value"]
            if c["key"] == "property" and c["person"] in g.nodes:  # the deal's real property replaces its placeholder everywhere
                g.nodes[c["person"]].props["property"] = c["value"]["label"]
                g.nodes[c["person"]].label = c["value"]["label"]
                g.nodes[c["person"].replace("deal:", "property:", 1)].label = c["value"]["label"]
        elif t == "rounds.started":
            g.rounds = {"event": e["id"], "at": e["at"], "reports": {}}
        elif t == "agent.pack" and g.rounds and e.get("caused_by") == g.rounds["event"]:
            g.rounds["reports"][e["agent"]] = c["pack"]
        elif t == "lobby.posted":
            n = g.add(c["id"], "lobby", c["text"], e, deal=deal, status="open", props=dict(c))
            if c.get("task"):
                g.link(n.id, "tracks", c["task"], e)
        elif t in ("lobby.seen", "lobby.reminded", "lobby.late", "lobby.done", "lobby.cancelled") and c.get("id") in g.nodes:
            n = g.nodes[c["id"]]
            step = t.split(".")[1]
            n.props.setdefault("history", []).append({"step": step, "at": e["at"], "by": e["actor"], "note": c.get("note")})
            if step in ("done", "cancelled"):
                n.status = step
                n.props["closed_at"] = e["at"]
            elif step == "late" and n.status != "done":
                n.status = "late"
            elif step == "seen" and n.status == "open":
                n.status = "seen"
            if step == "reminded":
                n.props["reminded"] = True
        elif t == "document.filed":
            d = g.add(c["id"], "document", c["title"], e, deal=c.get("deal"), status="filed", props=dict(c))
            if c.get("deal"):
                g.link(d.id, "filed_under", f"deal:{c['deal']}", e)
        elif t == "sale.closed":
            g.add(c["id"], "sale", c["listing"], e, status="closed", props=dict(c))
        elif t == "appointment.booked":
            v = g.add(c["id"], "viewing", f"{c.get('kind_name') or 'Viewing'} {c.get('listing') or ''}".strip(), e, deal=deal, status="booked", props=dict(c))
            if c.get("listing"):
                g.link(v.id, "of", f"listing:{c['listing']}", e)
            g.link(v.id, "with", g.person(c["broker"], e), e)
            if c.get("chat"):
                g.link(f"chat:{c['chat']}", "booked", v.id, e)
        elif t in ("appointment.link", "appointment.link_removed") and c.get("id") in g.nodes:  # a video call's link
            v = g.nodes[c["id"]]
            if t == "appointment.link_removed":
                v.props.pop("link", None)
            else:
                v.props["link"] = {k: c.get(k) for k in ("provider", "url", "meeting_id", "error")}
        elif t == "calendar.blocked":  # the broker's own busy time or day off; the same id changes it
            b = g.nodes.get(c["id"]) or g.add(c["id"], "block", c.get("reason") or "Busy", e, status="active", props={})
            b.props.clear()
            b.props.update(c)
            b.label = c.get("reason") or ("Day off" if c.get("kind") == "off" else "Busy")
        elif t == "calendar.unblocked" and c.get("id") in g.nodes:
            g.nodes[c["id"]].status = "removed"
        elif t == "appointment.cancelled" and c.get("id") in g.nodes:
            g.nodes[c["id"]].status = "cancelled"
        elif t in ("appointment.moved", "appointment.reminded", "appointment.done", "appointment.noshow") and c.get("id") in g.nodes:
            v = g.nodes[c["id"]]
            if t == "appointment.moved":
                v.props["at"], v.props["moved_from"] = c["at"], c.get("from")
                v.props.pop("reminded", None)  # a new time gets its reminders again
            elif t == "appointment.reminded":
                v.props.setdefault("reminded", []).append(c["which"])
            else:
                v.status = "done" if t == "appointment.done" else "no_show"
                v.props["closed_event"] = e["id"]
        elif t == "lead.assigned" and f"deal:{deal}" in g.nodes:
            d = g.nodes[f"deal:{deal}"]
            d.props.update(broker=c["to"], assigned_at=c.get("at") or e["at"], assigned_why=c.get("why"))
            g.link(g.person(c["to"], e), "broker_on", d.id, e)
            for n in g.of("attention", deal, "open"):
                n.props["who"] = c["to"]
        elif t == "attention.raised":
            if c.get("replaces") in g.nodes:
                g.nodes[c["replaces"]].status = "replaced"
            n = g.add(f"AT{e['id']}", "attention", c["reason"], e, deal=deal, status="open", props=dict(c))
            g.link(n.id, "about", f"chat:{c['chat']}", e)
        elif t in ("attention.overdue", "attention.cleared", "attention.moved", "lead.pooled", "lead.claimed") and c.get("id") in g.nodes:
            n = g.nodes[c["id"]]
            if t == "attention.moved":  # nobody called in time: it goes to the next free broker, with a new limit
                n.props.update(who=c["to"], due=c["due"], overdue=False, escalated=n.props.get("escalated", 0) + 1, moved_from=c["from"])
            elif t == "attention.overdue":
                n.props["overdue"] = True
            elif t == "attention.cleared":
                n.status = "cleared"
                n.props.update(action=c["action"], note=c.get("note"), cleared_by=e["actor"], cleared_at=e["at"], cleared_event=e["id"])
            elif t == "lead.pooled":
                n.props["pooled"] = True
                if f"deal:{deal}" in g.nodes:
                    g.nodes[f"deal:{deal}"].props["pool"] = True
            else:
                n.props.update(pooled=False, who=c["to"])
                if f"deal:{deal}" in g.nodes:
                    g.nodes[f"deal:{deal}"].props.update(pool=False, broker=c["to"], assigned_at=e["at"], assigned_why="claimed from the Pool")
        elif t == "agent.added":
            g.custom_agents[c["id"]] = dict(c) | {"status": "active", "added_by": e["actor"], "added_at": e["at"],
                                                  "done_upto": c.get("from_event", e["id"]), "runs": 0}
        elif t in ("agent.paused", "agent.resumed", "agent.removed") and c.get("id") in g.custom_agents:
            a = g.custom_agents[c["id"]]
            a["status"] = {"agent.paused": "paused", "agent.resumed": "active", "agent.removed": "removed"}[t]
            if t == "agent.resumed":
                a["done_upto"] = e["id"]  # a resumed agent starts from now, not from what it missed
        elif t == "qualify.form":
            g.qualify_form = dict(c) | {"saved_by": e["actor"], "saved_at": e["at"]}
        elif t in ("qualify.type", "qualify.answer", "qualify.asked", "qualify.passed", "qualify.not_fit", "qualify.open") \
                and f"deal:{deal}" in g.nodes:
            d = g.nodes[f"deal:{deal}"].props
            if t == "qualify.asked":
                d["qualify_asked"], d["qualify_asked_event"] = c["field"], e["id"]
                if c.get("checked") is not None:  # Rania asked them to confirm a figure: once
                    d["budget_checked"] = str(c["checked"])
            elif t == "qualify.type":
                d.update(qtype=c["type"], qtype_quote=c.get("quote"), qtype_source=c.get("source"))
            elif t == "qualify.answer":
                old = d.setdefault("answers", {}).get(c["field"]) or {}
                d["answers"][c["field"]] = {"value": c["value"], "quote": c.get("quote"), "at": e["at"], "by": e["actor"],
                                            "cause": e.get("caused_by"), "unsure": bool(c.get("unsure")), "source": c.get("source"),
                                            "times": old.get("times", 0) + 1 if c.get("unsure") else 0}
            elif t == "qualify.open":
                d.setdefault("open_questions", []).append(c["question"])
            else:
                d.update(qualify_status="qualified" if t == "qualify.passed" else "not_a_fit", qualify_reason=c.get("reason"),
                         qualify_at=e["at"], qualify_version=c.get("version"))
        elif t == "visit.summarized" and f"deal:{deal}" in g.nodes:  # what the client said at the visit, with their words
            g.nodes[f"deal:{deal}"].props["visit"] = dict(c) | {"at": e["at"], "id": e["id"]}
        elif t in ("followup.drafted", "followup.sent", "followup.dismissed") and f"deal:{deal}" in g.nodes:
            d = g.nodes[f"deal:{deal}"].props
            if t == "followup.drafted":
                d["followup"] = dict(c) | {"status": "draft", "at": e["at"], "id": e["id"]}
            elif d.get("followup"):
                d["followup"]["status"] = "sent" if t == "followup.sent" else "dismissed"
        elif t in ("lead.recommended", "lead.hot", "lead.unhot", "lead.no_calls", "lead.followups", "lead.kind", "lead.nurture", "lead.reopened", "followup.nudged", "lead.optout", "lead.outcome",
                   "lead.went_quiet") and f"deal:{deal}" in g.nodes:
            d = g.nodes[f"deal:{deal}"].props
            if t == "followup.nudged":  # a follow-up while the client was quiet, sent or skipped (and why)
                d.setdefault("nudges", []).append({"event": e["id"], "at": e["at"], "n": c["n"], "sent": c.get("sent"), "why": c.get("why")})
            elif t == "lead.optout":
                d["optout"] = {"quote": c.get("quote"), "at": e["at"], "event": e["id"]}
            elif t == "lead.went_quiet":
                d["went_quiet"] = e["id"]
            elif t == "lead.unhot":  # a person says it isn't hot after all
                d.pop("hot", None)
            elif t == "lead.followups":  # this lead's own follow-up schedule, or stopped for this lead (None: the office's)
                d["followups"] = {"after_hours": c.get("after_hours"), "stopped": bool(c.get("stopped")), "by": e["actor"], "at": e["at"]} \
                    if c.get("after_hours") or c.get("stopped") else None
            elif t == "lead.no_calls":  # the client asked not to be called (or asked for a call again)
                if c.get("on"):
                    d["no_calls"] = {"by": e["actor"], "at": e["at"], "quote": c.get("quote")}
                else:
                    d.pop("no_calls", None)
            elif t == "lead.kind":
                d["kind"], d["kind_name"] = c["kind"], c["name"]
            elif t == "lead.outcome":  # what came of the call, as the broker recorded it
                d["outcome"] = {"event": e["id"], "outcome": c["outcome"], "reason": c.get("reason"), "note": c.get("note"), "at": e["at"], "by": e["actor"]}
            elif t == "lead.recommended" and c.get("offered"):  # a new listing the broker sent: their list so far stays
                d["offered"] = (d.get("offered") or []) + list(c["refs"])
            elif t == "lead.recommended":
                d["recommended"] = list(c["refs"])
            elif t == "lead.nurture":  # not ready yet: nurtured (by Marketing, by default) until they come back
                d["nurture"] = {"reason": c.get("reason"), "quote": c.get("quote"), "to": c.get("to"), "at": e["at"]}
            elif t == "lead.reopened":
                d.pop("nurture", None)
                d["reopened"] = {"quote": c.get("quote"), "at": e["at"]}
            else:
                d["hot"] = {"listing": c.get("listing"), "why": c.get("why"), "quote": c.get("quote"), "at": e["at"]}
        elif t == "thread.posted":
            g.add(c["id"], "thread", c["title"], e, status="posted", props=dict(c))
        elif t == "playbook.added":
            g.add(c["id"], "playbook", c["pattern"], e, status="live", props=dict(c))
        elif t == "playbook.removed" and c["id"] in g.nodes:
            g.nodes[c["id"]].status = "removed"
        elif t == "experiment.proposed":
            g.add(c["id"], "experiment", c["title"], e, status="proposed", props=dict(c) | {"by": e["actor"]})
        elif t.startswith("experiment.") and c.get("id") in g.nodes:
            n, rest = g.nodes[c["id"]], {k: v for k, v in c.items() if k != "id"}
            if t == "experiment.switched":  # what a change left behind: a lesson, a topic
                n.props.update(rest)
            elif t == "experiment.approved":
                n.status = "running"
                n.props.update(rest | {"started": e["id"], "decided_by": e["actor"]})
                n.label = c["title"]
            elif t == "experiment.refused":
                n.status = "refused"
                n.props.update(reason=c.get("reason"), decided_by=e["actor"])
            elif t == "experiment.reported":
                n.status = "reporting"
                n.props["result"] = c["result"]
            elif t == "experiment.ended":
                n.status = c["outcome"]
                n.props.update(reason=c.get("reason"), decided_by=e["actor"], ended_at=c.get("at"))
        elif t == "notify.sent":
            g.add(f"NT{e['id']}", "notice", c["text"], e, status="new", props=dict(c))
        elif t == "notify.read":
            for i in c.get("ids", []):
                if i in g.nodes:
                    g.nodes[i].status = "read"
        elif t in ("decision.made", "question.answered") and c.get("card") in g.nodes:
            g.nodes[c["card"]].status = "closed"
            g.nodes[c["card"]].props["answer"] = c.get("answer")
    return g
