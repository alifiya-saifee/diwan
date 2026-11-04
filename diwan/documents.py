"""The documents a client sends (docs/deal-desk.md item 14). At conversion each party on our side (the buyer, the
seller, the tenant) gets one link for the documents the owner's settings list for them. Every upload is checked at once
and a bad one is never kept: the file must really be a JPEG, PNG or PDF of a sane size; a photo must be big, light and
sharp enough to read and not the same photo as another document; the details the client types (an Emirates ID's number
in the 784- format, an expiry date in the future, a unit that matches the deal) must be well formed. What passes waits
for the compliance officer, who compares the image with the typed details; only her confirmation puts them in the
client's file and archives the document with Records. Who the party is picks what they send: a company or a non-resident
gets a different list from a resident, and a mortgage adds the bank's letters. Until everything is in, the ladder runs on
the owner's hours: Rania nudges (under the same rules as every message to a client), the broker calls, the owner hears.
Reading the card itself needs a vision provider the owner approves for real IDs; until one is chosen the client types
the details and a person checks them.
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
         "title_deed": "Title deed", "trade_licence": "Trade licence", "proof_of_address": "Proof of address, last 3 months", "moa": "Memorandum and articles of association",
         "board_resolution": "Board resolution naming this unit and the signatory", "signatory_id": "Signatory's passport and Emirates ID",
         "ownership_declaration": "Ownership declaration, with IDs of 25% owners", "incorporation": "Certificate of incorporation", "good_standing": "Certificate of good standing",
         "registers": "Register of directors and shareholders", "poa": "Power of attorney", "attorney_id": "Attorney's passport and Emirates ID",
         "pre_approval": "Mortgage pre-approval", "liability_letter": "Bank liability letter", "bank_statement": "Bank statement", "salary_certificate": "Salary certificate",
         "relationship_proof": "Proof of how you are related to the payer", "other": "Other document"}
FIELDS = {"eid_front": [("number", "Emirates ID number"), ("name", "Name as on the card"), ("expiry", "Expiry date")],
          "passport": [("number", "Passport number"), ("expiry", "Expiry date")], "visa": [("expiry", "Expiry date")],
          "title_deed": [("number", "Title deed number"), ("unit", "Unit number")], "trade_licence": [("number", "Licence number"), ("expiry", "Expiry date")],
          "proof_of_address": [("dated", "Date on the document")], "good_standing": [("dated", "Date on the certificate")], "poa": [("expiry", "Expiry date")],
          "pre_approval": [("bank", "Bank"), ("expiry", "Valid until")], "liability_letter": [("bank", "Bank"), ("expiry", "Valid until")]}
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
        return [("tenant", d["customer"])] + ([("landlord", t["other_party"])] if t.get("other_party") else [])
    if p["id"] == "offplan":
        return [("buyer", d["customer"])]
    seller = t.get("other_party") or "the seller"
    return {"both": [("buyer", d["customer"]), ("seller", seller)], "seller": [("seller", seller)],
            "buyer": [("buyer", d["customer"])]}.get(t.get("sides"), [])


def kinds_for(g: Graph, deal: str, party: str) -> list[str]:
    """What this party sends: the owner's list for their side, changed by who they are and how the deal is paid."""
    rules, t = desk_rules.rules(g), desk_rules.terms(g, deal)
    base = list(rules["documents"].get(party) or [])
    who = t.get("other_party_type" if party in ("seller", "landlord") else "party_type")
    extra = rules["docs_by_party"].get(who) or []
    kinds = base + extra if who in (None, "resident", "poa") else extra + [k for k in base if k == "title_deed"]
    if party == "buyer" and t.get("finance") == "mortgage":
        kinds.append("pre_approval")
    if party == "seller" and t.get("seller_mortgage"):
        kinds.append("liability_letter")
    return list(dict.fromkeys(kinds))


def link(token: str) -> str:
    from diwan.config import env
    return f"{(env('PUBLIC_BASE_URL') or '').rstrip('/')}/web/docs.html?t={token}"


def _public() -> bool:
    from diwan.config import env
    return bool(env("PUBLIC_BASE_URL"))


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
            elif e["type"] == "docs.opened":
                r["opened"] = e["at"]
            elif e["type"] == "docs.renewed":
                r |= {k: c[k] for k in ("kinds", "expires", "name", "phone") if k in c}
    return list(out.values())


