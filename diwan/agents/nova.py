"""Nova, the front desk. She answers from the office graph, routes instructions down to a specialist, and briefs each
person in the morning. She never guesses: an unclear deal or team becomes one question back, an answer no record
supports is not shown, and anything only a person may do is refused with the name of who can.

With a model, Muse Spark writes the answer from the records the graph returned and every quote is checked against
them. Without one, the same records are put into plain sentences. Either way the records cited are the same.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from diwan.agents import operations, runner
from diwan.providers.chat import ProviderError
from diwan.agents.charters import get
from diwan.graph import OPEN, Graph
from diwan.office import Office
from diwan.pack import Action, Evidence, Pack
from diwan.people import PEOPLE, name, pid

NOVA = "nova"

INTENTS = {
    "needs": r"\b(needs?|waiting|wait|my day|for me|to ?do|on my plate)\b",
    "payer": r"\b(pay|pays|paying|payer|paid|deposit|payment|money)\b",
    "changed": r"\b(chang|correct|replac|took back|forget|differ)\w*",
    "impact": r"\b(affect|depend|rest|break|impact)\w*",
    "status": r"\b(status|where are we|stand|progress|update)\b",
}

# the words people ask with -> the kind of fact that answers them
KIND_WORDS = {
    "deal_term": r"\b(price|cost|budget|offer|million|aed|terms?)\b",
    "income_claim": r"\b(income|earn\w*|salary|make a month|afford)\b",
    "party": r"\b(brother|sister|wife|husband|family|father|mother|who else|involved|partner)\b",
    "document_shown": r"\b(document|passport|emirates id|bank statement|proof)\b",
    "commitment": r"\b(next step|promised|follow.?up|viewing)\b",
}

# instruction -> specialist, in the words people use. Checked after the refusals below.
ROUTES = [
    (r"\bform ?f\b|\bmou\b", "formf", "Prepare Form F"),
    (r"\bdeck\b|presentation|slides?\b", "deck", "Rebuild the customer deck from live facts"),
    (r"\bscreen|sanction|\bpep\b", "screen", "Screen the parties"),
    (r"source of (funds|wealth)|\bincome\b|afford", "sof", "Check the customer's money story"),
    (r"cash report|goaml|\bdpmsr\b", "report", "Draft the cash report"),
    (r"\bexpect|payment plan|track (the )?(deposit|payment)", "pay", "Track the expected payments"),
    (r"\binvoice", "inv", "Process the invoice"),
    (r"\bnoc\b|trustee|transfer appointment", "transfer", "Track the NOC and transfer"),
    (r"follow.?up|summary to (the )?(customer|client)", "follow", "Draft the customer's follow-up"),
]

# what only people do, in the words people use: (pattern, action kind, the reply)
REFUSE = [
    (r"\btell\b.*\b(customer|client|him|her|karim|sara)\b.*\b(complian|suspic|flag|report|screen)", "send",
     "No agent tells a customer anything about compliance: that would tip them off. Priya decides what is said."),
    (r"\bsubmit\b", "submit", "Only Joseph submits portal forms. The Form F clerk can fill it and stop before Submit: say \"prepare Form F\"."),
    (r"\bapprove\b|\bsign off\b", "approve", "Approvals are given by the person they wait for, never by an agent. I can remind them."),
    (r"\brelease\b|\bpay (him|her|them|the (seller|developer|agent))\b|\bwire\b|transfer the (money|funds)"
     r"|^(?!.*\b(did|does|has|have|had|when|how|why|who|whether|remember|need to|i must|got to)\b).*\b(pay|settle)\b.*\b(invoices?|bills?|commission)\b", "release_money",
     "Only Ahmed releases money. The Payment tracker shows what is expected."),
    (r"\bfile\b.*\b(str|sar|report|goaml)\b|\b(str|sar)\b", "file_report", "Only Priya files reports. The Report drafter can prepare a draft for her."),
    (r"\bsuspicious\b", "decide_suspicion", "Only Priya decides whether anything is suspicious. The Source-of-funds analyst can lay out what fits and what is missing."),
    (r"\bmark\b.*\b(received|paid)\b", "mark_received", "Only a person marks money received. Open the payment on the Deal desk: the form is there for you to confirm."),
    (r"\bclear\b.*\b(hit|match|screening|name)\b", "clear_hit", "Only the compliance officer clears a screening result."),
    (r"\bsign\b(?! off| up| in)", "sign", "Only a person signs. I can prepare it and show you what it rests on."),
    (r"\b(send|share|give)\b.*\b(bank details|iban|account (number|details))\b", "send_bank_details",
     "No agent sends bank details. Payment instructions come from the signed documents, and Finance confirms them by phone."),
    (r"\b(change|update|edit)\b.*\bsettings?\b", "change_settings", "I don't change Settings: the owner does that on the Settings page."),
]


def _req(office: Office, kind: str) -> str:
    return f"{kind}-{office.log.list()[-1]['id'] + 1 if office.log.list() else 1}"


def _ask_back(office: Office, req: str, person: str, text: str, options: list[str], why: str, deal: str | None = None) -> dict:
    ev = office.log.append("question.asked", actor=NOVA, agent=NOVA, request=req, deal=deal,
                           content={"to": person, "text": text, "options": options, "why": why})
    return {"kind": "question", "text": text, "options": options, "why": why, "card": f"Q{ev['id']}"}


def deal_words(g: Graph, deal: str) -> set[str]:
    d = g.nodes[f"deal:{deal}"]
    words = set(re.findall(r"[a-z0-9]+", f"{deal} {d.props['property']} {d.props['customer']}".lower()))
    for f in g.facts(deal, live=False):
        words |= set(re.findall(r"[a-z]+", f"{f.props.get('payer', '')} {f.props.get('party', '')}".lower()))
    return {w for w in words if (len(w) >= 3 or w.isdigit()) and w not in {"unit", "gate", "the"}}


def resolve_deal(g: Graph, text: str, person: str) -> tuple[str | None, list[str]]:
    said = set(re.findall(r"[a-z0-9]+", text.lower()))
    hits = [d.deal for d in g.deals() if said & deal_words(g, d.deal)]
    if len(hits) == 1:
        return hits[0], hits
    brokers_own = PEOPLE.get(person, {}).get("role") == "Broker"  # a broker's "which deal?" is among their own
    pool = hits or [d.deal for d in g.deals() if not brokers_own or d.props.get("broker") == person]
    return (pool[0], pool) if len(pool) == 1 else (None, pool)


def _label(g: Graph, deal: str) -> str:
    d = g.nodes[f"deal:{deal}"].props
    return f"{d['property']} ({d['customer'].split()[0]})"


def _who_knows(g: Graph, deal: str | None) -> str:
    if deal and not deal.startswith("lead-"):
        return f"{name(g.nodes[f'deal:{deal}'].props['broker'])} was in the meeting and would know"
    return "Ask me about a deal, a person, the numbers, listings or viewings"


# ---------- records the graph returns for a question ----------

def records_for(g: Graph, deal: str, intents: set[str], question: str) -> list[str]:
    ids: list[str] = []
    add = lambda xs: ids.extend(x for x in xs if x not in ids)  # noqa: E731
    if "payer" in intents:
        for f in g.facts(deal, "payer"):
            add(n.id for n in g.history(f.id))
        add(f.id for f in g.facts(deal, "payment_promise"))
        add(t.id for t in g.of("task", deal, OPEN) if t.props["agent"] == "pay")
        add(c.id for c in g.of("check", deal, "open"))
    if "changed" in intents or "impact" in intents:
        for old in g.facts(deal, live=False):
            if old.status == "superseded":
                add([old.id, old.props["superseded_by"]])
                add(x.id for x in g.impact(old.id) if x.type != "draft")
    if "status" in intents:
        add(f.id for f in g.facts(deal))
        add(t.id for t in g.of("task", deal, OPEN))
        add(c.id for t in ("decision", "question", "check", "request") for c in g.of(t, deal, "open"))
    for kind, rx in KIND_WORDS.items():
        if re.search(rx, question.lower()):
            for f in g.facts(deal, kind):
                add(n.id for n in g.history(f.id))
    if not ids:
        # what the question asks beyond naming the deal; nothing matches that, nothing is returned
        named = deal_words(g, deal) | set(re.findall(r"[a-z0-9]+", g.nodes[f"deal:{deal}"].props["property"].lower()))
        rest = " ".join(w for w in re.findall(r"[a-z0-9]+", question.lower()) if w not in named)
        add(n.id for n in g.search(rest, deal, types={"fact", "task", "approval", "slide", "decision", "check"}, k=4))
    return ids


def compose(g: Graph, deal: str, intents: set[str], ids: list[str]) -> str:
    """The same records in plain sentences, for when no model is plugged in."""
    out = []
    if "payer" in intents and (payers := g.facts(deal, "payer")):
        f = payers[-1]
        hist = g.history(f.id)
        s = f'{f.props["payer"]} pays: {name(f.props["speaker"])} said "{f.props["quote"]}" ({f.id}).'
        if older := next((x for x in hist[1:] if x.props["kind"] == "payer"), None):
            s += f' Earlier: "{older.props["quote"]}" ({older.id}), since replaced.'
        out.append(s)
        out += [f"Expected: {t.props['action'].removeprefix('Expect ')} ({t.id})." for t in g.of("task", deal, OPEN) if t.props["agent"] == "pay"]
        out += [f"Priya reviews the change before any money moves ({c.id})." for c in g.of("check", deal, "open")]
    elif "changed" in intents or "impact" in intents:
        for old in (f for f in g.facts(deal, live=False) if f.status == "superseded"):
            new = g.nodes[old.props["superseded_by"]]
            hit = [x for x in g.impact(old.id) if x.type != "draft"]
            out.append(f'"{old.props["quote"]}" ({old.id}) became "{new.props["quote"]}" ({new.id}).')
            if hit:
                out.append("It touched: " + "; ".join(g.record(x.id).split(" · ", 1)[1] + f" ({x.id})" for x in hit) + ".")
    else:
        for i in ids[:4]:
            n = g.nodes[i]
            out.append(f'{name(n.props["speaker"])} said "{n.props["quote"]}" ({i}).' if n.type == "fact"
                       else f'{g.record(i).split(" · ", 1)[1]} ({i}).')
    return " ".join(out)


def evidence_from(g: Graph, ids: list[str]) -> list[Evidence]:
    return [Evidence(g.nodes[i].props["quote"], i) for i in ids if g.nodes[i].type == "fact"]


# ---------- ask ----------

# what each conversation was last about, so "and who pays?" follows on from the deal just discussed
SESSIONS: dict[str, str] = {}


def converse(office: Office, text: str, person: str = "layla", *, session: str = "default", now: datetime | None = None,
             tape_root=None) -> dict:
    """One turn of talking to Nova: finish a read-back, take a request for someone, answer a question, or route work."""
    from diwan.agents import lobby
    now = now or datetime.now(DUBAI)
    person = pid(person) or "layla"
    t = text.strip()
    from diwan.agents import frontdesk, lessons
    if out := lessons.follow_up(office.log, t, session, person):
        return out
    if out := lobby.follow_up(office, t, person, session, now):
        return out
    if frontdesk.is_owner(person):
        from diwan.agents import triage
        if out := triage.follow_up(office, t, person, session, now):
            return out
    if out := frontdesk.handle(office, t, person, session, now):
        return out
    if m := re.match(r"(?i)^\s*(?:set\s+)?(\w[\w' -]*?)\s+(?:to|on)\s+(autopilot|review everything|review all|review key actions|review key|review)\s*$", t):
        from diwan.agents.charters import ROSTER
        agent = next((c.id for c in ROSTER if c.name.lower() == m.group(1).lower()), None)
        if agent:  # a setting: never changed by a PA, whoever asks
            res = runner.submit(office.log, get(NOVA), Pack(_req(office, "route"), NOVA, f"Not something an agent may do: {t}", actions=[Action("change_settings", t)]), sources={})
            return {"kind": "refused", "event": res.refused[0]["id"], "text": f"I don't change how agents run. Set {get(agent).name} on the Team page."}
    if out := lessons.draft(t, session):
        return out
    if m := re.match(r"(?i)^(?:brief me|set (?:my )?briefing)(?: at| for| to)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t):
        h = int(m.group(1)) + (12 if m.group(3) == "pm" and int(m.group(1)) < 12 else 0)
        at = f"{h:02d}:{m.group(2) or '00'}"
        set_briefing_time(office, person, at)
        return {"kind": "done", "text": f"Done. I'll do my rounds before {at} and have your briefing ready then."}
    if re.match(r"(?i)^(brief me|brief|play( the)? briefing|what('s| is) (new|happening))\W*$", t):
        return brief(office, person, log=False, now=now) | {"kind": "brief"}
    if not any(re.search(rx, t.lower()) for rx, _, _ in REFUSE) and (out := lobby.draft(t, person, session, now)):
        return out  # a request for a person; anything only people may do is refused by route() below first
    low = t.lower()
    jotting = re.search(r"\b(remember to|don'?t forget|not forget|forget to)\b", low)  # "I need to remember to sign the lease" asks for a note, not a signature
    if not jotting and any(re.search(rx, low) for rx, _, _ in REFUSE) and re.match(POLITE, low):  # "could you approve it?" is still asking her to approve it
        return route(office, t, person, tape_root=tape_root)
    named, _ = resolve_deal(office.graph(), t, person)
    asking = t.endswith("?") or re.match(ASKING, low)  # a trigger word inside a question is conversation, not an order
    exact = ((not asking and not jotting and any(re.search(rx, low) for rx, _, _ in REFUSE + ROUTES)) or re.search(HEAR, low) or (re.search(SMALLTALK, low) and len(low.split()) <= 6 and not frontdesk.TURNS.get(session))
             or (named and asking and len(low.split()) <= 14 and any(re.search(rx, low) for rx in INTENTS.values())))  # a short question about one deal, with its records
    if not exact and (out := frontdesk.think(office, t, person, session, now)):  # anything else: she thinks, with the whole office in front of her
        return out
    q = (t.endswith("?") or re.search(HEAR, t.lower()) or re.match(r"(?i)(who|what|when|where|why|how|is|are|does|did|can|which|show|find|any|hi|hello|hey|thanks|summar\w*|tell me|give me)\b", t)
         or re.search(SMALLTALK, t.lower()))
    return ask(office, t, person, session=session, tape_root=tape_root, today=now.date()) if q else route(office, t, person, tape_root=tape_root)


def ask(office: Office, question: str, person: str = "layla", *, session: str | None = None, tape_root=None, today=None, scoped: bool = False) -> dict:
    """`scoped`: a staff member's PA asking about one deal they may see: the deal's records only, not the office's numbers."""
    g, req, person = office.graph(), _req(office, "ask"), pid(person) or "layla"
    c = get(NOVA)
    intents = {k for k, rx in INTENTS.items() if re.search(rx, question.lower())}
    if not scoped and (out := everyday(office, g, question, person, req)):
        return out
    if not scoped and intents <= {"needs"} and "needs" in intents:
        b = brief(office, person, log=False)
        return {"kind": "answer", "text": b["text"], "cites": sorted({r for ln in b["lines"] for r in ln["refs"]}), "by": "rules", "request": req}
    from diwan.agents import records
    if not scoped and (out := records.delegate(office, question, person, req, today=today)):
        return out
    deal, pool = resolve_deal(g, question, person)
    if deal is None and session and SESSIONS.get(session) in {d.deal for d in g.deals()}:
        deal = SESSIONS[session]
    if deal and session:
        SESSIONS[session] = deal
    if deal is None and (not intents or len(pool) > MANY):  # nothing in the words points at a deal: don't read out the whole pipeline
        from diwan.agents import frontdesk
        if not scoped and re.search(r"\b(departments?|teams?|everyone|marketing|sales|finance|compliance|operations|going on|working on|summar\w*|brief)\b", question.lower()):
            return {"kind": "answer", "text": frontdesk.office_summary(office, person, datetime.now(DUBAI)), "cites": [], "by": "rules", "request": req}
        return {"kind": "unknown", "text": "I can't reach Muse just now, so I can only do the simple things. Ask me what needs you today, or name a client.", "cites": [], "request": req}
    if deal is None:
        opts = [_label(g, d) for d in pool]
        return _ask_back(office, req, person, f"Which deal do you mean: {' or '.join(opts)}?", opts,
                         "The question fits more than one deal, and answering about the wrong one is worse than asking.")
    ids = records_for(g, deal, intents, question)
    sources = {i: g.record(i) for i in ids}
    office.log.append("agent.started", actor=NOVA, agent=NOVA, request=req, deal=deal, content={"task": question, "sources": ids, "asked_by": person})
    if not ids:
        pack = Pack(req, NOVA, "I don't have that in the office's records.", missing=[question], next=[_who_knows(g, deal)])
        runner.submit(office.log, c, pack, sources=sources, deal=deal)
        return {"kind": "unknown", "text": f"Not recorded. {_who_knows(g, deal)}.", "cites": [], "request": req}
    system = runner.instructions(c, office.log)
    task = f"{name(person)} asks: {question}\nAnswer in at most three sentences from these records only, citing record ids in brackets."
    res = None
    if runner.has_model(c, system, runner.user_message(task, sources), tape_root=tape_root):
        try:
            res = runner.run(office.log, NOVA, request=req, task=task, sources=sources, deal=deal, tape_root=tape_root, timeout=runner.LIVE)
        except (runner.NotSetUp, ProviderError, KeyError, TypeError):
            res = None  # the model was too slow or failed (logged as agent.failed): answer from the records in plain sentences
    if res:
        if not res.pack.evidence:
            return {"kind": "unsupported", "request": req, "cites": [],
                    "text": f"I couldn't back an answer with a record, so I won't guess. {_who_knows(g, deal)}."}
        return {"kind": "answer", "text": res.pack.verdict, "cites": [e.source for e in res.pack.evidence], "by": res.usage.get("provider"), "request": req}
    text = compose(g, deal, intents, ids)
    pack = Pack(req, NOVA, text, evidence=evidence_from(g, ids), next=[])
    runner.submit(office.log, c, pack, sources=sources, deal=deal)
    return {"kind": "answer", "text": text, "cites": ids, "by": "rules", "request": req}


