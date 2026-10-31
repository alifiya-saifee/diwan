# Closed-loop spec: the full audit, line by line

Every requirement of `Diwan — Closed-Loop Office Spec` checked against the code on 31 Oct 2026, with where it was found. Generated from four independent read-throughs; the summary and the
order of work are in [closed-loop-checklist.md](closed-loop-checklist.md). Line numbers are from that day and will drift.

**Marks:** ✅ built · 🟡 partly · 🔑 built, waits on an outside connection · ❌ missing · 🔁 exists under another name, but no room reacts to it · 📦 the data exists, nothing reads it.

## Spine, Front Desk, PAs, settings

### Spine objects

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Person: one record per human | 🟡 Partly | Client nodes are derived from name strings, so two "Sara"s collapse into one node. Sellers are the literal "the seller". | diwan/graph.py:72, diwan/documents.py:51 |
| Person: staff | 🟡 Partly | Hard-coded dict of 9 (Layla, Omar...). | diwan/people.py:4 |
| Person: owner/landlord/developer contact types | ❌ Missing | No record type. A developer is a name string in rules. | diwan/desk_rules.py:36 |
| Person: phone | 🟡 Partly | Sits on the chat node, not the person. | diwan/graph.py:272 |
| Person: email | 🟡 Partly | Only inside a portal `chat.received` payload or a qualify answer. | diwan/leads.py:421, diwan/qualify.py:74 |
| Person: WhatsApp | 🟡 Partly | The chat id is the phone. Same-person merge exists. T: `tests/test_nudge.py`, chat.merged. | diwan/graph.py:290, diwan/leads.py:244 |
| Person: language | ❌ Missing | Arabic detected per message by regex; nothing stored. | diwan/agents/reception.py:1256 |
| Person: consent | 🟡 Partly | Recording consent per meeting only; no contact-consent field. | diwan/office.py:58 |
| Person: stop flag | 🟡 Partly | Works, but is stored on the deal (`optout`), not the Person. T: test_nudge:94. | diwan/graph.py:436, diwan/agents/nudge.py:320 |
| Person written by Front Desk, Sales | 🟡 Partly | Any `graph.person()` call creates one implicitly. | diwan/graph.py:72 |
| Case: one record per intent, first message to keys | ✅ Built (as `deal`) | A lead is `deal.opened` with id `lead-xxxx`; the same node continues into the Deal desk. | diwan/leads.py:413, diwan/graph.py:195 |
| Case: single `stage` field | ✅ Built (as `deal.props.stage`) | Set by `stage.changed`. | diwan/graph.py:296 |
| Case: single owner room | ❌ Missing | No `owner_room`. | diwan/graph.py:195 |
| Case: only owner room advances stage | ❌ Missing | The deal's broker, transactions officer or owner may move any stage; the Inbox also auto-moves. | diwan/desk_stages.py:28, diwan/inbox.py:260 |
| Case: `created_from` channel, Person link (Cmd 0) | 🟡 Partly | Channel only on the chat message; link via a `customer_of` edge to a name. | diwan/graph.py:199 |
| Fact: exact quote | ✅ Built | T: test_nova:33. | diwan/office.py:83 |
| Fact: source (chat/call/meeting) | 🟡 Partly | No field; only inferable through `caused_by`. | diwan/agents/scribe.py:168 |
| Fact: timestamp | ✅ Built | Event `at`. | diwan/graph.py:64 |
| Fact: Case link | ✅ Built | `deal` plus an `about` edge. | diwan/graph.py:202 |
| Fact: never edited, only superseded | ✅ Built | Append-only with `superseded_by`. Qualify answers are excluded, see next row. T: test_nova:41. | diwan/events.py:61, diwan/graph.py:210 |
| Fact: qualification answers are Facts | ❌ Missing | `qualify.answer` is a second quoted store, overwritten in place on the deal; it bypasses supersede. | diwan/graph.py:413 |
| Fact written by Scribe, Sales, Deal | ✅ Built | Scribe, Rania via `hear`, conversion price. | diwan/agents/scribe.py:204, diwan/desk_stages.py:168 |
| Task: owner room | 🟡 Partly | `team` = agent's parent, not a room. | diwan/office.py:136 |
| Task: assignee (agent or person) | ✅ Built | `agent` + `needs_person`. Role work follows the role holder. | diwan/office.py:136, diwan/roles.py:24 |
| Task: due date | 🟡 Partly | Only schedule-derived tasks carry `due`; no `due_at` param, Lobby deadline lives on the card. | diwan/office.py:131, diwan/agents/finance.py:68 |
| Task: depends on Facts | ✅ Built (as `rests_on`) | Optional; many tasks pass none (docs, Rania handover). T: test_nova:41. | diwan/graph.py:218, diwan/documents.py:209 |
| Task: status | ✅ Built | queued/working/withdrawn/done. | diwan/graph.py:21 |
| Task: `waiting_on` (Cmd 0) | 🟡 Partly | Free text on paperwork steps only. | diwan/agents/operations.py:108 |
| Document: file with a type | ✅ Built | `document.filed`, `docs.received`. | diwan/office.py:195, diwan/documents.py:207 |
| Document: check result | 🟡 Partly | Flags/reject reason in docs.* events; the filed archive record has none. | diwan/documents.py:202, diwan/office.py:199 |
| Document: Task it satisfies | 🟡 Partly | Reverse link only: the check task names token and kind. | diwan/documents.py:210 |
| Approval: a person's yes | ✅ Built | `approval.given`. | diwan/office.py:145 |
| Approval: on a specific version of Task output | 🟡 Partly | Free-text `action`; no task or draft version link. | diwan/app.py:858 |
| Approval: pinned to Facts | ✅ Built | `rests_on`; fact ids are immutable, so an id is a version. T: test_nova:59. | diwan/graph.py:232, diwan/office.py:158 |
| Approval: Review then a human | 🟡 Partly | Draft check runs automatically, but `office.approve` has no Review gate. | diwan/agents/review.py:67, diwan/office.py:145 |
| Event: append-only log | ✅ Built | DB triggers refuse update and delete. T: test_infra. | diwan/events.py:61 |
| Event: who, what, Case | ✅ Built | actor, agent, type, deal. | diwan/events.py:58 |
| Event: which Facts | 🟡 Partly | No column; only inside some payloads. | diwan/events.py:58 |
| Event: every room subscribes | ❌ Missing | No subscriber registry or consumer; a fixed-type allowlist plus the graph fold. | diwan/events.py:11, diwan/graph.py:188 |

### Three rules

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| R1: room never calls another room | ❌ Missing | The Office calls compliance, finance, operations and review directly; desk_stages calls agency_forms. | diwan/office.py:9, :91-94, :101, diwan/desk_stages.py:80 |
| R1: writes named Events (`case.qualified`, `doc.signed`, `payment.marked_received`) | 🟡 Partly (renamed) | Nearest are `qualify.passed`, `sign.signed`, `task.done` with result received. | diwan/events.py:40, :30, diwan/agents/finance.py:93 |
| R1: next room picks up the event | ❌ Missing | Only `custom_loop` polls for owner-added agents. | diwan/app.py:92 |
| R1: event with no subscriber shows as stuck | ❌ Missing | Nothing computes it. | diwan/desk_kpis.py:64 |
| R2: exit checklist per stage | 🟡 Partly | Closing checklist before Won only; intermediate stages have none. T: test_desk_rules. | diwan/desk_stages.py:58, diwan/agents/operations.py |
| R2: owner room ticks | 🟡 Partly | Closing items by role only. | diwan/desk_rules.py:55 |
| R2: Review checks the move | ❌ Missing | `move()` has no Review step. | diwan/desk_stages.py:47 |
| R2: human approves the move | 🟡 Partly | A person moves it, and there is a discount gate; no separate approval. T: test_desk_rules. | diwan/desk_stages.py:52, :131 |
| R3: dependent Tasks reopened | 🟡 Partly | Withdrawn, not reopened; only Form F/deck/agency drafts re-plan. T: test_deal_desk:182. | diwan/office.py:106, diwan/agents/operations.py:60 |
| R3: dependent Approvals reopened | ✅ Built | Decision card to the approver. T: test_nova:59. | diwan/agents/review.py:14 |
| R3: only dependents touched | ✅ Built | T: test_nova:41. | diwan/graph.py:105 |
| R3: Compliance told first | 🟡 Partly | Only for money kinds; other corrections skip Compliance. | diwan/agents/compliance.py:22 |
| R3: nothing downstream approved until re-done | 🟡 Partly | `execute` refuses stale, but `approve` accepts stale `rests_on`. | diwan/office.py:145, :158 |

### Where it most likely breaks

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Lead and deal in different tables, Facts lost | ✅ Built (not broken) | Same deal node; Facts carry over. T: test_inbox:34. | diwan/leads.py:413 |
| Rooms call functions, handoff silently dropped | ❌ Missing (still broken) | Direct calls everywhere, and failures have no retry or queue. | diwan/office.py:91 |
| No `depends_on_facts` | ✅ Built (as `rests_on`) | Coverage is uneven. | diwan/graph.py:218 |
| Reminders scheduled in more than one place | 🟡 Partly | One loop, but 5 separate schedulers with separate rules. | diwan/app.py:70-75 |
| Same issue: clients messaged at different hours | 🟡 Partly | The docs sweep hard-codes 09-20 and ignores quiet settings and Friday prayer. | diwan/documents.py:256 |

### Front Desk modes

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Nova always knows and shows the mode | ❌ Missing | No mode state or chip anywhere. | diwan/agents/nova.py:173 |
| Arrival: trigger, first open of the day | ❌ Missing | No per-day open tracking. | web/office3d.html:908 |
| Arrival: "good morning" trigger | 🟡 Partly | Smalltalk gives a count; not once-a-day, not the brief. | diwan/agents/nova.py:273 |
| Arrival: greets by name | ✅ Built | T: test_frontdesk:94. | diwan/agents/nova.py:543 |
| Arrival: leads with top 3, no wall of text | ❌ Missing | Reads all lines. | diwan/agents/nova.py:547 |
| Brief: "what's going on?" trigger | 🟡 Partly | "what's new/happening" matches; "going on" does not. | diwan/agents/nova.py:199 |
| Brief: never repeats dismissed items | ❌ Missing | No dismiss. | diwan/agents/nova.py:506 |
| Pocket: "Hey Pocket" trigger | ❌ Missing | Word absent from `diwan/` and `web/`. | none |
| Pocket: "I'm in a meeting" trigger | ❌ Missing | | diwan/agents/nova.py:173 |
| Pocket: calendar-event trigger | ❌ Missing | | diwan/app.py:779 |
| Pocket: silent, listens, transcribes | 🔑 Needs connection (other purpose) | Broker-run client meeting tied to a deal, by hand, with consent. Live audio needs META_API_KEY. | web/meeting.html, diwan/app.py:812-821 |
| Pocket: speaks only to wake word | ❌ Missing | | none |
| Pocket: summary afterwards | 🟡 Partly | Visit summary of the client's turns only. | diwan/agents/visit.py:95 |
| Pocket: decisions | ❌ Missing | | diwan/agents/visit.py:55 |
| Pocket: action items with owners | ❌ Missing | Only one `next_step`; no Tasks. | diwan/agents/visit.py:55 |
| Pocket: linked to exact quotes | ✅ Built | Non-quoted points dropped. | diwan/agents/visit.py:78 |
| Pocket: client statements become Facts, correction rule | ✅ Built | T: test_scribe, test_api:14. | diwan/agents/scribe.py:162 |
| Ask: from Records | ✅ Built | T: test_records. | diwan/agents/records.py:124 |
| Ask: from the calendar | 🟡 Partly | Booked viewings list only. | diwan/agents/nova.py:314 |
| Ask: from the Case log | ✅ Built | Graph records. | diwan/agents/nova.py:106 |
| Ask: from the web | ❌ Missing | | diwan/agents/nova.py:208 |
| Ask: says where the answer came from | ✅ Built | T: test_nova:78. | diwan/agents/nova.py:252, web/index.html:57 |
| Ask: "not recorded", no guess | ✅ Built | Wording differs. T: test_nova:97. | diwan/agents/nova.py:233 |
| Errand mode (research, plan, wait for yes) | ❌ Missing | Only the Lobby read-back resembles it. T: test_frontdesk:32. | diwan/agents/lobby.py:104 |
| DND: owner says so | ❌ Missing | | diwan/agents/nova.py:173 |
| DND: after hours | ❌ Missing | Quiet hours apply to client follow-ups only. | diwan/agents/nudge.py:72 |
| DND: queue except urgent | ❌ Missing | `notify` always sends. | diwan/leads.py:474 |

### Morning brief

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Built 7:30 Dubai | 🟡 Partly | Rounds fire 30 min before the earliest per-person time; default 09:00, charter says 07:00. T: test_nova:174. | diwan/agents/nova.py:558, diwan/app.py:66 |
| Working days only | ❌ Missing | Daily. | diwan/agents/nova.py:565 |
| Ready before arrival | 🟡 Partly | Rounds pre-built, the brief itself on read; `morning()` is never called. `last_brief` is in memory. | diwan/agents/nova.py:579, diwan/app.py:764 |
| Built from last 24h Events across rooms | 🟡 Partly | Open state, not an event window; Marketing not in `LEADS`. | diwan/agents/nova.py:488 |
| Urgent: anything overdue | 🟡 Partly | Late Lobby cards only. | diwan/agents/nova.py:519 |
| Urgent: Compliance flag | 🟡 Partly | Reaches Priya only, not the owner. Rounds line is a count. | diwan/agents/nova.py:511 |
| Urgent: payment due today | ❌ Missing | | diwan/agents/nova.py:506 |
| Urgent: unanswered call request | ❌ Missing | Attention cards not read. | diwan/agents/nova.py:506 |
| Today: meetings | ❌ Missing | | diwan/agents/nova.py:506 |
| Today: viewings | ❌ Missing | Separate broker notice only. | diwan/agents/reminders.py:109 |
| Today: client's last message | ❌ Missing | | none |
| Today: what the client cares about | ❌ Missing | | none |
| Pipeline: new leads | ❌ Missing | | none |
| Pipeline: hot leads | ❌ Missing | | none |
| Pipeline: deals that moved stage | ❌ Missing | | none |
| Pipeline: stuck more than N days | ❌ Missing in brief | KPI exists on Deal desk; N is one number. | diwan/desk_kpis.py:64 |
| Money: invoices sent | ❌ Missing | | none |
| Money: payments received | ❌ Missing | | none |
| Money: commissions due | ❌ Missing | | none |
| Decisions: approvals, one line each | 🟡 Partly | Lines exist. | diwan/agents/nova.py:511 |
| Decisions: approve / send back button | ❌ Missing | Chips only. | web/index.html:69 |
| One Lobby idea | ❌ Missing | Room 9 forum does not exist. | diwan/agents/lobby.py:1 |

### Errands

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Each errand ends in a draft the owner approves | 🟡 Partly | Lobby cards only. | diwan/agents/lobby.py:114 |
| Travel: search flights/hotels, compare 3 | ❌ Missing | No code. | none |
| Travel: hold if allowed | ❌ Missing | | none |
| Travel: read email, confirm names and dates | ❌ Missing | | none |
| Email: draft in owner's style | ❌ Missing | No email provider. | diwan/providers/ |
| Email: schedule sends | ❌ Missing | | none |
| Messages: chase non-responders | 🟡 Partly | Staff Lobby cards; client nudges by Rania. | diwan/agents/lobby.py:175, diwan/agents/nudge.py:264 |
| Calendar: book/move via Nova | ❌ Missing | Calendar API exists; Nova has no intent. | diwan/app.py:1643, diwan/agents/nova.py:173 |
| Calendar: decline | ❌ Missing | Cancel in UI only. | diwan/app.py:1690 |
| Calendar: protect focus time | 🟡 Partly | Manual busy blocks. T: test_own_time. | diwan/app.py:1605 |
| Calendar: travel time between viewings | ❌ Missing | No gap between appointments. | diwan/slots.py |
| Research: prices, listings, track record, news | ❌ Missing | Web search exists only in the studio. | diwan/agents/studio.py |
| Laptop/phone: open, find, fill, stop at Submit | ❌ Missing | | none |
| "Remind me Thursday to call Sara" becomes Task | ❌ Missing | "me" resolves to nobody; no self-reminder. Sara would become a target only if she were staff. | diwan/agents/lobby.py:73-88 |

### Front Desk emits

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| `task.created` from owner instructions | ✅ Built | T: test_nova:130. | diwan/agents/nova.py:424, diwan/agents/lobby.py:157 |
| `task.created` from meeting action items | ❌ Missing | | diwan/app.py:800 |
| `fact.recorded` from owner relay | ❌ Missing | Named `fact.created`; `converse` never records relayed facts. | diwan/agents/nova.py:173 |
| `approval.given` from the brief | ❌ Missing | Given via `/api/approvals`, not the brief. | diwan/app.py:865 |
| `approval.declined` from the brief | ❌ Missing | `approval.refused` is the guard or cancel. | diwan/agents/review.py:48 |

### Notifications

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| One notification service | 🟡 Partly | `notify()` exists; Lobby, tasks and checks bypass it. | diwan/leads.py:474, diwan/agents/lobby.py:183 |
| Three levels Now/Today/Brief | ❌ Missing | Only `kind` labels. | diwan/leads.py:474 |
| Now: push | 🟡 Partly | Browser `Notification` on the Inbox page only; no service worker. | web/inbox.html:394 |
| Now: WhatsApp to the person | 🔑 Needs connection | Needs phone, NOTIFY_TEMPLATE, AiSensy. Applies to every notice, not by level. | diwan/leads.py:481 |
| Now: repeats once after 10 min | ❌ Missing | | diwan/leads.py:172 |
| Now: then escalates | 🟡 Partly | Overdue tells the owner, then Pool at 60 min, for lead cards only. | diwan/leads.py:179-191 |
| Now examples: client asked for call | ✅ Built | Attention card and notice. T: test_leads. | diwan/leads.py:146 |
| Now examples: Compliance hit | ❌ Missing | No notice. | diwan/agents/compliance.py:25 |
| Now examples: payment mismatch | ❌ Missing | No proof reader. | diwan/agents/finance.py |
| Today: in-app | 🟡 Partly | Notices on screen. | diwan/app.py:1228 |
| Today: midday summary | ❌ Missing | | none |
| Brief level: brief only | ❌ Missing | | none |
| Quiet hours on client messages | 🟡 Partly | Nudges, reminders. Docs sweep has own hours. T: test_nudge:82. | diwan/agents/nudge.py:72, diwan/documents.py:256 |
| Friday prayer on client messages | 🟡 Partly | Same two sweeps; docs sweep ignores it. | diwan/agents/nudge.py:79 |
| DND on client messages | ❌ Missing | | none |
| Quiet/prayer/DND on staff unless Now | ❌ Missing | `notify` ignores all. | diwan/leads.py:474 |

### Who may do what

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Agents may read, draft, check | ✅ Built | Charter lists, enforced at submit. T: test_infra. | diwan/agents/runner.py:140 |
| Agents may fill up to Submit | 🟡 Partly | Field plan only; no portal driver, though charter says "browser". | diwan/agents/operations.py:64 |
| Agents may schedule reminders | ✅ Built | | diwan/agents/reminders.py:68 |
| Agents message clients inside 24h or with templates | ✅ Built | T: test_calendar_basics:85, test_nudge. | diwan/agents/reception.py:612, diwan/agents/nudge.py:285 |
| Only a person: approve | ✅ Built | T: test_nova:146. | diwan/agents/nova.py:58 |
| Only a person: submit to portal | ✅ Built | Role-checked record of it. | diwan/agents/operations.py:81 |
| Only a person: pay | ✅ Built | Release role-checked. | diwan/agents/finance.py:99 |
| Only a person: sign | ✅ Built | Signing links for people. | diwan/signing.py |
| Only a person: mark money received | ✅ Built | Role check, reference required. | diwan/agents/finance.py:80 |
| Only a person: file regulatory report | ✅ Built | | diwan/agents/compliance.py:92 |
| Only a person: clear a screening hit | ✅ Built | T: test_deal_desk:84. | diwan/agents/compliance.py:77 |
| No portal/bank/email passwords held | ✅ Built | By absence; WhatsApp, IG and Zoom API keys are in `.env`. | web/settings.html:52 |
| Sign-in in the person's own browser | 🟡 Partly | Person acts on the portal outside Diwan; nothing session-based exists. | diwan/agents/operations.py:81 |
| Broker sees only their Cases | ❌ Missing | `/api/chats` and `/api/desk/*` are unfiltered within Sales. T asserts department only. | diwan/inbox.py:123, diwan/deal_desk.py:313, tests/test_access.py:63 |
| Finance sees money | 🟡 Partly | Finance gets the whole deal view. | diwan/deal_desk.py:345 |
| Owner sees all | ✅ Built | T: test_access:105. | diwan/access.py:98 |

