"""Who the studio waits for, set in Setup by role, never by a name in the code: who picks the scripts and who approves
publishing. Until one is set, the card says nobody is set yet, and anyone can still answer it.
"""
from __future__ import annotations

from diwan.office import Office
from diwan.people import PEOPLE, name

ROLES = {"script": "Who picks the scripts", "publish": "Who approves publishing"}


def get(office: Office) -> dict[str, str | None]:
    out: dict[str, str | None] = {r: None for r in ROLES}
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "setting.changed" and c.get("person") == "studio" and c.get("key", "").startswith("approver:") and c["key"][9:] in ROLES:
            out[c["key"][9:]] = c.get("value") or None
    return out


def save(office: Office, values: dict, *, by: str) -> list[str]:
    cur, changed = get(office), []
    for role, who in values.items():
        if role not in ROLES:
            continue
        if who and who not in PEOPLE:
            raise ValueError(f"{who} is not on the team.")
        if (who or None) != cur[role]:
            office.log.append("setting.changed", actor=by, content={"person": "studio", "key": f"approver:{role}", "value": who or ""})
            changed.append(role)
    return changed


def label(office: Office, role: str) -> str:
    who = get(office)[role]
    return f"{name(who)} ({PEOPLE[who]['role']})" if who else "nobody set yet (Setup → Approvals)"


def team() -> list[dict]:
    return [{"id": k, "name": v["name"], "role": v["role"]} for k, v in PEOPLE.items()]
