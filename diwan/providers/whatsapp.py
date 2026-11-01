"""WhatsApp Cloud API (Meta). Off until WHATSAPP_TOKEN and WHATSAPP_PHONE_ID are set; until then chats run in the
sandbox phone on the Inbox screen and nothing leaves the machine.

Webhook: Meta calls GET with hub.mode/hub.verify_token/hub.challenge once to verify, then POSTs message events.
When WHATSAPP_APP_SECRET is set, every POST must carry a matching X-Hub-Signature-256.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx

from diwan.config import env

GRAPH = "https://graph.facebook.com/v21.0"
LABELS = {"image": "📷 Image", "document": "📄 Document", "audio": "🎵 Voice note", "video": "🎥 Video", "sticker": "💬 Sticker", "contacts": "👤 Contact card"}


def available() -> bool:
    return bool(env("WHATSAPP_TOKEN") and env("WHATSAPP_PHONE_ID"))


def missing() -> list[str]:
    return [k for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_VERIFY_TOKEN") if not env(k)]


def verify(params: dict) -> str | None:
    """The challenge to echo back, or None when the verify token does not match."""
    if params.get("hub.mode") == "subscribe" and env("WHATSAPP_VERIFY_TOKEN") and params.get("hub.verify_token") == env("WHATSAPP_VERIFY_TOKEN"):
        return params.get("hub.challenge")
    return None


def signed(body: bytes, header: str | None, secret: str | None = None) -> bool:
    secret = secret or env("WHATSAPP_APP_SECRET")
    if not secret:
        return not available()  # a live line always checks
    want = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return bool(header) and hmac.compare_digest(want, header)


def _content(m: dict) -> tuple[str, str | None]:
    """A message's words, and its media id. What has no words gets a label, the same as AiSensy's."""
    kind = m.get("type")
    if kind == "text":
        return m["text"]["body"], None
    if kind == "button":
        return m["button"].get("text", ""), None
    if kind == "interactive":
        i = m["interactive"]
        return (i.get("button_reply") or i.get("list_reply") or {}).get("title", ""), None
    if kind == "location":
        p = m["location"]
        return " ".join(str(x) for x in ("📍 Location", p.get("name"), p.get("address")) if x), None
    if kind in LABELS:
        part = m.get(kind) or {}
        return part.get("caption") or LABELS[kind], part.get("id")
    return "", None


def parse(payload: dict) -> list[dict]:
    """What arrived: [{phone, name, text, id, kind, media, line, echo, forwarded}]. `line` is which of our numbers it reached, `phone` the other
    person. `echo` marks what the owner typed in the WhatsApp Business app on a linked number. Statuses, reactions and groups are skipped."""
    out = []
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            v = ch.get("value", {})
            line = (v.get("metadata") or {}).get("phone_number_id")
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in v.get("contacts", [])}
            for m in v.get("messages", []):
                text, media = _content(m)
                if text and not m.get("group_id"):
                    out.append({"phone": m["from"], "name": names.get(m["from"]), "text": text, "id": m.get("id"), "kind": m.get("type"), "media": media, "line": line,
                                "echo": False, "forwarded": bool((m.get("context") or {}).get("forwarded"))})
            for m in v.get("message_echoes", []):
                text, media = _content(m)
                if text and not m.get("group_id"):
                    out.append({"phone": m["to"], "name": None, "text": text, "id": m.get("id"), "kind": m.get("type"), "media": media, "line": line, "echo": True, "forwarded": False})
    return out


def send_image(to: str, url: str, caption: str, transport: httpx.BaseTransport | None = None) -> dict:
    """A photo with a caption. `url` must be an https address WhatsApp can fetch."""
    with httpx.Client(transport=transport, timeout=20) as c:
        r = c.post(f"{GRAPH}/{env('WHATSAPP_PHONE_ID')}/messages", headers={"Authorization": f"Bearer {env('WHATSAPP_TOKEN')}"},
                   json={"messaging_product": "whatsapp", "to": to, "type": "image", "image": {"link": url, "caption": caption[:1024]}})
    if r.status_code >= 300:
        raise RuntimeError(f"WhatsApp send failed ({r.status_code}): {r.text[:200]}")
    return r.json()


def _post(body: dict, transport: httpx.BaseTransport | None, phone_id: str | None, token: str | None) -> dict:
    """The sales line unless a line's own id and token are given: each pathway sends only from its own number."""
    with httpx.Client(transport=transport, timeout=20) as c:
        r = c.post(f"{GRAPH}/{phone_id or env('WHATSAPP_PHONE_ID')}/messages", headers={"Authorization": f"Bearer {token or env('WHATSAPP_TOKEN')}"},
                   json={"messaging_product": "whatsapp"} | body)
    if r.status_code >= 300:
        raise RuntimeError(f"WhatsApp send failed ({r.status_code}): {r.text[:200]}")
    return r.json()


def send(to: str, text: str, transport: httpx.BaseTransport | None = None, *, phone_id: str | None = None, token: str | None = None) -> dict:
    return _post({"to": to, "type": "text", "text": {"body": text}}, transport, phone_id, token)


def send_template(to: str, name: str, params: list[str] | None = None, lang: str = "en", transport: httpx.BaseTransport | None = None, *, phone_id: str | None = None, token: str | None = None) -> dict:
    """An approved template, the only way to start or reopen a conversation after 24 hours."""
    comps = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}] if params else []
    return _post({"to": to, "type": "template", "template": {"name": name, "language": {"code": lang}, "components": comps}}, transport, phone_id, token)


def send_buttons(to: str, text: str, buttons: list[str], transport: httpx.BaseTransport | None = None, *, phone_id: str | None = None, token: str | None = None) -> dict:
    return _post({"to": to, "type": "interactive", "interactive": {"type": "button", "body": {"text": text[:1024]}, "action": {"buttons": [
        {"type": "reply", "reply": {"id": f"b{i}", "title": b[:20]}} for i, b in enumerate(buttons[:3])]}}}, transport, phone_id, token)
