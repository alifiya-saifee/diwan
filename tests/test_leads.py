import hashlib
import hmac
import json
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo, inbox, leads
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import portals
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)
PH = "971501234567"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def cards(o):
    return o.graph().of("attention", status="open")


def notices_for(o, who):
    return [n["text"] for n in leads.notices(o.graph(), who)]


# ---------- assignment ----------

def test_new_leads_go_round_robin_to_brokers_on_shift_and_skip_the_away(office):
    leads.set_agent(office, "hamza", "away", True, by="layla")
    reception.message(office, "971500000001", "Hi", name_="A", now=NOON)
    reception.message(office, "971500000002", "Hi", name_="B", now=NOON)
    reception.message(office, "971500000003", "Hi", name_="C", now=NOON)
    owners = [office.graph().nodes[f"chat:97150000000{i}"].deal for i in (1, 2, 3)]
    assert [office.graph().nodes[f"deal:{d}"].props["broker"] for d in owners] == ["omar", "nadia", "omar"]
    assert any("New lead: A" in t for t in notices_for(office, "omar"))


def test_off_shift_brokers_get_nothing_while_someone_is_on(office):
    leads.set_agent(office, "omar", "shift", "06:00-11:00", by="layla")
    reception.message(office, PH, "Hi", name_="A", now=NOON)
    deal = office.graph().nodes[f"chat:{PH}"].deal
    assert office.graph().nodes[f"deal:{deal}"].props["broker"] == "hamza"
    with pytest.raises(ValueError):
        leads.set_agent(office, "omar", "shift", "9 to 5", by="layla")


# ---------- attention ----------

def test_a_call_request_is_a_card_on_the_owners_limit_for_the_broker_with_a_notice(office):
    reception.message(office, PH, "Hi", name_="Ali", now=NOON)
    reception.message(office, PH, "Can you call me please?", now=NOON)
    [c] = cards(office)
    assert c.props["kind"] == "call" and c.props["who"] == "omar"
    assert datetime.fromisoformat(c.props["due"]) == NOON + timedelta(minutes=10)
    assert any("Ali wants a call" in t for t in notices_for(office, "omar"))
    row = inbox.listing(office, view="attention", person="omar", now=NOON)[0]
    assert row["attention"]["kind"] == "call" and row["attention"]["minutes_left"] == 10


def test_a_card_leaves_only_with_a_recorded_action(office):
    reception.message(office, PH, "Hi", name_="Ali", now=NOON)
    reception.message(office, PH, "Is a discount possible?", now=NOON)
    [c] = cards(office)
    with pytest.raises(ValueError):
        leads.clear(office, c.id, "done", by="omar")
    with pytest.raises(ValueError):
        leads.clear(office, c.id, "not_needed", by="omar")
    leads.clear(office, c.id, "not_needed", by="omar", note="Spoke to him at the viewing")
    assert not cards(office)
    assert office.graph().nodes[c.id].props["note"] == "Spoke to him at the viewing"


def test_the_broker_replying_clears_the_card(office):
    reception.message(office, PH, "Hi", name_="Ali", now=NOON)
    reception.message(office, PH, "I want to speak to a person", now=NOON)
    reception.person_sends(office, PH, "Omar here, how can I help?", by="omar")
    assert not cards(office)
    assert office.graph().of("attention")[0].props["action"] == "messaged"


def test_writing_while_a_person_has_the_chat_raises_a_card_for_them(office):
    reception.message(office, PH, "Hi", name_="Ali", now=NOON)
    reception.hand_over(office, PH, to="nadia", by="nadia", reason="taken from the Inbox")
    assert not cards(office)  # taking a chat yourself is not a card
    reception.message(office, PH, "Are you there?", now=NOON)
    [c] = cards(office)
    assert c.props["who"] == "nadia"


