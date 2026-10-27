"""The HTTP and WebSocket API every screen uses. Run: .venv/bin/uvicorn diwan.app:app --port 8030

Everything a screen shows comes from the event log or the graph built from it; every action here goes through the same
office, agents and charters the tests exercise.
"""
from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from pathlib import Path

import httpx

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
    """Every minute: chase the Lobby board, and do Nova's rounds 30 minutes before the earliest briefing time."""
    from diwan.agents import lobby
    while True:
        now = datetime.now(slots.DUBAI)
        gr = S.office.graph()
        first = min(nova.briefing_time(gr, p) for p in PEOPLE)
        if nova.briefing_due(now, S.last_brief, first, lead_minutes=30):
            nova.rounds(S.office, now)
            S.last_brief = now.date().isoformat()
        lobby.chase(S.office, now)
        await asyncio.sleep(60)


@contextlib.asynccontextmanager
async def lifespan(_):
    S.last_brief = None
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


@app.get("/api/agents/{aid}")
def agent_detail(aid: str):
    from dataclasses import asdict

    from diwan.agents import lessons
    from diwan.agents.charters import BY_ID
    if aid not in BY_ID:
        raise HTTPException(404, "no such agent")
    return asdict(BY_ID[aid]) | {"autonomy": lessons.level(S.office.log, aid), "levels": lessons.LEVELS,
                                 "lessons": lessons.active_from_log(S.office.log, aid)}


@app.get("/api/autonomy")
def autonomy():
    from diwan.agents import lessons
    return {"levels": lessons.LEVELS, "agents": lessons.levels(S.office.log)}


class LevelIn(BaseModel):
    level: str
    by: str = "layla"


@app.post("/api/agents/{aid}/autonomy")
def set_autonomy(aid: str, body: LevelIn):
    from diwan.agents import lessons
    try:
        lessons.set_level(S.office.log, aid, body.level, by=body.by)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}


class LessonIn(BaseModel):
    text: str
    agent: str | None = None
    by: str = "layla"


@app.post("/api/lessons")
def add_lesson(body: LessonIn):
    """"Never mention service charges" for an agent, or a full sentence naming the agent."""
    from diwan.agents import lessons
    text = f"{body.agent}, {body.text}" if body.agent and not lessons.parse(body.text) else body.text
    ls = lessons.parse(text) or lessons.parse(f"{lessons.who(body.agent) if body.agent else 'everyone'}, {body.text}")
    if not ls:
        raise HTTPException(422, 'Start with "never" or "always", for example "never mention service charges".')
    return {"id": lessons.add(S.office.log, ls, by=body.by), "lesson": ls}


@app.post("/api/lessons/{lid}/remove")
def remove_lesson(lid: str, by: str = "layla"):
    from diwan.agents import lessons
    lessons.remove(S.office.log, lid, by=by)
    return {"ok": True}


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
    session: str | None = None


@app.post("/api/nova/ask")
def ask(body: Ask):
    return nova.ask(S.office, body.text, body.person)


@app.post("/api/nova/route")
def route(body: Ask):
    return nova.route(S.office, body.text, body.person)


@app.post("/api/nova/say")
def say(body: Ask):
    """One box for talking to Nova: questions, instructions, requests for people, read-backs, settings."""
    return nova.converse(S.office, body.text, body.person, session=body.session or body.person)


@app.post("/api/nova/rounds")
def do_rounds():
    return nova.rounds(S.office)


class SettingIn(BaseModel):
    briefing_time: str


@app.get("/api/settings/{person}")
def get_settings(person: str):
    return {"briefing_time": nova.briefing_time(g(), person)}


@app.post("/api/settings/{person}")
def put_settings(person: str, body: SettingIn):
    try:
        nova.set_briefing_time(S.office, person, body.briefing_time)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"briefing_time": body.briefing_time}


@app.get("/api/lobby")
def lobby_board():
    from diwan.agents import lobby
    return lobby.board(g())


class DoneIn(BaseModel):
    by: str
    note: str = ""


@app.post("/api/lobby/{lid}/done")
def lobby_done(lid: str, body: DoneIn):
    from diwan.agents import lobby
    return lobby.done(S.office, lid, by=body.by, note=body.note)


@app.post("/api/lobby/{lid}/seen")
def lobby_seen(lid: str, body: DoneIn):
    from diwan.agents import lobby
    lobby.seen(S.office, lid, by=body.by)
    return {"ok": True}


@app.get("/api/nova/brief/{person}")
def brief(person: str):
    if person not in PEOPLE:
        raise HTTPException(404, "no such person")
    return nova.brief(S.office, person, log=False)  # reading a briefing is not an event; the 07:00 run is


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


@app.get("/api/records")
def records_view():
    gr = g()
    from diwan.agents.records import ledger
    return {"sales": ledger(gr), "documents": sorted((node_json(gr, d) for d in gr.of("document")), key=lambda d: d["props"]["date"], reverse=True)}


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
def chats(view: str = "all", person: str = "omar", stage: str | None = None, q: str = ""):
    from diwan import inbox
    return {"rows": inbox.listing(S.office, view=view, person=person, stage=stage, q=q), "counts": inbox.counts(S.office, person),
            "stages": inbox.STAGES}


@app.get("/api/chats/{phone}")
def chat_detail(phone: str):
    from diwan import inbox
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    return inbox.detail(S.office, phone) | {"quick": inbox.quick_replies(g())}


