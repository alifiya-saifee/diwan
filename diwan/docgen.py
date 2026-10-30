"""The content studio's handbook, generated from the code: charters, the real prompts, the supervisor's checks, KPI
targets, and the evaluation results. `python -m diwan doc <out.html>`. Nothing here is typed by hand that the code
already knows, so the handbook cannot drift from what the agents do.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = html.escape

ROOMS = [("research", "Research", "Find what is working, with proof."), ("plan", "Planning", "Decide what to make for this listing."),
         ("mcopy", "Scripting", "Write it, and get a person's yes before anything costs money."),
         ("mprod", "Production", "Turn the approved script into footage."), ("mart", "Editing", "Captions, the post text, the cut."),
         ("mpub", "Publishing", "Check the law, pick the time, wait for the owner.")]

STEPS = [
    ("Listing in", "mkt", "A listing with a permit number", "Checks the permit is on file; a listing without one stops here.", "Nothing is made for an unpermitted listing", None),
    ("Watch competitors", "mrival", "Competitor accounts set in Settings (or a spreadsheet of their posts)",
     "Fetches each account's recent posts through Instagram business discovery; scores every post as its likes plus comments over that account's median; pins posts at 2x or more.",
     "Outliers on the research board, each with its link", "Researcher"),
    ("Spot trends", "mtrend", "The listing's areas", "Asks Muse Spark to search the web for formats working for Dubai brokers this month; keeps only cards with a source.",
     "Up to 3 trend cards, each with its link", "Researcher"),
    ("Read the top video", "mtrans", "The top outlier, if it is a video", "Downloads it and transcribes it (Muse Voice Transcribe); pulls the hook and beats.",
     "Hook, beats, transcript", "Researcher"),
    ("Pick the idea", "midea", "The listing and the board", "Muse Spark proposes ideas that name the cards they build on; invented card ids are dropped. Without a model, one idea per card plus a walk-through.",
     "The chosen idea", "Strategist"),
    ("Balance the week", "mlane", "Our last 30 days of posts", "Sorts our captions into five lanes and names the empty one.", "Lane counts and the gap", None),
    ("Choose the angles", "mcopy", "Our posts and the competitors' outliers", "The strategy keeps angles that are winning on our account, drops ones that are fading or resting, leads with what wins in the market when we have no history, and always keeps one slot to explore.",
     "Up to 3 angles, each with the numbers behind it", None),
    ("Write the scripts", "mscript", "The idea, the listing, the outlier's hook, the angle", "One script per angle: a hook and 5 to 8 lines in English and Arabic, borrowing structure never words. Every amount must be on the listing. Each is checked before it is offered.",
     "2 to 3 checked scripts", "Copywriter"),
    ("Pick or change a script", "mcopy", "The checked scripts", "The Marketing manager picks one, or asks for a change to one in plain words (\"make the hook shorter, sea view first\"): only that script is rewritten, checked again and offered again. Nothing that spends filming, editing or model time starts before a pick.",
     "An approved script", "Marketing manager (a person)"),
    ("Get footage", "mshoot / mvideo", "The approved script", "The broker gets a film list with the time to shoot; or a person clicks Make AI video and an AI presenter (HeyGen) reads the script, after confirming the avatar's consent.",
     "Footage", "Producer"),
    ("Check the take", "mcheck", "The footage and the approved script", "Transcribes the take and compares it word by word with the script; names lines that were not said.", "Lines that drifted", "Copywriter"),
    ("Caption and cut", "mcap", "The footage and what was said", "Draws each caption and overlays it at the time it was said (ffmpeg); from the script if the audio cannot be transcribed.",
     "The captioned cut", "Art director"),
    ("Write the post", "mwriter", "The script and the listing", "Post text with the hook, the facts, the price and the permit number, in English and Arabic.", "Post text", "Art director"),
    ("Make covers", "mthumb", "The footage, the hook", "Two frames of our own footage with the hook on them; never a generated picture.", "Cover options", "Publisher"),
    ("Permit gate", "mpermit", "The post text and the listing", "Permit number present, only the listing's price, no banned promises. A hold is traced to whoever caused it, who fixes it.",
     "Pass, or held with each reason", "Publisher"),
    ("Schedule and format", "msched / mcross", "Our post history, the post text", "Picks the hour our posts did best (or the evening default, said so); cuts the text to each platform's limit.",
     "Slot and platform versions", "Publisher"),
    ("Publish", "mpub", "Everything above", "Asks the owner. After yes, posts the reel through the Instagram Content Publishing API.", "A live post", "Owner (a person)"),
    ("Answer comments", "rania", "Comments on the post", "Instagram comments come to Rania like WhatsApp: she answers from the listing and hands buyers to Sales.", "Replies and leads", "Broker"),
]


def _prompts() -> dict[str, str]:
    """The exact words the model is given at each model step, read from the source."""
    src = (ROOT / "diwan/agents/studio.py").read_text()
    grab = lambda rx: (re.search(rx, src, re.S).group(1) if re.search(rx, src, re.S) else "")  # noqa: E731
    return {
        "mtrend": re.sub(r'"\s+"', "", grab(r'meta\.search\(("What short-form.*?")\)')).strip('"'),
        "midea": grab(r'f"(Three short-video ideas.*?)"'),
        "mscript": grab(r'\+ "\\n(Write in the `script` format\..*?)"') + " " + grab(r'f"(Script for: .*?)"'),
        "suggest": re.sub(r'"\s+"', "", grab(r'meta\.search\(f("Which real-estate brokerages.*?")\)', ) if False else ""),
    }


def _eval_run():
    """A full studio run on the evaluation data, to measure the KPIs."""
    os.environ["DIWAN_OFFLINE"] = "1"
    os.environ["DIWAN_LOCAL_ASR"] = "0"
    from diwan import demo
    from diwan.agents import kpis, studio
    from diwan.evals import POSTS
    from diwan.events import EventLog
    from diwan.office import Office
    o = Office(EventLog())
    demo.seed(o)
    studio.import_posts(o, [dict(zip(studio.CSV_COLUMNS, map(str, p))) for p in POSTS], by="eval")
    studio.run_now(o, "MC-1204")
    studio.approve_script_now(o, "MC-1204")
    return kpis.measure(o)


def build(out: Path) -> None:
    from diwan.agents import qa, runner
    from diwan.agents.charters import BY_ID, children, get
    from diwan.agents.kpis import TARGETS
    from diwan.pack import ACTIONS
    res = json.loads((ROOT / "evals/results-rules.json").read_text())
    studio_cases = res["suites"]["Studio"]["cases"]
    measured = _eval_run()
    prompts = _prompts()
    checks_by_owner: dict[str, list] = {}
    for kind, cs in qa.CHECKS.items():
        for c in cs:
            checks_by_owner.setdefault(c.owner, []).append((kind, c))

    def chip(text, cls=""):
        return f'<span class="chip {cls}">{E(text)}</span>'

    def agent_card(aid: str) -> str:
        c = get(aid)
        alone = ", ".join(ACTIONS[a].lower() for a in c.alone) or "nothing"
        person = ", ".join(ACTIONS[a].lower() for a in c.person) or "nothing"
        rows = []
        for kind, ch in checks_by_owner.get(aid, []):
            rows.append(f"<li><b>{E(ch.rule)}</b> <span class=muted>Checked by the {E(get(qa.supervisor(aid)).name)}. If not: {E(ch.fix)}</span></li>")
        m = measured.get(aid, {})
        kp = "".join(f"<tr><td>{E(t['kpi'])}</td><td class=num>{E(t['target'])}</td><td class=muted>{E(t['means'])}</td></tr>" for t in m.get("targets", []))
        now = []
        for k, label in (("first_time_pass", "first-time pass"), ("returned", "returned"), ("escalated", "escalated"), ("blocked", "waiting on a connection"),
                         ("approved_by_manager", "approved by the manager"), ("cards_with_source", "cards with a source"), ("outliers_pinned", "outliers pinned"),
                         ("posts_with_permit", "posts with the permit")):
            v = m.get(k)
            if v is not None and (k not in ("returned", "escalated", "blocked") or v):
                now.append(f"{label} {v}{'%' if k in ('first_time_pass', 'approved_by_manager', 'cards_with_source', 'posts_with_permit') else ''}")
        prompt = ""
        if aid in prompts and prompts[aid]:
            prompt = f'<details><summary>The words the model is given</summary><pre>{E(runner._instructions(c))}\n\n{E(prompts[aid])}</pre></details>'
        return f"""<article class="agent" id="{aid}">
  <header><h4>{E(c.name)}</h4><span class="muted">{E(c.role)}</span>{chip(c.runs_on)}</header>
  <p>{E(c.job)}</p>
  <dl><dt>Reads</dt><dd>{E(c.inputs)}</dd><dt>May use</dt><dd>{E(c.sources)}</dd><dt>Hands on</dt><dd>{E(c.out)}</dd>
  <dt>Does alone</dt><dd>{E(alone)}</dd><dt>Needs a person</dt><dd>{E(person)}</dd><dt>Never</dt><dd class="never">{E(c.never)}</dd>
  <dt>When unsure</dt><dd>{E(c.on_missing)}</dd></dl>
  {f'<h5>Acceptance rules</h5><ul class="rules">{"".join(rows)}</ul>' if rows else ''}
  {f'<h5>KPIs</h5><table class="kpi"><tr><th>KPI</th><th>Target</th><th>Means</th></tr>{kp}</table>' if kp else ''}
  {f'<p class="now">On the evaluation run: {E(" · ".join(now))}</p>' if now else ''}
  {prompt}