def test_overdue_tells_the_owner_and_an_hour_puts_it_in_the_pool_to_claim(office):
    reception.message(office, PH, "Hi", name_="Ali", now=NOON)
    reception.message(office, PH, "Call me", now=NOON)
    [c] = cards(office)
    raised = datetime.fromisoformat(c.props["raised"])
    assert leads.sweep(office, raised + timedelta(minutes=9)) == []
    assert leads.sweep(office, raised + timedelta(minutes=11)) == [f"overdue {c.id}", f"moved {c.id} to hamza"]  # the client was promised a call
    assert any("Omar is late on Ali" in t for t in notices_for(office, "layla"))
    assert any("Omar is late on Ali" in t for t in notices_for(office, "rashid"))
    g = office.graph()
    assert g.nodes[c.id].props["who"] == "hamza" and g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"] == "hamza"
    assert any("wants a call" in t or "New lead" in t for t in notices_for(office, "hamza"))
    assert leads.sweep(office, raised + timedelta(minutes=12)) == []  # told once, and Hamza has a fresh limit
    with pytest.raises(ValueError):
        leads.claim(office, PH, by="nadia")
    later = raised + timedelta(minutes=61)
    assert leads.sweep(office, later) == [f"pooled {c.id}"]  # nobody acted within the hour: the Pool, as before
    assert inbox.listing(office, view="pool", now=later)[0]["phone"] == PH
    leads.claim(office, PH, by="nadia")
    g = office.graph()
    assert g.nodes[f"deal:{g.nodes[f'chat:{PH}'].deal}"].props["broker"] == "nadia" and g.nodes[c.id].props["who"] == "nadia"
    assert any("Nadia claimed Ali" in t for t in notices_for(office, "hamza"))


def test_notices_read(office):
    reception.message(office, PH, "Hi", name_="Ali", now=NOON)
    assert leads.notices(office.graph(), "omar")[0]["read"] is False
    leads.read_all(office, "omar")
    assert all(n["read"] for n in leads.notices(office.graph(), "omar"))


def test_notice_goes_to_the_brokers_whatsapp_with_the_approved_template(office, monkeypatch):
    sent = []
    monkeypatch.setenv("NOTIFY_TEMPLATE", "staff_alert")
    monkeypatch.setattr("diwan.providers.aisensy.available", lambda: True)
    monkeypatch.setattr("diwan.providers.aisensy.send_template", lambda *a: sent.append(a) or {"id": "x"})
    leads.set_agent(office, "omar", "phone", "+971 50 999 0000", by="omar")
    reception.message(office, PH, "Hi", name_="Ali", now=NOON)
    assert sent[0][:2] == ("971509990000", "staff_alert") and "New lead: Ali" in sent[0][2][0]
    assert leads.notices(office.graph(), "omar")[0]["via"] == "whatsapp"


# ---------- the catalog: the brokerage's own portal feed ----------

FEED = """<?xml version="1.0"?><list>
 <property><reference_number>PF-1</reference_number><permit_number>7100001</permit_number><title_en>Sea view 2BR</title_en>
   <price>2,450,000</price><bedroom>2</bedroom><property_type>AP</property_type><community>Dubai Marina</community>
   <agent><email>hamza@diwan.example</email><name>Hamza Ali</name></agent></property>
 <property><reference_number>PF-2</reference_number><title_en>Studio</title_en><price>650000</price><bedroom>studio</bedroom>
   <community>JLT</community></property>
</list>"""


def test_feed_sync_adds_maps_agents_keeps_unpermitted_unadvertised_and_marks_removed_off_market(office):
    s = leads.sync_listings(office, FEED)
    assert s == {"in_feed": 2, "added": 2, "changed": 0, "off_market": 0, "without_permit": 1, "waiting_for_portal": []}
    g = office.graph()
    pf1 = g.nodes["listing:PF-1"].props
    assert pf1["agent"] == "hamza" and pf1["type"] == "apartment" and pf1["price_aed"] == 2_450_000
    assert g.nodes["listing:PF-2"].props["beds"] == 0
    assert {n.props["ref"] for n in reception.advertisable(g)} >= {"PF-1"} and "PF-2" not in {n.props["ref"] for n in reception.advertisable(g)}
    assert leads.sync_listings(office, FEED)["added"] == 0  # nothing changed, nothing written
    s = leads.sync_listings(office, FEED.replace("2,450,000", "2,400,000").split("<property><reference_number>PF-2")[0] + "</list>")
    assert s["changed"] == 1 and s["off_market"] == 1
    assert office.graph().nodes["listing:PF-2"].status == "off-market"
    assert office.graph().nodes["listing:MC-1204"].status == "available"  # typed in by hand: untouched


def test_bad_feed_is_refused():
    with pytest.raises(portals.PortalError):
        portals.parse_feed("<not xml")


# ---------- portal enquiries ----------

