"""python -m diwan check        what is plugged in, what is missing, where each agent will run (no secrets shown)
python -m diwan check --ping one tiny live call per configured provider
python -m diwan roster       the agents as JSON, for screens
python -m diwan eval         score every agent on labelled cases (add --model to use the connected model)
python -m diwan nova         talk to Nova in the fictional demo office (ask, instruct, or "brief <person>")
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict

from diwan.agents.charters import ROSTER
from diwan.agents.runner import provider_for
from diwan.config import offline, tape_mode
from diwan.providers import tape
from diwan.providers.chat import PROVIDERS, ProviderError

PING = {"name": "ping", "strict": True, "schema": {"type": "object", "additionalProperties": False,
                                                   "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}}


def check(ping: bool) -> None:
    print(f"mode: {'offline (tapes only)' if offline() else 'online'} · tapes: {tape_mode()}\n")
    for p in PROVIDERS.values():
        state = "ready" if p.available() else "missing " + ", ".join(p.missing()) if p.missing() else "offline"
        line = f"  {p.label:34} {state}"
        if ping and p.available():
            try:
                r = p.complete_json("Reply with JSON.", 'Return {"ok": true}.', PING, timeout=30)
                line += f" · ping {r.usage['latency_ms']} ms"
            except ProviderError as e:
                line += f" · ping FAILED: {str(e)[:120]}"
        print(line)
    print()
    for c in ROSTER:
        if c.runs_on in ("spark", "open"):
            p = provider_for(c)
            where = p.label if p else "no live model"
        else:
            where = c.runs_on
        n = len(list((tape.DIR / c.id).glob("*.json"))) if (tape.DIR / c.id).exists() else 0
        flag = "" if c.hack else "  (not in the hackathon set)"
        print(f"  {c.name:24} {c.runs_on:8} -> {where}{f' · {n} tapes' if n else ''}{flag}")


def talk() -> None:
    from diwan import demo
    from diwan.agents import nova
    from diwan.events import EventLog
    from diwan.office import Office
    o = Office(EventLog())
    demo.seed(o)
    demo.correction(o)
    print("Demo office: Karim just said \"Actually, forget my brother. I'll pay it all myself.\"")
    print('Ask a question, give an instruction ("prepare Form F for Karim"), or type "brief ahmed". Ctrl-D to stop.\n')
    while True:
        try:
            line = input("you> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line.lower().startswith("brief"):
            r = nova.brief(o, (line.split()[1:] or ["layla"])[0])
        elif line.endswith("?"):
            r = nova.ask(o, line)
        else:
            r = nova.route(o, line)
        print(f"nova> {r['text']}")
        if r.get("options"):
            print("      options: " + " | ".join(r["options"]))
        if r.get("cites"):
            print("      records: " + ", ".join(r["cites"]))
        print()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check("--ping" in sys.argv)
    elif cmd == "eval":
        from diwan import evals
        res = evals.run(model="--model" in sys.argv)
        for name, st in res["suites"].items():
            print(f"{name:30} {st['passed']:>3}/{st['total']:<3} ({st['seconds']}s)")
            for c in st["cases"]:
                if not c["pass"]:
                    print(f"    FAIL  {c['case'][:70]}  ·  {c['why']}")
        print(f"\n{'TOTAL':30} {res['passed']:>3}/{res['total']}  ({res['mode']})")
    elif cmd == "nova":
        talk()
    elif cmd == "roster":
        print(json.dumps([asdict(c) for c in ROSTER], ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)
