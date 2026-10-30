"""Our own ad account's results, read-only, from Meta's Marketing API: each ad's status and its last 30 days (spend,
reach, impressions, clicks, leads). Nothing here creates, changes or pauses an ad. Competitors' ad results are not
available from any API (see the studio's "Their ads").

Settings: META_AD_ACCOUNT_ID (with or without the "act_" prefix) and META_ADS_TOKEN (a token with ads_read).
"""
from __future__ import annotations

import httpx

from diwan.config import env, offline

GRAPH = "https://graph.facebook.com/v21.0"
TRANSPORT: httpx.BaseTransport | None = None  # tests swap in a fake
FIELDS = "spend,reach,impressions,clicks,ctr,cpc,actions"


class AdsError(RuntimeError):
    pass


def account() -> str:
    a = (env("META_AD_ACCOUNT_ID") or "").strip()
    return a if not a or a.startswith("act_") else f"act_{a}"


def missing() -> list[str]:
    return [k for k, v in (("META_AD_ACCOUNT_ID", account()), ("META_ADS_TOKEN", env("META_ADS_TOKEN"))) if not v]


def ready() -> bool:
    return not missing() and not offline()


def _get(path: str, params: dict) -> dict:
    if not ready():
        raise AdsError("needs " + (", ".join(missing()) or "online mode"))
    with httpx.Client(transport=TRANSPORT, timeout=30) as c:
        r = c.get(f"{GRAPH}/{path}", params={**params, "access_token": env("META_ADS_TOKEN")})
    data = r.json() if r.headers.get("content-type", "").startswith(("application/json", "text/javascript")) else {}
    if r.status_code >= 300 or "error" in data:
        raise AdsError((data.get("error") or {}).get("message") or f"Meta returned {r.status_code}")
    return data


def _leads(actions: list[dict] | None) -> int | None:
    if actions is None:
        return None  # the ad did not run in the period: no number, not zero
    return sum(int(float(a.get("value") or 0)) for a in actions or [] if a.get("action_type") in ("lead", "onsite_conversion.lead_grouped", "leadgen_grouped"))


def _row(ins: dict) -> dict:
    num = lambda k, f=float: f(ins[k]) if ins.get(k) not in (None, "") else None  # noqa: E731
    return {"spend": num("spend"), "reach": num("reach", int), "impressions": num("impressions", int), "clicks": num("clicks", int),
            "ctr": num("ctr"), "cpc": num("cpc"), "leads": _leads(ins.get("actions"))}


def report(days: str = "last_30d") -> dict:
    """{account, name, currency, total, ads:[{id, name, status, ...numbers}]}. An ad that has not run has no numbers."""
    acc = _get(account(), {"fields": "name,currency,account_status"})
    total = (_get(f"{account()}/insights", {"fields": FIELDS, "date_preset": days}).get("data") or [{}])[0]
    ads = _get(f"{account()}/ads", {"fields": f"name,effective_status,created_time,insights.date_preset({days}){{{FIELDS}}}", "limit": 50}).get("data", [])
    rows = []
    for a in ads:
        ins = ((a.get("insights") or {}).get("data") or [{}])[0]
        rows.append({"id": a["id"], "name": a.get("name"), "status": (a.get("effective_status") or "").lower().replace("_", " "),
                     "created": (a.get("created_time") or "")[:10], **_row(ins)})
    return {"account": account(), "name": acc.get("name"), "currency": acc.get("currency"), "period": days, "total": _row(total), "ads": rows}
