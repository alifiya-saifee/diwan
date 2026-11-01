"""Why their best posts won. Muse Spark reads each competitor post once, the caption of every post and the cover of
those above their account's average, and notes its topic, its hook, who is on screen and what it asks people to do,
and whether it is about the competitor's own moment (an event, an award, a signing), which does not carry over to us.

Then, per account, rules compare the winners with that account's ordinary posts. A pattern is shown only when at least
MIN_WINS winning posts share it and they share it clearly more than the ordinary posts do (GAP); otherwise the account
says how many more it needs. Each pattern ends with what it means for us, pinned to the board for the idea and script
writers. Topics are named by the model for the business's own industry, so nothing here is about one trade.
"""
from __future__ import annotations

from collections import Counter

import httpx

from diwan import brand, business
from diwan.agents import studio
from diwan.office import Office
from diwan.providers import meta

MIN_WINS = 3      # winning posts that must share a trait before it is called a pattern
GAP = 0.25        # how much more often the winners have it than the ordinary posts (25 percentage points)
MAX_COVERS = 10   # covers read per account, the strongest winners first
BATCH = 6         # posts in one call: all of an account's posts in one call took over 3 minutes and timed out

HOOKS = ["a question", "a number or price", "a bold claim", "a story", "a how-to", "something else"]
SCREENS = ["a person talking to camera", "a walkthrough or tour", "text on images", "photos or footage without a person", "something else"]
ASKS = ["send a message", "comment", "call or WhatsApp", "the link in bio", "nothing", "something else"]
OFFERS = ["a discount or deal", "a price shown", "a free trial or demo", "a giveaway or contest", "no offer"]
READ = 2  # how posts are read now; a post read the older way (no offer, no season) is read again once

SCHEMA = {"name": "posts", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["topics", "posts"],
    "properties": {
        "topics": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["label", "for_us"],
                                              "properties": {"label": {"type": "string"}, "for_us": {"type": "string"}}}},
        "posts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                             "required": ["n", "topic", "hook", "on_screen", "asks", "tone", "offer", "seasonal", "carries_over", "why_not"],
                                             "properties": {"n": {"type": "integer"}, "topic": {"type": "string"}, "tone": {"type": "string"},
                                                            "offer": {"type": "string", "enum": OFFERS}, "seasonal": {"type": "string"},
                                                            "hook": {"type": "string", "enum": HOOKS},
                                                            "on_screen": {"type": "string", "enum": SCREENS},
                                                            "asks": {"type": "string", "enum": ASKS},
                                                            "carries_over": {"type": "boolean"}, "why_not": {"type": "string"}}}}}}}

SAYS = {  # how a shared trait reads in a sentence, and what it means for us when it is not a topic
    "hook": ("open with {v}", "open the first line with {v}"),
    "on_screen": ("show {v}", "a {format} showing {v}"),
    "asks": ("end by asking people to {v}", "end by asking people to {v}"),
    "offer": ("carry {v}", "a {format} that shows {v}"),
}


def reads(office: Office) -> dict[str, dict]:
    """Every post read the current way, by post id (the latest read wins)."""
    out = {}
    for e in office.log.list():
        if e["type"] == "post.read" and e["content"].get("v", 1) >= READ:
            out[e["content"]["post"]] = e["content"]
    return out


def _since(office: Office):
    """The oldest post date compared (Setup → Rhythm: the last N months; 12 unless changed)."""
    from datetime import timedelta
    from diwan.agents import rhythm
    return (studio._now() - timedelta(days=30 * int(rhythm.settings(office)["compare_months"]))).date().isoformat()


def judge(ps: list[dict], since: str) -> dict:
    """Which posts clearly won. Only posts since `since` are compared, each against the average of its own kind there.
    Like and comment counts swing by about the square root of their usual size, so a post counts as a winner only when it
    beats its kind's average by more than twice that: 8 against a usual 3 is chance; 900 against a usual 680 is not.
    {recent, old, wins (ids), usual {kind: avg}, low, high, noise {kind: n}}."""
    recent = [p for p in ps if (p.get("at") or "")[:10] >= since]
    by: dict[str, list[dict]] = {}
    for p in recent:
        by.setdefault(p["kind"], []).append(p)
    wins, usual, noise = set(), {}, {}
    for k, xs in by.items():
        if len(xs) < 2:
            continue
        avg = sum(x["engagement"] for x in xs) / len(xs)
        usual[k], noise[k] = round(avg), round(2 * avg ** 0.5)
        wins |= {x["id"] for x in xs if x["engagement"] - avg > 2 * avg ** 0.5}
    eng = [p["engagement"] for p in recent]
    return {"recent": recent, "old": len(ps) - len(recent), "wins": wins, "usual": usual, "noise": noise, "since": since,
            "low": min(eng, default=0), "high": max(eng, default=0), "latest": max(((p.get("at") or "")[:10] for p in ps), default="")}


