"""The HTTP and WebSocket API every screen uses. Run: .venv/bin/uvicorn diwan.app:app --port 8030

Everything a screen shows comes from the event log or the graph built from it; every action here goes through the same
office, agents and charters the tests exercise.
"""
from __future__ import annotations

import asyncio
import json
import re
import contextlib
from datetime import datetime
from pathlib import Path

import httpx

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from diwan import demo, sales, slots
from diwan import access
from diwan.agents import compliance, frontdesk, nova, reception, scribe
from diwan.agents.charters import ROSTER
from diwan.config import env
from diwan.events import EventLog
from diwan.office import Office
from diwan.people import PEOPLE
from diwan.providers import meta, portals, voice, whatsapp
from diwan.providers.chat import PROVIDERS

WEB = Path(__file__).resolve().parents[1] / "web"


class State:
    office: Office
    last_brief: str | None = None


S = State()


def fresh() -> Office:
    o = Office(EventLog(env("DIWAN_DB", ":memory:")))
    new = not o.log.list()
    if new:
        demo.seed(o)
    demo.catalog(o)
    demo.kinds(o)
    demo.projects(o)
    compliance.catch_up(o)  # deals recorded before a Compliance rule existed get it now (adds only what is missing)
    if new and env("DIWAN_DEMO_DAY") == "1":  # a public demo that starts fresh: a busy day, not an empty office
        from diwan import demo_day
        for miss in demo_day.run(o):
            print("demo day:", miss, flush=True)
    return o


S.office = fresh()


def frontdesk_alerts(office, now):
    from diwan.agents import watch
    return watch.alerts(office, now)


async def morning_loop():
    """Every minute: chase the Lobby board and the lead desk's Attention cards, do Nova's rounds 30 minutes before the
    earliest briefing time, and every 30 minutes read the listing feed when one is set."""
    from diwan import leads
    from diwan.agents import lobby, nudge, reminders
    ticks = 0

    def guarded(step: str, fn, *a):  # one job failing is logged and the rest still run
        try:
            return fn(*a)
        except Exception as e:  # noqa: BLE001
            S.office.log.append("step.blocked", actor="office-loop", content={"step": step, "needs": f"{type(e).__name__}: {e}"[:300]})

    while True:
        now = datetime.now(slots.DUBAI)
        gr = S.office.graph()
        first = min(nova.briefing_time(gr, p) for p in PEOPLE)
        if sales.brief_day(gr, now) and nova.briefing_due(now, S.last_brief, first, lead_minutes=30):
            nova.rounds(S.office, now)
            S.last_brief = now.date().isoformat()
        guarded("lobby", lobby.chase, S.office, now)
        from diwan import client_msgs, documents, lobby_room
        from diwan.agents import finance, watch
        guarded("documents", documents.sweep, S.office, now)  # the Deal desk: the ladder for documents still missing
        guarded("client messages", client_msgs.sweep, S.office, now)  # what quiet hours held
        if ticks % 30 == 0:
            guarded("finance reminders", finance.sweep, S.office, now)  # overdue invoices, instalments, rent cheques
            guarded("nova's watch", watch.sweep, S.office, now)  # the chief of staff chases what has stopped
            guarded("the lobby room", lobby_room.sweep, S.office, now)  # the week's threads, finished experiments, the month's tally
        guarded("leads", leads.sweep, S.office, now)
        guarded("follow-ups", nudge.sweep, S.office, now)  # follow-ups when a client goes quiet (the owner's schedule)
        guarded("reminders", reminders.sweep, S.office, now)  # appointment reminders; each broker's morning list
        guarded("sales", sales.sweep, S.office, now)  # the broker's list, reminders before calls, missing outcomes, the midday summary
        guarded("front desk", frontdesk.sweep, S.office, now)  # "remind me Thursday": at its time, once
        guarded("nova's alerts", frontdesk_alerts, S.office, now)  # what the owner should hear the moment it happens
        from diwan import ownerline
        from diwan.agents import triage
        guarded("the owner's whatsapp", triage.sweep, S.office, now)  # what matters on their own number, at the right moment
        if ticks % 1440 == 0:
            guarded("personal messages past their time", ownerline.prune, now)
        from diwan.agents import rhythm, studio
        await asyncio.to_thread(guarded, "planning ahead", rhythm.plan_due, S.office)  # this week and next, when the Marketing manager turned it on
        if (ref := rhythm.due(S.office)):  # the studio's automatic run, when the Marketing manager turned it on
            asyncio.create_task(studio.run(S.office, ref, auto=not rhythm.approved(S.office, ref)))  # a day a person approved needs no second yes
        await asyncio.to_thread(guarded, "scheduled posts", studio.publish_due, S.office)  # approved posts go out at their time
        await asyncio.to_thread(__import__("diwan.agents.marketing", fromlist=["tick"]).tick, S.office)  # tracing, posts following the facts, the day's lists
        if ticks % 60 == 0 and __import__("diwan.occasions", fromlist=["research_due"]).research_due(S.office):  # the business's occasions, researched for its country
            asyncio.create_task(asyncio.to_thread(guarded, "occasions research", __import__("diwan.occasions", fromlist=["research"]).research, S.office))
        if rhythm.refresh_due(S.office):  # the daily refresh of competitor posts, when the Marketing manager turned it on
            asyncio.create_task(asyncio.to_thread(studio.refresh_competitors, S.office, by="mrival", auto=True))
        if env("LISTING_FEED_URL") and ticks % 30 == 0:
            try:
                xml = await asyncio.to_thread(portals.fetch_feed)
                leads.sync_listings(S.office, xml)
            except (portals.PortalError, httpx.HTTPError) as e:
                S.office.log.append("step.blocked", actor="portal-feed", content={"step": "listing feed", "needs": str(e)[:300]})
        ticks += 1
        await asyncio.sleep(60)


async def custom_loop():
    """Every few seconds: the agents the owner added hand new triggers to their person (diwan/agents/custom.py)."""
    from diwan.agents import custom
    while True:
        try:
            await asyncio.to_thread(custom.run_pending, S.office)
        except Exception as e:  # noqa: BLE001  a bad turn must not stop the loop
            S.office.log.append("agent.failed", actor="custom-agents", content={"error": str(e)[:300]})
        await asyncio.sleep(3)


@contextlib.asynccontextmanager
async def lifespan(_):
    S.last_brief = None
    task, task2 = asyncio.create_task(morning_loop()), asyncio.create_task(custom_loop())
    yield
    task.cancel()
    task2.cancel()


app = FastAPI(title="Diwan", lifespan=lifespan)
app.include_router(access.router)
from diwan.brand_api import router as brand_router  # noqa: E402
app.include_router(brand_router)
from diwan.knowledge_api import router as knowledge_router  # noqa: E402
app.include_router(knowledge_router)
from diwan.lobby_api import router as lobby_room_router  # noqa: E402
app.include_router(lobby_room_router)
from diwan.deal_desk import router as desk_router  # noqa: E402
app.include_router(desk_router)
from diwan.floor import router as floor_router  # noqa: E402
app.include_router(floor_router)


@app.middleware("http")
async def fresh_pages(request: Request, call_next):
    """The app's pages and scripts are never cached, so a browser always shows the current version."""
    res = await call_next(request)
    if request.url.path.startswith("/web"):
        res.headers["Cache-Control"] = "no-cache, must-revalidate"
    return res


def g():
    return S.office.graph()


def node_json(gr, n) -> dict:
    return {"id": n.id, "type": n.type, "label": n.label, "status": n.status, "deal": n.deal, "record": gr.record(n.id), "event": n.event,
            "props": {k: v for k, v in n.props.items() if k != "messages"}}


# ---------- what is plugged in ----------

@app.get("/api/health")
def health():
    return {"ok": True, "providers": {p.id: p.available() for p in PROVIDERS.values()}, "voice": voice.available(),
            "whatsapp": whatsapp.available(), "events": len(S.office.log.list())}


@app.get("/api/roster")
def roster():
    from dataclasses import asdict

    from diwan.agents import custom
    mine = [asdict(custom.charter(a)) | {"custom": True, "status": a["status"]} for a in g().custom_agents.values() if a["status"] != "removed"]
    return [asdict(c) for c in ROSTER] + mine


class AgentIn(BaseModel):
    by: str
    name: str = ""
    role: str = ""
    job: str = ""
    trigger: str = ""
    team: str = ""
    to: str = ""


@app.get("/api/memory/agents")
def memory_agents(upto: int | None = None):
    """The Memory screen's Agents view: every agent, who it reports to, and the handoffs the log shows."""
    from diwan.agents import custom
    return custom.connections(S.office, upto)


@app.get("/api/memory/flow")
def memory_flow(upto: int | None = None):
    """The Memory screen's Agents view: departments, their agents, and the numbered flows between them."""
    from diwan.agents import custom
    return custom.office_flow(S.office, upto)


