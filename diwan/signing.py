"""Signing an agency form online (docs/deal-desk.md item 13). Each person who signs a form gets their own link: Form A
the seller and our broker, Form B the buyer and our broker, Form I our broker and the other agent. The broker shares
the links personally. The person opens it with no login, reads the form, gives their name and ID number, uploads an
image of their signature and agrees to sign electronically. A link works for one person on one version of the form,
for the owner's number of days; a form sent back (the price or terms changed) can't be signed. A signature is drawn on
screen or photographed; the check is a first filter on the picture, not a forgery test, and a person sees every signed
form. Form F binds the client, so its links wait for Compliance. When everyone has signed, the signatures and a signing record (who, when, from which device, and a fingerprint of what they signed) are
put on the PDF, which is filed with Records the same way as an uploaded signed copy.
"""
from __future__ import annotations

import hashlib
import io
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from diwan import agency_forms, desk_rules, roles
from diwan.agents import compliance
from diwan.graph import OPEN, Graph
from diwan.people import PEOPLE, name

if TYPE_CHECKING:
    from diwan.office import Office

SIGNERS = {"A": [("seller", "The seller"), ("broker", "The broker")], "B": [("buyer", "The buyer"), ("broker", "The broker")],
           "I": [("broker", "Our broker"), ("other", "The other broker")],
           "F": [("buyer", "The buyer"), ("seller", "The seller"), ("broker", "Our broker"), ("other", "The other broker")]}


def signers(g: Graph, deal: str, form: str) -> list[tuple[str, str]]:
    """Form F is signed by the other broker only when another agency is on the deal."""
    return [x for x in SIGNERS[form] if not (form == "F" and x[0] == "other" and not desk_rules.terms(g, deal).get("other_agency"))]
MAX_BYTES = 3_000_000


def _form(g: Graph, did: str):
    return g.nodes[did], agency_forms.form_of(g, did)


def _who(g: Graph, deal: str, form: str, signer: str) -> str:
    d, t = g.nodes[f"deal:{deal}"].props, desk_rules.terms(g, deal)
    return {"seller": "the seller", "buyer": d["customer"], "broker": name(d["broker"]),
            "other": t.get("other_agent") or t.get("other_agency") or "the other agent"}[signer]


def fingerprint(g: Graph, did: str) -> str:
    """What was signed: the form's lines as drafted, so any later change to them shows."""
    lines = [s.props["text"] for s in sorted(g.into(did, "part_of"), key=lambda s: s.props["n"])]
    return hashlib.sha256("\n".join([g.nodes[did].props["kind"], *lines]).encode()).hexdigest()


def links(events: list[dict], did: str) -> list[dict]:
    out, by_token = [], {}
    for e in events:
        c = e["content"]
        if e["type"] == "sign.link" and c.get("draft") == did:
            by_token[c["token"]] = dict(c, signed=None)
            out.append(by_token[c["token"]])
        elif e["type"] == "sign.signed" and c.get("token") in by_token:
            by_token[c["token"]]["signed"] = c | {"at": e["at"]}
        elif e["type"] == "sign.opened" and c.get("token") in by_token:
            by_token[c["token"]]["opened"] = e["at"]
        elif e["type"] == "sign.renewed" and c.get("token") in by_token:
            by_token[c["token"]]["expires"] = c["expires"]
    return out


def find(events: list[dict], token: str) -> dict | None:
    link = None
    for e in events:
        c = e["content"]
        if e["type"] == "sign.link" and c.get("token") == token:
            link = dict(c, signed=None)
        elif link and e["type"] == "sign.signed" and c.get("token") == token:
            link["signed"] = c | {"at": e["at"]}
        elif link and e["type"] == "sign.renewed" and c.get("token") == token:
            link["expires"] = c["expires"]
    return link


def renew(office: Office, token: str, by: str, *, today: date) -> None:
    """A link that ran out gets more days; a signed or replaced one doesn't."""
    g = office.graph()
    link = find(office.log.list(), token)
    if not link:
        raise KeyError(token)
    deal = g.nodes[f"deal:{g.nodes[link['draft']].deal}"].props
    if by != deal.get("broker") and by != roles.holder(g, "transactions") and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError(f"Only {name(deal.get('broker'))}, the transactions officer or the owner renews a link.")
    if status(g, link, today) not in ("expired", "open"):
        raise ValueError("Only an unsigned link on the current form can be renewed.")
    office.log.append("sign.renewed", actor=by, deal=g.nodes[link["draft"]].deal, content={"token": token, "expires": (today + timedelta(days=desk_rules.rules(g)["sign_link_days"])).isoformat()})


