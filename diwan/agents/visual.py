"""The visual brief: written by the script writer with the script, in the same call, so the words and the pictures are one
idea. It says what kind of post it is and, frame by frame, what the background shows, where the words go and how big,
where the logo sits, and for a video how each frame moves and for how long. The person sees it before picking a
script; the makers follow it (eventpost.render for a post's pictures, freevideo.ai_frames for a video's).

What the writer may choose is limited by the rules that already decided the post (eventpost.shape, topics.format_for):
the kind is set by them, and a listing's backgrounds are only ever its own photos. Anything missing or out of bounds
falls back to the house layout, so an old script without a brief is made exactly as before.
"""
from __future__ import annotations

import re

SOURCES = ("listing photo", "speaker", "AI photo", "brand colour")
TEXT_AT = ("top", "middle", "bottom")
SIZES = ("big", "medium", "small")
STYLES = ("band", "plain")
LOGO_AT = ("top-left", "top-right", "bottom-left", "bottom-right")
MOTIONS = ("none", "slow zoom in", "slow zoom out", "pan left", "pan right")

KINDS = {"graphic": "a single designed picture with words on it", "image": "a single photo with words on it",
         "carousel": "a carousel of pictures, one idea per slide", "to camera": "a short vertical video of a person talking to camera",
         "voice-over": "a short vertical video of the property's shots with a voice-over"}

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["why", "mood", "frames"], "properties": {
    "why": {"type": "string", "description": "one line: why this look, from the research and the plan"},
    "mood": {"type": "string", "description": "music and pace for a video; empty for a still"},
    "frames": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["background", "words", "logo", "motion", "seconds"],
                                          "properties": {
        "background": {"type": "object", "additionalProperties": False, "required": ["source", "place", "subject", "camera", "light"], "properties": {
            "source": {"type": "string", "enum": list(SOURCES)}, "place": {"type": "string"}, "subject": {"type": "string"},
            "camera": {"type": "string"}, "light": {"type": "string"}}},
        "words": {"type": "object", "additionalProperties": False, "required": ["text", "position", "size", "style"], "properties": {
            "text": {"type": "string"}, "position": {"type": "string", "enum": list(TEXT_AT)}, "size": {"type": "string", "enum": list(SIZES)},
            "style": {"type": "string", "enum": list(STYLES)}}},
        "logo": {"type": "string", "enum": list(LOGO_AT)},
        "motion": {"type": "string", "enum": list(MOTIONS)},
        "seconds": {"type": "number"}}}}}}


def kind_of(lst: dict, sh: dict | None, pictures: bool) -> str:
    """The kind the rules already chose for this post."""
    from diwan import topics
    return sh["format"] if pictures and sh else topics.format_for(lst)


def sources(lst: dict, kind: str) -> tuple[str, ...]:
    """Where a frame's background may come from. A listing shows itself: its own photos, never a made-up picture."""
    if lst.get("item") != "topic":
        return ("listing photo",)
    if lst.get("greeting"):
        return ("brand colour",)
    return ("speaker", "AI photo") if kind == "to camera" else ("AI photo",)  # a topic's still is a real-looking photo, never an abstract pattern


def instructions(lst: dict, kind: str, title: str, record: str = "") -> str:
    """What the writer is told about the brief."""
    from diwan.agents import shots
    places = {n: lk for n, lk in (shots.look_of(x) for x in re.split(r"[\n.;]", f"{title}. {record}")) if n}
    ok = sources(lst, kind)
    return ("\n\nAlso write `visual`, the visual brief for the person who approves it and for the makers. This post is "
            f"{KINDS.get(kind, kind)}: that is decided. `why` says in one line why this look fits, from the research and the plan. "
            "`mood` is the music and pace for a video, empty for a still. `frames`: one per spoken line, the hook first, in order "
            "(a single picture uses the first). For each frame:\n"
            f"- background.source: one of {', '.join(ok)}."
            + (" A listing is only ever shown in its own photos: subject says which of its photos (the view, the kitchen…)." if ok == ("listing photo",) else "")
            + "\n- background.subject: one concrete scene a photographer could shoot on a real day, never an idea, a map, a model, a collage, "
            "an icon or anything with words on it. place: the real named place it shows, or empty; when the line names a place, show that place "
            "as it really looks. camera: where the camera stands and the lens. light: the time of day and light. For `speaker`, describe the "
            "framing and the setting behind the person. People only from behind or far away, never a recognisable face.\n"
            "- words.text: the 2 to 8 words shown on that frame, taken from that line; position top, middle or bottom where the picture is calm; "
            "size big for the hook, medium or small after; style band (a dark strip behind the words) on a busy picture, plain on a calm one.\n"
            "- logo: the corner for the logo, away from the words.\n"
            "- motion and seconds: for a video how the frame moves and how long it holds (about the time the line takes to say); "
            "for a still, none and 0."
            + (f"\nWhat the places named here really look like: " + "; ".join(f"{n}: {lk}" for n, lk in places.items()) if places else ""))