@app.post("/api/agents/custom")
def agent_add(body: AgentIn):
    from diwan.agents import custom
    try:
        return custom.add(S.office, body.model_dump(), by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/agents/custom/{aid}/{what}")
def agent_change(aid: str, what: str, body: AgentIn):
    from diwan.agents import custom
    try:
        return custom.change(S.office, aid, what, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except KeyError:
        raise HTTPException(404, "no such agent") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/marketing/run")
@app.post("/api/marketing/demo")
async def marketing_run(ref: str = "MC-1204"):
    """Run a listing through the studio for real; steps that lack a connection say what they need."""
    from diwan.agents import studio
    from diwan import products, topics
    if f"listing:{ref}" not in g().nodes and ref not in products.items(S.office) and not topics.get(S.office, ref):
        raise HTTPException(404, "no such listing, product or topic")
    asyncio.create_task(studio.run(S.office, ref))
    return {"started": ref}


@app.get("/api/studio")
def studio_view(ref: str = "MC-1204"):
    from diwan import business, costs
    from diwan.agents import analysis, approvers, freevideo, journey, marketing, planner, rhythm, strategy, studio, taste
    from diwan.providers import instagram, meta
    blocked = {}
    for e in S.office.log.list():
        if e["type"] == "step.blocked":
            blocked[e["agent"]] = e["content"]["needs"]
        elif e["type"] in ("agent.pack", "content.made") and e["agent"] in blocked:
            blocked.pop(e["agent"])
    made = {k: studio.made(S.office, k, ref if k not in ("lanes", "slot", "playbook") else None)
            for k in ("ideas", "lanes", "film list", "script", "take check", "playbook", "cut", "remix plan", "post text", "cover", "slot", "versions", "transcript", "published", "slides")} | {"scheduled": __import__("diwan.agents.studio", fromlist=["scheduled"]).scheduled(S.office).get(ref)}
    reqs = [n for n in g().of("request", status="open") if n.props.get("agent") in ("mpub", "mcopy") and ref in n.props["text"]]  # this post's: another post's card is never pressed by mistake
    from diwan.providers import heygen
    ig = instagram.check(wait=False)  # green only when Instagram accepts the token, not merely when one is set
    return {"ref": ref, "connected": {"instagram": ig["ok"], "instagram_user": ig.get("username"), "instagram_why": ig.get("why"),
                                      "meta": meta.ready(), "public_url": bool(env("PUBLIC_BASE_URL"))},
            "analysis": analysis.report(S.office), "board": studio.board(S.office), "made": made, "blocked": blocked,
            "ads": [b for b in studio.board(S.office) if b["kind"] == "ad"],
            "ad_library": {n.lower(): studio.ad_library_url(n, business.get(S.office)["country"]) for n in studio.competitors(g())},
            "business": business.get(S.office) | {"missing": business.missing(S.office), "platforms_known": list(studio.LIMITS)},
            "refresh": {"last": rhythm.last_refresh(S.office), "next": rhythm.next_refresh(S.office)},
            "rhythm": {"settings": rhythm.settings(S.office), "next": rhythm.next_run(S.office), "plan": rhythm.current(S.office),
                       "started": sorted(rhythm.started(S.office)), "stages": marketing.stage_labels(S.office),
                       "evidence": planner.evidence(S.office, [d["ref"] for d in (rhythm.current(S.office) or {}).get("days", []) if d.get("ref")])},
            "footage": studio.footage(S.office, ref), "approvals": [{"id": n.id, "text": n.props["text"], "kind": n.props.get("kind"),
                           "options": [{k: x.get(k) for k in ("id", "angle", "why", "hook_en", "hook_ar", "lines_en", "via", "revises", "cards", "built_like", "own", "problems", "shots", "format", "slides", "director", "visual")} | {"stale": studio.stale(S.office, x), "look": __import__("diwan.agents.visual", fromlist=["describe"]).describe(x.get("visual"))}
                                       for x in studio.script_options(S.office, n.props["text"])] if n.props.get("kind") == "use_script" else []} for n in reqs],
            "strategy": strategy.report(S.office), "journey": journey.report(S.office), "costs": costs.summary(),
            "script_approved": bool(studio.approved_script(S.office, ref)), "heygen": heygen.ready(), "stopped": studio.stopped(S.office, ref),
            "making": studio.progress(S.office, ref), "making_refs": sorted(studio.RUNNING), "stuck": studio.stuck(S.office, ref),
            "chain": studio.chain(S.office, ref),
            "brand_voice": __import__("diwan.brand", fromlist=["profile"]).profile(S.office)["voice"]["value"],
            "approvers": {r: {"id": w, "label": approvers.label(S.office, r)} for r, w in approvers.get(S.office).items()},
            "others": [w for w in marketing.waiting(S.office) if w["ref"] != ref],
            "free_video": {"missing": freevideo.missing(), "photos": len(freevideo.photos(S.office, ref)), "voice": freevideo.voice(),
                           "photo_urls": [u for u in map(freevideo.served, freevideo.photos(S.office, ref)) if u],
                           "can_draw": freevideo.can_draw(S.office, ref), "frames": freevideo.AI_FRAMES, "review": freevideo.frame_review(S.office, ref), "doubt": taste.doubts_pictures(S.office)},
            "listings": [{"ref": p["ref"], "title": p["title"], "permit": p.get("permit"), "kind": p.get("kind")} for p in __import__("diwan.products", fromlist=["items"]).items(S.office).values()]
            + [{"ref": t["ref"], "title": t["title"], "permit": None, "kind": "topic"} for t in [*journey.items(S.office).values(), *__import__("diwan.topics", fromlist=["items"]).items(S.office).values()]]
            + [{"ref": n.props["ref"], "title": n.props["title"], "permit": n.props.get("permit"), "kind": "listing"} for n in g().of("listing")],
            "permit_needed": business.permit_needed(S.office),
            "topics": {"typed": __import__("diwan.topics", fromlist=["typed"]).typed(S.office),
                       "available": {k: sum(1 for t in __import__("diwan.topics", fromlist=["items"]).items(S.office).values() if t["source"] == k) for k in ("card", "product", "typed")},
                       "derived": [{"ref": t["ref"], "title": t["title"], "source": t["source"], "facts": len(t["features"]), "used": not t.get("excluded")}
                                   for t in __import__("diwan.topics", fromlist=["items"]).items(S.office, all_=True).values() if t["source"] != "typed"]}}


class NamesIn(BaseModel):
    usernames: str = ""     # the whole list (Undo puts a list back)
    add: str | None = None  # or one account to add, or one to remove: two quick clicks never overwrite each other
    remove: str | None = None
    by: str = "layla"


class OwnScriptIn(BaseModel):
    ref: str
    text: str
    by: str = "maya"


@app.post("/api/studio/own-script")
async def own_script(body: OwnScriptIn):
    """The Marketing manager's own script: checked, then told two other ways; all three wait to be picked."""
    from diwan.agents import studio
    from diwan import products, topics
    if f"listing:{body.ref}" not in g().nodes and body.ref not in products.items(S.office) and body.ref not in topics.items(S.office):
        raise HTTPException(404, f"no listing, product or topic {body.ref}")
    try:
        r = await asyncio.to_thread(studio.own_script, S.office, body.ref, body.text, by=body.by)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "problems": r["own"]["problems"], "others": len(r["others"])}


class AdIn(BaseModel):
    account: str
    url: str
    started: str
    text: str
    ended: str | None = None
    by: str = "maya"


@app.post("/api/studio/ads/pin")
def pin_ad(body: AdIn):
    """A competitor ad a person saw in the Ad Library, pinned on the research board (no numbers exist for it)."""
    from diwan.agents import studio
    try:
        return {"ok": True, "card": studio.pin_ad(S.office, **body.model_dump())}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


class UnpinIn(BaseModel):
    card: str
    by: str = "maya"


@app.post("/api/studio/ads/unpin")
def unpin_ad(body: UnpinIn):
    from diwan.agents import studio
    try:
        studio.unpin(S.office, body.card, by=body.by)
        return {"ok": True}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/studio/competitors")
def set_competitors(body: NamesIn):
    """Save the list; an account that was not on it before is fetched straight away (free: no model call)."""
    from diwan.agents import studio
    from diwan.providers import instagram
    before = set(studio.competitors(g()))
    names = studio.competitors(g())
    if body.add:
        u = body.add.strip().lstrip("@").lower()
        names = names if u in {n.lower() for n in names} else [*names, u]
    elif body.remove:
        names = [n for n in names if n.lower() != body.remove.strip().lstrip("@").lower()]
    value = ", ".join("@" + n for n in names) if (body.add or body.remove) else body.usernames
    S.office.log.append("setting.changed", actor=body.by, content={"person": "studio", "key": "competitors", "value": value})
    new = [u for u in studio.competitors(g()) if u not in before]
    if not new or not instagram.ready():
        return {"ok": True, "new": new, "fetched": False}
    after = S.office.log.list()[-1]["id"]
    studio.watch(S.office, None, only=new)
    checks = {e["content"]["account"]: e["content"] for e in S.office.log.list(after=after) if e["type"] == "competitor.checked"}
    reached = [u for u in new if checks.get(u, {}).get("ok")]
    return {"ok": True, "new": new, "fetched": True, "reached": reached, "not_reached": [u for u in new if u not in reached],
            "says": "; ".join(f"@{u}: " + (f"{checks[u].get('followers') or 0:,} followers, {checks[u].get('posts_read')} posts read" if u in reached
                                          else checks.get(u, {}).get("error", "not checked")) for u in new)}


@app.get("/api/studio/competitors/lookup")
def lookup_competitor(u: str):
    """A preview of an exact Instagram handle while it is typed: who it is, or why it can't be read. Free (no model)."""
    import re as _re
    from diwan.providers import instagram
    h = u.strip().lstrip("@").lower()
    if not _re.fullmatch(r"[a-z0-9_.]{1,30}", h):
        return {"ok": False, "why": "Letters, numbers, dots and underscores only, up to 30."}
    if not instagram.ready():
        return {"ok": None, "why": "Instagram is not connected, so it can't be checked yet."}
    try:
        acc = instagram.competitor_posts(h, limit=1)
    except instagram.InstagramError:
        return {"ok": False, "why": "Not found, or a personal account (Instagram only shares business and creator accounts)."}
    return {"ok": True, "handle": acc["username"], "name": acc.get("name"), "followers": acc.get("followers"), "posts": acc.get("media_count"),
            "avatar": acc.get("avatar"), "bio": (acc.get("bio") or "")[:160]}


@app.post("/api/studio/competitors/suggest")
def suggest_competitors(body: dict | None = None):
    from diwan.agents import analysis
    body = body or {}
    try:
        return analysis.suggest(S.office, exclude=tuple(str(x) for x in body.get("exclude", []))[:60], round=max(0, int(body.get("round", 0))))
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
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {"ok": False, "problems": ["This is not a CSV file. In your spreadsheet, choose Save as / Download → CSV, then import that file."]}
    reader = csv.DictReader(io.StringIO(text))
    rows = [{(k or "").strip().lower(): v for k, v in r.items()} for r in reader]
    if (problems := studio.check_import(reader.fieldnames or [], rows)):
        return {"ok": False, "problems": problems[:20], "more": max(0, len(problems) - 20)}  # nothing is imported until the file is right
    return {"ok": True} | studio.import_posts(S.office, rows, by=by)


@app.get("/api/studio/import-sample")
def import_sample():
    from diwan.agents import studio
    return {"columns": studio.CSV_SAMPLE}


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


@app.post("/api/studio/photos")
async def upload_photos(ref: str = Form(...), files: list[UploadFile] = File(...), by: str = Form("maya")):
    """Photos of a listing for the free video (the listing's own photos from the feed are used too), or of a moment."""
    from diwan import topics
    from diwan.providers import meta
    if f"listing:{ref}" not in g().nodes and not topics.get(S.office, ref):
        raise HTTPException(404, f"no listing or moment {ref}")
    meta.MEDIA.mkdir(exist_ok=True)
    n, paths = sum(1 for e in S.office.log.list() if e["type"] == "photos.added"), []
    for i, f in enumerate(files):
        if not (f.content_type or "").startswith("image/"):
            raise HTTPException(400, f"{f.filename} is not a picture")
        path = meta.MEDIA / f"photo-{ref}-{n + 1}-{i + 1}{Path(f.filename or 'p.jpg').suffix or '.jpg'}"
        path.write_bytes(await f.read())
        paths.append(str(path))
    S.office.log.append("photos.added", actor=by, content={"ref": ref, "paths": paths})
    return {"ok": True, "added": len(paths)}


class FreeVideoIn(BaseModel):
    ref: str
    by: str = "maya"


@app.post("/api/studio/free-video")
async def free_video(body: FreeVideoIn):
    """The free video: the computer's voice over the listing's photos, then the usual editing."""
    from diwan.agents import freevideo, studio
    r = await asyncio.to_thread(freevideo.make, S.office, body.ref, by=body.by)
    if r.get("ok"):
        asyncio.create_task(studio.after_footage(S.office, body.ref))
    return r


@app.post("/api/studio/ai-frames")
async def ai_frames(body: FreeVideoIn):
    """Muse Image draws the frames for a post about the brand or a topic, ready for the free video."""
    from diwan.agents import freevideo
    return await asyncio.to_thread(freevideo.ai_frames, S.office, body.ref, by=body.by)


class DecideIn(BaseModel):
    decision: str  # approve | reject | revise (a script: change `choice` as the note says)
    by: str = "layla"
    note: str = ""
    choice: str | None = None  # which of the offered scripts
    at: str | None = None  # a publishing time the person chose


class EditPictureIn(BaseModel):
    ref: str
    picture: str
    note: str = ""
    after: str = ""
    by: str = "layla"


@app.post("/api/studio/edit-picture")
async def edit_picture(body: EditPictureIn):
    """Muse Image edits one picture of a post with the person's words. Nothing in the post changes yet."""
    from diwan.agents import studio
    return await asyncio.to_thread(studio.edit_picture, S.office, body.ref, body.picture, body.note, by=body.by)


@app.post("/api/studio/edit-picture/use")
def use_edited_picture(body: EditPictureIn):
    """The edited picture replaces the old one in the post."""
    from diwan.agents import studio
    return studio.use_edit(S.office, body.ref, body.picture, body.after, body.note, by=body.by)


class StuckIn(BaseModel):
    choice: str
    by: str = "layla"


@app.post("/api/studio/stuck/{did}")
def studio_stuck(did: str, body: StuckIn):
    """The answer to work that failed review three times: Fix it myself, Accept as is, or Stop this reel."""
    from diwan.agents import studio
    return studio.resolve_stuck(S.office, did, body.choice, by=body.by)


@app.post("/api/requests/{rid}/decide")
async def decide(rid: str, body: DecideIn):
    """A person answers an agent's request. Approving a publish request publishes, or says what is still missing."""
    from diwan.agents import studio
    from diwan.agents import approvers, marketing
    from diwan.agents.charters import get as get_charter
    n = g().nodes.get(rid)
    if not n or n.type != "request":
        raise HTTPException(404, "no such request")
    if n.status != "open":  # a card already answered or replaced: the page was showing an old one
        return {"ok": False, "needs": ["this card was already answered or replaced: look at the newest one"]}
    role = {"use_script": "script", "approve_brief": "script", "publish": "publish"}.get(n.props.get("kind"))
    who = approvers.get(S.office)[role] if role else None
    if who and body.by != who and not access.is_owner(body.by):  # the person named in Setup, or the owner
        raise HTTPException(403, f"This waits for {approvers.label(S.office, role)}.")
    options = studio.script_options(S.office, n.props["text"]) if n.props.get("kind") == "use_script" else []
    # the scripts say what they are for: a listing, a product, a topic or a post about the brand
    ref_of = options[0]["ref"] if options else next((x.props["ref"] for x in g().of("listing") if x.props["ref"] in n.props["text"]), None)
    if n.props.get("kind") == "use_script" and ref_of:
        offered = [x["id"] for x in options]
        if body.choice and body.choice not in offered:
            raise HTTPException(400, f"{body.choice} is not one of the scripts offered ({', '.join(offered)})")
        wrong = next((x.get("problems") for x in options if x["id"] == body.choice and x.get("problems")), None)
        if wrong and body.decision == "approve":
            return {"ok": False, "needs": wrong}
        if body.decision == "revise":
            if not body.choice or not (body.note or "").strip():
                raise HTTPException(400, "say which script to change and what to change")
            S.office.log.append("decision.made", actor=body.by, content={"card": rid, "answer": "revise", "choice": body.choice, "note": body.note})
            asyncio.get_event_loop().create_task(studio.script_revise(S.office, ref_of, body.choice, body.note, rid))
            return {"ok": True, "next": f"{body.choice} back to the Script writer with your change"}
        S.office.log.append("decision.made", actor=body.by, content={"card": rid, "answer": body.decision, "note": body.note, "choice": body.choice})
        from diwan.agents import taste
        for x in options:  # the one picked over the ones passed by
            taste.signal(S.office, ref_of, 1 if x["id"] == body.choice and body.decision == "approve" else 0, "script", by=body.by, extra=taste.script_features(x),
                         strength=1.0 if x["id"] == body.choice or body.decision != "approve" else 0.3, why=body.note if x is options[0] and body.decision != "approve" else "")
        asyncio.get_event_loop().create_task(studio.after_script(S.office, ref_of) if body.decision == "approve" else studio.script_rejected(S.office, ref_of, body.note))
        filmed = "reel" in marketing.format_of(S.office, ref_of).lower()
        return {"ok": True, "next": ("film list to the broker" if filmed else "the pictures are being made, then it waits for your approval") if body.decision == "approve" else "back to the Script writer"}
    said = re.match(r"Publish the (\S+) ", n.props["text"]) if n.props.get("kind") == "publish" else None
    if said and body.decision == "approve":  # it counts once it can happen: a refused yes leaves the post waiting for a person
        r = studio.publish(S.office, said.group(1), by=body.by) if body.note == "now" else studio.approve_post(S.office, said.group(1), by=body.by, at=body.at)
        if not r.get("ok"):
            return r
    S.office.log.append("decision.made", actor=body.by, content={"card": rid, "answer": body.decision, "note": body.note})
    if said and body.decision in ("approve", "reject", "revise"):  # the finished post is the strongest yes or no
        from diwan.agents import freevideo, taste
        taste.signal(S.office, said.group(1), 1 if body.decision == "approve" else 0, "publish", by=body.by, why=body.note, strength=1.5 if body.decision != "revise" else 0.5,
                     extra=["picture:ai illustrations"] if freevideo.frame_review(S.office, said.group(1)) else None)
    if said and body.decision == "revise":  # the finished post: the change goes to whoever can fix it
        if not (body.note or "").strip():
            raise HTTPException(400, "say what to change")
        ref = said.group(1)
        who = studio.change_goes_to(studio.approved_script(S.office, ref), body.note)
        asyncio.get_event_loop().create_task(studio.change_post(S.office, ref, body.note))
        return {"ok": True, "next": f"your change is with the {get_charter(who).name}"}
    brief = re.match(r"Approve the brief for (\S+):", n.props["text"]) if n.props.get("kind") == "approve_brief" else None
    if brief and body.decision == "approve":
        asyncio.get_event_loop().create_task(studio.after_brief(S.office, brief.group(1)))
        return {"ok": True, "next": "the Script writer starts on it"}
    if body.decision == "reject" and (said or brief):  # stopped by a person: it comes off, and no list shows it as waiting
        from diwan.agents import marketing
        marketing.withdraw(S.office, (said or brief).group(1), body.note or f"stopped by {body.by}")
        return {"ok": True, "next": "it is off the plan"}
    if said and body.decision == "approve":
        return r
    if body.decision == "approve" and n.props.get("kind") == "publish":
        return {"ok": False, "needs": ["a listing reference"]}
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
            reception.message(S.office, f"ig:{c['username']}", c["text"], name_=f"@{c['username']}", comment_id=c["comment_id"], media_id=c.get("media_id"))
            __import__("diwan.agents.marketing", fromlist=["comment"]).comment(S.office, f"ig:{c['username']}", c.get("media_id"))
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
    from diwan import qualify
    if (who := access.USER.get()) and who not in qualify.owner_ids():
        raise HTTPException(403, "Only the owner resets the office")
    path = env("DIWAN_DB", ":memory:")
    old = S.office.log
    with old.lock:  # a page reading the log in another thread must not have the file closed and renamed under it
        if path != ":memory:" and Path(path).exists():
            old.db.close()
            bak = f"{path}.{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
            Path(path).rename(bak)
            for side in ("-wal", "-shm"):  # SQLite's journal files go with it, or the new log would read the old journal
                if Path(path + side).exists():
                    Path(path + side).rename(bak + side)
        S.office = Office(EventLog(path))
    demo.seed(S.office)
    demo.catalog(S.office)
    demo.kinds(S.office)
    demo.projects(S.office)
    if correction:
        demo.correction(S.office)
    elif env("DIWAN_DEMO_DAY") == "1":
        from diwan import demo_day
        for miss in demo_day.run(S.office):
            print("demo day:", miss, flush=True)
    return {"events": len(S.office.log.list())}


# ---------- the log and the graph ----------

@app.get("/api/events")
def events(deal: str | None = None, agent: str | None = None, after: int = 0):
    return access.visible(S.office.log.list(deal=deal, agent=agent, after=after))


@app.get("/api/graph")
def graph(deal: str | None = None, upto: int | None = None):
    gr = S.office.graph(upto)
    keep = {n.id for n in gr.nodes.values() if deal is None or n.deal in (deal, None) or n.type == "person"}
    steps = [e["id"] for e in S.office.log.list() if deal and e.get("deal") == deal]  # the slider steps through this deal only
    return {"last_event": gr.last_event, "steps": steps,
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
                if seen := access.visible(new):
                    await ws.send_json({"events": seen})
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


# ---------- the Front Desk: each signed-in person's PA ----------

class PaIn(BaseModel):
    person: str = "layla"
    text: str = ""
    session: str | None = None
    voice: bool = False
    history: list[dict] | None = None
    mode: str | None = None


def _me(person: str) -> str:
    return access.USER.get() or person


@app.post("/api/pa/say")
def pa_say(body: PaIn):
    """The chat box on every page: the signed-in person's own PA."""
    return frontdesk.say(S.office, body.text, _me(body.person), session=body.session, voice=body.voice, history=body.history)


@app.get("/api/pa/heads-up")
def pa_heads_up(person: str = "layla", after: int = 0, after_private: int = 0):
    """What Nova has to tell this person without being asked; a live call says it out loud."""
    from diwan.agents import frontdesk, triage, watch
    from diwan import novaline
    me = _me(person)
    out = watch.headsups(S.office.log, me, after)
    if frontdesk.is_owner(me):  # kept in the private store, so it has its own count
        novaline.seen(datetime.now(slots.DUBAI))
        out += triage.headsups(after_private)
    return out


@app.get("/api/pa/day")
def pa_day(person: str = "layla"):
    return frontdesk.day(S.office, _me(person), datetime.now(slots.DUBAI))


@app.post("/api/pa/arrive")
def pa_arrive(body: PaIn):
    """The first open of the day: a greeting and the top three."""
    return frontdesk.arrive(S.office, _me(body.person), datetime.now(slots.DUBAI))


@app.post("/api/pa/mode")
def pa_mode(body: PaIn):
    try:
        who = _me(body.person)
        if body.mode == "meeting":
            return frontdesk.start_pocket(S.office, who)
        if body.mode == "normal" and frontdesk.mode(g(), who) == "meeting":
            return frontdesk.end_pocket(S.office, who, datetime.now(slots.DUBAI))
        return {"mode": frontdesk.set_mode(S.office, who, body.mode or "")}
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/pa/errands/{eid}/{what}")
def pa_errand(eid: str, what: str, body: PaIn):
    """A person's yes, or no, to a draft. Nothing else moves an errand on."""
    if what not in ("confirm", "cancel"):
        raise HTTPException(404, "no such step")
    try:
        return frontdesk.decide_errand(S.office, eid, by=_me(body.person), yes=what == "confirm")
    except KeyError:
        raise HTTPException(404, "no such errand") from None


@app.post("/api/pa/notes")
def pa_note(body: PaIn):
    return {"added": frontdesk.add_notes(S.office, _me(body.person), body.text)}


@app.post("/api/pa/notes/{nid}/done")
def pa_note_done(nid: str, body: PaIn):
    try:
        frontdesk.finish_note(S.office, nid, by=_me(body.person))
    except KeyError:
        raise HTTPException(404, "no such note") from None
    return {"ok": True}


@app.post("/api/pa/reminders/{tid}/done")
def pa_reminder_done(tid: str, body: PaIn):
    try:
        frontdesk.finish_reminder(S.office, tid, by=_me(body.person))
    except KeyError:
        raise HTTPException(404, "no such reminder") from None
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    return {"ok": True}


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
    try:
        return lobby.done(S.office, lid, by=body.by, note=body.note)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None


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
    from diwan.agents import followup, steps, visit
    ev = S.office.end_meeting(mid)
    m = S.office.meeting(mid)
    if not ev.get("duplicate"):  # the meeting just ended: the visit summary, then the follow-up built on it, for the broker
        visit.from_meeting(S.office, mid, cause=ev["id"])
        followup.draft(S.office, m["deal"], why="after the meeting", cause=ev["id"])
    found = steps.propose(S.office, mid, cause=ev["id"])  # what was agreed at the table, for a person to approve
    chat = followup._chat(g(), m["deal"])
    return m | {"followup": followup.current(g(), m["deal"]), "visit": visit.latest(g(), m["deal"]), "chat": chat.props["phone"] if chat else None,
                "steps": found, "people": [{"id": k, "name": p["name"], "role": p["role"]} for k, p in PEOPLE.items()]}


class StepsIn(BaseModel):
    rows: list[dict]
    by: str = "layla"


@app.get("/api/meetings/{mid}/steps")
def meeting_steps(mid: str):
    from diwan.agents import steps
    return steps.latest(S.office, mid) or {}


@app.post("/api/meetings/{mid}/steps/approve")
def approve_steps(mid: str, body: StepsIn):
    from diwan.agents import steps
    try:
        return steps.approve(S.office, mid, body.rows, by=_me(body.by))
    except KeyError:
        raise HTTPException(404, "This meeting has no list yet: end the meeting first.") from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


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

    roles: dict[str, str] = {}

    def on_turn(t: dict):
        if "final" in t:
            who = scribe.role_of(roles, t["speaker"], t["final"])
            res = scribe.turn(S.office, mid, who, t["final"], turn_id=t.get("turn"))
            loop.create_task(ws.send_json({"final": t["final"], "speaker": "Client" if who == "customer" else "Broker", "facts": res["facts"]}))
        else:
            loop.create_task(ws.send_json(t))

    relay = asyncio.create_task(voice.stream(chunks(), on_turn))
    try:
        while True:
            msg = await ws.receive()
            if msg.get("bytes"):
                await q.put(msg["bytes"])
            elif msg.get("text") == "swap":
                roles.update({k: "broker" if v == "customer" else "customer" for k, v in roles.items()})
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
    agent: str | None = None
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
            "stages": inbox.stage_names(g())}


@app.get("/api/chats/{phone}")
def chat_detail(phone: str):
    from diwan import inbox
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    return inbox.detail(S.office, phone) | {"quick": inbox.quick_replies(g())}


def reply_wait() -> float:
    """Seconds Rania waits after a message for the next one, so a burst gets one reply (0: each at once)."""
    try:
        return max(0.0, min(30.0, float(env("DIWAN_REPLY_WAIT") or 4)))
    except ValueError:
        return 4.0


async def client_message(phone: str, text: str, name: str | None = None, mid: str | None = None) -> dict:
    """A client's message: kept at once; after a short wait, one reply to everything they sent since the office last
    wrote. If another message arrives meanwhile, that one answers (this returns {"merged": true}). Someone from the office
    writing to the sales number is not a client: no lead, and Rania stays out."""
    from diwan import contacts
    if contacts.person_by_phone(S.office, phone):
        await asyncio.to_thread(reception.line_only, phone, "This number is for clients. Please use the office app.")
        return {"merged": False, "reply": None, "mode": "staff"}
    r = await asyncio.to_thread(reception.receive, S.office, phone, text, name_=name, mid=mid)
    if r.get("duplicate"):  # WhatsApp sent it twice: it has been answered
        return {"merged": True, "reply": None, "mode": "ai"}
    if (wait := reply_wait()):
        await asyncio.sleep(wait)
    if any(m["type"] == "received" and m["event"] > r["got"]["id"] for m in g().nodes[f"chat:{phone}"].props["messages"]):
        return {"merged": True, "reply": None, "mode": "ai"}
    return await asyncio.to_thread(reception.message, S.office, phone, text, name_=name, received=r)


async def _later(work) -> None:
    """A webhook is acknowledged at once; with a wait, the reply follows in the background."""
    if reply_wait():
        asyncio.create_task(work)
    else:
        await work


@app.post("/api/chats/incoming")
async def incoming(body: ChatIn):
    """The sandbox phone: the same path a real WhatsApp message takes."""
    return await client_message(body.phone, body.text, body.name)


@app.post("/api/chats/{phone}/send")
def person_send(phone: str, body: SendIn):
    try:
        return reception.person_sends(S.office, phone, body.text, by=body.by)
    except (reception.WindowClosed, reception.OptedOut) as e:
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
    reason: str = ""


@app.post("/api/chats/{phone}/stage")
def chat_stage(phone: str, body: StageIn):
    """A person moves the lead, under the Deal desk's rules (a reason for Lost or moving back)."""
    from diwan import inbox
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    try:
        inbox.set_stage(S.office, phone, body.stage, by=body.by, reason=body.reason)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"ok": True}


