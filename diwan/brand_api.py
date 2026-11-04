"""The brand profile over HTTP: read it, save it, or have the Brand brain draft one for a person to edit."""
from __future__ import annotations

import asyncio
import contextlib
import io

from fastapi import APIRouter, File, Form, UploadFile, WebSocket
from pydantic import BaseModel

from diwan import brand

router = APIRouter()


def _office():
    from diwan.app import S
    return S.office


@router.get("/api/brand")
def get_brand():
    return {"fields": [{"key": k, "label": lab, "hint": hint, "list": lst} for k, (lab, hint, lst) in brand.FIELDS.items()],
            "profile": brand.profile(_office()), "set": brand.is_set(_office()), "used_by": brand.USED_BY}


class BrandIn(BaseModel):
    values: dict
    by: str = "maya"
    via: str = "typed"


@router.post("/api/brand")
def save_brand(body: BrandIn):
    changed = brand.save(_office(), body.values, by=body.by, via=body.via)
    return {"ok": True, "changed": changed}


@router.post("/api/brand/draft")
async def draft_brand():
    """One model call; nothing is saved until a person presses Save."""
    try:
        return await asyncio.to_thread(brand.draft, _office())
    except Exception as e:  # the model failed or timed out: say so, keep what was typed
        return {"needs": f"The draft failed: {str(e)[:160]}. You can type the profile yourself."}


@router.get("/api/memory/marketing")
def marketing_memory(upto: int | None = None):
    """The marketing team's memory as a graph, rewindable to any event."""
    from diwan.brain import marketing_graph
    return marketing_graph(_office(), upto)


class LearnIn(BaseModel):
    urls: list[str] = []
    document: str = ""          # pasted text: a company profile, a brochure
    document_name: str = "company profile"
    company: str = ""
    by: str = "maya"


@router.post("/api/brand/learn")
async def learn_company(body: LearnIn):
    """The Brand brain reads public pages and proposes knowledge cards (each proven by a quote) and a brand draft."""
    from diwan import learn
    try:
        docs = {body.document_name or "company profile": body.document} if body.document.strip() else {}
        return await asyncio.to_thread(learn.learn, _office(), body.urls[:learn.SITE_PAGES], documents=docs, by=body.by, company=body.company)
    except Exception as e:
        return {"needs": f"Reading the pages failed: {str(e)[:160]}"}


@router.get("/api/brand/demo-profile")
def demo_profile():
    """The fictional company profile the demo learns from."""
    from pathlib import Path
    return {"name": "Diwan Realty company profile", "text": (Path(__file__).parent / "demo_profile.md").read_text()}


@router.get("/api/business")
def get_business():
    """What business we are and where, with every country and its time zones to pick from."""
    from diwan import business
    from diwan.agents import studio
    return {"fields": [{"key": k, "label": lab, "hint": hint} for k, (lab, hint) in business.FIELDS.items()],
            "profile": business.profile(_office()), "missing": business.missing(_office()), "countries": business.countries(),
            "platforms_known": list(studio.LIMITS), "platforms_default": __import__("diwan.platforms", fromlist=["DEFAULT"]).DEFAULT + ["Property Finder"]}


class BusinessIn(BaseModel):
    values: dict
    by: str = "maya"


@router.post("/api/business")
def save_business(body: BusinessIn):
    from diwan import business
    try:
        return {"ok": True, "changed": business.save(_office(), body.values, by=body.by), "business": business.get(_office())}
    except business.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/studio/why/read")
async def read_posts():
    """Muse Spark reads the competitor posts not read yet (paid, Marketing's budget); nothing is read twice."""
    from diwan.agents import reader
    try:
        r = await asyncio.to_thread(reader.read, _office())
    except Exception as e:
        return {"needs": f"Reading failed: {str(e)[:160]}"}
    return r | {"why": reader.patterns(_office())}


@router.get("/api/studio/style")
def style_notes():
    from diwan.agents import style
    return {"notes": style.notes(_office()), "deleted": [n for n in style.notes(_office(), all_=True) if n["id"] in style.deleted(_office())]}


class NoteIn(BaseModel):
    note: str
    by: str = "maya"


@router.post("/api/studio/style/delete")
def delete_note(body: NoteIn):
    from diwan.agents import style
    try:
        style.delete(_office(), body.note, by=body.by)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True}


