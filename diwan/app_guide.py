"""What the PAs know about Diwan itself: what is set up right now, which models run, this month's spend, and what each
page is for. Nova answers "is my WhatsApp connected?" or "where do I add a lead?" from this, never from a guess.

Only whether a key is set is ever read here, never the key. A staff member's PA hears about the pages that person may open,
and not the owner's own WhatsApp or the spend.
"""
from __future__ import annotations

import re

from diwan.config import env, offline, tape_mode

# Every page, as the person sees it in the top bar: what it is for and how the usual things are done there.
PAGES = [
    ("office3d.html", "Office", "the 3D office: every department is a room and the agents are at their desks",
     "Click a room to enter it, click Whole office to come back. The Demo bar has 'Karim corrects himself' and Reset."),
    ("index.html", "Nova", "your chief of staff: the briefing, what needs you, your notebook and reminders",
     "Go live to talk out loud. The modes are At my desk, Hey Pocket (a meeting: I stay silent and keep the words) and Do not disturb."),
    ("personal.html", "My WhatsApp", "the owner's own WhatsApp, read by Nova for the owner alone, never the sales line",
     "Until the personal number is connected, the stand-in phone on that page feeds the same path."),
    ("sales.html", "Sales", "the Sales room: who to call now, outcomes after calls, the pipeline and each broker's day",
     "+ Add a lead (top right) for a walk-in, call or referral. After a call, record what came of it under Outcome needed."),
    ("inbox.html", "Inbox", "every WhatsApp and Instagram conversation with clients, with Rania replying",
     "The switch on a chat takes over from Rania or hands it back. The Sandbox phone writes as a client. Converted…, Follow up on…, Not interested… and Transfer to are on each chat."),
    ("calendar.html", "Calendar", "appointments and viewings for every broker",
     "Add an appointment, set a day off or busy time, and the hours, reminders and video settings. It opens from the Inbox."),
    ("studio.html", "Studio", "marketing: our business, brand, products and occasions, competitors, scripts, approvals, campaigns and video",
     "Scripts come from a listing; pick one, approve it, then post now or schedule it. AI video and free video are made here."),
    ("meeting.html", "Meeting", "the meeting table: nothing is heard until the client agrees, then the Scribe turns what is said into facts",
     "Start a meeting on a deal, tap The customer agrees, then add what is said. Approve all sends out the work it found."),
    ("deal.html", "Deals", "the Deal desk: every deal's gates, paperwork, money, compliance and the latest correction",
     "Tabs: Overview, My work, Deals, Board, Compliance, Finance, Operations. Mark what arrived, Re-approve and Mark lost are on a deal."),
    ("lobby.html", "Lobby", "each room's weekly lesson, playbooks and experiments the owner approves",
     "Propose an experiment; it runs on part of the leads and is kept only if Records shows it works."),
    ("knowledge.html", "Knowledge", "what the office tells clients once: company answers, listings and items, with their history",
     "Add a listing or Add an item; changes that need a yes wait under Waiting for a decision."),
    ("catalog.html", "Catalog", "the listings catalog with photos, map and area guide", "Price changes are proposed here and wait for a yes."),
    ("graph.html", "Memory", "how work flows between the agents", "Add an agent, or pause, resume and remove one."),
    ("team.html", "Team", "every agent's charter, its latest work and its lessons", "Teach an agent a lesson, and set how much it may do alone."),
    ("qualify.html", "Qualification", "what a lead must tell us, the front door, and follow-ups when a client goes quiet", "Try it shows how Rania would ask."),
    ("settings.html", "Settings", "connections and rules",
     "Tabs: WhatsApp line, Instagram, Meta models, Portals, Qualification, Sales rules, Team, Video (Zoom links and the HeyGen presenter), Logins, Kinds of deal."),
]