</article>"""

    rooms_html = []
    for rid, title, line in ROOMS:
        lead = get(rid)
        members = [rid] + [c.id for c in children(rid)]
        rooms_html.append(f"""<section class="room" id="room-{rid}"><h3>{E(title)} <span class="muted">· {E(lead.name)} leads</span></h3><p class="lede">{E(line)}</p>
<div class="agents">{"".join(agent_card(a) for a in members)}</div></section>""")
    steps_html = "".join(f"""<li><div class="step"><h4>{E(n)}</h4><p class="who">{E(" / ".join(get(x.strip()).name for x in w.split("/") if x.strip() in BY_ID))}</p>
<dl><dt>In</dt><dd>{E(i)}</dd><dt>How</dt><dd>{E(h)}</dd><dt>Out</dt><dd>{E(o)}</dd><dt>Checked by</dt><dd>{E(s or "nothing further: the rule is in code")}</dd></dl></div></li>"""
                         for n, w, i, h, o, s in STEPS)
    tests_html = "".join(f"<li class='{'pass' if c['pass'] else 'fail'}'>{'✓' if c['pass'] else '✗'} {E(c['case'])}</li>" for c in studio_cases)
    total = f"{res['passed']}/{res['total']}"
    page = f"""<title>Diwan Content Studio</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