### When something fails

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Model call: retry once | ❌ Missing | No retry; the second POST in `complete_json` is a format fallback. | diwan/providers/chat.py:86 |
| Model call: fall back to rules | 🟡 Partly | Nova, Scribe, Rania, visit do; `run()` logs and raises for others. T: test_infra:153. | diwan/agents/nova.py:243, diwan/agents/runner.py:171 |
| Output marked as fallback | 🟡 Partly | `by: rules` in Nova and Rania; `live_failed` on tapes. | diwan/agents/nova.py:252, diwan/agents/runner.py:114 |
| Event with no subscriber on Stuck board | ❌ Missing | | none |
| Overdue Task on Stuck board | ❌ Missing | No Stuck board on HQ; no task-overdue sweep. | web/office3d.html |
| Stuck deals tile | 🟡 Partly | KPI on Deal desk only. | diwan/desk_kpis.py:64, web/deal.html:337 |
| Overdue in the brief | ❌ Missing | Lobby lates only. | diwan/agents/nova.py:519 |
| Undeliverable: outside 24h, Task for broker to call | 🟡 Partly | Docs sweep raises a Task; nudges and reminders only log "skipped". | diwan/documents.py:287, diwan/agents/nudge.py:288, diwan/agents/reminders.py:94 |
| Undeliverable: number blocked | ❌ Missing | `_send` logs status failed; no Task. T: test_inbox:72. | diwan/agents/reception.py:559 |
| Turn logs charter version | ❌ Missing | Only `RULES_VERSION`. | diwan/pack.py:38 |
| Turn logs inputs | 🟡 Partly | Source ids and task; rules code often `sources={}`. | diwan/agents/runner.py:165 |
| Turn logs Facts used | 🟡 Partly | Evidence only. | diwan/agents/runner.py:149 |
| Turn logs outcome | ✅ Built | Pack, allowed, refused. | diwan/agents/runner.py:149 |
| Any output replayable | 🟡 Partly | Graph rewind and tapes; no replay by turn. T: test_nova:53. | diwan/office.py:21, diwan/providers/tape.py |

### A PA for every staff member

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Every signed-in person has a PA | ❌ Missing | `/api/nova/*` is owner-only. T asserts staff get 403. | diwan/access.py:53-63, tests/test_access.py:112 |
| Identity: one PA per account | ❌ Missing | | none |
| Identity: named by person, default "[Name]'s PA" | ❌ Missing | | none |
| Identity: voice and tone per person | ❌ Missing | | none |
| "Ask your PA" box | ❌ Missing | Still "Ask Nova..." | web/office3d.html:109 |
| Scope: role-limited | ❌ Missing | Nova's `person` is any name, owner-chosen dropdown. | web/index.html:24 |
| Scope: no other broker's clients | ❌ Missing | Hard-coded "omar" check. | diwan/agents/nova.py:89 |
| On call: chat box on every page | ❌ Missing | Only office3d and index. | web/app.js:141, web/inbox.html:671 |
| On call: push-to-talk | 🟡 Partly | Mic on HQ via the browser, owner only. | web/office3d.html:109 |
| On call: wake word on desktop | ❌ Missing | | none |
| On call: WhatsApp to own number | ❌ Missing | One-way notices only. | diwan/leads.py:481 |
| Morning: personal brief | 🟡 Partly | `brief()` is per person; staff cannot reach it. | diwan/agents/nova.py:506 |
| Morning: their calls | ❌ Missing | | none |
| Morning: their viewings | 🟡 Partly | Broker notice. | diwan/agents/reminders.py:109 |
| Morning: Tasks due | 🟡 Partly | Tasks listed, no due logic. | diwan/agents/nova.py:524 |
| Morning: items waiting on them | ✅ Built | T: test_nova:166. | diwan/agents/nova.py:511 |
| Morning: assigned overnight | ❌ Missing | | none |
| Doing: drafts/schedules/reminds/fills/searches via PA | ❌ Missing | | none |
| Doing: asks before client send | ❌ Missing as PA | | none |
| Doing: never approves on person's behalf | ✅ Built for Nova | Regex refusal. | diwan/agents/nova.py:58 |
| Handoff: "Tell Finance..." | 🟡 Partly | Lobby with read-back, owner only. Text "deposit came in" is a card, not a Finance action. T: test_frontdesk:32. | diwan/agents/lobby.py:71 |
| Handoff: Finance's PA picks it up | ❌ Missing | | none |
| Handoff: no PA-to-PA, via log | ✅ Built by absence | | diwan/agents/lobby.py:146 |
| Escalation: person first | 🟡 Partly | Lobby reminder before due; no Task sweep. | diwan/agents/lobby.py:186 |
| Escalation: room lead's PA | ❌ Missing | | none |
| Escalation: Nova | 🟡 Partly | Lead cards notify owner. | diwan/leads.py:191 |
| Memory: preferences as settings | 🟡 Partly | Only `briefing_time`; lessons are per agent. | diwan/app.py:718, diwan/agents/lessons.py |
| Out-of-office cover (spec line 807) | 🟡 Partly | "Away today" routing only. | diwan/leads.py:75 |

### Who sees which rooms

Finding: the gate is by department (`diwan/access.py:49-63`), with no row or field masking. Sales, Ops, Finance and Compliance all receive the identical `deal_view`, including `funds` (`diwan/deal_desk.py:89`). Status-only does not exist anywhere. Rooms Front Desk (`/api/nova`), Records (`/api/records`), Review and the Lobby board are unlisted, so they are owner-only.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Owner: all nine rooms | ✅ Built | T: test_access:105. | diwan/access.py:98 |
| Broker, Front Desk: own brief | 🟡 Partly | Appointment notice only. | diwan/agents/reminders.py:109 |
| Broker, Sales: own leads | 🟡 Partly | Sees all; "mine" is a view. | diwan/inbox.py:124 |
| Broker, Deal: own deals | 🟡 Partly | Sees all deals. | diwan/deal_desk.py:313 |
| Broker, Ops: status only | ❌ Missing | Full. | diwan/deal_desk.py:345 |
| Broker, Finance: own commission | ❌ Missing | Whole deal commission, no per-broker view. | diwan/deal_desk.py:353 |
| Broker, Compliance: status only | ❌ Missing | Full `funds` shown. | diwan/deal_desk.py:89 |
| Broker, Review: own items | 🟡 Partly | Own cards on desk. | diwan/deal_desk.py:331 |
| Broker, Records: own numbers | ❌ Missing | Owner only. | diwan/access.py:97 |
| Broker, Lobby: read | ❌ Missing | | diwan/access.py:53 |
| Sales lead, Front Desk: own brief | ❌ Missing | No morning notice: role not `Broker`. | diwan/agents/reminders.py:111 |
| Sales lead, Sales: all leads | ✅ Built | Dept mapped to sales. T: test_access:99. | diwan/access.py:82 |
| Sales lead, Deal: all deals | ✅ Built | | diwan/access.py:40 |
| Sales lead, Ops: status only | ❌ Missing | Full. | diwan/deal_desk.py:345 |
| Sales lead, Finance: team commission | ❌ Missing | | none |
| Sales lead, Compliance: status only | ❌ Missing | Full. | diwan/deal_desk.py:89 |
| Sales lead, Review: team items | ❌ Missing | | none |
| Sales lead, Records: team numbers | ❌ Missing | | diwan/access.py:97 |
| Sales lead, Lobby: read, propose | ❌ Missing | | none |
| Deal/Ops, Front Desk: own brief | ❌ Missing | | diwan/access.py:53 |
| Deal/Ops, Sales: read | ❌ Missing | Inbox is {SALES}. | diwan/access.py:49 |
| Deal/Ops, Deal: all | ✅ Built | | diwan/access.py:50 |
| Deal/Ops, Ops: all | ✅ Built | | diwan/access.py:50 |
| Deal/Ops, Finance: status only | ❌ Missing | Full. | diwan/deal_desk.py:353 |
| Deal/Ops, Compliance: status only | ❌ Missing | Full. | diwan/deal_desk.py:89 |
| Deal/Ops, Review: own items | 🟡 Partly | Desk cards. | diwan/deal_desk.py:331 |
| Deal/Ops, Records: Deals | ❌ Missing | | diwan/access.py:97 |
| Deal/Ops, Lobby: read | ❌ Missing | | none |
| Finance, Front Desk: own brief | ❌ Missing | | diwan/access.py:53 |
| Finance, Sales: No | ✅ Built | T: test_access:80. | diwan/access.py:49 |
| Finance, Deal: Amounts | ❌ Missing | Full deal, not amounts only. | diwan/deal_desk.py:345 |
| Finance, Ops: No | ❌ Missing | Sees it in deal view. | diwan/deal_desk.py:70 |
| Finance, Finance: all | ✅ Built | | diwan/access.py:50 |
| Finance, Compliance: payment flags | ❌ Missing | Full. | diwan/deal_desk.py:89 |
| Finance, Review: own items | 🟡 Partly | | diwan/deal_desk.py:331 |
| Finance, Records: Money | ❌ Missing | | diwan/access.py:97 |
| Finance, Lobby: read | ❌ Missing | | none |
| Compliance, Front Desk: own brief | ❌ Missing | | diwan/access.py:53 |
| Compliance, Sales: read | ❌ Missing | 403 on chats. T: test_access:83. | diwan/access.py:58 |
| Compliance, Deal: read | 🟡 Partly | Sees it; write endpoints are open to the dept, role checks vary. | diwan/access.py:61 |
| Compliance, Ops: read | 🟡 Partly | In deal view. | diwan/deal_desk.py:70 |
| Compliance, Finance: Payments | 🟡 Partly | In deal view. | diwan/deal_desk.py:76 |
| Compliance, Compliance: all | ✅ Built | | diwan/agents/compliance.py:77 |
| Compliance, Review: own items | 🟡 Partly | | diwan/deal_desk.py:331 |
| Compliance, Records: Compliance files | ❌ Missing | | diwan/access.py:97 |
| Compliance, Lobby: read | ❌ Missing | | none |
| "Status only" definition (done/blocked, no contents) | ❌ Missing | No masking code. | diwan/deal_desk.py:345 |

Marketing has a real department in code but no row in the spec.

### Part 5 shared kit

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Built once, configured per role | ❌ Missing | Nova is a single module. | diwan/agents/nova.py |
| Reach: chat on every page | ❌ Missing | | web/app.js:141 |
| Reach: voice | 🟡 Partly | HQ mic only. | web/office3d.html:109 |
| Reach: WhatsApp | ❌ Missing | Outbound only. | diwan/leads.py:481 |
| Reach: push | 🟡 Partly | Inbox page only. | web/inbox.html:394 |
| Limit: speaks only to own person | ❌ Missing | Owner picks "I am". | web/office3d.html:915 |
| Limit: never to clients except via Rania or approved message | ✅ Built | Nova has no send action. | diwan/agents/charters.py:42 |
| Knowledge: Cases, Facts, Tasks, Documents, Events by role | 🟡 Partly | Owner-wide graph, no role filter. | diwan/agents/nova.py:106 |
| Knowledge: calendar | 🟡 Partly | Viewings. | diwan/agents/nova.py:314 |
| Knowledge: knowledge base | 🟡 Partly | Rania uses it; Nova only via graph search types. | diwan/agents/nova.py:132 |
| Knowledge: Settings | ❌ Missing | | none |
| Limit: "not recorded" | ✅ Built | | diwan/agents/nova.py:233 |
| Limit: cites every answer | 🟡 Partly | Some `everyday` branches cite nothing. | diwan/agents/nova.py:275 |
| Memory: working hours | 🟡 Partly | Broker shift. | diwan/leads.py:53 |
| Memory: call windows | ❌ Missing | | none |
| Memory: tone | ❌ Missing | | none |
| Memory: language | ❌ Missing | | none |
| Memory: what to brief first | ❌ Missing | | none |
| Memory: viewable and editable by person | ❌ Missing | Settings owner-only. | diwan/access.py:112 |
| Memory: archived on leaving | 🟡 Partly | Log kept; login removable. People stay in code. | diwan/access.py:164 |
| Brief: at person's start time | 🟡 Partly | Per-person time, on read. | diwan/agents/nova.py:561 |
| Brief: from overnight Events | 🟡 Partly | `since` param, always 0 in app. | diwan/agents/nova.py:506 |
| Brief: max 5 before "more" | ❌ Missing | | diwan/agents/nova.py:547 |
| Reminders: "remind me" becomes a Task | ❌ Missing | | diwan/agents/lobby.py:73 |
| Reminders: respects quiet hours | ❌ Missing | | diwan/agents/lobby.py:175 |
| Drafting: messages | 🟡 Partly | Rania, follow-up, no PA. | diwan/agents/followup.py |
| Drafting: emails | ❌ Missing | | none |
| Drafting: forms | ✅ Built (not PA) | Form F plan, agency forms. | diwan/agents/operations.py:64 |
| Drafting: invoices | ✅ Built (not PA) | | diwan/agents/finance.py:158 |
| Drafting: summaries | ✅ Built (not PA) | | diwan/agents/visit.py:59 |
| Limit: every draft shows Facts used | 🟡 Partly | Slides carry facts. | diwan/graph.py:244 |
| Doing: schedule, book viewings | 🟡 Partly | Rania books, no PA. | diwan/agents/charters.py:60 |
| Doing: create/assign Tasks | 🟡 Partly | Nova route, Lobby. | diwan/agents/nova.py:424 |
| Doing: fill portals to Submit | 🟡 Partly | Plan. | diwan/agents/operations.py:64 |
| Doing: search Records | ✅ Built for owner | | diwan/agents/records.py:124 |
| Limit: asks before client/outsider sees | 🟡 Partly | Lobby read-back; `send` in person lists. | diwan/agents/lobby.py:114 |
| Handoff through Tasks and Events only | ✅ Built | Log-based. | diwan/agents/lobby.py:150 |
| Escalation: person, lead's PA, Nova | ❌ Missing | | none |
| Escalation chain from Settings | ❌ Missing | | none |
| Never: pay | ✅ Built | "release", "pay him". T: test_nova:146. | diwan/agents/nova.py:59 |
| Never: sign | ❌ Missing | No regex; "sign" not refused. `sign off` only. | diwan/agents/nova.py:58 |
| Never: submit | ✅ Built | | diwan/agents/nova.py:57 |
| Never: file a report | ✅ Built | | diwan/agents/nova.py:61 |
| Never: clear a screening hit | ❌ Missing | Not in REFUSE. Still blocked by no agent path. | diwan/agents/nova.py:54-63 |
| Never: mark money received | ❌ Missing | Not in REFUSE. Same note. | diwan/agents/nova.py:54-63 |
| Never: approve on behalf | ✅ Built | | diwan/agents/nova.py:58 |
| Never: change Settings | ❌ Missing | Nova does change them: autonomy and briefing time by chat. | diwan/agents/nova.py:185-198 |
| Never: send bank details | ❌ Missing | Not in REFUSE. | diwan/agents/nova.py:54-63 |
| Refusals logged | ✅ Built | `agent.refused`. | diwan/agents/runner.py:155 |

### Each PA

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Nova: greets on arrival | 🟡 Partly | See section 4. | diwan/agents/nova.py:273 |
| Nova: brief across all rooms | 🟡 Partly | Marketing omitted. | diwan/agents/nova.py:488 |
| Nova: flags compliance holds | ❌ Missing | No holds exist. | diwan/deal_desk.py |
| Nova: flags overdue money | ❌ Missing | | none |
| Nova: flags unanswered call-me | 🟡 Partly | Notice, not Nova. | diwan/leads.py:191 |
| Nova: flags stuck deals | ❌ Missing | | none |
| Nova: Pocket | ❌ Missing | | none |
| Nova: weekly Monday numbers | ❌ Missing | | none |
| Nova: one Lobby idea | ❌ Missing | | none |
| Nova: "How's the Marina deal?" | ✅ Built | T: test_nova:192. | diwan/agents/nova.py:359 |
| Nova: "Who hasn't called Sara back?" | ❌ Missing | | none |
| Nova: "Book my trip" | ❌ Missing | | none |
| Nova: "Draft a reply to Ahmed" | ❌ Missing | | none |
| Nova: "Remind me Thursday" | ❌ Missing | | diwan/agents/lobby.py:73 |
| Nova: asks before send/booking/approval | 🟡 Partly | Refuses or reads back. | diwan/agents/nova.py:388 |
| Nova: 2-line end-of-day wrap | ❌ Missing | | none |
| Broker PA | ❌ Missing | No PA. Pieces exist in Inbox and Calendar. | diwan/access.py:53 |
| Broker: morning list | 🟡 Partly | | diwan/agents/reminders.py:109 |
| Broker: call-now alerts | ✅ Built (not PA) | | diwan/leads.py:146 |
| Broker: reminders 15 min before calls | ❌ Missing | Calls explicitly skipped. | diwan/agents/reminders.py:80 |
| Broker: drafts follow-ups | ✅ Built (not PA) | | diwan/agents/followup.py |
| Broker: nudges for missing outcomes | 🟡 Partly | Attention needs a recorded action. | diwan/leads.py:150 |
| Broker: listing availability checks | ❌ Missing | | none |
| Broker: permit and Form A expiry reminders | ❌ Missing | | none |
| Broker: "log viewing" command | ❌ Missing | UI only. | diwan/app.py:1690 |
| Broker: end of day checks | ❌ Missing | | none |
| Sales lead PA | ❌ Missing | | diwan/access.py:53 |
| Sales lead: team board | 🟡 Partly | Team and KPI pages. | diwan/leads.py:90 |
| Sales lead: escalate call-now after 10 min | 🟡 Partly | 15 min, to owner, not lead. | diwan/leads.py:32, :191 |
| Sales lead: daily sweep per broker | ❌ Missing | | none |
| Sales lead: unassigned leads | 🟡 Partly | Pool. | diwan/inbox.py:134 |
| Sales lead: duplicate merge | 🟡 Partly | Manual merge; no detection. | diwan/leads.py:244 |
| Sales lead: listing-to-buyer matches | 🟡 Partly | `recommend`. | diwan/agents/reception.py |
| Sales lead: "Give Omar's leads to Layla" | ❌ Missing | Single-chat reassign only. | diwan/leads.py:209 |
| Deal coordinator PA | ❌ Missing | | none |
| Deal: missing items per deal | ✅ Built (not PA) | | diwan/deal_desk.py:92 |
| Deal: follow-up ladder | 🟡 Partly | Reminder count; days, not 24/48/72h. | diwan/documents.py:254 |
| Deal: rebuild checklists after corrections | 🟡 Partly | Form drafts only. | diwan/agents/operations.py:60 |
| Deal: Form F from Facts | ✅ Built (not PA) | T: test_deal_desk:182. | diwan/agents/operations.py:64 |
| Deal: expiry warnings | 🟡 Partly | One flag at upload. | diwan/documents.py:169 |
| Deal: waiting-on-outsider aging | 🟡 Partly | `waiting_on`, touchpoints KPI. | diwan/desk_kpis.py:83 |
| Operations PA | ❌ Missing | | none |
| Ops: portal drafts to Submit | 🟡 Partly | Plan. | diwan/agents/operations.py:64 |
| Ops: trustee and NOC tracking | 🟡 Partly | Steps with manual tick; `transfer` agent is planned. | diwan/agents/charters.py:88 |
| Ops: reminds clients what to bring | 🟡 Partly | Viewing photo ID only. | diwan/agents/reminders.py:62 |
| Ops: permit renewals | ❌ Missing | | none |
| Ops: handovers/move-outs scheduled | 🟡 Partly | "after" steps, no scheduling. | diwan/desk_rules.py:65 |
| Ops: recalls forms after corrections | ✅ Built | T: test_desk_rules:119. | diwan/agents/operations.py:60 |
| Finance PA | ❌ Missing | | none |
| Finance: invoices at each trigger | 🟡 Partly | Commission invoice, drafted by a person's action. | diwan/agents/finance.py:158 |
| Finance: due and overdue lists | ✅ Built (not PA) | | diwan/agents/finance.py:65 |
| Finance: reads payment proofs, flags mismatches | ❌ Missing | | none |
| Finance: cheque dates | ✅ Built (not PA) | | diwan/agents/finance.py:249 |
| Finance: instalment reminders | 🟡 Partly | Expected tasks, no client reminders. | diwan/agents/finance.py:265 |
| Finance: commission splits and payouts | 🟡 Partly | Other-agency split; no broker payout list. | diwan/agents/finance.py:191 |
| Finance: "Mark AED 50,000" opens form | ❌ Missing via PA | Form exists on desk. | diwan/deal_desk.py:481 |
| Finance: cash summary | ❌ Missing | | none |
| Compliance PA | ❌ Missing | | none |
| Compliance: corrections side by side | ✅ Built (not PA) | | diwan/agents/compliance.py:20 |
| Compliance: screening hits | 🟡 Partly | Manual, no list. | diwan/agents/compliance.py:63 |
| Compliance: source-of-funds files | ✅ Built (not PA) | | diwan/agents/compliance.py:111 |
| Compliance: holds with reasons | ❌ Missing | | none |
| Compliance: report drafts | ✅ Built (not PA) | T: test_deal_desk:118. | diwan/agents/compliance.py:162 |
| Compliance: threshold alerts | 🟡 Partly | Cash only. | diwan/agents/compliance.py:169 |
| Compliance: fraud-guard flags | ❌ Missing | | none |
| Marketing PA | ❌ Missing | `mchat`/lead_chat is a Marketing lead agent, similar in shape, not a personal PA. | diwan/agents/lead_chat.py |
| Marketing: scripts to approve | ✅ Built (not PA) | | diwan/app.py:479 |
| Marketing: listings needing content | ✅ Built (not PA) | | diwan/agents/rhythm.py:116 |
| Marketing: competitor posts | ✅ Built, NEEDS-CONNECTION | Instagram key. | diwan/agents/studio.py:381 |
| Marketing: pauses posts on permit expiry or withdrawal | ❌ Missing | Planning skips withdrawn listings, but a scheduled or live post is never paused; no expiry. | diwan/agents/rhythm.py:122 |
| Rania: replies in 24h window | ✅ Built, NEEDS-CONNECTION | WhatsApp. Sandbox otherwise. | diwan/agents/reception.py:530 |
| Rania: qualifies | ✅ Built | T: test_qualify. | diwan/qualify.py |
| Rania: books viewings | ✅ Built | T: test_calendar. | diwan/agents/charters.py:60 |
| Rania: sends portal links and receipts | 🟡 Partly | Docs link in reminders; no receipts. | diwan/documents.py:284 |
| Rania: follow-ups on schedule | ✅ Built | T: test_nudge:40. | diwan/agents/nudge.py:264 |
| Rania: visa/legal/tax advice goes to broker | 🟡 Partly | Returns have a fixed reply; visa and legal questions got an ordinary greeting when tried; tax only by accident. | diwan/agents/charters.py:59 |