def missing(r: dict) -> list[str]:
    return [k for k in r["kinds"] if k not in r["got"]]


def request_all(office: Office, deal: str, by: str, *, today: date | None = None) -> list[str]:
    """One link per party on our side not asked yet."""
    g = office.graph()
    have = {r["party"] for r in requests(office.log.list(deal=deal), deal)}
    rules, t = desk_rules.rules(g), desk_rules.terms(g, deal)
    phone = next((c.props.get("phone") for c in g.of("chat") if c.deal == deal), None)
    made = []
    for party, who in parties(g, deal):
        kinds = kinds_for(g, deal, party)
        if party in have or not kinds:
            continue
        tok = secrets.token_urlsafe(18)
        ours = party not in ("seller", "landlord")
        office.log.append("docs.requested", actor=by, agent="deal", deal=deal, content={
            "token": tok, "party": party, "name": who, "kinds": kinds, "phone": phone if ours else t.get("other_phone"),
            "expires": ((today or date.today()) + timedelta(days=rules["sign_link_days"])).isoformat()})
        made.append(tok)
        if ours and phone and _public():  # the spec's first message: what is needed, and the link
            from diwan import client_msgs
            first = who.split()[0]
            client_msgs.tell(office, deal, f"Hi {first}, {len(kinds)} things to complete your file: {', '.join(KINDS[k].lower() for k in kinds)}. It takes a few minutes: {link(tok)}",
                             what=f"send them their documents link for {', '.join(KINDS[k].lower() for k in kinds)}")
    return made


def refresh(office: Office, deal: str, by: str) -> None:
    """The deal changed who is on it or how it is paid: each open link asks for what applies now, and keeps what already came."""
    from diwan import agency_forms
    g = office.graph()
    if not agency_forms.converted(g, deal):
        return
    t = desk_rules.terms(g, deal)
    for r in requests(office.log.list(deal=deal), deal):
        kinds = kinds_for(g, deal, r["party"])
        kinds = list(dict.fromkeys(kinds + [k for k in r["kinds"] if k in r["got"]]))
        change = {"kinds": kinds} if set(kinds) != set(r["kinds"]) else {}
        if r["party"] in ("seller", "landlord"):
            if t.get("other_party") and t["other_party"] != r["name"]:
                change["name"] = t["other_party"]
            if t.get("other_phone") and t["other_phone"] != r.get("phone"):
                change["phone"] = t["other_phone"]
        if change:
            office.log.append("docs.renewed", actor=by, agent="deal", deal=deal, content={"token": r["token"]} | change)
    request_all(office, deal, by)


def ask(office: Office, deal: str, kinds: list[str], by: str, *, today: date | None = None) -> str:
    """Compliance needs more: added to the client's own link, so they have one place to go."""
    if unknown := [k for k in kinds if k not in KINDS]:
        raise ValueError(f"Unknown documents: {', '.join(unknown)}.")
    g = office.graph()
    d = g.nodes[f"deal:{deal}"].props
    days = desk_rules.rules(g)["sign_link_days"]
    expires = ((today or date.today()) + timedelta(days=days)).isoformat()
    mine = next((r for r in requests(office.log.list(deal=deal), deal) if r["party"] not in ("seller", "landlord")), None)
    if mine:
        office.log.append("docs.renewed", actor=by, agent="deal", deal=deal, content={"token": mine["token"], "kinds": list(dict.fromkeys(mine["kinds"] + kinds)), "expires": max(expires, mine["expires"])})
        return mine["token"]
    tok = secrets.token_urlsafe(18)
    phone = next((c.props.get("phone") for c in g.of("chat") if c.deal == deal), None)
    party = "tenant" if desk_rules.path(g, deal)["id"] == "rent" else "buyer"
    office.log.append("docs.requested", actor=by, agent="deal", deal=deal, content={"token": tok, "party": party, "name": d["customer"], "kinds": kinds, "phone": phone, "expires": expires})
    return tok


