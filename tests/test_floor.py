"""The 3D office's feed (Part 7): every event is accounted for, nothing moves without a cause, and roles are cut on the server."""
import pytest
from fastapi.testclient import TestClient

from diwan import access, demo, floor
from diwan.deal_desk import Ledger
from diwan.events import TYPES, EventLog
from diwan.office import Office


@pytest.fixture
def office(monkeypatch):
    import diwan.app as appmod
    monkeypatch.setenv("DIWAN_OFFLINE", "1")
    o = Office(EventLog(":memory:"))
    demo.seed(o)
    monkeypatch.setattr(appmod.S, "office", o)
    return o


def test_every_event_is_a_card_or_deliberately_not():
    assert TYPES == set(floor.ROUTES) | floor.QUIET
    assert not set(floor.ROUTES) & floor.QUIET


def test_nothing_moves_without_a_cause(office):
    demo.correction(office)
    g = office.graph()
    for e in office.log.list():
        if m := floor.message(e, g):
            assert m["caused_by"], e["type"]


def test_an_event_nobody_knows_falls_to_the_stuck_pile():
    m = floor.message({"id": 9, "type": "made.up", "at": "2026-11-01", "agent": "rania", "content": {}})
    assert m["stuck"] and m["caused_by"] == 9


def test_agents_sit_in_their_rooms():
    assert floor.room_of("screen") == floor.room_of("sof") == "comp"
    assert floor.room_of("rania") == "front" and floor.room_of("pay") == "fin"
    assert floor.room_of("nobody") is None


def test_the_ripple_matches_the_deal_desk(office):
    from datetime import date
    fid = demo.correction(office)
    g = office.graph()
    card = Ledger(g, date.today())._ripple(g.nodes[fid])
    r = floor.ripple(office, fid)
    for k in ("withdrawn", "approvals", "sent_back", "recalled", "other", "rooms", "compliance_first"):
        assert r[k] == card[k], k
    assert r["compliance_first"] and r["withdrawn"] == 2 and r["approvals"] == 1 and r["sent_back"] == 1 and r["other"] == 0
    assert "comp" in r["rooms"] and "ops" in r["untouched"] and not set(r["rooms"]) & set(r["untouched"])


def test_a_plain_fact_is_not_a_correction(office):
    with pytest.raises(KeyError):
        floor.ripple(office, "F1")


def test_the_ripple_keeps_its_events_off_the_loose_cards(office):
    n = len(office.log.list())
    fid = demo.correction(office)
    g, chain, seen = office.graph(), floor.Chain(), []
    for e in office.log.list(after=n):
        if m := floor.message(e, g):
            chain.mark(e, m)
            seen.append(m)
    assert seen[0]["ripple"] == fid
    assert all(m["in_ripple"] == fid for m in seen[1:])


def test_a_broker_sees_only_their_own_clients(office):
    o, g = office, office.graph()
    deal = g.deals()[0]
    deal.props["broker"] = "omar"
    m = {"card": "task", "text": "Karim Haddad wants a call", "deal": deal.deal, "record": "deal.html", "preview": {"kind": "typing", "lines": ["Karim"]}}
    brokers = [p for p in access.PEOPLE if access.department(p) == access.SALES]
    other = next(p for p in brokers if p != "omar")
    cut = floor.mask(m, other, g)
    assert "Karim" not in str(cut) and "preview" not in cut and cut["record"] == ""
    assert floor.mask(m, "omar", g)["text"] == m["text"]
    assert floor.mask(m, access.owner_id(), g) is m


def test_compliance_reasons_stay_with_compliance_and_the_owner(office):
    g = office.graph()
    m = {"card": "compliance", "text": "Payer looks wrong", "deal": None, "record": "deal.html", "preview": {"kind": "checklist", "lines": ["x"]}}
    staff = {access.department(p): p for p in access.PEOPLE if access.department(p)}
    assert floor.mask(m, staff[access.COMP], g)["text"] == m["text"]
    for dept in (access.SALES, access.FIN, access.OPS, access.MKT):
        cut = floor.mask(m, staff[dept], g)
        assert cut["text"] == "Compliance" and "preview" not in cut


def test_busy_paths_travel_as_one_stack():
    msgs = [{"id": i, "card": "task", "from": "sales", "to": ["deal"], "count": 1} for i in range(1, 8)]
    other = {"id": 20, "card": "money", "from": "fin", "to": ["deal"], "count": 1}
    out = floor.batch(msgs + [other])
    assert len(out) == 2 and out[0]["count"] == 7 and out[0]["stack"] == list(range(1, 8)) and out[1] == other
    assert len(floor.batch(msgs[:5])) == 5  # five on a path still fly apart


def test_monitors_show_the_events_own_words(office):
    fid = demo.correction(office)
    g = office.graph()
    sup = next(e for e in office.log.list() if e["type"] == "fact.superseded")
    pv = floor.message(sup, g)["preview"]
    assert pv["kind"] == "compare" and pv["new"] == g.nodes[fid].props["quote"] and pv["old"] == g.nodes[sup["content"]["id"]].props["quote"]


def test_pulses_stay_out_of_the_log_and_come_in_order(office):
    n = len(office.log.list())
    start = max((p["seq"] for p in floor.pulses(0)), default=0)
    floor.step("scribe", "read", "a task")
    floor.step("scribe", "write")
    got = floor.pulses(start)
    assert [p["step"] for p in got] == ["read", "write"] and all(p["caused_by"] for p in got) and got[0]["room"] == floor.room_of("scribe")
    assert len(office.log.list()) == n


def test_the_feed_and_its_lookups_need_a_sign_in(office, monkeypatch):
    import diwan.app as appmod
    c = TestClient(appmod.app)
    fid = demo.correction(office)
    monkeypatch.setenv("DIWAN_AUTH", "on")
    assert c.get(f"/api/floor/ripple/{fid}").status_code == 401
    assert c.get("/api/floor/stuck").status_code == 401
    monkeypatch.setenv("DIWAN_AUTH", "off")
    assert c.get(f"/api/floor/ripple/{fid}").json()["fact"] == fid
    assert c.get("/api/floor/ripple/F1").status_code == 404
