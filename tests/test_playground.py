from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo, evals, playground
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers.chat import PROVIDERS
from diwan.slots import DUBAI
from tests.conftest import fake

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def test_a_test_conversation_never_touches_the_real_office(office):
    before = len(office.log.list())
    sid = playground.start(office, "Ali")["session"]
    t = playground.say(sid, "Hi, 2 bed in the Marina around 2.7 million?", brain="rules", now=NOON)
    assert t["by"] == "rules" and t["why_rules"] == "You chose rules only"
    assert any(u["id"] == "listing:MC-1204" for u in t["used"]) and "Unit 1204" in t["reply"]
    assert any("Deal terms" in f["text"] for f in t["heard"]) and t["stage"] == "New"  # buy or rent not said yet: not qualifying until the type is known
    t = playground.say(sid, "Can you call me? Is a discount possible?", brain="rules", now=NOON)
    assert t["mode"] == "human" and t["to"] == "Omar" and t["card"]["kind"] == "call"
    assert len(office.log.list()) == before  # nothing reached the real log


def test_nothing_is_sent_even_with_whatsapp_connected(office, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a test message reached WhatsApp")
    monkeypatch.setattr("diwan.providers.aisensy.available", lambda: True)
    monkeypatch.setattr("diwan.providers.aisensy.send_text", boom)
    monkeypatch.setattr("diwan.providers.aisensy.send_template", boom)
    monkeypatch.setenv("NOTIFY_TEMPLATE", "staff_alert")
    sid = playground.start(office)["session"]
    t = playground.say(sid, "I want to speak to an agent", brain="rules", now=NOON)
    assert t["mode"] == "human"
    sent = [e for e in playground.SESSIONS[sid]["office"].log.list() if e["type"] == "chat.sent"]
    assert sent and all(e["content"]["via"] == "sandbox" for e in sent)


def test_it_shows_the_model_and_what_a_guard_stopped(office, monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(
        {"reply": "Unit 1204 is yours for AED 2,100,000 if you sign today.", "listing_refs": ["MC-1204"], "knowledge_refs": [],
         "book_listing": None, "book_when": None, "handover": False}))
    sid = playground.start(office)["session"]
    t = playground.say(sid, "How much is the Marina unit?", brain="model", now=NOON)
    assert t["by"] == "model" and t["who"].startswith("Meta Model API")
    assert t["held"] == "Unit 1204 is yours for AED 2,100,000 if you sign today."  # a price not on the listing: not sent
    assert t["handover"] == "reply named an amount not on any listing" and "reply to you here personally" in t["reply"]


def test_with_no_model_it_says_why_the_rules_answered(office):
    sid = playground.start(office)["session"]
    t = playground.say(sid, "Hi", brain="model", now=NOON)
    assert t["by"] == "rules" and "No model is connected" in t["why_rules"]


def test_api_and_rania_cases(monkeypatch):
    monkeypatch.setattr(appmod.S, "office", Office(EventLog()))
    demo.seed(appmod.S.office)
    c = TestClient(appmod.app)
    sid = c.post("/api/playground/start", json={"customer": "Sara"}).json()["session"]
    r = c.post(f"/api/playground/{sid}/say", json={"text": "What are your fees?", "brain": "rules"}).json()
    assert any(u["id"] == "K3" for u in r["used"])
    assert c.post("/api/playground/nope/say", json={"text": "hi"}).status_code == 404
    import time
    res = c.post("/api/playground/cases?brain=rules").json()
    for _ in range(100):  # the cases run in the background; the page polls the same way
        if res["finished"]:
            break
        time.sleep(0.05)
        res = c.get(f"/api/playground/cases/{res['id']}").json()
    assert res["finished"] and not res["error"] and res["total"] == len(evals.RANIA) and res["passed"] == len(evals.RANIA) and len(res["cases"]) == len(evals.RANIA)
    assert c.get("/api/playground/cases/nope").status_code == 404
    assert not appmod.S.office.graph().of("chat")  # neither the console nor the cases left a chat behind


def test_free_and_spark_pick_their_own_model_and_the_office_order_is_a_setting(office, monkeypatch):
    from diwan.providers.chat import for_tier
    monkeypatch.setenv("META_API_KEY", "k")
    monkeypatch.setenv("NVIDIA_API_KEY", "n")
    seen = {"meta": [], "nvidia": []}
    reply = {"reply": "Hello, how can I help?", "listing_refs": [], "knowledge_refs": [], "book_listing": None, "book_when": None, "handover": False}
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(reply, seen["meta"]))
    monkeypatch.setattr(PROVIDERS["nvidia"], "transport", fake(reply, seen["nvidia"]))
    sid = playground.start(office)["session"]
    t = playground.say(sid, "Hi", brain="free", now=NOON)
    assert t["who"].startswith("NVIDIA endpoint") and seen["nvidia"] and not seen["meta"]
    t = playground.say(sid, "Hello again", brain="spark", now=NOON)
    assert t["who"].startswith("Meta Model API") and seen["meta"]
    assert playground.brains() == {"spark": True, "free": True, "default": "Meta Model API (Muse Spark) · muse-spark-1.3"}
    monkeypatch.setenv("DIWAN_SPARK_ORDER", "nvidia,meta")  # everyday development on the free endpoint
    assert for_tier("spark").id == "nvidia"