/* Layout: a handbook. One reading column for the story, wide grids only where agents sit side by side. */
:root {{ --bg:#f7f5f0; --panel:#ffffff; --ink:#1c1f26; --muted:#5f6573; --line:#e3dfd5; --gold:#9a6b14; --gold-soft:#f3e7cc; --bad:#a3352c; --ok:#2f7a4f;
  --display:"Newsreader", Georgia, serif; --body:"IBM Plex Sans", system-ui, sans-serif; --mono:"IBM Plex Mono", ui-monospace, monospace; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#0d1017; --panel:#151a23; --ink:#ebe7de; --muted:#9aa1b0; --line:#262c38; --gold:#e3bf75; --gold-soft:#2b2516; --bad:#f08a7e; --ok:#7fd3a0; color-scheme:dark; }} }}
:root[data-theme="dark"] {{ --bg:#0d1017; --panel:#151a23; --ink:#ebe7de; --muted:#9aa1b0; --line:#262c38; --gold:#e3bf75; --gold-soft:#2b2516; --bad:#f08a7e; --ok:#7fd3a0; color-scheme:dark; }}
body {{ background:var(--bg); color:var(--ink); font:15px/1.6 var(--body); padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); padding-block:40px 80px; }}
main {{ max-width:1080px; margin:0 auto; display:grid; gap:56px; }}
.col {{ max-width:68ch; }}
h1,h2,h3 {{ font-family:var(--display); font-weight:400; text-wrap:balance; margin:0; }}
h1 {{ font-size:clamp(34px,5vw,52px); line-height:1.05; }} h1 em {{ color:var(--gold); }}
h2 {{ font-size:30px; margin-bottom:10px; }} h3 {{ font-size:24px; }}
h4 {{ margin:0; font-size:15px; }} h5 {{ margin:14px 0 6px; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }}
.eyebrow {{ font:600 11px var(--body); letter-spacing:.16em; text-transform:uppercase; color:var(--gold); }}
.muted {{ color:var(--muted); }} .lede {{ color:var(--muted); margin:4px 0 16px; }}
.strip {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:18px; }}
.chip {{ font:12px var(--mono); padding:3px 9px; border-radius:99px; border:1px solid var(--line); color:var(--muted); background:var(--panel); white-space:nowrap; }}
.chip.ok {{ color:var(--ok); }} .chip.gold {{ color:var(--gold); background:var(--gold-soft); border-color:transparent; }}
ol.steps {{ list-style:none; padding:0; margin:0; display:grid; gap:12px; counter-reset:s; }}
ol.steps > li {{ counter-increment:s; display:grid; grid-template-columns:42px 1fr; gap:14px; }}
ol.steps > li::before {{ content:counter(s); font:600 14px var(--mono); color:var(--gold); border:1px solid var(--line); border-radius:50%; width:34px; height:34px; display:grid; place-items:center; background:var(--panel); }}
.step {{ border-bottom:1px solid var(--line); padding-bottom:12px; min-width:0; }} .step .who {{ margin:2px 0 8px; color:var(--gold); font-size:13px; }}
dl {{ display:grid; grid-template-columns:110px 1fr; gap:4px 14px; margin:0; font-size:13.5px; }} dt {{ color:var(--muted); }} dd {{ margin:0; min-width:0; }}
.never {{ color:var(--bad); }}
.gate {{ border:1px solid var(--line); background:var(--panel); border-radius:14px; padding:18px 20px; }}
.gates {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:14px; }}
.gate b {{ font-family:var(--display); font-size:19px; font-weight:400; display:block; margin-bottom:6px; }}
.ladder {{ display:grid; gap:0; border-left:2px solid var(--gold); padding-left:18px; }}
.ladder div {{ padding:8px 0; }} .ladder b {{ display:block; }}
.agents {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px; }}
.agent {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px 18px; min-width:0; }}
.agent header {{ display:flex; flex-wrap:wrap; gap:8px; align-items:baseline; margin-bottom:6px; }} .agent header .chip {{ margin-left:auto; }}
.agent p {{ margin:4px 0 10px; }}
ul.rules {{ margin:0; padding-left:18px; font-size:13.5px; display:grid; gap:4px; }} ul.rules span {{ display:block; }}
table.kpi {{ width:100%; border-collapse:collapse; font-size:13px; }} .kpi th, .kpi td {{ text-align:left; padding:5px 6px; border-bottom:1px solid var(--line); vertical-align:top; }}
.kpi th {{ font-size:11px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); font-weight:500; }} .num {{ white-space:nowrap; font-variant-numeric:tabular-nums; }}
.now {{ font:12px var(--mono); color:var(--ok); margin:10px 0 0; }}
details {{ margin-top:10px; }} summary {{ cursor:pointer; color:var(--gold); font-size:13px; }}
pre {{ white-space:pre-wrap; font:12px/1.55 var(--mono); background:var(--bg); border:1px solid var(--line); border-radius:10px; padding:12px; overflow-x:auto; }}
.room {{ display:grid; gap:4px; }}
.tests {{ columns:2 300px; padding:0; list-style:none; font-size:13.5px; }} .tests li {{ break-inside:avoid; padding:3px 0; }} .tests .pass {{ color:var(--ok); }} .tests .fail {{ color:var(--bad); }}
.diagram {{ overflow-x:auto; background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:16px; }}
:focus-visible {{ outline:2px solid var(--gold); outline-offset:2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior:auto; }} }}
</style>
<main>
<header class="col">
  <p class="eyebrow">Diwan · Marketing</p>
  <h1>The content <em>studio</em></h1>
  <p class="lede">How one listing becomes a published reel: who does each step, the words the model is given, what each piece of work must pass, who checks it and when, who fixes what goes wrong, where a person must say yes, and the numbers each agent is held to. Generated from the code; nothing here is described that the agents do not do.</p>
  <div class="strip">{chip(f"{len([a for a in BY_ID if a.startswith('m') or a in ('research','plan')])} agents in 7 rooms")}{chip(f"studio tests {res['suites']['Studio']['passed']}/{res['suites']['Studio']['total']}", "ok")}{chip(f"all agents {total}", "ok")}{chip("2 person approvals", "gold")}</div>
