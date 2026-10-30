"""Instagram Graph API (Meta), for an Instagram professional account connected to a Meta app.

- Our posts and their numbers: GET /{ig-user-id}/media (like_count, comments_count) and /{media-id}/insights.
- Competitors' public posts: business discovery, GET /{ig-user-id}?fields=business_discovery.username(NAME){...}.
  Works for other business and creator accounts only; it gives likes and comments, not views.
- Publishing a reel: POST /{ig-user-id}/media (REELS, a public video_url, caption), wait for FINISHED, then
  POST /{ig-user-id}/media_publish. The video must be reachable at a public https address.
- Comments arrive by webhook (object "instagram", field "comments"); a reply goes to POST /{comment-id}/replies.
Off until IG_ACCESS_TOKEN and IG_USER_ID are set.
"""
from __future__ import annotations

import time

import httpx

from diwan.config import env

GRAPH = "https://graph.facebook.com/v21.0"
TRANSPORT: httpx.BaseTransport | None = None
MEDIA_FIELDS = "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,like_count,comments_count"


class InstagramError(RuntimeError):
    pass


def missing() -> list[str]:
    return [k for k in ("IG_ACCESS_TOKEN", "IG_USER_ID") if not env(k)]


def ready() -> bool:
    return not missing()


_CHECKED: dict[int, tuple[float, dict]] = {}


def check(ttl: float = 600) -> dict:
    """Does Instagram accept our token? {"ok": True, "username"} or {"ok": False, "why"}. One cheap call, remembered for
    ttl seconds, so a page can show the truth without calling Instagram on every load."""
    if not ready():
        return {"ok": False, "why": "needs " + ", ".join(missing())}
    key = hash((env("IG_ACCESS_TOKEN"), env("IG_USER_ID")))
    hit = _CHECKED.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    try:
        out = {"ok": True, "username": _get(env("IG_USER_ID"), {"fields": "username"}).get("username")}
    except (InstagramError, httpx.HTTPError) as e:
        hint = " (this is an Instagram-login token; Diwan needs the Facebook Page token of a Page linked to the account)" if env("IG_ACCESS_TOKEN").startswith("IG") else ""
        out = {"ok": False, "why": f"Instagram refused the token: {str(e)[:160]}{hint}"}
    _CHECKED[key] = (time.monotonic(), out)
    return out


def _get(path: str, params: dict) -> dict:
    if not ready():
        raise InstagramError("needs " + ", ".join(missing()))
    with httpx.Client(transport=TRANSPORT, timeout=30) as c:
        r = c.get(f"{GRAPH}/{path}", params={**params, "access_token": env("IG_ACCESS_TOKEN")})
    data = r.json() if r.headers.get("content-type", "").startswith(("application/json", "text/javascript")) else {}
    if r.status_code >= 300 or "error" in data:
        raise InstagramError((data.get("error") or {}).get("message") or f"Instagram returned {r.status_code}")
    return data


def _post(path: str, data: dict) -> dict:
    if not ready():
        raise InstagramError("needs " + ", ".join(missing()))
    with httpx.Client(transport=TRANSPORT, timeout=60) as c:
        r = c.post(f"{GRAPH}/{path}", data={**data, "access_token": env("IG_ACCESS_TOKEN")})
    out = r.json() if r.content else {}
    if r.status_code >= 300 or "error" in out:
        raise InstagramError((out.get("error") or {}).get("message") or f"Instagram returned {r.status_code}")
    return out


def _post_row(m: dict, account: str) -> dict:
    return {"id": m["id"], "account": account, "caption": (m.get("caption") or "")[:600], "type": m.get("media_type"),
            "media_url": m.get("media_url"), "thumb": m.get("thumbnail_url") or (m.get("media_url") if m.get("media_type") in ("IMAGE", "CAROUSEL_ALBUM") else None),
            "permalink": m.get("permalink"), "at": m.get("timestamp"), "likes": m.get("like_count") or 0, "comments": m.get("comments_count") or 0}


