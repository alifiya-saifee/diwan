"""The Records team: the Archivist finds documents, the Data analyst answers with numbers. Every number is computed in
code from the records it counts, and every answer lists those records; a model may phrase an answer, never produce a
number. A question about a period or document the records do not cover says so.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from diwan.agents import runner
from diwan.agents.charters import get
from diwan.graph import Graph
from diwan.office import Office
from diwan.pack import Action, Evidence, Pack
from diwan.people import name

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
NUMBERS = r"\b(sales?|sold|revenue|turnover|volume|commissions?|earned|made|pipeline|how many deals|closed|spend|spent|expenses?|costs?|top broker|best broker)\b"
DOCUMENTS = r"\b(invoices?|bills?|receipts?|contracts?|mou|form ?f|documents?|files?|statements?|paperwork|archive)\b"
DOC_KINDS = {"invoice": "invoice", "bill": "bill", "receipt": "receipt", "contract": "contract", "mou": "contract",
             "form": "form", "statement": "statement"}


def period(text: str, today: date) -> tuple[date, date, str] | None:
    """The period a question asks about: (first day, last day, how to say it). None when no period is named."""
    low = text.lower()
    first_this = today.replace(day=1)
    if "last month" in low or "previous month" in low:
        end = first_this - timedelta(days=1)
        start = end.replace(day=1)
        return start, end, f"last month ({start.strftime('%B %Y')})"
    if "this month" in low:
        return first_this, today, f"this month ({today.strftime('%B %Y')}, so far)"
    if "this year" in low or "year to date" in low or "ytd" in low:
        return date(today.year, 1, 1), today, f"{today.year} so far"
    if "last year" in low:
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), str(today.year - 1)
    if m := re.search(r"\bq([1-4])\b", low):
        q = int(m.group(1))
        start = date(today.year, 3 * q - 2, 1)
        end = (date(today.year + (q == 4), (3 * q) % 12 + 1, 1)) - timedelta(days=1)
        return start, end, f"Q{q} {today.year}"
    for i, mname in enumerate(MONTHS):
        if re.search(rf"\b{mname}\b|\b{mname[:3]}\b", low):
            y = today.year if i + 1 <= today.month else today.year - 1
            start = date(y, i + 1, 1)
            end = date(y + (i == 11), (i + 1) % 12 + 1, 1) - timedelta(days=1)
            return start, end, start.strftime("%B %Y")
    if "last week" in low:
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6), "last week"
    return None


def _in(d: str, p: tuple[date, date, str]) -> bool:
    return p[0] <= date.fromisoformat(d[:10]) <= p[1]


def aed(v: float) -> str:
    return f"AED {round(v):,}"


def analyse(g: Graph, question: str, today: date) -> tuple[str, list[str], list[str]]:
    """(answer, records counted, what is missing)."""
    low = question.lower()
    p = period(question, today)
    if re.search(r"\bpipeline\b|open deals|in progress", low):
        deals = [d for d in g.deals() if not d.deal.startswith("lead-")]
        expected = [(d, (g.facts(d.deal, "deal_term") or [None])[-1]) for d in deals]
        value = sum(f.props["amount_aed"] for _, f in expected if f)
        refs = [d.id for d in deals] + [f.id for _, f in expected if f]
        leads = [d for d in g.deals() if d.deal.startswith("lead-")]
        return (f"{len(deals)} open deal{'s' if len(deals) != 1 else ''} worth {aed(value)} at the prices customers stated, "
                f"plus {len(leads)} WhatsApp lead{'s' if len(leads) != 1 else ''}.", refs, [])
    if p is None:
        return "", [], ["Which period: last month, this month, this year, or a month by name?"]
    if re.search(r"\b(spend|spent|expenses?|costs?|bills?)\b", low):
        docs = [d for d in g.of("document") if d.props["kind"] in ("invoice", "bill") and _in(d.props["date"], p)]
        total = sum(d.props.get("amount_aed") or 0 for d in docs)
        if not docs:
            return f"No invoices or bills are filed for {p[2]}.", [], [f"Invoices and bills for {p[2]}"]
        top = max(docs, key=lambda d: d.props.get("amount_aed") or 0)
        return (f"Spending {p[2]}: {aed(total)} across {len(docs)} invoice{'s' if len(docs) != 1 else ''} and bills; "
                f"the largest was {top.props['title']} ({aed(top.props['amount_aed'])}).", [d.id for d in docs], [])
    sales = [s for s in g.of("sale") if _in(s.props["date"], p)]
    if not sales:
        return f"No sales closed {p[2]}.", [], []
    value = sum(s.props["price_aed"] for s in sales)
    comm = sum(s.props["commission_aed"] for s in sales)
    refs = [s.id for s in sales]
    if re.search(r"\b(top|best) broker|by broker|who sold", low):
        by: dict[str, int] = {}
        for s in sales:
            by[s.props["broker"]] = by.get(s.props["broker"], 0) + s.props["commission_aed"]
        ranked = sorted(by.items(), key=lambda x: -x[1])
        return (f"{p[2].capitalize()}: " + "; ".join(f"{name(b)} {aed(v)} commission" for b, v in ranked) + ".", refs, [])
    if re.search(r"\bcommissions?|earned|made\b", low):
        return f"Commission {p[2]}: {aed(comm)} from {len(sales)} sale{'s' if len(sales) != 1 else ''} worth {aed(value)}.", refs, []
    return (f"Sales {p[2]}: {len(sales)} closed, {aed(value)} in value, {aed(comm)} commission. "
            f"Largest: {max(sales, key=lambda s: s.props['price_aed']).props['listing']}.", refs, [])


def find_documents(g: Graph, question: str, today: date) -> tuple[str, list[str], list[str]]:
    low = question.lower()
    kinds = {v for k, v in DOC_KINDS.items() if re.search(rf"\b{k}", low)}
    p = period(question, today)
    docs = [d for d in g.of("document") if (not kinds or d.props["kind"] in kinds) and (not p or _in(d.props["date"], p))]
    words = set(re.findall(r"[a-z0-9]{3,}", low)) - set(DOC_KINDS) - {"the", "for", "show", "find", "get", "all", "our", "and",
                                                                       "last", "this", "month", "year", "documents", "files"} - set(MONTHS)
    named = [d for d in docs if words & set(re.findall(r"[a-z0-9]{3,}", f"{d.props['title']} {d.props.get('party') or ''}".lower()))]
    docs = named or docs
    plural = "s" if len(docs) != 1 else ""
    what = " and ".join(f"{k}{plural}" for k in sorted(kinds)) if kinds else f"document{plural}"
    when = f" for {p[2]}" if p else ""
    if not docs:
        what = " and ".join(f"{k}s" for k in sorted(kinds)) if kinds else "documents"
        return f"There are no {what}{when} in the archive.", [], [f"{what}{when}"]
    lines = "; ".join(f"{d.props['title']} ({d.props['date']}{', ' + aed(d.props['amount_aed']) if d.props.get('amount_aed') else ''})" for d in docs[:6])
    total = sum(d.props.get("amount_aed") or 0 for d in docs)
    tail = f" Total {aed(total)}." if total and len(docs) > 1 else ""
    return f"{len(docs)} {what}{when}: {lines}.{tail}", [d.id for d in docs], []


def delegate(office: Office, question: str, person: str, req: str, *, today: date | None = None) -> dict | None:
    """Nova hands a numbers or documents question to the Records team. None when it is neither."""
    low = question.lower()
    kind = "analyst" if re.search(NUMBERS, low) else "archivist" if re.search(DOCUMENTS, low) else None
    if not kind:
        return None
    today = today or datetime.now().date()
    g = office.graph()
    nova, lead, agent = get("nova"), get("records"), get(kind)
    runner.submit(office.log, nova, Pack(req, "nova", f"Asked the {lead.name} for {agent.name}.", actions=[Action("route", question)]), sources={})
    runner.submit(office.log, lead, Pack(req, lead.id, f"{agent.name}: {question}", actions=[Action("assign", question)]), sources={})
    office.log.append("agent.started", actor=agent.id, agent=agent.id, request=req, content={"task": question, "asked_by": person})
    text, refs, missing = (analyse if kind == "analyst" else find_documents)(g, question, today)
    sources = {r: g.record(r) for r in refs}
    pack = Pack(req, agent.id, text or missing[0], evidence=[Evidence(sources[r], r) for r in refs], missing=missing,
                actions=[Action("draft", "Answer")])
    runner.submit(office.log, agent, pack, sources=sources)
    if not text:
        return {"kind": "question", "text": missing[0], "options": ["Last month", "This month", "This year"], "request": req, "delegated_to": kind}
    return {"kind": "answer", "text": f"The {agent.name} says: {text}", "cites": refs, "by": kind, "request": req, "delegated_to": kind}


def ledger(g: Graph) -> list[dict]:
    return sorted(({"id": s.id, **s.props} for s in g.of("sale")), key=lambda s: s["date"], reverse=True)
