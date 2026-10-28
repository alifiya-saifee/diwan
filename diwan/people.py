"""The brokerage's people (fictional). Agents never act as them; they only prepare work and ask."""
from __future__ import annotations

PEOPLE = {
    "layla": {"name": "Layla", "role": "Owner", "team": None},
    "omar": {"name": "Omar", "role": "Broker", "team": "sales"},
    "priya": {"name": "Priya", "role": "Compliance officer", "team": "comp"},
    "joseph": {"name": "Joseph", "role": "Transactions officer", "team": "ops"},
    "ahmed": {"name": "Ahmed", "role": "Finance", "team": "fin"},
    "maya": {"name": "Maya", "role": "Marketing manager", "team": "mkt"},
}

# A charter names its reviewer by role; this is who that is today.
BY_ROLE = {"The owner": "layla", "Owner": "layla", "Broker": "omar", "Compliance officer": "priya",
           "Transactions officer": "joseph", "Finance": "ahmed", "Finance lead": "ahmed",
           "Marketing manager": "maya"}

# Who decides what an agent may not.
ONLY_PEOPLE = {
    "submit": ("joseph", "submits portal forms"),
    "approve": (None, "approves work: the person the approval is for"),
    "release_money": ("ahmed", "releases money"),
    "file_report": ("priya", "files reports with the FIU"),
    "decide_suspicion": ("priya", "decides whether anything is suspicious"),
}


def pid(who: str | None) -> str | None:
    """A person id from an id, a name or a role."""
    if not who:
        return None
    w = who.strip()
    if w.lower() in PEOPLE:
        return w.lower()
    for k, p in PEOPLE.items():
        if p["name"].lower() == w.lower():
            return k
    return BY_ROLE.get(w)


def name(who: str | None) -> str:
    k = pid(who)
    return PEOPLE[k]["name"] if k else (who or "someone")