def topics(office: Office, account: str) -> dict[str, str]:
    """The topic labels already used for an account, with what each means for us."""
    out = {}
    for e in office.log.list():
        if e["type"] == "post.read" and e["content"]["account"] == account and e["content"].get("for_us"):
            out[e["content"]["topic"]] = e["content"]["for_us"]
    return out


def _cover(url: str | None) -> bytes | None:
    """The cover picture, or None when Instagram's link has expired or is not a picture."""
    if not url:
        return None
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True)
        return r.content if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/") and len(r.content) < 3_000_000 else None
    except httpx.HTTPError:
        return None


US = "us"  # the account key our own posts are read under


def _saved_posts(office: Office) -> dict[str, list[dict]]:
    saved = {n.lower() for n in studio.competitors(office.graph())}
    by: dict[str, list[dict]] = {}
    for p in studio.posts(office, "competitor"):
        if p["account"].lower() in saved:
            by.setdefault(p["account"], []).append(p)
    return {a: studio.scored(ps) for a, ps in by.items()}


def _ours(office: Office) -> list[dict]:
    return studio.scored(studio.posts(office, "own"))


def _all(office: Office) -> dict[str, list[dict]]:
    """Every account to read: the competitors, then us."""
    return _saved_posts(office) | ({US: ours} if (ours := _ours(office)) else {})


def unread(office: Office) -> dict:
    """How many posts are waiting to be read, and how many of them are winners (their covers are read too)."""
    done, accs, since = reads(office), _all(office), _since(office)
    todo = [p for ps in accs.values() for p in ps if p["id"] not in done and (p.get("at") or "")[:10] >= since]
    wins = sum(1 for p in todo if studio.is_outlier(p))
    return {"posts": len(todo), "winners": wins, "covers": min(wins, MAX_COVERS * max(1, len(accs)))}


def read(office: Office, cause: int | None = None) -> dict:
    """Read every post not read yet, one call per account. Returns {"read", "accounts"} or {"needs"}."""
    if (why := business.needs(office, "each post's topic is judged for your market")):
        return {"needs": why}
    if not meta.ready():
        return {"needs": "Reading posts needs Muse Spark (META_API_KEY)."}
    done, total, errors = reads(office), 0, []
    since = _since(office)
    for acc, ps in _all(office).items():
        todo = [p for p in ps if p["id"] not in done and (p.get("at") or "")[:10] >= since]  # older posts are not compared, so not read
        if not todo:
            continue
        who = "our own account" if acc == US else "one competitor"
        wins = sorted((p for p in todo if studio.is_outlier(p)), key=lambda p: -p["score"])
        covers = {p["id"]: b for p in wins[:MAX_COVERS] if (b := _cover(p.get("thumb")))}
        ordered = wins + [p for p in todo if p not in wins]  # the strongest first: a run cut short has read what matters
        for at in range(0, len(ordered), BATCH):
            todo = ordered[at:at + BATCH]
            known = topics(office, acc)
            lines = [f"{i}. [{p.get('type') or 'post'}{', cover attached' if p['id'] in covers else ''}] {(p.get('caption') or '(no caption)')[:500]}"
                     for i, p in enumerate(todo)]
            order = [p["id"] for p in todo if p["id"] in covers]
            system = (f"You read social media posts by {who} and describe each one plainly. " + business.describe(office) + "\n"
                      "For each post: its topic as a short label of 2 to 4 words that fits this industry (reuse a label from the known topics "
                      "when one fits, so posts on the same subject share a label); its hook, from the first line or the cover; who or what is "
                      "on screen, from the cover when attached, else from the caption and the post type; what it asks people to do; its tone "
                      "in 2 to 4 plain words (e.g. warm and personal, formal and factual, playful); the offer it makes, if any; and seasonal: "
                      "the occasion it is tied to (e.g. Ramadan, Eid, National Day, a holiday sale, the summer), or empty if it is not tied to one.\n"
                      "carries_over is false when the post is about the competitor's own moment, which another business cannot copy: their "
                      "event or party, an award, a partnership or signing, a team photo or celebration, a celebrity, a holiday greeting, "
                      "their own launch. Then why_not says which, in a few words; otherwise why_not is empty.\n"
                      "For every topic label you use, for_us is one line on what our business could make on that topic, in our own words: "
                      "never copy their post, and never use their numbers, awards, sales or partners.\n" + brand.brief(office))
            text = (f"{'Our own account' if acc == US else f'Competitor @{acc}'}. Known topics: {', '.join(known) or 'none yet'}.\nCovers are attached in this order: "
                    f"{', '.join(str([p['id'] for p in todo].index(x)) for x in order) or 'none'}.\nPosts:\n" + "\n".join(lines))
            try:
                    got = meta.look(system, text, [covers[x] for x in order], SCHEMA, agent="mrival")
            except meta.MetaError as e:
                errors.append(f"@{acc}: {e}")
                break  # what was read is kept; the next run goes on from there
            for_us = {t["label"].strip().lower(): t["for_us"] for t in got.get("topics") or []}
            for r in got.get("posts") or []:
                if not (isinstance(r.get("n"), int) and 0 <= r["n"] < len(todo)):
                    continue  # a post number the model invented is dropped
                p = todo[r["n"]]
                office.log.append("post.read", actor="mrival", agent="mrival", caused_by=cause, key=f"read{READ}:{p['id']}",
                                  content={"post": p["id"], "account": acc, "topic": r["topic"].strip().lower(), "hook": r["hook"], "on_screen": r["on_screen"],
                                           "asks": r["asks"], "tone": (r.get("tone") or "").strip().lower(), "offer": r.get("offer") or "no offer",
                                           "seasonal": (r.get("seasonal") or "").strip(), "v": READ, "carries_over": acc == US or bool(r["carries_over"]), "why_not": r["why_not"] if not r["carries_over"] else "",
                                           "for_us": for_us.get(r["topic"].strip().lower()) or known.get(r["topic"].strip().lower(), ""), "cover_read": p["id"] in covers})
                total += 1
    pin(office, cause)
    return {"read": total, "errors": errors}


