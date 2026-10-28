"""What the models cost, and a cap so they cannot cost more than the owner allows.

Every live model call is written to a ledger (usage.jsonl, next to the .env): the agent, the provider, the tokens and
an estimated price. A request answered from the cache is written too, with the cost it saved. Before a live call,
`allowed()` checks this month's spend against DIWAN_BUDGET_USD (default 25); once it is reached, agents fall back to
rules and templates and the screens say why, rather than spending past the cap.

Prices are estimates per million tokens (input, output) and say so on screen. NVIDIA's free endpoint costs nothing.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from diwan import config

PRICES = {  # USD per 1M tokens: (input, output). Estimates; set DIWAN_PRICE_<PROVIDER>="in,out" to correct one.
    "meta": (0.50, 1.50), "baseten": (0.30, 0.90), "fireworks": (0.30, 0.90), "modal": (0.30, 0.90), "nvidia": (0.0, 0.0),
}


def _file():
    return config.ROOT / "usage.jsonl"


def price(provider: str) -> tuple[float, float]:
    custom = config.env(f"DIWAN_PRICE_{provider.upper()}")
    if custom:
        a, _, b = custom.partition(",")
        return float(a), float(b or a)
    return PRICES.get(provider, (1.0, 3.0))


def estimate(provider: str, input_tokens: int | None, output_tokens: int | None) -> float:
    i, o = price(provider)
    return round(((input_tokens or 0) * i + (output_tokens or 0) * o) / 1_000_000, 6)


def budget() -> float:
    return float(config.env("DIWAN_BUDGET_USD", "25"))


def record(agent: str, usage: dict, *, cached: bool = False) -> None:
    src = usage.get("recorded_from") if cached else usage.get("provider")
    cost = estimate(src or "", usage.get("input_tokens"), usage.get("output_tokens")) if src else 0.0
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "agent": agent, "provider": src,
           "model": usage.get("model"), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
           "cached": cached, "cost_usd": 0.0 if cached else cost, "saved_usd": cost if cached else 0.0}
    try:
        with _file().open("a") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass  # the ledger never stops the work


def rows() -> list[dict]:
    f = _file()
    if not f.exists():
        return []
    out = []
    for line in f.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def month_spend(now: datetime | None = None) -> float:
    m = (now or datetime.now(timezone.utc)).strftime("%Y-%m")
    return round(sum(r["cost_usd"] for r in rows() if r["at"].startswith(m)), 6)


def allowed() -> bool:
    return month_spend() < budget()


def summary(now: datetime | None = None) -> dict:
    m = (now or datetime.now(timezone.utc)).strftime("%Y-%m")
    this = [r for r in rows() if r["at"].startswith(m)]
    by_agent: dict[str, dict] = {}
    for r in this:
        a = by_agent.setdefault(r["agent"], {"agent": r["agent"], "calls": 0, "cached": 0, "tokens": 0, "cost_usd": 0.0, "saved_usd": 0.0})
        a["calls"] += 1
        a["cached"] += r["cached"]
        a["tokens"] += (r.get("input_tokens") or 0) + (r.get("output_tokens") or 0)
        a["cost_usd"] = round(a["cost_usd"] + r["cost_usd"], 6)
        a["saved_usd"] = round(a["saved_usd"] + r["saved_usd"], 6)
    spend = round(sum(r["cost_usd"] for r in this), 6)
    return {"month": m, "budget_usd": budget(), "spend_usd": spend, "left_usd": round(max(budget() - spend, 0), 6),
            "saved_usd": round(sum(r["saved_usd"] for r in this), 6), "calls": len(this),
            "cached_calls": sum(r["cached"] for r in this), "over": spend >= budget(),
            "by_agent": sorted(by_agent.values(), key=lambda a: -a["cost_usd"]), "estimate": True}
