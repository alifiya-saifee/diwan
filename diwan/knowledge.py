"""What every agent may know and say, and the listings catalog, as one kind of item (docs/knowledge.md).

Knowledge items (K ids) and listings (listing:REF) share one format, one search, and one set of rules: the kind's owner
edits and retires; anyone else proposes, and the proposal waits for the owner. An edit is a new version (the old one
stays, marked replaced); a retire hides the item from every agent with a reason and can be undone. Nothing is erased:
each change is an event, and the graph is rebuilt from those events.

For agents, `search(g, question)` returns the best few confirmed, customer-facing items, each in `item()` format with
the id to cite. Nothing fits: the list is empty and the agent hands the chat to a person.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from diwan.graph import Graph, Node
from diwan.people import PEOPLE, name

# tab: (label, who may edit and retire besides the owner, what to add when it is empty)
KINDS = {
    "company": ("Company", {"layla"}, "Hours, fees, the buying process, policies and how to reach you. Add one item per fact, e.g. \"Office hours\"."),
    "answer": ("Approved answers", {"layla", "rashid"}, "Questions customers ask and the answer you approve. Brokers' replies in chats arrive here as proposals."),
    "project": ("Projects", {"layla", "rashid"}, "Off-plan projects: developer, payment plan, handover date. Set a valid-until date so an ended plan stops by itself."),
    "area": ("Areas", {"layla", "maya"}, "One guide per community, titled with its name (e.g. \"Dubai Marina\"): schools, metro, service-charge range."),
    "people": ("People", {"layla"}, "Which broker covers which areas, their languages and shifts."),
    "brand": ("Brand", {"layla", "maya"}, "The voice, words to use and avoid, and the sign-off. One item is enough."),
}
LISTING_OWNERS = {"layla", "rashid"}  # a broker proposes a price change; the listing owner decides (decision in docs/knowledge.md §7)
# kinds written before the tabs existed, and the topics the Brand brain learns, land on a tab
TAB_OF = {"faq": "answer", "fees": "company", "policy": "company", "policies": "company", "hours": "company", "document": "company",
          "about": "company", "services": "company", "contact": "company", "track record": "company", "areas": "area"}
FAST_REVIEW = {"fees", "policy", "policies"}  # re-confirmed every 90 days; other company basics every 180
FIELDS = ("title", "text", "audience", "review_by", "valid_until", "applies_to", "price_aed", "permit", "status", "photo")
FEED_QUIET = timedelta(days=7)


def tab(n: Node) -> str:
    if n.type == "listing":
        return "listing"
    k = n.props.get("kind") or "company"
    return k if k in KINDS else TAB_OF.get(k, "company")


def owners(n: Node) -> set[str]:
    return LISTING_OWNERS if n.type == "listing" else KINDS[tab(n)][1]


def may_edit(n: Node, who: str) -> bool:
    return who in owners(n)


def _day(iso: str | None) -> date | None:
    try:
        return date.fromisoformat(iso[:10]) if iso else None
    except ValueError:
        return None


def review_by(n: Node) -> date | None:
    """When this item must be re-confirmed: the date a person set, else the kind's period from its last confirmation."""
    if n.type == "listing":
        return None
    if set_by := _day(n.props.get("review_by")):
        return set_by
    t = tab(n)
    days = {"company": 90 if n.props.get("kind") in FAST_REVIEW else 180, "area": 90, "answer": 180}.get(t)
    seen = _day(n.props.get("reviewed_at") or n.at)
    return seen + timedelta(days=days) if days and seen else None


def stale(n: Node, today: date | None = None) -> str | None:
    """Why this item needs a person's look, or None."""
    today = today or datetime.now(timezone.utc).date()
    if n.status == "retired":
        return None
    if n.type == "listing":
        last = n.props.get("updated_at") or n.at
        if n.props.get("source") == "feed" and last and datetime.fromisoformat(last) < datetime.now(timezone.utc) - FEED_QUIET:
            return "the feed has not updated it for 7 days"
        return None
    if (until := _day(n.props.get("valid_until"))) and until < today:
        return f"ended on {until.isoformat()}"
    if (due := review_by(n)) and due < today:
        return f"review was due {due.isoformat()}"
    return None


def advertised(n: Node) -> bool:
    return n.type == "listing" and bool(n.props.get("permit")) and n.status == "available"


def usable(n: Node, today: date | None = None) -> bool:
    """May an agent say this to a customer?"""
    if n.type == "listing":
        return advertised(n)
    until = _day(n.props.get("valid_until"))
    return (n.type == "knowledge" and n.status == "confirmed" and n.props.get("audience", "customer") == "customer"
            and not (until and until < (today or datetime.now(timezone.utc).date())))


