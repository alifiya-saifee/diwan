"""Qualification the owner sets: what a lead must tell us before a person takes over, and the conditions that decide it.

The owner edits one form (the Qualification screen): common questions, then questions per customer type (buyer,
tenant, seller, landlord, or any type they add), each with its wording in English and Arabic, a kind, options, how
strict it is, and "ask only if" another answer holds. Strictness, per question:
- "Must answer" (required, strict): "I'm not sure" does not count. Rania helps and asks once more; a second "not sure"
  stops her asking and gives the broker a card to help on a call. The lead does not qualify without it.
- "'Not sure' is OK" (required, not strict): "I'm not sure" counts as the answer; the broker sees "Not sure".
- "Optional": never blocks qualifying.
A condition on an answer the customer was not sure about is skipped (it can be neither met nor failed). Then the conditions, the way an n8n IF node reads:
- Qualified (PASS_TO_AGENT) when every required answer is in and every "qualify when" condition holds.
- Not a fit when any "not a fit when" condition holds: the owner's polite reply, and the lead is closed with the reason.
- Otherwise ASK_QUESTION: Rania asks the next missing required question, one at a time.
Before the type is known the verdict is DISCOVERY: find out whether they want to buy, rent, sell or let out.

The model only reads answers out of what the customer wrote (each with their exact words; an answer whose quote is not
in their messages is dropped). Code, not the model, applies the conditions, so the same answers always get the same
verdict, and the verdict names the rule that decided it. Every saved form is a new version in the log.
"""
from __future__ import annotations

import copy
import re

from diwan.graph import Graph
from diwan.office import Office
from diwan.people import PEOPLE

KINDS = ("text", "number", "money", "choice", "area", "date", "yesno")
OPS = ("=", "!=", ">=", "<=", ">", "<", "in", "not in", "contains", "is set", "is not set")


NOT_SURE = "Not sure"
UNSURE = (r"\b(not sure|unsure|(i )?(don'?t|do not) know|idk|no idea|not decided|haven'?t decided|undecided|depends|"
          r"open to (anything|options)|flexible|no clue|no (fixed|set) (date|time|plan)|"
          r"(when|once|whenever|as soon as) i (see|find|get|come across)|"  # "when I see a good project": it depends, not a date
          r"(when|once) the right (one|project|property|place))\b|لا أعرف|ما أعرف|مش عارف|مش متأكد|غير متأكد|ما أدري|مو متأكد")


def unsure(text) -> bool:
    return bool(re.search(UNSURE, str(text or "").lower()))


NEGATED = r"\b(not|don'?t|doesn'?t|no|never|isn'?t|won'?t|without|rather than|instead of)\b[^.,;!?]*$"
SAID_AS = {"now": r"asap|as soon as possible|soon|immediately|right away|straight away|urgent(ly)?|this month",
           "later": r"next year|no rush|not in a hurry|in a year"}  # common ways of saying an option, used when the form has it


def option_said(option: str, low: str) -> bool:
    """The client chose this option: its words (a hyphen or a space alike, "off plan" = "Off-plan"), or a common way of
    saying it, and not just after "not" / "don't" ("I don't think ready made will fit")."""
    rx = re.escape(option.lower()).replace(r"\-", r"[-\s]?").replace(r"\ ", r"[-\s]?")
    alt = SAID_AS.get(option.lower())
    for m in re.finditer(rf"\b(?:{rx}{'|' + alt if alt else ''})\b", low):
        if not re.search(NEGATED, low[max(0, m.start() - 40):m.start()]):
            return True
    return False


def _f(key, label, en, ar, kind="text", options=None, required=True, ask_if=None, strict=False):
    return {"key": key, "label": label, "question_en": en, "question_ar": ar, "kind": kind, "options": options or [],
            "required": required, "strict": strict, "ask_if": ask_if}


AREA = _f("areas", "Area", "Which area are you looking at?", "في أي منطقة تبحث؟", "area")
TYPE = _f("property_type", "Property type", "What type of property: apartment, villa or townhouse?", "أي نوع عقار: شقة، فيلا أو تاون هاوس؟",
          "choice", ["Apartment", "Villa", "Townhouse", "Penthouse", "Plot", "Office"])