def _pick(v, allowed: tuple, default):
    return v if v in allowed else default


def clean(v: dict | None, lst: dict, kind: str, data: dict) -> dict | None:
    """The brief as the makers may use it: kinds and sources the rules allow, words only from the script, sensible timing.
    None when there is nothing usable."""
    if not isinstance(v, dict) or not isinstance(v.get("frames"), list) or not v["frames"]:
        return None
    said = " ".join([data.get("hook_en", ""), *data.get("lines_en", [])]).lower()
    words = set(re.findall(r"[a-z0-9']+", said))
    ok = sources(lst, kind)
    still = kind in ("graphic", "image", "carousel")
    frames = []
    spoken = [data.get("hook_en", ""), *data.get("lines_en", [])]
    for i, f in enumerate(v["frames"][:12]):
        if not isinstance(f, dict):
            continue
        bg, w = f.get("background") or {}, f.get("words") or {}
        text = (w.get("text") or "").strip()
        if text and not set(re.findall(r"[a-z0-9']+", text.lower())) <= words:  # words on screen come from the script, never new claims
            text = ""
        if not text and i < len(spoken):  # no usable words: the frame's own line, as the maker draws it
            text = spoken[i]
        frames.append({
            "background": {"source": _pick(bg.get("source"), ok, ok[0]), **{k: str(bg.get(k) or "")[:300] for k in ("place", "subject", "camera", "light")}},
            "words": {"text": text[:80], "position": _pick(w.get("position"), TEXT_AT, "middle" if still else "bottom"),
                      "size": _pick(w.get("size"), SIZES, "big" if i == 0 else "medium"), "style": _pick(w.get("style"), STYLES, "band")},
            "logo": _pick(f.get("logo"), LOGO_AT, "top-left"),
            "motion": "none" if still else _pick(f.get("motion"), MOTIONS, "slow zoom in"),
            "seconds": 0 if still else min(8.0, max(1.5, float(f.get("seconds") or 3)))})
    if not frames:
        return None
    for f in frames:  # the words and the logo never share a corner of the picture
        if f["words"]["position"] == f["logo"].split("-")[0]:
            f["logo"] = ("bottom" if f["words"]["position"] == "top" else "top") + "-" + f["logo"].split("-")[1]
    return {"kind": kind, "why": str(v.get("why") or "")[:240], "mood": "" if still else str(v.get("mood") or "")[:160], "frames": frames}


def frame(sc: dict | None, i: int) -> dict | None:
    """The brief's frame for slide or shot `i` (from 0), or None."""
    fr = ((sc or {}).get("visual") or {}).get("frames") or []
    return fr[i] if 0 <= i < len(fr) else None


def shot(f: dict) -> dict | None:
    """A frame's background as a shot for shots.prompt(), when it is a made picture with a subject."""
    from diwan.agents import shots
    b = (f or {}).get("background") or {}
    if b.get("source") != "AI photo" or not b.get("subject"):
        return None
    return {"place": b.get("place", ""), "subject": b["subject"], "camera": b.get("camera") or "eye level, 24mm wide lens",
            "light": b.get("light") or "late afternoon golden hour", "looks": shots.look_of(b.get("place") or b["subject"])[1]}


def describe(v: dict | None) -> list[str]:
    """The brief in plain words, one line a frame, for the person who approves it."""
    if not v:
        return []
    out = []
    for i, f in enumerate(v["frames"], 1):
        b, w = f["background"], f["words"]
        pic = {"listing photo": f"the listing's photo: {b['subject']}" if b["subject"] else "the listing's own photo",
               "speaker": f"you to camera{': ' + b['subject'] if b['subject'] else ''}", "brand colour": "a designed background in the brand's colours"}.get(
            b["source"], f"AI photo of {b['subject']}" + (f" ({b['light']})" if b["light"] else ""))
        words = f'"{w["text"]}", {w["size"]}, {w["position"]}' + (" on a band" if w["style"] == "band" else "") if w["text"] else "no words"
        move = f" · {f['seconds']:g} s, {f['motion']}" if f["seconds"] else ""
        out.append(f"Frame {i} · {pic} · {words} · logo {f['logo']}{move}")
    return out
