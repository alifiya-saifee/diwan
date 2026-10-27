"""The HTTP and WebSocket API every screen uses. Run: .venv/bin/uvicorn diwan.app:app --port 8030

Everything a screen shows comes from the event log or the graph built from it; every action here goes through the same
office, agents and charters the tests exercise.
"""
from __future__ import annotations

import asyncio
import contextlib
import re
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from diwan import demo, slots
from diwan.agents import nova, reception, scribe
from diwan.agents.charters import ROSTER
from diwan.config import env
from diwan.events import EventLog
from diwan.office import Office
from diwan.people import PEOPLE
from diwan.providers import voice, whatsapp
from diwan.providers.chat import PROVIDERS

WEB = Path(__file__).resolve().parents[1] / "web"


class State:
    office: Office
    last_brief: str | None = None


S = State()


def fresh() -> Office:
    o = Office(EventLog(env("DIWAN_DB", ":memory:")))
    if not o.log.list():
        demo.seed(o)
    return o


S.office = fresh()


async def morning_loop():
    while True:
        now = datetime.now(slots.DUBAI)
        if nova.briefing_due(now, S.last_brief):
            nova.morning(S.office)
            S.last_brief = now.date().isoformat()
        await asyncio.sleep(60)


@contextlib.asynccontextmanager
async def lifespan(_):
    S.last_brief = datetime.now(slots.DUBAI).date().isoformat()  # the first briefing is tomorrow 07:00, or on demand
    task = asyncio.create_task(morning_loop())
    yield
    task.cancel()


app = FastAPI(title="Diwan", lifespan=lifespan)


def g():
    return S.office.graph()


def node_json(gr, n) -> dict:
    return {"id": n.id, "type": n.type, "label": n.label, "status": n.status, "deal": n.deal, "record": gr.record(n.id),
            "props": {k: v for k, v in n.props.items() if k != "messages"}}


# ---------- what is plugged in ----------

@app.get("/api/health")
def health():
    return {"ok": True, "providers": {p.id: p.available() for p in PROVIDERS.values()}, "voice": voice.available(),
            "whatsapp": whatsapp.available(), "events": len(S.office.log.list())}


@app.get("/api/roster")
def roster():
    from dataclasses import asdict
    return [asdict(c) for c in ROSTER]


@app.get("/api/people")
def people():
    return PEOPLE


@app.post("/api/demo/reset")
def reset(correction: bool = False):
    S.office = Office(EventLog(":memory:"))
    demo.seed(S.office)
    if correction:
        demo.correction(S.office)
    return {"events": len(S.office.log.list())}


# ---------- the log and the graph ----------

@app.get("/api/events")
def events(deal: str | None = None, agent: str | None = None, after: int = 0):
    return S.office.log.list(deal=deal, agent=agent, after=after)


@app.get("/api/graph")
def graph(deal: str | None = None, upto: int | None = None):
    gr = S.office.graph(upto)
    keep = {n.id for n in gr.nodes.values() if deal is None or n.deal in (deal, None) or n.type == "person"}
    return {"last_event": gr.last_event,
            "nodes": [node_json(gr, gr.nodes[i]) for i in keep],
            "edges": [{"src": e.src, "rel": e.rel, "dst": e.dst, "via": e.via} for e in gr.edges if e.src in keep and e.dst in keep]}


@app.get("/api/deals")
def deals():
    gr = g()
    return [node_json(gr, d) for d in gr.deals()]


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket, after: int = 0):
    await ws.accept()
    last = after
    try:
        while True:
            new = S.office.log.list(after=last)
            if new:
                last = new[-1]["id"]
                await ws.send_json({"events": new})
            await asyncio.sleep(0.4)
    except (WebSocketDisconnect, RuntimeError):
        pass


# ---------- Nova ----------

class Ask(BaseModel):
    text: str
    person: str = "layla"


@app.post("/api/nova/ask")
def ask(body: Ask):
    return nova.ask(S.office, body.text, body.person)