BEDS = _f("bedrooms", "Bedrooms", "How many bedrooms?", "كم غرفة نوم؟", "number")

# The starting form, from the n8n qualification schema (common + one bucket per workstream). The owner changes it.
DEFAULT_FORM = {
    "common": [
        _f("full_name", "Full name", "May I have your full name?", "ممكن اسمك الكامل؟", required=False),
        _f("email", "Email", "What email should we send details to?", "ما هو بريدك الإلكتروني؟", required=False),
        _f("nationality", "Nationality", "What is your nationality?", "ما هي جنسيتك؟", required=False),
        _f("preferred_communication", "Preferred contact", "Do you prefer a call or WhatsApp?", "تفضل اتصال أو واتساب؟",
           "choice", ["Call", "WhatsApp", "Email"], required=False),
    ],
    "types": {
        "buyer": {"label": "Buyer", "fields": [
            AREA, TYPE, BEDS,
            _f("budget_aed", "Budget (AED)", "What budget do you have in mind?", "كم الميزانية تقريباً؟", "money", strict=True),
            _f("finance", "Cash or mortgage", "Will you buy with cash or a mortgage?", "الشراء كاش أو تمويل عقاري؟", "choice", ["Cash", "Mortgage"]),
            _f("mortgage_preapproved", "Mortgage pre-approved", "Do you already have a mortgage pre-approval?", "هل عندك موافقة مبدئية على التمويل؟",
               "yesno", required=False, ask_if={"field": "finance", "op": "=", "value": "Mortgage"}),
            _f("ready_or_offplan", "Ready or off-plan", "Ready to move in, or off-plan?", "جاهز للسكن أو على الخارطة؟", "choice",
               ["Ready", "Off-plan"], required=False),
            _f("timeline", "When", "When are you looking to buy?", "متى تخطط للشراء؟", "choice", ["Now", "1-3 months", "3-6 months", "Later"]),
        ]},
        "tenant": {"label": "Tenant", "fields": [
            AREA, TYPE, BEDS,
            _f("budget_aed", "Yearly rent (AED)", "What yearly rent are you aiming for?", "كم الإيجار السنوي المناسب لك؟", "money", strict=True),
            _f("move_in", "Move-in", "When would you like to move in?", "متى تريد الانتقال؟", "date"),
            _f("family_size", "People living", "How many people will live there?", "كم شخص سيسكن؟", "number", required=False),
        ]},
        "seller": {"label": "Seller", "fields": [
            AREA, TYPE, _f("bedrooms", "Bedrooms", "How many bedrooms does it have?", "كم غرفة نوم فيه؟", "number", required=False),
            _f("asking_price", "Asking price (AED)", "What price are you hoping to sell for?", "كم السعر المطلوب؟", "money", strict=True),
            _f("occupancy_status", "Occupancy", "Is it vacant, tenanted or lived in by you?", "هل هو شاغر، مؤجر أو تسكنه؟", "choice",
               ["Vacant", "Tenanted", "Owner-occupied"]),
            _f("standout_features", "Highlights", "What makes it stand out?", "ما الذي يميزه؟", required=False),
        ]},
        "landlord": {"label": "Landlord", "fields": [
            AREA, TYPE, BEDS,
            _f("expected_rent", "Expected yearly rent (AED)", "What yearly rent are you expecting?", "كم الإيجار السنوي المتوقع؟", "money", strict=True),
            _f("occupancy_status", "Occupancy", "Is it vacant now?", "هل هو شاغر الآن؟", "choice", ["Vacant", "Tenanted", "Owner-occupied"]),
            _f("standout_features", "Highlights", "What makes it stand out?", "ما الذي يميزه؟", required=False),
        ]},
    },
    # n8n IF logic, per type: all of "qualify_when" must hold; any of "not_fit_when" closes the lead politely.
    "rules": {t: {"qualify_when": [], "not_fit_when": [], "not_fit_reply": ""} for t in ("buyer", "tenant", "seller", "landlord")},
}

