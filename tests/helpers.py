"""The people's steps the Deal desk now waits for, for tests that are about something later in the deal."""
from datetime import date

from diwan import documents
from diwan.agents import compliance, finance
from diwan.graph import OPEN


def clear_deal(office, deal: str, *, note: str = "Proof seen on the file") -> None:
    """What the compliance officer really does: screens everyone, reviews the checks, rates the risk, clears the deal."""
    g = office.graph()
    for t in g.of("task", deal):
        if t.props["agent"] == "screen" and t.status in OPEN:
            compliance.record_screening(office, t.id, "priya", "clear", "UN, UAE lists")
    for c in g.of("check", deal, "open"):
        if c.props.get("agent") == "comp":
            office.log.append("decision.made", actor="priya", deal=deal, content={"card": c.id, "answer": "Reviewed"})
            if c.props.get("payment"):
                finance.release_held(office, c, "priya", date.today())
    for q in g.of("question", deal, "open"):
        if q.props.get("kind") == "funding":
            office.log.append("question.answered", actor="priya", deal=deal, content={"card": q.id, "answer": "Own savings"})
    for r in documents.requests(office.log.list(deal=deal), deal):
        for k in r["kinds"]:
            if k not in r["got"]:
                office.log.append("docs.received", actor="client", deal=deal, content={"token": r["token"], "kind": k, "file": "x.jpg", "sha": k, "fields": {}, "flags": []})
            if k not in r["confirmed"]:
                office.log.append("docs.confirmed", actor="priya", deal=deal, content={"token": r["token"], "kind": k, "party": r["party"], "name": r["name"], "fields": {}})
    if not office.graph().nodes[f"deal:{deal}"].props.get("risk"):
        compliance.rate(office, deal, "priya", "low")
    compliance.clear(office, deal, "priya", note)


def sign_form_f(office, did: str) -> str:
    """Form F signed by everyone, on paper."""
    deal = office.graph().nodes[did].deal
    return office.file_document(kind="Form F", title=f"Form F ({did}) signed on paper", date="2026-10-31", by="joseph", deal=deal)