@app.post("/api/chats/incoming")
def incoming(body: ChatIn):
    """The sandbox phone: the same path a real WhatsApp message takes."""
    return reception.message(S.office, body.phone, body.text, name_=body.name)


@app.post("/api/chats/{phone}/send")
def person_send(phone: str, body: SendIn):
    try:
        return reception.person_sends(S.office, phone, body.text, by=body.by)
    except reception.WindowClosed as e:
        raise HTTPException(409, str(e))


class TemplateIn(BaseModel):
    name: str
    params: list[str] = []
    by: str = "omar"


@app.get("/api/templates")
def list_templates():
    from diwan import inbox
    from diwan.providers import aisensy
    if aisensy.available():
        try:
            return {"source": "aisensy", "templates": [t for t in aisensy.templates() if t["status"] in ("APPROVED", "")]}
        except aisensy.AiSensyError as e:
            return {"source": "error", "error": str(e), "templates": []}
    return {"source": "sample", "templates": inbox.SAMPLE_TEMPLATES}


@app.post("/api/chats/{phone}/template")
def send_template(phone: str, body: TemplateIn):
    t = next((x for x in list_templates()["templates"] if x["name"] == body.name), None)
    if not t:
        raise HTTPException(404, "no such approved template")
    return reception.send_template(S.office, phone, t, body.params, by=body.by)


class StageIn(BaseModel):
    stage: str
    by: str = "omar"


@app.post("/api/chats/{phone}/stage")
def chat_stage(phone: str, body: StageIn):
    from diwan import inbox
    try:
        inbox.set_stage(S.office, phone, body.stage, by=body.by)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"ok": True}


@app.post("/api/chats/{phone}/take")
def take(phone: str, by: str = "omar"):
    reception.hand_over(S.office, phone, to=by, by=by, reason="taken from the Inbox")
    return {"ok": True}


@app.post("/api/chats/{phone}/release")
def release(phone: str, by: str = "omar"):
    reception.give_back(S.office, phone, by=by)
    return {"ok": True}


# ---------- integrations: AiSensy, Meta's WhatsApp Cloud API ----------

@app.get("/api/integrations")
def integrations(request: Request):
    from diwan.providers import aisensy
    is_set = lambda k: bool(env(k))  # noqa: E731
    base = str(request.base_url).rstrip("/")
    return {
        "provider": env("WHATSAPP_PROVIDER") or ("aisensy" if aisensy.available() else "cloud" if whatsapp.available() else "sandbox"),
        "aisensy": {"connected": aisensy.available(), "fields": {k: is_set(k) for k in ("AISENSY_PROJECT_ID", "AISENSY_PROJECT_API_PWD", "AISENSY_API_KEY")},
                    "webhook": f"{base}/api/aisensy/webhook?token=…" if is_set("AISENSY_WEBHOOK_TOKEN") else None},
        "cloud": {"connected": whatsapp.available(), "fields": {k: is_set(k) for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET")},
                  "webhook": f"{base}/api/whatsapp/webhook"},
        "meta": {p.id: p.available() for p in PROVIDERS.values()} | {"voice": voice.available()},
    }


class IntegrationIn(BaseModel):
    values: dict[str, str]


@app.post("/api/integrations")
def save_integrations(body: IntegrationIn):
    """Keys go into the local .env. They are never echoed back: screens learn only whether each is set."""
    from diwan.config import set_env
    vals = {k: v.strip() for k, v in body.values.items() if v is not None}
    if "AISENSY_PROJECT_ID" in vals and not vals.get("AISENSY_WEBHOOK_TOKEN"):
        if not env("AISENSY_WEBHOOK_TOKEN"):
            import secrets
            vals["AISENSY_WEBHOOK_TOKEN"] = secrets.token_urlsafe(24)
    try:
        return {"changed": set_env(vals)}
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/integrations/aisensy/webhook-url")
def aisensy_webhook_url(request: Request):
    """The one place the full webhook URL (with its secret token) is shown, for pasting into AiSensy."""
    if not env("AISENSY_WEBHOOK_TOKEN"):
        raise HTTPException(404, "Save the AiSensy project first")
    return {"url": f"{str(request.base_url).rstrip('/')}/api/aisensy/webhook?token={env('AISENSY_WEBHOOK_TOKEN')}"}


@app.post("/api/integrations/aisensy/test")
def aisensy_test():
    from diwan.providers import aisensy
    try:
        ts = aisensy.templates()
        return {"ok": True, "templates": len(ts), "approved": len([t for t in ts if t["status"] == "APPROVED"])}
    except aisensy.AiSensyError as e:
        return {"ok": False, "error": str(e)}
    except httpx.HTTPError as e:
        return {"ok": False, "error": f"Could not reach AiSensy: {e}"}


@app.post("/api/aisensy/webhook")
async def aisensy_webhook(request: Request, token: str = ""):
    from diwan.providers import aisensy
    if not aisensy.token_ok(token):
        raise HTTPException(401, "bad token")
    for m in aisensy.parse(await request.json()):
        if m["text"]:
            reception.message(S.office, m["phone"], m["text"], name_=m["name"])
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
    return RedirectResponse("/web/office3d.html")


if WEB.exists():
    app.mount("/web", StaticFiles(directory=WEB), name="web")
