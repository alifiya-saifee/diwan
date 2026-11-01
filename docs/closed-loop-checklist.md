# Diwan: what is there and what needs to be there

The [Closed-Loop Office Spec](closed-loop-spec.md), line by line, against the code as it stood on 31 Oct 2026.

**How to read each line**

- `[x]` **Built.** It works in the code, with a screen or a route. Any note says what to watch.
- `[ ] 🟡` **Partly.** "There" is what exists now; "Needed" is exactly what is missing.
- `[ ]` **Not built.** "Needed" is what to build.
- **(outside)** needs an account or service from outside Diwan. The code can only be finished or proven once that exists.

Tick a line only when it works and has a test. Update this file in the same change as the code.

**How far to trust it.** Five read-only audits traced every spec item through the code, and the most serious findings were checked again by hand. The code was read, not run, for this checklist. The last test run was 494 passed, 1 failed on an expired date and 2 files that need macOS. Function names are given rather than line numbers because the code is still moving.

**Contents:** [Where it stands](#where-it-stands) · [Fix first](#fix-first-these-are-wrong-today) · [Decisions](#decisions-needed-before-building) · [Suggested order](#suggested-order) · [Spine](#the-spine) · [Rules in every room](#rules-in-every-room) · [PAs](#pas) · [Access](#who-sees-which-rooms) · [1 Front Desk](#room-1-front-desk) · [2 Sales](#room-2-sales) · [3 Deal](#room-3-deal) · [Uploads](#uploads-and-their-checks) · [4 Operations](#room-4-operations) · [5 Finance](#room-5-finance) · [6 Compliance](#room-6-compliance) · [7 Review](#room-7-review) · [8 Records](#room-8-records) · [9 Lobby](#room-9-lobby) · [Marketing](#marketing) · [Deal types](#each-deal-type-step-by-step) · [Unhappy paths](#when-things-go-wrong) · [Part 4 cases](#cases-from-part-4) · [Listing upkeep](#listing-upkeep) · [Stages](#case-stages) · [Events](#event-catalog) · [Settings](#owner-settings) · [Office answers](#answers-only-the-office-can-give) · [Outside accounts](#outside-accounts-needed) · [End-to-end test](#the-end-to-end-test) · [Scenarios](#seed-scenarios) · [Definition of done](#definition-of-done-by-room) · [Later](#later)

## Where it stands

**Updated 31 Oct, after the Front Desk and Sales rooms, and the Deal, Operations, Finance and Compliance rooms, were built** (docs/deal-desk.md item 18, decisions in [open-questions.md](open-questions.md)). A ticked line in those rooms may still say what was missing when it was written: the tick is the current state. The Lobby followed. Checked with 860 tests and `e2e/lobby_flow.py`, `e2e/rooms_flow.py`, `e2e/deal_flow.py` and `e2e/property_flow.py` in the browser. The upload tables and each deal type's step tables were not re-marked line by line.

| Area | Built | Partly | Not built |
|---|---:|---:|---:|
| The spine | 4 | 15 | 6 |
| Rules in every room | 7 | 8 | 4 |
| PAs | 38 | 29 | 34 |
| Who sees which rooms | 2 | 5 | 1 |
| Room 1: Front Desk | 25 | 8 | 2 |
| Room 2: Sales | 34 | 4 | 1 |
| Room 3: Deal | 25 | 13 | 5 |
| Uploads and their checks | 2 | 28 | 22 |
| Room 4: Operations | 12 | 9 | 3 |
| Room 5: Finance | 24 | 2 | 3 |
| Room 6: Compliance | 25 | 7 | 7 |
| Room 7: Review | 0 | 9 | 12 |
| Room 8: Records | 3 | 14 | 11 |
| Room 9: Lobby | 12 | 2 | 0 |
| Marketing | 25 | 13 | 3 |
| Each deal type, step by step | 1 | 34 | 7 |
| When things go wrong | 0 | 12 | 8 |
| Cases from Part 4 | 0 | 9 | 8 |
| Listing upkeep | 0 | 1 | 6 |
| Case stages | 5 | 7 | 8 |
| Event catalog | 5 | 21 | 15 |
| Owner settings | 0 | 11 | 1 |
| Answers only the office can give | 0 | 1 | 12 |
| Outside accounts needed | 0 | 0 | 12 |
| The end-to-end test | 0 | 2 | 6 |
| Seed scenarios | 0 | 6 | 5 |
| Later | 6 | 4 | 7 |
| **Total** | **240** | **275** | **222** |

Also open: 67 lines in the two lists below, 15 faults to fix first and 52 decisions. The line-by-line detail, with the file and line for every requirement, is in [closed-loop-checklist-detail.md](closed-loop-checklist-detail.md).

The sale itself runs: a client can go from a first WhatsApp message to a signed Form F, a marked payment and a closed sale, and a correction withdraws exactly the work that rested on the old words. What is missing is the joining-up. There is no event subscriber system, no Stuck board, no compliance gate, no Review queue, no personal PAs and no notification levels, and the listing side of the business (seller sign-up, permits, availability checks) barely exists. None of the 8 end-to-end boxes passes in full today.

## Fix first: these are wrong today

These are faults in what exists, not missing features. Each one can cause real harm once real clients are on the system.

**Compliance and money**

- [x] **A screening "possible match" closes itself.** `compliance.record_screening` marks the task done whatever the result, and `operations.closing` counts only open tasks, so a deal with a recorded hit can close. Needed: a hit stays open as a hold until the compliance officer resolves it, and blocks closing.
- [x] **Nothing stops a person going past Compliance.** `operations.submitted`, `finance.mark_received`, `approve_release` and `desk_stages.move` never read Compliance. Form F can be submitted with parties unscreened. Needed: the clearance gate in [Room 6](#room-6-compliance).
- [x] **A receipt is issued at once for any payer.** `finance.mark_received` files it immediately, and `invoices.receipt_pdf` prints the customer as payer even when a third party paid. That is a false record. Needed: hold the receipt for third-party or over-threshold cash, and print the real payer.
- [x] **A marked payment cannot be undone.** Needed: undo with a reason, kept in the log.
- [ ] **Any file starting `%PDF` counts as a signed form.** `agency_forms` looks at the first bytes only, so an unsigned or wrong PDF passes. Needed: check it is the right form and signed, or have a person confirm it.
- [x] **Form F can be submitted unsigned.** `agency_forms.unsigned` covers Forms A, B and I only. Needed: include Form F's own signatures.
- [x] **`/proof` marks a document received with no file.** `deal_desk` takes a title only. Needed: require the file.
- [x] **"By Monday" gets no due date.** `finance.due_date` treats Monday (index 0) as false. Needed: test for `None`, and add a Monday test.
- [x] **Payment questions always go to Omar.** `finance.payment_rules` hard-codes `"to": "omar"`. Needed: use the deal's broker.

**Messages to clients**

- [x] **Document reminders ignore the rules.** `documents.sweep` sends free text at fixed hours 09 to 20, with no "stop" check, no 24-hour window check, no quiet hours and no Friday prayer. Needed: the same checks as `nudge.allowed` and an approved template outside 24 hours.
- [ ] **Follow-ups after a visit send the general text.** `nudge.sweep` looks the visit up as `viewing:<id>`, but appointment nodes have no such prefix, so it is never found and the visit message never goes out. Needed: look it up by its id, and add a test.
- [ ] **A scheduled post goes out whatever has changed since it was approved.** `studio.publish_due` checks the cut, the text and the connection, not whether the listing sold or its price or permit changed. Needed: check again just before posting and stop it with the reason.
- [x] **"Stop" does not reach everything.** `documents.sweep`, `change_from_calendar` and `send_link` do not check it, and it only reads English and Arabic. Needed: one check before every automated send.

**Permissions**

- [ ] **The owner's "Viewing as" records actions under the other person's name.** The owner can mark money received as Ahmed or clear a name as Priya, and the log names them. Needed: log the real person, or block person-only actions while viewing as someone else.
- [ ] **`POST /api/approvals` accepts any approver name**, including an agent's, and `POST /api/approvals/{aid}/execute` has no approver check. Owner-only today. Needed: a person only, and the same check as the desk route.
- [x] **Nova changes Settings.** "Set X to autopilot" and the briefing time work with no owner check. The spec says no PA changes Settings. Needed: refuse, or send for the owner's confirmation.
- [x] **Nova's refusals have gaps.** `REFUSE` has nothing for marking money received, clearing a hit, signing or sending bank details. Needed: hard-coded, logged refusals for all of them.
- [x] **Charter wording is too loose.** `pay` says never "without evidence", which implies it may with evidence. `screen` lists "screen" as allowed alone with output "Match or clear". Needed: tighten both before any agent runs them.
- [ ] **`DIWAN_AUTH=off` opens everything.** Needed: keep it for tests only, and refuse to start with it on a public address.

**Wrong on screen**

- [x] **Inbox still shows "Qualified · step 3 of 8".** `web/inbox.html` counts the stage position. Needed: "Qualifying 3/8" from the form.
- [ ] **Rania says "with Hamza" while the broker is Omar.** `reception.book` uses the listing's agent and leaves the deal's broker unchanged. Needed: one name, and decide who attends.
- [x] **Screening task reads "named by Ali Rahman".** `compliance.parties`. Needed: name the Fact or room that raised it.
- [x] **Deals vanish from the overview funnel.** `deal_desk.STAGES` is a second list without Offer accepted, Reservation, SPA, Oqood, Contract, Ejari or Move-in. Needed: one stage list.
- [ ] 🟡 **A failed WhatsApp send makes no Task.** `reception._send` shows the failure in the Inbox only and `reminders` only logs it. Needed: a broker call Task.
- [x] **`documents["company"]` is a dead setting.** It can never be used because `parties()` never returns a company. Needed: wire it up with company buyers.

**Reliability**

- [x] **One error stops every timed job without a word.** `app.morning_loop` guards only the listing feed, so an exception in any sweep ends the brief, reminders, follow-ups and scheduled posts until a restart. Needed: guard each job, log the failure and carry on.

**Real data in the demo**

- [ ] **The demo office holds a real brokerage's data.** In `~/.diwan/diwan.db` and the tracked `data/try.db`: website `samplebrokerage-sc.com`, 56 website listings, 15 knowledge cards, 5 products and a brand call-to-action naming Sample Brokerage, plus `tapes/mbrand/*`, and 4 real Dubai competitor accounts. The spec requires fictional data, and the log cannot delete. Needed: a decision (see D3).
- [ ] **Brand name typed "Diwan Realty".** A value in the data, not code. Needed: retype "Diwan Realty" in Setup.
- [ ] **Permit set to "no" in the data, which turns off every permit check.** Needed: set it to Yes in Setup, and see D12.

## Decisions needed before building

The spec's own rule says: where parts disagree, build neither side until answered. Each answer goes in a new `docs/open-questions.md`, which does not exist yet.

**Biggest: these change how everything is built**

- [ ] **D1. Event names.** The spec says only its names may exist. The code uses about 150, of which 5 match. The log is append-only, so old events cannot be renamed. Recommended: keep old events, add the spec's names for new work, and read both through a map.
- [ ] **D2. Stages.** The spec has one fixed list where any other name is a bug. The code has stages the owner can edit, by design, and the Inbox depends on them. Recommended: a fixed internal stage, with the owner's label on top.
- [ ] **D3. Real data in the demo.** Options: a new clean demo database, or cover it with new events. If it matters, also remove it from git history. Recommended: a new clean database.
- [ ] **D4. Delete vs keep forever.** Room 8 says nothing is deleted, but "delete on request", "who may delete" and "retention clean-up" need deletion, and database triggers forbid it. Options: encrypt client data and destroy the key, or keep personal data outside the log. Needs legal advice.
- [ ] **D5. Are qualifying answers Facts?** Today they sit beside Facts and are overwritten in place, so a corrected budget triggers nothing. Recommended: yes, make them Facts.
- [ ] **D6. Withdrawn or reopened?** The spec says reopened; the code withdraws and creates new work, and only for open tasks. What should happen to a finished screening or a marked payment that rested on the old Fact?
- [ ] **D7. Does every Fact go to Compliance first, or money only?** The spec says every Fact; the code does money only, so "it's 3.1M not 2.8M" never reaches Compliance. Recommended: every money, identity, price and finance Fact.
- [ ] **D8. Does Review stand before every approval?** It would change every approval path. Does Studio's room-lead check count as Review?
- [ ] **D9. Commission and closing.** The stage table needs commission received before `closed_won`. The failure table and end-to-end box 8 close the Case and report commission due. The code requires it paid. Box 8 cannot pass until this is decided.
- [x] **D10. Name clash: "Lobby".** Screens now say "Requests board" for the staff board; the spec's room is the Lobby. The board's `lobby.*` events stay, since the log can't be rewritten ([open-questions.md](open-questions.md)).

**Sales**

- [x] **D11. Does a booked viewing need checks first?** Form B "before the first viewing" and "is it still available?" before any booking would both block Rania's instant booking.
- [ ] **D12. Permit.** The spec says default Yes. The code is yes until answered, for any industry, and a person's "no" turns off all checks. Should "no" be refused for UAE real estate?
- [x] **D13. Who is the Sales lead?** An agent, Rashid, or both? The code's `sales` charter is a meetings role.
- [x] **D14. Call timer.** 10 minutes in the spec, 15 in the code and tests. Automatic reassignment in the spec, an overdue notice then a claim Pool at 60 minutes in the code. Replace, or keep both?
- [x] **D15. Heat score.** The spec has a formula (budget fits, under 60 days, finance ready); the code has owner triggers (pick, viewing, qualified, call). Replace or combine?
- [x] **D16. Which brokers see which chats?** The spec says a broker sees their own Cases. Today all Sales staff see all chats and deals.
- [x] **D17. After "stop", if the client writes again.** The spec lets brokers reply. Rania still replies automatically. Is that "automated"?
- [ ] **D18. New fits to past clients.** The spec needs the broker's yes. `nudge` sends them unprompted, and a test expects that.
- [ ] **D19. Same person on two channels.** Instagram gives a username, not a phone, so the "same phone" test cannot happen unless the client states a number. Redefine the test?
- [ ] **D20. Several offers vs one deal per listing.** `deal_property._holder` allows one live deal per listing.
- [ ] **D21. Lost reasons.** "Sold elsewhere" is used in listing upkeep but missing from the dropdown list. Can a Lost deal come back? The code allows it; the spec says closed Cases never reopen.
- [ ] **D22. Stage gaps.** `converted` and `valuation` are targets but not stages; `not_a_lead` has no ending; `nurture` is both a target and a side state.

**Deal and Operations**

- [ ] **D23. NOC deadlock.** Room 4 requests the NOC after `deal.ready_for_transfer`, but the stage table and Room 3's exit need it before. As written it can never finish.
- [ ] **D24. Stage `cleared` has two triggers:** documents in, or `compliance.cleared`.
- [ ] **D25. When are Forms A and B made?** The spec says at listing and before the first viewing; the code makes them at conversion.
- [ ] **D26. Listing template trigger.** The command fires on `case.converted`, but a seller signing has no conversion.
- [ ] **D27. When does a rental close?** Step 7 says at move-in, but the stages carry on to move-out.
- [ ] **D28. When does an off-plan deal close?** The spec says at handover; the code closes before it, on purpose.
- [ ] **D29. Order of rental cheques.** Before the contract (step 3), or after signing (Room 4)?
- [ ] **D30. What does `listing.ready` mean?** "Your listing is live" in one table, "Photo date" in another.
- [ ] **D31. What is Form F?** A signed MOU, a portal submission, or both? Needs the conveyancer.
- [ ] **D32. Booking paid only to the developer**, yet Finance must mark it received. What counts as received?
- [ ] **D33. Who sees documents first?** The spec says Review; the code sends them to the compliance officer. Room 3 says Deal does not judge identity.
- [ ] **D34. Keep rejected uploads?** The Document record implies yes, for overrides. The code deliberately never keeps them.
- [ ] **D35. Follow-up ladder.** 24/48/72 hours in the spec; N reminders every N days in the code. Expiry warning 30 days in the spec, 60 in the code.
- [ ] **D36. Agent names.** Scheduler or Transfer tracker; Deal manager or Deal coordinator; Records clerk or Archivist.
- [ ] **D37. Reject wording** differs between Room 3 and Part 3. Pick one.

**Finance, Compliance, Records, Marketing**

- [ ] **D38. Mark received order.** Saving sends the receipt and unblocks Deal, but Compliance must go before the receipt. Does a held third-party deposit unblock Deal?
- [ ] **D39. Part-payers.** "My brother will pay part of it" needs two live payers. The code treats two payers as a contradiction.
- [ ] **D40. Deposit cheque held, returned or refunded.** Part 3 says it is covered, but no such row exists. The code defaults to "the seller's agency, in trust".
- [ ] **D41. Screening timing.** After KYC in the spec; from the first money or party Fact in the code, which is stricter. Keep the stricter one?
- [ ] **D42. `screening.hit` audience.** "Compliance officer only", yet the owner sees all and Nova flags holds.
- [ ] **D43. Messages outside 24 hours.** Through Review for approval, or template or broker Task?
- [ ] **D44. Who asks the client for documents?** Compliance PA, Deal's portal, or Deal coordinator's PA?
- [ ] **D45. Renewal owner.** Records raises a Sales Task in Part 1; the code makes an Ops task at closing. Daily scan or monthly?
- [ ] **D46. Marketing events** are in Part 5 but missing from Part 4's "only" list, as are the six listing-upkeep events. Add them to the list?
- [ ] **D47. "Paused" on a live post.** Instagram's connection cannot hide or delete. Built for now as a status and a Task for a person; confirm.
- [ ] **D48. Access table has no Marketing column.**
- [x] **D49. Meeting mode.** The Front Desk command includes it, but the status note calls the meeting agent Phase 2.
- [ ] **D50. Morning brief.** 07:30 or the person's start time? Top 3, 6 sections, or 5 before "more"? The broker sweep is 08:30 in the spec, shift start minus 60 in the code.
- [ ] **D51. Owner room.** `transferred` has two owners, "Finance + Ops", against "a single owner room".
- [ ] **D52. Names in the scenarios collide.** Priya (compliance officer) sells a flat, Ahmed (Finance) is a tenant, and Layla (the owner in code) is treated as staff in the spec. Rename the scenario people.

## Suggested order

1. **Fix first** list above, because it is about safety and is small.
2. **Decisions D1 to D10**, an hour with the owner.
3. **Spine** (spec's Command 0): owner room, tasks and approvals, event consumers, Stuck board, room filters.
4. **Compliance gate, Review queue and notifications.** This is where "marketing lead name waiting for user name" lives.
5. **Department PAs**, built on the above. This was step 3 of the plan agreed earlier; it moves after the spine because PAs need Tasks, notifications and role filters to stand on.
6. Then rooms in deal order: Sales exit, Deal, Finance, Operations, Records, Lobby. Zoom and phone calls stay last.

## The spine

### Objects

- [ ] 🟡 **Person.** There: a graph node keyed by name, staff in `people.py`. Needed: one record for every client, owner, broker, landlord and developer contact, with phone, email, WhatsApp, language, consent and a stop flag per person, not per deal.
- [ ] 🟡 **Case.** There: the deal node, with stage and broker; lead and deal are already one record. Needed: `owner_room`, `created_from` as a field, a real Person link, and a new Case for a returning client's second intent (today one deal per chat). Only the owner room may advance the stage.
- [ ] 🟡 **Fact.** There: quote, speaker, deal, time, superseded by, never edited, and WhatsApp words become Facts through `scribe.hear`. Needed: a source field (chat, call, meeting), and qualifying answers as Facts (D5).
- [ ] 🟡 **Task.** There: agent, `needs_person`, `rests_on`. Needed: `owner_room`, `due_at` on every task, `waiting_on` from the fixed list, `rests_on` on transfer tasks (many are empty, so a correction cannot reach them), and a real "working" status (nothing ever sets it).
- [ ] 🟡 **Document.** There: uploads in `docs.*` events and filed papers in `document.filed`. Needed: one record with the fields under [Uploads](#uploads-and-their-checks).
- [ ] 🟡 **Approval.** There: pinned through `rests_on`, stale ones refused. Needed: the same pin on the yeses that are not Approvals today (discount, scripts, publishing), and a Review step first.
- [ ] 🟡 **Event.** There: append-only with database triggers, actor, deal, time, cause. Needed: `fact_ids` with versions on every event, and subscribers.

### The three rules

- [ ] **Rule 1: rooms write Events, never call each other.** `office.py` calls compliance, finance, operations and review directly, and `desk_stages` calls `agency_forms`. Needed: a subscriber registry, handlers per room, and a move of those calls onto it.
- [ ] 🟡 **Rule 2: a Case moves only on a complete checklist.** There: an agreed-price gate and the closing checklist for Won. Needed: an exit checklist per stage, a Review check and a person's approval; forward jumps are free today.
- [ ] 🟡 **Rule 3: correction rule.** There: dependent open tasks withdrawn, unrelated work untouched, stale approvals refused. Needed: see [Correction rule](#correction-rule).

### "Where it most likely breaks"

- [x] **Lead and deal in different tables.** Not a problem here: same deal node, same id, Facts stay.
- [ ] **Rooms call each other's functions.** Still true (Rule 1).
- [x] **Tasks have no `depends_on_facts`.** It exists as `rests_on`. It is not filled on every task (see Task above).
- [ ] 🟡 **Reminders in several places.** There: five sweeps in `app.py` (`lobby.chase`, `documents.sweep`, `leads.sweep`, `nudge.sweep`, `reminders.sweep`). Needed: one service, with a once-only key on `documents.sweep`.

### Command 0

- [ ] 🟡 1. One Case table: see Case.
- [ ] 🟡 2. Facts: see Fact.
- [ ] 🟡 3. Tasks: see Task.
- [x] 4. Approvals pinned, stale refused: `office.execute`, tested. Covers Approval objects only.
- [ ] 🟡 5. Event log. There: append-only. Needed: subscriber registry, each room's declared events, and the Stuck panel.
- [ ] **HQ Stuck board.** Only a "stuck" number on the Deal page exists. Needed: events with no taker, overdue Tasks, and agent Tasks unstarted after 5 minutes.
- [ ] 6. **Agents pick up open Tasks or say why not.** Only `formf` has a handler; Nova says "will pick it up" and nothing does, and a test expects that. The floor counts cards, not tasks, so the Screening analyst shows idle with T5 open. Needed: a worker, a blocker reason on each card, and the floor showing queued tasks.
- [ ] 🟡 7. Room stats and walls filtered. There: HQ wall screens filter agents and tasks, and walls filter for Compliance, Finance, Operations and Review. Needed: the top stats per room, a Facts stat, walls for Sales, Records and Front Desk, and the left wall showing the Facts this room's Tasks depend on.
- [ ] **One demo button.** "Karim corrects himself" shows everywhere except Marketing. Needed: HQ only.
- [x] Test: correction rule, in `test_nova.py`.
- [ ] Test: Playwright check that each room's stats differ.

## Rules in every room

### Notifications

- [ ] **One service with levels Now, Today and Brief.** `leads.notify` has kinds only, and Rania's chats, the request board and the Deal desk do not use it. Needed: one service, used by every room, including approval notices such as "marketing lead name waiting for user name".
- [ ] 🟡 **Now.** There: an on-screen notice in the Inbox, WhatsApp if `NOTIFY_TEMPLATE` is set (outside), and overdue to the owner then a Pool. Needed: real push, a repeat after 10 minutes, a set escalation, and Now alerts for Compliance hits and payment mismatches, which notify nobody today.
- [ ] **Today:** in-app, with a midday summary.
- [ ] **Brief:** reports only in the morning brief.
- [ ] 🟡 **Quiet hours for clients and staff.** There: `nudge.allowed` for follow-ups and reminders. Needed: every client message through it, staff messages unless Now, and Do not disturb.

### Who may do what

- [ ] 🟡 Agents message clients inside 24 hours or with templates. There: follow-ups and reminders obey. Needed: fix `documents.sweep`.
- [x] Only a person approves.
- [x] Only a person submits to a portal.
- [x] Only a person pays or releases money.
- [ ] 🟡 Only a person signs. There: the charter blocks it. Needed: a refusal in Nova.
- [x] Only a person marks money received (`finance.mark_received`, role check). Nova refusal missing (see Fix first).
- [x] Only a person files a report.
- [x] Only a person records a screening result. But see Fix first: a hit does not hold.
- [x] Agents hold no portal, bank or email passwords.
- [ ] 🟡 Each person sees only their rooms: see [Access](#who-sees-which-rooms).

### When something fails

- [ ] 🟡 Model call fails. There: falls back to rules and marks it. Needed: one retry first.
- [ ] No-subscriber Event or overdue Task shows on the Stuck board and in the brief.
- [ ] 🟡 Undeliverable message makes a broker Task. There: document reminders only. Needed: every send.
- [ ] 🟡 Every turn logs charter version, inputs, Facts and outcome. There: task, source ids, pack, evidence, usage. Needed: charter version and enough to replay without a tape.

## PAs

Today only Nova is real, and only the owner can reach her; a test expects staff to get 403. No personal PA, and no "PA" in the code, exists yet. Marketing has its own chat.

### The shared kit

- [ ] **Identity:** one PA per account, named by the person, with voice and tone.
- [ ] 🟡 **Scope.** There: `nova.brief(person)` is limited by person. Needed: `ask` and routing limited by role.
- [ ] **Chat box on every page**, talking to the signed-in person's PA ("Ask your PA"). The box is only on two owner pages.
- [ ] 🟡 **Push-to-talk.** There: a microphone on the owner's floor. Needed: for all staff, built for the phone.
- [ ] **Wake word** on desktop.
- [ ] **WhatsApp to the person's own number** (outside).
- [ ] 🟡 **Knowledge.** There: graph, request board, viewings, Records; says "I don't have that" and cites. Needed: Settings, the knowledge base, role filter, and the wording "not recorded".
- [ ] **Memory** as settings the person can see and edit; archived when they leave. Only briefing time exists.
- [ ] 🟡 **Morning brief.** There: per-person time. Needed: staff access and at most 5 items before "more".
- [ ] **"Remind me" becomes a Task with a due time.** "Remind me Thursday to call Sara" falls through to "Which team?".
- [ ] 🟡 **Drafting.** There: follow-ups, deck and Form F outside the PA. Needed: through the PA, with emails, each showing the Facts used.
- [ ] 🟡 **Doing.** There: routing and tasks. Needed: book viewings, fill portals up to Submit.
- [ ] 🟡 **Handoff.** There: "Tell Finance…" makes a task and a board post. Needed: the receiver sees it (the task has no deal, no notice goes out, and the board is owner-only).
- [ ] 🟡 **Escalation.** There: broker, owner, Pool for call cards. Needed: every overdue Task, through the person, their lead's PA, then Nova, from Settings.
- [ ] 🟡 **Hard refusals, logged.** There: submit, approve, release, file, suspicion. Needed: pay, sign, mark received, clear a hit, change Settings, send bank details.

### Nova (owner)

- [x] Greets on arrival, once a day, by name, with the top 3.
- [x] Morning brief across the rooms: urgent, today, pipeline, money, decisions, stuck, on the Nova page. Compliance flags, overdue money and unanswered calls are in it.
- [ ] 🟡 Weekly Monday numbers and one Lobby idea. There: the Lobby idea. Needed: the weekly numbers (Room 8).
- [x] "How's the Marina deal?"
- [x] "Who hasn't called Sara back?"
- [ ] 🟡 "Book my trip from this email." There: travel search with sources, ending in a draft for a yes, using Muse web search. Needed: reading email and holding a booking (outside).
- [x] "Draft a reply to Ahmed." A draft with Confirm; you send it, because no email is connected (outside).
- [x] "Remind me Thursday to call the developer."
- [x] Asks first before any send, booking, purchase or approval.
- [x] End of day: two-line wrap, after 5 PM.

### Broker's PA

- [x] Today's calls, viewings and quiet clients, on the Sales room and as the daily list at 08:30.
- [x] Call-now alerts, with the last 3 messages.
- [x] Reminder 15 minutes before a call at a time the client chose.
- [x] Drafts follow-ups (`followup.py`).
- [x] Nudges for a missing outcome, once, after 2 hours (a setting).
- [ ] Listing availability checks with owners. See Listing upkeep.
- [ ] 🟡 Permit and Form A expiry reminders. See Listing upkeep. The broker's own licence warning is built.
- [x] "Book Sara a viewing Thursday after 4." Read back, booked on a yes.
- [x] "What did Karim say about budget?" Their own clients only.
- [x] "Send him the 3 closest options." Shows the message, sends on a yes.
- [x] "Log: viewing done, liked the view, worried about service charges."
- [x] Asks before every client message.
- [ ] 🟡 End of day. There: the Sales room shows calls with no outcome. Needed: tomorrow's viewings confirmed with clients and owners.

### Sales lead's PA

Decided: the Sales lead is Rashid, a person, with his own PA (D13).

- [x] Team board: the Sales room shows Rashid every broker's day.
- [x] Told when a call is late; the call moves to the next free broker.
- [x] Daily list per broker.
- [x] Unassigned leads: the Pool.
- [x] Duplicate leads to merge, proposed on the Sales room.
- [x] Listing-to-buyer matches, on the Sales room. The client hears only on the broker's yes.
- [x] "Who's slowest to call back?", "Give Omar's leads to Hamza", "Which hot leads have no viewing?"
- [x] Asks before reassigning. Reassigning needs the broker, Rashid or the owner.
- [ ] 🟡 End of day: team numbers. There: the board. Needed: a wrap for him, and routing as a setting.

### Deal coordinator's PA

- [ ] 🟡 Missing items per deal: on the deal page.
- [ ] 🟡 Follow-up ladder: Rania's sweep.
- [ ] Rebuilds checklists after corrections.
- [ ] 🟡 Prepares Form F: a person presses it.
- [ ] Expiry warnings on uploaded documents.
- [ ] Waiting-on-outsider ageing.
- [ ] "What's missing for Sara's deal?", "Send Karim the portal link again", "Has the bank sent the final offer?"
- [ ] Asks before sending forms or overriding a failed check.
- [ ] End of day: every deal has a next step and date.

### Operations PA

- [ ] 🟡 Portal drafts ready: a work queue, Form F only.
- [ ] Trustee and NOC tracking; reminds clients what to bring; permit renewals; handovers and move-outs scheduled; recalls forms.
- [ ] "Book the trustee", "What does Sara need to bring?", "Prepare Ejari for 1204".
- [x] Every Submit is a person's.
- [ ] Asks before messages to developers or government.
- [ ] End of day: transfers marked, tomorrow confirmed.

### Finance lead's PA

- [ ] Invoices drafted at each trigger.
- [ ] 🟡 Due and overdue lists: on screen only.
- [ ] Reads proofs and flags mismatches.
- [ ] 🟡 Cheque dates: stored, no reminder.
- [ ] Instalment reminders.
- [ ] 🟡 Splits and payout list: co-broker split only.
- [ ] "What's outstanding from developers?", "What do I owe brokers?"
- [ ] "Mark AED 50,000 received" opens the form for the person.
- [ ] Asks before sending invoices and reminders.
- [ ] End of day: cash summary.
- [ ] 🟡 "What's waiting on me?" Payment tasks have no `needs_person`, so they do not show as Ahmed's.

### Compliance officer's PA

- [x] Corrections side by side: brief line.
- [ ] 🟡 Screening hits: open tasks only, so a recorded hit disappears.
- [x] Source-of-funds files: a work row.
- [ ] Holds with reasons.
- [x] Report drafts: cash only.
- [ ] 🟡 Threshold alerts: cash only.
- [ ] Fraud-guard flags.
- [ ] "Why is Sara's deal on hold?"
- [ ] 🟡 "What did she say about where the money comes from?" From recorded Facts.
- [ ] "Draft the cash report for Case 118." It queues a task with no handler.
- [ ] Asks before document requests and every draft report.
- [ ] End of day: open holds and hits.

### Marketing PA

- [x] Chat that drafts on request (`lead_chat.py`, `web/mchat.js`); needs a model key.
- [x] "Make 3 reels for 1204 Marina Crest."
- [ ] 🟡 "What worked for competitors this week?" No "this week" window.
- [ ] 🟡 Scripts to approve: request cards, not pushed.
- [ ] Listings needing content.
- [ ] 🟡 Competitor posts worth a look: pinned on the board, not a list.
- [ ] Yesterday's leads by source.
- [ ] Pauses posts on permit expiry or withdrawal.
- [x] Asks before every post.
- [ ] End of day: tomorrow's posts, anything paused with the reason.

### Rania (clients, not a PA)

- [x] Replies inside the 24-hour window.
- [x] Qualifies.
- [x] Books viewings.
- [x] Follow-ups on schedule.
- [ ] 🟡 Portal links and receipts: Deal room's work; see Room 3.
- [x] Advice on visas, returns, legal and tax goes to the broker.

## Who sees which rooms

Built at department level in `access.py`. The spec's table is finer, and "Status only" (done or blocked, no contents) exists nowhere.

- [x] **Owner:** all nine.
- [x] Sign-in, department pages and routes, forced identity, event filtering, client documents limited to the deal team.
- [ ] 🟡 **Broker.** Needed: own brief; own leads and deals (sees all today, D16); status only for Ops (sees all; Compliance is status only since 1 Nov); own commission; own Review items; own numbers; Lobby read.
- [ ] 🟡 **Sales lead.** There: all leads and deals. Needed: own brief, status-only views, team commission, team items, team numbers, Lobby read and propose.
- [ ] 🟡 **Deal and Ops staff.** There: Deal and Ops. There too: Compliance is status only. Needed: own brief, Sales read (403 today), status-only Finance, Deals in Records, Lobby read.
- [ ] 🟡 **Finance.** There: no Sales, all Finance. There too: payment flags only in Compliance, no client documents. Needed: Deal amounts only (sees quotes today), no Ops in the deal view, Money in Records, own brief, Lobby read.
- [ ] 🟡 **Compliance officer.** There: all Compliance. Needed: Sales read (403 today, a test expects it), read-only Deal and Ops, Payments, compliance files in Records, own brief, Lobby read.
- [ ] **Status-only views** in every room that needs them.

## Room 1: Front Desk

Built 31 Oct: `diwan/agents/frontdesk.py`, the Nova page, and the "Ask your PA" box on every page. Tests in `tests/test_front_desk_day.py`; in Chrome, `e2e/sales_room_flow.py` and `e2e/sales_room_people.py`.

### Modes

- [x] **Arrival.** First open of the day: greeting by name and the top 3.
- [x] **Brief.** Urgent first, on the page and on request.
- [ ] 🟡 **Dismissing an item** so it isn't repeated. Needed: a dismiss button.
- [x] **Meeting ("pocket").** "Hey Pocket" or "I'm in a meeting": silent, keeps the words, answers only to its name. Afterwards a summary, decisions and action items, each with the exact words. Action items go on the board for the person named, and what a client said goes on their file.
- [ ] 🟡 **Meeting from the calendar.** Needed: an owner's calendar event marked meeting, which needs an owner's calendar (outside). Listening uses the browser's own speech recognition, Chrome and Edge only.
- [x] **Ask.** Answers from records with the source; says "Not recorded" rather than guessing.
- [x] **Errand.** Ends in a draft; only a yes moves it on.
- [x] **Do not disturb.** Only Now gets through.
- [x] **Mode chip on screen.**

### Morning brief

- [x] Ready at 07:30 with the default 08:00 briefing time. It runs Monday to Saturday (a setting).
- [x] Urgent: overdue, Compliance flags, payments due, unanswered calls, payment fraud.
- [x] Today: appointments with the client's last words and what they care about.
- [x] Pipeline: new, hot, moved, by stage, and stuck over the owner's N days.
- [x] Money: payments marked, invoices, commission due.
- [ ] 🟡 Decisions. There: each with an Open link to the Deal desk. Needed: approve and send-back buttons on the card, which come with the Review room.
- [x] One Lobby idea.

### Errands, all ending in a draft the owner approves

- [x] Reminders as Tasks, delivered once at their time, outside quiet hours.
- [x] Email and messages: the draft. Sending needs a connected email (outside).
- [ ] 🟡 Travel and research: searches with sources when Muse is connected, compared in a draft. Needed: holding a booking (outside).
- [ ] 🟡 Calendar. There: viewings for brokers. Needed: the owner's own calendar (outside).
- [ ] Laptop or phone: files and forms. Needs a desktop app.

### Emits

- [x] `task.created`, from instructions and meeting action items.
- [x] `fact.recorded` when the owner relays what a client said ("Sara now wants 3 beds, not 2"), after a read-back. Spec name kept as `fact.created` (D1).
- [ ] 🟡 `approval.given` from the brief. Comes with the buttons above.

### Blocks on screen

- [x] Today · Urgent · Decisions · Pipeline · Money · Stuck · Errands · Reminders · Mode chip.
- [x] Lobby idea of the day.

### Personal PAs (the shared kit)

- [x] Chat box on every page, talking to the signed-in person's own PA.
- [x] Sees only what the role sees: a broker their own clients, Marketing no deals, and nobody can speak as someone else.
- [x] "What's waiting on me?" for every role.
- [x] Handoff through the board: "Tell Finance…" reaches that person. Never PA to PA.
- [x] Hard refusals, logged: pay, sign, submit, file, clear a hit, mark money received, change Settings, send bank details.
- [ ] 🟡 Naming a PA, voice and tone per person. Needed: a settings screen.
- [ ] WhatsApp to the person's own number (outside), and a wake word on desktop.
- [ ] 🟡 Memory as settings. There: briefing time, mode. Needed: call windows, tone, what to brief first, viewable and editable.

### Tests

- [x] Brief contents from a seeded day; meeting mode creates Tasks with quotes; no send without confirm.

## Room 2: Sales

Built 31 Oct: `diwan/sales.py`, the Sales room (`web/sales.html`), Settings → Sales rules, and the Inbox changes. Your four decisions are in: brokers see their own leads, 10 minutes then the next broker then the Pool, the longer form, instant booking kept.

### Channels in

- [x] WhatsApp (outside: real line).
- [x] Property Finder, Bayut, Dubizzle webhooks (outside: field names are guessed until partner docs arrive).
- [x] Instagram comments, keeping which post it was (outside: real account).
- [ ] Instagram DMs, Facebook, TikTok (outside: Meta and TikTok access).
- [x] Website form: `POST /api/portals/webform`, off until `WEBFORM_TOKEN` is set.
- [x] Phone call notes, walk-ins and referrals: "+ Add a lead".

### Discovery

- [x] Portal enquiry on a listing.
- [x] "Is this still available?": confirms, then live or invest. On a post with no listing named, she asks which one.
- [x] "I want to sell my flat": unit, deed holder, mortgage, price.
- [x] "Can you manage my apartment?": a landlord, with unit and tenant.
- [x] "Hi" or "price?": a warm hello and one question.
- [x] Company question: answered from knowledge.
- [x] Spam, job seekers and suppliers: the owner's reply, not a lead.

### Qualifying

- [x] Owner's form, one question at a time, versioned.
- [x] Buyer: area, type, beds, budget, cash or mortgage, pre-approval, timeline, purpose, residency.
- [x] Seller: unit, deed holder, mortgage, expected price, vacant or tenanted, timeline.
- [x] Tenant: move-in, cheques, company or personal, pets. Landlord: unit, current tenant.
- [ ] 🟡 Each answer as a Fact. There: the value with their exact words, beside Facts. Needed: D5, so a corrected answer triggers the correction rule.
- [ ] 🟡 Nationality only if Compliance needs it. There: optional. Needed: a trigger from Compliance.
- [x] Heat score from the owner's rules: shown on every lead, and makes a lead hot if the owner ticks it. Records uses it when Room 8 is built.

### PA behaviour

- [x] Call now: Rania promises the owner's number; off shift she doesn't promise minutes.
- [x] Broker alert with the last 3 messages and a one-tap call.
- [ ] 🟡 Push. There: a browser notice with the page open, WhatsApp with a template. Needed: real push (outside).
- [x] Not called in time: moves to the next free broker, the owner and Rashid hear; the Pool after an hour.
- [x] Call later: Task and calendar entry, reminder before it, confirmed to the client.
- [x] In their time zone when they name one ("2pm London time"), said back in Dubai time. Their phone's country is not used: a +44 number in Dubai is common.
- [x] Hot lead: the card, the heat score and Book a viewing.
- [x] Daily list for each broker at 08:30: who to call, who went quiet, who waits on options.
- [x] Follow-ups on the owner's schedule, never at night or at Friday prayer, never twice the same.
- [x] "Stop" stops everything automated; if they write again, a person answers. English, Arabic, Russian, Hindi, Chinese.

### Exit

- [x] Outcome after a call: follow up on a date, not interested with a reason from the list, no response. The lead shows "Outcome needed" until there is one.
- [x] Converted: the Convert step, with a link to the deal.
- [x] Every Fact carries over: lead and deal are one record.

### Blocks on screen

- [x] Call now queue · Hot leads · New leads by channel · Qualifying x/n · Follow-ups due today · Quiet clients · Each broker's day · Outcome needed, plus new listings for waiting clients and duplicates.

### Fix first in the spec

- [x] Qualified only when the form is complete; "Qualifying 3/8" everywhere.
- [x] The budget keeps their exact words on the chip; out of range, Rania asks once.
- [x] One Rania suggestion per message, with Try again.
- [x] One name per staff member: the lead's broker attends the visit, and the listing's agent is told so the keys reach them.

### Tests

- [x] Convert lands in Deal; escalation; outcome required: `tests/test_sales_room.py` and `e2e/sales_room_flow.py`.

## Room 3: Deal

- [ ] 🟡 Deal owns the Case from conversion to ready for transfer. There: deal page, `on_convert`. Needed: a ready-for-transfer point.
- [ ] **Deal manager agent.** None; a person does the work.
- [x] **Waits for Compliance before anything binding.** No gate; signing and submit never read it.
- [x] **Deal room on the 3D floor.**

### Checklist by deal type

"Tick" below means a free-text step a person ticks, with no document, gate, date or client message behind it.

- [ ] 🟡 Checklist chosen from the Case's Facts. There: from the sales desk or a broker's override, three paths. Needed: from Facts, with cash or mortgage and party type.
- [ ] 🟡 Owner edits each template. There: steps, stages, closing, in the deal rules panel. Needed: documents and reminder fields on screen, in Settings.
- [x] Secondary: Form A, Form B, Form I. Drafted at conversion (D25).
- [ ] 🟡 Secondary: Form F. There: built and signed online. Needed: seller and passport filled in.
- [x] IDs and passports. There: link for our side. Needed: a named seller with a phone (today literally "the seller").
- [ ] 🟡 Title deed. There: requested. Needed: unit check; a link when we act for the buyer only.
- [ ] 🟡 Developer NOC, DLD appointment: ticks. Needed: document, date, place.
- [x] Mortgage: pre-approval, valuation, final offer, manager's cheques, liability letter: ticks shown on every ready deal. Needed: conditional steps and upload kinds.
- [ ] 🟡 Off-plan: reservation form, SPA, Oqood: ticks. Needed: real items and files.
- [ ] Off-plan: booking payment.
- [x] Off-plan: payment plan schedule.
- [ ] 🟡 Rental: tenancy contract, Ejari: ticks. Needed: a contract template.
- [x] Rental: cheques and security deposit schedule. No photo or number capture.
- [x] Rental IDs. There: tenant. Needed: landlord.
- [ ] Rental: title deed copy; landlord's authorisation if a POA.
- [ ] Listing checklist: Form A, title deed, ID, Trakheesi, photos. No listing path exists.
- [ ] Off-plan resale path.

### Client form portal

- [x] 1. WhatsApp with a private link. There: link logged; the first WhatsApp is a reminder two days later; signing links are copied by hand. Needed: sent at once, with the "3 things, 2 minutes" text.
- [x] 2. Mobile page with only this client's missing items, pre-filled. There: two separate pages. Needed: one page, pre-filled.
- [x] 3. Signature. There: photo upload. Needed: **draw on screen**, the preferred way.
- [ ] 🟡 4. Every upload checked on arrival. There: structural checks. Needed: [the real checks](#the-checks).
- [x] 5. WhatsApp receipt naming what came in and what is next.
- [ ] 🟡 5. Task closes, Document stored, event. There: filed when the officer confirms. Needed: the checklist line closes too.
- [x] 6. Nudge at 24 hours. There: at 2 days.
- [x] 6. Broker call Task at 48 hours. There: after 3 reminders, about 8 days.
- [x] 6. Owner sees it at 72 hours.
- [x] Same quiet hours as Sales: see Fix first.

### Exit

- [x] Ready for transfer only when all lines are done, Compliance cleared, payment in, Review passed and the owner approved, on current Facts.
- [x] Correction rebuilds the checklist and reissues affected forms. There: price, terms and property redraft. Needed: cash-to-mortgage changes the steps; buyer name as a Fact; signed forms recalled.

### Blocks on screen

- [x] Deals by stage. There: table and bars. Needed: a board.
- [ ] 🟡 Checklist per deal. Needed: owner room per line, shown from the start (ticks appear only after Form F).
- [x] Portal status. There: uploaded, turned away, reminders. Needed: "opened".
- [ ] 🟡 Follow-up ladder. There: a count. Needed: the ladder.
- [ ] 🟡 Waiting on. There: free text on transfer steps. Needed: the fixed list on every Task.
- [x] Gates panel: Compliance, Finance, Review, owner.

### Tests

- [x] Selfie as signature rejected.
- [x] Drawn signature accepted: photo only.
- [x] WhatsApp receipt in the sandbox.
- [x] Gates block the transfer. Only unsigned forms block today.

## Uploads and their checks

This whole section needs a vision or OCR provider the owner approves (outside), or the checks stay as typed fields.

### Identity by party

- [ ] 🟡 UAE resident. There: passport, Emirates ID, typed expiry, ID format check, name flag on the ID only, brightness. Needed: document type, name across both, corners, warn at 30 days as a setting, and re-check later.
- [ ] Non-resident: passport, proof of address. The link always asks for EID and visa, so a non-resident cannot finish.
- [ ] GCC national: passport or national ID.
- [ ] Joint buyers: one identity set each, who signs what. One buyer only today.
- [ ] Company, onshore or free zone: licence, memorandum, board resolution, signatory, owners of 25% or more.
- [ ] Company, offshore: incorporation, good standing, register, attested and translated.
- [ ] Power of attorney: document, attorney IDs, principal's passport, block if it expires before transfer.
- [ ] Estate, inheritance or minor: flag to a person and the lawyer.

### Deal documents

- [ ] 🟡 Cash, buyer: identity, deposit, source of funds, manager's cheque, DLD and commission cheques. There: identity link, deposit task, fee amounts, ticks. Needed: cheque uploads and client proof uploads.
- [ ] 🟡 Cash, seller: identity, title deed. Needed: a named seller.
- [ ] Cash, seller: tenancy contract and Ejari if tenanted; service charge clearance.
- [x] Office: Forms A, B, I, invoices, receipts.
- [ ] 🟡 Office: Form F.
- [ ] 🟡 Mortgage items: ticks.
- [ ] Mortgage timeline Task list.
- [ ] 🟡 Seller has a mortgage: liability letter tick. Needed: valid date, clearance.
- [ ] Payment split to the seller's bank.
- [ ] 🟡 Off-plan buyer. There: identity, schedule. Needed: reservation form, booking proof, SPA, instalment proofs.
- [ ] 🟡 Off-plan outside: schedule only. Needed: receipt, Oqood certificate.
- [x] Off-plan office: commission invoice to the developer.
- [ ] Off-plan office: reservation summary.
- [ ] Off-plan resale: the whole row.
- [ ] 🟡 Rental tenant: IDs and cheque tasks. Needed: uploads.
- [ ] Rental: employer letter; landlord set (identity, deed, DEWA, POA).
- [ ] Rental office: tenancy contract, key handover form, condition report with photos.
- [ ] 🟡 Rental office: agency fee invoice.
- [ ] 🟡 Renewal reminder: at 90 days. Needed: at 60 too.
- [ ] Renewal: cheques, new rent, Ejari renewal, contract.
- [ ] Listing row.

### The checks

- [ ] Drawn signature: no drawing exists.
- [ ] 🟡 Signature photo. There: format and size. A selfie passes. Needed: ink, no face, no document.
- [ ] 🟡 ID or passport. There: blur, dark, repeat file, typed expiry. Needed: right document, name, MRZ, 4 corners.
- [ ] 🟡 Two-sided ID. There: two items. Needed: "please add the back".
- [ ] 🟡 Title deed or Oqood. There: any image. Needed: layout and unit match, and an Oqood kind.
- [ ] 🟡 Signed PDF. There: right signer by link, old versions blocked. Needed: every signature line, page message.
- [ ] Cheque photo.
- [ ] Bank letter, pre-approval, offer letter.
- [ ] Proof of address.
- [ ] 🟡 Any upload. There: type and size, fixed 8 MB. Needed: opens, not password-protected, size as a setting.
- [ ] A person overrides a rejection with a reason (D34).
- [ ] 🟡 A person sees each document in Review. There: the compliance officer confirms (D33).

### What each upload stores

- [ ] 🟡 Case, party, role: no party id.
- [ ] 🟡 Kind: 6 kinds. Needed: forms, cheque, pre-approval, liability letter, POA, licence.
- [ ] 🟡 File, pages, hash: no pages; repeat check only within one link.
- [ ] 🟡 Uploaded by, at: no channel.
- [ ] 🟡 Extracted: typed by the client, not read.
- [ ] 🟡 Check result: reasons and flags. Needed: overridden by whom and why.
- [ ] 🟡 Expires at: no ongoing warnings.
- [ ] 🟡 Satisfies task: the task points to the document, not the other way.
- [ ] 🟡 Based on Facts: on drafts only.
- [ ] Status: current, superseded, voided.
- [ ] 🟡 Reviewed by, at: the compliance officer.

## Room 4: Operations

- [ ] 🟡 Fills portals up to Submit. There: a field plan for Form F. No browser fill exists, despite the charter saying so (outside: DLD, Trakheesi, Ejari, Dubai REST).
- [ ] 🟡 Ops lead and Form F clerk: charters exist.
- [ ] Scheduler.
- [ ] 🟡 Executes Tasks from other rooms. There: tasks. Needed: an agent that runs them; a person does everything now.

### What it picks up

- [ ] 🟡 Form task → builds and sends. There: builds; the broker copies the link. Needed: sending, and sending to the other agency.
- [ ] 🟡 Document received → files and renames. There: fixed file name on confirm. Needed: the office's convention, attach to the portal draft.
- [x] Ready for transfer → NOC, trustee, slot. There: ticks.
- [ ] Listing signed → permit, photographer, portal draft.
- [x] Rental signed → Ejari, cheques Task. There: tick and a hand-entered schedule. Needed: triggered by signing.
- [x] Transfer complete → handover, welcome, close. There: one tick and `operations.close`. Needed: keys, cards, DEWA, chiller, welcome message.

### Rules

- [ ] 🟡 Stops before Submit, with a filled screen. There: a person submits from a field list. Needed: the filled screen; beyond Form F.
- [ ] 🟡 Forms from Facts, never retyped. There: yes, with blanks printed for seller, IDs and deed. Needed: fill them; record Fact versions on the form.
- [x] Recall and resend. There: sent back, old link "replaced". Needed: the client message, automatic new link, signed forms.
- [ ] 🟡 Waiting-on on each Task. There: transfer steps. Needed: all Tasks, days waited.
- [ ] Over the owner's limit goes to the brief.

### Blocks on screen

- [x] An Operations screen. Today it is a section of one deal plus the work queue.
- [x] Forms sent, with version: per deal.
- [x] Portal drafts: Form F only.
- [x] Appointments: trustee, DLD, handover.
- [x] Waiting on outsiders with days.
- [x] Recalled forms.
- [ ] 🟡 Handover checklist: closing checklist only.

### Tests

- [x] Ops room shows Tasks after ready for transfer.
- [x] Recall after a price correction, with the client message.

## Room 5: Finance

### Job

- [x] Bill at the trigger. There: a person presses a button. Needed: automatic drafts on Form F signed, transfer completed, tenancy signed, as a setting.
- [x] Client or developer, commission %, VAT, TRN on the invoice.
- [x] Invoice due date.
- [ ] 🟡 A person approves. There: "I sent it", with a stale check. Needed: an Approval, pinned.
- [ ] Sent by email and WhatsApp (outside for email).
- [x] Status. There: open, overdue, received. Needed: draft, sent, due, partly paid, written off.
- [x] Polite reminders on the owner's schedule.
- [x] Overdue developer commission to the brief.
- [ ] 🟡 Split. There: co-broker. Needed: held-split state.
- [x] Broker commission and payout list.
- [x] Report. There: next 7 days, overdue, billed vs collected. Needed: cash this month, 30 days, per broker.
- [x] Invoice clerk's charter still says supplier invoices. Needed: outgoing first.

### Mark received

- [x] 1. Taps Mark received. There: a reference box and a button. Needed: a form.
- [x] 2. Amount, date, method, proof.
- [ ] 3. Reads the proof and flags a mismatch.
- [x] 4. Part-payment keeps the balance open.
- [x] 5. `payment.marked_received`, unblocks Deal.
- [x] 5. WhatsApp receipt. A PDF exists, not sent.
- [x] 6. Cash over threshold or third-party payer to Compliance first.
- [x] 7. Logged with who. Needed: undo with a reason.
- [ ] Later, if wanted: bank alert forwarding.

### Blocks on screen

- [x] Invoices by status: per deal.
- [x] Mark received.
- [x] Expected payments, each tied to the client's words.
- [x] Commissions to split and pay.
- [x] Cash, outstanding, 30 days: 7 days only.
- [x] Flags for Compliance.

### Tests

- [x] Mismatched proof shows a flag.
- [x] Third-party payer to Compliance before the receipt.

## Room 6: Compliance

### Checks

- [ ] 🟡 KYC on conversion. There: documents requested and confirmed. Needed: a KYC result.
- [ ] 🟡 IDs and names. There: one name against the deal. Needed: across documents.
- [ ] Address.
- [x] Risk rating: low, medium, high.
- [ ] 🟡 Screening. There: a task per party, on every Fact, before KYC, and a person records it by hand. Needed: spelling corrections re-screened; D41.
- [ ] Sanctions lists (outside: choose a provider; a person checks by hand today).
- [ ] PEP status.
- [ ] Adverse media.
- [x] Hit goes to a person, never auto-cleared. No agent clears, but the hit does not hold (Fix first).
- [x] Source-of-funds trigger. There: runs on every deal. Needed: threshold, high risk, PEP.
- [x] Source of funds: what the client said, in quotes.
- [x] Documents asked for. There: a list. Needed: request from the client through the portal.
- [ ] Whether documents support the story.
- [x] Payment pattern on marked payment: cash, third party, split, crypto, mismatch.
- [ ] Mortgage checks.
- [x] Enhanced due diligence with senior sign-off.
- [x] Reporting. There: cash report draft, the officer files with a reference. Needed: suspicious transaction report draft.

### Correction rule

- [ ] 🟡 1. A new Fact contradicts an old one. There: works with an explicit link from the Scribe, including from WhatsApp. Other clashes go to the broker on a card with no way to answer it.
- [x] 2. Compliance first, both quotes. There: payer, payment, income. Needed: price and finance too (D7).
- [ ] 🟡 3. Dependent work withdrawn. There: open tasks. Needed: done tasks, a "based on superseded fact" status (D6).
- [ ] 🟡 3. Sent form recalled. There: unsigned forms; signed forms lock terms. Needed: `form.recalled`.
- [ ] 🟡 4. Compliance decides what reruns. There: a new name auto-makes a screen; a "Reviewed" button. Needed: a choice.
- [x] 5. Old approvals refused.
- [x] 5. Unrelated work untouched.

### Clearance

- [x] `compliance.cleared` on current Facts.
- [x] `compliance.needs_info` to a portal request.
- [x] `compliance.blocked`: Case stops, owner told.
- [x] Transfer gated on clearance.

### Blocks on screen

- [x] Corrections side by side: overview, latest 8.
- [x] Screening queue and hits.
- [x] Source-of-funds files: per deal.
- [x] Risk rating per Case.
- [x] Holds, and why.
- [x] Report drafts: cash only.
- [x] Rule book. The floor label says so; the content is checks and payment facts.

### Fix first in the spec

- [ ] Open Tasks on idle agents start: see Spine.
- [x] Task titles name what raised them: see Fix first.
- [x] Thresholds as settings. There: cash. Needed: source of funds; remove "AED 55,000" from the charter.

### Tests

- [x] New payer reruns screening and blocks the transfer until cleared. Rerun works, block does not.

## Room 7: Review

Today Review is an automatic check on drafts: does this rest on words that were replaced? The rest is not built. The Devil's advocate is a charter only.

- [ ] 🟡 Nothing reaches a person's approve button unchecked. There: drafts. Approvals and task actions skip it.
- [ ] 🟡 Quotes current: drafts' linked Facts. Needed: every claim has a quote.
- [ ] Numbers consistent across the Case.
- [ ] Completeness: checklist and signatures.
- [ ] Authority: charter respected, nothing sent without a yes.
- [ ] 🟡 Tone and promises. There: marketing and follow-ups, English. Needed: in Review.
- [ ] No Compliance hold bypassed.
- [ ] Devil's advocate that runs.
- [ ] `review.requested` from forms, invoices, decks, transfer requests and messages (D43).
- [ ] One card per item with a green, amber or red verdict and one line per finding.
- [ ] 🟡 Links to quotes: ids only.
- [ ] Approve, Send back with a note, Edit.
- [ ] 🟡 Approve pins to Fact versions: yes, outside Review.
- [ ] Send back creates a Task with the note.
- [ ] **Review area visible to the owner and agents, and notifications to the approver.** Asked for by the owner.

### Blocks on screen

- [ ] Items awaiting review.
- [ ] 🟡 Findings per item.
- [ ] 🟡 Sent back with the note.
- [ ] 🟡 Approved with pinned versions: under Finance.
- [ ] Patterns this week.

### Tests

- [ ] 🟡 Invoice price differs from the Fact: red, approval blocked. There: sent back, refused. Needed: the red verdict.

## Room 8: Records

- [ ] 🟡 System of record, searchable. There: append-only log. Needed: search across Cases, retention period.
- [x] Agents: Records lead, Archivist, Data analyst (D36).

### Case file

- [ ] 🟡 Timeline of every Event. There: last 14 of 18 types, in the Deal drawer.
- [x] Every Fact with quote and superseded history.
- [ ] 🟡 Document versions: drafts and forms only.
- [ ] 🟡 Every approval, who and when: no single list.
- [ ] One Case file view on a Records screen.

### Registers

- [ ] 🟡 Deals closed: endpoint exists, no screen calls it.
- [x] Listings.
- [ ] Tenancies with renewal dates.
- [ ] 🟡 Commissions: billed vs collected. Needed: per deal, per broker.
- [ ] 🟡 Compliance files. Needed: register and retention.
- [ ] 🟡 Audit trail. There: read-only log. Needed: a screen.
- [ ] Void with a reason.

### Data analyst

- [ ] 🟡 Through Nova: sales, spend, pipeline, documents, with citations. Needed: a dashboard and every question below.
- [ ] Funnel by channel, broker and month.
- [ ] 🟡 Days in each stage: yes-to-close and paperwork only.
- [ ] Time to first reply; time to call after "call me".
- [ ] 🟡 Commission closed and pending.
- [ ] Cost per lead by channel; average deal size.
- [ ] 🟡 Broker leaderboard: on request.
- [ ] Follow-up discipline; send-back rate.
- [ ] 🟡 Asking vs closing prices. Needed: by area.
- [ ] 🟡 Renewals become Sales Tasks. There: one Ops task at closing. Needed: a scan, `renewal.due`, a Sales Task (D45).
- [ ] Weekly Monday report in the brief.

### Blocks and tests

- [ ] A Records page with search, registers, funnel, speed, money, renewals and audit.
- [ ] Records wall shows its own work; it is office-wide.
- [ ] Test: renewal Task for a seeded tenancy ending in 60 days.

## Room 9: Lobby

Built on 31 Oct 2026: `diwan/lobby_room.py`, `diwan/lobby_api.py`, `web/lobby.html`, the Lobby on the floor. Checked by `tests/test_lobby_room.py` and in a real browser (`e2e/lobby_flow.py`). `agents/lobby.py` is the staff requests board (D10). Decisions L1 to L6 are in [open-questions.md](open-questions.md).

- [x] Lobby room on the floor, with a host and a rep per room.
- [ ] 🟡 Input: anonymised, opt-in playbooks from other offices. There: the opt-in, the no-client-data filter, and playbooks people file by hand. Needed: something that carries them between offices (outside).
- [x] Input: competitor posts: the Marketing rep reads the best one of the week.
- [ ] 🟡 Input: portal trends, DLD data, news on projects and regulation (outside). There: a person can file what they read as a playbook. Needed: the feeds.
- [x] Input: send-backs, lost reasons, Rania's unanswered questions: as counts and topics, never a client's words.
- [x] Weekly thread per room, ending in at most one experiment. Written by rules from the log: no model is called.
- [x] Experiment: change, audience, period, metric.
- [x] Owner approves; Records reports; keep or roll back. Half the audience is the comparison; the change stops by itself at the end of the period.
- [x] One idea a day in the brief.
- [x] Agents cannot apply their own changes: they suggest, the owner approves, and it is a dated lesson while it runs.
- [x] Compliance rules and Settings cannot change from the Lobby: refused by kind, by word and by agent, on proposal and again on approval.
- [x] Blocks: threads, playbook cards, proposed, running, kept and rolled back.
- [x] Test: an experiment changes a template only for its audience and period.
- [x] Monthly: experiments kept and rolled back, on the 1st.

## Marketing

Built on 31 Oct 2026 after this list was first written; spec: [marketing-complete-spec.md](marketing-complete-spec.md). Checked in a
real browser (`e2e/marketing_flow.py`, `e2e/event_flow.py`, `e2e/journey_flow.py`, `e2e/studio_flow.py`) and by `tests/test_marketing.py`.

### Command

- [ ] Fix the brand typo, in Setup (Fix first).
- [ ] 🟡 Permit default Yes. There: in code. Off in the data.
- [x] Permit number on any listing post: checked at run, QA, approve and publish.
- [ ] Confirm the permit rule with the office.
- [ ] Fictional demo data (D3).
- [ ] 🟡 Every script and post through Review. There: room-lead QA, no bypass left (D8).
- [x] A script or post paused or withdrawn when its listing changes, at any stage.

### Content stages

One stage per piece of content, `idea` to `archived`, folded from the spec's events and shown on the Studio's Results tab.

- [x] Idea from a topic the owner sets.
- [x] Idea from a new listing or a price change: suggested on the Results tab, written only when a person presses.
- [ ] 🟡 Idea from a competitor signal: read in every run; a signal does not start one.
- [x] Idea from a Lobby idea: an approved content experiment reaches the Studio as an idea its people may write.
- [x] Brief approved by a person: pressing Write is the yes; an automatic run waits for one. `briefed` stage.
- [x] Scripted: three scripts from their own Facts, the person picks.
- [ ] 🟡 In production: video, captions, cover. Free video has a Windows voice, not run end to end; HeyGen is (outside).
- [ ] 🟡 Permit number on screen: in the shot list, not verified in the cut.
- [x] Ready: permit present and in date; expiry date on the listing, warned at 14 and 3 days.
- [x] Person approves the post and its time.
- [x] Scheduled and posted (outside: Instagram, `PUBLIC_BASE_URL`). The owner's auto-post switch, off by default.
- [x] Live, with its Instagram id.
- [x] Paused, with the reason. On a live post it records the status and gives a person the task, because Instagram's connection can't delete (D47, assumed).
- [x] Withdrawn when a listing is gone or a moment has passed; archived after the owner's days.

### Closing the loop with Sales

- [x] Code word on every post and ad. Listings are traced through portal enquiries.
- [x] `lead.attributed`: code word, the post a comment came from, or the listing. First source wins.
- [ ] 🟡 Comments and DMs to Sales. There: every comment goes. Needed: buying questions only, and DMs (outside).
- [x] Per post and campaign: leads, qualified, viewings, deals, commission.
- [x] Weekly: what brought deals. Angles that bring enquiries rank first.

### Campaigns and spend

- [x] Campaign record: goal, audience, budget, dates, content.
- [x] Spend setting with a hard monthly cap.
- [ ] 🟡 Agents draft ads: copy with the code word. Audiences are typed by a person.
- [x] A person launches and pays: Diwan cannot launch.
- [ ] 🟡 Cost per qualified lead over the limit: flagged to the Marketing person when spend is read (outside: ad account). Not in Nova's brief yet.

### Rules

- [ ] 🟡 No post without a valid permit, Review and approval. Permit and approval are enforced at publishing; Review is D8.
- [ ] 🟡 Every price and claim from a current Fact. There: amounts and track-record numbers, in English. Needed: size.
- [x] A changed listing pauses the post.
- [ ] 🟡 No promises: returns, price rises, visas. English only, and in QA.
- [ ] 🟡 Competitors studied, never copied. There: instructions. Needed: a check against competitor text.
- [ ] 🟡 Music and footage licensed: a reminder on the publishing card, no check.

### Definition of done

- [x] A post's leads on the right Cases with their source.
- [x] A price change pauses every post within a minute.
- [x] A permit expiry pauses every post for that unit.
- [x] Results show deals and commission per post (on the Studio's Results tab; Records has no page yet).

## Each deal type, step by step

### Secondary sale

- [ ] 🟡 1. Listing exists. There: listings, permit gate. Needed: Form A at listing, seller KYC, message.
- [ ] 🟡 2. Buyer qualifies and views. There: all of Rania's flow. Needed: Form B before the viewing (D11, D25).
- [ ] 🟡 3. Offer made. There: a stage. Needed: an offer record with quote and terms, message to the seller.
- [ ] 🟡 4. Counter and accept. There: agreed price at conversion, discount gate. Needed: counters, quoted acceptance, "Offer accepted" message.
- [ ] 🟡 5. Co-broke: Form I and share. Needed: an agreed marker.
- [ ] 🟡 6. KYC both sides. There: screening, links. Needed: seller always covered, a cleared outcome.
- [ ] 🟡 7. Liability letter: tick.
- [ ] 🟡 8. Valuation and final offer: tick. Needed: valuation gate, bank updates.
- [ ] 🟡 9. MOU from Facts. Needed: owner approval, Review.
- [ ] 🟡 10. MOU signed, deposit. There: signing, marked received. Needed: cheque check, message.
- [ ] 🟡 11. NOC: tick.
- [ ] 🟡 12. Transfer booked: tick. Needed: gate, "what to bring".
- [ ] 🟡 13. Cheques prepared: tick. Needed: payee list, split match.
- [ ] 🟡 14. Transfer completes: tick. Needed: client message.
- [ ] 🟡 15. Invoice and commission. Needed: client receipt sent.
- [ ] 🟡 16. Handover: tick. Needed: welcome, review ask.
- [ ] 17. Aftercare: 30 days later, renewal, referral.

### Off-plan

- [ ] 🟡 1. Project and unit. Needed: dated price list, hold, `unit.held`.
- [ ] 🟡 2. Reservation. Needed: form, proof, developer-account rule, "reserved until".
- [ ] 🟡 3. KYC.
- [ ] 🟡 4. SPA: tick and reference. Needed: upload, all pages signed.
- [ ] 🟡 5. Oqood: tick.
- [x] 6. Commission to the developer on its trigger.
- [ ] 🟡 7. Instalments tracked, overdue shown. Needed: reminders 14 and 3 days before.
- [ ] 🟡 8. Handover. Needed: notice, snag list, final payment (D28).

### Rental

- [ ] 🟡 1. Tenant qualifies and views.
- [ ] 🟡 2. Offer. Needed: rent, cheques, move-in as Facts, quoted acceptance, message.
- [ ] 🟡 3. Documents and cheques. Needed: cheque uploads, date and amount checks.
- [ ] 🟡 4. Contract: tick. Needed: generated, reviewed, signed.
- [ ] 🟡 5. Ejari: tick (outside).
- [ ] 🟡 6. Agency fee. Needed: client receipt.
- [ ] 🟡 7. Move-in: tick. Needed: keys, condition report, DEWA steps.
- [ ] 🟡 8. Cheque dates. Needed: landlord reminder.
- [ ] 🟡 9. Renewal: broker task. Needed: client message, Sales ownership.

### Listing

- [ ] 1. Seller enquiry and valuation, from comparable sales.
- [ ] 2. Form A signed as a listing step, seller KYC.
- [ ] 3. Permit and photos (outside: Trakheesi).
- [ ] 🟡 4. Live. There: permit needed before ads; portal feed read-only. Needed: publishing (outside).
- [ ] 5. Weekly seller report.
- [ ] 6. Price change withdraws every ad, script and form. Listing price is not a Fact today.
- [ ] 🟡 7. Offer received: a buyer deal can pick the listing. Needed: link to a seller Case.
- [ ] 8. Form A expiry at 14 days.

## When things go wrong

- [ ] 🟡 **Client corrects themselves.** Built for the correction engine; see [Correction rule](#correction-rule).
- [ ] 🟡 **Buyer goes quiet after the offer.** There: general ladder, which stops once a person has the chat. Needed: offer-aware, owner brief, seller updates.
- [ ] 🟡 **Buyer walks after the MOU.** There: Lost with a reason, listing released. Needed: quote, deposit options, seller told.
- [ ] 🟡 **Seller withdraws after the MOU.** There: Lost. Needed: buyer alternatives, back to Sales.
- [ ] **Mortgage refused:** options.
- [ ] **Valuation below price:** gap and options. A new price after conversion is refused today.
- [ ] **Liability letter expires.**
- [ ] **NOC refused or delayed.** No transfer date on the deal.
- [ ] 🟡 **Screening hit or unclear funds.** There: tipping-off guards. Needed: hold, "we need more information", officer closes.
- [ ] 🟡 **Third-party payment.** There: screened at the Fact stage. Needed: at Mark received, receipt held.
- [ ] **Cheque bounced.**
- [ ] 🟡 **Commission not paid.** There: open task, unpaid list. Needed: due date, ladder, brief, dispute log (D9).
- [ ] 🟡 **Co-broker dispute.** There: Form I and the log. Needed: a hold on the split.
- [ ] **Deposit returned or refunded** (D40).
- [ ] **Client complaint:** words like "complaint", "unhappy", "lawyer"; record; owner told; acknowledgement only.
- [ ] 🟡 **Wrong document accepted.** There: sent back before confirming. Needed: void after confirming, reopen steps.
- [ ] 🟡 **Staff member leaves.** There: reassign, away. Needed: one-step handover, PA memory archived, clients told.
- [ ] **Client asks to delete their data** (D4).
- [ ] 🟡 **Client asks to stop.** See Fix first.
- [ ] 🟡 **Lost reasons.** There: free text. Needed: the dropdown, so Records can count.

## Cases from Part 4

- [ ] 🟡 1. Same person on two channels. There: manual merge. Needed: detection, proposal, never when two brokers own them (D19).
- [ ] 🟡 2. Two brokers claim one client. There: Pool claim, logged. Needed: a claim flow, permission on reassign, Sales manager allowed.
- [ ] 3. New listing matches waiting buyers.
- [ ] 🟡 4. Viewing logistics. There: 24-hour and 2-hour confirmations. Needed: keys, tenant notice, travel time.
- [ ] 🟡 5. No-show. There: marked. Needed: one reschedule message, heat effect.
- [ ] 🟡 6. Viewing feedback. There: notes, Rania asks next day. Needed: as a Fact, in the seller report.
- [ ] 7. Several offers on one unit (D20).
- [ ] 🟡 8. Rental move-out. There: one task. Needed: notice Fact, inspection photos, deductions, deposit return, Ejari cancellation.
- [ ] 9. Rent increase at renewal, with the rent index.
- [ ] 🟡 10. Visas, returns, legal, tax. There: returns. Needed: all four, with a broker Task straight away.
- [ ] 🟡 11. Off-plan escrow. There: payee escrow, no release. Needed: Rania never sends bank details, account changes flagged.
- [ ] 🟡 12. Broker licence. There: number. Needed: expiry, 30-day warning, no new Cases when expired.
- [ ] 13. Mortgage broker referral.
- [ ] 14. Snagging (Phase 2).
- [ ] 15. Property management (Phase 2).
- [ ] 16. Commercial and holiday homes (Phase 2).
- [ ] **Fraud guard.** Any "change bank details" or "send to this account" message raises a Now flag to Finance and Compliance, no agent acts, and it is confirmed by phone.

## Listing upkeep

No listing has an expiry or a last-confirmed date. Rania only offers listings that have a permit and are available, and the feed sync is the only freshness check.

- [ ] Permit expiring at 14 and 3 days; paused on expiry day.
- [ ] Form A expiring.
- [ ] Still available? Every 7 days for sale, 3 for rent, and before a viewing (D11).
- [ ] No answer in 48 hours: broker Task, then unconfirmed, ads paused.
- [ ] Portal refresh rule (outside).
- [ ] 🟡 Off-plan price list. There: knowledge has a valid-until date. Needed: developer price list, 14 days, "to be confirmed".
- [ ] Tenant moving out: re-listing 60 days ahead.

## Case stages

See D2. "Code" is the name used today.

- [x] `new` → code "New".
- [ ] `discovering`.
- [x] `qualifying` → "Qualifying".
- [x] `qualified` → "Qualified".
- [ ] 🟡 `viewing` → "Viewing booked", plus an extra "Viewed".
- [ ] 🟡 `offer` → "Offer", not on the off-plan path.
- [ ] 🟡 `converted` → "Offer accepted" or "Reservation".
- [ ] `documents`, `cleared`.
- [ ] 🟡 `mou_signed` ≈ "Form F"; `transfer_ready` ≈ "Transfer".
- [ ] `transfer_booked`, `transferred`.
- [ ] 🟡 `reserved` ≈ "Reservation"; `spa_signed` ≈ "SPA"; `registered` ≈ "Oqood".
- [ ] `handover_due`.
- [ ] 🟡 `contract_signed` ≈ "Contract"; `moved_in` ≈ "Move-in".
- [ ] `tenancy_active`, `renewal_due`, `move_out`.
- [ ] `listing_signed`, `listing_live`, `under_offer`, `listing_expiring`.
- [x] `closed_won` → "Won"; `closed_lost` → "Lost" with a reason.
- [ ] Side state `on_hold`.
- [x] Side state `nurture`.
- [ ] Owner room per stage.
- [ ] 🟡 Disallowed moves refused and logged. There: unknown stages refused, not logged; forward jumps free.

## Event catalog

### Same name in the code

- [x] `fact.superseded`, `task.created`, `task.done`, `approval.given`.
- [x] `review.passed`, drafts only.

### Exists under another name (D1)

- [ ] 🟡 `message.received` = `chat.received`
- [ ] 🟡 `case.created` = `deal.opened`
- [ ] 🟡 `case.intent_set` = `qualify.type`, `lead.kind`
- [ ] 🟡 `case.merged` = `chat.merged`
- [ ] 🟡 `fact.recorded` = `fact.created`
- [ ] 🟡 `task.reopened` = `task.withdrawn` plus a new task
- [ ] 🟡 `call.requested` = `attention.raised` with kind call
- [ ] 🟡 `viewing.booked`, `done`, `no_show` = `appointment.booked`, `done`, `noshow`
- [ ] 🟡 `case.converted` = `setting.changed` (agreed) plus `stage.changed`
- [ ] 🟡 `case.lost` = `stage.changed` to Lost
- [ ] 🟡 `cobroke.agreed` = `setting.changed` (terms)
- [ ] 🟡 `doc.requested`, `received`, `rejected` = `docs.*`
- [ ] 🟡 `form.ready` = `draft.made`; `form.sent` = `sign.link`; `form.signed` = `sign.signed`; `form.recalled` = `review.returned`
- [ ] 🟡 `compliance.needs_info` = `question.asked`, the closest
- [ ] 🟡 `screening.hit` = `task.done` with result possible match
- [ ] 🟡 `review.sent_back` = `review.returned`
- [ ] 🟡 `approval.declined` = `approval.refused`
- [ ] 🟡 `noc.received`, `transfer.booked`, `transfer.completed`, `ejari.ready` = `task.done` on a step
- [ ] 🟡 `invoice.sent`, `payment.marked_received` = `task.done`
- [ ] 🟡 `renewal.due` = `task.created` with step renewal
- [ ] 🟡 `case.closed` = `sale.closed` plus `stage.changed`

### Not there at all

`events.py` refuses any name not on its list, so each needs adding first.

- [ ] `offer.made`, `offer.countered`
- [ ] `compliance.cleared`, `compliance.blocked`
- [ ] `mortgage.preapproved`, `mortgage.final_offer`, `mortgage.refused`
- [ ] `review.requested`
- [ ] `deal.ready_for_transfer`
- [ ] `listing.ready`, `listing.live`, `listing.signed`
- [ ] `payment.flagged`
- [ ] `cheque.due`, `cheque.bounced`, `installment.due`
- [ ] `form.expiring`, `doc.expiring`
- [ ] `complaint.opened`
- [ ] `experiment.approved`, `experiment.ended`
- [ ] `unit.held`, `valuation.sent`, `seller.report`, `oqood.received`, `funds.ready`, `referral.asked`
- [ ] `permit.expiring`, `permit.expired`, `listing.check_due`, `listing.confirmed`, `listing.unconfirmed`, `listing.withdrawn`
- [x] `content.idea`, `content.briefed`, `content.scripted`, `content.ready`
- [x] `post.approved`, `post.live`, `post.paused`, `post.withdrawn`
- [x] `campaign.started`, `campaign.ended`, `lead.attributed`
- [ ] Every event carries `fact_ids` with versions.
- [ ] Every event has a consumer.

## Owner settings

The spec wants one page. Today they are spread over Settings, the Deal rules panel, Calendar, the qualifying form, Studio, Team and `.env`.

- [ ] 🟡 **Office.** There: name, licence, address, TRN, working hours, quiet hours, Friday switch. Needed: prayer window as a setting, public holidays, languages Rania speaks.
- [ ] 🟡 **People.** There: shift, days, away, phone, desk roles, logins. Needed: staff, roles, rooms and display names as settings (hard-coded), who covers whom, PA names.
- [ ] 🟡 **Sales.** There: qualifying form, follow-up schedule, deal kinds. Needed: heat rules, call limit (in env), routing by area or language.
- [ ] 🟡 **Deal.** There: steps, documents per party, link days, reminders. Needed: expiry warnings, ladder, party-type templates.
- [ ] 🟡 **Money.** There: commission per path, VAT, deposit held by, developers. Needed: invoice triggers, payout rules, reminder schedule.
- [ ] 🟡 **Compliance.** There: cash report threshold, named officer. Needed: source-of-funds threshold, screening lists, high-risk rules, retention, who may delete.
- [ ] 🟡 **Messaging.** There: template pickers. Needed: opt-in record, stop words per language, which messages need approval.
- [ ] 🟡 **Marketing.** There: permit, brand voice, start times. Needed: posting hours.
- [ ] 🟡 **Review.** There: autonomy per agent, discount percent. Needed: which items need Review, who may approve what amount.
- [ ] 🟡 **Limits.** There: spend limits in env, one stuck number. Needed: limits on screen, stuck days per stage, escalation chain.
- [ ] `docs/open-questions.md`, for the no-guess rule.
- [ ] 🟡 Every number a setting. Constants remain in `leads.py`, `documents.py`, `nudge.py`, `nova.py` and `access.py`.

## Answers only the office can give

- [ ] Which deal types the office does. Setting exists for three paths.
- [ ] Commission rates and who pays. Setting exists; when it is invoiced does not.
- [ ] Does the office hold client money? A text setting exists, with no gate.
- [ ] Source-of-funds and cash thresholds, from the compliance officer. Cash exists.
- [ ] Which mortgage brokers or banks.
- [ ] Languages Rania speaks. English and Arabic work today.
- [ ] How long documents are kept, and who may delete them.
- [ ] Which email and calendar the owner uses.
- [ ] Voice replies on the phone, or text only?
- [ ] Who else may talk to Nova.
- [ ] Conveyancer and compliance officer confirm the Dubai document lists.
- [ ] The office confirms the permit rule.
- [ ] 🟡 Consent: "stop" works. Needed: WhatsApp opt-in record.

## Outside accounts needed

- [ ] Real WhatsApp line and approved templates, including `NOTIFY_TEMPLATE`.
- [ ] `PUBLIC_BASE_URL`, so photos and links reach clients and Instagram. HTTPS before going online.
- [ ] Instagram DMs, Facebook, TikTok.
- [ ] Partner docs for Property Finder, Bayut, Dubizzle.
- [ ] Zoom keys. Google Meet and Teams have no connection.
- [ ] Email and calendar provider.
- [ ] Vision or OCR provider for documents.
- [ ] Sanctions, PEP and adverse-media lists.
- [ ] DLD, Dubai Trustee, Trakheesi, Ejari and portal accounts.
- [ ] Push notification service.
- [ ] Phone calling provider. Meta has no speech-output or telephony model.
- [ ] Meta ads, if paid ads are used.

## The end-to-end test

No Playwright test of this journey exists. None of the eight passes in full today.

- [ ] 🟡 **1. Sara qualifies, says "call me", the broker gets an alert within 1 minute.** The closest; probably works on screen. Not proven; the WhatsApp alert needs a template.
- [ ] **2. Broker converts; Deal shows the cash checklist with her Facts.** Convert works and Facts carry over. No cash variant, and the steps appear only after Form F is submitted.
- [ ] **3. Selfie rejected, signs on screen, WhatsApp receipt.** A selfie passes, no drawing, no receipt.
- [ ] **4. Compliance clears, invoice, deposit, receipt.** No list or clearance, invoice not sent, no receipt.
- [ ] **5. "My brother will pay part of it".** Her words become a Fact. But part-payment reads as a contradiction (D39) and goes to the broker, and work is withdrawn, not reopened. With a clean correction, Compliance first, old approval refused and unrelated work untouched all work.
- [ ] **6. Compliance clears, Review passes, owner approves, transfer filled up to Submit.** No clearance, no Review item, no owner step, no portal fill.
- [ ] 🟡 **7. Transfer complete, handover message, Case closes, in the funnel.** Ticks and closing work. No handover message, no funnel, closing needs commission paid.
- [ ] **8. Next morning's brief mentions the closed deal and commission, nothing stuck.** The brief reports no sales, no Stuck board, and commission due is impossible after closing (D9).

## Seed scenarios

- [ ] 🟡 Sara corrects the payer to her brother. `e2e/deal_flow.py` is the opposite, Karim dropping his brother.
- [ ] 🟡 Karim, mortgage, valuation AED 150,000 low. Only his payer correction is seeded.
- [ ] Al Noor Trading LLC, company buyer.
- [ ] Priya sells under a power of attorney, unit mortgaged and tenanted (D52).
- [ ] 🟡 Omar's buyer walks after the MOU. Lost and release are tested, not deposit options.
- [ ] Tenant Ahmed: 4 cheques, one bounces, renews, moves out (D52).
- [ ] 🟡 Off-plan buyer Lina: parts tested, not as one scenario.
- [ ] Selfie as signature, wrong-unit deed.
- [ ] 🟡 Expired passport: refused only if the client types the true date.
- [ ] 🟡 WhatsApp and Instagram lead from the same phone: manual merge (D19).
- [ ] "Please send the deposit to this new account."

## Definition of done by room

Six tests per room: own stats, event handlers, Tasks start within 5 minutes, PA answers "what's waiting on me?", every exit tested, correction reaches only its own work. No room meets all six.

| Room | Own view | Events | Tasks start | PA | Exits tested | Correction |
|---|---|---|---|---|---|---|
| Front Desk | No | No | No | Owner only | No | No |
| Sales | No | No | No | No | Part | Part |
| Deal | Part | No | No | No | Part | Part |
| Operations | Part | No | No | No | Part | Part |
| Finance | Part | No | No | Part | Part | Part |
| Compliance | Part | No | No | Part | Part | Part |
| Review | Part | No | No | No | Part | Yes |
| Records | Part | No | Part | Part | No | No |
| Lobby | No | No | No | No | No | No |
| Marketing | Part | No | Part | Part | Part | No |

## Later

### Meeting agent

- [ ] Joins Zoom, Meet or Teams as "Diwan notes" when added, and announces itself. Zoom today only creates meetings (outside).
- [ ] 🟡 Recording consent at the start: in-person only.
- [ ] 🟡 Listens and makes Facts with quotes: in-room only, event time rather than call time.
- [ ] 🟡 After: summary and follow-up draft built. Needed: decisions and action items as Tasks.
- [ ] Quiet question in the side chat.
- [x] Facts through one pipeline, for chat and meetings.

### Meeting page today

- [x] Deal, title, Start, consent card in English and Arabic.
- [x] Typed turns with speaker.
- [ ] 🟡 Live microphone: needs a Meta key; uses an old browser audio call.
- [x] End gives a follow-up draft, Copy, link to the Inbox.
- [x] "What the Scribe heard".

### 3D client showroom

- [ ] Client floor: reception with Rania, galleries, viewing rooms, meeting room.
- [ ] Clients enter by link and see no staff data.
- [ ] What a client says inside becomes a Fact.
- [ ] Separate scene and permissions, shared engine.
- [x] Everything writes through Events. `auth.db` for logins is the one exception.

### Phone calls

- [ ] Muse on calls: asked for by the owner, not in the spec. Muse Voice Transcribe hears but cannot speak, so it needs a telephony and speech provider (outside).
