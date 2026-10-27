"""The content studio's walkthrough: one listing goes from research to a post waiting for the owner's approval.

What can be computed here is real: the listing and its permit, the permit check, the lane count, the schedule rule,
and the comment that comes back is answered by Rania for real. What needs the Meta key (web research, transcripts of
other people's videos, generated covers) is sample work, and every such pack says so (`usage.sample`). With the key,
those steps are replaced by Muse Spark search, Voice Transcribe and Muse Image calls.
"""
from __future__ import annotations

import asyncio

from diwan.agents import reception, runner
from diwan.agents.charters import get
from diwan.office import Office
from diwan.pack import Action, Pack

PAUSE = 1.1


def _pack(office: Office, agent: str, verdict: str, *, cause: int | None, kind: str | None = "draft", sample: bool = False,
          next_: list[str] | None = None, req: str = "studio") -> int:
    res = runner.submit(office.log, get(agent), Pack(req, agent, verdict, next=next_ or [], actions=[Action(kind, verdict)] if kind else []),
                        sources={}, caused_by=cause, usage={"sample": sample} if sample else {})
    return res.event["id"]


def steps(office: Office, ref: str = "MC-1204"):
    """The walkthrough as a list of callables, each returning the event id the next one is caused by."""
    g = office.graph()
    lst = g.nodes[f"listing:{ref}"].props
    price = f"AED {lst['price_aed']:,}"
    permit = lst.get("permit")
    title = lst["title"]
    lanes = {"listing": 2, "area guide": 1, "market update": 0, "behind the scenes": 1, "client story": 0}
    low = min(lanes, key=lanes.get)
    st: dict = {}

    def start():
        st["c"] = _pack(office, "mkt", f"New reel for {title} ({ref}): permit {permit} on file, starting research.", cause=None, kind="assign")
        return st["c"]

    def trend():
        st["t"] = _pack(office, "mtrend", "Rising in Dubai property: walk-throughs that reveal the price at the end.", cause=st["c"], sample=True)
        return st["t"]

    def rival():
        st["r"] = _pack(office, "mrival", "Outlier: a competitor's Marina sunset tour at 4.2x their usual views.", cause=st["c"], sample=True)
        return st["r"]

    def transcript():
        return _pack(office, "mtrans", "Hook in that video: \"Guess what this view costs.\" Beats: view, rooms, price, call.", cause=st["r"], sample=True)

    def board():
        st["b"] = _pack(office, "research", "Board: 3 cards pinned, each with its source.", cause=st["t"], kind="assign")
        return st["b"]

    def idea():
        st["i"] = _pack(office, "midea", f"Idea: \"Sunset at {title}: what {price} buys in Dubai Marina\" (from {ref} and the trend card).", cause=st["b"])
        return st["i"]

    def lane():
        return _pack(office, "mlane", f"This week: {', '.join(f'{v} {k}' for k, v in lanes.items())}. Add a {low}.", cause=st["i"])

    def film():
        st["f"] = _pack(office, "mfilm", "Film list for Omar: balcony at 5:30 PM, kitchen pan, master bedroom, view reveal last.", cause=st["i"])
        return st["f"]

    def script():
        st["s"] = _pack(office, "mscript", f"Hook A: \"What does {price} buy in Dubai Marina?\" · Hook B: \"ماذا تشتري {lst['price_aed'] / 1e6:.1f} مليون درهم في دبي مارينا؟\"",
                        cause=st["f"])
        return st["s"]

    def check():
        return _pack(office, "mcheck", "Script checked against the brand rules: no promised returns, price matches the listing.", cause=st["s"])

    def captions():
        st["cap"] = _pack(office, "mcap", "Captions in English and Arabic: 14 lines, timed to the cut.", cause=st["s"], sample=True)
        return st["cap"]

    def writer():
        return _pack(office, "mwriter", f"Post text: \"{title}, 2 bed, sea view. {price}. Permit {permit}.\" Same in Arabic.", cause=st["cap"])

    def thumb():
        return _pack(office, "mthumb", "Two cover options: balcony at sunset, and the view with the price.", cause=st["cap"], sample=True)

    def permit_check():
        ok = bool(permit)
        st["p"] = _pack(office, "mpermit", f"{'Pass' if ok else 'Held'}: permit {permit or 'missing'}, price matches {ref}, no banned promises.",
                        cause=st["cap"], kind=None if ok else "hold")
        return st["p"]

    def schedule():
        return _pack(office, "msched", "Scheduled for Thursday 7:30 PM: evenings bring most enquiries.", cause=st["p"])

    def cross():
        return _pack(office, "mcross", "Versions ready for Instagram, TikTok, YouTube Shorts and Property Finder.", cause=st["p"])

    def publish():
        st["pub"] = _pack(office, "mpub", f"Publish the {ref} reel on Thursday 7:30 PM.", cause=st["p"], kind="publish")
        return st["pub"]

    def comment():
        r = reception.message(office, "971509990001", f"PRICE for the Marina one? Saw your reel ({ref})", name_="Comment · @competitor_four")
        return None if not r else st["pub"]

    return [start, trend, rival, transcript, board, idea, lane, film, script, check, captions, writer, thumb, permit_check,
            schedule, cross, publish, comment]


async def run(office: Office, ref: str = "MC-1204", pause: float = PAUSE) -> None:
    for step in steps(office, ref):
        step()
        await asyncio.sleep(pause)


def run_now(office: Office, ref: str = "MC-1204") -> None:
    for step in steps(office, ref):
        step()