def make_links(office: Office, did: str, by: str, *, today: date) -> list[dict]:
    """One link per person who signs this form, made once per version."""
    g = office.graph()
    d, form = _form(g, did)
    deal = g.nodes[f"deal:{d.deal}"].props
    if by != deal.get("broker") and by != roles.holder(g, "transactions") and PEOPLE.get(by, {}).get("role") != "Owner":
        raise PermissionError(f"Only {name(deal.get('broker'))}, the transactions officer or the owner makes signing links.")
    if d.status == "sent_back":
        raise ValueError(f"{did} was sent back; make the links for the new version.")
    if form == "F":
        compliance.require(g, d.deal, "Form F's signatures")
    task = next((t for t in g.of("task", d.deal) if t.props.get("step") == "sign" and t.props.get("draft") == did), None)
    if form == "F":  # Form F has no signature task of its own: its plan's submit step waits on the portal, not on this
        task = next((t for t in g.of("task", d.deal) if t.props.get("agent") == "formf" and t.props.get("draft") == did), None)
        if any(x["signed"] for x in links(office.log.list(deal=d.deal), did)) and all(x["signed"] for x in links(office.log.list(deal=d.deal), did)):
            raise ValueError(f"{did} is already signed.")
    elif not task or task.status not in OPEN:
        raise ValueError(f"{did} isn't waiting for signatures.")
    have = {x["signer"] for x in links(office.log.list(deal=d.deal), did)}
    expires = (today + timedelta(days=desk_rules.rules(g)["sign_link_days"])).isoformat()
    for signer, _ in signers(g, d.deal, form):
        if signer not in have:
            office.log.append("sign.link", actor=by, deal=d.deal, content={"token": secrets.token_urlsafe(18), "draft": did, "form": form, "task": task.id if task else None,
                                                                            "signer": signer, "name": _who(g, d.deal, form, signer), "expires": expires})
    if not d.props.get("sent"):
        office.log.append("form.sent", actor=by, agent="ops", deal=d.deal, content={"draft": did, "form": form, "version": d.props.get("version"), "facts": sorted({f for s in g.into(did, "part_of") for f in s.props.get("facts", [])})})
    return links(office.log.list(deal=d.deal), did)


def status(g: Graph, link: dict, today: date) -> str:
    if link["signed"]:
        return "signed"
    if g.nodes[link["draft"]].status == "sent_back":
        return "replaced"
    if link["expires"] < today.isoformat():
        return "expired"
    return "open"


def page(office: Office, token: str, *, today: date) -> dict:
    """What the signer sees: the form's lines and whether it can be signed. Nothing about anyone else's checks."""
    g = office.graph()
    link = find(office.log.list(), token)
    if not link:
        raise KeyError(token)
    d, form = _form(g, link["draft"])
    r = desk_rules.rules(g)
    office.log.append("sign.opened", actor=f"signer:{link['signer']}", deal=d.deal, key=f"sign.opened:{token}", content={"token": token, "draft": link["draft"]})
    rows = [{"section": s, "label": lab, "value": v} for s, lab, v, _ in agency_forms.rows(g, link["draft"], form)]
    return {"title": agency_forms.TITLES_ALL[form], "agency": r["agency"]["name"] or "Diwan", "signer": link["name"],
            "as": dict(SIGNERS[form])[link["signer"]], "status": status(g, link, today), "expires": link["expires"], "rows": rows,
            "signed_at": link["signed"]["at"] if link["signed"] else None}


NOT_SIGNATURE = "This looks like a photo of {}, not a signature. Please sign on the white box, or on white paper and photograph just the signature."


