"""What happens when something is said, built on the graph. A replaced statement is traced through the graph to
everything resting on it: compliance hears first, then dependent tasks are withdrawn, approvals go back to the person
who gave them, and drafts are sent back. Nothing that does not rest on the old statement is touched.
"""
from __future__ import annotations

from diwan.agents.charters import get
from diwan.events import EventLog
from diwan.graph import OPEN, Graph, build

MONEY_KINDS = {"payer", "payment_promise", "income_claim"}
CONFLICTS = {"payer": "payer", "deal_term": "amount_aed"}  # kinds where two different live values cannot both be true


class Office:
    def __init__(self, log: EventLog):
        self.log = log

    def graph(self, upto: int | None = None) -> Graph:
        return build(self.log.list(), upto)

    def _next(self, g: Graph, type: str, prefix: str) -> str:
        return f"{prefix}{len(g.of(type)) + 1}"

    def open_deal(self, deal: str, *, property: str, customer: str, broker: str, by: str = "omar") -> dict:
        return self.log.append("deal.opened", actor=by, deal=deal, key=f"deal:{deal}",
                               content={"property": property, "customer": customer, "broker": broker})

    def record_fact(self, deal: str, kind: str, quote: str, speaker: str, *, replaces: str | None = None,
                    actor: str = "scribe", caused_by: int | None = None, **props) -> str:
        g = self.graph()
        fid = self._next(g, "fact", "F")
        ev = self.log.append("fact.created", actor=actor, agent="scribe", deal=deal, caused_by=caused_by,
                             content={"id": fid, "kind": kind, "quote": quote, "speaker": speaker, "replaces": replaces, **props})
        if replaces:
            self._replace(deal, replaces, fid, ev["id"])
        else:
            self._contradictions(deal, fid, ev["id"])
        self._payment_rules(deal, ev["id"])
        return fid

    def _replace(self, deal: str, old: str, new: str, cause: int) -> None:
        g = self.graph()
        o, n = g.nodes[old], g.nodes[new]
        if o.props["kind"] in MONEY_KINDS or n.props["kind"] in MONEY_KINDS:
            self.log.append("check.raised", actor="comp", agent="comp", deal=deal, caused_by=cause,
                            content={"who": "priya", "title": "Payment arrangement changed", "refs": [old, new],
                                     "text": f'Payment arrangement changed: "{o.props["quote"]}" became "{n.props["quote"]}". Review before any money moves.'})
        sup = self.log.append("fact.superseded", actor="scribe", agent="scribe", deal=deal, caused_by=cause, content={"id": old, "by": new})
        g = self.graph()
        sent_back = set()
        for x in g.impact(old):
            if x.type == "task" and x.status in OPEN:
                self.log.append("task.withdrawn", actor=x.props["agent"], agent=x.props["agent"], deal=deal, caused_by=sup["id"],
                                content={"id": x.id, "reason": f'{old} was replaced by {new}: "{n.props["quote"]}"'})
            elif x.type == "approval" and x.status == "given":
                self.log.append("decision.needed", actor="factcheck", agent="factcheck", deal=deal, caused_by=sup["id"],
                                content={"who": x.props["approver"], "refs": [x.id, old, new], "options": ["Re-approve on the new facts", "Cancel"],
                                         "question": f'Your approval "{x.props["action"]}" rests on "{o.props["quote"]}", which the customer replaced with "{n.props["quote"]}".'})
            elif x.type == "slide":
                draft = g.out(x.id, "part_of")[0]
                if draft.id not in sent_back and draft.status != "sent_back":
                    sent_back.add(draft.id)
                    self.log.append("review.returned", actor="factcheck", agent="factcheck", deal=deal, caused_by=sup["id"],
                                    content={"draft": draft.id, "slide": x.props["n"], "old": o.props["quote"], "new": n.props["quote"],
                                             "reason": f"Slide {x.props['n']} still says what {old} said; the customer replaced it ({new})."})

    def _contradictions(self, deal: str, fid: str, cause: int) -> None:
        """Two live statements that cannot both be true, and nothing said which replaces which: never pick one.
        Both quotes go to the broker side by side; money work on that point waits."""
        g = self.graph()
        new = g.nodes[fid]
        field = CONFLICTS.get(new.props["kind"])
        if not field:
            return
        for old in g.facts(deal, new.props["kind"]):
            if old.id != fid and old.props.get(field) != new.props.get(field):
                broker = g.nodes[f"deal:{deal}"].props["broker"]
                self.log.append("decision.needed", actor="scribe", agent="scribe", deal=deal, caused_by=cause,
                                content={"who": broker, "refs": [old.id, fid], "options": [f"{fid} replaces {old.id}", f"{old.id} stands", "Ask the customer"],
                                         "question": f'These can\'t both be true: "{old.props["quote"]}" ({old.id}) and "{new.props["quote"]}" ({fid}). Which stands?'})

    def _payment_rules(self, deal: str, cause: int) -> None:
        """The Payment tracker's rules: every live payment promise has one open expectation resting on the promise and
        on who pays. A third-party payer is screened. Nobody named as payer: one question to the broker."""
        g = self.graph()
        payers = g.facts(deal, "payer")
        customer = g.nodes[f"deal:{deal}"].props["customer"]
        if len(payers) > 1:
            return  # a contradiction about who pays is open; nothing is expected from anyone until the broker decides
        for p in g.facts(deal, "payment_promise"):
            payer = payers[-1] if payers else None
            rests = [p.id] + ([payer.id] if payer else [])
            if any(t.props["agent"] == "pay" and t.status in OPEN and set(t.props.get("rests_on", [])) == set(rests) for t in g.of("task", deal)):
                continue
            if not payer:
                if not any(q.status == "open" and p.id in q.props.get("refs", []) for q in g.of("question", deal)):
                    self.log.append("question.asked", actor="pay", agent="pay", deal=deal, caused_by=cause,
                                    content={"to": "omar", "refs": [p.id], "text": f'Who pays this: "{p.props["quote"]}"?'})
                continue
            who = payer.props["payer"]
            self.add_task(deal, "pay", f"Expect AED {p.props['amount_aed']:,} by {p.props.get('method') or 'a method not yet stated'} from {who}",
                          rests_on=rests, caused_by=cause)
            if who.lower() != customer.lower():
                self.add_task(deal, "screen", f"Screen {who}, who will pay for {customer}", rests_on=[payer.id], caused_by=cause)
            g = self.graph()

    def add_task(self, deal: str | None, agent: str, action: str, *, rests_on: list[str] | None = None, needs_person: str | None = None,
                 by: str | None = None, caused_by: int | None = None, request: str | None = None) -> str:
        c = get(agent)
        tid = self._next(self.graph(), "task", "T")
        self.log.append("task.created", actor=by or agent, agent=agent, deal=deal, caused_by=caused_by, request=request,
                        content={"id": tid, "agent": agent, "agent_name": c.name, "team": c.parent, "action": action,
                                 "rests_on": rests_on or [], "needs_person": needs_person, "by": by or agent})
        return tid

    def finish_task(self, tid: str, reason: str, *, caused_by: int | None = None) -> None:
        t = self.graph().nodes[tid]
        self.log.append("task.done", actor=t.props["agent"], agent=t.props["agent"], deal=t.deal, caused_by=caused_by,
                        content={"id": tid, "reason": reason})

    def approve(self, deal: str, approver: str, action: str, rests_on: list[str]) -> str:
        aid = self._next(self.graph(), "approval", "A")
        self.log.append("approval.given", actor=approver, deal=deal, content={"id": aid, "approver": approver, "action": action, "rests_on": rests_on})
        return aid

    def execute(self, approval: str, key: str) -> dict:
        """The guard: an approval runs only while every statement it rests on is still live. Run twice, it runs once."""
        if done := next((e for e in self.log.list() if e["type"] == "execution.done" and e["content"]["key"] == key), None):
            return {"ok": True, "event": done, "duplicate": True}
        g = self.graph()
        a = g.nodes[approval]
        if a.status != "given":
            return {"ok": False, "because": f"{approval} is {a.status}"}
        if stale := g.stale(approval):
            f = stale[0]
            because = f'{f.id} ("{f.props["quote"]}") was replaced by {f.props["superseded_by"]}'
            self.log.append("approval.refused", actor="guard", agent="factcheck", deal=a.deal, content={"id": approval, "because": because})
            return {"ok": False, "because": because}
        ev = self.log.append("execution.done", actor=a.props["approver"], deal=a.deal, key=f"exec:{key}",
                             content={"approval": approval, "key": key, "action": a.props["action"]})
        return {"ok": True, "event": ev}

    def make_draft(self, deal: str, kind: str, slides: list[dict], *, by: str = "deck") -> str:
        g = self.graph()
        did = self._next(g, "draft", "D")
        version = 1 + len([d for d in g.of("draft", deal) if d.props["kind"] == kind])
        self.log.append("draft.made", actor=by, agent=by, deal=deal, content={"id": did, "kind": kind, "version": version, "slides": slides})
        return did
