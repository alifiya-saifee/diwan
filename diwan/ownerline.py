"""The owner's own WhatsApp: a second pathway that never meets the sales line. Sales stays with Rania, the Inbox and the event log.
This line is read by Nova for the owner alone, and it lives in its own small database next to the office's, because the event log is
permanent and family messages must be deletable. Nothing here is written to the event log, and nothing reads it but the owner's Nova.

Off until PERSONAL_WHATSAPP_TOKEN and PERSONAL_WHATSAPP_PHONE_ID are set; until then a stand-in phone on the Personal page feeds the
same path. Even connected it only reads until PERSONAL_WHATSAPP_SENDING=on, so a first week can prove her judgement with nothing sent.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from diwan import config
from diwan.config import env
from diwan.providers import whatsapp
from diwan.slots import DUBAI

KEEP_DAYS = 90
ONE_TIME = re.compile(r"\b(otp|one[- ]?time|verification code|security code|login code|passcode|pin code|cvv)\b|رمز|كلمة المرور", re.I)
SCHEMA = """
create table if not exists messages (id integer primary key, at text, mid text unique, chat text, mine integer, by text, name text, kind text, text text, media text, via text);
create table if not exists contacts (phone text primary key, name text, circle text, note text, quiet integer default 0);
create table if not exists matters (id integer primary key, at text, chat text, name text, level text, summary text, needs text, whenever text, draft text, status text, told_at text,
                                    last_message integer, followup integer default 0);
create table if not exists notices (id integer primary key, at text, level text, text text);
"""


class ReadOnly(RuntimeError):
    """Connected, but sending has not been turned on."""


def path() -> Path:
    office = env("DIWAN_DB")
    return Path(office).with_name("personal.db") if office and office != ":memory:" else config.ROOT / "personal.db"


@contextmanager
def db():
    c = sqlite3.connect(path(), timeout=20)
    c.row_factory = sqlite3.Row
    try:
        c.executescript(SCHEMA)
        with c:
            yield c
    finally:
        c.close()


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def line_id() -> str | None:
    return env("PERSONAL_WHATSAPP_PHONE_ID")


def connected() -> bool:
    """Connected, and on a number of its own: sharing the sales number would join the two pathways, so it counts as not connected."""
    return bool(env("PERSONAL_WHATSAPP_TOKEN") and line_id() and line_id() != env("WHATSAPP_PHONE_ID"))


def sending() -> bool:
    return env("PERSONAL_WHATSAPP_SENDING") == "on"


def is_personal(line: str | None) -> bool:
    return bool(line) and connected() and line == line_id()


def one_time(text: str) -> bool:
    """A login or bank code: not kept, and never shown to a model."""
    return bool(ONE_TIME.search(text or "")) and bool(re.search(r"\d{4,8}", text or ""))


def keep(m: dict, now: datetime | None = None) -> dict | None:
    """One message, in or out. None for a repeat of one already kept, and for a one-time code, which is dropped on arrival."""
    if one_time(m.get("text", "")):
        return None
    now = now or datetime.now(DUBAI)
    with db() as c:
        cur = c.execute("insert or ignore into messages (at, mid, chat, mine, by, name, kind, text, media, via) values (?,?,?,?,?,?,?,?,?,?)",
                        (now.isoformat(), m.get("id"), _digits(m["phone"]), int(bool(m.get("echo"))), "owner" if m.get("echo") else "them", m.get("name"),
                         m.get("kind", "text"), m.get("text", ""), m.get("media"), "whatsapp"))
        if not cur.rowcount:
            return None
        return dict(c.execute("select * from messages where id=?", (cur.lastrowid,)).fetchone())


def set_text(mid: int, text: str) -> None:
    """A voice note, once transcribed."""
    with db() as c:
        c.execute("update messages set text=? where id=?", (text, mid))


def chat(phone: str, n: int = 12) -> list[dict]:
    with db() as c:
        return [dict(r) for r in c.execute("select * from messages where chat=? order by id desc limit ?", (_digits(phone), n))][::-1]


def chats() -> list[dict]:
    """Each conversation's newest message, newest first."""
    with db() as c:
        return [dict(r) for r in c.execute("select * from messages where id in (select max(id) from messages group by chat) order by id desc")]


def owed() -> list[dict]:
    """Chats where the other person spoke last: who the owner owes a reply."""
    return [m for m in chats() if not m["mine"]]


def send(phone: str, text: str, *, by: str = "nova", transport=None) -> dict:
    """Out through this line's own credentials, never the sales line's. With no line connected it stays on the stand-in phone."""
    phone = _digits(phone)
    via, mid = "sandbox", None
    if connected() and not config.sandbox_only():
        if not sending():
            raise ReadOnly("Your WhatsApp is connected for reading only, so nothing was sent.")
        r = whatsapp.send(phone, text, transport, phone_id=line_id(), token=env("PERSONAL_WHATSAPP_TOKEN"))
        via, mid = "whatsapp", (r.get("messages") or [{}])[0].get("id")
    now = datetime.now(DUBAI)
    with db() as c:
        c.execute("insert into messages (at, mid, chat, mine, by, kind, text, via) values (?,?,?,1,?,?,?,?)", (now.isoformat(), mid, phone, by, "text", text, via))
    return {"via": via, "id": mid}


def forget(phone: str) -> int:
    """Everything said with this person, gone for good."""
    phone = _digits(phone)
    with db() as c:
        c.execute("delete from matters where chat=?", (phone,))
        return c.execute("delete from messages where chat=?", (phone,)).rowcount


def forget_all() -> None:
    with db() as c:
        for t in ("messages", "matters", "notices"):
            c.execute(f"delete from {t}")  # noqa: S608  fixed names


def prune(now: datetime | None = None) -> int:
    """Personal messages are kept for a set time, then go."""
    now = now or datetime.now(DUBAI)
    limit = (now - timedelta(days=int(env("PERSONAL_KEEP_DAYS") or KEEP_DAYS))).isoformat()
    with db() as c:
        c.execute("delete from matters where at<? and status='closed'", (limit,))
        c.execute("delete from notices where at<?", (limit,))
        return c.execute("delete from messages where at<?", (limit,)).rowcount
