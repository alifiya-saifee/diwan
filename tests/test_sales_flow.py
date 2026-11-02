"""The owner's rules for the client's journey, 2 Nov: an agent confirms a viewing, Compliance starts when there is a deal, and offers are on the record."""
from datetime import datetime, timedelta

import pytest

from diwan import demo, desk_stages, inbox, offers, qualify
from diwan.agents import finance, frontdesk, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.slots import DUBAI

PH, WHO = "971507771001", "Layth Mansour"


@pytest.fixture
def office(monkeypatch):
    monkeypatch.setattr(reception, "agent_confirms", lambda g: not __import__("diwan.sales", fromlist=["settings"]).settings(g).get("rania_books"))
    o = Office(EventLog(":memory:"))
    demo.seed(o) if hasattr(demo, "seed") else None
    return o


def next_week():
    return (datetime.now(DUBAI) + timedelta(days=7)).replace(hour=16, minute=0, second=0, microsecond=0)


def lead(o, *said):
    for t in said or ("Hi, I'm looking to buy a villa in JVC",):
        r = reception.message(o, PH, t, name_=WHO)
    return r


def deal(o):
    return o.graph().nodes[f"chat:{PH}"].deal


def listing(o):
    return next(iter(o.graph().of("listing", status="available")))


def test_rania_notes_a_viewing_and_books_nothing(office):
    lead(office)
    d, n = deal(office), listing(office)
    text, refs = reception.book(office, PH, d, n, next_week(), datetime.now(DUBAI), 1, False)
    assert "will talk to you" in text and "Booked" not in text and refs == [n.id]
    g = office.graph()
    assert not g.of("viewing", d) and (g.nodes[f"deal:{d}"].props.get("stage") or "New") != "Viewing booked"
    assert [c for c in g.of("attention", status="open") if "Viewing request" in c.props["reason"]]


def test_a_request_with_no_place_asks_which(office):
    lead(office)
    assert "Which property" in reception.book(office, PH, deal(office), None, next_week(), datetime.now(DUBAI), 1, False)[0]


def test_the_agent_must_confirm_before_it_is_on_the_calendar(office):
    lead(office)
    g, n = office.graph(), listing(office)
    k = next(x for x in __import__("diwan.slots", fromlist=["appointments"]).appointments(g) if x["where"] == "property")
    broker = g.nodes[f"deal:{deal(office)}"].props["broker"]
    args = dict(by=broker, broker=broker, phone=PH, name_=WHO, kind_id=k["id"], ref=n.props["ref"], when=next_week(), now=datetime.now(DUBAI))
    with pytest.raises(ValueError, match="confirm"):
        reception.add_by_hand(office, **args)
    reception.add_by_hand(office, **args, confirmed=True)
    assert office.graph().of("viewing", deal(office), "booked")


def test_no_compliance_work_on_a_lead(office):
    lead(office, "Hi, I'm looking to buy a villa in JVC", "My budget is 5 million, I will pay in cash")
    g = office.graph()
    assert not [t for t in g.of("task", deal(office)) if t.props["agent"] in ("screen", "pay")]
    assert not g.of("question", deal(office), "open")


def test_conversion_starts_compliance_and_expects_the_deposit(office):
    lead(office)
    d, n = deal(office), listing(office)
    desk_stages.convert(office, d, office.graph().nodes[f"deal:{d}"].props["broker"], n.props.get("price_aed") or 2000000, {"source": "listing", "ref": n.props["ref"]})
    tasks = office.graph().of("task", d)
    assert [t for t in tasks if t.props["agent"] == "screen"] and [t for t in tasks if t.props["agent"] == "pay"]


