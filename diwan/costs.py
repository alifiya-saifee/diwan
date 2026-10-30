"""What the models cost, and a cap so they cannot cost more than the owner allows.

Every live model call is written to a ledger (usage.jsonl, next to the .env): the agent, the provider, the tokens and
an estimated price. A request answered from the cache is written too, with the cost it saved. Before a live call,
`allowed(agent)` checks this month's spend against the cap of the agent's part of the office: Marketing has
DIWAN_BUDGET_MARKETING_USD (default 80% of the total: 20), the rest of the office what is left of DIWAN_BUDGET_USD
(default 25, so 5).
Once a part's cap is reached, its agents fall back to rules and templates and the screens say why; the other part
keeps working.

Prices are estimates per million tokens (input, output) and say so on screen. NVIDIA's free endpoint costs nothing.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from diwan import config

PRICES = {  # USD per 1M tokens: (input, output). Estimates; set DIWAN_PRICE_<PROVIDER>="in,out" to correct one.
    "meta": (1.25, 4.25),  # Muse Spark list price as reported Oct 2026; confirm on Meta's Models page
    "baseten": (0.30, 0.90), "fireworks": (0.30, 0.90), "modal": (0.30, 0.90), "nvidia": (0.0, 0.0),
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


def part_of(agent: str | None) -> str:
    """"marketing" for an agent under the Marketing lead (or one of the studio's own ids), else "rest"."""
    from diwan.agents.charters import get
    c = get(agent) if agent else None
    while c:
        if c.id == "mkt":
            return "marketing"
        c = get(c.parent) if c.parent else None
    return "rest"


def budget(part: str | None = None) -> float:
    """The monthly cap: the whole office's, or one part's (Marketing's own cap; the rest gets what is left)."""
    total = float(config.env("DIWAN_BUDGET_USD", "25"))
    if part is None:
        return total
    set_ = config.env("DIWAN_BUDGET_MARKETING_USD")  # unset: Marketing gets 80% of the total (20 of the default 25)
    marketing = min(float(set_), total) if set_ else total * 0.8
    return marketing if part == "marketing" else total - marketing


def fee(name: str, default: float) -> float:
    """A per-use price for Meta's other services (web search, an image, a minute of audio). Estimates; set DIWAN_PRICE_META_<NAME>."""
    return float(config.env(f"DIWAN_PRICE_META_{name.upper()}", str(default)))


def record(agent: str, usage: dict, *, cached: bool = False, extra_usd: float = 0.0, what: str | None = None) -> None:
    src = usage.get("recorded_from") if cached else usage.get("provider")
    cost = (estimate(src or "", usage.get("input_tokens"), usage.get("output_tokens")) if src else 0.0) + extra_usd
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "agent": agent, "provider": src,
           "model": usage.get("model"), "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "reasoning_tokens": usage.get("reasoning_tokens"),
           "cached": cached, "cost_usd": 0.0 if cached else round(cost, 6), "saved_usd": round(cost, 6) if cached else 0.0, "what": what or "chat"}
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


def month_spend(now: datetime | None = None, part: str | None = None) -> float:
    m = (now or datetime.now(timezone.utc)).strftime("%Y-%m")
    return round(sum(r["cost_usd"] for r in rows() if r["at"].startswith(m) and (part is None or part_of(r["agent"]) == part)), 6)


def allowed(agent: str | None = None) -> bool:
    """Whether a live call may run: the whole office is under its cap and, for an agent, so is its part."""
    if month_spend() >= budget():
        return False
    return agent is None or month_spend(part=part_of(agent)) < budget(part_of(agent))


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
    parts = {}
    for part in ("marketing", "rest"):
        s = round(sum(r["cost_usd"] for r in this if part_of(r["agent"]) == part), 6)
        parts[part] = {"budget_usd": round(budget(part), 6), "spend_usd": s, "left_usd": round(max(budget(part) - s, 0), 6), "over": s >= budget(part)}
    return {"month": m, "budget_usd": budget(), "spend_usd": spend, "left_usd": round(max(budget() - spend, 0), 6), "parts": parts,
            "saved_usd": round(sum(r["saved_usd"] for r in this), 6), "calls": len(this),
            "cached_calls": sum(r["cached"] for r in this), "over": spend >= budget(),
            "by_agent": sorted(by_agent.values(), key=lambda a: -a["cost_usd"]), "estimate": True}
