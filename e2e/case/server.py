"""The scratch office for the case study. It has its own data and its own clock, so a test can move time forward and a viewing really is in
the past, a reminder really falls due. Only this file moves the clock: the app has no such thing. Sign-in is on, with every person's password
PASSWORD, so each role is tested as itself. Nothing leaves: WhatsApp isn't connected, and email is cut off here.

    python e2e/case/server.py <port> <folder for its data>
"""
import asyncio
import datetime as dt
import importlib
import os
import pkgutil
import sys
from pathlib import Path

PORT, HOME = int(sys.argv[1]), Path(sys.argv[2]).resolve()
HOME.mkdir(parents=True, exist_ok=True)
os.environ.update(DIWAN_DB=str(HOME / "case.db"), DIWAN_MEDIA=str(HOME / "media"), DIWAN_TAPE="off", DIWAN_REPLY_WAIT="1", DIWAN_LOCAL_ASR="0")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import uvicorn  # noqa: E402

import diwan  # noqa: E402
from diwan import app as A, access  # noqa: E402
from diwan.people import PEOPLE  # noqa: E402

for m in pkgutil.walk_packages(diwan.__path__, "diwan."):
    if not m.name.endswith("__main__"):
        try:
            importlib.import_module(m.name)
        except Exception as e:  # noqa: BLE001
            print("not loaded:", m.name, e)

PASSWORD = "a good password"
SKIP = [dt.timedelta(0)]
REAL, REAL_DAY = dt.datetime, dt.date


class Same(type):
    def __instancecheck__(cls, x):
        return isinstance(x, REAL)


class Clock(REAL, metaclass=Same):
    @classmethod
    def now(cls, tz=None):
        return REAL.now(tz) + SKIP[0]

    @classmethod
    def utcnow(cls):
        return REAL.utcnow() + SKIP[0]


class SameDay(type):
    def __instancecheck__(cls, x):
        return isinstance(x, REAL_DAY)


class Day(REAL_DAY, metaclass=SameDay):
    @classmethod
    def today(cls):
        return (REAL.now() + SKIP[0]).date()


for name, mod in list(sys.modules.items()):
    if name.startswith("diwan") and mod is not None:
        if getattr(mod, "datetime", None) is REAL:
            mod.datetime = Clock
        if getattr(mod, "date", None) is REAL_DAY:
            mod.date = Day

from diwan.providers import email  # noqa: E402

email.available = lambda: False


async def quiet():
    await asyncio.Event().wait()


A.morning_loop = quiet  # time only passes when a test says so: each tick is a step on screen
A.custom_loop = quiet


@A.app.post("/api/case/clock")
def move_clock(body: dict):
    SKIP[0] += dt.timedelta(hours=float(body.get("hours") or 0), minutes=float(body.get("minutes") or 0))
    return {"now": Clock.now(A.slots.DUBAI).isoformat()}


@A.app.post("/api/case/set-clock")
def set_clock(body: dict):
    """To an exact time, for quiet hours and Fridays."""
    SKIP[0] = REAL.fromisoformat(body["at"]) - REAL.now(A.slots.DUBAI)
    return {"now": Clock.now(A.slots.DUBAI).isoformat()}


@A.app.post("/api/case/tick")
def tick():
    """One turn of the office's minute loop: every sweep, in its order."""
    from diwan import client_msgs, documents, leads, lobby_room, ownerline, sales
    from diwan.agents import finance, frontdesk, lobby, nudge, reminders, triage, watch
    now = Clock.now(A.slots.DUBAI)
    out = {}
    for label, fn, args in (("lobby", lobby.chase, (A.S.office, now)), ("documents", documents.sweep, (A.S.office, now)), ("client messages", client_msgs.sweep, (A.S.office, now)),
                            ("finance", finance.sweep, (A.S.office, now)), ("watch", watch.sweep, (A.S.office, now)), ("lobby room", lobby_room.sweep, (A.S.office, now)),
                            ("leads", leads.sweep, (A.S.office, now)), ("follow-ups", nudge.sweep, (A.S.office, now)), ("reminders", reminders.sweep, (A.S.office, now)),
                            ("sales", sales.sweep, (A.S.office, now)), ("front desk", frontdesk.sweep, (A.S.office, now)), ("alerts", watch.alerts, (A.S.office, now)),
                            ("owner's whatsapp", triage.sweep, (A.S.office, now)), ("personal", ownerline.prune, (now,))):
        try:
            out[label] = fn(*args)
        except Exception as e:  # noqa: BLE001
            out[label] = f"FAILED {type(e).__name__}: {e}"
            print("SWEEP FAILED", label, repr(e), flush=True)
    return {"now": now.isoformat(), "did": {k: str(v)[:200] for k, v in out.items() if v}}


@A.app.get("/api/case/spend")
def spend():
    from diwan import costs
    return {"rest": costs.month_spend(part="rest"), "cap": costs.budget("rest"), "total": costs.month_spend()}


for p in PEOPLE:
    access.set_password(p, PASSWORD)
uvicorn.run(A.app, port=PORT, log_level="warning")
