"""A post from what really happened: the photos a person took at an event, read, searched once, shaped into the right
format, and made into images. Real photos stay real (crop, words, a dark band); only a graphic's plain background may
be generated. A person picks and approves as for any script. See docs/event-post-spec.md.

Formats: reel (a clip, or photos when our reels clearly win), carousel (4+ usable photos), image (1 to 3), graphic (none).
"""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

from diwan import brand, business, topics
from diwan.agents import director, freevideo, studio
from diwan.office import Office
from diwan.providers import meta

FORMATS = {"reel": "Reel", "carousel": "Carousel", "image": "Single image", "graphic": "Graphic"}
MIN_WINNERS = 10  # fewer winning posts than this say nothing about format
SLIDES = ("carousel", "image", "graphic")  # made here as pictures, not filmed
W, H = 1080, 1350
MAX_SLIDES = 10
MIN_WIDTH, MIN_SHARP, MIN_LIGHT = 600, 25.0, 30  # below these a photo is not used. Measured: real photos 33+, blurred 18 or less; a dim room is still fine
REELS_WIN, MIN_EACH = 1.5, 3
FONTS = ("C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
GOLD, INK = (240, 220, 170), (14, 18, 27)

READ_SCHEMA = {"name": "photos", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["photos"], "properties": {"photos": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["n", "what", "people", "strength"],
                               "properties": {"n": {"type": "integer"}, "what": {"type": "string"}, "people": {"type": "boolean"}, "strength": {"type": "integer"}}}}}}}


def _load(path: str) -> Image.Image | None:
    try:
        return Image.open(path).convert("RGB")
    except (OSError, ValueError):
        return None


def measure(path: str) -> dict:
    """What code can say about a photo without a model: {path, usable, problem}."""
    img = _load(path)
    if img is None:
        return {"path": path, "usable": False, "problem": "can't be opened"}
    small = img.convert("L")
    small.thumbnail((512, 512))
    sharp = ImageStat.Stat(small.filter(ImageFilter.FIND_EDGES)).stddev[0]
    light = ImageStat.Stat(small).mean[0]
    problem = ("too small" if img.width < MIN_WIDTH else "too dark" if light < MIN_LIGHT else "blurred" if sharp < MIN_SHARP else "")  # dark photos have weak edges too
    return {"path": path, "usable": not problem, "problem": problem, "width": img.width, "height": img.height, "sharp": round(sharp, 1), "light": round(light)}


def _copy(url: str, fetch: bool) -> str | None:
    """A listing's web photo as a file here (downloaded once, when fetch), or None."""
    path = meta.MEDIA / f"web-{hashlib.sha1(url.encode()).hexdigest()[:16]}.jpg"
    if not path.exists() and fetch:
        meta.MEDIA.mkdir(exist_ok=True)
        try:
            r = httpx.get(url, timeout=30, follow_redirects=True)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                path.write_bytes(r.content)
        except httpx.HTTPError:
            return None
    return str(path) if path.exists() else None


def photos(office: Office, ref: str, fetch: bool = False) -> list[dict]:
    """The photos with what is known of each: measured always; read by the model once `read` has run. A listing's web
    photos are measured from a local copy, fetched once when `fetch` (a page view never downloads)."""
    known = {p["path"]: p for e in office.log.list() if e["type"] == "photo.read" and e["content"]["ref"] == ref for p in e["content"]["photos"]}
    out = []
    for path in freevideo.photos(office, ref):
        if path.startswith("http"):
            local = _copy(path, fetch)
            if not local:
                out.append({"path": path, "usable": False, "problem": "not fetched yet"})
                continue
            path = local
        out.append(known.get(path) or measure(path))
    return out


def _bytes(path: str) -> bytes:
    img = _load(path)
    img.thumbnail((768, 768))
    b = io.BytesIO()
    img.save(b, "JPEG", quality=80)
    return b.getvalue()


