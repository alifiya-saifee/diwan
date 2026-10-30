"""The deal room's KPIs (the plan's list), each counted from the event log and the graph, never typed in, and each
with the deals behind it so someone can act on it today. A deal's "yes" is when its paperwork started (the first Form F
or paperwork step); its close is when Records recorded the sale. The targets are the owner's settings.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

from diwan import desk_rules
from diwan.agents import finance, operations
from diwan.graph import OPEN, Graph
from diwan.people import name


def _days(a: str, b: str) -> float:
    return (datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds() / 86400


def _med(xs: list[float]) -> float | None:
    return round(median(xs), 1) if xs else None


def kpis(g: Graph, events: list[dict], today: date) -> dict:
    r = desk_rules.rules(g)
    created, done, start, closed, lost = {}, {}, {}, {}, {}
    month = (today - timedelta(days=30)).isoformat()
    caught = defaultdict(int)
    for e in events:
        c, d = e["content"], e.get("deal")
        if e["type"] == "task.created":
            created[c["id"]] = e
            if d and c.get("agent") in ("formf", "transfer"):
                start.setdefault(d, e["at"])
        elif e["type"] == "task.done":
            done[c["id"]] = e
        elif e["type"] == "sale.closed" and d:
            closed[d] = e["at"]
        elif e["type"] == "stage.changed" and d:
            if c.get("stage") == "Lost":
                lost[d] = {"at": e["at"], "why": c.get("why") or "no reason given"}
            else:
                lost.pop(d, None)
        if e["at"][:10] >= month and e["type"] in ("review.returned", "decision.needed", "approval.refused", "task.withdrawn"):
            caught[e["type"]] += 1

    deals = {n.deal: n for n in g.of("deal")}
    who = lambda d: deals[d].props.get("customer") if d in deals else d  # noqa: E731
    row = lambda d, **kw: {"deal": d, "customer": who(d), **kw}  # noqa: E731

    # days from yes to closed, per path
    per = defaultdict(list)
    rows = []
    for d, at in closed.items():
        if d in start:
            n = _days(start[d], at)
            per[desk_rules.path_of(g, d)].append(n)
            rows.append(row(d, days=round(n, 1)))
    alldays = [x for v in per.values() for x in v]
    to_close = {"median": _med(alldays), "n": len(alldays), "target": r["close_days_target"],
                "paths": {p: {"median": _med(v), "n": len(v)} for p, v in per.items()}, "deals": sorted(rows, key=lambda x: -x["days"])}

    # stuck: started, not closed or lost, nothing done for the owner's number of days
    stuck = []
    for d, at in start.items():
        if d in closed or d in lost or d not in deals:
            continue
        last = max([done[t.id]["at"] for t in g.of("task", d) if t.id in done] + [at])
        idle = (today - datetime.fromisoformat(last).astimezone(finance.DUBAI).date()).days
        if idle >= r["stuck_days"]:
            step = next((t for t in g.of("task", d) if t.status in OPEN and t.props["agent"] in ("transfer", "formf", "ops")), None)
            stuck.append(row(d, days=idle, step=step.props["action"] if step else None,
                             waiting_on=(step.props.get("waiting_on") or name(step.props.get("needs_person"))) if step else None))
    stuck.sort(key=lambda x: -x["days"])

    # time per touchpoint: each paperwork step from started to done (steps marked not needed don't count)
    steps = defaultdict(list)
    waits = {}
    for t in g.of("task"):
        if t.props["agent"] == "transfer" and t.id in done and t.id in created and t.props.get("result") != "not needed":
            steps[t.props["action"]].append(_days(created[t.id]["at"], done[t.id]["at"]))
            waits[t.props["action"]] = t.props.get("waiting_on")
    touch = sorted(({"step": s, "median": _med(v), "n": len(v), "waiting_on": waits[s]} for s, v in steps.items()), key=lambda x: -(x["median"] or 0))

    # compliance clear before money: every screening opened before the first money received was done before it
    clean, dirty = 0, []
    for d in deals:
        got = sorted(done[t.id]["at"] for t in g.of("task", d) if t.props["agent"] == "pay" and t.props.get("result") == "received" and t.id in done)
        if not got:
            continue
        screens = [t for t in g.of("task", d) if t.props["agent"] == "screen" and t.id in created and created[t.id]["at"] <= got[0]]
        late = [t for t in screens if t.id not in done or done[t.id]["at"] > got[0] or t.props.get("result") == "possible match"]
        if screens and not late:
            clean += 1
        else:
            dirty.append(row(d, why=f"{late[0].props.get('person')} not cleared when money arrived" if late else "money arrived before anyone was screened"))
    comp = {"pct": round(clean * 100 / (clean + len(dirty))) if clean + len(dirty) else None, "n": clean + len(dirty), "deals": dirty}

    # fall-through: deals lost after their paperwork started, with the reason
    fell = [row(d, why=lost[d]["why"]) for d in start if d in lost]
    fall = {"pct": round(len(fell) * 100 / len(start)) if start else None, "n": len(start), "deals": fell}

    # money overdue, by what it is
    over = defaultdict(lambda: {"aed": 0, "deals": []})
    for t in g.of("task"):
        if t.props["agent"] == "pay" and t.status in OPEN and t.deal:
            e = finance.expected(g, t, today)
            if e.get("overdue"):
                k = over[e.get("kind") or "payment"]
                k["aed"] += e.get("amount_aed") or 0
                k["deals"].append(row(t.deal, aed=e.get("amount_aed"), due=e.get("due"), what=t.props["action"]))

    # commission billed vs collected, by who pays
    bill = defaultdict(lambda: {"billed": 0, "collected": 0, "days": []})
    unpaid = []
    for t in g.of("task"):
        if t.props["agent"] != "inv" or t.props.get("step") != "collect" or not t.deal:
            continue
        payer = t.props.get("payer") or finance.commission(g, t.deal)["payer"]
        b = bill[payer]
        b["billed"] += t.props.get("amount_aed") or 0
        if t.props.get("result") == "received" and t.id in created and t.id in done:
            b["collected"] += t.props.get("amount_aed") or 0
            b["days"].append(_days(created[t.id]["at"], done[t.id]["at"]))
        elif t.status in OPEN:
            unpaid.append(row(t.deal, aed=t.props.get("amount_aed"), payer=payer))
    billed = {"payers": {p: {"billed": v["billed"], "collected": v["collected"], "days": _med(v["days"])} for p, v in bill.items()},
              "billed": sum(v["billed"] for v in bill.values()), "collected": sum(v["collected"] for v in bill.values()), "deals": unpaid}

    # documents missing at closing
    missing = []
    for d in deals:
        cl = operations.closing(g, d)
        if cl and not cl["sale"] and not next(i for i in cl["items"] if i["key"] == "docs")["done"]:
            missing.append(row(d, what=next(i for i in cl["items"] if i["key"] == "docs")["text"]))

    return {"to_close": to_close, "stuck": {"days": r["stuck_days"], "deals": stuck}, "touchpoints": touch, "compliance": comp,
            "caught": {"sent_back": caught["review.returned"], "approvals": caught["decision.needed"], "refused": caught["approval.refused"],
                       "withdrawn": caught["task.withdrawn"]},
            "fall": fall, "overdue": {"aed": sum(v["aed"] for v in over.values()), "kinds": dict(over)}, "commission": billed,
            "docs_missing": missing}
