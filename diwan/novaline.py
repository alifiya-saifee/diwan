"""Nova's own number, a third line carrying only the owner and Nova. The owner can't message their own WhatsApp, and using the sales line would
join the pathways, so this is how she reaches them when they aren't in the app, and how they answer or give her orders from the road.

Off until NOVA_WHATSAPP_TOKEN and NOVA_WHATSAPP_PHONE_ID are set: alerts then stay in the app and on Live calls. Only the owner's own
number is listened to here. WhatsApp allows free text for 24 hours after the owner last wrote; after that, the approved template in
NOVA_ALERT_TEMPLATE, with one variable, carries the alert.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from diwan import leads, ownerline
from diwan.config import env, sandbox_only
from diwan.office import Office
from diwan.providers import whatsapp

SESSION = "whatsapp-owner"
AWAY = timedelta(minutes=3)  # the app asks every minute: this long with no call means they aren't in it
SEEN: dict[str, datetime] = {}
FROM: dict[str, datetime] = {}  # when the owner last wrote here, which is what opens WhatsApp's 24 hours
BUTTONS = ["Send", "Change", "Leave it"]


def line_id() -> str | None:
    return env("NOVA_WHATSAPP_PHONE_ID")


def connected() -> bool:
    i = line_id()
    return bool(env("NOVA_WHATSAPP_TOKEN") and i and i not in (env("WHATSAPP_PHONE_ID"), env("PERSONAL_WHATSAPP_PHONE_ID")))


def is_nova(line: str | None) -> bool:
    return bool(line) and connected() and line == line_id()


def owner_phone(office: Office) -> str | None:
    from diwan.agents.triage import owner_id
    return ownerline._digits(env("OWNER_WHATSAPP_NUMBER") or "") or leads.setting(office.graph(), owner_id(), "phone")


def seen(now: datetime) -> None:
    SEEN["owner"] = now


def away(now: datetime) -> bool:
    return "owner" not in SEEN or now - SEEN["owner"] >= AWAY


def _send(to: str, text: str, buttons: bool, transport=None) -> dict:
    token, pid = env("NOVA_WHATSAPP_TOKEN"), line_id()
    if buttons:
        return whatsapp.send_buttons(to, text, BUTTONS, transport, phone_id=pid, token=token)
    return whatsapp.send(to, text, transport, phone_id=pid, token=token)


def push(office: Office, text: str, level: str, now: datetime, transport=None) -> bool:
    """Only when they're away from the app. Round-ups wait for them to come back."""
    phone = owner_phone(office)
    if not (connected() and phone and level != "roundup" and away(now)) or sandbox_only():
        return False
    try:
        if "owner" in FROM and now - FROM["owner"] < timedelta(hours=23):
            _send(phone, text, text.rstrip().endswith("?"), transport)
        elif env("NOVA_ALERT_TEMPLATE"):
            whatsapp.send_template(phone, env("NOVA_ALERT_TEMPLATE"), [text[:900]], "en", transport, phone_id=line_id(), token=env("NOVA_WHATSAPP_TOKEN"))
        else:
            return False
    except Exception:  # noqa: BLE001  it's still waiting for them in the app
        return False
    return True


def receive(office: Office, m: dict, now: datetime, transport=None) -> dict | None:
    """The owner talking to Nova from their phone. Anyone else on this number is ignored: orders come from one number only."""
    from diwan.agents import frontdesk
    from diwan.agents.triage import owner_id
    phone = owner_phone(office)
    if m.get("echo") or not phone or ownerline._digits(m["phone"]) != phone:
        return None
    FROM["owner"] = now
    said = {"send": "yes", "leave it": "leave it", "change": "What should I tell them instead?"}.get(m["text"].strip().lower(), m["text"])
    if said.endswith("instead?"):
        reply = {"kind": "question", "text": said}
    else:
        reply = frontdesk.say(office, said, owner_id(), session=SESSION, now=now)
    text = reply.get("text") or ""
    if text and connected() and not sandbox_only():
        try:
            _send(phone, text[:4000], False, transport)
        except Exception:  # noqa: BLE001  noted by the send failing, and they can ask again
            pass
    return reply
