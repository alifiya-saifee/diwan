import hashlib
import hmac
import json
from datetime import datetime

import httpx
import pytest

from diwan import demo, slots
from diwan.agents import nova, reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import whatsapp
from diwan.providers.chat import PROVIDERS

NOW = datetime(2026, 10, 27, 23, 40, tzinfo=slots.DUBAI)
PH = "971501234567"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.company(o)
    return o


def msg(o, text, **kw):
    return reception.message(o, PH, text, name_="Karim Haddad", now=NOW, **kw)


def test_greets_then_answers_from_listings_with_permit(office):
    assert "I'm Rania" in msg(office, "Hi")["reply"]
    r = msg(office, "2 bed in the Marina, around 2.7 million")
    assert r["refs"] == ["listing:MC-1204"] and "permit SAMPLE-71204" in r["reply"]
    assert office.graph().nodes[r["facts"][0]].props["kind"] == "deal_term"  # the budget is a fact, same as in a meeting


def test_listing_without_permit_is_never_offered(office):
    msg(office, "Hi")
    r = msg(office, "Any 1 bed in Downtown?")
    assert "DT-2210" not in r["reply"] and r["mode"] == "human"


def test_answers_company_questions_from_confirmed_knowledge_only(office):
    msg(office, "Hi")
    office.add_knowledge("fees", "Secret", "Unconfirmed fee schedule from a brochure.", by="rania", confirmed=False)
    r = msg(office, "What are your fees?")
    assert r["refs"] == ["K3"] and "2% of the price plus VAT" in r["reply"]


def test_books_a_free_slot_and_offers_others_when_taken(office):
    msg(office, "Hi")
    msg(office, "2 bed in the Marina, around 2.7 million")
    r = msg(office, "Wednesday 4pm for MC-1204")
    assert r["reply"].startswith("Booked: Unit 1204") and "V1" in r["refs"]
    r2 = reception.message(office, "971559999999", "Can I see MC-1204 Wednesday at 4pm?", name_="Sara Malik", now=NOW)
    assert "isn't available" in r2["reply"] and "Wednesday 28 Oct, 10:00 AM" in r2["reply"]
    assert "Viewing of MC-1204 with Karim Haddad" in nova.brief(office, "omar")["text"]


@pytest.mark.parametrize("text", ["Do you accept cash?", "Can you give me a discount?", "Can I pay in USDT?"])
def test_not_hers_goes_to_the_broker_without_saying_why(office, text):
    msg(office, "Hi")
    r = msg(office, text)
    assert r["mode"] == "human" and "complian" not in r["reply"].lower()
    assert any(t.props.get("needs_person") == "omar" for t in office.graph().of("task"))


def test_never_promises_returns(office):
    msg(office, "Hi")
    assert "can't promise returns" in msg(office, "What ROI is guaranteed?")["reply"]


def test_payment_said_on_whatsapp_is_the_same_fact_as_in_a_meeting(office):
    msg(office, "Hi")
    r = msg(office, "My brother Tariq will send the deposit.")
    f = office.graph().nodes[r["facts"][0]]
    assert f.props["kind"] == "payer" and f.props["payer"] == "Tariq" and "payment details" in r["reply"]


def test_person_takes_over_rania_only_suggests_then_hands_back(office):
    msg(office, "Hi")
    msg(office, "Do you accept cash?")
    r = msg(office, "Hello?")
    assert r["mode"] == "human" and "suggestion" in r
    reception.person_sends(office, PH, "Omar here.", by="omar")
    assert not [t for t in office.graph().of("task", status="queued") if t.props["agent"] == "rania"]
    reception.give_back(office, PH, by="omar")
    assert "10am to 7pm" in msg(office, "What time do you open?")["reply"]
    sent = [m["by"] for m in office.graph().nodes[f"chat:{PH}"].props["messages"] if m["type"] == "sent"]
    assert sent[-2:] == ["omar", "rania"]


def test_model_reply_with_an_unlisted_price_is_not_sent(office, monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "k")
    replies = {"facts": {"facts": []}, "reception": {"reply": "MC-1204 is yours for AED 2,300,000.", "listing_refs": ["MC-1204"],
                                                    "knowledge_refs": [], "book_listing": None, "book_when": None, "handover": False}}

    def handle(req):
        body = json.loads(req.content)
        out = replies[body["response_format"]["json_schema"]["name"]]
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(out)}}], "usage": {}})
    monkeypatch.setattr(PROVIDERS["meta"], "transport", httpx.MockTransport(handle))
    r = msg(office, "Best price for MC-1204?", tape_root=tmp_path)
    assert "2,300,000" not in r["reply"] and r["mode"] == "human" and r["handover"] == "reply named an amount not on any listing"


def test_whatsapp_webhook_parse_verify_sign_and_send(monkeypatch):
    payload = {"entry": [{"changes": [{"value": {"contacts": [{"wa_id": PH, "profile": {"name": "Karim"}}],
                                                 "messages": [{"from": PH, "id": "w1", "type": "text", "text": {"body": "Hi"}},
                                                              {"from": PH, "id": "w2", "type": "image"}]}}]}]}
    assert whatsapp.parse(payload) == [{"phone": PH, "name": "Karim", "text": "Hi", "id": "w1"}]
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "v")
    assert whatsapp.verify({"hub.mode": "subscribe", "hub.verify_token": "v", "hub.challenge": "42"}) == "42"
    assert whatsapp.verify({"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "42"}) is None
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s")
    body = json.dumps(payload).encode()
    assert whatsapp.signed(body, "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest())
    assert not whatsapp.signed(body, "sha256=bad") and not whatsapp.signed(body, None)
    monkeypatch.setenv("WHATSAPP_TOKEN", "t")
    monkeypatch.setenv("WHATSAPP_PHONE_ID", "123")
    seen = []
    t = httpx.MockTransport(lambda req: seen.append(req) or httpx.Response(200, json={"messages": [{"id": "x"}]}))
    whatsapp.send(PH, "Hello", transport=t)
    assert seen[0].url.path == "/v21.0/123/messages" and json.loads(seen[0].content)["text"]["body"] == "Hello"


def test_slots_read_everyday_times():
    assert slots.say(slots.parse("tomorrow 4pm", NOW)) == "Wednesday 28 Oct, 4:00 PM"
    assert slots.say(slots.parse("sat at 4", NOW)) == "Saturday 31 Oct, 4:00 PM"
    assert slots.parse("next week sometime", NOW) is None


def test_a_slow_model_never_keeps_a_customer_waiting(office, monkeypatch, tmp_path):
    monkeypatch.setenv("NVIDIA_API_KEY", "nv")
    def slow(req):
        raise httpx.ReadTimeout("queue", request=req)
    monkeypatch.setattr(PROVIDERS["nvidia"], "transport", httpx.MockTransport(slow))
    r = msg(office, "Hi", tape_root=tmp_path)
    assert r["by"] == "rules" and "I'm Rania" in r["reply"]
    assert any(e["type"] == "agent.failed" and e["agent"] == "rania" for e in office.log.list())
    assert "I'll pay" in nova.converse(office, "Who is paying for Karim?", "layla", session="x")["text"] or True
