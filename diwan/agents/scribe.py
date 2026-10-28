"""The Scribe: each finished spoken turn becomes facts with the speaker's exact words, and a correction is linked to the
earlier statements it replaces.

With a model, Muse Spark reads the turn next to the deal's live facts and proposes facts and links. Without one, a small
rules reader handles plain English (amounts in words or digits, who pays, family, income). Either way a quote that is
not word for word in the turn is dropped and recorded, and a correction that could mean more than one earlier statement
replaces nothing: the broker gets one question instead, because withdrawing the wrong work is worse than asking.
"""
from __future__ import annotations

import re

from diwan.agents import runner
from diwan.agents.charters import get
from diwan.graph import Graph, Node
from diwan.office import Office
from diwan.pack import Action, Evidence, Pack, norm

KINDS = ["deal_term", "payer", "payment_promise", "income_claim", "party", "document_shown", "commitment"]
CUES = re.compile(r"\b(actually|forget|instead|scratch that|change of plan|on second thought|not anymore|no longer|rather)\b"
                  r"|(?:^|\s)no,|انسى|بدلا|بدلاً", re.I)
RELATIONS = "brother|sister|father|mother|wife|husband|son|daughter|cousin|uncle|aunt|partner|friend|employer|company"

_n = {"type": ["number", "null"]}
_s = {"type": ["string", "null"]}
FACTS_SCHEMA = {"name": "facts", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["facts"],
    "properties": {"facts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["kind", "quote", "stance", "payer", "party", "relation", "amount_aed", "method", "due", "monthly_income_aed", "replaces"],
        "properties": {"kind": {"type": "string", "enum": KINDS}, "quote": {"type": "string"},
                       "stance": {"type": "string", "enum": ["asserted", "negated", "hypothetical"]},
                       "payer": _s, "party": _s, "relation": _s, "amount_aed": _n, "method": _s, "due": _s, "monthly_income_aed": _n,
                       "replaces": {"type": "array", "items": {"type": "string"}}}}}}}}

RULES = """
For this turn, list the facts it states, in the `facts` format, not agent_pack:
- quote: the shortest run of the speaker's exact words that states the fact, copied character for character.
- payer / party: a person's name as said, or the speaker's own name when they say "I", "me" or "myself".
- amount_aed: a number in dirhams ("two point six million" = 2600000).
- stance: hypothetical for "if", "maybe", "might"; negated for something denied.
- replaces: the ids of earlier facts (given as sources) that this turn takes back or changes. Only when the speaker
  clearly corrects or withdraws them; otherwise an empty list.
Small talk states no facts: return an empty list."""


# ---------- amounts in words or digits ----------

UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
                                    "fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
SCALES = {"thousand": 1_000, "million": 1_000_000, "k": 1_000, "m": 1_000_000, "mn": 1_000_000}
NUMWORD = set(UNITS) | set(TENS) | {"hundred", "thousand", "million", "point", "and", "a"}


def _words(tokens: list[str]) -> float:
    total, cur, dec = 0.0, 0.0, None
    for w in tokens:
        if w == "point":
            dec = ""
        elif dec is not None and w in UNITS:
            dec += str(UNITS[w])
        elif w in UNITS:
            cur += UNITS[w]
        elif w in TENS:
            cur += TENS[w]
        elif w == "hundred":
            cur = (cur or 1) * 100
        elif w in ("thousand", "million"):
            total += (cur + (float("0." + dec) if dec else 0)) * SCALES[w]
            cur, dec = 0.0, None
    return total + cur + (float("0." + dec) if dec else 0)


