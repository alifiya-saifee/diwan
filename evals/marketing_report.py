"""The scoreboard of the Marketing real-user test, written only from the run's own results (e2e/marketing_real_user.py):
every case with its pass rule, both verdicts, the blind score, the evidence, and the manual steps per flow.

    .venv/bin/python evals/marketing_report.py <out dir>/results.json docs/marketing-real-user-test.md [before.json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROUNDS = {"R0": "Setup", "R1": "Competitors", "R2": "The Marketing lead: questions", "R2H": "The Marketing lead: hard questions",
          "R3": "A listing reel, end to end", "R4": "Occasions and the logo", "R5": "An informational video", "R6": "The plan",
          "R7": "Learning the user's taste", "R8": "Results and campaigns", "R9": "Facts change", "R10": "The 3D floor",
          "R11": "Every page, desktop and phone", "R14": "Platforms"}


def mark(c: dict) -> str:
    if c.get("works") is None:
        return "Not run"
    if c.get("works") and c.get("sense") is not False:
        return "Pass"
    return "Works, but weak" if c.get("works") else "Fail"


def score(c: dict) -> str:
    s = c.get("score")
    if isinstance(s, dict):
        return ", ".join(f"{k} {v}" for k, v in s.items() if v is not None)
    return "" if s is None else str(s)


def main(src: str, dst: str, before: str | None = None):
    d = json.loads(Path(src).read_text())
    old = {(c["round"], c["case"]): c for c in json.loads(Path(before).read_text())["cases"]} if before and Path(before).exists() else {}
    cases = d["cases"]
    out = ["# Marketing: real-user test", "",
           "Run in a real Chrome window on a copy of the GitHub test data (`data/try.db`), with publishing off and WhatsApp in sandbox. "
           "Each case has its pass rule written before it ran, two verdicts (it works; it makes sense for a brokerage marketer), a blind 1–5 score "
           "from a fixed judge (\"would a professional Dubai brokerage publish this?\") where something was made, and its evidence.", "",
           f"Model spend for the whole test: ${d.get('spent', 0):.2f}.", "", "## Summary", "", "| Round | Cases | Pass | Works, but weak | Fail | Not run | Average score |",
           "|---|---|---|---|---|---|---|"]
    for r, name in ROUNDS.items():
        cs = [c for c in cases if c["round"] == r]
        if not cs:
            continue
        nums = [c["score"] if isinstance(c.get("score"), (int, float)) else (sum(v for v in c["score"].values() if isinstance(v, (int, float))) /
                max(1, sum(1 for v in c["score"].values() if isinstance(v, (int, float))))) for c in cs if c.get("score")]
        nums = [n for n in nums if n]
        out.append(f"| {name} | {len(cs)} | {sum(mark(c) == 'Pass' for c in cs)} | {sum(mark(c) == 'Works, but weak' for c in cs)} | "
                   f"{sum(mark(c) == 'Fail' for c in cs)} | {sum(mark(c) == 'Not run' for c in cs)} | {round(sum(nums) / len(nums), 2) if nums else ''} |")
    flows = d.get("flows") or {}
    if flows:
        out += ["", "## What a person still had to do beyond yes or no", "", "| Flow | Step | What Diwan should have done |", "|---|---|---|"]
        for f, steps in flows.items():
            out += [f"| {f} | {s['step']} | {s['should']} |" for s in steps]
    for r, name in ROUNDS.items():
        cs = [c for c in cases if c["round"] == r]
        if not cs:
            continue
        out += ["", f"## {name}", "", "| Case | Pass rule | Result | Score | Before | What happened |", "|---|---|---|---|---|---|"]
        for c in cs:
            b = old.get((c["round"], c["case"]))
            what = str(c.get("detail", "")).replace("|", "/").replace("\n", " ")[:420]
            out.append(f"| {c['case']} | {c['rule']} | {mark(c)} | {score(c)} | {(mark(b) + ' ' + score(b)).strip() if b else ''} | {what} |")
    errs = d.get("page_errors") or []
    out += ["", "## Page errors seen in the browser", "", *(f"- {e}" for e in errs[:30])] if errs else ["", "No page errors were seen in the browser."]
    Path(dst).write_text("\n".join(out) + "\n")
    print(f"wrote {dst}: {len(cases)} cases")


if __name__ == "__main__":
    main(*sys.argv[1:4])