</header>

<section class="col"><p class="eyebrow">The final product</p><h2>What comes out the end</h2>
<p>For each permitted listing: <b>a captioned vertical reel</b> (filmed by the broker or read by an AI presenter), <b>post text in English and Arabic with the permit number</b>, <b>two cover options</b>, <b>a version for each platform</b> within its limits, and <b>a slot</b> chosen from our own results. It is published only after the owner says yes. Every comment it brings in is answered by Rania from the listing and becomes a lead for Sales, the same way a WhatsApp message does.</p></section>

<section><p class="eyebrow">Flow</p><h2>The line, end to end</h2>
<div class="diagram"><pre class="mermaid">
flowchart LR
  L[Listing with permit] --> R1[Competitor watch] & R2[Trend scout]
  R1 --> R3[Transcript reader]
  R1 & R2 & R3 --> B[(Research board)]
  B --> I[Idea generator]
  I -->|Strategist checks| S[Script writer]
  S -->|Copywriter checks| A1{{Marketing manager approves}}
  A1 -->|no + note| S
  A1 -->|yes| F[Film list to broker]
  A1 -->|yes + consent click| V[AI presenter video]
  F & V --> K[Video check]
  K --> C[Captions and cut]
  C --> P[Post text] --> G{{Permit gate}}
  G -->|held: traced to cause| S
  G -->|held: traced to cause| P
  G -->|pass| T[Slot and platform versions]
  T --> A2{{Owner approves}} -->|yes| IG[Published on Instagram]
  IG --> CM[Comments] --> RA[Rania] --> SL[Leads for Sales]
