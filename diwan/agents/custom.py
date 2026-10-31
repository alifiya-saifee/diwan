"""Agents the owner adds from the Memory screen, without code.

A custom agent listens for one kind of event (a lead qualifies, a customer takes something back...), writes what its
job asks for with the model, and hands the result to a person as a task. It never acts by itself: it cannot message a
customer, change a fact, approve or move money, so adding one can never bypass the office's safety rules. Without a
model it still hands the person the task, with the record that triggered it.

The built-in agents are code with duties the office depends on (screening, the fact check), so they are not removed or
paused here; their autonomy is set on the Team page. A custom agent can be paused, resumed and removed; every change
is an event, so its history stays.
"""
from __future__ import annotations

import re

from diwan.agents.charters import BY_ID, Charter
from diwan.office import Office
from diwan.people import PEOPLE

TRIGGERS = {  # the event it listens for: what the owner reads on the screen
    "chat.received": "A customer writes on WhatsApp",
    "qualify.passed": "A lead qualifies",
    "qualify.not_fit": "A lead is not a fit",
    "fact.created": "The Scribe records something a customer said",
    "fact.superseded": "A customer takes back or changes something they said",
    "appointment.booked": "A viewing is booked",
    "stage.changed": "A deal moves to another stage",
    "deal.opened": "A new deal opens",
    "check.raised": "Compliance raises a check",
    "listings.synced": "The portal feed is read",
}
TEAMS = ("sales", "comp", "fin", "ops", "review", "records", "mkt")
SCHEMA = {"name": "custom_agent", "schema": {"type": "object", "additionalProperties": False, "required": ["task"],
                                             "properties": {"task": {"type": "string"}}}}
PER_RUN = 20  # at most this many triggers handled in one pass, so a burst can't run up the bill


def owners() -> set[str]:
    return {p for p, v in PEOPLE.items() if v["role"] == "Owner"}


def charter(a: dict) -> Charter:
    """A custom agent as a charter, so the runner builds its instructions like any other agent's."""
    return Charter(a["id"], a["name"], a.get("role") or "Custom agent", a["team"], None, "spark", a["job"],
                   TRIGGERS.get(a["trigger"], a["trigger"]), "The record that triggered it and its deal's records only",
                   f"A task for {PEOPLE.get(a['to'], {}).get('name', a['to'])}", TRIGGERS.get(a["trigger"], a["trigger"]),
                   PEOPLE.get(a["to"], {}).get("name", a["to"]), "Says what is missing in the task", (), ("assign",),
                   "Message a customer, change a fact, approve anything, move money", status="custom")


def add(office: Office, spec: dict, *, by: str) -> dict:
    if by not in owners():
        raise PermissionError("Only the owner adds agents")
    name, job = (spec.get("name") or "").strip(), (spec.get("job") or "").strip()
    errs = [m for ok, m in ((name, "Give it a name"), (len(job) >= 10, "Say what its job is, in a sentence"),
                            (spec.get("trigger") in TRIGGERS, "Pick what it listens for"), (spec.get("team") in TEAMS, "Pick its team"),
                            (spec.get("to") in PEOPLE, "Pick the person it hands its work to")) if not ok]
    if errs:
        raise ValueError("; ".join(errs))
    g = office.graph()
    aid = "x-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "agent")
    if aid in BY_ID or aid in g.custom_agents:
        raise ValueError(f"An agent called {name} exists")
    office.log.append("agent.added", actor=by, content={"id": aid, "name": name[:60], "role": (spec.get("role") or "").strip()[:60],
                                                         "job": job[:500], "trigger": spec["trigger"], "team": spec["team"], "to": spec["to"],
                                                         "from_event": g.last_event})
    return office.graph().custom_agents[aid]


def change(office: Office, aid: str, what: str, *, by: str) -> dict:
    """pause, resume or remove one of the owner's agents."""
    if by not in owners():
        raise PermissionError("Only the owner changes agents")
    g = office.graph()
    if aid in BY_ID:
        raise ValueError("Built-in agents are part of the office's code and its safety rules: set their autonomy on the Team page")
    if aid not in g.custom_agents or g.custom_agents[aid]["status"] == "removed":
        raise KeyError(aid)
    if what not in ("pause", "resume", "remove"):
        raise ValueError(what)
    office.log.append({"pause": "agent.paused", "resume": "agent.resumed", "remove": "agent.removed"}[what], actor=by, content={"id": aid})
    return office.graph().custom_agents[aid]


