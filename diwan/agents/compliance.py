"""Compliance: the legal duties come first. Any change to who pays, how, or what the customer earns reaches the
compliance officer before any other room acts on it, with the old and new words side by side.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from diwan.graph import Node

if TYPE_CHECKING:
    from diwan.office import Office

MONEY_KINDS = {"payer", "payment_promise", "income_claim"}


def money_changed(office: Office, deal: str, olds: list[Node], new: Node, cause: int) -> None:
    """Raised before anything else happens to the replaced statements (rooms.md rule 8)."""
    if new.props["kind"] not in MONEY_KINDS and not any(o.props["kind"] in MONEY_KINDS for o in olds):
        return
    before = " / ".join(f'"{o.props["quote"]}"' for o in olds)
    office.log.append("check.raised", actor="comp", agent="comp", deal=deal, caused_by=cause,
                      content={"who": "priya", "title": "Payment arrangement changed", "refs": [o.id for o in olds] + [new.id],
                               "text": f'Payment arrangement changed: {before} became "{new.props["quote"]}". Review before any money moves.'})
