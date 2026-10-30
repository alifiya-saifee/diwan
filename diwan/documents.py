"""The documents a client sends (docs/deal-desk.md item 14). At conversion each party on our side (the buyer, the
seller, the tenant) gets one link for the documents the owner's settings list for them. Every upload is checked at once
and a bad one is never kept: the file must really be a JPEG, PNG or PDF of a sane size; a photo must be big, light and
sharp enough to read and not the same photo as another document; the details the client types (an Emirates ID's number
in the 784- format, an expiry date in the future) must be well formed. What passes waits for the compliance officer,
who compares the image with the typed details; only her confirmation puts them in the client's file and archives the
document with Records. Until everything is in, Rania reminds the client every few days in the daytime, and after the
owner's number of reminders the broker is asked to call. Reading the card itself needs a vision provider the owner
approves for real IDs; until one is chosen the client types the details and a person checks them.
"""
from __future__ import annotations

import hashlib
import io
import re
import secrets
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from diwan import desk_rules, roles
from diwan.graph import OPEN, Graph
from diwan.people import name

if TYPE_CHECKING:
    from diwan.office import Office

KINDS = {"eid_front": "Emirates ID, front", "eid_back": "Emirates ID, back", "passport": "Passport photo page", "visa": "Residence visa",
         "title_deed": "Title deed", "trade_licence": "Trade licence"}
FIELDS = {"eid_front": [("number", "Emirates ID number"), ("name", "Name as on the card"), ("expiry", "Expiry date")],
          "passport": [("number", "Passport number"), ("expiry", "Expiry date")], "visa": [("expiry", "Expiry date")],
          "title_deed": [("number", "Title deed number")], "trade_licence": [("number", "Licence number"), ("expiry", "Expiry date")]}
MAX_BYTES = 8_000_000
EID = re.compile(r"^784-?\d{4}-?\d{7}-?\d$")


def _luhn(digits: str) -> bool:
    s = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if i % 2 else 1)
        s += n - 9 if n > 9 else n
    return s % 10 == 0


def parties(g: Graph, deal: str) -> list[tuple[str, str]]:
    """(party, name) on our side of the deal: who we collect documents from."""
    p, t, d = desk_rules.path(g, deal), desk_rules.terms(g, deal), g.nodes[f"deal:{deal}"].props
    if p["id"] == "rent":
        return [("tenant", d["customer"])]
    if p["id"] == "offplan":
        return [("buyer", d["customer"])]
    return {"both": [("buyer", d["customer"]), ("seller", "the seller")], "seller": [("seller", "the seller")],
            "buyer": [("buyer", d["customer"])]}.get(t.get("sides"), [])


def requests(events: list[dict], deal: str | None = None) -> list[dict]:
    """Every documents link with what came in, what was turned away, what was confirmed and the reminders sent."""
    out: dict[str, dict] = {}
    for e in events:
        c = e["content"]
        if deal and e.get("deal") != deal:
            continue
        if e["type"] == "docs.requested":
            out[c["token"]] = dict(c, at=e["at"], deal=e["deal"], got={}, turned={}, confirmed={}, reminders=[])
        elif c.get("token") in out:
            r = out[c["token"]]
            if e["type"] == "docs.received":
                r["got"][c["kind"]] = c | {"at": e["at"]}
                r["turned"].pop(c["kind"], None)
                r["confirmed"].pop(c["kind"], None)
            elif e["type"] == "docs.rejected":
                r["turned"][c["kind"]] = c | {"at": e["at"]}
                if c.get("by_person"):
                    r["got"].pop(c["kind"], None)
            elif e["type"] == "docs.confirmed":
                r["confirmed"][c["kind"]] = c | {"at": e["at"], "by": e["actor"]}
            elif e["type"] == "docs.reminded":
                r["reminders"].append(c | {"at": e["at"]})
    return list(out.values())


def missing(r: dict) -> list[str]:
    return [k for k in r["kinds"] if k not in r["got"]]


