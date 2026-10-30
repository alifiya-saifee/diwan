"""Talking to the Marketing lead: by text or by voice, about marketing only. It answers from the studio's own data (the
board, Why they win, our weak posts, the strategy, the plan, the scripts waiting), reads what you upload (a reel, a
post, a screenshot of its comments), searches a competitor's posts by date, and reads our ads. It never invents a
number: what it measured, what you told it and what it does not know are said apart.

Anything that changes the studio (rewrite a script, run a listing, plan the week) is proposed first and done only after
the person says yes. Leads, customers and WhatsApp belong to Sales: it says so and stays on marketing.

Uploads: speech is transcribed on this computer first (local Whisper, free), Muse Voice Transcribe if that cannot; the
cuts are counted with ffmpeg's scene detection; a few frames, or the picture, are read by Muse Spark.
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import threading
from pathlib import Path

from diwan import brand, business
from diwan.agents import runner
from diwan.agents.charters import get
from diwan.office import Office
from diwan.providers import instagram, local_asr, meta

ACTIONS = ["none", "search_posts", "read_our_ads", "ask_upload", "note_facts", "revise_script", "run_listing", "plan_week", "confirm", "cancel"]
CHANGES = {"revise_script", "run_listing", "plan_week"}  # these wait for a yes
ARGS = ["account", "since", "until", "script", "note", "ref", "kind", "whose", "likes", "comments"]
SCHEMA = {"name": "lead", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["reply", "action", *ARGS],
          "properties": {"reply": {"type": "string"}, "action": {"type": "string", "enum": ACTIONS}, **{a: {"type": "string"} for a in ARGS}}}}

LOOK = {"name": "upload", "strict": True, "schema": {"type": "object", "additionalProperties": False,
        "required": ["what", "topic", "hook", "on_screen", "on_screen_text", "asks", "tone", "why_it_worked", "carries_over", "why_not", "for_us"],
        "properties": {"what": {"type": "string"}, "topic": {"type": "string"}, "hook": {"type": "string"}, "on_screen": {"type": "string"},
                       "on_screen_text": {"type": "string"}, "asks": {"type": "string"}, "tone": {"type": "string"},
                       "why_it_worked": {"type": "array", "items": {"type": "string"}}, "carries_over": {"type": "boolean"},
                       "why_not": {"type": "string"}, "for_us": {"type": "string"}}}}
COMMENTS = {"name": "comments", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["asked", "liked", "worried"],
            "properties": {k: {"type": "array", "items": {"type": "string"}} for k in ("asked", "liked", "worried")}}}


# ---------- the conversation, from the log ----------

def history(office: Office, session: str) -> list[dict]:
    return [e["content"] | {"at": e["at"], "id": e["id"]} for e in office.log.list()
            if e["type"] in ("mchat.said", "mchat.upload", "mchat.analysed") and e["content"].get("session") == session]


def uploads(office: Office, session: str) -> list[dict]:
    """This conversation's uploads, each with the facts the person gave and what was measured and read."""
    out: dict[str, dict] = {}
    for e in office.log.list():
        c = e["content"]
        if c.get("session") != session:
            continue
        if e["type"] == "mchat.upload":
            out.setdefault(c["upload"], {}).update({k: v for k, v in c.items() if v not in (None, "")})
        elif e["type"] == "mchat.analysed":
            out.setdefault(c["upload"], {})["analysis"] = c["analysis"]
    return list(out.values())


def pending(office: Office, session: str) -> dict | None:
    """The change the lead proposed and is waiting on a yes for, if any."""
    for c in reversed(history(office, session)):
        if c.get("who") == "lead":
            return c.get("pending")
        if c.get("who") == "person":
            continue
    return None


# ---------- what the lead knows ----------

