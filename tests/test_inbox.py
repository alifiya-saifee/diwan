import json
import os
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from diwan import app as appmod
from diwan import demo, inbox
from diwan.agents import reception
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import aisensy

PH = "971501234567"


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    return o


def test_list_shows_stage_interests_waiting_and_window(office):
    reception.message(office, PH, "Hi, looking to buy a 2 bed in the Marina, budget 2.7 million", name_="Ali Rahman")
    row = inbox.listing(office)[0]
    assert row["name"] == "Ali Rahman" and row["stage"] == "Qualifying" and row["window_open"]
    assert {c["label"] for c in row["chips"]} >= {"Buy", "Marina", "2 bed", "AED 2.7M"}
    assert row["waiting_min"] is None  # Rania answered


def test_whatsapp_from_a_known_customer_joins_their_deal(office):
    reception.message(office, PH, "Hello, it's Karim about the Marina unit", name_="Karim Haddad")
    row = inbox.listing(office)[0]
    assert row["deal"] == "marina-1204" and row["linked"]


def test_booking_moves_the_stage_and_never_backwards(office):
    reception.message(office, PH, "Hi", name_="Ali Rahman")
    reception.message(office, PH, "2 bed in the Marina, around 2.7 million")
    reception.message(office, PH, "Can I see MC-1204 Saturday at 4pm?")
    assert inbox.listing(office)[0]["stage"] == "Viewing booked"
    reception.message(office, PH, "Budget is 2.5 million actually")
    assert inbox.listing(office)[0]["stage"] == "Viewing booked"


def test_free_text_after_24_hours_is_refused_template_goes_through(office):
    reception.message(office, PH, "Hi", name_="Ali Rahman")
    later = datetime.now(timezone.utc) + timedelta(hours=25)
    row = inbox.conversation(office.graph(), office.graph().nodes[f"chat:{PH}"], later)
    assert not row["window_open"]
    ev = reception.send_template(office, PH, inbox.SAMPLE_TEMPLATES[1], ["Ali", "Dubai Marina"], by="omar")
    assert ev["content"]["text"] == "Hi Ali, are you still looking in Dubai Marina? We have new listings this week."
    assert ev["content"]["template"] == "still_looking" and ev["content"]["via"] == "sandbox"


def test_aisensy_sends_session_text_and_templates(monkeypatch):
    monkeypatch.setenv("AISENSY_PROJECT_ID", "proj")
    monkeypatch.setenv("AISENSY_PROJECT_API_PWD", "pwd")
    seen = []
    t = httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200, json={"messages": [{"id": "wamid.1"}]}))
    assert aisensy.send_text("0501234567", "Hello", transport=t) == {"id": "wamid.1"}
    aisensy.send_template("+971 50 123 4567", "still_looking", ["Ali", "Marina"], transport=t)
    assert seen[0].url.path == "/project-apis/v1/project/proj/messages" and seen[0].headers["X-AiSensy-Project-API-Pwd"] == "pwd"
    assert json.loads(seen[0].content) == {"to": "971501234567", "type": "text", "text": {"body": "Hello"}}
    body = json.loads(seen[1].content)
    assert body["template"]["name"] == "still_looking" and body["template"]["components"][0]["parameters"][1] == {"type": "text", "text": "Marina"}


def test_aisensy_failure_is_shown_on_the_message_not_hidden(office, monkeypatch):
    monkeypatch.setenv("AISENSY_PROJECT_ID", "proj")
    monkeypatch.setenv("AISENSY_PROJECT_API_PWD", "pwd")
    monkeypatch.setattr(aisensy, "send_text", lambda *a, **k: (_ for _ in ()).throw(aisensy.AiSensyError("refused (401)")))
    reception.message(office, PH, "Hi", name_="Ali Rahman")
    sent = [m for m in office.graph().nodes[f"chat:{PH}"].props["messages"] if m["type"] == "sent"][-1]
    ev = next(e for e in office.log.list() if e["id"] == sent["event"])
    assert ev["content"]["via"] == "aisensy" and ev["content"]["status"] == "failed" and "401" in ev["content"]["error"]
    assert inbox.listing(office)[0]["failed"] == 1


def test_aisensy_webhook_needs_the_token_and_skips_our_echoes(monkeypatch):
    c = TestClient(appmod.app)
    c.post("/api/demo/reset")
    monkeypatch.setenv("AISENSY_WEBHOOK_TOKEN", "tok")
    msg = lambda sender: {"topic": "message.created", "data": {"contact": {"name": "Sara"},  # noqa: E731
                          "message": {"phone_number": "971559990000", "sender": sender, "message_type": "TEXT", "message_content": {"text": "Any villa in JVC?"}}}}
    assert c.post("/api/aisensy/webhook?token=wrong", json=msg("USER")).status_code == 401
    assert c.post("/api/aisensy/webhook?token=tok", json=msg("API")).json() == {"ok": True}
    assert c.get("/api/chats").json()["rows"] == []
    c.post("/api/aisensy/webhook?token=tok", json=msg("USER"))
    rows = c.get("/api/chats").json()["rows"]
    assert rows[0]["name"] == "Sara" and rows[0]["last"]["refs"] == ["listing:JVC-88"]


def test_settings_store_keys_but_never_show_them(monkeypatch, tmp_path):
    c = TestClient(appmod.app)
    r = c.post("/api/integrations", json={"values": {"AISENSY_PROJECT_ID": "proj", "AISENSY_PROJECT_API_PWD": "s3cret"}})
    assert set(r.json()["changed"]) >= {"AISENSY_PROJECT_ID", "AISENSY_PROJECT_API_PWD", "AISENSY_WEBHOOK_TOKEN"}
    env = (tmp_path / ".env").read_text()
    assert "AISENSY_PROJECT_API_PWD=s3cret" in env and (os.name == "nt" or oct((tmp_path / ".env").stat().st_mode)[-3:] == "600")
    info = c.get("/api/integrations").text
    assert "s3cret" not in info and json.loads(info)["aisensy"]["connected"] is True
    assert c.post("/api/integrations", json={"values": {"META_API_KEY": "x"}}).status_code == 422