# ---------- everyday questions the records answer directly ----------

SMALLTALK = r"^\s*(hi|hello|hey|salam|marhaba|good (morning|afternoon|evening))\b|\bhow are you\b|^\s*(thanks|thank you)\b"
HEAR = r"\b(can|do|could) you (hear|see|read) me\b|\bare you (there|listening|working)\b|^\W*(testing|test|mic check)\W*$"
ASKING = r"\W*(who|what|when|where|why|how|is|are|does|did|can|which|should|do|has|have|will|would)\b"
POLITE = r"\W*(please\b|(could|can|would|will) you\b(?!\s+(tell|show|explain|check|see|find)\b)|i (need|want) you to\b)"  # a request dressed as a question
MANY = 5  # more deals than this is a list nobody can read: ask for a name instead
FOCUS = r"\b(focus|priorit\w*|what should i (do|look at)|my day|on my plate|anything urgent|urgent)\b"
JUDGE = (r"\b(good|bad|trustworthy|trusted|reliable|honest|risky|dodgy|safe|serious|genuine)\s+(customer|client|buyer|person|guy|lead)\b"
         r"|\bis \w+ (trustworthy|risky|honest|reliable|suspicious|legit)\b|\bcan (we|i) trust\b")
SUMMARY = r"\b(summar\w*|overview|status|where are we|tell me about|update on|brief me on|how is .* going)\b"


