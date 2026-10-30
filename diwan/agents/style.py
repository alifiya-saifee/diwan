"""Style notes: what the studio has learned about how the Marketing manager likes scripts, from what they did, shown in
Setup so they can delete any they disagree with. Nothing is guessed: every note counts the decisions behind it.

  asked     a change they asked for ("make the hook shorter"), once per distinct request
  picked    the angle they pick most, once they have picked at least MIN_PICKS scripts
  wrote     how their own scripts are built (hook length, number of lines), once they wrote one

The Script writer reads the notes that are not deleted, next to the brand profile.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter

from diwan.office import Office

MIN_PICKS = 3


def _content(office: Office) -> dict[str, dict]:
    return {e["content"]["id"]: e["content"] for e in office.log.list() if e["type"] == "content.made"}


def deleted(office: Office) -> set[str]:
    out = set()
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "setting.changed" and c.get("person") == "style" and c.get("key", "").startswith("note:"):
            (out.add if c.get("value") == "deleted" else out.discard)(c["key"][5:])
    return out


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def notes(office: Office, *, all_: bool = False) -> list[dict]:
    """[{id, kind, text, from}] newest evidence last; deleted notes are left out unless all_."""
    made, out = _content(office), {}
    picks: list[str] = []
    for e in office.log.list():
        c = e["content"]
        if e["type"] != "decision.made":
            continue
        if c.get("answer") == "revise" and (c.get("note") or "").strip():
            note = c["note"].strip().rstrip(".")
            if note.lower().startswith("the listing changed"):
                continue  # a fact update, not a taste
            k = "asked-" + _key(note)
            n = out.setdefault(k, {"id": k, "kind": "asked", "text": f"You asked: \"{note}\".", "from": 0})
            n["from"] += 1
        elif c.get("answer") == "approve" and c.get("choice") in made and made[c["choice"]].get("kind") == "script":
            picks.append(made[c["choice"]].get("angle") or "?")
    if len(picks) >= MIN_PICKS:
        angle, n = Counter(picks).most_common(1)[0]
        out[f"picked-{angle}"] = {"id": f"picked-{angle}", "kind": "picked", "text": f"You picked the {angle} angle {n} of {len(picks)} times.", "from": len(picks)}
    own = [c for c in made.values() if c.get("kind") == "script" and c.get("own")]
    if own:
        hook = round(statistics.mean(len(c["hook_en"].split()) for c in own))
        lines = round(statistics.mean(len(c["lines_en"]) for c in own))
        out["wrote"] = {"id": "wrote", "kind": "wrote", "from": len(own),
                        "text": f"Your own scripts open with a hook of about {hook} words and run about {lines} lines."}
    gone = set() if all_ else deleted(office)
    return [n for n in out.values() if n["id"] not in gone]


def delete(office: Office, note: str, *, by: str) -> None:
    if note not in {n["id"] for n in notes(office, all_=True)}:
        raise ValueError(f"no style note {note}")
    office.log.append("setting.changed", actor=by, content={"person": "style", "key": f"note:{note}", "value": "deleted"})


def restore(office: Office, note: str, *, by: str) -> None:
    office.log.append("setting.changed", actor=by, content={"person": "style", "key": f"note:{note}", "value": "kept"})


def brief(office: Office) -> str:
    """The notes as the Script writer reads them."""
    ns = notes(office)
    return ("How the Marketing manager likes scripts, learned from their decisions:\n" + "\n".join(f"- {n['text']}" for n in ns)) if ns else ""


def _words(sc: dict) -> set[str]:
    return set(re.findall(r"[a-z؀-ۿ]+|\d+", " ".join([sc.get("hook_en", ""), *sc.get("lines_en", [])]).lower()))


def used(office: Office) -> list[dict]:
    """Scripts a person approved for filming: the ones that went (or will go) out."""
    made = _content(office)
    return [made[e["content"]["choice"]] for e in office.log.list()
            if e["type"] == "decision.made" and e["content"].get("answer") == "approve" and e["content"].get("choice") in made]


def too_close(office: Office, sc: dict, limit: float = 0.6) -> dict | None:
    """The approved script this one is too close to (60% or more of the words shared), or None. A revision is not
    compared with the script it revises."""
    mine = _words(sc)
    for old in used(office):
        if old["id"] in (sc.get("id"), sc.get("revises")) or not mine:
            continue
        theirs = _words(old)
        if theirs and len(mine & theirs) / len(mine | theirs) >= limit:
            return old
    return None