DETECT = [  # rules-mode guess of the type from the words (the model decides when connected)
    ("landlord", r"\b(let out|rent out|rent my|lease my|landlord|tenant for my)\b"),
    ("seller", r"\b(sell|selling|sale of my|list my)\b|أبيع|بيع"),
    ("tenant", r"\b(rent|renting|lease|to let)\b|إيجار|استأجر|أستأجر"),
    ("buyer", r"\b(buy|buying|purchase|invest|own)\b|أشتري|شراء"),
]


def owner_ids() -> set[str]:
    return {p for p, v in PEOPLE.items() if v["role"] == "Owner"}


# ---------- the form ----------

def form(g: Graph) -> dict:
    """The form in force: the owner's latest saved version, or the default (version 0)."""
    saved = getattr(g, "qualify_form", None)
    return copy.deepcopy(saved) if saved else copy.deepcopy(DEFAULT_FORM) | {"version": 0}


def validate(f: dict) -> list[str]:
    errs = []
    if not f.get("types"):
        errs.append("Add at least one customer type")
    for t, spec in (f.get("types") or {}).items():
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", t):
            errs.append(f"Type id {t!r}: lowercase letters, digits and _ only")
        keys = [x.get("key") for x in spec.get("fields", [])] + [x.get("key") for x in f.get("common", [])]
        for x in spec.get("fields", []) + f.get("common", []):
            if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", x.get("key") or ""):
                errs.append(f"{spec.get('label', t)}: field key {x.get('key')!r} must be lowercase letters, digits and _")
            if x.get("kind") not in KINDS:
                errs.append(f"{x.get('label') or x.get('key')}: unknown kind {x.get('kind')!r}")
            if x.get("kind") == "choice" and not x.get("options"):
                errs.append(f"{x.get('label') or x.get('key')}: a choice needs options")
            if not (x.get("question_en") or "").strip():
                errs.append(f"{x.get('label') or x.get('key')}: write the question")
        rules = (f.get("rules") or {}).get(t, {})
        for cond in rules.get("qualify_when", []) + rules.get("not_fit_when", []):
            if cond.get("field") not in keys:
                errs.append(f"{spec.get('label', t)}: a condition uses {cond.get('field')!r}, which is not one of its questions")
            if cond.get("op") not in OPS:
                errs.append(f"{spec.get('label', t)}: unknown condition {cond.get('op')!r}")
        if rules.get("not_fit_when") and not (rules.get("not_fit_reply") or "").strip():
            errs.append(f"{spec.get('label', t)}: write the polite reply for leads that are not a fit")
    return errs


def save_form(office: Office, f: dict, *, by: str) -> dict:
    """Only the owner changes the form. Each save is a new version; the old ones stay in the log."""
    if by not in owner_ids():
        raise PermissionError("Only the owner can change the qualification questions and conditions")
    f = {k: v for k, v in f.items() if k in ("common", "types", "rules")}
    for t in f.get("types", {}):
        f.setdefault("rules", {}).setdefault(t, {"qualify_when": [], "not_fit_when": [], "not_fit_reply": ""})
    if errs := validate(f):
        raise ValueError("; ".join(errs))
    version = form(office.graph()).get("version", 0) + 1
    return office.log.append("qualify.form", actor=by, content=f | {"version": version})


# ---------- answers and the verdict ----------