def everyday(office: Office, g: Graph, q: str, person: str, req: str) -> dict | None:
    low = q.lower().strip()
    c = get(NOVA)

    def answer(text: str, cites: list[str], kind: str = "answer") -> dict:
        runner.submit(office.log, c, Pack(req, NOVA, text, evidence=evidence_from(g, [x for x in cites if x in g.nodes])),
                      sources={x: g.record(x) for x in cites if x in g.nodes})
        return {"kind": kind, "text": text, "cites": cites, "by": "rules", "request": req}

    if re.search(HEAR, low):
        return {"kind": "answer", "text": f"Yes, I can hear you, {name(person)}. What do you need?", "cites": [], "by": "rules", "request": req}
    if re.search(SMALLTALK, low) and len(low.split()) <= 6:
        if low.startswith(("thanks", "thank you")):
            return {"kind": "answer", "text": "Any time.", "cites": [], "by": "rules", "request": req}
        b = brief(office, person, log=False)
        n = len([ln for ln in b["lines"] if ln["needs"]])
        return {"kind": "answer", "cites": [], "by": "rules", "request": req,
                "text": f"{greeting(datetime.now(DUBAI))}, {name(person)}. All good here. "
                        + (f"{n} thing{'s' if n != 1 else ''} need{'' if n != 1 else 's'} you; shall I go through them?" if n else "Nothing needs you right now.")}
    if re.search(FOCUS, low):
        b = brief(office, person, log=False)
        needs = [ln for ln in b["lines"] if ln["needs"]]
        others = []
        if person == "layla":  # the owner also sees what everyone else is waiting on
            for who in PEOPLE:
                if who == person:
                    continue
                theirs = [ln for ln in brief(office, who, log=False)["lines"] if ln["needs"]]
                if theirs:
                    others.append((who, theirs))
        tail = (" Waiting on others: " + " ".join(f"{name(w)}: {ls[0]['text']}" + (f" (and {len(ls) - 1} more)" if len(ls) > 1 else "") for w, ls in others)
                if others else "")
        if not needs:
            return answer("Nothing is waiting on you personally." + (tail or " The agents have the rest in hand."),
                          [r for _, ls in others for ln in ls for r in ln["refs"]])
        return answer("Here's what needs you, most urgent first: " + " ".join(f"{i}. {ln['text']}" for i, ln in enumerate(needs, 1)) + tail,
                      [r for ln in needs for r in ln["refs"]])
    if re.search(JUDGE, low):
        deal, _ = resolve_deal(g, q, person)
        facts = [f.id for f in g.facts(deal)] if deal else []
        return answer("I don't judge people, and nobody here decides that from a feeling. Here is what's on record"
                      + (f": {compose(g, deal, {'status'}, facts)}" if facts else ".") + " Anything about risk is Priya's call.", facts)
    if re.search(r"\b(experiments?|lobby (room|idea)|idea of the day)\b", low):
        from diwan import lobby_room
        run = g.of("experiment", status="running")
        tip = lobby_room.idea(g)
        refs = [x.id for x in run] + (tip["refs"] if tip else [])
        return answer((f"{len(run)} experiment{'s' if len(run) != 1 else ''} running: " + "; ".join(f"{x.id}, {x.label}" for x in run) + "." if run else "No experiments are running.")
                      + (f" Today's idea from the Lobby: {tip['text']}." if tip else ""), refs)
    if re.search(r"\b(lobby|board|requests?|what did i ask|asked for|chas\w*|late|overdue)\b", low):
        cards = [c for c in g.of("lobby") if c.status not in ("cancelled",)]
        live = [c for c in cards if c.status != "done"]
        if not cards:
            return answer("The requests board is empty. Tell me who needs to do what, and by when.", [])
        line = lambda c: f"{c.id}: {name(c.props['to'])}, \"{c.props['text']}\", due {lobby_due(c)}, {c.status}"  # noqa: E731
        late = [c for c in live if c.status == "late"]
        return answer(f"{len(live)} open on the requests board" + (f", {len(late)} late" if late else "") + ". "
                      + "; ".join(line(c) for c in live) + "." + (f" Done: {len(cards) - len(live)}." if len(cards) > len(live) else ""),
                      [c.id for c in cards])
    if re.search(r"\bviewings?\b", low):
        vs = g.of("viewing", status="booked")
        if not vs:
            return answer("No viewings are booked yet. Rania books them from WhatsApp.", [])
        return answer(f"{len(vs)} viewing{'s' if len(vs) != 1 else ''} booked: " + "; ".join(g.record(v.id).split(" · ", 1)[1] for v in vs) + ".", [v.id for v in vs])
    if re.search(r"\b(listings?|propert(y|ies)|most expensive|cheapest|for sale|on the market|inventory)\b", low):
        ls = g.of("listing")
        if not ls:
            return answer("There are no listings yet. Add them on the Knowledge page.", [])
        ad = [x for x in ls if x.props.get("permit") and x.status == "available"]
        if "expensive" in low or "highest" in low:
            x = max(ls, key=lambda n: n.props["price_aed"])
            return answer(f"The most expensive is {x.props['title']}, {x.props['community']}, at AED {x.props['price_aed']:,}.", [x.id])
        if "cheap" in low or "lowest" in low:
            x = min(ls, key=lambda n: n.props["price_aed"])
            return answer(f"The cheapest is {x.props['title']}, {x.props['community']}, at AED {x.props['price_aed']:,}.", [x.id])
        no_permit = [x for x in ls if x not in ad]
        return answer(f"{len(ls)} listings, {len(ad)} advertised: " + "; ".join(f"{x.props['title']} (AED {x.props['price_aed']:,})" for x in ad)
                      + (f". Not advertised until a permit is added: {', '.join(x.props['title'] for x in no_permit)}." if no_permit else "."), [x.id for x in ls])
    if m := re.match(r"^\s*who(?:'s| is)\s+([a-z]+)", low):
        who = m.group(1)
        if who in ("paying", "pays", "handling", "the", "on", "in"):
            return None
        ppl = [n for n in g.of("person") if n.label.lower().split()[0] == who or n.label.lower() == who]
        if not ppl and pid(who):
            p = PEOPLE[pid(who)]
            team = f", working with the {get(p['team']).name}" if p.get("team") else ""
            waiting = [ln for ln in brief(office, pid(who), log=False)["lines"] if ln["needs"]]
            return answer(f"{p['name']} is our {p['role'].lower()}{team}. "
                          + (f"{len(waiting)} thing{'s' if len(waiting) != 1 else ''} waiting for {p['name']} now." if waiting else "Nothing is waiting for them now."),
                          [r for ln in waiting for r in ln["refs"]])
        if not ppl:
            return answer(f"I don't have anyone called {m.group(1).capitalize()} in the records.", [])
        n = ppl[0]
        bits = [f"{n.label}" + (f" is the {n.props['role'].lower()}" if n.props.get("role") else "")]
        for e in g.edges:
            if e.dst == n.id and e.rel not in ("said", "customer_of", "broker_on", "pays_for", "with"):
                bits.append(f"{g.nodes[e.src].label}'s {e.rel}" + (f" ({e.via})" if e.via else ""))
            if e.src == n.id and e.rel == "customer_of":
                bits.append(f"customer on {g.nodes[e.dst].label}")
            if e.src == n.id and e.rel == "pays_for" and g.nodes.get(e.via) and g.nodes[e.via].status == "superseded":
                bits.append(f"was going to pay, but that was taken back ({e.via})")
            elif e.src == n.id and e.rel == "pays_for":
                bits.append(f"pays for {g.nodes[e.dst].label} ({e.via})")
        return answer(", ".join(bits) + ".", [e.via for e in g.edges if (e.src == n.id or e.dst == n.id) and e.via])
    if re.search(SUMMARY, low):
        deal, pool = resolve_deal(g, q, person)
        if deal:
            ids = records_for(g, deal, {"status", "changed"}, q)
            d = g.nodes[f"deal:{deal}"].props
            facts = g.facts(deal)
            open_t = g.of("task", deal, OPEN)
            cards = [n for t in ("decision", "check", "question", "request") for n in g.of(t, deal, "open")]
            head = f"{d['property']}, customer {d['customer']}, broker {name(d['broker'])}. "
            body = " ".join(f'{name(f.props["speaker"])} said "{f.props["quote"]}" ({f.id}).' for f in facts[:4])
            changed = compose(g, deal, {"changed"}, ids)
            tail = f" {len(open_t)} task{'s' if len(open_t) != 1 else ''} open; {len(cards)} waiting for people." if open_t or cards else ""
            return answer(head + body + (" Changes: " + changed if changed else "") + tail, ids)
    return None


