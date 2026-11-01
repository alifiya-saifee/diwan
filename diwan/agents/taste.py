"""What the studio has learned from what people did, as weights: an online logistic regression over a post's features. Every
yes, no and lead nudges the weights of what that post was (its format, subject, area, kind, angle), and the weights steer the
choices themselves: what goes on the plan, which format, which script comes first. A reason a person gives is read by the
model and becomes features too, so "too salesy" counts against a tone, not just that post.

It is all replayed from the log, recent decisions counting more, so a wrong lesson fades and can be forgotten. With only a
few decisions the weights are a lean, not proof: nothing is hidden because of one no, only after repeated ones.
"""
from __future__ import annotations

import math
import re
import threading
from datetime import datetime, timezone

from diwan.office import Office

LR, HALF_LIFE_DAYS, REASON = 0.6, 45, 0.4  # a reason alone leans: with its no it stays above BLOCK, so it takes saying twice to stop something
LEAN, BLOCK = 0.35, -0.9  # below BLOCK it stops being chosen; a single no moves a weight about -0.3
LEAD = 2.0  # a real enquiry counts double a person's yes: it is the market's answer
DIMS = {"format": "Format", "subject": "Subject", "area": "Area", "home": "Type of home", "price": "Price range", "tone": "Tone", "picture": "Pictures",
        "length": "Length", "angle": "Script angle", "hook": "Opening"}
SCHEMA = {"name": "lessons", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["lessons"], "properties": {"lessons": {
    "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["dim", "value", "sign"],
                               "properties": {"dim": {"type": "string", "enum": list(DIMS)}, "value": {"type": "string"}, "sign": {"type": "integer"}}}}}}}