def request_all(office: Office, deal: str, by: str, *, today: date | None = None) -> list[str]:
    """One link per party on our side not asked yet."""
    g = office.graph()
    have = {r["party"] for r in requests(office.log.list(deal=deal), deal)}
    rules = desk_rules.rules(g)
    phone = next((c.props.get("phone") for c in g.of("chat") if c.deal == deal), None)
    made = []
    for party, who in parties(g, deal):
        if party in have or not rules["documents"].get(party):
            continue
        tok = secrets.token_urlsafe(18)
        office.log.append("docs.requested", actor=by, deal=deal, content={
            "token": tok, "party": party, "name": who, "kinds": rules["documents"][party], "phone": phone if party != "seller" else None,
            "expires": ((today or date.today()) + timedelta(days=rules["sign_link_days"])).isoformat()})
        made.append(tok)
    return made


def find(office: Office, token: str) -> dict:
    r = next((x for x in requests(office.log.list()) if x["token"] == token), None)
    if not r:
        raise KeyError(token)
    return r


def page(office: Office, token: str, *, today: date) -> dict:
    """What the client sees: each document, received, to send again (with the reason) or still needed. Nothing else."""
    r = find(office, token)
    g = office.graph()
    agency = desk_rules.rules(g)["agency"]["name"] or "Diwan"
    docs = [{"kind": k, "label": KINDS[k], "fields": [{"key": f, "label": lab} for f, lab in FIELDS.get(k, [])],
             "status": "received" if k in r["got"] else "again" if k in r["turned"] else "needed",
             "reason": r["turned"][k]["reason"] if k in r["turned"] and k not in r["got"] else None} for k in r["kinds"]]
    return {"agency": agency, "name": r["name"], "expired": r["expires"] < today.isoformat(), "expires": r["expires"], "docs": docs,
            "done": not missing(r)}


# ---------- the checks at upload: a bad file is turned away and never kept ----------

def _image_checks(data: bytes) -> str | None:
    from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
    try:
        Image.open(io.BytesIO(data)).verify()
        im = Image.open(io.BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError, SyntaxError):
        return "That photo can't be read. Take it again."
    if min(im.size) < 380 or max(im.size) < 600:
        return "The photo is too small to read. Take it closer, filling the frame with the document."
    grey = im.convert("L")
    grey.thumbnail((1000, 1000))
    light = ImageStat.Stat(grey).mean[0]
    if light < 45:
        return "The photo is too dark. Take it again in good light."
    if light > 235:
        return "The photo is washed out. Take it again without the flash or glare."
    # sharpness: the variance of the Laplacian (a sharp photo of print scores in the hundreds, a blurred one under 100)
    if ImageStat.Stat(grey.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], 1, 128))).var[0] < 120:
        return "The photo is blurry. Hold the phone still and take it again."
    return None


def _field_checks(kind: str, fields: dict, today: date) -> tuple[str | None, dict, list[str]]:
    """(why it's turned away, the cleaned details, what the compliance officer should look at)."""
    clean, flags = {}, []
    for key, label in FIELDS.get(kind, []):
        v = str(fields.get(key) or "").strip()
        if not v:
            return f"Fill in the {label.lower()}.", {}, []
        clean[key] = v
    if kind == "eid_front":
        if not EID.match(clean["number"].replace(" ", "")):
            return "The Emirates ID number has 15 digits and starts with 784 (784-YYYY-NNNNNNN-N).", {}, []
        digits = re.sub(r"\D", "", clean["number"])
        clean["number"] = f"{digits[:3]}-{digits[3:7]}-{digits[7:14]}-{digits[14]}"
        if not _luhn(digits):
            flags.append("the ID number's check digit doesn't add up: compare it with the card")
    if "expiry" in clean:
        try:
            exp = date.fromisoformat(clean["expiry"])
        except ValueError:
            return "Give the expiry date as on the document.", {}, []
        if exp < today:
            return f"This {KINDS[kind].split(',')[0].lower()} expired on {exp.isoformat()}. Send a valid one.", {}, []
        if exp < today + timedelta(days=60):
            flags.append(f"it expires soon ({exp.isoformat()})")
    return None, clean, flags