@router.post("/api/studio/style/restore")
def restore_note(body: NoteIn):
    from diwan.agents import style
    style.restore(_office(), body.note, by=body.by)
    return {"ok": True}


@router.get("/api/studio/rhythm")
def get_rhythm():
    from diwan.agents import rhythm
    return {"settings": rhythm.settings(_office()), "labels": rhythm.LABELS, "rhythms": list(rhythm.EVERY),
            "next": rhythm.next_run(_office()), "next_refresh": rhythm.next_refresh(_office())}


class RhythmIn(BaseModel):
    values: dict
    by: str = "maya"


@router.post("/api/studio/rhythm")
def save_rhythm(body: RhythmIn):
    from diwan.agents import rhythm
    try:
        return {"ok": True, "changed": rhythm.save(_office(), body.values, by=body.by), "next": rhythm.next_run(_office()), "next_refresh": rhythm.next_refresh(_office())}
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/studio/plan/week")
def plan_week(by: str = "maya"):
    """Plan this week and next from today: the Strategist chooses. Nothing is written until each day."""
    from datetime import datetime, timezone
    from diwan import business
    from diwan.agents import rhythm
    return rhythm.make_plan(_office(), business.local(datetime.now(timezone.utc), _office()).date(), auto=False, by=by, days_ahead=rhythm.AHEAD_DAYS, think=True)


class MoveIn(BaseModel):
    day: str
    step: int
    by: str = "maya"


@router.post("/api/studio/plan/move")
def plan_move(body: MoveIn):
    from diwan.agents import rhythm
    try:
        return {"ok": True, "plan": rhythm.move(_office(), body.day, body.step, by=body.by)}
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/studio/our-ads")
async def our_ads():
    """Our own ad account's last 30 days, read-only."""
    from diwan.providers import ads
    if not ads.ready():
        return {"ok": False, "needs": f"Our ads need {', '.join(ads.missing()) or 'online mode'} in .env."}
    try:
        return {"ok": True} | await asyncio.to_thread(ads.report)
    except ads.AdsError as e:
        return {"ok": False, "needs": f"Meta refused: {e}"}


@router.get("/api/studio/approvers")
def get_approvers():
    from diwan.agents import approvers
    return {"roles": approvers.ROLES, "set": approvers.get(_office()), "team": approvers.team()}


class ApproversIn(BaseModel):
    values: dict
    by: str = "layla"


