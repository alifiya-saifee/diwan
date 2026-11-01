"""Where our account is, and what the next post is for. The strategy picks how to say something; this picks what needs
saying, the way a marketing lead does before anyone writes a line:

  a moment    something that matters more than the plan: a new project, or news a person typed with its facts
  comeback    the account went quiet: say we are back before anything else
  introduce   fewer than 9 posts: the first nine below, so a stranger meets us before being sold to
  build, grow the usual mix (rhythm), with the angles chosen from our own results (strategy)

Zero posts only means a new account when Instagram is connected or a person said so; otherwise it asks.
A job with nothing true to say is skipped and says why. See docs/content-journey-spec.md.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from datetime import date, datetime, timedelta

from diwan import brand, business, knowledge as kn, topics
from diwan.office import Office
from diwan.providers import instagram

FIRST_NINE = ("introduce", "why-us", "educate", "offer", "prove", "educate", "offer", "team", "educate")
INTRO_POSTS, GROW_POSTS = 9, 30
SILENT_DAYS = 45       # no post for this long is a comeback
NEW_PROJECT_DAYS = 14  # a project card confirmed this recently is a moment
NEW_LISTING_DAYS, BULK_LISTINGS = 7, 3  # a listing added this recently is too, unless it came in a batch: an import is not news
HOUSEKEEPING = {"fees", "hours", "policy", "policies", "contact"}  # true, but not what a brand post is about, and their numbers are not results

STAGES = {"unknown": "Not known yet", "introduce": "Introduce", "build": "Build trust", "grow": "Grow", "comeback": "Comeback"}
JOBS = {  # job: label, what the post must do, how it closes; the brand's own jobs also have a title, hook and angles
    "introduce": {"label": "Introduce us", "title": "Meet {name}", "hook": "Meet {name}.", "what": "Who we are, who we help and why to follow us",
                  "brief": "This is the first thing a stranger sees. Say who we are, who we help and what they get from following us. Sell nothing.",
                  "close": "Close by inviting them to follow and to message us with what they are looking for.",
                  "angles": {"say-hello": "A person from the business says hello to camera and says who they help",
                             "who-we-help": "Open on the viewer and what they need, then say that is who we are here for",
                             "why-we-exist": "Why the business exists, as one short story, only from the facts given"}},
    "why-us": {"label": "Why us", "title": "Why {name}", "hook": "Why people choose {name}.", "what": "What makes us different",
               "brief": "Say what is different about us, in terms of what the viewer gets. Give one reason well, not a list. Sell nothing yet.",
               "close": "Close by inviting them to ask us anything.",
               "angles": {"what-you-get": "What the viewer gets from us that they would not get elsewhere",
                          "how-we-work": "How we work, one step that shows the difference",
                          "what-we-wont-do": "What we refuse to do, and why that helps the viewer"}},
    "prove": {"label": "Show proof", "title": "What {name} has done", "hook": "What {name} has done so far.", "what": "Real results",
              "brief": "Show a real result. Use only the numbers given, exactly as given, and do not round them up.",
              "close": "Close by inviting them to get in touch.",
              "angles": {"the-number": "Open on the strongest real number, then what it means for the viewer",
                         "one-result": "One real result, told simply",
                         "what-it-took": "What it took to get that result"}},
    "team": {"label": "Meet the team", "title": "The people at {name}", "hook": "The people behind {name}.", "what": "Who the viewer will deal with",
             "brief": "Show who the viewer will actually deal with. People trust people.",
             "close": "Close by inviting them to message the team.",
             "angles": {"meet-one": "One person, what they do and who they help", "who-does-what": "Who the viewer meets, in order",
                        "a-day-here": "What the team does for a client in one day, only from the facts given"}},
    "comeback": {"label": "Come back", "title": "{name} is back", "hook": "{name} is back.", "what": "We are back, and what is coming",
                 "brief": "We have been quiet. Say so plainly, without apologising at length, and say what followers will get now.",
                 "close": "Close by inviting them to tell us what they want to see.",
                 "angles": {"what-is-next": "What is coming next", "what-we-did": "What we were doing while we were quiet, only from the facts given",
                            "ask-them": "Ask followers what they want to see"}},
    "educate": {"label": "Teach something", "brief": "Teach one useful thing to a viewer who will not buy today. Do not sell in this post."},
    "offer": {"label": "Offer something", "brief": "Now show what we offer, with its real facts."},
    "moment": {"label": "Something new", "brief": "This is about something that just happened. Say what it means for the viewer, using only the facts given. Stay calm and useful.",
               "angles": {"what-happened": "Say plainly what happened", "what-it-means": "Open on what it means for the viewer, then what happened",
                          "what-to-do": "What the viewer can do now, only from the facts given"}},
}
ANGLES = {a: text for j in JOBS.values() for a, text in j.get("angles", {}).items()}


def _today(office: Office) -> date:
    from diwan.agents import studio
    return business.local(studio._now(), office).date()


def _cards(office: Office, tab: str = "company") -> list:
    return [n for n in office.graph().of("knowledge") if kn.tab(n) == tab and kn.usable(n) and (n.props.get("text") or "").strip()]


def company(office: Office, about: str = "", k: int = 6) -> list[str]:
    """The confirmed, customer-facing company facts, the ones sharing most words with `about` first."""
    want = set(re.findall(r"[a-z]{4,}", about.lower()))
    cards = sorted([n for n in _cards(office) if (n.props.get("kind") or "") not in HOUSEKEEPING], key=lambda n: -len(want & set(re.findall(r"[a-z]{4,}", f"{n.props.get('title', '')} {n.props['text']}".lower()))))
    return [f"{n.props.get('title') or n.label}: {n.props['text'].strip()}" for n in cards[:k]]


def _facts(office: Office, job: str) -> list[str]:
    p = brand.profile(office)
    if job == "team":
        return [s for n in _cards(office, "people") for s in topics._facts(n.props["text"])][:8]
    sentences = [s for n in _cards(office) if (n.props.get("kind") or "") not in HOUSEKEEPING for s in topics._facts(n.props["text"])]
    if job == "prove":
        return [s for s in sentences if re.search(r"\d", s)][:8]
    own = [x for x in (p["positioning"]["value"], f"We are here for {p['audience']['value']}." if p["audience"]["value"] else "") if x]
    return ([*own, *sentences][:8]) if own else []


def item(office: Office, ref: str) -> dict | None:
    """A post about the brand itself, shaped like a topic so it goes through the same steps. None when there is nothing
    true to say yet."""
    job = ref[4:] if ref.startswith("JOB-") else ""
    j = JOBS.get(job)
    name = brand.profile(office)["name"]["value"].strip()
    if not j or "angles" not in j or job == "moment" or not name:
        return None
    facts = _facts(office, job)
    if not facts:
        return None
    return {"ref": ref, "title": j["title"].format(name=name), "hook": j["hook"].format(name=name), "what": j["what"], "features": facts,
            "source": "job", "kind": "topic", "job": job, "from": "the brand profile and confirmed company cards"}


def items(office: Office) -> dict[str, dict]:
    return {f"JOB-{j}": t for j in JOBS if (t := item(office, f"JOB-{j}"))}


def job_of(lst: dict) -> str:
    return lst.get("job") or ("moment" if lst.get("moment") else "educate" if lst.get("item") == "topic" else "offer")


def pick_angles(job: str, n: int, avoid: set[str]) -> list[dict]:
    angles = JOBS[job]["angles"]
    order = ([a for a in angles if a not in avoid] + [a for a in angles if a in avoid])[:n]
    return [{"angle": a, "slot": JOBS[job]["label"], "why": angles[a]} for a in order]


def account(office: Office) -> dict:
    """What we know about our own account: posts seen, the last one's date, and scripts approved but not posted yet (an
    approved script counts, because publishing may be off)."""
    from diwan.agents import rhythm, studio
    ours = studio.posts(office, "own")
    published = sum(1 for e in office.log.list() if e["type"] == "content.made" and e["content"].get("kind") == "published")
    days = [p["at"][:10] for p in ours if p.get("at")]
    return {"posts": len(ours), "last": max(days, default=None), "waiting": max(0, len(rhythm.used(office)) - published)}


_TRIED = {"at": 0.0}  # a failed read is not repeated on every page load


def own_read(office: Office) -> str | None:
    """The day our own posts were last read from Instagram, even if there were none."""
    return next((e["content"]["value"] for e in reversed(office.log.list()) if e["type"] == "setting.changed"
                 and e["content"].get("person") == "journey" and e["content"].get("key") == "own_read"), None)


def read_own(office: Office) -> None:
    """Read our own posts, at most once a day: "connected, no posts seen" means nothing until someone has looked."""
    today = _today(office).isoformat()
    if not instagram.ready() or own_read(office) == today or time.time() - _TRIED["at"] < 600:
        return
    _TRIED["at"] = time.time()
    try:
        ours = instagram.own_posts()
    except instagram.InstagramError:
        return
    for p in ours:
        office.log.append("post.seen", actor="mrival", agent="mrival", key=f"own:{p['id']}:{p['likes']}:{p['comments']}",
                          content={**p, "source": "own", "engagement": p["likes"] + p["comments"]})
    office.log.append("setting.changed", actor="mrival", content={"person": "journey", "key": "own_read", "value": today})


def stage(office: Office) -> str:
    from diwan.agents import rhythm
    a = account(office)
    if not a["posts"]:
        said = "no" if own_read(office) else business.get(office).get("posted_before", "")  # read and empty: it really is new
        if not said:
            return "unknown"
        if said == "yes":
            return "build"
    if a["last"] and (_today(office) - date.fromisoformat(a["last"])).days > SILENT_DAYS:
        if not any(u.get("job") == "comeback" and u["at"] >= a["last"] for u in rhythm.used(office)):
            return "comeback"
    total = a["posts"] + a["waiting"]
    return "introduce" if total < INTRO_POSTS else "build" if total < GROW_POSTS else "grow"


def _confirmed_on(office: Office) -> dict[str, str]:
    """When each knowledge card was last confirmed by a person (the demo's own seed does not count as news)."""
    out = {}
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "knowledge.confirmed" or e["type"] == "knowledge.added" and c.get("confirmed") and c.get("source") != "demo":
            out[c["id"]] = e["at"][:10]
    return out


def _new_listings(office: Office, today: date, done: set[str]) -> list[dict]:
    """Listings added by themselves in the last few days that can be posted about, newest first."""
    from diwan.agents import rhythm
    first, batch = {}, Counter()
    for e in office.log.list():
        ref = e["content"].get("ref")
        if e["type"] == "listing.added" and e["content"].get("title") and ref not in first:
            first[ref] = (e["at"][:10], e["actor"], e["content"]["title"])
            batch[e["actor"], e["at"][:10]] += 1
    live = {x["ref"] for x in rhythm.listings(office)}
    new = [(on, ref, title) for ref, (on, who, title) in first.items() if ref in live and ref not in done
           and batch[who, on] <= BULK_LISTINGS and (today - date.fromisoformat(on)).days <= NEW_LISTING_DAYS]
    return [{"job": "moment", "ref": ref, "title": title, "type": "listing", "why": f"Just added on {on}, so show it while it is new"} for on, ref, title in sorted(new, reverse=True)]


def moments(office: Office) -> list[dict]:
    """What matters more than the plan right now: typed moments still in date, projects newly confirmed and listings just
    added, until a script for them is approved."""
    from diwan.agents import rhythm
    today = _today(office)
    done = {u["ref"] for u in rhythm.used(office)} | rhythm.stopped_lately(office, today)  # stopped means no: it does not come back as news
    out = [{"job": "moment", "ref": t["ref"], "title": t["title"], "type": "topic", "why": f"you added this moment; it holds until {t['until']}"}
           for t in topics.items(office).values() if t.get("moment") and t["ref"] not in done]
    seen = _confirmed_on(office)
    for n in _cards(office, "project"):
        on = seen.get(n.id)
        if on and (today - date.fromisoformat(on)).days <= NEW_PROJECT_DAYS and n.id not in done and n.id in topics.items(office):
            out.append({"job": "moment", "ref": n.id, "title": n.props.get("title") or n.label, "type": "topic", "why": f"a new project, confirmed on {on}"})
    return out + _new_listings(office, today, done)


def _left(office: Office) -> tuple[list[str], list[bool]]:
    """The jobs of the first nine still to do, and which of the nine are done. Each approved script ticks one step."""
    from diwan.agents import rhythm
    done = Counter(u.get("job") or ("offer" if not u["ref"].startswith(("T-", "JOB-")) else "educate") for u in rhythm.used(office))
    ticks = []
    for job in FIRST_NINE:
        ticks.append(done[job] > 0)
        done[job] -= 1
    return [j for j, t in zip(FIRST_NINE, ticks) if not t], ticks


def _subject(office: Office, job: str, day: date, taken: dict) -> tuple[str | None, str]:
    from diwan.agents import rhythm
    if job == "educate":
        return rhythm._pick_topic(office, day, taken)
    if job == "offer":
        return rhythm._pick(office, day, taken)
    t = item(office, f"JOB-{job}")
    if t:
        return t["ref"], "One of your first nine posts"
    if job in ("introduce", "why-us", "comeback"):
        return None, "Add the brand name and \"Who we are\" in Setup first: this post is written from them."
    return None, ("no confirmed company fact has a number in it" if job == "prove" else "no confirmed card on the People tab of Knowledge")


def upcoming(office: Office, n: int, day: date | None = None) -> list[dict]:
    """The next n posts that have a reason to go first; empty when the usual mix decides."""
    read_own(office)
    day = day or _today(office)
    out, taken = list(moments(office)), {}
    st = stage(office)
    jobs = ["comeback"] if st == "comeback" else []
    if st == "introduce":
        left, _ = _left(office)
        a = account(office)
        jobs = left[:INTRO_POSTS - a["posts"] - a["waiting"]]
    stock = [m for m in out if m["type"] == "listing"] if jobs[:1] == ["introduce"] else []  # a stranger meets us before a listing
    out = [m for m in out if m not in stock]
    for job in jobs:
        if len(out) >= n:
            break
        d = day + timedelta(days=len(out))
        ref, why = _subject(office, job, d, taken)
        if not ref and job in ("prove", "team"):
            continue
        if ref:
            taken[ref] = d
        out.append({"job": job, "ref": ref, "why": why, "type": "listing" if job == "offer" else "topic"})
        if not ref:
            break  # the brand's first posts wait for the brand: the rest do not jump ahead of them
    out[1:1] = stock
    return out[:n]


def title_of(office: Office, ref: str | None) -> str:
    from diwan.agents import studio
    try:
        return studio._listing(office, ref)["title"] if ref else ""
    except KeyError:
        return ""


def report(office: Office) -> dict:
    """The Run tab's panel: where the account is, what the next post is for and why, and the first nine."""
    read_own(office)
    st, a = stage(office), account(office)
    why = {"unknown": "No posts can be seen yet, and that is not the same as a new account.",
           "introduce": "A stranger should meet you before being sold to, so the first nine posts follow an order.",
           "build": "Mixing useful posts and offers, the share set in Setup → Rhythm.",
           "grow": "Enough posts to choose angles from your own results.",
           "comeback": f"The last post was on {a['last']}. Say you are back before selling again."}[st]
    if st == "build" and not a["posts"]:
        why = "You said this account has posts, but they can't be seen. Connect Instagram or import them, so the studio can learn from them."
    nxt = upcoming(office, 1)
    left, ticks = _left(office)
    steps, skipped = [], []
    for i, (job, tick) in enumerate(zip(FIRST_NINE, ticks)):
        if not tick and job in ("prove", "team") and not item(office, f"JOB-{job}"):
            skipped.append(f"{JOBS[job]['label']}: {_subject(office, job, _today(office), {})[1]}")
        steps.append({"n": i + 1, "job": job, "label": JOBS[job]["label"], "state": "done" if tick else "not yet"})
    first = next((s for s in steps if s["state"] == "not yet" and s["job"] == (nxt[0]["job"] if nxt else None)), None)
    if first:
        first["state"] = "waiting"
    from diwan.agents import eventpost
    return {"stage": st, "label": STAGES[st], "why": why, "shape": eventpost.suggest(office, nxt[0]["ref"]) if nxt and nxt[0]["job"] == "moment" and nxt[0]["ref"].startswith("T-") else None, "posts": a["posts"], "waiting": a["waiting"], "ask": st == "unknown",
            "next": [x | {"label": JOBS[x["job"]]["label"], "title": x.get("title") or title_of(office, x["ref"])} for x in nxt][0] if nxt else None,
            "moments": moments(office), "steps": steps if st == "introduce" else [], "skipped": skipped if st == "introduce" else []}


def brief(office: Office, lst: dict) -> str:
    """What the writers are told this post is for."""
    job = job_of(lst)
    j = JOBS[job]
    st = stage(office)
    if job == "offer" and st not in ("introduce", "comeback"):
        return ""
    return (f"\n\nThe job of this post: {j['brief']}" + (f" {j['close']}" if j.get("close") else "")
            + (" Most viewers do not know us yet: name the company once, near the end, not in the opening." if st in ("introduce", "comeback") and not lst.get("job") else "")
            + (" Say only what the facts say. Never invent a memory, a story, an experience or a feeling that is not in them. Leave out opening hours, "
               "fees and paperwork: they are not what this post is for." if lst.get("job") or lst.get("item") == "topic" else "")
            + " Trends and competitors' posts below give the format only: the message comes from the facts given.")
