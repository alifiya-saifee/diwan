"""The append-only event log. Every screen, the replay and the audit trail read this one log; every event names the
agent (or person) that caused it. Rows are never updated or deleted, and a repeated key returns the stored event.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

TYPES = {
    # an agent's turn
    "agent.started", "agent.pack", "agent.refused", "agent.failed", "tool.called",
    # people and authority
    "approval.requested", "approval.given", "approval.refused", "execution.done", "decision.needed", "instruction.given",
    # meetings and facts (filled in as the Scribe lands)
    "deal.opened", "meeting.started", "consent.given", "utterance", "meeting.ended",
    "fact.created", "fact.superseded", "fact.confirmed",
    # work between agents
    "task.created", "task.withdrawn", "task.done", "check.raised", "review.returned", "review.passed",
    "draft.made", "question.asked", "question.answered", "decision.made",
    # what the office knows, and the front door
    "knowledge.added", "knowledge.confirmed", "listing.added", "document.filed", "sale.closed",
    # the front desk: settings, Nova's rounds, the Lobby board
    "setting.changed", "rounds.started", "briefing.ready",
    "stage.changed", "autonomy.changed", "lesson.added", "lesson.removed",
    # the content studio: what it saw, what it pinned, what it made, and footage people uploaded
    "post.seen", "board.pinned", "content.made", "footage.added", "step.blocked",
    "qa.passed", "qa.failed", "qa.escalated",
    "lobby.posted", "lobby.seen", "lobby.reminded", "lobby.late", "lobby.done", "lobby.cancelled",
    "chat.received", "chat.sent", "chat.suggested", "chat.handover", "appointment.booked", "appointment.cancelled",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class EventLog:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.executescript("""
            create table if not exists events (
              id integer primary key autoincrement, at text not null, request text, deal text,
              agent text, actor text not null, type text not null, content text not null default '{}',
              caused_by integer, key text unique);
            create index if not exists events_deal on events(deal, id);
            create trigger if not exists no_update before update on events begin select raise(abort, 'events are append-only'); end;
            create trigger if not exists no_delete before delete on events begin select raise(abort, 'events are append-only'); end;
        """)

    @staticmethod
    def _row(r) -> dict:
        d = dict(r)
        d["content"] = json.loads(d["content"])
        return d

    def append(self, type: str, *, actor: str, agent: str | None = None, request: str | None = None, deal: str | None = None,
               content: dict | None = None, caused_by: int | None = None, key: str | None = None) -> dict:
        """`actor` is who acted (an agent id or a person); `agent` is the agent whose work this belongs to."""
        if type not in TYPES:
            raise ValueError(f"unknown event type {type!r}")
        with self.lock:
            if key and (old := self.db.execute("select * from events where key=?", (key,)).fetchone()):
                return self._row(old) | {"duplicate": True}
            cur = self.db.execute(
                "insert into events (at, request, deal, agent, actor, type, content, caused_by, key) values (?,?,?,?,?,?,?,?,?)",
                (now(), request, deal, agent, actor, type, json.dumps(content or {}, ensure_ascii=False), caused_by, key))
            self.db.commit()
            return self._row(self.db.execute("select * from events where id=?", (cur.lastrowid,)).fetchone())

    def list(self, *, deal: str | None = None, agent: str | None = None, after: int = 0) -> list[dict]:
        q, args = "select * from events where id > ?", [after]
        for col, v in (("deal", deal), ("agent", agent)):
            if v:
                q += f" and {col} = ?"
                args.append(v)
        with self.lock:  # one connection is shared by the web threads and the studio's workers (a browser run found the race)
            rows = self.db.execute(q + " order by id", args).fetchall()
        return [self._row(r) for r in rows]