@app.post("/api/nova/route")
def route(body: Ask):
    return nova.route(S.office, body.text, body.person)


@app.post("/api/nova/say")
def say(body: Ask):
    """One box for people: a question goes to ask, anything else is an instruction."""
    t = body.text.strip()
    if t.lower().startswith("brief"):
        return nova.brief(S.office, (t.split()[1:] or [body.person])[0])
    q = t.endswith("?") or re.match(r"(?i)(who|what|when|where|why|how|is|are|does|did|can|which)\b", t)
    return nova.ask(S.office, t, body.person) if q else nova.route(S.office, t, body.person)


@app.get("/api/nova/brief/{person}")
def brief(person: str):
    if person not in PEOPLE:
        raise HTTPException(404, "no such person")
    return nova.brief(S.office, person)


# ---------- meetings ----------

class MeetingIn(BaseModel):
    deal: str
    title: str = "Meeting"


class TurnIn(BaseModel):
    speaker: str = "customer"
    text: str


@app.post("/api/meetings")
def start_meeting(body: MeetingIn):
    mid = f"M{len([e for e in S.office.log.list() if e['type'] == 'meeting.started']) + 1}"
    S.office.start_meeting(body.deal, mid, title=body.title)
    return S.office.meeting(mid)


@app.post("/api/meetings/{mid}/consent")
def consent(mid: str, by: str = "customer"):
    S.office.give_consent(mid, by=by)
    return S.office.meeting(mid)


@app.post("/api/meetings/{mid}/turn")
def turn(mid: str, body: TurnIn):
    try:
        return scribe.turn(S.office, mid, body.speaker, body.text)
    except PermissionError as e:
        raise HTTPException(409, str(e))


@app.post("/api/meetings/{mid}/end")
def end(mid: str):
    S.office.end_meeting(mid)
    return S.office.meeting(mid)


@app.websocket("/api/meetings/{mid}/audio")
async def audio(ws: WebSocket, mid: str):
    """The table phone streams PCM16 at 16 kHz; finished turns go to the Scribe, partial lines come back for the screen."""
    await ws.accept()
    m = S.office.meeting(mid)
    if not m["consent"]:
        await ws.close(4009, "no consent")
        return
    if not voice.available():
        await ws.close(4001, "live transcription needs META_API_KEY")
        return
    q: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def chunks():
        while (c := await q.get()) is not None:
            yield c

    def on_turn(t: dict):
        if "final" in t:
            res = scribe.turn(S.office, mid, t["speaker"], t["final"], turn_id=t.get("turn"))
            loop.create_task(ws.send_json({"final": t["final"], "speaker": t["speaker"], "facts": res["facts"]}))
        else:
            loop.create_task(ws.send_json(t))

    relay = asyncio.create_task(voice.stream(chunks(), on_turn))
    try:
        while True:
            msg = await ws.receive()
            if msg.get("bytes"):
                await q.put(msg["bytes"])
            elif msg.get("type") == "websocket.disconnect" or msg.get("text") == "end":
                break
    finally:
        await q.put(None)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(relay, 15)


# ---------- approvals ----------

@app.post("/api/approvals/{aid}/execute")
def execute(aid: str, key: str):
    return S.office.execute(aid, key)


class ApproveIn(BaseModel):
    deal: str
    approver: str
    action: str
    rests_on: list[str]


@app.post("/api/approvals")
def approve(body: ApproveIn):
    return {"id": S.office.approve(body.deal, body.approver, body.action, body.rests_on)}


# ---------- knowledge and listings ----------

class KnowledgeIn(BaseModel):
    kind: str = "faq"
    title: str
    text: str
    by: str = "layla"


class DocIn(BaseModel):
    text: str
    by: str = "layla"
    source: str = "pasted document"


class ListingIn(BaseModel):
    ref: str
    title: str
    community: str
    type: str = "apartment"
    beds: int
    price_aed: int
    permit: str | None = None
    features: list[str] = []
    by: str = "omar"


