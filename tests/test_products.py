"""What the business sells, when it is not a property: products from its own website, confirmed by a person, written
for like a listing; the permit is a setting, not an assumption."""
import httpx
import pytest

from diwan import business, demo, learn, products
from diwan.agents import qa, rhythm, runner, studio
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers.chat import Reply


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    business.save(o, {"industry": "Robotics", "country": "AE", "city": "Dubai", "permit": "no"}, by="maya")
    return o


def test_a_product_is_saved_checked_and_only_used_once_confirmed(office):
    with pytest.raises(ValueError, match="not a number"):
        products.save(office, {"title": "D1", "price": "call us"}, by="maya")
    ref = products.propose(office, [{"title": "Delivery robot D1", "kind": "product", "what": "Carries plates to tables", "features": "3 trays, 8 hours, lidar",
                                     "price": "45,000", "currency": "AED", "page": "https://x.ae/d1"}], by="mbrand")[0]
    assert ref == "P-DELIVERY-ROBOT-D1" and ref not in products.items(office) and products.get(office, ref)["status"] == "proposed"
    assert products.propose(office, [{"title": "delivery robot d1"}], by="mbrand") == []  # already known
    products.save(office, {"status": "confirmed"}, by="maya", ref=ref)
    p = products.items(office)[ref]
    assert p["features"] == ["3 trays", "8 hours", "lidar"] and p["price"] == 45000
    assert any(x["ref"] == ref for x in rhythm.listings(office))  # the plan can pick it


def test_a_product_goes_through_the_studio_without_a_permit_when_none_is_needed(office):
    ref = products.save(office, {"title": "Delivery robot D1", "what": "Carries plates to tables", "features": ["3 trays", "8 hours battery", "lidar"],
                                 "price": "45000", "currency": "AED"}, by="maya")
    studio.run_now(office, ref)
    req = next(n for n in office.graph().of("request", status="open") if n.props.get("kind") == "use_script")
    sc = studio.script_options(office, req.props["text"])[0]
    assert sc["ref"] == ref and "Delivery robot D1" in " ".join([sc["hook_en"], *sc["lines_en"]]) and "AED 45,000." in sc["lines_en"]
    assert not any("permit" in x.lower() for x in sc["lines_en"])
    studio.approve_script_now(office, ref, choice=sc["id"])
    text = studio.made(office, "post text", ref)["text"]
    assert "Delivery robot D1" in text and "AED 45,000" in text and "Permit" not in text
    assert studio.permit_check(office, ref, {"text": text}, None)
    assert not studio.permit_check(office, ref, {"text": text + " Now AED 39,000!"}, None)  # a price not on the product is still held
    film = studio.made(office, "film list", ref)
    assert film["shots"][-1] == "End on the price card (added in editing)"


def test_the_permit_is_required_when_the_business_says_so(office):
    business.save(office, {"permit": "yes"}, by="maya")
    ref = products.save(office, {"title": "Delivery robot D1", "features": ["lidar"]}, by="maya")
    studio.run_now(office, ref)
    assert any("no permit number" in e["content"]["needs"] for e in office.log.list() if e["type"] == "step.blocked")
    with pytest.raises(business.Invalid):
        business.save(office, {"permit": "maybe"}, by="maya")


def test_the_arabic_hook_is_checked_only_when_arabic_is_a_language_we_post_in(office):
    sc = {"id": "C1", "hook_en": "Meet D1", "hook_ar": "", "lines_en": ["a", "b", "c", "d", "Message us."]}
    names = lambda: {f["check"] for f in qa.review(office, "script", "MC-1204", sc, cause=None, attempt=1)}  # noqa: E731
    assert "script-arabic" not in names()
    business.save(office, {"languages": "English, Arabic"}, by="maya")
    assert "script-arabic" in names()


def site(pages: dict[str, str], robots: str = ""):
    def handle(req: httpx.Request):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        body = pages.get(req.url.path)
        return httpx.Response(200, text=body, headers={"content-type": "text/html"}) if body is not None else httpx.Response(404, text="")
    return httpx.MockTransport(handle)


def test_the_site_is_read_from_its_home_page_same_site_only_and_robots_txt_respected(monkeypatch):
    home = '<title>Alpha Robots</title><a href="/about">About</a><a href="/products/d1">D1</a><a href="/private/x">x</a>' \
           '<a href="https://other.com/p">elsewhere</a><a href="/brochure.pdf">pdf</a><a href="/blog/post-1">blog</a>'
    monkeypatch.setattr(learn, "TRANSPORT", site({"/": home, "/about": "<title>About us</title>", "/products/d1": "<title>D1</title>",
                                                   "/private/x": "<title>x</title>", "/blog/post-1": "<title>Post</title>"},
                                                  robots="User-agent: *\nDisallow: /private"))
    r = learn.crawl("alpharobots.ae")
    urls = [p["url"] for p in r["pages"]]
    assert urls[0].rstrip("/") == "https://alpharobots.ae" and set(urls[1:3]) == {"https://alpharobots.ae/about", "https://alpharobots.ae/products/d1"}  # profile pages first
    assert "https://alpharobots.ae/blog/post-1" in urls and not any("other.com" in u or "pdf" in u or "private" in u for u in urls)
    assert r["refused"] == ["https://alpharobots.ae/private/x"] and r["pages"][1]["title"] in ("About us", "D1")
    with pytest.raises(ValueError):
        learn.crawl("not a site")


def test_products_on_the_pages_are_proposed_only_with_a_quote_from_their_page(office, monkeypatch):
    page = "<p>" + "Alpha Robots builds robots in Dubai. " * 10 + "The D1 delivery robot carries three trays for eight hours. </p>"
    monkeypatch.setattr(learn, "TRANSPORT", site({"/d1": page}))
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: True)
    reply = {"company": "Alpha Robots", "cards": [], "brand": {}, "products": [
        {"title": "D1 delivery robot", "kind": "product", "what": "A delivery robot", "features": ["three trays", "eight hours"], "price": "", "currency": "",
         "quote": "The D1 delivery robot carries three trays for eight hours.", "source": "https://alpharobots.ae/d1"},
        {"title": "Made-up robot", "kind": "product", "what": "x", "features": [], "price": "", "currency": "", "quote": "not on the page at all", "source": "https://alpharobots.ae/d1"}]}
    monkeypatch.setattr(runner, "call", lambda *a, **k: Reply(reply, {}))
    monkeypatch.setattr(runner, "submit", lambda *a, **k: None)
    r = learn.learn(office, ["https://alpharobots.ae/d1"], by="maya")
    assert [p["title"] for p in r["products"]] == ["D1 delivery robot"] and r["products"][0]["status"] == "proposed"
    assert any(d["title"] == "Made-up robot" for d in r["dropped"])
