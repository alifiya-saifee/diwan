"""The website's properties: found by their shape on two differently built sites, read in code, never added twice."""
import json

import httpx

from diwan import learn, sitelistings
from diwan.agents import runner
from diwan.events import EventLog
from diwan.office import Office


def page(title, body, head=""):
    return f"<html><head><title>{title} - Acme Homes</title>{head}</head><body><nav>Home Buy Rent Price guide</nav><h1>{title}</h1>{body}</body></html>"


LABELLED = {  # site A: facts as "Label: value" text, like many WordPress themes
    f"/homes/h{i}": page(f"Sunny {i}BR in Palm Grove", f"<p>Price: AED {i},200,000 Beds: {i} Baths: {i + 1} Area: {i}00 sqft "
                                                       f"Reference No: AC-{i}00 Permit (Trakheesi) 7100{i}</p>"
                                                       f"<div>Similar homes: AED 9,999,000 · 5 Beds</div>")
    for i in range(1, 6)
}
LABELLED["/homes/h5"] = page("Two prices", "<p>Price: AED 1,000,000</p><p>Price: AED 2,000,000 Beds: 2</p>")  # which one? neither
JSONLD = {  # site B: schema.org data and a table, different words, no "Label:" text at all
    f"/listings/x{i}": page(f"Garden villa {i}", f"<table><tr><th>Bedrooms</th><td>{i + 2}</td></tr><tr><th>Location</th><td>Olive Hills</td></tr></table>",
                            head='<script type="application/ld+json">' + json.dumps({"@type": "Offer", "price": 3000000 + i, "priceCurrency": "AED"}) + "</script>")
    for i in range(1, 5)
}
BLOG = {f"/blog/post{i}": page(f"Market news {i}", "<p>Prices rose in many areas this year.</p>") for i in range(1, 6)}


def site(pages):
    home = page("Acme Homes", " ".join(f'<a href="{u}">x</a>' for u in pages))

    def handle(req):
        path = req.url.path.rstrip("/") or "/"
        if path == "/robots.txt":
            return httpx.Response(404)
        if path == "/":
            return httpx.Response(200, text=home, headers={"content-type": "text/html"})
        return httpx.Response(200, text=pages[path], headers={"content-type": "text/html"}) if path in pages else httpx.Response(404)
    return httpx.MockTransport(handle)


def test_finds_property_pages_by_shape_on_differently_built_sites(monkeypatch):
    monkeypatch.setattr(learn, "TRANSPORT", site(LABELLED | JSONLD | BLOG))
    with httpx.Client(transport=learn.TRANSPORT, base_url="https://acme.test") as c:
        f = sitelistings.find("https://acme.test", client=c)
    assert sorted(f["families"]) == ["/homes", "/listings"]  # the blog is a family of pages, but not of properties
    assert len(f["pages"]) == 9


def test_reads_labelled_text_and_schema_data_and_leaves_a_conflict_empty():
    a = sitelistings.read_page(LABELLED["/homes/h2"], "https://acme.test/homes/h2")
    assert (a["title"], a["price"], a["currency"], a["beds"], a["baths"], a["size_sqft"]) == ("Sunny 2BR in Palm Grove", 2200000, "AED", 2, 3, 200)
    assert (a["ref"], a["permit"]) == ("AC-200", "71002")  # the permit has no colon on the page
    b = sitelistings.read_page(JSONLD["/listings/x1"], "https://acme.test/listings/x1")
    assert (b["price"], b["beds"], b["community"]) == (3000001, 3, "Olive Hills")
    two = sitelistings.read_page(LABELLED["/homes/h5"], "https://acme.test/homes/h5")
    assert "price" not in two and "price" in two["unsure"]  # never picks one of two prices