def upload(office: Office, token: str, kind: str, data: bytes, fields: dict, *, media, today: date) -> dict:
    r = find(office, token)
    g = office.graph()
    if r["expires"] < today.isoformat():
        raise ValueError("This link has expired. Ask your broker for a new one.")
    if kind not in r["kinds"]:
        raise ValueError("That document isn't asked for on this link.")
    if kind in r["got"]:
        raise ValueError(f"Your {KINDS[kind].lower()} is already received.")
    is_pdf, is_img = data.startswith(b"%PDF"), data.startswith(b"\xff\xd8\xff") or data.startswith(b"\x89PNG\r\n\x1a\n")
    why = None
    if len(data) > MAX_BYTES:
        why = "The file is too large; keep it under 8 MB."
    elif not (is_pdf or is_img):
        why = "Send a photo (JPEG or PNG) or a PDF of the document."
    elif is_img:
        why = _image_checks(data)
    sha = hashlib.sha256(data).hexdigest()
    if not why and (same := next((k for k, v in r["got"].items() if v.get("sha") == sha), None)):
        why = f"This is the same file as your {KINDS[same].lower()}. Send the {KINDS[kind].lower()}."
    clean, flags = {}, []
    if not why:
        why, clean, flags = _field_checks(kind, fields, today)
    if not why and kind == "eid_front" and r["party"] != "seller":
        from diwan.agents.compliance import _same
        if not _same(clean["name"], r["name"]):
            flags.append(f"the name on the card ({clean['name']}) differs from the deal's ({r['name']})")
    if why:  # turned away: the reason is logged, the file is not kept
        office.log.append("docs.rejected", actor=f"client:{r['party']}", deal=r["deal"], content={"token": token, "kind": kind, "reason": why})
        raise ValueError(why)
    media.mkdir(parents=True, exist_ok=True)
    path = media / f"doc-{token}-{kind}{'.pdf' if is_pdf else '.jpg' if data.startswith(b'\xff\xd8') else '.png'}"
    path.write_bytes(data)
    office.log.append("docs.received", actor=f"client:{r['party']}", deal=r["deal"],
                      content={"token": token, "kind": kind, "file": path.name, "sha": sha, "fields": clean, "flags": flags})
    office.add_task(r["deal"], "ops", f"Check {r['name']}'s {KINDS[kind].lower()} against what they typed" + (f": {'; '.join(flags)}" if flags else ""),
                    needs_person=roles.holder(g, "compliance"), props={"step": "doc", "token": token, "kind": kind, "desk_role": "compliance"})
    return {"received": kind, "left": [KINDS[k] for k in missing(find(office, token))]}


# ---------- the compliance officer's check; then the client's file and the archive ----------

def confirm(office: Office, tid: str, by: str, ok: bool, note: str = "", *, today: date) -> str | None:
    g = office.graph()
    roles.check(g, "compliance", by)
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("step") != "doc":
        raise KeyError(tid)
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    r = find(office, t.props["token"])
    kind = t.props["kind"]
    got = r["got"].get(kind)
    if not got:
        raise ValueError("That document is no longer on file.")
    if not ok and not note.strip():
        raise ValueError("Say what the client should fix; they see it on their link.")
    office.log.append("task.done", actor=by, agent="ops", deal=t.deal, content={"id": tid, "reason": "Confirmed" if ok else f"Sent back: {note.strip()}",
                                                                              "result": "confirmed" if ok else "rejected"})
    if not ok:
        office.log.append("docs.rejected", actor=by, deal=t.deal, content={"token": r["token"], "kind": kind, "reason": note.strip(), "by_person": True})
        return None
    office.log.append("docs.confirmed", actor=by, deal=t.deal, content={"token": r["token"], "kind": kind, "party": r["party"], "name": r["name"],
                                                                       "fields": got["fields"]})
    return office.file_document(kind=KINDS[kind], title=f"{KINDS[kind]} of {r['name']} ({r['party']})", date=today.isoformat(), by=by, deal=t.deal,
                                party=r["name"], text=f"/media/{got['file']}")


