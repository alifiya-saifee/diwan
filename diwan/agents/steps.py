"""The Next-step taker (docs/meeting-tasks-spec.md): when a meeting ends, the work people agreed to at the table, each item
with an owner, a date and the words it came from. Nothing becomes a task until a person approves the list; an item whose
words are not in the meeting is dropped, an owner nobody named is never guessed, and a date the words don't give is left
empty. Muse Spark reads the meeting when connected; plain rules otherwise. The owner always comes from the team settings.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from diwan import roles, slots
from diwan.agents import runner
from diwan.agents.charters import get
from diwan.agents.lobby import DAYWORDS, due_from
from diwan.graph import OPEN, Graph
from diwan.office import Office
from diwan.pack import norm
from diwan.people import PEOPLE, name, pid

ROLE_WORDS = {"finance": "finance", "accounts": "finance", "compliance": "compliance", "transactions officer": "transactions",
              "transactions": "transactions", "operations": "transactions"}
WILL = r"(?:will|'ll|is going to|are going to|shall|needs? to|has to|should)"
NOBODY = r"someone|somebody|we|they|the office|the team"
SCHEMA = {"name": "steps", "schema": {"type": "object", "additionalProperties": False, "required": ["items"],
                                      "properties": {"items": {"type": "array", "items": {
                                          "type": "object", "additionalProperties": False, "required": ["action", "owner_words", "quote"],
                                          "properties": {"action": {"type": "string"}, "owner_words": {"type": ["string", "null"]},
                                                         "quote": {"type": "string"}}}}}}}
TASK = ("Each thing someone at this meeting agreed to do. action: what, as a short instruction. owner_words: the words naming who "
        "does it, exactly as said (\"Ahmed\", \"finance\", \"I\"), or null when nobody is named. quote: the sentence it came from, "
        "copied word for word from one turn; two items may share a sentence. A staff member's promise to send, book or do something "
        "is always an item. Leave out wishes, questions, anything the client took back, and the client's own words about who pays "
        "or how much (the payment tracker already follows those).")
MONEY = {"payer", "payment_promise", "deal_term", "income"}  # already facts with their own work: not tasks from the meeting


def _due(text: str, now: datetime) -> tuple[str | None, str]:
    """The date the words give, or none. "next week" is the Friday of next week; everything else is the Lobby's reader."""
    local = now.astimezone(slots.DUBAI)
    m = re.search(r"\s*\b(?:by|for|within|before)?\s*next week\b", text, re.I)
    if m:
        friday = local.date() - timedelta(days=local.weekday()) + timedelta(days=11)
        return friday.isoformat(), (text[:m.start()] + text[m.end():]).strip(" .,")
    due, rest = due_from(text, now)
    if not due:  # "tomorrow", "on Thursday": a day said without "by"
        due, rest = due_from(re.sub(rf"(?:\b(?:on|this)\s+)?\b(?=(?:{DAYWORDS})\b)", "by ", text, count=1, flags=re.I), now)
    return (due.date().isoformat() if due else None), (rest if due else text)


def _owner(g: Graph, words: str | None, speaker_role: str, broker: str) -> str | None:
    """Who the words name: a person, a role held in the team settings, or the speaker's "I". None when nobody is named."""
    w = (words or "").strip().lower()
    if not w or re.fullmatch(NOBODY, w):
        return None
    if w in ("i", "me", "myself"):
        return broker if speaker_role == "broker" else "customer"
    for word, role in ROLE_WORDS.items():
        if re.search(rf"\b{word}\b", w):
            return roles.holder(g, role)
    for k, p in PEOPLE.items():
        if w == k or w in (p["name"].lower(), p["name"].split()[0].lower()):
            return k
    return pid(w)


def _phrase(action: str, customer: str) -> str:
    a = re.sub(r"^(?:and|then|also)\s+", "", action.strip(" .,"), flags=re.I)
    a = re.sub(r"\b(you|him|her)\b", _first_name(customer), a, count=1, flags=re.I)
    return a[:1].upper() + a[1:]


def _first_name(full: str) -> str:
    return (full or "the client").split()[0]