def read(office: Office, ref: str, cause: int | None) -> list[dict]:
    """Muse Spark says what is in each usable photo, once per set of photos. Without a model they stay measured, and it says so."""
    rows = photos(office, ref)
    good = [p for p in rows if p["usable"]]
    new = [p for p in good if "what" not in p]
    if not new:
        return rows
    if not meta.ready():
        studio._blocked(office, "mthumb", "Reading what is in the photos needs Muse Spark (META_API_KEY): they were measured for size, sharpness and light only", cause=cause)
        return rows
    t = topics.get(office, ref) or studio._listing(office, ref)
    try:
        r = meta.look("You describe photos for a marketing team. Say only what can be seen. Never guess a name or who someone is.",
                      f"Post: {t.get('title')}. For each photo, in order, starting at 1: n; what (what can be seen, under 15 words); people (true if a person's "
                      "face can be recognised); strength (1 to 5, how well it would stop someone scrolling).", [_bytes(p["path"]) for p in new], READ_SCHEMA, agent="mthumb")
    except meta.MetaError as e:
        studio._blocked(office, "mthumb", f"The photos could not be read: {str(e)[:120]}", cause=cause)
        return rows
    said = {x["n"]: x for x in r.get("photos", [])}
    for i, p in enumerate(new, 1):
        x = said.get(i)
        if x:
            p |= {"what": x["what"][:120], "people": bool(x["people"]), "strength": max(1, min(5, int(x["strength"])))}
    key = "photos:" + hashlib.sha1("|".join(p["path"] for p in new).encode()).hexdigest()
    office.log.append("photo.read", actor="mthumb", agent="mthumb", key=key, caused_by=cause, content={"ref": ref, "photos": new})
    studio._pack(office, "mthumb", f"Read {len(new)} photo{'s' if len(new) != 1 else ''} of {ref}.", cause=cause)
    return photos(office, ref)


def search(office: Office, ref: str, cause: int | None) -> list[dict]:
    """One web search about this event, once. Only pages the search really opened are pinned."""
    if any(e["type"] == "board.pinned" and e["content"].get("about") == ref for e in office.log.list()):
        return []
    t = topics.get(office, ref)
    if not meta.ready():
        studio._blocked(office, "mtrend", f"Searching for \"{t['title']}\" needs Muse Spark web search (META_API_KEY)", cause=cause)
        return []
    b = business.get(office)
    try:
        r = meta.search(f"How do {b['industry']} businesses in {business.place(office)} post well about this kind of event or news: \"{t['title']}\"? "
                        "Use at most two searches. Answer with exactly two lines and nothing else, each in the form:\n"
                        "1. <what works, under 12 words> | <why, under 15 words> | <the URL of the page you saw it on>", country=b["country"])
    except meta.MetaError as e:
        studio._blocked(office, "mtrend", f"Web search failed: {e}", cause=cause)
        return []
    seen = {s["url"].rstrip("/.)") for s in [*r["sources"], *r["cited"]] if s.get("url")}
    cards = []
    for ln in r["text"].splitlines():
        m = re.match(r"\s*\d+[.)]\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(https?://\S+)", ln)
        if m and m.group(3).rstrip("/.)") in seen:
            c = {"id": studio._stable_id("B-event", m.group(3) + ref), "kind": "trend", "about": ref, "title": m.group(1)[:120], "why": m.group(2)[:160], "url": m.group(3).rstrip(".)")}
            office.log.append("board.pinned", actor="mtrend", agent="mtrend", key=f"pin:{c['id']}", content=c)
            cards.append(c)
    if cards:
        studio._pack(office, "mtrend", f"Searched for \"{t['title']}\": {len(cards)} finding{'s' if len(cards) != 1 else ''} tied to a page it opened.", cause=cause)
    else:
        studio._blocked(office, "mtrend", f"The search on \"{t['title']}\" found nothing tied to a page it opened, so this post is written from your facts alone", cause=cause)
    return cards


def _text_wins(office: Office) -> str | None:
    """A sentence when competitors' winning posts are clearly more often words on pictures than a person on camera, else None."""
    from diwan.agents import reader
    w = reader.winning(office)
    text, talk = w["on_screen"].get("text on images", 0), w["on_screen"].get("a person talking to camera", 0)
    return f"{text} of {w['posts']} winning competitor posts are text on images, against {talk} with a person on camera" if w["posts"] >= MIN_WINNERS and text > talk else None


def _reels_win(office: Office) -> str | None:
    """A sentence when our own reels clearly beat our other posts, else None."""
    by = {"reel": [], "post": []}
    for p in studio.posts(office, "own"):
        by[studio.kind(p)].append(p.get("engagement") or (p.get("likes") or 0) + (p.get("comments") or 0))
    if min(len(by["reel"]), len(by["post"])) < MIN_EACH:
        return None
    r, o = sum(by["reel"]) / len(by["reel"]), sum(by["post"]) / len(by["post"])
    return f"your reels average {round(r)} likes and comments against {round(o)} for other posts" if o and r >= REELS_WIN * o else None


