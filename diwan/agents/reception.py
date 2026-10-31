"""Rania, the receptionist on WhatsApp. Every message is heard by the Scribe first, so what a buyer types at midnight is
the same quoted fact as what they say in a meeting. Then Rania replies from confirmed company knowledge and permitted
listings only, books viewings in a broker's free slot, and hands the chat to a person whenever asked or whenever the
question is not hers to answer. While a person has the chat, Rania only suggests replies.

A model reply that names an amount not found in the listings or knowledge it was given is not sent: the chat goes to
the broker instead. That is how "never quote a price that is not on a listing" is enforced, not just asked for.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from diwan import slots
from diwan.agents import lessons, runner, scribe
from diwan.agents.charters import get
from diwan.graph import Graph, Node
from diwan.office import Office
from diwan.pack import Action, Pack
from diwan.people import name
from diwan.config import env
from diwan.providers import whatsapp

RANIA = "rania"
COMPANY = "Diwan Realty"

HANDOVER = r"\b(agent|human|real person|someone|call me|speak to|talk to|broker|manager)\b"
NOT_MINE = (r"\b(cash|crypto|bitcoin|usdt|source of (funds|wealth)|aml|sanction\w*|anonymous|without (id|documents|kyc)|"
            r"no (id|documents)|third party|offshore|negotiat\w*|discount|lower (the )?price|best price|commission split)\b")
RETURNS = r"\b(roi|returns?|yield|guarantee\w*|rental income|appreciat\w*)\b"
# "a project with good ROI" is what they want; "what ROI will I get?" or "is the return guaranteed?" gets the fixed answer
FINANCE_ASK = r"\b(mortgage|financ\w*|loan|payment|installment)s?\s+(option|options|plan|plans)\b"

PRICE = r"\b(price|how much|cost|asking|aed\?)\b|\bpp\b|السعر|كم"
BOOK = (r"\b(view|viewing|visit|book|appointment|come (by|over)|show me)\b"
        r"|\bsee (it|this|that|them|one|the (property|unit|flat|apartment|villa|townhouse|place|house|penthouse))\b")  # not "once I see a good project"
SEARCH = r"\b(bed|br|bedroom|studio|villa|apartment|flat|townhouse|looking for|budget|available|listings?|options?|anything)\b"

RECEPTION_SCHEMA = {"name": "reception", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["reply", "listing_refs", "knowledge_refs", "book_listing", "book_when", "handover"],
    "properties": {"reply": {"type": "string"}, "listing_refs": {"type": "array", "items": {"type": "string"}},
                   "knowledge_refs": {"type": "array", "items": {"type": "string"}},
                   "book_listing": {"type": ["string", "null"]}, "book_when": {"type": ["string", "null"]},
                   "handover": {"type": "boolean"}}}}

QUESTION = r"\?|؟|^(do|does|can|could|is|are|what|when|where|which|who|how|why|will|would)\b"
SOFT_HANDOVERS = {"Rania couldn't answer", "no listing fits the brief", "Rania handed over: the sources did not cover it"}


def clean_text(t: str) -> str:
    """A model reply as the client should see it: an emoji that arrived mis-encoded ("ð\x9f\x98\x8a") is repaired when
    its bytes are all there, and a leftover fragment (a lone "ð", invisible control characters) is dropped."""
    def fix(m):
        try:
            return m.group(0).encode("latin-1").decode("utf-8")
        except UnicodeError:
            return m.group(0)
    t = re.sub(r"[\u00c2-\u00f4][\u0080-\u00bf]{1,3}", fix, t)
    t = re.sub(r"[\u0080-\u009f]", "", t)
    t = re.sub(r"(^|\s)[\u00f0-\u00f4](?=\s|$)", r"\1", t)  # the first byte of a 4-byte emoji, alone
    return re.sub(r"  +", " ", t)


def asks_returns(low: str) -> bool:
    return bool(re.search(RETURNS, low) and re.search(r"\?|؟|\b(guarantee\w*|promis\w*|assured|fixed return|what|how much|expect\w*|will i (get|make)|can i (get|make))\b", low))


def qualify_schema(form: dict) -> dict:
    """Rania's answer format: her reply, plus the customer type and answers she heard in this message."""
    from diwan import qualify
    s = {**RECEPTION_SCHEMA, "schema": {**RECEPTION_SCHEMA["schema"]}}
    s["schema"]["properties"] = RECEPTION_SCHEMA["schema"]["properties"] | qualify.schema_part(form)
    s["schema"]["required"] = RECEPTION_SCHEMA["schema"]["required"] + ["customer_type", "answers"]
    return s


GUIDE = f"""
You are on WhatsApp for {COMPANY}, a Dubai real-estate brokerage. Write like a helpful person on WhatsApp: warm and
short (one to three sentences), in the customer's language (Arabic or English; reply in Gulf Arabic if they write it).
Answer in the `reception` format.

How to run the conversation:
- Answer what they asked first. Show only listings that are in the sources (ref, place, beds, price), never more than
  the Recommendations block below allows, then ask at most one question.
- Do not repeat a listing you already showed in this conversation unless they ask about it again; just move on.
- A listing fits only if it matches everything they have said so far: buy or rent, area, type, bedrooms and budget.
  Leave out anything that does not.
- If nothing fits, never say we don't have it or have nothing listed: say a broker will contact them with options that
  fit, and keep going with the Qualification questions (handover false): the broker takes over once they are qualified.
- If they ask to view or book without saying which listing, and more than one is in play, ask which one.
- When they ask something else (fees, hours, process), just answer it. Do not list properties again unless they ask.
- First reply to a new customer who has not said what they want: say "I'm Rania from {COMPANY}" and ask ONE open
  question: are they looking to buy, rent, or sell or let out? Never assume they are buying.
- Ask at most one question per message. The Qualification block below says what is still needed: its next question is
  the only one you may ask. Read the whole conversation and "What this customer has told us": never ask for anything
  they already said, even if they changed their mind about something else.
- "Booked for this customer, on the calendar" lines are the truth about their appointments and calls. When they ask or
  mention the time, say exactly that time; if an earlier message of the conversation says another time, the calendar
  is right (it was moved). Never promise a time that is not there.
- Refer to a broker or colleague by name, never "he" or "she": you do not know their pronouns.
- Every listing in the sources says whether it is for sale or for rent. Never offer a sale listing to someone renting.
- Use the customer's first name only if one is given below. Never invent a name.
- Facts about listings, prices, fees and the company come only from the sources; name the listing ref you mean. If the
  sources do not answer, say a broker will confirm and set handover to true.
- To book a viewing, set book_listing to the ref and book_when to the day and time the customer asked for, in their words.
- Set handover to true when the customer asks for a person, or asks about payment methods, discounts, negotiation,
  returns, documents, checks, or anything the sources do not answer. Never explain why."""

NOT_NAMES = {"test", "customer", "lead", "buyer", "whatsapp", "instagram", "user", "unknown", "new"}


def first_name(label: str | None) -> str | None:
    """A first name worth using: a real word, not a number, a placeholder or "Test"."""
    w = (label or "").strip().split(" ")[0]
    if len(w) < 2 or not w[0].isalpha() or w.lower() in NOT_NAMES:
        return None
    return w


MAX_LISTINGS = 8  # with a big catalog, only the listings that fit this customer go into the prompt


def prompt_sources(g: Graph, deal: str, chat: Node, text: str, *, listings: bool = True, n: int = MAX_LISTINGS) -> dict[str, str]:
    """What Rania may read for this reply: what the customer told us, then only what knowledge.search() returns
    (confirmed, customer-facing, in-date knowledge and advertised listings that fit), and the conversation so far (the
    newest message is in the task line, not repeated here). Internal-only items never reach her."""
    from diwan import knowledge
    out = {f.id: g.record(f.id) for f in g.facts(deal)}  # "What this customer has told us"
    asked = recent_words(chat, text)
    # only as many listings as the owner allows, and none while qualifying unless the customer asks (the setting)
    found = knowledge.search(g, asked, k=n, tabs={"listing"}, offering=_offering(g, deal)) if listings else []
    named = [n_.id for n_ in advertisable(g) if n_.props["ref"].lower() in text.lower()]
    mentioned = [r for m in chat.props["messages"] for r in m.get("refs", []) if r.startswith("listing:")]
    ids = list(dict.fromkeys(named + [i["id"] for i in found] + [r for r in mentioned if r in g.nodes and knowledge.usable(g.nodes[r])]))
    out |= {i: f"{g.record(i)} · for {'rent' if 'rent' in (g.nodes[i].props.get('offering') or '') else 'sale'}" for i in ids[:max(n, len(named))]}
    out |= {i["id"]: i["record"] for i in knowledge.search(g, asked, k=6, tabs=KNOWLEDGE_TABS)}
    who = lambda m: "Customer" if m["type"] == "received" else "Rania" if m["by"] == RANIA else name(m["by"])  # noqa: E731
    history = [m for m in chat.props["messages"] if m["type"] in ("received", "sent")][:-1][-8:]
    out |= {f"msg:{m['event']}": f"{who(m)}: {m['text']}" for m in history}
    # what is booked for this customer, from the calendar (the conversation may describe a time that was later moved)
    for v in g.of("viewing", status="booked"):
        if v.props.get("chat") == chat.props["phone"] and datetime.fromisoformat(v.props["at"]) > datetime.now(slots.DUBAI) - timedelta(hours=1):
            k = slots.kind(g, v.props.get("kind"))
            out[f"appt:{v.id}"] = (f"Booked for this customer, on the calendar: {k['name']}"
                                   f"{' of ' + v.props['listing'] if v.props.get('listing') else ''} with {name(v.props['broker'])}, "
                                   f"{slots.say(datetime.fromisoformat(v.props['at']))}")
    return out


KNOWLEDGE_TABS = {"company", "answer", "project", "area", "people", "brand"}  # everything but listings


def recent_words(chat: Node | None, text: str, n: int = 4) -> str:
    """The customer's last few messages and the new one: what a search should look for."""
    said = [m["text"] for m in (chat.props["messages"] if chat else []) if m["type"] == "received"][-n:]
    return " ".join(dict.fromkeys(said + [text]))


def customer_knowledge(g: Graph, text: str, k: int = 3) -> list[dict]:
    from diwan import knowledge
    return knowledge.search(g, text, k=k, tabs=KNOWLEDGE_TABS)


def _offering(g: Graph, deal: str | None) -> str | None:
    """A buyer sees listings for sale, a tenant listings for rent (from the qualification type)."""
    from diwan import knowledge
    return knowledge.FOR.get((g.nodes.get(f"deal:{deal}") or Node("", "", "")).props.get("qtype")) if deal else None


# ---------- recommendations and the hot lead (the owner's setting, on the Qualification screen) ----------

RECOMMEND = {"when": "after_qualified", "how_many": 3, "hot_on": ["pick", "viewing"]}
WHEN = {"after_qualified": "Once the lead qualifies (and when the customer asks for listings)",
        "as_soon_as_fit": "As soon as something fits what they said",
        "never": "Never: the broker sends the options"}
HOT_ON = {"pick": "They pick one of the recommended properties", "viewing": "They ask to view one",
          "qualified": "They qualify", "call": "They ask for a call (once qualified)"}
ASKING = r"\?|؟|\b(any|do you have|have you got|show me|send me|options|listings?|available|what (do you|have you) got)\b"
INTEREST = r"\b(interested|i like|i love|love it|that one|this one|sounds good|perfect|go with|let'?s do)\b|يعجبني|مهتم"
ORDINAL = {"first": 0, "1st": 0, "one": 0, "1": 0, "second": 1, "2nd": 1, "two": 1, "2": 1, "third": 2, "3rd": 2, "three": 2, "3": 2,
           "fourth": 3, "4th": 3, "four": 3, "4": 3, "fifth": 4, "5th": 4, "five": 4, "5": 4, "last": -1}


def recommend_settings(g: Graph) -> dict:
    return RECOMMEND | (g.settings.get("rania", {}).get("recommend") or {})


