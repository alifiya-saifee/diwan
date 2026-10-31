"""Property portals: the brokerage's own listings, and the enquiries Property Finder, Bayut and Dubizzle send it.

The portals give API access to brokerages through their partner programmes and do not publish the specifications,
so this reads the two shapes every brokerage already has:
- The listing feed: the XML the brokerage publishes for the portals to pull, one <property> or <listing> per ad.
  Diwan reads the same URL (LISTING_FEED_URL), so its listings are exactly what is advertised. Nothing is scraped.
- Lead webhooks: the portal (or the brokerage's lead connector) posts each enquiry to /api/portals/{portal}/lead,
  signed with that portal's shared secret: HMAC-SHA256 of the body in X-Signature, or ?token= when a sender can only
  add a token. No secret set: the hook refuses everything.
Field names follow the common feed and lead formats; a portal that names a field differently is added to FIELDS once
its documentation arrives with the key.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import xml.etree.ElementTree as ET

import httpx

from diwan.config import env

TRANSPORT: httpx.BaseTransport | None = None  # tests swap in a fake
PORTALS = {"propertyfinder": "Property Finder", "bayut": "Bayut", "dubizzle": "Dubizzle"}
MAX_FEED = 10_000_000

FIELDS = {  # our name: the names feeds and lead payloads use for it, first match wins
    "ref": ("reference_number", "reference", "ref", "listing_reference", "property_reference", "property_ref", "listing_ref"),
    "permit": ("permit_number", "permit", "rera_permit", "trakheesi", "dld_permit", "advertisement_permit"),
    "permit_until": ("permit_expiry", "permit_expires", "permit_valid_until", "permit_end_date"),
    "title": ("title_en", "title", "name", "property_title"),
    "price": ("price", "price_aed", "selling_price", "amount"),
    "beds": ("bedroom", "bedrooms", "beds", "no_of_bedrooms"),
    "type": ("property_type", "type", "category", "unit_type"),
    "community": ("community", "sub_community", "location", "area", "city"),
    "offering": ("offering_type", "purpose", "listing_type"),
    "description": ("description_en", "description", "details"),
    "completion": ("completion_status", "completion", "ready_or_offplan", "project_status"),
    "project": ("project_name", "project", "development_name"),
    "size": ("size", "size_sqft", "area_sqft", "plot_size", "built_up_area"),
    "geopoints": ("geopoints", "geo", "coordinates"),
    "lat": ("latitude", "lat", "geo.lat"),
    "lng": ("longitude", "lng", "lon", "geo.lng"),
    "agent_email": ("agent_email", "email", "agent.email"),
    "agent_name": ("agent_name", "agent", "agent.name"),
    "name": ("name", "full_name", "client_name", "contact_name", "contact.name", "lead.name"),
    "phone": ("phone", "mobile", "phone_number", "contact.phone", "contact.mobile", "lead.phone"),
    "email_lead": ("email", "contact.email", "lead.email"),
    "message": ("message", "comment", "enquiry", "inquiry", "body", "lead.message"),
}
TYPES = {"ap": "apartment", "vh": "villa", "th": "townhouse", "pe": "penthouse", "duplex": "duplex"}


class PortalError(RuntimeError):
    pass


def secret(portal: str) -> str | None:
    return env(f"PORTAL_SECRET_{portal.upper()}")


def signed(portal: str, body: bytes, header: str | None, token: str = "") -> bool:
    """A lead counts only when it carries this portal's secret. No secret configured: refuse."""
    s = secret(portal)
    if not s:
        return False
    if token:
        return hmac.compare_digest(token, s)
    if not header:
        return False
    want = hmac.new(s.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(want, header.removeprefix("sha256=").strip().lower())


# ---------- listings ----------

def _text(el: ET.Element, names: tuple[str, ...]) -> str | None:
    for n in names:
        found = el.find(n.replace(".", "/"))
        if found is not None and (found.text or "").strip():
            return found.text.strip()
        if el.get(n):
            return el.get(n).strip()
    return None


def _int(s: str | None) -> int | None:
    if not s:
        return None
    if s.strip().lower() in ("studio", "st"):
        return 0
    digits = re.sub(r"[^\d.]", "", s)
    return int(float(digits)) if digits else None


PHOTOS = ("photos", "photo", "images", "image", "pictures", "photo_urls")


def _photos(el: ET.Element) -> list[str]:
    """Image links in any of the usual shapes: <photos><photo>url</photo></photos>, <images><image><url>url</url>, or
    <photo url="..."/>. Only web addresses (or the demo's own /web/ paths) are kept."""
    out = []
    for box in el:
        if box.tag.lower() not in PHOTOS:
            continue
        for x in [box, *box.iter()]:
            v = (x.get("url") or x.text or "").strip()
            if re.match(r"(https?://|/web/)\S+$", v) and v not in out:
                out.append(v)
    return out[:20]


def _geo(f: dict) -> tuple[float, float] | None:
    """Latitude and longitude, from geopoints ("lat,lng") or separate fields. The UAE's latitude (22-27) is always below
    its longitude (51-57), so a feed that writes "lng,lat" is read the right way round there."""
    try:
        if f.get("geopoints"):
            a, b = (float(x) for x in re.split(r"[,\s]+", f["geopoints"].strip())[:2])
        elif f.get("lat") and f.get("lng"):
            a, b = float(f["lat"]), float(f["lng"])
        else:
            return None
    except ValueError:
        return None
    lat, lng = (b, a) if 50 < a < 58 and 21 < b < 28 else (a, b)
    return (round(lat, 6), round(lng, 6)) if -90 <= lat <= 90 and -180 <= lng <= 180 else None


OFFERING = {"rs": "sale", "cs": "sale", "sell": "sale", "for sale": "sale", "buy": "sale",
            "rr": "rent", "cr": "rent", "for rent": "rent", "lease": "rent", "let": "rent"}  # portal codes: RS = residential sale


def parse_feed(xml: str | bytes) -> list[dict]:
    """Listings from the brokerage's portal feed. A listing without a permit is kept and never advertised."""
    if len(xml) > MAX_FEED:
        raise PortalError("The feed is larger than 10 MB")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise PortalError(f"The feed is not valid XML: {e}") from None
    items = [el for el in root.iter() if el.tag.lower() in ("property", "listing", "unit")]
    out = []
    for el in items:
        f = {k: _text(el, v) for k, v in FIELDS.items() if k in ("ref", "permit", "permit_until", "title", "price", "beds", "type", "community",
                                                                  "offering", "agent_email", "agent_name", "description", "size",
                                                                  "geopoints", "lat", "lng", "completion", "project")}
        if not f["ref"] or _int(f["price"]) is None:
            continue
        t = (f["type"] or "apartment").lower()
        out.append({"ref": f["ref"], "permit": f["permit"], "permit_until": (f.get("permit_until") or "")[:10] or None, "price_aed": _int(f["price"]), "beds": _int(f["beds"]) or 0,
                    "type": TYPES.get(t, t), "community": f["community"] or "Dubai",
                    "title": f["title"] or f"{f['ref']}, {f['community'] or 'Dubai'}", "offering": OFFERING.get((f["offering"] or "").lower(), (f["offering"] or "").lower() or None),
                    "agent_email": f["agent_email"], "agent_name": f["agent_name"],
                    "photos": _photos(el), "geo": _geo(f), "description": f["description"], "size_sqft": _int(f["size"]),
                    "completion": ("off_plan" if re.search(r"off|under|plan", f["completion"].lower()) else "ready") if f["completion"] else None,
                    "project": f["project"]})
    return out


def fetch_feed(url: str | None = None) -> bytes:
    url = url or env("LISTING_FEED_URL")
    if not url:
        raise PortalError("Set LISTING_FEED_URL: the address of the listing feed you give the portals")
    with httpx.Client(transport=TRANSPORT, timeout=30, follow_redirects=True) as c:
        r = c.get(url)
    if r.status_code != 200:
        raise PortalError(f"The feed answered {r.status_code}")
    return r.content


# ---------- leads ----------

def _get(d: dict, path: str):
    for part in path.split("."):
        if not isinstance(d, dict):
            return None
        d = d.get(part)
    return d


def _first(d: dict, names: tuple[str, ...]) -> str | None:
    for n in names:
        v = _get(d, n)
        if v not in (None, ""):
            return str(v).strip()
    return None


def parse_lead(portal: str, body: dict) -> dict:
    """One enquiry: who, how to reach them, what they wrote, and which listing it is about."""
    lead = body.get("data") if isinstance(body.get("data"), dict) else body
    phone = re.sub(r"\D", "", _first(lead, FIELDS["phone"]) or "")
    if phone.startswith("00"):
        phone = phone[2:]
    elif phone.startswith("05") and len(phone) == 10:
        phone = "971" + phone[1:]
    ref = _first(lead, FIELDS["ref"]) or _first(lead, ("listing.reference", "property.reference", "listing.ref"))
    if not phone:
        raise PortalError("The enquiry has no phone number")
    return {"portal": portal, "name": _first(lead, FIELDS["name"]), "phone": phone, "email": _first(lead, FIELDS["email_lead"]),
            "message": _first(lead, FIELDS["message"]) or "", "ref": ref}