### Owner settings

General: there is no single Settings page. Settings are spread across `web/settings.html`, the Deal desk rules (`web/deal.html:275`), the Calendar gear, `web/qualify.html`, Studio Setup and `.env`.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Everything on one Settings page | ❌ Missing | See above. | web/settings.html:191 |
| Office: name | ✅ Built | `agency.name`. | diwan/desk_rules.py:37 |
| Office: licence numbers | 🟡 Partly | ORN and BRNs; no trade licence. | diwan/desk_rules.py:37, :40 |
| Office: TRN | ✅ Built | | diwan/desk_rules.py:37 |
| Office: address | ✅ Built | | diwan/desk_rules.py:37 |
| Office: working hours | ✅ Built | Calendar setting. | diwan/slots.py:14 |
| Office: quiet hours | ✅ Built | | diwan/agents/nudge.py:19 |
| Office: Friday prayer window | 🟡 Partly | On/off; window hard-coded. T: test_nudge:82. | diwan/agents/nudge.py:22 |
| Office: public holidays | ❌ Missing | | diwan/slots.py:14 |
| Office: languages Rania speaks | ❌ Missing | `business.languages` is posting only. | diwan/business.py:128 |
| People: staff | ❌ Missing | Code dict. | diwan/people.py:4 |
| People: roles | 🟡 Partly | 3 desk roles assignable. T: test_desk_rules. | diwan/roles.py:55 |
| People: rooms they see | ❌ Missing | Code. | diwan/access.py:49 |
| People: display names | ❌ Missing | Code. | diwan/people.py:4, web/app.js:2 |
| People: who covers whom | ❌ Missing | "Away today" only. | web/settings.html:249 |
| People: PA names | ❌ Missing | | none |
| Sales: qualifying forms per intent | ✅ Built | T: test_qualify. | diwan/app.py:1727 |
| Sales: heat-score rules | 🟡 Partly | `hot_on` triggers, no score. | diwan/agents/reception.py:1098 |
| Sales: call-now limit (default 10) | 🟡 Partly | Env var, default 15. | diwan/leads.py:32 |
| Sales: follow-up schedule | ✅ Built | T: test_nudge. | diwan/agents/nudge.py:41 |
| Sales: routing round-robin | ✅ Built | T: test_leads. | diwan/leads.py:96 |
| Sales: routing by area | 🟡 Partly | Via deal-kind rule. | diwan/deal_kinds.py |
| Sales: routing by language | ❌ Missing | | diwan/leads.py:96 |
| Deal: checklist per deal type | ✅ Built | | diwan/desk_rules.py:41 |
| Deal: checklist per party type | 🟡 Partly | Document list per party. | diwan/desk_rules.py:32 |
| Deal: document expiry warnings | 🟡 Partly | Hard-coded 60 days, not a setting. | diwan/documents.py:169 |
| Deal: follow-up ladder 24/48/72h | 🟡 Partly | Every N days, count M. | diwan/desk_rules.py:34 |
| Deal: portal link lifetime | ✅ Built | `sign_link_days`. | diwan/desk_rules.py:31 |
| Money: commission per type and payer | ✅ Built | T: test_desk_rules. | diwan/desk_rules.py:44 |
| Money: VAT | ✅ Built | | diwan/desk_rules.py:28 |
| Money: invoice triggers | ❌ Missing | | none |
| Money: deposit rule | ✅ Built | `deposit_held_by`, `deposit_pct`. | diwan/desk_rules.py:38 |
| Money: payout split rules | 🟡 Partly | Per-deal other-agency share; no broker split. | diwan/desk_rules.py:240 |
| Money: reminder schedule | ❌ Missing | | none |
| Compliance: cash threshold | ✅ Built | T: test_deal_desk:118. | diwan/desk_rules.py:27 |
| Compliance: source-of-funds threshold | ❌ Missing | | none |
| Compliance: screening lists | ❌ Missing | No list; manual result. | diwan/agents/compliance.py:64 |
| Compliance: high-risk rules | ❌ Missing | | none |
| Compliance: named officer | ✅ Built | | diwan/roles.py:55 |
| Compliance: retention period | ❌ Missing | Words in the UI only. | web/deal.html:652 |
| Compliance: who may delete | ❌ Missing | | none |
| Messaging: approved templates | 🔑 Needs connection | From AiSensy; pickers per use. | diwan/agents/reminders.py:13 |
| Messaging: opt-in record | ❌ Missing | | none |
| Messaging: stop words per language | 🟡 Partly | Hard-coded EN/AR regex. T: test_nudge:94. | diwan/agents/nudge.py:24 |
| Messaging: which messages need approval | 🟡 Partly | Per-agent autonomy, not per message. | diwan/app.py:588 |
| Marketing: permit required (default Yes) | ✅ Built | Default yes. | diwan/business.py:134 |
| Marketing: brand voice | ✅ Built | | diwan/brand.py |
| Marketing: posting hours | 🟡 Partly | Run hour only, in `rhythm`; no posting-hours setting found. | diwan/agents/rhythm.py:22 |
| Review: which items need Review and owner approval | 🟡 Partly | Autonomy levels, discount. | diwan/desk_rules.py:30 |
| Review: who may approve what amount | 🟡 Partly | One discount %. | diwan/desk_stages.py:98 |
| Limits: model spend | 🟡 Partly | Env vars only, not on a page. T: test_costs:38. | diwan/costs.py:56 |
| Limits: stuck thresholds per stage | 🟡 Partly | One number. | diwan/desk_rules.py:29 |
| Limits: escalation chain | ❌ Missing | | none |

### What each upload stores

There are two records: `docs.received` for client uploads and `document.filed` for the archive. Person-entered proofs reach only `document.filed`.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| One Document record | 🟡 Partly | Split in two, joined by nothing but `text` path. | diwan/documents.py:207, :238 |
| case_id | ✅ Built | Deal. | diwan/documents.py:207 |
| party_id | 🟡 Partly | Name string; no id. | diwan/documents.py:238 |
| role | ✅ Built | `party`. | diwan/documents.py:96 |
| kind: passport | ✅ Built | | diwan/documents.py:27 |
| kind: eid_front, eid_back | ✅ Built | | diwan/documents.py:27 |
| kind: title_deed | ✅ Built | | diwan/documents.py:28 |
| kind: trade_licence | ✅ Built | | diwan/documents.py:28 |
| kind: form_b, form_f | 🟡 Partly | Generated drafts, not uploads. | diwan/agency_forms.py |
| kind: cheque, pre_approval, liability_letter, poa | ❌ Missing | Not in KINDS. | diwan/documents.py:27 |
| file | ✅ Built | | diwan/documents.py:208 |
| pages | ❌ Missing | | diwan/documents.py:208 |
| hash | 🟡 Partly | sha256; compared only within one link, against other kinds. | diwan/documents.py:191 |
| uploaded_by | ✅ Built | `client:<party>`. | diwan/documents.py:207 |
| channel | ❌ Missing | Implicit. | diwan/documents.py:207 |
| at | ✅ Built | | diwan/documents.py:67 |
| extracted | 🟡 Partly, NEEDS-CONNECTION | Client types the details; a vision provider is not chosen. | diwan/documents.py:8 |
| check_result: passed | 🟡 Partly | Implicit in received. | diwan/documents.py:207 |
| check_result: failed + reasons | ✅ Built | `docs.rejected`. T: test_desk_rules. | diwan/documents.py:202 |
| check_result: overridden by whom and why | ❌ Missing | | diwan/documents.py:201 |
| expires_at | 🟡 Partly | In `fields.expiry`; no recurring warning. | diwan/documents.py:162 |
| satisfies_task | 🟡 Partly | Reverse link. | diwan/documents.py:210 |
| based_on_facts | 🟡 Partly | Drafts and slides; not on the Document. | diwan/graph.py:244 |
| status: current | 🟡 Partly | Implicit. | diwan/graph.py:333 |
| status: superseded | ❌ Missing | | diwan/documents.py:64 |
| status: voided with reason | ❌ Missing | | diwan/documents.py:70 |
| reviewed_by, at | 🟡 Partly | `docs.confirmed` by the compliance officer, not Review. | diwan/documents.py:236 |

### Case stages

Overall: **the code does not match the spec's list.** The code uses Title Case labels, editable per path by the owner, with `stage.changed` (a free label). The spec says "any other stage name in the code is a bug". None of the spec's stage or transition event names (`case.converted`, `compliance.cleared`, `deal.ready_for_transfer`, `transfer.booked`, `renewal.due`, `listing.live`) exist in `diwan/events.py`.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Only allowed list, fixed | ❌ Missing | Owner-editable. | diwan/desk_rules.py:163 |
| Other moves refused and logged | 🟡 Partly | Refused with an exception, not logged; any stage reachable (no adjacency). | diwan/desk_stages.py:61 |
| Moves only on named event | ❌ Missing | Free `stage.changed`. | diwan/desk_stages.py:74 |
| new | ✅ Built (as "New") | | diwan/desk_rules.py:86 |
| discovering | ❌ Missing | | diwan/desk_rules.py:86 |
| qualifying | ✅ Built (as "Qualifying") | Auto. | diwan/inbox.py:270 |
| qualified | ✅ Built (as "Qualified") | Auto. | diwan/inbox.py:272 |
| viewing | ✅ Built (as "Viewing booked", "Viewed") | Two stages. | diwan/inbox.py:274 |
| offer | ✅ Built (as "Offer") | | diwan/desk_rules.py:45 |
| Sale: documents | 🟡 Partly | No stage; "Offer accepted" then Form F. Docs requested at conversion. | diwan/desk_rules.py:45 |
| Sale: cleared | ❌ Missing | | diwan/desk_rules.py:45 |
| Sale: mou_signed | 🟡 Partly (as "Form F") | | diwan/desk_rules.py:45 |
| Sale: transfer_ready | ❌ Missing | | diwan/desk_rules.py:45 |
| Sale: transfer_booked | ❌ Missing | Step, not stage. | diwan/desk_rules.py:52 |
| Sale: transferred | 🟡 Partly (as "Transfer") | | diwan/desk_rules.py:45 |
| Off-plan: reserved | ✅ Built (as "Reservation") | | diwan/desk_rules.py:61 |
| Off-plan: spa_signed | ✅ Built (as "SPA") | | diwan/desk_rules.py:61 |
| Off-plan: registered | ✅ Built (as "Oqood") | | diwan/desk_rules.py:61 |
| Off-plan: handover_due | 🟡 Partly | "after" step. | diwan/desk_rules.py:65 |
| Rental: documents | ❌ Missing | | diwan/desk_rules.py:73 |
| Rental: contract_signed | ✅ Built (as "Contract") | | diwan/desk_rules.py:73 |
| Rental: moved_in | ✅ Built (as "Move-in") | "Ejari" extra stage. | diwan/desk_rules.py:73 |
| Rental: tenancy_active | ❌ Missing | | diwan/desk_rules.py:73 |
| Rental: renewal_due | 🟡 Partly | `renewal_notice_days` setting; no stage. | diwan/desk_rules.py:72 |
| Rental: move_out | ❌ Missing | | diwan/desk_rules.py:73 |
| Listing: listing_signed, live, under_offer, expiring | ❌ Missing | No seller-side path. | diwan/desk_rules.py:41 |
| Extra stage not in spec: "Offer accepted", "Closing" | 🟡 Partly | Spec would call these bugs. | diwan/desk_rules.py:45, :165 |
| Endings: closed_won | ✅ Built (as "Won") | Only via closing. | diwan/desk_stages.py:58 |
| Endings: closed_lost with reason | ✅ Built (as "Lost") | | diwan/desk_stages.py:69 |
| Side state: on_hold | ❌ Missing | No hold anywhere on the desk. | diwan/deal_desk.py |
| Side state: nurture | ✅ Built (as a deal prop) | T: test_nudge. | diwan/graph.py:454 |
| Closed never reopened | 🟡 Partly | Won is locked; Lost can move back. | diwan/desk_stages.py:56, :71 |
| New linked Case after close | ❌ Missing | | none |

### Five biggest structural gaps

1. **There is no event-driven spine.** Rooms call each other's code (`diwan/office.py:91-101`, `diwan/desk_stages.py:80`). There is no subscriber registry or consumers, so there is no Stuck board for orphaned Events and no overdue-Task sweep. The spec's event and stage names are also absent from `diwan/events.py`.
2. **Staff PAs do not exist.** Nova is one owner-only module, and a test locks that in (`diwan/access.py:53-63`, `tests/test_access.py:112`). There is no per-person identity, memory or brief access, no chat on every page, no WhatsApp inbound, and no escalation chain. No role PA from the "Each PA" table is built. Their pieces sit in screens instead.
3. **Front Desk modes and errands are absent.** There is no Arrival, Pocket or Do not disturb state, no mode chip, no email or travel provider, and self-reminders fail. The brief lacks Today, Pipeline and Money, payments due, and approve / send back buttons. Nothing emits `fact.recorded` from the owner.
4. **The Case is not a governed state machine.** There is no `owner_room`, no per-stage exit checklists, no Review gate on moves, no `on_hold`, and no listing/seller path. Stage labels are owner-editable and do not match the spec. Qualification answers are a separate overwritable quote store that bypasses the correction rule (`diwan/graph.py:413`), and Compliance is told first only for money facts (`diwan/agents/compliance.py:22`).
5. **Access is by department, and people and policy live in code.** A broker sees every lead and deal, and everyone on the deal team gets the same full view, including source-of-funds (`diwan/deal_desk.py:89`). That is a tipping-off exposure for brokers. "Status only" does not exist. People, rooms, display names and many policies are hard-coded or in env vars, with no single Settings page. Persons are name strings, not records, and Documents are split across two event types without the spec's fields. Notifications have no levels, repeats or staff quiet hours.


## Sales and listing upkeep


### Room 2: Channels in

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| WhatsApp | 🔑 Needs connection | Meta and AiSensy webhooks built; the sandbox goes through the same path | `diwan/app.py:1891,1910,1001`; `tests/test_burst.py` |
| Instagram comments | 🔑 Needs connection | Comment webhook and reply built; `media_id` is parsed then dropped, so a lead has no link to its post | `diwan/providers/instagram.py:154-168`; `diwan/app.py:539-541` |
| Instagram DM | ❌ Missing | Only the `comments` field is parsed; `_send` can only reply to a comment | `diwan/providers/instagram.py:161`; `diwan/agents/reception.py:538-544` |
| Facebook (Messenger, comments) | ❌ Missing | No route or provider; `graph.facebook.com` is used only for WhatsApp, IG and ads | `diwan/app.py` route list |
| TikTok | ❌ Missing | No inbound code; Studio only has it as a post format | `diwan/agents/studio.py:56` |
| Website form | ❌ Missing | No public lead route; the `PUBLIC_API` list has none | `diwan/access.py:45` |
| Property Finder / Bayut / Dubizzle leads | 🔑 Needs connection | Signed webhook built; refuses everything until `PORTAL_SECRET_*` is set. Field names are guessed until portal docs arrive | `diwan/app.py:1255`; `diwan/leads.py:399`; `diwan/providers/portals.py:9-11`; `tests/test_leads.py:176,195` |
| Phone call notes | 🟡 Partly | Card clear takes a note on an existing lead; a call cannot start a lead | `diwan/leads.py:150` |
| Walk-ins added by hand | 🟡 Partly | A lead can only be created by booking an appointment on the calendar; no walk-in source; no "add lead" action | `diwan/agents/reception.py:771-804` |
| Referrals | ❌ Missing | No source or referrer field; "referral" appears nowhere | grep over `diwan/` |

### Room 2: Discovery table

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Portal: intent from listing | ✅ Built | Buy or rent set from listing offering, marked with source | `diwan/leads.py:430-451` |
| Portal: fills known fields, never budget | ✅ Built | Area, type and beds filled; budget deliberately not | `diwan/leads.py:444`; `tests/test_leads.py:176` |
| Portal: Rania asks only what's missing | 🟡 Partly | Rania does not open; broker gets a call card and an optional template. She asks only after the client writes | `diwan/leads.py:400-402,454-469` |
| "Still available?" on a post: knows which listing | ❌ Missing | Post link dropped, as above | `diwan/app.py:541` |
| "Still available?": confirms | 🟡 Partly | Probe: lists several listings under "Here's what fits", no per-listing confirmation | `diwan/agents/reception.py:1028-1042` |
| "Still available?": asks live or invest | ❌ Missing | No purpose field on the form | `diwan/qualify.py:80-89` |
| "Still available?": intent from listing | ❌ Missing | Only portal leads use `from_listing`; probe: stays DISCOVERY | `diwan/leads.py:424` |
| "Sell my flat in JVC": intent Sell | ✅ Built | Sets `qtype=seller` | `diwan/qualify.py:114-119` |
| Sell: asks unit, size, price, deed holder, mortgage | 🟡 Partly | Only area, type, price, occupancy. Probe: rules reply also says "I'll send you the best options", wrong for a seller | `diwan/qualify.py:96-102`; `diwan/agents/reception.py:1026` |
| "Can you manage my apartment?": landlord / PM intent | 🟡 Partly | No rule for "manage" (a model could pick landlord); no PM intent exists. Probe: replies by listing properties for sale | `diwan/qualify.py:115` |
| Manage: asks unit, tenant, rent | 🟡 Partly | Only rent and occupancy, and only once type is landlord | `diwan/qualify.py:103-108` |
| "Hi": warm hello and one question | ✅ Built | Owner's greeting or default; asks buy/rent/sell. "Just looking" option absent from wording, though it nurtures if said | `diwan/agents/reception.py:1048-1051,1208`; `tests/test_sales_journey.py:124` |
| "price?" with no context | 🟡 Partly | Probe: dumps listings instead of a hello, ignoring the "not before qualified" setting | `diwan/agents/reception.py:1005-1010` |
| Company question: answers from knowledge | 🟡 Partly | Works via `customer_knowledge`, but probe "What are your office hours?" tries to book an office meeting (regex matches "your office") | `diwan/agents/reception.py:688,1045-1047,1199` |
| Company question: then asks about a property | ✅ Built | Rules append the discovery question | `diwan/agents/reception.py:1420` |
| Company question: intent Marketing / nurture | ❌ Missing | Stays unknown | `diwan/agents/reception.py:1112` |
| Spam / job seekers / suppliers: routed, Not a lead | ❌ Missing | No classifier, stage or routing. Probe: supplier gets the sales greeting; job seeker gets a broker card only because the text said "agent" | `diwan/agents/reception.py:27` |

### Room 2: Qualifying fields (default form; the owner can add any field)

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| One question at a time | ✅ Built | The verdict gives one `next` | `diwan/qualify.py:221-260`; `tests/test_qualify.py:84` |
| Each answer kept with client's words | ✅ Built | Quote not in their messages is dropped | `diwan/qualify.py:342` |
| Each answer stored as a Fact | 🟡 Partly | Stored as `deal.props.answers`, not Fact nodes; no `superseded_by`. Probe: 7 answers gave 1 Fact | `diwan/graph.py:413-417` |
| Buyer: purpose (live / invest) | ❌ Missing | Not on form | `diwan/qualify.py:80-89` |
| Buyer: area, type, beds, budget | ✅ Built | Required | `diwan/qualify.py:81-82` |
| Buyer: cash or mortgage | ✅ Built | Required | `diwan/qualify.py:83` |
| Buyer: mortgage pre-approval | 🟡 Partly | Optional, so never asked (only required fields are asked) | `diwan/qualify.py:84,237` |
| Buyer: timeline | ✅ Built | Required | `diwan/qualify.py:88` |
| Buyer: residency | ❌ Missing | Not on form | `diwan/qualify.py:80-89` |
| Buyer: nationality only if Compliance needs it | 🟡 Partly | Optional common field; no Compliance trigger | `diwan/qualify.py:75` |
| Seller: unit | ❌ Missing | Area and type only | `diwan/qualify.py:96-102` |
| Seller: title deed | ❌ Missing | Not on form | same |
| Seller: mortgage outstanding | ❌ Missing | Not on form | same |
| Seller: expected price | ✅ Built | `asking_price` | `diwan/qualify.py:98` |
| Seller: vacant or tenanted | ✅ Built | `occupancy_status` | `diwan/qualify.py:99` |
| Seller: timeline | ❌ Missing | Not on form | same |
| Tenant: move-in date | ✅ Built | Required | `diwan/qualify.py:93` |
| Tenant / landlord: cheques | ❌ Missing | Not on either form | `diwan/qualify.py:90-108` |
| Tenant / landlord: Ejari | ❌ Missing | Not on either form | same |
| Tenant / landlord: pets | ❌ Missing | Not on either form | same |
| Tenant / landlord: company or personal | ❌ Missing | Not on either form | same |
| Landlord: move-in date | ❌ Missing | Not on form | `diwan/qualify.py:103-108` |

### Room 2: Heat score

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Heat score exists | 🟡 Partly | A yes/no `hot` flag, not a score. "heat" appears nowhere | `diwan/graph.py:460` |
| Owner's rules for hot | 🟡 Partly | Owner picks triggers (pick, viewing, qualified, call) | `diwan/agents/reception.py:175-180,191-209` |
| Budget fits + timeline under 60 days + finance ready | ❌ Missing | Triggers are events, not answer conditions | `diwan/agents/reception.py:179` |
| One setting used by Rania | ✅ Built | `rania.recommend.hot_on` | `diwan/agents/reception.py:187` |
| Same setting used by the brief and Records | ❌ Missing | No `hot` in nova, records or KPIs | `diwan/agents/nova.py:451-481` |
| Broker can mark hot / not hot | ✅ Built | Extra to spec | `diwan/leads.py:281`; `web/inbox.html:602` |