LEAD = {"data": {"name": "Fatima Noor", "phone": "+971 55 123 4567", "message": "Is this still available? Please call me.",
                 "listing": {"reference": "MC-1204"}}}


def test_a_portal_enquiry_goes_to_the_listing_agent_as_a_call_and_rania_does_not_message_first(office):
    leads.set_agent(office, "omar", "shift", "09:00-21:00", by="layla")
    r = leads.portal_lead(office, portals.parse_lead("propertyfinder", LEAD), now=NOON)
    g = office.graph()
    assert r["chat"] == "971551234567" and g.nodes[f"deal:{r['deal']}"].props["broker"] == "omar"
    [c] = cards(office)
    assert c.props["kind"] == "call" and "Property Finder enquiry about Unit 1204, Marina Crest" in c.props["reason"]
    row = inbox.conversation(g, g.nodes["chat:971551234567"], NOON)
    assert row["source"] == "propertyfinder" and not row["window_open"]  # a portal message does not open WhatsApp's window
    assert not [m for m in g.nodes["chat:971551234567"].props["messages"] if m["type"] == "sent"]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(appmod.S, "office", Office(EventLog()))
    demo.seed(appmod.S.office)
    return TestClient(appmod.app)


def test_portal_webhook_needs_the_signature(client, monkeypatch):
    body = json.dumps(LEAD).encode()
    assert client.post("/api/portals/bayut/lead", content=body).status_code == 401  # no secret set: refuse everything
    monkeypatch.setenv("PORTAL_SECRET_BAYUT", "s3cret")
    assert client.post("/api/portals/bayut/lead", content=body, headers={"x-signature": "nope"}).status_code == 401
    sig = hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    r = client.post("/api/portals/bayut/lead", content=body, headers={"x-signature": f"sha256={sig}", "content-type": "application/json"})
    assert r.status_code == 200 and r.json()["chat"] == "971551234567"
    assert client.post("/api/portals/bayut/lead?token=s3cret", json={"name": "No phone"}).status_code == 422


def test_api_attention_clear_and_assign(client):
    client.post("/api/chats/incoming", json={"phone": PH, "name": "Ali", "text": "call me"})
    card = client.get(f"/api/chats/{PH}").json()["attention"]
    assert card and card["kind"] == "call"
    assert client.post(f"/api/attention/{card['id']}/clear", json={"action": "not_needed", "by": "omar"}).status_code == 422
    assert client.post(f"/api/attention/{card['id']}/clear", json={"action": "called", "by": "omar"}).status_code == 200
    assert client.get(f"/api/chats/{PH}").json()["attention"] is None
    assert client.post(f"/api/chats/{PH}/assign", json={"to": "priya", "by": "layla"}).status_code == 422
    assert client.post(f"/api/chats/{PH}/assign", json={"to": "nadia", "by": "layla"}).status_code == 200
    assert client.get(f"/api/chats/{PH}").json()["broker"] == "nadia"
    assert client.get("/api/notices/nadia").json()["unread"] >= 1


def test_feed_sync_endpoint_reads_the_brokerages_feed(client, monkeypatch):
    monkeypatch.setenv("LISTING_FEED_URL", "https://example.test/feed.xml")
    monkeypatch.setattr(portals, "TRANSPORT", httpx.MockTransport(lambda req: httpx.Response(200, content=FEED.encode())))
    r = client.post("/api/listings/sync")
    assert r.status_code == 200 and r.json()["added"] == 2


# ---------- handoff.md issue 2: the feed sync keeps what people decided ----------

def _pf1(o):
    return o.graph().nodes["listing:PF-1"]


def test_sync_keeps_a_status_set_by_a_person_and_asks_to_take_it_off_the_portals(office):
    from diwan import knowledge
    leads.sync_listings(office, FEED)
    knowledge.edit(office, "listing:PF-1", {"status": "reserved"}, by="layla", why="deposit paid")
    s = leads.sync_listings(office, FEED)
    assert _pf1(office).status == "reserved" and "PF-1" in s["waiting_for_portal"]
    assert _pf1(office).props["portal_pending"]["status"] == {"ours": "reserved", "portal": "advertised"}
    tasks = [t for t in office.graph().of("task") if "PF-1" in t.props["action"]]
    assert len(tasks) == 1 and tasks[0].props["needs_person"] == "hamza" and "take it off the portals" in tasks[0].props["action"]
    leads.sync_listings(office, FEED)  # the same again: no second task
    assert len([t for t in office.graph().of("task") if "PF-1" in t.props["action"]]) == 1
    assert "PF-1" not in {n.props["ref"] for n in reception.advertisable(office.graph())}  # never offered while reserved


