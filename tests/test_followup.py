from datetime import datetime

import pytest

from diwan import demo, inbox
from diwan.agents import followup, reception, runner
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers.chat import Reply
from diwan.slots import DUBAI

NOON = datetime(2026, 10, 28, 12, tzinfo=DUBAI)
READY = ("I want to buy", "Dubai Marina", "An apartment", "2 bed", "Budget is 2.7 million", "Cash", "Now", "To live in", "UAE resident", "The second one")


@pytest.fixture
def office():
    o = Office(EventLog())
    demo.seed(o)
    demo.catalog(o)
    demo.kinds(o)
    demo.projects(o)
    return o


def lead(o, phone, msgs, name="Sara Khan"):
    for t in msgs:
        reception.message(o, phone, t, name_=name, now=NOON)
    return o.graph().nodes[f"chat:{phone}"].deal


def test_marking_the_lead_viewed_drafts_the_follow_up_from_the_records(office):
    deal = lead(office, "971500010001", READY)
    inbox.set_stage(office, "971500010001", "Viewed", by="omar")
    f = followup.current(office.graph(), deal)
    assert f["text"].startswith("Hi Sara, thank you for your time today at the viewing.")
    assert "MC-1204" in f["text"] and "within your budget of AED 2,700,000" in f["text"] and "make an offer" in f["text"]
    assert f["refs"] == ["listing:MC-1204"] and not f["by_model"]


def test_a_model_draft_that_tips_off_the_customer_is_thrown_away(office, monkeypatch):
    deal = lead(office, "971500010002", READY)
    monkeypatch.setattr(runner, "has_model", lambda *a, **k: True)
    monkeypatch.setattr(runner, "call", lambda *a, **k: Reply({"message": "Thanks! Our compliance team is screening your funds.", "refs": []}, {}))
    f = followup.draft(office, deal, why="after the meeting")
    assert "compliance" not in f["text"].lower() and not f["by_model"]
    monkeypatch.setattr(runner, "call", lambda *a, **k: Reply({"message": "Thanks Sara! Lovely to meet you. Omar", "refs": []}, {}))
    assert followup.draft(office, deal, why="after the meeting")["by_model"]


def test_only_the_broker_sends_it_and_never_with_compliance_words(office):
    deal = lead(office, "971500010003", READY)
    inbox.set_stage(office, "971500010003", "Viewed", by="omar")
    text = followup.current(office.graph(), deal)["text"]
    with pytest.raises(PermissionError):
        followup.send(office, deal, text, by="hamza")
    with pytest.raises(ValueError, match="never told"):
        followup.send(office, deal, text + " We are also doing a source of funds check.", by="omar")
    followup.send(office, deal, text, by="omar")
    g = office.graph()
    assert followup.current(g, deal) is None and g.nodes["chat:971500010003"].props["messages"][-1]["text"] == text


def test_a_meeting_drafts_it_too_and_a_deal_without_whatsapp_says_so(office):
    office.start_meeting("jvc-88", "M9", title="Villa 88 viewing")
    office.end_meeting("M9")
    f = followup.draft(office, "jvc-88", why="after the meeting")
    assert f["text"].startswith("Hi Sara, thank you for your time today.")
    with pytest.raises(ValueError, match="no WhatsApp conversation"):
        followup.send(office, "jvc-88", f["text"], by="omar")


def test_an_arabic_customer_gets_arabic(office):
    deal = lead(office, "971500010004", ("أريد شراء شقة",), name="Huda Ali")
    f = followup.draft(office, deal, why="after the meeting")
    assert f["text"].startswith("مرحباً Huda")


def test_the_follow_up_answers_the_worry_from_the_recorded_visit(office):
    from diwan.agents import visit
    deal = lead(office, "971500010001", READY)
    office.start_meeting(deal, "MV1", title="Site visit")
    office.give_consent("MV1", by="customer")
    for t in ("We love the view from the balcony.", "But the kitchen is too small for us.", "Let me talk to my wife and get back to you."):
        office.utterance("MV1", "customer", t)
    office.utterance("MV1", "broker", "The kitchen can be opened up.")
    s = visit.from_meeting(office, "MV1")
    assert s["interest"] == "thinking" and s["liked"] == ["We love the view from the balcony."] and s["worries"] == ["the kitchen is too small for us."]
    assert "opened up" not in str(s)  # only the client's words
    f = followup.draft(office, deal, why="after the meeting")
    assert "You mentioned “the kitchen is too small for us”" in f["text"] and "Take your time" in f["text"]


def test_not_for_them_is_never_pushed_again(office):
    from diwan.agents import visit
    deal = lead(office, "971500010001", READY)
    visit.summarize(office, deal, said="Honestly it's not for us, too far from the school.", source="notes")
    f = followup.draft(office, deal, why="after the viewing")
    assert "What would you change" in f["text"] and "make an offer" not in f["text"]


def test_a_summary_never_keeps_words_that_were_not_said(office):
    from diwan.agents import visit
    s = visit.rules("Nice light. Parking is a problem.")
    assert s["liked"] == ["Nice light."] and s["worries"] == ["Parking is a problem."] and s["interest"] == "unknown"
