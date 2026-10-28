"""What each department's core remembers, for the brain you click on its floor. Every item is a record from the log
(with its id, so it opens in the memory graph); a section with nothing in it says so instead of showing a sample.
"""
from __future__ import annotations

import re

from diwan.agents.charters import get
from diwan.graph import Graph
from diwan.office import Office

DEPTS = {"mkt", "sales", "records", "review", "ops", "fin", "comp", "front"}


def dept_of(agent: str) -> str | None:
    c = get(agent)
    while c:
        if c.id in DEPTS:
            return c.id
        if c.id == "nova":
            return "front"
        c = get(c.parent) if c.parent else None
    return None


def _items(g: Graph, nodes, sub=None, limit: int = 12) -> list[dict]:
    return [{"ref": n.id, "text": g.record(n.id).split(" · ", 1)[-1], "sub": sub(n) if sub else None} for n in list(nodes)[-limit:]]


def _section(title: str, note: str, items: list[dict], empty: str) -> dict:
    return {"title": title, "note": note, "items": items, "empty": empty}


def lessons(g: Graph, dept: str) -> dict:
    ls = [n for n in g.of("lesson", status="active") if dept_of(n.props["agent"]) == dept]
    return _section("Lessons people taught", "Every one goes into that agent's instructions; \"never\" lessons are enforced in code.",
                    [{"ref": n.id, "text": n.props["rule"], "sub": f"{get(n.props['agent']).name} · taught by {n.props.get('by')}"} for n in ls],
                    "None yet. Teach one on the Team page.")


def brain(office: Office, dept: str) -> dict:
    g = office.graph()
    if dept == "mkt":
        from diwan.agents import strategy, studio
        evs = [e["content"] for e in office.log.list() if e["type"] == "content.made"]
        approved = [s for s in (studio.approved_script(office, n.props["ref"]) for n in g.of("listing")) if s]
        plays = [c for c in evs if c["kind"] == "playbook"]
        st = strategy.report(office)
        comp = studio.competitors(g)
        known = [n for n in g.of("knowledge", status="confirmed")]
        from diwan import brand
        bp = brand.profile(office)
        prof = [{"ref": None, "text": f"{brand.FIELDS[k][0]}: {v['value']}", "sub": f"set by {v['by']} · {(v['at'] or '')[:10]}" + (f" · {v['via']}" if v.get("via") else "")}
                for k, v in bp.items() if v["value"]]
        return {"title": "Brand brain", "about": "What the marketing team writes from: the brand, what works for us, what people taught it.", "sections": [
            _section("Brand profile", "Read by " + ", ".join(brand.USED_BY) + " on every idea, script and post. Owned by the Marketing manager.",
                     prof, "Not set: writers are told to write plainly and invent no slogan. Set it in the Studio (Brand)."),
            _section("Company knowledge", "Confirmed facts about the office (hours, fees, who we are). Rania quotes them; the brand draft starts from them.", _items(g, known), "Nothing confirmed yet. Add it on the Knowledge page."),
            lessons(g, "mkt"),
            _section("Script library", "Scripts a person approved for filming.",
                     [{"ref": s["id"], "text": s["hook_en"], "sub": f"{s['ref']} · {s.get('angle', 'price-reveal')} · {s.get('via')}"} for s in approved],
                     "No approved script yet."),
            _section("Playbook", "Structures that worked on our own posts, with the posts that prove it.",
                     [{"ref": p["id"], "text": p.get("structure") or p.get("text") or "entry", "sub": None} for p in plays],
                     "Empty until we have 5 or more posts of our own to learn from."),
            _section("What to post next", "Each angle on our own posts against our median.",
                     [{"ref": None, "text": f"{a['angle']}: {a['status']}", "sub": a["why"]} for a in st["angles"]], ""),
            _section("Who we compete with", "Accounts a person set; their posts are scored against their own usual.",
                     [{"ref": None, "text": "@" + c, "sub": None} for c in comp], "None set. Add them in the Studio."),
            _section("Listings we can advertise", "Only listings with a permit number.",
                     _items(g, [n for n in g.of("listing") if n.props.get("permit")]), "No permitted listing."),
        ]}
    facts = g.of("fact")
    live = [n for n in facts if n.status == "live"]
    replaced = [n for n in facts if n.status == "superseded"]
    work = [n for n in g.of("task", status="queued") if dept_of(n.props.get("agent") or "nova") == dept]
    common = [_section("Open work", "Tasks this department's agents are holding.", _items(g, work), "Nothing open."), lessons(g, dept)]
    if dept == "sales":
        secs = [_section("Deal memory: live facts", "Each one is a customer's exact words, with the meeting it came from.", _items(g, live), "Nothing heard yet."),
                _section("Replaced statements", "Kept, never deleted; anything built on them is withdrawn.", _items(g, replaced), "None.")]
    elif dept == "records":
        secs = [_section("Archive", "Filed documents.", _items(g, g.of("document")), "Nothing filed."),
                _section("Sales ledger", "Closed sales; every figure the analyst gives is counted from these.", _items(g, g.of("sale")), "No sales.")]
    elif dept == "review":
        secs = [_section("Live facts", "What review checks every draft against.", _items(g, live), "None."),
                _section("Replaced", "A draft citing one of these is sent back.", _items(g, replaced), "None.")]
    elif dept == "comp":
        secs = [_section("Checks raised", "Compliance hears every payment change first; it never decides suspicion.", _items(g, g.of("check")), "None raised."),
                _section("Payment facts", "What was said about who pays and how.",
                         _items(g, [n for n in live if n.props.get("kind") in ("payer", "payment_promise", "income_claim")]), "None.")]
    elif dept == "fin":
        secs = [_section("Ledger: expected payments", "Each rests on the exact words it came from.",
                         _items(g, [n for n in live if n.props.get("kind") in ("payment_promise", "payer", "price")]), "None.")]
    elif dept == "ops":
        secs = [_section("Deals in progress", "Form F is filled from live facts only and stops before Submit.", _items(g, g.of("deal")), "No deals.")]
    else:
        secs = [_section("Lobby board", "Jobs Nova handed to people, with read-back and deadlines.", _items(g, g.of("lobby")), "Empty."),
                _section("Company knowledge", "Confirmed by a person.", _items(g, g.of("knowledge", status="confirmed")), "None.")]
    names = {"sales": "Deal memory", "records": "Archive", "review": "Live facts", "comp": "Rule book", "fin": "Ledger", "ops": "Portal", "front": "Lobby board"}
    return {"title": names.get(dept, "Memory"), "about": "What this department remembers, straight from the office's log.", "sections": secs + common}


