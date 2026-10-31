"""The Follow-up drafter: after a meeting or a viewing, a WhatsApp message for the broker to edit and send.

Its charter (agents/charters.py, "follow"): from the deal's records only, in the customer's language, and never a word
about compliance (no tipping off: a customer is never told about a check, a screening or source of funds). That rule is
enforced in code: a model draft that breaks it, or names an amount that is not in the records, is replaced by the plain
draft. Nothing is sent by the drafter: the broker sends it from the Inbox, or as a template once the 24-hour window shut.
"""
from __future__ import annotations

import re
from datetime import datetime

from diwan.office import Office
from diwan.people import name

TIPPING_OFF = r"compliance|screen|anti.?money|\baml\b|source of (funds|wealth)|suspicious|sanction|due diligence|kyc|امتثال|غسل"
SCHEMA = {"name": "followup", "schema": {"type": "object", "additionalProperties": False, "required": ["message", "refs"],
                                         "properties": {"message": {"type": "string"}, "refs": {"type": "array", "items": {"type": "string"}}}}}


def _chat(g, deal: str):
    return next((c for c in g.of("chat") if c.deal == deal), None)


def plain(g, deal: str, why: str) -> tuple[str, list[str]]:
    """The draft without a model: thanks, the property, the brief in their terms, and the next step for this deal kind."""
    from diwan import deal_kinds, qualify
    from diwan.agents.reception import first_name
    d = g.nodes[f"deal:{deal}"].props
    chat = _chat(g, deal)
    arabic = bool(chat and any(re.search(r"[؀-ۿ]", m["text"]) for m in chat.props["messages"] if m["type"] == "received"))
    first = first_name(chat.label) if chat else (d.get("customer") or "").split(" ")[0] or None
    lid = (d.get("hot") or {}).get("listing")
    p = g.nodes[lid].props if lid and lid in g.nodes else None
    answers = {a["key"]: a for a in qualify.state(g, deal)["answers"]}
    budget = qualify.number((answers.get("budget_aed") or {}).get("value"))
    refs = [lid] if p else []
    broker = name(d["broker"])
    k = deal_kinds.kind_for(g, deal)
    v = d.get("visit") or {}  # what they said at the visit (the Visit summarizer), with their words
    worry = (v.get("worries") or [None])[0]
    if arabic:
        lines = [f"مرحباً{' ' + first if first else ''}، شكراً على وقتك اليوم."]
        if v.get("interest") == "not_for_them":
            lines.append("شكراً على صراحتك. ما الذي تود تغييره: المنطقة أو المساحة أو الميزانية؟ سأبحث لك من جديد.")
            return "\n".join(lines + [broker]), refs
        if p:
            lines.append(f"بخصوص {p['title']} ({p['ref']})، السعر {p['price_aed']:,} درهم.")
        if worry:
            lines.append(f"ذكرت \u201c{worry}\u201d، سأبحث عن خيارات تحل ذلك وأرسلها لك.")
        lines.append("هل تود أن نرتب الخطوة التالية؟")
        return "\n".join(lines + [broker]), refs
    lines = [f"Hi{' ' + first if first else ''}, thank you for your time today{' at the viewing' if 'view' in why.lower() else ''}."]
    if v.get("interest") == "not_for_them":  # never push the same property again
        lines.append("Thank you for being honest that it wasn't the one. What would you change: the area, the size or the budget? I'll look again.")
        return "\n".join(lines + [broker]), refs
    if p:
        price = f"AED {p['price_aed']:,}{' a year' if p.get('offering') == 'rent' else ''}"
        lines.append(f"As discussed: {p['title']} ({p['ref']}), {price}" + (f", within your budget of AED {budget:,.0f}." if budget and p["price_aed"] <= budget else "."))
    if worry and v.get("source") == "recording":  # their own words
        lines.append(f"You mentioned \u201c{worry.rstrip('.!')}\u201d: I'll look for options that solve that and send them to you.")
    elif worry:  # the broker's notes are not the client's words: no quote
        lines.append("I've noted what didn't quite work for you, and I'll look for options that solve it.")
    if v.get("interest") == "thinking":
        lines.append("Take your time to think it over; I'm here for any question.")
    elif p and p.get("completion") == "off_plan":
        lines.append(f"I'll send you the payment plan and the reservation steps for {p.get('project') or p['title']}.")
    elif (p and p.get("offering") == "rent") or (k and k["listings"].get("offering") == "rent"):
        lines.append("Shall I prepare your offer to the landlord?")
    else:
        lines.append("Would you like to make an offer, or shall I show you one or two alternatives?")
    return "\n".join(lines + [broker]), refs


