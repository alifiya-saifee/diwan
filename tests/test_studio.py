from diwan import demo
from diwan.agents import studio
from diwan.events import EventLog
from diwan.office import Office


def test_studio_walks_a_listing_to_an_approval_and_marks_sample_work():
    o = Office(EventLog())
    demo.seed(o)
    n = o.log.list()[-1]["id"]
    studio.run_now(o, "MC-1204")
    evs = o.log.list(after=n)
    packs = [e for e in evs if e["type"] == "agent.pack"]
    assert [e["agent"] for e in packs][:5] == ["mkt", "mtrend", "mrival", "mtrans", "research"]
    assert {e["agent"] for e in packs if e["content"]["usage"].get("sample")} == {"mtrend", "mrival", "mtrans", "mcap", "mthumb"}
    assert "Pass: permit SAMPLE-71204" in next(e for e in packs if e["agent"] == "mpermit")["content"]["pack"]["verdict"]
    req = next(e for e in evs if e["type"] == "approval.requested")
    assert req["agent"] == "mpub" and req["content"]["reviewer"] == "The owner"
    assert not [e for e in evs if e["type"] == "agent.refused"]
    assert any(e["type"] == "chat.sent" and "MC-1204" in str(e["content"]["refs"]) for e in evs)
    assert all(e["caused_by"] for e in packs[1:])