HOW = [
    (r"whatsapp", "The sales WhatsApp line is connected in Settings, WhatsApp line, through AiSensy or Meta's Cloud API. Until then clients are simulated with the Sandbox phone in the Inbox."),
    (r"instagram", "Instagram is connected in Settings, Instagram."),
    (r"\bzoom\b", "Zoom is connected in Settings, Video, under 'Zoom · links for video calls', with a Server-to-Server OAuth app from your Zoom account."),
    (r"\b(heygen|presenter)\b", "The AI presenter is connected in Settings, Video, under HeyGen."),
    (r"\b(login|password|sign[- ]?in|account)s?\b", "Staff logins and passwords are set in Settings, Logins."),
    (r"\b(lead|walk[- ]?in|referral)\b", "To add a lead by hand: Sales, + Add a lead."),
    (r"\b(listing|propert(y|ies))\b", "To add a listing: Knowledge, Add a listing. The Catalog shows them with photos and a map."),
    (r"\b(appointment|viewing|day off|calendar)\b", "Appointments, viewings and days off are on the Calendar, opened from the Inbox."),
    (r"\b(agent|autonomy|lesson|teach)\b", "Agents are on the Team page: teach them a lesson there or set how much they may do alone."),
    (r"\b(brief|briefing)\b", "Say 'brief me at 8' and I'll have the briefing ready then."),
    (r"\b(video|reel|script|post)\b", "Scripts, videos and posts are made in the Studio."),
    (r"\b(model|muse|ai)\b", "Which Meta models run is set in Settings, Meta models."),
]

LINE = {"aisensy": "AiSensy", "cloud": "Meta's WhatsApp Cloud API"}
MODEL = {"meta": "Muse Spark on Meta's API", "baseten": "Muse Spark Open on Baseten", "fireworks": "Fireworks", "modal": "Modal", "nvidia": "Muse Glimmer on NVIDIA"}


def _set(*keys: str) -> bool:
    return all(bool(env(k)) for k in keys)


def status() -> dict:
    """The live state: what is set up, which models answer, and this month's spend. Yes and no only: no key is ever read out.
    "Set up" means its keys are in place; nothing here sends a test message."""
    from diwan import costs, ownerline
    from diwan.providers import aisensy, voice, whatsapp
    from diwan.providers import email as mail
    from diwan.providers import zoom
    from diwan.providers.chat import PROVIDERS
    ready = {"aisensy": aisensy.available(), "cloud": whatsapp.available()}
    chosen = env("WHATSAPP_PROVIDER") or next((k for k, on in ready.items() if on), "sandbox")
    spend = costs.summary()
    return {
        "whatsapp": {"line": chosen, "connected": ready.get(chosen, False), "named_not_ready": chosen in ready and not ready[chosen]},
        "owner_whatsapp": {"connected": ownerline.connected(), "sending": env("PERSONAL_WHATSAPP_SENDING") == "on"},
        "instagram": _set("IG_ACCESS_TOKEN", "IG_USER_ID"),
        "email": mail.available(), "zoom": zoom.available(), "voice": voice.available(),
        "heygen": _set("HEYGEN_API_KEY", "HEYGEN_AVATAR_ID", "HEYGEN_VOICE_ID"),
        "listing_feed": _set("LISTING_FEED_URL"),
        "models": {p.id: p.available() for p in PROVIDERS.values()},
        "offline": offline(), "tapes": tape_mode(),
        "spend": {"month": spend["month"], "spent": round(spend["spend_usd"], 2), "budget": round(spend["budget_usd"], 2), "over": spend["over"]},
        "sign_in": env("DIWAN_AUTH", "on") != "off",
        "logins": _logins(),
    }


def _logins() -> dict[str, bool]:
    """Who can sign in today: a staff member with no password set can't, whatever the sign-in setting says."""
    from diwan import access
    try:
        return {pid: access.has_password(pid) for pid in access.PEOPLE}
    except Exception:  # noqa: BLE001  no auth database yet: nobody has a login
        return {}


def facts(s: dict) -> dict[str, str]:
    """One plain sentence per part of the app."""
    wa, own = s["whatsapp"], s["owner_whatsapp"]
    models = [MODEL.get(k, k) for k, on in s["models"].items() if on]
    on = lambda b, what: f"{what} is set up." if b else f"{what} is not set up."  # noqa: E731
    if wa["connected"]:
        sales = f"The office's sales WhatsApp line, the number clients write to, is connected through {LINE[wa['line']]}."
    else:
        sales = ((f"The office's sales WhatsApp line, the number clients write to, is not connected: {LINE[wa['line']]} is chosen but its keys are missing"
                  if wa["named_not_ready"] else "The office's sales WhatsApp line, the number clients write to, is not connected")
                 + ", so clients are simulated with the Sandbox phone in the Inbox. It is connected in Settings, WhatsApp line.")
    return {
        "whatsapp": sales,
        "owner_whatsapp": ("The owner's own personal WhatsApp number, separate from the sales line, is connected" + ("." if own["sending"] else ", reading only: sending is off.")
                           if own["connected"] else "The owner's own personal WhatsApp number, separate from the sales line, is not connected yet; "
                           "the stand-in phone on the My WhatsApp page feeds Nova meanwhile."),
        "instagram": on(s["instagram"], "Instagram"), "email": on(s["email"], "Email sending"), "zoom": on(s["zoom"], "Zoom"),
        "voice": on(s["voice"], "Voice transcription (Muse Voice)"), "heygen": on(s["heygen"], "The AI presenter for video (HeyGen)"),
        "feed": on(s["listing_feed"], "The portal listing feed"),
        "models": ("The AI models connected are " + ", ".join(models) + "." if models else "No AI model is connected, so the agents use their rules.")
                  + (" The office is set to offline, so only recorded replies are used." if s["offline"] else ""),
        "spend": f"AI spend this month is USD {s['spend']['spent']:.2f} of the USD {s['spend']['budget']:.2f} budget"
                 + (": the cap is reached, so agents use their rules until next month." if s["spend"]["over"] else "."),
        "sign_in": "Sign-in is on." if s["sign_in"] else "Sign-in is off: anyone with the address can open the office.",
        "logins": _login_line(s),
    }