def draft(office: Office, deal: str, *, why: str, by: str = "follow", cause: int | None = None) -> dict:
    """Write the follow-up for this deal and keep it for the broker. A model writes it when one is connected; the code
    checks it before anyone sees it."""
    from diwan.agents import reception, runner
    from diwan.agents.charters import get
    g = office.graph()
    d = g.nodes[f"deal:{deal}"].props
    text, refs = plain(g, deal, why)
    c = get("follow")
    sources = {f.id: g.record(f.id) for f in g.facts(deal)}
    if (lid := (d.get("hot") or {}).get("listing")) and lid in g.nodes:
        sources[lid] = g.record(lid)
    if v := d.get("visit"):  # answer what worried them, and don't push a property that wasn't for them
        sources["visit"] = (f"At the visit: interest {v.get('interest')}; liked: {'; '.join(v.get('liked') or []) or 'not said'}; "
                            f"worries: {'; '.join(v.get('worries') or []) or 'none said'}; next step: {v.get('next_step') or 'not said'}")
    system = runner.instructions(c, office.log, pack=False) + (
        "\n\nWrite ONE WhatsApp message from the broker to the customer after the meeting: three to five short sentences, warm, "
        "in the customer's language, signed with the broker's first name. Thank them, recap only what the sources say, and "
        "give one clear next step. If the visit notes give a worry, answer it; if the property was not for them, do not push it. "
        "Never mention compliance, checks, screening, source of funds or anything about the "
        "office's internal work. Return the ids you used in refs.")
    user = runner.user_message(f"Customer: {d.get('customer')}. Broker: {name(d['broker'])}. Why now: {why}.", sources)
    by_model = False
    try:
        if runner.has_model(c, system, user, schema=SCHEMA):
            out = runner.call(c, system, user, schema=SCHEMA, timeout=runner.LIVE).data
            m = out["message"].strip()
            if m and not re.search(TIPPING_OFF, m.lower()) and reception._amounts_ok(m, sources):
                text, refs, by_model = m, [r for r in out["refs"] if r in sources] or refs, True
    except Exception as e:  # the broker still gets the plain draft
        office.log.append("agent.failed", actor="follow", agent="follow", deal=deal, caused_by=cause, content={"error": str(e)[:300]})
    ev = office.log.append("followup.drafted", actor=by, agent="follow", deal=deal, caused_by=cause,
                           content={"text": text, "refs": refs, "why": why, "by_model": by_model})
    return {"id": ev["id"], "text": text, "refs": refs, "why": why, "by_model": by_model}


def current(g, deal: str) -> dict | None:
    f = g.nodes[f"deal:{deal}"].props.get("followup")
    return f if f and f.get("status") == "draft" else None


def send(office: Office, deal: str, text: str, *, by: str) -> dict:
    """The broker sends the follow-up (edited or not) on WhatsApp; only the deal's broker or the owner."""
    from diwan import qualify
    from diwan.agents import reception
    g = office.graph()
    d = g.nodes[f"deal:{deal}"].props
    if by != d["broker"] and by not in qualify.owner_ids():
        raise PermissionError(f"Only {name(d['broker'])}, the deal's broker, or the owner sends it")
    if re.search(TIPPING_OFF, text.lower()):
        raise ValueError("Leave out anything about compliance or checks: the customer is never told about them")
    chat = _chat(g, deal)
    if not chat:
        raise ValueError("This deal has no WhatsApp conversation: copy the text and send it from your phone")
    sent = reception.person_sends(office, chat.props["phone"], text, by=by)
    office.log.append("followup.sent", actor=by, deal=deal, content={"text": text})
    return sent


def dismiss(office: Office, deal: str, *, by: str, why: str = "") -> None:
    office.log.append("followup.dismissed", actor=by, deal=deal, content={"why": why})