def _find(acc: str, wins: list, rest: list, whose: str, j: dict | None = None) -> list[dict]:
    """The traits the winners share clearly more often than the ordinary posts: at least MIN_WINS winners, a gap of GAP.
    Each finding says the numbers behind it; what it means for us is a reel or a post, as the winners were."""
    found = []
    reels = sum(1 for p, _ in wins if p["kind"] == "reel")
    fmt = "short video" if reels * 2 >= len(wins) else "post"
    for dim in ("topic", "on_screen", "hook", "asks", "offer"):
        best = None
        for v in {r.get(dim) for _, r in wins} - {None, "", "no offer", "something else", "nothing"}:
            w = [p for p, r in wins if r.get(dim) == v]
            o = sum(1 for _, r in rest if r.get(dim) == v)
            gap = len(w) / len(wins) - (o / len(rest) if rest else 0)
            if len(w) >= MIN_WINS and gap >= GAP and (not best or gap > best[2]):
                best = (v, w, gap, o)
        if best:
            v, w, gap, o = best
            if dim == "topic":
                says, for_us = f"are about {v}", next((r["for_us"] for _, r in wins if r["topic"] == v and r["for_us"]), "")
            else:
                says, for_us = SAYS[dim][0].format(v=v), SAYS[dim][1].format(v=v, format=fmt)
            top = max(w, key=lambda p: p["engagement"])
            nums = f" (best: {top['engagement']:,} likes + comments against {whose} usual {(j or {}).get('usual', {}).get(top['kind'], top['avg']):,} for a {top['kind']})"
            found.append({"id": f"why-{acc}-{dim}-{v}".replace(" ", "-"), "account": acc, "dim": dim, "value": v,
                          "finding": f"{len(w)} of {whose} {len(wins)} best posts {says}; {o} of {whose} {len(rest)} ordinary posts do{nums}.",
                          "for_us": for_us, "posts": [_card(p) for p in sorted(w, key=lambda p: (-p["score"], -p["engagement"]))[:4]]})
    return found


def _tone(wins: list) -> str:
    """The tone most of the best posts share, with how many."""
    from collections import Counter
    tones = Counter(r.get("tone") for _, r in wins if r.get("tone"))
    if not tones:
        return ""
    t, n = tones.most_common(1)[0]
    return f"{t} ({n} of {len(wins)} best posts)"


