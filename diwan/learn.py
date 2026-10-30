"""The AI builds the company's knowledge from public pages: it reads them, writes knowledge cards and a brand draft,
and every card must carry a quote that appears word for word on the page it cites, or it is dropped. Cards are saved
as proposed; a person confirms them on the Knowledge page before Rania, Nova or the writers use them.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from diwan import brand
from diwan.agents import runner
from diwan.agents.charters import get
from diwan.office import Office
from diwan.pack import Action, Evidence, Pack, norm

TRANSPORT: httpx.BaseTransport | None = None  # tests swap in a fake
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"}
MAX_CHARS = 12_000   # per page: enough for a profile page, bounded so one call stays cheap
TOPICS = ["about", "services", "areas", "people", "contact", "track record", "policies"]

SITE_PAGES = 20      # pages read from one site at most
BUDGET = 60_000      # characters sent in one call, shared by the pages
PRIORITY = re.compile(r"about|product|service|solution|pricing|price|contact|team|compan|faq|case|industr|what-we|who-we", re.I)
SKIP = re.compile(r"\.(pdf|jpe?g|png|gif|svg|webp|zip|mp4|mov|docx?|xlsx?)$|/(login|signin|cart|checkout|account|wp-admin|feed)\b", re.I)

SCHEMA = {"name": "company", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["company", "cards", "brand", "products"],
          "properties": {
              "company": {"type": "string"},
              "products": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                      "required": ["title", "kind", "what", "features", "price", "currency", "quote", "source"],
                                                      "properties": {"title": {"type": "string"}, "kind": {"type": "string", "enum": ["product", "service"]},
                                                                     "what": {"type": "string"}, "features": {"type": "array", "items": {"type": "string"}},
                                                                     "price": {"type": "string"}, "currency": {"type": "string"},
                                                                     "quote": {"type": "string"}, "source": {"type": "string"}}}},
              "cards": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                   "required": ["topic", "title", "text", "quote", "source"],
                                                   "properties": {"topic": {"type": "string", "enum": TOPICS}, "title": {"type": "string"},
                                                                  "text": {"type": "string"}, "quote": {"type": "string"},
                                                                  "source": {"type": "string"}}}},
              "brand": {"type": "object", "additionalProperties": False, "required": list(brand.FIELDS),
                        "properties": {k: {"type": "string"} for k in brand.FIELDS}}}}}


def page_text(html: str) -> str:
    html = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    return re.sub(r"\s+", " ", text).strip()


def _host(u: str) -> str:
    return urlparse(u).netloc.lower().removeprefix("www.")


def crawl(url: str, limit: int = SITE_PAGES) -> dict:
    """The company's own pages, found by following links from its home page: same site only, the site's robots.txt
    respected, the pages a company profile usually lives on (about, products, services, contact...) first. Nothing is
    read for knowledge here; the person picks from this list. {ok, pages: [{url, title}], refused}."""
    from urllib.robotparser import RobotFileParser
    from urllib.parse import urldefrag, urljoin
    url = url.strip()
    if not url:
        raise ValueError("Give the website's address.")
    if not url.startswith("http"):
        url = "https://" + url
    host = _host(url)
    if not host or "." not in host:
        raise ValueError(f"{url} is not a web address.")
    robots = RobotFileParser()
    with httpx.Client(transport=TRANSPORT, timeout=15, follow_redirects=True, headers=UA) as c:
        try:
            r = c.get(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
            robots.parse(r.text.splitlines() if r.status_code == 200 else [])
        except httpx.HTTPError:
            robots.parse([])
        from concurrent.futures import ThreadPoolExecutor

        def get(u: str):
            try:
                return c.get(u)
            except httpx.HTTPError:
                return None

        seen, queue, pages, refused, found = set(), [url], [], [], set()
        with ThreadPoolExecutor(6) as pool:
            while queue and len(pages) < limit:
                queue.sort(key=lambda u: (not PRIORITY.search(urlparse(u).path), len(urlparse(u).path)))
                batch = []
                while queue and len(batch) < 6:  # six pages at a time, the profile pages first
                    u = queue.pop(0)
                    if u in seen:
                        continue
                    seen.add(u)
                    (batch if robots.can_fetch("*", u) else refused).append(u)
                for u, r in zip(batch, pool.map(get, batch)):
                    if r is None or r.status_code >= 400 or "html" not in r.headers.get("content-type", "html") or len(pages) >= limit:
                        continue
                    final = str(r.url).rstrip("/")
                    if final in found:
                        continue  # a redirect to a page already read
                    found.add(final)
                    title = re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)
                    pages.append({"url": str(r.url), "title": re.sub(r"\s+", " ", title.group(1)).strip()[:90] if title else urlparse(u).path or "/"})
                    for href in re.findall(r"""<a[^>]+href=["']([^"'#]+)""", r.text, re.I):
                        nxt = urldefrag(urljoin(str(r.url), href))[0].split("?")[0].rstrip("/")
                        if nxt.startswith("http") and _host(nxt) == host and not SKIP.search(nxt) and nxt not in seen:
                            queue.append(nxt)
    if not pages:
        raise ValueError(f"Nothing could be read at {url}: the site refused, or it is built in the browser. Paste the pages' text instead.")
    return {"ok": True, "pages": pages, "refused": refused[:10]}


def fetch(urls: list[str]) -> tuple[dict[str, str], list[str]]:
    """{url: text} for the pages that could be read, and why the others could not."""
    pages, problems = {}, []
    with httpx.Client(transport=TRANSPORT, timeout=20, follow_redirects=True, headers=UA) as c:
        for u in urls:
            u = u.strip()
            if not u:
                continue
            if not urlparse(u).scheme.startswith("http"):
                problems.append(f"{u}: not a web address")
                continue
            try:
                r = c.get(u)
            except httpx.HTTPError as e:
                problems.append(f"{u}: could not connect ({type(e).__name__})")
                continue
            text = page_text(r.text)[:max(2_000, min(MAX_CHARS, BUDGET // max(1, len(urls))))]  # many pages share one call's budget
            if r.status_code >= 400:
                problems.append(f"{u}: the site refused ({r.status_code})")
            elif len(text) < 200:
                problems.append(f"{u}: no readable text (the page is probably built in the browser)")
            else:
                pages[u] = text
    return pages, problems


def learn(office: Office, urls: list[str] | None = None, *, documents: dict[str, str] | None = None, by: str = "maya", company: str = "") -> dict:
    """Read public pages and/or documents a person pasted (a company profile, a brochure), propose knowledge cards, each
    proven by a quote from its source, and a brand draft. One model call."""
    pages, problems = fetch(urls or [])
    for name, text in (documents or {}).items():
        text = re.sub(r"\s+", " ", text or "").strip()[:MAX_CHARS * 2]
        if len(text) >= 200:
            pages[name] = text
        elif text:
            problems.append(f"{name}: too short to learn from")
    if not pages:
        return {"needs": "Nothing could be read: " + ("; ".join(problems) or "give a web address or paste a document"), "problems": problems}
    c = get("mbrand")
    system = runner.instructions(c, office.log) + (
        "\nYou are learning about one company from public pages. Write in the `company` format.\n"
        "cards: 8 to 15 facts about this company only (pages may also list other agencies or listings: ignore those). Each card has a "
        "short title, one or two plain sentences, `quote`: 5 to 25 words copied exactly, character for character, from the page that "
        "supports it, and `source`: that page's address or document name exactly as given. Never state anything the pages do not say.\n"
        "brand: the brand profile drawn from how the company describes itself; leave a field empty when the pages say nothing about it.\n"
        "products: each product or service this company itself sells, as the pages describe it: title, kind, what it is in one sentence, "
        "its features as the pages list them, price and currency only when a page shows them (else empty), a 5 to 25 word quote copied "
        "exactly from the page that describes it, and that page as source. None that the pages do not describe.")
    user = runner.user_message(f"Learn about {company or 'the company these pages describe'}.", pages)
    if not runner.has_model(c, system, user, schema=SCHEMA):
        return {"needs": "A model (META_API_KEY), or this month's budget, to read the pages.", "problems": problems}
    data = runner.call(c, system, user, schema=SCHEMA).data
    g = office.graph()
    have = {n.props["title"].lower() for n in g.of("knowledge")}
    kept, dropped, ids = [], [], []
    for card in data.get("cards", []):
        src = next((u for u in pages if u.rstrip("/") == card["source"].rstrip("/")), None)
        if not src or not card["quote"].strip() or norm(card["quote"]) not in norm(pages[src]):
            dropped.append({"title": card["title"], "why": "its quote is not on the page it cites" if src else "it cites a page that was not read"})
            continue
        if card["title"].lower() in have:
            continue
        kid = office.add_knowledge(card["topic"], card["title"], card["text"], by="mbrand", confirmed=False, source=src)
        ids.append(kid)
        kept.append(card | {"id": kid})
    runner.submit(office.log, c, Pack(f"learn-{len(ids)}", "mbrand",
                                      f"Read {len(pages)} page{'s' if len(pages) != 1 else ''} about {data.get('company') or company}: proposed {len(kept)} knowledge "
                                      f"card{'s' if len(kept) != 1 else ''}, each with its quote; dropped {len(dropped)} that the pages did not prove.",
                                      evidence=[Evidence(k["quote"], next(u for u in pages if u.rstrip('/') == k["source"].rstrip('/'))) for k in kept],
                                      actions=[Action("draft", "Knowledge cards to confirm")]),
                  sources=pages)
    from diwan import products
    found, nope = [], []
    for item in data.get("products", []):
        src = next((u for u in pages if u.rstrip("/") == item["source"].rstrip("/")), None)
        if not src or not item["quote"].strip() or norm(item["quote"]) not in norm(pages[src]):
            nope.append({"title": item["title"], "why": "its quote is not on the page it cites" if src else "it cites a page that was not read"})
            continue
        price = re.sub(r"[^\d.]", "", item.get("price") or "")
        found.append({"title": item["title"], "kind": item["kind"], "what": item["what"], "features": item["features"],
                      "price": price if price and price.replace(".", "", 1).isdigit() else "", "currency": item.get("currency", ""), "page": src})
    new = products.propose(office, found, by="mbrand")
    return {"company": data.get("company") or company, "pages": list(pages), "problems": problems, "proposed": kept, "dropped": dropped + nope,
            "products": [products.get(office, r) for r in new],
            "brand": {k: (data.get("brand", {}).get(k) or "").strip() for k in brand.FIELDS}, "by": "Brand brain (Muse Spark)"}
