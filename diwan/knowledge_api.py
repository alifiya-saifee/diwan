"""Knowledge and the catalog over HTTP (docs/knowledge.md): tabs with counts, filters, add, edit, retire and restore,
proposals, history, the catalog's paged and filtered listing grid, and the one search the header box and agents use."""
from __future__ import annotations

import re
from collections import Counter

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from diwan import knowledge as kn
from diwan.people import PEOPLE

router = APIRouter()


def _office():
    from diwan.app import S
    return S.office


def _call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except KeyError as e:
        raise HTTPException(404, f"no such item {e.args[0]}") from None
    except kn.NotAllowed as e:
        raise HTTPException(403, str(e)) from None
    except ValueError as e:
        raise HTTPException(400, str(e)) from None


def _areas(g) -> list[str]:
    return sorted({n.props.get("title", "") for n in g.of("knowledge") if kn.tab(n) == "area" and n.status != "retired"}
                  | {n.props["community"] for n in g.of("listing")})


@router.get("/api/items")
def items(tab: str = "company", status: str = "", audience: str = "", stale: bool = False, area: str = "", q: str = "",
          retired: bool = False, by: str = "layla"):
    """One tab of the Knowledge page. Retired items appear only with `retired`."""
    g = _office().graph()
    used = kn.usage(g)
    every = g.of("knowledge")
    counts = {t: sum(1 for n in every if kn.tab(n) == t and n.status != "retired") for t in kn.KINDS}
    counts["listing"] = sum(1 for n in g.of("listing") if n.status != "retired")
    words = kn._words(q)
    rows = []
    for n in every:
        if kn.tab(n) != tab or n.status == "retired" and not retired:
            continue
        if status and n.status != status or audience and n.props.get("audience", "customer") != audience:
            continue
        if stale and not kn.stale(n):
            continue
        if area and area.lower() not in f"{n.props.get('applies_to') or ''} {n.props.get('title', '')}".lower():
            continue
        if words and not words & (kn._words(n.props.get("title", "")) | kn._words(n.props.get("text", ""))):
            continue
        rows.append(kn.item(g, n, used) | {"can_edit": kn.may_edit(n, by)})
    rows.sort(key=lambda r: (r["status"] != "proposed", not r["stale"], r["title"].lower()))
    proposals = [p.props | {"status": p.status, "title": g.nodes[p.props["item"]].props.get("title"), "can_decide": kn.may_edit(g.nodes[p.props["item"]], by)}
                 for p in g.of("proposal", status="open") if p.props["item"] in g.nodes]
    return {"tab": tab, "counts": counts, "rows": rows, "proposals": proposals, "areas": _areas(g),
            "kinds": {k: {"label": v[0], "owners": [PEOPLE[o]["name"] for o in sorted(v[1])], "empty": v[2]} for k, v in kn.KINDS.items()},
            "stale_count": sum(1 for n in every if kn.tab(n) == tab and kn.stale(n))}


@router.get("/api/items/{iid:path}/history")
def item_history(iid: str):
    g = _office().graph()
    n = _call(kn._node, g, iid)
    used = kn.usage(g)
    return {"item": kn.item(g, n, used), "history": kn.history(_office(), iid),
            "versions": [v.props for v in g.out(iid, "replaces")],
            "related": [kn.item(g, x, used) for x in kn.area_of(g, n)][:50]}


class ItemIn(BaseModel):
    kind: str
    title: str
    text: str
    audience: str = "customer"
    review_by: str | None = None
    valid_until: str | None = None
    applies_to: str | None = None
    by: str = "layla"


class EditIn(BaseModel):
    changes: dict
    why: str = ""
    by: str = "layla"


class WhyIn(BaseModel):
    why: str = ""
    by: str = "layla"


class DecideIn(BaseModel):
    accept: bool
    why: str = ""
    by: str = "layla"


@router.post("/api/items")
def add_item(body: ItemIn):
    if not body.title.strip() or not body.text.strip():
        raise HTTPException(400, "Add a title and the text")
    for d in (body.review_by, body.valid_until):
        if d:
            _call(date.fromisoformat, d)
    return _call(kn.add, _office(), body.kind, body.title.strip(), body.text.strip(), by=body.by, audience=body.audience,
                 review_by=body.review_by, valid_until=body.valid_until, applies_to=body.applies_to)


class NewListingIn(BaseModel):
    values: dict
    anyway: bool = False
    by: str = "layla"


@router.post("/api/listings/new")
def new_listing(body: NewListingIn):
    """One listing typed in by hand (the Listings tab). {ok, ref} or {ok: false, error} or {duplicate: ref} to confirm."""
    from diwan import listing_add
    try:
        return {"ok": True, **listing_add.add(_office(), body.values, by=body.by, anyway=body.anyway)}
    except listing_add.Duplicate as e:
        return {"ok": False, "duplicate": e.ref, "error": str(e)}
    except listing_add.Invalid as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/items/{iid:path}/edit")
def edit_item(iid: str, body: EditIn):
    ch = dict(body.changes)
    if "price_aed" in ch:
        try:
            ch["price_aed"] = int(ch["price_aed"])
        except (TypeError, ValueError):
            raise HTTPException(400, "The price must be a number") from None
    return _call(kn.edit, _office(), iid, ch, by=body.by, why=body.why)


@router.post("/api/items/{iid:path}/retire")
def retire_item(iid: str, body: WhyIn):
    return _call(kn.retire, _office(), iid, by=body.by, why=body.why)


@router.post("/api/items/{iid:path}/restore")
def restore_item(iid: str, body: WhyIn):
    return _call(kn.restore, _office(), iid, by=body.by)


