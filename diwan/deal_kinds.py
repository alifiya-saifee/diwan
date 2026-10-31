"""The brokerage's deal kinds (its sales desks or CRM pipelines): Ready sales, Off-plan, Leasing, or whatever the owner
lists. Nothing here is fixed in code: the list is a setting in the log (person "sales", key "kinds"), edited on the
Settings page, and a CRM's pipelines can fill it the same way.

Each kind says which customers it serves (a customer type from the qualification form, optionally with a condition on
an answer, in the same form as the qualification conditions), which listings it covers (for sale or rent; ready or
off-plan), and its brokers. The first kind whose rule matches a qualified lead is the lead's kind: Rania recommends only
its listings, and the lead goes to one of its brokers (the listing's agent first).
"""
from __future__ import annotations

import re

from diwan.graph import Graph
from diwan.office import Office
from diwan.people import PEOPLE

OFFERINGS = {"": "Any", "sale": "For sale", "rent": "For rent"}
COMPLETIONS = {"": "Any", "ready": "Ready", "off_plan": "Off-plan"}


def kinds(g: Graph) -> list[dict]:
    return list(g.settings.get("sales", {}).get("kinds") or [])


def validate(ks: list[dict]) -> list[str]:
    from diwan import leads, qualify
    errs, seen = [], set()
    for k in ks:
        label = k.get("name") or k.get("id") or "a deal kind"
        if not (k.get("name") or "").strip():
            errs.append("Every deal kind needs a name")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", k.get("id") or ""):
            errs.append(f"{label}: id must be lowercase letters, digits and _")
        if k.get("id") in seen:
            errs.append(f"{label}: two deal kinds have the id {k.get('id')!r}")
        seen.add(k.get("id"))
        if not k.get("serves"):
            errs.append(f"{label}: say which customers it serves")
        for s in k.get("serves", []):
            w = s.get("when")
            if w and (w.get("op") not in qualify.OPS or not w.get("field")):
                errs.append(f"{label}: a condition is incomplete")
        li = k.get("listings") or {}
        if li.get("offering", "") not in OFFERINGS or li.get("completion", "") not in COMPLETIONS:
            errs.append(f"{label}: unknown listing filter")
        if bad := [b for b in k.get("brokers", []) if b not in leads.brokers()]:
            errs.append(f"{label}: not brokers: {', '.join(bad)}")
    return errs


def save(office: Office, ks: list[dict], *, by: str) -> list[dict]:
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes the deal kinds")
    types = set(qualify.form(office.graph())["types"])
    ks = [{"id": k.get("id"), "name": (k.get("name") or "").strip(), "brokers": list(k.get("brokers") or []),
           "listings": {"offering": (k.get("listings") or {}).get("offering") or "", "completion": (k.get("listings") or {}).get("completion") or ""},
           "serves": [{"type": s.get("type"), "when": s.get("when") or None} for s in k.get("serves") or []]} for k in ks]
    errs = validate(ks) + [f"{k['name']}: {s['type']!r} is not a customer type on the qualification form"
                           for k in ks for s in k["serves"] if s["type"] not in types]
    if errs:
        raise ValueError("; ".join(errs))
    office.log.append("setting.changed", actor=by, content={"person": "sales", "key": "kinds", "value": ks})
    return ks


def kind_for(g: Graph, deal: str) -> dict | None:
    """The first deal kind whose rule matches this lead's customer type and answers."""
    from diwan import qualify
    d = g.nodes[f"deal:{deal}"].props
    answers = d.get("answers", {})
    for k in kinds(g):
        for s in k["serves"]:
            if s["type"] == d.get("qtype") and (not s.get("when") or qualify.holds(s["when"], answers)):
                return k
    return None


def fits(k: dict | None, p: dict) -> bool:
    """Whether a listing (its props) is one this deal kind covers."""
    if not k:
        return True
    li = k.get("listings") or {}
    if li.get("offering") and p.get("offering") and p["offering"] != li["offering"]:
        return False
    if li.get("completion") and (p.get("completion") or "ready") != li["completion"]:
        return False
    return True


def describe(k: dict) -> str:
    serves = "; ".join(s["type"] + (f" when {s['when']['field']} {s['when']['op']} {s['when'].get('value', '')}".rstrip() if s.get("when") else "")
                       for s in k["serves"])
    who = ", ".join(PEOPLE[b]["name"] for b in k["brokers"] if b in PEOPLE) or "any broker"
    return f"{k['name']}: serves {serves}; brokers {who}"
