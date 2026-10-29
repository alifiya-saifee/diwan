"""Labelled test cases for every working agent, scored. `python -m diwan eval` (rules) or `python -m diwan eval --model`
(whatever model is connected; slow on free endpoints). Results go to evals/results.json for the write-up.

A case passes only if every expectation holds; the reason for each failure is kept.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime
from pathlib import Path

from diwan import demo, slots
from diwan.events import EventLog
from diwan.office import Office

NOW = datetime(2026, 10, 27, 23, 40, tzinfo=slots.DUBAI)
TODAY = date(2026, 10, 27)
OUT = Path(__file__).resolve().parents[1] / "evals"


def _office(full: bool = True, corrected: bool = False) -> Office:
    o = Office(EventLog())
    (demo.seed if full else demo.company)(o)
    if corrected:
        demo.correction(o)
    return o


# ---------- Scribe: facts from what was said ----------

SCRIBE = [
    (["We're looking at two point six million for the Marina unit."], {"kind": "deal_term", "amount_aed": 2_600_000}),
    (["My budget is around 1.8 million."], {"kind": "deal_term", "amount_aed": 1_800_000}),
    (["I earn about forty-five thousand a month."], {"kind": "income_claim", "monthly_income_aed": 45_000}),
    (["I make 600k a year."], {"kind": "income_claim", "monthly_income_aed": 50_000}),
    (["My brother Tariq will send the deposit."], {"kind": "payer", "payer": "Tariq"}),
    (["I'll pay it myself."], {"kind": "payer", "payer": "Karim Haddad"}),
    (["Two hundred sixty thousand deposit by bank transfer next week."], {"kind": "payment_promise", "amount_aed": 260_000, "method": "bank transfer", "due": "next week"}),
    (["Fifty thousand in cash as the booking deposit."], {"kind": "payment_promise", "amount_aed": 50_000, "method": "cash"}),
    (["If the view is better maybe we go to three million."], {"kind": "deal_term", "stance": "hypothetical"}),
    (["Hello, nice to meet you."], {"none": True}),
    (["Can you send me the floor plan?"], {"none": True}),
    (["My brother Tariq will send the deposit.", "Actually, forget my brother. I'll pay it all myself."], {"kind": "payer", "payer": "Karim Haddad", "replaces_kind": "payer"}),
]


def eval_scribe() -> list[dict]:
    from diwan.agents import scribe
    out = []
    for lines, want in SCRIBE:
        o = Office(EventLog())
        o.open_deal("d", property="Unit 1204, Marina Crest", customer="Karim Haddad", broker="omar")
        o.start_meeting("d", "M1", title="t")
        o.give_consent("M1", by="Karim Haddad")
        r = None
        for ln in lines:
            r = scribe.turn(o, "M1", "customer", ln)
        g = o.graph()
        facts = [g.nodes[f] for f in r["facts"]]
        fails = []
        if want.get("none"):
            if facts:
                fails.append(f"heard {len(facts)} fact(s) where there were none")
        elif not facts:
            fails.append("heard nothing")
        else:
            f = next((x for x in facts if x.props["kind"] == want["kind"]), None)
            if not f:
                fails.append(f"no {want['kind']} fact (got {[x.props['kind'] for x in facts]})")
            else:
                for k, v in want.items():
                    if k in ("kind", "replaces_kind"):
                        continue
                    got = f.props.get(k)
                    if (got if not isinstance(v, str) else (got or "")) != v:
                        fails.append(f"{k}: wanted {v!r}, got {got!r}")
                if want.get("replaces_kind") and not any(g.nodes[x].props["kind"] == want["replaces_kind"] for x in f.props.get("replaces") or []):
                    fails.append("did not link the correction to the earlier statement")
        out.append({"case": " / ".join(lines), "pass": not fails, "why": "; ".join(fails), "by": r["by"]})
    return out


# ---------- Rania: the receptionist ----------

RANIA = [
    (["Hi"], {"contains": "I'm Rania"}),
    (["Hi", "2 bed in the Marina around 2.7 million"], {"refs": "listing:MC-1204"}),
    (["Hi", "Any villa in JVC?"], {"refs": "listing:JVC-88"}),
    (["Hi", "Any 1 bed in Downtown?"], {"not_contains": "DT-2210", "handover": True}),
    (["Hi", "What are your fees?"], {"refs": "K3"}),
    (["Hi", "Do you accept cash?"], {"handover": True, "not_contains": "complian"}),
    (["Hi", "Can I pay in crypto?"], {"handover": True}),
    (["Hi", "Can you give me a discount?"], {"handover": True}),
    (["Hi", "What ROI is guaranteed?"], {"contains": "can't promise returns"}),
    (["Hi", "I want to speak to an agent"], {"handover": True}),
    (["Hi", "Can I see MC-1204 Saturday at 4pm?"], {"booked": True}),
    (["Hi", "What time do you open?"], {"contains": "10am to 7pm"}),
]


def eval_rania() -> list[dict]:
    from diwan.agents import reception
    out = []
    for i, (msgs, want) in enumerate(RANIA):
        o = _office(full=False)
        r = None
        for m in msgs:
            r = reception.message(o, f"97150000{i:04d}", m, name_="Test Buyer", now=NOW)
        text = r.get("reply") or r.get("suggestion") or ""
        fails = []
        if "contains" in want and want["contains"].lower() not in text.lower():
            fails.append(f"reply lacks {want['contains']!r}")
        if "not_contains" in want and want["not_contains"].lower() in text.lower():
            fails.append(f"reply contains {want['not_contains']!r}")
        if "refs" in want and want["refs"] not in r.get("refs", []):
            fails.append(f"did not cite {want['refs']} (cited {r.get('refs')})")
        if want.get("handover") and r.get("mode") != "human":
            fails.append("did not hand over to a person")
        if want.get("booked") and not o.graph().of("viewing", status="booked"):
            fails.append("no viewing booked")
        out.append({"case": " → ".join(msgs), "pass": not fails, "why": "; ".join(fails), "reply": text[:160], "by": r.get("by")})
    return out


# ---------- Nova: the front desk ----------

NOVA = [
    ("Who is paying for Karim?", {"contains": "I'll pay it all myself", "cites": "F7"}),
    ("What changed on the Marina deal?", {"cites": "A1"}),
    ("Who pays the deposit?", {"kind": "question"}),
    ("What is the seller's name on the Marina unit?", {"kind": "unknown"}),
    ("What were last month's sales?", {"contains": "AED 7,850,000"}),
    ("What did we spend in September?", {"contains": "AED 42,680"}),
    ("How were sales?", {"kind": "question"}),
    ("Find the contract for the JVC villa", {"contains": "MOU (Form F), Villa 31"}),
    ("Is Karim a good customer?", {"contains": "don't judge"}),
    ("Who is Tariq?", {"contains": "brother"}),
    ("Which listing is the most expensive?", {"contains": "Unit 1204"}),
    ("Prepare Form F for the Marina unit", {"kind": "done"}),
    ("Submit Form F for Karim", {"kind": "refused", "contains": "Joseph"}),
    ("Tell Karim his file was flagged by compliance", {"kind": "refused"}),
    ("Approve the deposit", {"kind": "refused"}),
    ("Tell Priya I need the Karim review ready by this evening", {"kind": "confirm", "contains": "6:00 PM"}),
    ("Rania, never mention the transfer fee", {"kind": "confirm"}),
    ("Hi Nova, how are you?", {"contains": "Nothing needs you"}),
]


def eval_nova() -> list[dict]:
    from diwan.agents import nova
    out = []
    for q, want in NOVA:
        o = _office(corrected=True)
        r = nova.converse(o, q, "layla", session=f"eval-{hash(q)}", now=NOW.replace(hour=10))
        fails = []
        if "kind" in want and r.get("kind") != want["kind"]:
            fails.append(f"kind {r.get('kind')!r}, wanted {want['kind']!r}")
        if "contains" in want and want["contains"].lower() not in (r.get("text") or "").lower():
            fails.append(f"answer lacks {want['contains']!r}")
        if "cites" in want and want["cites"] not in (r.get("cites") or []):
            fails.append(f"did not cite {want['cites']}")
        out.append({"case": q, "pass": not fails, "why": "; ".join(fails), "reply": (r.get("text") or "")[:160], "by": r.get("by")})
    return out


# ---------- correction engine and Lobby ----------

def eval_engine() -> list[dict]:
    from diwan.agents import lobby
    out = []
    o = _office()
    demo.correction(o)
    g = o.graph()
    checks = [("compliance hears first", [e["type"] for e in o.log.list()].index("check.raised") < [e["type"] for e in o.log.list()].index("fact.superseded")),
              ("only dependent tasks withdrawn", {t.id for t in g.of("task", status="withdrawn")} == {"T2", "T3"}),
              ("new expectation from the new payer", any("Karim Haddad" in t.props["action"] for t in g.of("task", status="queued"))),
              ("stale approval refused", not o.execute("A1", "k")["ok"]),
              ("deck sent back", g.nodes["D1"].status == "sent_back")]
    out += [{"case": c, "pass": bool(ok), "why": "" if ok else "failed"} for c, ok in checks]
    for words, when in [("by this evening", "2026-10-27T18:00"), ("by tomorrow at 10am", "2026-10-28T10:00"), ("by Thursday 3pm", "2026-10-29T15:00"),
                        ("by noon", "2026-10-27T12:00"), ("by 4pm", "2026-10-27T16:00")]:
        d = lobby.due_from(f"send it {words}", NOW.replace(hour=9))[0]
        ok = bool(d) and d.isoformat().startswith(when)
        out.append({"case": f"Lobby deadline '{words}'", "pass": ok, "why": "" if ok else f"got {d}"})
    return out


# ---------- Data analyst and Archivist ----------

def eval_records() -> list[dict]:
    from diwan.agents import records
    g = _office().graph()
    cases = [("What were last month's sales?", "3 closed, AED 7,850,000 in value, AED 157,000 commission"),
             ("How much commission did we make this year?", "AED 339,400"), ("What did we spend last month?", "AED 42,680"),
             ("Who is the top broker in Q3?", "Omar AED 317,000"), ("What's in the pipeline?", "2 open deals worth AED 4,500,000")]
    out = []
    for q, want in cases:
        text, refs, _ = records.analyse(g, q, TODAY)
        out.append({"case": q, "pass": want in text and bool(refs), "why": "" if want in text else f"got {text[:120]}"})
    text, refs, missing = records.analyse(g, "How were sales?", TODAY)
    out.append({"case": "No period → asks which", "pass": not text and bool(missing), "why": ""})
    for q, want in [("Show me the invoices for October", "Office rent, October"), ("Find the contract for the JVC villa", "Villa 31"), ("Any receipts for July?", "no receipts")]:
        text, _, _ = records.find_documents(g, q, TODAY)
        out.append({"case": q, "pass": want.lower() in text.lower(), "why": "" if want.lower() in text.lower() else f"got {text[:120]}"})
    return out


# ---------- the studio ----------

POSTS = [("competitor", "rival.one", 12000, f"https://instagram.com/p/a{i}", "REELS" if i < 2 else "IMAGE",
          "What does 2M buy in Dubai Marina? DM us" if i < 2 else "New listing in our portfolio with many features and long text " * 3,
          900 if i < 2 else 100, 10, "2026-10-20 19:30" if i < 2 else "2026-10-21 11:00") for i in range(8)] + \
        [("competitor", "rival.two", 5000, f"https://instagram.com/p/b{i}", "IMAGE", "Office day #a #b #c #d #e", 300 if i == 0 else 40, 5, "2026-10-19 10:00") for i in range(6)]


def eval_studio() -> list[dict]:
    from diwan.agents import analysis, studio
    out = []
    o = _office()
    rows = [dict(zip(studio.CSV_COLUMNS, map(str, p))) for p in POSTS]
    r = studio.import_posts(o, rows, by="eval")
    found = {b["post"] for b in studio.board(o)}
    want = {"https://instagram.com/p/a0", "https://instagram.com/p/a1", "https://instagram.com/p/b0"}
    out.append({"case": "Competitor watch finds every outlier (2x the account's median)", "pass": found == want, "why": "" if found == want else f"found {sorted(found)}"})
    out.append({"case": "No false outliers", "pass": r["outliers"] == 3, "why": f"{r['outliers']} outliers"})
    a = analysis.report(o)
    k = next(x for x in a["competitors"] if x["account"] == "rival.one")["kpis"]
    out.append({"case": "KPIs: engagement rate per follower", "pass": k["engagement_rate"] == round(100 * (910 * 2 + 110 * 6) / 8 / 12000, 2), "why": str(k.get("engagement_rate"))})
    out.append({"case": "KPIs: best hour from post times", "pass": k["best_hour"] == 19, "why": str(k.get("best_hour"))})
    feats = {w["feature"] for w in a["why"]}
    for f in ("open with a question", "are reels or videos", "were posted in the evening (6 to 11 PM Dubai)"):
        out.append({"case": f"Finding measured: outliers {f}", "pass": f in feats, "why": "" if f in feats else f"findings: {sorted(feats)}"})
    out.append({"case": "Every finding links example posts", "pass": all(w["examples"] for w in a["why"]), "why": ""})
    studio.run_now(o, "MC-1204")
    out.append({"case": "Nothing costly before a person approves the script",
                "pass": not studio.made(o, "film list", "MC-1204") and any(n.props.get("kind") == "use_script" for n in o.graph().of("request", status="open")), "why": ""})
    studio.approve_script_now(o, "MC-1204")
    out.append({"case": "Approved script → film list goes to the broker", "pass": any("Film MC-1204" in t.props["action"] for t in o.graph().of("task")), "why": ""})
    text = studio.made(o, "post text", "MC-1204")
    out.append({"case": "Post text carries the permit number", "pass": "SAMPLE-71204" in text["text"], "why": ""})
    for t, ok_expected, label in [(text["text"], True, "real post passes"), (text["text"].replace("SAMPLE-71204", ""), False, "missing permit is held"),
                                  (text["text"] + " Now AED 2,300,000!", False, "price not on the listing is held"),
                                  (text["text"] + " Guaranteed returns.", False, "banned promise is held")]:
        passed = studio.permit_check(o, "MC-1204", {"text": t}, None)
        out.append({"case": f"Permit checker: {label}", "pass": passed == ok_expected, "why": "" if passed == ok_expected else "wrong verdict"})
    o2 = _office()
    studio.run_now(o2, "DT-2210")
    out.append({"case": "No permit, no reel", "pass": not studio.made(o2, "script", "DT-2210"), "why": ""})
    out.append({"case": "Missing connections are named, never faked",
                "pass": not any(e["content"].get("usage", {}).get("sample") for e in o.log.list() if e["type"] == "agent.pack"), "why": ""})
    return out


SUITES = {"Scribe": eval_scribe, "Rania": eval_rania, "Nova": eval_nova, "Correction engine and Lobby": eval_engine,
          "Data analyst and Archivist": eval_records, "Studio": eval_studio}


def run(model: bool = False) -> dict:
    if not model:
        os.environ["DIWAN_OFFLINE"] = "1"
        os.environ["DIWAN_LOCAL_ASR"] = "0"
    os.environ["DIWAN_TAPE"] = "record" if model else "off"  # measure the model or the rules, never a cached answer
    res = {"at": datetime.now().isoformat(timespec="seconds"), "mode": "model" if model else "rules", "suites": {}}
    for name, fn in SUITES.items():
        t0 = time.monotonic()
        cases = fn()
        res["suites"][name] = {"passed": sum(c["pass"] for c in cases), "total": len(cases), "seconds": round(time.monotonic() - t0, 1), "cases": cases}
    res["passed"] = sum(s["passed"] for s in res["suites"].values())
    res["total"] = sum(s["total"] for s in res["suites"].values())
    OUT.mkdir(exist_ok=True)
    (OUT / f"results-{res['mode']}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    return res