class HotIn(BaseModel):
    by: str
    on: bool = True
    note: str = ""


@app.post("/api/chats/{phone}/hot")
def chat_hot(phone: str, body: HotIn):
    """The broker (or the owner) marks the lead hot, or not."""
    from diwan import leads
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    try:
        leads.mark_hot(S.office, phone, on=body.on, by=body.by, note=body.note)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    return {"ok": True}


class NoCallsIn(BaseModel):
    by: str
    on: bool = True


@app.post("/api/chats/{phone}/no-calls")
def chat_no_calls(phone: str, body: NoCallsIn):
    """The client asked not to be called: Rania never offers a call, and call cards become reply cards."""
    from diwan import leads
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    try:
        leads.set_no_calls(S.office, phone, on=body.on, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    return {"ok": True}


class LeadFollowIn(BaseModel):
    by: str
    after_hours: list[float] | None = None
    stopped: bool = False


@app.post("/api/chats/{phone}/followups")
def chat_followups(phone: str, body: LeadFollowIn):
    """This lead's own follow-up schedule, stopped for this lead, or back on the office's (neither given)."""
    from diwan.agents import nudge
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    try:
        return {"followups": nudge.set_for_lead(S.office, phone, by=body.by, after_hours=body.after_hours, stopped=body.stopped)}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class MergeIn(BaseModel):
    by: str
    other: str


@app.post("/api/chats/{phone}/merge")
def chat_merge(phone: str, body: MergeIn):
    """The same person on two numbers or accounts: one lead from now on."""
    from diwan import leads
    try:
        return leads.merge(S.office, phone, body.other, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class FollowAtIn(BaseModel):
    by: str
    at: str
    kind: str = "call"
    note: str = ""


@app.post("/api/chats/{phone}/follow-up-on")
def chat_follow_up_on(phone: str, body: FollowAtIn):
    """Follow up on a date: a card for the broker, due then. Nothing is sent to the client."""
    from diwan import leads
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    try:
        return {"card": leads.follow_up_on(S.office, phone, by=body.by, at=_when(body.at, "day and time"), kind=body.kind,
                                           note=body.note, now=datetime.now(slots.DUBAI))}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


# ---------- the lead desk: Attention, the Pool, the sales team, notices ----------

class ClearIn(BaseModel):
    action: str
    by: str = "omar"
    note: str = ""


@app.post("/api/attention/{card}/clear")
def attention_clear(card: str, body: ClearIn):
    from diwan import leads
    try:
        return leads.clear(S.office, card, body.action, by=body.by, note=body.note)
    except KeyError:
        raise HTTPException(404, "no such card")
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/chats/{phone}/claim")
def chat_claim(phone: str, by: str = "omar"):
    from diwan import leads
    try:
        return leads.claim(S.office, phone, by=by)
    except ValueError as e:
        raise HTTPException(409, str(e))


class AssignIn(BaseModel):
    to: str
    by: str = "layla"


@app.post("/api/chats/{phone}/assign")
def chat_assign(phone: str, body: AssignIn):
    from diwan import leads
    if f"chat:{phone}" not in g().nodes:
        raise HTTPException(404, "no such conversation")
    try:
        return leads.reassign(S.office, phone, body.to, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(422, str(e))


# ---------- the Sales room ----------

@app.get("/api/sales/board")
def sales_board(person: str | None = None):
    return sales.board(S.office, person or access.USER.get())


@app.get("/api/sales/rules")
def sales_rules():
    return sales.settings(g())


class SalesRulesIn(BaseModel):
    by: str = "layla"
    value: dict


@app.post("/api/sales/rules")
def sales_rules_save(body: SalesRulesIn):
    try:
        return sales.set_settings(S.office, body.value, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class SuggestIn(BaseModel):
    by: str = "omar"


@app.post("/api/chats/{phone}/suggest")
def chat_suggest(phone: str, body: SuggestIn):
    try:
        return reception.suggest_again(S.office, phone, by=body.by)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class OutcomeIn(BaseModel):
    by: str
    outcome: str
    reason: str = ""
    note: str = ""
    at: str | None = None
    kind: str = "call"


@app.post("/api/chats/{phone}/outcome")
def chat_outcome(phone: str, body: OutcomeIn):
    """What came of the call: follow up on a date, not interested and why, or no response."""
    try:
        return sales.record_outcome(S.office, phone, body.outcome, by=body.by, reason=body.reason, note=body.note, kind=body.kind,
                                    at=_when(body.at, "day and time") if body.at else None, now=datetime.now(slots.DUBAI))
    except KeyError:
        raise HTTPException(404, "no such conversation") from None
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class LeadIn(BaseModel):
    by: str = "layla"
    name: str
    phone: str
    source: str
    note: str = ""
    email: str = ""
    ref: str = ""
    referred_by: str = ""


@app.post("/api/leads/add")
def lead_add(body: LeadIn):
    """A walk-in, a phone call or a referral: a lead like any other, with where it came from."""
    try:
        return sales.add_lead(S.office, by=body.by, name_=body.name, phone=body.phone, source=body.source, note=body.note, email=body.email,
                              ref=body.ref, referred_by=body.referred_by)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class WebformIn(BaseModel):
    token: str
    name: str
    phone: str
    message: str = ""
    email: str = ""
    ref: str = ""


@app.post("/api/portals/webform")
def lead_webform(body: WebformIn):
    """The office's own website form, posted by its server with the shared token. Off until WEBFORM_TOKEN is set."""
    import hmac
    want = env("WEBFORM_TOKEN")
    if not want or not hmac.compare_digest(want, body.token):
        raise HTTPException(403, "not allowed")
    try:
        return sales.add_lead(S.office, by="website", name_=body.name, phone=body.phone, source="website", note=body.message, email=body.email, ref=body.ref)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class MatchIn(BaseModel):
    by: str
    ref: str


@app.post("/api/chats/{phone}/send-match")
def chat_send_match(phone: str, body: MatchIn):
    """The broker's yes: a new listing goes to this client."""
    try:
        return sales.send_match(S.office, phone, body.ref, by=body.by)
    except KeyError:
        raise HTTPException(404, "not found") from None
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except reception.OptedOut as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None


@app.get("/api/team")
def sales_team():
    from diwan import leads
    return leads.team(g(), datetime.now(slots.DUBAI))


class TeamIn(BaseModel):
    shift: str | None = None
    days: list[int] | None = None
    away: bool | None = None
    phone: str | None = None
    licence: str | None = None
    licence_expiry: str | None = None
    by: str = "layla"


@app.post("/api/team/{person}")
def sales_team_set(person: str, body: TeamIn):
    from diwan import leads
    try:
        for k in ("shift", "days", "away", "phone", "licence", "licence_expiry"):
            if (v := getattr(body, k)) is not None:
                leads.set_agent(S.office, person, k, v, by=body.by)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return sales_team()


@app.get("/api/notices/{person}")
def person_notices(person: str):
    from diwan import leads
    ns = leads.notices(g(), person)
    return {"unread": sum(1 for n in ns if not n["read"]), "items": ns}


@app.post("/api/notices/{person}/read")
def person_notices_read(person: str):
    from diwan import leads
    leads.read_all(S.office, person)
    return {"ok": True}


# ---------- property portals: the listing feed and enquiry webhooks ----------

@app.post("/api/listings/sync")
def listings_sync():
    from diwan import leads
    try:
        return leads.sync_listings(S.office, portals.fetch_feed())
    except portals.PortalError as e:
        raise HTTPException(422, str(e))
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Could not reach the feed: {e}")


@app.post("/api/portals/{portal}/lead")
async def portal_lead(portal: str, request: Request, token: str = ""):
    from diwan import leads
    if portal not in portals.PORTALS:
        raise HTTPException(404, "unknown portal")
    body = await request.body()
    if not portals.signed(portal, body, request.headers.get("x-signature"), token):
        raise HTTPException(401, f"bad or missing signature (set PORTAL_SECRET_{portal.upper()})")
    try:
        lead = portals.parse_lead(portal, await request.json())
    except portals.PortalError as e:
        raise HTTPException(422, str(e))
    return leads.portal_lead(S.office, lead)


# ---------- qualification: the owner's questions and conditions ----------

class QualifyFormIn(BaseModel):
    form: dict
    by: str


class ByIn(BaseModel):
    by: str


@app.get("/api/decks/{did}")
def deck_get(did: str):
    """A pitch deck for the meeting page: its slides with their sources, the customer, the review and the approval."""
    from diwan.agents import deck
    gr = g()
    if did not in gr.nodes or gr.nodes[did].type != "draft":
        raise HTTPException(404, "no such deck")
    v = deck.view(gr, did)
    d = gr.nodes[f"deal:{v['deal']}"].props
    chat = next((c.props["phone"] for c in gr.of("chat") if c.deal == v["deal"]), None)
    return v | {"customer": d.get("customer"), "broker": d.get("broker"), "chat": chat,
                "sources": {r: gr.record(r) for s in v["slides"] for r in s["sources"] if r in gr.nodes}}


@app.post("/api/chats/{phone}/deck")
def deck_make(phone: str, body: ByIn):
    """Make the pitch deck again from what stands now (the deal's broker or the owner)."""
    from diwan import qualify
    from diwan.agents import deck
    gr = g()
    if f"chat:{phone}" not in gr.nodes or not gr.nodes[f"chat:{phone}"].deal:
        raise HTTPException(404, "no such lead")
    deal = gr.nodes[f"chat:{phone}"].deal
    if body.by != gr.nodes[f"deal:{deal}"].props["broker"] and body.by not in qualify.owner_ids():
        raise HTTPException(403, "Only the deal's broker or the owner makes the deck")
    did = deck.build(S.office, deal, by="deck")
    if not did:
        raise HTTPException(400, "The customer hasn't chosen a property yet")
    return deck.view(g(), did)


@app.post("/api/decks/{did}/approve")
def deck_approve(did: str, body: ByIn):
    from diwan.agents import deck
    try:
        deck.approve(S.office, did, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return deck.view(g(), did)


class FollowIn(BaseModel):
    by: str
    text: str = ""


def _deal_of(phone: str) -> str:
    gr = g()
    if f"chat:{phone}" not in gr.nodes or not gr.nodes[f"chat:{phone}"].deal:
        raise HTTPException(404, "no such lead")
    return gr.nodes[f"chat:{phone}"].deal


@app.post("/api/chats/{phone}/followup")
def followup_make(phone: str, body: FollowIn):
    """Draft the follow-up now (the deal's broker or the owner)."""
    from diwan import qualify
    from diwan.agents import followup
    deal = _deal_of(phone)
    if body.by != g().nodes[f"deal:{deal}"].props["broker"] and body.by not in qualify.owner_ids():
        raise HTTPException(403, "Only the deal's broker or the owner")
    return followup.draft(S.office, deal, why="asked by the broker")


@app.post("/api/chats/{phone}/followup/send")
def followup_send(phone: str, body: FollowIn):
    from diwan.agents import followup
    try:
        return followup.send(S.office, _deal_of(phone), body.text, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except reception.WindowClosed as e:
        raise HTTPException(409, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/chats/{phone}/followup/dismiss")
def followup_dismiss(phone: str, body: FollowIn):
    from diwan.agents import followup
    followup.dismiss(S.office, _deal_of(phone), by=body.by, why=body.text)
    return {"ok": True}


class KindsIn(BaseModel):
    by: str
    kinds: list[dict]


@app.get("/api/deal-kinds")
def deal_kinds_get():
    """The brokerage's deal kinds (sales desks), and what the editor needs: brokers, customer types and their questions."""
    from diwan import deal_kinds, leads, qualify
    f = qualify.form(g())
    return {"kinds": deal_kinds.kinds(g()), "brokers": [{"id": b, "name": PEOPLE[b]["name"]} for b in leads.brokers()],
            "types": {t: {"label": s["label"], "fields": [{"key": x["key"], "label": x["label"], "options": x.get("options") or []}
                                                           for x in qualify.fields_for(f, t)]} for t, s in f["types"].items()},
            "offerings": deal_kinds.OFFERINGS, "completions": deal_kinds.COMPLETIONS, "ops": list(qualify.OPS),
            "owners": sorted(qualify.owner_ids())}


@app.post("/api/deal-kinds")
def deal_kinds_set(body: KindsIn):
    from diwan import deal_kinds
    try:
        return {"kinds": deal_kinds.save(S.office, body.kinds, by=body.by)}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class RecommendIn(BaseModel):
    by: str
    when: str | None = None
    how_many: int | None = None
    hot_on: list[str] | None = None


@app.get("/api/rania/recommend")
def recommend_get():
    """When Rania recommends properties, how many, and what makes a lead hot (the owner's setting)."""
    return reception.recommend_settings(g()) | {"whens": reception.WHEN, "hots": reception.HOT_ON}


@app.post("/api/rania/recommend")
def recommend_set(body: RecommendIn):
    try:
        return reception.set_recommend(S.office, {k: v for k, v in body.model_dump().items() if k != "by" and v is not None}, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class FrontIn(BaseModel):
    by: str
    nurture_to: str | None = None
    portal_template: str | None = None
    greeting: str | None = None
    greeting_ar: str | None = None


@app.get("/api/rania/front")
def front_get():
    """Who nurtures leads that are not ready yet, and the first message to a portal lead (the owner's setting)."""
    from diwan import inbox
    return reception.front_settings(g()) | {"nurture_tos": reception.NURTURE_TO,
                                            "templates": [{"name": t["name"], "body": t["body"], "params": t.get("params")} for t in inbox.templates()]}


@app.post("/api/rania/front")
def front_set(body: FrontIn):
    try:
        return reception.set_front(S.office, {k: v for k, v in body.model_dump().items() if k != "by"}, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class QuietIn(BaseModel):
    by: str
    after_hours: list[float] | None = None
    after_visit_hours: list[float] | None = None
    quiet_from: str | None = None
    quiet_to: str | None = None
    friday_prayer: bool | None = None
    template: str | None = None
    then: str | None = None
    then_after_hours: float | None = None


@app.get("/api/rania/quiet")
def quiet_get():
    """When a client goes quiet: the owner's schedule, quiet hours, template and last step, and what is due next."""
    from diwan import inbox
    from diwan.agents import nudge
    return nudge.settings(g()) | {"thens": nudge.THEN, "upcoming": nudge.upcoming(g(), datetime.now(slots.DUBAI)),
                                  "templates": [{"name": t["name"], "body": t["body"], "params": t.get("params")} for t in inbox.templates()]}


@app.post("/api/rania/quiet")
def quiet_set(body: QuietIn):
    from diwan.agents import nudge
    try:
        return nudge.set_settings(S.office, {k: v for k, v in body.model_dump().items() if k != "by" and (v is not None or k == "template")}, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class SweepIn(BaseModel):
    at: str


@app.post("/api/nudges/run")
def nudges_run(body: SweepIn):
    """The sandbox only (no WhatsApp line connected): run the follow-up sweep as if it were `at`, to see what goes out."""
    from diwan.agents import nudge
    from diwan.providers import aisensy
    if aisensy.available() or whatsapp.available():
        raise HTTPException(403, "Only in the sandbox: a connected WhatsApp line would really send these")
    try:
        at = datetime.fromisoformat(body.at)
    except ValueError:
        raise HTTPException(400, "Use a time like 2026-11-02T10:00:00+04:00") from None
    from diwan.agents import reminders
    return {"done": nudge.sweep(S.office, at) + reminders.sweep(S.office, at)}


def _range(start: str | None, days: int | None):
    from datetime import date as _date, timedelta as _td
    try:
        d = _date.fromisoformat(start) if start else datetime.now(slots.DUBAI).date()
    except ValueError:
        raise HTTPException(400, "Use a date like 2026-11-02") from None
    return (d, days) if days else (d - _td(days=d.weekday()), 7)  # no length: the week of that day


@app.get("/api/calendar")
def calendar(person: str, start: str | None = None, broker: str | None = None, days: int | None = None):
    """From `start` for `days` days (default: the week of that day, from Monday): the owner sees every broker, a broker their own."""
    from diwan import qualify, video
    from diwan.agents import reminders
    d, n = _range(start, days)
    try:
        out = slots.week(g(), d, person=person, broker=broker or None, n=n) | {"reminders": reminders.settings(g()), "video": video.settings(g())}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if person in qualify.owner_ids():
        out["video_status"] = video.status()
    return out


@app.get("/api/calendar/search")
def calendar_search(person: str, q: str = ""):
    try:
        return {"results": slots.search(g(), q, person=person)}
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None


@app.get("/api/calendar.ics")
def calendar_ics(person: str, start: str | None = None, broker: str | None = None, days: int | None = None):
    """The shown range as a calendar file any phone, Outlook or Google imports."""
    from fastapi.responses import Response
    d, n = _range(start, days)
    try:
        body = slots.ics(g(), slots.week(g(), d, person=person, broker=broker or None, n=n))
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="diwan-{d.isoformat()}-{n}d.ics"'})


class VideoIn(BaseModel):
    by: str
    provider: str | None = None
    auto: bool = False


@app.post("/api/calendar/video")
def calendar_video(body: VideoIn):
    from diwan import video
    try:
        return video.set_settings(S.office, {"provider": body.provider or None, "auto": body.auto}, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class CalSetIn(BaseModel):
    by: str
    hours: dict | None = None
    kinds: list[dict] | None = None
    reminders: dict | None = None


@app.post("/api/calendar/settings")
def calendar_set(body: CalSetIn):
    """The owner's opening hours, kinds of appointment and reminders."""
    from diwan.agents import reminders
    try:
        if body.hours is not None:
            slots.set_hours(S.office, body.hours, by=body.by)
        if body.kinds is not None:
            slots.set_appointments(S.office, body.kinds, by=body.by)
        if body.reminders is not None:
            reminders.set_settings(S.office, body.reminders, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"ok": True}


class BlockIn(BaseModel):
    by: str
    broker: str
    kind: str = "busy"  # "busy" (start, end) or "off" (first, last day)
    start: str | None = None
    end: str | None = None
    first: str | None = None
    last: str | None = None
    reason: str = ""
    repeat: str | None = None
    until: str | None = None


def _when(v: str | None, what: str) -> datetime:
    try:
        t = datetime.fromisoformat(v or "")
    except ValueError:
        raise HTTPException(400, f"The {what}: a day and a time") from None
    return t if t.tzinfo else t.replace(tzinfo=slots.DUBAI)


@app.post("/api/calendar/blocks")
@app.post("/api/calendar/blocks/{bid}")
def calendar_block(body: BlockIn, bid: str | None = None):
    """The broker's own busy time (once or every week) or days off; the same id changes it."""
    try:
        if body.kind == "off":
            if bid:
                raise ValueError("To change a day off, delete it and add it again")
            return slots.day_off(S.office, by=body.by, broker=body.broker, first=body.first or "", last=body.last or "", reason=body.reason)
        return slots.block(S.office, by=body.by, broker=body.broker, start=_when(body.start, "start"), end=_when(body.end, "end"),
                           reason=body.reason, repeat=body.repeat or None, until=body.until or None, bid=bid)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/calendar/blocks/{bid}/delete")
def calendar_unblock(bid: str, body: ByIn):
    try:
        slots.unblock(S.office, bid, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(404, str(e)) from None
    return {"ok": True}


class HandIn(BaseModel):
    by: str
    broker: str
    phone: str
    name: str | None = None
    kind: str
    listing: str | None = None
    at: str
    confirmed: bool = False  # the broker has talked to the client and the place is available


@app.post("/api/appointments")
def appointment_add(body: HandIn):
    """An appointment the broker agreed with the client on the phone: the same checks and reminders as Rania's."""
    try:
        return reception.add_by_hand(S.office, by=body.by, broker=body.broker, phone=body.phone, name_=body.name, kind_id=body.kind,
                                     ref=body.listing, when=_when(body.at, "time"), now=datetime.now(slots.DUBAI), confirmed=body.confirmed)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class ChangeIn(BaseModel):
    by: str
    at: str | None = None
    cancel: bool = False
    reason: str = ""


@app.post("/api/appointments/{vid}/change")
def appointment_change(vid: str, body: ChangeIn):
    """The broker or the owner moves or cancels it from the calendar; the client is told in one message."""
    try:
        return reception.change_from_calendar(S.office, vid, by=body.by, when=_when(body.at, "new time") if not body.cancel else None,
                                              cancel=body.cancel, reason=body.reason, now=datetime.now(slots.DUBAI))
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class OwnerIn(BaseModel):
    by: str
    said: str  # yes, other, no
    times: list[str] = []


@app.post("/api/appointments/{vid}/owner")
def appointment_owner(vid: str, body: OwnerIn):
    """The broker's answer for the owner or tenant on a viewing waiting for them (docs/viewing-access-spec.md)."""
    from diwan import viewings
    try:
        return viewings.answer(S.office, vid, by=body.by, said=body.said, times=body.times, now=datetime.now(slots.DUBAI))
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class AccessIn(BaseModel):
    by: str
    mode: str
    who: str | None = None
    notice_hours: int | None = None
    place: str | None = None
    open: str | None = None
    close: str | None = None
    days: list[int] = []


@app.get("/api/listings/{ref}/access")
def listing_access(ref: str, person: str):
    from diwan import viewings
    lst = g().nodes.get(f"listing:{ref.upper()}")
    if not lst:
        raise HTTPException(404, "No such listing")
    from diwan.agents import reception
    return viewings.access(g(), lst) | {"can": viewings.may_change(g(), lst, person), "modes": viewings.MODES,
                                        "broker_confirms": reception.agent_confirms(g())}  # the owner's rule: the broker confirms each viewing


@app.post("/api/listings/{ref}/access")
def listing_access_set(ref: str, body: AccessIn):
    """How a listing is viewed: at once, after asking the owner or tenant, or at the developer's gallery."""
    from diwan import viewings
    try:
        return viewings.set_access(S.office, ref, body.model_dump(exclude={"by"}), by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


@app.post("/api/appointments/{vid}/link")
def appointment_link(vid: str, body: ByIn):
    """Make the video link with the owner's service and send it to the client."""
    try:
        return reception.send_link(S.office, vid, by=body.by, now=datetime.now(slots.DUBAI))
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


class ApptIn(BaseModel):
    by: str
    notes: str | None = None


@app.post("/api/appointments/{vid}/{what}")
def appointment_after(vid: str, what: str, body: ApptIn):
    """After the time: Done (the lead moves to Viewed, which drafts the follow-up) or No-show. The broker or the owner."""
    from diwan import inbox, qualify
    v = g().nodes.get(vid)
    if not v or v.type != "viewing" or what not in ("done", "noshow"):
        raise HTTPException(404, "no such appointment")
    if body.by != v.props["broker"] and body.by not in qualify.owner_ids():
        raise HTTPException(403, "Only the appointment's broker or the owner marks it")
    if v.status != "booked":
        raise HTTPException(409, f"It is already {v.status.replace('_', '-')}")
    if datetime.fromisoformat(v.props["at"]) > datetime.now(slots.DUBAI):
        raise HTTPException(409, "It hasn't happened yet")
    from diwan.agents import followup, visit
    ev = S.office.log.append(f"appointment.{what}", actor=body.by, deal=v.deal, content={"id": vid, "notes": (body.notes or "").strip() or None})
    if what == "noshow":
        return {"ok": True, "then": sales.no_show(S.office, vid, ev["id"])}
    if what == "done" and (body.notes or "").strip():  # the broker's notes: the visit summary the follow-up is built on
        visit.summarize(S.office, v.deal, said=body.notes, source="notes", appointment=vid, by=body.by, cause=ev["id"])
    if what == "done" and v.props.get("chat") and v.props.get("where", "property") == "property":
        inbox.set_stage(S.office, v.props["chat"], "Viewed", by=body.by, only_forward=True)  # drafts the follow-up
    elif what == "done" and (body.notes or "").strip():
        followup.draft(S.office, v.deal, why="after the meeting", cause=ev["id"])
    return {"ok": True, "visit": visit.latest(g(), v.deal)}


@app.get("/api/leads/nurture")
def nurture_list():
    """For Marketing: leads that are not ready yet (in their words) or not a fit (the owner's reason)."""
    return {"leads": reception.nurture_list(g())}


@app.get("/api/qualify/form")
def qualify_form():
    from diwan import qualify
    f = qualify.form(g())
    return f | {"can_edit": sorted(qualify.owner_ids()), "kinds": list(qualify.KINDS), "ops": list(qualify.OPS)}


@app.post("/api/qualify/form")
def qualify_form_save(body: QualifyFormIn):
    from diwan import qualify
    try:
        ev = qualify.save_form(S.office, body.form, by=body.by)
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"version": ev["content"]["version"]}


class QualifyCheckIn(BaseModel):
    form: dict
    type: str
    answers: dict[str, str]


@app.post("/api/qualify/check")
def qualify_check(body: QualifyCheckIn):
    """Try a form before saving it: these answers under these questions and conditions give this verdict."""
    from diwan import qualify
    f = {k: body.form.get(k) for k in ("common", "types", "rules")} | {"version": body.form.get("version", 0)}
    answers = {k: {"value": v, "quote": v, "unsure": qualify.unsure(v)} for k, v in body.answers.items() if str(v).strip()}
    v = qualify.evaluate(f, body.type, answers)
    return {k: v.get(k) for k in ("verdict", "reasons", "missing", "reply")} | {"next": (v.get("next") or {}).get("label")}


# ---------- the test console: talk to Rania on a copy of the office ----------

class TrialStart(BaseModel):
    customer: str = "Test Buyer"


class TrialSay(BaseModel):
    text: str
    brain: str = "model"


@app.get("/api/playground")
def playground_info():
    from diwan import playground
    return {"model": playground.model_name(), "brains": playground.brains(), "listings": len([n for n in g().of("listing", status="available") if n.props.get("permit")]),
            "knowledge": len(g().of("knowledge", status="confirmed"))}


@app.post("/api/playground/start")
def playground_start(body: TrialStart):
    from diwan import playground
    return playground.start(S.office, body.customer.strip() or "Test Buyer")


@app.post("/api/playground/{sid}/say")
def playground_say(sid: str, body: TrialSay):
    from diwan import playground
    if sid not in playground.SESSIONS:
        raise HTTPException(404, "This test conversation has ended. Start a new one.")
    if body.brain not in ("model", "spark", "free", "rules") or not body.text.strip():
        raise HTTPException(422, "Say something, with brain 'spark', 'free', 'model' or 'rules'")
    return playground.say(sid, body.text.strip(), brain=body.brain)


@app.post("/api/playground/cases")
def playground_cases(brain: str = "rules"):
    """Starts the 12 cases in the background; poll /api/playground/cases/{id} for progress."""
    from diwan import playground
    return playground.start_cases(brain=brain if brain in ("model", "spark", "free") else "rules")


@app.get("/api/playground/cases/{jid}")
def playground_cases_status(jid: str):
    from diwan import playground
    if jid not in playground.JOBS:
        raise HTTPException(404, "This run is gone (the server restarted). Run the cases again.")
    return playground.job_status(jid)


@app.post("/api/chats/{phone}/take")
def take(phone: str, by: str = "omar"):
    reception.hand_over(S.office, phone, to=by, by=by, reason="taken from the Inbox")
    return {"ok": True}


@app.post("/api/chats/{phone}/release")
def release(phone: str, by: str = "omar"):
    reception.give_back(S.office, phone, by=by)
    return {"ok": True}


# ---------- integrations: AiSensy, Meta's WhatsApp Cloud API ----------

@app.get("/api/line")
def whatsapp_line():
    """Which WhatsApp line is in use and whether it is connected: all the Inbox needs, with no addresses or tokens."""
    from diwan.providers import aisensy
    return {"provider": env("WHATSAPP_PROVIDER") or ("aisensy" if aisensy.available() else "cloud" if whatsapp.available() else "sandbox"),
            "aisensy": {"connected": aisensy.available()}, "cloud": {"connected": whatsapp.available()}}


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
        "zoom": {"connected": all(is_set(k) for k in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET")),
                 "fields": {k: is_set(k) for k in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET")}},
        "meta": {p.id: p.available() for p in PROVIDERS.values()} | {"voice": voice.available()},
        "portals": {"feed": is_set("LISTING_FEED_URL"), "notify_template": is_set("NOTIFY_TEMPLATE"),
                    "last_sync": next((e["content"] | {"at": e["at"]} for e in reversed(S.office.log.list()) if e["type"] == "listings.synced"), None),
                    "hooks": {p: {"name": n, "secret": is_set(f"PORTAL_SECRET_{p.upper()}"), "webhook": f"{base}/api/portals/{p}/lead"}
                              for p, n in portals.PORTALS.items()}},
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
            await _later(client_message(m["phone"], m["text"], m["name"], m["id"]))
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
    await _arrivals(whatsapp.parse(await request.json()))
    return {"ok": True}


async def _personal(m: dict):
    from diwan.agents import triage
    await asyncio.to_thread(triage.arrive, S.office, m)


async def _arrivals(messages: list[dict], *, only: str | None = None) -> None:
    """Meta sends one app's numbers to one address, so each message goes by the number it reached: the three pathways never meet."""
    from diwan import novaline, ownerline
    for m in messages:
        line = "personal" if ownerline.is_personal(m["line"]) else "nova" if novaline.is_nova(m["line"]) else "sales"
        if only and line != only:
            continue
        if line == "personal":
            await _later(_personal(m))
        elif line == "nova":
            await asyncio.to_thread(novaline.receive, S.office, m, datetime.now(slots.DUBAI))
        elif not m["echo"]:
            await _later(client_message(m["phone"], m["text"], m["name"], m["id"]))


@app.get("/api/personal/webhook")
def personal_verify(request: Request):
    p = dict(request.query_params)
    if p.get("hub.mode") != "subscribe" or not env("PERSONAL_WHATSAPP_VERIFY_TOKEN") or p.get("hub.verify_token") != env("PERSONAL_WHATSAPP_VERIFY_TOKEN"):
        raise HTTPException(403, "verify token does not match")
    return PlainTextResponse(p.get("hub.challenge"))


@app.post("/api/personal/webhook")
async def personal_receive(request: Request):
    """The owner's own number, if it comes in on an address of its own. It always needs a signature."""
    from diwan import ownerline
    body = await request.body()
    secret = env("PERSONAL_WHATSAPP_APP_SECRET") or env("WHATSAPP_APP_SECRET")
    if not ownerline.connected() or not secret or not whatsapp.signed(body, request.headers.get("x-hub-signature-256"), secret):
        raise HTTPException(401, "bad signature")
    await _arrivals(whatsapp.parse(await request.json()), only="personal")
    return {"ok": True}


# ---------- the owner's own WhatsApp: closed to everyone but the owner, like anything access.py doesn't list ----------

class PersonalIn(BaseModel):
    phone: str
    text: str
    name: str | None = None
    kind: str = "text"
    mine: bool = False
    forwarded: bool = False


class ContactIn(BaseModel):
    phone: str
    name: str | None = None
    circle: str | None = None
    note: str | None = None
    quiet: bool | None = None


@app.post("/api/personal/incoming")
def personal_incoming(body: PersonalIn):
    """The stand-in phone: the same path a message on the owner's number takes."""
    from diwan.agents import triage
    return {"matter": triage.arrive(S.office, {"phone": body.phone, "text": body.text, "name": body.name, "kind": body.kind, "echo": body.mine, "forwarded": body.forwarded})}


@app.get("/api/personal")
def personal_view():
    from diwan import contacts, novaline, ownerline
    with ownerline.db() as c:
        matters = [dict(r) for r in c.execute("select * from matters where status!='closed' order by id desc")]
        notices = [dict(r) for r in c.execute("select * from notices order by id desc limit 30")]
    return {"line": {"connected": ownerline.connected(), "sending": ownerline.sending(), "nova": novaline.connected(), "keep_days": int(env("PERSONAL_KEEP_DAYS") or ownerline.KEEP_DAYS)},
            "chats": [m | {"who": contacts.who(S.office, m["chat"], m["name"])} for m in ownerline.chats()], "matters": matters, "notices": notices,
            "contacts": contacts.everyone(), "circles": contacts.CIRCLES}


@app.get("/api/personal/chats/{phone}")
def personal_chat(phone: str):
    from diwan import ownerline
    return ownerline.chat(phone, 100)


@app.post("/api/personal/contacts")
def personal_contact(body: ContactIn):
    from diwan import contacts
    try:
        return contacts.place(body.phone, name_=body.name, circle=body.circle, note=body.note, quiet=body.quiet)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/api/personal/chats/{phone}/forget")
def personal_forget(phone: str):
    from diwan import ownerline
    return {"gone": ownerline.forget(phone)}


@app.post("/api/personal/forget")
def personal_forget_all():
    from diwan import ownerline
    ownerline.forget_all()
    return {"ok": True}


class PersonalSend(BaseModel):
    text: str


@app.post("/api/personal/chats/{phone}/send")
def personal_send(phone: str, body: PersonalSend):
    """The owner typing in their own chat: their words, from their number. Whatever Nova held about it is finished."""
    from diwan import ownerline
    with ownerline.db() as c:
        c.execute("update matters set status='closed' where chat=?", (phone,))
    try:
        return ownerline.send(phone, body.text, by="owner")
    except ownerline.ReadOnly as e:
        raise HTTPException(409, str(e))


@app.post("/api/personal/matters/{mid}/{what}")
def personal_decide(mid: int, what: str):
    """The buttons on what Nova is holding: Send, or Leave it. The same yes as saying it to her."""
    from diwan import ownerline
    from diwan.agents import triage
    with ownerline.db() as c:
        r = c.execute("select * from matters where id=?", (mid,)).fetchone()
    if not r or what not in ("yes", "leave"):
        raise HTTPException(404, "no such matter")
    if what == "leave":
        triage._close(mid)
        return {"kind": "done", "text": "Left."}
    return triage._act(S.office, dict(r), triage.owner_id(), datetime.now(slots.DUBAI))


# ---------- screens ----------

@app.middleware("http")
async def no_store(request: Request, call_next):
    r = await call_next(request)
    if request.url.path.startswith("/web"):
        r.headers["Cache-Control"] = "no-store"
    return r


app.add_middleware(access.Gate)  # last added runs first: nothing reaches the app without passing it
access.chat_guard = lambda person, phone: f"chat:{phone}" not in g().nodes or sales.may_see(g(), phone, person)


def _broker_keeps_to_their_own(person: str, deal: str) -> bool:
    return f"deal:{deal}" not in g().nodes or PEOPLE.get(person, {}).get("role") != "Broker" or frontdesk.sees_deal(g(), deal, person)


def _file_guard(person: str, filename: str) -> bool:
    """A broker sees the IDs, signatures and signed forms of their own clients only. A file no deal claims is nobody's to open."""
    if PEOPLE.get(person, {}).get("role") != "Broker":
        return True
    for e in S.office.log.list():
        if e.get("deal") and filename in json.dumps(e["content"], ensure_ascii=False):
            return _broker_keeps_to_their_own(person, e["deal"])
    return False


access.deal_guard = _broker_keeps_to_their_own
access.file_guard = _file_guard


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