def suggest(office: Office, ref: str) -> dict:
    """The format and why: {format, label, why, usable, unusable (reasons), chosen}."""
    rows = photos(office, ref)
    good = [p for p in rows if p["usable"]]
    bad = [f"{Path(p['path']).name}: {p['problem']}" for p in rows if not p["usable"]]
    n = len(good)
    win = _reels_win(office)
    if _is_listing(office, ref):  # a listing: chosen from its selling point, its photos and what wins in the trade (listing_look)
        chosen = _chosen(office, ref)
        look = studio.made(office, "listing look", ref) or {}
        fmt = chosen or look.get("format") or "reel"
        why = "you chose this" if chosen else look.get("why") or "a reel until its photos and selling point are looked at"
        return {"format": fmt, "label": FORMATS[fmt], "why": why, "usable": n, "unusable": bad, "chosen": chosen, "usp": look.get("usp", "")}
    if _greeting(office, ref):  # a greeting greets: a designed card by default; the person's own photos (the team, the office) only when they choose them
        chosen = (topics.get(office, ref) or {}).get("format")
        fmt = chosen if chosen in FORMATS else "graphic"
        return {"format": fmt, "label": FORMATS[fmt], "why": "a greeting is a designed card for the day; choose Image or Carousel to use your own photos of the team or office"
                if fmt == "graphic" else "you chose this", "usable": n, "unusable": bad, "chosen": chosen}
    if studio.footage(office, ref):
        fmt, why = "reel", "you have a video clip"
    elif n >= 4 and win:
        fmt, why = "reel", f"you have {n} usable photos and {win}"
    elif n >= 4:
        fmt, why = "carousel", f"{n} usable photos tell it better than one"
    elif n:
        fmt, why = "image", f"{n} usable photo{'s' if n != 1 else ''}: one strong picture is better than a thin carousel"
    else:
        wins = _text_wins(office)
        fmt, why = "graphic", f"no usable photos yet, and {wins}" if wins else "no usable photos yet: words on a clean background"
    chosen = (topics.get(office, ref) or {}).get("format")
    if chosen and chosen != fmt:
        fmt, why = chosen, f"you chose this (Diwan suggested {FORMATS[fmt].lower()}: {why})"
    return {"format": fmt, "label": FORMATS[fmt], "why": why, "usable": n, "unusable": bad, "chosen": chosen}


def _is_listing(office: Office, ref: str) -> bool:
    try:
        return studio._listing(office, ref).get("item") == "listing"
    except KeyError:
        return False


def _chosen(office: Office, ref: str) -> str | None:
    """The format a person chose for this post, if any (any subject, not only a topic)."""
    return next((e["content"]["format"] for e in reversed(office.log.list()) if e["type"] == "topic.saved" and e["content"].get("ref") == ref and e["content"].get("format")), None)


LISTING_FORMATS = ("reel", "carousel", "image")
KINDS = {"REELS": "reel", "VIDEO": "reel", "CAROUSEL_ALBUM": "carousel", "IMAGE": "image"}
MIN_CAROUSEL, MIN_REEL = 3, 3  # usable photos a carousel, or a reel made from photos, needs
LOOK_SCHEMA_LISTING = {"name": "listing_look", "strict": True, "schema": {"type": "object", "additionalProperties": False,
                       "required": ["usp", "format", "photos", "why"], "properties": {
                           "usp": {"type": "string"}, "format": {"type": "string"}, "photos": {"type": "array", "items": {"type": "integer"}}, "why": {"type": "string"}}}}


def trend(office: Office) -> dict:
    """Which format wins in this trade, from the saved competitors' posts: each format's share of their winning posts against
    its share of all their posts (lift above 1 means it wins more than it is used). Our own results join when there are enough."""
    from diwan.agents import reader
    ps = [p for x in reader._saved_posts(office).values() for p in x]
    wins = [p for p in ps if studio.is_outlier(p)]
    share = lambda xs, k: sum(1 for p in xs if KINDS.get((p.get("type") or "").upper()) == k) / len(xs) if xs else 0  # noqa: E731
    lift = {k: round(share(wins, k) / share(ps, k), 2) for k in LISTING_FORMATS if len(wins) >= MIN_WINNERS and share(ps, k)}
    line = ("; ".join(f"{k}s are {share(wins, k):.0%} of competitors' winning posts against {share(ps, k):.0%} of all their posts" for k in sorted(lift, key=lift.get, reverse=True))
            if lift else f"too few winning competitor posts ({len(wins)}) to say which format wins")
    ours = {k: [p.get("engagement") or 0 for p in studio.posts(office, "own") if KINDS.get((p.get("type") or "").upper()) == k] for k in LISTING_FORMATS}
    mine = {k: round(sum(v) / len(v)) for k, v in ours.items() if len(v) >= MIN_EACH}
    if len(mine) >= 2:
        line += "; ours: " + ", ".join(f"{k}s average {v} likes and comments" for k, v in sorted(mine.items(), key=lambda kv: -kv[1]))
    return {"lift": lift, "ours": mine, "winners": len(wins), "posts": len(ps), "line": line}


