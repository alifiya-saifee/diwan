"""Who is writing on the owner's own WhatsApp, and what Nova may do about it. What the owner has said wins, then a staff number, then a
client on the sales records. A number nobody has placed stays unknown: a message claiming to be someone never changes who it is.
"""
from __future__ import annotations

import re

from diwan import leads, ownerline
from diwan.config import env
from diwan.office import Office
from diwan.people import PEOPLE, name

CIRCLES = ("family", "friend", "important", "client", "staff", "vendor", "unknown", "muted")
RELATIONS = {"mum": "family", "mom": "family", "mother": "family", "dad": "family", "father": "family", "wife": "family", "husband": "family", "son": "family", "daughter": "family",
             "brother": "family", "sister": "family", "aunt": "family", "uncle": "family", "cousin": "family", "friend": "friend", "client": "client", "vendor": "vendor",
             "supplier": "vendor", "developer": "vendor", "agent": "vendor", "partner": "important", "banker": "important", "lawyer": "important", "accountant": "important"}


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _said(phone: str) -> dict | None:
    with ownerline.db() as c:
        r = c.execute("select * from contacts where phone=?", (_digits(phone),)).fetchone()
    return dict(r) if r else None


def person_by_phone(office: Office, phone: str) -> str | None:
    """The owner or a member of staff, by the number on their settings."""
    g, p = office.graph(), _digits(phone)
    if p and p == _digits(env("OWNER_WHATSAPP_NUMBER") or ""):  # set once when their number is linked
        return next(k for k, v in PEOPLE.items() if v.get("role") == "Owner")
    return next((k for k in PEOPLE if p and leads.setting(g, k, "phone") == p), None)


def who(office: Office, phone: str, profile: str | None = None) -> dict:
    """The sender's name and circle, and where that came from."""
    phone = _digits(phone)
    if (r := _said(phone)) and r["circle"]:
        return r | {"source": "owner"}
    if k := person_by_phone(office, phone):
        return {"phone": phone, "name": name(k), "circle": "staff", "person": k, "quiet": 0, "source": "staff"}
    g = office.graph()
    if (ch := g.nodes.get(f"chat:{phone}")) and not ch.props.get("merged_into"):
        return {"phone": phone, "name": ch.label, "circle": "client", "deal": ch.deal, "quiet": 0, "source": "sales"}
    return {"phone": phone, "name": (r or {}).get("name") or profile or f"+{phone}", "circle": "unknown", "quiet": 0, "source": "none"}


def place(phone: str, *, name_: str | None = None, circle: str | None = None, note: str | None = None, quiet: bool | None = None) -> dict:
    """The owner said so."""
    if circle and circle not in CIRCLES:
        raise ValueError(f"A circle: {', '.join(CIRCLES)}")
    phone = _digits(phone)
    was = _said(phone) or {}
    row = (phone, name_ or was.get("name"), circle or was.get("circle"), note or was.get("note"), int(was.get("quiet") or 0) if quiet is None else int(quiet))
    with ownerline.db() as c:
        c.execute("insert or replace into contacts (phone, name, circle, note, quiet) values (?,?,?,?,?)", row)
    return _said(phone)


def everyone() -> list[dict]:
    with ownerline.db() as c:
        return [dict(r) for r in c.execute("select * from contacts order by name")]


def named(office: Office, words: str) -> list[dict]:
    """Everyone on this line the owner could mean. "my mum" finds whoever is noted as mum."""
    low = re.sub(r"^(?:my|the)\s+", "", words.strip().lower())
    seen: dict[str, dict] = {}
    for r in everyone():
        if low == str(r.get("note") or "").lower() or low in re.findall(r"[a-z]+", str(r.get("name") or "").lower()) or low == str(r.get("name") or "").lower():
            seen[r["phone"]] = who(office, r["phone"])
    for m in ownerline.chats():
        c = who(office, m["chat"], m["name"])
        if m["chat"] not in seen and (low == str(c["name"]).lower() or low in re.findall(r"[a-z]+", str(c["name"]).lower())):
            seen[m["chat"]] = c
    return list(seen.values())
