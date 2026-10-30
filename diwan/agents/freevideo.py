"""A video at no cost, made on this computer from the approved script: the computer's own voice (macOS `say`) reads
each line, over the listing's photos with a slow zoom, the price card where the script shows the price, and an end
card. It then goes through the same editing as filmed footage: take check, captions, cover, permit check, publish
request. No avatar and no model: for a talking presenter, the paid AI presenter (HeyGen) is the other choice.

Photos come from the listing (the CRM feed) and any the Marketing manager uploads for it in the studio.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import httpx

from diwan.config import env
from diwan.office import Office

W, H, FPS = 1080, 1920, 30


def missing() -> list[str]:
    return [x for x, ok in (("the macOS voice (say)", shutil.which("say")), ("ffmpeg", shutil.which("ffmpeg"))) if not ok]


def voice() -> str:
    return env("DIWAN_FREE_VOICE", "Samantha")


def photos(office: Office, ref: str) -> list[str]:
    """The listing's photos (links from the feed) and the ones uploaded for it, in that order."""
    lst = office.graph().nodes.get(f"listing:{ref}")
    out = list((lst.props.get("photos") or []) if lst else [])
    for e in office.log.list():
        if e["type"] == "photos.added" and e["content"]["ref"] == ref:
            out += e["content"]["paths"]
    return out


def _local(src: str, folder: Path, i: int) -> Path | None:
    """A photo as a file here: an uploaded path as it is, a web link downloaded once."""
    if not src.startswith("http"):
        p = Path(src)
        return p if p.exists() else None
    out = folder / f"photo{i}.jpg"
    if not out.exists():
        try:
            r = httpx.get(src, timeout=30, follow_redirects=True)
            if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
                return None
            out.write_bytes(r.content)
        except httpx.HTTPError:
            return None
    return out


def _card(text: str, path: Path) -> Path:
    """A plain card (the price, the end card) as a full-size picture."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (W, H), (14, 18, 27))
    d = ImageDraw.Draw(img)
    font = None
    for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(f, 72)
            break
        except OSError:
            continue
    font = font or ImageFont.load_default()
    parts = [x.strip() for x in text.split("·") if x.strip()] or [text]
    y = H // 2 - len(parts) * 60
    for ln in parts:
        d.text(((W - d.textlength(ln, font=font)) / 2, y), ln, font=font, fill=(240, 220, 170))
        y += 120
    img.save(path)
    return path


def _run(*args: str) -> None:
    r = subprocess.run(list(args), capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout)[-300:] or f"{args[0]} failed")


def make(office: Office, ref: str, *, by: str) -> dict:
    """Make the video for the approved script and hand it to editing as footage. Returns {"ok", "footage"} or {"needs"}."""
    from diwan.agents import studio
    from diwan.providers import meta
    sc = studio.approved_script(office, ref)
    if not sc:
        return {"ok": False, "needs": "an approved script (pick one first)"}
    if (m := missing()):
        return {"ok": False, "needs": ", ".join(m)}
    pics = photos(office, ref)
    if not pics:
        return {"ok": False, "needs": f"photos of {ref}: add them to the listing in the CRM, or upload some here"}
    rows = sc.get("shots") or studio.video_plan(sc, studio._listing(office, ref))
    n = 1 + sum(1 for e in office.log.list() if e["type"] == "footage.added")
    folder = meta.MEDIA / f"free-{ref}-{n}"
    folder.mkdir(parents=True, exist_ok=True)
    local = [p for i, s in enumerate(pics) if (p := _local(s, folder, i))]
    if not local:
        return {"ok": False, "needs": f"photos of {ref} that can be opened (none of the {len(pics)} links could be downloaded)"}
    clips, k = [], 0
    for i, r in enumerate(rows):
        speech = folder / f"line{i}.aiff"
        _run("say", "-v", voice(), "-o", str(speech), r["say"])
        dur = studio._duration(speech) + 0.35
        if "price card" in r["show"].lower() or "end card" in r["show"].lower():
            still = _card(r.get("text") or r["say"], folder / f"card{i}.png")
        else:
            still, k = local[k % len(local)], k + 1
        frames = max(1, round(dur * FPS))
        clip = folder / f"clip{i}.mp4"
        studio._ffmpeg("-i", str(still), "-i", str(speech),
                       "-filter_complex", f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                                          f"zoompan=z='min(zoom+0.0008,1.12)':d={frames}:s={W}x{H}:fps={FPS},format=yuv420p[v];[1:a]apad[a]",
                       "-map", "[v]", "-map", "[a]", "-t", f"{dur:.2f}", "-c:v", "libx264", "-c:a", "aac", "-ar", "44100", str(clip))
        clips.append(clip)
    listing = folder / "clips.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips))
    out = meta.MEDIA / f"footage-{ref}-{n}-free.mp4"
    studio._ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out))
    office.log.append("footage.added", actor=by, agent="mvideo",
                      content={"id": f"F{n}", "ref": ref, "path": str(out), "served": f"/media/{out.name}",
                               "source": f"free video: the computer's voice ({voice()}) over {len(local)} photo{'s' if len(local) != 1 else ''}"})
    studio._pack(office, "mvideo", f"Free video for {ref} ready ({round(studio._duration(out))} seconds, {len(rows)} shots, voice {voice()}): handed to editing.")
    return {"ok": True, "footage": f"F{n}"}