def listing_look(office: Office, ref: str, cause: int | None = None) -> dict:
    """A listing's selling point and the format that shows it best: its photos fetched and read, then Muse Spark looks at
    them with the facts, what wins in the trade (trend) and what the week already has, and chooses a single photo (one view
    sells it), a carousel (several rooms or features) or a reel (the space and the flow), and the photo order. Only formats
    its photos can make are allowed. Without a model: the format that wins most in the trade that the photos allow. Once per listing."""
    if (done := studio.made(office, "listing look", ref)):
        return done
    from diwan.agents import rhythm
    lst = studio._listing(office, ref)
    photos(office, ref, fetch=True)
    read(office, ref, cause)
    good = [p for p in photos(office, ref) if p["usable"]][:MAX_SLIDES]
    can = [f for f in LISTING_FORMATS if (f == "reel" and (len(good) >= MIN_REEL or studio.footage(office, ref))) or (f == "carousel" and len(good) >= MIN_CAROUSEL) or (f == "image" and good)] or ["reel"]
    tr = trend(office)
    from diwan.agents import marketing
    week = [marketing.format_of(office, d["ref"]) for d in (rhythm.current(office) or {}).get("days", [])[:7] if d.get("ref") and d.get("ref") != ref]
    pick = None
    if meta.ready() and good:
        try:
            pick = meta.look("You are the head of marketing at a top agency choosing how to post one property listing on Instagram. First name its unique selling point: "
                             "the one thing a buyer would stop for, from the facts and what the photos really show. Then choose the format that shows that best: image (one "
                             "photo carries it, e.g. a view), carousel (several rooms or features each add something) or reel (the space, the flow, a walk-through). "
                             "Lean towards what wins in this trade when the listing suits it, and avoid repeating the week's formats when another fits as well. "
                             "photos: the photo numbers in the order to show them, the one that shows the selling point first. why: one plain sentence for the owner.",
                             f"Listing: {lst['title']}. Facts: {studio._brief(office, ref)[:700]}\nWhat wins in the trade: {tr['line']}\nThe week already has: {', '.join(week) or 'nothing yet'}\n"
                             f"Allowed formats: {', '.join(can)}.\n" + "\n".join(f"Photo {i}: {p.get('what') or 'not described'}" for i, p in enumerate(good, 1)),
                             [_bytes(p["path"]) for p in good[:8]], LOOK_SCHEMA_LISTING, agent="mthumb")
        except (meta.MetaError, OSError, ValueError):
            pick = None
    if pick and pick.get("format") in can:
        order = [good[n - 1]["path"] for n in dict.fromkeys(pick.get("photos") or []) if isinstance(n, int) and 0 < n <= len(good)]
        out = {"format": pick["format"], "usp": pick["usp"][:160], "why": pick["why"][:200], "photos": order + [p["path"] for p in good if p["path"] not in order],
               "trend": tr["line"], "by": "muse-spark"}
    else:
        fmt = max(can, key=lambda f: tr["lift"].get(f, 0)) if tr["lift"] else ("reel" if "reel" in can else can[0])
        out = {"format": fmt, "usp": (lst.get("features") or [""])[0], "why": f"{FORMATS[fmt].lower()}: {tr['line']}" if tr["lift"] else f"{FORMATS[fmt].lower()}: {tr['line']}, so the usual",
               "photos": [p["path"] for p in sorted(good, key=lambda p: -p.get("strength", 0))], "trend": tr["line"], "by": "rules"}
    studio._made(office, "mthumb", "listing look", ref, out, cause)
    studio._pack(office, "mthumb", f"{lst['title']}: {FORMATS[out['format']].lower()}. Selling point: {out['usp'] or 'not found'}. {out['why']}", cause=cause)
    return out


def _greeting(office: Office, ref: str) -> bool:
    try:
        return bool(studio._listing(office, ref).get("greeting"))
    except KeyError:
        return False


def choose(office: Office, ref: str, fmt: str, *, by: str) -> None:
    if fmt not in FORMATS:
        raise ValueError(f"The format is one of: {', '.join(FORMATS)}.")
    if _is_listing(office, ref):
        photos(office, ref, fetch=True)
    if fmt in ("carousel", "image") and not suggest(office, ref)["usable"]:
        raise ValueError("That format needs at least one usable photo.")
    if fmt == "carousel" and suggest(office, ref)["usable"] < 2:
        raise ValueError("A carousel needs at least two usable photos.")
    office.log.append("topic.saved", actor=by, content={"ref": ref, "format": fmt})