def profile(events: list[dict], deal: str) -> dict:
    """The client's file: confirmed details by party, as the compliance officer confirmed them."""
    out: dict[str, dict] = {}
    for r in requests(events, deal):
        p = out.setdefault(r["party"], {"name": r["name"], "details": {}})
        for k, c in r["confirmed"].items():
            p["details"][KINDS[k]] = c["fields"] | {"confirmed_by": name(c["by"]), "file": f"/media/{r['got'][k]['file']}" if k in r["got"] else None}
    return out


# ---------- reminders: Rania every few days in the daytime, then the broker ----------

def sweep(office: Office, now: datetime) -> int:
    """Run every minute by the office loop. Returns how many reminders went out."""
    if not 9 <= now.hour < 20:
        return 0
    g = office.graph()
    rules = desk_rules.rules(g)
    every, most = rules["docs_reminder_days"], rules["docs_reminders"]
    sent = 0
    for r in requests(office.log.list()):
        left = missing(r)
        if not left or r["expires"] < now.date().isoformat() or f"deal:{r['deal']}" not in g.nodes:
            continue
        since = max([r["at"]] + [v["at"] for v in r["got"].values()])
        recent = [x for x in r["reminders"] if x["at"] > since]
        last = max([since] + [x["at"] for x in recent])
        if (now - datetime.fromisoformat(last)).total_seconds() < every * 86400:
            continue
        d = g.nodes[f"deal:{r['deal']}"].props
        if len(recent) >= most:
            if not any(t.props.get("step") == "docs_call" and t.props.get("token") == r["token"] and t.status in OPEN for t in g.of("task", r["deal"])):
                office.add_task(r["deal"], "ops", f"Call {r['name']}: {most} reminders and still missing {', '.join(KINDS[k].lower() for k in left)}",
                                needs_person=d["broker"], props={"step": "docs_call", "token": r["token"]})
            continue
        first = r["name"].split()[0] if not r["name"].startswith("the ") else "there"
        text = (f"Hi {first}, {len(r['kinds']) - len(left)} of {len(r['kinds'])} documents are in for your file with {d['property']}. "
                f"Still needed: {', '.join(KINDS[k].lower() for k in left)}. You can send them here: {{link}}")
        from diwan.config import env
        base = (env("PUBLIC_BASE_URL") or "").rstrip("/")
        if r.get("phone") and base:  # Rania can only send a link the client can open
            from diwan.agents import reception
            reception._send(office, r["phone"], r["deal"], text.replace("{link}", f"{base}/web/docs.html?t={r['token']}"), refs=[])
            office.log.append("docs.reminded", actor="rania", agent="rania", deal=r["deal"], content={"token": r["token"], "n": len(recent) + 1, "via": "whatsapp"})
        else:
            if not any(t.props.get("step") == "docs_call" and t.props.get("token") == r["token"] and t.status in OPEN for t in g.of("task", r["deal"])):
                why = "no WhatsApp on file" if not r.get("phone") else "Diwan has no public address for the link yet"
                office.add_task(r["deal"], "ops", f"Remind {r['name']} to send their documents ({why}): still missing {', '.join(KINDS[k].lower() for k in left)}",
                                needs_person=d["broker"], props={"step": "docs_call", "token": r["token"]})
            office.log.append("docs.reminded", actor="rania", agent="rania", deal=r["deal"], content={"token": r["token"], "n": len(recent) + 1, "via": "broker"})
        sent += 1
    return sent


def call_done(office: Office, tid: str, by: str, note: str) -> None:
    """The broker reached the client about their documents."""
    from diwan.people import PEOPLE
    g = office.graph()
    t = g.nodes.get(tid)
    if not t or t.type != "task" or t.props.get("step") != "docs_call":
        raise KeyError(tid)
    if by != t.props.get("needs_person") and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError(f"This is {name(t.props.get('needs_person'))}'s to do.")
    if t.status not in OPEN:
        raise ValueError(f"{tid} is {t.status}.")
    if not note.strip():
        raise ValueError("Say what the client said.")
    office.log.append("task.done", actor=by, agent="ops", deal=t.deal, content={"id": tid, "reason": note.strip(), "result": "done"})