def test_an_accepted_price_waits_for_the_portal_then_clears_and_the_portal_can_still_move_it(office):
    from diwan import knowledge
    leads.sync_listings(office, FEED)
    p = knowledge.edit(office, "listing:PF-1", {"price_aed": 2_350_000}, by="hamza", why="seller agreed")["proposal"]
    knowledge.decide(office, p, accept=True, by="layla")
    s = leads.sync_listings(office, FEED)  # the portal still says 2,450,000
    n = _pf1(office)
    assert n.props["price_aed"] == 2_350_000 and n.props["portal_pending"]["price_aed"] == {"ours": 2_350_000, "portal": 2_450_000}
    assert "PF-1" in s["waiting_for_portal"]
    assert knowledge.item(office.graph(), n)["listing"]["portal_pending"]  # the Catalog page reads this
    assert any("AED 2,350,000 here, AED 2,450,000 on the portal" in t for t in notices_for(office, "hamza"))
    leads.sync_listings(office, FEED.replace("2,450,000", "2,350,000"))  # the portal caught up
    assert _pf1(office).props["price_aed"] == 2_350_000 and _pf1(office).props["portal_pending"] == {}
    leads.sync_listings(office, FEED.replace("2,450,000", "2,300,000"))  # changed on the portal itself: the feed wins
    assert _pf1(office).props["price_aed"] == 2_300_000 and _pf1(office).props["portal_pending"] == {}


def test_a_listing_back_in_the_feed_is_available_again(office):
    leads.sync_listings(office, FEED)
    leads.sync_listings(office, FEED.split("<property><reference_number>PF-2")[0] + "</list>")
    assert office.graph().nodes["listing:PF-2"].status == "off-market"
    leads.sync_listings(office, FEED)
    assert office.graph().nodes["listing:PF-2"].status == "available"


# ---------- the demo catalog and what a feed carries ----------

def test_feed_photos_location_and_the_demo_catalog():
    from diwan import demo, knowledge
    from diwan.providers import portals
    xml = """<list><property><reference_number>X-1</reference_number><permit_number>P1</permit_number><offering_type>RR</offering_type>
      <title_en>Unit 1</title_en><community>Dubai Marina</community><bedroom>1</bedroom><price>90000</price>
      <geopoints>55.14,25.08</geopoints><size>800 sqft</size><photos><photo>https://cdn.example/a.jpg</photo>
      <photo>javascript:alert(1)</photo></photos><images><image><url>https://cdn.example/b.jpg</url></image></images></property></list>"""
    it = portals.parse_feed(xml)[0]
    assert it["photos"] == ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"]  # only web addresses
    assert it["geo"] == (25.08, 55.14) and it["offering"] == "rent" and it["size_sqft"] == 800  # "lng,lat" read the right way round
    o = Office(EventLog())
    demo.company(o)
    demo.catalog(o)
    demo.catalog(o)  # loaded once
    g = o.graph()
    assert len(g.of("listing")) == 39 and sum(e["type"] == "listings.synced" for e in o.log.list()) == 1
    mg = knowledge.item(g, g.nodes["listing:MC-1204"])["listing"]
    assert mg["photos"][0] == "/web/img/demo/marina.jpg" and mg["lat"] and mg["agent"] == "omar" and mg["offering"] == "sale"
    # one area match everywhere: "villa in JVC" is Jumeirah Village Circle, not the community called "The Villa"
    assert knowledge.areas_in(g, "Any villa in JVC?") == {"jumeirah village circle"}
    assert knowledge.areas_in(g, "something on the Palm") == {"palm jumeirah"}
    assert {i["listing"]["community"] for i in knowledge.search(g, "villa in Palm Jumeirah", tabs={"listing"})} == {"Palm Jumeirah"}
    # a buyer never sees a yearly rental, a tenant never a sale
    sale = knowledge.search(g, "2 bed in Dubai Marina", tabs={"listing"}, offering="sale")
    rent = knowledge.search(g, "studio to rent in Dubai Marina", tabs={"listing"})
    assert sale and all(i["listing"]["offering"] == "sale" for i in sale)
    assert [i["listing"]["ref"] for i in rent] == ["DR-103"]
