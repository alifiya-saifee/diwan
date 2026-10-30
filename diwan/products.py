"""What the business sells, when it is not a property listing: its products and services, each with what it does, its
features, its price if the business shows one, and the page it came from. The studio writes ideas, scripts and posts for
them the same way it does for a listing.

They come from the company's own website (proposed by the Brand brain, each fact quoted from its page) or are typed in
Setup, and are used only once a person confirms them. They live in the office's log (`product.saved`, the latest
version of each wins), apart from the CRM's listings, so the front desk never offers one as a property.
"""
from __future__ import annotations

import re

from diwan.office import Office

FIELDS = ("title", "kind", "what", "features", "price", "currency", "page", "status")
KINDS = ("product", "service")


def items(office: Office, *, all_: bool = False) -> dict[str, dict]:
    """{ref: product}, confirmed ones only unless all_ (proposed and removed too)."""
    out: dict[str, dict] = {}
    for e in office.log.list():
        if e["type"] == "product.saved":
            c = e["content"]
            out[c["ref"]] = {**out.get(c["ref"], {}), **c, "by": e["actor"], "at": e["at"]}
    return out if all_ else {r: p for r, p in out.items() if p.get("status") == "confirmed"}


def get(office: Office, ref: str) -> dict | None:
    return items(office, all_=True).get(ref)


def _ref(office: Office, title: str) -> str:
    base = "P-" + (re.sub(r"[^A-Z0-9]+", "-", title.upper()).strip("-")[:18] or "ITEM")
    taken, ref, n = items(office, all_=True), "", 1
    ref = base
    while ref in taken:
        n += 1
        ref = f"{base}-{n}"
    return ref


def _clean(values: dict) -> dict:
    v = {k: values[k] for k in FIELDS if k in values}
    if "title" in v:
        v["title"] = str(v["title"]).strip()[:80]
    if "features" in v:
        fs = v["features"] if isinstance(v["features"], list) else re.split(r"[,\n;]", str(v["features"]))
        v["features"] = [f.strip() for f in fs if f and f.strip()][:8]
    if "price" in v:
        p = str(v["price"] or "").replace(",", "").strip()
        if p and not re.fullmatch(r"\d+(\.\d+)?", p):
            raise ValueError(f"The price \"{v['price']}\" is not a number. Leave it empty if the price is not public.")
        v["price"] = (int(float(p)) if float(p).is_integer() else float(p)) if p else None
    if "kind" in v and v["kind"] not in KINDS:
        raise ValueError("Kind is product or service.")
    return v


def save(office: Office, values: dict, *, by: str, ref: str | None = None) -> str:
    """Add one (no ref) or change one. A person's save confirms it unless they say otherwise."""
    v = _clean(values)
    if not ref:
        if not v.get("title"):
            raise ValueError("Give it a name.")
        ref = _ref(office, v["title"])
        v = {"kind": "product", "features": [], "price": None, "currency": "", "page": "", "what": "", "status": "confirmed"} | v
    elif ref not in items(office, all_=True):
        raise ValueError(f"No product {ref}.")
    office.log.append("product.saved", actor=by, content={"ref": ref, **v})
    return ref


def propose(office: Office, found: list[dict], *, by: str) -> list[str]:
    """Products the Brand brain found on the company's pages, saved as proposed (not used until confirmed). One already
    known by the same name is left alone."""
    known = {p["title"].lower() for p in items(office, all_=True).values()}
    refs = []
    for f in found:
        if not f.get("title") or f["title"].strip().lower() in known:
            continue
        try:
            refs.append(save(office, {**f, "status": "proposed"}, by=by))
        except ValueError:
            continue
        known.add(f["title"].strip().lower())
    return refs


def record(p: dict) -> str:
    """One line for the writers, like a listing's record."""
    price = f"{p.get('currency') or ''} {p['price']:,}".strip() if isinstance(p.get("price"), (int, float)) else "price not public"
    return f"{p['title']} ({p.get('kind') or 'product'}): {p.get('what') or ''} · features: {'; '.join(p.get('features') or []) or 'none recorded'} · {price}"
