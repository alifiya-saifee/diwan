"""Who holds each Deal desk role. Work is routed to a role, never to a name in the code: the owner assigns the holder
on the Deal desk (a `setting.changed` in the log, so every change keeps who made it and when); until then the person
whose team role says so holds it. With nobody in a role, the work says who must be assigned instead of guessing.
"""
from __future__ import annotations

from diwan.graph import Graph
from diwan.people import PEOPLE, name

ROLES = {"compliance": "Compliance officer", "finance": "Finance", "transactions": "Transactions officer"}
OWNER = "Owner"


def holder(g: Graph, role: str) -> str | None:
    if v := g.settings.get("desk", {}).get(f"role:{role}"):
        return v
    return next((k for k, p in PEOPLE.items() if p.get("role") == ROLES[role]), None)


ROLE_WORK = {("task", "screen"): "compliance", ("task", "report"): "compliance", ("check", "comp"): "compliance",
             ("task", "formf"): "transactions", ("task", "transfer"): "transactions", ("task", "inv"): "finance"}


def current(g: Graph, node) -> str | None:
    """Who a piece of work waits for now. A role's own work (Compliance's checks, screenings and reports; Form F and
    transfer steps) follows whoever holds the role, so open work moves when the holder changes. Anything addressed to
    a particular person, such as a question to the deal's broker, stays with that person."""
    stored = node.props.get("needs_person") if node.type == "task" else node.props.get("who")
    role = ROLE_WORK.get((node.type, node.props.get("agent")))
    if node.type == "task" and node.props.get("closing") and node.props.get("step") == "docs":
        role = "transactions"
    if node.type == "task" and node.props.get("desk_role") in ROLES:  # work that names its role (after-closing tasks)
        role = node.props["desk_role"]
    return (holder(g, role) or stored) if role and stored else stored


def who(g: Graph, role: str) -> str:
    """The holder's name for a sentence, or the role itself when nobody holds it."""
    h = holder(g, role)
    return name(h) if h else f"the {ROLES[role].lower()} (nobody assigned)"


def check(g: Graph, role: str, by: str | None) -> None:
    h = holder(g, role)
    if not h:
        raise PermissionError(f"Nobody is the {ROLES[role].lower()} yet: the owner assigns one on the Deal desk.")
    if by != h:
        raise PermissionError(f"Only {name(h)}, the {ROLES[role].lower()}, can do this.")


def is_owner(by: str | None) -> bool:
    return bool(by) and PEOPLE.get(by, {}).get("role") == OWNER


def assign(office, role: str, person: str, *, by: str) -> None:
    if role not in ROLES:
        raise ValueError(f"No role {role!r}.")
    if not is_owner(by):
        raise PermissionError("Only the owner assigns Deal desk roles.")
    if person not in PEOPLE:
        raise ValueError(f"{person!r} is not on the team.")
    office.log.append("setting.changed", actor=by, content={"person": "desk", "key": f"role:{role}", "value": person})


def table(g: Graph) -> list[dict]:
    return [{"role": r, "title": t, "holder": holder(g, r), "holder_name": name(holder(g, r)) if holder(g, r) else None,
             "set": bool(g.settings.get("desk", {}).get(f"role:{r}"))} for r, t in ROLES.items()]
