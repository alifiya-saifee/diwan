"""The Visit summarizer (docs/visit-summary-spec.md): after a site visit or meeting, from the recording (the client's turns)
or the broker's notes, a short summary the follow-up is built on: how keen they seemed, what they liked, what worried
them, any change of budget, and the next step. Each point carries the words it came from; a point whose words are not in
the recording or the notes is dropped, so nothing is guessed. Muse Spark writes it when connected; plain rules otherwise.
"""
from __future__ import annotations

import re

from diwan.office import Office

INTEREST = {"keen": "Keen", "thinking": "Thinking it over", "not_for_them": "Not for them"}
SCHEMA = {"name": "visit", "schema": {"type": "object", "additionalProperties": False,
                                      "required": ["interest", "interest_quote", "liked", "worries", "budget_quote", "next_step", "next_quote"],
                                      "properties": {"interest": {"type": "string", "enum": list(INTEREST) + ["unknown"]},
                                                     "interest_quote": {"type": ["string", "null"]},
                                                     "liked": {"type": "array", "items": {"type": "string"}},
                                                     "worries": {"type": "array", "items": {"type": "string"}},
                                                     "budget_quote": {"type": ["string", "null"]},
                                                     "next_step": {"type": ["string", "null"]}, "next_quote": {"type": ["string", "null"]}}}}
LIKE = r"\b(love|loved|like|liked|great|nice|beautiful|perfect|amazing|lovely|stunning|bright|spacious)\b|يعجبني|حلو|جميل"
WORRY = (r"\b(small|tiny|too|far|expensive|noisy|noise|dark|old|worried|concern\w*|problem|issue|but|traffic|cramped)\b"
         r"|صغير|غالي|بعيد")
KEEN = r"\b(make an offer|put in an offer|let'?s do it|we'?ll take it|go ahead|ready to (buy|sign|book)|reserve it|book it)\b"
THINK = r"\b(think about|thinking|talk to|discuss with|sleep on it|let me (check|think)|get back to you|my (wife|husband|family|partner))\b"
NOT = r"\b(not for (us|me)|don'?t like|didn'?t like|not what we|not interested|no,? thanks|too far for us)\b"
NEXT = r"\b(offer|second viewing|see it again|come back|send me|call me|talk to|think about|get back|next week|tomorrow)\b"


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?؟])\s+|\n+|;\s*|,\s+(?=but\b)", text) if len(s.strip()) > 2]


def _in(quote: str | None, said: str) -> bool:
    from diwan.pack import norm
    return bool(quote) and norm(quote) in norm(said)


def rules(said: str) -> dict:
    """Plain rules: sort the client's sentences into liked, worries, interest and next step."""
    ss = _sentences(said)
    low = [s.lower() for s in ss]
    # a worry keeps the client's exact words, without a leading "but" or "and"
    worries = [re.sub(r"^(but|and|although|though|however|only)\b,?\s*", "", s, flags=re.I) for s, lw in zip(ss, low)
               if re.search(WORRY, lw) and not re.search(NOT, lw)]
    liked = [s for s, lw in zip(ss, low) if re.search(LIKE, lw) and not re.search(WORRY, lw) and not re.search(NOT, lw)]
    interest, iq = "unknown", None
    for key, rx in (("not_for_them", NOT), ("keen", KEEN), ("thinking", THINK)):
        if hit := next((s for s, lw in zip(ss, low) if re.search(rx, lw)), None):
            interest, iq = key, hit
            break
    nxt = next((s for s, lw in zip(ss, low) if re.search(NEXT, lw)), None)
    from diwan.agents import scribe
    budget = next((s for s in ss if scribe.amounts(s) and re.search(r"\b(budget|stretch|max|maximum|up to|afford|go to)\b", s.lower())), None)
    return {"interest": interest, "interest_quote": iq, "liked": liked[:3], "worries": worries[:3], "budget_quote": budget,
            "next_step": nxt, "next_quote": nxt}


def summarize(office: Office, deal: str, *, said: str, source: str, appointment: str | None = None, meeting: str | None = None,
              by: str = "visit", cause: int | None = None) -> dict | None:
    """Summarize what the client said (`source`: "recording" or "notes") and keep it on the deal. None when nothing was said."""
    from diwan.agents import runner
    from diwan.agents.charters import get
    said = (said or "").strip()
    if not said:
        return None
    out, by_model = rules(said), False
    c = get("visit")
    system = runner.instructions(c, office.log, pack=False) + (
        "\n\nRead what the client said at a property visit (or the broker's notes about it) and fill the `visit` format. "
        "interest: keen (they want to go ahead), thinking (they need time or someone else's view), not_for_them, or unknown. "
        "Every quote must be copied word for word from the text; liked and worries are short quotes from it. Leave out "
        "anything the text does not say. Never mention compliance, checks or source of funds.")
    user = runner.user_message("What was said:", {"said": said})
    try:
        if runner.has_model(c, system, user, schema=SCHEMA):
            m = runner.call(c, system, user, schema=SCHEMA, timeout=runner.LIVE).data
            keep = lambda q: q if _in(q, said) else None  # noqa: E731  a quote not in the text is dropped
            out = {"interest": m["interest"] if m["interest"] in INTEREST and keep(m.get("interest_quote")) else "unknown",
                   "interest_quote": keep(m.get("interest_quote")), "liked": [q for q in m["liked"] if _in(q, said)][:3],
                   "worries": [q for q in m["worries"] if _in(q, said)][:3], "budget_quote": keep(m.get("budget_quote")),
                   "next_step": m.get("next_step") if keep(m.get("next_quote")) else None, "next_quote": keep(m.get("next_quote"))}
            by_model = True
    except Exception as e:  # the broker still gets the rules summary
        office.log.append("agent.failed", actor="visit", agent="visit", deal=deal, caused_by=cause, content={"error": str(e)[:300]})
    ev = office.log.append("visit.summarized", actor=by, agent="visit", deal=deal, caused_by=cause,
                           content=out | {"source": source, "appointment": appointment, "meeting": meeting, "by_model": by_model})
    return out | {"id": ev["id"], "source": source, "by_model": by_model}


def latest(g, deal: str | None) -> dict | None:
    return g.nodes[f"deal:{deal}"].props.get("visit") if deal and f"deal:{deal}" in g.nodes else None


def from_meeting(office: Office, mid: str, *, cause: int | None = None) -> dict | None:
    """A recorded visit ended: summarize the client's own turns (not the broker's)."""
    m = office.meeting(mid)
    said = "\n".join(t["text"] for t in m["turns"] if t.get("label") in ("customer", "speaker_1"))
    g = office.graph()
    appt = next((v.id for v in sorted(g.of("viewing"), key=lambda v: v.props["at"], reverse=True) if v.deal == m["deal"]), None)
    return summarize(office, m["deal"], said=said, source="recording", meeting=mid, appointment=appt, cause=cause)