def number(v) -> float | None:
    from diwan.agents.scribe import amounts
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "")
    found = amounts(s) or [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", s)]
    return float(found[0]) if found else None


def holds(cond: dict, answers: dict) -> bool:
    a = answers.get(cond.get("field"))
    a = None if a and a.get("unsure") else a  # "not sure" is no value to compare
    val = a["value"] if a else None
    op, want = cond.get("op"), cond.get("value")
    if op == "is set":
        return a is not None
    if op == "is not set":
        return a is None
    if a is None:
        return False
    if op in (">=", "<=", ">", "<"):
        x, y = number(val), number(want)
        return x is not None and y is not None and {">=": x >= y, "<=": x <= y, ">": x > y, "<": x < y}[op]
    sv, sw = str(val).strip().lower(), str(want or "").strip().lower()
    if op == "=":
        return sv == sw or (number(val) is not None and number(val) == number(want))
    if op == "!=":
        return not (sv == sw or (number(val) is not None and number(val) == number(want)))
    if op == "contains":
        return sw in sv
    items = [w.strip().lower() for w in str(want or "").split(",") if w.strip()]
    inside = any(w in sv or sv in w for w in items)
    return inside if op == "in" else not inside


def describe(cond: dict) -> str:
    return f"{cond.get('field')} {cond.get('op')} {cond.get('value')}".strip() if cond.get("op") not in ("is set", "is not set") \
        else f"{cond.get('field')} {cond.get('op')}"


def fields_for(f: dict, qtype: str | None) -> list[dict]:
    return f.get("common", []) + ((f["types"].get(qtype) or {}).get("fields", []) if qtype else [])


def evaluate(f: dict, qtype: str | None, answers: dict) -> dict:
    """The verdict for these answers under this form. Pure: the same answers always get the same verdict."""
    if not qtype or qtype not in f["types"]:
        return {"verdict": "DISCOVERY", "type": None, "missing": [], "next": None, "reasons": ["customer type not known yet"],
                "version": f.get("version", 0)}
    rules = f.get("rules", {}).get(qtype, {})
    fields = fields_for(f, qtype)
    vague = {k for k, a in answers.items() if a.get("unsure")}
    for cond in rules.get("not_fit_when", []):
        if cond.get("field") not in vague and holds(cond, answers):
            return {"verdict": "NOT_A_FIT", "type": qtype, "missing": [], "next": None, "reasons": [f"not a fit: {describe(cond)}"],
                    "reply": rules.get("not_fit_reply", ""), "version": f.get("version", 0)}
    def answered(x):
        a = answers.get(x["key"])
        return a is not None and not (a.get("unsure") and x.get("strict"))

    needed = [x for x in fields if x.get("required") and not answered(x) and (not x.get("ask_if") or holds(x["ask_if"], answers))]
    # a "must answer" question the customer was not sure about twice: Rania stops asking, a person helps on a call
    stuck = [x for x in needed if (answers.get(x["key"]) or {}).get("times", 0) >= 2]
    ask = [x for x in needed if x not in stuck]
    allowed = [x["label"] for x in fields if x["key"] in vague and not x.get("strict")]
    note = [f"not sure, which the owner allows: {', '.join(allowed)}"] if allowed else []
    base = {"type": qtype, "version": f.get("version", 0), "stuck": [x["key"] for x in stuck]}
    if ask:
        nxt = ask[0]
        return base | {"verdict": "ASK_QUESTION", "missing": [x["key"] for x in needed], "next": nxt,
                       "retry": nxt["key"] if nxt["key"] in vague else None,
                       "reasons": [f"still needed: {', '.join(x['label'] for x in needed)}"]
                       + ([f"not sure twice about {', '.join(x['label'] for x in stuck)}, which the owner requires: the broker helps"]
                          if stuck else [])}
    if stuck:
        return base | {"verdict": "ASK_QUESTION", "missing": [x["key"] for x in stuck], "next": None, "hold": True,
                       "reasons": [f"the customer is not sure about {', '.join(x['label'] for x in stuck)}, which the owner requires: "
                                   "a person follows up"]}
    failing = [describe(c) for c in rules.get("qualify_when", []) if c.get("field") not in vague and not holds(c, answers)]
    if failing:
        return base | {"verdict": "ASK_QUESTION", "missing": [], "next": None, "hold": True,
                       "reasons": [f"all answered, but a condition does not hold: {'; '.join(failing)}"]}
    return base | {"verdict": "PASS_TO_AGENT", "missing": [], "next": None,
                   "reasons": ["every required answer is in" + (" and every condition holds" if rules.get("qualify_when") else "")] + note}


def state(g: Graph, deal: str) -> dict:
    d = g.nodes[f"deal:{deal}"].props
    f = form(g)
    answers = d.get("answers", {})
    v = evaluate(f, d.get("qtype"), answers)
    labels = {x["key"]: x["label"] for x in fields_for(f, d.get("qtype"))}
    return v | {"answers": [{"key": k, "label": labels.get(k, k), **a} for k, a in answers.items()],
                "open_questions": d.get("open_questions", []),
                "type_label": (f["types"].get(d.get("qtype")) or {}).get("label"), "type_quote": d.get("qtype_quote"), "type_source": d.get("qtype_source"),
                "status": d.get("qualify_status")}


# ---------- reading answers out of what the customer wrote ----------

def _areas(g: Graph) -> list[str]:
    known = {n.props["community"] for n in g.of("listing")} | {
        "Dubai Marina", "JVC", "Jumeirah Village Circle", "Business Bay", "Downtown Dubai", "Palm Jumeirah", "Dubai Hills",
        "Yas Island", "Saadiyat", "Al Reem", "Arabian Ranches", "JLT", "Damac Hills", "Creek Harbour", "Al Barsha", "Meydan"}
    return sorted(known, key=len, reverse=True)


def read_rules(g: Graph, f: dict, qtype: str | None, text: str, last_asked: str | None) -> tuple[str | None, list[dict]]:
    """Plain rules, for when no model answers: the type from its words, and answers that are unmistakable."""
    from diwan.agents.scribe import amounts
    low = text.lower()
    found_type = None
    if not qtype:
        found_type = next((t for t, rx in DETECT if t in f["types"] and re.search(rx, low)), None)
    t = qtype or found_type
    out = []
    for x in fields_for(f, t):
        k, kind = x["key"], x["kind"]
        v = None
        vague = last_asked == k and unsure(text)
        if kind == "money":
            nums = [a for a in amounts(text) if a >= 1000]
            if nums and (re.search(r"budget|price|rent|million|\bk\b|aed|dirham|\d", low)):
                v = max(nums)
        elif kind == "number" and k == "bedrooms":
            if m := re.search(r"\b(\d|one|two|three|four|five|six)\s*-?\s*(bed|br|bedroom)", low):
                v = int(m.group(1)) if m.group(1).isdigit() else ["one", "two", "three", "four", "five", "six"].index(m.group(1)) + 1
            elif "studio" in low:
                v = 0
        elif kind == "area":
            v = next((a for a in _areas(g) if a.lower() in low or a.lower().replace("dubai ", "") in low), None)
        elif kind == "choice":
            v = next((o for o in x["options"] if option_said(o, low)), None)
        elif kind == "yesno" and last_asked == k and not vague:
            v = "Yes" if re.search(r"\b(yes|yeah|yep|sure|already|نعم|ايوه)\b", low) else "No" if re.search(r"\b(no|not yet|nope|لا)\b", low) else None
        elif kind in ("text", "date", "number") and last_asked == k and not vague and len(text) < 160 and not text.strip().endswith("?"):
            if kind == "date" and not re.search(r"\d|now|asap|soon|next|this|week|month|year|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
                                                r"شهر|أسبوع|الآن|قريب", low):
                continue
            v = text.strip()
        if v is not None and v != "":
            out.append({"field": k, "value": v, "quote": text.strip()[:200]})
        elif vague:
            out.append({"field": k, "value": NOT_SURE, "quote": text.strip()[:200], "unsure": True})
    return found_type, out


def record(office: Office, deal: str, *, qtype: str | None, type_quote: str | None, answers: list[dict], said: str,
           by: str, cause: int | None) -> list[str]:
    """Keep only answers whose quote the customer really wrote; a new answer to a field replaces the old one."""
    from diwan.pack import norm
    g = office.graph()
    d = g.nodes[f"deal:{deal}"].props
    f = form(g)
    keys = {x["key"]: x for x in fields_for(f, qtype or d.get("qtype"))}
    kept = []
    if qtype and qtype in f["types"] and qtype != d.get("qtype"):
        office.log.append("qualify.type", actor=by, agent="rania", deal=deal, caused_by=cause,
                          content={"type": qtype, "quote": type_quote, "was": d.get("qtype")})
    for a in answers:
        k = a.get("field")
        if k not in keys or a.get("value") in (None, ""):
            continue
        if not a.get("quote") or norm(a["quote"]) not in norm(said):
            continue  # a quote the customer did not write is never kept
        old = d.get("answers", {}).get(k)
        if a.get("unsure") or unsure(a["value"]):
            # "not sure" only answers the question she just asked, never replaces a real answer, and counts once a message
            if k != d.get("qualify_asked") or (old and not old.get("unsure")) or (old and old.get("cause") == cause):
                continue
            office.log.append("qualify.answer", actor=by, agent="rania", deal=deal, caused_by=cause,
                              content={"field": k, "value": NOT_SURE, "quote": a["quote"][:300], "unsure": True})
            kept.append(k)
            continue
        if old and not old.get("unsure") and str(old["value"]) == str(a["value"]):
            continue
        office.log.append("qualify.answer", actor=by, agent="rania", deal=deal, caused_by=cause,
                          content={"field": k, "value": a["value"], "quote": a["quote"][:300], "replaces": (old or {}).get("value")})
        kept.append(k)
    return kept


def schema_part(f: dict) -> dict:
    """What the model returns next to its reply: the customer type it heard, and answers with the customer's words."""
    return {"customer_type": {"type": ["string", "null"]},
            "answers": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["field", "value", "quote"],
                                                    "properties": {"field": {"type": "string"}, "value": {"type": "string"},
                                                                   "quote": {"type": "string"}}}}}