</pre></div></section>

<section class="col"><p class="eyebrow">Step by step</p><h2>Who does what, in order</h2><ol class="steps">{steps_html}</ol></section>

<section><p class="eyebrow">People and money</p><h2>Where a person must say yes</h2>
<div class="gates">
 <div class="gate"><b>The script</b>The Marketing manager picks one of 2 to 3 checked scripts, or asks for a change to one. Until then nothing that spends filming time, HeyGen credits, editing or image generation can start. A "send back" with a note goes straight to the Script writer, whose next draft is checked again and asked again.</div>
 <div class="gate"><b>A face or a voice</b>An AI presenter video starts only when a person clicks Make AI video and confirms that the person in the avatar agreed. The confirmation is recorded with the footage.</div>
 <div class="gate"><b>Publishing</b>The owner approves the finished post. If something is still missing (the cut, Instagram, a public address for the video), the approval is kept and the post says what it needs.</div>
</div></section>

<section class="col"><p class="eyebrow">Supervision</p><h2>When work is checked, and who fixes it</h2>
<p><b>When:</b> the moment each piece is made. The room lead holds every agent in the room to written acceptance rules (listed on each agent below). Rules that cannot run count as failed, never as passed.</p>
<p><b>Who fixes it:</b> every rule names an owner, so a failure goes back to the agent who made the work, with the rule, what was found, and the fix. A problem found later is traced to its cause: if the permit checker holds a post because of a price, it looks in the script first; if the price came from the script, the <i>Script writer</i> fixes it, not the Content writer who noticed it.</p>
<div class="ladder">
 <div><b>1. Made</b><span class="muted">The agent hands its work to the room lead.</span></div>
 <div><b>2. Checked</b><span class="muted">Each acceptance rule runs. Pass: the work moves on.</span></div>
 <div><b>3. Returned, up to twice</b><span class="muted">The owner gets the reasons and the fix. A model step gets them in its instructions; a rules step is corrected in code.</span></div>
 <div><b>4. Escalated</b><span class="muted">Third failure: the Marketing lead raises it to the owner with every reason, as a decision: fix it myself, accept as is, or stop this reel.</span></div>
 <div><b>5. Learned</b><span class="muted">A correction a person makes can be saved as a lesson ("Script writer, never mention service charges"). It goes into that agent's instructions, and "never" lessons are enforced in code from the next draft.</span></div>
</div></section>