def test_no_deposit_before_compliance_clears(office):
    lead(office)
    d, n = deal(office), listing(office)
    desk_stages.convert(office, d, office.graph().nodes[f"deal:{d}"].props["broker"], n.props.get("price_aed") or 2000000, {"source": "listing", "ref": n.props["ref"]})
    t = next(x for x in office.graph().of("task", d) if x.props["agent"] == "pay")
    with pytest.raises(ValueError, match="Compliance"):
        finance.mark_received(office, t.id, "ahmed", "ENBD 1", today=datetime.now(DUBAI).date())


def test_saying_different_things_is_not_a_conflict(office):
    lead(office, "Buying, to live in", "A 4 bed villa", "Budget is about 5 million", "Cash")
    assert not office.graph().of("decision", deal(office), "open")


def test_two_budgets_ask_which_stands_and_the_answer_counts(office):
    from fastapi.testclient import TestClient
    from diwan import app as A
    office.record_fact("x", "deal_term", "x", "x") if False else None
    with TestClient(A.app) as c:
        A.S.office = office
        lead(office)
        d = deal(office)
        a = office.record_fact(d, "deal_term", "Budget is 5 million", WHO, amount_aed=5000000)
        b = office.record_fact(d, "deal_term", "Budget is 6 million", WHO, amount_aed=6000000)
        card = office.graph().of("decision", d, "open")[0]
        assert c.post(f"/api/desk/cards/{card.id}/answer", json={"by": "omar", "choice": f"{b} replaces {a}"}).status_code == 200
    g = office.graph()
    assert g.nodes[a].status == "superseded" and g.nodes[b].status != "superseded" and not g.of("decision", d, "open")


def test_the_villa_is_not_the_area(office):
    g = office.graph()
    _, got = qualify.read_rules(g, qualify.form(g), "buyer", "Can I see the villa in JVC on Thursday?", None)
    assert [a["value"] for a in got if a["field"] == "areas"] in ([], ["Jumeirah Village Circle"], ["JVC"])


def test_offers_are_kept_and_a_new_figure_answers_the_last(office):
    lead(office)
    d = deal(office)
    b = office.graph().nodes[f"deal:{d}"].props["broker"]
    offers.make(office, d, b, "client", 1900000)
    offers.make(office, d, b, "seller", 1950000, "Final")
    rows = offers.rows(office.log, d)
    assert [r["status"] for r in rows] == ["declined", "open"] and rows[1]["note"] == "Final"
    assert offers.decide(office, d, "O2", b, True)["amount"] == 1950000
    with pytest.raises(ValueError):
        offers.decide(office, d, "O2", b, False)
    assert "1,950,000" in frontdesk.picture(office, "layla", datetime.now(DUBAI))


def test_only_the_deals_people_record_offers(office):
    lead(office)
    with pytest.raises(PermissionError):
        offers.make(office, deal(office), "priya", "client", 100)


@pytest.mark.parametrize("amount", ["", "abc", 0, -5])
def test_a_bad_offer_is_refused(office, amount):
    lead(office)
    d = deal(office)
    with pytest.raises(ValueError):
        offers.make(office, d, office.graph().nodes[f"deal:{d}"].props["broker"], "client", amount)


def test_a_follow_up_has_a_time_and_someone_answers_for_it(office):
    from diwan.agents import followup
    lead(office)
    d = deal(office)
    t0 = datetime.now(DUBAI)
    followup.draft(office, d, why="after the viewing")
    card = next(c for c in office.graph().of("attention", status="open") if "follow-up" in c.props["reason"])
    left = datetime.fromisoformat(card.props["due"]) - t0
    assert timedelta(hours=1, minutes=55) < left < timedelta(hours=2, minutes=5)
    assert card.props["who"] == office.graph().nodes[f"deal:{d}"].props["broker"]


def test_nova_reads_no_record_numbers(office, monkeypatch):
    monkeypatch.setattr(frontdesk, "_turn", lambda *a: {"kind": "answer", "text": "Layth is buying [T5] for 5 million [F7][F8] (F9) and (T1, F2)."})
    assert frontdesk.say(office, "x", "layla", session="ids")["text"] == "Layth is buying for 5 million and."