def run_pending(office: Office) -> int:
    """Hand every new trigger to the agents listening for it. Returns how many tasks were made."""
    from diwan.agents import runner
    g = office.graph()
    live = [a for a in g.custom_agents.values() if a["status"] == "active"]
    if not live:
        return 0
    start = min(a["done_upto"] for a in live)
    made = 0
    for e in office.log.list(after=start):
        for a in live:
            if made >= PER_RUN:
                return made
            if e["id"] <= a["done_upto"] or e["type"] != a["trigger"] or e.get("agent") == a["id"]:
                continue
            c = charter(a)
            what = _what(g, e)
            text = f"{a['name']}: {TRIGGERS[a['trigger']].lower()}. {what}"
            system = runner.instructions(c, office.log, pack=False) + (
                "\n\nWrite the task for the person in two to four plain sentences: what happened, and what your job says "
                "they should do. Use only the record below; if something is missing, say so.")
            user = runner.user_message("Write the task.", {f"event:{e['id']}": what})
            try:
                if runner.has_model(c, system, user, schema=SCHEMA):
                    text = f"{a['name']}: {runner.call(c, system, user, schema=SCHEMA, timeout=runner.BACKGROUND).data['task'][:600]}"
            except Exception as err:  # the person still gets the task, with the record
                office.log.append("agent.failed", actor=a["id"], agent=a["id"], deal=e.get("deal"), caused_by=e["id"],
                                  content={"error": str(err)[:300]})
            office.log.append("task.created", actor=a["id"], agent=a["id"], deal=e.get("deal"), caused_by=e["id"],
                              content={"id": office._next(office.graph(), "task", "T"), "agent": a["id"], "agent_name": a["name"],
                                       "team": a["team"], "action": text, "rests_on": [], "needs_person": a["to"], "by": a["id"],
                                       "custom": True, "trigger_event": e["id"]})
            made += 1
    return made


def _what(g, e: dict) -> str:
    """The trigger in words, from its record when it has one."""
    c = e["content"]
    for key in ("id", "chat"):
        nid = c.get(key) if key == "id" else f"chat:{c.get('chat')}"
        if nid and nid in g.nodes:
            return g.record(nid)[:400]
    if e.get("deal") and f"deal:{e['deal']}" in g.nodes:
        d = g.nodes[f"deal:{e['deal']}"]
        extra = c.get("text") or c.get("reason") or c.get("stage") or ""
        return f"Deal {d.label} ({d.props.get('customer', '')}). {extra}".strip()[:400]
    return ", ".join(f"{k}: {v}" for k, v in c.items() if isinstance(v, (str, int, float)))[:400]


# ---------- the agents map (Memory screen) ----------

def _dept(cid: str, agents: dict) -> str:
    seen = set()
    while cid in agents and cid not in seen:
        seen.add(cid)
        a = agents[cid]
        if a["level"] in ("lead", "chief") or not a["parent"]:
            return cid
        cid = a["parent"]
    return cid


