"""Adding one listing by hand (the Listings tab). The same listing record the portal feed and the website finder write,
with the same checks: a number is a number, the same permit or the same beds, price and community is not added twice
unless the person says so, and one without a permit is kept but never advertised."""
from __future__ import annotations

import re

from diwan import knowledge as kn
from diwan import sitelistings
from diwan.office import Office

OFFERINGS = ("sale", "rent")


class Invalid(ValueError):
    pass


class Duplicate(ValueError):
    def __init__(self, ref: str, title: str):
        super().__init__(f"{ref} ({title}) looks like the same property")
        self.ref, self.title = ref, title


def _num(v, what: str, *, whole: bool = False, required: bool = False):
    s = re.sub(r"[,\s]", "", str(v if v is not None else ""))
    if not s:
        if required:
            raise Invalid(f"Give the {what}.")
        return None
    try:
        n = float(s)
    except ValueError:
        raise Invalid(f"The {what} \"{v}\" is not a number.") from None
    if n < 0:
        raise Invalid(f"The {what} can't be negative.")
    return int(n) if n.is_integer() or whole else n


def _ref(office: Office, title: str) -> str:
    taken = {n.props.get("ref") for n in office.graph().of("listing")}
    base = "MAN-" + (re.sub(r"[^A-Z0-9]+", "-", title.upper()).strip("-")[:14] or "LISTING")
    ref, n = base, 1
    while ref in taken:
        n += 1
        ref = f"{base}-{n}"
    return ref


def add(office: Office, v: dict, *, by: str, anyway: bool = False) -> dict:
    if by not in kn.LISTING_OWNERS:
        from diwan.people import PEOPLE
        raise Invalid(f"Only {' or '.join(PEOPLE[o]['name'] for o in sorted(kn.LISTING_OWNERS))} can add a listing.")
    title = str(v.get("title") or "").strip()
    if not title:
        raise Invalid("Give it a title.")
    beds = _num(v.get("beds"), "number of bedrooms (0 for a studio)", whole=True, required=True)
    price = _num(v.get("price"), "price", required=True)
    cur = str(v.get("currency") or "").strip().upper()
    offering = str(v.get("offering") or "").strip().lower()
    if offering and offering not in OFFERINGS:
        raise Invalid("Offering is sale or rent.")
    permit = str(v.get("permit") or "").strip() or None
    p = {"url": "", "title": title, "beds": beds, "price": price, "currency": cur, "permit": permit,
         "community": str(v.get("community") or "").strip()}
    existing = [n.props for n in office.graph().of("listing") if n.status != "retired"]
    if (x := sitelistings.match(p, existing)) and not anyway:
        raise Duplicate(x["ref"], x.get("title") or x["ref"])
    ref = _ref(office, title)
    content = {"ref": ref, "title": title, "community": p["community"], "type": str(v.get("type") or "").strip(), "beds": beds,
               "baths": _num(v.get("baths"), "number of bathrooms"), "size_sqft": _num(v.get("size_sqft"), "size"),
               "price": price, "currency": cur, "price_aed": price if cur in ("AED", "") else None, "permit": permit,
               "offering": offering, "completion": str(v.get("completion") or "").strip(), "country": str(v.get("country") or "").strip(),
               "photos": [u for u in [str(v.get("photo") or "").strip()] if u], "status": "available", "features": [], "agent": None,
               "source": "typed"}
    office.log.append("listing.added", actor=by, content={k: x for k, x in content.items() if x not in (None, "") or k in sitelistings.CRM})
    return {"ref": ref, "advertised": bool(permit)}
