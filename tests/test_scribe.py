import pytest

from diwan.agents import scribe
from diwan.events import EventLog
from diwan.office import Office
from diwan.providers import voice
from diwan.providers.chat import PROVIDERS
from tests.conftest import fake


@pytest.fixture
def office():
    o = Office(EventLog())
    o.open_deal("marina-1204", property="Unit 1204, Marina Crest", customer="Karim Haddad", broker="omar")
    o.start_meeting("marina-1204", "M1", title="First viewing")
    return o


def say(o, *lines, label="customer"):
    return [scribe.turn(o, "M1", label, t) for t in lines]


def test_nothing_is_heard_before_consent(office):
    with pytest.raises(PermissionError):
        say(office, "My brother Tariq will send the deposit.")
    assert not [e for e in office.log.list() if e["type"] == "utterance"]


@pytest.mark.parametrize("text, value", [("two point six million", 2_600_000), ("Two hundred sixty thousand", 260_000),
                                         ("forty-five thousand a month", 45_000), ("AED 260,000", 260_000), ("2.6m", 2_600_000)])
def test_amounts_in_words_and_digits(text, value):
    assert scribe.amounts(text) == [value]


def test_meeting_becomes_facts_and_one_correction_replaces_everything_it_takes_back(office):
    office.give_consent("M1", by="Karim Haddad")
    say(office, "We're looking at two point six million for the Marina unit.",
        "My brother Tariq is helping. My brother Tariq will send the deposit.",
        "Two hundred sixty thousand deposit, by bank transfer, next week.")
    g = office.graph()
    assert [f.props["kind"] for f in g.of("fact")] == ["deal_term", "party", "payer", "payment_promise"]
    assert [t.props["action"] for t in g.of("task")] == ["Expect AED 260,000 by bank transfer from Tariq", "Screen Tariq, who will pay for Karim Haddad"]
    r = say(office, "Actually, forget my brother. I'll pay it all myself.")[0]
    g = office.graph()
    new = g.nodes[r["facts"][0]]
    assert new.props["quote"] == "I'll pay it all myself." and set(new.props["replaces"]) == {"F2", "F3"}
    assert [t.status for t in g.of("task")] == ["withdrawn", "withdrawn", "queued"]


def test_maybe_is_kept_but_changes_nothing(office):
    office.give_consent("M1", by="Karim Haddad")
    say(office, "We're looking at two point six million for the Marina unit.", "If the view is better maybe we go to three million.")
    g = office.graph()
    assert g.nodes["F2"].props["stance"] == "hypothetical" and g.facts("marina-1204", "deal_term") == [g.nodes["F1"]]
    assert not g.of("decision")


def test_unclear_correction_asks_the_broker_instead_of_guessing(office):
    office.give_consent("M1", by="Karim Haddad")
    office.record_fact("marina-1204", "payment_promise", "Fifty thousand cash now.", "Karim Haddad", amount_aed=50_000, method="cash")
    office.record_fact("marina-1204", "payment_promise", "Two hundred thousand by cheque.", "Karim Haddad", amount_aed=200_000, method="cheque")
    r = say(office, "Actually, the deposit is three hundred thousand.")[0]
    assert r["questions"] and office.graph().nodes["F1"].status == office.graph().nodes["F2"].status == "live"


def test_model_quotes_not_in_the_turn_are_dropped(office, monkeypatch, tmp_path):
    office.give_consent("M1", by="Karim Haddad")
    monkeypatch.setenv("META_API_KEY", "k")
    blank = {"stance": "asserted", "party": None, "relation": None, "amount_aed": None, "method": None, "due": None, "monthly_income_aed": None, "replaces": []}
    monkeypatch.setattr(PROVIDERS["meta"], "transport", fake({"facts": [
        {**blank, "kind": "payer", "quote": "I'll pay it all myself.", "payer": "Karim Haddad"},
        {**blank, "kind": "payer", "quote": "My brother sends it from Lagos.", "payer": "Tariq"}]}))
    r = scribe.turn(office, "M1", "customer", "Fine. I'll pay it all myself.", tape_root=tmp_path)
    assert r["by"] == "meta" and r["rejected"] == ["My brother sends it from Lagos."] and len(r["facts"]) == 1


def test_voice_events_become_turns():
    t = voice.Turns()
    assert t.feed({"type": "speaker", "label": "speaker_1"}) is None
    assert t.feed({"type": "transcript", "transcript": "I'll pay", "final": False}) == {"partial": "I'll pay", "speaker": "speaker_1"}
    assert t.feed({"type": "speechComplete", "transcript": "I'll pay it myself.", "turnId": "7"}) == {"final": "I'll pay it myself.", "speaker": "speaker_1", "turn": "7"}
    with pytest.raises(voice.VoiceError):
        t.feed({"type": "error", "message": "bad audio"})