def usage(g: Graph, since: timedelta = timedelta(days=7)) -> dict[str, dict]:
    """{item id: {"week": replies this week that cited it, "last_chat": the chat that last did}} from what was sent."""
    cut, out = (datetime.now(timezone.utc) - since).isoformat(), {}
    for ch in g.of("chat"):
        for m in ch.props["messages"]:
            if m["type"] != "sent":
                continue
            for r in m.get("refs") or []:
                u = out.setdefault(r, {"week": 0, "total": 0, "last_chat": None, "last_at": ""})
                u["total"] += 1
                u["week"] += m["at"] >= cut
                if m["at"] >= u["last_at"]:
                    u.update(last_chat=ch.props["phone"], last_at=m["at"], last_name=ch.label)
    return out


def item(g: Graph, n: Node, used: dict | None = None) -> dict:
    """The one item format every screen and agent reads. `cite` is the id an answer names."""
    p, t = n.props, tab(n)
    out = {"id": n.id, "cite": n.id, "tab": t, "kind": p.get("kind") or t, "title": p.get("title") or n.label,
           "status": n.status,
           "audience": "customer" if n.type == "listing" else p.get("audience", "customer"),
           "source": p.get("source") or "typed", "quote": p.get("quote"),
           "version": p.get("version", 1), "valid_until": p.get("valid_until"), "applies_to": p.get("applies_to"),
           "review_by": (rb.isoformat() if (rb := review_by(n)) else None), "stale": stale(n),
           "usable": usable(n), "record": g.record(n.id), "retired": p.get("retired"), "at": n.at,
           "used": (used or {}).get(n.id, {"week": 0, "total": 0, "last_chat": None})}
    if n.type == "listing":
        out["text"] = f"{p['beds']} bed {p['type']} in {p['community']} · " + (f"AED {p['price_aed']:,}" if p.get("price_aed") is not None else f"{p.get('currency') or ''} {p.get('price') or 'price not set'}".strip())
        out["listing"] = {"ref": p["ref"], "community": p["community"], "beds": p["beds"], "type": p["type"], "price_aed": p["price_aed"],
                          "permit": p.get("permit"), "advertised": advertised(n), "agent": p.get("agent"), "agent_name": name(p.get("agent")) if p.get("agent") else None,
                          "photo": (p.get("photos") or [None])[0] or p.get("photo"), "offering": p.get("offering"),
                          "listing_status": p.get("status_before", n.status) if n.status == "retired" else n.status,
                          "portal_pending": p.get("portal_pending") or {},
                          "photos": p.get("photos") or ([p["photo"]] if p.get("photo") else []),
                          "lat": p.get("lat"), "lng": p.get("lng"), "description": p.get("description"), "size_sqft": p.get("size_sqft"),
                          "completion": p.get("completion"), "project": p.get("project"),
                          "country": p.get("country"), "page": p.get("page"), "source": p.get("source"), "price": p.get("price"), "currency": p.get("currency")}
    else:
        out["text"] = p.get("text", "")
    return out


# ---------- search: the header box and the agents' lookup ----------

WORD = re.compile(r"[a-z؀-ۿ0-9]+")
STOP = {"the", "and", "you", "your", "what", "when", "where", "which", "does", "for", "with", "this", "that", "are", "was", "has",
        "have", "about", "from", "will", "there", "any", "how", "can", "please", "tell", "much", "is", "do", "a", "an", "of", "to", "in"}
NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def _words(s: str) -> set[str]:
    return {w for w in WORD.findall(s.lower()) if w not in STOP and (len(w) > 1 or w.isdigit())}


RENT = r"\b(rent|renting|rental|lease|to let|yearly|per year|tenant)\b|إيجار|استئجار"
BUY = r"\b(buy|buying|purchase|invest|investment)\b|شراء|أشتري"
FOR = {"buyer": "sale", "tenant": "rent"}  # a qualified customer type says which listings fit


