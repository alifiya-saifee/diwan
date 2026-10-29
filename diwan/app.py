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

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from diwan import demo, slots
from diwan.agents import nova, reception, scribe
from diwan.agents.charters import ROSTER
from diwan.config import env
from diwan.events import EventLog
from diwan.office import Office
from diwan.people import PEOPLE
from diwan.providers import meta, voice, whatsapp
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


@app.middleware("http")
async def fresh_pages(request: Request, call_next):
    """The app's pages and scripts are never cached, so a browser always shows the current version."""
    res = await call_next(request)
    if request.url.path.startswith("/web"):
        res.headers["Cache-Control"] = "no-cache, must-revalidate"
    return res


from diwan.brand_api import router as brand_router  # noqa: E402
app.include_router(brand_router)
from diwan.deal_desk import router as desk_router  # noqa: E402
app.include_router(desk_router)
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


@app.post("/api/marketing/run")
@app.post("/api/marketing/demo")
async def marketing_run(ref: str = "MC-1204"):
    """Run a listing through the studio for real; steps that lack a connection say what they need."""
    from diwan.agents import studio
    if f"listing:{ref}" not in g().nodes:
        raise HTTPException(404, "no such listing")
    asyncio.create_task(studio.run(S.office, ref))
    return {"started": ref}


@app.get("/api/studio")
def studio_view(ref: str = "MC-1204"):
    from diwan import costs
    from diwan.agents import analysis, strategy, studio
    from diwan.providers import instagram, meta
    blocked = {}
    for e in S.office.log.list():
        if e["type"] == "step.blocked":
            blocked[e["agent"]] = e["content"]["needs"]
        elif e["type"] in ("agent.pack", "content.made") and e["agent"] in blocked:
            blocked.pop(e["agent"])
    made = {k: studio.made(S.office, k, ref if k not in ("lanes", "slot", "playbook") else None)
            for k in ("ideas", "lanes", "film list", "script", "take check", "playbook", "cut", "remix plan", "post text", "cover", "slot", "versions", "transcript", "published")}
    reqs = [n for n in g().of("request", status="open") if n.props.get("agent") in ("mpub", "mcopy")]
    from diwan.providers import heygen
    return {"ref": ref, "connected": {"instagram": instagram.ready(), "meta": meta.ready(), "public_url": bool(env("PUBLIC_BASE_URL"))},
            "analysis": analysis.report(S.office), "board": studio.board(S.office), "made": made, "blocked": blocked,
            "footage": studio.footage(S.office, ref), "approvals": [{"id": n.id, "text": n.props["text"], "kind": n.props.get("kind"),
                           "options": [{k: x.get(k) for k in ("id", "angle", "why", "hook_en", "hook_ar", "lines_en", "via", "revises")}
                                       for x in studio.script_options(S.office, n.props["text"])] if n.props.get("kind") == "use_script" else []} for n in reqs],
            "strategy": strategy.report(S.office), "costs": costs.summary(),
            "script_approved": bool(studio.approved_script(S.office, ref)), "heygen": heygen.ready(),
            "listings": [{"ref": n.props["ref"], "title": n.props["title"], "permit": n.props.get("permit")} for n in g().of("listing")]}


class NamesIn(BaseModel):
    usernames: str
    by: str = "layla"


@app.post("/api/studio/competitors")
def set_competitors(body: NamesIn):
    S.office.log.append("setting.changed", actor=body.by, content={"person": "studio", "key": "competitors", "value": body.usernames})
    return {"ok": True}


@app.post("/api/studio/competitors/suggest")
def suggest_competitors():
    from diwan.agents import analysis
    try:
        return analysis.suggest(S.office)
    except Exception as e:  # the search failed: say so
        return {"ok": False, "needs": f"Search failed: {str(e)[:160]}"}


@app.get("/api/studio/import-template")
def import_template():
    from diwan.agents import studio
    return PlainTextResponse(studio.CSV_TEMPLATE, headers={"Content-Disposition": "attachment; filename=diwan-posts-template.csv"}, media_type="text/csv")


@app.post("/api/studio/import")
async def import_posts(file: UploadFile = File(...), by: str = Form("layla")):
    import csv
    import io
    from diwan.agents import studio
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    missing = [c for c in ("account", "likes", "comments") if rows and c not in rows[0]]
    if not rows or missing:
        raise HTTPException(422, f"Use the template: missing columns {', '.join(missing) or 'all'}")
    return studio.import_posts(S.office, rows, by=by)


class AIVideoIn(BaseModel):
    ref: str
    by: str = "maya"
    consent: bool = False


@app.post("/api/studio/ai-video")
async def make_ai_video(body: AIVideoIn):
    """A person starts an AI presenter video from the approved script, confirming the avatar's consent."""
    from diwan.agents import studio
    if not studio.approved_script(S.office, body.ref):
        raise HTTPException(409, "No approved script for this listing yet")
    if not body.consent:
        raise HTTPException(422, "Confirm that the person in the avatar agreed to it")
    asyncio.create_task(studio.ai_video(S.office, body.ref, by=body.by, consent=True))
    return {"started": body.ref}


