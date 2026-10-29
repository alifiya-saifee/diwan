# Diwan: which sessions, and why

Departments whose code is linked are built by one session; departments that only meet through events run in their
own session, in parallel. Each session owns its files, builds to the contract in `docs/rooms.md`, and follows the
rules in `docs/handoff.md` section 2. Deadline: 4 Nov 2026, 9 PM ET. Read `docs/handoff.md` first.

## What is linked, and what is independent (from the code)

| Departments | Linked? | Why (in the code today) |
|---|---|---|
| Review + Compliance + Finance + Operations | **linked: one session** | `office._replace` (the correction) raises the Compliance check, withdraws the Finance payment task, refuses stale approvals and sends back the deck slide in one function; `office._payment_rules` creates both the Finance "expect payment" task and the Compliance "screen the payer" task; Form F rests on the same approvals and the same live facts. Split, they would collide in the same functions. |
| Front desk + Sales (with knowledge and catalog) | **linked: one session** | Rania, the Scribe, the inbox, leads, Nova and the knowledge store work on the same chats, leads and items; Nova reads the knowledge and the leads. |
| Marketing | **independent** | Meets Sales only at one event: a comment or DM on a published post becomes a lead tagged with that post. |
| Records | **independent** | Nova calls one function (`records.delegate`); documents and the sales ledger are its own. |

So **four sessions, all four can start now and run in parallel**: where they meet is an event or one function call,
written down in "Where sessions meet" below.

## Rules for every session (the product owner's standing instructions)

1. **No feature without a reason.** Every change states which row of `docs/rooms.md` or which checklist item below it
   fulfils. Anything on neither is not built without the product owner's OK, however useful it looks.
2. **Work the checklist top to bottom.** Items are in priority order: safety first, then what the demo shows, then the rest.
3. **Working means working for a person.** Each item is checked in the browser the way a user would use it, with a
   screenshot, including missing, wrong and real-scale cases. Passing tests alone is not done.
4. **Efficient output.** Each agent produces exactly the output its contract names, from its sources, cited; no extra
   steps, no repeated model calls (use the saved replies), the cheapest reasoning level that keeps quality.
5. **Stay in your files.** Shared files take small additions only; commit only your own hunks
   (`git diff -U0 <file>` → keep yours → `git apply --cached --unidiff-zero`); one line in the changelog.
6. **End-of-day report** to the product owner: each item marked checked in the browser / tested in code only / not
   done (with the reason); the day's model spend; anything that needs their decision.
7. **Target: the checklist working by the end of 29 Oct.** Say early if an item cannot be finished properly.
8. **Tests offline** (`DIWAN_OFFLINE=1`); the live model only for one final pass, with its cost reported.

## The four sessions

| Session | Departments and agents | Owns these files |
|---|---|---|
| **1. Marketing** | Research, Planning, Scripting, Production, Editing, Publishing, Library (brand) | `agents/studio.py, qa.py, strategy.py, kpis.py, analysis.py`; `brand.py, brand_api.py, brain.py, learn.py, costs.py, docgen.py, demo_profile.md`; `providers/instagram.py, heygen.py, meta.py`; `web/studio.html, graph.html` |
| **2. Front desk & Sales** | Nova, the Lobby; Intake, Scribe, Profiler, Rania, Dispatcher, Briefer, Lead desk, Follow-up; meetings; knowledge store and catalog | `agents/reception.py, scribe.py, nova.py, lobby.py`; `inbox.py, leads.py, qualify.py, slots.py, knowledge.py, knowledge_api.py, playground.py`; `providers/portals.py, aisensy.py, whatsapp.py, voice.py, local_asr.py`; `web/inbox.html, knowledge.html, catalog.html, index.html, meeting.html, team.html, settings.html` |
| **3. Deal desk** (Review, Compliance, Finance, Operations) | Fact checker, Devil's advocate; Screening, Source of funds, Report drafter; Payment tracker, Invoice clerk; Form F clerk, Transfer tracker | `office.py` (the correction engine, payment rules, approvals, Form F guard); new `agents/compliance.py, finance.py, operations.py, review.py`; Nova's `formf_plan` moves to `agents/operations.py` (one small commit, announced); new `web/deal.html` |
| **4. Records** | Archivist, Data analyst | `agents/records.py`; `office.file_document, close_sale`; new `web/records.html` |

**Shared by everyone** (small additions only): `app.py, events.py, graph.py, people.py, demo.py, config.py, pack.py,
agents/charters.py, agents/runner.py, agents/lessons.py, providers/chat.py, providers/tape.py, web/app.js, web/app.css,
web/office3d.html`.

