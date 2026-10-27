"""AiSensy, the WhatsApp Business partner many UAE and Indian businesses already use.

Project API (session messages inside the 24-hour window, approved templates, template list):
  POST https://apis.aisensy.com/project-apis/v1/project/{project_id}/messages   header X-AiSensy-Project-API-Pwd
  GET  https://apis.aisensy.com/project-apis/v1/project/{project_id}/wa_template/
Webhook: AiSensy POSTs {topic: "message.created", data: {message: {phone_number, message_content, sender, message_type,
messageId}, contact: {name}}}. AiSensy does not sign webhooks, so the URL carries a secret token we check.
Phone numbers go out as digits only, UAE local numbers widened to 971.
"""
from __future__ import annotations

import hmac
import re

import httpx

from diwan.config import env

BASE = "https://apis.aisensy.com/project-apis/v1/project"
INCOMING = {"USER", "CONTACT", "CUSTOMER", "INCOMING", "IN", ""}


class AiSensyError(RuntimeError):
    pass


def missing() -> list[str]:
    return [k for k in ("AISENSY_PROJECT_ID", "AISENSY_PROJECT_API_PWD") if not env(k)]


def available() -> bool:
    return not missing()


def digits(phone: str) -> str:
    p = re.sub(r"\D", "", phone)
    if p.startswith("00"):
        p = p[2:]
    if p.startswith("0") and len(p) == 10:
        p = "971" + p[1:]
    if len(p) == 9:
        p = "971" + p
    return p


def _post(body: dict, transport=None) -> dict:
    if not available():
        raise AiSensyError("AiSensy is not connected: " + ", ".join(missing()))
    with httpx.Client(transport=transport, timeout=20) as c:
        r = c.post(f"{BASE}/{env('AISENSY_PROJECT_ID')}/messages", json=body,
                   headers={"X-AiSensy-Project-API-Pwd": env("AISENSY_PROJECT_API_PWD"), "Content-Type": "application/json"})
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 300 or data.get("error"):
        raise AiSensyError(f"AiSensy refused the message ({r.status_code}): {str(data.get('message') or data.get('error') or r.text)[:200]}")
    return {"id": (data.get("messages") or [{}])[0].get("id") or data.get("messageId") or data.get("id")}


def send_text(to: str, text: str, transport=None) -> dict:
    """A free-text message. WhatsApp allows it only within 24 hours of the customer's last message."""
    return _post({"to": digits(to), "type": "text", "text": {"body": text}}, transport)


def send_template(to: str, name: str, params: list[str] | None = None, lang: str = "en", transport=None) -> dict:
    """An approved template, the only way to start or reopen a conversation after 24 hours."""
    comps = [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}] if params else []
    return _post({"to": digits(to), "type": "template", "template": {"name": name, "language": {"code": lang}, "components": comps}}, transport)


def templates(transport=None) -> list[dict]:
    if not available():
        raise AiSensyError("AiSensy is not connected: " + ", ".join(missing()))
    with httpx.Client(transport=transport, timeout=20) as c:
        r = c.get(f"{BASE}/{env('AISENSY_PROJECT_ID')}/wa_template/", params={"limit": 100},
                  headers={"X-AiSensy-Project-API-Pwd": env("AISENSY_PROJECT_API_PWD")})
    if r.status_code >= 300:
        raise AiSensyError(f"AiSensy templates ({r.status_code}): {r.text[:200]}")
    data = r.json()
    rows = data if isinstance(data, list) else data.get("data") or data.get("templates") or data.get("results") or []
    out = []
    for t in rows:
        body = t.get("body") or t.get("text") or ""
        if not body:
            body = next((c.get("text", "") for c in t.get("components", []) if c.get("type", "").upper() == "BODY"), "")
        out.append({"name": t.get("name") or t.get("template_name"), "status": str(t.get("status") or "").upper(),
                    "language": (t.get("language") or "en") if isinstance(t.get("language"), str) else "en",
                    "category": t.get("category"), "body": body, "params": len(re.findall(r"\{\{\d+\}\}", body))})
    return [t for t in out if t["name"]]


def token_ok(token: str | None) -> bool:
    want = env("AISENSY_WEBHOOK_TOKEN")
    return bool(want) and bool(token) and hmac.compare_digest(want, token)


def parse(body: dict) -> list[dict]:
    """Incoming customer messages from a webhook body: [{phone, name, text, id}]. Our own echoes are skipped."""
    topic = body.get("topic") or body.get("type") or ""
    if topic != "message.created":
        return []
    data = body.get("data") or body.get("payload") or {}
    m = data.get("message") or data
    sender = str(m.get("sender") or m.get("senderType") or m.get("direction") or "").upper()
    if sender not in INCOMING or not m.get("phone_number"):
        return []
    content = m.get("message_content") or {}
    kind = str(m.get("message_type") or "TEXT").upper()
    text = content.get("text") or content.get("body") or {"IMAGE": "📷 Image", "DOCUMENT": "📄 Document", "AUDIO": "🎵 Voice note",
                                                         "VIDEO": "🎥 Video", "LOCATION": "📍 Location"}.get(kind, "")
    if content.get("caption"):
        text = content["caption"]
    return [{"phone": digits(m["phone_number"]), "name": (data.get("contact") or {}).get("name") or m.get("contact_name"),
             "text": text, "id": m.get("messageId") or m.get("id") or m.get("_id"), "kind": kind.lower()}]
