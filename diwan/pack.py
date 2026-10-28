"""The one shape every agent hands up, model-driven or rules-driven: what it concluded, the exact words that support
it, what is missing, what should happen next, and the actions it proposes. Quotes are checked word for word against
the sources the agent was given; a quote that is not there is removed and recorded, never shown as evidence.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from diwan.events import now

RULES_VERSION = "uae-brokerage-2026.10.1"


@dataclass
class Evidence:
    quote: str
    source: str  # the id of the input it came from, e.g. "meeting:M1"


@dataclass
class Action:
    kind: str     # from ACTIONS
    summary: str


@dataclass
class Pack:
    request: str
    agent: str
    verdict: str
    evidence: list[Evidence] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    next: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    as_of: str = field(default_factory=now)
    rules: str = RULES_VERSION
    rejected_quotes: list[Evidence] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# Every action an agent may propose. Authority over each comes from its charter, and anything not listed is refused.
ACTIONS = {
    "record_fact": "Record a fact from what was said",
    "ask_question": "Ask a person a question",
    "draft": "Draft a document or message",
    "assign": "Hand work to another agent",
    "route": "Pass a request to a lead",
    "brief": "Brief a person",
    "screen": "Screen a name against official lists",
    "fill_form": "Type into a portal form",
    "send_back": "Send a draft back with the reason",
    "expect_payment": "Create or withdraw an expected payment",
    "hold": "Hold an item for a person",
    "publish": "Publish or schedule a post",
    "use_script": "Use a script for filming (spends filming, editing and model time)",
    "send": "Send a message to a customer or third party",
    "reply": "Reply to a customer's enquiry from listings and company knowledge",
    "book_viewing": "Book a viewing in a broker's free slot",
    "approve": "Approve work",
    "submit": "Submit a portal form",
    "release_money": "Release or move money",
    "file_report": "File a regulatory report",
    "decide_suspicion": "Decide whether something is suspicious",
}

PACK_SCHEMA = {
    "name": "agent_pack", "strict": True,
    "schema": {
        "type": "object", "additionalProperties": False,
        "required": ["verdict", "evidence", "missing", "next", "actions"],
        "properties": {
            "verdict": {"type": "string"},
            "evidence": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["quote", "source"],
                                                     "properties": {"quote": {"type": "string"}, "source": {"type": "string"}}}},
            "missing": {"type": "array", "items": {"type": "string"}},
            "next": {"type": "array", "items": {"type": "string"}},
            "actions": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["kind", "summary"],
                                                    "properties": {"kind": {"type": "string", "enum": sorted(ACTIONS)},
                                                                   "summary": {"type": "string"}}}},
        },
    },
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().casefold()


def check_evidence(pack: Pack, sources: dict[str, str]) -> Pack:
    """Keep only quotes that appear word for word in the source they cite."""
    keep, drop = [], []
    for e in pack.evidence:
        text = sources.get(e.source)
        (keep if text is not None and e.quote.strip() and norm(e.quote) in norm(text) else drop).append(e)
    pack.evidence, pack.rejected_quotes = keep, pack.rejected_quotes + drop
    return pack


def from_model(request: str, agent: str, data: dict) -> Pack:
    return Pack(request=request, agent=agent, verdict=data["verdict"],
                evidence=[Evidence(**e) for e in data.get("evidence", [])], missing=list(data.get("missing", [])),
                next=list(data.get("next", [])), actions=[Action(**a) for a in data.get("actions", [])])