### Room 2: PA behaviour 1-5

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1. Detect "call me" / "can someone call" | ✅ Built | Regex, English and Arabic | `diwan/agents/reception.py:221`; `tests/test_leads.py:60` |
| 1. Reply "will call you in the next 10 minutes" | 🟡 Partly | Says "shortly" | `diwan/agents/reception.py:270` |
| 1. Broker alert on screen | ✅ Built | Immediate, card plus notice | `diwan/leads.py:146` |
| 1. Broker WhatsApp alert | 🔑 Needs connection | Needs `NOTIFY_TEMPLATE`, AiSensy, a broker number | `diwan/leads.py:481`; `tests/test_leads.py:128` |
| 1. Browser or phone push | ❌ Missing | No push service | `diwan/leads.py:474` |
| 1. Card shows name and what they want | ✅ Built | Quote plus answers summary | `diwan/agents/reception.py:1108-1109` |
| 1. Last 3 messages | ❌ Missing | Only the current message | same |
| 1. One-tap call | ❌ Missing | No `tel:` link anywhere in `web/` | grep |
| 1. 10-minute timer | 🟡 Partly | 15 minutes, read from env, not Settings | `diwan/leads.py:31-32` |
| 1. Escalates to next free broker | 🟡 Partly | At 60 minutes goes to the Pool for any broker to claim; no auto-reassign | `diwan/leads.py:179-186`; `tests/test_leads.py:101` |
| 1. Tells owner in the brief | 🟡 Partly | Instant notice to Layla, not in the brief | `diwan/leads.py:191` |
| 2. Stated time becomes a Task due then | ✅ Built | Calendar phone call plus card due then, under another name. Exact times only. Probe: "tomorrow at 5pm" works; "tomorrow after 4" falls to the 15-minute card, time lost | `diwan/agents/reception.py:1062-1083,1095-1097`; `e2e/call_flow.py:48` |
| 2. Client's time zone | ❌ Missing | Always Dubai | `diwan/slots.py` DUBAI |
| 2. Reminder 15 minutes before | ❌ Missing | Calls are skipped by reminders; the broker only hears when overdue | `diwan/agents/reminders.py:80` |
| 2. Rania confirms the time | ✅ Built | Plus free-time check | `diwan/agents/reception.py:268`; `e2e/call_flow.py:67` |
| 3. Hot lead reaches the broker | ✅ Built | Hot card with summary; deck built | `diwan/agents/reception.py:1471-1481` |
| 3. "Book a viewing?" buttons | ❌ Missing | Card has no booking button | `diwan/agents/reception.py:1478`; `web/inbox.html:601-633` |
| 4. Morning list each broker | 🟡 Partly | Today's appointments only, and nothing if there are none | `diwan/agents/reminders.py:109-126`; `tests/test_calendar.py:133` |
| 4. Who to call | ❌ Missing | Not in the list | same |
| 4. Who's gone quiet | ❌ Missing | Not in the list | same |
| 4. Who's waiting on options | ❌ Missing | Not in the list | same |
| 5. Owner's schedule | ✅ Built | Per office and per lead | `diwan/agents/nudge.py:19,114`; `tests/test_nudge.py:40,179` |
| 5. Never at night or Friday prayer | 🟡 Partly | Follow-ups and reminders obey; document reminders use a fixed 9-20 window with no prayer check. Prayer times are a constant | `diwan/agents/nudge.py:22,72`; `diwan/documents.py:256`; `tests/test_nudge.py:82` |
| 5. Never the same message twice | ✅ Built | Skips with reason | `diwan/agents/nudge.py:294`; `tests/test_nudge.py:63` |
| 5. "Stop" means stop everywhere | 🟡 Partly | See "When things go wrong" below | `diwan/agents/nudge.py:24`; `tests/test_nudge.py:94` |

### Room 2: Exit outcomes and gaps

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Outcome: converted | ✅ Built | Convert with agreed price | `diwan/desk_stages.py:105`; `tests/test_desk_rules.py:524`; `e2e/deal_flow.py:725-763` |
| Outcome: follow up on [date] | ✅ Built | Refused while a card is open; nothing goes to the client | `diwan/leads.py:296`; `tests/test_front_door.py:191` |
| Outcome: not interested + reason | 🟡 Partly | Lost with free text; no dropdown of the spec's reasons | `web/inbox.html:595-596` |
| Outcome: no response | 🟡 Partly | Only free-text Lost, or a card marked `no_answer` | `diwan/leads.py:27` |
| `case.converted` emitted | 🟡 Partly | Event does not exist; job done by `stage.changed` plus `on_convert` | `diwan/desk_stages.py:74,80` |
| Every Fact carried, nothing retyped | ✅ Built | Same deal record, nothing copied | `diwan/desk_stages.py:162-175` |
| Gap: outcomes | 🟡 Partly | As above; no outcome forced after a call | `diwan/leads.py:27` |
| Gap: escalation timer | 🟡 Partly | Pool, not reassign | `diwan/leads.py:172` |
| Gap: IG / FB DM | ❌ Missing | Comments only | see Channels |
| Gap: portal webhooks | 🔑 Needs connection | Built | see Channels |
| Gap: one heat setting | 🟡 Partly | See Heat score | see above |

### Part 2: Sales fix-firsts and build items

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Sales lead as brokers' PA | 🟡 Partly | Charter is "Owns what comes out of meetings"; no chasing logic of its own; `leads.sweep` does the job under Rania | `diwan/agents/charters.py:45` |
| Fix: one display name (Hamza vs Omar) | 🟡 Partly | `name()` is single-source, and Rania's fixed replies use the deal's broker, but no check on names in model text; a site visit goes to the listing's agent while the label stays the deal's broker; a person's reply has no signature; a transfer or `_route` leaves earlier promises standing | `diwan/people.py:44`; `diwan/agents/reception.py:743,1392`; `diwan/agents/followup.py:72` |
| Fix: "Qualified" only when the form is complete | 🟡 Partly | Auto stage is correct, but probe: a broker moved a brand-new lead to Qualified with no answers, then to Viewed | `diwan/inbox.py:272`; `diwan/desk_stages.py:47-74` |
| Fix: "Qualifying 3/8" instead of "step 3 of 8" | ❌ Missing | Hard-coded: `step ${idx+1} of 8` is the stage position, so the original bug is still on screen; no answered/required count | `web/inbox.html:657-658` |
| Fix: exact quote stored with number | ✅ Built | On the answer and on the Fact; the chip itself has no quote | `diwan/qualify.py:355`; `diwan/inbox.py:74-76` |
| Fix: confirm out-of-range budget | ❌ Missing | Probe: "budget 20k" on off-plan qualified, and Rania promised options "around AED 20,000". An owner condition can only reject or hold | `diwan/qualify.py:298-301`; `diwan/agents/reception.py:400` |
| Fix: one suggestion per incoming message | 🟡 Partly | One per message, but each message adds a bubble. Probe: 2 messages gave 2 suggestions; old ones stay. A burst waits in the live path only | `diwan/agents/reception.py:1438`; `web/inbox.html:346` |
| Regenerate suggestion on request | ❌ Missing | Only "Use this reply" | `web/inbox.html:346` |
| Build 1: Now Task with last 3 messages and call button | 🟡 Partly | Card yes; last 3 and button no | see PA item 1 |
| Build 1: alerts | 🔑 Needs connection | WhatsApp only; push absent | `diwan/leads.py:481` |
| Build 1: reassign at 10 minutes, tell owner | 🟡 Partly | Owner told when due; pool at 60 | `diwan/leads.py:179-191` |
| Build 2: Call later | 🟡 Partly | No time zone, no 15-minute reminder | see PA item 2 |
| Build 3: sweep per broker at 08:30 | 🟡 Partly | Fires an hour before shift, not a set 08:30; content is appointments only | `diwan/agents/reminders.py:113` |
| Build 4: outcomes after every call | 🟡 Partly | Action required (called, messaged, no answer, not needed); not the 4 outcomes | `diwan/leads.py:27,150` |
| Build 5: Convert carries Facts | ✅ Built | Same deal | `diwan/desk_stages.py:162` |
| Build 5: lands in Deal, Inbox link | ✅ Built | "Open the deal →" | `web/inbox.html:569-579`; `e2e/deal_flow.py:763` |
| Convert button clear | ✅ Built | Explains and shows card; needs agreed price | `web/inbox.html:608-616` |
| Test: call-now escalation (Playwright) | ❌ Missing | Pytest only | `tests/test_leads.py:101` |
| Test: outcome required (Playwright) | ❌ Missing | Only "card needs an action", pytest | `tests/test_leads.py:71` |
| Test: convert lands in Deal (Playwright) | ✅ Built | Script exists | `e2e/deal_flow.py:725-763` |

### Part 4: Cases still missing (16 rows)

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1. Match on phone, email, name + listing | ❌ Missing | No matching; IG chats have only a username | `diwan/agents/reception.py:505` |
| 1. Propose merge to broker | ❌ Missing | Manual picker only | `web/inbox.html:626-632` |
| 1. Merge by a person | ✅ Built | Histories and answers join; other lead closes | `diwan/leads.py:244`; `tests/test_front_door.py:257`; `e2e/profile_flow.py:178` |
| 1. Never automatic across two brokers | 🟡 Partly | No auto-merge, but a new chat with the same customer name as one open non-`lead-` deal attaches to it silently | `diwan/agents/reception.py:499-502` |
| 2. First owner keeps it | 🟡 Partly | Claims work only from the Pool; no claim on an owned lead | `diwan/leads.py:196-200` |
| 2. Sales lead reassigns | 🟡 Partly | Any caller can reassign; no role check. `rashid` (Sales manager) has no special path | `diwan/leads.py:209`; `diwan/app.py:1191` |
| 2. Claim and decision logged | ✅ Built | `lead.claimed`, `lead.assigned` | `diwan/leads.py:203` |
| 3. On `listing.live` match qualified buyers | ❌ Missing | No trigger; only a quiet lead's follow-up may mention a new match | `diwan/agents/nudge.py:229-235` |
| 3. Brokers get a list | ❌ Missing | None | none |
| 3. Rania sends only with broker's yes | ❌ Missing | That nudge sends with no yes, the opposite | `diwan/agents/nudge.py:299` |
| 4. Key / access with seller or tenant | ❌ Missing | None; tenant notice none | `diwan/agents/reception.py:733-768` |
| 4. Client confirmation 24h and 2h | ✅ Built | Owner-set | `diwan/agents/reminders.py:13`; `tests/test_calendar.py:116` |
| 4. Broker travel time | ❌ Missing | No gap between appointments | grep travel/buffer |
| 5. Broker marks no-show | ✅ Built | Calendar button | `diwan/app.py:1690`; `web/calendar.html:577`; `tests/test_calendar.py:154` |
| 5. One reschedule message | ❌ Missing | Logged only; `app.py:1704` does nothing else | `diwan/app.py:1704` |
| 5. Second no-show lowers heat | ❌ Missing | No score, no count | none |
| 6. Broker notes / recording | 🟡 Partly | Typed notes and recorded meetings; no voice-note upload | `diwan/app.py:1705`; `diwan/agents/visit.py:59,95`; `tests/test_calendar.py:168` |
| 6. Rania asks client next day | ✅ Built | Day 1 "What did you think?" | `diwan/agents/nudge.py:19,207`; `tests/test_sales_journey.py:170,199` |
| 6. Feedback is a Fact | 🟡 Partly | Kept as `deal.visit` with quotes, not a Fact | `diwan/graph.py:423` |
| 6. Seller report includes it | ❌ Missing | No seller report | none |
| 7. Offers side by side, seller's choice, others told | ❌ Missing | No offer object; one agreed price per deal | `diwan/desk_stages.py:121` |
| 8. Tenant notice, inspection vs move-in, deductions, approval | ❌ Missing | Single task | `diwan/agents/operations.py:280` |
| 8. Deposit return and Ejari cancellation | 🟡 Partly | Named in one task, closed with a note | `diwan/agents/operations.py:280,290` |
| 9. Rent increase vs rent index, sent to landlord | ❌ Missing | None | none |
| 10. Returns: no advice, broker Task | ✅ Built | Fixed reply plus task | `diwan/agents/reception.py:997-999,576` |
| 10. Visas: no advice, specialist | ❌ Missing | Probe: treated as buyer; no notice or task. Only the prompt says handover if sources don't cover | `diwan/agents/reception.py:28-30` |
| 10. Legal: no advice, specialist | ❌ Missing | Probe: greeted, no task | same |
| 10. Tax: no advice, specialist | 🟡 Partly | Probe: handled only because "rental income" hits the returns rule | `diwan/agents/reception.py:30` |
| 11. Payments from developer documents | 🟡 Partly | Escrow payee in Finance; no link to a developer document | `diwan/agents/finance.py:239-240` |
| 11. Rania never sends bank details | 🟡 Partly | Prompt only; amount guard, no account-number guard | `diwan/agents/reception.py:107,1344` |
| 11. Account change is a Compliance flag | ❌ Missing | None | see Fraud guard |
| 12. Licence number in People settings | 🟡 Partly | BRN in desk rules; no expiry | `diwan/desk_rules.py:40` |
| 12. Warn 30 days before | ❌ Missing | None | none |
| 12. Expired broker can't be assigned | ❌ Missing | `pick` has no licence check | `diwan/leads.py:96` |
| 13. Mortgage referral, consent, Finance line | ❌ Missing | None | grep referral |
| 14. Snagging (Phase 2) | ❌ Missing | Only step text | `diwan/desk_rules.py:65` |
| 15. Property management (Phase 2) | ❌ Missing | No room | none |
| 16. Commercial / holiday homes (Phase 2) | ❌ Missing | "Office" and "Plot" are type options only | `diwan/qualify.py:67` |

### Fraud guard

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Detect change of bank details, other account, urgent money | ❌ Missing | No pattern. Probe: both phrases got the sales greeting with no card, task or Fact | `diwan/agents/reception.py:28-29` |
| Agent never acts | 🟡 Partly | Agents cannot pay; but Rania replies normally | `diwan/agents/charters.py` |
| Now flag to Finance and Compliance | ❌ Missing | No Now level; nothing routes | none |
| Confirm by phone on a known number | ❌ Missing | None | none |
| Inbound from staff or other parties | ❌ Missing | Not covered | none |

### Listing upkeep

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Permit number required to advertise | ✅ Built | Foundation only | `diwan/agents/reception.py:487`; `diwan/knowledge.py:88` |
| Permit expiry date stored | ❌ Missing | Permit is a bare string | `diwan/leads.py:328` |
| Warn at 14 and 3 days | ❌ Missing | None | none |
| Renewal prepared up to Submit | ❌ Missing | None | none |
| Auto-pause ads and Studio posts on expiry | ❌ Missing | None | none |
| Form A expiry 14 days, seller asked | ❌ Missing | Form A is only a generated form; only link expiry exists | `diwan/agency_forms.py:21`; `diwan/documents.py:98` |
| `listing_expiring` stage | ❌ Missing | None | `diwan/desk_rules.py:86` |
| Check every 7 / 3 days | ❌ Missing | None | none |
| Check before any viewing is booked | ❌ Missing | `book()` checks only broker's time, and a hot listing is not rechecked | `diwan/agents/reception.py:733,1302` |
| Message to seller or landlord | ❌ Missing | None | none |
| Yes: refreshed with date | ❌ Missing | None | none |
| Changed: supersedes old price, ads updated | 🟡 Partly | Feed sync flags portal mismatches with a task; no Fact, no owner reply | `diwan/leads.py:332-396`; `tests/test_leads.py:232,246` |
| Sold elsewhere: withdrawn, buyers told, Case lost | 🟡 Partly | Leaving the feed sets off-market, so Rania stops offering it; buyers not told, Case not closed | `diwan/leads.py:390-392`; `tests/test_leads.py:150,263` |
| No answer at 48h: broker Task | ❌ Missing | None | none |
| Unconfirmed: no viewings, ads paused | ❌ Missing | None | none |
| Portal refresh rule | 🟡 Partly | A feed listing untouched 7 days is flagged; it still shows to Rania; constant, no draft | `diwan/knowledge.py:34,76-80,94` |
| Off-plan price list stale after 14 days | 🟡 Partly | A knowledge item past `valid_until` is hidden; no 14-day rule, no "to be confirmed", and listing prices aren't covered | `diwan/knowledge.py:92-98` |
| Re-list 60 days before tenant leaves | ❌ Missing | None | none |
| Events `permit.*`, `listing.*` (6) | ❌ Missing | None in the catalog | `diwan/events.py` |

### Case stages: Shared start

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| new | ✅ Built | "New" default; enters on first message, portal, hand add | `diwan/desk_rules.py:86`; `diwan/inbox.py:98` |
| discovering | ❌ Missing | Not a stage; only verdict DISCOVERY on screen, and new goes straight to Qualifying | `diwan/inbox.py:270` |
| `case.intent_set` | 🟡 Partly | `qualify.type` does the job | `diwan/qualify.py:336` |
| not_a_lead exit | ❌ Missing | Not-a-fit closes as Lost, a different thing | `diwan/inbox.py:264` |
| qualifying | ✅ Built | Auto on type | `diwan/inbox.py:270` |
| qualified | 🟡 Partly | Auto correct; manual bypass (probe) | `diwan/inbox.py:272` |
| valuation exit (seller) | ❌ Missing | None | none |
| viewing | ✅ Built | "Viewing booked", auto; calls excluded | `diwan/inbox.py:274`; `tests/test_inbox.py:40` |
| offer | 🟡 Partly | "Offer" stage on ready and rent paths only, manual; off-plan has none; no `offer.made` | `diwan/desk_rules.py:45,61,73` |
| Leaves on acceptance quoted | 🟡 Partly | Needs a price, not a quote | `diwan/desk_stages.py:105` |
| Extra stage "Viewed" | 🟡 Partly | Not in spec's list, though useful | `diwan/desk_rules.py:86` |
| Disallowed move refused and logged | 🟡 Partly | Unknown names refused, not logged; stages can be skipped forward (probe) | `diwan/desk_stages.py:61-68` |
| Side state nurture | ✅ Built | `lead.nurture`, reopens | `diwan/agents/reception.py:1112,1179-1186`; `tests/test_front_door.py` |
| Side state on_hold | ❌ Missing | No such state; qualify `hold` is unrelated | `diwan/qualify.py:252` |

### Rental and listing steps belonging to Sales

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Viewing (`viewing.done`) | ✅ Built | As `appointment.done`; moves to Viewed, drafts follow-up | `diwan/app.py:1704-1708` |
| Form B before first viewing | ❌ Missing | Generated at convert, no gate on `book()` | `diwan/agents/reception.py:733`; `diwan/agency_forms.py:21` |
| Offer as a Fact (price, terms, quote) | ❌ Missing | No capture before convert | `diwan/desk_stages.py:162` |
| Rental offer: rent, cheques, move-in | ❌ Missing | Amount only | same |
| Seller or landlord acceptance quoted | ❌ Missing | Not asked | same |
| Client hears "An offer came in" / "accepted" | ❌ Missing | No message sent | same |
| Counter offers as Facts | ❌ Missing | None | none |
| Offer received on a listing joins sale | 🟡 Partly | Stage exists, no link to seller | `diwan/deal_property.py:192` |
| Valuation with comparables, `valuation.sent` | ❌ Missing | None | grep comparable |
| Weekly seller report | ❌ Missing | None | grep seller report |
| Renewal task 90 days before | 🟡 Partly | Dated broker task at close; no `renewal.due`; no sweep acts on the date; the case does not reopen in Sales | `diwan/agents/operations.py:275-279` |
| Renewal message to client | ❌ Missing | Broker writes it | same |

### When things go wrong (Sales rows)

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Buyer quiet after offer: detected | 🟡 Partly | Generic ladder at any stage; no offer logic | `diwan/agents/nudge.py:150-174` |
| Broker call Task | 🟡 Partly | Only if owner picks "broker"; default is Nurture | `diwan/agents/nudge.py:19,314`; `tests/test_nudge.py:117` |
| Then owner brief | ❌ Missing | None | none |
| Seller kept informed | ❌ Missing | None | none |
| Lost "no response" | 🟡 Partly | Free text | `web/inbox.html:595` |
| Lost reasons dropdown | ❌ Missing | Free text; Records cannot count | same |
| Complaint: words detected | ❌ Missing | Probe: "complaint... unhappy... lawyer" got the sales greeting | `diwan/agents/reception.py:27-29` |
| Complaint record, owner told, acknowledgement only | ❌ Missing | None | none |
| Stop: English whole-message | ✅ Built | "STOP", "Please stop messaging me" | `diwan/agents/nudge.py:24`; `tests/test_nudge.py:94` |
| Stop: any wording, any language | 🟡 Partly | English and basic Arabic only, whole message. Probe missed "please stop sending me messages", "no more messages please", "arrêtez" | `diwan/agents/nudge.py:24-26` |
| Stop while Rania is on review | 🟡 Partly | Bug, probe: at `review_key`, "STOP" is not recorded, because the function returns first | `diwan/agents/reception.py:1442-1449,1469` |
| Stop: follow-ups, reminders, nurture | ✅ Built | Guarded | `diwan/agents/nudge.py:155`; `diwan/agents/reminders.py:87`; `diwan/agents/reception.py:313` |
| Stop: all automated messages | 🟡 Partly | `_send` has no guard: document reminders and calendar moves still go | `diwan/documents.py:284`; `diwan/agents/reception.py:941-971` |
| Brokers may reply if client writes | ✅ Built | Blocked until then | `diwan/agents/reception.py:610`; `tests/test_sales_journey.py:53,62` |
| Delete data: detected and logged | ❌ Missing | Probe: sales greeting. "remove me" counts only as stop | `diwan/agents/nudge.py:24` |
| Delete, keep what law requires, tell client | ❌ Missing | Log is append-only; no erasure path | `diwan/events.py` |

