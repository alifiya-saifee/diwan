"""KPIs for the content studio's agents, like a person's targets: each has a target and is measured from the office's
own log, so the number on screen is what actually happened. `None` means there is nothing to measure yet.

Shared by every agent: first-time pass rate at review, work returned, escalations to a person, steps blocked waiting
for a connection, and how much of its work came from a model rather than rules or a template.
"""
from __future__ import annotations

from collections import Counter

from diwan.agents import qa
from diwan.agents.charters import children
from diwan.office import Office

TEAM = ["mkt", "research", "mtrend", "mrival", "mtrans", "plan", "midea", "mlane", "mfilm", "mcopy", "mscript", "mcheck", "mplay",
        "mprod", "mshoot", "mvideo", "mart", "mcap", "mremix", "mwriter", "mpub", "mthumb", "mpermit", "msched", "mcross"]

# what each agent is held to: (kpi, target, what it means)
TARGETS: dict[str, list[tuple[str, str, str]]] = {
    "mrival": [("accounts covered", "100% of the competitors set", "every account on the list was reached this run"),
               ("outliers found", "≥ 1 a week", "posts at 2x or more their account's usual"),
               ("data age", "≤ 7 days", "the newest post it read")],
    "mtrend": [("cited cards", "100%", "every trend card links to where it was seen"), ("cards a week", "3", "rising formats pinned")],
    "mtrans": [("outliers transcribed", "≥ 80% of video outliers", "hooks and beats pulled from the top videos")],
    "research": [("board cards with a source", "100%", "nothing pinned without a link")],
    "midea": [("first-time pass", "≥ 90%", "ideas the Strategist accepts without sending back"), ("ideas built on research", "≥ 50%", "ideas citing a pinned card")],
    "mlane": [("lanes left empty", "≤ 1", "of the five content lanes this week")],
    "mfilm": [("first-time pass", "100%", "film lists ending on the price and permit, with 4+ shots")],
    "mscript": [("first-time pass", "≥ 90%", "scripts the Copywriter accepts as written"), ("approved by the Marketing manager", "≥ 80%", "scripts approved without being sent back"),
                ("written by the model", "≥ 80% once a model is connected", "rather than the template")],
    "mcopy": [("scripts reviewed before approval", "100%", "no script reaches the Marketing manager unchecked")],
    "mcheck": [("takes checked", "100% of uploaded takes", "each take compared with the approved script")],
    "mplay": [("playbook entries", "≥ 1 a month", "structures from our own outliers")],
    "mshoot": [("film list sent within a day of approval", "100%", "the broker knows what to shoot")],
    "mvideo": [("AI videos with recorded consent", "100%", "never a face or voice without it"), ("render success", "≥ 95%", "videos made per request")],
    "mcap": [("cuts with captions", "100%", "every cut has captions from what was said")],
    "mwriter": [("posts with the permit number", "100%", "Dubai requires it on every ad"), ("first-time pass", "≥ 95%", "post text accepted as written")],
    "mthumb": [("covers per reel", "≥ 2", "a frame and a generated option")],
    "mpermit": [("posts checked before publishing", "100%", "nothing reaches the owner unchecked"), ("holds traced to the right agent", "100%", "fixed by whoever caused it")],
    "msched": [("slots in waking hours", "100%", "8 AM to 11 PM Dubai")],
    "mcross": [("versions within limits", "100%", "every platform's length limit")],
    "mpub": [("posts published only after owner approval", "100%", "no exceptions")],
    "mkt": [("escalations to a person", "≤ 1 a week", "work that failed review three times"), ("reels to approval", "≥ 2 a week", "listings that reached the owner")],
}


def measure(office: Office) -> dict[str, dict]:
    evs = office.log.list()
    by = {a: Counter() for a in TEAM}
    provider = {a: Counter() for a in TEAM}
    for e in evs:
        a, t, c = e.get("agent"), e["type"], e["content"]
        if t == "qa.passed" or t == "qa.failed":
            owners = [qa.CHECKS[c["kind"]][0].owner] if c.get("kind") in qa.CHECKS else c.get("returned_to", [])
            for o in owners:
                if o in by:
                    by[o]["reviews"] += 1
                    if t == "qa.passed" and c.get("attempt") == 1:
                        by[o]["first_pass"] += 1
                    if t == "qa.failed":
                        by[o]["returned"] += 1
        if a not in by:
            continue
        if t == "agent.pack":
            by[a]["outputs"] += 1
            p = (c.get("usage") or {}).get("provider")
            if p:
                provider[a][p] += 1
        elif t == "step.blocked":
            by[a]["blocked"] += 1
        elif t == "agent.failed":
            by[a]["failed"] += 1
        elif t == "qa.escalated":
            by[a]["escalated"] += 1
        elif t == "content.made":
            by[a]["made"] += 1
    # specific measures
    approvals = [e for e in evs if e["type"] == "approval.requested" and e["agent"] == "mcopy"]
    decided = {e["content"]["card"]: e["content"]["answer"] for e in evs if e["type"] == "decision.made"}
    cards = [f"R{e['id']}" for e in approvals]
    approved = sum(1 for c in cards if decided.get(c) == "approve")
    sent_back = sum(1 for c in cards if decided.get(c) in ("reject", "revise"))  # a change request is a send-back
    pinned = [e["content"] for e in evs if e["type"] == "board.pinned"]
    posts = [e for e in evs if e["type"] == "content.made" and e["content"]["kind"] == "post text"]
    footage_ai = [e for e in evs if e["type"] == "footage.added" and e["content"].get("source", "").startswith("AI")]
    out = {}
    for a in TEAM:
        b = by[a]
        model = sum(n for p, n in provider[a].items() if p not in ("rules", "template"))
        total_p = sum(provider[a].values())
        row = {"outputs": b["outputs"], "made": b["made"], "reviews": b["reviews"], "returned": b["returned"], "escalated": b["escalated"],
               "blocked": b["blocked"], "failed": b["failed"],
               "first_time_pass": round(100 * b["first_pass"] / b["reviews"]) if b["reviews"] else None,
               "model_share": round(100 * model / total_p) if total_p else None}
        if a == "mscript":
            row["approved_by_manager"] = round(100 * approved / (approved + sent_back)) if approved + sent_back else None
        if a == "research":
            row["cards_with_source"] = round(100 * sum(1 for p in pinned if p.get("url")) / len(pinned)) if pinned else None
        if a == "mtrend":
            t = [p for p in pinned if p["kind"] == "trend"]
            row["cited_cards"] = round(100 * sum(1 for p in t if p.get("url")) / len(t)) if t else None
        if a == "mrival":
            row["outliers_pinned"] = sum(1 for p in pinned if p["kind"] == "outlier")
        if a == "mwriter":
            row["posts_with_permit"] = (round(100 * sum(1 for e in posts if "Permit" in e["content"]["text"]) / len(posts)) if posts else None)
        if a == "mvideo":
            row["ai_videos"] = len(footage_ai)
            row["with_consent"] = (round(100 * sum(1 for e in footage_ai if e["content"].get("consent_by")) / len(footage_ai)) if footage_ai else None)
        row["targets"] = [{"kpi": k, "target": t, "means": m} for k, t, m in TARGETS.get(a, [])]
        out[a] = row
    return out


def team_tree() -> list[dict]:
    return [{"room": r.id, "lead": r.name, "agents": [c.id for c in children(r.id)]} for r in children("mkt")]