## 1. Marketing

**Goal:** on the main demo database, a person runs the whole studio through the screens with the live model, and it is right every time.

- [ ] Brand: learn Diwan Realty from the demo profile, confirm the cards, save the brand; it shows in the Brand brain and the memory graph.
- [ ] Run a listing: trend cards with sources, competitors from the spreadsheet import, an idea, 3 scripts on different angles, each passing review, in the brand's voice and sign-off.
- [ ] Ask for a change to one script; only it is rewritten; pick it.
- [ ] Production and editing: film-list task to the broker; upload a take; take check; captions burned in; post text with the permit and brand hashtags; covers.
- [ ] Publish request reaches the owner; with Instagram connected approving publishes, otherwise it says what it needs.
- [ ] A comment on a post reaches Rania tagged with the post and angle (event shape agreed with session 2 in the changelog).
- [ ] Strategy ranks angles by enquiries per post once session 2 reports them.
- [ ] Every 3D view and the Studio page: no overlaps, no sample data, works at 1280 wide.
- [ ] One full run's spend measured and shown.

## 2. Front desk & Sales

**Goal:** a customer on the sandbox WhatsApp line or an Instagram DM is answered, qualified, assigned, briefed and
booked correctly, from the knowledge store and catalog, with people in control; Nova runs the office's day.

- [ ] **Fix first:** Rania uses `knowledge.search()` only, so internal-only items never reach a customer (handoff.md issue 1).
- [ ] **Fix first:** the feed sync keeps a listing's status; an accepted price shows "waiting for the portal" instead of reverting (issue 2).
- [ ] Knowledge and catalog: the header search box on every screen; pages work at phone width; then commit the knowledge work.
- [ ] Intake: duplicates ignored, bursts merged, spam to "not a lead", source tagged (including Marketing posts).
- [ ] Profiler: tags with quotes, persona checklists, Qualified only when complete and the customer agreed.
- [ ] Rania's three stages: discovery, one question at a time, waiting for the broker; booking in free slots; handover on everything that isn't hers.
- [ ] Dispatcher, Briefer, Lead desk, Follow-up: assignment, a 5-line brief, cards with due times, overdue, the Pool, nudges.
- [ ] Nova: the morning briefing, questions answered with citations, Lobby jobs with read-back and chasing.
- [ ] Reports leads and viewings per Marketing post and angle.

## 3. Deal desk (Review, Compliance, Finance, Operations)

**Goal:** the correction moment works every time, and every deal's money and paperwork rest on the customer's live words.

- [x] **The correction end to end:** "Actually, forget my brother. I'll pay it all myself." → the fact is replaced (history kept) → Compliance flagged first with both quotes → the brother's payment and screening withdrawn → an approval resting on the old fact refused and turned into a decision → executing it blocked → the deck slide sent back → Nova explains who pays, citing the live fact. *Checked in the browser 29 Oct (offline, `e2e/deal_flow.py`, 15/15): meeting page → Deal desk; Compliance first; A1 "Carry it out" blocked naming F3; Layla can't answer Ahmed's card; the old wording refused; A2 rests on F7+F4 and runs once; Priya marks the check reviewed; Nova cites F7 and "F3, since replaced"; 1280 and phone width.*
- [x] Split by department inside the session, not across sessions: move the compliance rules to `agents/compliance.py`, payments to `agents/finance.py`, Form F to `agents/operations.py`, send-backs to `agents/review.py`; the correction engine in `office.py` calls them. Behaviour unchanged, tests green.
- [x] Compliance: every party screened, including a third-party payer; a source-of-funds view with the missing proof; a cash-report draft at AED 55,000 or more, waiting for the officer. *Checked in the browser 29 Oct (offline, `e2e/deal_flow.py` 3a–3i): Karim and Tariq up for screening, only Priya records clear/possible match (a match needs its entry); source of funds with numbers, quotes and 4 missing proofs, "Received" files the proof with Records; cash AED 260,000 → report draft and a filing task for Priya, a goAML reference required; a correction sends the draft back and withdraws the task. No sanctions list is connected: a person records the result.*
- [x] Finance: expected payments per deal, each with its quote; a person marks received; overdue flagged; releasing money always needs a person. *Checked in the browser 29 Oct (`e2e/deal_flow.py` 4a–4f): payment with its quote and due day ("next week" → Thu 5 Nov); "Received" needs Ahmed and a reference and files a receipt with Records; "Approve release" is Ahmed's approval on the payment's words, refused with the reason after the correction. Overdue: tested in code only (the demo has no payment past its day).*
- [x] Operations: Form F filled from live facts, stopping before Submit; a replaced fact blocks it with the reason; the transfer checklist with who is waiting. *Checked in the browser 29 Oct (`e2e/deal_flow.py` 5a–5g): "Prepare Form F" → plan v1 from live facts, passed review, Seller and passport left for Joseph; only Joseph marks it submitted; the correction sends v1 back naming slide 5 and withdraws its submit step; v2 says Karim pays; a portal reference is required; the transfer checklist shows who each step waits on and Joseph ticks it.*
- [x] Review: no draft resting on a replaced fact reaches a person; each send-back names the fact and its replacement. *Checked in the browser 29 Oct (6a, 5c): send-backs name the slide, the old fact and its replacement; every new draft is checked when made (`review.passed`, or sent back at once: tested in code).*
- [ ] A Deal desk screen (one deal: checks, payments, paperwork, send-backs); each department's 3D floor shows its work.