def _need(found: list, wins: list, j: dict | None = None, whose: str = "their") -> str:
    if found:
        return ""
    if j and not j["recent"] and j["old"]:
        return (f"Nothing recent to compare: all {j['old']} of {whose} posts are older than {j['since']} (the latest is {j['latest']}). "
                "To include them, raise the months in Setup → Rhythm; older posts say less about what works now.")
    if j and j["recent"] and len(wins) < MIN_WINS and j["high"] - min(j["usual"].values(), default=0) <= max(j["noise"].values(), default=0) * 2:
        return (f"Too small to tell: {whose} recent posts get {j['low']:,} to {j['high']:,} likes + comments, so a difference of a few is chance "
                f"at that size, not a reason.")
    if len(wins) < MIN_WINS:
        return f"Not enough posts yet to tell: {len(wins)} winning post{'s' if len(wins) != 1 else ''} read, a pattern needs {MIN_WINS} that share it."
    return "No clear pattern yet: the winners differ from each other as much as from the ordinary posts."


def winning(office: Office) -> dict:
    """What competitors' winning posts show, pooled across accounts: one account alone has too few to say."""
    done = reads(office)
    wins = [done[p["id"]] for ps in _saved_posts(office).values() for p in ps if p["id"] in done and studio.is_outlier(p)]
    shows = Counter(r.get("on_screen") for r in wins if r.get("on_screen") not in (None, "", "something else"))
    top = ", ".join(f"{k} ({n} of {len(wins)})" for k, n in shows.most_common(3))
    return {"posts": len(wins), "on_screen": dict(shows), "line": top or "not known yet"}


def patterns(office: Office) -> dict:
    """Per competitor: its patterns (each with the posts behind it and what it means for us), the tone of its winners,
    the winners that do not carry over, and when there is no pattern, why not. Then the same for us, with advice for
    each of our weak posts."""
    done, out, since = reads(office), [], _since(office)
    for acc, ps in _saved_posts(office).items():
        j = judge(ps, since)
        rd = [(p, done[p["id"]]) for p in j["recent"] if p["id"] in done]
        won = lambda p: p["id"] in j["wins"]  # noqa: E731
        wins = [(p, r) for p, r in rd if won(p) and r["carries_over"] and not r.get("seasonal")]
        rest = [(p, r) for p, r in rd if not won(p)]
        skip = [(p, r) for p, r in rd if won(p) and not r["carries_over"]]
        season = [(p, r) for p, r in rd if won(p) and r["carries_over"] and r.get("seasonal")]
        found = _find(acc, wins, rest, "their", j)
        behind = {c["permalink"]: c for f in found for c in f["posts"]}  # the posts behind any pattern, each shown once
        out.append({"account": acc, "read": len(rd), "posts": len(ps), "old": j["old"], "since": since, "winners": len(wins) + len(skip) + len(season),
                    "patterns": found, "need": _need(found, wins, j), "tone": _tone(wins), "for_us": [f["for_us"] for f in found if f["for_us"]],
                    "business": [_business(f, "their") for f in found if f["dim"] == "offer"],
                    "best": sorted(behind.values(), key=lambda c: (-c["x"], -c["engagement"])),
                    "top": [] if found else _top(wins, j),  # no shared pattern: still show their strongest, and say so
                    "skipped": [_card(p) | {"why_not": r["why_not"] or "their own moment"} for p, r in skip],
                    "seasonal": [_card(p) | {"season": r["seasonal"]} for p, r in season]})
    return {"accounts": out, "ours": ours(office, out), "unread": unread(office), "since": since,
            "business": _market(out), "needs": business.needs(office, "each post's topic is judged for your market")}


def _top(wins: list, j: dict) -> list[dict]:
    """With no pattern to copy: the account's strongest posts that carry over, or, when none stand out, its most liked recent ones."""
    if wins:
        return [_card(p) | {"why": "clearly above their usual"} for p, _ in sorted(wins, key=lambda x: (-x[0]["score"], -x[0]["engagement"]))[:4]]
    return [_card(p) | {"why": "their most liked recently"} for p in sorted(j["recent"], key=lambda p: (-p["engagement"], -(p["score"] or 0)))[:3]]


def _business(f: dict, whose: str) -> str:
    return (f"{whose.capitalize()} best posts carry {f['value']}. Worth considering one of our own, if it suits us: a decision for the owner "
            f"(Diwan never sets prices or offers).")


def _market(accs: list[dict]) -> list[str]:
    """Offers that win for more than one competitor: a stronger sign for the business than one account."""
    from collections import Counter
    c = Counter(f["value"] for a in accs for f in a["patterns"] if f["dim"] == "offer")
    return [f"{n} competitors' best posts carry {v}. Worth weighing an offer of our own: the owner decides (Diwan never sets prices or offers)."
            for v, n in c.items() if n >= 2]


WEAK = 0.8  # one of our posts below 80% of our average for its kind is weak


