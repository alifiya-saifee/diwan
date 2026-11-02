"""Marketing as plain lines for a PA to read: what the studio is working on and what each post brought, with the leads by name."""
from __future__ import annotations

from diwan.office import Office


def lines(office: Office) -> list[str]:
    from diwan.agents import journey, marketing, reader, rhythm
    out = []
    try:
        out += [f"Marketing waiting for a person: {p['text']}" for p in marketing.waiting(office)[:8]]
        nxt = journey.report(office)["next"]
        out += [f"Marketing's next post: {nxt['title']} ({nxt['label']}): {nxt['why']}."] if nxt else ["Marketing's next post: nothing first in line, the plan decides."]
        days = [d for d in (rhythm.current(office) or {}).get("days", []) if d.get("ref")][:10]
        out += ["Marketing's plan: " + "; ".join(f"{d['date']} {journey.title_of(office, d['ref'])}" for d in days)] if days else ["Marketing's plan: nothing planned yet."]
        for a in reader.patterns(office)["accounts"]:
            out += [f"Our competitor research, @{a['account']}: {f['finding']}" for f in a["patterns"]]
        out += [f"Marketing stopped: {s['title']}: {s['why']}" for s in marketing.plan_view(office)["stopped"][:5]]
        v = marketing.overview(office)
        out.append("Marketing pieces by stage: " + ", ".join(f"{s['label']} {s['n']}" for s in v["stages"] if s["n"]))
        g = office.graph()
        names: dict[str, list[str]] = {}
        for a in marketing._attributions(office):
            if n := g.nodes.get(f"deal:{a['deal']}"):
                names.setdefault(a["ref"] or a.get("post") or "unknown post", []).append(n.props.get("customer") or a["deal"])
        for r in v["results"][:10]:
            who = ", ".join(names.get(r["ref"], [])[:12]) or "none"
            out.append(f"Marketing result: {r['title']}: {r['leads']} leads ({who}), {r['qualified']} qualified, {r['viewings']} viewings, {r['deals']} deals, "
                       f"commission AED {r['commission_aed']:,}, likes {r['likes']}, comments {r['comments']}, reach {r['reach']}.")
        out.append(f"Marketing ad budget this month: AED {v['cap']['committed']:,} committed of {v['cap']['cap']:,}.")
    except Exception as e:  # noqa: BLE001  the PA can still talk about everything else
        out.append(f"Marketing: not available ({type(e).__name__})")
    return out
