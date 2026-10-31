# Diwan: handoff for the next session

Read this first, then `docs/sessions.md` (which session owns what, with a starting message for each),
`docs/rooms.md` (what every department must produce and hand on), `PROJECT.md` (what Diwan is),
`docs/knowledge.md` (knowledge and catalog spec) and `docs/front-office.md` (leads and WhatsApp design). Written 28 Oct 2026.

## 1. The project in five lines

Diwan is an office of AI agents for a Dubai real-estate brokerage, built for the **Meta Global AI Developer Hackathon:
due 4 Nov 2026, 9 PM ET (5 Nov, 6 AM Dubai)**. Every agent has a charter enforced in code, all share one append-only
event log rebuilt into a knowledge graph, and people approve anything legal, financial or public. The core moment: a
customer corrects themselves ("forget my brother, I'll pay it all myself") and the whole office updates. Screens: a 3D
office, Nova (chief of staff), an Inbox (WhatsApp and Instagram), the Studio (marketing), Knowledge, Catalog, Memory
(graph), Team, Settings. Demo company: **Diwan Realty, fictional**.

## 2. Rules that always hold

- **Fictional data only** in demos and on Meta's free credits (Meta may use that content). The demo company profile is `diwan/demo_profile.md`.
- **Never print, log or paste secrets.** Keys live in `diwan-hackathon/.env` (never committed). Set now: `META_API_KEY`, `NVIDIA_API_KEY`, `WHATSAPP_PROVIDER`.
- **Git identity:** `git -c user.name=alifiya-saifee -c user.email=166434982+alifiya-saifee@users.noreply.github.com commit ...`. Never use the owner address. End commit messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Repo:** `github.com/alifiya-saifee/diwan`, private until submission; make it public before submitting.
- **Agents never hold portal or bank credentials** and never promise returns; a person submits, pays, files and publishes.
- **Definition of done** (the user insists): write a checklist spec in `docs/` before coding; cover add, edit, retire, search, real scale (hundreds to thousands), empty and error states; check every item in the browser with screenshots; report item by item (checked in browser / tested in code only / not done). Finish one feature before starting the next.
- **Ask before** force-pushing or rewriting history (the auto-mode classifier blocked one attempt).

## 3. Money: Meta credits and the app's own cap

- Meta: **$150 free credits**; a card is on file only because Meta requires one. A temporary authorisation hold of AED 73.85 (ref V645LHNHQ4) should drop off by itself. The balance stays 0 while credits last; after that Meta bills in 70 AED steps.
- Muse Spark reported price: **$1.25 per million tokens in, $4.25 per million out**; reasoning tokens bill as output; the default reasoning effort is high. `DIWAN_REASONING` (default `low`; `minimal` tested well for Studio scripts) sets it.
- The app's protections (`diwan/costs.py`): an identical request is answered from its saved reply (`tapes/`, `DIWAN_TAPE=cache`); every live call goes to `usage.jsonl` with tokens and an estimated price; live calls stop at `DIWAN_BUDGET_USD` (default 25 a month). Web search, Muse Image and transcription are capped and logged too. Trend search runs once a day.
- Spend so far: about **$1.50** this month. About 400 Rania/Scribe calls ($1.24) ran in one hour on 28 Oct, mostly from another session's tests. **Run repeated tests offline** (`DIWAN_OFFLINE=1 DIWAN_TAPE=off`) or from saved replies, never against the live model in a loop.

## 4. Running and testing

```
cd /Users/alifiya/Downloads/Assignment/diwan-hackathon
DIWAN_DB=diwan.db .venv/bin/uvicorn diwan.app:app --port 8030 --reload --reload-dir diwan   # the demo server
.venv/bin/python -m pytest -q                 # unit tests
.venv/bin/python -m diwan eval                # 78 labelled cases, rules mode (78/78)
.venv/bin/python -m diwan check --ping        # one tiny live call per provider
.venv/bin/python -m diwan doc out.html        # marketing handbook from the code
```

**Browser tests** (Playwright, in `e2e/`): run against a separate test server with its own database and media folder,
never against `diwan.db`:

```
SP=<scratch dir>; DIWAN_AUTH=off DIWAN_DB=$SP/e2e.db DIWAN_MEDIA=$SP/media DIWAN_OFFLINE=1 DIWAN_TAPE=off \
  .venv/bin/uvicorn diwan.app:app --port 8031
.venv/bin/python e2e/studio_flow.py http://127.0.0.1:8031 $SP <take.mp4>    # WATCH=1 for a visible window
```

| Script | Checks |
|---|---|
| `office_flow.py` | WhatsApp sandbox → Rania booking → takeover; a lesson kept; an Instagram comment; Nova read-back → Lobby |
| `studio_flow.py` | run → 3 scripts → change one → pick → footage → captioned cut → publish request |
| `floor_flow.py` | the 3D Marketing floor: robots leave their desks, the Brand brain panel, the Production set |
| `views_flow.py` | every 3D camera view at 1440 and 1280: zero overlapping labels |
| `brand_flow.py` | brand draft → save → scripts follow it (live model) |
| `learn_flow.py` | the AI learns the company from the demo profile → cards confirmed → memory graph |
| `memory_flow.py` | the Marketing & brand memory graph, click and rewind |
| `knowledge_flow.py` | knowledge and catalog definition of done (written by the knowledge session) |