def amounts(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(k|m|mn|million|thousand)?\b", text, re.I):
        base = float(m.group(1).replace(",", ""))
        v = base * SCALES.get((m.group(2) or "").lower(), 1) if base < 10_000 else base  # "2.6 million", never "2,600,000 million"
        out.append(v)
    toks = re.findall(r"[a-z]+", text.lower().replace("-", " "))
    run: list[str] = []
    for w in toks + ["_end"]:
        if w in NUMWORD and (w not in ("and", "a", "point") or run):
            run.append(w)
        elif run:
            if any(x in UNITS or x in TENS for x in run):
                out.append(_words(run))
            run = []
    return [int(v) if v == int(v) else v for v in out if v >= 1000]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def read_rules(text: str, speaker: str) -> list[dict]:
    """Plain-English facts from one turn. Covers the common cases; anything it misses waits for the model."""
    facts = []
    blank = {"stance": "asserted", "payer": None, "party": None, "relation": None, "amount_aed": None, "method": None, "due": None,
             "monthly_income_aed": None, "replaces": []}
    for s in _sentences(text):
        low = s.lower()
        hyp = bool(re.search(r"\b(if|maybe|might|perhaps|thinking of|could)\b", low)) and not CUES.search(s)
        stance = "hypothetical" if hyp else "asserted"
        nums = amounts(s)
        if re.search(r"\b(i'?ll|i will|i'?m going to|i am going to|i'?m|i am) (pay|paying)\b|\bpay (it |for it )?(all )?myself\b", low):
            facts.append({**blank, "kind": "payer", "quote": s, "payer": speaker, "stance": stance})
        elif m := re.search(rf"\bmy ({RELATIONS})(?: ([A-Z][a-z]+))?\b[^.]*\b(will|'ll|is going to|is)? ?(pay|send|cover|transfer|paying|sending)", s, re.I):
            who = m.group(2) or f"{speaker.split()[0]}'s {m.group(1).lower()}"
            facts.append({**blank, "kind": "payer", "quote": s, "payer": who, "party": who, "relation": m.group(1).lower(), "stance": stance})
        elif m := re.search(rf"\b[Mm]y ({RELATIONS}) ([A-Z][a-z]+)\b", s):
            facts.append({**blank, "kind": "party", "quote": s, "party": m.group(2), "relation": m.group(1).lower(), "stance": stance})
        if nums and re.search(r"\b(earn|make|salary|income)\b", low):
            monthly = nums[0] / 12 if re.search(r"\b(year|annual|a year)\b", low) else nums[0]
            facts.append({**blank, "kind": "income_claim", "quote": s, "monthly_income_aed": round(monthly), "stance": stance})
        elif nums and re.search(r"\b(deposit|down ?payment|cheque|check|instal+ment|booking)\b", low):
            method = next((v for k, v in (("cash", "cash"), ("cheque", "cheque"), ("check", "cheque"), ("transfer", "bank transfer"),
                                          ("card", "card"), ("crypto", "crypto")) if k in low), None)
            due = (re.search(r"\b(today|tomorrow|next week|next month|this week|on \w+day|by (?!bank|cash|cheque|check|card|transfer|wire)\w+)\b", low) or [None])[0]
            facts.append({**blank, "kind": "payment_promise", "quote": s, "amount_aed": nums[0], "method": method, "due": due, "stance": stance})
        elif nums and re.search(r"\b(million|price|budget|offer|for the (unit|villa|apartment|flat|townhouse))\b", low):
            facts.append({**blank, "kind": "deal_term", "quote": s, "amount_aed": max(nums), "stance": stance})
    return facts


# ---------- linking a correction ----------

def _differs(old: Node, new: dict) -> bool:
    p = old.props
    k = new["kind"]
    if k == "payer":
        return norm(p.get("payer") or "") != norm(new.get("payer") or "")
    if k in ("deal_term", "income_claim"):
        f = "amount_aed" if k == "deal_term" else "monthly_income_aed"
        return p.get(f) != new.get(f)
    if k == "payment_promise":
        return p.get("amount_aed") != new.get("amount_aed") or (new.get("method") and p.get("method") != new.get("method"))
    return False


def link(g: Graph, deal: str, fact: dict, turn: str) -> tuple[list[str], list[Node] | None]:
    """The earlier facts this one replaces, or (no links, the candidates) when it is unclear which."""
    live = g.facts(deal)
    if fact["replaces"]:
        return [i for i in fact["replaces"] if i in {f.id for f in live}], None
    if not CUES.search(turn):
        return [], None
    same = [f for f in live if f.props["kind"] == fact["kind"] and _differs(f, fact)]
    if len(same) > 1:
        return [], same
    extra = []
    if fact["kind"] == "payer":  # "forget my brother" also takes back what was said about the brother's part
        low = turn.lower()
        extra = [f for f in live if f.props["kind"] == "party" and
                 ((f.props.get("relation") or "~") in low or (f.props.get("party") or "~").split()[0].lower() in low)]
    return [f.id for f in same + extra], None


# ---------- one turn ----------

def turn(office: Office, mid: str, label: str, text: str, *, turn_id: str | None = None, tape_root=None) -> dict:
    """A finished spoken turn in a meeting."""
    ev = office.utterance(mid, label, text, turn=turn_id)
    return hear(office, office.meeting(mid)["deal"], ev["content"]["speaker"], text, ev["id"], tape_root=tape_root)


def hear(office: Office, deal: str, speaker: str, text: str, cause: int, *, tape_root=None) -> dict:
    """Anything a customer said, in a meeting or on WhatsApp: the same facts, quotes and corrections either way."""
    c = get("scribe")
    g = office.graph()
    src = f"said:{cause}"
    sources = {src: f"{speaker}: {text}"} | {f.id: g.record(f.id) for f in g.facts(deal)}
    system = runner.instructions(c, office.log) + RULES
    user = runner.user_message(f"New turn from {speaker}. Earlier facts of this deal are also given.", sources)
    found = None
    if runner.has_model(c, system, user, schema=FACTS_SCHEMA, tape_root=tape_root):
        try:
            reply = runner.call(c, system, user, schema=FACTS_SCHEMA, tape_root=tape_root, timeout=runner.LIVE)
            found, by = reply.data["facts"], reply.usage.get("provider")
        except Exception as e:  # too slow or failed while people are talking: the rules reader hears it, and that is noted
            office.log.append("agent.failed", actor=c.id, agent=c.id, deal=deal, caused_by=cause, content={"error": str(e)[:300]})
    if found is None:
        found, by = read_rules(text, speaker), "rules"
    if not found:
        return {"facts": [], "rejected": [], "questions": [], "by": by, "turn": cause}
    pack = Pack(f"heard-{cause}", c.id, f"{len(found)} fact(s) heard", evidence=[Evidence(f["quote"], src) for f in found],
                actions=[Action("record_fact", f"{f['kind']}: {f['quote']}") for f in found])
    res = runner.submit(office.log, c, pack, sources={src: text}, deal=deal, caused_by=cause, usage={"provider": by})
    kept = {norm(e.quote) for e in res.pack.evidence}
    recorded, questions = [], []
    for f in found:
        if norm(f["quote"]) not in kept:
            continue
        g = office.graph()
        ids, unclear = link(g, deal, f, text)
        if unclear:
            q = office.log.append("question.asked", actor=c.id, agent=c.id, deal=deal, caused_by=cause,
                                  content={"to": g.nodes[f"deal:{deal}"].props["broker"], "refs": [x.id for x in unclear],
                                           "options": [x.props["quote"] for x in unclear] + ["Neither"],
                                           "text": f'"{f["quote"]}" changes something, but which: ' + " or ".join(f'"{x.props["quote"]}"' for x in unclear) + "?"})
            questions.append(f"Q{q['id']}")
        props = {k: v for k, v in f.items() if k not in ("kind", "quote", "stance", "replaces") and v is not None}
        recorded.append(office.record_fact(deal, f["kind"], f["quote"], speaker, replaces=ids, stance=f["stance"],
                                           caused_by=cause, **props))
    return {"facts": recorded, "rejected": [e.quote for e in res.pack.rejected_quotes], "questions": questions, "by": by, "turn": cause}
