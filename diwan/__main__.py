"""python -m diwan check        what is plugged in, what is missing, where each agent will run (no secrets shown)
python -m diwan check --ping one tiny live call per configured provider
python -m diwan roster       the agents as JSON, for screens
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


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check("--ping" in sys.argv)
    elif cmd == "roster":
        print(json.dumps([asdict(c) for c in ROSTER], ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)
