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
from datetime import datetime

from diwan.people import PEOPLE, name, pid

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
            return f"{n.id} · {p['title']}: {p['text']}{'' if n.status == 'confirmed' else ' [not confirmed]'}"
        if n.type == "listing":
            return (f"{p['ref']} · {p['title']}, {p['community']} · {p['beds']} bed {p['type']} · AED {p['price_aed']:,} · "
                    f"permit {p.get('permit') or 'MISSING'} · {n.status}")
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
            return f"{n.id} · viewing of {p['listing']} with {name(p['broker'])}, {when}, for {p.get('customer')}{tag if n.status != 'booked' else ''}"
        if n.type == "deal":
            return f"{n.id.split(':', 1)[1]} · {p.get('property')} · customer {p.get('customer')} · broker {name(p.get('broker'))}"
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
        elif t in ("task.withdrawn", "task.done") and c.get("id") in g.nodes:
            n = g.nodes[c["id"]]
            n.status = t.split(".")[1]
            n.props["reason"] = c.get("reason")
            if c.get("result"):
                n.props["result"] = c["result"]
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
        elif t == "listing.added":
            g.add(f"listing:{c['ref']}", "listing", c["title"], e, status=c.get("status", "available"), props=dict(c))
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
                                             "comment_id": c.get("comment_id"), "channel": c.get("channel")})
                ch.props["last_at"] = e["at"]
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
            v = g.add(c["id"], "viewing", f"Viewing {c['listing']}", e, deal=deal, status="booked", props=dict(c))
            g.link(v.id, "of", f"listing:{c['listing']}", e)
            g.link(v.id, "with", g.person(c["broker"], e), e)
            if c.get("chat"):
                g.link(f"chat:{c['chat']}", "booked", v.id, e)
        elif t == "appointment.cancelled" and c.get("id") in g.nodes:
            g.nodes[c["id"]].status = "cancelled"
        elif t in ("decision.made", "question.answered") and c.get("card") in g.nodes:
            g.nodes[c["card"]].status = "closed"
            g.nodes[c["card"]].props["answer"] = c.get("answer")
    return g