def context(office: Office, session: str, ref: str | None) -> str:
    """The studio's state in a few lines, for the model to answer from."""
    from diwan.agents import reader, rhythm, strategy, studio
    lines = [business.describe(office) or "The business is not set yet (Setup).", brand.brief(office)]
    why = reader.patterns(office)
    for a in why["accounts"]:
        lines.append(f"@{a['account']}: {a['read']} of {a['posts']} posts read, {a['winners']} above their average."
                     + (f" Patterns: {' '.join(f['finding'] for f in a['patterns'])}" if a["patterns"] else f" {a['need']}")
                     + (f" Tone of their best: {a['tone']}." if a["tone"] else "")
                     + (f" For the business: {' '.join(a['business'])}" if a.get("business") else "")
                     + (f" Seasonal winners: {', '.join(x['season'] for x in a['seasonal'])}." if a.get("seasonal") else ""))
    o = why["ours"]
    if o["read"]:
        lines.append(f"Our posts: {o['read']} read, {o['winners']} above our average. " + (" ".join(f["finding"] for f in o["patterns"]) or o["need"]))
        lines += [f"Our weak post \"{w['hook'][:60]}\": {w['why']}. Advice: {' '.join(w['advice']) or 'none yet'}" for w in o["weak"][:3]]
    lines.append("Angles: " + "; ".join(f"{x['angle']} is {x['status']}" for x in strategy.report(office)["angles"]))
    if (p := rhythm.current(office)):
        lines.append("The plan: " + "; ".join(f"{d['date']} {d['ref']}" for d in p["days"]))
    for n in office.graph().of("request", status="open"):
        if n.props.get("kind") == "use_script":
            for s in studio.script_options(office, n.props["text"]):
                lines.append(f"Script {s['id']} for {s['ref']} ({s.get('angle')}), waiting to be picked: \"{s['hook_en']}\" / " + " / ".join(s["lines_en"]))
    from diwan.agents import rhythm as _r
    lines.append("What we can make videos for (products, services, listings): " + ", ".join(f"{x['ref']} ({x.get('title')})" for x in _r.listings(office)))
    for u in uploads(office, session):
        told = {k: u[k] for k in ("kind", "whose", "likes", "comments") if u.get(k)}
        missing = [k for k in ("kind", "whose", "likes", "comments") if k not in told]
        a = u.get("analysis") or {}
        lines.append(f"Upload {u['upload']} ({u.get('name')}, {'video' if u.get('mime', '').startswith('video/') else 'picture'}). "
                     f"The manager told you: {json.dumps(told) if told else 'nothing yet'}. Not told yet: {', '.join(missing) or 'nothing'}. "
                     f"Measured by the studio: {json.dumps(a.get('measured') or 'nothing (a picture)')}. "
                     + (f"Speech ({a.get('speech_via')}): {a.get('speech')[:600]}. " if a.get("speech") else "")
                     + f"Read from the frames by Muse Spark: {json.dumps(a.get('read') or a.get('comments') or 'not read', ensure_ascii=False)[:1200]}")
    if ref:
        lines.append(f"The listing open in the studio: {ref}.")
    return "\n".join(x for x in lines if x)


SYSTEM = (
    "You are the Marketing lead of the business's content studio, talking with the Marketing manager. You know marketing only: "
    "content, competitors, scripts, filming, editing, publishing, ads. For leads, customers, viewings or WhatsApp, say that is the "
    "Sales team's (Rania) and stay on marketing.\n"
    "Answer from the studio's data below and from what the person says; never invent a number, a post or a result. Keep apart what was "
    "measured, what the person told you, and what you do not know, and say which. Talk the way a colleague would: a few natural, "
    "complete sentences (you may be read aloud), never a list of one-word fragments.\n"
    "Choose one action:\n"
    "- search_posts: fetch an account's posts (account without @; since/until as YYYY-MM-DD, empty if not given)\n"
    "- read_our_ads: read our own ad account\n"
    "- ask_upload: the person has a file on their device; ask them to upload it\n"
    "- note_facts: the person told you about the latest upload: kind (reel, post, carousel, comments screenshot), whose (@account or us), likes, comments\n"
    "- revise_script (script id, note), run_listing (ref), plan_week: changes. Propose them in reply and wait: they are done only after a yes\n"
    "- confirm / cancel: the person answered yes or no to the change you proposed\n"
    "- none: just answer\n"
    "After an upload, if you do not know what it is, whose it is, or its likes and comments, ask for them (and for a screenshot of its "
    "comments). Explain why a post worked only from its analysis and the numbers given. Fill unused fields with empty strings.")


def _model_turn(office: Office, session: str, text: str, ref: str | None, extra: str = "") -> dict:
    c = get("mkt")
    talk = "\n".join(f"{'Manager' if h['who'] == 'person' else 'You'}: {h['text']}" for h in history(office, session)[-14:] if h.get("who") in ("person", "lead"))
    wait = pending(office, session)
    user = runner.user_message((f"Waiting for a yes on: {json.dumps(wait)}\n" if wait else "") + f"The manager says: {text}" + (f"\n\n{extra}" if extra else ""),
                               {"studio": context(office, session, ref), "conversation": talk or "(this is the start)"})
    if not runner.has_model(c, SYSTEM, user, schema=SCHEMA):
        return {"reply": "I need Muse Spark to talk (the Meta key, within Marketing's budget). The studio's screens still work.", "action": "none"}
    try:
        return runner.call(c, SYSTEM, user, schema=SCHEMA, timeout=150).data
    except Exception:  # noqa: BLE001  one more try: a slow answer is usually a busy endpoint
        return runner.call(c, SYSTEM, user, schema=SCHEMA, timeout=150).data