### End-to-end step 1 and seed scenarios

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Sara asks "is the 2-bed in Marina still available?" | 🟡 Partly | Probe: right listing shown, not stated as available | `diwan/agents/reception.py:1041` |
| Rania qualifies her | 🟡 Partly | Probe: stays DISCOVERY; asks nothing after the listing line, because a "?" in the reply suppresses it | `diwan/agents/reception.py:1420` |
| "Call me": broker alert within 1 minute | ✅ Built | On screen at once; WhatsApp needs connection | `diwan/leads.py:146` |
| Playwright covers this exact path | 🟡 Partly | Pieces in `office_flow` and `front_door_flow`, not as one | `e2e/office_flow.py:39`; `e2e/front_door_flow.py:119` |
| WhatsApp + Instagram same phone: detected | ❌ Missing | IG has no phone; no detection. Probe: same name gave 2 separate leads, nothing flagged | `diwan/agents/reception.py:503` |
| Same: merge by a person | ✅ Built | Test exists; the seed scenario itself isn't scripted | `tests/test_front_door.py:257` |
| "Send the deposit to this new account": Now flag | ❌ Missing | Probe: greeting, no flag | see Fraud guard |
| Same: no agent action | 🟡 Partly | Nothing done, but also nobody told | same |

### 5 biggest gaps

1. **Fraud, complaints and data deletion have no code.** All three got the ordinary sales greeting in probes, with no card, task or flag. These are the highest-risk messages Rania can receive.
2. **Offers do not exist in Sales.** There is no offer as a Fact, counter-offer, quoted acceptance, side-by-side comparison or seller messaging. Convert is just a typed price, and `case.converted` does not exist. Valuation, seller report and the Lost reasons dropdown are also missing, so the seller side has no Sales flow.
3. **Listing upkeep is nearly all absent.** There is no permit expiry, still-available check, Form A expiry, unconfirmed state or new-listing match to waiting buyers. Only the feed sync helps, so expired or sold units can stay advertised unless the feed drops them.
4. **The broker PA is thin.** There is no heat score, no 10-minute auto-reassign (Pool at 60 minutes instead), no last 3 messages, no one-tap call, no 15-minute call reminder, and the morning list is appointments only. The no-show follow-up is missing, and the Sales lead has no behaviour of its own.
5. **Qualifying is incomplete, and two visible bugs remain.**
 - Default forms lack purpose, residency, seller deed/mortgage/unit/timeline, and tenant cheques/Ejari/pets/company.
 - Answers are not Facts.
 - "step 3 of 8" is still hard-coded at `web/inbox.html:658`.
 - AED 20K passes unchallenged, and spam or job seekers are unrouted.
 - "Stop" is lost when Rania is on review (`diwan/agents/reception.py:1442-1449`) and misses common wording.
 - Only WhatsApp, IG comments and portals exist as channels; DM, Facebook, TikTok, website form and referrals are absent.


## Deal, Operations, Finance, Compliance, Review


### Cross-cutting

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Part 4 catalog events in code | ❌ Missing | Grep of diwan, web, tests and e2e finds zero of the Part 4 catalog events checked (`compliance.*`, `deal.ready_for_transfer`, `review.requested`, `payment.marked_received`, `doc.*`, `form.*`, `transfer.*`, and others) | diwan/events.py:11-42 |
| Rooms react to events | ❌ Missing | Rooms call each other's functions directly | diwan/office.py:9, 91-94 |
| Allowed stage list | ❌ Missing | Stages are owner-editable strings; `documents`, `cleared`, `mou_signed` and the rest don't exist | diwan/desk_rules.py:45, 61, 73 |
| Side states on_hold, nurture on a Case | ❌ Missing | No on_hold anywhere; nurture exists only as a lead flag | diwan/agents/nudge.py:309 |

### Room 3 Deal: checklist by deal type

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Template picked from Facts | 🟡 Partly | Path comes from the sales desk or the broker, not Facts | diwan/desk_rules.py:107-118 |
| Secondary cash and mortgage as separate templates | ❌ Missing | One `ready` path; mortgage steps removed by hand with "Not needed" | diwan/desk_rules.py:47-54; diwan/agents/operations.py:123 |
| Cash: Form A, B, I by side | ✅ Built | Picked from `sides`. T: TDR seller-side test | diwan/agency_forms.py:45-52 |
| Cash: Form F | ✅ Built | Plan and PDF from Facts; online signing | diwan/agents/operations.py:37-50; diwan/signing.py:24-26 |
| Cash: IDs and passports, buyer and seller | 🟡 Partly | Link for each of our sides only; compliance officer checks | diwan/documents.py:44-52 |
| Cash: title deed | 🟡 Partly | Uploaded, typed number only | diwan/desk_rules.py:32 |
| Cash: developer NOC, DLD appointment | 🟡 Partly | Hand-ticked steps, no document | diwan/desk_rules.py:50, 52 |
| Mortgage: pre-approval | ❌ Missing | Only a free-text proof line "mortgage pre-approval or proof of funds" | diwan/agents/compliance.py:149-151 |
| Mortgage: valuation, final offer | 🟡 Partly | One tick line | diwan/desk_rules.py:48 |
| Mortgage: manager's cheques | 🟡 Partly | One tick line | diwan/desk_rules.py:51 |
| Mortgage: seller liability letter | 🟡 Partly | One tick line | diwan/desk_rules.py:49 |
| Off-plan: reservation form | 🟡 Partly | Tick line | diwan/desk_rules.py:62 |
| Off-plan: booking payment | 🟡 Partly | Only if a payment-promise fact exists | diwan/agents/finance.py:16-36 |
| Off-plan: SPA | 🟡 Partly | Tick line; reference typed with the plan | diwan/desk_rules.py:63; diwan/agents/finance.py:282 |
| Off-plan: Oqood | 🟡 Partly | Tick line | diwan/desk_rules.py:64 |
| Off-plan: payment plan schedule | ✅ Built | Entered by a person, must add up. T: TDR spa_payment_plan | diwan/agents/finance.py:265-307 |
| Rental: tenancy contract | 🟡 Partly | Tick line; not generated | diwan/desk_rules.py:75 |
| Rental: Ejari | 🟡 Partly | Tick line | diwan/desk_rules.py:78 |
| Rental: cheques | 🟡 Partly | Dated expectations; no cheque image | diwan/agents/finance.py:249-262 |
| Rental: security deposit | ✅ Built | Percent of rent, furnished variant | diwan/agents/operations.py:149-155 |
| Rental: IDs | 🟡 Partly | Tenant only | diwan/documents.py:47-48 |
| Rental: title deed copy, landlord POA | ❌ Missing | Landlord never asked for anything | diwan/documents.py:47-48 |
| Listing checklist | ❌ Missing | No listing path; only ready, offplan, rent | diwan/desk_rules.py:41-85 |
| Each line is a Task | 🟡 Partly | Steps created only after Form F is submitted or paperwork is started, not at conversion | diwan/agents/operations.py:102, 148 |
| Owner room on each line | 🟡 Partly | Only `waiting_on` plus the transactions officer | diwan/agents/operations.py:105-109 |
| Due date on each line | ❌ Missing | Only rental after-close tasks have dates | diwan/agents/operations.py:108 |
| Facts it depends on | ❌ Missing | `add_steps` sets no `rests_on`, so a correction can't touch steps | diwan/agents/operations.py:108 |
| Owner edits templates | 🟡 Partly | Editable on the Deal page, not Settings; no cash/mortgage or party templates. T: TDR new_step | web/deal.html:259-267, 301 |

### Room 3 Deal: client form portal

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1. WhatsApp sends private link | 🟡 Partly | No first send; broker copies links; Rania sends the first reminder after 2 days | diwan/documents.py:85-100, 284; web/deal.html:836 |
| 1. Message lists the items | 🟡 Partly | Reminder only | diwan/documents.py:278 |
| 1. Link for a signature | ❌ Missing | Broker shares it personally; never sent | diwan/signing.py:2-3; web/deal.html:886 |
| 2. Private expiring link | ✅ Built | Token, `sign_link_days`. T: TDR replaced_or_expired | diwan/documents.py:95-98; diwan/signing.py:91 |
| 2. One portal for docs and signing | 🟡 Partly | Two separate pages, two links | web/docs.html; web/sign.html |
| 2. Mobile page | ✅ Built | 640px column. T: E2E 17b | web/docs.html:12 |
| 2. Only missing items | 🟡 Partly | Lists all items with status | web/docs.html:46-51 |
| 2. Pre-filled from Facts | 🟡 Partly | Form rows are; docs page fields are blank and the client types | diwan/signing.py:117; web/docs.html:49 |
| 3. Signature drawn on screen | ❌ Missing | No canvas; file input only | web/sign.html:56 |
| 3. Signature photo upload | ✅ Built | T: E2E 17c | diwan/signing.py:123-147 |
| 4. Checked on arrival, re-upload with reason | 🟡 Partly | Format, photo quality and typed fields only. T: TDR bad_upload, E2E 18b | diwan/documents.py:183-203 |
| 5. WhatsApp receipt after submit | ❌ Missing | Page text only | web/docs.html:44; diwan/documents.py:207-211 |
| 5. Task closes | 🟡 Partly | Upload opens a compliance task; `docs_requested` has no task | diwan/documents.py:209 |
| 5. Document stored on Case | 🟡 Partly | Only after a person confirms. T: TDR confirms_into_file | diwan/documents.py:238 |
| 5. `doc.received` emitted | 🟡 Partly | Named `docs.received`, no consumer of the catalog name | diwan/documents.py:207 |
| 6. Nudge at 24h | 🟡 Partly | Every 2 days, 3 times, a setting. T: TDR rania_reminds | diwan/desk_rules.py:34 |
| 6. Broker call Task at 48h | 🟡 Partly | After the 3 reminders, about day 8 | diwan/documents.py:272-275 |
| 6. Owner brief at 72h | ❌ Missing | The owner sees only tasks she owns | diwan/agents/nova.py:524-527 |
| 6. Ladder covers unsigned forms | ❌ Missing | Documents only | diwan/documents.py:262-263 |
| 6. Quiet hours as Sales | 🟡 Partly | Hard-coded 9-20, ignores owner's quiet hours | diwan/documents.py:256 vs diwan/agents/nudge.py:73 |
| 6. Friday prayer | ❌ Missing | Not applied | diwan/documents.py:256 |

### Room 3 Deal: upload checks

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Signature: ink on light, not blank | ❌ Missing | Only type, readable, min 120x40; a blank white image passes | diwan/signing.py:128-137 |
| Signature: no face, no text, no typed name | ❌ Missing | A selfie passes | diwan/signing.py:123-147 |
| Passport/EID: right document type | 🔑 Needs connection | Nothing reads the image; waits on a vision provider | diwan/documents.py:8-9 |
| Passport/EID: name matches Case | 🟡 Partly | EID only, typed name, flag not reject, not for sellers | diwan/documents.py:197-200 |
| Passport/EID: not expired | 🟡 Partly | Typed date only; the client can type anything | diwan/documents.py:162-168 |
| Passport/EID: 4 corners | ❌ Missing | Not checked | diwan/documents.py:124-144 |
| Passport/EID: readable | 🟡 Partly | Size, light and blur on images only; PDFs skip this | diwan/documents.py:183-190 |
| Title deed: layout | 🔑 Needs connection | No reader | diwan/documents.py:31 |
| Title deed: unit matches Case | ❌ Missing | Typed deed number, never compared | diwan/documents.py:31 |
| PDF form: every line signed | 🟡 Partly | Online all-signers yes; uploaded copy checks only `%PDF` | diwan/agency_forms.py:293; diwan/signing.py:177 |
| PDF form: right version | 🟡 Partly | Link tied to version; upload refused if sent back | diwan/signing.py:102; diwan/agency_forms.py:291 |
| Person sees every signed form in Review | ❌ Missing | Signed forms are filed directly | diwan/signing.py:181-186 |

### Room 3 Deal: exit

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| All tasks done before transfer | ❌ Missing | Trustee step is ticked with no prior gate | diwan/agents/operations.py:112-120 |
| Compliance cleared gate | ❌ Missing | No gate in `tick`, `submitted` or `move` | diwan/agents/operations.py:81-120 |
| Finance deposit received gate | ❌ Missing | Not checked | diwan/agents/operations.py:81-102 |
| Review passed, owner approved | ❌ Missing | Only unsigned agency forms block Form F | diwan/agents/operations.py:95 |
| Emit `deal.ready_for_transfer` | ❌ Missing | Not in code | diwan/events.py |
| Fact corrected: rebuild checklist | ❌ Missing | Steps untouched | diwan/office.py:97-114 |
| Fact corrected: reissue only affected forms | 🟡 Partly | Drafts resting on a fact redo. Cash-to-mortgage has no fact kind. T: TDR changed_price_sends_forms_back | diwan/agents/operations.py:53-61; diwan/graph.py:19 |

### Room 4 Operations

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| `task.created` for form: build from Facts | ✅ Built | Drafts at conversion, blanks left for hand | diwan/agency_forms.py:151-175 |
| Send to client portal or other agency | 🟡 Partly | Broker shares by hand | diwan/agency_forms.py:170 |
| Emit `form.sent` | ❌ Missing | | diwan/events.py |
| Records Fact versions used | 🟡 Partly | Slides link to facts; no version stamp beyond draft number | diwan/agency_forms.py:164 |
| `doc.received`: file on Case | 🟡 Partly | After officer confirms | diwan/documents.py:238 |
| Rename to convention | 🟡 Partly | Internal names only | diwan/documents.py:205 |
| Attach to portal draft | ❌ Missing | | diwan/agents/operations.py:37-50 |
| Emit `doc.filed` | ❌ Missing | `document.filed` is the nearest | diwan/office.py:198 |
| Ready for transfer: request NOC | 🟡 Partly | Tick line; nothing requested | diwan/desk_rules.py:50 |
| Fill trustee request up to Submit | ❌ Missing | No browser code in `diwan/`; Form F "fill" is a field plan | diwan/agents/operations.py:64-78 |
| Book trustee slot | 🟡 Partly | Tick line | diwan/desk_rules.py:52 |
| Emit `transfer.booked` | ❌ Missing | | diwan/events.py |
| Listing signed: permit application | ❌ Missing | | diwan/agency_forms.py |
| Book photographer, draft portal listing | ❌ Missing | | diwan/agents/operations.py |
| Emit `listing.ready` | ❌ Missing | | diwan/events.py |
| Rental signed: Ejari up to Submit | 🟡 Partly | Tick line only | diwan/desk_rules.py:78 |
| Collect cheques Task for Finance | 🟡 Partly | Hand tick plus transactions enters cheques. T: TDR tenancy_cheques | diwan/desk_rules.py:77; diwan/agents/finance.py:265 |
| Emit `ejari.ready` | ❌ Missing | | diwan/events.py |
| `transfer.completed` marked by a person | 🟡 Partly | "Title deed issued" tick, not an event | diwan/desk_rules.py:53 |
| Handover checklist | 🟡 Partly | One tick line for keys, cards and utilities | diwan/desk_rules.py:54 |
| DEWA and chiller reminders | ❌ Missing | | diwan/desk_rules.py:54 |
| Welcome message | ❌ Missing | | diwan/agents/operations.py:245-282 |
| Emit `case.closed` | 🟡 Partly | `sale.closed` + Won. T: TDR closes_when_all_four | diwan/agents/operations.py:271-273 |
| Rule: stop before Submit, Pay, Sign | 🟡 Partly | True: agents have no such action; a person records the reference. T: E2E 5a-5b | diwan/agents/charters.py:83-87; diwan/agents/operations.py:81-98 |
| Rule: filled screen and entered checklist | ❌ Missing | Draft slides only; no screen | web/deal.html:957-968 |
| Rule: built from Facts | ✅ Built | T: TDD form_f_plan | diwan/agents/operations.py:25-34 |
| Rule: withdraw with client message, resend | 🟡 Partly | Draft and link replaced, no message | diwan/agents/review.py:56-64; diwan/signing.py:102 |
| Rule: Task shows waiting-on | 🟡 Partly | Text on steps; not outside-party typed. T: E2E 5f | diwan/agents/operations.py:108 |
| Rule: days waited | 🟡 Partly | Not per task; deal-level stuck KPI only | diwan/desk_kpis.py:64-75 |
| Rule: over limit goes to brief | ❌ Missing | KPI page only | diwan/desk_kpis.py:71 |

### Room 5 Finance

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Bill: automatic draft at trigger | 🟡 Partly | Person presses Draft; signed-form and developer gates exist. T: TDR developer_owes | diwan/agents/finance.py:158-179 |
| Bill: trigger owner-set | ❌ Missing | No trigger setting | diwan/desk_rules.py:26-40 |
| Bill: client or developer payer | ✅ Built | T: TDR diwan_numbers | diwan/invoices.py:28-34 |
| Bill: commission %, VAT 5% | ✅ Built | Settings | diwan/agents/finance.py:125-155 |
| Bill: TRN | ✅ Built | Ours and the payer's | diwan/invoices.py:39-59 |
| Bill: due date | ❌ Missing | Not on the invoice | diwan/invoices.py:57-65 |
| Bill: person approves | 🟡 Partly | "I sent it" is the only step | diwan/agents/finance.py:200-216 |
| Bill: send by email and WhatsApp | ❌ Missing | Person sends and records it | web/deal.html:605 |
| Track: all statuses | 🟡 Partly | Open/done tasks; no due, partly paid, written off | diwan/agents/finance.py:182-234 |
| Chase: reminders on schedule | ❌ Missing | | diwan/app.py:72-75 |
| Chase: overdue developer commission to brief | ❌ Missing | Collect task has no date | diwan/agents/finance.py:214-216 |
| Split: broker commission | ❌ Missing | | diwan/agents/finance.py:125-155 |
| Split: co-broker share | ✅ Built | T: TDR split_paid_out | diwan/agents/finance.py:146-148, 228-231 |
| Split: payout list | 🟡 Partly | Task per other agency only | diwan/agents/finance.py:229 |
| Report: cash in this month | ❌ Missing | 30-day commission only | diwan/deal_desk.py:274 |
| Report: outstanding | 🟡 Partly | Overdue and billed vs collected | diwan/desk_kpis.py:115-129 |
| Report: next 30 days | 🟡 Partly | Next 7 days and an 18-day strip | diwan/deal_desk.py:255, 265 |
| Report: per broker | ❌ Missing | Only pricing KPI is per broker | diwan/desk_kpis.py:139 |
| Mark 1: opens payment, taps | ✅ Built | Payment expectations and commission tasks; a Received button | web/deal.html:415, 566 |
| Mark 2: reference | ✅ Built | Required. T: TDD received_needs | diwan/agents/finance.py:89 |
| Mark 2: amount, date, method | ❌ Missing | Assumes the expected amount | diwan/deal_desk.py:476-484 |
| Mark 2: proof asked | ❌ Missing | | diwan/deal_desk.py:476 |
| Mark 3: reads proof, flags mismatch | ❌ Missing | | diwan/agents/finance.py:80-96 |
| Mark 4: partial keeps balance | ❌ Missing | Task is all or nothing | diwan/agents/finance.py:93 |
| Mark 5: emits event | 🟡 Partly | `task.done`, no `payment.marked_received` | diwan/agents/finance.py:93 |
| Mark 5: unblocks Deal | ❌ Missing | Only developer trigger reads it | diwan/agents/finance.py:119-122 |
| Mark 5: WhatsApp receipt | ❌ Missing | PDF by hand, no send | diwan/invoices.py:69-87 |
| Mark 6: cash threshold to Compliance first | ❌ Missing | Cash report keys on the promise, not the receipt | diwan/agents/compliance.py:162-180 |
| Mark 6: non-client payer holds receipt | ❌ Missing | No check in `mark_received` | diwan/agents/finance.py:80-96 |
| Mark 7: logged who | ✅ Built | Event actor | diwan/agents/finance.py:93 |
| Mark 7: undo with reason | ❌ Missing | No undo code | diwan/agents/finance.py |

