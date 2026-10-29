"""The Deal desk over HTTP (docs/deal-desk.md): the deals list, one deal as its departments see it (what the customer
said and what replaced what, Compliance, Finance, Paperwork, Review), and the few things only a person does here:
answer a card, carry out an approval.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from diwan.agents import review
from diwan.agents.charters import BY_ID
from diwan.graph import KIND, OPEN, Graph, Node
from diwan.people import name, pid

router = APIRouter()
PAGE = 50
DEPTS = {"comp": "Compliance", "fin": "Finance", "ops": "Paperwork", "review": "Review"}


def _office():
    from diwan.app import S
    return S.office


def dept(agent: str | None) -> str:
    c = BY_ID.get(agent or "")
    if not c:
        return "office"
    return c.id if c.level == "lead" else c.parent or "office"


def _fact(g: Graph, f: Node) -> dict:
    p = f.props
    return {"id": f.id, "kind": p["kind"], "label": KIND.get(p["kind"], p["kind"]), "quote": p["quote"], "speaker": p.get("speaker"),
            "stance": p.get("stance", "asserted"), "status": f.status, "replaced_by": p.get("superseded_by"),
            "replaces": p.get("replaces") or [], "at": f.at}


def _facts_on(g: Graph, ids: list[str]) -> list[dict]:
    return [{"id": i, "quote": g.nodes[i].props.get("quote"), "status": g.nodes[i].status} for i in ids if i in g.nodes]


def _card(g: Graph, n: Node) -> dict:
    p = n.props
    can = None
    if n.status == "open" and n.type == "decision" and p.get("agent") == "factcheck":
        can = "reapprove"
    elif n.status == "open" and n.type == "check" and dept(p.get("agent")) == "comp":
        can = "reviewed"
    old = g.nodes.get((p.get("refs") or [None])[0]) if can == "reapprove" else None
    return {"id": n.id, "type": n.type, "who": p.get("who"), "who_name": name(p.get("who")), "text": p["text"],
            "title": p.get("title"), "options": p.get("options") or [], "status": n.status, "answer": p.get("answer"),
            "agent": p.get("agent"), "dept": dept(p.get("agent")), "at": n.at, "can": can,
            "refs": _facts_on(g, [r for r in p.get("refs", []) if r.startswith("F")]),
            "approval": old.props["action"] if old else None}


def deal_view(g: Graph, deal: str) -> dict:
    d = g.nodes.get(f"deal:{deal}")
    if not d or d.type != "deal":
        raise KeyError(deal)
    tasks = [{"id": t.id, "agent": t.props["agent"], "agent_name": t.props.get("agent_name"), "dept": dept(t.props["agent"]),
              "action": t.props["action"], "status": t.status, "reason": t.props.get("reason"), "at": t.at,
              "needs_person": t.props.get("needs_person"), "rests_on": _facts_on(g, t.props.get("rests_on", []))}
             for t in g.of("task", deal)]
    approvals = [{"id": a.id, "approver": a.props["approver"], "approver_name": name(a.props["approver"]), "action": a.props["action"],
                  "status": a.status, "because": a.props.get("because"), "stale": [f.id for f in g.stale(a.id)],
                  "rests_on": _facts_on(g, a.props.get("rests_on", []))} for a in g.of("approval", deal)]
    drafts = [{"id": x.id, "kind": x.props["kind"], "version": x.props.get("version", 1), "status": x.status, "reason": x.props.get("reason"),
               "slides": [{"n": s.props["n"], "text": s.props["text"], "facts": s.props.get("facts", []), "stale": [f.id for f in g.stale(s.id)]}
                          for s in sorted(g.into(x.id, "part_of"), key=lambda s: s.props["n"])]}
              for x in g.of("draft", deal)]
    cards = [_card(g, n) for t in ("check", "decision", "question") for n in g.of(t, deal)]
    cards.sort(key=lambda c: c["at"])
    return {"deal": deal, "property": d.props.get("property"), "customer": d.props.get("customer"), "broker": d.props.get("broker"),
            "broker_name": name(d.props.get("broker")), "stage": d.props.get("stage"),
            "said": [_fact(g, f) for f in g.of("fact", deal)], "cards": cards, "tasks": tasks, "approvals": approvals, "drafts": drafts}


def waiting(g: Graph, deal: str) -> list[str]:
    """The people something on this deal is waiting for."""
    who = [n.props.get("who") for t in ("check", "decision", "question") for n in g.of(t, deal, "open")]
    who += [t.props.get("needs_person") for t in g.of("task", deal) if t.status in OPEN]
    return sorted({w for w in who if w})


# ---------- HTTP ----------

@router.get("/api/desk/deals")
def deals(q: str = "", needs: bool = False, page: int = 1):
    g = _office().graph()
    words = q.lower().split()
    rows = []
    for d in sorted(g.deals(), key=lambda d: -d.event):
        p, deal = d.props, d.deal
        hay = f"{deal} {p.get('property', '')} {p.get('customer', '')} {name(p.get('broker'))}".lower()
        if words and not all(w in hay for w in words):
            continue
        w = waiting(g, deal)
        if needs and not w:
            continue
        rows.append({"deal": deal, "property": p.get("property"), "customer": p.get("customer"), "broker_name": name(p.get("broker")),
                     "stage": p.get("stage"), "waiting": [name(x) for x in w]})
    page = max(1, page)
    return {"total": len(rows), "page": page, "pages": max(1, -(-len(rows) // PAGE)), "rows": rows[(page - 1) * PAGE: page * PAGE]}


@router.get("/api/desk/deals/{deal}")
def deal(deal: str):
    try:
        return deal_view(_office().graph(), deal)
    except KeyError:
        raise HTTPException(404, f"There is no deal {deal!r}.") from None


class Answer(BaseModel):
    by: str
    choice: str
    action: str = ""
    note: str = ""


@router.post("/api/desk/cards/{card}/answer")
def answer(card: str, body: Answer):
    o = _office()
    g = o.graph()
    n = g.nodes.get(card)
    if not n or n.type not in ("check", "decision", "question"):
        raise HTTPException(404, f"There is no card {card}.")
    if n.status != "open":
        raise HTTPException(409, f"{card} was already answered: {n.props.get('answer')}.")
    if pid(body.by) != n.props.get("who"):
        raise HTTPException(403, f"Only {name(n.props.get('who'))} can answer {card}.")
    c = _card(g, n)
    try:
        if c["can"] == "reapprove" and body.choice == "Re-approve on the new facts":
            return {"approval": review.reapprove(o, n, pid(body.by), body.action)}
        if c["can"] == "reapprove" and body.choice == "Cancel":
            review.cancel(o, n, pid(body.by))
            return {"ok": True}
        if c["can"] == "reviewed" and body.choice == "Reviewed":
            o.log.append("decision.made", actor=pid(body.by), deal=n.deal, content={"card": card, "answer": "Reviewed", "note": body.note})
            return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    raise HTTPException(400, f"{card} can't be answered with {body.choice!r} here.")


class Run(BaseModel):
    by: str


@router.post("/api/desk/approvals/{aid}/execute")
def execute(aid: str, body: Run):
    o = _office()
    a = o.graph().nodes.get(aid)
    if not a or a.type != "approval":
        raise HTTPException(404, f"There is no approval {aid}.")
    if pid(body.by) != a.props["approver"]:
        raise HTTPException(403, f"Only {name(a.props['approver'])} can carry out {aid}.")
    return o.execute(aid, aid)