# ---------- actions ----------

def _search(office: Office, a: dict) -> str:
    from diwan.agents import studio
    acc = (a.get("account") or "").lstrip("@").strip()
    if not acc:
        return "No account was named."
    if not instagram.ready():
        return "Instagram is not connected, so posts cannot be fetched."
    try:
        r = instagram.posts_between(acc, a.get("since") or None, a.get("until") or None)
    except instagram.InstagramError as e:
        return f"Instagram could not read @{acc}: {e}"
    ps = studio.scored(r["posts"])
    for p in ps:
        office.log.append("post.seen", actor="mrival", agent="mrival", key=f"post:{p['id']}:{p['engagement']}", content={**p, "source": "competitor", "followers": r.get("followers")})
    top = sorted(ps, key=lambda p: -p["engagement"])[:5]
    span = f"between {a.get('since') or 'the start'} and {a.get('until') or 'today'}"
    return (f"@{r['username']}: {len(ps)} posts {span} (read {r['read']}, back to {r['oldest']}). " +
            " ".join(f"[{(p['at'] or '')[:10]}, {p.get('type')}] {p['likes']:,} likes, {p['comments']:,} comments, {p['score']}x their average: \"{(p['caption'] or '')[:80]}\""
                     for p in top))


def _ads() -> str:
    from diwan.providers import ads
    if not ads.ready():
        return f"Our ads need {', '.join(ads.missing()) or 'online mode'}."
    try:
        r = ads.report()
    except ads.AdsError as e:
        return f"Meta refused: {e}"
    return f"{r['name']} ({r['currency']}), last 30 days: total {r['total']}. Ads: " + "; ".join(f"{x['name']} {x['status']} spend {x['spend']} reach {x['reach']} leads {x['leads']}" for x in r["ads"])


def _do(office: Office, p: dict, by: str) -> str:
    """Carry out a change the person said yes to. Long work runs in the background and shows on the Run tab."""
    from diwan.agents import rhythm, studio
    if p["action"] == "plan_week":
        plan = rhythm.make_plan(office, business.local(studio._now(), office).date(), auto=False, by=by)
        return "Planned: " + "; ".join(f"{d['date']} {d['ref']}" for d in plan["days"])
    if p["action"] == "run_listing":
        ref = p.get("ref")
        if f"listing:{ref}" not in office.graph().nodes:
            return f"There is no listing {ref}."
        threading.Thread(target=lambda: asyncio.run(studio.run(office, ref, pause=0)), daemon=True).start()
        return f"Started a run for {ref}: the scripts will wait on the Run tab."
    if p["action"] == "revise_script":
        sid, note = p.get("script"), p.get("note")
        req = next((n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script"
                    and sid in [x["id"] for x in studio.script_options(office, n.props["text"])]), None)
        if not req or not note:
            return f"Script {sid} is not waiting to be picked, so it cannot be changed here."
        ref = next(x["ref"] for x in studio.script_options(office, req.props["text"]) if x["id"] == sid)
        office.log.append("decision.made", actor=by, content={"card": req.id, "answer": "revise", "choice": sid, "note": note})
        threading.Thread(target=lambda: asyncio.run(studio.script_revise(office, ref, sid, note, req.id, pause=0)), daemon=True).start()
        return f"Sent {sid} back to the Script writer: \"{note}\". The new version will wait on the Run tab."
    return "Nothing to do."