### Room 6 Compliance

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| KYC runs at conversion | 🟡 Partly | Docs requested; no KYC record | diwan/agency_forms.py:174 |
| KYC: ID verified | 🟡 Partly | A person compares image and typed fields; a button, not a check | diwan/documents.py:216-239 |
| KYC: names match across documents | 🟡 Partly | One flag against EID | diwan/documents.py:197-200 |
| KYC: address | ❌ Missing | | diwan/documents.py:27-31 |
| KYC: risk rating | ❌ Missing | | diwan/agents/compliance.py |
| Screening trigger: after KYC | 🟡 Partly | Runs on money facts instead. T: TDD every_party | diwan/agents/office hook diwan/office.py:91 |
| Screening again on name or payer change | 🟡 Partly | New payer yes; customer rename no | diwan/agents/compliance.py:38-74 |
| Screening against lists | 🔑 Needs connection | Person records the result; no list | diwan/agents/compliance.py:63-65 |
| PEP status, adverse media | ❌ Missing | Result is clear or possible match only | diwan/agents/compliance.py:84 |
| Hit goes to person, never auto-cleared | ✅ Built | T: TDD only_priya | diwan/agents/compliance.py:77-89 |
| Source of funds: threshold trigger | ❌ Missing | No threshold; runs on any price or deposit | diwan/agents/compliance.py:141-151 |
| SoF: high risk or PEP trigger | ❌ Missing | | diwan/agents/compliance.py |
| SoF: exact quote | ✅ Built | T: TDD source_of_funds | diwan/agents/compliance.py:125-134 |
| SoF: documents asked | 🟡 Partly | Lists proof; not sent to the client | diwan/agents/compliance.py:140-151 |
| SoF: do documents support the story | 🟡 Partly | A "Received" button; no file needed | diwan/deal_desk.py:455-473; web/deal.html:953 |
| Payment pattern check | ❌ Missing | Nothing on receipt | diwan/agents/finance.py:80-96 |
| Mortgage checks | ❌ Missing | No mortgage fact kind | diwan/graph.py:19 |
| Enhanced due diligence | ❌ Missing | | diwan/agents/compliance.py |
| Reporting: cash report draft | ✅ Built | Officer files with reference. T: TDD cash_at_threshold | diwan/agents/compliance.py:92-102, 162-180 |
| Reporting: STR draft | ❌ Missing | Cash only | diwan/agents/compliance.py |
| Reporting: person decides | 🟡 Partly | Cash draft is automatic on a promise | diwan/agents/compliance.py:162 |
| Correction 1: contradiction detected | 🟡 Partly | Payer and price only; a person or agent must supply `replaces`. T: TDD a_payer_in_dispute | diwan/office.py:14, 116-129 |
| Correction 2: Compliance first, both quotes | 🟡 Partly | Only payer, promise, income. A price change skips Compliance. T: E2E 1c | diwan/agents/compliance.py:17, 22 |
| Correction 3: tasks withdrawn | 🟡 Partly | Rest-on tasks only; transfer steps rest on nothing. T: E2E 1e | diwan/office.py:106-109 |
| Correction 3: approvals back | ✅ Built | T: TDD reapprove | diwan/agents/review.py:14-18 |
| Correction 3: marked superseded | ✅ Built | Reason names the fact | diwan/office.py:109 |
| Correction 3: sent form recalled | 🟡 Partly | Replaced; no client notice | diwan/signing.py:102 |
| Correction 4: Compliance decides rerun | 🟡 Partly | Screening reruns automatically; no decision step. No clear test for rerun blocking transfer | diwan/office.py:91-93 |
| Correction 5: stale approvals refused | ✅ Built | T: TDD stale_approval, E2E 1g | diwan/office.py:158-162 |
| Correction 5: other work untouched | ✅ Built | By graph impact | diwan/graph.py:105-111 |
| `compliance.cleared` | ❌ Missing | "Clear" is a display label | diwan/deal_desk.py:143-144 |
| `compliance.needs_info` to portal | ❌ Missing | Only a broker question | diwan/agents/compliance.py:202 |
| `compliance.blocked`, Case stops | ❌ Missing | "Possible match" is a label; the deal moves on | diwan/deal_desk.py:133 |
| Transfer needs clearance | ❌ Missing | A recorded possible match leaves the task done, so closing passes | diwan/agents/operations.py:195-196, 208 |

### Room 7 Review

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Quotes: current | 🟡 Partly | Drafts only, stale check. T: TDD draft_using_replaced | diwan/agents/review.py:67-79 |
| Quotes: every claim traces | 🟡 Partly | Agent packs get a quote check, drafts don't | diwan/agents/runner.py:1 |
| Numbers consistent across documents | ❌ Missing | No cross-check | diwan/agents/review.py |
| Completeness: checklist done | ❌ Missing | | diwan/agents/review.py |
| Completeness: signatures on every line | 🟡 Partly | Online all-signers outside Review | diwan/signing.py:177 |
| Authority: charter | 🟡 Partly | At the agent turn, not in Review | diwan/agents/runner.py:139-156 |
| Authority: nothing sent without a yes | ❌ Missing | No such check | diwan/agents/review.py |
| Tone and promises | 🟡 Partly | Studio permit and claims QA only; not deal items | diwan/agents/charters.py:243; diwan/agents/qa.py |
| Compliance hold | ❌ Missing | No hold exists | diwan/agents/review.py |
| One card per item | 🟡 Partly | Draft card, slides listed | web/deal.html:957-968 |
| What, room, agent | 🟡 Partly | Kind only | web/deal.html:963 |
| Green/amber/red verdict | ❌ Missing | Passed or sent back | diwan/agents/review.py:75-79 |
| Finding per line, links to quotes | 🟡 Partly | One reason, slide stale notes | web/deal.html:965-967 |
| Approve | ❌ Missing | Pass is automatic; no human button on drafts | web/deal.html:957-968 |
| Send back with note | ❌ Missing | Only automatic | diwan/agents/review.py:56-64 |
| Edit | ❌ Missing | | web/deal.html |
| Approve pins to Fact versions | 🟡 Partly | `approval` rests on facts, used for release only. T: TDD | diwan/office.py:145-148; diwan/agents/finance.py:114 |
| Send back creates Task with note | ❌ Missing | Redrafts itself | diwan/agents/operations.py:53-61 |
| Patterns feed Lobby | ❌ Missing | KPI count only | diwan/desk_kpis.py:45 |

### Part 2 commands and bug rows

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Deal: room on 3D floor | ❌ Missing | Departments: Sales, Review, Operations, Finance, Compliance | web/office3d.html:129-138 |
| Deal blocks: board | 🟡 Partly | Table, stage filter, overview bars | diwan/deal_desk.py:271 |
| Deal blocks: portal status | 🟡 Partly | Status and reminders; "opened" not tracked | diwan/deal_desk.py:722; web/deal.html:808 |
| Deal blocks: gates panel | 🟡 Partly | Four status boxes, display only | web/deal.html:994 |
| Deal cmd 1 to 7 | 🟡 Partly | See Room 3 rows | diwan/deal_desk.py |
| Deal tests: selfie rejected, drawn accepted, sandbox receipt, gates | ❌ Missing | None | tests/test_desk_rules.py:672 |
| Ops blocks: forms with version | 🟡 Partly | Agency forms show version | web/deal.html:879 |
| Ops blocks: recalled forms | 🟡 Partly | Sent-back list | web/deal.html:888 |
| Ops blocks: appointments | ❌ Missing | Trustee has no date | diwan/desk_rules.py:52 |
| Ops test: tasks after ready_for_transfer | ❌ Missing | Recall has partial cover in TDR | tests/test_desk_rules.py:505 |
| Finance blocks: invoices, Mark received, words | 🟡 Partly | Per Room 5 | web/deal.html:566-610 |
| Finance blocks: flags for Compliance | ❌ Missing | | web/deal.html |
| Finance tests: mismatch flag, third-party before receipt | ❌ Missing | | tests/ |
| Compliance blocks: corrections side by side | ✅ Built | T: E2E 8a | diwan/deal_desk.py:279-290 |
| Compliance blocks: screening queue | ✅ Built | T: E2E 8f | diwan/deal_desk.py:229 |
| Compliance blocks: SoF files | 🟡 Partly | | web/deal.html:944-955 |
| Compliance blocks: risk rating, holds, rule book | ❌ Missing | | web/deal.html |
| Compliance blocks: report drafts | 🟡 Partly | Cash only | diwan/agents/compliance.py:177 |
| Compliance test: new payer blocks transfer | ❌ Missing | | tests/ |
| Review blocks | 🟡 Partly | Sent-back and approvals visible; no green/amber/red or patterns | web/deal.html:957 |
| Review test: red invoice blocks approve | 🟡 Partly | Send refused when the price changed; no red. T: TDR changed_price_sends_invoice_back | diwan/agents/finance.py:207 |
| T5 screening idle | ❌ Missing | Waiting counts only cards, not tasks, so analyst stays idle | web/office3d.html:628-631 |
| Open Task auto-starts or shows why blocked | ❌ Missing | Tasks stay queued for a person | diwan/graph.py:217 |
| "named by Ali Rahman" | ❌ Missing | String still there | diwan/agents/compliance.py:57 |
| Review 0 tasks | 🟡 Partly | Drafts checked at make; no task or `review.requested`; messages and transfers skip it | diwan/office.py:172 |
| Devil's advocate no work | ❌ Missing | No status, so "planned"; no code runs it | diwan/agents/charters.py:136-138, 31 |
| Operations 0 tasks | 🟡 Partly | Tasks exist after conversion and Form F, without the event | diwan/agency_forms.py:170 |
| Invoice clerk reads supplier invoices | 🟡 Partly | Code does outgoing commission; charter text is unchanged | diwan/agents/charters.py:103-106 |

### Part 3: gap table

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1 Deal falls through | 🟡 Partly | Lost with free text; listing released. T: TDP lost_deal | diwan/desk_stages.py:75-76 |
| 2 Who the party is | ❌ Missing | Customer is one name | diwan/documents.py:44-52 |
| 3 Co-broking | ✅ Built | Form I, share, payout. T: TDP, TDR | diwan/agency_forms.py:45-52; diwan/agents/finance.py:228 |
| 4 Seller side and listings | 🟡 Partly | Form A; catalog; no flow | diwan/agency_forms.py:196; diwan/listing_add.py |
| 5 Seller's mortgage | 🟡 Partly | Tick line | diwan/desk_rules.py:49 |
| 6 Tenanted units sold | ❌ Missing | | diwan/desk_rules.py |
| 7 Deposit held, returned, refunded | 🟡 Partly | Holder setting and release approval; no return or refund | diwan/desk_rules.py:38; diwan/agents/finance.py:99-114 |
| 8 Bounced cheques | ❌ Missing | No bounce state | diwan/agents/finance.py |
| 9 Renewals and move-out | 🟡 Partly | Dated tasks closed with free text. T: TDR closing_a_rental | diwan/agents/operations.py:275-281 |
| 10 Expiry of uploads | 🟡 Partly | At upload only; no sweep | diwan/documents.py:162-170 |
| 11 Client languages | 🟡 Partly | Rania Arabic/English; portal pages English | diwan/agents/reception.py:79; web/docs.html |
| 12 Consent and privacy | 🟡 Partly | Stop handled; no opt-in record or deletion | diwan/agents/nudge.py:321 |
| 13 Disputes and complaints | ❌ Missing | No complaint code | diwan/ |
| 14 Staff leave | 🟡 Partly | Role and single lead moves; no one-step handover | diwan/roles.py:55; diwan/leads.py:209; diwan/access.py:164 |
| 15 Developer vs client commission | ✅ Built | Payer, trigger, KPIs by payer. T: TDR | diwan/agents/finance.py:125-155; diwan/desk_kpis.py:115 |

### Part 3: identity table

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| UAE resident: uploads | ✅ Built | EID both sides, passport, visa | diwan/desk_rules.py:32 |
| UAE resident: type, cross-name | 🔑 Needs connection | No reader | diwan/documents.py:8-9 |
| UAE resident: EID format | ✅ Built | Pattern and check-digit flag | diwan/documents.py:155-161 |
| UAE resident: corners, glare | 🟡 Partly | Average brightness only | diwan/documents.py:136-140 |
| UAE resident: warn 30 days | 🟡 Partly | 60 days hard-coded, flag at upload only | diwan/documents.py:169 |
| UAE resident: block at expiry | 🟡 Partly | At upload only | diwan/documents.py:167 |
| Non-resident | ❌ Missing | No party type, no address kind | diwan/documents.py:27 |
| GCC national | ❌ Missing | | diwan/documents.py:27 |
| Joint buyers | ❌ Missing | One customer; forms have one buyer line | diwan/agency_forms.py:213 |
| Company onshore | ❌ Missing | `documents.company` is never used; `parties` has no company | diwan/desk_rules.py:33; diwan/documents.py:44-52 |
| Company offshore | ❌ Missing | | diwan/documents.py |
| POA | ❌ Missing | | diwan/documents.py |
| Estate, minor: flag to person | ❌ Missing | | diwan/documents.py |

### Part 3: deal documents

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Sale cash: buyer | 🟡 Partly | Identity yes; deposit by promise; manager's cheque by tick | diwan/desk_rules.py:32, 51 |
| Sale cash: seller | 🟡 Partly | Identity, deed; no tenancy, no service charge | diwan/desk_rules.py:32 |
| Sale cash: outside parties | 🟡 Partly | Two tick lines | diwan/desk_rules.py:50, 52 |
| Sale cash: generated | ✅ Built | Forms, invoice, receipt | diwan/agency_forms.py:241; diwan/invoices.py |
| Sale mortgage | 🟡 Partly | Tick lines; no document kinds or timeline tasks | diwan/desk_rules.py:48 |
| Seller has a mortgage | 🟡 Partly | Tick; no payment split | diwan/desk_rules.py:49 |
| Off-plan: buyer | 🟡 Partly | Identity and hand ticks; no proof upload | diwan/desk_rules.py:62-63 |
| Off-plan: outside | 🟡 Partly | Tick for Oqood; receipt none | diwan/desk_rules.py:64 |
| Off-plan: generated | 🟡 Partly | Developer invoice yes; reservation summary no | diwan/invoices.py:28 |
| Off-plan resale | ❌ Missing | Sources allow only listing or agency, no fields | diwan/deal_property.py:33-35 |
| Rental: tenant | 🟡 Partly | Identity, cheques data; no employer letter | diwan/desk_rules.py:33 |
| Rental: landlord | ❌ Missing | | diwan/documents.py:47 |
| Rental: Ejari certificate | 🟡 Partly | Named in closing text only | diwan/desk_rules.py:81 |
| Rental: generated | 🟡 Partly | Agency fee invoice; no contract, handover or move-in report | diwan/invoices.py |
| Rental renewal | 🟡 Partly | One notice task; no 60-day, no contract | diwan/agents/operations.py:278 |
| Listing | ❌ Missing | Identity through a deal only | diwan/desk_rules.py:41 |

### Part 3: portal checks

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Drawn signature strokes | ❌ Missing | No drawing | web/sign.html:56 |
| Signature photo | ❌ Missing | Size only | diwan/signing.py:136 |
| ID or passport | 🟡 Partly | Typed expiry and number format; no MRZ. T: TDR bad_upload | diwan/documents.py:147-171 |
| Two-sided ID | 🟡 Partly | Two items; no specific message | diwan/desk_rules.py:32 |
| Title deed, Oqood | ❌ Missing | Oqood kind absent | diwan/documents.py:27-31 |
| Signed PDF form | 🟡 Partly | Per signer online only | diwan/signing.py:177 |
| Cheque photo | ❌ Missing | No kind | diwan/documents.py:27 |
| Bank letter, pre-approval | ❌ Missing | No kind | diwan/documents.py:27 |
| Proof of address | ❌ Missing | No kind | diwan/documents.py:27 |
| Any upload: type, size | ✅ Built | 8 MB. T: TDR bad_upload | diwan/documents.py:185-188 |
| Any upload: opens, not password-protected | 🟡 Partly | Images verified; PDF header only | diwan/documents.py:183-190 |
| Same file noticed | ✅ Built | Within one link only | diwan/documents.py:192 |
| Person overrides rejection with reason | ❌ Missing | Rejected files are not kept | diwan/documents.py:201-203 |

### Part 3: Secondary sale

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1 Listing exists | 🟡 Partly | Catalog record; no flow or message | diwan/office.py:185 |
| 2 Form B before viewing | ❌ Missing | Forms start at conversion; no gate on viewing | diwan/desk_stages.py:79 |
| 3 Offer as Fact | 🟡 Partly | Stage plus price at convert; no seller message | diwan/desk_stages.py:162-175 |
| 4 Counter, accept | 🟡 Partly | No counters; acceptance not quoted; no message | diwan/desk_stages.py:105 |
| 5 Co-broke | ✅ Built | No event | diwan/agency_forms.py:106-119 |
| 6 KYC both sides | 🟡 Partly | Seller "the seller" never screened | diwan/agents/compliance.py:38-60 |
| 7 Liability letter | 🟡 Partly | Tick; validity not checked | diwan/desk_rules.py:49 |
| 8 Valuation and final offer | 🟡 Partly | Tick; no valuation comparison | diwan/desk_rules.py:48 |
| 9 MOU from Facts | 🟡 Partly | Review auto; no owner approval | diwan/deal_desk.py:516-526 |
| 10 MOU signed, deposit | 🟡 Partly | Signing built, self-ticks. T: TDR form_f_signed_online; no cheque check or message | diwan/signing.py:182-191 |
| 11 NOC | 🟡 Partly | Tick; no charges gate or message | diwan/desk_rules.py:50 |
| 12 Transfer booked | 🟡 Partly | Tick; no gate or message | diwan/desk_rules.py:52 |
| 13 Cheques | 🟡 Partly | Tick; fees shown; no split or cheque list | diwan/desk_rules.py:51; diwan/agents/finance.py:149 |
| 14 Transfer completes | 🟡 Partly | Tick, no message | diwan/desk_rules.py:53 |
| 15 Invoice, commission | ✅ Built | Receipt not sent | diwan/agents/finance.py:158-234 |
| 16 Handover | 🟡 Partly | Tick and closing; no welcome or review ask | diwan/agents/operations.py:245 |
| 17 Aftercare | ❌ Missing | Rental only has after-close work | diwan/agents/operations.py:275 |

### Part 3: Off-plan

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1 Unit held, dated price list | ❌ Missing | No dated list; hold only on our listing | diwan/deal_property.py:187-192 |
| 2 Reservation | 🟡 Partly | Developer account rule covers scheduled instalments only | diwan/agents/finance.py:239, 305 |
| 3 KYC | 🟡 Partly | As Room 6 | diwan/agents/compliance.py:63 |
| 4 SPA | 🟡 Partly | Tick; pages not checked | diwan/desk_rules.py:63 |
| 5 Oqood | 🟡 Partly | Tick, no message | diwan/desk_rules.py:64 |
| 6 Commission to developer | ✅ Built | Trigger enforced. T: TDR developer_owes, E2E 14f | diwan/agents/finance.py:170 |
| 7 Instalments tracked | 🟡 Partly | Due and overdue; no 14 and 3 day reminders | diwan/agents/finance.py:68-70 |
| 8 Handover | 🟡 Partly | After-closing tick; no snag list. T: TDR offplan_closes | diwan/desk_rules.py:65 |

### Part 3: Rental

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1 Qualifies, views | ✅ Built | Sales. Not audited in depth | diwan/inbox.py:252 |
| 2 Offer | 🟡 Partly | Landlord acceptance not quoted | diwan/desk_stages.py:105 |
| 3 Documents and cheques | 🟡 Partly | Cheques not checked | diwan/agents/finance.py:249 |
| 4 Contract | 🟡 Partly | Tick; not generated | diwan/desk_rules.py:75 |
| 5 Ejari | 🟡 Partly | Tick; certificate not sent | diwan/desk_rules.py:78 |
| 6 Agency fee | 🟡 Partly | Invoice and receipt PDF; not sent. T: E2E 12d | diwan/agents/finance.py:158 |
| 7 Move-in | 🟡 Partly | Tick; no report | diwan/desk_rules.py:79 |
| 8 Cheque dates | 🟡 Partly | Overdue shown; landlord not reminded | diwan/agents/finance.py:68 |
| 9 Renewal | 🟡 Partly | Broker task; no message. T: E2E 13k | diwan/agents/operations.py:278 |

### Part 3: Listing

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1 Valuation | ❌ Missing | | diwan/ |
| 2 Form A signed | 🟡 Partly | Only on a converted deal | diwan/agency_forms.py:45-52 |
| 3 Permit and photos | ❌ Missing | Permit is a stored field | diwan/office.py:185 |
| 4 Live, permit on ads | 🟡 Partly | Studio permit check and Rania only offer permitted | diwan/agents/reception.py:488; diwan/agents/charters.py:243 |
| 5 Weekly seller report | ❌ Missing | | diwan/ |
| 6 Price change | 🟡 Partly | Listing edit proposal; not a fact, no withdrawal | diwan/knowledge.py:28, 285 |
| 7 Offer continues to sale | 🟡 Partly | Via deal conversion | diwan/deal_property.py:58 |
| 8 Form A expiring | ❌ Missing | | diwan/ |

### Part 3: When things go wrong

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Client corrects | 🟡 Partly | Payer strong; price skips Compliance | diwan/agents/compliance.py:22 |
| Buyer walks after MOU | 🟡 Partly | Lost, listing back; no deposit options, no message, no lost reason list | diwan/deal_property.py:201-203; web/deal.html:715 |
| Seller withdraws | 🟡 Partly | Same; buyer not sent back to Sales | diwan/desk_stages.py:75 |
| Mortgage refused | ❌ Missing | | diwan/ |
| Valuation below price | ❌ Missing | | diwan/ |
| Liability letter expires | ❌ Missing | | diwan/ |
| NOC refused or delayed | ❌ Missing | Waiting text and stuck KPI only | diwan/desk_kpis.py:71 |
| Screening hit | 🟡 Partly | Label; no hold; no client wording. Tipping-off guard in follow-ups | diwan/deal_desk.py:133; diwan/agents/followup.py:16 |
| Third-party payment | 🟡 Partly | Screened from words, not at receipt; receipt not held | diwan/agents/compliance.py:58; diwan/agents/finance.py:80 |
| Cheque bounced | ❌ Missing | | diwan/agents/finance.py |
| Commission not paid | 🟡 Partly | Blocks closing, opposite of spec; no ladder or dispute log | diwan/agents/operations.py:192-194 |
| Co-broker dispute | ❌ Missing | Log exists; no hold | diwan/agents/finance.py:228 |
| Wrong document accepted | ❌ Missing | No void after confirm; send back only while task open | diwan/documents.py:222-223 |
| Staff leaves | 🟡 Partly | Login removal, role move; no bulk or client notice. T: E2E 9c | diwan/access.py:164; diwan/roles.py:55 |