def renew(office: Office, token: str, by: str, *, today: date) -> None:
    """A link that ran out gets more days."""
    from diwan.people import PEOPLE
    r = find(office, token)
    g = office.graph()
    d = g.nodes[f"deal:{r['deal']}"].props
    if by != d.get("broker") and by != roles.holder(g, "transactions") and by != roles.holder(g, "compliance") and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError(f"Only {name(d.get('broker'))}, the transactions officer, the compliance officer or the owner renews a link.")
    office.log.append("docs.renewed", actor=by, agent="deal", deal=r["deal"], content={"token": token, "expires": (today + timedelta(days=desk_rules.rules(g)["sign_link_days"])).isoformat()})


def expired(events: list[dict], deal: str, today: date) -> list[str]:
    """Confirmed documents that have since run out: a later step can't rest on them."""
    out = []
    for r in requests(events, deal):
        for k, c in r["confirmed"].items():
            if (c.get("fields") or {}).get("expiry", "9") < today.isoformat():
                out.append(f"{r['name']}'s {KINDS[k].lower()} expired on {c['fields']['expiry']}")
    return out


def find(office: Office, token: str) -> dict:
    r = next((x for x in requests(office.log.list()) if x["token"] == token), None)
    if not r:
        raise KeyError(token)
    return r


def page(office: Office, token: str, *, today: date) -> dict:
    """What the client sees: each document, received, to send again (with the reason) or still needed. Nothing else."""
    r = find(office, token)
    g = office.graph()
    office.log.append("docs.opened", actor=f"client:{r['party']}", deal=r["deal"], key=f"docs.opened:{token}", content={"token": token})
    agency = desk_rules.rules(g)["agency"]["name"] or "Diwan"
    from diwan import signing
    signer = {"tenant": "buyer"}.get(r["party"], r["party"])
    sign = []
    events = office.log.list(deal=r["deal"])
    for d in g.of("draft", r["deal"]):  # one place for the client: what they still have to sign is on the same page
        if d.status != "sent_back":
            for x in signing.links(events, d.id):
                if x["signer"] == signer and not x["signed"] and signing.status(g, x, today) == "open":
                    sign.append({"title": d.props["kind"].split(":")[0], "url": f"/web/sign.html?t={x['token']}"})
    docs = [{"kind": k, "label": KINDS[k], "fields": [{"key": f, "label": lab} for f, lab in FIELDS.get(k, [])],
             "status": "received" if k in r["got"] else "again" if k in r["turned"] else "needed",
             "reason": r["turned"][k]["reason"] if k in r["turned"] and k not in r["got"] else None} for k in r["kinds"]]
    return {"agency": agency, "name": r["name"], "expired": r["expires"] < today.isoformat(), "expires": r["expires"], "docs": docs,
            "done": not missing(r), "sign": sign}


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


def unit_of(g: Graph, deal: str) -> str | None:
    """The deal's unit number: from its terms, else the number in the property's name."""
    t = desk_rules.terms(g, deal)
    if t.get("unit"):
        return str(t["unit"]).strip()
    m = re.search(r"\b(\d{3,4})\b", g.nodes[f"deal:{deal}"].props.get("property") or "")
    return m.group(1) if m else None


def _field_checks(kind: str, fields: dict, today: date, warn_days: int = 30, standing_days: int = 180) -> tuple[str | None, dict, list[str]]:
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
        if exp < today + timedelta(days=warn_days):
            flags.append(f"it expires soon ({exp.isoformat()})")
    if "dated" in clean:
        try:
            on = date.fromisoformat(clean["dated"])
        except ValueError:
            return "Give the date as on the document.", {}, []
        limit = 92 if kind == "proof_of_address" else standing_days
        if on > today:
            return "That date is still to come. Give the date on the document.", {}, []
        if (today - on).days > limit:
            return f"This is from {on.strftime('%B')}; please send one from the last {'3 months' if limit == 92 else f'{limit} days'}.", {}, []
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
        rules = desk_rules.rules(g)
        why, clean, flags = _field_checks(kind, fields, today, rules["doc_expiry_warn_days"], rules["good_standing_days"])
    if not why and kind == "title_deed" and (have := unit_of(g, r["deal"])) and re.sub(r"\W", "", clean["unit"]).lower() != re.sub(r"\W", "", have).lower():
        why = f"The unit on this deed ({clean['unit']}) doesn't match the one we have ({have}). Is this the right deed?"
    if not why and kind == "eid_front" and not r["name"].startswith("the "):
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
    left = [KINDS[k] for k in missing(find(office, token))]
    if r["party"] not in ("seller", "landlord"):
        from diwan import client_msgs
        client_msgs.tell(office, r["deal"], f"Received your {KINDS[kind].lower()}, thank you. " + (f"Still needed: {', '.join(x.lower() for x in left)}." if left else "That's everything from you for now."),
                         what=f"confirm their {KINDS[kind].lower()} arrived")
    return {"received": kind, "left": left}


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