def shape(office: Office, lst: dict) -> dict | None:
    """How a post made as pictures will be made, for the writers: a moment, or a teaching post when competitors' winners
    show words on pictures work. None for everything else. A post about the brand stays a person speaking: people buy from people."""
    from diwan.agents import rhythm, taste
    ours = taste.weight(office, "format:graphic"), taste.weight(office, "format:reel, to camera")  # what this business itself said beats what competitors do
    week = rhythm.planned_format(office, lst["ref"])  # the week's mix, when this post is on the plan
    leans = week == "graphic" if week else ours[1] <= taste.BLOCK or (ours[0] > taste.BLOCK and bool(_text_wins(office)))
    teaching = lst.get("item") == "topic" and not lst.get("job") and not lst["ref"].startswith("JOB-") and leans
    if lst.get("item") == "listing":  # a listing as pictures when its look chose a carousel or a single photo
        s = suggest(office, lst["ref"])
        if s["format"] not in ("carousel", "image"):
            return None
        order = (studio.made(office, "listing look", lst["ref"]) or {}).get("photos") or []
        good = [p for p in photos(office, lst["ref"]) if p["usable"]]
        rank = {p: i for i, p in enumerate(order)}
        return s | {"photos": sorted(good, key=lambda p: (rank.get(p["path"], len(rank)), -p.get("strength", 0)))}
    if not lst.get("moment") and not teaching:
        return None
    s = suggest(office, lst["ref"])
    if not lst.get("moment") and s["format"] == "reel":
        return None  # there is real footage: use it
    good = [] if lst.get("greeting") and s["format"] == "graphic" else sorted([p for p in photos(office, lst["ref"]) if p["usable"]], key=lambda p: -p.get("strength", 0))
    return s | {"photos": good}


def brief(sh: dict | None) -> str:
    if not sh:
        return ""
    listed = "\n".join(f"Photo {i}: {p.get('what') or 'not described'}" for i, p in enumerate(sh["photos"], 1))
    if sh["format"] == "reel":
        return f"\n\nThe footage is real, from the event.\n{listed}" if listed else ""
    how = {"carousel": "a carousel of pictures, not a video: the hook is on the first slide and each line on one slide, so each line stands alone in under 12 words",
           "image": "one picture with the hook on it, not a video: the lines are the caption",
           "graphic": "one graphic with the hook on it, not a video: the lines are the caption"}[sh["format"]]
    return (f"\n\nThis post is {how}. Write for reading, not speaking. Say nothing about the event that the facts or the photos do not show. "
            + (f"In `photos`, give the photo number for the hook and then for each line, the photo that best shows those words.\n{listed}" if listed else "In `photos`, give an empty list."))


def slides(data: dict, sh: dict) -> list[dict]:
    """Which words go on which photo. The call to action stays last; a photo is used once."""
    words = [data["hook_en"], *data["lines_en"]]
    if sh["format"] != "carousel":
        return [{"photo": sh["photos"][0]["path"] if sh["format"] == "image" and sh["photos"] else None, "text": words[0]}]
    n = min(len(sh["photos"]), MAX_SLIDES, len(words))
    if n < len(words):
        words = [*words[:n - 1], words[-1]]
    wanted = data.get("photos") or []
    free = [p["path"] for p in sh["photos"]]
    what = {p["path"]: _stems(p.get("what") or "") for p in sh["photos"]}
    out = []
    for i, text in enumerate(words):
        k = wanted[i] - 1 if i < len(wanted) and isinstance(wanted[i], int) else -1
        path = sh["photos"][k]["path"] if 0 <= k < len(sh["photos"]) and sh["photos"][k]["path"] in free else free[0]
        say = _stems(text)
        better = max(free, key=lambda p: len(say & what[p]))  # the writer's pick, unless another photo plainly shows these words and it doesn't
        if i and not say & what[path] and say & what[better]:
            path = better
        free.remove(path)
        out.append({"photo": path, "text": text})
    return out