@app.get("/api/knowledge")
def knowledge():
    gr = g()
    return [node_json(gr, n) for n in gr.of("knowledge")]


@app.post("/api/knowledge")
def add_knowledge(body: KnowledgeIn):
    return {"id": S.office.add_knowledge(body.kind, body.title, body.text, by=body.by)}


@app.post("/api/knowledge/document")
def add_document(body: DocIn):
    """Each line of a pasted document becomes a proposed item, word for word, waiting for a person to confirm it."""
    ids = []
    for line in (ln.strip(" -•\t") for ln in body.text.splitlines()):
        if len(line) < 8:
            continue
        title, _, rest = line.partition(":")
        title, text = (title.strip(), line) if rest.strip() and len(title) <= 40 else (" ".join(line.split()[:5]), line)
        ids.append(S.office.add_knowledge("document", title, text, by=body.by, confirmed=False, source=body.source))
    return {"proposed": ids}


@app.post("/api/knowledge/{kid}/confirm")
def confirm(kid: str, by: str = "layla"):
    S.office.confirm_knowledge(kid, by=by)
    return {"ok": True}


@app.get("/api/listings")
def listings():
    gr = g()
    return [node_json(gr, n) | {"advertised": bool(n.props.get("permit")) and n.status == "available"} for n in gr.of("listing")]


@app.post("/api/listings")
def add_listing(body: ListingIn):
    return {"id": S.office.add_listing(**body.model_dump())}


# ---------- the inbox and WhatsApp ----------

class ChatIn(BaseModel):
    phone: str
    text: str
    name: str | None = None


class SendIn(BaseModel):
    text: str
    by: str = "omar"


@app.get("/api/chats")
def chats():
    gr = g()
    out = []
    for c in gr.of("chat"):
        facts = [gr.record(f.id) for f in gr.facts(c.deal)] if c.deal else []
        viewings = [gr.record(v.id) for v in gr.of("viewing", status="booked") if v.props.get("chat") == c.props["phone"]]
        out.append(node_json(gr, c) | {"messages": c.props["messages"], "facts": facts, "viewings": viewings})
    return sorted(out, key=lambda c: c["props"].get("last_at", ""), reverse=True)


@app.post("/api/chats/incoming")
def incoming(body: ChatIn):
    """The sandbox phone: the same path a real WhatsApp message takes."""
    return reception.message(S.office, body.phone, body.text, name_=body.name)


@app.post("/api/chats/{phone}/send")
def person_send(phone: str, body: SendIn):
    return reception.person_sends(S.office, phone, body.text, by=body.by)


@app.post("/api/chats/{phone}/take")
def take(phone: str, by: str = "omar"):
    reception.hand_over(S.office, phone, to=by, by=by, reason="taken from the Inbox")
    return {"ok": True}


@app.post("/api/chats/{phone}/release")
def release(phone: str, by: str = "omar"):
    reception.give_back(S.office, phone, by=by)
    return {"ok": True}


@app.get("/api/whatsapp/webhook")
def wa_verify(request: Request):
    challenge = whatsapp.verify(dict(request.query_params))
    if challenge is None:
        raise HTTPException(403, "verify token does not match")
    return PlainTextResponse(challenge)


@app.post("/api/whatsapp/webhook")
async def wa_receive(request: Request):
    body = await request.body()
    if not whatsapp.signed(body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    for m in whatsapp.parse(await request.json()):
        reception.message(S.office, m["phone"], m["text"], name_=m["name"])
    return {"ok": True}


# ---------- screens ----------

@app.middleware("http")
async def no_store(request: Request, call_next):
    r = await call_next(request)
    if request.url.path.startswith("/web"):
        r.headers["Cache-Control"] = "no-store"
    return r


@app.get("/")
def root():
    return RedirectResponse("/web/index.html")


if WEB.exists():
    app.mount("/web", StaticFiles(directory=WEB), name="web")
