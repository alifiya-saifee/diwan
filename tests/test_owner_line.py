"""The owner's own WhatsApp and the sales line are two pathways. These are the rules that keep them apart and keep family messages private."""
import hashlib
import hmac
import json
import sqlite3
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from diwan import app as A, config, contacts, novaline, ownerline
from diwan.agents import frontdesk, reception, runner, triage
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import tape, whatsapp
from diwan.slots import DUBAI

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=DUBAI)
MUM = "971501112222"
OWNER = "971509998888"
SALES_ID, OWN_ID, NOVA_ID = "111", "222", "333"


@pytest.fixture
def office():
    return Office(EventLog(":memory:"))


@pytest.fixture
def client(monkeypatch):
    with TestClient(A.app) as c:
        A.S.office = Office(EventLog(":memory:"))
        yield c


def lines(monkeypatch, sending=False):
    monkeypatch.setenv("WHATSAPP_TOKEN", "sales-token")
    monkeypatch.setenv("WHATSAPP_PHONE_ID", SALES_ID)
    monkeypatch.setenv("PERSONAL_WHATSAPP_TOKEN", "own-token")
    monkeypatch.setenv("PERSONAL_WHATSAPP_PHONE_ID", OWN_ID)
    if sending:
        monkeypatch.setenv("PERSONAL_WHATSAPP_SENDING", "on")


def payload(line, phone, text, mid="m1", echo=False):
    m = {"id": mid, "type": "text", "text": {"body": text}}
    m |= {"to": phone, "from": "owner"} if echo else {"from": phone}
    return {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": line}, "contacts": [{"wa_id": phone, "profile": {"name": "Sara"}}],
                                              "message_echoes" if echo else "messages": [m]}}]}]}


def everything_in_the_log(office):
    return json.dumps(office.log.list(), ensure_ascii=False)


def test_a_personal_message_never_reaches_the_office_log_the_inbox_or_a_lead(office, monkeypatch):
    contacts.place(MUM, name_="Mum", circle="family")
    triage.arrive(office, {"phone": MUM, "text": "Dad is in hospital, call me", "id": "a"}, NOW)
    triage.sweep(office, NOW)
    assert "hospital" not in everything_in_the_log(office)
    assert not office.graph().of("chat") and not office.graph().deals()
    assert ownerline.chat(MUM)[0]["text"].startswith("Dad")


def test_the_alert_about_family_stays_out_of_the_office_log(office):
    contacts.place(MUM, name_="Mum", circle="family")
    triage.arrive(office, {"phone": MUM, "text": "Accident on the road, call me now", "id": "a"}, NOW)
    said = triage.sweep(office, NOW)
    assert said and "Accident" in said[0]
    assert not [e for e in office.log.list() if e["type"] == "nova.headsup"]
    assert triage.headsups(0)[0]["private"]