def ours(office: Office, theirs: list[dict] | None = None) -> dict:
    """Our own posts, read the same way: what our best posts share, their tone, and for each weak post what it lacked
    that our winners (or, without patterns of ours yet, a competitor's winners) have."""
    done, ps = reads(office), _ours(office)
    j = judge(ps, _since(office))
    rd = [(p, done[p["id"]]) for p in j["recent"] if p["id"] in done]
    wins = [(p, r) for p, r in rd if p["id"] in j["wins"] and not r.get("seasonal")]
    rest = [(p, r) for p, r in rd if p["id"] not in j["wins"]]
    found = _find(US, wins, rest, "our", j)
    guide = found or [f for a in (theirs or []) for f in a["patterns"]]
    weak = []
    for p, r in sorted((x for x in rest if x[0]["score"] is not None), key=lambda x: x[0]["score"]):  # a post with nothing of its kind to compare to has no score
        if p["score"] >= WEAK:
            continue
        lacks = [f for f in guide if r.get(f["dim"]) != f["value"]]
        src = "our best posts" if found else "what wins for competitors"
        advice = [f"{f['for_us'][:1].upper()}{f['for_us'][1:]} ({'ours' if found else '@' + f['account']})." for f in lacks if f["for_us"]][:3]
        weak.append(_card(p) | {"read": {k: r.get(k) for k in ("topic", "hook", "on_screen", "asks", "tone")},
                                "advice": advice, "from": src if advice else "",
                                "why": f"{p['score']}x our average {p['kind']}: a {r.get('topic')} that opened with {r.get('hook')}, showing {r.get('on_screen')}, in a {r.get('tone') or 'plain'} tone"})
    return {"read": len(rd), "posts": len(ps), "old": j["old"], "winners": len(wins), "patterns": found, "need": _need(found, wins, j, "our"),
            "tone": _tone(wins), "weak": weak[:6]}


def _card(p: dict) -> dict:
    return {"permalink": p.get("permalink"), "hook": (p.get("caption") or "").strip().split("\n")[0][:120], "engagement": p["engagement"],
            "x": p["score"], "avg": p["avg"], "kind": p["kind"], "thumb": p.get("thumb")}


def pin(office: Office, cause: int | None = None) -> None:
    """One card per competitor with patterns goes on the board for the idea and script writers: what it means for us,
    and the findings behind it. When the patterns change, the old card comes off and the new one goes on."""
    now, every = {}, patterns(office)
    o = every["ours"]
    us = [{"account": US, "patterns": o["patterns"], "for_us": [f["for_us"] for f in o["patterns"] if f["for_us"]],
           "best": [c for f in o["patterns"] for c in f["posts"]]}] if o["patterns"] else []
    for a in every["accounts"] + us:
        if a["for_us"]:
            key = "|".join(f"{f['dim']}={f['value']}" for f in a["patterns"])
            now[studio._stable_id(f"B-why-{a['account']}", key)] = a
    for c in studio.board(office):
        if c["kind"] == "pattern" and c["id"] not in now:
            studio.unpin(office, c["id"], by="mrival")
    on = {c["id"] for c in studio.board(office)}
    for i, a in now.items():
        if i not in on:
            office.log.append("board.pinned", actor="mrival", agent="mrival", caused_by=cause,
                              content={"id": i, "kind": "pattern", "account": a["account"], "title": "; ".join(a["for_us"])[:240],
                                       "why": ("Our own best posts: " if a["account"] == US else f"@{a['account']}: ") + " ".join(f["finding"] for f in a["patterns"]), "url": a["best"][0]["permalink"] if a["best"] else None})


FIT_SCHEMA = {"name": "fit", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["same_industry", "why"],
              "properties": {"same_industry": {"type": "boolean"}, "why": {"type": "string"}}}}


def fits(office: Office, acc: dict) -> dict:
    """Whether a competitor account looks like it is in our industry, from its name, bio and recent captions:
    {"fits": bool, "fit_why"}, or {} when it cannot be judged (no business set, no model, or the call failed)."""
    b = business.get(office)
    if not b["industry"] or not meta.ready():
        return {}
    caps = "\n".join(f"- {(p.get('caption') or '')[:200]}" for p in acc.get("posts", [])[:8])
    try:
        r = meta.look("You judge whether an Instagram account is a business in a given industry. Answer from what is written only; "
                      "why is one short sentence quoting what decided it.",
                      f"Our industry: {b['industry']}. Account @{acc.get('username')}, name: {acc.get('name') or '-'}, bio: {acc.get('bio') or '-'}.\nRecent captions:\n{caps}",
                      [], FIT_SCHEMA, agent="mrival", timeout=60)
    except meta.MetaError:
        return {}
    return {"fits": bool(r.get("same_industry")), "fit_why": str(r.get("why") or "")[:200]}