def signature_problem(im) -> str | None:
    """A first filter, not a forgery test: dark ink on a plain light background. A photo of a person has colour and midtones,
    a document has text from edge to edge, and a blank page has no ink."""
    from PIL import ImageStat
    rgb = im.convert("RGB")
    rgb.thumbnail((400, 400))
    px = sorted(rgb.convert("L").getdata())
    n, paper = len(px), px[len(px) * 9 // 10]  # the paper: a dense page of print is mostly not paper
    if paper < 150:
        return NOT_SIGNATURE.format("a person")
    ink = sum(p < paper - 70 for p in px) / n
    if ink < 0.002:
        return "We can't see a signature on this. Please sign and try again."
    mid = sum(paper - 70 <= p < paper - 15 for p in px) / n
    if ImageStat.Stat(rgb.convert("HSV")).mean[1] > 45 or mid > 0.30:
        return NOT_SIGNATURE.format("a person")
    if ink > 0.22:
        return NOT_SIGNATURE.format("a document")
    grey = rgb.convert("L")
    w, h = grey.size
    data = list(grey.getdata())
    rows = sum(any(data[y * w + x] < paper - 70 for x in range(w)) for y in range(h)) / h
    if rows > 0.85 and ink > 0.06:
        return NOT_SIGNATURE.format("a document")
    return None


def _jpeg(data: bytes, *, drawn: bool = False, strokes: int = 0) -> tuple[bytes, int, int]:
    """The signature as a clean JPEG, or why it can't be used. Only real PNG or JPEG images are kept. One drawn on the
    page says how many strokes it took."""
    from PIL import Image, UnidentifiedImageError
    if drawn and strokes < 2:
        raise ValueError("Please sign with your usual signature.")
    if len(data) > MAX_BYTES:
        raise ValueError("The image is too large; keep it under 3 MB.")
    if not (data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff")):
        raise ValueError("Upload the signature as a PNG or JPEG photo.")
    try:
        Image.open(io.BytesIO(data)).verify()
        im = Image.open(io.BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValueError("That image can't be read; take the photo again.") from None
    if im.width < 120 or im.height < 40:
        raise ValueError("The image is too small to show a signature; take it closer.")
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    if why := signature_problem(im):
        raise ValueError(why)
    im = im.convert("RGB")
    im.thumbnail((800, 300))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue(), im.width, im.height


def sign(office: Office, token: str, *, full_name: str, id_no: str, consent: bool, image: bytes, ip: str, device: str,
         media, today: date, drawn: bool = False, strokes: int = 0) -> dict:
    g = office.graph()
    events = office.log.list()
    link = find(events, token)
    if not link:
        raise KeyError(token)
    st = status(g, link, today)
    if st != "open":
        raise ValueError({"signed": "This form is already signed with this link.",
                          "replaced": "This version was replaced. Your broker will send you the new one.",
                          "expired": "This link has expired. Ask your broker for a new one."}[st])
    if not full_name.strip() or not id_no.strip():
        raise ValueError("Give your full name and your ID or passport number.")
    if not consent:
        raise ValueError("Tick that you agree to sign electronically.")
    jpeg, w, h = _jpeg(image, drawn=drawn, strokes=strokes)
    media.mkdir(parents=True, exist_ok=True)
    path = media / f"sig-{token}.jpg"
    path.write_bytes(jpeg)
    office.log.append("sign.signed", actor=f"signer:{link['signer']}", deal=g.nodes[link["draft"]].deal,
                      content={"token": token, "draft": link["draft"], "signer": link["signer"], "name": full_name.strip(), "id_no": id_no.strip(),
                               "file": path.name, "w": w, "h": h, "ip": ip, "device": device[:160], "fingerprint": fingerprint(g, link["draft"]), "drawn": drawn})
    if link["signer"] in ("buyer", "seller"):
        from diwan import client_msgs
        client_msgs.tell(office, g.nodes[link["draft"]].deal, f"Received your signature on {agency_forms.TITLES_ALL[link['form']].split(':')[0]}, thank you.", what="confirm their signature was received")
    all_links = links(office.log.list(deal=g.nodes[link["draft"]].deal), link["draft"])
    done = {x["signer"] for x in all_links if x["signed"]}
    form = link["form"]
    deal = g.nodes[link["draft"]].deal
    if done >= {s for s, _ in signers(g, deal, form)}:
        sigs = [x["signed"] | {"as": dict(SIGNERS[form])[x["signer"]], "jpeg": (media / x["signed"]["file"]).read_bytes()} for x in all_links if x["signed"]]
        data = agency_forms.render(office.graph(), link["draft"], signatures=sigs)
        if form != "F":
            agency_forms.signed(office, link["task"], g.nodes[f"deal:{deal}"].props["broker"], data, "signed online", media=media, today=today)
        else:  # the signed memorandum is filed, and the paperwork step for its signatures ticks itself
            path = media / f"deal-{deal}-form-F-{link['draft']}-signed.pdf"
            path.write_bytes(data)
            office.file_document(kind="Form F", title=f"Form F ({link['draft']}) signed online by {len(sigs)}", date=today.isoformat(), by="ops",
                                 deal=deal, party=g.nodes[f"deal:{deal}"].props.get("customer"), text=f"/media/{path.name}")
            from diwan.agents import operations
            operations.form_f_done(office, deal)
        return {"status": "signed", "complete": True}
    return {"status": "signed", "complete": False}


def when(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=4))).strftime("%d %b %Y, %H:%M Dubai time")