def rules(turns: list[dict]) -> list[dict]:
    """Plain rules: "<name, role, I or someone> will <do something>" in any turn, one item per clause."""
    names = sorted({w for p in PEOPLE.values() for w in (p["name"].split()[0], p["name"])} | set(ROLE_WORDS), key=len, reverse=True)
    who = "|".join(re.escape(n) for n in names) + rf"|I|{NOBODY}"
    out = []
    for t in turns:
        for clause in re.split(r"(?<=[.!?])\s+|,\s*(?:and\s+)?(?=(?:" + who + r")\b)|\s+and\s+(?=(?:" + who + rf")\s+{WILL})", t["text"], flags=re.I):
            m = re.match(rf"\s*(?:actually,?\s*|ok(?:ay)?,?\s*|so,?\s*)?(?:the\s+)?({who})(?:\s+team)?\s*({WILL})\s+(.+)", clause, re.I)
            if m and not re.match(r"(?:not|never)\b", m.group(3), re.I):
                out.append({"action": m.group(3), "owner_words": m.group(1), "quote": clause.strip(), "turn": t["n"]})
    return out


def _turns(office: Office, mid: str) -> list[dict]:
    evs = [e for e in office.log.list() if e["type"] == "utterance" and e["content"].get("meeting") == mid]
    return [{"n": i, "label": e["content"].get("label"), "speaker": e["content"].get("speaker"), "text": e["content"]["text"], "event": e["id"]}
            for i, e in enumerate(evs)]


def propose(office: Office, mid: str, *, cause: int | None = None, now: datetime | None = None, tape_root=None) -> dict:
    """What the meeting agreed, for a person to approve. Logged once per meeting; asking again returns the same list."""
    if found := latest(office, mid):
        return found
    now = now or datetime.now(slots.DUBAI)
    g, m = office.graph(), office.meeting(mid)
    deal = m["deal"]
    d = g.nodes[f"deal:{deal}"].props
    broker, customer = d.get("broker"), d.get("customer", "")
    turns = _turns(office, mid)
    c, by = get("steps"), "rules"
    raw = None
    sources = {f"turn:{t['n']}": f"{t['speaker']} ({'broker' if t['label'] in ('broker', 'speaker_0') else 'client'}): {t['text']}" for t in turns}
    if turns:
        system, user = runner.instructions(c, office.log, pack=False), runner.user_message(TASK, sources)
        if runner.has_model(c, system, user, schema=SCHEMA, tape_root=tape_root):
            try:
                reply = runner.call(c, system, user, schema=SCHEMA, tape_root=tape_root, timeout=runner.LIVE)
                raw, by = reply.data["items"], reply.usage.get("provider") or "model"
            except Exception as e:  # noqa: BLE001  the list still comes, from the rules, and the failure is on the record
                office.log.append("agent.failed", actor=c.id, agent=c.id, deal=deal, caused_by=cause, content={"error": str(e)[:300]})
    found = rules(turns)
    if raw is None:
        raw = found
    else:  # a plain "<name> will …" the model left out is still a promise made at the table
        mine = lambda q, w: (norm(w or ""), norm(q))  # noqa: E731
        have = [mine(r["quote"], r.get("owner_words")) for r in raw]
        raw += [r for r in found if not any(o == norm(r["owner_words"]) and (norm(r["quote"]) in q or q in norm(r["quote"])) for o, q in have)]
    items, unclear, seen = [], [], set()
    for r in raw:
        turn = next((t for t in turns if norm(r["quote"]) and norm(r["quote"]) in norm(t["text"])), None)
        if not turn:
            continue  # words that weren't said at this meeting are never a task
        role = "broker" if turn["label"] in ("broker", "speaker_0") else "client"
        due, action = _due(r["action"], now)
        if not due:
            due = _due(r["quote"], now)[0]
        owner = _owner(g, r.get("owner_words"), role, broker)
        action = _phrase(action, customer)
        if owner == "customer":  # the client's own promise: the broker makes sure it happens
            owner, action = broker, f"Check {_first_name(customer)} does it: {action[:1].lower() + action[1:]}"
        made = [e["content"] for e in office.log.list(deal=deal) if e["type"] == "fact.created" and e["caused_by"] == turn["event"]]
        if role == "client" and any(f.get("kind") in MONEY for f in made):
            continue  # "I'll pay it all myself" is a fact the money work already follows
        facts = [f["id"] for f in made]
        if (norm(action), owner) in seen:
            continue
        seen.add((norm(action), owner))
        row = {"action": action, "owner": owner, "due": due, "quote": r["quote"].strip(), "speaker": name(turn["speaker"]), "turn": turn["n"], "facts": facts}
        (items if owner in PEOPLE else unclear).append(row)
    started = next(e["id"] for e in office.log.list(deal=deal) if e["type"] == "meeting.started" and e["content"]["meeting"] == mid)
    ended = next((e["id"] for e in office.log.list(deal=deal) if e["type"] == "meeting.ended" and e["content"]["meeting"] == mid), None)
    withdrawn = [{"id": e["content"]["id"], "action": g.nodes[e["content"]["id"]].props["action"], "because": e["content"].get("reason", "")}
                 for e in office.log.list(deal=deal) if e["type"] == "task.withdrawn" and e["id"] > started and (not ended or e["id"] < ended)
                 and e["content"].get("id") in g.nodes]
    ev = office.log.append("steps.proposed", actor=c.id, agent=c.id, deal=deal, caused_by=cause, key=f"steps:{mid}",
                           content={"meeting": mid, "items": items, "unclear": unclear, "withdrawn": withdrawn, "by": by,
                                    "text": f"{len(items)} task{'' if len(items) == 1 else 's'} listed from the meeting, waiting for approval"})
    return ev["content"] | {"deal": deal, "approved": None}


