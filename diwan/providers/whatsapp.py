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


def available() -> bool:
    return bool(env("WHATSAPP_TOKEN") and env("WHATSAPP_PHONE_ID"))


def missing() -> list[str]:
    return [k for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_VERIFY_TOKEN") if not env(k)]


def verify(params: dict) -> str | None:
    """The challenge to echo back, or None when the verify token does not match."""
    if params.get("hub.mode") == "subscribe" and env("WHATSAPP_VERIFY_TOKEN") and params.get("hub.verify_token") == env("WHATSAPP_VERIFY_TOKEN"):
        return params.get("hub.challenge")
    return None


def signed(body: bytes, header: str | None) -> bool:
    secret = env("WHATSAPP_APP_SECRET")
    if not secret:
        return True
    want = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return bool(header) and hmac.compare_digest(want, header)


def parse(payload: dict) -> list[dict]:
    """Incoming text messages: [{phone, name, text, id}]. Statuses and non-text messages are skipped."""
    out = []
    for entry in payload.get("entry", []):
        for ch in entry.get("changes", []):
            v = ch.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name") for c in v.get("contacts", [])}
            for m in v.get("messages", []):
                if m.get("type") == "text":
                    out.append({"phone": m["from"], "name": names.get(m["from"]), "text": m["text"]["body"], "id": m.get("id")})
    return out


def send_image(to: str, url: str, caption: str, transport: httpx.BaseTransport | None = None) -> dict:
    """A photo with a caption. `url` must be an https address WhatsApp can fetch."""
    with httpx.Client(transport=transport, timeout=20) as c:
        r = c.post(f"{GRAPH}/{env('WHATSAPP_PHONE_ID')}/messages", headers={"Authorization": f"Bearer {env('WHATSAPP_TOKEN')}"},
                   json={"messaging_product": "whatsapp", "to": to, "type": "image", "image": {"link": url, "caption": caption[:1024]}})
    if r.status_code >= 300:
        raise RuntimeError(f"WhatsApp send failed ({r.status_code}): {r.text[:200]}")
    return r.json()


def send(to: str, text: str, transport: httpx.BaseTransport | None = None) -> dict:
    with httpx.Client(transport=transport, timeout=20) as c:
        r = c.post(f"{GRAPH}/{env('WHATSAPP_PHONE_ID')}/messages", headers={"Authorization": f"Bearer {env('WHATSAPP_TOKEN')}"},
                   json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": text}})
    if r.status_code >= 300:
        raise RuntimeError(f"WhatsApp send failed ({r.status_code}): {r.text[:200]}")
    return r.json()