def set_recommend(office: Office, value: dict, *, by: str) -> dict:
    """Only the owner sets when Rania recommends, how many, and what makes a lead hot. Each change is logged."""
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes Rania's recommendations")
    v = recommend_settings(office.graph()) | {k: value[k] for k in RECOMMEND if k in value}
    if v["when"] not in WHEN:
        raise ValueError("Pick when Rania recommends")
    try:
        v["how_many"] = int(v["how_many"])
    except (TypeError, ValueError):
        raise ValueError("How many: a number from 1 to 5") from None
    if not 1 <= v["how_many"] <= 5:
        raise ValueError("How many: a number from 1 to 5")
    v["hot_on"] = [h for h in v.get("hot_on") or [] if h in HOT_ON]
    if not v["hot_on"]:
        raise ValueError("Say what makes a lead hot")
    office.log.append("setting.changed", actor=by, content={"person": "rania", "key": "recommend", "value": v})
    return v


# ---------- the front door: not ready yet, coming back, asking for a call (the owner's setting) ----------

FRONT = {"nurture_to": "marketing", "portal_template": None}
NURTURE_TO = {"marketing": "Marketing nurtures them", "broker": "Their broker keeps them", "none": "Nobody: park the chat"}
# only looking for now; "not interested in villas" or "not looking at JVC" is a preference, not this
NOT_READY = (r"\b(just|only) (looking|browsing|checking|curious)\b|\bnot (now|ready|in the market)\b|\bnot (interested|looking)\b(?!\s+(in|at|for)\b)"
             r"|\bmaybe (later|next (year|month))\b|\bno longer (interested|looking)\b|\bwindow shopping\b"
             r"|مجرد (أتفرج|اطلع|أشوف)|مو الحين|مش دلوقتي|مش مهتم|غير مهتم|بعدين")
CALL_ME = (r"\b(call me|call me back|call back|callback|give me a call|phone me|ring me|"
           r"(can|could|would) (you|someone|somebody|anyone) (please )?(call|phone|ring)|(want|like|prefer) (a|to get a|to have a) (phone )?call)\b"
           r"|اتصل (بي|علي)|اتصلوا|كلمني|تتصل")
READY = r"\b(ready|interested|i want to (buy|rent)|looking to (buy|rent)|options|what do you have|send me)\b|مهتم|جاهز"


def front_settings(g: Graph) -> dict:
    return FRONT | (g.settings.get("rania", {}).get("front") or {})


def set_front(office: Office, value: dict, *, by: str) -> dict:
    """Only the owner sets who nurtures leads that are not ready, and the first message to a portal lead."""
    from diwan import qualify
    if by not in qualify.owner_ids():
        raise PermissionError("Only the owner changes the front door")
    v = front_settings(office.graph()) | {k: value[k] for k in FRONT if k in value}
    if v["nurture_to"] not in NURTURE_TO:
        raise ValueError("Pick who nurtures leads that are not ready")
    v["portal_template"] = v["portal_template"] or None
    office.log.append("setting.changed", actor=by, content={"person": "rania", "key": "front", "value": v})
    return v


def front_reply(front: str, arabic: bool, first: str | None, broker: str, at: datetime | None = None, at_ok: bool = True,
                same: bool = False, busy: list[datetime] | None = None) -> str:
    you = f" {first}" if first else ""
    if front == "call" and busy is not None:  # the time they asked for is taken: the nearest free ones, and the broker is told
        opts = ", ".join(slots.say(t) for t in busy)
        if arabic:
            return f"أكيد{you}! {broker} غير متاح في ذلك الوقت" + (f"، لكنه يستطيع الاتصال {opts}. أي وقت يناسبك؟" if busy else "، وسيتصل بك في أقرب وقت.")
        return (f"Of course{you}. {broker} isn't free then" + (f"; {broker} could call you {opts}. Which suits you?" if busy else ", and will call you as soon as he can.")
                + f" I've let {broker} know you'd like a call.")
    if front == "call" and at and same:  # they are checking a call already set for that time
        return (f"نعم{you}، {broker} سيتصل بك {slots.say(at)}." if arabic else f"Yes{you}, {broker} will call you {slots.say(at)}.")
    if front == "call" and at:  # the time they asked for, said back to them
        if not at_ok:
            return (f"أكيد{you}. أبلغت {broker}، لكنه لا يعمل في ذلك الوقت، فسيتصل بك في أقرب وقت ممكن منه." if arabic else
                    f"Of course{you}. That's outside {broker}'s working hours, so I've asked for a call as close to that time as possible.")
        return f"أكيد{you}! حجزت لك مكالمة مع {broker} {slots.say(at)}." if arabic else f"Of course{you}. I've booked a call with {broker} for {slots.say(at)}."
    if front == "call":
        return f"أكيد{you}! {broker} من فريقنا سيتصل بك قريباً." if arabic else f"Of course{you}. {broker} from our team will call you shortly."
    if front == "stop":
        return ("تمام، لن أرسل لك رسائل أخرى. إذا احتجت أي شيء، اكتب لي هنا." if arabic else
                "Understood. I won't message you again. If you ever need anything, just write here.")
    if front == "nurture":
        return ("ولا يهمك! خذ وقتك، وأنا هنا متى ما احتجت أي معلومة." if arabic else
                f"No problem at all{you}, take your time. I'm here whenever you'd like to know more: just message me.")
    return "العفو! أنا هنا متى ما كنت جاهز." if arabic else "Anytime! I'm here whenever you're ready."


def comes_back(g: Graph, text: str) -> bool:
    """A nurtured client showing real intent again: a budget, a viewing, a call, a pick, asking for options."""
    low = text.lower()
    if re.search(NOT_READY, low):
        return False
    return bool(re.search(BOOK, low) or re.search(CALL_ME, low) or re.search(READY, low) or scribe.amounts(text))


def nurture_list(g: Graph) -> list[dict]:
    """For Marketing: who is not ready yet (in their words) and who was not a fit (the owner's reason)."""
    out = []
    for d in g.deals():
        p = d.props
        chat = next((c for c in g.of("chat") if c.deal == d.deal), None)
        if p.get("optout"):  # said "stop": nobody messages them
            continue
        if p.get("nurture"):
            out.append({"deal": d.deal, "customer": p.get("customer"), "chat": chat.props["phone"] if chat else None, "why": (p["nurture"].get("reason") or "not ready yet").capitalize(),
                        "quote": p["nurture"].get("quote"), "since": p["nurture"]["at"], "to": p["nurture"].get("to")})
        elif p.get("qualify_status") == "not_a_fit":
            out.append({"deal": d.deal, "customer": p.get("customer"), "chat": chat.props["phone"] if chat else None, "why": "Not a fit",
                        "quote": p.get("qualify_reason"), "since": p.get("qualify_at"), "to": front_settings(g)["nurture_to"]})
    return sorted(out, key=lambda r: r["since"] or "", reverse=True)


def recommend(g: Graph, deal: str, n: int) -> list[Node]:
    """The best `n` advertised listings for this customer's qualification answers: their offering (buy or rent), area,
    type, bedrooms and budget, closest to the budget first. Nothing that misses an answer they gave."""
    from diwan import deal_kinds, knowledge, qualify
    answers = {k: v["value"] for k, v in g.nodes[f"deal:{deal}"].props.get("answers", {}).items() if not v.get("unsure")}
    dk = deal_kinds.kind_for(g, deal)
    offering = (dk or {}).get("listings", {}).get("offering") or _offering(g, deal)
    areas = knowledge.areas_in(g, str(answers.get("areas", ""))) if answers.get("areas") else set()
    beds, budget = qualify.number(answers.get("bedrooms")), qualify.number(answers.get("budget_aed"))
    kind = str(answers.get("property_type") or "").lower()
    built = COMPLETION.get(str(answers.get("ready_or_offplan") or "").lower())
    out = []
    for n_ in advertisable(g):
        p = n_.props
        if offering and p.get("offering") and p["offering"] != offering:
            continue
        if built and p.get("completion") and p["completion"] != built:
            continue
        if not deal_kinds.fits(dk, p):
            continue
        if answers.get("areas") and p["community"].lower() not in areas:
            continue  # an area they named that we have nothing in ("Palm Jumeirah") matches nothing, not everything
        if beds is not None and p["beds"] != int(beds):
            continue
        if budget and p["price_aed"] > budget * 1.05:
            continue
        if kind in ("apartment", "villa", "townhouse", "penthouse") and p["type"] != kind:
            continue
        out.append(n_)
    out.sort(key=lambda x: (abs(budget - x.props["price_aed"]) if budget else 0, -x.event))
    return out[:n]


COMPLETION = {"ready": "ready", "off-plan": "off_plan", "off plan": "off_plan"}  # the client's answer → the listing's field


def nearest(g: Graph, deal: str, n: int) -> tuple[list[Node], str]:
    """Nothing fits every answer: the closest listings, loosening one thing at a time in the order a client usually
    gives way (the type, then the bedrooms, then up to 15% over budget), never what they're buying or renting or the
    kind of deal they chose, never the area they named. Returns the listings and what differs, in words."""
    from diwan import deal_kinds, qualify
    d = g.nodes[f"deal:{deal}"].props
    answers = {k: v["value"] for k, v in d.get("answers", {}).items() if not v.get("unsure")}
    dk = deal_kinds.kind_for(g, deal)
    offering = (dk or {}).get("listings", {}).get("offering") or _offering(g, deal)
    beds, budget = qualify.number(answers.get("bedrooms")), qualify.number(answers.get("budget_aed"))
    kind = str(answers.get("property_type") or "").lower()
    built = COMPLETION.get(str(answers.get("ready_or_offplan") or "").lower())
    from diwan import knowledge
    areas = knowledge.areas_in(g, str(answers.get("areas", ""))) if answers.get("areas") else set()
    pool = [x for x in advertisable(g) if (not offering or not x.props.get("offering") or x.props["offering"] == offering) and deal_kinds.fits(dk, x.props)
            and not (built and x.props.get("completion") and x.props["completion"] != built)
            and not (answers.get("areas") and x.props["community"].lower() not in areas)]  # the area they named is never loosened
    steps = [("type", lambda p: (beds is None or p["beds"] == int(beds)) and (not budget or p["price_aed"] <= budget * 1.05)),
             ("bedrooms", lambda p: (kind not in ("apartment", "villa", "townhouse", "penthouse") or p["type"] == kind) and (not budget or p["price_aed"] <= budget * 1.05)),
             ("budget", lambda p: (beds is None or p["beds"] == int(beds)) and (kind not in ("apartment", "villa", "townhouse", "penthouse") or p["type"] == kind)
              and (not budget or p["price_aed"] <= budget * 1.15))]
    for what, ok in steps:
        found = sorted((x for x in pool if ok(x.props)), key=lambda x: (abs(budget - x.props["price_aed"]) if budget else 0, -x.event))[:n]
        if found:
            return found, what
    return [], ""