def latest(office: Office, mid: str) -> dict | None:
    """The proposed list for this meeting and, once approved, what was sent to whom."""
    out = None
    for e in office.log.list():
        c = e["content"]
        if c.get("meeting") != mid:
            continue
        if e["type"] == "steps.proposed":
            out = c | {"deal": e["deal"], "approved": None}
        elif e["type"] == "steps.approved" and out:
            out["approved"] = c
    return out


def approve(office: Office, mid: str, rows: list[dict], *, by: str) -> dict:
    """The list as the person left it (edited, trimmed, added to): one task per row, for its owner. Once per meeting."""
    found = latest(office, mid)
    if not found:
        raise KeyError(mid)
    if found["approved"]:
        return found["approved"] | {"duplicate": True}
    g, deal = office.graph(), found["deal"]
    made = []
    for r in rows:
        action, owner = (r.get("action") or "").strip(), pid(r.get("owner"))
        if not action:
            continue
        if owner not in PEOPLE:
            raise ValueError(f"Choose who does \"{action}\".")
        live = [f for f in r.get("facts") or [] if f in g.nodes and g.nodes[f].status == "live"]
        tid = office.add_task(deal, "steps", action, rests_on=live, needs_person=owner, by=by,
                              props={"due": r.get("due") or None, "quote": r.get("quote"), "speaker": r.get("speaker"), "meeting": mid,
                                     "added": not r.get("quote")})
        made.append({"id": tid, "owner": owner, "action": action})
    ev = office.log.append("steps.approved", actor=by, agent="steps", deal=deal, key=f"steps-approved:{mid}",
                           content={"meeting": mid, "tasks": made, "by": by,
                                    "text": "From the meeting: " + "; ".join(f"{name(t['owner']).split()[0]}: {t['action']}" for t in made)})
    return ev["content"]


def done(office: Office, tid: str, *, by: str, note: str = "") -> None:
    """The owner ticks their task from a meeting. The owner of the office may too."""
    g = office.graph()
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props["agent"] != "steps":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is already {t.status}.")
    if by != t.props.get("needs_person") and not roles.is_owner(by):
        raise PermissionError(f"Only {name(t.props.get('needs_person'))} ticks this.")
    office.log.append("task.done", actor=by, agent="steps", deal=t.deal, content={"id": tid, "reason": f"Done{': ' + note.strip() if note.strip() else ''}"})