## 4. Records

**Goal:** every number Nova or the owner asks for is computed from records, and every document can be found.

- [ ] "What did we sell last month", commission, pipeline and top broker answered from records, never estimated, citing sale ids.
- [ ] Documents filed against the right deal and found again by kind, party, date or deal.
- [ ] Answers Nova delegates come back with their records; a question the records can't answer says so.
- [ ] A Records screen (archive and ledger); the Records floor shows it.

## Starting message (paste into a new chat in the diwan-hackathon folder, with the session name filled in)

> You are the **<session name>** session for Diwan. Read docs/handoff.md, docs/rooms.md and docs/sessions.md (for
> Front desk & Sales also docs/front-office.md and docs/knowledge.md). You own that session's row in
> docs/sessions.md; don't edit other sessions' files, and treat shared files as rule 5 says. Build your checklist in
> docs/sessions.md top to bottom, checking each item in the browser with screenshots and reporting item by item.
> Follow "Rules for every session" exactly: nothing outside the checklist without my OK, tests offline, and send me
> the end-of-day report.

## Where sessions meet (the only links between them)

| From → to | Through | Meaning |
|---|---|---|
| Marketing → Front desk & Sales | `content.made` published (listing ref, angle) | comments and DMs on it open leads tagged with the post |
| Front desk & Sales → Marketing | lead and viewing counts per post and angle | the strategy ranks angles by enquiries |
| Front desk & Sales → Deal desk | `fact.created`, `fact.superseded` from the Scribe | the correction engine runs; Compliance hears money facts first |
| Front desk & Sales → Deal desk | a deal reaching Offer accepted | Form F starts |
| Deal desk → everyone | `check.raised`, `decision.needed`, `review.returned` | money-related work waits for the officer; stale work goes back |
| Front desk & Sales ↔ Records | `records.delegate()` from Nova | numbers and documents answered from records only |

A new event shape at a meeting point is written in the changelog before either side builds it.

## Changelog (one line per shared change or new event shape)

- 29 Oct (Deal desk): every draft is checked by Review when made (`review.passed`, or `review.returned` at once); the Form F plan is now a draft (kind "Form F") with a "Submit Form F D… on the DLD portal" task for Joseph resting on its facts, remade after a correction; Joseph's submission starts transfer-checklist tasks (agent `transfer`, `waiting_on`). Nova's "prepare Form F" event sequence gains draft.made, review.passed, task.created (test_nova.py updated).
- 29 Oct (Deal desk): Compliance screens every party as a task for Priya (`task.created` may carry `person`, `role`, `draft`; `task.done` may carry `result`); payer screening moved from the payment rules to Compliance, so task numbers shift (expectations updated in `test_nova.py`, `test_scribe.py`, `test_frontdesk.py`, `evals.py`). Priya marking a proof received calls Records' `office.file_document(kind=…, deal=…)`. `office.add_task` takes `props`.
- 29 Oct (Deal desk): `nova.formf_plan` moved to `agents/operations.py` (Nova calls it there); the correction engine's department work moved out of `office.py` into `agents/compliance.py, finance.py, review.py`. Same events, same order. Spec: `docs/deal-desk.md`.
- 29 Oct (Front desk & Sales): new event `qualify.open` (a customer's question Rania could not answer while qualifying; it goes on the broker's qualified-lead card); `qualify.answer` may carry `unsure: true`; each qualification question has `strict` (owner's choice: must answer / "not sure" is OK / optional). Small additions to events.py, graph.py, app.py.