@router.post("/api/items/{iid:path}/reconfirm")
def reconfirm_item(iid: str, body: WhyIn):
    return _call(kn.reconfirm, _office(), iid, by=body.by)


@router.post("/api/proposals/{pid}/decide")
def decide_proposal(pid: str, body: DecideIn):
    return _call(kn.decide, _office(), pid, accept=body.accept, by=body.by, why=body.why)


@router.get("/api/search")
def search(q: str, staff: bool = True, k: int = 8):
    """The header search (staff: every item) and Rania's lookup (staff=false: what may be said to a customer)."""
    g = _office().graph()
    return {"q": q, "items": kn.search(g, q, k=min(k, 50), for_customer=not staff, used=kn.usage(g))}


def _stage(v) -> str:
    """A completion stage written one way: "off_plan", "Off-plan" and "off plan" are all "off-plan"."""
    return re.sub(r"[\s_]+", "-", str(v or "").strip().lower())


@router.get("/api/catalog")
def catalog(area: str = "", beds: str = "", min_price: int | None = None, max_price: int | None = None, status: str = "",
            agent: str = "", permit: str = "", q: str = "", page: int = 1, size: int = 50, retired: bool = False, by: str = "layla",
            offering: str = "", type: str = "", country: str = "", completion: str = ""):
    """The listings, filtered and paged (50 at a time), and every filtered listing's map pin."""
    g = _office().graph()
    every = g.of("listing")
    words = kn._words(q)
    ql = q.strip().lower()
    rows = []
    for n in every:
        p = n.props
        if n.status == "retired" and not retired:
            continue
        if area and area.lower() not in p["community"].lower():
            continue
        if beds and not (p["beds"] >= 5 if beds == "5" else p["beds"] == int(beds)):
            continue
        pa = p.get("price_aed")
        if (min_price is not None or max_price is not None) and pa is None:
            continue  # no AED price to compare (a listing in another currency)
        if min_price is not None and pa < min_price or max_price is not None and pa > max_price:
            continue
        if status and n.status != status or agent and p.get("agent") != agent:
            continue
        if permit == "yes" and not p.get("permit") or permit == "no" and p.get("permit"):
            continue
        if offering and p.get("offering") != offering:
            continue
        if completion and _stage(p.get("completion")) != completion:
            continue
        if type and (p.get("type") or "").lower() != type.lower() or country and (p.get("country") or "") != country:
            continue
        if ql and ql not in p["ref"].lower() and not words <= (kn._words(p.get("title", "")) | kn._words(p["community"]) | kn._words(p["ref"])):
            continue
        rows.append(n)
    rows.sort(key=lambda n: -n.event)
    size = max(1, min(size, 100))
    used = kn.usage(g)
    start = (max(page, 1) - 1) * size
    return {"total": len(rows), "page": page, "size": size, "all": len(every),
            "rows": [kn.item(g, n, used) | {"can_edit": kn.may_edit(n, by)} for n in rows[start:start + size]],
            "pins": [{"id": n.id, "ref": n.props["ref"], "title": n.props.get("title") or n.label, "price_aed": n.props.get("price_aed"),
                      "offering": n.props.get("offering"), "lat": n.props["lat"], "lng": n.props["lng"], "advertised": kn.advertised(n)}
                     for n in rows if n.props.get("lat") is not None and n.props.get("lng") is not None],
            "areas": sorted({n.props["community"] for n in every}),
            "types": sorted({t for n in every if (t := (n.props.get("type") or "").strip())}),
            "currency": (Counter(n.props.get("currency") or "AED" for n in every).most_common(1) or [("", 0)])[0][0],  # what most listings are priced in
            "completions": sorted({c for n in every if (c := _stage(n.props.get("completion")))}),
            "countries": sorted({c for n in every if (c := n.props.get("country"))}),
            "agents": sorted({a for n in every if (a := n.props.get("agent"))}),
            "statuses": sorted({n.status for n in every if n.status != "retired"}),
            "proposals": [p.props | {"status": p.status, "can_decide": kn.may_edit(g.nodes[p.props["item"]], by)}
                          for p in g.of("proposal", status="open") if p.props["item"].startswith("listing:") and p.props["item"] in g.nodes]}


@router.get("/api/memory/knowledge")
def memory(upto: int | None = None):
    """The memory graph's Knowledge view: every item, its replaced versions, retired items dimmed with their reason,
    proposals, and the links between areas and their listings (listings only where linked, so the view stays readable)."""
    from diwan.app import node_json
    g = _office().graph(upto)
    keep = {n.id for n in g.nodes.values() if n.type in ("knowledge", "version", "proposal")}
    links = [(x.id, "in_area", k.id) for k in g.of("knowledge") if kn.tab(k) == "area" for x in kn.area_of(g, k)[:12]]
    keep |= {a for a, _, _ in links}
    nodes = []
    for i in keep:
        d = node_json(g, g.nodes[i])
        n = g.nodes[i]
        if n.status == "retired":
            d["record"] += f" · retired: {n.props['retired']['why']}"
        if n.type == "version":
            d["record"] = f"{n.props['of']} version {n.props['version']} (replaced): {n.props.get('title')}: {n.props.get('text') or ''}" + (
                f" AED {n.props['price_aed']:,}" if n.props.get("price_aed") else "")
        nodes.append(d)
    edges = [{"src": e.src, "rel": e.rel, "dst": e.dst, "via": e.via} for e in g.edges if e.src in keep and e.dst in keep]
    edges += [{"src": a, "rel": r, "dst": b, "via": None} for a, r, b in links]
    return {"last_event": g.last_event, "nodes": nodes, "edges": edges}
