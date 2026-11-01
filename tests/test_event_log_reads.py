"""The log parses each row once. It must still see every write, filter the same, and hand out rows a caller can't spoil."""
from diwan.events import EventLog


def test_a_write_from_another_process_is_seen(tmp_path):
    path = str(tmp_path / "log.db")
    a, b = EventLog(path), EventLog(path)
    a.append("listing.added", actor="maya", content={"ref": "A"})
    assert [e["content"]["ref"] for e in b.list()] == ["A"]
    a.append("listing.added", actor="maya", content={"ref": "B"})
    assert [e["content"]["ref"] for e in b.list()] == ["A", "B"]


def test_the_filters_read_as_before():
    log = EventLog()
    one = log.append("listing.added", actor="maya", agent="mkt", deal="D1", content={"ref": "A"})
    two = log.append("listing.added", actor="maya", agent="plan", deal="D2", content={"ref": "B"})
    assert [e["id"] for e in log.list(after=one["id"])] == [two["id"]]
    assert [e["id"] for e in log.list(deal="D1")] == [one["id"]]
    assert [e["id"] for e in log.list(agent="plan")] == [two["id"]]
    assert log.list(after=two["id"]) == []


def test_a_read_is_a_list_of_its_own():
    log = EventLog()
    log.append("listing.added", actor="maya", content={"ref": "A"})
    log.list().clear()
    assert len(log.list()) == 1