def connections(office: Office, upto: int | None = None) -> dict:
    """Every agent, who it reports to, and the handoffs the log shows: event A by one agent caused event B by
    another (or a customer's message started an agent's work, or an agent's work waits for a person)."""
    from dataclasses import asdict

    from diwan.agents.charters import ROSTER
    events = office.log.list()
    if upto:
        events = [e for e in events if e["id"] <= upto]
    g = office.graph(upto)
    agents = {c.id: asdict(c) | {"custom": False} for c in ROSTER}
    for a in g.custom_agents.values():
        agents[a["id"]] = asdict(charter(a)) | {"custom": True, "status": a["status"], "trigger_event": a["trigger"],
                                                 "to": a["to"], "runs": a["runs"]}
    by_id = {e["id"]: e for e in events}
    acts, hands = {}, {}
    def who(e):
        if e.get("agent") in agents:
            return e["agent"]
        a = str(e.get("actor") or "")
        return "customer" if a.startswith("customer:") else f"person:{a}" if a in PEOPLE else None
    for e in events:
        if e.get("agent") in agents:
            acts[e["agent"]] = acts.get(e["agent"], 0) + 1
        dst = who(e)
        src = who(by_id[e["caused_by"]]) if e.get("caused_by") in by_id else None
        if dst in agents and src and src != dst:
            hands.setdefault((src, dst), {}).setdefault(e["type"], 0)
            hands[(src, dst)][e["type"]] += 1
        person = (e["content"] or {}).get("needs_person") or (e["content"] or {}).get("who") if e["type"] in ("task.created", "decision.needed", "attention.raised") else None
        if e.get("agent") in agents and person in PEOPLE:
            hands.setdefault((e["agent"], f"person:{person}"), {}).setdefault(e["type"], 0)
            hands[(e["agent"], f"person:{person}")][e["type"]] += 1
    nodes = []
    for cid, a in agents.items():
        n = acts.get(cid, 0)
        status = a["status"] if a["custom"] else ("working" if n else "planned" if a["status"] in ("planned", "parked") else "idle")
        rec = (f"{a['name']} · {a['role']}{' · added by the owner' if a['custom'] else ''}. Job: {a['job']} Listens for: {a['trigger']}. "
               f"Produces: {a['out']}. Never: {a['never']}. {n} actions in the log so far.")
        nodes.append({"id": f"agent:{cid}", "type": "agent", "label": a["name"], "status": status, "record": rec, "deal": None,
                      "props": a | {"dept": _dept(cid, agents), "actions": n}})
    used = {x for pair in hands for x in pair}
    if "customer" in used:
        nodes.append({"id": "agent:customer", "type": "person", "label": "Customers", "status": "live", "deal": None, "props": {},
                      "record": "Customers: their messages and words start most of the office's work."})
    for p in sorted(x for x in used if x.startswith("person:")):
        pid_ = p.split(":", 1)[1]
        nodes.append({"id": f"agent:{p}", "type": "person", "label": PEOPLE[pid_]["name"], "status": "live", "deal": None, "props": {},
                      "record": f"{PEOPLE[pid_]['name']} · {PEOPLE[pid_]['role']}: agents hand them what needs a person."})
    edges = [{"src": f"agent:{cid}", "rel": "reports_to", "dst": f"agent:{a['parent']}", "via": None}
             for cid, a in agents.items() if a["parent"] in agents]
    edges += [{"src": f"agent:{s}", "rel": "hands_to", "dst": f"agent:{d}", "via": None, "count": sum(t.values()), "types": t}
              for (s, d), t in hands.items()]
    return {"last_event": events[-1]["id"] if events else 0, "nodes": nodes, "edges": edges,
            "triggers": TRIGGERS, "teams": {t: agents[t]["name"] for t in TEAMS}, "owners": sorted(owners())}


# ---------- the office flow: departments, what passes between them, and their agents (Memory → Agents) ----------