def prompt_block(f: dict, st: dict, arabic: bool, broker: str, no_calls: bool = False) -> str:
    """The qualification part of Rania's instructions for this one reply."""
    types = ", ".join(f"{t} ({s['label']})" for t, s in f["types"].items())
    lines = [f"Qualification (set by the owner, version {f.get('version', 0)}). Customer types: {types}."]
    if st["verdict"] == "DISCOVERY":
        lines.append("You do not know yet what they want: find out whether they want to buy, rent, sell or let out (one question).")
    else:
        lines.append(f"Customer type: {st['type']}.")
        done = [a for a in st["answers"] if a["key"] not in (st.get("missing") or [])]
        if done:
            lines.append("Already answered (never ask again): " + "; ".join(f"{a['label']} = {a['value']}" for a in done))
        if st.get("next"):
            q = st["next"]["question_ar" if arabic and st["next"].get("question_ar") else "question_en"]
            if st.get("retry"):
                lines.append(f"They said they are not sure about {st['next']['label']}, and the owner needs a real answer. Say a rough "
                             f"idea is fine, help them (offer a range or the options), and ask once more: {q}")
            else:
                lines.append(f"Next question, the only one to ask in this message (in your own words, after answering what they asked): {q}")
        elif st.get("stuck"):
            lines.append(f"They are not sure about something the owner requires: say kindly that {broker} will {'reply here' if no_calls else 'call'} to help with it. Ask nothing more.")
        elif st["verdict"] == "PASS_TO_AGENT":
            lines.append(f"Everything needed is in: thank them and say {broker} will contact them shortly. Ask nothing more.")
    fields = "; ".join(f"{x['key']} ({x['kind']}{': ' + '/'.join(x['options']) if x['options'] else ''})"
                       for x in fields_for(f, st.get("type")) or fields_for(f, None))
    lines.append("In customer_type and answers, return what THIS message tells you: customer_type is one of the type ids or null; "
                 f"answers use these fields only: {fields}. Each answer quotes the customer's exact words. If they say they don't know "
                 "or aren't sure to the question you asked, or their answer depends on something (\"when I find the right project\"), return "
                 "that field with value \"not sure\": never ask the same question again. A \"not\" or \"don't\" before an option "
                 "means they don't want it. Return none if none.")
    return "\n".join(lines)


def again(q: dict, arabic: bool) -> str:
    """Rules mode, a "must answer" question they were not sure about: help, then ask once more."""
    if arabic:
        return f"لا مشكلة، فكرة تقريبية تكفي. {q.get('question_ar') or q['question_en']}"
    return f"No problem, a rough idea is fine. {q['question_en']}"


def stuck_reply(arabic: bool, broker: str, no_calls: bool = False) -> str:
    if no_calls:  # they asked not to be called
        return f"لا مشكلة! سيساعدك {broker} في ذلك هنا." if arabic else f"No problem! {broker} will help you with that here."
    if arabic:
        return f"لا مشكلة! سيتصل بك {broker} ليساعدك في ذلك."
    return f"No problem! {broker} will give you a call to help with that."


def closing(arabic: bool, first: str | None, broker: str) -> str:
    if arabic:
        return f"شكراً{' ' + first if first else ''}! عندي كل المعلومات اللازمة، وسيتواصل معك {broker} قريباً."
    return f"Thank you{' ' + first if first else ''}! I have everything {broker} needs, and {broker} will contact you shortly."