def _stems(text: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", text.lower())} - {"with", "from", "your", "this", "that", "into", "over"}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(d: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    out, line = [], ""
    for w in text.split():
        t = f"{line} {w}".strip()
        if d.textlength(t, font=font) <= width:
            line = t
        else:
            out.append(line)
            line = w
    return [*out, line] if line else out


ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")  # the Arabic font has no Western digits: they were drawn as boxes


def _wrap_rtl(d: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    """Arabic words into lines that fit, measured right to left (shaped words are wider than their letters)."""
    out, cur = [], ""
    for w in text.split():
        nxt = f"{cur} {w}".strip()
        try:
            fits = d.textlength(nxt, font=font, direction="rtl", language="ar") <= width
        except (KeyError, ValueError, OSError):
            fits = d.textlength(nxt, font=font) <= width
        if fits or not cur:
            cur = nxt
        else:
            out.append(cur)
            cur = w
    return out + ([cur] if cur else [])


def _fit(img: Image.Image) -> Image.Image:
    """Crop to the post's shape around the middle; nothing else changes in a real photo."""
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)))
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _background(office: Office, ref: str, feedback: str | None = None) -> tuple[Image.Image, str]:
    """A graphic's background: abstract, made by Muse Image when it can be, else plain."""
    dark, accent = brand.colours(office)
    plain = Image.new("RGB", (W, H), dark)
    if not meta.ready():
        return plain, "plain"
    voice = brand.profile(office)["voice"]["value"] or "calm, professional"
    try:
        lst = studio._listing(office, ref)
    except KeyError:  # a background with no subject: no occasion motif
        lst = {}
    motif = (lst.get("motif") or f"symbols, light and colours that people associate with {lst['title']}") if lst.get("greeting") else ""  # from the research
    colours = f" Its colours lean to {'#%02x%02x%02x' % dark} and {'#%02x%02x%02x' % accent}."
    from diwan import occasions
    learned = (occasions.studied(office, lst["occasion"]) or {}).get("notes", {}).get("look", "") if lst.get("occasion") else ""
    try:
        served = meta.image((f"An elegant greeting-card background for {lst['title']}: {motif}. Festive but calm, premium, lots of quiet space in the middle "
                             f"for words.{colours} " + (f"Aim for this, learned from the best competitor posts for the day: {learned[:300]} " if learned else "") if motif else
                             f"A refined background for a post by this business: {business.describe(office)} Mood: {voice}. Quiet and uncluttered, so words read easily on it, "
                             f"and it clearly suits this trade and place.{colours} ")
                            + "Strictly no text, letters, logos, people, faces, clip-art icons or real buildings."
                            + (f" The last one was turned down: {feedback[:300]} Fix that." if feedback else ""), f"bg-{ref}", size="1024x1792")
        return _fit(Image.open(meta.media_path(served)).convert("RGB")), "Muse Image"
    except (meta.MetaError, OSError) as e:
        studio._blocked(office, "mthumb", f"Muse Image failed, using a plain background: {str(e)[:120]}")
        return plain, "plain"


ARABIC_FONTS = ("/System/Library/Fonts/SFArabic.ttf", "/System/Library/Fonts/GeezaPro.ttc", "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf")
SAFE = 60  # px kept clear at the edges: Instagram's own buttons and crops sit there


def _arabic(size: int):
    """A font that shapes Arabic (joined letters, right to left) through libraqm; None when there is none."""
    from PIL import features
    for f in ARABIC_FONTS:
        try:
            return ImageFont.truetype(f, size, layout_engine=ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC)
        except OSError:
            continue
    return None


