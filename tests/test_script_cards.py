"""The "Pick a script" cards: "Recommended" (and the gold border) only for a script the Creative Director scored 4/5 or
better; otherwise the top card says "Best scored: N/5". Runs the page's own bestOf() in node."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = (Path(__file__).parent.parent / "web/studio.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def best_of(scores):
    src = re.search(r"function bestOf\(options\) \{.*?\n\}\n", PAGE, re.S).group(0)
    opts = [{"director": {"score": s}} if s is not None else {} for s in scores]
    out = subprocess.run([NODE, "-e", f"{src}\nconsole.log(JSON.stringify(bestOf({json.dumps(opts)})))"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


@pytest.mark.skipif(not NODE, reason="node is not installed")
@pytest.mark.parametrize("scores, want", [
    ([4, 2, 2], {"i": 0, "score": 4, "recommended": True}),
    ([2, 5, 5], {"i": 1, "score": 5, "recommended": True}),       # a tie: the first one
    ([3, 2, 3], {"i": 0, "score": 3, "recommended": False}),      # 3/5 is the best, but not recommended
    ([2, 2, 1], {"i": 0, "score": 2, "recommended": False}),
    ([None, None, None], {"i": -1, "score": -1, "recommended": False}),  # no scores: no mark at all
])
def test_recommended_only_at_four_or_better(scores, want):
    assert best_of(scores) == want


def test_the_card_says_best_scored_when_none_reaches_four():
    assert "pick.recommended ? h(\"span\", { class: \"rec\" }, \"Recommended\")" in PAGE
    assert "`Best scored: ${pick.score}/5`" in PAGE
    assert 'class: `opt${i === best && pick.recommended ? " best" : ""}`' in PAGE  # the gold border only when recommended


def test_your_next_post_is_one_line_on_make():
    run = PAGE[PAGE.index('id="tab-run"'):PAGE.index('id="tab-competitors"')]
    assert '<details id="jfold"><summary class="jsum"><b>Your next post:</b>' in run
    assert 'id="jbody"' in run and 'id="jmoment"' in run  # still all there when opened
