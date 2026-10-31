"""The test console for Rania: talk to her as a customer and see exactly why she answered the way she did.

Each test conversation runs on a private copy of the office (every event so far, in memory), so nothing it does
reaches the real office: no chats, facts, bookings or cards appear in the Inbox, and nothing is sent to WhatsApp,
Instagram or anyone's phone. You choose the brain for each message: Muse Spark on Meta's API (paid credits), Muse
Glimmer on NVIDIA's free endpoint (everyday testing, fictional data only), or the rules alone, always live, never a
recorded answer, so they can be compared on the same words.

For every reply it reports: who answered (which model, or the rules and why), how long it took, the listings and
company knowledge she used, the facts the Scribe heard, whether the chat went to a person and why, and what a guard
stopped her from saying (a price that is not on a listing, a "never" lesson).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from diwan.config import TRIAL
from diwan.events import EventLog
from diwan.office import Office
from diwan.people import name
from diwan.providers.chat import PROVIDERS, for_tier
from diwan.slots import DUBAI

SESSIONS: dict[str, dict] = {}
MAX_SESSIONS = 20


def copy_of(office: Office) -> Office:
    """The office as it is now, in memory: same events, same ids, so every record a reply cites is the real one."""
    log = EventLog()
    with office.log.lock:
        rows = office.log.db.execute("select id, at, request, deal, agent, actor, type, content, caused_by, key from events order by id").fetchall()
    log.db.executemany("insert into events (id, at, request, deal, agent, actor, type, content, caused_by, key) values (?,?,?,?,?,?,?,?,?,?)",
                       [tuple(r) for r in rows])
    log.db.commit()
    return Office(log)


def start(office: Office, customer: str = "Test Buyer") -> dict:
    if len(SESSIONS) >= MAX_SESSIONS:
        SESSIONS.pop(next(iter(SESSIONS)))
    sid = uuid.uuid4().hex[:10]
    SESSIONS[sid] = {"office": copy_of(office), "phone": f"9715{int(sid[:7], 16) % 10**8:08d}", "customer": customer, "turns": []}
    return {"session": sid, "phone": SESSIONS[sid]["phone"]}


BRAINS = {"spark": "meta", "free": "nvidia"}  # the console's choices; "model" means whatever the office uses by default


def model_name(brain: str = "model") -> str | None:
    token = TRIAL.set({"provider": BRAINS[brain]} if brain in BRAINS else {})
    try:
        p = for_tier("spark")
    finally:
        TRIAL.reset(token)
    return f"{p.label} · {p.model()}" if p else None


def brains() -> dict:
    return {b: PROVIDERS[pid].available() for b, pid in BRAINS.items()} | {"default": model_name()}


def _trial(brain: str) -> dict:
    return {"sandbox": True, "tape": "off"} | ({"offline": True} if brain == "rules" else {"provider": BRAINS[brain]} if brain in BRAINS else {})


def say(sid: str, text: str, *, brain: str = "model", now: datetime | None = None) -> dict:
    """One customer message in a test conversation. `brain`: "spark", "free", "model" (the office's default) or "rules"."""
    from diwan.agents import reception
    s = SESSIONS[sid]
    o, phone = s["office"], s["phone"]
    before = o.log.list()[-1]["id"] if o.log.list() else 0
    token = TRIAL.set(_trial(brain))
    t0 = time.monotonic()
    try:
        r = reception.message(o, phone, text, name_=s["customer"] if not s["turns"] else None, now=now or datetime.now(DUBAI))
    finally:
        TRIAL.reset(token)
    ms = int((time.monotonic() - t0) * 1000)
    new = o.log.list(after=before)
    g = o.graph()
    failed = next((e["content"]["error"] for e in new if e["type"] == "agent.failed" and e["agent"] == "rania"), None)
    if r["by"] == "model":
        p = PROVIDERS.get(r["usage"].get("provider"))
        who = f"{p.label} · {r['usage'].get('model')}" if p else model_name() or "model"
        why = None
    elif r["by"] == "policy":
        who, why = "Fixed reply", None  # a sensitive topic: the same safe answer whatever model is on
    elif brain == "rules":
        who, why = "Rules", "You chose rules only"
    else:
        who = "Rules"
        why = (f"The model failed or was too slow, so the rules answered: {failed}" if failed
               else {"spark": "Muse Spark is not connected (add META_API_KEY)", "free": "The free endpoint is not connected (add NVIDIA_API_KEY)"}.get(
                   brain, "No model is connected (add META_API_KEY, or NVIDIA_API_KEY for development)") if not model_name(brain)
               else "The model was not used for this message (budget reached, or offline)")
    deal = g.nodes[f"chat:{phone}"].deal
    card = next((e["content"] for e in new if e["type"] == "attention.raised"), None)
    turn = {
        "text": text, "reply": r.get("reply") or r.get("suggestion") or "", "mode": r["mode"], "brain": brain, "by": r["by"],
        "who": who, "why_rules": why, "ms": ms, "usage": {k: v for k, v in r.get("usage", {}).items() if k in ("input_tokens", "output_tokens", "cost_usd", "fallback")},
        "used": [{"id": ref, "text": g.record(ref) if ref in g.nodes else ref} for ref in r.get("refs", [])],
        "heard": [{"id": f, "text": g.record(f)} for f in r.get("facts", []) if f in g.nodes],
        "handover": r.get("handover") or (card or {}).get("reason"),
        "to": name(card["who"]) if card else None, "card": {"kind": card["kind"], "due": card["due"]} if card else None,
        "held": r.get("held"),
        "prompt": r.get("prompt"),  # exactly what the model was sent (also when the rules answered instead)
        "qualify": {k: (r.get("qualify") or {}).get(k) for k in ("verdict", "type", "type_label", "answers", "missing", "reasons", "version")}
        | {"next": ((r.get("qualify") or {}).get("next") or {}).get("label")},
        "booked": [g.record(e["content"]["id"]) for e in new if e["type"] == "appointment.booked"],
        "stage": (g.nodes[f"deal:{deal}"].props.get("stage") or "New") if deal else None,
        "broker": name(g.nodes[f"deal:{deal}"].props.get("broker")) if deal else None,
    }
    s["turns"].append(turn)
    return turn


JOBS: dict[str, dict] = {}


def start_cases(*, brain: str = "rules") -> dict:
    """Run the cases in the background: on a model they take minutes, longer than a web request should be held open
    (and a reloading server would cut it). The page asks for progress until the job is done."""
    import threading
    jid = uuid.uuid4().hex[:10]
    job = JOBS[jid] = {"id": jid, "brain": brain, "model": model_name(brain) if brain != "rules" else None, "done": 0, "total": None,
                       "cases": [], "finished": False, "error": None, "started": time.time()}

    def work():
        token = TRIAL.set(_trial(brain))  # a thread starts with an empty context: set the trial inside it
        try:
            from diwan import evals
            evals.eval_rania(on_case=lambda c, done, total: (job["cases"].append(c), job.update(done=done, total=total)))
        except Exception as e:  # the screen shows it rather than spinning forever
            job["error"] = str(e)[:300]
        finally:
            TRIAL.reset(token)
            job.update(finished=True, seconds=round(time.time() - job["started"], 1))
    threading.Thread(target=work, daemon=True).start()
    if len(JOBS) > 20:
        JOBS.pop(next(iter(JOBS)))
    return job_status(jid)


def job_status(jid: str) -> dict:
    j = JOBS[jid]
    return {k: v for k, v in j.items() if k != "started"} | {"passed": sum(c["pass"] for c in j["cases"]),
                                                            "seconds": j.get("seconds", round(time.time() - j["started"], 1))}


def cases(*, brain: str = "rules") -> dict:
    """Rania's labelled test cases (diwan/evals.py), each on a fresh demo office, in the sandbox."""
    from diwan import evals
    token = TRIAL.set(_trial(brain))
    t0 = time.monotonic()
    try:
        out = evals.eval_rania()
    finally:
        TRIAL.reset(token)
    return {"brain": brain, "model": model_name(brain) if brain != "rules" else None, "passed": sum(c["pass"] for c in out), "total": len(out),
            "seconds": round(time.monotonic() - t0, 1), "cases": out}