def no_exact_match(g: Graph, deal: str, near: list[Node], differs: str, arabic: bool, first: str | None, broker: str) -> str:
    """When nothing fits every answer: the broker connects with options for what they asked for (never "we don't have
    it", product owner 30 Oct), and meanwhile the closest, each with how it differs."""
    from diwan import deal_kinds, qualify
    d = g.nodes[f"deal:{deal}"].props
    a = {k: v["value"] for k, v in d.get("answers", {}).items() if not v.get("unsure")}
    dk = deal_kinds.kind_for(g, deal)
    beds, budget = qualify.number(a.get("bedrooms")), qualify.number(a.get("budget_aed"))
    want = " ".join(x for x in [
        (dk or {}).get("name", "").lower() if (dk or {}).get("listings", {}).get("completion") else "",
        f"{int(beds)}-bed" if beds is not None else "", str(a.get("property_type") or "property").lower()] if x)
    area = a.get("areas") if a.get("areas") and str(a.get("areas")).lower() != "not sure" else None
    around = (f" in {area}" if area else "") + (f" around AED {int(budget):,}" if budget else "")
    hi = f"Thank you{' ' + first if first else ''}!"
    an_ = lambda w: f"{'an' if w[:1] in 'aeiou' else 'a'} {w}"  # noqa: E731
    if arabic:
        lead = f"شكراً{' ' + first if first else ''}! سيتواصل معك {broker} قريباً بخيارات تناسب طلبك."
        if not near:
            return lead
        return f"{lead} وفي الأثناء، هذه خيارات قريبة قد تعجبك:\n" + "\n".join(f"{i}. {_listing_line(x)}" for i, x in enumerate(near, 1))
    connect = f"{hi} {broker} will contact you shortly with options for {an_(want)}{around}."
    if not near:
        return connect
    an = lambda w: f"{'an' if w[:1] in 'aeiou' else 'a'} {w}"  # noqa: E731
    how = {"type": lambda x: f"{an(x.props['type'])}, not {an(str(a.get('property_type')).lower())}",
           "bedrooms": lambda x: f"{x.props['beds']} bed instead of {int(beds)}" if beds is not None else "",
           "budget": lambda x: f"AED {x.props['price_aed'] - int(budget):,} over your budget" if budget else ""}[differs]
    lines = "\n".join(f"{i}. {_listing_line(x)}" + (f" ({how(x)})" if how(x) else "") for i, x in enumerate(near, 1))
    return f"{connect} Meanwhile, a few close ones you might like:\n{lines}\nWould any be worth a look?"


def _route(office: Office, deal: str, phone: str, cause: int, now: datetime) -> dict | None:
    """Once qualified, the lead's deal kind (the owner's list) decides who handles it: if its broker is not one of the
    kind's brokers, the lead moves to one who is (the listing's agent first), and the change is logged."""
    from diwan import deal_kinds, leads
    g = office.graph()
    k = deal_kinds.kind_for(g, deal)
    if not k:
        return None
    office.log.append("lead.kind", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause, content={"kind": k["id"], "name": k["name"]})
    broker = g.nodes[f"deal:{deal}"].props["broker"]
    if k["brokers"] and broker not in k["brokers"]:
        to, why = leads.pick(g, now, among=k["brokers"])
        leads.assign(office, deal, to, by=RANIA, why=f"{k['name']}: {why}", cause=cause, chat=phone, now=now)
    return k


def picked(g: Graph, deal: str, text: str) -> Node | None:
    """Which recommended listing the customer means: its ref, a word of its title only it has, "the second one", or
    "I like it" when there was only one."""
    shown = [g.nodes[r] for r in g.nodes[f"deal:{deal}"].props.get("recommended", []) if r in g.nodes]
    if not shown:
        return None
    low = text.lower()
    for n_ in shown:
        if n_.props["ref"].lower() in low:
            return n_
    said = set(re.findall(r"[a-z]{4,}", low))
    own = {n_.id: set(re.findall(r"[a-z]{4,}", n_.props["title"].lower())) for n_ in shown}
    for n_ in shown:
        if said & (own[n_.id] - set().union(*(w for i, w in own.items() if i != n_.id))):
            return n_
    m = (re.search(r"\b(first|second|third|fourth|fifth|last|1st|2nd|3rd|4th|5th)\b", low)
         or re.search(r"\b(?:option|number|no\.?|#)\s*(\d|one|two|three|four|five)\b", low) or re.fullmatch(r"\s*(\d)\s*[.)!]?\s*", low))
    if m and m.group(1) in ORDINAL:
        i = ORDINAL[m.group(1)]
        return shown[i] if -len(shown) <= i < len(shown) else None
    if len(shown) == 1 and (re.search(INTEREST, low) or re.search(BOOK, low)):
        return shown[0]
    return None


def options_reply(office: Office, phone: str, deal: str, arabic: bool, first: str | None, broker: str, n: int, cause: int) -> tuple[str, list[str]]:
    """A qualified client asks for options: the listings that fit everything they said, or the broker will send some and,
    meanwhile, the closest (each saying how it differs). Never "we don't have it"."""
    g = office.graph()
    recs = recommend(g, deal, n)
    near, differs = ([], "") if recs else nearest(g, deal, n)
    if recs:
        reply = recommendation_text(g, deal, recs, arabic, first)
    elif near:
        reply = no_exact_match(g, deal, near, differs, arabic, first, broker)
    else:
        reply = (f"سيرسل لك {broker} خيارات تناسب كل ما ذكرته." if arabic else
                 f"{broker} will send you options that fit everything you told me, shortly.")
    shown = recs or near
    if shown:
        office.log.append("lead.recommended", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause,
                          content={"refs": [x.id for x in shown], "chat": phone} | ({"near": differs} if near else {}))
    return reply, [x.id for x in shown]


def recommendation_text(g: Graph, deal: str, recs: list[Node], arabic: bool, first: str | None) -> str:
    lines = "\n".join(f"{i}. {_listing_line(n_)}" for i, n_ in enumerate(recs, 1))
    if arabic:
        return f"شكراً{' ' + first if first else ''}! هذه أفضل الخيارات لك:\n{lines}\nأيها يعجبك؟"
    return f"Thank you{' ' + first if first else ''}! Based on what you told me, these fit best:\n{lines}\nWhich one interests you?"


def advertisable(g: Graph) -> list[Node]:
    return [n for n in g.of("listing", status="available") if n.props.get("permit")]


def _lead(office: Office, phone: str, who: str | None, now: datetime) -> str:
    """The deal this chat belongs to: the chat's own, an open deal for the same customer, or a new WhatsApp lead, which
    goes to a broker on shift (see diwan/leads.py)."""
    from diwan import leads
    g = office.graph()
    ch = g.nodes.get(f"chat:{phone}")
    if ch and ch.deal:
        return ch.deal
    if who:
        same = [d for d in g.deals() if d.props.get("customer", "").lower() == who.strip().lower() and not d.deal.startswith("lead-")]
        if len(same) == 1:
            return same[0].deal
    deal = f"lead-{re.sub(r'[^a-z0-9]', '', phone.lower())[-8:]}"
    to, why = leads.pick(g, now)
    office.open_deal(deal, property="Instagram enquiry" if phone.startswith("ig:") else "WhatsApp enquiry",
                     customer=who or f"+{phone}", broker=to, by=RANIA)
    leads.assign(office, deal, to, by=RANIA, why=why, chat=phone, now=now)
    return deal


def _send(office: Office, phone: str, deal: str, text: str, refs: list[str], by: str = RANIA, cause: int | None = None,
          template: dict | None = None, extra: dict | None = None) -> dict:
    """Send through whichever WhatsApp line is connected (AiSensy, Meta's Cloud API) and log what happened.
    With neither connected the message stays in the sandbox and is marked so."""
    from diwan.providers import aisensy
    from diwan.config import sandbox_only
    via, status, err, mid = "sandbox", "sent", None, None
    choice = "" if sandbox_only() else env("WHATSAPP_PROVIDER") or ("aisensy" if aisensy.available() else "cloud" if whatsapp.available() else "")
    if phone.startswith("ig:"):
        from diwan.providers import instagram
        g = office.graph()
        cid = next((m.get("comment_id") for m in reversed(g.nodes[f"chat:{phone}"].props["messages"]) if m["type"] == "received" and m.get("comment_id")), None)
        via = "instagram" if instagram.ready() and cid and not sandbox_only() else "sandbox"
        try:
            mid = instagram.reply_comment(cid, text) if via == "instagram" else None
        except Exception as e:
            status, err = "failed", str(e)[:300]
        return office.log.append("chat.sent", actor=by, agent=RANIA if by == RANIA else None, deal=deal, caused_by=cause,
                                 content={"chat": phone, "text": text, "refs": refs, "via": via, "status": status, "error": err,
                                          "provider_id": mid, "channel": "instagram"})
    try:
        if choice == "aisensy" and aisensy.available():
            via = "aisensy"
            mid = (aisensy.send_template(phone, template["name"], template.get("params"), template.get("language", "en")) if template
                   else aisensy.send_text(phone, text))["id"]
        elif choice == "cloud" and whatsapp.available():
            via = "cloud"
            whatsapp.send(phone, text)
    except Exception as e:  # the send failed: logged on the message, shown in the Inbox, nothing retried silently
        status, err = "failed", str(e)[:300]
    return office.log.append("chat.sent", actor=by, agent=RANIA if by == RANIA else None, deal=deal, caused_by=cause,
                             content={"chat": phone, "text": text, "refs": refs, "via": via, "status": status, "error": err,
                                      "provider_id": mid, "template": template["name"] if template else None} | (extra or {}))


def hand_over(office: Office, phone: str, *, to: str | None = None, by: str = RANIA, reason: str = "", cause: int | None = None,
              text: str = "", now: datetime | None = None) -> None:
    """The chat goes to a person: the lead's broker unless someone is named. When Rania hands it over, the broker also
    gets an Attention card with a due time and a notice; a person taking it themselves needs neither."""
    from diwan import leads
    g = office.graph()
    deal = g.nodes[f"chat:{phone}"].deal
    to = to or g.nodes[f"deal:{deal}"].props["broker"]
    office.log.append("chat.handover", actor=by, agent=RANIA, deal=deal, caused_by=cause, content={"chat": phone, "mode": "human", "by": to, "reason": reason})
    who = g.nodes[f"chat:{phone}"].label
    office.add_task(deal, RANIA, f"Reply to {who} on WhatsApp{f': {reason}' if reason else ''}", needs_person=to, by=RANIA, caused_by=cause)
    if by == RANIA:
        leads.raise_card(office, phone, reason=reason or "needs a person", text=text, to=to, cause=cause, now=now)


def give_back(office: Office, phone: str, *, by: str) -> None:
    deal = office.graph().nodes[f"chat:{phone}"].deal
    office.log.append("chat.handover", actor=by, deal=deal, content={"chat": phone, "mode": "ai", "by": by})


class WindowClosed(RuntimeError):
    """WhatsApp allows free text only within 24 hours of the customer's last message; after that, a template."""


def send_template(office: Office, phone: str, template: dict, params: list[str], *, by: str) -> dict:
    from diwan import inbox
    ch = office.graph().nodes[f"chat:{phone}"]
    from diwan import leads
    text = inbox.render(template["body"], params)
    ev = _send(office, phone, ch.deal, text, [], by=by, template={"name": template["name"], "params": params,
                                                                  "language": template.get("language", "en")})
    leads.replied(office, phone, by=by, cause=ev["id"])
    return ev


def person_sends(office: Office, phone: str, text: str, *, by: str) -> dict:
    """A person replying from the Inbox. Taking the chat is implied: Rania goes quiet."""
    from diwan import inbox
    g = office.graph()
    ch = g.nodes[f"chat:{phone}"]
    if not inbox.conversation(g, ch, datetime.now(slots.DUBAI))["window_open"]:
        raise WindowClosed("More than 24 hours since the customer's last message: send an approved template instead.")
    if ch.props["mode"] != "human":
        office.log.append("chat.handover", actor=by, deal=ch.deal, content={"chat": phone, "mode": "human", "by": by})
    ev = _send(office, phone, ch.deal, text, [], by=by)
    for t in g.of("task", ch.deal, {"queued"}):
        if t.props["agent"] == RANIA and t.props["action"].startswith(f"Reply to {ch.label} on WhatsApp"):
            office.finish_task(t.id, f"{name(by)} replied", caused_by=ev["id"])
    from diwan import leads
    leads.replied(office, phone, by=by, cause=ev["id"])
    return ev


