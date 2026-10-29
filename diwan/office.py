"""What happens when something is said, built on the graph. A replaced statement is traced through the graph to
everything resting on it: compliance hears first, then dependent tasks are withdrawn, approvals go back to the person
who gave them, and drafts are sent back. Nothing that does not rest on the old statement is touched.
What each department does with a change lives in its own module (agents/compliance, finance, review); this engine
decides the order.
"""
from __future__ import annotations

from diwan.agents import compliance, finance, operations, review
from diwan.agents.charters import get
from diwan.events import EventLog
from diwan.graph import OPEN, Graph, build

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

    # meetings: nothing is heard before the customer agrees to the recording
    def meeting(self, mid: str) -> dict:
        m = None
        for e in self.log.list():
            c = e["content"]
            if e["type"] == "meeting.started" and c["meeting"] == mid:
                m = {"id": mid, "deal": e["deal"], "title": c.get("title"), "speakers": c.get("speakers", {}), "consent": False,
                     "ended": False, "turns": []}
            elif m and c.get("meeting") == mid:
                if e["type"] == "consent.given":
                    m["consent"] = True
                elif e["type"] == "meeting.ended":
                    m["ended"] = True
                elif e["type"] == "utterance":
                    m["turns"].append(c)
        if m is None:
            raise KeyError(f"no meeting {mid!r}")
        return m

    def start_meeting(self, deal: str, mid: str, *, title: str, speakers: dict[str, str] | None = None, by: str = "omar") -> dict:
        """`speakers` maps the labels transcription gives (speaker_0, customer...) to people."""
        g = self.graph()
        d = g.nodes[f"deal:{deal}"].props
        speakers = speakers or {"customer": d["customer"], "broker": d["broker"], "speaker_0": d["broker"], "speaker_1": d["customer"]}
        return self.log.append("meeting.started", actor=by, deal=deal, key=f"meeting:{mid}",
                               content={"meeting": mid, "title": title, "speakers": speakers})

    def give_consent(self, mid: str, *, by: str) -> dict:
        m = self.meeting(mid)
        return self.log.append("consent.given", actor=by, deal=m["deal"], key=f"consent:{mid}", content={"meeting": mid, "by": by})

    def utterance(self, mid: str, label: str, text: str, *, turn: str | None = None) -> dict:
        m = self.meeting(mid)
        if not m["consent"]:
            raise PermissionError("The customer has not agreed to the recording; nothing is kept.")
        if m["ended"]:
            raise PermissionError("The meeting has ended.")
        speaker = m["speakers"].get(label, label)
        return self.log.append("utterance", actor="voice", agent="scribe", deal=m["deal"], key=f"turn:{mid}:{turn}" if turn else None,
                               content={"meeting": mid, "label": label, "speaker": speaker, "text": text})

    def end_meeting(self, mid: str, *, by: str = "omar") -> dict:
        m = self.meeting(mid)
        return self.log.append("meeting.ended", actor=by, deal=m["deal"], key=f"end:{mid}", content={"meeting": mid, "turns": len(m["turns"])})

    def record_fact(self, deal: str, kind: str, quote: str, speaker: str, *, replaces: str | list[str] | None = None,
                    stance: str = "asserted", actor: str = "scribe", caused_by: int | None = None, **props) -> str:
        """`stance`: asserted, negated or hypothetical. Only asserted statements create or change work."""
        g = self.graph()
        fid = self._next(g, "fact", "F")
        olds = [replaces] if isinstance(replaces, str) else list(replaces or [])
        ev = self.log.append("fact.created", actor=actor, agent="scribe", deal=deal, caused_by=caused_by,
                             content={"id": fid, "kind": kind, "quote": quote, "speaker": speaker, "stance": stance,
                                      "replaces": olds, **props})
        if stance != "asserted":
            return fid
        if olds:
            self._replace(deal, olds, fid, ev["id"])
        else:
            self._contradictions(deal, fid, ev["id"])
        compliance.screen_parties(self, deal, ev["id"])
        compliance.cash_rules(self, deal, ev["id"])
        compliance.ask_funding(self, deal, ev["id"])
        finance.payment_rules(self, deal, ev["id"])
        return fid

    def _replace(self, deal: str, olds: list[str], new: str, cause: int) -> None:
        g = self.graph()
        n = g.nodes[new]
        os_ = [g.nodes[o] for o in olds]
        compliance.money_changed(self, deal, os_, n, cause)
        sent_back = set()
        for o in os_:
            sup = self.log.append("fact.superseded", actor="scribe", agent="scribe", deal=deal, caused_by=cause, content={"id": o.id, "by": new})
            g = self.graph()
            for x in g.impact(o.id):
                if x.type == "task" and x.status in OPEN:
                    self.log.append("task.withdrawn", actor=x.props["agent"], agent=x.props["agent"], deal=deal, caused_by=sup["id"],
                                    content={"id": x.id, "reason": f'{o.id} was replaced by {new}: "{n.props["quote"]}"'})
                elif x.type == "approval" and x.status == "given":
                    review.approval_stale(self, deal, x, o, n, sup["id"])
                elif x.type == "slide":
                    review.slide_stale(self, g, deal, x, o, n, sup["id"], sent_back)
        operations.replan(self, deal, sent_back, cause)

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

    def add_task(self, deal: str | None, agent: str, action: str, *, rests_on: list[str] | None = None, needs_person: str | None = None,
                 by: str | None = None, caused_by: int | None = None, request: str | None = None, props: dict | None = None) -> str:
        c = get(agent)
        tid = self._next(self.graph(), "task", "T")
        self.log.append("task.created", actor=by or agent, agent=agent, deal=deal, caused_by=caused_by, request=request,
                        content={"id": tid, "agent": agent, "agent_name": c.name, "team": c.parent, "action": action,
                                 "rests_on": rests_on or [], "needs_person": needs_person, "by": by or agent, **(props or {})})
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
        review.check_draft(self, did)
        return did

    # what the office knows: typed by a person it is confirmed; pulled from a document it waits for a person to confirm
    def add_knowledge(self, kind: str, title: str, text: str, *, by: str, confirmed: bool = True, source: str | None = None) -> str:
        kid = self._next(self.graph(), "knowledge", "K")
        self.log.append("knowledge.added", actor=by, content={"id": kid, "kind": kind, "title": title, "text": text,
                                                              "confirmed": confirmed, "source": source})
        return kid

    def confirm_knowledge(self, kid: str, *, by: str) -> dict:
        return self.log.append("knowledge.confirmed", actor=by, key=f"confirm:{kid}", content={"id": kid})

    def add_listing(self, *, ref: str, title: str, community: str, type: str, beds: int, price_aed: int, permit: str | None,
                    status: str = "available", features: list[str] | None = None, by: str = "omar") -> str:
        """A listing without a permit number is kept but never advertised: Dubai requires a permit for every ad."""
        self.log.append("listing.added", actor=by, content={"ref": ref, "title": title, "community": community, "type": type,
                                                            "beds": beds, "price_aed": price_aed, "permit": permit,
                                                            "status": status, "features": features or []})
        return f"listing:{ref}"

    # the archive
    def file_document(self, *, kind: str, title: str, date: str, by: str = "archivist", deal: str | None = None,
                      amount_aed: int | None = None, party: str | None = None, text: str = "") -> str:
        did = f"DOC{len(self.graph().of('document')) + 1}"
        self.log.append("document.filed", actor=by, agent="archivist", deal=deal,
                        content={"id": did, "kind": kind, "title": title, "date": date, "deal": deal, "amount_aed": amount_aed,
                                 "party": party, "text": text})
        return did

    def close_sale(self, *, listing: str, price_aed: int, commission_aed: int, broker: str, date: str, deal: str | None = None) -> str:
        sid = f"S{len(self.graph().of('sale')) + 1}"
        self.log.append("sale.closed", actor=broker, agent="records", deal=deal,
                        content={"id": sid, "listing": listing, "price_aed": price_aed, "commission_aed": commission_aed,
                                 "broker": broker, "date": date, "deal": deal})
        return sid
