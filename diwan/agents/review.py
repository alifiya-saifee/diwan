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


def slide_stale(office: Office, g: Graph, deal: str, slide: Node, old: Node, new: Node, cause: int, sent_back: set) -> None:
    """One send-back per draft, naming the first slide found that still says the old words."""
    draft = g.out(slide.id, "part_of")[0]
    if draft.id in sent_back or draft.status == "sent_back":
        return
    sent_back.add(draft.id)
    office.log.append("review.returned", actor="factcheck", agent="factcheck", deal=deal, caused_by=cause,
                      content={"draft": draft.id, "slide": slide.props["n"], "old": old.props["quote"], "new": new.props["quote"],
                               "reason": f"Slide {slide.props['n']} still says what {old.id} said; the customer replaced it ({new.id})."})