def test_adds_new_ones_and_never_twice(monkeypatch, tmp_path):
    monkeypatch.setattr(learn, "TRANSPORT", site(LABELLED | JSONLD | BLOG))
    o = Office(EventLog(str(tmp_path / "o.db")))
    o.log.append("listing.added", actor="omar", content={"ref": "OLD-1", "title": "Palm Grove 1BR", "beds": 1, "price_aed": 1200000, "permit": "71001"})
    o.log.append("listing.added", actor="omar", content={"ref": "OLD-3", "title": "Palm Grove 3BR", "beds": 3, "price_aed": 3000000, "permit": "71003"})
    r = sitelistings.run(o, "https://acme.test", by="maya")
    assert [x["ref"] for x in r["same"]] == ["OLD-1"]
    assert r["differs"] == [{"url": "https://acme.test/homes/h3", "title": "Sunny 3BR in Palm Grove", "ref": "OLD-3",
                             "fields": {"price": {"diwan": 3000000, "website": 3200000}}}]
    assert o.graph().nodes["listing:OLD-3"].props["price_aed"] == 3000000  # shown, not overwritten
    assert sorted(x["ref"] for x in r["added"]) == ["AC-200", "AC-400"] + sorted(x["ref"] for x in r["added"] if x["ref"].startswith("WEB-"))
    assert [x["url"] for x in r["skipped"]] == ["https://acme.test/homes/h5"]
    new = o.graph().nodes["listing:AC-200"].props
    assert (new["source"], new["page"], new["permit"], new["price_aed"]) == ("website", "https://acme.test/homes/h2", "71002", 2200000)
    again = sitelistings.run(o, "https://acme.test", by="maya")
    assert again["added"] == [] and len(again["same"]) == len(r["added"]) + 1


def test_a_different_permit_is_never_the_same_property():
    p = {"url": "u", "title": "Palm Grove 2BR", "beds": 2, "price": 2200000, "currency": "AED", "permit": "71002"}
    assert sitelistings.match(p, [{"ref": "A", "title": "Palm Grove 2BR", "beds": 2, "price_aed": 2200000, "permit": "99999"}]) is None
    assert sitelistings.match(p, [{"ref": "B", "title": "Palm Grove 2BR", "beds": 2, "price_aed": 2200000, "permit": None}])["ref"] == "B"


def test_the_model_only_keeps_what_the_page_shows(monkeypatch, tmp_path):
    o = Office(EventLog(str(tmp_path / "o.db")))
    p = sitelistings.read_page(LABELLED["/homes/h2"], "https://acme.test/homes/h2")
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: True)
    reply = {"items": [{"url": p["url"], "community": "Palm Grove", "type": "Penthouse", "offering": "", "price": "", "currency": "",
                        "beds": "", "baths": "", "size_sqft": "", "permit": "", "ref": ""}]}
    monkeypatch.setattr(runner, "call", lambda *a, **k: type("R", (), {"data": reply})())
    m = sitelistings.fill(o, [p])
    assert p["community"] == "Palm Grove" and "type" not in p and m == {"calls": 1, "dropped": 1}  # no penthouse on the page


def test_one_permit_on_two_units_is_two_listings_and_flagged():
    p = {"url": "u2", "title": "Palm Grove 3BR", "beds": 3, "price": 3100000, "currency": "AED", "permit": "71002"}
    old = [{"ref": "A", "title": "Palm Grove 4BR", "beds": 4, "price_aed": 5000000, "permit": "71002", "page": "u1"}]
    assert sitelistings.match(p, old) is None and sitelistings.shares_permit(p, old) == ["A"]
    assert sitelistings.match(p | {"beds": 4, "price": 4900000}, old)["ref"] == "A"  # same permit, same beds: one unit, new price


def test_a_listing_from_the_site_has_every_field_the_crm_reads(monkeypatch, tmp_path):
    monkeypatch.setattr(learn, "TRANSPORT", site({f"/homes/h{i}": page(f"Flat {i}", f"<p>Price: AED {i},000,000 Beds: {i}</p>") for i in range(1, 5)}))
    o = Office(EventLog(str(tmp_path / "o.db")))
    r = sitelistings.run(o, "https://acme.test", by="maya")
    props = o.graph().nodes[f"listing:{r['added'][0]['ref']}"].props
    assert all(k in props for k in sitelistings.CRM) and props["community"] == ""  # not on the page: empty, but there
