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

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

from diwan import brand, business, topics
from diwan.agents import freevideo, studio
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


def photos(office: Office, ref: str) -> list[dict]:
    """The uploaded photos with what is known of each: measured always; read by the model once `read` has run."""
    known = {p["path"]: p for e in office.log.list() if e["type"] == "photo.read" and e["content"]["ref"] == ref for p in e["content"]["photos"]}
    out = []
    for path in freevideo.photos(office, ref):
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
    t = topics.get(office, ref) or {}
    try:
        r = meta.look("You describe event photos for a marketing team. Say only what can be seen. Never guess a name or who someone is.",
                      f"Event: {t.get('title')}. For each photo, in order, starting at 1: n; what (what can be seen, under 15 words); people (true if a person's "
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


def choose(office: Office, ref: str, fmt: str, *, by: str) -> None:
    if fmt not in FORMATS:
        raise ValueError(f"The format is one of: {', '.join(FORMATS)}.")
    if fmt in ("carousel", "image") and not suggest(office, ref)["usable"]:
        raise ValueError("That format needs at least one usable photo.")
    if fmt == "carousel" and suggest(office, ref)["usable"] < 2:
        raise ValueError("A carousel needs at least two usable photos.")
    office.log.append("topic.saved", actor=by, content={"ref": ref, "format": fmt})


def shape(office: Office, lst: dict) -> dict | None:
    """How a post made as pictures will be made, for the writers: a moment, or a teaching post when competitors' winners
    show words on pictures work. None for everything else. A post about the brand stays a person speaking: people buy from people."""
    from diwan.agents import taste
    ours = taste.weight(office, "format:graphic"), taste.weight(office, "format:reel, to camera")  # what this business itself said beats what competitors do
    leans = ours[1] <= taste.BLOCK or (ours[0] > taste.BLOCK and bool(_text_wins(office)))
    teaching = lst.get("item") == "topic" and not lst.get("job") and not lst["ref"].startswith("JOB-") and leans
    if not lst.get("moment") and not teaching:
        return None
    s = suggest(office, lst["ref"])
    if not lst.get("moment") and s["format"] == "reel":
        return None  # there is real footage: use it
    good = sorted([p for p in photos(office, lst["ref"]) if p["usable"]], key=lambda p: -p.get("strength", 0))
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
    out = []
    for i, text in enumerate(words):
        k = wanted[i] - 1 if i < len(wanted) and isinstance(wanted[i], int) else -1
        path = sh["photos"][k]["path"] if 0 <= k < len(sh["photos"]) and sh["photos"][k]["path"] in free else free[0]
        free.remove(path)
        out.append({"photo": path, "text": text})
    return out


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


def _fit(img: Image.Image) -> Image.Image:
    """Crop to the post's shape around the middle; nothing else changes in a real photo."""
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)))
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _background(office: Office, ref: str) -> tuple[Image.Image, str]:
    """A graphic's background: abstract, made by Muse Image when it can be, else plain."""
    plain = Image.new("RGB", (W, H), INK)
    if not meta.ready():
        return plain, "plain"
    voice = brand.profile(office)["voice"]["value"] or "calm, professional"
    try:
        served = meta.image(f"A refined background for a post by this business: {business.describe(office)} Mood: {voice}. Quiet and uncluttered, so words read easily on it, "
                            "and it clearly suits this trade and place. Strictly no text, letters, logos, people, faces, clip-art icons or real buildings.", f"bg-{ref}", size="1024x1792")
        return _fit(Image.open(meta.media_path(served)).convert("RGB")), "Muse Image"
    except (meta.MetaError, OSError) as e:
        studio._blocked(office, "mthumb", f"Muse Image failed, using a plain background: {str(e)[:120]}")
        return plain, "plain"


def _draw(img: Image.Image, text: str, name: str, centre: bool) -> Image.Image:
    """The words on a dark band across the bottom (or the middle of a graphic), and the brand's name."""
    img = img.convert("RGBA")
    d = ImageDraw.Draw(img)
    font = _font(64)
    lines = _wrap(d, text, font, W - 160)
    while len(lines) > 5 and font.size > 36:
        font = _font(font.size - 6)
        lines = _wrap(d, text, font, W - 160)
    high = len(lines) * (font.size + 16) + 96
    top = (H - high) // 2 if centre else H - high
    band = Image.new("RGBA", (W, high), (*INK, 205))
    img.alpha_composite(band, (0, top))
    d = ImageDraw.Draw(img)
    y = top + 48
    for ln in lines:
        d.text((80, y), ln, font=font, fill=(255, 255, 255))
        y += font.size + 16
    if name:
        small = _font(30)
        d.text((W - 60 - d.textlength(name, font=small), 40), name, font=small, fill=GOLD, stroke_width=2, stroke_fill=INK)
    return img.convert("RGB")


def render(office: Office, ref: str, sc: dict, cause: int | None) -> dict | None:
    """The real images for the approved post."""
    name = brand.profile(office)["name"]["value"].strip()
    meta.MEDIA.mkdir(exist_ok=True)
    out, bg_by = [], None
    for i, s in enumerate(sc["slides"], 1):
        if s["photo"]:
            base = _load(s["photo"])
            if base is None:
                studio._blocked(office, "mart", f"A photo of {ref} can't be opened any more: {Path(s['photo']).name}", cause=cause)
                return None
            base = _fit(base)
        else:
            base, bg_by = _background(office, ref)
        path = meta.MEDIA / f"post-{ref}-{sc['id']}-{i}.jpg"
        _draw(base, s["text"], name, centre=not s["photo"]).save(path, "JPEG", quality=90)
        out.append({"path": str(path), "served": f"/media/{path.name}", "text": s["text"]})
    known = {p["path"]: p for p in photos(office, ref)}
    people = sum(1 for s in sc["slides"] if known.get(s["photo"], {}).get("people"))
    m = studio._made(office, "mart", "slides", ref, {"images": out, "format": sc["format"], "people": people, **({"background": bg_by} if bg_by else {})}, cause)
    studio._pack(office, "mart", f"{FORMATS[sc['format']]} for {ref} ready: {len(out)} image{'s' if len(out) != 1 else ''}"
                 + (f", background: {bg_by}" if bg_by else "") + (f"; {people} show people" if people else "") + ".", cause=cause)
    return m