def _listing_named(g: Graph, text: str, chat: Node | None) -> Node | None:
    """The listing a message names: its reference, or a word of its title that no other listing has ("Ponderosa"),
    never a shared word like "villa" or "marina"."""
    low = text.lower()
    said = set(re.findall(r"[a-z]{4,}", low))
    ads = advertisable(g)
    own = {n.id: set(re.findall(r"[a-z]{4,}", n.props["title"].lower())) for n in ads}
    for n in ads:
        if n.props["ref"].lower() in low:
            return n
    # the building's whole name ("Marina Crest"), when exactly one listing has it: its words alone may be shared
    # ("Harbour Gate", "Marina Crown"), the name together isn't
    building = lambda n: [p.strip().lower() for p in n.props["title"].split(",")  # noqa: E731
                          if len(p.strip()) > 4 and not re.match(r"(unit|apartment|apt|flat|studio|villa|townhouse|penthouse|office|shop)\b", p.strip(), re.I)]
    hits = [n for n in ads if any(re.search(rf"\b{re.escape(b)}\b", low) for b in building(n))]
    if len(hits) == 1:
        return hits[0]
    for n in ads:
        unique = own[n.id] - set().union(*(w for i, w in own.items() if i != n.id))
        if said & unique:
            return n
    for m in reversed(chat.props["messages"] if chat else []):
        refs = [r for r in m.get("refs", []) if r.startswith("listing:") and r in g.nodes]
        if len(refs) == 1:
            return g.nodes[refs[0]]
    return None


def matches(g: Graph, deal: str, text: str) -> list[Node]:
    low = text.lower()
    want_beds = None
    if m := re.search(r"\b(\d|one|two|three|four|five)\s*-?\s*(bed|br|bedroom)", low):
        want_beds = int(m.group(1)) if m.group(1).isdigit() else ["one", "two", "three", "four", "five"].index(m.group(1)) + 1
    elif "studio" in low:
        want_beds = 0
    named = [n for n in advertisable(g) if n.props["ref"].lower() in low]
    if named:
        return named
    budgets = [a for a in scribe.amounts(text) if a >= 50_000] or [f.props["amount_aed"] for f in g.facts(deal, "deal_term")]
    budget = max(budgets) if budgets else None
    kind = next((k for k in ("villa", "apartment", "townhouse") if k in low or (k == "apartment" and "flat" in low)), None)
    from diwan import knowledge
    asked = knowledge.areas_in(g, text)
    offering = knowledge.wants(text).get("offering") or _offering(g, deal)
    out = []
    for n in advertisable(g):
        p = n.props
        if want_beds is not None and p["beds"] != want_beds:
            continue
        if budget and p["price_aed"] > budget * 1.1:
            continue
        if kind and p["type"] != kind:
            continue
        if offering and p.get("offering") and p["offering"] != offering:
            continue
        if not asked or p["community"].lower() in asked:
            out.append(n)
    return out[:3]


VIDEO = r"\b(video( call)?|zoom|teams call|google meet|facetime|online meeting)\b"
OFFICE = r"\b(your office|the office|at the office|office meeting|in person meeting|meet (you )?in person)\b"
MOVE = (r"\b(move|reschedule|re-schedule|postpone|push (it|back)|change (the|my) (time|day|viewing|appointment|meeting|call)|"
        r"(make|change|shift|switch|bump) it|another (time|day)|instead)\b")
CANCEL = r"\b(cancel|can'?t make it|cannot make it|won'?t make it|call (it )?off)\b"
ASKS_WHEN = (r"\b(when|what time|what day|which day)\b.{0,30}\b(my|our|the)\s+(viewing|visit|site visit|appointment|meeting|video call|call)\b"
        r"|\b(is|are) (my|our|the) (viewing|visit|appointment|meeting|video call)\b.{0,20}\b(still on|confirmed|booked)\b"
        r"|\b(what'?s|whats|what is|what|which|when)\s+(the\s+)?(time|day|date)?\b.{0,30}\b(we|you|i)\s+(booked|book|agreed|agree|set|scheduled|fixed|arranged|said)\b"
        r"|\bwhat time did (we|you) (book|agree|set|schedule|fix|arrange|say)\b"
        r"|\bwhen (will|is|does|should|are)\s+(he|she|they|you|someone|the (broker|agent)|\w+)\s+(be\s+)?(call|calling|ring|ringing|phone|phoning|come|coming|visit|visiting)\b")


def appointment_kind(g: Graph, text: str) -> dict | None:
    """The kind of appointment the client asks for, from the owner's list: a video call, the office, or None."""
    low = text.lower()
    want = "video" if re.search(VIDEO, low) else "office" if re.search(OFFICE, low) else None
    return next((k for k in slots.appointments(g) if k["where"] == want), None) if want else None


def upcoming(g: Graph, phone: str, now: datetime, text: str = "") -> Node | None:
    """The client's next booked appointment, or the one they name ("the viewing", "the video call", "the meeting")."""
    vs = sorted((v for v in g.of("viewing", status="booked") if v.props.get("chat") == phone and datetime.fromisoformat(v.props["at"]) > now),
                key=lambda v: v.props["at"])
    low = text.lower()
    want = ("video" if re.search(VIDEO, low) else "office" if re.search(r"\b(office|meeting)\b", low)
            else "phone" if re.search(r"\b(call|phone)\b", low)
            else "property" if re.search(r"\b(viewing|visit|see|showing)\b", low) else None)
    named = [v for v in vs if (v.props.get("where") or "property") == want] if want else []
    return (named or vs or [None])[0]


def _what(g: Graph, k: dict, listing: Node | None) -> str:
    if listing:
        return f"{listing.props['title']} ({listing.props['ref']})" if k["where"] == "property" else f"a {k['name'].lower()} about {listing.props['title']}"
    return f"a {k['name'].lower()}"


def yours(k: dict, listing: Node | None) -> str:
    """How the client hears about their own appointment: "your site visit to Unit 1204 (MC-1204)", "your video call"."""
    if listing and k["where"] == "property":
        return f"your {k['name'].lower()} to {listing.props['title']} ({listing.props['ref']})"
    return f"your {k['name'].lower()}" + (f" about {listing.props['title']}" if listing else "")


def book(office: Office, phone: str, deal: str, listing: Node | None, when: datetime | None, now: datetime, cause: int,
         dry: bool = False, kind: dict | None = None) -> tuple[str, list[str]]:
    """Book a free time for the kind of appointment asked for (the owner's list; a site visit when a property is named).
    A site visit goes to the listing's agent (who has the keys), unless they are away; anything else to the lead's broker.
    The broker's hours, days and other appointments decide what is free. `dry` (Rania is on review) only proposes it."""
    from diwan import leads
    g = office.graph()
    k = kind or slots.kind(g, None)
    agent = listing.props.get("agent") if listing else None
    broker = agent if k["where"] == "property" and agent in leads.brokers() and not leads.setting(g, agent, "away") \
        else g.nodes[f"deal:{deal}"].props["broker"]
    who = g.nodes[f"chat:{phone}"].label
    what, refs = _what(g, k, listing), [listing.id] if listing else []
    options = slots.nearest(g, broker, when, now, 3, k["minutes"]) if when else slots.free(g, broker, now, 3, k["minutes"])
    if when is None or when <= now or not slots.is_open(g, broker, when, k["minutes"]):
        if not options:
            return f"{name(broker)} has no free time in the next two weeks; I've asked them to reply to you here.", refs
        opts = ", ".join(slots.say(t) for t in options)
        lead = "That time isn't available. " if when else ""
        return f"{lead}I can book {what} with {name(broker)} on {opts}. Which suits you?", refs
    if dry:
        return f"I can book {what} with {name(broker)}, {slots.say(when)}. Shall I confirm it?", refs
    vid = f"V{len(g.of('viewing')) + 1}"
    booked_ev = office.log.append("appointment.booked", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause,
                      content={"id": vid, "listing": listing.props["ref"] if listing else None, "broker": broker, "at": when.isoformat(),
                               "customer": who, "chat": phone, "kind": k["id"], "kind_name": k["name"], "minutes": k["minutes"],
                               "where": k["where"]})
    task = (f"Viewing of {listing.props['ref']}" if k["where"] == "property" and listing else f"{k['name']}: {what}")
    office.add_task(deal, RANIA, f"{task} with {who}, {slots.say(when)}", needs_person=broker, by=RANIA, caused_by=cause)
    from diwan import video
    url = video.make(office, vid, by=RANIA, cause=booked_ev["id"]) if k["where"] == "video" and video.settings(g)["auto"] else None
    place = {"property": "", "office": " at our office", "phone": " by phone",
             "video": f" by video ({k['minutes']} min). Join here at that time: {url}" if url else f" by video ({k['minutes']} min): {name(broker)} will send the link"}[k["where"]]
    lobby = k["where"] == "property" and any("photo id" in i["text"].lower() for i in customer_knowledge(g, "viewing photo id lobby", k=6))
    return (f"Booked: {what} with {name(broker)}, {slots.say(when)}{place}." + (" Please bring a photo ID for the building lobby." if lobby else "")), refs + [vid]


def add_by_hand(office: Office, *, by: str, broker: str, phone: str, name_: str | None, kind_id: str, ref: str | None,
                when: datetime, now: datetime) -> dict:
    """A broker adds an appointment they agreed with the client on the phone (docs/calendar-own-time-spec.md): the same
    free-time check as Rania's bookings, the same reminders, and Rania knows about it. Nothing is sent to the client now."""
    from diwan import inbox, leads
    slots._may(by, broker)
    phone = re.sub(r"\D", "", phone or "")
    if not 8 <= len(phone) <= 15:
        raise ValueError("A phone number with the country code, like 971501234567")
    g = office.graph()
    k = next((x for x in slots.appointments(g) if x["id"] == kind_id), None)
    if not k:
        raise ValueError("Pick a kind of appointment")
    listing = g.nodes.get(f"listing:{(ref or '').strip().upper()}") if ref else None
    if ref and not listing:
        raise ValueError(f"No listing {ref}")
    if k["where"] == "property" and not listing:
        raise ValueError(f"{k['name']}: which property?")
    if when <= now:
        raise ValueError("That time has already passed")
    if not slots.is_open(g, broker, when, k["minutes"]):
        opts = ", ".join(slots.say(t) for t in slots.nearest(g, broker, when, now, 3, k["minutes"]))
        raise ValueError(f"{name(broker)} isn't free {slots.say(when)}." + (f" Free: {opts}." if opts else ""))
    ch = g.nodes.get(f"chat:{phone}")
    if ch and ch.deal:
        deal, who = ch.deal, ch.label
    else:
        who = (name_ or "").strip()
        if not who:
            raise ValueError("The client's name")
        deal = f"lead-{phone[-8:]}"
        office.open_deal(deal, property=listing.label if listing else k["name"], customer=who, broker=broker, by=by)
        leads.assign(office, deal, broker, by=by, why="added by hand on the calendar", chat=phone, now=now)
        office.log.append("chat.handover", actor=by, deal=deal, content={"chat": phone, "name": who, "mode": "ai", "by": None})
    vid = f"V{len(office.graph().of('viewing')) + 1}"
    ev = office.log.append("appointment.booked", actor=by, deal=deal,
                           content={"id": vid, "listing": listing.props["ref"] if listing else None, "broker": broker, "at": when.isoformat(),
                                    "customer": who, "chat": phone, "kind": k["id"], "kind_name": k["name"], "minutes": k["minutes"],
                                    "where": k["where"], "by_hand": by})
    if k["where"] == "phone" and (card := leads.open_card(office.graph(), phone)) and card.props["kind"] == "call":  # their call card follows
        leads.raise_card(office, phone, kind="call", cause=ev["id"], now=now, replace=True, due=when, to=broker,
                         reason=f"Call {slots.say(when)} (set by {name(by)})")
    if broker != by:
        leads.notify(office, broker, f"{name(by)} added {_what(g, k, listing)} with {who}, {slots.say(when)}.", chat=phone, kind="info", cause=ev["id"])
    from diwan import video
    if k["where"] == "video" and video.settings(g)["auto"]:
        video.make(office, vid, by=by, cause=ev["id"])  # in the reminders; nothing is sent now
    inbox.auto_stage(office, deal, cause=ev["id"])
    return {"id": vid, "deal": deal, "chat": phone}