### Case stages

Common to every row: stages are moved by hand. T: TDR who_moves_a_stage. The move itself is at diwan/desk_stages.py:47-80.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Sale: documents | 🟡 Partly | "Offer accepted" is nearest; no exit gate | diwan/desk_rules.py:45 |
| Sale: cleared | ❌ Missing | | diwan/desk_rules.py:45 |
| Sale: mou_signed | 🟡 Partly | "Form F"; no check | diwan/desk_rules.py:45 |
| Sale: transfer_ready | 🟡 Partly | "Transfer"; no gate | diwan/desk_rules.py:45 |
| Sale: transfer_booked | ❌ Missing | | diwan/desk_rules.py:45 |
| Sale: transferred | 🟡 Partly | "Closing" derived from steps | diwan/agents/operations.py:173 |
| closed_won rule | 🟡 Partly | Won only from closing. T: TDR closes_when_all_four | diwan/desk_stages.py:58 |
| Off-plan: reserved | 🟡 Partly | "Reservation", not by payment | diwan/desk_rules.py:61 |
| Off-plan: spa_signed | 🟡 Partly | "SPA", by hand | diwan/desk_rules.py:61 |
| Off-plan: registered | 🟡 Partly | "Oqood", by hand | diwan/desk_rules.py:61 |
| Off-plan: handover_due | 🟡 Partly | After-closing step; Won comes before handover | diwan/desk_rules.py:65 |
| Rental: documents | 🟡 Partly | "Offer accepted" | diwan/desk_rules.py:73 |
| Rental: contract_signed | 🟡 Partly | "Contract" | diwan/desk_rules.py:73 |
| Rental: moved_in | 🟡 Partly | "Move-in" | diwan/desk_rules.py:73 |
| Rental: tenancy_active | ❌ Missing | Deal is Won; after-tasks only | diwan/agents/operations.py:273 |
| Rental: renewal_due | 🟡 Partly | Task, not a stage | diwan/agents/operations.py:278 |
| Rental: move_out | 🟡 Partly | Task, not a stage | diwan/agents/operations.py:280 |
| Listing: all 4 stages | ❌ Missing | | diwan/desk_rules.py:41 |
| Moves off-list refused and logged | 🟡 Partly | Refused; skipping forward allowed; not logged | diwan/desk_stages.py:61-68 |
| Lost reason dropdown | ❌ Missing | Free text | web/deal.html:715 |
| Closed never reopens, new linked Case | 🟡 Partly | Won refuses; Lost comes back | diwan/desk_stages.py:56, 71-73 |

### Seed scenarios

No Playwright scenario with these names exists, and none of the e2e flows runs one of these as an end-to-end story.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Sara | 🟡 Partly | Karim demo covers correction in the reverse direction; no receipt hold | diwan/demo.py:115; e2e/deal_flow.py:65-82 |
| Karim, mortgage, valuation gap | ❌ Missing | | diwan/desk_rules.py:48 |
| Al Noor Trading | ❌ Missing | No match in code or tests | diwan/documents.py |
| Priya POA | ❌ Missing | Priya is also the seeded compliance officer's name | diwan/agents/nova.py:147 |
| Omar's buyer walks | 🟡 Partly | Listing back: T: TDP lost_deal; no deposit options | tests/test_deal_property.py:208 |
| Tenant Ahmed | 🟡 Partly | 4 cheques, renewal and move-out tasks; no bounce. Ahmed is also finance | e2e/deal_flow.py:526, 565 |
| Lina off-plan | 🟡 Partly | Flow in E2E 14 under other names, stages by hand | e2e/deal_flow.py:613-669 |
| Selfie as signature | ❌ Missing | Would be accepted | diwan/signing.py:123-147 |
| Expired passport | 🟡 Partly | Rejected from the typed date only | diwan/documents.py:167 |
| Deed with wrong unit | ❌ Missing | | diwan/documents.py:31 |

### Five biggest gaps

1. **No spine or gates.** None of the Part 4 catalog events checked exists, so `compliance.cleared` and `deal.ready_for_transfer` exist nowhere. Stages are hand-moved labels. There is no on_hold, and a "possible match" does not stop a deal, even at closing (diwan/agents/operations.py:195).
2. **Upload checks never look at the document.** There is no reader, no drawn signature, and a selfie or blank image passes as a signature. Cheques, bank letters, address proof, Oqood and deed-unit checks don't exist. WhatsApp is not used for the first link or for receipts.
3. **One buyer shape only.** Non-resident, joint, company, POA and estate parties are absent, and the `company` setting is dead. There is no cash/mortgage split and no Listing path. Tenanted sale, mortgage refusal, valuation gap, bounced cheque and off-plan resale are absent.
4. **Finance's Mark received is a reference box.** It has no amount, method, date, proof, partial payment, undo, receipt send, third-party or cash hold, or payment-pattern check. Invoices have no due date, chase, approval or delivery, and there are no broker payouts or a per-broker report.
5. **Review is an automatic stale check and Operations has no execution.** There is no human card, verdict, Approve, Send back or Edit, and the Devil's advocate has no code. Operations fills no portals. NOC, Ejari, trustee and permit are ticks. Clients get no recall, welcome or status messages.

## Records, Lobby, Marketing, events, schedules


### Room 8 Records: what it holds

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Records clerk agent | ✅ Built | Under the name Archivist | agents/charters.py:146 |
| Data analyst agent | ✅ Built | Rules only, no estimates | agents/charters.py:151; agents/records.py:63 |
| Searchable Person/Case/Fact/Doc | 🟡 Partly | Keyword search over items and graph; no Person/Case model, no Records search screen | knowledge_api.py:169; graph.py:171 |
| Kept for the retention period | ❌ Missing | No retention setting or job | no code hit |
| Case file: Event timeline | 🟡 Partly | Raw `/api/events` and graph replay; no case-file view | graph.py:188; web/graph.html |
| Case file: Facts, quotes, superseded history | 🟡 Partly | Data exists; shown on deal view, not a case file | graph.py:113; deal_desk.py:89 |
| Case file: document versions | 🟡 Partly | Draft versions only; filed documents have no version | office.py:170; office.py:195 |
| Case file: approvals and who | 🟡 Partly | Approval carries approver; deal view only | office.py:145 |
| Register: deals closed | ✅ Built | Ledger, but `/api/records` has no page calling it | agents/records.py:146; app.py:928 |
| Register: listings | 🟡 Partly | Catalog page, not a register | web/catalog.html |
| Register: tenancies with renewal dates | ❌ Missing | Dates sit in deal terms and a task; no register | agents/operations.py:275-280 |
| Register: commissions | 🟡 Partly | Ledger column plus Deal desk KPI | desk_kpis.py:114-129 |
| Register: compliance files with retention | ❌ Missing | Tasks and documents only | agents/compliance.py |
| Audit trail: who did what, agents included | ✅ Built | Actor and agent on every event; test test_infra.py:83 | events.py:56-62 |
| Audit: read-only, nothing deleted | ✅ Built | SQL triggers abort update and delete | events.py:61-62 |
| Void with reason | ❌ Missing | No void concept; knowledge retire and approval refuse only | grep "void" no hit |

### Room 8 Records: Data analyst answers

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Funnel by channel, broker, month, drop-off | ❌ Missing | Raw events exist; nothing computes it; fall-through covers post-paperwork only | desk_kpis.py:100-102 |
| Speed: first reply time | ❌ Missing | Not computed | no code hit |
| Speed: time to call after "call me" | ❌ Missing | Attention card has due and clear times; never measured | leads.py:142,161 |
| Speed: days in each stage | 🟡 Partly | Days per paperwork step and yes-to-closed only; no stage durations | desk_kpis.py:54-62,77-84 |
| Money: commission closed | ✅ Built | Test test_records.py:28 | agents/records.py:97 |
| Money: commission pending | 🟡 Partly | Pipeline is at price, not commission; billed vs collected on Deal desk only | agents/records.py:67-74; desk_kpis.py:114 |
| Money: cost per lead by channel | ❌ Missing | No ad spend joined to leads | providers/ads.py:58 |
| Money: average deal size | ❌ Missing | Not computed | agents/records.py |
| People: broker leaderboard | 🟡 Partly | "top broker" by commission for a named period only | agents/records.py:91-96 |
| People: follow-up discipline | ❌ Missing | Not computed | no code hit |
| People: send-back rate in Review | 🟡 Partly | Office-wide count over 30 days, not a rate or per broker | desk_kpis.py:44,149 |
| Market: asking vs closing by area | 🟡 Partly | Agreed vs listing % per broker; not by area; analyst cannot answer it | desk_kpis.py:138-146 |
| Renewals: 90 days become Sales Tasks | 🟡 Partly | One task made at closing, agent `ops` not Sales, no scan, no new Case; test test_desk_rules.py:353 | agents/operations.py:275-280 |
| Answers through Nova | 🟡 Partly | Works for the owner; `/api/nova*` is not in access API, so staff cannot call it; test test_records.py:28 | agents/records.py:124; access.py:53-63,108 |
| Answers on Records dashboard | ❌ Missing | No Records page; floor has only the "Archive" orb | web/ listing; brain.py:81 |
| Every number links to records | 🟡 Partly | Nova answers cite ids; Deal desk KPIs list deals | agents/records.py:138-143 |
| "Not recorded" rather than estimate | ✅ Built | Asks for a period, says when missing; test test_records.py:46 | agents/records.py:75-87 |

### Room 8 Records: weekly report

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Monday report in brief | ❌ Missing | No weekly job; rounds is daily, task counts only | app.py:57-89; agents/nova.py:451-481 |
| Report numbers link to records | ❌ Missing | No report exists | same |

### Room 9 Lobby

Today's Lobby is a job board: `agents/lobby.py` holds work requests with due dates. `lobby.*` events and tests/test_frontdesk.py cover that board only. None of the rows below is met by it.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Lobby as a learning room | ❌ Missing | Name reused for a job board | agents/lobby.py:1 |
| Lobby host agent | ❌ Missing | No charter | agents/charters.py:37-256 |
| One rep per room | ❌ Missing | No charter | same |
| Input: anonymised opt-in playbooks | ❌ Missing | `playbook` is own-post structures only | agents/studio.py:976 |
| Input: competitor posts | 📦 Data, no reader | Reader and board exist; no Lobby to read them | agents/reader.py:245; agents/studio.py:76 |
| Input: portal listing trends | ❌ Missing | Feed sync is our own listings | leads.py:340 |
| Input: DLD transaction data | ❌ Missing | No provider | providers/ |
| Input: project and regulation news | ❌ Missing | Trends only per run | agents/studio.py:446 |
| Input: Review send-backs | 📦 Data, no reader | `review.returned`, `qa.failed` logged; no reader for learning | agents/review.py:60; agents/qa.py:218 |
| Input: lost deals with reasons | 📦 Data, no reader | `stage.changed` carries why | desk_stages.py:74 |
| Input: questions Rania couldn't answer | 📦 Data, no reader | `qualify.open` stored on the deal | graph.py:418 |
| Weekly thread per room | ❌ Missing | Nothing | no code hit |
| Each proposal an experiment | ❌ Missing | No model | grep "experiment" no hit in events |
| Owner approves experiment | ❌ Missing | Nothing | same |
| Records reports result, keep or roll back | ❌ Missing | Nothing | same |
| Experiment applies to audience and period only | ❌ Missing | Spec's test cannot exist | tests/ |
| One idea a day in brief | ❌ Missing | Not in rounds or brief | agents/nova.py:488,506 |
| Guardrail: agent suggests, cannot apply | ❌ Missing | No suggestion path; lessons are taught by people only | agents/lessons.py |
| Guardrail: compliance and owner settings untouchable from Lobby | ❌ Missing | Nothing to guard; rules are owner-saved | desk_rules.py |

### Marketing: content stages

No stage field exists. A piece of content is inferred from `content.made` kinds. The screen's chain uses other names: "Pick a script, Film it, Editing, Approve publishing" (agents/studio.py:1595-1602). `journey.STAGES` are account stages, a different concept (agents/journey.py:29).

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Single per-content stage, only these names | ❌ Missing | No state machine | agents/studio.py:189,1585 |
| idea: name and owner | 🟡 Partly | `ideas` from Idea generator, reviewed by QA | agents/studio.py:626,1329 |
| idea enters: Lobby idea | ❌ Missing | No Lobby | n/a |
| idea enters: competitor signal | 🟡 Partly | Fed in when a run starts; signal does not start one | agents/studio.py:1318-1326 |
| idea enters: new listing | ❌ Missing | `listing.added` triggers nothing in the studio | leads.py:355 |
| idea enters: price change | ❌ Missing | Nothing | same |
| idea enters: owner's topic | ✅ Built | Topics and moments; tests test_journey.py:142 | agents/rhythm.py:176; agents/journey.py:185 |
| idea leaves: brief approved by person | ❌ Missing | Goes straight to scripts | agents/studio.py:1329-1337 |
| briefed stage | ❌ Missing | `_brief` is a fact sheet; no approval | agents/studio.py:196 |
| scripted: three scripts | ✅ Built | Up to 3 angles; test test_strategy.py:38 | agents/studio.py:935 |
| scripted: each from its own Facts | 🟡 Partly | Listing field snapshot `listing_was`, not Fact ids | agents/studio.py:872,882 |
| scripted leaves: person picks, Review passed | 🟡 Partly | Person picks; "Review" is the Copywriter QA | agents/studio.py:1344; agents/qa.py:204 |
| in_production: film list, footage, editing | 🟡 Partly | Works, unnamed; no stage | agents/studio.py:1422,1529 |
| in_production exit: video, captions, cover | 🟡 Partly | Cut and captions checked; cover has no check | agents/qa.py:175-179; agents/studio.py:1540 |
| in_production exit: permit on screen and caption | 🟡 Partly | Caption checked; on-screen is a film-list shot, not verified in the cut | agents/qa.py:111,156 |
| ready: final cut + Review + permit valid | 🟡 Partly | Permit gate checks number present, not validity | agents/studio.py:1142,1287 |
| ready leaves: person approves post and time | 🟡 Partly | Approves or "now"; time is the proposed slot, no time edit server-side | app.py:517-521; agents/studio.py:1202 |
| scheduled | ✅ Built | Same word as a content kind; test test_studio.py:349 | agents/studio.py:1210,1216 |
| scheduled: auto-post only if owner switched on | 🟡 Partly | Every approved post auto-goes at its time; no such switch | agents/studio.py:1233; app.py:79 |
| live | 🟡 Partly | `published` kind; no further state | agents/studio.py:1263 |
| paused | ❌ Missing | No code | grep "paused" in studio.py no hit |
| paused back to ready | ❌ Missing | No code | same |
| withdrawn | ❌ Missing | `unschedule` is pre-post only; no delete in Instagram provider | agents/studio.py:1228; providers/instagram.py |
| archived | ❌ Missing | No code | no code hit |

### Marketing: events

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Emit and consume marketing events | ❌ Missing | See the catalog table below; no handler reacts to any listing or fact change | events.py:32 |

### Marketing: closing the loop

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1. Tracked link on posts and ads | ❌ Missing | No tracking code | grep utm/referral/ctwa no hit |
| 1. Code word ("reply MARINA") | ❌ Missing | None | same |
| 1. Portal listing traced | 🟡 Partly | Portal lead keeps `ref` and channel; not a code | leads.py:419-421 |
| 2. `lead.attributed` on Case | ❌ Missing | Inbox derives first channel only | inbox.py:94 |
| 2. Comment names its post | 🔑 Needs connection | `media_id` parsed then dropped by the webhook | providers/instagram.py:167; app.py:541 |
| 3. Comments go to Sales | ✅ Built | As `chat.received`; test test_studio.py:374 | app.py:539-541 |
| 3. DMs go to Sales | ❌ Missing | Only field "comments" parsed | providers/instagram.py:161 |
| 3. Marketing does not answer | ✅ Built | Lead chat routes to Sales | agents/lead_chat.py:116 |
| 4. Report: reach per post | 🟡 Partly | Own insights, no lead data alongside | providers/instagram.py:88-90 |
| 4. Report: leads, qualified, viewings, deals, commission per post | ❌ Missing | Self-declared unbuilt (flows 2, 3) | agents/custom.py:221-222 |
| 4. Report: spend per campaign | 🟡 Partly | Per-ad spend read live from Meta, never stored | providers/ads.py:58 |
| 5. Weekly: what brought deals | ❌ Missing | Strategy ranks engagement only | agents/strategy.py:1-16 |
| 5. Lobby turns it into an experiment | ❌ Missing | No Lobby | n/a |

### Marketing: campaigns and spend

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Campaign with goal, audience, budget, dates, content | ❌ Missing | No model | grep "campaign" no hit |
| Spend as setting with hard cap | ❌ Missing | Budget in studio is model cost, not ad spend | web/studio.html:493 |
| Agents draft ads and audiences | ❌ Missing | Read-only provider; test test_ads.py:24 | providers/ads.py:1 |
| Person launches and pays | ✅ Built | True by absence: nothing can launch | providers/ads.py:1 |
| CPL over limit flagged in brief | ❌ Missing | No limit, not in brief | agents/nova.py:488 |

### Marketing: rules that make it safe

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| No post without valid permit number | 🟡 Partly | Number presence at run and gate; no expiry; gated off when setting is "no"; tests test_studio.py:58,481 | agents/studio.py:1142,1315 |
| Permit re-checked at publish | ❌ Missing | `publish`, `publish_due` check only `_missing` | agents/studio.py:1194,1233,1246 |
| Review passed before going live | 🟡 Partly | Room QA, not Review room | agents/qa.py:204 |
| Person's approval before going live | ✅ Built | Approver role enforced; test test_studio.py:349 | app.py:490,517 |
| Every price or claim from current Fact | 🟡 Partly | Amounts and claims checked at writing, against listing, not Facts | agents/qa.py:121,126; agents/studio.py:1144 |
| Superseded Fact pauses post | ❌ Missing | `_replace` never touches content | office.py:97-114 |
| No promises: returns, price rises | ✅ Built | Regex; test test_strategy.py:109 | agents/qa.py:21,124 |
| No promises: visas | ❌ Missing | Regex has no visa pattern | agents/qa.py:21 |
| Competitor content never copied | 🟡 Partly | Structure-only rule in charters; `too_close` compares our own scripts | agents/charters.py:204; agents/qa.py:148 |
| Music and footage licensed or own | ❌ Missing | Charter words only; no check | agents/charters.py:220 |
| Fictional people only in demos | 🟡 Partly | Seed is fictional; live data is not (see Bugs) | demo.py:11; ~/.diwan/diwan.db event 553 |

### Marketing PA's day

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Marketing PA exists | 🟡 Partly | Marketing lead chat, on request only; model required | agents/lead_chat.py:1,139 |
| Morning: posts to approve | 🟡 Partly | Open cards appear if `brief` is requested; nothing pushed; Marketing not in rounds | agents/nova.py:488,511 |
| Morning: listings without content | ❌ Missing | Not computed | no code hit |
| Morning: competitor posts worth a look | 🟡 Partly | Board and chat, not a list; refresh off by default | agents/rhythm.py:294; agents/lead_chat.py:80 |
| Morning: yesterday's leads by source | ❌ Missing | Lead chat refuses leads questions | agents/lead_chat.py:116 |
| Day: drafts on request | ✅ Built | run, revise, plan after a yes | agents/lead_chat.py:28,181 |
| End of day: tomorrow's schedule | ❌ Missing | No job | app.py:57-89 |
| End of day: anything paused, with reason | ❌ Missing | No paused state | n/a |
| Pauses posts on permit expiry or withdrawal | ❌ Missing | No code | n/a |

### Marketing definition of done

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Post's leads on right Cases with source | ❌ Missing | `media_id` discarded | app.py:541 |
| Price change pauses every post within minutes | ❌ Missing | Only a warning on an open script card; test test_studio.py:523 checks that warning | app.py:243; agents/studio.py:886 |
| Permit expiry pauses every post for that unit | ❌ Missing | No expiry field on a permit | no code hit |
| Records shows deals and commission per post | ❌ Missing | Ledger has no post link | agents/records.py:146 |

### Part 2 Marketing / Studio command 1-5 and Bugs

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| 1. Typo "Meet Diwan Realty" | 🟡 Partly | Code is clean; title is `Meet {name}` from brand name; live brand name is still "Diwan Realty" (also data/try.db) | agents/journey.py:31; ~/.diwan/diwan.db event 751 |
| 2. Permit default Yes | 🟡 Partly | Unset means yes in code; live office answered "no" (also data/try.db), so all permit gates are off | business.py:134-136; web/studio.html:317; ~/.diwan/diwan.db event 501 |
| 2. Permit required before approval | 🟡 Partly | Gate before the publish request; not at approve or publish | agents/studio.py:1458,1202 |
| 2. Rule confirmed with office | ❌ Missing | No record; no docs/open-questions.md | docs/ |
| 3. Fictional website in Setup | 🟡 Partly | No code default; live value `https://samplebrokerage-sc.com` (also data/try.db); data/diwan.db has none | business.py:25; ~/.diwan/diwan.db event 553 |
| 4. Script and post through Review | 🟡 Partly | Room-lead QA and permit gate do the job; no `review.requested`, Review room sees nothing | agents/qa.py:1-7; agents/review.py |
| 4. No bypass | 🟡 Partly | Own script with failures is still offered and server accepts picking it; post text can skip QA | agents/studio.py:1367-1371,1381,1539; app.py:495-506 |
| 5. Reel depends on listing Facts | 🟡 Partly | Snapshot compare, not `depends_on_facts` | agents/studio.py:872,886 |
| 5. Price or status change withdraws script | ❌ Missing | Warning only on unpicked options; `FACTS` drive the check; nothing withdrawn after approval | app.py:243; web/studio.html:583 |