# ---------- route ----------

ROUTE_SCHEMA = {"name": "route", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": ["agent", "action", "confidence", "question"],
    "properties": {"agent": {"type": "string"}, "action": {"type": "string"}, "confidence": {"type": "number"},
                   "question": {"type": "string"}}}}


def route(office: Office, text: str, person: str = "layla", *, tape_root=None) -> dict:
    g, req, person = office.graph(), _req(office, "route"), pid(person) or "layla"
    nova = get(NOVA)
    said = office.log.append("instruction.given", actor=person, agent=NOVA, request=req, content={"text": text})
    low = text.lower()
    for rx, kind, reply in REFUSE:
        if re.search(rx, low):
            res = runner.submit(office.log, nova, Pack(req, NOVA, f"Not something an agent may do: {text}", actions=[Action(kind, text)]),
                                sources={}, caused_by=said["id"])
            return {"kind": "refused", "text": reply, "event": res.refused[0]["id"], "request": req}
    hits = list(dict.fromkeys(agent for rx, agent, _ in ROUTES if re.search(rx, low)))
    action = next((a for rx, agent, a in ROUTES if hits and agent == hits[0] and re.search(rx, low)), None)
    if not hits:
        user = f"Instruction: {text}\nAgents: " + "; ".join(f"{c.id} = {c.name}: {c.job}" for c in _specialists())
        out = None
        if runner.has_model(nova, runner.instructions(nova), user, schema=ROUTE_SCHEMA, tape_root=tape_root):
            try:
                out = runner.call(nova, runner.instructions(nova), user, schema=ROUTE_SCHEMA, tape_root=tape_root, timeout=runner.LIVE).data
            except (ProviderError, KeyError):
                out = None
        if out:
            if out["confidence"] >= 0.6 and out["agent"] in {c.id for c in _specialists()}:
                hits, action = [out["agent"]], out["action"]
            else:
                return _ask_back(office, req, person, out["question"] or "Which team should take this?", _teams(),
                                 f"Not sure enough to route it (confidence {out['confidence']:.2f}).")
        else:
            return _ask_back(office, req, person, "Which team should take this?", _teams(), "No team's work matches these words.")
    if len(hits) > 1:
        opts = [get(h).name for h in hits]
        return _ask_back(office, req, person, f"Should this go to the {' or the '.join(opts)}?", opts, "The words fit more than one agent.")
    c = get(hits[0])
    lead = get(c.parent)
    deal, pool = resolve_deal(g, text, person)
    if deal is None and len(pool) > MANY:
        return _ask_back(office, req, person, "For which client or property?", [], "The instruction does not name a deal.")
    if deal is None:
        opts = [_label(g, d) for d in pool]
        return _ask_back(office, req, person, f"For which deal: {' or '.join(opts)}?", opts, "The instruction does not name a deal.")
    runner.submit(office.log, nova, Pack(req, NOVA, f"Sent to the {lead.name}, for the {c.name}.", actions=[Action("route", f"{action} → {lead.name}")]),
                  sources={}, deal=deal, caused_by=said["id"])
    runner.submit(office.log, lead, Pack(req, lead.id, f"{c.name}: {action}.", actions=[Action("assign", f"{action} → {c.name}")]),
                  sources={}, deal=deal, caused_by=said["id"])
    tid = office.add_task(deal, c.id, action, by=lead.id, request=req, caused_by=said["id"])
    if handler := HANDLERS.get(c.id):
        result = handler(office, deal, tid, req)
        return {"kind": "done", "text": f"The {lead.name} gave it to the {c.name}. {result}", "task": tid, "agent": c.id, "request": req}
    state = "not built yet" if c.status in ("planned", "parked") else "will pick it up"
    return {"kind": "queued", "text": f"The {lead.name} gave it to the {c.name} ({tid}); the {c.name} is {state}.", "task": tid, "agent": c.id, "request": req}