def say(office: Office, session: str, text: str, *, by: str, ref: str | None = None) -> dict:
    """One thing the person said; returns the lead's answer: {reply, pending?, upload?: True when a file is asked for}."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Say something first.")
    office.log.append("mchat.said", actor=by, agent="mkt", content={"session": session, "who": "person", "text": text})
    d = _model_turn(office, session, text, ref)
    act, out = d.get("action", "none"), {}
    if act in ("search_posts", "read_our_ads"):
        found = _search(office, d) if act == "search_posts" else _ads()
        d = _model_turn(office, session, text, ref, extra=f"What the {'search' if act == 'search_posts' else 'ad account'} returned (answer from this):\n{found}") | {"action": "none"}
        out["found"] = found
    elif act == "note_facts":
        ups = uploads(office, session)
        if ups:
            office.log.append("mchat.upload", actor=by, agent="mkt", content={"session": session, "upload": ups[-1]["upload"],
                              **{k: d.get(k, "") for k in ("kind", "whose", "likes", "comments") if d.get(k)}})
    elif act in CHANGES:
        out["pending"] = {k: d.get(k, "") for k in ("script", "note", "ref") if d.get(k)} | {"action": act}
    elif act in ("confirm", "cancel") and (p := pending(office, session)):
        d["reply"] = (d["reply"] + " " if d.get("reply") else "") + (_do(office, p, by) if act == "confirm" else "Left as it was.")
    elif act == "ask_upload":
        out["upload"] = True
    office.log.append("mchat.said", actor="mkt", agent="mkt", content={"session": session, "who": "lead", "text": d["reply"], "action": act, **out})
    return {"reply": d["reply"], "action": act, **out}


# ---------- uploads ----------

def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, timeout=300)


def _transcribe(path: Path) -> dict:
    """Speech in a video: local Whisper first (free), then Muse Voice Transcribe."""
    from diwan.agents import studio
    wav = studio._wav(path)
    if local_asr.available():
        try:
            return local_asr.transcribe(wav) | {"via": "local Whisper"}
        except Exception:  # noqa: BLE001  fall through to Muse Voice
            pass
    if meta.ready():
        return meta.transcribe(wav) | {"via": "Muse Voice Transcribe"}
    return {"text": "", "via": "nothing could transcribe it"}


def measure(path: Path) -> dict:
    """What can be measured from a video: its length, the cuts (scene changes) and how often they come."""
    from diwan.agents import studio
    dur = studio._duration(path)
    r = _run("ffmpeg", "-v", "info", "-i", str(path), "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-")
    cuts = len(re.findall(r"pts_time:", r.stderr))
    return {"seconds": round(dur, 1), "cuts": cuts, "seconds_per_cut": round(dur / (cuts + 1), 1) if dur else None}


def _frames(path: Path, n: int = 6) -> list[bytes]:
    from diwan.agents import studio
    dur, out = studio._duration(path), []
    for i in range(n):
        f = path.with_name(f"{path.stem}-f{i}.jpg")
        studio._ffmpeg("-ss", f"{dur * (i + .5) / n:.2f}", "-i", str(path), "-frames:v", "1", "-vf", "scale=540:-2", str(f))
        if f.exists():
            out.append(f.read_bytes())
    return out


def add_upload(office: Office, session: str, path: Path, name: str, mime: str, *, by: str, facts: dict | None = None) -> dict:
    """A file the person uploaded into the conversation: recorded, then analysed (paid: Muse Spark reads the frames)."""
    n = 1 + sum(1 for e in office.log.list() if e["type"] == "mchat.upload" and e["content"].get("path"))
    uid = f"U{n}"
    office.log.append("mchat.upload", actor=by, agent="mkt", content={"session": session, "upload": uid, "path": str(path), "name": name, "mime": mime,
                                                                       **{k: v for k, v in (facts or {}).items() if v}})
    return analyse(office, session, uid)


def analyse(office: Office, session: str, uid: str) -> dict:
    u = next(x for x in uploads(office, session) if x["upload"] == uid)
    path, video = Path(u["path"]), u["mime"].startswith("video/")
    res: dict = {}
    if video:
        res["measured"] = measure(path)
        t = _transcribe(path)
        res["speech"], res["speech_via"] = t["text"][:2000], t["via"]
    if not meta.ready():
        res["read"] = "Reading the pictures needs Muse Spark (the Meta key)."
    else:
        imgs = _frames(path) if video else [path.read_bytes()]
        sys_ = ("You read one social media post for a marketing team. " + business.describe(office) + " Describe only what the pictures and words show; "
                "never guess numbers. carries_over is false when it is about its owner's own moment (an event, award, signing, celebration, "
                "holiday, launch); then why_not says which. for_us: what our business could make from it, in our own words, never copying it.")
        try:
            if u.get("kind") == "comments screenshot":
                res["comments"] = meta.look("You read a screenshot of a post's comments. List what people asked, liked and worried about, in their words.",
                                            "The comments:", imgs, COMMENTS, agent="mkt")
            else:
                res["read"] = meta.look(sys_, f"A {'video' if video else 'picture'}"
                                        + (f"; spoken words: {res['speech'][:1500]}" if res.get("speech") else "")
                                        + (f"; measured: {res['measured']}" if video else "") + ". Frames in order.", imgs, LOOK, agent="mkt")
        except meta.MetaError as e:
            res["read"] = f"Muse Spark could not read it: {e}"
    office.log.append("mchat.analysed", actor="mkt", agent="mkt", content={"session": session, "upload": uid, "analysis": res})
    return res