### Event catalog

Totals across 78 names: 5 exact, 44 under another name, 29 absent.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| `message.received` | 🔁 Other name | `chat.received`; Rania called directly, event only folded plus custom trigger | agents/reception.py:1133; app.py:541; agents/custom.py:21 |
| `case.created` | 🔁 Other name | `deal.opened`; graph fold, custom trigger | office.py:27 |
| `case.intent_set` | 🔁 Other name | `qualify.type`; graph fold | graph.py:411 |
| `case.merged` | 🔁 Other name | `chat.merged`; graph fold | leads.py:244; graph.py:290 |
| `fact.recorded` | 🔁 Other name | `fact.created`; Compliance gets direct calls, not the event | office.py:82-94 |
| `fact.superseded` | 🟡 Partly | Exact name; order enforced by direct calls, no event handler | office.py:101-114 |
| `task.created` | 🟡 Partly | Exact name; fold, KPIs | office.py:135; desk_kpis.py:33 |
| `task.done` | 🟡 Partly | Exact name; fold, KPIs, rounds count | office.py:142; agents/nova.py:459 |
| `task.reopened` | ❌ Missing | Only `task.withdrawn` | events.py:20; office.py:108 |
| `call.requested` | 🔁 Other name | `attention.raised` kind=call; graph fold, sweep reads nodes | leads.py:142,172 |
| `viewing.booked` | 🔁 Other name | `appointment.booked`; fold, reminders read nodes | graph.py:338; agents/reminders.py:76 |
| `viewing.done` | 🔁 Other name | `appointment.done`; fold, follow-ups | graph.py:360; agents/nudge.py:140 |
| `viewing.no_show` | 🔁 Other name | `appointment.noshow`; fold only | graph.py:368 |
| `offer.made` | ❌ Missing | Stage "Offer" only | desk_rules.py:43 |
| `offer.countered` | ❌ Missing | None | none |
| `case.converted` | 🔁 Other name | `stage.changed` + `setting.changed agreed`; direct `on_convert` call | desk_stages.py:79-80,162-175 |
| `case.lost` | 🔁 Other name | `stage.changed` stage=Lost; KPI reads; direct `deal_property.lost` | desk_stages.py:74-76; desk_kpis.py:40 |
| `cobroke.agreed` | 🔁 Other name | Deal terms `setting.changed`; Finance reads settings | desk_rules.py:243; agents/finance.py:125 |
| `doc.requested` | 🔁 Other name | `docs.requested`; `documents.requests` reads | events.py:30; documents.py:258 |
| `doc.received` | 🔁 Other name | `docs.received`; same | events.py:30 |
| `doc.rejected` | 🔁 Other name | `docs.rejected`; same | events.py:30 |
| `form.ready` | 🔁 Other name | `draft.made`; Review called directly | office.py:171-172 |
| `form.sent` | 🔁 Other name | `sign.link`; `signing.links` reads | signing.py:94 |
| `form.signed` | 🔁 Other name | `sign.signed`; signing reads | signing.py:170 |
| `form.recalled` | 🔁 Other name | `review.returned` + `task.withdrawn` on change | agency_forms.py:122-130 |
| `compliance.cleared` | 🔁 Other name | `task.done` agent=screen result=clear; per person, no room-level clearance | agents/compliance.py:88 |
| `compliance.needs_info` | 🔁 Other name | `question.asked` kind=funding; fold | agents/compliance.py:202 |
| `compliance.blocked` | ❌ Missing | `check.raised` only flags, blocks nothing | agents/compliance.py:25 |
| `screening.hit` | 🔁 Other name | `task.done` result "possible match"; KPI reads; not officer-only (`task.` visible to whole deal team) | agents/compliance.py:88; access.py:66; desk_kpis.py:93 |
| `mortgage.preapproved` | ❌ Missing | Qualification answer only | qualify.py:84 |
| `mortgage.final_offer` | ❌ Missing | Generic step task | desk_rules.py:48 |
| `mortgage.refused` | ❌ Missing | None | none |
| `review.requested` | ❌ Missing | Review called directly | office.py:172 |
| `review.passed` | 🟡 Partly | Exact name, drafts only; emitted, UI display only | agents/review.py:79; web/deal.html |
| `review.sent_back` | 🔁 Other name | `review.returned`; fold, KPIs | agents/review.py:60; graph.py:246 |
| `approval.given` | 🟡 Partly | Exact name; guard reads node; no pinned Fact versions, ids only | office.py:147,158 |
| `approval.declined` | 🔁 Other name | `approval.refused`; fold | agents/review.py:44; graph.py:234 |
| `deal.ready_for_transfer` | ❌ Missing | Steps added on Form F submit, direct | agents/operations.py:102 |
| `noc.received` | 🔁 Other name | `task.done` on a step; closing reads | agents/operations.py:119; desk_rules.py |
| `transfer.booked` | 🔁 Other name | Same, step "Trustee office appointment booked" | desk_rules.py:52 |
| `transfer.completed` | 🔁 Other name | Same, step "Title deed issued" | desk_rules.py:53 |
| `ejari.ready` | 🔁 Other name | Same, rental step | desk_rules.py:78 |
| `listing.ready` | ❌ Missing | None | none |
| `listing.live` | 🔁 Other name | `listing.added` status available; Marketing does not react | graph.py:263; agents/rhythm.py:116 |
| `invoice.sent` | 🔁 Other name | `task.done` result=sent; direct next task | agents/finance.py:197 |
| `payment.marked_received` | 🔁 Other name | `task.done` result=received + receipt filed; KPIs | agents/finance.py:93-95; desk_kpis.py:89 |
| `payment.flagged` | ❌ Missing | No mismatch check | grep "mismatch" no hit |
| `cheque.due` | 🔁 Other name | Dated `pay` task; no due event, no reminder | agents/finance.py:68,265 |
| `cheque.bounced` | ❌ Missing | None | grep "bounc" no hit |
| `installment.due` | 🔁 Other name | Dated `pay` task; overdue computed on view | agents/finance.py:68; desk_kpis.py:106 |
| `renewal.due` | ❌ Missing | Dated task at closing, no event | agents/operations.py:278 |
| `form.expiring` | ❌ Missing | Only link expiry | signing.py:105 |
| `doc.expiring` | ❌ Missing | Rejected at upload if expired; no scan | documents.py:162-168 |
| `case.closed` | 🔁 Other name | `sale.closed` + stage Won; Records called directly | agents/operations.py:288-290; office.py:203 |
| `complaint.opened` | ❌ Missing | None | grep no hit |
| `experiment.approved` | ❌ Missing | None | none |
| `experiment.ended` | ❌ Missing | None | none |
| `unit.held` | 🔁 Other name | `listing.added` status=reserved; no developer or expiry | deal_property.py:192 |
| `listing.signed` | ❌ Missing | Form A only on conversion | agency_forms.py:87 |
| `valuation.sent` | ❌ Missing | None | none |
| `seller.report` | ❌ Missing | None | none |
| `oqood.received` | 🔁 Other name | `task.done` on step | desk_rules.py:64 |
| `funds.ready` | 🔁 Other name | `task.done` on "Manager's cheques" step | desk_rules.py:51 |
| `referral.asked` | ❌ Missing | None | none |
| `content.idea` | 🔁 Other name | `content.made` kind=ideas; screens only | agents/studio.py:189,626 |
| `content.briefed` | ❌ Missing | No stage | none |
| `content.scripted` | 🔁 Other name | `content.made` kind=script; `rhythm.used` | agents/rhythm.py:80 |
| `content.ready` | 🔁 Other name | Publish request; approval card | agents/studio.py:1190 |
| `post.approved` | 🔁 Other name | `decision.made` + `content.made` scheduled; `publish_due` | app.py:508; agents/studio.py:1210,1233 |
| `post.live` | 🔁 Other name | `content.made` kind=published; strategy reads | agents/studio.py:1263; agents/strategy.py:54 |
| `post.paused` | ❌ Missing | None | none |
| `post.withdrawn` | 🔁 Other name | `content.made` unscheduled, pre-post only | agents/studio.py:1228 |
| `campaign.started` | ❌ Missing | None | none |
| `campaign.ended` | ❌ Missing | None | none |
| `lead.attributed` | ❌ Missing | None | none |
| `permit.expired` | ❌ Missing | None | none |
| `listing.withdrawn` | 🔁 Other name | Status change via `listing.added` or `item.retired`; studio does not react | graph.py:263 |
| `listing.unconfirmed` | ❌ Missing | No availability check | none |

### Event rule and HQ Stuck board

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Only catalog names used | ❌ Missing | `TYPES` is a whitelist of mostly other names | events.py:11-43 |
| Every event carries case_id, actor, at | 🟡 Partly | Columns exist; `deal` often null | events.py:56-59 |
| Every event carries fact_ids with versions | ❌ Missing | No such column | events.py:56-59 |
| Subscriber registry | ❌ Missing | Only custom agents' 10 triggers | agents/custom.py:20-31,85 |
| Every event has a consumer in code | ❌ Missing | Cannot be proven; most are graph folds | graph.py:188 |
| Stuck: events with no consumer | ❌ Missing | None | grep |
| Stuck: overdue Tasks | ❌ Missing | Tasks have no general due field | office.py:136 |
| Stuck: agent Task not started in 5 min | ❌ Missing | None | none |
| HQ Stuck board | ❌ Missing | Deal desk KPI tile of idle deals only, no-step 7 days | web/deal.html:337; desk_kpis.py:64 |
| Stuck in the brief | ❌ Missing | Not in brief | agents/nova.py:506 |
| Department with no input shows Stuck | ❌ Missing | Nearest: flow map marks unseen links on Memory screen | agents/custom.py:219-258 |

### Missing from the floor, and "Every room" bugs (web/office3d.html)

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Stats filtered by room | 🟡 Partly | HQ signs filter agents, tasks, waiting; floor HUD is global on every floor; no Facts filter | web/office3d.html:632-636,647-651 |
| Left wall = Facts this room's Tasks depend on | 🟡 Partly | Comp and Fin show money kinds only; others all live facts | web/office3d.html:587 |
| Right wall = room's Tasks only | 🟡 Partly | Filtered only on comp, fin, ops, review; Sales, Records, Front show office-wide | web/office3d.html:584,589-590 |
| Demo button: one on HQ or each room's part | 🟡 Partly | Removed from Marketing only; still on all other floors | web/office3d.html:831 |
| Playwright: room stats differ | ❌ Missing | No assertion | e2e/floor_flow.py; e2e/office_flow.py |
| Deal room | ❌ Missing | Not in `DEPTS`; page web/deal.html | web/office3d.html:129-139 |
| Lobby room | ❌ Missing | Orb and tab in Front Desk | web/office3d.html:130,919 |
| Sales lead PA | ❌ Missing | `sales` charter is about meetings; no PA | agents/charters.py:45 |
| Call-now queue in Sales room | 🟡 Partly | Inbox "Needs you" and Attention cards do it; not on the floor | web/inbox.html:249; leads.py:172 |
| Finance: Mark received | 🟡 Partly | Built, on Deal desk only | agents/finance.py:80; deal_desk.py:484 |
| Finance: invoice drafting | 🟡 Partly | Same; Invoice clerk charter still says supplier invoices | deal_desk.py:601; agents/charters.py:103 |
| Finance: commission split | 🟡 Partly | Other-agency share only; no broker splits or payout list | agents/finance.py:212; deal_desk.py:697 |
| Stuck board on HQ | ❌ Missing | None | see above |

### Each department's lifecycle: scheduled jobs

Only one scheduler exists, `app.morning_loop`, on a 60-second tick, plus `custom_loop`. Sweeps active: lobby chase, documents, leads, nudge, reminders, studio auto, publish, competitor refresh, listing feed.

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Front Desk daily: 07:30 brief | 🟡 Partly | Rounds at 08:30 by default (09:00 less 30), per-person setting; not pushed, not `morning()` | app.py:66-68; agents/nova.py:558 |
| Front Desk daily: end-of-day wrap | ❌ Missing | No job | app.py:57-89 |
| Front Desk weekly: Monday numbers | ❌ Missing | No job | same |
| Front Desk monthly: owner review | ❌ Missing | No job | same |
| Marketing daily: approvals | 🟡 Partly | Approval on request; no daily list | app.py:479 |
| Marketing daily: posting | ✅ Built | `publish_due` every minute | app.py:79 |
| Marketing daily: pause expired or old price | ❌ Missing | No job | n/a |
| Marketing weekly: leads and deals per post | ❌ Missing | No job | n/a |
| Marketing monthly: campaign results, spend vs cap | ❌ Missing | No job | n/a |
| Marketing monthly: next month's content plan | 🟡 Partly | Weekly plan at most | agents/rhythm.py:199 |
| Sales daily: call-now queue | ✅ Built | Card overdue and Pool sweep | leads.py:172; app.py:73 |
| Sales daily: broker sweep 08:30 | 🟡 Partly | Appointments only, an hour before shift, not missing outcomes | agents/reminders.py:109-126 |
| Sales daily: follow-ups | ✅ Built | Test tests/test_nudge.py | agents/nudge.py:264; app.py:74 |
| Sales daily: listing availability checks | ❌ Missing | Feed sync only | leads.py:340 |
| Sales weekly: quiet clients | 🟡 Partly | Continuous nudges, no weekly list | agents/nudge.py:264 |
| Sales weekly: listing-to-buyer matches | 🟡 Partly | Only inside a nudge | agents/nudge.py:229-235 |
| Sales weekly: seller reports | ❌ Missing | No job | n/a |
| Sales monthly: renewals in 90 days | ❌ Missing | No scan | n/a |
| Deal daily: missing items | 🟡 Partly | Desk view, not scheduled | deal_desk.py:237 |
| Deal daily: follow-up ladder | ✅ Built | Reminders then broker task; hours constant | documents.py:254 |
| Deal weekly: stuck by days in stage | 🟡 Partly | On-demand KPI | desk_kpis.py:64 |
| Deal monthly: Form A and document expiries | ❌ Missing | No job | n/a |
| Compliance daily: hits and holds | 🟡 Partly | Open cards on desk and brief; not scheduled | agents/nova.py:511 |
| Compliance weekly: re-screen | ❌ Missing | `catch_up` runs at boot, adds missing only | app.py:50; agents/compliance.py:207 |
| Compliance monthly: reports, thresholds, retention | ❌ Missing | No job | n/a |
| Finance daily: due, overdue, mark received | 🟡 Partly | On view only | deal_desk.py:147 |
| Finance weekly: chasing list | ❌ Missing | No job | n/a |
| Finance monthly: close, payouts, VAT | ❌ Missing | No job | n/a |
| Ops daily: today's appointments | ❌ Missing | Steps have no date | agents/operations.py:105 |
| Ops daily: drafts to submit | 🟡 Partly | On desk view | deal_desk.py |
| Ops weekly: waiting-on-outsiders aging | 🟡 Partly | Touchpoint medians only | desk_kpis.py:77 |
| Ops monthly: permit renewals | ❌ Missing | No job | n/a |
| Review daily: queue under time limit | ❌ Missing | No queue or limit | n/a |
| Review weekly: send-back patterns | ❌ Missing | No job | n/a |
| Records daily: expiry and renewal scan | ❌ Missing | No job | n/a |
| Records Monday report | ❌ Missing | No job | n/a |
| Records monthly numbers | ❌ Missing | No job | n/a |
| Records yearly clean-up | ❌ Missing | No job | n/a |
| Lobby daily idea | ❌ Missing | No job | n/a |
| Lobby weekly threads | ❌ Missing | No job | n/a |
| Lobby monthly kept and rolled back | ❌ Missing | No job | n/a |

### Later

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Meeting agent joins Zoom, Meet, Teams | ❌ Missing | Zoom provider only creates and moves meetings | providers/zoom.py:1-10 |
| Named participant, announces itself | ❌ Missing | Nothing | same |
| Consent at start | ✅ Built | In-person meeting flow; utterance refused without it | office.py:58,64 |
| Statements become Facts via Scribe pipeline | 🟡 Partly | In-person and browser audio only | agents/scribe.py:162-168 |
| Summary after the call | 🟡 Partly | Visit summary from a meeting | agents/visit.py:95 |
| Action items as Tasks | 🟡 Partly | Follow-up and rules-driven tasks only | agents/followup.py |
| Follow-up draft for the broker | ✅ Built | Test tests/test_followup.py | agents/followup.py |
| Quiet side-chat answers | ❌ Missing | Nothing | none |
| 3D client showroom | ❌ Missing | No scene, page or permissions; spec copies only | web/ listing |
| Showroom statements become Facts | ❌ Missing | Nothing | none |
| Shared 3D engine, separate data | ❌ Missing | Engine is inline in web/office3d.html | web/office3d.html |
| One Facts pipeline | 🟡 Partly | `scribe.hear` used for chat and portal; Rania and Sales also write qualify answers | leads.py:422,448 |
| Meeting writes only through Events | ✅ Built | Event log is the only store | office.py:55-74 |

### No-guess rules

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| docs/open-questions.md exists | ❌ Missing | File not on disk | docs/ listing |
| Numbers are settings: strongest areas | 🟡 Partly | Good: `desk_rules`, `nudge.QUIET`, `rhythm`, `REMIND` | desk_rules.py:26-29; agents/nudge.py:19; agents/rhythm.py:22 |
| Offender: strategy thresholds | ❌ Missing | WIN, FADE, RETIRE 1.2/1.0/0.8, REST_DAYS 30 | agents/strategy.py:32-33 |
| Offender: journey | ❌ Missing | INTRO 9, GROW 30, SILENT_DAYS 45, NEW_PROJECT_DAYS 14 | agents/journey.py:24-26 |
| Offender: QA rules | ❌ Missing | BANNED words, MAX_TRIES 3, waking hours 8-23, hook 12 words | agents/qa.py:21-22,118,184 |
| Offender: reader and eventpost | ❌ Missing | MIN_WINS, GAP, photo limits, REELS_WIN | agents/reader.py:19-20; agents/eventpost.py:25-26 |
| Offender: posting defaults | ❌ Missing | Hour 19, min 5 posts | agents/studio.py:1158,1166 |
| Offender: doc reminder hours | ❌ Missing | 9 to 20 hard-coded | documents.py:256 |
| Offender: Friday prayer, 24h window | ❌ Missing | Constants | agents/nudge.py:22-23 |
| Offender: rounds lead, default brief | ❌ Missing | 30 min, 09:00 | app.py:67; agents/nova.py:558 |
| Offender: people hard-coded | ❌ Missing | "omar", "layla", staff list in logic | agents/finance.py:31; leads.py:191; agents/nova.py:528 |
| Offender: env not Settings | 🟡 Partly | Call, reply, Pool minutes from env | leads.py:31-36 |
| Marketing KPI targets | ❌ Missing | Constants | agents/kpis.py:19-44 |
| No room calls another room | ❌ Missing | See the next six rows | below |
| Example: Sales fact into Compliance, Finance | ❌ Missing | `record_fact` calls both | office.py:91-94 |
| Example: correction chain | ❌ Missing | Compliance, Review, Ops called directly | office.py:101,111,113-114 |
| Example: private call across rooms | ❌ Missing | `reception._send`; `compliance._same` | agents/nudge.py:299; agents/reminders.py:101; documents.py:198,282 |
| Example: Ops into Records and Finance | ❌ Missing | `close_sale`, `finance.commission` | agents/operations.py:275-288 |
| Example: stage into forms | ❌ Missing | `agency_forms.on_convert` | desk_stages.py:80 |
| Example: Nova into Ops | ❌ Missing | `HANDLERS` | agents/nova.py:441 |

### Definition of done for each room

| Requirement | Status | Detail | Evidence |
|---|---|---|---|
| Room shows only its own stats, Tasks, Facts, Stuck | 🟡 Partly | Comp, Fin, Ops, Review walls partly; none has Stuck; HUD global | web/office3d.html:584,632-636 |
| Consumed events have handlers, emitted have consumers | ❌ Missing | No catalog or registry | events.py:11 |
| Agent Task starts in 5 min or shows why | ❌ Missing | Only `formf` on route; `route` says "will pick it up"; card shows idle | agents/nova.py:425-429,441; web/office3d.html:620-624 |
| PA answers "what's waiting on me?" per role | 🟡 Partly | `nova.brief` per person but staff cannot call `/api/nova`; no per-staff PA; scope hard-coded | agents/nova.py:506,528; access.py:53-63 |
| Every way out has a test | 🟡 Partly | Strong on correction, closing, nudges; no scenario map; catalog scenarios absent | tests/; e2e/ |
| Correction reopens only that room's work | 🟡 Partly | Withdraws dependent tasks, compliance first, approval refused; not "reopen"; Marketing outside it; tests test_deal_desk.py:29 | office.py:97-114 |

### The 5 biggest gaps

1. No event spine: 5 of 78 catalog names exist. There is no subscriber registry, rooms hand off by direct function calls, and a failed handoff is invisible.
2. No Stuck board and no Task pick-up: agent Tasks do not auto-start, Tasks have no general due field, and nothing shows work with no taker.
3. Marketing's loop is open: `media_id` is thrown away, and there are no tracked links, no DMs, no `lead.attributed`, no per-post deals or commission, and no campaigns.
4. Live posts have no safety life: no paused, withdrawn or archived state. A price change, permit expiry or sold listing touches nothing, and publish does not re-check the permit. Live settings make this worse: `permit=no`, a real brokerage website, and the typo in the brand name.
5. Records and Lobby are not rooms yet: no dashboard, funnel, speed numbers, Monday report or scans; the Lobby is a job board with no experiments. Nearly every weekly and monthly job in the table does not exist.