@app.post("/api/studio/footage")
async def upload_footage(ref: str = Form(...), file: UploadFile = File(...), by: str = Form("omar")):
    from diwan.agents import studio
    from diwan.providers import meta
    meta.MEDIA.mkdir(exist_ok=True)
    n = 1 + sum(1 for e in S.office.log.list() if e["type"] == "footage.added")
    path = meta.MEDIA / f"footage-{ref}-{n}{Path(file.filename or 'clip.mp4').suffix or '.mp4'}"
    with path.open("wb") as f:
        while chunk := await file.read(1 << 20):
            f.write(chunk)
    S.office.log.append("footage.added", actor=by, content={"id": f"F{n}", "ref": ref, "path": str(path), "served": f"/media/{path.name}"})
    asyncio.create_task(studio.after_footage(S.office, ref))
    return {"id": f"F{n}"}


class DecideIn(BaseModel):
    decision: str  # approve | reject | revise (a script: change `choice` as the note says)
    by: str = "layla"
    note: str = ""
    choice: str | None = None  # which of the offered scripts


@app.post("/api/requests/{rid}/decide")
async def decide(rid: str, body: DecideIn):
    """A person answers an agent's request. Approving a publish request publishes, or says what is still missing."""
    from diwan.agents import studio
    n = g().nodes.get(rid)
    if not n or n.type != "request":
        raise HTTPException(404, "no such request")
    ref_of = next((x.props["ref"] for x in g().of("listing") if x.props["ref"] in n.props["text"]), None)
    if n.props.get("kind") == "use_script" and ref_of:
        offered = [x["id"] for x in studio.script_options(S.office, n.props["text"])]
        if body.choice and body.choice not in offered:
            raise HTTPException(400, f"{body.choice} is not one of the scripts offered ({', '.join(offered)})")
        if body.decision == "revise":
            if not body.choice or not (body.note or "").strip():
                raise HTTPException(400, "say which script to change and what to change")
            S.office.log.append("decision.made", actor=body.by, content={"card": rid, "answer": "revise", "choice": body.choice, "note": body.note})
            asyncio.get_event_loop().create_task(studio.script_revise(S.office, ref_of, body.choice, body.note, rid))
            return {"ok": True, "next": f"{body.choice} back to the Script writer with your change"}
        S.office.log.append("decision.made", actor=body.by, content={"card": rid, "answer": body.decision, "note": body.note, "choice": body.choice})
        asyncio.get_event_loop().create_task(studio.after_script(S.office, ref_of) if body.decision == "approve" else studio.script_rejected(S.office, ref_of, body.note))
        return {"ok": True, "next": "film list to the broker" if body.decision == "approve" else "back to the Script writer"}
    S.office.log.append("decision.made", actor=body.by, content={"card": rid, "answer": body.decision, "note": body.note})
    if body.decision == "approve" and n.props.get("kind") == "publish":
        ref = next((x.props["ref"] for x in g().of("listing") if x.props["ref"] in n.props["text"]), None)
        return studio.publish(S.office, ref, by=body.by) if ref else {"ok": False, "needs": ["a listing reference"]}
    return {"ok": True}


@app.get("/api/instagram/webhook")
def ig_verify(request: Request):
    p = dict(request.query_params)
    if p.get("hub.mode") == "subscribe" and env("IG_VERIFY_TOKEN") and p.get("hub.verify_token") == env("IG_VERIFY_TOKEN"):
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "verify token does not match")


@app.post("/api/instagram/webhook")
async def ig_receive(request: Request):
    from diwan.providers import instagram
    body = await request.body()
    if not whatsapp.signed(body, request.headers.get("x-hub-signature-256")):
        raise HTTPException(401, "bad signature")
    for c in instagram.parse_comments(await request.json()):
        if c["username"] and c["text"]:
            reception.message(S.office, f"ig:{c['username']}", c["text"], name_=f"@{c['username']}", comment_id=c["comment_id"])
    return {"ok": True}


@app.get("/api/brain/{dept}")
def dept_brain(dept: str):
    from diwan import brain
    if dept not in brain.DEPTS:
        raise HTTPException(404, "no such department")
    return brain.brain(S.office, dept)


@app.get("/api/costs")
def model_costs():
    from diwan import costs
    return costs.summary()


@app.get("/api/kpis/marketing")
def marketing_kpis():
    from diwan.agents import kpis
    return {"agents": kpis.measure(S.office), "rooms": kpis.team_tree()}


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
    """A fresh demo office. With a saved log, the old file is kept as a dated backup (logs are never rewritten)."""
    path = env("DIWAN_DB", ":memory:")
    if path != ":memory:" and Path(path).exists():
        S.office.log.db.close()
        Path(path).rename(f"{path}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak")
    S.office = Office(EventLog(path))
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
        "instagram": {"connected": all(is_set(k) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID")),
                      "fields": {k: is_set(k) for k in ("IG_ACCESS_TOKEN", "IG_USER_ID", "IG_VERIFY_TOKEN", "PUBLIC_BASE_URL")},
                      "webhook": f"{base}/api/instagram/webhook"},
        "heygen": {"connected": all(is_set(k) for k in ("HEYGEN_API_KEY", "HEYGEN_AVATAR_ID", "HEYGEN_VOICE_ID")),
                   "fields": {k: is_set(k) for k in ("HEYGEN_API_KEY", "HEYGEN_AVATAR_ID", "HEYGEN_VOICE_ID")}},
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


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="13" fill="none" stroke="#d4af6a" stroke-width="4"/></svg>'
    return Response(svg, media_type="image/svg+xml")


@app.get("/")
def root():
    return RedirectResponse("/web/office3d.html")


if WEB.exists():
    app.mount("/web", StaticFiles(directory=WEB), name="web")
(Path(__file__).resolve().parents[1] / "media").mkdir(exist_ok=True)
meta.MEDIA.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=meta.MEDIA), name="media")