def _login_line(s: dict) -> str:
    from diwan.people import PEOPLE
    has = [PEOPLE[p]["name"] for p, ok in s["logins"].items() if ok]
    not_yet = [PEOPLE[p]["name"] for p, ok in s["logins"].items() if not ok]
    if not s["sign_in"]:
        return "Sign-in is off, so no one needs a login to open the office."
    return ("Logins: " + (", ".join(has) + " can sign in" if has else "no one can sign in yet")
            + (f"; {', '.join(not_yet)} have no password yet, set in Settings, Logins." if not_yet else "; everyone has a login."))


def _owner(person: str | None) -> bool:
    from diwan import access
    return not person or access.is_owner(person)


def pages_for(person: str | None) -> list[tuple]:
    from diwan import access
    return PAGES if _owner(person) else [p for p in PAGES if access.may_open(person, p[0])]


def lines(person: str | None) -> list[str]:
    """What a PA's picture of the office says about the app itself."""
    f = facts(status())
    if not _owner(person):
        f.pop("owner_whatsapp")
        f.pop("spend")
        f.pop("logins")
    return [f"App: {v}" for v in f.values()]


def page_lines(person: str | None) -> list[str]:
    """What each page is for and how things are done there: sent to the model only when the question is about the app."""
    return [f"App page {name}: {what}. {how}" for _, name, what, how in pages_for(person)]


ABOUT = re.compile(r"\b(connect\w*|set ?up|linked|working|live|status|integrat\w*|models?|budget|spen[dt]|cost|log ?in|logins|password|"
                   r"where (do|can|should) i|how (do|can|should) i|which page|what page|where is|page)\b", re.I)
KEYS = [(r"\binstagram\b", "instagram"), (r"\bzoom\b", "zoom"), (r"\be-?mail\b", "email"), (r"\b(heygen|presenter)\b", "heygen"),
        (r"\b(voice|transcri\w*|microphone)\b", "voice"), (r"\b(feed|portal)s?\b", "feed"), (r"\b(log ?in|logins|password|sign[- ]?in)\b", "logins")]


def answer(question: str, person: str | None) -> str | None:
    """A plain answer about the app, for when no model is there. None if the question isn't about the app."""
    q = question.lower()
    if not ABOUT.search(q):
        return None
    owner, f = _owner(person), facts(status())
    asks_how = re.search(r"\bhow (do|can|should) i\b|\bwhere (do|can|should) i\b", q)
    if "whatsapp" in q and not asks_how:
        if re.search(r"\b(my own|personal|private|my number|family)\b", q):
            return f["owner_whatsapp"] if owner else None
        return f["whatsapp"] + (" " + f["owner_whatsapp"] if owner and re.search(r"\bmy\b", q) else "")
    if not asks_how:
        for rx, k in KEYS:
            if re.search(rx, q) and k in f and (k != "logins" or owner):
                return f[k]
        if owner and re.search(r"\b(budget|spen[dt]|cost)\b", q) and re.search(r"\b(ai|models?|muse|meta|api|budget|tokens?)\b", q):
            return f["spend"]  # "what did we spend last month?" is the office's own spending, which Records answers
        if re.search(r"\b(models?|muse)\b", q):
            return f["models"]
    for rx, how in HOW:
        if asks_how and re.search(rx, q):
            return how
    if re.search(r"\b(page|where is|which page|what page)\b", q):
        for _, name, what, how in pages_for(person):
            if re.search(rf"\b{name.lower()}\b", q):
                return f"{name} is {what}. {how}"
    return None