def own_posts(limit: int = 30) -> list[dict]:
    me = _get(env("IG_USER_ID"), {"fields": "username"}).get("username", "us")
    rows = [_post_row(m, me) for m in _get(f"{env('IG_USER_ID')}/media", {"fields": MEDIA_FIELDS, "limit": limit}).get("data", [])]
    for p in rows:  # views where Instagram gives them; a post without insights keeps its likes and comments
        try:
            ins = _get(f"{p['id']}/insights", {"metric": "views,reach,saved,shares"}).get("data", [])
            p.update({x["name"]: (x.get("values") or [{}])[0].get("value", x.get("total_value", {}).get("value")) for x in ins})
        except InstagramError:
            pass
    return rows


def competitor_posts(username: str, limit: int = 25) -> dict:
    fields = f"business_discovery.username({username}){{username,name,biography,followers_count,media_count,profile_picture_url,media.limit({limit}){{{MEDIA_FIELDS}}}}}"
    bd = _get(env("IG_USER_ID"), {"fields": fields}).get("business_discovery", {})
    return {"username": bd.get("username", username), "followers": bd.get("followers_count"), "media_count": bd.get("media_count"),
            "avatar": bd.get("profile_picture_url"), "name": bd.get("name"), "bio": bd.get("biography"),
            "posts": [_post_row(m, bd.get("username", username)) for m in (bd.get("media") or {}).get("data", [])]}


def posts_between(username: str, since: str | None = None, until: str | None = None, pages: int = 8) -> dict:
    """An account's posts between two dates (YYYY-MM-DD, either may be empty), newest first, paging back 25 at a time
    through business discovery as far as Instagram allows (at most `pages` pages). Says how far back it got."""
    rows, after, acc = [], None, {}
    for _ in range(pages):
        media = f"media.after({after}).limit(25)" if after else "media.limit(25)"
        bd = _get(env("IG_USER_ID"), {"fields": f"business_discovery.username({username}){{username,followers_count,{media}{{{MEDIA_FIELDS}}}}}"}).get("business_discovery", {})
        acc = acc or {"username": bd.get("username", username), "followers": bd.get("followers_count")}
        got = [_post_row(m, acc["username"]) for m in (bd.get("media") or {}).get("data", [])]
        rows += got
        after = ((bd.get("media") or {}).get("paging") or {}).get("cursors", {}).get("after")
        if not got or not after or (since and min((r["at"] or "")[:10] for r in got) < since):
            break
    keep = [r for r in rows if (not since or (r["at"] or "")[:10] >= since) and (not until or (r["at"] or "")[:10] <= until)]
    oldest = min(((r["at"] or "")[:10] for r in rows), default=None)
    return acc | {"posts": keep, "read": len(rows), "oldest": oldest}


def publish_reel(video_url: str, caption: str, *, wait: float = 120) -> str:
    box = _post(f"{env('IG_USER_ID')}/media", {"media_type": "REELS", "video_url": video_url, "caption": caption})["id"]
    t0 = time.monotonic()
    while time.monotonic() - t0 < wait:
        st = _get(box, {"fields": "status_code"}).get("status_code")
        if st == "FINISHED":
            return _post(f"{env('IG_USER_ID')}/media_publish", {"creation_id": box})["id"]
        if st == "ERROR":
            raise InstagramError("Instagram could not process the video")
        time.sleep(3)
    raise InstagramError("Instagram is still processing the video; try publishing again in a minute")


def reply_comment(comment_id: str, text: str) -> str:
    return _post(f"{comment_id}/replies", {"message": text})["id"]


def parse_comments(body: dict) -> list[dict]:
    """New comments from a webhook body: [{comment_id, username, user_id, text, media_id}]."""
    out = []
    if body.get("object") != "instagram":
        return out
    for entry in body.get("entry", []):
        for ch in entry.get("changes", []):
            if ch.get("field") != "comments":
                continue
            v = ch.get("value", {})
            frm = v.get("from") or {}
            if frm.get("id") and frm.get("id") == env("IG_USER_ID"):
                continue  # our own reply
            out.append({"comment_id": v.get("id"), "username": frm.get("username"), "user_id": frm.get("id"),
                        "text": v.get("text", ""), "media_id": (v.get("media") or {}).get("id")})
    return out