def _clean(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().lower()[:40]


def _band(aed) -> str | None:
    if not aed:
        return None
    return "under 1m" if aed < 1_000_000 else "1m to 3m" if aed < 3_000_000 else "3m to 10m" if aed < 10_000_000 else "over 10m"


def features(office: Office, ref: str) -> list[str]:
    """What a post is, as features. Frozen into each signal, so the past does not change when the catalog does."""
    from diwan.agents import marketing
    lst = marketing._subject(office, ref)
    if not lst:
        return []
    subject = "our company" if ref.startswith("JOB-") else "teaching" if lst.get("item") == "topic" else "homes for sale"
    pairs = [("subject", subject), ("format", marketing.format_of(office, ref)), ("area", lst.get("community")), ("home", lst.get("type")), ("price", _band(lst.get("price_aed")))]
    return [f"{d}:{_clean(v)}" for d, v in pairs if v]


def script_features(sc: dict) -> list[str]:
    hook = sc.get("hook_en") or ""
    kind = "a question" if hook.rstrip().endswith("?") else "a number" if re.search(r"\d", hook) else "a statement"
    return [f"angle:{_clean(sc.get('angle'))}", f"hook:{kind}"] if sc.get("angle") else [f"hook:{kind}"]


def signal(office: Office, ref: str | None, y: int, source: str, *, by: str, why: str = "", extra: list[str] | None = None, strength: float = 1.0) -> None:
    """A person said yes (1) or no (0). A reason is read in the background: nobody waits for it."""
    from diwan.providers import meta
    feats = (features(office, ref) if ref else []) + (extra or [])
    if not feats:
        return
    office.log.append("taste.signal", actor=by, agent="mkt", content={"ref": ref, "y": y, "strength": strength, "features": feats, "source": source, "why": why.strip()})
    if why.strip() and meta.ready():
        threading.Thread(target=understand, args=(office, ref, why.strip(), feats), daemon=True).start()


def understand(office: Office, ref: str | None, why: str, feats: list[str]) -> list[dict]:
    """What a person's reason means, as features with a direction."""
    from diwan import business
    from diwan.providers import meta
    system = ("You turn a marketing manager's reason for a decision into what should change in future. " + business.describe(office) + "\n"
              "Give only what the reason really says. Each lesson has a dim, a value of 1 to 3 plain words, and sign -1 for less of it or 1 for more of it. Reuse the "
              "exact value from the post's features when the reason is about one of them. If the reason says nothing general, give none.")
    try:
        got = meta.look(system, f"The post's features: {', '.join(feats)}\nTheir reason: {why[:300]}", [], SCHEMA, agent="mkt")
    except meta.MetaError:
        return []
    out = [{"dim": x["dim"], "value": _clean(x["value"]), "sign": 1 if x["sign"] > 0 else -1} for x in got.get("lessons") or [] if x.get("dim") in DIMS and _clean(x.get("value"))]
    if out:
        office.log.append("taste.reason", actor="mkt", agent="mkt", content={"ref": ref, "why": why, "lessons": out})
    return out


def _age_gain(at: str, now: datetime) -> float:
    days = max(0.0, (now - datetime.fromisoformat(at)).total_seconds() / 86400)
    return 0.5 ** (days / HALF_LIFE_DAYS)


def weights(office: Office, now: datetime | None = None) -> dict[str, float]:
    """The replay: for each signal in order, each of its features moves by how wrong the current weights were about it."""
    log = office.log.list()
    last = log[-1]["id"] if log else 0
    cached = getattr(office, "taste_seen", None)
    if not now and cached and cached[0] == last:
        return cached[1]
    now_ = now or datetime.now(timezone.utc)
    w: dict[str, float] = {}
    known: dict[str, list[str]] = {}

    def learn(feats: list[str], y: float, strength: float, gain: float) -> None:
        p = 1 / (1 + math.exp(-sum(w.get(f, 0.0) for f in feats)))
        for f in feats:
            w[f] = w.get(f, 0.0) + LR * (y - p) * strength * gain

    for e in log:
        t, c = e["type"], e["content"]
        if t == "taste.signal":
            known[c["ref"]] = c["features"]
            learn(c["features"], c["y"], c.get("strength", 1.0), _age_gain(e["at"], now_))
        elif t == "taste.reason":
            for x in c["lessons"]:
                k = f"{x['dim']}:{x['value']}"
                w[k] = w.get(k, 0.0) + x["sign"] * REASON * _age_gain(e["at"], now_)
        elif t == "taste.forgotten":
            w.pop(c["key"], None)
        elif t == "lead.attributed" and c.get("ref") in known:
            learn(known[c["ref"]], 1, LEAD, _age_gain(e["at"], now_))
    if not now:
        office.taste_seen = (last, w)
    return w


def weight(office: Office, key: str) -> float:
    return weights(office).get(key, 0.0)


def score(office: Office, ref: str, extra: list[str] | None = None) -> float:
    """How much this post fits what has been learned. 0 before anything is known, and then nothing is computed."""
    w = weights(office)
    return sum(w.get(f, 0.0) for f in features(office, ref) + (extra or [])) if w else 0.0


def script_score(office: Office, sc: dict) -> float:
    w = weights(office)
    return sum(w.get(f, 0.0) for f in script_features(sc)) if w else 0.0


def ruled_out(office: Office, ref: str) -> bool:
    """Repeatedly turned down: a feature of it has gone below the bar."""
    w = weights(office)
    return bool(w) and any(w.get(f, 0.0) <= BLOCK for f in features(office, ref))


def doubts_pictures(office: Office) -> bool:
    """A person has turned down how the pictures look."""
    return any(k.startswith("picture:") and v <= -LEAN for k, v in weights(office).items())


def learned(office: Office) -> dict:
    """What it has learned, for a person to see and undo."""
    ups = sum(1 for e in office.log.list() if e["type"] == "taste.signal")
    rows = [{"key": k, "what": DIMS.get(k.split(":")[0], k.split(":")[0]), "value": k.split(":", 1)[1], "weight": round(v, 2),
             "lean": "more" if v > 0 else "less", "strong": abs(v) >= abs(BLOCK)} for k, v in weights(office).items() if abs(v) >= LEAN]
    return {"decisions": ups, "early": ups < 10, "rows": sorted(rows, key=lambda r: -abs(r["weight"]))}


def brief(office: Office) -> str:
    """For whoever writes, chooses or judges: the direction, strongest first."""
    rows = learned(office)["rows"][:8]
    less = [f"{r['what'].lower()}: {r['value']}" for r in rows if r["lean"] == "less"]
    more = [f"{r['what'].lower()}: {r['value']}" for r in rows if r["lean"] == "more"]
    parts = ([f"Do less of ({'; '.join(less)})."] if less else []) + ([f"Do more of ({'; '.join(more)})."] if more else [])
    return ("Learned from this business's own decisions and results: " + " ".join(parts)) if parts else ""


def forget(office: Office, key: str, *, by: str) -> None:
    office.log.append("taste.forgotten", actor=by, agent="mkt", content={"key": key})

