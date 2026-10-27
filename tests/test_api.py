from fastapi.testclient import TestClient

from diwan import app as appmod


def client():
    c = TestClient(appmod.app)
    c.post("/api/demo/reset")
    return c


def test_meeting_correction_through_the_api_then_nova_explains():
    c = client()
    m = c.post("/api/meetings", json={"deal": "marina-1204", "title": "Second meeting"}).json()
    assert c.post(f"/api/meetings/{m['id']}/turn", json={"text": "hello"}).status_code == 409
    c.post(f"/api/meetings/{m['id']}/consent")
    r = c.post(f"/api/meetings/{m['id']}/turn", json={"text": "Actually, forget my brother. I'll pay it all myself."}).json()
    assert r["facts"]
    assert not c.post("/api/approvals/A1/execute", params={"key": "k"}).json()["ok"]
    say = c.post("/api/nova/say", json={"text": "Who is paying for Karim?"}).json()
    assert "I'll pay it all myself" in say["text"]
    gr = c.get("/api/graph", params={"deal": "marina-1204"}).json()
    assert any(n["id"] == "F3" and n["status"] == "superseded" for n in gr["nodes"])


def test_inbox_sandbox_takeover_and_listings():
    c = client()
    c.post("/api/chats/incoming", json={"phone": "971500000001", "text": "Hi", "name": "Sara Malik"})
    r = c.post("/api/chats/incoming", json={"phone": "971500000001", "text": "Any villa in JVC?"}).json()
    assert r["refs"] == ["listing:JVC-88"]
    c.post("/api/chats/971500000001/send", json={"text": "Omar here.", "by": "omar"})
    chat = c.get("/api/chats").json()[0]
    assert chat["props"]["mode"] == "human" and chat["messages"][-1]["by"] == "omar"
    ls = {x["props"]["ref"]: x["advertised"] for x in c.get("/api/listings").json()}
    assert ls == {"MC-1204": True, "JVC-88": True, "BB-305": True, "DT-2210": False}


def test_pasted_document_waits_for_confirmation():
    c = client()
    ids = c.post("/api/knowledge/document", json={"text": "Parking: two spaces per unit\n- Service charge: AED 18 per sq ft"}).json()["proposed"]
    ks = {k["id"]: k["status"] for k in c.get("/api/knowledge").json()}
    assert [ks[i] for i in ids] == ["proposed", "proposed"]
    c.post(f"/api/knowledge/{ids[0]}/confirm")
    assert {k["id"]: k["status"] for k in c.get("/api/knowledge").json()}[ids[0]] == "confirmed"


def test_whatsapp_webhook_verify_and_receive(monkeypatch):
    c = client()
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "v")
    assert c.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "v", "hub.challenge": "7"}).text == "7"
    assert c.get("/api/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "7"}).status_code == 403
    payload = {"entry": [{"changes": [{"value": {"contacts": [{"wa_id": "971", "profile": {"name": "Ali"}}],
                                                 "messages": [{"from": "971", "type": "text", "text": {"body": "Hi"}}]}}]}]}
    assert c.post("/api/whatsapp/webhook", json=payload).json() == {"ok": True}
    assert c.get("/api/chats").json()[0]["label"] == "Ali"


def test_audio_needs_consent_first():
    c = client()
    m = c.post("/api/meetings", json={"deal": "marina-1204"}).json()
    with c.websocket_connect(f"/api/meetings/{m['id']}/audio") as ws:
        msg = ws.receive()
    assert msg["code"] == 4009