def test_sensitive_topics_get_the_fixed_safe_reply_and_never_reach_the_model(office, monkeypatch):
    monkeypatch.setenv("META_API_KEY", "k")
    seen = []
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake(
        {"reply": "Sure, cash is fine and we guarantee 9% returns!", "listing_refs": [], "knowledge_refs": [],
         "book_listing": None, "book_when": None, "handover": False}, seen))
    sid = playground.start(office)["session"]
    for text in ("Do you accept cash?", "What ROI is guaranteed?", "Can I pay in crypto?", "Can you give me a discount?"):
        before = len([s for s in seen if "reception" in str(s.get("response_format", "")) or "reply" in str(s)])
        t = playground.say(sid, text, brain="spark", now=NOON)
        assert t["by"] == "policy" and t["who"] == "Fixed reply" and "guarantee 9%" not in t["reply"], text
    assert "can't promise returns" in playground.SESSIONS[sid]["turns"][1]["reply"]
    assert not any("reception" in str(s) for s in seen)  # Rania's model was never asked (the Scribe may still read facts)


def test_the_model_is_told_to_introduce_herself():
    from diwan.agents import reception
    assert "I'm Rania from Diwan Realty" in reception.GUIDE


def test_the_prompt_is_clean_and_shown_in_the_console(office):
    sid = playground.start(office, "Test Buyer")["session"]
    t = playground.say(sid, "Hi", brain="rules", now=NOON)
    system, user = t["prompt"]["system"], t["prompt"]["user"]
    assert "agent_pack" not in system.split("reception` format")[0]  # no contradictory answer format
    assert "Never assume they are buying" in system and "one question per message" in system.lower()
    assert "Customer: name not known" in user and "This is their first message." in user  # "Test" is not a name
    assert "customer:9715" not in user  # history reads "Customer:", not a phone id
    assert t["reply"].startswith("Hi, I'm Rania") and "buy, rent, or sell" in t["reply"]
    t = playground.say(sid, "Looking for a 2 bed, budget 2.7 million", brain="rules", now=NOON)
    t = playground.say(sid, "Is it still available?", brain="rules", now=NOON)
    user = t["prompt"]["user"]
    assert "What this customer has told us: F" in user and "2.7 million" in user  # she can see what they already said
    assert "Customer: Looking for a 2 bed" in user and "Their new message: Is it still available?" in user


def test_a_big_catalog_only_sends_the_listings_that_fit(office):
    from diwan.agents import reception
    reception.set_recommend(office, {"when": "as_soon_as_fit"}, by="layla")
    for i in range(30):
        office.add_listing(ref=f"X-{i}", title=f"Tower {i}", community="Dubai Hills", type="villa", beds=5, price_aed=9_000_000 + i,
                           permit=f"P{i}", agent="omar")
    sid = playground.start(office)["session"]
    t = playground.say(sid, "2 bed in the Marina around 2.7 million", brain="rules", now=NOON)
    listed = [line for line in t["prompt"]["user"].splitlines() if line.startswith('<source id="listing:')]
    assert 0 < len(listed) <= reception.MAX_LISTINGS and '<source id="listing:MC-1204">' in listed


def test_once_a_person_has_the_chat_rania_never_books_by_herself(office):
    from diwan.agents import reception
    reception.message(office, "971500000077", "Hi", name_="Ali", now=NOON)
    reception.hand_over(office, "971500000077", to="omar", by="omar", reason="taken from the Inbox")
    r = reception.message(office, "971500000077", "Can I see MC-1204 Saturday at 4pm?", now=NOON)
    assert r["mode"] == "human" and not office.graph().of("viewing", status="booked")


def test_internal_and_retired_knowledge_never_reach_rania(office):
    """handoff.md issue 1: Rania read every confirmed item, internal ones included."""
    from diwan import knowledge
    internal = knowledge.add(office, "company", "Broker commission split", "Our brokers keep 50% of the commission on their own deals.",
                             by="layla", audience="internal")["id"]
    old = knowledge.add(office, "company", "Old commission", "Our buyer commission is 1% of the price.", by="layla")["id"]
    knowledge.retire(office, old, by="layla", why="replaced")
    sid = playground.start(office)["session"]
    t = playground.say(sid, "What commission do your brokers keep?", brain="rules", now=NOON)
    sources = t["prompt"]["user"]
    assert internal not in sources and "50%" not in sources and "50%" not in t["reply"]
    assert old not in sources and "1% of the price" not in t["reply"]
    t = playground.say(sid, "What are your fees?", brain="rules", now=NOON)
    assert "2% of the price" in t["reply"] and any(u["id"] == "K3" for u in t["used"])  # customer-facing fees still answered
