"""The properties on the company's own website, added to the CRM's listings when they are not there already.

Nothing here knows one site's layout. It finds the property pages by their shape: a family of pages under one parent
path (/properties/a, /properties/b, ...) whose pages each read as one property. Each page is read in code, in this order
of trust:

  1. schema.org data the page carries for search engines (JSON-LD: price, rooms, floor size, address)
  2. labelled facts in the page ("Price: AED 8,300,000", "Beds: 4", a table row, a dt/dd pair)
  3. a number with its unit ("4 Beds", "7842 sqft"), only when it is the one such number on the page

A fact the code finds twice with different values (a "similar properties" strip, say) is left for the model, not
guessed. The model (Brand brain) then reads the pages that still miss something, eight at a time, and every value it
gives must appear on that page as written, or it is dropped: a field is empty rather than wrong.

A property already in Diwan (the same page; the same permit or reference with the same bedrooms; or the same beds, price
and community) is not added twice; one that matches but differs (a new price) is listed for a person and never
overwritten. A site can show one permit on several units, so a permit alone doesn't make two pages one property: a new
unit sharing another's permit is added and listed for a person to check.
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urldefrag, urljoin, urlparse

import httpx

from diwan import business, learn
from diwan.agents import runner
from diwan.agents.charters import get
from diwan.office import Office
from diwan.pack import norm

INDEX_PAGES = 40     # pages read to find where the properties are listed (then the pages that list them)
MAX_ITEMS = 200      # property pages read at most
FAMILY = 4           # pages under one parent path before it counts as a family
BATCH = 8            # pages per model call
NUM = r"\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
CUR = r"[A-Z]{3}|[$€£¥₹]"

# what a fact is called on property pages, in general (not one site's words)
LABELS = {
    "price": r"(?:asking\s+|sale\s+|rent(?:al)?\s+)?price|cost|rent",
    "beds": r"bed(?:room)?s?|br",
    "baths": r"bath(?:room)?s?",
    "size_sqft": r"(?:built[\s-]?up\s+|plot\s+|lot\s+|floor\s+|living\s+)?(?:area|size)|bua",
    "ref": r"(?:property\s+|listing\s+)?(?:reference|ref)(?:\s*(?:no\.?|number|#|id))?",
    "permit": r"(?:advertising\s+)?(?:permit|trakheesi|madhmoun|rera|dld|licen[cs]e)(?:\s*\([^)]{1,30}\))?(?:\s*(?:no\.?|number|#))?",
    "type": r"(?:property\s+)?type",
    "community": r"community|neighbou?rhood|district|area\s+name|location|building|project",
    "completion": r"completion(?:\s+status)?|status|handover",
    "furnishing": r"furnish(?:ing|ed)(?:\s+types?)?",
}
LD_TYPES = re.compile(r"RealEstateListing|Offer|Product|Residence|Accommodation|Apartment|House|Place|Room|Suite", re.I)


CRM = ("ref", "title", "community", "type", "beds", "price_aed", "permit", "status", "features", "agent")  # every listing has these, even empty


class Invalid(ValueError):
    pass


# ---------- finding the property pages ----------

def _parent(u: str) -> str:
    p = urlparse(u).path.rstrip("/")
    return p.rsplit("/", 1)[0] if "/" in p.strip("/") else ""


def _links(base: str, page: str, host: str) -> set[str]:
    out = set()
    for href in re.findall(r"""<a[^>]+href=["']([^"'#]+)""", page, re.I):
        u = urldefrag(urljoin(base, htmllib.unescape(href)))[0]
        u = re.sub(r"\?(?!.*\bpage=).*$", "", u).rstrip("/")  # keep ?page=2, drop tracking queries
        if u.startswith("http") and learn._host(u) == host and not learn.SKIP.search(u):
            out.add(u)
    return out


def find(url: str, *, client: httpx.Client | None = None) -> dict:
    """{pages: [url], families: [parent path], refused, read}: the property pages of the site."""
    from urllib.robotparser import RobotFileParser
    url = (url or "").strip()
    if not url:
        raise Invalid("Put your website under Our business first.")
    if not url.startswith("http"):
        url = "https://" + url
    host = learn._host(url)
    own = client is None
    c = client or httpx.Client(transport=learn.TRANSPORT, timeout=15, follow_redirects=True, headers=learn.UA)
    try:
        robots = RobotFileParser()
        try:
            r = c.get(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
            robots.parse(r.text.splitlines() if r.status_code == 200 else [])
        except httpx.HTTPError:
            robots.parse([])

        def fetch(u):
            try:
                r = c.get(u)
                return r.text if r.status_code < 400 and "html" in r.headers.get("content-type", "html") else None
            except httpx.HTTPError:
                return None

        seen, refused, cache, out = set(), [], {}, {}  # out: page -> the links on it
        read = 0

        def visit(urls):
            nonlocal read
            todo = []
            for u in urls:
                if u in seen:
                    continue
                seen.add(u)
                (todo if robots.can_fetch("*", u) else refused).append(u)
            with ThreadPoolExecutor(8) as pool:
                for u, page in zip(todo, pool.map(fetch, todo)):
                    read += 1
                    if page is not None:
                        cache[u] = page
                        out[u] = _links(u, page, host)

        # 1. the site's pages, nearest the home page first
        queue = [url.rstrip("/")]
        while queue and read < INDEX_PAGES:
            visit(queue[:8])
            queue = sorted({v for u in out for v in out[u]} - seen, key=lambda u: len(urlparse(u).path))
        # 2. families of pages under one parent path; a family is kept when most of a sample reads as one property each
        kept: set[str] = set()
        checked: set[str] = set()
        for _ in range(6):
            kids: dict[str, set[str]] = {}
            for u in out:
                for v in out[u]:
                    kids.setdefault(_parent(v), set()).add(v)
            for p in sorted((p for p, k in kids.items() if p and len(k) >= FAMILY and p not in checked), key=lambda p: -len(kids[p])):
                checked.add(p)
                sample = sorted(kids[p])[:3]
                visit(sample)
                if sum(1 for u in sample if u in cache and _looks_like_one(read_page(cache[u], u))) >= 2:
                    kept.add(p)
            # 3. the pages that list them (a category, the next page of results) and those pages' siblings, until no new ones
            lists = {u for u in out if len({v for v in out[u] if _parent(v) in kept}) >= 3}
            more = {v for u in lists for v in out[u] if _parent(v) not in kept} & {v for u in lists for v in out[u] if _parent(v) in {_parent(x) for x in lists}}
            more |= {v for u in lists for v in out[u] if re.search(r"(?:/page/|[?&]page=)\d+", v)}
            more -= seen
            if not more:
                break
            visit(sorted(more)[:40])
        pages = sorted({v for u in out for v in out[u] if _parent(v) in kept and robots.can_fetch("*", v)})[:MAX_ITEMS]
        kept = sorted(kept)
        return {"pages": pages, "families": kept, "refused": refused[:10], "read": read, "_cache": cache, "_fetch": fetch}
    finally:
        if own:
            c.close()


def _looks_like_one(p: dict) -> bool:
    """A page about one property: a price, and its beds or its size."""
    return p.get("price") is not None and (p.get("beds") is not None or p.get("size_sqft") is not None)


# ---------- reading one page in code ----------

def _num(s: str) -> float | None:
    s = re.sub(r"[,\s]", "", s or "")
    try:
        return float(s)
    except ValueError:
        return None


def _int(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


def _jsonld(page: str) -> dict:
    out = {}

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            t = o.get("@type")
            t = " ".join(t) if isinstance(t, list) else str(t or "")
            if LD_TYPES.search(t):
                offers = o.get("offers")
                offers = offers[0] if isinstance(offers, list) and offers else offers
                if isinstance(offers, dict) and offers.get("price") is not None and "price" not in out:
                    out["price"] = _num(str(offers["price"]))
                    out["currency"] = offers.get("priceCurrency") or ""
                if o.get("price") is not None and "price" not in out:
                    out["price"] = _num(str(o["price"]))
                    out["currency"] = o.get("priceCurrency") or ""
                for k, ours in (("numberOfBedrooms", "beds"), ("numberOfRooms", "beds"), ("numberOfBathroomsTotal", "baths")):
                    if o.get(k) is not None and ours not in out:
                        out[ours] = _num(str(o[k] if not isinstance(o[k], dict) else o[k].get("value")))
                fs = o.get("floorSize")
                if isinstance(fs, dict) and fs.get("value") is not None and "size_sqft" not in out:
                    v = _num(str(fs["value"]))
                    out["size_sqft"] = v * 10.7639 if v and str(fs.get("unitCode", "")).upper() in ("MTK", "SQM") else v
                addr = o.get("address")
                if isinstance(addr, dict) and "community" not in out:
                    out["community"] = addr.get("addressLocality") or addr.get("streetAddress") or ""
            for v in o.values():
                walk(v)

    for block in re.findall(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", page, re.S | re.I):
        try:
            walk(json.loads(block))
        except ValueError:
            continue
    return {k: v for k, v in out.items() if v not in (None, "")}


def _pairs(page: str) -> list[tuple[str, str]]:
    """(label, value) from table rows and dt/dd pairs, the structured ways a page lists facts."""
    strip = lambda s: re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
    out = [(strip(a), strip(b)) for a, b in re.findall(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", page, re.S | re.I)]
    out += [(strip(a), strip(b)) for a, b in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>\s*<td[^>]*>(.*?)</td>", page, re.S | re.I)]
    return [(a.rstrip(":"), b) for a, b in out if a and b and len(a) < 40]


def _labelled(text: str, pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    """Every value each fact is given on the page, by its label."""
    found: dict[str, set[str]] = {}
    for key, lab in LABELS.items():
        vals = set()
        for a, b in pairs:
            if re.fullmatch(rf"(?:{lab})", a, re.I):
                vals.add(b[:80])
        if key in ("ref", "permit"):  # a code right after its label, with or without a colon; it must hold a digit
            pat = rf"(?<![\w-])(?:{lab})\s*[:#]?\s*([A-Z0-9][A-Z0-9/-]{{3,40}})"
        else:
            pat = rf"(?<![\w-])(?:{lab})\s*:\s*([^:]{{1,80}}?)(?=\s+[A-Z][\w/()\s-]{{0,30}}:|$|\s{{2}}|\s-\s)"
        for m in re.finditer(pat, text, re.I):
            vals.add(m.group(1).strip())
        if vals:
            found[key] = vals
    return found


def _amount(v: str) -> tuple[float | None, str]:
    m = re.search(rf"(?:({CUR})\s*)?({NUM})\s*({CUR})?", v)
    if not m:
        return None, ""
    return _num(m.group(2)), m.group(1) or m.group(3) or ""


def read_page(page: str, url: str) -> dict:
    """What the code can read on one property page, without the model. A fact given two different values is left out
    and listed in `unsure`."""
    text = learn.page_text(page)
    title = re.search(r"""<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)""", page, re.I) or \
        re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S | re.I) or re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    title = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", title.group(1)))).strip() if title else ""
    site = re.search(r"""<meta[^>]+property=["']og:site_name["'][^>]+content=["']([^"']+)""", page, re.I)
    site = _words(site.group(1) if site else "") | _words(learn._host(url).split(".")[0])
    parts = re.split(r"\s+[|\-–—]\s+", title)
    if len(parts) > 1 and _words(parts[-1]) and (_words(parts[-1]) <= site or norm(parts[-1]).replace(" ", "") in learn._host(url).replace("-", "")):
        title = title[:len(title) - len(parts[-1])].rstrip(" |-–—")  # " - Site name" at the end
    out = {"url": url, "title": title[:120], "unsure": []}
    out |= _jsonld(page)
    main = text[max(0, text.find(title[:30])):] if title and title[:30] in text else text  # the menu above the title is no help
    lab = _labelled(main, _pairs(page))

    def one(key, parse):
        if key in out:
            return
        vals = {parse(v) for v in lab.get(key, ())}
        vals.discard(None)
        if len(vals) == 1:
            out[key] = vals.pop()
        elif len(vals) > 1:
            out["unsure"].append(key)

    prices = {_amount(v) for v in lab.get("price", ())}
    prices = {p for p in prices if p[0]}
    if "price" not in out:
        if len({p[0] for p in prices}) == 1:
            out["price"], out["currency"] = next(iter(prices))
            out["currency"] = out["currency"] or next((c for _, c in prices if c), "")
        elif prices:
            out["unsure"].append("price")
    one("beds", lambda v: 0.0 if re.match(r"studio", v, re.I) else _num(m.group(0)) if (m := re.match(r"\d+", v)) else None)
    one("baths", lambda v: _num(m.group(0)) if (m := re.match(r"\d+", v)) else None)
    one("size_sqft", lambda v: _num(m.group(1)) * (10.7639 if re.search(r"m2|m²|sqm|sq\.?\s*m\b", v, re.I) else 1)
        if (m := re.match(rf"({NUM})", v)) else None)
    for key in ("ref", "permit"):
        one(key, lambda v: m.group(0) if (m := re.match(r"[A-Z0-9][A-Z0-9/-]{3,40}", v, re.I)) and re.search(r"\d", m.group(0)) else None)
    for key in ("type", "community", "completion", "furnishing"):
        one(key, lambda v: v.strip()[:60] or None)
    # a number with its unit, when the page gives only one such number
    for key, unit in (("beds", r"bed(?:room)?s?|br\b"), ("baths", r"bath(?:room)?s?"), ("size_sqft", r"sq\.?\s*ft|sqft|square\s+feet")):
        if key not in out and key not in out["unsure"]:
            vals = {_num(m.group(1)) for m in re.finditer(rf"({NUM})\s*(?:{unit})", text, re.I)}
            vals.discard(None)
            if len(vals) == 1:
                out[key] = vals.pop()
            elif vals:
                out["unsure"].append(key)
    if "price" not in out and "price" not in out["unsure"]:  # the most repeated amount with a currency, when one clearly leads
        counts: dict[tuple, int] = {}
        for m in re.finditer(rf"({CUR})\s*({NUM})", text):
            k = (_num(m.group(2)), m.group(1))
            counts[k] = counts.get(k, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: -x[1])
        if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]) and ranked[0][1] >= 2:
            out["price"], out["currency"] = ranked[0][0]
        elif ranked:
            out["unsure"].append("price")
    imgs = re.findall(r"""<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)""", page, re.I)
    imgs += [urljoin(url, s) for s in re.findall(r"""<img[^>]+src=["']([^"']+\.(?:jpe?g|webp|png))""", page, re.I)
             if not re.search(r"logo|icon|avatar|flag|sprite|placeholder", s, re.I)]
    out["photos"] = list(dict.fromkeys(imgs))[:8]
    out["text"] = text
    for k in ("price", "beds", "baths", "size_sqft"):
        if k in out:
            out[k] = _int(round(out[k], 0)) if k != "price" else _int(out[k])
    return out


# ---------- what the model fills in, every value checked against the page ----------

SCHEMA = {"name": "properties", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {
    "items": {"type": "array", "items": {"type": "object", "additionalProperties": False,
              "required": ["url", "community", "type", "offering", "price", "currency", "beds", "baths", "size_sqft", "permit", "ref"],
              "properties": {"url": {"type": "string"}, "community": {"type": "string"}, "type": {"type": "string"},
                             "offering": {"type": "string", "enum": ["sale", "rent", ""]}, "price": {"type": "string"},
                             "currency": {"type": "string"}, "beds": {"type": "string"}, "baths": {"type": "string"},
                             "size_sqft": {"type": "string"}, "permit": {"type": "string"}, "ref": {"type": "string"}}}}}}}
FILL = ("community", "type", "offering", "price", "currency", "beds", "baths", "size_sqft", "permit", "ref")


def _on_page(v: str, text: str) -> bool:
    if not v:
        return False
    if re.fullmatch(NUM, v.strip()):
        n = _num(v)
        return any(_num(m) == n for m in re.findall(NUM, text))
    return norm(v) in norm(text)


def _main(p: dict) -> str:
    """The page from its title on (the menu above it is no help), bounded."""
    t, i = p["text"], p["text"].find(p["title"][:30]) if p["title"] else -1
    return t[max(0, i):][:3000] if i >= 0 else t[:3000]


def fill(office: Office, items: list[dict]) -> dict:
    """Ask the model only about the facts the code could not read; keep an answer only when the page shows it."""
    c = get("mbrand")
    need = [p for p in items if any(k not in p for k in ("community", "type", "price", "beds"))]
    calls = dropped = 0
    system = runner.instructions(c, office.log) + (
        "\nEach source is one property's page on the company's own website. For each, give the property's community or "
        "building, its type (apartment, villa...), whether it is for sale or rent, and its price, currency, bedrooms, "
        "bathrooms, size in sqft, permit or licence number and reference number. Copy each value exactly as the page "
        "writes it (numbers as digits). Leave a value empty when the page does not state it, or states several for this "
        "property. Ignore other properties the page shows (similar listings, recently viewed).")
    parts = [need[i:i + BATCH] for i in range(0, len(need), BATCH)]
    users = [runner.user_message("Read these property pages.", {p["url"]: _main(p) for p in part}) for part in parts]

    def ask(user):
        if not runner.has_model(c, system, user, schema=SCHEMA):
            return None
        try:
            return runner.call(c, system, user, schema=SCHEMA).data
        except Exception:
            return None

    with ThreadPoolExecutor(4) as pool:
        replies = list(pool.map(ask, users))
    for part, data in zip(parts, replies):
        if data is None:
            continue
        calls += 1
        by = {p["url"]: p for p in part}
        for row in data.get("items", []):
            p = by.get(row.get("url"))
            if not p:
                continue
            for k in FILL:
                v = str(row.get(k) or "").strip()
                if k in p or not v:
                    continue
                if k == "offering":
                    if re.search(rf"\b(for\s+)?{v}\b", p["text"], re.I):
                        p[k] = v
                    continue
                if k in ("type", "currency") and v.lower() in p["text"].lower():
                    p[k] = v
                elif _on_page(v, _main(p)):
                    p[k] = _int(_num(v)) if k in ("price", "beds", "baths", "size_sqft") else v
                else:
                    dropped += 1
            p["unsure"] = [k for k in p["unsure"] if k not in p]
    return {"calls": calls, "dropped": dropped}


# ---------- not twice ----------

def _digits(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def _words(s) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(s or "").lower()) if len(w) > 2}


def _agree(p: dict, x: dict) -> bool:
    """The same number of bedrooms, or one side doesn't say: a site can show one permit on several units."""
    return p.get("beds") is None or x.get("beds") is None or p["beds"] == x["beds"]


def match(p: dict, listings: list[dict]) -> dict | None:
    """The listing this page is, or None. The same page always is; the same permit or reference is when the bedrooms
    agree; otherwise the same beds, price and community or building. A different permit never is."""
    for x in listings:
        if x.get("page") and x["page"].rstrip("/") == p["url"].rstrip("/"):
            return x
    for x in listings:
        a, b = _digits(p.get("permit")), _digits(x.get("permit"))
        if a and b and a != b:
            continue
        if a and a == b and _agree(p, x):
            return x
        if p.get("ref") and str(p["ref"]).lower() in (str(x.get("ref", "")).lower(), str(x.get("site_ref", "")).lower()) and _agree(p, x):
            return x
        price = p.get("price") if (p.get("currency") or "").upper() in ("AED", "") else None
        if p.get("beds") is not None and price and x.get("beds") == p["beds"] and x.get("price_aed") == price:
            a, b = _words(p.get("community") or p["title"]), _words(f"{x.get('community', '')} {x.get('title', '')}")
            if a and len(a & b) / len(a) >= 0.5:
                return x
    return None


def shares_permit(p: dict, listings: list[dict]) -> list[str]:
    """Other listings showing this page's permit number for a different unit: worth a person's look."""
    a = _digits(p.get("permit"))
    return [x["ref"] for x in listings if a and a == _digits(x.get("permit")) and not _agree(p, x)]


def _differs(p: dict, x: dict) -> dict:
    out = {}
    price = p.get("price") if (p.get("currency") or "").upper() in ("AED", "") else None
    for k, ours in (("price", "price_aed"), ("beds", "beds"), ("permit", "permit")):
        v = price if k == "price" else p.get(k)
        if v not in (None, "") and x.get(ours) not in (None, "") and (_digits(v) != _digits(x[ours]) if k == "permit" else v != x[ours]):
            out[k] = {"diwan": x[ours], "website": v}
    return out


def _new_ref(p: dict, taken: set[str]) -> str:
    base = re.sub(r"[^A-Z0-9-]", "", str(p.get("ref") or "").upper())[:24] or "WEB-" + hashlib.sha1(p["url"].encode()).hexdigest()[:6].upper()
    ref, n = base, 1
    while ref in taken:
        n += 1
        ref = f"{base}-{n}"
    return ref


def run(office: Office, url: str, *, by: str) -> dict:
    """Find the site's properties, read them, add the new ones to the listings. The summary says what happened to each."""
    with httpx.Client(transport=learn.TRANSPORT, timeout=15, follow_redirects=True, headers=learn.UA) as c:
        f = find(url, client=c)
        if not f["pages"]:
            return {"ok": True, "found": 0, "added": [], "same": [], "differs": [], "skipped": [], "shared": [], "families": [], "read": f["read"],
                    "note": "No property pages were found on the site: its listings may be built in the browser, or kept on a portal."}
        cache, fetch = f["_cache"], f["_fetch"]
        missing = [u for u in f["pages"] if u not in cache]
        with ThreadPoolExecutor(6) as pool:
            for u, t in zip(missing, pool.map(fetch, missing)):
                if t:
                    cache[u] = t
    items = [read_page(cache[u], u) for u in f["pages"] if cache.get(u)]
    items = [p for p in items if _looks_like_one(p) or p.get("title")]
    model = fill(office, items)
    g = office.graph()
    existing = [n.props | {"ref": n.props.get("ref") or n.id.split(":", 1)[1]} for n in g.of("listing")]
    taken = {x["ref"] for x in existing}
    added, same, differs, skipped, shared = [], [], [], [], []
    for p in items:
        if p.get("price") is None or (p.get("beds") is None and p.get("size_sqft") is None):
            skipped.append({"url": p["url"], "title": p["title"], "why": "no single price, or no beds or size, on its page"})
            continue
        x = match(p, existing)
        if x:
            d = _differs(p, x)
            (differs if d else same).append({"url": p["url"], "title": p["title"], "ref": x["ref"], **({"fields": d} if d else {})})
            continue
        ref = _new_ref(p, taken)
        taken.add(ref)
        if others := shares_permit(p, existing):
            shared.append({"ref": ref, "title": p["title"], "url": p["url"], "permit": p["permit"], "with": others})
        cur = (p.get("currency") or "").upper()
        content = {"ref": ref, "title": p["title"], "community": p.get("community") or "", "type": p.get("type") or "",
                   "beds": p.get("beds"), "baths": p.get("baths"), "price_aed": p["price"] if cur in ("AED", "") else None,
                   "price": p["price"], "currency": cur, "size_sqft": p.get("size_sqft"), "permit": p.get("permit"),
                   "site_ref": p.get("ref"), "offering": p.get("offering") or "", "completion": p.get("completion"),
                   "furnishing": p.get("furnishing"), "photos": p.get("photos") or [], "page": p["url"], "status": "available",
                   "features": [], "agent": None, "source": "website", "country": business.get(office)["country_name"]}
        office.log.append("listing.added", actor=by, content={k: v for k, v in content.items() if v not in (None, "") or k in CRM})
        existing.append(content)
        added.append({"ref": ref, "title": p["title"], "url": p["url"], "price": p["price"], "currency": cur,
                      "permit": bool(p.get("permit")), "empty": [k for k in ("community", "type", "permit") if not p.get(k)]})
    office.log.append("listings.found", actor=by, content={"site": url, "found": len(items), "added": len(added), "same": len(same),
                                                           "differs": len(differs), "skipped": len(skipped), "shared_permit": len(shared), "model_calls": model["calls"]})
    return {"ok": True, "found": len(items), "families": f["families"], "read": f["read"], "added": added, "same": same,
            "differs": differs, "skipped": skipped, "shared": shared, "model": model, "refused": f["refused"]}
