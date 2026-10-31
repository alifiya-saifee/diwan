"""A video at no cost, made on this computer from the approved script: the computer's own voice (macOS `say`, or the Windows one) reads
each line, over the listing's photos with a slow zoom, the price card where the script shows the price, and an end
card. It then goes through the same editing as filmed footage: take check, captions, cover, permit check, publish
request. No avatar and no model: for a talking presenter, the paid AI presenter (HeyGen) is the other choice.

Photos come from the listing (the CRM feed) and any the Marketing manager uploads for it in the studio.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from diwan.config import env
from diwan.office import Office

W, H, FPS = 1080, 1920, 30
WINDOWS = sys.platform == "win32"


def missing() -> list[str]:
    return [x for x, ok in (("the computer's voice", WINDOWS or shutil.which("say")), ("ffmpeg", shutil.which("ffmpeg"))) if not ok]


def voice() -> str:
    return env("DIWAN_FREE_VOICE", "the Windows voice" if WINDOWS else "Samantha")


def _speak(text: str, path: Path) -> Path:
    """The line as a sound file."""
    if not WINDOWS:
        out = path.with_suffix(".aiff")
        _run("say", "-v", voice(), "-o", str(out), text)
        return out
    out, words = path.with_suffix(".wav"), path.with_suffix(".txt")
    words.write_text(text, encoding="utf-8")  # read from a file, so nothing in the script reaches the shell
    _run("powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
         f"$s.SetOutputToWaveFile('{out}'); $s.Speak((Get-Content -Raw -Encoding UTF8 '{words}')); $s.Dispose()")
    return out


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


def _fit(path: Path) -> "Image.Image":
    from PIL import Image
    img = Image.open(path).convert("RGB")
    k = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * k), round(img.height * k)))
    x, y = (img.width - W) // 2, (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def _font(size: int):
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/arialbd.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _card(text: str, path: Path, back: Path | None = None) -> Path:
    """A card over the property itself, blurred and darkened so the words stand out: the price, or the end of the reel."""
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    img = ImageEnhance.Brightness(_fit(back).filter(ImageFilter.GaussianBlur(26))).enhance(.35) if back else Image.new("RGB", (W, H), (14, 18, 27))
    d = ImageDraw.Draw(img)
    parts = [x.strip() for x in text.split("·") if x.strip()] or [text]
    y = H // 2 - len(parts) * 80
    for i, ln in enumerate(parts):
        font = _font(112 if i == 0 else 68)
        while d.textlength(ln, font=font) > W - 120 and font.size > 40:
            font = _font(font.size - 6)
        d.text(((W - d.textlength(ln, font=font)) / 2, y), ln, font=font, fill=(240, 220, 170) if i == 0 else (255, 255, 255))
        y += font.size + 56
    img.save(path)
    return path


def _title(text: str, path: Path) -> Path:
    """The hook, big, on a band across the upper part of the opening shot."""
    from PIL import Image, ImageDraw
    font, words, lines, line = _font(92), text.split(), [], ""
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for w in words:
        t = f"{line} {w}".strip()
        if d.textlength(t, font=font) > W - 140 and line:
            lines.append(line)
            line = w
        else:
            line = t
    lines.append(line)
    high = len(lines) * 112 + 70
    img = Image.new("RGBA", (W, high), (14, 18, 27, 190))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        d.text(((W - d.textlength(ln, font=font)) / 2, 34 + i * 112), ln, font=font, fill=(255, 255, 255))
    img.save(path)
    return path


def spoken(text: str) -> str:
    """How a person says a line: no permit numbers (they are on screen), prices and sizes in words."""
    t = re.sub(r"[^.!?]*\bpermit\b[^.!?]*[.!?]?", " ", text, flags=re.I)

    def money(m):
        v = int(m.group(1).replace(",", ""))
        if v >= 1_000_000:
            return f"{v / 1_000_000:g} million dirhams"
        return f"{v // 1000} thousand dirhams" if v >= 1000 else f"{v} dirhams"
    t = re.sub(r"AED\s*([\d,]+)", money, t)
    t = re.sub(r"\b(\d)-bed\b", lambda m: f"{m.group(1)} bedroom", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


MOVES = ("in", "right", "out", "left")


def _shot(still: Path, seconds: float, move: str, out: Path) -> None:
    """One shot: 2 to 3 seconds of a still with real movement; each shot moves differently from the last."""
    from diwan.agents import studio
    frames = max(2, round(seconds * FPS))
    step = .22 / frames
    z, x, y = {"in": (f"1+{step:.6f}*on", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
               "out": (f"1.22-{step:.6f}*on", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
               "right": ("1.2", f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"),
               "left": ("1.2", f"(iw-iw/zoom)*(1-on/{frames})", "ih/2-(ih/zoom/2)")}[move]
    studio._ffmpeg("-i", str(still), "-vf", f"scale={W * 3 // 2}:{H * 3 // 2}:force_original_aspect_ratio=increase,crop={W * 3 // 2}:{H * 3 // 2},"
                                            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS},format=yuv420p",
                   "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast", str(out))


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
    n_ = 1 + sum(1 for e in office.log.list() if e["type"] == "footage.added")
    folder = meta.MEDIA / f"free-{ref}-{n_}"
    folder.mkdir(parents=True, exist_ok=True)
    local = [p for i, s in enumerate(pics) if (p := _local(s, folder, i))]
    if not local:
        return {"ok": False, "needs": f"photos of {ref} that can be opened (none of the {len(pics)} links could be downloaded)"}
    from diwan import brand
    from diwan.agents import marketing
    shots, voices, said, at, k, m = [], [], [], 0.0, 0, 0
    for i, r in enumerate(rows):
        words = spoken(r["say"])
        if not words:
            continue
        speech = _speak(words, folder / f"line{i}")
        dur = studio._duration(speech) + 0.3
        pad = folder / f"voice{i}.wav"
        studio._ffmpeg("-i", str(speech), "-af", f"apad=whole_dur={dur:.2f}", "-ar", "44100", "-ac", "1", str(pad))
        voices.append(pad)
        if i:  # the hook is the big title; everything after it is a caption
            said.append({"start": round(at, 2), "end": round(at + dur - .15, 2), "text": words})
        show = r["show"].lower()
        last = i == len(rows) - 1
        if "price card" in show or "end card" in show or last:
            name = brand.profile(office)["name"]["value"].strip()
            text = f"{name} · Message us · Say {marketing.code_for(office, ref)}" if last else r.get("text") or words
            card = _card(text, folder / f"card{i}.png", local[k % len(local)])
            parts = [(card, dur)]
        else:
            n = max(1, round(dur / 2.6))
            parts = []
            for _ in range(n):
                parts.append((local[k % len(local)], dur / n))
                k += 1
        for still, secs in parts:
            clip = folder / f"shot{len(shots)}.mp4"
            _shot(still, secs, MOVES[m % len(MOVES)], clip)
            m += 1
            shots.append(clip)
        at += dur
    if not shots:
        return {"ok": False, "needs": "a script with something to say"}
    picture, voice_ = folder / "picture.mp4", folder / "voice.wav"
    (folder / "shots.txt").write_text("".join(f"file '{c.name}'\n" for c in shots))
    (folder / "voices.txt").write_text("".join(f"file '{c.name}'\n" for c in voices))
    studio._ffmpeg("-f", "concat", "-safe", "0", "-i", str(folder / "shots.txt"), "-c", "copy", str(picture))
    studio._ffmpeg("-f", "concat", "-safe", "0", "-i", str(folder / "voices.txt"), "-c", "copy", str(voice_))
    title = _title(sc["hook_en"], folder / "title.png")
    first = studio._duration(voices[0])
    out = meta.MEDIA / f"footage-{ref}-{n_}-free.mp4"
    music = env("DIWAN_FREE_MUSIC")  # your own or a licensed track, under the voice; none is built in
    inputs = ["-i", str(picture), "-i", str(voice_), "-i", str(title)] + (["-stream_loop", "-1", "-i", music] if music and Path(music).exists() else [])
    mix = ";[3:a]volume=0.14[m];[1:a][m]amix=inputs=2:duration=first[a]" if len(inputs) > 6 else ""
    studio._ffmpeg(*inputs, "-filter_complex", f"[0:v][2:v]overlay=0:240:enable='lt(t,{first:.2f})',format=yuv420p[v]{mix}", "-map", "[v]", "-map", "[a]" if mix else "1:a",
                   "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "44100", "-shortest", str(out))
    office.log.append("footage.added", actor=by, agent="mvideo",
                      content={"id": f"F{n_}", "ref": ref, "path": str(out), "served": f"/media/{out.name}",
                               "source": f"free video: {voice()} over {len(local)} photo{'s' if len(local) != 1 else ''}, {len(shots)} shots", "lines": said})
    studio._pack(office, "mvideo", f"Free video for {ref} ready ({round(studio._duration(out))} seconds, {len(shots)} shots, {voice()}): handed to editing.")
    return {"ok": True, "footage": f"F{n_}"}