def _specialists():
    from diwan.agents.charters import ROSTER
    return [c for c in ROSTER if c.level is None and c.hack]


def _teams() -> list[str]:
    return ["Sales", "Operations", "Finance", "Compliance"]


HANDLERS = {"formf": operations.formf_plan}


# ---------- brief ----------

def greeting(now: datetime) -> str:
    h = now.astimezone(DUBAI).hour
    return "Good morning" if h < 12 else "Good afternoon" if h < 17 else "Good evening"


def lead_report(office: Office, g: Graph, lead_id: str, day_start: str) -> Pack:
    """One department's update for Nova's rounds, built only from its records."""
    from diwan.agents.charters import children
    lead = get(lead_id)
    team = {lead_id} | {c.id for c in children(lead_id)}
    open_tasks = [t for t in g.of("task", status=OPEN) if t.props["agent"] in team and not t.props.get("needs_person")]
    waiting = [t for t in g.of("task", status=OPEN) if t.props["agent"] in team and t.props.get("needs_person")]
    cards = [n for typ in ("check", "decision", "request", "question") for n in g.of(typ, status="open") if n.props.get("agent") in team]
    done_today = [e for e in office.log.list() if e["type"] == "task.done" and e["agent"] in team and e["at"] >= day_start]
    board = [c for c in g.of("lobby", status={"open", "seen", "late"}) if c.props["team"] == lead_id]
    parts, refs = [], []
    if done_today:
        parts.append(f"{len(done_today)} done today")
    if open_tasks:
        parts.append(f"{len(open_tasks)} task{'s' if len(open_tasks) != 1 else ''} in hand")
        refs += [t.id for t in open_tasks]
    by_person: dict[str, list] = {}
    for c in cards:
        by_person.setdefault(name(c.props.get("who")), []).append(c)
    for who, cs in by_person.items():
        what = cs[0].props.get("title") or {"decision": "a decision", "question": "a question", "request": cs[0].props.get("summary", "a sign-off")}.get(cs[0].type, "an item")
        parts.append(f"{who} to review: {what.lower()}" if len(cs) == 1 else f"{who} has {len(cs)} items to review")
        refs += [c.id for c in cs]
    for c in board:
        parts.append(f"{c.id} for {name(c.props['to'])}, due {lobby_due(c)}{' (LATE)' if c.status == 'late' else ''}")
        refs.append(c.id)
    if waiting and not board:
        parts.append(f"{len(waiting)} waiting on people")
        refs += [t.id for t in waiting]
    verdict = f"{lead.name.replace(' lead', '')}: " + ("; ".join(parts) if parts else "all quiet") + "."
    return Pack(f"rounds", lead_id, verdict, next=refs)


