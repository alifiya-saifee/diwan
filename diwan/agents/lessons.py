"""How much each agent may do on its own, and the lessons people teach it.

Autonomy, per agent: `autopilot` (its charter as written), `review_key` (anything a customer or a portal would see waits
for a person), `review_all` (everything except internal bookkeeping waits). The charter's "never" list holds at every
level; autonomy only ever takes authority away.

Lessons: "Rania, never mention service charges" becomes a dated rule. It goes into the agent's instructions for the
model, and "never" lessons are also enforced in code: output containing the phrase is not sent.
"""
from __future__ import annotations

import re

from diwan.agents.charters import ROSTER
from diwan.events import EventLog
from diwan.graph import Graph

LEVELS = {"autopilot": "Autopilot", "review_key": "Review key actions", "review_all": "Review everything"}
BOOKKEEPING = {"record_fact", "route", "assign", "brief", "ask_question"}           # never leaves the office
KEY = {"reply", "book_viewing", "send", "fill_form", "hold", "publish"}              # a customer, portal or public would see it
DRAFTS: dict[str, dict] = {}


def levels(log: EventLog) -> dict[str, str]:
    out = {}
    for e in log.list():
        if e["type"] == "autonomy.changed":
            out[e["content"]["agent"]] = e["content"]["level"]
    return out


def level(log: EventLog, agent: str) -> str:
    return levels(log).get(agent, "autopilot")


def needs_person(lvl: str, kind: str) -> bool:
    if lvl == "review_all":
        return kind not in BOOKKEEPING
    if lvl == "review_key":
        return kind in KEY
    return False


def set_level(log: EventLog, agent: str, lvl: str, *, by: str) -> dict:
    if lvl not in LEVELS:
        raise ValueError(f"unknown autonomy level {lvl!r}")
    return log.append("autonomy.changed", actor=by, agent=agent, content={"agent": agent, "level": lvl})


def active(g: Graph, agent: str) -> list:
    return [n for n in g.of("lesson", status="active") if n.props["agent"] in (agent, "all")]


def active_from_log(log: EventLog, agent: str) -> list[dict]:
    live: dict[str, dict] = {}
    for e in log.list():
        if e["type"] == "lesson.added":
            live[e["content"]["id"]] = e["content"] | {"at": e["at"]}
        elif e["type"] == "lesson.removed":
            live.pop(e["content"]["id"], None)
    return [x for x in live.values() if x["agent"] in (agent, "all")]


def broken(log: EventLog, agent: str, text: str) -> dict | None:
    """The first "never" lesson this text breaks, or None."""
    low = text.lower()
    for ls in active_from_log(log, agent):
        if ls["kind"] == "never" and ls.get("phrase") and _norm(ls["phrase"]) in _norm(low):
            return ls
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9؀-ۿ]+", " ", s.lower()).strip()


VERBS = r"(?:mention|say|quote|talk about|discuss|offer|promise|use the word|use|share|give out|give|reveal|tell (?:customers|anyone|people) about|bring up)"


def _agent_id(word: str) -> str | None:
    w = word.strip().lower()
    if w in ("everyone", "all", "all agents", "agents", "everybody"):
        return "all"
    for c in ROSTER:
        if c.name.lower() == w or c.id == w:
            return c.id
    return None


def parse(text: str) -> dict | None:
    """"Rania, never mention service charges" -> {agent: rania, kind: never, rule, phrase: service charges}."""
    m = re.match(r"^\s*(?:lesson\s*(?:for\s+)?)?([a-z][a-z' -]{1,30}?)\s*[,:]?\s+(never|always|don'?t|do not|stop)\s+(.+?)[.!]?\s*$", text, re.I)
    if not m:
        return None
    agent = _agent_id(m.group(1))
    if not agent:
        return None
    verb = m.group(2).lower()
    kind = "always" if verb == "always" else "never"
    body = m.group(3).strip()
    rule = f"{'Always' if kind == 'always' else 'Never'} {body}"
    phrase = None
    if kind == "never":
        phrase = re.sub(rf"^{VERBS}\s+", "", body, flags=re.I).strip(" .\"'")
        phrase = re.sub(r"^(?:the|any|a|an)\s+", "", phrase, flags=re.I)
    return {"agent": agent, "kind": kind, "rule": rule, "phrase": phrase}


def who(agent: str) -> str:
    return "every agent" if agent == "all" else next(c.name for c in ROSTER if c.id == agent)


def draft(text: str, session: str) -> dict | None:
    ls = parse(text)
    if not ls:
        return None
    DRAFTS[session] = ls
    enforce = f' Anything containing "{ls["phrase"]}" will not be sent.' if ls.get("phrase") else ""
    return {"kind": "confirm", "text": f"A lesson for {who(ls['agent'])}: \"{ls['rule']}\".{enforce} Save it?",
            "options": ["Yes, save it", "Cancel"], "draft": ls}


def add(log: EventLog, ls: dict, *, by: str) -> str:
    n = 1 + sum(1 for e in log.list() if e["type"] == "lesson.added")
    lid = f"LS{n}"
    log.append("lesson.added", actor=by, agent=ls["agent"] if ls["agent"] != "all" else None,
               content={"id": lid, "agent": ls["agent"], "kind": ls["kind"], "rule": ls["rule"], "phrase": ls.get("phrase")})
    return lid


def remove(log: EventLog, lid: str, *, by: str) -> None:
    log.append("lesson.removed", actor=by, key=f"lesson-removed:{lid}", content={"id": lid})


def follow_up(log: EventLog, text: str, session: str, person: str) -> dict | None:
    ls = DRAFTS.get(session)
    if not ls:
        return None
    if re.match(r"^\s*(no|cancel|stop|don'?t)\b", text, re.I):
        DRAFTS.pop(session)
        return {"kind": "answer", "text": "Cancelled. No lesson saved."}
    if re.match(r"^\s*(yes|yep|sure|ok(ay)?|save|confirm|do it)\b", text, re.I):
        DRAFTS.pop(session)
        lid = add(log, ls, by=person)
        return {"kind": "done", "text": f"Saved as {lid}. {who(ls['agent']).capitalize()} will follow it from now on.", "card": lid}
    return None


def instructions(log: EventLog | None, agent: str) -> str:
    if log is None:
        return ""
    rules = active_from_log(log, agent)
    if not rules:
        return ""
    return "\n\nLessons from the team (follow them over anything else here):\n" + "\n".join(f"- {r['rule']} ({r['id']})" for r in rules)