def bare_time(low: str) -> str | None:
    """A time with no day ("make it 11", "at 4pm"): just the time, or None. A count ("2 bed") is not one."""
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low) or re.search(
        r"\b(?:at|to|make it|change it|shift it|switch it|bump it)\s+(\d{1,2})(?::(\d{2}))?()\b(?!\s*(?:bed|br|bhk|room|million|m\b|k\b|sq|%|aed|year|min))", low)
    return f"{m.group(1)}{':' + m.group(2) if m.group(2) else ''}{m.group(3) or ''}" if m else None


def move_or_cancel(office: Office, phone: str, deal: str, appt: Node, text: str, now: datetime, cause: int) -> str:
    """The client changes or cancels their appointment in the chat. The broker is told either way."""
    from diwan import leads
    g = office.graph()
    p = appt.props
    k = slots.kind(g, p.get("kind"))
    listing = g.nodes.get(f"listing:{p['listing']}") if p.get("listing") else None
    what, broker, was = _what(g, k, listing), p["broker"], datetime.fromisoformat(p["at"])
    low_ = text.lower()
    said = slots.parse(f"today at {bare_time(low_)}", now) if bare_time(low_) and len(low_.split()) <= 6 and not re.search(MOVE, low_) else None
    if said and not re.search(CANCEL, low_) and not re.search(ASKS_WHEN, low_):  # "at 10 then": the booked time, whichever they said
        was_l, said_l = was.astimezone(slots.DUBAI), said.astimezone(slots.DUBAI)
        same = (was_l.hour, was_l.minute) == (said_l.hour, said_l.minute)
        yours_ = yours(k, listing)
        if k["where"] == "phone":
            core = f"{name(broker)} will call you {slots.say(was)}"
        else:
            core = f"{yours_[0].upper() + yours_[1:]} is {slots.say(was)} with {name(broker)}"
        return (f"Yes, {core[0].lower() + core[1:] if core.startswith('Your') else core}. If you need to change it, just tell me." if same else
                f"Just to be clear: {core[0].lower() + core[1:] if core.startswith('Your') else core}. If you'd like another time, tell me.")
    if re.search(ASKS_WHEN, text.lower()) and not re.search(CANCEL, text.lower()) and not re.search(MOVE, text.lower()):
        place = {"property": "", "office": " at our office", "video": " by video"}.get(k["where"], "")
        if k["where"] == "phone":
            return f"{name(broker)} will call you {slots.say(was)}. If you need to change it, just tell me."
        yours_ = yours(k, listing)
        if re.match(r"\s*(is|are|so|will|does|did)\b", text.lower()):  # a check ("is it still on?"), so a yes
            return f"Yes, {yours_} is {slots.say(was)} with {name(broker)}{place}. If you need to change it, just tell me."
        return f"{yours_[0].upper() + yours_[1:]} is {slots.say(was)} with {name(broker)}{place}. If you need to change it, just tell me."
    if re.search(CANCEL, text.lower()):
        ev = office.log.append("appointment.cancelled", actor=f"customer:{phone}", deal=deal, caused_by=cause,
                               content={"id": appt.id, "by": "customer", "quote": text[:200]})
        if p.get("where") == "phone" and (card := leads.open_card(office.graph(), phone)) and card.props["kind"] == "call":
            leads.clear(office, card.id, "not_needed", by=RANIA, note="The client cancelled the call")
        leads.notify(office, broker, f"{appt.props['customer']} cancelled {what}, {slots.say(was)}: \u201c{text[:120]}\u201d", chat=phone, kind="info", cause=ev["id"])
        from diwan import video
        video.cancelled(office, appt.id, by=f"customer:{phone}", cause=ev["id"])
        return f"No problem, I've cancelled {yours(k, listing)} on {slots.say(was)}. If you'd like another time, just tell me."
    when = slots.parse(text, now)
    if not when and (t := bare_time(low := text.lower())):  # "make it 11": the same day as the appointment
        d = (was.astimezone(slots.DUBAI).date() - now.astimezone(slots.DUBAI).date()).days
        when = slots.parse(f"{'today' if d <= 0 else 'tomorrow' if d == 1 else was.strftime('%A')} at {t}", now)
    if when and when > now and slots.is_open(g, broker, when, int(p.get("minutes") or 60), ignore=appt.id):
        ev = office.log.append("appointment.moved", actor=f"customer:{phone}", deal=deal, caused_by=cause,
                               content={"id": appt.id, "at": when.isoformat(), "from": p["at"], "quote": text[:200]})
        leads.notify(office, broker, f"{appt.props['customer']} moved {what} from {slots.say(was)} to {slots.say(when)}.", chat=phone, kind="info", cause=ev["id"])
        from diwan import video
        video.moved(office, appt.id, by=f"customer:{phone}", cause=ev["id"])
        if p.get("where") == "phone":  # the broker's call card is due at the new time
            leads.raise_card(office, phone, kind="call", cause=ev["id"], now=now, replace=True, due=when, to=broker,
                             reason=f"Call {slots.say(when)}, as they asked. They said: \u201c{text[:160]}\u201d")
        return f"Done: {yours(k, listing)} is now {slots.say(when)} with {name(broker)}."
    opts = ", ".join(slots.say(t) for t in (slots.nearest(g, broker, when, now, 3, int(p.get("minutes") or 60), ignore=appt.id) if when
                                             else slots.free(g, broker, now, 3, int(p.get("minutes") or 60), ignore=appt.id)))
    return (f"{'That time isn' + chr(39) + 't free. ' if when else ''}{name(broker)} can do {opts}. Which suits you? "
            f"Your current time, {slots.say(was)}, stays booked until you choose.")


def change_from_calendar(office: Office, vid: str, *, by: str, when: datetime | None = None, cancel: bool = False,
                         reason: str = "", now: datetime) -> dict:
    """The broker (or the owner) moves or cancels an appointment on the calendar. The client is told in one plain
    message; outside WhatsApp's 24-hour window it can't go without a template, so the broker gets a card to tell them.
    The reason for a cancellation stays inside the office."""
    from diwan import inbox, leads, video
    g = office.graph()
    v = g.nodes.get(vid)
    if not v or v.type != "viewing":
        raise ValueError("No such appointment")
    p = v.props
    slots._may(by, p["broker"])
    if v.status != "booked":
        raise ValueError(f"It is already {v.status.replace('_', '-')}")
    was, minutes = datetime.fromisoformat(p["at"]), int(p.get("minutes") or 60)
    if was < now:
        raise ValueError("It has already started: mark it Done or No-show instead")
    k = slots.kind(g, p.get("kind"))
    listing = g.nodes.get(f"listing:{p['listing']}") if p.get("listing") else None
    if cancel:
        ev = office.log.append("appointment.cancelled", actor=by, deal=v.deal, content={"id": vid, "by": "broker", "reason": (reason or "").strip()[:200] or None})
        video.cancelled(office, vid, by=by, cause=ev["id"])
        msg = f"{yours(k, listing)} on {slots.say(was)} has been cancelled. If you'd like another time, just reply here."
        if p.get("where") == "phone" and (card := leads.open_card(office.graph(), p["chat"])) and card.props["kind"] == "call":
            leads.clear(office, card.id, "not_needed", by=by, note="The call was cancelled on the calendar")
    else:
        if not when or when <= now:
            raise ValueError("Pick a new day and time ahead")
        if not slots.is_open(g, p["broker"], when, minutes, ignore=vid):
            opts = ", ".join(slots.say(t) for t in slots.nearest(g, p["broker"], when, now, 3, minutes, ignore=vid))
            raise ValueError(f"{name(p['broker'])} isn't free {slots.say(when)}." + (f" Free: {opts}." if opts else ""))
        ev = office.log.append("appointment.moved", actor=by, deal=v.deal, content={"id": vid, "at": when.isoformat(), "from": p["at"], "by": "broker"})
        video.moved(office, vid, by=by, cause=ev["id"])
        link = (office.graph().nodes[vid].props.get("link") or {}).get("url")
        if p.get("where") == "phone" and p.get("chat"):  # the broker's call card is due at the new time
            leads.raise_card(office, p["chat"], kind="call", cause=ev["id"], now=now, replace=True, due=when, to=p["broker"],
                             reason=f"Call {slots.say(when)} (moved by {name(by)})")
        msg = (f"{name(p['broker'])} has moved {yours(k, listing)}: it's now {slots.say(when)}." + (f" The link stays the same: {link}" if link else "")
               + " If that doesn't suit you, reply here and I'll find another time.")
    if by != p["broker"]:
        leads.notify(office, p["broker"], f"{name(by)} {'cancelled' if cancel else 'moved'} {_what(g, k, listing)} with {p.get('customer')}"
                     + ("" if cancel else f" to {slots.say(when)}") + ".", chat=p.get("chat"), kind="info", cause=ev["id"])
    chat = g.nodes.get(f"chat:{p['chat']}") if p.get("chat") else None
    if not chat:
        return {"id": vid, "told": "no_chat", "text": msg}
    first = first_name(chat.label)
    text = f"Hi{' ' + first if first else ''}, {msg}"
    if not inbox.conversation(office.graph(), office.graph().nodes[chat.id], now)["window_open"]:
        # more than 24 hours since they wrote: only an approved template can go, the owner's pick for a move or a cancel
        from diwan.agents import reminders
        want = reminders.settings(office.graph())["cancel_template" if cancel else "change_template"]
        t = next((t for t in inbox.templates() if t["name"] == want), None) if want else None
        if t:
            params = [first or "there", yours(k, listing).removeprefix("your "), slots.say(was if cancel else when)][:int(t.get("params") or 0)]
            _send(office, chat.props["phone"], chat.deal, inbox.render(t["body"], params), [vid], by=by, cause=ev["id"],
                  template={"name": t["name"], "params": params, "language": t.get("language", "en")})
            return {"id": vid, "told": "template", "text": inbox.render(t["body"], params)}
        leads.raise_card(office, chat.props["phone"], reason=f"Tell the client: {'cancelled' if cancel else 'moved to ' + slots.say(when)} "
                         "(more than 24 hours since their last message, and no approved template is picked in the calendar settings)", to=p["broker"], kind="call", cause=ev["id"], now=now)
        return {"id": vid, "told": "card", "text": text}
    _send(office, chat.props["phone"], chat.deal, text, [vid], by=by, cause=ev["id"])
    return {"id": vid, "told": "sent", "text": text}


def send_link(office: Office, vid: str, *, by: str, now: datetime) -> dict:
    """"Create link" on a video call: make it with the owner's service and send it to the client in one message."""
    from diwan import inbox, leads, video
    g = office.graph()
    v = g.nodes.get(vid)
    if not v or v.type != "viewing" or (v.props.get("where") or "property") != "video":
        raise ValueError("Only a video call has a link")
    slots._may(by, v.props["broker"])
    url = video.make(office, vid, by=by)
    if not url:
        raise ValueError((office.graph().nodes[vid].props.get("link") or {}).get("error") or "The link couldn't be made")
    p = office.graph().nodes[vid].props
    chat = g.nodes.get(f"chat:{p['chat']}") if p.get("chat") else None
    if not chat:
        return {"url": url, "told": "no_chat"}
    first = first_name(chat.label)
    text = (f"Hi{' ' + first if first else ''}, here is the link for your {(p.get('kind_name') or 'video call').lower()} with {name(p['broker'])}, "
            f"{slots.say(datetime.fromisoformat(p['at']))}: {url}")
    if not inbox.conversation(g, chat, now)["window_open"]:
        return {"url": url, "told": "window_closed"}  # it goes in the reminders
    _send(office, chat.props["phone"], chat.deal, text, [vid], by=by)
    return {"url": url, "told": "sent", "text": text}


def _listing_line(n: Node) -> str:
    p = n.props
    size = f"studio {p['type']}" if p["beds"] == 0 else f"{p['beds']} bed {p['type']}"
    rent = " a year" if p.get("offering") == "rent" else ""
    return f"{p['title']}, {p['community']}: {size}, AED {p['price_aed']:,}{rent} (ref {p['ref']}, permit {p['permit']})"