def lobby_due(c) -> str:
    return datetime.fromisoformat(c.props["due"]).strftime("%I:%M %p %a").lstrip("0") if c.props.get("due") else "no deadline"


LEADS = ["sales", "mkt", "ops", "fin", "comp", "review", "records"]


def rounds(office: Office, now: datetime | None = None) -> dict:
    """Nova goes to every department lead and collects its update, so the briefing is ready before anyone asks."""
    now = now or datetime.now(DUBAI)
    day_start = now.astimezone(DUBAI).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
    start = office.log.append("rounds.started", actor=NOVA, agent=NOVA, content={"leads": LEADS})
    g = office.graph()
    reports = {}
    for lid in LEADS:
        pack = lead_report(office, g, lid, day_start)
        runner.submit(office.log, get(lid), pack, sources={}, caused_by=start["id"])
        reports[lid] = pack.verdict
    office.log.append("briefing.ready", actor=NOVA, agent=NOVA, caused_by=start["id"], content={"reports": reports})
    return reports


def brief(office: Office, person: str, *, since: int = 0, log: bool = True, now: datetime | None = None) -> dict:
    """Hello, then what needs this person, then each department's update from Nova's rounds. Every line cites records."""
    g, person = office.graph(), pid(person) or person
    now = now or datetime.now(DUBAI)
    lines: list[dict] = []
    for typ in ("check", "decision", "request", "question"):
        for n in g.of(typ, status="open"):
            if n.props.get("who") == person and n.props.get("agent") != NOVA:  # her own "which deal?" was answered in the chat, or dropped
                lines.append({"text": n.props["text"], "refs": [n.id] + list(n.props.get("refs", [])), "needs": True})
    for c in g.of("lobby", status={"open", "seen", "late"}):
        if c.props.get("to") == person:
            lines.append({"text": f"{name(c.props['by'])} asked for \"{c.props['text']}\", due {lobby_due(c)}{' and it is late' if c.status == 'late' else ''}.",
                          "refs": [c.id], "needs": True})
        elif c.props.get("by") == person and c.status == "late":
            lines.append({"text": f"{name(c.props['to'])} is late with \"{c.props['text']}\" (was due {lobby_due(c)}).", "refs": [c.id], "needs": True})
    for c in g.of("lobby", status="done"):
        if c.props.get("by") == person and c.event > since:
            lines.append({"text": f"{name(c.props['to'])} finished \"{c.props['text']}\".", "refs": [c.id], "needs": False})
    for t in g.of("task", status=OPEN):
        if t.props.get("needs_person") == person and not any(r for ln in lines for r in ln["refs"] if g.nodes.get(r) and g.nodes[r].type == "lobby"
                                                              and g.nodes[r].props.get("task") == t.id):
            lines.append({"text": t.props["action"], "refs": [t.id], "needs": True})
    mine = [d.deal for d in g.deals() if person in ("layla", "priya", "ahmed", "joseph") or d.props.get("broker") == person]
    for f in g.of("fact", status="superseded"):
        if f.deal in mine and f.event > since:
            new = g.nodes[f.props["superseded_by"]]
            if not any({f.id, new.id} <= set(ln["refs"]) for ln in lines):
                said = (f"{new.props['quote']}." if new.props["quote"].startswith("Agreed price")  # a broker entering a price takes nothing back
                        else f'{name(new.props["speaker"])} took back "{f.props["quote"]}" and said "{new.props["quote"]}".')
                lines.append({"text": said, "refs": [f.id, new.id], "needs": False})
    if PEOPLE.get(person, {}).get("role") == "Owner":  # the Lobby: what finished and waits for the owner, and one idea a day
        from diwan import lobby_room
        for x in lobby_room.waiting(g):
            lines.append({"text": f"Experiment {x.id} has finished: {x.label}. {x.props['result']['line']} Keep it or roll it back.", "refs": [x.id], "needs": True})
        if tip := lobby_room.idea(g, now):
            lines.append({"text": f"One idea from the Lobby: {tip['text']}.", "refs": [r for r in tip["refs"] if r in g.nodes], "needs": False, "idea": True})
    departments = []
    if g.rounds:
        scope = LEADS if person == "layla" else [PEOPLE_TEAM.get(person)] if PEOPLE_TEAM.get(person) else []
        for lid in scope:
            if p := g.rounds["reports"].get(lid):
                departments.append({"text": p["verdict"], "refs": [r for r in p.get("next", []) if r in g.nodes], "lead": lid})
    working = [t for t in g.of("task", status=OPEN) if not t.props.get("needs_person") and t.deal in mine]
    needs = [ln for ln in lines if ln["needs"]]
    head = f"{greeting(now)}, {name(person)}. " + (f"{len(needs)} thing{'s' if len(needs) != 1 else ''} need{'' if len(needs) != 1 else 's'} you."
                                                  if needs else "Nothing needs you.")
    tail = f" The agents are handling {len(working)} task{'s' if len(working) != 1 else ''}." if working else ""
    dept = (" Here is the round of the departments. " + " ".join(d["text"] for d in departments)) if departments else ""
    text = " ".join([head] + [ln["text"] for ln in needs] + [ln["text"] for ln in lines if not ln["needs"]]) + tail + dept
    if log:
        refs = list(dict.fromkeys(r for ln in lines for r in ln["refs"] if r in g.nodes))
        pack = Pack(_req(office, "brief"), NOVA, head, evidence=evidence_from(g, refs), next=[ln["text"] for ln in lines])
        runner.submit(office.log, get(NOVA), pack, sources={r: g.record(r) for r in refs})
    return {"person": person, "text": text, "lines": lines, "departments": departments, "working": [t.id for t in working],
            "rounds_at": g.rounds["at"] if g.rounds else None}