def wants(text: str) -> dict:
    """What a question says about a listing: beds, budget (AED), a reference, and for sale or for rent."""
    low, out = text.lower(), {}
    rent, buy = bool(re.search(RENT, low)), bool(re.search(BUY, low))
    if rent != buy:
        out["offering"] = "rent" if rent else "sale"
    if m := re.search(r"\b(\d|one|two|three|four|five|six)\s*-?\s*(bed|br|bedroom)", low):
        out["beds"] = int(NUM.get(m.group(1), m.group(1)))
    elif re.search(r"\bstudio\b", low):
        out["beds"] = 0
    if m := re.search(r"(?:under|below|up to|max(?:imum)?|budget(?: of| is)?|within)\s*(?:aed\s*)?([\d.,]+)\s*(m|million|k|thousand)?", low):
        v = float(m.group(1).replace(",", ""))
        out["budget"] = int(v * {"m": 1e6, "million": 1e6, "k": 1e3, "thousand": 1e3}.get(m.group(2) or "", 1) if v < 1e5 or m.group(2) else v)
    if m := re.search(r"\b([a-z]{1,4}-?\d{2,6})\b", low):
        out["ref"] = m.group(1)
    return out


ALIASES = {"palm jumeirah": ["the palm"], "dubai creek harbour": ["creek harbour"], "arabian ranches": ["the ranches"]}


def _phrases(community: str) -> set[str]:
    """How a customer names a community: the full name, without "Dubai", and its initials (JVC, JBR, JLT)."""
    c = community.lower().strip()
    out = {c, re.sub(r"^dubai |\s+dubai$", "", c)} | set(ALIASES.get(c, []))
    parts = c.split()
    if len(parts) >= 3:
        out.add("".join(w[0] for w in parts))
    return {x for x in out if x and x != "dubai"}


def areas_in(g: Graph, text: str) -> set[str]:
    """The communities a question names, as whole phrases: "villa in JVC" names Jumeirah Village Circle, not "The Villa";
    "Palm Jumeirah" is not JBR or JLT just because they share "Jumeirah"."""
    low = " " + " ".join(WORD.findall(text.lower())) + " "
    names = {n.props["community"] for n in g.of("listing")} | {n.props.get("title", "") for n in g.of("knowledge") if tab(n) == "area"}
    return {c.lower() for c in names if c and any(f" {ph} " in low for ph in _phrases(c))}


def _score(g: Graph, n: Node, words: set[str], want: dict, areas: set[str]) -> float:
    p = n.props
    if n.type == "listing":
        if want.get("ref") and want["ref"].replace("-", "") == p["ref"].lower().replace("-", ""):
            return 100
        if "beds" in want and p["beds"] != want["beds"]:
            return 0
        if "budget" in want and p["price_aed"] > want["budget"]:
            return 0
        if want.get("offering") and p.get("offering") and p["offering"] != want["offering"]:
            return 0
        comm = _words(p["community"])
        if areas and p["community"].lower() not in areas:
            return 0
        s = len(words & (_words(p.get("title", "")) | comm | {p["ref"].lower()} | _words(p.get("type", ""))))
        s += 2 * ("beds" in want) + 2 * ("budget" in want) + 3 * bool(areas)
        return s
    title, text = _words(p.get("title", "")), _words(p.get("text", ""))
    return 2 * len(words & title) + len(words & text)


def search(g: Graph, text: str, *, k: int = 8, for_customer: bool = True, tabs: set[str] | None = None,
           include_retired: bool = False, used: dict | None = None, offering: str | None = None) -> list[dict]:
    """The best `k` items for a question, best first, in `item()` format.

    for_customer=True (the agents): confirmed, customer-facing, in-date knowledge and advertised listings only. Listings
    must fit the beds, budget and area the question names; everything else is matched word by word. An empty list means
    nothing fits: hand the chat to a person.
    for_customer=False (the header search): every item, any status, matched on any word of its title or text.
    offering ("sale" or "rent"): only listings on that offering, e.g. from the customer type; the question's own words win."""
    words, want = _words(text), wants(text)
    if offering and "offering" not in want:
        want["offering"] = offering
    areas = areas_in(g, text)
    hits = []
    for n in g.nodes.values():
        if n.type not in ("knowledge", "listing") or (tabs and tab(n) not in tabs):
            continue
        if for_customer and not usable(n):
            continue
        if not for_customer and n.status == "retired" and not include_retired:
            continue
        if n.type == "listing" and not for_customer and not want.get("ref"):
            s = len(words & (_words(n.props.get("title", "")) | _words(n.props["community"]) | _words(n.props["ref"])))
        else:
            s = _score(g, n, words, want, areas if n.type == "listing" else set())
        if s > 0:
            hits.append((s, n.event, n))
    hits.sort(key=lambda x: (-x[0], -x[1]))
    return [item(g, n, used) | {"score": s} for s, _, n in hits[:k]]


# ---------- changes: every one is an event ----------

class NotAllowed(Exception):
    pass