The test server does not reload code: restart it after a change. Pages are served with no-cache headers.

## 5. Who owns what (several Claude sessions share this repo)

| Area | Owner | Files |
|---|---|---|
| Marketing studio, brand, strategy, costs, 3D office, Memory graph marketing view | the session that wrote this file | `agents/studio.py, qa.py, strategy.py, kpis.py`, `brand.py, brand_api.py, brain.py, learn.py, costs.py`, `web/studio.html, graph.html` |
| WhatsApp, Inbox, leads, portal feed, sales, finance, compliance | the WhatsApp session | `agents/reception.py`, `inbox.py, leads.py, providers/portals.py`, `web/inbox.html`, `docs/front-office.md` |
| Knowledge store, Knowledge page, Catalog | the knowledge session | `knowledge.py, knowledge_api.py`, `web/knowledge.html, catalog.html`, `tests/test_knowledge.py` |
| Shared (edit carefully, commit only your own hunks) | everyone | `app.py, events.py, graph.py, office.py, people.py, demo.py, web/office3d.html, web/app.js` |

To commit only your own lines of a shared file: `git diff -U0 <file>`, keep your hunk, `git apply --cached --unidiff-zero <patch>`.
**Uncommitted right now:** the knowledge session's work and the WhatsApp session's work (both large). Do not commit someone else's files.

## 6. What is built and verified

- **Marketing studio:** a listing goes research → 2 to 3 checked scripts on different angles → the Marketing manager picks one or asks for a change in plain words (only that script is rewritten) → film list or AI presenter (HeyGen, paid, consent required) → captions → permit gate → owner approves publishing. Supervision: each room lead checks work against written rules, returns it up to twice, then escalates. Checked in the browser, offline and live.
- **Angle strategy** (`strategy.py`): winning (last 2 at 1.2x our median) keep; fading (falling 3 times, under median) shift; resting (2 under 0.8x) 30 days; always one explore slot. Unit tests only; needs our real post history to show live.
- **Brand profile:** the Marketing manager sets it or edits a draft; writers receive it; review sends back never-use words; templates and post text use its sign-off and hashtags. Live: 3 of 3 scripts used the brand sign-off, no banned words.
- **The AI builds the knowledge graph** (`learn.py`): from a document or public pages, proposes cards each proven by a word-for-word quote (unproven ones dropped), drafts the brand; a person confirms. Live on the demo profile: 10 cards, 0 dropped, $0.008.
- **Memory page:** a Marketing & brand view rebuilt from the log, rewindable, readable labels.
- **3D office:** department floors, leads walk to the work they check, the brain shows real memory, no sample data, no overlapping labels in 38 views.
- **Cost controls** as in section 3. **Knowledge and Catalog**: built by the knowledge session, 20 of 22 checks pass (independently re-checked).
- Tests: 179 pass on the committed code (192 with the knowledge session's uncommitted tests); evals 78/78.

## 7. Open issues, most urgent first

1. **Leak: Rania can tell customers internal-only knowledge.** `reception.py` line ~95 gives the model every confirmed item. Fix: use `knowledge.search(g, question, k=8)` (customer-facing, confirmed, in date) and hand over when it returns nothing. Owner: WhatsApp session. Details in `docs/knowledge.md` section 5b.
2. **Feed sync resets listing status.** `leads.sync_listings` writes `status: "available"` every sync, so sold or reserved listings come back, and accepted prices revert. Decision: the feed is the truth for advertised listings; an accepted change should show "waiting for the portal" and give the broker a task, not revert silently. Owner: WhatsApp session.
3. **No search box on every screen** (spec 5a promises one in the header). Owner: knowledge session.
4. **Permissions trust the browser-sent name** ("Acting as"): fine for the demo, not real.
5. **Knowledge and Catalog pages scroll sideways on a phone.**
6. **Trend cards are not linked to the scripts that use them** (the idea generator does not cite the card).
7. **A script's first line can nearly repeat its hook** (one word different): add a near-duplicate check.
8. **Rania and Scribe not yet tried at `DIWAN_REASONING=minimal`.** Reasoning was 80% of output tokens at low.
9. **Unverified:** the real cost of web search (check Meta's Usage page); the cheaper search settings.
10. **Git history** still contains `diwan.db.20261028-063807.bak` (fictional data only). Scrubbing it needs the user's explicit OK, before the repo goes public.

## 8. Waiting on the user

Instagram professional account and token; a WhatsApp test number (AiSensy or Cloud API); HeyGen key and a consented
avatar (optional, paid); the hackathon track; making the repo public before submitting.

## 9. Next steps, in order

1. WhatsApp session: fix issues 1 and 2; stop live-model test loops.
2. Knowledge session: header search (issue 3) and phone layout (issue 5); then commit its work.
3. Re-run every `e2e/` script on a fresh offline test server; one live pass of `brand_flow.py` and `learn_flow.py`.
4. Record the demo: the correction moment, the front desk, a listing through the studio to an approved captioned reel, the AI learning the company.
5. Scrub the history (with permission), make the repo public, submit.