PEOPLE_TEAM = {"priya": "comp", "ahmed": "fin", "joseph": "ops", "omar": "sales"}
DUBAI = timezone(timedelta(hours=4))
DEFAULT_TIME = "08:00"  # with the rounds 30 minutes before: 07:30 Dubai time


def briefing_time(g: Graph, person: str) -> str:
    return g.settings.get(person, {}).get("briefing_time", DEFAULT_TIME)


def briefing_due(now: datetime, last_day: str | None, at: str = "07:00", lead_minutes: int = 0) -> bool:
    """Once a day, `lead_minutes` before the time `at` (Dubai)."""
    local = now.astimezone(DUBAI)
    hh, mm = map(int, at.split(":"))
    target = local.replace(hour=hh, minute=mm, second=0, microsecond=0) - timedelta(minutes=lead_minutes)
    return local >= target and local.date().isoformat() != last_day


def set_briefing_time(office: Office, person: str, at: str) -> None:
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", at):
        raise ValueError("Use a time like 09:00")
    office.log.append("setting.changed", actor=person, content={"person": person, "key": "briefing_time", "value": at.zfill(5)})


def morning(office: Office, now: datetime | None = None) -> list[dict]:
    rounds(office, now)
    return [brief(office, p, now=now) for p in PEOPLE]