def _mark(img: Image.Image, name: str, logo: str | None, dark, accent, *, big: bool = False, bigger: bool = False) -> None:
    """The company on the picture: its logo (when set) and its name, top-left inside the safe area, on a small plate so
    they read on any photo. `bigger` is a person asking for a bigger logo."""
    d = ImageDraw.Draw(img)
    font = _font(56 if bigger else 46 if big else 38)
    x, y = SAFE, SAFE
    mark = None
    if logo:
        try:
            mark = Image.open(logo).convert("RGBA")
            side = 200 if bigger else 132 if big else 104
            mark.thumbnail((side, side))
        except OSError:
            mark = None
    w = (mark.width + 18 if mark else 0) + (int(d.textlength(name, font=font)) if name else 0) + 44
    h = max(mark.height if mark else 0, font.size) + 32
    plate = Image.new("RGBA", (w, h), (*dark, 215))
    img.alpha_composite(plate, (x - 22, y - 16))
    if mark:
        img.alpha_composite(mark, (x, y + (h - 32 - mark.height) // 2))
        x += mark.width + 18
    if name:
        ImageDraw.Draw(img).text((x, y + (h - 32 - font.size) // 2 - 2), name, font=font, fill=accent)


def _draw(img: Image.Image, text: str, name: str, centre: bool, *, logo: str | None = None, colours=None, arabic: str = "",
          greeting: bool = False, big_logo: bool = False, sub: str = "") -> Image.Image:
    """The words on a band across the bottom (or a centred card for a graphic or a greeting), the company's logo and name
    on every picture, the Arabic words under the English when the business posts in Arabic."""
    dark, accent = colours or (INK, GOLD)
    img = img.convert("RGBA")
    d = ImageDraw.Draw(img)
    font = _font(84 if greeting else 64)
    lines = _wrap(d, text, font, W - 2 * SAFE - 40)
    while len(lines) > (4 if greeting else 5) and font.size > 36:
        font = _font(font.size - 6)
        lines = _wrap(d, text, font, W - 2 * SAFE - 40)
    arabic = re.sub(r"[^\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF0-9\s.,:!?()-]", "", arabic or "").translate(ARABIC_DIGITS).strip()  # only what the Arabic font draws
    afont = _arabic(int(font.size * .8)) if arabic else None
    alines = _wrap_rtl(d, arabic, afont, W - 2 * SAFE - 40) if afont else []
    while afont and len(alines) > 2 and afont.size > 28:
        afont = _arabic(afont.size - 4)
        alines = _wrap_rtl(d, arabic, afont, W - 2 * SAFE - 40)
    alines = alines[:2]
    sfont = _font(max(30, font.size // 2 - 4)) if sub else None
    high = len(lines) * (font.size + 16) + 96 + (len(alines) * (afont.size + 20) + 8 if afont else 0) + ((sfont.size + 30) if sfont else 0)
    top = (H - high) // 2 if centre or greeting else H - high - SAFE
    band = Image.new("RGBA", (W, high), (*dark, 225 if greeting else 205))
    img.alpha_composite(band, (0, top))
    d = ImageDraw.Draw(img)
    if greeting:  # an accent rule above the words, the way a printed card is set
        d.rectangle(((W - 120) // 2, top + 30, (W + 120) // 2, top + 36), fill=accent)
    y = top + 52
    for ln in lines:
        x = (W - d.textlength(ln, font=font)) // 2 if greeting or centre else SAFE + 20
        d.text((x, y), ln, font=font, fill=(255, 255, 255))
        y += font.size + 16
    if afont:
        try:
            for al in alines:
                aw = d.textlength(al, font=afont, direction="rtl", language="ar")
                d.text(((W - aw) // 2 if greeting or centre else W - SAFE - 20 - aw, y + 8), al, font=afont, fill=accent, direction="rtl", language="ar")
                y += afont.size + 20
            y += 8
        except (KeyError, ValueError, OSError):  # no shaping engine here: leave the Arabic out rather than draw it broken
            pass
    if sfont:
        d.text(((W - d.textlength(sub, font=sfont)) // 2, y + 14), sub, font=sfont, fill=(225, 225, 225))
    _mark(img, name, logo, dark, accent, big=greeting, bigger=big_logo)
    return img.convert("RGB")


def render(office: Office, ref: str, sc: dict, cause: int | None, feedback: str | None = None, look: dict | None = None) -> dict | None:
    """The real images for the approved post. `look` is a person's change already worked out (change()): a designed
    card instead of photos, new words, a bigger logo, Arabic, what the background should show."""
    name = brand.profile(office)["name"]["value"].strip()
    lst = studio._listing(office, ref)
    look = look or {}
    meta.MEDIA.mkdir(exist_ok=True)
    out, bg_by = [], None
    card = (bool(lst.get("greeting")) and sc["format"] == "graphic") or look.get("card")  # a card ignores photos; a greeting is one unless the person chose photos
    feedback = "\n".join(x for x in (feedback, look.get("background") and f"The person asked: {look['background']}") if x) or None
    tag = f"-v{look['v']}" if look.get("v") else ""
    for i, s in enumerate(sc["slides"], 1):
        if s["photo"] and not card:
            base = _load(s["photo"])
            if base is None:
                studio._blocked(office, "mart", f"A photo of {ref} can't be opened any more: {Path(s['photo']).name}", cause=cause)
                return None
            base = _fit(base)
        else:
            if bg_by is None or not card:  # a card's slides share one background: one Muse Image call, not one per slide
                bg, bg_by = _background(office, ref, feedback)
            base = bg.copy()
        path = meta.MEDIA / f"post-{ref}-{sc['id']}{tag}-{i}.jpg"
        hello = bool(lst.get("greeting")) and i == 1 and lst.get("greet")  # a greeting's card says the greeting itself; the script's line goes in the caption
        text = look.get("words") if i == 1 and look.get("words") else lst["greet"] if hello else s["text"]
        arabic = (look.get("arabic_text") if i == 1 and look.get("arabic_text") else
                  (lst.get("greet_ar") if hello and not look.get("words") else s.get("text_ar") or (sc.get("hook_ar") if i == 1 else ""))
                  if "Arabic" in business.languages(office) or look.get("arabic") else "")
        greet = (bool(lst.get("greeting")) or bool(look.get("card"))) and i == 1
        sub = (name if lst.get("sombre") else f"From all of us at {name}") if hello and name else ""
        _draw(base, text, name, centre=card or not s["photo"], logo=brand.logo(office), colours=brand.colours(office), arabic=arabic,
              greeting=greet, big_logo=bool(look.get("bigger_logo")), sub=sub).save(path, "JPEG", quality=90)
        out.append({"path": str(path), "served": f"/media/{path.name}", "text": text})
    known = {p["path"]: p for p in photos(office, ref)}
    people = 0 if card else sum(1 for s in sc["slides"] if known.get(s["photo"], {}).get("people"))
    from diwan import occasions
    from diwan.agents import director, journey
    job = journey.job_of(lst)
    theirs = (occasions.studied(office, lst["occasion"]) or {}).get("posts", []) if lst.get("occasion") else []
    seen = director.review(office, f"{lst['title']} (a {journey.JOBS[job]['label'].lower()} post)", " ".join(x["text"] for x in out), [x["path"] for x in out],
                           against=theirs[:2])
    review = {"score": seen["score"], "failed": {str(k): v for k, v in seen["failed"].items()}, **({"against": seen["against"]} if seen.get("against") else {})} if seen else None
    if review and job == "greeting" and not card and review["score"] < director.PASS_SCORE:
        review["advice"] = "These photos don't read as a greeting: ask for a designed card, or use photos of the team or the office."
    m = studio._made(office, "mart", "slides", ref, {"images": out, "format": "graphic" if card and sc["format"] != "carousel" else sc["format"], "people": people,
                                                    **({"background": bg_by} if bg_by else {}), **({"review": review} if review else {})}, cause)
    studio._pack(office, "mart", f"{FORMATS[sc['format']]} for {ref} ready: {len(out)} image{'s' if len(out) != 1 else ''}"
                 + (f", background: {bg_by}" if bg_by else "") + (f"; {people} show people" if people else "") + ".", cause=cause)
    return m


LOOK_SCHEMA = {"name": "picture_change", "strict": True, "schema": {"type": "object", "additionalProperties": False,
               "required": ["card", "words", "arabic", "arabic_text", "bigger_logo", "background", "cannot"], "properties": {
                   "card": {"type": "boolean"}, "words": {"type": "string"}, "arabic": {"type": "boolean"}, "arabic_text": {"type": "string"},
                   "bigger_logo": {"type": "boolean"}, "background": {"type": "string"}, "cannot": {"type": "string"}}}}
CARD_ASK = r"\b(festive|no (property|listing|house|building|photo)|not? (a )?(property|listing)|greeting card|design(ed)?|graphic|celebrat)"


def _look_by_rules(note: str) -> dict:
    low = note.lower()
    return {"card": bool(re.search(CARD_ASK, low)), "words": "", "arabic": bool(re.search(r"\barabic\b|عرب", low)), "arabic_text": "",
            "bigger_logo": bool(re.search(r"\b(bigger|larger|more visible)\b.*\blogo\b|\blogo\b.*\b(bigger|larger|more visible)\b", low)),
            "background": note if re.search(r"\b(background|colou?rs?|festive|moon|lantern|light|dark|brighter)\b", low) else "", "cannot": ""}


def change(office: Office, ref: str, sc: dict, note: str, cause: int | None) -> dict | None:
    """A person asked for a change to the finished pictures. The note is worked out into what to change (a designed card
    instead of photos, new words, Arabic, a bigger logo, what the background shows); the pictures are made again with it;
    the Director looks at before and after and says whether the change was really made. Nothing else is changed."""
    before = studio.made(office, "slides", ref) or {}
    lst = studio._listing(office, ref)
    look = None
    if meta.ready():
        try:
            look = meta.look("You turn a client's change request for a social post's picture into settings for the designer. card: true when they want a designed "
                             "card instead of the photos (festive, no property, cleaner). words: the new words for the picture if they asked to change the words, else empty; "
                             "keep facts, add none. arabic: true if they want Arabic on it; arabic_text: when arabic is true, a faithful Arabic translation of the words that will be on the picture (the new words if any, else the words on it now). "
                             "bigger_logo: true if they want the logo bigger or clearer. background: what the background should show, if they asked about the look, else "
                             "empty. cannot: what in the request a picture change can't do (for example a new price or a different property), else empty.",
                             f"The post: {lst['title']}. Words on it now: {' / '.join(x['text'] for x in before.get('images', []))[:400]}\n"
                             + (f"It is a greeting: {lst.get('greet', '')} / {lst.get('greet_ar', '')}.\n" if lst.get("greeting") else "")
                             + f"The client asked: {note[:400]}", [], LOOK_SCHEMA, agent="mart")
        except (meta.MetaError, OSError, ValueError):
            look = None
    look = look if isinstance(look, dict) and "card" in look else _look_by_rules(note)
    kept = (before.get("change") or {}).get("look") or {}  # what earlier changes asked stays: a bigger logo doesn't undo the Arabic
    look = kept | {k: v for k, v in look.items() if v} | {"asked": note}
    look["v"] = 1 + sum(1 for e in office.log.list() if e["type"] == "content.made" and e["content"].get("kind") == "slides" and e["content"].get("ref") == ref)
    new = render(office, ref, sc, cause, look=look)
    if not new:
        return None
    seen = director.done(office, note, [x["path"] for x in before.get("images", [])], [x["path"] for x in new["images"]]) if before.get("images") else None
    result = {"look": {k: v for k, v in look.items() if k not in ("asked", "v", "cannot")}, "asked": note, "applied": {k: look[k] for k in ("card", "words", "arabic", "bigger_logo", "background") if look.get(k)},
              "cannot": look.get("cannot") or "", "before": [x["served"] for x in before.get("images", [])], **(seen or {"done": None, "how": "not checked"})}
    return studio._made(office, "mart", "slides", ref, {k: v for k, v in new.items() if k not in ("id", "kind", "ref", "by")} | {"change": result}, cause)
