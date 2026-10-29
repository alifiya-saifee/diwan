# Diwan: how the work is split between sessions

Two sessions build Diwan in parallel until the hackathon deadline (4 Nov 2026, 9 PM ET). Each owns a set of rooms and
files, builds them to the contract in `docs/rooms.md`, and follows the rules in `docs/handoff.md` section 2. Read
`docs/handoff.md` first.

## Rules for both sessions (the product owner's standing instructions)

1. **No feature without a reason.** Every change states which row of `docs/rooms.md` or which checklist item below it
   fulfils. Anything that is on neither is not built without the product owner's OK, however useful it looks.
2. **Work the checklist top to bottom.** The items are in priority order: safety first, then what the demo shows,
   then the rest. Finish and check one before starting the next, so if time runs out, what is missing is the least important.
3. **Working means working for a person.** Each item is checked in the browser the way a user would use it, with a
   screenshot, including what happens when something is missing, wrong or at real scale. Passing tests alone is not done.
4. **Efficient output.** Each agent produces exactly the output its contract names, from its sources, cited; no extra
   steps, no repeated model calls (use the saved replies), the cheapest reasoning level that keeps quality.
5. **End-of-day report** to the product owner: every checklist item marked checked in the browser / tested in code
   only / not done, with the reason; the day's model spend; anything that needs their decision.
6. **Target: everything on the checklist working by the end of 29 Oct.** If an item cannot be finished properly, say
   so early rather than shipping it half-done.

## The split

| | Marketing session | Front office session |
|---|---|---|
| Departments | Marketing (the content studio) | Front desk (Nova, Lobby) and Sales (WhatsApp, Instagram DMs, portals, leads), the knowledge store and catalog; the back office after its core work |
| Owns these files | `agents/studio.py, qa.py, strategy.py, kpis.py, analysis.py`; `brand.py, brand_api.py, brain.py, learn.py, costs.py, docgen.py`; `providers/instagram.py, heygen.py, meta.py`; `web/studio.html, graph.html`; `e2e/studio_flow, brand_flow, learn_flow, memory_flow, floor_flow, views_flow` | `agents/reception.py, scribe.py, nova.py, lobby.py, records.py`; `inbox.py, leads.py, knowledge.py, knowledge_api.py, playground.py`; `providers/portals.py, aisensy.py, whatsapp.py`; `web/inbox.html, knowledge.html, catalog.html, index.html, meeting.html, team.html, settings.html`; `e2e/office_flow, knowledge_flow` |
| Shared (small changes only, commit only your own hunks, say so in the changelog below) | `app.py, events.py, graph.py, office.py, people.py, demo.py, config.py, agents/charters.py, agents/runner.py, providers/chat.py, web/app.js, web/app.css, web/office3d.html` | same |

## Marketing session: make the studio start working for real

**Goal:** on the main demo database, through the screens, a person can run the whole studio with the live model and
it is right every time.

Definition of done (checked in the browser, with screenshots):
- [ ] Brand: learn Diwan Realty from the demo profile, confirm the cards, save the brand; it shows in the Brand brain and the memory graph.
- [ ] Run a listing: research (trend cards with sources; competitors from the spreadsheet import), an idea, 3 scripts on different angles, each passing review, all in the brand's voice and sign-off.
- [ ] Ask for a change to one script; only it is rewritten; pick it.
- [ ] Production: film list task to the broker; upload a take; take check; captions burned in; post text with the permit and brand hashtags; covers.
- [ ] Publish request reaches the owner; with Instagram connected, approving publishes (otherwise it says what it needs).
- [ ] A comment on the post reaches Rania with `source: post <id>, angle` (needs the Front office session's intake; agree the event shape with them).
- [ ] Strategy ranks angles by enquiries per post once Front desk reports leads per post (rooms.md, "hands back").
- [ ] Every 3D view and the Studio page: no overlaps, no sample data, works at 1280 wide.
- [ ] Spend for one full run is measured and shown; the model runs at the cheapest reasoning level that keeps quality.

Open items it inherits (handoff.md section 7): trend cards not linked to the scripts that use them; near-duplicate
hook lines; web search cost unverified.

**Paste this to start it:**
> You are the Marketing session for Diwan. Read docs/handoff.md, docs/rooms.md and docs/sessions.md. You own the
> Marketing rows in docs/sessions.md; don't edit the Front office session's files. Build the Marketing definition of
> done in docs/sessions.md, one item at a time, checking each in the browser with screenshots and reporting item by
> item. Follow "Rules for both sessions" exactly: nothing outside the checklist without my OK, work top to bottom, and
> send me the end-of-day report. Run repeated tests offline (DIWAN_OFFLINE=1); use the live model only for a final
> pass, and tell me the cost.

## Front office session: front desk and sales working end to end

**Goal:** a customer on the sandbox WhatsApp line (and Instagram DMs) is answered, qualified, assigned, briefed and
booked correctly, from the knowledge store and catalog, with people in control.

Definition of done (checked in the browser, with screenshots):
- [ ] **Fix first:** Rania uses `knowledge.search()` only, so internal-only items never reach a customer (handoff.md issue 1).
- [ ] **Fix first:** the feed sync keeps a listing's status and shows an accepted price as "waiting for the portal" instead of reverting (issue 2).
- [ ] Knowledge and catalog: the header search box on every screen; pages work at phone width; then commit the knowledge work.
- [ ] Intake: duplicates ignored, bursts merged, spam to "not a lead", source tagged (including posts from Marketing).
- [ ] Profiler: tags with quotes, persona checklists, Qualified only when complete and the customer agreed.
- [ ] Rania's three stages: discovery, one question at a time, waiting for the broker; booking in free slots; handover on everything that isn't hers.
- [ ] Dispatcher, Briefer, Lead desk: assignment, a 5-line brief, cards with due times, overdue, the Pool, notices.
- [ ] Nova: the morning briefing, questions answered with citations, Lobby jobs with read-back.
- [ ] The correction moment works end to end across Compliance, Finance, Operations and Review.
- [ ] Reports leads and viewings per Marketing post and angle (rooms.md, "hands back").

**Paste this to start it:**
> You are the Front office session for Diwan. Read docs/handoff.md, docs/rooms.md, docs/sessions.md,
> docs/front-office.md and docs/knowledge.md. You own the Front office rows in docs/sessions.md; don't edit the
> Marketing session's files. Fix the two "fix first" items, then build the Front office definition of done in
> docs/sessions.md, one item at a time, checking each in the browser with screenshots and reporting item by item.
> Follow "Rules for both sessions" exactly: nothing outside the checklist without my OK, work top to bottom, and send
> me the end-of-day report. Run repeated tests offline (DIWAN_OFFLINE=1); never loop tests against the live model.

## Where the two sessions meet

| Meeting point | Marketing produces | Front office produces |
|---|---|---|
| A post's comments and DMs | the post with its listing ref and angle | a lead tagged with that post and angle |
| Lead attribution | — | leads and viewings per post and angle |
| Listings | reads them (permit, features, price) | masters them (feed, proposals) |
| Brand | masters it (voice, sign-off, never-use words) | Rania signs off in it and avoids its never-use words |
| Knowledge | proposes cards learned from documents | owns the store, confirmation and `knowledge.search()` |

Agree any new event shape at a meeting point in the changelog below before building it.

## Changelog (append one line per shared change)

- 29 Oct: split agreed; rooms.md and sessions.md written; rules for both sessions added (no feature without a reason, priority order, end-of-day report).
