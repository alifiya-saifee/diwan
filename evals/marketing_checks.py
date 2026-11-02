"""Checks in code on what the Marketing room makes: no model, the same answer every time. Each check returns
{"check", "ok", "detail"}; a list of them is one item's verdict. Used by e2e/marketing_real_user.py.

Images and video frames are read with tesseract (OCR), so "is the brand name on it" is measured, not guessed.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

FOREIGN = re.compile(r"re/?max|samplebrokerage|sample realty", re.I)  # names from the real website the test data was read from
PLACEHOLDER = re.compile(r"\[[^\]]*\]|\bTBD\b|\blorem\b|\bplaceholder\b|\bSay BRAND\b", re.I)
PLATFORM = {  # the platforms' own published limits and sizes (2026): caption characters, hashtags that read well, picture shapes
    "Instagram": {"chars": 2200, "tags": (3, 10), "shapes": {(1080, 1350), (1080, 1080), (1080, 1920)}},
    "Facebook": {"chars": 63206, "tags": (0, 3), "shapes": {(1080, 1350), (1080, 1080), (1200, 630), (1080, 1920)}},
    "LinkedIn": {"chars": 3000, "tags": (3, 5), "shapes": {(1200, 627), (1080, 1080), (1080, 1350)}},
    "TikTok": {"chars": 2200, "tags": (3, 6), "shapes": {(1080, 1920)}},
    "YouTube Shorts": {"chars": 100, "tags": (0, 3), "shapes": {(1080, 1920)}},
    "Property Finder": {"chars": 500, "tags": (0, 0), "shapes": set()},
}


def c(check: str, ok: bool, detail: str = "") -> dict:
    return {"check": check, "ok": bool(ok), "detail": str(detail)[:200]}


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", (s or "").lower())


# ---------- text ----------

def script(sc: dict, *, brand_name: str = "", price: int | float | None = None, about_brand: bool = False) -> list[dict]:
    lines = [sc.get("hook_en", ""), *sc.get("lines_en", [])]
    flat = " ".join(lines)
    norm = [re.sub(r"[^a-z0-9]", "", x.lower()) for x in lines if x.strip()]
    out = [c("hook ≤ 12 words", len(words(sc.get("hook_en", ""))) <= 12, sc.get("hook_en", "")),
           c("5 to 8 lines", 5 <= len(sc.get("lines_en", [])) <= 8, len(sc.get("lines_en", []))),
           c("no repeated line", len(norm) == len(set(norm))),
           c("no placeholder or junk", not PLACEHOLDER.search(flat), (PLACEHOLDER.search(flat) or [""])[0]),
           c("no other company's name", not FOREIGN.search(flat), (FOREIGN.search(flat) or [""])[0]),
           c("ends inviting contact", bool(re.search(r"\b(message|dm|call|whatsapp|book|contact|get in touch|reach out|talk to|visit)\b", (sc.get("lines_en") or [""])[-1], re.I)),
             (sc.get("lines_en") or [""])[-1])]
    if about_brand and brand_name:
        out.append(c("names the company", brand_name.lower() in flat.lower(), brand_name))
    if price:
        money = {int(re.sub(r"\D", "", m)) for m in re.findall(r"\d[\d,]{4,}", flat)}
        out.append(c("only the real price", not money or money <= {int(price)}, sorted(money)))
    return out


def caption(text: str, platform: str = "Instagram", *, brand_name: str = "") -> list[dict]:
    lim = PLATFORM.get(platform, PLATFORM["Instagram"])
    tags = re.findall(r"#\w+", text or "")
    lo, hi = lim["tags"]
    out = [c(f"{platform}: within {lim['chars']} characters", len(text or "") <= lim["chars"], len(text or "")),
           c(f"{platform}: {lo}–{hi} hashtags", lo <= len(tags) <= hi, len(tags)),
           c(f"{platform}: no hashtag over 25 characters", all(len(t) <= 26 for t in tags), [t for t in tags if len(t) > 26][:2]),
           c(f"{platform}: no placeholder or junk", not PLACEHOLDER.search(text or ""), (PLACEHOLDER.search(text or "") or [""])[0]),
           c(f"{platform}: no other company's name", not FOREIGN.search(text or ""), (FOREIGN.search(text or "") or [""])[0])]
    place = re.findall(r"[A-Z][a-z]+(?: [A-Z][a-z]+)*", text or "")
    rep = [w for w, n in Counter(place).items() if n >= 3 and len(w) > 3]
    out.append(c(f"{platform}: no place name 3 times", not rep, rep[:3]))
    if brand_name:
        out.append(c(f"{platform}: names the company", brand_name.lower() in (text or "").lower(), brand_name))
    return out


def code_word(w: str) -> list[dict]:
    return [c("code word means something", bool(w) and w.upper() not in ("HELLO", "POST", "CODE"), w)]


# ---------- pictures ----------

def ocr(path: str | Path) -> str:
    if not shutil.which("tesseract"):
        return ""
    r = subprocess.run(["tesseract", str(path), "-", "--psm", "11"], capture_output=True, text=True)
    return re.sub(r"\s+", " ", r.stdout).strip()


def image(path: str | Path, *, brand_name: str = "", expect: tuple[int, int] | None = (1080, 1350), words_on: str = "") -> list[dict]:
    from PIL import Image, ImageStat
    p = Path(path)
    if not p.exists():
        return [c("image exists", False, str(p))]
    im = Image.open(p).convert("RGB")
    stat = ImageStat.Stat(im.convert("L"))
    text = ocr(p)
    out = [c("image exists", True, p.name),
           c("size", expect is None or im.size == expect, f"{im.size[0]}x{im.size[1]}"),
           c("not blank", stat.stddev[0] > 12, round(stat.stddev[0], 1)),
           c("words readable (OCR finds 3+ words)", len(words(text)) >= 3, text[:80])]
    if brand_name:
        out.append(c("company name on the picture", brand_name.lower().split()[0] in text.lower(), brand_name))
    if words_on:
        want = [w for w in words(words_on) if len(w) > 3]
        hit = sum(1 for w in want if w in text.lower())
        out.append(c("its words are on it", not want or hit / len(want) >= .5, f"{hit}/{len(want)}"))
    return out


def has_logo(path: str | Path, logo: str | Path) -> dict:
    """The logo is on the picture: template match of the logo, scaled, in the picture's corners and edges."""
    try:
        import numpy as np
        from PIL import Image
        big = np.asarray(Image.open(path).convert("L"), dtype=float)
        best = 0.0
        for w in (90, 120, 160, 200, 260):
            lg = Image.open(logo).convert("L")
            lg = lg.resize((w, max(1, int(lg.height * w / lg.width))))
            t = np.asarray(lg, dtype=float)
            t = (t - t.mean()) / (t.std() + 1e-6)
            th, tw = t.shape
            step = 8
            for y in range(0, big.shape[0] - th, step):
                for x in range(0, big.shape[1] - tw, step):
                    if not (y < big.shape[0] * .22 or y > big.shape[0] * .7 or x < big.shape[1] * .2 or x > big.shape[1] * .6):
                        continue  # logos sit near an edge or a corner
                    win = big[y:y + th, x:x + tw]
                    s = float(((win - win.mean()) / (win.std() + 1e-6) * t).mean())
                    best = max(best, s)
        return c("logo on the picture", best > .55, round(best, 2))
    except Exception as e:  # noqa: BLE001
        return c("logo on the picture", False, f"could not check: {e}")