def add(office, kind: str, title: str, text: str, *, by: str, audience: str = "customer", review_by: str | None = None,
        valid_until: str | None = None, applies_to: str | None = None, source: str | None = None, quote: str | None = None) -> dict:
    """The kind's owner adds a confirmed item; anyone else's waits as proposed."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    g = office.graph()
    kid = f"K{len(g.of('knowledge')) + 1}"
    confirmed = by in KINDS[kind][1]
    office.log.append("knowledge.added", actor=by, content={
        "id": kid, "kind": kind, "title": title, "text": text, "confirmed": confirmed, "source": source or "typed",
        "audience": audience, "review_by": review_by or None, "valid_until": valid_until or None, "applies_to": applies_to or None,
        "quote": quote})
    return {"id": kid, "status": "confirmed" if confirmed else "proposed"}


def propose_answer(office, question: str, answer: str, *, by: str, chat: str | None = None) -> dict:
    """A broker answered what Rania could not: their reply becomes a proposed approved answer for the sales manager."""
    return add(office, "answer", question.strip()[:120], answer.strip(), by=by, source=f"chat:{chat}" if chat else "chat", quote=answer.strip())


def _node(g: Graph, iid: str) -> Node:
    n = g.nodes.get(iid)
    if not n or n.type not in ("knowledge", "listing"):
        raise KeyError(iid)
    return n


def edit(office, iid: str, changes: dict, *, by: str, why: str = "") -> dict:
    """The owner's edit is a new version at once; anyone else's is a proposal. A listing's price is never edited by a broker."""
    g = office.graph()
    n = _node(g, iid)
    changes = {k: v for k, v in changes.items() if k in FIELDS and v != n.props.get(k)}
    if not changes:
        return {"id": iid, "changed": False}
    if not may_edit(n, by):
        pid = f"P{len(g.of('proposal')) + 1}"
        office.log.append("change.proposed", actor=by, content={"id": pid, "item": iid, "changes": changes, "why": why,
                                                                "owners": sorted(owners(n))})
        return {"id": iid, "proposal": pid, "waits_for": [name(o) for o in sorted(owners(n))]}
    e = office.log.append("item.edited", actor=by, content={"id": iid, "changes": changes, "why": why, "version": n.props.get("version", 1) + 1})
    return {"id": iid, "version": e["content"]["version"]}


def decide(office, pid: str, *, accept: bool, by: str, why: str = "") -> dict:
    g = office.graph()
    p = g.nodes.get(pid)
    if not p or p.type != "proposal" or p.status != "open":
        raise KeyError(pid)
    n = _node(g, p.props["item"])
    if not may_edit(n, by):
        raise NotAllowed(f"Only {', '.join(name(o) for o in sorted(owners(n)))} can decide this")
    e = office.log.append("change.decided", actor=by, content={"id": pid, "accepted": accept, "why": why})
    if accept:
        office.log.append("item.edited", actor=by, caused_by=e["id"], content={
            "id": n.id, "changes": p.props["changes"], "why": p.props.get("why") or f"accepted {pid} from {name(p.props['by'])}",
            "version": n.props.get("version", 1) + 1, "proposal": pid, "proposed_by": p.props["by"]})
    return {"id": pid, "accepted": accept}


def retire(office, iid: str, *, by: str, why: str) -> dict:
    n = _node(office.graph(), iid)
    if not may_edit(n, by):
        raise NotAllowed(f"Only {', '.join(name(o) for o in sorted(owners(n)))} can retire this")
    if not why.strip():
        raise ValueError("Say why it is retired")
    office.log.append("item.retired", actor=by, content={"id": iid, "why": why.strip()})
    return {"id": iid, "status": "retired"}


def restore(office, iid: str, *, by: str) -> dict:
    n = _node(office.graph(), iid)
    if not may_edit(n, by):
        raise NotAllowed(f"Only {', '.join(name(o) for o in sorted(owners(n)))} can restore this")
    office.log.append("item.restored", actor=by, content={"id": iid})
    return {"id": iid}


def reconfirm(office, iid: str, *, by: str) -> dict:
    n = _node(office.graph(), iid)
    if not may_edit(n, by):
        raise NotAllowed(f"Only {', '.join(name(o) for o in sorted(owners(n)))} can re-confirm this")
    office.log.append("item.reconfirmed", actor=by, content={"id": iid})
    return {"id": iid}