DEPARTMENTS = [  # id, name, what it does for the office, column on the screen (Nova spans the top)
    ("nova", "Nova · chief of staff", "Briefs every person each morning, answers questions from the records, and routes instructions to the right team.", 0),
    ("customers", "Customers", "Write on WhatsApp, comment on posts, enquire on the portals, meet a broker.", 1),
    ("mkt", "Marketing studio", "Finds what works, plans the week, writes scripts in the brand's voice, films, edits and publishes posts that bring enquiries.", 2),
    ("sales", "Front desk & Sales", "Rania answers day and night; the Scribe keeps every customer's exact words as facts; leads are qualified, assigned to a broker and booked; the deal deck is built.", 3),
    ("comp", "Compliance", "Hears every payer or money change first; screens every party; checks source of funds; drafts reports for the officer.", 4),
    ("fin", "Finance", "Knows what money is expected, received and owed, each resting on the customer's current words. Releasing money needs a person.", 4),
    ("review", "Review", "Checks every draft against what is true now; sends back anything resting on a replaced statement, with both quotes.", 4),
    ("ops", "Operations", "Turns agreed terms into Form F and the transfer checklist, from live facts, stopping before Submit.", 4),
    ("records", "Records", "Files every document against its deal and answers numbers (sales, commission, pipeline) from records only.", 5),
    ("people", "People in control", "Approve, decide and call: the owner, brokers, the compliance officer, finance.", 5),
]
FLOWS = [  # n, from, to, what passes, built yet
    (1, "customers", "sales", "A customer's message or meeting: Rania answers, the Scribe keeps their exact words as facts", True),
    (2, "mkt", "sales", "A comment or DM on a published post opens a lead tagged with the post and its angle", False),
    (3, "sales", "mkt", "Leads and viewings per post and angle, so the strategy ranks what brings enquiries", False),
    (4, "sales", "comp", "Payer, party and money facts reach Compliance first: screening, source of funds, checks", True),
    (5, "sales", "fin", "A payment promise becomes an expected payment, resting on the customer's words", True),
    (6, "sales", "review", "Every deck and draft is checked against the customer's live words", True),
    (7, "review", "sales", "Work resting on a replaced statement is sent back, naming the old and new quote", True),
    (8, "sales", "ops", "Terms agreed: Form F and the transfer checklist start from the live facts", False),
    (9, "sales", "people", "A qualified lead goes to its broker with a call card; anything Rania can't answer goes to a person", True),
    (10, "comp", "people", "Checks and reports wait for the compliance officer", True),
    (11, "review", "people", "An approval resting on a replaced statement becomes a decision for the person who gave it", True),
    (14, "fin", "people", "Expected payments are marked received by a person; releasing money always needs a person", True),
    (12, "ops", "records", "A closed sale and its documents go to the archive and ledger", False),
    (13, "records", "nova", "Numbers come from records, citing the sale ids, never estimated", True),
]
def office_flow(office: Office, upto: int | None = None) -> dict:
    """Departments with their agents, and the numbered flows between departments, each counted from the log."""
    m = connections(office, upto)
    agents = {n["id"].split(":", 1)[1]: n for n in m["nodes"] if n["type"] == "agent"}
    dept_of = {aid: n["props"]["dept"] for aid, n in agents.items()}
    dept_of["customer"] = "customers"

    def dept(node_id: str) -> str | None:
        x = node_id.split(":", 1)[1]
        return "people" if x.startswith("person:") else dept_of.get(x)
    seen = {}
    for e in m["edges"]:
        if e["rel"] != "hands_to":
            continue
        a, b = dept(e["src"]), dept(e["dst"])
        if a and b and a != b:
            seen[(a, b)] = seen.get((a, b), 0) + e["count"]
    # a draft sent back flows from Review to the team whose draft it was
    ev = [e for e in office.log.list() if not upto or e["id"] <= upto]
    seen[("review", "sales")] = sum(e["type"] == "review.returned" for e in ev)
    # numbers Nova delegates to Records
    seen[("records", "nova")] = seen.get(("records", "nova"), 0) + sum(e["type"] == "agent.pack" and e.get("agent") in ("records", "analyst") for e in ev)
    flows = [{"n": n, "from": a, "to": b, "what": w, "built": built or seen.get((a, b), 0) > 0, "count": seen.get((a, b), 0)}
             for n, a, b, w, built in FLOWS]
    known = {(f["from"], f["to"]) for f in flows}
    extra = [{"n": None, "from": a, "to": b, "what": "seen in the log", "built": True, "count": c}
             for (a, b), c in seen.items() if (a, b) not in known and c and a in dict((d[0], 1) for d in DEPARTMENTS) and b in dict((d[0], 1) for d in DEPARTMENTS)]
    rooms = {a: n for a, n in agents.items() if n["props"].get("level") == "room"}
    depts = []
    for did, name, what, col in DEPARTMENTS:
        members = [n for aid, n in agents.items() if n["props"]["dept"] == did and aid != did and aid not in rooms]
        lead = agents.get(did)
        depts.append({"id": did, "name": name, "what": what, "col": col, "lead": lead,
                      "agents": [n | {"room": rooms[n["props"]["parent"]]["label"] if n["props"].get("parent") in rooms else None} for n in members],
                      "rooms": [n for n in rooms.values() if n["props"]["dept"] == did],
                      "people": [{"id": p, "name": v["name"], "role": v["role"]} for p, v in PEOPLE.items()] if did == "people" else []})
    return {"last_event": m["last_event"], "departments": depts, "flows": flows + extra, "triggers": m["triggers"], "teams": m["teams"],
            "owners": m["owners"], "agents": agents}