<section class="col"><p class="eyebrow">Strategy</p><h2>When to keep an angle, and when to shift</h2>
<p>Every post is put in one angle: price reveal, walk-through, lifestyle, investor facts, or market check. Each of our own posts is measured against our median engagement, oldest first.</p>
<table class="kpi"><tr><th>Status</th><th>Rule</th><th>What the studio does</th></tr>
<tr><td>Winning</td><td>The last 2 posts both at 1.2x our median or more</td><td>Keep making it; it gets the first script</td></tr>
<tr><td>Fading</td><td>It worked before, each of the last 3 did worse than the one before, and the latest is under our median</td><td>Shift away: no script on it this run</td></tr>
<tr><td>Resting</td><td>The last 2 posts both under 0.8x our median</td><td>Stop for 30 days, then it may be tested again</td></tr>
<tr><td>Steady</td><td>In between</td><td>Keep in rotation</td></tr>
<tr><td>Untested</td><td>Fewer than 2 posts of ours</td><td>A candidate for the explore slot, ranked by how it does for competitors</td></tr></table>
<p>Up to 2 scripts come from what is working (ours first, then the competitors' outliers) and 1 always explores, so the account never runs one idea until it dies.</p></section>

<section class="col"><p class="eyebrow">Cost</p><h2>Not paying twice, and a cap</h2>
<p><b>Cache.</b> An identical request (same agent, same prompt, same format) is answered from its recording at no cost. A changed prompt, or changed facts, is a new call.</p>
<p><b>Ledger.</b> Every live call is written down with its tokens and an estimated price, and every cache hit with what it saved. The Studio shows this month's spend, the budget and the savings.</p>
<p><b>Cap.</b> At the monthly budget (DIWAN_BUDGET_USD, default 25) live calls stop; agents use rules and templates and say so. NVIDIA's free endpoint costs nothing.</p>
<p><b>Order of spend.</b> Research and scripts are text and cost cents. Filming time and HeyGen (about $1 a minute, no free API credits) only start after a person picks a script.</p></section>

<section class="col"><p class="eyebrow">The research agent, in depth</p><h2>How research works and how we know it is right</h2>
<p><b>Who the competitors are.</b> A person lists the accounts. "Suggest" asks Muse Spark to search the web for Dubai brokerages active in our listing areas; nothing is watched until a person confirms. Without an Instagram connection, real posts can be copied into a spreadsheet template and imported.</p>
<p><b>What it reads.</b> Instagram business discovery returns each competitor's recent posts with likes, comments, type, caption and link, plus their follower count. It does not return their views, reach or stories, and the studio says so instead of guessing. Our own account adds views, reach, saves and shares.</p>
<p><b>How it scores.</b> Each post's likes plus comments, divided by the median of that account's posts. A post at 2x or more is an outlier. Accounts with fewer than 5 posts are not scored. Comparing each account to itself keeps a small brokerage's breakout visible next to a big one's ordinary post.</p>
<p><b>How it explains why.</b> It measures ten features on every post (reel or not, opens with a question, price in the first line, names an area, Arabic, a call to action, caption length, evening posting, hashtags) and reports only features where outliers differ from the rest by 25 points or more, with links to the example posts.</p>
<p><b>The words the trend scout gives the model:</b></p><pre>{E(prompts.get("mtrend", ""))}</pre>
<p class="muted">Limits today: the outlier score uses likes and comments because that is what Instagram gives for other accounts; a 25-point difference over a handful of posts is a signal to test, not a law. Both are stated on the Studio page.</p></section>

<section><p class="eyebrow">The team</p><h2>Every agent: job, rules, prompt, checks, KPIs</h2>
<p class="lede col">Shared KPIs for every agent: first-time pass at review, work returned, escalations, steps waiting on a connection, and how much came from a model. The specific ones are below each agent, with what the evaluation run measured.</p>
{"".join(rooms_html)}</section>

<section class="col"><p class="eyebrow">Testing</p><h2>What is tested, and the result</h2>
<p>{res['suites']['Studio']['passed']} of {res['suites']['Studio']['total']} studio cases pass, and {total} across every agent ({E(res['mode'])} mode, {E(res['at'])}). Run them with <code>python -m diwan eval</code>.</p>
<ul class="tests">{tests_html}</ul></section>

<section class="col"><p class="eyebrow">To go live</p><h2>What each connection unlocks</h2>
<table class="kpi"><tr><th>Connection</th><th>Unlocks</th></tr>
<tr><td>Meta Model API key</td><td>Trend research, transcripts of competitor videos and our takes, scripts and ideas on Muse Spark</td></tr>
<tr><td>Instagram professional account</td><td>Competitor posts fetched automatically, our insights, publishing, comments to Rania</td></tr>
<tr><td>Public address for the app</td><td>Instagram can fetch the reel when publishing</td></tr>
<tr><td>HeyGen key, consented avatar and voice</td><td>AI presenter videos from approved scripts</td></tr>
<tr><td>NVIDIA key (connected)</td><td>Muse Glimmer stands in for Muse Spark on background steps until the Meta key arrives</td></tr></table></section>
</main>"""
    out.write_text(page)
