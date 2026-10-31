"""Two messages in a row get one reply (product owner 30 Oct: "why two messages, thank you, thank you"): each message is
kept at once; Rania waits a moment and answers them together."""
from concurrent.futures import ThreadPoolExecutor
import time

from fastapi.testclient import TestClient

from diwan import app as appmod

PH = "971501112233"


def test_a_burst_gets_one_reply(monkeypatch):
    monkeypatch.setenv("DIWAN_REPLY_WAIT", "1")
    c = TestClient(appmod.app)
    c.post("/api/demo/reset")
    send = lambda t: c.post("/api/chats/incoming", json={"phone": PH, "name": "Ali Rahman", "text": t}).json()  # noqa: E731
    with ThreadPoolExecutor(2) as ex:
        first = ex.submit(send, "Hi, I want to buy an apartment in Dubai Marina")
        time.sleep(0.3)
        second = ex.submit(send, "2 bed, budget around 2.7 million")
        a, b = first.result(), second.result()
    assert a.get("merged") and b["reply"]
    msgs = c.get(f"/api/chats/{PH}").json()["messages"]
    assert [m["type"] for m in msgs] == ["received", "received", "sent"]  # both kept, one answer
    deal = appmod.S.office.graph().nodes[f"chat:{PH}"].deal
    answers = appmod.S.office.graph().nodes[f"deal:{deal}"].props["answers"]
    assert answers["bedrooms"]["value"] == 2 and answers["areas"]["value"] == "Dubai Marina"  # both read


def test_without_a_wait_each_message_is_answered(monkeypatch):
    monkeypatch.setenv("DIWAN_REPLY_WAIT", "0")
    c = TestClient(appmod.app)
    c.post("/api/demo/reset")
    for t in ("Hi", "I want to buy"):
        assert c.post("/api/chats/incoming", json={"phone": PH, "name": "Ali Rahman", "text": t}).json()["reply"]