# ---------- video ----------

def probe(path: str | Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    try:
        return json.loads(r.stdout or "{}")
    except ValueError:
        return {}


def frame(path: str | Path, at: float, out: Path) -> Path:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{at}", "-i", str(path), "-frames:v", "1", str(out)], capture_output=True)
    return out


def video(path: str | Path, *, hook: str = "", brand_name: str = "") -> tuple[list[dict], list[Path]]:
    p = Path(path)
    if not p.exists():
        return [c("video exists", False, str(p))], []
    info = probe(p)
    streams = info.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    dur = float((info.get("format") or {}).get("duration") or 0)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1) if num else 0
    tmp = Path(tempfile.mkdtemp())
    frames = [frame(p, t, tmp / f"f{i}.jpg") for i, t in enumerate((1.0, dur * .5, max(0, dur - 1)))]
    first, last = ocr(frames[0]), ocr(frames[-1])
    out = [c("video exists", True, p.name),
           c("9:16 at 1080 wide", (v.get("width"), v.get("height")) in ((1080, 1920),), f"{v.get('width')}x{v.get('height')}"),
           c("15 to 90 seconds", 15 <= dur <= 90, round(dur, 1)),
           c("24+ frames a second", fps >= 24, round(fps, 1)),
           c("has sound", any(s.get("codec_type") == "audio" for s in streams)),
           c("words on screen in the first second", len(words(first)) >= 2, first[:80])]
    if hook:
        want = [w for w in words(hook) if len(w) > 3]
        out.append(c("the hook shows at the start", not want or sum(w in first.lower() for w in want) / len(want) >= .4, first[:80]))
    if brand_name:
        out.append(c("ends on the company name", brand_name.lower().split()[0] in last.lower(), last[:80]))
    return out, frames


# ---------- the plan ----------

def plan(days: list[dict]) -> list[dict]:
    """days: [{date, ref, format}] from the plan. Mixed formats each week, nothing twice in a row."""
    weeks: dict[int, list[str]] = {}
    for i, d in enumerate(days):
        weeks.setdefault(i // 7, []).append(d.get("format") or "?")
    out = []
    for w, fs in weeks.items():
        counts = Counter(fs)
        out.append(c(f"week {w + 1}: more than one format", len(counts) > 1 or len(fs) < 2, dict(counts)))
        out.append(c(f"week {w + 1}: no format over 60%", max(counts.values()) / len(fs) <= .6 or len(fs) < 3, dict(counts)))
    refs = [d.get("ref") for d in days if d.get("ref")]
    out.append(c("no subject twice in a row", all(a != b for a, b in zip(refs, refs[1:])), refs[:8]))
    return out


def passed(checks: list[dict]) -> bool:
    return all(x["ok"] for x in checks)