def answer_rules(office: Office, phone: str, deal: str, text: str, now: datetime, cause: int,
                 heard: list[str] = (), dry: bool = False, answering: bool = False, listings: bool = True,
                 n: int = 3) -> tuple[str, list[str], list[Action], str | None]:
    """Reply, refs, actions, and a handover reason if the chat should go to a person. `answering`: the customer is
    answering Rania's own qualification question (e.g. "cash"), so it is not treated as a compliance topic."""
    g = office.graph()
    low = text.lower()
    chat = g.nodes.get(f"chat:{phone}")
    fn = first_name(chat.label) if chat else None
    hi = f"Hi {fn}" if fn else "Hi"
    broker = name(g.nodes[f"deal:{deal}"].props["broker"])
    if answering:
        return "Thank you, noted.", [], [Action("record_fact", "Qualification answer")], None
    if re.search(NOT_MINE, low):
        return f"That's one for {broker} personally, who will reply to you here.", [], [Action("assign", "Hand to broker")], "a question for a person"
    if asks_returns(low):
        return (f"I can't promise returns or yields. {broker} can share recent sales and rental data for the area and will reply here.",
                [], [Action("assign", "Hand to broker")], "asked about returns")
    if any(g.nodes[f].props["kind"] in ("payer", "payment_promise", "income_claim") for f in heard):
        # noted by the Scribe, so the office already acts on it; Rania does not discuss money
        return f"Thank you, noted. {broker} will go through the payment details with you personally.", list(heard), [Action("record_fact", "Noted")], None
    if re.search(HANDOVER, low):
        return f"Of course. I'm passing you to {broker}, who will reply here shortly.", [], [Action("assign", "Hand to broker")], "asked for a person"
    if re.search(PRICE, low) and not re.search(SEARCH + r"|\d", low):
        listing = _listing_named(g, text, chat)
        if listing:
            return f"{_listing_line(listing)}. Would you like to see it? Tell me a day and time.", [listing.id], [Action("reply", "Price")], None
        opts = "\n".join(f"• {_listing_line(x)}" for x in advertisable(g)[:n])
        return f"Happy to help. Which property do you mean? Here are some of ours:\n{opts}", [x.id for x in advertisable(g)[:n]], [Action("reply", "Ask which listing")], None
    if re.search(BOOK, low) or slots.parse(text, now):
        listing = _listing_named(g, text, chat)
        if not listing:
            opts = "; ".join(_listing_line(x) for x in advertisable(g)[:n])
            return f"Happy to arrange a viewing. Which property would you like to see? {opts}", [x.id for x in advertisable(g)[:n]], [Action("reply", "Ask which listing")], None
        reply, refs = book(office, phone, deal, listing, slots.parse(text, now), now, cause, dry)
        kind = "book_viewing" if any(r.startswith("V") for r in refs) else "reply"
        return reply, refs, [Action(kind, reply)], None
    from diwan import knowledge
    # an area named in a question about something else ("the chiller fees at Marina Crest?") is not a property search
    area = bool(knowledge.areas_in(g, text)) and not re.search(QUESTION, low)
    low_s = re.sub(FINANCE_ASK, " ", low)  # "do you have mortgage options?" is a finance question, not a search
    if (re.search(SEARCH, low_s) or scribe.amounts(text) or area) and not listings:
        return ("Thank you, noted. I'll send you the best options once I know a little more.", [],
                [Action("reply", "Noted: listings come once the lead qualifies")], None)
    if re.search(SEARCH, low_s) or scribe.amounts(text) or area:
        found = matches(g, deal, text)[:n]
        says = re.search(r"\b(\d+|one|two|three|four|five)\s*-?\s*(bed|br|bedroom)|studio|villa|apartment|flat|townhouse|penthouse", low) or scribe.amounts(text) or area
        if not says and g.nodes[f"deal:{deal}"].props.get("qualify_status") == "qualified":
            exact = recommend(g, deal, n)  # "any options?" after qualifying: from what they told her
            found, close = (exact, False) if exact else (nearest(g, deal, n)[0], True)
            if found and close:
                lines = "\n".join(f"• {_listing_line(x)}" for x in found)
                return (f"{broker} will send you options that fit everything you told me. Meanwhile, a few close ones:\n{lines}\nWould any be worth a look?",
                        [x.id for x in found], [Action("reply", "Closest listings")], None)
        if not found:
            return (f"I've passed this to {broker}, who hears about new ones first and will contact you with options that fit.",
                    [], [Action("assign", "Brief the broker")], "no listing fits the brief")
        lines = "\n".join(f"• {_listing_line(n)}" for n in found)
        return f"Here's what fits:\n{lines}\nWould you like to see one? Tell me a day and time.", [n.id for n in found], [Action("reply", "Listings")], None
    words = set(re.findall(r"[a-z]{4,}", low)) - {"what", "your", "have", "does", "about", "with", "there", "hello", "thanks", "please", "could",
                                                   "would", "want", "need", "know", "tell", "this", "that", "just", "still", "much", "they", "them"}
    best = next(iter(customer_knowledge(g, text, k=1)), None)
    if best and words & set(re.findall(r"[a-z]{4,}", f"{best['title']} {best['text']}".lower())):
        return best["text"], [best["id"]], [Action("reply", best["title"])], None
    if not chat or len(chat.props["messages"]) <= 1:
        return (f"{hi}, I'm Rania from {COMPANY}. Are you looking to buy, rent, or sell a property?",
                [], [Action("reply", "Greet and ask the brief")], None)
    if re.search(r"\b(hi|hello|salam|marhaba|hey|thanks|thank you)\b|السلام|مرحبا|شكرا", low):
        return f"{hi}, how can I help?", [], [Action("reply", "Greet")], None
    return f"I'm not sure I can answer that well. I've asked {broker} to reply to you here.", [], [Action("assign", "Hand to broker")], "Rania couldn't answer"


def _amounts_ok(reply: str, sources: dict[str, str]) -> bool:
    known = {a for s in sources.values() for a in scribe.amounts(s)}
    return all(a in known for a in scribe.amounts(reply))


def schedule_call(office: Office, phone: str, deal: str, at: datetime, now: datetime, cause: int) -> tuple[bool, list[datetime]]:
    """The client asked to be called at a time: put it on their broker's calendar as a Phone call appointment, so nothing
    else is booked over it. A call already set for this client moves with them. Returns (done, free times near it when the
    broker isn't free)."""
    g = office.graph()
    broker = g.nodes[f"deal:{deal}"].props["broker"]
    who = g.nodes[f"chat:{phone}"].label
    k = next(x for x in slots.appointments(g) if x["where"] == "phone")  # always there (slots.appointments)
    minutes = k["minutes"]
    old = next((v for v in g.of("viewing", status="booked") if v.props.get("chat") == phone and v.props.get("where") == "phone"
                and datetime.fromisoformat(v.props["at"]) > now), None)
    me = old.id if old else None
    if not slots.is_open(g, broker, at, minutes, ignore=me):
        return False, slots.nearest(g, broker, at, now, 3, minutes, ignore=me)
    if old:
        office.log.append("appointment.moved", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause,
                          content={"id": old.id, "at": at.isoformat(), "from": old.props["at"], "by": "client"})
    else:
        office.log.append("appointment.booked", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause,
                          content={"id": f"V{len(g.of('viewing')) + 1}", "listing": None, "broker": broker, "at": at.isoformat(), "customer": who,
                                   "chat": phone, "kind": k["id"], "kind_name": k["name"], "minutes": minutes, "where": "phone"})
    return True, []


def _call_requested(office: Office, phone: str, deal: str, text: str, q: dict, rs: dict, cause: int, now: datetime,
                    at: datetime | None = None) -> None:
    """"Can someone call me?": always a call card for the broker, with the conversation so far. Once qualified it is a
    hot lead when the owner counts a call request as hot."""
    from diwan import leads
    g = office.graph()
    d = g.nodes[f"deal:{deal}"].props
    summary = " · ".join(f"{a['label']}: {a['value']}" for a in q["answers"])
    when = f"Call {slots.say(at)}, as they asked. " if at else ""
    if at:  # a time they chose: the card is due then, and replaces one due sooner
        leads.raise_card(office, phone, kind="call", cause=cause, now=now, replace=True, due=at,
                         reason=f"{when}They said: \u201c{text[:160]}\u201d" + (f" · {summary}" if summary else ""))
        if not (q["status"] == "qualified" and "call" in rs["hot_on"] and not d.get("hot")):
            return
    if q["status"] == "qualified" and "call" in rs["hot_on"] and not d.get("hot"):
        office.log.append("lead.hot", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause,
                          content={"listing": None, "why": "asked for a call", "quote": text[:300], "chat": phone})
        if not at:
            leads.raise_card(office, phone, kind="call", cause=cause, now=now, replace=True,
                             reason=f"🔥 Hot lead, ready to close: asked for a call. They said: \u201c{text[:160]}\u201d · {summary}")
        return
    cur = leads.open_card(g, phone)
    leads.raise_card(office, phone, kind="call", cause=cause, now=now, replace=bool(cur and cur.props["kind"] != "call"),
                     reason=f"Asked for a call: \u201c{text[:160]}\u201d" + (f" · {summary}" if summary else ""))


def _nurture(office: Office, phone: str, deal: str, text: str, cause: int) -> None:
    """Only looking for now: nurtured (by Marketing, by default), not chased. Their broker's open card closes, so no
    broker time is spent and nothing goes overdue; the broker hears once, and again if they come back ready."""
    from diwan import leads
    g = office.graph()
    to = front_settings(g)["nurture_to"]
    ev = office.log.append("lead.nurture", actor=RANIA, agent=RANIA, deal=deal, caused_by=cause,
                           content={"reason": "not ready yet", "quote": text[:300], "to": to, "chat": phone})
    if card := leads.open_card(g, phone):
        leads.clear(office, card.id, "not_needed", by=RANIA, note="Not ready yet: moved to nurture")
    label = g.nodes[f"chat:{phone}"].label
    leads.notify(office, g.nodes[f"deal:{deal}"].props["broker"],
                 f"{label} is only looking for now ({NURTURE_TO[to].lower()}). You'll hear if they come back ready.",
                 chat=phone, kind="info", cause=ev["id"])


def receive(office: Office, phone: str, text: str, *, name_: str | None = None, now: datetime | None = None, tape_root=None,
            comment_id: str | None = None) -> dict:
    """A customer message arrives: kept in the chat at once, and the Scribe hears it. The reply is `message`."""
    now = now or datetime.now(slots.DUBAI)
    deal = _lead(office, phone, name_, now)
    got = office.log.append("chat.received", actor=f"customer:{phone}", deal=deal,
                            content={"chat": phone, "name": name_, "text": text, "comment_id": comment_id,
                                     "channel": "instagram" if phone.startswith("ig:") else "whatsapp"})
    heard = scribe.hear(office, deal, office.graph().nodes[f"deal:{deal}"].props["customer"], text, got["id"], tape_root=tape_root)
    return {"deal": deal, "got": got, "heard": heard}


def unanswered(g: Graph, phone: str) -> list[dict]:
    """The client's messages since the office last wrote to them: a burst ("any options?" / "just to get an idea")."""
    out = []
    for m in reversed(g.nodes[f"chat:{phone}"].props["messages"]):
        if m["type"] != "received":
            break
        out.append(m)
    return out[::-1]


