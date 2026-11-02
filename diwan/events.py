"""The append-only event log. Every screen, the replay and the audit trail read this one log; every event names the
agent (or person) that caused it. Rows are never updated or deleted, and a repeated key returns the stored event.
"""
from __future__ import annotations

import json
import sqlite3
from bisect import bisect_right
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
    "knowledge.added", "knowledge.confirmed", "listing.added",
    # changing an item (knowledge or a listing): new versions, retire and restore, proposals that wait for the owner
    "item.edited", "item.retired", "item.restored", "item.reconfirmed", "change.proposed", "change.decided", "document.filed", "sale.closed",
    # the front desk: settings, Nova's rounds, the Lobby board
    "setting.changed", "rounds.started", "briefing.ready",
    "stage.changed", "autonomy.changed", "lesson.added", "lesson.removed",
    # the Deal desk's links to clients: signing a form, and the documents they send
    "sign.link", "sign.signed", "docs.requested", "docs.received", "docs.rejected", "docs.reminded", "docs.confirmed",
    "sign.opened", "docs.opened", "docs.renewed", "sign.renewed", "document.voided", "client.queued", "client.released",
    # the closed loop: the spec's own names for what passes between the rooms (docs/closed-loop-spec.md)
    "task.reopened", "case.converted", "case.lost", "case.closed", "deal.ready_for_transfer",
    "compliance.cleared", "compliance.needs_info", "compliance.blocked", "compliance.rated", "screening.hit", "screening.resolved",
    "payment.marked_received", "payment.undone", "payment.flagged", "payment.reminded", "invoice.written_off",
    "form.sent", "form.recalled", "portal.drafted", "portal.submitted", "transfer.booked", "transfer.completed",
    # the content studio: what it saw, what it pinned, what it made, and footage people uploaded
    "post.seen", "post.read", "photo.read", "content.idea", "content.briefed", "content.scripted", "content.ready",
    "post.approved", "post.live", "post.paused", "post.withdrawn", "campaign.started", "campaign.ended", "lead.attributed", "product.saved", "mchat.said", "mchat.upload", "mchat.analysed", "photos.added", "plan.made", "plan.started", "competitor.checked", "board.pinned", "board.unpinned", "content.made", "footage.added", "step.blocked",
    "qa.passed", "qa.failed", "qa.escalated", "taste.signal", "taste.reason", "taste.forgotten",
    # the Lobby room (the spec's Room 9), not the requests board below, which kept the old "lobby." names
    "thread.posted", "playbook.added", "playbook.removed", "experiment.proposed", "experiment.refused", "experiment.approved", "experiment.switched", "experiment.reported", "experiment.ended",
    "lobby.posted", "lobby.seen", "lobby.reminded", "lobby.late", "lobby.done", "lobby.cancelled",
    "chat.received", "chat.sent", "chat.suggested", "chat.handover", "appointment.booked", "appointment.cancelled", "viewing.requested",
    "offer.made", "offer.accepted", "offer.declined",
    # the lead desk: who owns a lead, what needs a person by when, the Pool, and notices to people
    "lead.assigned", "lead.pooled", "lead.claimed", "attention.raised", "attention.overdue", "attention.cleared",
    "notify.sent", "notify.read", "listings.synced", "listings.found", "topic.saved", "competitors.refreshed",
    # qualification: the owner's form, the customer type, answers with quotes, and the verdict
    "qualify.form", "qualify.type", "qualify.answer", "qualify.asked", "qualify.passed", "qualify.not_fit", "qualify.open",
    "agent.added", "agent.paused", "agent.resumed", "agent.removed", "lead.recommended", "lead.hot", "lead.kind",
    "followup.drafted", "followup.sent", "followup.dismissed", "lead.nurture", "lead.reopened", "followup.nudged", "lead.optout", "lead.went_quiet", "appointment.moved", "appointment.reminded", "appointment.done", "appointment.noshow", "calendar.morning", "visit.summarized", "calendar.blocked", "calendar.unblocked", "appointment.link", "appointment.link_removed", "lead.unhot", "lead.no_calls", "lead.followups", "chat.merged",
    # the Sales room: a card moved to the next broker, what came of a call, the broker's list, a nudge
    "attention.moved", "lead.outcome", "lead.sweep", "lead.nudged", "notify.digest",
    # the Front Desk: the first open of the day, errands that wait for a yes, and the meeting Nova sits in on
    "email.sent", "email.failed", "note.added", "note.done", "nova.arrived", "nova.watched", "nova.headsup", "errand.drafted", "errand.confirmed", "errand.cancelled", "pocket.started", "pocket.line", "pocket.ended",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class EventLog:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.seen: list[dict] = []  # append-only, so each row is parsed once; a page reads the log hundreds of times
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
        with self.lock:  # one connection is shared by the web threads and the studio's workers (a browser run found the race)
            rows = self.db.execute("select * from events where id > ? order by id", (self.seen[-1]["id"] if self.seen else 0,)).fetchall()
            self.seen.extend(self._row(r) for r in rows)  # reading what is new also finds another process's writes
            seen = self.seen[bisect_right(self.seen, after, key=lambda e: e["id"]):] if after else list(self.seen)
        return [e for e in seen if (not deal or e["deal"] == deal) and (not agent or e["agent"] == agent)] if deal or agent else seen  # rows are shared: read them, never change them