# ---------- the ladder: Rania nudges, the broker calls, the owner hears ----------

def _task(office: Office, g: Graph, r: dict, who: str | None, text: str, step: str) -> None:
    if not any(t.props.get("step") == "docs_call" and t.props.get("token") == r["token"] and t.props.get("ladder") == step for t in g.of("task", r["deal"])):
        office.add_task(r["deal"], "ops", text, needs_person=who, props={"step": "docs_call", "token": r["token"], "ladder": step})


def sweep(office: Office, now: datetime) -> int:
    """Run every minute by the office loop. Each rung goes once, counted from the last thing to arrive. Returns how many went."""
    from diwan import client_msgs
    from diwan.people import PEOPLE
    g = office.graph()
    rules = desk_rules.rules(g)
    nudge, call, brief = rules["docs_ladder_hours"]
    owner = next((p for p, v in PEOPLE.items() if v.get("role") == "Owner"), None)
    sent = 0
    for r in requests(office.log.list()):
        left = missing(r)
        if not left or r["expires"] < now.date().isoformat() or f"deal:{r['deal']}" not in g.nodes:
            continue
        since = max([r["at"]] + [v["at"] for v in r["got"].values()])
        recent = [x for x in r["reminders"] if x["at"] > since]
        age = (now - datetime.fromisoformat(since)).total_seconds() / 3600
        rung = 3 if age >= brief else 2 if age >= call else 1 if age >= nudge else 0
        if rung <= len(recent):
            continue
        n = len(recent) + 1
        d = g.nodes[f"deal:{r['deal']}"].props
        what = ", ".join(KINDS[k].lower() for k in left)
        ours = r["party"] not in ("seller", "landlord")
        if n == 1 and ours and r.get("phone") and _public():
            first = r["name"].split()[0]
            client_msgs.tell(office, r["deal"], f"Hi {first}, {len(r['kinds']) - len(left)} of {len(r['kinds'])} documents are in for your file with {d['property']}. Still needed: {what}. You can send them here: {link(r['token'])}",
                             what=f"remind them to send: {what}", now=now)
            via = "whatsapp"
        elif n == 3:
            _task(office, g, r, owner, f"{r['name']} still hasn't sent {what}, {brief} hours on: {name(d['broker'])} has been asked to call", "owner")
            via = "owner"
        else:
            why = "" if n == 2 else " (no WhatsApp on file)" if not r.get("phone") or not ours else " (Diwan has no public address for the link yet)"
            _task(office, g, r, d["broker"], f"Call {r['name']}{why}: still missing {what}", "broker")
            via = "broker"
        office.log.append("docs.reminded", actor="rania", agent="rania", deal=r["deal"], content={"token": r["token"], "n": n, "via": via})
        sent += 1
    return sent + expiry_sweep(office, now.date())


def expiry_sweep(office: Office, today: date) -> int:
    """A confirmed document about to run out goes to the broker once, the owner's number of days ahead."""
    g = office.graph()
    warn = desk_rules.rules(g)["doc_expiry_warn_days"]
    n = 0
    for r in requests(office.log.list()):
        if f"deal:{r['deal']}" not in g.nodes or g.nodes[f"deal:{r['deal']}"].props.get("stage") in ("Won", "Lost"):
            continue
        for k, c in r["confirmed"].items():
            exp = (c.get("fields") or {}).get("expiry")
            if exp and today.isoformat() <= exp <= (today + timedelta(days=warn)).isoformat():
                if not any(t.props.get("step") == "docs_call" and t.props.get("ladder") == f"expiry:{r['token']}:{k}" for t in g.of("task", r["deal"])):
                    office.add_task(r["deal"], "ops", f"{r['name']}'s {KINDS[k].lower()} expires on {exp}: ask for a new one", needs_person=g.nodes[f"deal:{r['deal']}"].props["broker"],
                                    props={"step": "docs_call", "token": r["token"], "ladder": f"expiry:{r['token']}:{k}"})
                    n += 1
    return n


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