def message(office: Office, phone: str, text: str, *, name_: str | None = None, now: datetime | None = None, tape_root=None,
            comment_id: str | None = None, received: dict | None = None) -> dict:
    """A customer message. `phone` is the chat id: a WhatsApp number, or "ig:<username>" for an Instagram comment.
    With `received` (already kept by `receive`), one reply answers every message they sent since the office last wrote."""
    now = now or datetime.now(slots.DUBAI)
    r = received or receive(office, phone, text, name_=name_, now=now, tape_root=tape_root, comment_id=comment_id)
    deal, got, heard = r["deal"], r["got"], r["heard"]
    if received:
        text = "\n".join(m["text"] for m in unanswered(office.graph(), phone)) or text
    g = office.graph()
    chat = g.nodes[f"chat:{phone}"]
    c = get(RANIA)
    rs = recommend_settings(g)
    dp0 = g.nodes[f"deal:{deal}"].props
    # the front door, decided in code: not ready yet (nurtured, not chased), back and ready, or asking for a call
    from diwan import leads
    from diwan.agents import nudge
    low0, front = text.lower(), None
    if re.search(nudge.STOP, low0.strip()) and chat.props["mode"] == "ai":
        front = "stop"  # no more follow-ups or nurture messages, ever
    elif dp0.get("nurture"):
        # someone who only went quiet is back as soon as they write; someone who said they're only looking, when they show
        # intent (noticed even while a person has the chat)
        if str(dp0["nurture"].get("reason") or "").startswith("went quiet") or comes_back(g, text):
            ev = office.log.append("lead.reopened", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"quote": text[:300], "chat": phone})
            leads.notify(office, dp0["broker"], f"{chat.label} is back and ready: “{text[:160]}”", chat=phone, kind="lead", cause=ev["id"])
            g = office.graph()
            dp0 = g.nodes[f"deal:{deal}"].props
        elif chat.props["mode"] == "ai":
            front = "quiet"
    elif re.search(NOT_READY, low0) and not dp0.get("hot") and not re.search(CALL_ME, low0) and chat.props["mode"] == "ai":
        front = "nurture"
    appt = upcoming(g, phone, now, text)
    time_check = bool(appt and len(low0.split()) <= 6 and bare_time(low0) and not re.search(MOVE, low0)
                      and (re.search(r"\b(then|ok|okay|so|right|yes|yeah|sure|fine|perfect|confirmed|correct)\b|\?", low0)))  # "at 10 then"
    if front is None and chat.props["mode"] == "ai" and appt and (re.search(CANCEL, low0) or re.search(ASKS_WHEN, low0) or time_check or (re.search(MOVE, low0) and (
            slots.parse(text, now) or re.search(r"\b(viewing|visit|appointment|meeting|time|day)\b", low0) or bare_time(low0)))):
        front = "appt"  # they change or cancel what is booked
    elif front is None and chat.props["mode"] == "ai" and appointment_kind(g, text):
        front = "meet"  # a video call or an office meeting
    if front is None and re.search(CALL_ME, low0):
        front = "call"
    from diwan import knowledge
    if (front is None and chat.props["mode"] == "ai" and dp0.get("qualify_status") == "qualified" and not dp0.get("hot")
            and re.search(r"\b(options?|listings?|anything|available|show me|send me|what (do you|have you) got)\b", re.sub(FINANCE_ASK, " ", low0))
            and not re.search(r"\b(\d+|one|two|three|four|five)\s*-?\s*(bed|br|bedroom)|studio|villa|apartment|flat|townhouse|penthouse", low0)
            and not scribe.amounts(text) and not knowledge.areas_in(g, text)):
        front = "options"  # "any options?" once qualified: from what they told her, never "we don't have it"
    # "call me tomorrow at 10": the time they chose, and whether it is inside their broker's working hours
    call_at = slots.parse(text, now) if front == "call" else None
    call_at = call_at if call_at and call_at > now else None
    cur_card = leads.open_card(g, phone) if call_at else None
    on_calendar = bool(call_at) and any(v.props.get("chat") == phone and v.props.get("where") == "phone" and datetime.fromisoformat(v.props["at"]) == call_at
                                        for v in g.of("viewing", status="booked"))
    call_same = bool(cur_card and cur_card.props.get("due") and datetime.fromisoformat(cur_card.props["due"]) == call_at) and on_calendar
    call_ok = bool(call_at) and bool(w := slots.window(g, dp0["broker"], call_at.date())) and w[0] <= call_at.hour * 60 + call_at.minute < w[1]
    asking = bool(re.search(ASKING, re.sub(FINANCE_ASK, " ", text.lower())))  # "mortgage options?" is not asking for listings
    listings_ok = front not in ("quiet", "nurture") and (
        rs["when"] == "as_soon_as_fit" or (rs["when"] == "after_qualified" and (dp0.get("qualify_status") == "qualified" or asking)))
    sources = prompt_sources(g, deal, chat, text, listings=listings_ok, n=rs["how_many"])
    known = [k for k in sources if k.startswith("F")]
    fn = first_name(chat.label)
    task = (f"Customer: {fn or 'name not known'}. "
            + (f"What this customer has told us: {', '.join(known)}. " if known else "Nothing known about this customer yet. ")
            + ("This is their first message." if len([m for m in chat.props["messages"] if m["type"] == "received"]) <= 1 else "")
            + f"\nTheir new message: {text}")
    # qualification (the owner's form): clear answers read by plain rules first, so the prompt and the verdict see them
    from diwan import qualify
    form = qualify.form(g)
    said = " \n ".join(m["text"] for m in chat.props["messages"] if m["type"] == "received")
    dprops = g.nodes[f"deal:{deal}"].props
    stuck_before = qualify.state(g, deal).get("stuck", [])  # before this message's answers
    rtype, ranswers = qualify.read_rules(g, form, dprops.get("qtype"), text, dprops.get("qualify_asked"))
    qualify.record(office, deal, qtype=rtype, type_quote=text if rtype else None, answers=ranswers, said=said, by="rules", cause=got["id"])
    # asked, and two replies later still no clear answer: she doesn't ask a third time, it counts as "not sure"
    # (the owner allows it: she moves on; "must answer": a rough idea once, then the broker helps)
    g = office.graph()
    dprops = g.nodes[f"deal:{deal}"].props
    k_asked = dprops.get("qualify_asked")
    if k_asked and k_asked in (qualify.state(g, deal).get("missing") or []) and k_asked not in dprops.get("answers", {}):
        since = dprops.get("qualify_asked_event") or 0
        if len([m for m in chat.props["messages"] if m["type"] == "received" and m["event"] > since]) >= 2:
            qualify.record(office, deal, qtype=None, type_quote=None, said=said, by="rules", cause=got["id"],
                           answers=[{"field": k_asked, "value": qualify.NOT_SURE, "quote": text.strip()[:200], "unsure": True}])
    g = office.graph()
    chat = g.nodes[f"chat:{phone}"]
    q_before = qualify.state(g, deal)
    arabic = bool(re.search(r"[\u0600-\u06ff]", text))
    broker_name = name(g.nodes[f"deal:{deal}"].props["broker"])
    schema = qualify_schema(form)
    rec_rule = (f"Recommendations (set by the owner): show at most {rs['how_many']} listings in one message. "
                + ("" if listings_ok else "Do not list properties in this message: you are still learning what they need. If they ask, say you will "
                   "send the best options once you know a little more."))
    if front == "quiet":
        rec_rule += ("\nThis customer said they are only looking for now: answer what they ask, warmly and briefly. Do not ask any "
                     "qualification question and do not list properties.")
    system = runner.instructions(c, office.log, pack=False) + GUIDE + "\n\n" + qualify.prompt_block(form, q_before, arabic, broker_name) + "\n" + rec_rule
    user = runner.user_message(task, sources)
    from diwan.config import sandbox_only
    prompt = {"system": system, "user": user} if sandbox_only() else None  # shown in the test console only
    reason = None
    lvl = lessons.level(office.log, RANIA)
    dry = lvl != "autopilot" or chat.props["mode"] == "human"  # a person has the chat: a booking is only proposed
    out = None
    usage, held = {}, None  # which model answered; what it wanted to say when a guard stopped it (for the test console)
    # Cash, crypto, discounts, negotiation, source of funds, guaranteed returns: one fixed, safe answer every time,
    # whichever model is connected, so a model can never improvise on a compliance or pricing question.
    # ...except a short answer to Rania's own "cash or mortgage?" question: that is qualification, not a compliance topic
    answering = (dprops.get("qualify_asked") == "finance" and len(text) < 60 and not text.strip().endswith("?")
                 and bool(re.search(r"\b(cash|mortgage|finance|financing|loan)\b|كاش|تمويل", text.lower())))
    fixed = not answering and bool(re.search(NOT_MINE, text.lower()) or asks_returns(text.lower()))
    # the customer picks one of the recommended properties (or asks to see it): a hot lead, decided in code
    hot = None
    if not fixed and front is None and not (dp0.get("hot") or {}).get("listing") and dp0.get("recommended"):
        pick, view = picked(g, deal, text), bool(re.search(BOOK, text.lower()) or slots.parse(text, now))
        if pick and ("pick" in rs["hot_on"] or (view and "viewing" in rs["hot_on"])):
            hot = (pick, "asked to view it" if view else "picked it")
    # a call request, "only looking", or a nurtured client saying nothing new: one plain reply, no model, no question
    front_done = not fixed and (front in ("call", "nurture", "stop", "appt", "meet", "options") or (front == "quiet" and not re.search(QUESTION, low0)))
    if front_done:
        refs = []
        if front == "appt":
            reply = move_or_cancel(office, phone, deal, appt, text, now, got["id"])
        elif front == "meet":
            lid = (dp0.get("hot") or {}).get("listing")
            reply, refs = book(office, phone, deal, g.nodes.get(lid) if lid else None, slots.parse(text, now), now, got["id"], dry,
                               kind=appointment_kind(g, text))
        else:
            call_busy = None
            if call_at and call_ok and not call_same:  # a call at a time they chose goes on the broker's calendar now
                done, near = schedule_call(office, phone, deal, call_at, now, got["id"])
                if not done:
                    call_busy, call_at = near, None  # taken: the card is for as soon as possible, not that time
            reply = front_reply(front, arabic, fn, broker_name, call_at, call_ok, call_same, call_busy)
        if front == "options":
            reply, refs = options_reply(office, phone, deal, arabic, fn, broker_name, rs["how_many"], got["id"])
        actions, by = [Action("book_viewing" if any(r.startswith("V") for r in refs) else "reply",
                              {"call": "Asked for a call: the broker calls", "nurture": "Not ready yet: nurture", "quiet": "Nurtured: door open",
                               "stop": "Asked us to stop: no more follow-ups", "appt": "Changed their appointment",
                               "options": "Asked for options: from their answers",
                               "meet": "Asked for a meeting"}[front])], "rules"
    elif hot:
        pick = hot[0]
        if slots.parse(text, now):  # they gave a time too: book it
            reply, refs = book(office, phone, deal, pick, slots.parse(text, now), now, got["id"], dry)
        else:
            broker_id = g.nodes[f"deal:{deal}"].props["broker"]
            free = ", ".join(slots.say(t) for t in slots.free(office.graph(), broker_id, now, 2))
            reply = (f"Great choice! {pick.props['title']} ({pick.props['ref']}). I've told {broker_name}, who will call you shortly. "
                     f"Would you like to see it? {broker_name} is free {free}." if not arabic else
                     f"اختيار رائع! {pick.props['title']} ({pick.props['ref']}). أبلغت {broker_name} وسيتصل بك قريباً. هل تود معاينته؟ {broker_name} متاح {free}.")
            refs = [pick.id]
        actions, by = [Action("reply", "Hot lead: hand to the broker")], "rules"
    elif not fixed and runner.has_model(c, system, user, schema=schema, tape_root=tape_root):
        try:
            answered = runner.call(c, system, user, schema=schema, tape_root=tape_root, timeout=runner.LIVE)
            out, usage = answered.data, answered.usage
        except Exception as e:  # a customer is waiting: too slow or failed, answer by the rules and note it
            office.log.append("agent.failed", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"error": str(e)[:300]})
            out = None
    if hot or front_done:
        pass
    elif out:
        reply, refs = clean_text(out["reply"]), [r if r.startswith(("listing:", "K")) else f"listing:{r}" for r in out["listing_refs"]] + out["knowledge_refs"]
        actions = [Action("reply", reply)]
        if not _amounts_ok(reply, sources):
            reason, held = "reply named an amount not on any listing", reply
            reply = f"I've asked {name(g.nodes[f'deal:{deal}'].props['broker'])} to reply to you here personally."
            actions = [Action("assign", "Hand to broker")]
        elif out["handover"]:
            # her own words are kept: compliance and pricing topics never reach the model (the fixed replies above),
            # and this reply has passed the price check; the lessons check below still applies
            reason = "asked for a person" if re.search(HANDOVER, text.lower()) else "Rania handed over: the sources did not cover it"
            actions = [Action("assign", "Hand to broker")]
        elif out["book_listing"] and f"listing:{out['book_listing']}" in g.nodes:
            reply, refs = book(office, phone, deal, g.nodes[f"listing:{out['book_listing']}"], slots.parse(out["book_when"] or "", now), now, got["id"], dry)
            actions = [Action("book_viewing", reply)]
        by = "model"
    else:
        reply, refs, actions, reason = answer_rules(office, phone, deal, text, now, got["id"], heard["facts"], dry, answering=answering,
                                                    listings=listings_ok, n=rs["how_many"])
        by = "policy" if fixed else "rules"
    # the verdict, applied in code: the model's answers are kept only with the customer's own words
    if out:
        mtype = out.get("customer_type") if out.get("customer_type") in form["types"] else None
        qualify.record(office, deal, qtype=mtype, type_quote=text if mtype else None, answers=out.get("answers") or [],
                       said=said, by="rania", cause=got["id"])
    q = qualify.state(office.graph(), deal)
    # handovers that only mean "nothing listed fits" or "I can't answer that" wait while qualification goes on:
    # the broker gets the lead with every answer once it qualifies, or the owner's reply closes it if it is not a fit
    soft = reason in SOFT_HANDOVERS
    if soft and front == "quiet" and chat.props["mode"] == "ai":
        # in Nurture: no broker's time on a handover; their question is kept and the broker hears it, without a card
        office.log.append("qualify.open", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"question": text[:300]})
        leads.notify(office, g.nodes[f"deal:{deal}"].props["broker"], f"{chat.label} (in Nurture) asked: \u201c{text[:160]}\u201d. "
                     "Answer when you can; no call needed.", chat=phone, kind="info", cause=got["id"])
        reply = ("سؤال جيد، سأتأكد وأعود لك بالإجابة." if arabic else "Good question. I'll check and come back to you on that.")
        reason, actions = None, [Action("reply", reply)]
    elif soft and q["verdict"] in ("ASK_QUESTION", "PASS_TO_AGENT", "NOT_A_FIT") and chat.props["mode"] == "ai":
        # a real question (not "not sure" to hers) reaches the broker with the qualified lead (decided 29 Oct)
        if reason != "no listing fits the brief" and not qualify.unsure(text) and re.search(QUESTION, text.lower()):
            office.log.append("qualify.open", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"question": text[:300]})
            q = qualify.state(office.graph(), deal)
        if reason == "Rania couldn't answer":
            reply = "Thank you, noted."
        elif reason == "no listing fits the brief":
            reply = f"Noted. {broker_name} will look for options that fit and contact you."
        reason, actions = None, [Action("reply", reply)]
    talking = chat.props["mode"] == "ai" and not reason and not fixed and not front_done
    if q["verdict"] == "PASS_TO_AGENT" and q["status"] != "qualified":
        office.log.append("qualify.passed", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"],
                          content={"type": q["type"], "version": q["version"], "reason": q["reasons"][0],
                                   "answers": {a["key"]: a["value"] for a in q["answers"]}})
        _route(office, deal, phone, got["id"], now)  # the lead's deal kind decides its broker
        broker_name = name(office.graph().nodes[f"deal:{deal}"].props["broker"])
        recs = recommend(office.graph(), deal, rs["how_many"]) if rs["when"] != "never" else []
        near, differs = ([], "") if recs or rs["when"] == "never" else nearest(office.graph(), deal, rs["how_many"])
        if talking and recs:
            reply, refs = recommendation_text(g, deal, recs, arabic, first_name(chat.label)), [n_.id for n_ in recs]
            actions = [Action("reply", f"Qualified: {len(recs)} recommendations")]
            office.log.append("lead.recommended", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"refs": refs, "chat": phone})
        elif talking and rs["when"] != "never":
            # nothing fits exactly: say so plainly, show the closest with how they differ, never push; the broker has the lead
            reply = no_exact_match(office.graph(), deal, near, differs, arabic, first_name(chat.label), broker_name)
            refs = [n_.id for n_ in near]
            actions = [Action("reply", f"Qualified: no exact match, {len(near)} close")]
            if near:
                office.log.append("lead.recommended", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"],
                                  content={"refs": refs, "chat": phone, "near": differs})
        elif talking:
            reply, actions = qualify.closing(arabic, first_name(chat.label), broker_name), [Action("reply", "Qualified: hand to the broker")]
    elif q["verdict"] == "NOT_A_FIT" and q["status"] != "not_a_fit":
        office.log.append("qualify.not_fit", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"],
                          content={"type": q["type"], "version": q["version"], "reason": q["reasons"][0]})
        if talking and q.get("reply"):
            reply, refs, actions = q["reply"], [], [Action("reply", "Not a fit: the owner's reply")]
    elif q["verdict"] in ("ASK_QUESTION", "DISCOVERY") and talking and front is None:
        nxt = q.get("next")
        newly_stuck = [k for k in q.get("stuck", []) if k not in stuck_before]
        if any(a.kind == "book_viewing" for a in actions):
            pass  # a booking confirmation stands on its own: no question tacked on
        elif by == "rules" and q["verdict"] == "DISCOVERY" and "?" not in reply:  # type not known yet: ask it
            reply = f"{reply} {'هل تبحث عن شراء أو إيجار أو بيع أو تأجير عقار؟' if arabic else 'Are you looking to buy, rent, sell or let out a property?'}"
        elif newly_stuck:  # not sure twice about a "must answer" question: she stops asking, the broker calls to help
            reply, actions = qualify.stuck_reply(arabic, broker_name), [Action("reply", "Not sure twice: the broker helps")]
        elif by == "rules" and nxt and q.get("retry") == nxt["key"]:
            reply = qualify.again(nxt, arabic)
        elif by == "rules" and nxt and "?" not in reply:  # the rules answered something else: add the next question
            reply = f"{reply} {nxt['question_ar' if arabic and nxt.get('question_ar') else 'question_en']}"
        asked = (q_before.get("next") or {}).get("key") if (q_before.get("next") or {}).get("key") in q["missing"] else (nxt or {}).get("key")
        if asked and asked != g.nodes[f"deal:{deal}"].props.get("qualify_asked"):
            office.log.append("qualify.asked", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"field": asked})
    if ls := lessons.broken(office.log, RANIA, reply):
        reason = f"held by lesson {ls['id']} ({ls['rule']})"
        held = reply
        reply = f"I've asked {name(g.nodes[f'deal:{deal}'].props['broker'])} to reply to you here personally."
        refs, actions = [ls["id"]], [Action("assign", "Hand to broker")]
    from diwan import leads
    if chat.props["mode"] == "human":
        office.log.append("chat.suggested", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"], content={"chat": phone, "text": reply, "refs": refs})
        leads.raise_card(office, phone, reason="wrote while you have the chat", text=text, to=chat.props.get("handled_by"), cause=got["id"], now=now)
        return {"mode": "human", "suggestion": reply, "refs": refs, "facts": heard["facts"], "by": by, "usage": usage, "held": held, "prompt": prompt, "qualify": q}
    res = runner.submit(office.log, c, Pack(f"chat-{got['id']}", RANIA, reply, actions=actions), sources={}, deal=deal, caused_by=got["id"])
    if res.approvals:  # Rania is on review: her reply waits for the broker as a suggestion
        office.log.append("chat.suggested", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"],
                          content={"chat": phone, "text": reply, "refs": refs, "review": lvl})
        if reason:
            hand_over(office, phone, reason=reason, cause=got["id"], text=text, now=now)
        else:
            leads.raise_card(office, phone, reason="Rania's reply waits for your review", text=text, cause=got["id"], now=now)
        return {"mode": "review", "suggestion": reply, "refs": refs, "facts": heard["facts"], "by": by, "autonomy": lvl, "usage": usage, "held": held, "prompt": prompt, "qualify": q}
    _send(office, phone, deal, reply, refs, cause=got["id"])
    if reason:
        hand_over(office, phone, reason=reason, cause=got["id"], text=text, now=now)
    elif front_done and front == "call" and not call_same:  # already set for that time: nothing new for the broker
        _call_requested(office, phone, deal, text, q, rs, got["id"], now, at=call_at)
    elif front_done and front == "nurture":
        _nurture(office, phone, deal, text, got["id"])
    elif front_done and front == "stop":
        nudge.stop(office, phone, deal, text, got["id"])
    elif hot:
        p = hot[0].props
        summary = " · ".join(f"{a['label']}: {a['value']}" for a in q["answers"])
        office.log.append("lead.hot", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"],
                          content={"listing": hot[0].id, "why": hot[1], "quote": text[:300], "chat": phone})
        from diwan.agents import deck
        deck.build(office, deal, cause=got["id"], listing=hot[0].id)  # the pitch deck for the meeting, from records only
        leads.raise_card(office, phone, kind="call", cause=got["id"], now=now, replace=True,
                         reason=f"🔥 Hot lead, ready to close: {hot[1]} {p['ref']} ({p['title']}, AED {p['price_aed']:,}). "
                                f"They said: \u201c{text[:160]}\u201d · {summary}"
                                + "".join(f" · Asked, not answered yet: {x}" for x in q.get("open_questions", [])))
    elif q["verdict"] == "PASS_TO_AGENT" and q["status"] != "qualified":
        summary = " · ".join([q.get("type_label") or q["type"]] + [f"{a['label']}: {a['value']}" for a in q["answers"]]
                             + [f"Asked, not answered yet: {x}" for x in q.get("open_questions", [])])
        recs_sent = [r for r in refs if r.startswith("listing:")] if any(a.kind == "reply" and "recommendations" in a.summary for a in actions) else []
        if "qualified" in rs["hot_on"]:  # the owner counts qualifying as hot: the broker is called in now
            office.log.append("lead.hot", actor=RANIA, agent=RANIA, deal=deal, caused_by=got["id"],
                              content={"listing": None, "why": "qualified", "quote": text[:300], "chat": phone})
            leads.raise_card(office, phone, kind="call", cause=got["id"], now=now, replace=True,
                             reason=f"🔥 Hot lead, ready to close: qualified · {summary}"
                                    + (f" · Rania sent {len(recs_sent)} options" if recs_sent else ""))
        elif recs_sent:  # the broker is told now, and called in when the customer picks one
            leads.notify(office, g.nodes[f"deal:{deal}"].props["broker"],
                         f"{chat.label} qualified: {summary}. Rania sent {len(recs_sent)} options; you'll get a hot-lead card when they pick one.",
                         chat=phone, kind="info", cause=got["id"])
        else:
            leads.raise_card(office, phone, reason=f"Qualified lead: {summary}", kind="call", cause=got["id"], now=now, replace=True)
    elif newly := [k for k in q.get("stuck", []) if k not in stuck_before]:
        labels = {a["key"]: a["label"] for a in q["answers"]}
        leads.raise_card(office, phone, kind="call", cause=got["id"], now=now,
                         reason=f"Not sure about {', '.join(labels.get(k, k) for k in newly)}, which you require: call to help"
                                + "".join(f" · Asked, not answered yet: {x}" for x in q.get("open_questions", [])))
    from diwan import inbox
    inbox.auto_stage(office, deal, got["id"])
    return {"mode": "human" if reason else "ai", "reply": reply, "refs": refs, "facts": heard["facts"], "handover": reason, "by": by,
            "usage": usage, "held": held, "prompt": prompt, "qualify": q}