@router.post("/api/studio/approvers")
def save_approvers(body: ApproversIn):
    from diwan.agents import approvers
    try:
        return {"ok": True, "changed": approvers.save(_office(), body.values, by=body.by)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


# ---------- talking to the Marketing lead ----------

class ChatIn(BaseModel):
    session: str
    text: str
    ref: str | None = None
    by: str = "maya"


@router.post("/api/marketing/chat")
async def chat_say(body: ChatIn):
    from diwan.agents import lead_chat
    try:
        from diwan import access
        return await asyncio.to_thread(lead_chat.say, _office(), body.session, body.text, by=access.USER.get() or body.by, ref=body.ref)
    except ValueError as e:
        return {"reply": str(e), "action": "none"}
    except Exception as e:  # noqa: BLE001  the model failed: say so, keep the conversation
        return {"reply": f"I couldn't answer that just now ({str(e)[:120]}). Try again in a moment.", "action": "none"}


@router.get("/api/marketing/chat/{session}")
def chat_history(session: str):
    from diwan.agents import lead_chat
    o = _office()
    return {"messages": [m for m in lead_chat.history(o, session) if m.get("who") in ("person", "lead")],
            "uploads": lead_chat.uploads(o, session), "pending": lead_chat.pending(o, session)}


@router.post("/api/marketing/chat/upload")
async def chat_upload(session: str = Form(...), files: list[UploadFile] = File(...), ref: str = Form(""), kind: str = Form(""),
                      whose: str = Form(""), likes: str = Form(""), comments: str = Form(""), by: str = Form("maya")):
    """Files for the Marketing lead to read: a reel, a post, or a screenshot of its comments. Each is analysed, then the
    lead answers (and asks for what it still needs)."""
    from pathlib import Path
    from diwan.agents import lead_chat
    from diwan.providers import meta
    meta.MEDIA.mkdir(exist_ok=True)
    names = []
    for i, f in enumerate(files):
        mime = f.content_type or ""
        if not mime.startswith(("video/", "image/")):
            return {"reply": f"{f.filename} is not a video or a picture.", "action": "none"}
        path = meta.MEDIA / f"chat-{session[:12]}-{len(lead_chat.uploads(_office(), session)) + i + 1}{Path(f.filename or 'f').suffix or ('.mp4' if mime.startswith('video') else '.jpg')}"
        path.write_bytes(await f.read())
        facts = {"kind": kind, "whose": whose, "likes": likes, "comments": comments}
        await asyncio.to_thread(lead_chat.add_upload, _office(), session, path, f.filename or path.name, mime, by=by, facts=facts)
        names.append(f.filename or path.name)
    told = ", ".join(f"{k} {v}" for k, v in (("a", kind), ("by", whose), ("likes:", likes), ("comments:", comments)) if v)
    try:
        return await asyncio.to_thread(lead_chat.say, _office(), session, f"I uploaded {', '.join(names)}" + (f" ({told})" if told else "") + ".", by=by, ref=ref or None)
    except Exception as e:  # noqa: BLE001
        return {"reply": f"I read {', '.join(names)} but couldn't answer just now ({str(e)[:120]}).", "action": "none"}


@router.websocket("/api/marketing/chat/audio")
async def chat_audio(ws: WebSocket, session: str, ref: str = "", by: str = "maya"):
    """A spoken conversation: the browser streams the microphone (PCM16, 16 kHz) until the person stops. Each finished
    sentence goes to the Marketing lead; its answer comes back to be spoken, and listening goes on."""
    from diwan.agents import lead_chat
    from diwan.providers import voice
    await ws.accept()
    if not voice.available():
        await ws.close(4001, "Listening needs Muse Voice Transcribe (the Meta key in .env). You can type instead.")
        return
    q: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def chunks():
        while (c := await q.get()) is not None:
            yield c

    async def answer(text: str):
        await ws.send_json({"heard": text})
        if text.lower().strip(" .!?") in ("stop", "stop talking", "that's all", "that is all", "bye", "goodbye"):
            await ws.send_json({"stop": True, "reply": "Okay, stopping. Type or press Talk when you need me.", "action": "none"})
            return
        try:
            r = await asyncio.to_thread(lead_chat.say, _office(), session, text, by=by, ref=ref or None)
        except Exception as e:  # noqa: BLE001
            r = {"reply": f"I couldn't answer that just now ({str(e)[:100]}).", "action": "none"}
        await ws.send_json(r)

    def on_turn(t: dict):
        loop.create_task(answer(t["final"]) if "final" in t else ws.send_json(t))

    ended = asyncio.Event()

    def dropped(task: asyncio.Task):
        if not ended.is_set():  # the person is still talking and nobody is listening
            loop.create_task(ws.close(4002, "Listening stopped. Press Talk to carry on, or type."))

    relay = asyncio.create_task(voice.stream(chunks(), on_turn))
    relay.add_done_callback(dropped)
    try:
        while True:
            msg = await ws.receive()
            if msg.get("bytes"):
                await q.put(msg["bytes"])
            elif msg.get("type") == "websocket.disconnect" or msg.get("text") == "end":
                break
    except RuntimeError:  # closed from this side, above
        pass
    finally:
        ended.set()
        await q.put(None)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(relay, 15)



# ---------- our products and services ----------

@router.get("/api/products")
def list_products():
    from diwan import products
    return {"products": list(products.items(_office(), all_=True).values()), "kinds": list(products.KINDS)}


class ProductIn(BaseModel):
    values: dict
    ref: str | None = None
    by: str = "maya"


@router.post("/api/products")
def save_product(body: ProductIn):
    from diwan import products
    try:
        return {"ok": True, "ref": products.save(_office(), body.values, by=body.by, ref=body.ref)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


class CrawlIn(BaseModel):
    url: str


@router.post("/api/brand/crawl")
async def crawl_site(body: CrawlIn):
    """The pages of the company's own site, found from its home page, for the person to choose before anything is read."""
    from diwan import learn
    try:
        return await asyncio.to_thread(learn.crawl, body.url)
    except ValueError as e:
        return {"ok": False, "error": str(e)}


class FindListingsIn(BaseModel):
    url: str = ""
    by: str = "maya"


@router.post("/api/brand/find-listings")
async def find_listings(body: FindListingsIn):
    """The properties on the company's own website, read in code (the model only fills what the code could not read,
    each value checked against its page), and added to the listings unless they are there already."""
    from diwan import business, sitelistings
    url = body.url.strip() or business.get(_office())["website"]
    try:
        return await asyncio.to_thread(sitelistings.run, _office(), url, by=body.by)
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/studio/competitors/refresh")
async def refresh_now(by: str = "maya"):
    """Re-read the competitors' posts now (new posts, changed likes), read the new ones, redo the patterns."""
    from diwan.agents import studio
    return await asyncio.to_thread(studio.refresh_competitors, _office(), by=by)


class TopicIn(BaseModel):
    values: dict
    ref: str | None = None
    by: str = "maya"


@router.post("/api/topics")
def save_topic(body: TopicIn):
    """A topic typed in Setup (the facts a video may use), or one changed or removed."""
    from diwan import topics
    try:
        return {"ok": True, "ref": topics.save(_office(), body.values, by=body.by, ref=body.ref)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/moments")
def add_moment(body: TopicIn):
    """Something that just happened: it goes before the plan until its script is approved or its date passes."""
    from diwan import topics
    try:
        return {"ok": True, "ref": topics.save_moment(_office(), body.values, by=body.by)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/marketing/plan")
def marketing_plan():
    """The Plan tab: the days ahead, what waits for a person, what is scheduled, what came off."""
    from diwan.agents import marketing
    return marketing.plan_view(_office())


class PlanIn(BaseModel):
    days: int = 7
    per_week: int = 0
    by: str = "maya"


@router.post("/api/marketing/plan")
async def make_marketing_plan(body: PlanIn):
    """Plan the days ahead. Today's day, if the plan has one, is written straight away; each later day on its morning."""
    from datetime import datetime, timezone
    from diwan import business
    from diwan.agents import rhythm, studio
    if not 1 <= body.days <= 31:
        return {"ok": False, "error": "Plan 1 to 31 days."}
    if body.per_week:
        try:
            rhythm.save(_office(), {"posts_per_week": body.per_week}, by=body.by)
        except rhythm.Invalid as e:
            return {"ok": False, "error": str(e)}
    await asyncio.to_thread(rhythm.make_plan, _office(), business.local(datetime.now(timezone.utc), _office()).date(), auto=False, by=body.by,
                            days_ahead=body.days, think=True)
    today = rhythm.due(_office(), any_hour=True)
    if today:
        asyncio.create_task(studio.run(_office(), today))
    return {"ok": True, "writing_today": today}


class DayIn(BaseModel):
    day: str
    decision: str = ""
    why: str = ""
    by: str = "maya"


def _may_plan(by: str) -> bool:
    from diwan import access
    from diwan.agents import approvers
    who = approvers.get(_office())["script"]
    return not who or by == who or access.is_owner(by)


@router.get("/api/marketing/learned")
def marketing_learned():
    """What the studio has learned from decisions and results."""
    from diwan.agents import taste
    return taste.learned(_office())


class ForgetIn(BaseModel):
    key: str
    by: str = "maya"


@router.post("/api/marketing/learned/forget")
def marketing_forget(body: ForgetIn):
    from diwan.agents import taste
    taste.forget(_office(), body.key, by=body.by)
    return {"ok": True}


class ChangeDayIn(BaseModel):
    day: str
    ref: str
    by: str = "maya"


@router.post("/api/marketing/plan/change")
def change_plan_day(body: ChangeDayIn):
    """Put something else on a planned day."""
    from diwan.agents import approvers, rhythm
    if not _may_plan(body.by):
        return {"ok": False, "error": f"This waits for {approvers.label(_office(), 'script')}."}
    try:
        return {"ok": True, "plan": rhythm.change_day(_office(), body.day, body.ref, by=body.by)}
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/marketing/plan/day")
def decide_plan_day(body: DayIn):
    """Approved stays on the plan. Rejected comes off, and the day stays empty."""
    from diwan.agents import approvers, rhythm
    if not _may_plan(body.by):
        return {"ok": False, "error": f"This waits for {approvers.label(_office(), 'script')}."}
    try:
        return {"ok": True, "plan": rhythm.decide_day(_office(), body.day, body.decision, by=body.by, why=body.why)}
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/marketing/plan/write")
async def write_plan_day(body: DayIn):
    """Write a planned day's post now. Pressing this is the brief's yes."""
    import asyncio
    from diwan.agents import approvers, rhythm, studio
    if not _may_plan(body.by):
        return {"ok": False, "error": f"This waits for {approvers.label(_office(), 'script')}."}
    try:
        ref = rhythm.start_day(_office(), body.day, by=body.by)
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}
    asyncio.create_task(studio.run(_office(), ref))
    return {"ok": True, "ref": ref}


@router.get("/api/marketing/overview")
def marketing_overview():
    """The Results tab: every piece's stage, what each post brought, the day's lists and the campaigns."""
    from diwan.agents import marketing
    return marketing.overview(_office())


class PostNowIn(BaseModel):
    ref: str
    by: str = "maya"


@router.post("/api/studio/post-now")
def post_now(body: PostNowIn):
    """A scheduled post, at or before its time, by the person named to approve publishing, or the owner."""
    from diwan import access
    from diwan.agents import approvers, studio
    who = approvers.get(_office())["publish"]
    if who and body.by != who and not access.is_owner(body.by):
        return {"ok": False, "needs": [f"This waits for {approvers.label(_office(), 'publish')}."]}
    return studio.publish(_office(), body.ref, by=body.by)


class CampaignIn(BaseModel):
    ref: str
    values: dict
    by: str = "maya"


@router.post("/api/marketing/campaigns")
def add_campaign(body: CampaignIn):
    from diwan.agents import marketing
    try:
        return {"ok": True, "campaign": marketing.draft(_office(), body.ref, body.values, by=body.by)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


class CampaignStepIn(BaseModel):
    ad_id: str = ""
    why: str = ""
    by: str = "maya"


@router.post("/api/marketing/campaigns/{cid}/start")
def start_campaign(cid: str, body: CampaignStepIn):
    """A person launched it in Ads Manager and pays: this records it."""
    from diwan.agents import marketing
    try:
        marketing.start(_office(), cid, ad_id=body.ad_id, by=body.by)
        return {"ok": True}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/marketing/campaigns/{cid}/end")
def end_campaign(cid: str, body: CampaignStepIn):
    from diwan.agents import marketing
    marketing.end(_office(), cid, by=body.by, why=body.why)
    return {"ok": True}


@router.get("/api/marketing/campaigns/spend")
def campaign_spend():
    """Reads the ad account (a network call), so only when a person asks."""
    from diwan.agents import marketing
    return marketing.campaign_report(_office(), spend=True)


class UnscheduleIn(BaseModel):
    ref: str
    by: str = "maya"


class RescheduleIn(BaseModel):
    ref: str
    at: str
    by: str = "maya"


@router.post("/api/studio/reschedule")
def reschedule_post(body: RescheduleIn):
    """An approved post goes out at another time."""
    from diwan.agents import studio
    return studio.reschedule(_office(), body.ref, body.at, by=body.by)


class MoveDayIn(BaseModel):
    day: str
    to: str
    by: str = "maya"


@router.post("/api/marketing/plan/reschedule")
def reschedule_day(body: MoveDayIn):
    """A planned post moves to another date."""
    from diwan.agents import approvers, rhythm
    if not _may_plan(body.by):
        return {"ok": False, "error": f"This waits for {approvers.label(_office(), 'script')}."}
    try:
        return {"ok": True, "plan": rhythm.reschedule(_office(), body.day, body.to, by=body.by)}
    except rhythm.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/studio/unschedule")
def unschedule(body: UnscheduleIn):
    """Stop an approved post before its time. It goes back to waiting for a yes: cancelling the time is not stopping the post."""
    from diwan.agents import marketing, studio
    studio.unschedule(_office(), body.ref, by=body.by)
    marketing._resume(_office(), body.ref, {})
    return {"ok": True}


class MomentFormatIn(BaseModel):
    ref: str
    format: str
    by: str = "maya"


@router.post("/api/moments/format")
def moment_format(body: MomentFormatIn):
    """A person overrides the format Diwan suggested."""
    from diwan.agents import eventpost
    try:
        eventpost.choose(_office(), body.ref, body.format, by=body.by)
        return {"ok": True}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


class TopicUseIn(BaseModel):
    ref: str
    use: bool
    by: str = "maya"


@router.post("/api/topics/use")
def topic_use(body: TopicUseIn):
    """Stop (or resume) making videos about a Knowledge card or a service. It stays in Knowledge for the agents."""
    from diwan import topics
    if body.ref not in topics.items(_office(), all_=True):
        return {"ok": False, "error": f"No topic {body.ref}."}
    topics.exclude(_office(), body.ref, by=body.by, on=not body.use)
    return {"ok": True}


class OccasionIn(BaseModel):
    key: str
    on: str | None = None
    by: str = "maya"


@router.post("/api/occasions/prepare")
async def occasion_prepare(body: OccasionIn):
    """One yes on an occasion from the calendar: a greeting post is written now and goes out on the day."""
    from diwan import occasions
    from diwan.agents import studio
    try:
        ref = occasions.prepare(_office(), body.key, by=body.by, on=body.on)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    asyncio.create_task(studio.run(_office(), ref))
    return {"ok": True, "ref": ref}


@router.get("/api/occasions")
def occasions_list():
    """The business's occasions (researched for its country, with a person's changes), what the research dropped and why, and its sources."""
    from diwan import occasions
    r = occasions.researched(_office()) or {}
    return {"rows": occasions.all_(_office()), "researched": r.get("day"), "country": r.get("country"), "dropped": r.get("dropped", []),
            "sources": r.get("sources", []), "due": occasions.research_due(_office())}


@router.post("/api/occasions/research")
async def occasions_research(by: str = "maya"):
    """Find this business's occasions for the next year now (one web search)."""
    from diwan import occasions
    r = await asyncio.to_thread(occasions.research, _office(), by=by)
    return {"ok": "needs" not in r, **({"needs": r["needs"]} if "needs" in r else {"found": len(r["rows"]), "dropped": r["dropped"]})}


class OccasionRow(BaseModel):
    title: str
    on: str
    greeting: str
    greeting_local: str = ""
    tags: list[str] = []
    about: str = ""
    sombre: bool = False
    key: str | None = None
    by: str = "maya"


@router.post("/api/occasions/save")
def occasions_save(body: OccasionRow):
    """A person adds or corrects an occasion: their word wins over the research."""
    from diwan import occasions
    try:
        return {"ok": True, "row": occasions.save(_office(), body.model_dump(exclude={"key", "by"}), by=body.by, key=body.key)}
    except ValueError as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/occasions/remove")
def occasions_remove(body: OccasionIn):
    """Not an occasion this business marks."""
    from diwan import occasions
    occasions.remove(_office(), body.key, by=body.by)
    return {"ok": True}


@router.post("/api/occasions/skip")
def occasion_skip(body: OccasionIn):
    """Not this year."""
    from diwan import occasions
    occasions.skip(_office(), body.key, by=body.by)
    return {"ok": True}


@router.post("/api/brand/logo")
async def brand_logo(file: UploadFile = File(...), by: str = Form("maya")):
    """The company's logo, a PNG (a clear background is best) or JPEG: it goes on every picture, cover and end card."""
    from PIL import Image
    from diwan.providers import meta
    data = await file.read()
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "That file is not a picture. Upload the logo as a PNG or JPEG."}
    if min(img.size) < 120:
        return {"ok": False, "error": f"The logo is too small ({img.size[0]}x{img.size[1]}): use one at least 300 pixels wide."}
    meta.MEDIA.mkdir(exist_ok=True)
    path = meta.MEDIA / "brand-logo.png"
    img.convert("RGBA").save(path, "PNG")
    _office().log.append("setting.changed", actor=by, content={"person": "brand_logo", "key": "logo", "value": str(path)})
    from diwan.agents import studio
    studio.keep(_office(), "brand", "logo", {"file": f"/media/{path.name}"})  # a copy in Supabase Storage, when a bucket is set
    return {"ok": True, "served": f"/media/{path.name}"}


@router.get("/api/brand/logo")
def brand_logo_get():
    from pathlib import Path
    from diwan import brand
    p = brand.logo(_office())
    return {"served": f"/media/{Path(p).name}" if p else None}