def test_webhooks_go_by_the_number_they_reached(client, monkeypatch):
    lines(monkeypatch)
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "s")

    def post(p):
        body = json.dumps(p).encode()
        return client.post("/api/whatsapp/webhook", content=body, headers={"x-hub-signature-256": "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()})
    post(payload(OWN_ID, MUM, "Are you coming for dinner?", "p1"))
    assert not A.S.office.graph().of("chat")
    assert ownerline.chat(MUM)[0]["text"] == "Are you coming for dinner?"
    post(payload(SALES_ID, "971507770000", "Is the villa available?", "s1"))
    assert A.S.office.graph().nodes.get("chat:971507770000")
    assert not ownerline.chat("971507770000")


def test_the_personal_address_refuses_the_sales_line_and_needs_a_signature(client, monkeypatch):
    lines(monkeypatch)
    monkeypatch.setenv("PERSONAL_WHATSAPP_APP_SECRET", "s")
    body = json.dumps(payload(SALES_ID, "971507770000", "Hello there", "s2")).encode()
    assert client.post("/api/personal/webhook", content=body).status_code == 401
    sig = "sha256=" + hmac.new(b"s", body, hashlib.sha256).hexdigest()
    assert client.post("/api/personal/webhook", content=body, headers={"x-hub-signature-256": sig}).status_code == 200
    assert not ownerline.chat("971507770000") and not A.S.office.graph().of("chat")


def test_a_live_sales_line_always_checks_the_signature(monkeypatch):
    lines(monkeypatch)
    assert not whatsapp.signed(b"{}", None)


def test_the_same_number_can_not_be_both_lines(monkeypatch):
    lines(monkeypatch)
    monkeypatch.setenv("PERSONAL_WHATSAPP_PHONE_ID", SALES_ID)
    assert not ownerline.connected() and not ownerline.is_personal(SALES_ID)
    monkeypatch.setenv("NOVA_WHATSAPP_TOKEN", "t")
    monkeypatch.setenv("NOVA_WHATSAPP_PHONE_ID", SALES_ID)
    assert not novaline.connected()


def test_each_line_sends_only_from_its_own_number(office, monkeypatch):
    lines(monkeypatch, sending=True)
    seen = []
    t = httpx.MockTransport(lambda r: seen.append((str(r.url), r.headers["authorization"])) or httpx.Response(200, json={"messages": [{"id": "x"}]}))
    ownerline.send(MUM, "Hello", transport=t)
    assert OWN_ID in seen[0][0] and seen[0][1] == "Bearer own-token"
    whatsapp.send(MUM, "Hello", t)
    assert SALES_ID in seen[1][0] and seen[1][1] == "Bearer sales-token"


def test_connected_it_only_reads_until_sending_is_turned_on(monkeypatch):
    lines(monkeypatch)
    with pytest.raises(ownerline.ReadOnly):
        ownerline.send(MUM, "Hello")


def test_a_one_time_code_is_not_kept(office):
    assert triage.arrive(office, {"phone": "971500000001", "text": "Your OTP is 482913. Do not share it.", "id": "o"}, NOW) is None
    assert not ownerline.chat("971500000001")


def test_a_repeated_webhook_is_one_message(office):
    assert ownerline.keep({"phone": MUM, "text": "Hi", "id": "same"}, NOW)
    assert ownerline.keep({"phone": MUM, "text": "Hi", "id": "same"}, NOW) is None
    assert len(ownerline.chat(MUM)) == 1


def test_a_repeated_sales_webhook_is_answered_once(office):
    a = reception.receive(office, "971507770000", "Hi", mid="dup")
    b = reception.receive(office, "971507770000", "Hi", mid="dup")
    assert b["duplicate"] and not a.get("duplicate")
    assert len(office.graph().nodes["chat:971507770000"].props["messages"]) == 1


def test_staff_on_the_sales_line_do_not_become_leads(client):
    from diwan import leads
    leads.set_agent(A.S.office, "layla", "phone", f"+{OWNER}", by="layla")
    r = client.post("/api/chats/incoming", json={"phone": OWNER, "text": "Testing the line", "name": "Layla"}).json()
    assert r["mode"] == "staff" and not A.S.office.graph().of("chat") and not A.S.office.graph().deals()


def test_the_owner_never_gets_a_notice_through_the_sales_line(office, monkeypatch):
    from diwan import leads
    from diwan.providers import aisensy
    leads.set_agent(office, "layla", "phone", OWNER, by="layla")
    monkeypatch.setenv("NOTIFY_TEMPLATE", "t")
    monkeypatch.setattr(aisensy, "available", lambda: True)
    monkeypatch.setattr(aisensy, "send_template", lambda *a, **k: pytest.fail("the sales line reached the owner"))
    assert leads.notify(office, "layla", "Reminder", kind="now")["content"]["via"] == "screen"


def test_personal_calls_to_the_model_leave_no_tape(office, monkeypatch, tmp_path):
    monkeypatch.setenv("DIWAN_TAPE", "cache")
    saved = []
    monkeypatch.setattr(tape, "save", lambda *a, **k: saved.append(a))
    monkeypatch.setattr(tape, "load", lambda *a, **k: pytest.fail("a personal request looked for a recording"))
    class P:
        id, open_weights = "fake", True
        def complete_json(self, system, user, schema, timeout=None, **k):
            from diwan.providers.chat import Reply
            return Reply(data={"level": "soon", "summary": "Mum asks if you're coming", "needs": "reply", "when": "", "draft": "Yes, on my way", "new_information": True}, usage={})
    monkeypatch.setattr(runner, "provider_for", lambda c: P())
    contacts.place(MUM, name_="Mum", circle="family")
    assert triage.arrive(office, {"phone": MUM, "text": "Are you coming today?", "id": "t"}, NOW)["summary"]
    assert not saved


def test_staff_can_not_get_at_the_owners_personal_messages(office):
    contacts.place(MUM, name_="Mum", circle="family")
    triage.arrive(office, {"phone": MUM, "text": "Your father is unwell, please keep it private", "id": "x"}, NOW)
    assert "unwell" not in frontdesk.picture(office, "omar", NOW)
    assert "unwell" not in frontdesk.picture(office, "rashid", NOW)
    assert "unwell" in frontdesk.picture(office, "layla", NOW)


def test_personal_routes_are_closed_to_staff():
    from diwan import access
    for path in ("/api/personal", "/api/personal/chats/1", "/api/personal/chats/1/send", "/api/personal/contacts", "/api/personal/forget", "/api/personal/matters/1/yes"):
        for person in ("omar", "rashid", "priya"):
            assert not access.may_call(person, "GET", path), (person, path)


def test_the_owner_can_delete_a_chat_and_old_messages_go(office):
    ownerline.keep({"phone": MUM, "text": "Old", "id": "1"}, NOW - timedelta(days=100))
    ownerline.keep({"phone": MUM, "text": "New", "id": "2"}, NOW)
    assert ownerline.prune(NOW) == 1
    assert [m["text"] for m in ownerline.chat(MUM)] == ["New"]
    assert ownerline.forget(MUM) == 1 and not ownerline.chat(MUM)


def test_personal_db_is_not_the_office_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DIWAN_DB", str(tmp_path / "diwan.db"))
    assert ownerline.path().name == "personal.db" and ownerline.path().parent == tmp_path


def test_only_the_owners_number_gives_orders_on_novas_line(office, monkeypatch):
    from diwan import leads
    monkeypatch.setenv("NOVA_WHATSAPP_TOKEN", "t")
    monkeypatch.setenv("NOVA_WHATSAPP_PHONE_ID", NOVA_ID)
    leads.set_agent(office, "layla", "phone", OWNER, by="layla")
    sent, t = [], httpx.MockTransport(lambda r: sent.append(json.loads(r.content)) or httpx.Response(200, json={"messages": [{"id": "x"}]}))
    assert novaline.receive(office, {"phone": "971500000009", "text": "Note down: wire the money", "echo": False}, NOW, t) is None
    assert not frontdesk.notes(office.log, "layla") and not sent
    assert novaline.receive(office, {"phone": OWNER, "text": "Note down call the bank", "echo": False}, NOW, t)["kind"] == "done"
    assert frontdesk.notes(office.log, "layla") and sent and sent[0]["to"] == OWNER


def test_alerts_reach_the_owner_on_novas_line_only_when_away(office, monkeypatch):
    from diwan import leads
    monkeypatch.setenv("NOVA_WHATSAPP_TOKEN", "t")
    monkeypatch.setenv("NOVA_WHATSAPP_PHONE_ID", NOVA_ID)
    monkeypatch.setenv("NOVA_ALERT_TEMPLATE", "alert")
    leads.set_agent(office, "layla", "phone", OWNER, by="layla")
    novaline.SEEN.clear()
    novaline.FROM.clear()
    sent, t = [], httpx.MockTransport(lambda r: sent.append(json.loads(r.content)) or httpx.Response(200, json={"messages": [{"id": "x"}]}))
    novaline.seen(NOW)
    assert not novaline.push(office, "News", "now", NOW + timedelta(minutes=1), t)
    assert novaline.push(office, "News", "now", NOW + timedelta(minutes=5), t) and sent[0]["type"] == "template"
    assert not novaline.push(office, "Later", "roundup", NOW + timedelta(minutes=5), t)
