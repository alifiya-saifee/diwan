"""Each platform gets its own version of a post, the way each one is read (docs/marketing-research-notes.md): its own
words, length, hashtags and picture shape, never the Instagram caption cut short.

Instagram posts by itself once approved. The others are written ready to copy, because posting to them needs each
platform's own app approval: the approval card shows each version with a Copy button.

One model call writes them all from the approved caption (the Content writer); the code then holds each to its
platform's limits and checks that no number appears that the caption didn't have. Without a model, each is made by
rules from the caption.
"""
from __future__ import annotations

import re

from diwan.office import Office

RULES = {  # platform: limit (characters), hashtags (fewest, most), shape, how it is written, posts by itself
    "Instagram": (2200, (3, 8), "4:5 picture (1080×1350) or 9:16 reel (1080×1920)",
                  "Short: the hook first, the point in the first two lines, then the facts in a few short lines.", True),
    "Facebook": (5000, (0, 3), "4:5 picture (1080×1350) or 9:16 video",
                 "Fuller and conversational: a clear first sentence, then the facts in plain sentences; a question to the reader is fine.", False),
    "LinkedIn": (3000, (3, 5), "4:5 or 1:1 picture, or a vertical video",
                 "Professional and insight-led: the first line (under 200 characters) says what a reader learns or why it matters, then one idea per line, "
                 "no emoji, hashtags at the end only.", False),
    "TikTok": (2200, (3, 6), "9:16 video (1080×1920)", "Very short and casual: one line that makes someone watch, then the hashtags.", False),
    "YouTube Shorts": (100, (0, 2), "9:16 video (1080×1920)", "A title only, under 100 characters, plain and specific.", False),
    "Property Finder": (500, (0, 0), "the listing's own photos", "Plain listing text: what it is, where, the key facts; no hashtags or emoji.", False),
}
SCHEMA = {"name": "versions", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["versions"], "properties": {
    "versions": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["platform", "text"],
                                            "properties": {"platform": {"type": "string"}, "text": {"type": "string"}}}}}}}
EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")


DEFAULT = ["Instagram", "Facebook", "LinkedIn"]  # where a post goes until the business picks its own (Setup, Where we post)
VIDEO_ONLY = {"TikTok", "YouTube Shorts"}  # they take a video, never pictures; off until someone picks them
LISTING_ONLY = {"Property Finder"}  # a property portal: a listing's own post, never a topic or a greeting


def known() -> list[str]:
    return list(RULES)


def for_post(office: Office, *, listing: bool, video: bool) -> list[str]:
    """The platforms this post gets a version for: the ones picked in Setup (or the defaults, plus Property Finder for a
    listing), less any that can't take it (a video-only platform for pictures, a portal for something that isn't a
    listing). Instagram, where it posts by itself, always."""
    from diwan import business
    want = business.platforms(office) or DEFAULT + (sorted(LISTING_ONLY) if listing else [])
    want = [p for p in want if p in RULES and (video or p not in VIDEO_ONLY) and (listing or p not in LISTING_ONLY)]
    return list(dict.fromkeys(["Instagram"] + want))


def _tags(text: str) -> list[str]:
    return re.findall(r"#\w+", text)


def _numbers(text: str) -> set[str]:
    return {re.sub(r"\D", "", m) for m in re.findall(r"\d[\d,.]*", text) if len(re.sub(r"\D", "", m)) >= 2}


def fit(platform: str, text: str, tags: list[str]) -> str:
    """Hold a version to its platform: the hashtags it takes (at the end), its limit, and no emoji on LinkedIn."""
    limit, (lo, hi), _, _, _ = RULES[platform]
    body = re.sub(r"(\s*#\w+)+\s*$", "", text.strip()).strip()
    have = [t for t in _tags(body)]
    body = re.sub(r"\s*#\w+", "", body).strip() if platform in ("LinkedIn", "Property Finder", "YouTube Shorts") else body
    if platform == "LinkedIn":
        body = EMOJI.sub("", body)
    use = list(dict.fromkeys(tags + have))[:hi]
    out = body + (("\n\n" if platform != "YouTube Shorts" else " ") + " ".join(use) if use and hi else "")
    if len(out) > limit:
        out = out[:limit - 1].rsplit(" ", 1)[0] + "…"
    return out.strip()


def by_rules(platform: str, caption: str) -> str:
    """Without a model: the caption reshaped for the platform."""
    tags = _tags(caption)
    body = re.sub(r"\s*#\w+", "", caption).strip()
    first = body.split("\n")[0]
    if platform == "YouTube Shorts":
        return first[:100]
    if platform == "TikTok":
        return fit(platform, first, tags)
    if platform == "Property Finder":
        return fit(platform, re.sub(r"\s*Say [A-Z0-9]+\.?", "", body), [])
    if platform == "LinkedIn":
        return fit(platform, "\n".join(x for x in body.split("\n") if x.strip()), tags)
    return fit(platform, body, tags)


def versions(office: Office, caption: str, *, what: str = "", platforms: list[str] | None = None, listing: bool = True,
             video: bool = True) -> dict[str, dict]:
    """{platform: {text, shape, posts}} for each platform this post can go to (for_post), or the ones given."""
    from diwan import brand, business
    from diwan.agents import runner
    from diwan.agents.charters import get
    want = [p for p in platforms if p in RULES] if platforms else for_post(office, listing=listing, video=video)
    if "Instagram" in RULES and "Instagram" not in want:
        want = want or ["Instagram"]
    tags = _tags(caption)
    got: dict[str, str] = {}
    c = get("mwriter")
    system = runner.instructions(c, office.log) + (
        "\nRewrite one approved caption as a version for each platform listed, each in that platform's own way. Keep every fact and number exactly; "
        "add nothing that isn't in the caption; keep the code word line if there is one. Platforms:\n"
        + "\n".join(f"- {p}: {RULES[p][3]}" for p in want if p != "Instagram"))
    user = runner.user_message("Write the versions.", {"caption": caption, "post": what[:400], "brand": brand.brief(office)})
    others = [p for p in want if p != "Instagram"]
    if others and runner.has_model(c, system, user, schema=SCHEMA):
        try:
            for v in runner.call(c, system, user, schema=SCHEMA).data.get("versions") or []:
                p = v.get("platform")
                if p in others and v.get("text") and _numbers(v["text"]) <= _numbers(caption):  # never a number the caption didn't have
                    got[p] = fit(p, v["text"], tags)
        except Exception:  # noqa: BLE001  the rules version below stands
            pass
    out = {}
    for p in want:
        text = caption if p == "Instagram" else got.get(p) or by_rules(p, caption)
        if p == "Instagram":
            text = fit(p, caption, tags)
        out[p] = {"text": text, "shape": RULES[p][2], "posts": "by itself once approved" if RULES[p][4] else "copy and post by hand"}
    return out


def check(platform: str, text: str) -> list[str]:
    """What is wrong with a version for its platform: [] when it fits."""
    limit, (lo, hi), _, _, _ = RULES[platform]
    tags = _tags(text)
    bad = []
    if len(text) > limit:
        bad.append(f"{len(text)} characters, over {limit}")
    if not lo <= len(tags) <= hi:
        bad.append(f"{len(tags)} hashtags, {platform} takes {lo} to {hi}")
    if platform == "LinkedIn" and EMOJI.search(text):
        bad.append("emoji on LinkedIn")
    return bad