def apply(g: Graph, e: dict) -> None:
    """Fold one item event into the graph (called by graph.build)."""
    t, c = e["type"], e["content"]
    if t == "change.proposed":
        p = g.add(c["id"], "proposal", f"change to {c['item']}", e, status="open", props=dict(c) | {"by": e["actor"], "at": e["at"]})
        g.link(p.id, "changes", c["item"], e)
        return
    if t == "change.decided" and c["id"] in g.nodes:
        g.nodes[c["id"]].status = "accepted" if c["accepted"] else "rejected"
        g.nodes[c["id"]].props.update(decided_by=e["actor"], decided_why=c.get("why"))
        return
    n = g.nodes.get(c.get("id"))
    if not n:
        return
    if t == "item.edited":
        v = n.props.get("version", 1)
        old = {k: n.props.get(k) for k in FIELDS if k in n.props or k in c["changes"]}
        prev = g.add(f"{n.id}~v{v}", "version", f"{n.props.get('title', n.label)} v{v}", e, status="replaced",
                     props=old | {"of": n.id, "version": v, "by": n.props.get("edited_by") or e["actor"], "at": n.props.get("edited_at") or n.at,
                                  "type": n.type, "replaced_why": c.get("why")})
        g.link(n.id, "replaces", prev.id, e)
        n.props.update(c["changes"], version=c["version"], edited_by=e["actor"], edited_at=e["at"], reviewed_at=e["at"], why=c.get("why"))
        if "title" in c["changes"]:
            n.label = c["changes"]["title"]
        if n.type == "listing" and "status" in c["changes"]:
            n.status = c["changes"]["status"]
    elif t == "item.retired":
        n.props.update(status_before=n.status, retired={"why": c["why"], "by": e["actor"], "at": e["at"]})
        n.status = "retired"
    elif t == "item.restored" and n.status == "retired":
        n.status = n.props.pop("status_before", "confirmed")
        n.props["retired"] = None
    elif t == "item.reconfirmed":
        n.props["reviewed_at"] = e["at"]
        if n.props.get("review_by"):  # a date a person set moves on by the kind's period (90 days when it has none)
            n.props["review_by"] = None
            n.props["review_by"] = ((review_by(n) or _day(e["at"]) + timedelta(days=90))).isoformat()


def history(office, iid: str) -> list[dict]:
    """Every change to one item, oldest first: who, when, what and why."""
    out = []
    for e in office.log.list():
        c = e["content"]
        if e["type"] == "knowledge.added" and c.get("id") == iid or e["type"] == "listing.added" and f"listing:{c.get('ref')}" == iid:
            what = f"added ({c.get('source') or 'typed'})" if not out else "updated by the feed"
            out.append({"at": e["at"], "by": name(e["actor"]) if e["actor"] in PEOPLE else e["actor"], "what": what,
                        "text": c.get("text") or (f"AED {c['price_aed']:,}" if c.get("price_aed") else "")})
        elif e["type"] == "knowledge.confirmed" and c.get("id") == iid:
            out.append({"at": e["at"], "by": name(e["actor"]), "what": "confirmed"})
        elif e["type"].startswith("item.") and c.get("id") == iid:
            what = {"item.edited": f"version {c.get('version')}", "item.retired": "retired", "item.restored": "restored",
                    "item.reconfirmed": "re-confirmed"}[e["type"]]
            text = "; ".join(f"{k}: {f'AED {v:,}' if k == 'price_aed' else v}" for k, v in c.get("changes", {}).items())
            out.append({"at": e["at"], "by": name(e["actor"]), "what": what, "text": text, "why": c.get("why")})
        elif e["type"] == "change.proposed" and c.get("item") == iid:
            out.append({"at": e["at"], "by": name(e["actor"]), "what": f"proposed {c['id']}",
                        "text": "; ".join(f"{k}: {v}" for k, v in c["changes"].items()), "why": c.get("why")})
        elif e["type"] == "change.decided" and any(o["what"] == f"proposed {c['id']}" for o in out):
            out.append({"at": e["at"], "by": name(e["actor"]), "what": f"{'accepted' if c['accepted'] else 'rejected'} {c['id']}", "why": c.get("why")})
    return out


def area_of(g: Graph, n: Node) -> list[Node]:
    """A listing's area guides (and items that apply to it); an area guide's listings."""
    if n.type == "listing":
        comm = n.props["community"].lower()
        return [k for k in g.of("knowledge") if k.status != "retired" and (
            (tab(k) == "area" and k.props.get("title", "").lower() in comm) or k.props.get("applies_to") in (n.id, n.props["community"]))]
    if tab(n) == "area":
        t = n.props.get("title", "").lower()
        return [x for x in g.of("listing") if t and t in x.props["community"].lower()]
    return []