def marketing_graph(office: Office, upto: int | None = None) -> dict:
    """The marketing team's memory as a graph, rebuilt from the log up to an event (so it can be rewound like the deals):
    the brand profile and what it was drafted from, listings, research cards, ideas, scripts and their angles, who
    picked or sent back each script, the post text, and the lessons the writers follow."""
    from diwan import brand as brandmod
    from diwan.agents import strategy
    evs = [e for e in office.log.list() if upto is None or e["id"] <= upto]
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(i, t, record, status="live", label=None):
        nodes.setdefault(i, {"id": i, "type": t, "status": status, "record": record, "label": label})
        return nodes[i]

    short = lambda text, n=26: text if len(text) <= n else text[:n - 1].rstrip() + "…"  # noqa: E731

    def edge(a, b, rel):
        if a in nodes and b in nodes and a != b:
            edges.append({"src": a, "dst": b, "rel": rel})

    brand_fields, scripts, latest_idea, requests = {}, {}, {}, {}
    for e in evs:
        t, c = e["type"], e["content"]
        if t == "listing.added":
            node(f"listing:{c['ref']}", "listing", f"{c['ref']} · {c['title']}, {c['community']} · AED {c['price_aed']:,} · features: "
                 f"{', '.join(c.get('features') or []) or 'none'} · permit {c.get('permit') or 'MISSING'}")
        elif t == "knowledge.added":
            node(c["id"], "knowledge", f"{c['id']} · {c['title']}: {c['text']}" + (f" · from {c['source']}" if c.get("source") else ""),
                 status="confirmed" if c.get("confirmed", True) else "proposed", label=short(c["title"]))
            if (c.get("source") or "").startswith("http"):
                dom = re.sub(r"^www\.", "", c["source"].split("/")[2])
                node(f"source:{dom}", "source", f"public pages on {dom}", label=dom)
                edge(c["id"], f"source:{dom}", "from")
            elif c.get("source"):  # a document a person gave the office
                node(f"source:{c['source']}", "source", f"document: {c['source']}", label="📄 " + short(c["source"], 22))
                edge(c["id"], f"source:{c['source']}", "from")
        elif t == "knowledge.confirmed" and c.get("id") in nodes:
            nodes[c["id"]]["status"] = "confirmed"
            nodes[c["id"]]["record"] += f" · confirmed by {e['actor']}"
        elif t == "setting.changed" and c.get("person") == "brand" and c.get("key") in brandmod.FIELDS:
            brand_fields[c["key"]] = (c.get("value") or "", e["actor"], e["at"][:10], c.get("via"))
            node("brand:profile", "brand", "Brand profile · read by " + ", ".join(brandmod.USED_BY), label="BRAND")
        elif t == "setting.changed" and c.get("person") == "studio" and c.get("key") == "competitors":
            for name in [x.strip().lstrip("@") for x in (c.get("value") or "").split(",") if x.strip()]:
                node(f"competitor:{name}", "competitor", f"@{name} · a competitor the team watches")
        elif t == "board.pinned":
            node(c["id"], c.get("kind", "card"), f"{c['id']} · {c['kind']}: {c['title']} · {c.get('why', '')} · {c.get('url', '')}", label=short(c["title"]))
            if c.get("account"):
                node(f"competitor:{c['account']}", "competitor", f"@{c['account']} · a competitor the team watches")
                edge(c["id"], f"competitor:{c['account']}", "posted_by")
        elif t == "lesson.added":
            node(c["id"], "lesson", f"{c['id']} · {c['rule']} (taught to {c['agent']} by {e['actor']})")
        elif t == "lesson.removed" and c.get("id") in nodes:
            nodes[c["id"]]["status"] = "withdrawn"
        elif t == "content.made" and c["kind"] == "ideas":
            i = c["id"]
            node(i, "idea", f"{i} · idea for {c['ref']}: {c['pick']['title']} ({c.get('via')})", label="💡 " + short(c["pick"]["title"]))
            edge(i, f"listing:{c['ref']}", "for")
            for card in c["pick"].get("cards", []):
                edge(i, card, "builds_on")
            latest_idea[c["ref"]] = i
        elif t == "content.made" and c["kind"] == "script":
            i = c["id"]
            scripts[i] = c
            node(i, "script", f"{i} · {c.get('angle', 'price-reveal')} script for {c['ref']} ({c.get('via')}): \"{c['hook_en']}\" · "
                 + " / ".join(c.get("lines_en", [])), status="drafted", label=f"{i} {short(c['hook_en'], 22)}")
            edge(i, f"listing:{c['ref']}", "for")
            if c["ref"] in latest_idea:
                edge(i, latest_idea[c["ref"]], "from_idea")
            if brand_fields:
                edge(i, "brand:profile", "follows")
            if c.get("revises"):
                edge(i, c["revises"], "revises")
                if c["revises"] in nodes:
                    nodes[c["revises"]]["status"] = "superseded"
            a = c.get("angle")
            if a:
                node(f"angle:{a}", "angle", f"angle · {a}: {strategy.ANGLES.get(a, ('',))[0]}")
                edge(i, f"angle:{a}", "angle")
        elif t == "content.made" and c["kind"] == "post text":
            node(c["id"], "post", f"{c['id']} · post text for {c['ref']}: {c['text'][:300]}")
            edge(c["id"], f"listing:{c['ref']}", "for")
        elif t == "approval.requested" and c.get("kind") == "use_script":
            requests[f"R{e['id']}"] = c.get("summary", "")
            for sid in re.findall(r"script (C\d+)", c.get("summary", "")):
                if sid in nodes and nodes[sid]["status"] == "drafted":
                    nodes[sid]["status"] = "offered"
        elif t == "decision.made" and c.get("card") in requests:
            who = e["actor"]
            node(f"person:{who}", "person", f"{who}")
            offered = re.findall(r"script (C\d+)", requests[c["card"]])
            pick = c.get("choice") or (offered[0] if offered else None)
            if c.get("answer") == "approve" and pick in nodes:
                nodes[pick]["status"] = "approved"
                edge(f"person:{who}", pick, "picked")
            elif c.get("answer") in ("reject", "revise"):
                for sid in ([pick] if c.get("answer") == "revise" else offered):
                    if sid in nodes:
                        edge(f"person:{who}", sid, "sent_back")
    if brand_fields:
        for k, (v, by, at, via) in brand_fields.items():
            if v:
                node(f"brand:{k}", "brand", f"{brandmod.FIELDS[k][0]}: {v} · set by {by} on {at}{' · ' + via if via else ''}", label=brandmod.FIELDS[k][0])
                edge(f"brand:{k}", "brand:profile", "part_of")
                node(f"person:{by}", "person", by)
                edge(f"person:{by}", f"brand:{k}", "set")
        for n in [n for n in nodes.values() if n["type"] == "knowledge" and n["status"] == "confirmed"]:
            edge(n["id"], "brand:profile", "informs")  # only what a person confirmed shapes the brand
        for n in [n for n in nodes.values() if n["type"] == "lesson" and n["status"] != "withdrawn"]:
            edge(n["id"], "brand:profile", "rule_for_writers")
    return {"nodes": list(nodes.values()), "edges": edges, "last_event": evs[-1]["id"] if evs else 0}
