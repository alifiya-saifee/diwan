"""The Deal desk over HTTP (docs/deal-desk.md): the deals list, one deal as its departments see it (what the customer
said and what replaced what, Compliance, Finance, Paperwork, Review), and the few things only a person does here:
answer a card, carry out an approval.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from diwan import agency_forms, deal_gates, deal_property, desk_kpis, desk_rules, desk_stages, documents, invoices, roles, signing
from diwan.agents import compliance, finance, operations, review
from diwan.agents.charters import BY_ID
from diwan.graph import KIND, OPEN, Graph, Node
from diwan.people import PEOPLE, name, pid

router = APIRouter()
PAGE = 50
DEPTS = {"comp": "Compliance", "fin": "Finance", "ops": "Paperwork", "review": "Review"}
DRAFT_DEPT = {"cash report": "comp", "suspicious transaction report": "comp", "Form F": "ops", "commission invoice": "fin"} | {k: "ops" for k in agency_forms.FORM_OF}  # any other (the deck) is Review's


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
    elif n.status == "open" and n.type == "question":
        can = "answer"
    old = g.nodes.get((p.get("refs") or [None])[0]) if can == "reapprove" else None
    w = roles.current(g, n)
    return {"id": n.id, "type": n.type, "who": w, "who_name": name(w), "text": p["text"],
            "title": p.get("title"), "options": p.get("options") or [], "status": n.status, "answer": p.get("answer"),
            "agent": p.get("agent"), "dept": dept(p.get("agent")), "at": n.at, "can": can,
            "refs": _facts_on(g, [r for r in p.get("refs", []) if r.startswith("F")]),
            "approval": old.props["action"] if old else None}


def deal_view(g: Graph, deal: str, today: date | None = None) -> dict:
    d = g.nodes.get(f"deal:{deal}")
    if not d or d.type != "deal":
        raise KeyError(deal)
    tasks = [{"id": t.id, "agent": t.props["agent"], "agent_name": t.props.get("agent_name"), "dept": dept(t.props["agent"]),
              "action": t.props["action"], "status": t.status, "reason": t.props.get("reason"), "at": t.at,
              "needs_person": roles.current(g, t), "rests_on": _facts_on(g, t.props.get("rests_on", [])),
              "person": t.props.get("person"), "result": t.props.get("result"), "draft": t.props.get("draft"),
              "waiting_on": t.props.get("waiting_on"), "step": t.props.get("step"), "amount_aed": t.props.get("amount_aed"),
              "after": operations.is_after(t), "due": t.props.get("due"), "flag": t.props.get("flag"), "portal": t.props.get("portal"), "invoice": t.props.get("invoice"),
              "portal_kind": (operations.portal_of(t.props["action"]) or [None, None])[1] if t.props["agent"] == "transfer" else None,
              "days": (today or date.today()).toordinal() - date.fromisoformat(t.at[:10]).toordinal(), "hit": t.props.get("hit"),
              **(finance.expected(g, t, today or date.today()) if t.props["agent"] == "pay" else {})}
             for t in g.of("task", deal)]
    approvals = [{"id": a.id, "approver": a.props["approver"], "approver_name": name(a.props["approver"]), "action": a.props["action"],
                  "status": a.status, "because": a.props.get("because"), "stale": [f.id for f in g.stale(a.id)],
                  "rests_on": _facts_on(g, a.props.get("rests_on", []))} for a in g.of("approval", deal)]
    drafts = [{"id": x.id, "kind": x.props["kind"], "dept": DRAFT_DEPT.get(x.props["kind"], "review"), "version": x.props.get("version", 1), "status": x.status, "reason": x.props.get("reason"),
               "slides": [{"n": s.props["n"], "text": s.props["text"], "facts": s.props.get("facts", []), "stale": [f.id for f in g.stale(s.id)]}
                          for s in sorted(g.into(x.id, "part_of"), key=lambda s: s.props["n"])]}
              for x in g.of("draft", deal)]
    cards = [_card(g, n) for t in ("check", "decision", "question") for n in g.of(t, deal)]
    cards.sort(key=lambda c: c["at"])
    return {"deal": deal, "property": d.props.get("property"), "customer": d.props.get("customer"), "broker": d.props.get("broker"),
            "broker_name": name(d.props.get("broker")), "stage": d.props.get("stage"),
            "said": [_fact(g, f) for f in g.of("fact", deal)], "cards": cards, "funds": compliance.source_of_funds(g, deal), "tasks": tasks, "approvals": approvals, "drafts": drafts}


def _compliance_view(g: Graph, deal: str) -> dict:
    d = g.nodes[f"deal:{deal}"].props
    return compliance.state(g, deal) | {"risk": d.get("risk"), "blockers": compliance.blockers(_office(), deal), "sof_needed": compliance.sof_needed(g, deal), "needs_senior": compliance.needs_senior(d.get("risk") or {})}


def waiting(g: Graph, deal: str) -> list[str]:
    """The people something on this deal is waiting for."""
    who = [n.props.get("who") for t in ("check", "decision", "question") for n in g.of(t, deal, "open")]
    who += [t.props.get("needs_person") for t in g.of("task", deal) if t.status in OPEN]
    return sorted({w for w in who if w})


# ---------- the whole office: summaries, the work queue, the overview ----------

SEV = {"bad": 0, "warn": 1, "info": 2}



def stage_order(g: Graph) -> list[str]:
    """Every stage any deal can be at, in the order deals travel, so none drops out of the overview."""
    return list(dict.fromkeys(desk_rules.SALES_STAGES + [x for p in desk_rules.rules(g)["paths"].values() for x in p["stages"]] + ["Won", "Lost"]))


class Ledger:
    """One pass over the graph, every node grouped by deal and type, so hundreds of deals cost one scan."""

    def __init__(self, g: Graph, today: date):
        self.g, self.today = g, today
        self.by: dict[str, dict[str, list[Node]]] = defaultdict(lambda: defaultdict(list))
        for n in g.nodes.values():
            if n.deal:
                self.by[n.deal][n.type].append(n)
        self._sum: dict[str, dict] = {}

    def live(self, deal: str) -> list[Node]:
        return [f for f in self.by[deal]["fact"] if f.status == "live" and f.props.get("stance", "asserted") == "asserted"]

    def open_tasks(self, deal: str, agent: str | None = None) -> list[Node]:
        return [t for t in self.by[deal]["task"] if t.status in OPEN and (agent is None or t.props["agent"] == agent)]

    def summary(self, deal: str) -> dict:
        if deal in self._sum:
            return self._sum[deal]
        g, by, d = self.g, self.by[deal], self.g.nodes[f"deal:{deal}"]
        live = self.live(deal)
        price = ([f for f in live if f.props["kind"] == "deal_term"] or [None])[-1]
        funds = compliance.source_of_funds(g, deal, by)
        screens = [t for t in by["task"] if t.props["agent"] == "screen"]
        flags = {"match": any(t.props.get("result") == "possible match" for t in screens), "cash": bool(self.open_tasks(deal, "report")),
                 "unscreened": any(t.status in OPEN for t in screens),
                 "checks": any(c.status == "open" and dept(c.props.get("agent")) == "comp" for c in by["check"]), "proof": bool(funds["missing"]),
                 "uncleared": bool(g.settings.get(f"deal:{deal}", {}).get("agreed")) and not compliance.state(g, deal)["ok"]}
        if any(t.props.get("result") == "possible match" for t in screens):
            comp = ("bad", "Possible match")
        elif self.open_tasks(deal, "report"):
            comp = ("bad", "Cash report to file")
        elif (st := compliance.state(g, deal))["state"] == "blocked":
            comp = ("bad", "Blocked")
        elif [t for t in screens if t.status in OPEN]:
            comp = ("bad", "Not screened")
        elif [c for c in by["check"] if c.status == "open" and dept(c.props.get("agent")) == "comp"]:
            comp = ("warn", "Check open")
        elif st["ok"]:
            comp = ("ok", "Cleared")
        elif funds["missing"]:
            comp = ("warn", f"{funds['missing']} proof missing")
        elif st["state"] in ("stale", "needs_info"):
            comp = ("warn", "Clear again" if st["state"] == "stale" else "Needs information")
        elif screens:
            comp = ("warn", "To clear")
        else:
            comp = ("none", "Nothing yet")
        pays = [finance.expected(g, t, self.today) | {"t": t} for t in by["task"] if t.props["agent"] == "pay"]
        due = [p for p in pays if p["t"].status in OPEN]
        late = [p for p in due if p.get("overdue")]
        got = [p for p in pays if p["t"].props.get("result") == "received"]
        money = (("bad", f"AED {_k(sum(p['amount_aed'] or 0 for p in late))} overdue") if late else
                 ("warn", f"AED {_k(sum(p['amount_aed'] or 0 for p in due))} expected") if due else
                 ("ok", f"AED {_k(sum(p['amount_aed'] or 0 for p in got))} received") if got else ("none", "Not said"))
        plans = [x for x in by["draft"] if x.props["kind"] == "Form F"]
        steps = [t for t in by["task"] if t.props["agent"] == "transfer"]
        submit = [t for t in self.open_tasks(deal, "formf") if t.props.get("draft")]
        if steps:
            n = sum(t.status == "done" for t in steps)
            paper = ("ok" if n == len(steps) else "warn", "Transfer done" if n == len(steps) else f"Transfer {n}/{len(steps)}")
        elif plans and plans[-1].status == "sent_back":
            paper = ("bad", "Form F sent back")
        elif submit:
            paper = ("warn", "Form F to submit")
        else:
            paper = ("none", "Not started")
        back = [x for x in by["draft"] if x.status == "sent_back" and DRAFT_DEPT.get(x.props["kind"], "review") == "review"]
        rev = ("bad", f"{len(back)} sent back") if back else ("ok", "Passed") if by["draft"] else ("none", "Nothing yet")
        waits = {roles.current(g, c) for t in ("check", "decision", "question") for c in by[t] if c.status == "open"}
        waits |= {roles.current(g, t) for t in by["task"] if t.status in OPEN}
        if due:
            waits.add(roles.holder(g, "finance"))
        week = (self.today - timedelta(days=7)).isoformat()
        cl = operations.closing(g, deal)
        phase = "closed" if cl and cl["sale"] else "closing" if cl else None
        out = {"phase": phase, "sale": cl["sale"] if cl else None, "closing_left": sum(not i["done"] for i in cl["items"]) if cl else None,
               "deal": deal, "customer": d.props.get("customer"), "property": d.props.get("property"), "broker": d.props.get("broker"),
               "broker_name": name(d.props.get("broker")), "stage": d.props.get("stage") or "New",
               "value": price.props.get("amount_aed") if price else None,
               "comp": comp, "money": money, "paper": paper, "review": rev,
               "steps": [sum(t.status == "done" for t in steps), len(steps)] if steps else None,
               "waiting": sorted(w for w in waits if w), "proof_missing": funds["missing"], "flags": flags,
               "changed": max([n.at for ns in by.values() for n in ns] + [d.at]),
               "corrected": any(f.props.get("replaces") and f.at[:10] >= week for f in by["fact"]),
               "expected": [{"amount": p["amount_aed"], "due": p["due"], "overdue": p.get("overdue")} for p in due]}
        self._sum[deal] = out
        return out

    def work(self) -> list[dict]:
        """Everything waiting for a person, across every deal: one row each, with what they can do about it."""
        items = []
        for deal, by in self.by.items():
            if f"deal:{deal}" not in self.g.nodes:
                continue
            s = self.summary(deal)
            base = {"deal": deal, "customer": s["customer"], "property": s["property"]}
            for c in (c for t in ("check", "decision", "question") for c in by[t] if c.status == "open" and c.props.get("who")):
                ag = c.props.get("agent")
                act = "reviewed" if c.type == "check" and dept(ag) == "comp" else "reapprove" if c.type == "decision" and ag == "factcheck" \
                    else "answer" if c.type == "question" else "open"
                kind = {"check": "Check", "decision": "Decision", "question": "Question"}[c.type]
                items.append(base | {"id": c.id, "who": roles.current(self.g, c), "kind": kind, "sev": "bad" if c.type in ("check", "decision") else "warn",
                                     "title": c.props.get("title") or c.props["text"], "text": c.props["text"], "at": c.at, "act": act,
                                     "approval": self.g.nodes[c.props["refs"][0]].props["action"] if act == "reapprove" else None})
            for t in by["task"]:
                if t.status not in OPEN:
                    continue
                ag, who = t.props["agent"], roles.current(self.g, t)
                if ag == "pay":
                    e = finance.expected(self.g, t, self.today)
                    soon = e.get("due") and e["due"] <= (self.today + timedelta(days=2)).isoformat()
                    items.append(base | {"id": t.id, "who": roles.holder(self.g, "finance"), "kind": "Overdue" if e.get("overdue") else "Due soon" if soon else "Expected",
                                         "sev": "bad" if e.get("overdue") else "warn" if soon else "info", "title": t.props["action"],
                                         "at": t.at, "act": "received", "due": e.get("due")})
                elif who and t.props["agent"] == "ops" and t.props.get("after_close"):
                    late = t.props.get("due", "9") < self.today.isoformat()
                    items.append(base | {"id": t.id, "who": who, "kind": "After closing", "sev": "bad" if late else "info", "title": t.props["action"],
                                         "at": t.at, "act": "after", "due": t.props.get("due")})
                elif who and t.props["agent"] == "ops" and t.props.get("step") in ("doc", "docs_call"):
                    items.append(base | {"id": t.id, "who": who, "kind": "Documents", "sev": "warn" if t.props["step"] == "doc" else "bad",
                                         "title": t.props["action"], "at": t.at, "act": "open" if t.props["step"] == "doc" else "docscall"})
                elif who and t.props["agent"] == "ops" and t.props.get("step") == "discount":
                    items.append(base | {"id": t.id, "who": who, "kind": "Discount", "sev": "warn", "title": t.props["action"], "at": t.at, "act": "discount"})
                elif who and t.props["agent"] == "ops" and t.props.get("step") in ("sides", "sign"):
                    items.append(base | {"id": t.id, "who": who, "kind": "Agency forms", "sev": "warn", "title": t.props["action"], "at": t.at,
                                         "act": "open" if t.props["step"] == "sides" else "sign", "draft": t.props.get("draft")})
                elif who and operations.is_closing(t):
                    items.append(base | {"id": t.id, "who": who, "kind": "Closing", "sev": "warn", "title": t.props["action"], "at": t.at,
                                         "act": "confirm" if t.props.get("step") == "figures" else "docs"})
                elif who and ag == "screen" and t.props.get("result") == "possible match":
                    items.append(base | {"id": t.id, "who": who, "kind": "Possible match", "sev": "bad", "title": f"{t.props.get('person')}: {t.props.get('hit')}", "at": t.at, "act": "hit"})
                elif who and ag in ("screen", "report", "formf", "transfer", "inv"):
                    kind, sev, act = {"screen": ("Screening", "warn", "screen"), "report": ("Report to file", "bad", "filed"),
                                      "formf": ("Form F", "warn", "submitted"), "transfer": ("Transfer", "info", "open" if t.props.get("flag") == "gate" else "tick"),
                                      "inv": ("Commission", "warn", {"send": "invoiced", "split": "split", "payout": "split"}.get(t.props.get("step"), "commission"))}[ag]
                    if ag == "formf" and not t.props.get("draft"):
                        continue
                    items.append(base | {"id": t.id, "who": who, "kind": kind, "sev": sev, "title": t.props["action"], "at": t.at, "act": act,
                                         "waiting_on": t.props.get("waiting_on")})
            if s["flags"]["uncleared"]:
                st = compliance.state(self.g, deal)
                items.append(base | {"id": f"{deal}:clear", "who": roles.holder(self.g, "compliance"), "kind": "Clearance", "sev": "bad" if st["state"] == "blocked" else "warn", "at": s["changed"], "act": "open",
                                     "title": st["reason"] if st["state"] != "not cleared" else "Converted: clear this deal so its paperwork can go on"})
            risk = self.g.nodes[f"deal:{deal}"].props.get("risk") or {}
            owner = next((p for p, v in PEOPLE.items() if v.get("role") == "Owner"), None)
            if compliance.needs_senior(risk) and not risk.get("senior"):
                items.append(base | {"id": f"{deal}:senior", "who": owner, "kind": "Sign-off", "sev": "warn", "at": s["changed"], "act": "open", "title": "A high-risk deal needs your sign-off"})
            if deal_gates.applies(self.g, deal) and (gv := deal_gates.view(self.g, deal))["can_approve"]:
                items.append(base | {"id": f"{deal}:gate", "who": owner, "kind": "Transfer", "sev": "warn", "at": s["changed"], "act": "open", "title": "Every gate has passed: approve the transfer"})
            missing = [p["kind"] for p in compliance.source_of_funds(self.g, deal, by)["proof"] if not p["have"] and p["kind"] != "source of funds"]
            if missing:  # one row per deal, however many proofs: she marks each one in the deal
                items.append(base | {"id": f"{deal}:proof", "who": roles.holder(self.g, "compliance"), "kind": "Proof", "sev": "info", "at": s["changed"], "act": "open",
                                     "title": f"{len(missing)} proof{'s' if len(missing) > 1 else ''} missing: {', '.join(missing)}"})
        items.sort(key=lambda x: (SEV[x["sev"]], x["at"]))
        return items

    def overview(self) -> dict:
        sums = [self.summary(d.deal) for d in self.g.deals()]
        work = self.work()
        week = (self.today + timedelta(days=7)).isoformat()
        exp = [e for s in sums for e in s["expected"]]
        late = [e for e in exp if e["overdue"]]
        nxt = [e for e in exp if not e["overdue"] and e["due"] and e["due"] <= week]
        by_day = defaultdict(int)
        for e in exp:
            if e["due"]:
                by_day[e["due"]] += e["amount"] or 0
        days = [(self.today + timedelta(days=i)).isoformat() for i in range(-4, 14)]
        early = sum(v for k, v in by_day.items() if k < days[0])
        corrections = []
        for f in self.g.of("fact"):
            if f.props.get("replaces") and f.status == "live" and f.deal:
                corrections.append(self._ripple(f))
        corrections.sort(key=lambda c: c["at"], reverse=True)
        return {"deals": len(sums), "value": sum(s["value"] or 0 for s in sums),
                "waiting": {p: sum(1 for w in work if w["who"] == p) for p in sorted({w["who"] for w in work})},
                "work": len(work),
                "money": {"next7": sum(e["amount"] or 0 for e in nxt), "next7_n": len(nxt), "overdue": sum(e["amount"] or 0 for e in late),
                          "overdue_n": len({s["deal"] for s in sums if s["money"][0] == "bad"}),
                          "days": [{"day": d, "aed": by_day.get(d, 0) + (early if i == 0 else 0)} for i, d in enumerate(days)]},
                "comp": {k: sum(s["flags"][k] for s in sums) for k in ("unscreened", "proof", "cash", "checks", "match", "uncleared")},
                "paper": {"submit": sum(s["paper"][1] == "Form F to submit" for s in sums), "sentback": sum(s["paper"][1] == "Form F sent back" for s in sums),
                          "transfer": sum(s["paper"][1].startswith("Transfer ") and s["paper"][1] != "Transfer done" for s in sums)},
                "stages": [{"stage": st, "deals": sum(s["stage"] == st for s in sums), "waiting": sum(s["stage"] == st and bool(s["waiting"]) for s in sums),
                            "value": sum(s["value"] or 0 for s in sums if s["stage"] == st)} for st in stage_order(self.g) if any(s["stage"] == st for s in sums)],
                "after": {"closing": sum(s["phase"] == "closing" for s in sums), "closed30": sum(1 for s in sums if s["phase"] == "closed"),
                          "commission30": sum(n.props.get("commission_aed") or 0 for n in self.g.of("sale") if n.props.get("deal")),
                          "left": {k: sum(1 for s in sums if s["phase"] == "closing" and any(i["key"] == k and not i["done"] for i in operations.closing(self.g, s["deal"])["items"]))
                                   for k in ("figures", "invoice", "compliance", "docs")}},
                "corrections": corrections[:8], "corrections_week": sum(1 for c in corrections if c["at"][:10] >= (self.today - timedelta(days=7)).isoformat())}

    def _ripple(self, f: Node) -> dict:
        """What one correction set off, counted from the log by what each event says caused it."""
        g, evs = self.g, _office().log.list(deal=f.deal)
        made = next(e for e in evs if e["type"] == "fact.created" and e["content"]["id"] == f.id)
        causes = {made["id"]} | {e["id"] for e in evs if e["caused_by"] == made["id"] and e["type"] == "fact.superseded"}
        after = [e for e in evs if e["caused_by"] in causes]
        olds = [g.nodes[o] for o in f.props.get("replaces", []) if o in g.nodes]
        return {"deal": f.deal, "customer": g.nodes[f"deal:{f.deal}"].props.get("customer"), "fact": f.id, "quote": f.props["quote"],
                "old": [{"id": o.id, "quote": o.props["quote"]} for o in olds], "at": f.at,
                "compliance_first": bool(after) and after[0]["type"] == "check.raised",
                "withdrawn": sum(e["type"] == "task.withdrawn" for e in after), "approvals": sum(e["type"] == "decision.needed" for e in after),
                "sent_back": sum(e["type"] == "review.returned" for e in after)}


def _k(n: float) -> str:
    return f"{n / 1e6:.2f}".rstrip("0").rstrip(".") + "M" if n >= 1e6 else f"{round(n / 1000)}k" if n else "0"


FILTERS = {"uncleared": lambda s: s["flags"]["uncleared"], "closing": lambda s: s["phase"] == "closing", "closed": lambda s: s["phase"] == "closed", "waiting": lambda s: s["waiting"], "overdue": lambda s: s["money"][0] == "bad", "expected": lambda s: s["money"][0] == "warn",
           "unscreened": lambda s: s["flags"]["unscreened"], "proof": lambda s: s["flags"]["proof"], "cash": lambda s: s["flags"]["cash"],
           "checks": lambda s: s["flags"]["checks"], "match": lambda s: s["flags"]["match"],
           "submit": lambda s: s["paper"][1] == "Form F to submit", "sentback": lambda s: s["paper"][1] == "Form F sent back",
           "transfer": lambda s: s["paper"][1].startswith("Transfer ") and s["paper"][1] != "Transfer done", "corrected": lambda s: s["corrected"]}
SORTS = {"changed": lambda s: s["changed"], "value": lambda s: s["value"] or 0, "customer": lambda s: (s["customer"] or "").lower(),
         "stage": lambda s: s["stage"], "waiting": lambda s: len(s["waiting"])}


# ---------- HTTP ----------

@router.get("/api/desk/deals")
def deals(q: str = "", needs: bool = False, filter: str = "", person: str = "", stage: str = "", sort: str = "changed", desc: bool = True, page: int = 1):
    led = Ledger(_office().graph(), date.today())
    words = q.lower().split()
    rows = []
    for d in led.g.deals():
        s = led.summary(d.deal)
        hay = f"{d.deal} {s['property']} {s['customer']} {s['broker_name']}".lower()
        if words and not all(w in hay for w in words):
            continue
        if (s["phase"] == "closed") != (filter == "closed"):  # closed deals live in the archive, found with the Closed filter
            continue
        if (needs and not s["waiting"]) or (filter in FILTERS and not FILTERS[filter](s)) or (person and person not in s["waiting"]) \
                or (stage and s["stage"] != stage):
            continue
        rows.append(s | {"waiting_names": [name(w) for w in s["waiting"]]})
    order = stage_order(led.g)
    rows.sort(key=(lambda s: order.index(s["stage"]) if s["stage"] in order else -1) if sort == "stage" else SORTS.get(sort, SORTS["changed"]), reverse=desc)
    page = max(1, page)
    return {"total": len(rows), "all": len(led.g.deals()), "page": page, "pages": max(1, -(-len(rows) // PAGE)),
            "rows": rows[(page - 1) * PAGE: page * PAGE]}


@router.get("/api/desk/work")
def work(person: str = ""):
    items = Ledger(_office().graph(), date.today()).work()
    counts = defaultdict(int)
    for x in items:
        counts[x["who"]] += 1
    p = pid(person) or person
    return {"counts": dict(counts), "items": [x for x in items if not p or x["who"] == p]}


@router.get("/api/desk/overview")
def overview():
    return Ledger(_office().graph(), date.today()).overview()


@router.get("/api/desk/deals/{deal}")
def deal(deal: str, request: Request):
    try:
        g = _office().graph()
        p = desk_rules.path(g, deal)
        return deal_view(g, deal) | {"summary": Ledger(g, date.today()).summary(deal), "roles": roles.table(g),
                                     "path": {"id": p["id"], "name": p["name"], "chosen": bool(g.settings.get(f"deal:{deal}", {}).get("path")),
                                              "from_desk": bool(g.nodes[f"deal:{deal}"].props.get("kind"))},
                                     "commission": finance.commission(g, deal), "closing": operations.closing(g, deal),
                                     "terms": desk_rules.terms(g, deal), "developers": [x["name"] for x in desk_rules.rules(g)["developers"]],
                                     "schedule": dict(zip(("kind", "payee", "document"), finance.SCHEDULE[p["id"]])) if p["id"] in finance.SCHEDULE else None,
                                     "stages": desk_stages.view(g, deal), "agency": _agency_view(g, deal, _base(request)),
                                     "documents": _docs_view(g, deal, _base(request)), "compliance": _compliance_view(g, deal), "gates": deal_gates.view(g, deal),
                                     "party_types": desk_rules.PARTY_TYPES, "doc_kinds": documents.KINDS}
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
    w = roles.current(g, n)
    if pid(body.by) != w:
        raise HTTPException(403, f"Only {name(w)} can answer {card}.")
    c = _card(g, n)
    try:
        if c["can"] == "reapprove" and body.choice == "Re-approve on the new facts":
            return {"approval": review.reapprove(o, n, pid(body.by), body.action)}
        if c["can"] == "reapprove" and body.choice == "Cancel":
            review.cancel(o, n, pid(body.by))
            return {"ok": True}
        if n.type == "question" and body.choice == "Answered":
            if not body.note.strip():
                raise ValueError("Write the answer.")
            o.log.append("question.answered", actor=pid(body.by), deal=n.deal, content={"card": card, "answer": body.note.strip()})
            return {"ok": True}
        if c["can"] == "reviewed" and body.choice == "Reviewed":
            o.log.append("decision.made", actor=pid(body.by), deal=n.deal, content={"card": card, "answer": "Reviewed", "note": body.note})
            if n.props.get("payment"):  # a held payment: looked at, so its receipt goes
                finance.release_held(o, n, pid(body.by), date.today())
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


class Screen(BaseModel):
    by: str
    result: str
    note: str = ""


def _act(fn, *a):
    try:
        fn(*a)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except KeyError as e:
        raise HTTPException(404, f"There is no {e.args[0]} to do that to.") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"ok": True}


@router.post("/api/desk/tasks/{tid}/screen")
def screen(tid: str, body: Screen):
    return _act(compliance.record_screening, _office(), tid, pid(body.by), body.result, body.note)


class Filed(BaseModel):
    by: str
    reference: str = ""


@router.post("/api/desk/tasks/{tid}/filed")
def filed(tid: str, body: Filed):
    return _act(compliance.record_filing, _office(), tid, pid(body.by), body.reference)


class Proof(BaseModel):
    by: str
    kind: str
    title: str = ""


@router.post("/api/desk/deals/{deal}/proof")
async def proof(deal: str, by: str = Form(...), kind: str = Form(...), title: str = Form(""), file: UploadFile = File(...)):
    """The compliance officer has the proof in hand: the file is kept and filed with Records against the deal."""
    from diwan.providers import meta
    data = await file.read()
    body = Proof(by=by, kind=kind, title=title)
    o = _office()
    g = o.graph()
    if f"deal:{deal}" not in g.nodes:
        raise HTTPException(404, f"There is no deal {deal!r}.")
    try:
        roles.check(g, "compliance", pid(body.by))
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    need = next((p for p in compliance.source_of_funds(g, deal)["proof"] if p["kind"] == body.kind), None)
    if not need:
        raise HTTPException(400, f"{body.kind!r} is not asked for on this deal.")
    if need["have"]:
        raise HTTPException(409, f"Already received: {need['have']} {need['have_title']}.")
    if not data or not (data.startswith(b"%PDF") or data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG")):
        raise HTTPException(400, "Attach the proof as a PDF or a photo.")
    meta.MEDIA.mkdir(parents=True, exist_ok=True)
    path = meta.MEDIA / f"doc-proof-{deal}-{body.kind.replace(' ', '-')}{'.pdf' if data.startswith(b'%PDF') else '.jpg'}"
    path.write_bytes(data)
    customer = g.nodes[f"deal:{deal}"].props["customer"]
    return {"document": o.file_document(kind=body.kind, title=body.title.strip() or need["text"], date=date.today().isoformat(),
                                        by=pid(body.by), deal=deal, party=customer, text=f"/media/{path.name}")}


class Received(BaseModel):
    by: str
    reference: str = ""
    amount: float | str | None = None
    method: str = "transfer"
    on: str = ""
    payer: str = ""
    proof_amount: float | str | None = None
    confirm: bool = False


@router.post("/api/desk/tasks/{tid}/received")
def received(tid: str, body: Received):
    try:
        return finance.mark_received(_office(), tid, pid(body.by), body.reference, today=date.today(), amount=body.amount, method=body.method, on=body.on,
                                     payer=body.payer, proof_amount=body.proof_amount, confirm=body.confirm)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except KeyError:
        raise HTTPException(404, f"There is no payment {tid}.") from None
    except finance.ProofMismatch as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class Undo(BaseModel):
    by: str
    payment: str
    why: str = ""


@router.post("/api/desk/tasks/{tid}/undo")
def undo_received(tid: str, body: Undo):
    _call(finance.undo_received, _office(), tid, pid(body.by), body.payment, body.why)
    return {"ok": True}


@router.post("/api/desk/tasks/{tid}/release")
def release(tid: str, body: Run):
    try:
        return {"approval": finance.approve_release(_office(), tid, pid(body.by))}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except KeyError:
        raise HTTPException(404, f"There is no payment {tid}.") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


def _call(fn, *a, missing="task", **kw):
    try:
        return fn(*a, **kw)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except KeyError:
        raise HTTPException(404, f"There is no such {missing}.") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@router.post("/api/desk/deals/{deal}/formf")
def prepare_formf(deal: str, body: Run):
    """The Form F clerk makes the plan from live facts (the same clerk Nova hands "prepare Form F" to)."""
    o = _office()
    g = o.graph()
    if f"deal:{deal}" not in g.nodes:
        raise HTTPException(404, f"There is no deal {deal!r}.")
    if ready := [d for d in g.of("draft", deal) if d.props["kind"] == "Form F" and d.status != "sent_back"]:
        raise HTTPException(409, f"{ready[-1].id} is the current Form F plan.")
    tid = o.add_task(deal, "formf", "Prepare Form F from the live facts", by=pid(body.by) or body.by)
    return {"text": operations.formf_plan(o, deal, tid, f"desk-{tid}")}


class Submitted(BaseModel):
    by: str
    reference: str = ""


@router.post("/api/desk/tasks/{tid}/submitted")
def formf_submitted(tid: str, body: Submitted):
    _call(operations.submitted, _office(), tid, pid(body.by), body.reference)
    return {"ok": True}


class Tick(BaseModel):
    by: str
    note: str = ""


@router.post("/api/desk/tasks/{tid}/tick")
def tick(tid: str, body: Tick):
    _call(operations.tick, _office(), tid, pid(body.by), body.note)
    return {"ok": True}


# ---------- who holds each role (the owner assigns; nothing is wired to a name) ----------

@router.get("/api/desk/roles")
def get_roles():
    return roles.table(_office().graph())


class RoleIn(BaseModel):
    by: str
    role: str
    person: str


@router.post("/api/desk/roles")
def set_role(body: RoleIn):
    _call(roles.assign, _office(), body.role, pid(body.person) or body.person, missing="role", by=pid(body.by) or body.by)
    return roles.table(_office().graph())


# ---------- the owner's rules (cash limit, VAT, each path's steps, deposit, commission and closing) ----------

def _rules_view(g):
    last = next((e for e in reversed(_office().log.list()) if e["type"] == "setting.changed"
                 and e["content"].get("person") == "desk" and e["content"].get("key") == "rules"), None)
    return {"rules": desk_rules.rules(g), "defaults": desk_rules.DEFAULTS, "roles": desk_rules.ROLES, "payers": desk_rules.PAYERS,
            "changed_by": name(last["actor"]) if last else None, "changed_at": last["at"] if last else None}


@router.get("/api/desk/rules")
def get_rules():
    return _rules_view(_office().graph())


class RulesIn(BaseModel):
    by: str
    rules: dict


@router.post("/api/desk/rules")
def set_rules(body: RulesIn):
    _call(desk_rules.save, _office(), body.rules, missing="rule", by=pid(body.by) or body.by)
    return _rules_view(_office().graph())


# ---------- commission: draft the invoice, send it, collect it (Finance) ----------

@router.post("/api/desk/deals/{deal}/invoice")
def draft_invoice(deal: str, body: Run):
    if f"deal:{deal}" not in _office().graph().nodes:
        raise HTTPException(404, f"There is no deal {deal!r}.")
    return {"draft": _call(finance.draft_invoice, _office(), deal, pid(body.by), missing="deal")}


class InvoiceIn(BaseModel):
    by: str
    number: str = ""


@router.post("/api/desk/tasks/{tid}/invoiced")
def invoiced(tid: str, body: InvoiceIn):
    return {"task": _call(finance.invoice_sent, _office(), tid, pid(body.by), body.number)}


@router.post("/api/desk/tasks/{tid}/commission")
def commission_in(tid: str, body: Received):
    return {"document": _call(finance.commission_received, _office(), tid, pid(body.by), body.reference, today=date.today(), amount=body.amount)}


class Why(BaseModel):
    by: str
    why: str = ""


@router.post("/api/desk/tasks/{tid}/writeoff")
def write_off(tid: str, body: Why):
    _call(finance.write_off, _office(), tid, pid(body.by) or body.by, body.why)
    return {"ok": True}


# ---------- a rental or off-plan deal's path and paperwork ----------

class PathIn(BaseModel):
    by: str
    path: str


@router.post("/api/desk/deals/{deal}/path")
def set_path(deal: str, body: PathIn):
    _call(desk_rules.set_path, _office(), deal, body.path, missing="deal", by=pid(body.by) or body.by)
    return {"path": desk_rules.path_of(_office().graph(), deal)}


@router.post("/api/desk/deals/{deal}/paperwork")
def start_paperwork(deal: str, body: Run):
    if f"deal:{deal}" not in _office().graph().nodes:
        raise HTTPException(404, f"There is no deal {deal!r}.")
    return {"tasks": _call(operations.start_paperwork, _office(), deal, pid(body.by))}


# ---------- closing a deal, then Records ----------

@router.post("/api/desk/tasks/{tid}/confirm")
def confirm_figures(tid: str, body: Run):
    _call(operations.confirm_figures, _office(), tid, pid(body.by) or body.by)
    return {"ok": True}


@router.post("/api/desk/tasks/{tid}/docs")
def closing_docs(tid: str, body: Run):
    _call(operations.docs_filed, _office(), tid, pid(body.by))
    return {"ok": True}


@router.post("/api/desk/deals/{deal}/close")
def close_deal(deal: str, body: Run):
    if f"deal:{deal}" not in _office().graph().nodes:
        raise HTTPException(404, f"There is no deal {deal!r}.")
    return {"sale": _call(operations.close, _office(), deal, pid(body.by), missing="deal", today=date.today())}



# ---------- what the signed documents say, the payment schedule, the KPIs ----------

class TermsIn(BaseModel):
    by: str
    terms: dict


@router.post("/api/desk/deals/{deal}/terms")
def set_terms(deal: str, body: TermsIn):
    return {"terms": _call(desk_rules.set_terms, _office(), deal, body.terms, missing="deal", by=pid(body.by) or body.by)}


class ScheduleIn(BaseModel):
    by: str
    document: str = ""
    rows: list[dict] = []
    cheques: int | None = None


@router.post("/api/desk/deals/{deal}/schedule")
def set_schedule(deal: str, body: ScheduleIn):
    o = _office()
    if f"deal:{deal}" not in o.graph().nodes:
        raise HTTPException(404, f"There is no deal {deal!r}.")
    rows = _call(finance.cheques, o.graph(), deal, body.cheques) if body.cheques else body.rows
    return {"tasks": _call(finance.schedule, o, deal, rows, pid(body.by), document=body.document)}


@router.post("/api/desk/tasks/{tid}/notneeded")
def not_needed(tid: str, body: Tick):
    _call(operations.not_needed, _office(), tid, pid(body.by), body.note)
    return {"ok": True}


@router.post("/api/desk/tasks/{tid}/split")
def split_paid(tid: str, body: Received):
    _call(finance.split_paid, _office(), tid, pid(body.by), body.reference)
    return {"ok": True}


@router.post("/api/desk/tasks/{tid}/after")
def after_done(tid: str, body: Tick):
    _call(operations.after_done, _office(), tid, pid(body.by) or body.by, body.note)
    return {"ok": True}


@router.get("/api/desk/kpis")
def kpis():
    o = _office()
    return desk_kpis.kpis(o.graph(), o.log.list(), date.today())



# ---------- stages, and the agency forms at conversion ----------

def _base(request: Request | None = None) -> str:
    from diwan.config import env
    return (env("PUBLIC_BASE_URL") or (str(request.base_url) if request else "")).rstrip("/")


def _links(g: Graph, deal: str, did: str, base: str) -> list[dict]:
    return [{"signer": x["signer"], "name": x["name"], "status": signing.status(g, x, date.today()), "expires": x["expires"],
             "signed_at": x["signed"]["at"] if x["signed"] else None, "opened": x.get("opened"), "url": f"{base}/web/sign.html?t={x['token']}"}
            for x in signing.links(_office().log.list(deal=deal), did)]


def _agency_view(g: Graph, deal: str, base: str) -> dict:
    li = agency_forms.our_listing(g, deal)
    ask = next((t for t in g.of("task", deal) if t.props.get("step") == "sides" and t.status in OPEN), None)
    return {"asking": ask.id if ask else None, "our_listing": li.props["ref"] if li else None, "needed": agency_forms.needed(g, deal),
            "forms": [f | {"links": _links(g, deal, f["draft"], base)} for f in agency_forms.forms(g, deal)],
            "sides": desk_rules.SIDES, "terms": desk_rules.terms(g, deal),
            "formf": [{"draft": d.id, "version": d.props.get("version"), "links": _links(g, deal, d.id, base)}
                      for d in g.of("draft", deal) if d.props["kind"] == "Form F" and d.status != "sent_back"]}


class StageIn(BaseModel):
    by: str
    stage: str
    reason: str = ""


@router.post("/api/desk/deals/{deal}/stage")
def move_stage(deal: str, body: StageIn):
    _call(desk_stages.move, _office(), deal, body.stage, pid(body.by) or body.by, body.reason, missing="deal")
    return desk_stages.view(_office().graph(), deal)


class SidesIn(BaseModel):
    by: str
    sides: str
    other: dict = {}


@router.post("/api/desk/deals/{deal}/sides")
def set_sides(deal: str, body: SidesIn):
    return {"drafts": _call(agency_forms.set_sides, _office(), deal, pid(body.by) or body.by, body.sides, body.other, missing="deal")}


@router.get("/api/desk/forms/{did}.pdf")
def form_pdf(did: str):
    from fastapi.responses import Response
    g = _office().graph()
    data = _call(agency_forms.render, g, did, missing="form")
    form = agency_forms.form_of(g, did)
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="Form-{form}-{g.nodes[did].deal}-{did}.pdf"'})


@router.post("/api/desk/tasks/{tid}/signed")
async def form_signed(tid: str, by: str = Form(...), checked: str = Form(""), file: UploadFile = File(...)):
    from diwan.providers import meta
    if checked not in ("1", "true", "on", "yes"):
        raise HTTPException(400, "Tick that you checked every signature line on it.")
    data = await file.read()
    return {"document": _call(agency_forms.signed, _office(), tid, pid(by) or by, data, file.filename or "", media=meta.MEDIA, today=date.today())}


@router.post("/api/desk/forms/{did}/signed")
async def formf_paper(did: str, by: str = Form(...), checked: str = Form(""), file: UploadFile = File(...)):
    from diwan.providers import meta
    if checked not in ("1", "true", "on", "yes"):
        raise HTTPException(400, "Tick that you checked every signature line on it.")
    data = await file.read()
    return {"document": _call(agency_forms.formf_signed_copy, _office(), did, pid(by) or by, data, media=meta.MEDIA, today=date.today(), missing="form")}


class ConvertIn(BaseModel):
    by: str
    amount: float | str = ""
    property: dict | None = None


@router.post("/api/desk/deals/{deal}/convert")
def convert(deal: str, body: ConvertIn):
    return _call(desk_stages.convert, _office(), deal, pid(body.by) or body.by, body.amount, body.property, missing="deal")


class PropertyIn(BaseModel):
    by: str
    property: dict


@router.post("/api/desk/deals/{deal}/property")
def set_property(deal: str, body: PropertyIn):
    return _call(deal_property.save, _office(), deal, body.property, pid(body.by) or body.by, missing="deal")


@router.get("/api/desk/deals/{deal}/listings")
def deal_listings(deal: str, q: str = ""):
    g = _office().graph()
    if f"deal:{deal}" not in g.nodes:
        raise HTTPException(404, f"There is no deal {deal!r}.")
    return deal_property.search(g, deal, q)


@router.get("/api/desk/agencies")
def known_agencies():
    return deal_property.agencies(_office().graph())


class DiscountIn(BaseModel):
    by: str
    approve: bool
    note: str = ""


@router.post("/api/desk/tasks/{tid}/discount")
def decide_discount(tid: str, body: DiscountIn):
    _call(desk_stages.decide_discount, _office(), tid, pid(body.by) or body.by, body.approve, body.note)
    return {"ok": True}



# ---------- signing online: the links, and the public page they open ----------

@router.post("/api/desk/forms/{did}/links")
def make_links(did: str, body: Run, request: Request):
    _call(signing.make_links, _office(), did, pid(body.by) or body.by, missing="form", today=date.today())
    g = _office().graph()
    return {"links": _links(g, g.nodes[did].deal, did, _base(request))}


@router.get("/api/sign/{token}")
def sign_page(token: str):
    return _call(signing.page, _office(), token, missing="link", today=date.today())


@router.post("/api/sign/{token}")
async def sign(token: str, request: Request, full_name: str = Form(""), id_no: str = Form(""), consent: str = Form(""),
               drawn: str = Form(""), strokes: int = Form(0), image: UploadFile = File(...)):
    from diwan.providers import meta
    data = await image.read()
    return _call(signing.sign, _office(), token, full_name=full_name, id_no=id_no, consent=consent in ("1", "true", "on", "yes"), image=data,
                 ip=request.client.host if request.client else "", device=request.headers.get("user-agent", ""), media=meta.MEDIA,
                 today=date.today(), drawn=drawn == "1", strokes=strokes, missing="link")


@router.post("/api/desk/links/{token}/renew")
def renew_link(token: str, body: Run):
    _call(signing.renew, _office(), token, pid(body.by) or body.by, missing="link", today=date.today())
    return {"ok": True}


@router.post("/api/desk/docs/{token}/renew")
def renew_docs(token: str, body: Run):
    _call(documents.renew, _office(), token, pid(body.by) or body.by, missing="link", today=date.today())
    return {"ok": True}



# ---------- the documents a client sends ----------

def _docs_view(g: Graph, deal: str, base: str) -> dict:
    evs = _office().log.list(deal=deal)
    checks = {(t.props.get("token"), t.props.get("kind")): t.id for t in g.of("task", deal) if t.props.get("step") == "doc" and t.status in OPEN}
    reqs = [{"party": r["party"], "name": r["name"], "url": f"{base}/web/docs.html?t={r['token']}", "expires": r["expires"], "token": r["token"], "opened": r.get("opened"),
             "reminders": len(r["reminders"]), "phone": bool(r.get("phone")), "expired": r["expires"] < date.today().isoformat(),
             "docs": [{"kind": k, "label": documents.KINDS[k], "status": "confirmed" if k in r["confirmed"] else "to check" if k in r["got"] else "needed",
                       "fields": r["got"][k]["fields"] if k in r["got"] else None, "flags": r["got"][k]["flags"] if k in r["got"] else [],
                       "file": f"/media/{r['got'][k]['file']}" if k in r["got"] else None, "check": checks.get((r["token"], k)),
                       "turned": r["turned"][k]["reason"] if k in r["turned"] and k not in r["got"] else None} for k in r["kinds"]]}
            for r in documents.requests(evs, deal)]
    return {"requests": reqs, "profile": documents.profile(evs, deal)}


@router.get("/api/docs/{token}")
def docs_page(token: str):
    return _call(documents.page, _office(), token, missing="link", today=date.today())


@router.post("/api/docs/{token}")
async def docs_upload(token: str, kind: str = Form(...), fields: str = Form("{}"), file: UploadFile = File(...)):
    import json
    from diwan.providers import meta
    data = await file.read()
    try:
        f = json.loads(fields or "{}")
    except ValueError:
        f = {}
    return _call(documents.upload, _office(), token, kind, data, f if isinstance(f, dict) else {}, media=meta.MEDIA, today=date.today(), missing="link")


class DocCheck(BaseModel):
    by: str
    ok: bool
    note: str = ""


@router.post("/api/desk/tasks/{tid}/doc")
def doc_checked(tid: str, body: DocCheck):
    return {"document": _call(documents.confirm, _office(), tid, pid(body.by) or body.by, body.ok, body.note, today=date.today())}


@router.post("/api/desk/tasks/{tid}/docscall")
def docs_called(tid: str, body: Tick):
    _call(documents.call_done, _office(), tid, pid(body.by) or body.by, body.note)
    return {"ok": True}



# ---------- the tax invoice and receipts as PDFs ----------

def _pdf(data: bytes, filename: str):
    from fastapi.responses import Response
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/api/desk/invoices/{tid}.pdf")
def invoice_pdf(tid: str):
    g = _office().graph()
    data = _call(invoices.invoice_pdf, g, tid, missing="invoice")
    return _pdf(data, f"{g.nodes[tid].props.get('invoice') or 'invoice-draft'}.pdf")


@router.get("/api/desk/receipts/{tid}.pdf")
def receipt_pdf(tid: str):
    return _pdf(_call(invoices.receipt_pdf, _office().graph(), tid, missing="receipt"), f"RCT-{tid}.pdf")


# ---------- the four rooms: what each department works from ----------

class Note(BaseModel):
    by: str
    note: str = ""


@router.post("/api/desk/tasks/{tid}/hit")
def resolve_hit(tid: str, body: DocCheck):
    _call(compliance.resolve_hit, _office(), tid, pid(body.by) or body.by, not body.ok, body.note)
    return {"ok": True}


class Rate(BaseModel):
    by: str
    risk: str
    pep: bool = False
    note: str = ""


@router.post("/api/desk/deals/{deal}/compliance/rate")
def rate(deal: str, body: Rate):
    _call(compliance.rate, _office(), deal, pid(body.by) or body.by, body.risk, pep=body.pep, note=body.note, missing="deal")
    return {"ok": True}


@router.post("/api/desk/deals/{deal}/compliance/signoff")
def sign_off(deal: str, body: Run):
    _call(compliance.sign_off, _office(), deal, pid(body.by) or body.by, missing="deal")
    return {"ok": True}


@router.post("/api/desk/deals/{deal}/compliance/clear")
def clear(deal: str, body: Note):
    _call(compliance.clear, _office(), deal, pid(body.by) or body.by, body.note, missing="deal")
    return {"ok": True}


class NeedsInfo(BaseModel):
    by: str
    kinds: list[str] = []
    note: str = ""


@router.post("/api/desk/deals/{deal}/compliance/needs-info")
def needs_info(deal: str, body: NeedsInfo):
    return {"token": _call(compliance.needs_info, _office(), deal, pid(body.by) or body.by, body.kinds, body.note, missing="deal")}


@router.post("/api/desk/deals/{deal}/compliance/block")
def block(deal: str, body: Note):
    _call(compliance.block, _office(), deal, pid(body.by) or body.by, body.note, missing="deal")
    return {"ok": True}


@router.post("/api/desk/deals/{deal}/compliance/str")
def draft_str(deal: str, body: Note):
    return {"draft": _call(compliance.draft_str, _office(), deal, pid(body.by) or body.by, body.note, missing="deal")}


@router.post("/api/desk/deals/{deal}/transfer/approve")
def approve_transfer(deal: str, body: Run):
    return {"approval": _call(deal_gates.approve, _office(), deal, pid(body.by) or body.by, missing="deal")}


class Book(BaseModel):
    by: str
    when: str = ""
    place: str = ""


@router.post("/api/desk/tasks/{tid}/book")
def book(tid: str, body: Book):
    _call(operations.book_transfer, _office(), tid, pid(body.by) or body.by, body.when, body.place, today=date.today())
    return {"ok": True}


@router.post("/api/desk/tasks/{tid}/portal")
def portal_draft(tid: str, body: Run):
    return {"fields": _call(operations.portal_draft, _office(), tid, pid(body.by) or body.by)}


@router.post("/api/desk/tasks/{tid}/portal/submitted")
def portal_submitted(tid: str, body: Submitted):
    _call(operations.portal_submitted, _office(), tid, pid(body.by) or body.by, body.reference)
    return {"ok": True}


@router.get("/api/desk/rooms/compliance")
def room_compliance():
    return compliance.room(_office().graph(), date.today())


@router.get("/api/desk/rooms/finance")
def room_finance():
    return finance.room(_office().graph(), date.today())


@router.get("/api/desk/rooms/operations")
def room_operations():
    return operations.room(_office().graph(), date.today())


@router.get("/api/desk/board")
def board():
    """Every open deal by stage, in the order deals travel."""
    led = Ledger(_office().graph(), date.today())
    g, cols = led.g, {}
    for d in g.deals():
        s = led.summary(d.deal)
        if s["phase"] != "closed":
            cols.setdefault(s["stage"], []).append({k: s[k] for k in ("deal", "customer", "property", "value", "comp", "money")} | {"waiting": [name(w) for w in s["waiting"]]})
    order = desk_rules.SALES_STAGES + [x for p in desk_rules.rules(g)["paths"].values() for x in p["stages"]] + ["Lost"]
    seen = list(dict.fromkeys(x for x in order if x in cols)) + [x for x in cols if x not in order]
    return [{"stage": k, "deals": cols[k]} for k in seen]
