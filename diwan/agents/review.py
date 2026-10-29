"""Review: work is checked against what is true now before a person sees it. An approval resting on replaced words goes
back to the person who gave it as a decision; a draft using them is sent back, naming the slide and both quotes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan.graph import Graph, Node

if TYPE_CHECKING:
    from diwan.office import Office


def approval_stale(office: Office, deal: str, approval: Node, old: Node, new: Node, cause: int) -> None:
    office.log.append("decision.needed", actor="factcheck", agent="factcheck", deal=deal, caused_by=cause,
                      content={"who": approval.props["approver"], "refs": [approval.id, old.id, new.id],
                               "options": ["Re-approve on the new facts", "Cancel"],
                               "question": f'Your approval "{approval.props["action"]}" rests on "{old.props["quote"]}", which the customer replaced with "{new.props["quote"]}".'})


def live_version(g: Graph, fid: str) -> str:
    """The statement that stands now in place of `fid` (itself if nothing replaced it)."""
    seen = {fid}
    while (n := g.nodes[fid]).status == "superseded" and (nxt := n.props.get("superseded_by")) and nxt not in seen:
        fid = nxt
        seen.add(fid)
    return fid


def reapprove(office: Office, card: Node, by: str, action: str) -> str:
    """The person re-approves in their own words; the new approval rests on the statements that stand now."""
    g = office.graph()
    old = g.nodes[card.props["refs"][0]]
    action = " ".join(action.split())
    if not action:
        raise ValueError("Write what you approve now.")
    if action.lower() == old.props["action"].lower():
        raise ValueError("That is the old wording, which rested on replaced words. Write what you approve now, "
                         "e.g. who pays as the customer said it last.")
    rests = list(dict.fromkeys(live_version(g, f) for f in old.props["rests_on"]))
    aid = office.approve(old.deal, by, action, rests)
    if old.status == "given":
        office.log.append("approval.refused", actor=by, deal=old.deal, content={"id": old.id, "because": f"re-approved on the new facts as {aid}"})
    office.log.append("decision.made", actor=by, deal=old.deal, content={"card": card.id, "answer": "Re-approve on the new facts", "approval": aid})
    return aid


def cancel(office: Office, card: Node, by: str) -> None:
    g = office.graph()
    old = g.nodes[card.props["refs"][0]]
    if old.status == "given":
        office.log.append("approval.refused", actor=by, deal=old.deal, content={"id": old.id, "because": f"cancelled by {by} after the customer changed it"})
    office.log.append("decision.made", actor=by, deal=old.deal, content={"card": card.id, "answer": "Cancel"})


def slide_stale(office: Office, g: Graph, deal: str, slide: Node, old: Node, new: Node, cause: int, sent_back: set) -> None:
    """One send-back per draft, naming the first slide found that still says the old words."""
    draft = g.out(slide.id, "part_of")[0]
    if draft.id in sent_back or draft.status == "sent_back":
        return
    sent_back.add(draft.id)
    office.log.append("review.returned", actor="factcheck", agent="factcheck", deal=deal, caused_by=cause,
                      content={"draft": draft.id, "slide": slide.props["n"], "old": old.props["quote"], "new": new.props["quote"],
                               "reason": f"Slide {slide.props['n']} still says what {old.id} said; the customer replaced it ({new.id})."})
