# Diwan: closed-loop checklist, line by line

The detail behind [closed-loop-checklist.md](closed-loop-checklist.md). Use that file as the working checklist: it has the
faults to fix first, the decisions and the suggested order. This one is the reference. It takes every requirement of
[the spec](closed-loop-spec.md) separately, says what is there and what is needed, and cites the file and line for each.
Written 31 Oct 2026 from the working tree, including uncommitted work.

**How to read a line**

- ✅ built, and a browser check covers it
- 🧪 built, but pytest only or no test (the line says which)
- 🟡 partly there: the line says what exists and what is missing
- ❌ not there: the line says what to build
- ❓ needs the office's answer

`(L123)` is the line in `closed-loop-spec.md`.

**How far to trust it.** Six reviewers read the spec against the code section by section, and every file and line cited
here was checked to exist. They did not run the tests or the browser checks, so ✅ means a check exists, not that it passes
today. For example, [e2e/studio_flow.py](../e2e/studio_flow.py) is out of date after its upload step. About a dozen of the
most serious findings were confirmed by opening the code; the rest were not rechecked one by one. Line numbers will drift
as other sessions change the code.

## Where things stand

| Part | ✅ | 🧪 | 🟡 | ❌ | ❓ | Lines |
|---|---|---|---|---|---|---|
| [A. The spine, rules, stages, events and rhythm](#part-a) | 42 | 10 | 164 | 122 | 2 | 340 |
| [B. Front Desk, PAs and access](#part-b) | 47 | 68 | 141 | 218 | 3 | 477 |
| [C. Sales](#part-c) | 41 | 17 | 66 | 100 | 7 | 231 |
| [D. Deal and Operations](#part-d) | 49 | 6 | 145 | 201 | 5 | 406 |
| [E. Finance, Compliance, Review, Records, Lobby](#part-e) | 42 | 15 | 115 | 176 | 3 | 351 |
| [F. Marketing](#part-f) | 4 | 27 | 43 | 70 | 6 | 150 |
| **Total** | **225** | **143** | **674** | **887** | **26** | **1955** |

The spec says many things more than once (a room's section, its command, its PA, a day in the job), so these count
checklist lines, not separate features, and they run higher than the working checklist's totals, which merge repeats.
Read them as a sense of size.

## Contents

- [Part A: The spine, rules, stages, events and rhythm](#part-a)
- [Part B: Front Desk, PAs and access](#part-b)
- [Part C: Sales](#part-c)
- [Part D: Deal and Operations](#part-d)
- [Part E: Finance, Compliance, Review, Records, Lobby](#part-e)
- [Part F: Marketing](#part-f)
- [All conflicts found](#all-conflicts-found)

<a id="part-a"></a>

## Part A: The spine, rules, stages, events and rhythm

"Case" below means the deal node in the graph. Line numbers are from the working tree on 2026-10-31.

### The spine objects (L9-19)

- [ ] 🟡 **One Person record per human** (L13). There: a person node with only a name and a role, keyed by name; staff are a fixed list. Needed: a Person record shared across Cases, keyed by a stable id, not a name. [graph.py:72](../diwan/graph.py#L72), [people.py:4](../diwan/people.py#L4), test: [test_nova.py](../tests/test_nova.py)
- [ ] 🟡 **Person holds phone, email, WhatsApp** (L13). There: the phone lives on the chat node; email is not kept. Needed: phone, email and WhatsApp fields on Person. [graph.py:272](../diwan/graph.py#L272)
- [ ] ❌ **Person holds language and consent** (L13). Needed: language and consent fields on Person. Arabic is guessed per message; meeting consent exists only per meeting. [nudge.py:282](../diwan/agents/nudge.py#L282)
- [ ] 🟡 **Person holds the "stop" flag** (L13). There: `lead.optout` is kept on the deal, so a second lead for the same human is not stopped. Needed: the flag on Person. [graph.py:436](../diwan/graph.py#L436), test: [test_sales_journey.py](../tests/test_sales_journey.py)
- [ ] 🟡 **Landlord, developer contact and other parties as Persons** (L13). There: the seller is the text "the seller" and other parties are names on facts. Needed: Person records with a party role on the Case. [documents.py:51](../diwan/documents.py#L51)
- [x] ✅ **Case runs first message to keys on one record** (L14). There: a lead is a deal node with a `lead-` id and keeps that id through conversion. [reception.py:503](../diwan/agents/reception.py#L503), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py)
- [ ] 🟡 **One Case per client intent** (L14). There: one chat holds one deal for ever, and an existing chat always returns its deal. Needed: a second intent from the same client opens a second Case, linked to the first. [reception.py:497](../diwan/agents/reception.py#L497)
- [x] ✅ **Case has a single `stage` field** (L14). There: `stage` on the deal, set only by `stage.changed`. [graph.py:296](../diwan/graph.py#L296), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [ ] ❌ **Case has a single owner room** (L14). Needed: an `owner_room` value per stage on the deal, shown on screen. Nothing in the code holds it.
- [ ] ❌ **Only the owner room advances `stage`** (L14). Needed: a check against `owner_room`. Today any of broker, transactions officer or owner moves any stage, and Rania moves early stages. [desk_stages.py:28](../diwan/desk_stages.py#L28), [inbox.py:277](../diwan/inbox.py#L277)
- [x] ✅ **Fact holds the exact quote** (L15). There: `fact.created` keeps quote, speaker and kind; an invented quote is dropped. [office.py:82](../diwan/office.py#L82), test: [test_scribe.py](../tests/test_scribe.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Fact holds its source (chat, call, meeting)** (L15). There: only traceable through `caused_by` to the chat or utterance event. Needed: a `source` field on every Fact. [office.py:82](../diwan/office.py#L82)
- [x] ✅ **Fact holds timestamp and its Case** (L15). There: event `at` and `deal`. [events.py:80](../diwan/events.py#L80), test: [test_scribe.py](../tests/test_scribe.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Facts are never edited, only superseded** (L15). There: append-only log; `fact.superseded` links old to new. [graph.py:210](../diwan/graph.py#L210), test: [test_infra.py](../tests/test_infra.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Everything the client says is a Fact** (L15). There: chat goes through the Scribe, but qualification answers are `qualify.answer` on the deal, with a quote but no Fact, so correcting one reopens nothing. Needed: qualification answers recorded as Facts. [reception.py:1136](../diwan/agents/reception.py#L1136), [graph.py:413](../diwan/graph.py#L413)
- [ ] 🟡 **Task has an owner room** (L16). There: `team` (the agent's parent) is stored; a Task is shown by agent. Needed: an explicit `owner_room` that all screens read. [office.py:135](../diwan/office.py#L135)
- [x] ✅ **Task has an assignee, agent or person** (L16). There: `agent` plus `needs_person`. [office.py:131](../diwan/office.py#L131), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Task has a due date** (L16). There: `due` only on scheduled payments and after-close work. Needed: `due_at` on every Task. [finance.py:68](../diwan/agents/finance.py#L68), [operations.py:279](../diwan/agents/operations.py#L279)
- [x] ✅ **Task lists the Facts it depends on** (L16). There: `rests_on`, drawn as graph edges; `impact()` finds them. [graph.py:105](../diwan/graph.py#L105), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Task has a status** (L16). There: queued, done, withdrawn. [graph.py:224](../diwan/graph.py#L224), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Document record shared by all rooms** (L17). There: two shapes, `docs.received` for uploads and `document.filed` for the archive. Needed: one Document record (see the upload list below). [documents.py:207](../diwan/documents.py#L207), [office.py:198](../diwan/office.py#L198)
- [ ] 🟡 **Approval is a person's yes on one version of a Task's output** (L18). There: `approval.given` holds words, approver and `rests_on`, with no link to a Task or draft version. Needed: `task_id` and output version on the Approval. [office.py:145](../diwan/office.py#L145)
- [x] ✅ **Approval is pinned to the Facts it rests on** (L18). There: `rests_on` Fact ids; a Fact id never changes, so the id is the version. [office.py:147](../diwan/office.py#L147), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Approvals go through Review, then a human** (L18). There: only drafts are checked by Review; an approval goes straight to the person. Needed: a Review step before every approval. [review.py:67](../diwan/agents/review.py#L67)
- [x] ✅ **Event is an append-only line: who, what, which Case** (L19). There: database triggers refuse update and delete. [events.py:61](../diwan/events.py#L61), test: [test_infra.py](../tests/test_infra.py), browser: all flows read it
- [ ] ❌ **Every Event names its Facts** (L19). Needed: a `fact_ids` field on every event; today only some events carry `refs` or `rests_on`.
- [ ] ❌ **Every room subscribes to Events** (L19). Needed: a subscriber registry. Today the graph is a read model and only the owner's custom agents listen for events, and only for 10 kinds. [custom.py:20](../diwan/agents/custom.py#L20)

### The three rules (L21-25)

- [ ] ❌ **A room never calls another room** (L23). Needed: rooms react to Events. Today recording a fact calls Compliance and Finance directly, and at least seven other direct calls exist. [office.py:91](../diwan/office.py#L91), [desk_stages.py:80](../diwan/desk_stages.py#L80), [documents.py:284](../diwan/documents.py#L284), [signing.py:187](../diwan/signing.py#L187)
- [ ] ❌ **An Event with no subscriber shows as stuck** (L23). Needed: the registry above and a Stuck view.
- [ ] 🟡 **A Case moves only when its exit checklist is complete** (L24). There: a closing checklist blocks Won, and an agreed price blocks conversion; no other stage has a checklist. Needed: a checklist per stage, enforced in the move. [operations.py:255](../diwan/agents/operations.py#L255), [desk_stages.py:67](../diwan/desk_stages.py#L67), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] ❌ **Review checks the checklist before a move** (L24). Needed: `review.requested` on each stage move.
- [ ] 🟡 **A human approves the move** (L24). There: a person moves paperwork stages; Rania moves New to Viewing booked alone. Needed: decide with the office whether early stages count. [inbox.py:252](../diwan/inbox.py#L252)
- [ ] 🟡 **A superseded Fact reopens its Tasks** (L25). There: dependent Tasks are withdrawn; payment, Form F and agency forms are remade by rules; others are not. Needed: `task.reopened`, or an answer on the Conflict below. [office.py:108](../diwan/office.py#L108), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Unrelated work stays done** (L25). There: `impact()` touches only what rests on the old Fact. [graph.py:105](../diwan/graph.py#L105), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **A superseded Fact sends its approvals back to the approver** (L25). There: a decision card to the approver. [review.py:14](../diwan/agents/review.py#L14), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Compliance is told first** (L25). There: `check.raised` comes before `fact.superseded`, but only for money facts; a corrected price or name does not reach Compliance. Needed: every supersede, or a decision on the Conflict below. [office.py:101](../diwan/office.py#L101), [compliance.py:22](../diwan/agents/compliance.py#L22), test: [test_nova.py](../tests/test_nova.py)
- [x] ✅ **An old approval cannot run** (L25). There: `execute` refuses and logs `approval.refused`. [office.py:158](../diwan/office.py#L158), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Nothing downstream may be approved until re-done** (L25). There: the guard works at execute only; `approve()` accepts a superseded Fact id. Needed: the same check inside `approve()`. [office.py:145](../diwan/office.py#L145), [app.py:867](../diwan/app.py#L867)

### Where it most likely breaks now (L27-32)

- [x] ✅ **A converted lead carries its Facts** (L29). There: one table and one id, so nothing has to be carried. [desk_stages.py:162](../diwan/desk_stages.py#L162), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py)
- [ ] 🟡 **Nothing still treats a converted lead as a lead** (L29). There: the pipeline answer splits on the `lead-` prefix, so a converted lead is counted as a WhatsApp lead with no value. Needed: split on stage, not id. [records.py:68](../diwan/agents/records.py#L68), [nova.py:99](../diwan/agents/nova.py#L99), [inbox.py:99](../diwan/inbox.py#L99)
- [ ] ❌ **A failed room call cannot drop a handoff** (L30). Needed: event delivery with retries. In `record_fact`, an error in one room skips the rooms after it, with the Fact already written. [office.py:91](../diwan/office.py#L91)
- [x] ✅ **Tasks know their Facts, so a correction can find them** (L31). There: `rests_on`. [office.py:135](../diwan/office.py#L135), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Reminders run from one place** (L32). There: one loop calls five separate sweeps, each with its own rules. Needed: one reminder service. [app.py:70](../diwan/app.py#L70)
- [ ] ❌ **Reminders can't silently stop** (L32). Needed: a guard around each sweep. `morning_loop` has no try/except, so one error ends every sweep until a restart, with nothing logged; `custom_loop` has the guard. [app.py:63](../diwan/app.py#L63), [app.py:98](../diwan/app.py#L98)
- [ ] 🟡 **Nothing fires twice** (L32). There: sweeps use keys, but the last-brief day is kept in memory, so a restart after the hour runs the rounds again. Needed: read the last brief from the log. [app.py:105](../diwan/app.py#L105)

### Notifications (L301-309)

- [ ] 🟡 **One notification service** (L301). There: `leads.notify`, used by Sales and the calendar only; Compliance, Finance, Operations and Review never call it. Needed: every room's alerts through it. [leads.py:474](../diwan/leads.py#L474), test: [test_leads.py](../tests/test_leads.py)
- [ ] ❌ **Three levels: Now, Today, Brief** (L303). Needed: a level on each notice; today `kind` is lead, call, overdue, pool or info.
- [ ] 🟡 **Now reaches the person by Push and WhatsApp** (L305). There: screen always, WhatsApp when a staff number and template are set; no push. Needed: push. [leads.py:481](../diwan/leads.py#L481), test: [test_leads.py](../tests/test_leads.py)
- [ ] ❌ **Now repeats once after 10 minutes** (L305). Needed: a repeat in the service.
- [ ] 🟡 **Now then escalates** (L305). There: an overdue Attention card tells the owner, hard-coded to Layla. Needed: the escalation chain, for every Now item. [leads.py:191](../diwan/leads.py#L191), test: [test_leads.py](../tests/test_leads.py)
- [ ] 🟡 **A client's call request is Now** (L305). There: Attention card and notice at once. Needed: the Now behaviour above. [leads.py:146](../diwan/leads.py#L146), test: [test_leads.py](../tests/test_leads.py), browser: [call_flow.py](../e2e/call_flow.py)
- [ ] ❌ **A Compliance hit is Now** (L305). Needed: a notice to the officer; today a check card and a task wait on the Deal desk. [compliance.py:25](../diwan/agents/compliance.py#L25)
- [ ] ❌ **A payment mismatch is Now** (L305). Needed: a mismatch check and notice; `mark_received` compares nothing. [finance.py:80](../diwan/agents/finance.py#L80)
- [ ] ❌ **Today items collected into a midday summary** (L306). Needed: a midday job. Nothing runs at midday.
- [ ] 🟡 **Brief items only in the morning brief** (L307). There: the brief lists what needs a person and each department's round. Needed: stuck deals, ideas and reports in it. [nova.py:506](../diwan/agents/nova.py#L506), test: [test_frontdesk.py](../tests/test_frontdesk.py)
- [ ] 🟡 **Quiet hours and prayer apply to client messages always** (L309). There: follow-ups and reminders respect them; document reminders use a fixed 09:00-20:00 and ignore prayer; Rania replies at any hour. Needed: one check for all. [nudge.py:73](../diwan/agents/nudge.py#L73), [documents.py:256](../diwan/documents.py#L256), test: [test_nudge.py](../tests/test_nudge.py)
- [ ] ❌ **Quiet hours apply to staff unless Now** (L309). Needed: the check in `notify`, which sends at any hour. Per-person do-not-disturb is also missing. [leads.py:474](../diwan/leads.py#L474)

### Who may do what (L311-316)

- [x] 🧪 **Agents may only read, draft, check, fill and remind** (L313). There: every action passes the charter; anything else is refused and logged. [runner.py:140](../diwan/agents/runner.py#L140), test: [test_infra.py](../tests/test_infra.py) (no browser check)
- [ ] 🟡 **Agents message clients only inside 24 hours or by template** (L313). There: Inbox, follow-ups, reminders and calendar notices all check; document reminders do not. Needed: the check inside `_send`. [reception.py:612](../diwan/agents/reception.py#L612), [documents.py:284](../diwan/documents.py#L284), test: [test_nudge.py](../tests/test_nudge.py)
- [x] ✅ **Only a person approves** (L314). There: an approval names a person; only that person can carry it out. [deal_desk.py:411](../diwan/deal_desk.py#L411), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Only a person submits to a portal** (L314). There: the officer records the portal reference; no agent can. [operations.py:81](../diwan/agents/operations.py#L81), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] 🧪 **Only a person pays** (L314). There: no code pays; `inv` and `pay` charters refuse it. [charters.py:106](../diwan/agents/charters.py#L106), test: [test_infra.py](../tests/test_infra.py) (no browser check)
- [x] ✅ **Only a person signs** (L314). There: signing links are for people; a form completes only on their signatures. [signing.py:150](../diwan/signing.py#L150), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Only a person marks money received** (L314). There: finance role plus a reference. [finance.py:80](../diwan/agents/finance.py#L80), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Only a person files a regulatory report** (L314). There: the officer gives the goAML reference. [compliance.py:92](../diwan/agents/compliance.py#L92), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Only a person clears a screening hit** (L314). There: only the compliance role records a result. [compliance.py:77](../diwan/agents/compliance.py#L77), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] 🧪 **Agents never hold portal, bank or email passwords** (L315). There: no such setting exists, and the charter forbids it; only API keys for WhatsApp, Instagram and models are held. [charters.py:87](../diwan/agents/charters.py#L87) (no test)
- [ ] ❌ **Portal sign-in happens in the person's own browser session** (L315). Needed: the portal fill itself; Form F today is a field plan, with no browser step. [operations.py:64](../diwan/agents/operations.py#L64)
- [x] 🧪 **Each person sees only their department** (L316). There: one sign-in gate over pages, API, sockets and files; events are filtered. [access.py:328](../diwan/access.py#L328), test: [test_access.py](../tests/test_access.py) (browser flows run with auth off)
- [ ] 🟡 **A broker sees only their Cases** (L316). There: filtered on the calendar and in an Inbox "mine" view, but any broker can open every lead and deal. Needed: a per-broker filter on the data. [access.py:58](../diwan/access.py#L58), [deal_desk.py:308](../diwan/deal_desk.py#L308)
- [ ] 🟡 **Finance sees money only** (L316). There: Finance, Compliance and Operations share the whole Deal desk, compliance cards included. Needed: per-section filtering in the deal view. [access.py:40](../diwan/access.py#L40), [deal_desk.py:345](../diwan/deal_desk.py#L345)
- [x] 🧪 **The owner sees all** (L316). There: the gate lets the owner through. [access.py:353](../diwan/access.py#L353), test: [test_access.py](../tests/test_access.py) (browser flows run with auth off)

### When something fails (L318-323)

- [ ] ❌ **A failed model call retries once** (L320). Needed: one retry in `runner.call`. It goes straight to the fallback. [runner.py:110](../diwan/agents/runner.py#L110)
- [x] 🧪 **Then falls back to rules** (L320). There: Rania, the Scribe, Nova and the visit summary all do, and log `agent.failed`. Marketing agents fail loudly instead. [reception.py:1336](../diwan/agents/reception.py#L1336), [scribe.py:181](../diwan/agents/scribe.py#L181), test: [test_infra.py](../tests/test_infra.py) (no browser check)
- [ ] 🟡 **The output is marked as fallback** (L320). There: `by: "rules"` in the turn's result, not on the message the client got or on the stored output. Needed: a fallback mark on the logged output. [reception.py:1331](../diwan/agents/reception.py#L1331)
- [ ] ❌ **An Event with no subscriber shows on a Stuck board** (L321). Needed: the registry and the board.
- [ ] ❌ **An overdue Task shows on a Stuck board** (L321). Needed: a due date on Tasks and the board. Only Attention cards, Lobby cards and payments go overdue.
- [ ] ❌ **Both show in the brief** (L321). Needed: a Stuck section in `nova.brief`. [nova.py:506](../diwan/agents/nova.py#L506)
- [ ] 🟡 **An undeliverable message becomes a Task for the broker to call** (L322). There: moved or cancelled appointments and missing document links do this. A failed send only shows as failed in the Inbox; a skipped follow-up or reminder is only logged. Needed: a Task in each of these. [reception.py:559](../diwan/agents/reception.py#L559), [nudge.py:288](../diwan/agents/nudge.py#L288), [reminders.py:94](../diwan/agents/reminders.py#L94)
- [ ] ❌ **Each turn logs the charter version** (L323). Needed: a version on charters and in `agent.started`. [runner.py:165](../diwan/agents/runner.py#L165)
- [ ] 🟡 **Each turn logs inputs, Facts used and outcome** (L323). There: `agent.started` keeps source ids, `agent.pack` the outcome, tapes the exact text; chat replies are not packs. Needed: the same record for all turns. [runner.py:149](../diwan/agents/runner.py#L149), test: [test_infra.py](../tests/test_infra.py)
- [ ] 🟡 **Any output can be replayed** (L323). There: model tapes replay by exact prompt and the graph rewinds to any event. Needed: replay from a logged turn. [runner.py:96](../diwan/agents/runner.py#L96), test: [test_nova.py](../tests/test_nova.py)

### Build order (L327-337)

- [ ] 🟡 **Step 1, Spine** (L329). There: Facts with supersede, Tasks with `rests_on`, pinned Approvals, an Event log. Needed: Case fields, subscribers, Stuck board.
- [ ] 🟡 **Step 2, Sales exit** (L330). There: Convert and a broker's action on each card. Needed: `case.converted`. [desk_stages.py:105](../diwan/desk_stages.py#L105)
- [ ] 🟡 **Step 3, Deal** (L331). There: path steps, document links with checks, reminders. Needed: templates per deal and party type, WhatsApp receipts, the 24/48/72 ladder. [documents.py:174](../diwan/documents.py#L174)
- [ ] ❌ **Step 4, Compliance gate** (L332). Needed: a clearance event and a block on the transfer. Form F can be submitted with screening still open; only the closing checklist counts it. [operations.py:81](../diwan/agents/operations.py#L81)
- [ ] 🟡 **Step 5, Finance** (L333). There: invoices from Facts and Mark received. Needed: a proof check beyond a typed reference, and a client receipt sent. [finance.py:80](../diwan/agents/finance.py#L80)
- [ ] 🟡 **Step 6, Operations** (L334). There: Form F plan, steps, closing. Needed: form recall, real portal fills, handover message, `case.closed`.
- [ ] 🟡 **Step 7, Review** (L335). There: draft checks with reasons. Needed: one card per item for everything a person approves.
- [ ] 🟡 **Step 8, Front Desk** (L336). There: brief, meeting table, Lobby board errands. Needed: the brief built from all rooms' Events; today it reads tasks and cards.
- [ ] ❌ **Step 9, Records analyst, renewals into Sales, the Lobby** (L337). Needed: renewals as new Cases and the Lobby room. The analyst answers questions only.

### The end-to-end test (L339-348)

- [ ] 🟡 **One scripted test, Playwright, scratch database** (L339). There: scattered flows on the seeded office. Needed: one script with one fictional client through all eight lines below.
- [ ] 🟡 **Test line 1: WhatsApp, Rania qualifies, "call me", alert within a minute** (L341). There: each part exists and the card is immediate. Needed: this line in the script, with a timing assertion. [leads.py:146](../diwan/leads.py#L146), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **Test line 2: converted, cash secondary checklist with Facts filled** (L342). There: conversion and a ready-sale path. Needed: a cash version; the mortgage steps appear for every ready sale and are ticked off as not needed. [desk_rules.py:47](../diwan/desk_rules.py#L47)
- [ ] 🟡 **Test line 3: portal, selfie refused, signs, WhatsApp receipt** (L343). There: signing and image checks. Needed: a selfie check (any clear photo passes) and a receipt message. [signing.py:123](../diwan/signing.py#L123)
- [ ] 🟡 **Test line 4: screen and clear, invoice, deposit marked, receipt to Sara** (L344). There: all but clearance and the client receipt, which is only filed. Needed: both. [finance.py:95](../diwan/agents/finance.py#L95)
- [ ] 🟡 **Test line 5: "my brother will pay part of it"** (L345). There: proven for a meeting correction. Needed: the same through WhatsApp, and a partial payer; Facts hold one payer. [scribe.py:168](../diwan/agents/scribe.py#L168), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **Test line 6: clears again, Review passes, owner approves, transfer request filled** (L346). Needed: clearance, the Review gate and the owner approval.
- [ ] ❌ **Test line 7: transfer complete, handover message, Case closes, funnel** (L347). Needed: `transfer.completed`, a handover message and a funnel view. Closing itself works. [operations.py:245](../diwan/agents/operations.py#L245)
- [ ] ❌ **Test line 8: next morning's brief, nothing Stuck** (L348). Needed: closed deals and commission due in the brief, and the Stuck board.

### What the screenshots show: Every room, Compliance, Review, Operations, Finance (L354-367)

- [ ] 🟡 **Room stats filtered to the room** (L360). There: the HQ wall screen counts per room; the fixed panel top-left still shows office-wide numbers inside every room. Needed: that panel filtered. [office3d.html:636](../web/office3d.html#L636), [office3d.html:650](../web/office3d.html#L650)
- [ ] ❌ **Stats include the Facts the room's Tasks depend on** (L360). Needed: a per-room fact count. The room screen has no facts number.
- [ ] 🟡 **Left wall is the Facts this room's Tasks depend on** (L361). There: Compliance and Finance show money facts, others every live fact. Needed: facts reached through `rests_on` of the room's Tasks. [office3d.html:587](../web/office3d.html#L587)
- [ ] 🟡 **Right wall is this room's Tasks only** (L361). There: Compliance, Finance, Operations and Review are filtered; Sales, Records and Front desk still show the office's. Needed: the same filter on those. [office3d.html:584](../web/office3d.html#L584), browser (pictures only): [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **One demo button, or each room's part** (L362). There: "Karim corrects himself" shows in every room but Marketing. Needed: HQ only, or per room. [office3d.html:831](../web/office3d.html#L831)
- [ ] ❌ **An open Task makes its agent start, or show why blocked** (L363). Needed: a `started` state and a blocked reason. Tasks never go to working, and the floor's state ignores tasks, so the Screening analyst still reads idle with T5 open. [office3d.html:628](../web/office3d.html#L628), [office3d.html:620](../web/office3d.html#L620)
- [ ] ❌ **T5 names who or what raised it** (L364). Needed: the Fact or room in the wording. It still reads "named by" the customer. [compliance.py:57](../diwan/agents/compliance.py#L57)
- [ ] 🟡 **Every item awaiting approval passes Review first** (L365). There: every draft is passed or sent back. Discounts, money release and deck approvals skip it. Needed: a Review card for each. [review.py:67](../diwan/agents/review.py#L67), [desk_stages.py:133](../diwan/desk_stages.py#L133), [finance.py:99](../diwan/agents/finance.py#L99)
- [ ] ❌ **Devil's advocate has work** (L365). Needed: a trigger. Still status "planned", with no code behind it. [charters.py:136](../diwan/agents/charters.py#L136), [office3d.html:883](../web/office3d.html#L883)
- [ ] 🟡 **Operations gets work** (L366). There: Form F plan, transfer steps and closing tasks exist, started by a person's button. Needed: `deal.ready_for_transfer` starting them. [deal_desk.py:516](../diwan/deal_desk.py#L516), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Transfer tracker has live status** (L366). There: tasks use its id, but its charter still says "planned". Needed: charter updated. [charters.py:88](../diwan/agents/charters.py#L88)
- [ ] 🟡 **Invoice clerk's core job is outgoing commission invoices** (L367). There: the code does exactly that. Needed: the charter and floor text still say "Reads supplier invoices". [finance.py:158](../diwan/agents/finance.py#L158), [charters.py:103](../diwan/agents/charters.py#L103), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] ❌ **Supplier bills as a secondary job** (L367). Needed: reading supplier bills; nothing does, despite the charter.

### Missing from the floor (L377-383)

- [ ] ❌ **Deal room on the floor** (L379). Needed: a Deal entry in `DEPTS` with checklist, portal status and follow-ups. It is a page only. [office3d.html:129](../web/office3d.html#L129)
- [ ] ❌ **Lobby room** (L380). Needed: a room. Still only the "Lobby board" orb in Front desk. [office3d.html:130](../web/office3d.html#L130)
- [ ] 🟡 **Sales lead PA in the Sales room** (L381). There: a Sales lead charter with no PA duties. Needed: the PA. [charters.py:45](../diwan/agents/charters.py#L45)
- [ ] 🟡 **"Call now" queue** (L381). There: Attention view in the Inbox. Needed: the same queue in the Sales room. [inbox.py:130](../diwan/inbox.py#L130)
- [ ] 🟡 **Finance room: Mark received, invoice drafting, commission split** (L382). There: all work on the Deal desk page; the Finance floor only shows walls. Needed: in the room, or links to it. [finance.py:80](../diwan/agents/finance.py#L80), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Commission split to our own brokers** (L382). There: the other agency's share only. Needed: broker splits and payouts. [finance.py:191](../diwan/agents/finance.py#L191)
- [ ] ❌ **Stuck board on HQ** (L383). Needed: the panel on HQ. Only a "Stuck" tile for idle deals exists, on the Deal desk KPIs. [desk_kpis.py:65](../diwan/desk_kpis.py#L65), [deal.html:337](../web/deal.html#L337)

### Command 0 (L421-436)

- [x] ✅ **Leads and deals are the same table** (L426). There: one deal node. [graph.py:195](../diwan/graph.py#L195), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py)
- [ ] 🟡 **Case fields: stage, owner_room, broker_id, created_from, Person link** (L426). There: stage, broker, and a customer name. Needed: `owner_room`, `created_from`, a real Person link. [office.py:28](../diwan/office.py#L28)
- [ ] 🟡 **Facts: quote, source, timestamp, case_id, superseded_by** (L427). There: all but `source`. [graph.py:212](../diwan/graph.py#L212)
- [x] ✅ **Never update a Fact in place** (L427). There: the log refuses it. [events.py:61](../diwan/events.py#L61), test: [test_infra.py](../tests/test_infra.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Tasks: owner_room, assignee, due_at, status, depends_on_facts** (L428). There: assignee, status, `rests_on`, `team`. Needed: `due_at` on all, explicit room.
- [ ] 🟡 **Tasks: waiting_on as client/bank/developer/government/person** (L428). There: free text on transfer steps only. Needed: the fixed list on all Tasks. [operations.py:108](../diwan/agents/operations.py#L108)
- [x] ✅ **Approvals pinned, stale ones refused** (L429). There: see the rule above. [office.py:158](../diwan/office.py#L158), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Event log is append-only** (L430). There: triggers. [events.py:61](../diwan/events.py#L61), test: [test_infra.py](../tests/test_infra.py), browser: every flow
- [ ] ❌ **Subscriber registry; rooms declare what they consume and emit** (L430). Needed: the registry. `TYPES` only lists allowed names. [events.py:11](../diwan/events.py#L11)
- [ ] ❌ **HQ Stuck panel: Events with no consumer** (L430). Needed: as named.
- [ ] ❌ **HQ Stuck panel: Tasks overdue** (L430). Needed: as named.
- [ ] ❌ **HQ Stuck panel: agent Tasks not started in 5 minutes** (L430). Needed: a started event and as named.
- [ ] ❌ **Idle agents pick up their Tasks or show why** (L431). Needed: a pickup loop. Only custom agents run by themselves. [app.py:92](../diwan/app.py#L92)
- [ ] 🟡 **Room stats and walls filtered by room** (L432). There: see the screenshot lines above. Needed: the rest of the filters.
- [x] ✅ **Pytest for the correction rule** (L433). There: only dependent Tasks change, the old approval is refused. test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **Playwright check that each room's stats differ** (L433). Needed: the check; no flow reads the stats.

### Owner settings (L811-826)

- [ ] 🟡 **One Settings page** (L811). There: Settings holds connections and the sales team; the rest is spread over Deal desk rules, Qualification, Calendar, Studio Setup, Team page and `.env`. Needed: one page. [settings.html:191](../web/settings.html#L191), [deal.html:272](../web/deal.html#L272)
- [ ] 🟡 **One setting, read everywhere** (L811). There: Deal rules are read this way; many values are constants or `.env`. Needed: see no-guess rule 3 below.
- [x] ✅ **Office: name, licence, TRN, address** (L817). There: agency name, ORN, TRN, address in the Deal rules. [desk_rules.py:37](../diwan/desk_rules.py#L37), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Office: working hours** (L817). There: calendar opening hours. [slots.py:49](../diwan/slots.py#L49), test: [test_calendar.py](../tests/test_calendar.py), browser: [basics_flow.py](../e2e/basics_flow.py)
- [x] ✅ **Office: quiet hours** (L817). There: `quiet_from`, `quiet_to`, for follow-ups only. [nudge.py:19](../diwan/agents/nudge.py#L19), test: [test_nudge.py](../tests/test_nudge.py), browser: [quiet_flow.py](../e2e/quiet_flow.py)
- [ ] 🟡 **Office: Friday prayer window** (L817). There: an on/off tick; the window itself is a constant. Needed: editable times. [nudge.py:22](../diwan/agents/nudge.py#L22)
- [ ] ❌ **Office: public holidays** (L817). Needed: a list, read by slots and reminders.
- [ ] ❌ **Office: languages Rania speaks** (L817). Needed: a setting. `business.languages` is for marketing posts only.
- [ ] 🟡 **People: staff** (L818). There: a fixed list in code. Needed: add or remove staff without code. [people.py:4](../diwan/people.py#L4)
- [x] 🧪 **People: roles and rooms they see** (L818). There: owner assigns desk roles and logins; rooms come from the department. [roles.py:14](../diwan/roles.py#L14), [access.py:49](../diwan/access.py#L49), test: [test_access.py](../tests/test_access.py)
- [ ] ❌ **People: display names, who covers whom, PA names** (L818). Needed: these settings.
- [x] ✅ **Sales: qualifying forms** (L819). There: Qualification page, per customer type. Per intent comes through deal kinds. [qualify.html](../web/qualify.html), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] ❌ **Sales: heat-score rules** (L819). Needed: a score. Hot is a yes or no mark.
- [ ] 🟡 **Sales: call-now limit, default 10 min** (L819). There: `.env`, default 15, not on a page. Needed: a page setting. [leads.py:32](../diwan/leads.py#L32)
- [x] ✅ **Sales: follow-up schedule** (L819). There: owner's schedule. [nudge.py:42](../diwan/agents/nudge.py#L42), test: [test_nudge.py](../tests/test_nudge.py), browser: [quiet_flow.py](../e2e/quiet_flow.py)
- [ ] 🟡 **Sales: lead routing** (L819). There: listing agent then round-robin; deal kinds restrict brokers. Needed: by area, by language, as a chosen setting. [leads.py:96](../diwan/leads.py#L96), test: [test_leads.py](../tests/test_leads.py)
- [ ] 🟡 **Deal: checklist templates per deal type and party type** (L820). There: steps per path, documents per party. Needed: per deal type within a path (cash, mortgage, company). [desk_rules.py:41](../diwan/desk_rules.py#L41), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] ❌ **Deal: document expiry warnings** (L820). Needed: a setting. 60 days is a constant, and only flags at upload. [documents.py:169](../diwan/documents.py#L169)
- [ ] 🟡 **Deal: follow-up ladder 24 / 48 / 72h** (L820). There: every N days, M times, default 2 days × 3. Needed: the ladder in hours. [desk_rules.py:34](../diwan/desk_rules.py#L34)
- [x] 🧪 **Deal: portal link lifetime** (L820). There: `sign_link_days`. [desk_rules.py:31](../diwan/desk_rules.py#L31), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [x] ✅ **Money: commission rates per deal type and payer** (L821). There: per path, plus developer agreements. [desk_rules.py:44](../diwan/desk_rules.py#L44), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [x] ✅ **Money: VAT** (L821). There: `vat_pct`. [desk_rules.py:28](../diwan/desk_rules.py#L28), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Money: invoice triggers** (L821). There: a developer's "payable after" share only. Needed: triggers for other paths. [finance.py:170](../diwan/agents/finance.py#L170)
- [x] 🧪 **Money: deposit rule, who holds it** (L821). There: `deposit_held_by`, printed on Form F. [desk_rules.py:39](../diwan/desk_rules.py#L39), [agency_forms.py:236](../diwan/agency_forms.py#L236) (no direct test)
- [ ] ❌ **Money: payout split rules** (L821). Needed: a setting; a deal's other-agency share is typed per deal.
- [ ] ❌ **Money: reminder schedule** (L821). Needed: a setting and the reminders; none go out for money.
- [ ] 🟡 **Compliance: thresholds** (L822). There: cash report only. Needed: source-of-funds threshold. [desk_rules.py:27](../diwan/desk_rules.py#L27), test: [test_deal_desk.py](../tests/test_deal_desk.py)
- [ ] ❌ **Compliance: screening lists, high-risk rules** (L822). Needed: these settings. Lists are named in the charter only.
- [x] ✅ **Compliance: the named officer** (L822). There: owner assigns the role. [roles.py:14](../diwan/roles.py#L14), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **Compliance: retention period, who may delete** (L822). Needed: both; the log can't delete anything, and that clash needs an answer.
- [ ] 🟡 **Messaging: approved WhatsApp templates** (L823). There: read from AiSensy, marked samples when none; picks per use. Needed: one place. [inbox.py:41](../diwan/inbox.py#L41), test: [test_inbox.py](../tests/test_inbox.py)
- [ ] ❌ **Messaging: opt-in record** (L823). Needed: a record per Person.
- [ ] 🟡 **Messaging: stop words in each language** (L823). There: English and Arabic, as a constant. Needed: a setting. [nudge.py:24](../diwan/agents/nudge.py#L24), test: [test_nudge.py](../tests/test_nudge.py)
- [ ] 🟡 **Messaging: which messages need approval** (L823). There: autonomy per agent, not per message. Needed: per message kind. [lessons.py:20](../diwan/agents/lessons.py#L20)
- [ ] 🟡 **Marketing: permit required, default Yes** (L824). There: setting read by the studio; the UAE default is not forced. Needed: confirm the default (Marketing reviewer). [rhythm.py:120](../diwan/agents/rhythm.py#L120), test: [test_studio.py](../tests/test_studio.py)
- [x] ✅ **Marketing: brand voice** (L824). There: brand profile. [brand_api.py](../diwan/brand_api.py), test: [test_brand.py](../tests/test_brand.py), browser: [brand_flow.py](../e2e/brand_flow.py)
- [x] 🧪 **Marketing: posting hours** (L824). There: the studio's start time and slots. [rhythm.py:22](../diwan/agents/rhythm.py#L22), test: [test_studio.py](../tests/test_studio.py)
- [ ] 🟡 **Review: which items need Review and owner approval; who may approve what amount** (L825). There: only a discount limit. Needed: a table of items and amounts. [desk_rules.py:30](../diwan/desk_rules.py#L30), test: [test_deal_property.py](../tests/test_deal_property.py)
- [ ] 🟡 **Limits: model spend limits** (L826). There: `.env` budgets, enforced. Needed: on the page. [costs.py:54](../diwan/costs.py#L54), test: [test_costs.py](../tests/test_costs.py)
- [ ] 🟡 **Limits: stuck thresholds, days per stage** (L826). There: one number for all stages. Needed: per stage. [desk_rules.py:29](../diwan/desk_rules.py#L29), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] ❌ **Limits: escalation chain** (L826). Needed: a setting.

### What each upload stores (L828-842)

- [ ] 🟡 **One Document record per upload** (L828). There: `docs.received`, then `document.filed` after confirmation, with different fields. Needed: one record.
- [ ] 🟡 **case_id, party_id, role** (L832). There: deal, and party as a role word and a name. Needed: a real `party_id`. [documents.py:96](../diwan/documents.py#L96)
- [ ] 🟡 **kind** (L833). There: six kinds at upload (passport, Emirates ID, visa, deed, licence). Needed: form_b, form_f, cheque, pre_approval, liability_letter, poa and the rest. [documents.py:27](../diwan/documents.py#L27)
- [ ] 🟡 **file, pages, hash** (L834). There: file and SHA-256. Needed: page count. [documents.py:191](../diwan/documents.py#L191)
- [ ] 🟡 **A re-upload of the same file is noticed** (L834). There: refused against this link's other documents only. Needed: across the Case. [documents.py:192](../diwan/documents.py#L192), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [x] ✅ **uploaded_by, channel, at** (L835). There: actor `client:<party>`, the docs link, event time. [documents.py:207](../diwan/documents.py#L207), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **extracted** (L836). There: what the client typed, not read from the file. Needed: reading by vision, once the owner picks a provider. [documents.py:147](../diwan/documents.py#L147)
- [ ] 🟡 **check_result: passed / failed + reasons** (L837). There: failed uploads log reasons; passing ones keep flags; the officer's result sits on a task. Needed: one field on the record. [documents.py:202](../diwan/documents.py#L202)
- [ ] ❌ **check_result: overridden by whom and why** (L837). Needed: an override path.
- [ ] 🟡 **expires_at** (L838). There: a typed `expiry` in `fields`. Needed: its own field that drives warnings. [documents.py:162](../diwan/documents.py#L162)
- [ ] 🟡 **satisfies_task** (L839). There: the check task points to the document, not the checklist task it closes. Needed: the link the other way. [documents.py:209](../diwan/documents.py#L209)
- [ ] 🟡 **based_on_facts** (L840). There: drafts link slide to Fact, and a form has a fingerprint. Needed: on the Document record. [office.py:171](../diwan/office.py#L171)
- [ ] 🟡 **status: current / superseded / voided** (L841). There: draft states only; uploads have none. Needed: this field with a reason.
- [ ] 🟡 **reviewed_by, at** (L842). There: `docs.confirmed` actor and time, by the compliance officer, not Review. Needed: Review's. [documents.py:236](../diwan/documents.py#L236)

### Case stages: the rules (L889-891, L944)

- [ ] ❌ **Only the listed stages exist** (L891). Needed: rename to the list, or an answer on the Conflict below. Code stages are few, title-case and owner-editable. [desk_rules.py:86](../diwan/desk_rules.py#L86)
- [ ] 🟡 **Any move not listed is refused and logged** (L891). There: unknown stages are refused, not logged; any forward jump passes. Needed: a from-to table and a logged refusal. [desk_stages.py:61](../diwan/desk_stages.py#L61), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] ❌ **Moves happen on the named event** (L891). Needed: events that drive stages; apart from Rania's early moves, a stage moves when a person picks it.
- [ ] ❌ **Side state on_hold; nothing binding may happen** (L891). Needed: a state set by Compliance or the owner, and a check before every binding action. `hold` exists only as an action word. [pack.py:57](../diwan/pack.py#L57)
- [x] ✅ **Side state nurture, follow-ups only** (L891). There: `lead.nurture`, on the deal, leaving its stage alone. [graph.py:454](../diwan/graph.py#L454), test: [test_nudge.py](../tests/test_nudge.py), browser: [quiet_flow.py](../e2e/quiet_flow.py)
- [ ] 🟡 **Shared start: Sales** (L897-902). There: New, Qualifying, Qualified, viewing, Offer. Needed: discovering, and `offer.made`. See the table.
- [ ] 🟡 **Sale (ready unit)** (L908-913). There: Form F, Transfer, Closing, Won. Needed: documents, cleared, transfer_ready, transfer_booked, transferred. See the table.
- [ ] 🟡 **Off-plan** (L919-922). There: Reservation, SPA, Oqood, Won. Needed: handover_due as a stage; the deal closes on our commission and handover runs on as tasks. [desk_rules.py:61](../diwan/desk_rules.py#L61)
- [ ] 🟡 **Rental** (L928-933). There: Contract, Ejari, Move-in, Won, then two tasks. Needed: documents, tenancy_active, renewal_due, move_out. [operations.py:275](../diwan/agents/operations.py#L275), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **Listing (seller side)** (L939-942). Needed: all four stages. A listing is a catalogue record with no Case and no Form A step before it. [office.py:185](../diwan/office.py#L185)
- [ ] 🟡 **Endings with a lost reason** (L944). There: Won and Lost; a person must give a reason, and Rania's auto-Lost carries the rule. Needed: the reason in a fixed list. [desk_stages.py:69](../diwan/desk_stages.py#L69), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [ ] 🟡 **A closed Case is never reopened** (L944). There: a Won deal is refused; a Lost deal can come back with a reason. Needed: see Conflicts. [desk_stages.py:56](../diwan/desk_stages.py#L56), [desk_stages.py:65](../diwan/desk_stages.py#L65)
- [ ] ❌ **A new linked Case instead** (L944). Needed: Case-to-Case links.
- [ ] 🟡 **Final-stage Cases still feed aftercare and renewals** (L944). There: a rental's renewal and move-out tasks, off-plan after-steps. Needed: aftercare for sales. [operations.py:275](../diwan/agents/operations.py#L275), browser: [deal_flow.py](../e2e/deal_flow.py)

**Stage table** (`stage.changed` is the only writer: [desk_stages.py:74](../diwan/desk_stages.py#L74), [inbox.py:277](../diwan/inbox.py#L277), [operations.py:273](../diwan/agents/operations.py#L273); read by [inbox.py:13](../diwan/inbox.py#L13), [desk_kpis.py:40](../diwan/desk_kpis.py#L40))

| Spec stage | In code as | Used by (emits / consumes) | Status |
| --- | --- | --- | --- |
| new | New | Default when no stage / Inbox, Deal desk | same, different case |
| discovering | none | Nothing; the chat stays New | missing |
| qualifying | Qualifying | Rania auto / Inbox | same |
| qualified | Qualified | Rania auto / Inbox | same |
| viewing | Viewing booked, Viewed (two stages) | Rania auto, person / Inbox | split |
| offer | Offer (ready, rent paths); none off-plan | Person / Deal desk | partial |
| documents (sale) | none; Offer accepted is nearest | Person / Deal desk | missing |
| cleared | none | None | missing |
| mou_signed | Form F (nearest; a stage, not proof of signing) | Person / Deal desk | near |
| transfer_ready | Transfer (nearest) | Person / Deal desk | near |
| transfer_booked | none; a step task | None | missing |
| transferred | none; a step task | None | missing |
| reserved | Reservation | Person, Convert / Deal desk | near |
| spa_signed | SPA | Person / Deal desk | near |
| registered | Oqood | Person / Deal desk | near |
| handover_due | none; an after-close task | Transfer tasks | missing as a stage |
| documents (rental) | none | None | missing |
| contract_signed | Contract | Person / Deal desk | near |
| moved_in | Move-in | Person / Deal desk | near |
| tenancy_active | none; deal is Won | None | missing |
| renewal_due | none; `ops` task, step renewal | Task / Deal desk | missing as a stage |
| move_out | none; `ops` task, step moveout | Task / Deal desk | missing as a stage |
| listing_signed | none | None | missing |
| listing_live | listing status "available" (not a Case) | `listing.added` / catalogue | missing as a stage |
| under_offer | listing status "reserved" (not a Case) | `listing.added` / catalogue | missing as a stage |
| listing_expiring | none | None | missing |
| closed_won | Won | `operations.close` / Inbox, KPIs | same idea |
| closed_lost | Lost | Person, Rania auto, merge / Inbox, KPIs | same idea |
| on_hold (side) | none | None | missing |
| nurture (side) | `lead.nurture` prop | Rania, nudge / Inbox | same idea |
| not_a_lead (L898) | `qualify.not_fit` then Lost | Rania auto / Inbox | near |
| not in spec | Offer accepted, Ejari, Transfer, Closing | Path settings | code-only stage names |

### Event catalog (L946-989)

- [ ] ❌ **These are the only event names** (L948). Needed: the code's 133 allowed names and the catalog brought together. Only 5 of the catalog's 64 names match exactly. [events.py:11](../diwan/events.py#L11)
- [ ] 🟡 **Every event carries case_id, actor, at** (L948). There: `deal`, `actor`, `at` as columns, but `deal` is empty on many. [events.py:57](../diwan/events.py#L57)
- [ ] ❌ **Every event carries fact_ids with versions** (L948). Needed: the field.
- [ ] ❌ **Every event has at least one consumer in code** (L989). Needed: a consumer map and a test that walks the catalog. Today 32 of the catalog's 64 names have no code at all.
- [ ] ❌ **The Stuck board lists events emitted with no consumer** (L989). Needed: the board.
- [ ] 🟡 **`message.received`** (L952). There: `chat.received`, for WhatsApp, Instagram and portals. [events.py:35](../diwan/events.py#L35), [graph.py:270](../diwan/graph.py#L270), test: [test_reception.py](../tests/test_reception.py), browser: [office_flow.py](../e2e/office_flow.py)
- [ ] 🟡 **`case.created`** (L953). There: `deal.opened`; no source channel in it. [office.py:28](../diwan/office.py#L28), test: [test_nova.py](../tests/test_nova.py)
- [ ] 🟡 **`case.intent_set`** (L954). There: `qualify.type` and `lead.kind`; no fixed intent list. [graph.py:411](../diwan/graph.py#L411), test: [test_qualify.py](../tests/test_qualify.py)
- [ ] 🟡 **`case.merged`, a person confirms** (L955). There: `chat.merged` by the broker. Needed: duplicates proposed by the system, and notice to all rooms. [leads.py:257](../diwan/leads.py#L257), test: [test_front_door.py](../tests/test_front_door.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [ ] 🟡 **`fact.recorded`** (L956). There: `fact.created`, and Compliance reacts by a direct call. Needed: the event name and a subscription. [office.py:82](../diwan/office.py#L82), test: [test_scribe.py](../tests/test_scribe.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **`fact.superseded`** (L957). There: same name; payload is `id` and `by`, consumers are direct calls. [office.py:104](../diwan/office.py#L104), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **`task.created` / `task.done`** (L958). There: same names; `rests_on` instead of `depends_on_facts`, no `due`. [office.py:135](../diwan/office.py#L135), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **`task.reopened`** (L958). There: `task.withdrawn`, which ends a task; it never reopens. [office.py:108](../diwan/office.py#L108), test: [test_nova.py](../tests/test_nova.py)
- [ ] 🟡 **`call.requested`** (L959). There: `attention.raised` with kind call. [leads.py:142](../diwan/leads.py#L142), test: [test_leads.py](../tests/test_leads.py), browser: [call_flow.py](../e2e/call_flow.py)
- [ ] 🟡 **`viewing.booked` / `viewing.done` / `viewing.no_show`** (L960). There: `appointment.booked`, `.done`, `.noshow`; Ops gets nothing for access. [graph.py:338](../diwan/graph.py#L338), test: [test_calendar.py](../tests/test_calendar.py), browser: [calendar_flow.py](../e2e/calendar_flow.py)
- [ ] ❌ **`offer.made` / `offer.countered`** (L961). Needed: offers as events; a stage called Offer and a final agreed price are all that exist.
- [ ] 🟡 **`case.converted`** (L962). There: `setting.changed` key "agreed" plus `stage.changed`, then a direct call to agency forms. Finance, Compliance and Records are not told. Needed: the event, with deal and party types. [desk_stages.py:170](../diwan/desk_stages.py#L170), [desk_stages.py:80](../diwan/desk_stages.py#L80), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py)
- [ ] 🟡 **`case.lost`** (L963). There: `stage.changed` to Lost, releasing the listing; Records has no lost view. Needed: the event with a lost reason. [desk_stages.py:75](../diwan/desk_stages.py#L75), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] 🟡 **`cobroke.agreed`** (L964). There: other agency and share in the `setting.changed` deal terms. [desk_rules.py:314](../diwan/desk_rules.py#L314), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **`doc.requested` / `doc.received` / `doc.rejected`** (L965). There: `docs.requested`, `.received`, `.rejected`, plus `.confirmed`, `.reminded`. [documents.py:96](../diwan/documents.py#L96), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **`form.ready` / `form.sent` / `form.signed`** (L966). There: `draft.made`, `sign.link`, `sign.signed`. [events.py:30](../diwan/events.py#L30), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **`form.recalled`** (L966). Needed: a recall. A changed term sends a draft back, but nothing voids a form the other side already holds.
- [ ] ❌ **`compliance.cleared` / `.needs_info` / `.blocked`** (L967). Needed: all three. A person records a screening result on a task; nothing clears a Case. [compliance.py:88](../diwan/agents/compliance.py#L88)
- [ ] 🟡 **`screening.hit`, officer only** (L968). There: a `task.done` with result "possible match", visible to the whole deal team. Needed: the event and a restricted view. [compliance.py:88](../diwan/agents/compliance.py#L88)
- [ ] ❌ **`mortgage.preapproved` / `.final_offer` / `.refused`** (L969). Needed: all three; mortgage is one transfer step.
- [ ] ❌ **`review.requested`** (L970). Needed: as named; Review runs by direct call. [office.py:172](../diwan/office.py#L172)
- [ ] 🟡 **`review.passed` / `review.sent_back`** (L970). There: `review.passed`, and `review.returned`, for drafts only. [review.py:79](../diwan/agents/review.py#L79), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **`approval.given` / `approval.declined`** (L971). There: `approval.given`, and `approval.refused`, which also means the guard's refusal. [office.py:147](../diwan/office.py#L147), test: [test_nova.py](../tests/test_nova.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **`deal.ready_for_transfer`** (L972). Needed: as named, with the transfer date wanted.
- [ ] ❌ **`noc.received` / `transfer.booked` / `transfer.completed`** (L973). Needed: all three. These are ticks on `transfer` tasks, matched by nothing. [operations.py:119](../diwan/agents/operations.py#L119)
- [ ] ❌ **`ejari.ready` / `listing.ready`** (L974). Needed: both.
- [ ] 🟡 **`listing.live`** (L974). There: `listing.added` with status available and a permit. [office.py:189](../diwan/office.py#L189), test: [test_leads.py](../tests/test_leads.py)
- [ ] 🟡 **`invoice.sent`** (L975). There: `task.done` with result "sent". [finance.py:212](../diwan/agents/finance.py#L212), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **`payment.marked_received`** (L975). There: `task.done` with result "received"; Compliance does not hear. [finance.py:93](../diwan/agents/finance.py#L93), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **`payment.flagged`** (L975). Needed: as named.
- [ ] ❌ **`cheque.due` / `cheque.bounced` / `installment.due`** (L976). Needed: all three. Scheduled payments exist as `pay` tasks, but nothing fires on the date, and nothing marks a bounce. [finance.py:265](../diwan/agents/finance.py#L265)
- [ ] ❌ **`renewal.due`** (L977). Needed: as named; today a dated task made at closing, which nothing raises. [operations.py:278](../diwan/agents/operations.py#L278)
- [ ] ❌ **`form.expiring` / `doc.expiring`** (L977). Needed: both and the scan.
- [ ] 🟡 **`case.closed`** (L978). There: `sale.closed` plus `stage.changed` Won. [office.py:205](../diwan/office.py#L205), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **`complaint.opened`** (L979). Needed: as named.
- [ ] ❌ **`experiment.approved` / `experiment.ended`** (L980). Needed: both.
- [ ] 🟡 **`unit.held`** (L981). There: `listing.added` with status reserved, on our listings; no developer unit, hold expiry or price-list date. [deal_property.py:192](../diwan/deal_property.py#L192), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py)
- [ ] ❌ **`listing.signed`** (L982). Needed: as named; Form A signs on a buyer's deal only.
- [ ] ❌ **`valuation.sent`** (L983). Needed: as named.
- [ ] ❌ **`seller.report`** (L984). Needed: as named.
- [ ] ❌ **`oqood.received`** (L985). Needed: as named; a tick on a step.
- [ ] ❌ **`funds.ready`** (L986). Needed: as named.
- [ ] ❌ **`referral.asked`** (L987). Needed: as named.

**Event table.** "Graph" means the only consumer is the read model in [graph.py](../diwan/graph.py), which is a screen, not a room reacting. "Custom" means it is also a trigger for the owner's custom agents ([custom.py:20](../diwan/agents/custom.py#L20)).

| Spec event | In code as | Used by (emits / consumes) | Status |
| --- | --- | --- | --- |
| message.received | chat.received | reception, webhooks / Graph, Custom, runs Rania | near |
| case.created | deal.opened | office / Graph, Custom | near |
| case.intent_set | qualify.type, lead.kind | reception / Graph | near |
| case.merged | chat.merged | leads / Graph | near |
| fact.recorded | fact.created | office / Graph, Custom; Compliance by direct call | near |
| fact.superseded | fact.superseded | office / Graph, Custom; rooms by direct call | same name |
| task.created | task.created | office / Graph | same name |
| task.done | task.done | Many / Graph, closing checklist | same name |
| task.reopened | task.withdrawn (ends, not reopens) | office / Graph | different meaning |
| call.requested | attention.raised, kind call | leads / Graph, sweep | near |
| viewing.booked | appointment.booked | reception / Graph, Custom | near |
| viewing.done | appointment.done | reception, calendar / Graph | near |
| viewing.no_show | appointment.noshow | calendar / Graph | near |
| offer.made | none | None | missing |
| offer.countered | none | None | missing |
| case.converted | setting.changed "agreed" + stage.changed | desk_stages / Graph, agency forms by direct call | no event |
| case.lost | stage.changed Lost | desk_stages, inbox, leads / Graph, KPIs | no event |
| cobroke.agreed | setting.changed "terms" | desk_rules / finance reads | no event |
| doc.requested | docs.requested | documents / documents, screens | near |
| doc.received | docs.received | documents / documents, screens | near |
| doc.rejected | docs.rejected | documents / documents, screens | near |
| form.ready | draft.made | office / Graph, Review by direct call | near |
| form.sent | sign.link | signing / signing | near |
| form.signed | sign.signed | signing / signing | near |
| form.recalled | none | None | missing |
| compliance.cleared | none | None | missing |
| compliance.needs_info | none (question.asked funding is nearest) | None | missing |
| compliance.blocked | none | None | missing |
| screening.hit | task.done "possible match" | compliance / screens | no event |
| mortgage.preapproved | none | None | missing |
| mortgage.final_offer | none | None | missing |
| mortgage.refused | none | None | missing |
| review.requested | none | None | missing |
| review.passed | review.passed | review / screens | same name, drafts only |
| review.sent_back | review.returned | review, agency forms / Graph | near |
| approval.given | approval.given | office / Graph | same name |
| approval.declined | approval.refused | office guard, review / Graph | near |
| deal.ready_for_transfer | none | None | missing |
| noc.received | none (transfer task) | None | missing |
| transfer.booked | none (transfer task) | None | missing |
| transfer.completed | none (transfer task) | None | missing |
| ejari.ready | none | None | missing |
| listing.ready | none | None | missing |
| listing.live | listing.added | office, deal_property / Graph | near |
| invoice.sent | task.done "sent" | finance / closing | no event |
| payment.marked_received | task.done "received" | finance / closing, commission | no event |
| payment.flagged | none | None | missing |
| cheque.due | none | None | missing |
| cheque.bounced | none | None | missing |
| installment.due | none | None | missing |
| renewal.due | none (ops task) | None | missing |
| form.expiring | none | None | missing |
| doc.expiring | none | None | missing |
| case.closed | sale.closed + stage.changed Won | office, operations / Graph, Records | no event |
| complaint.opened | none | None | missing |
| experiment.approved | none | None | missing |
| experiment.ended | none | None | missing |
| unit.held | listing.added "reserved" | deal_property / Graph | near |
| listing.signed | none | None | missing |
| valuation.sent | none | None | missing |
| seller.report | none | None | missing |
| oqood.received | none | None | missing |
| funds.ready | none | None | missing |
| referral.asked | none | None | missing |
| not in catalog | 128 other names, e.g. check.raised, lead.*, attention.*, qualify.*, post.*, content.* | Across the app | code-only names |

### No-guess rules (L995-1006)

- [ ] 🟡 **Rule 1: only Part 4's stages and events** (L997). There: names are limited to a list, but not that list. Needed: see the catalog above.
- [ ] ❌ **Rule 2: unknowns go to docs/open-questions.md** (L998). Needed: the file; it does not exist.
- [ ] 🟡 **Rule 3: no constants, every number a setting** (L999). There: Deal rules are settings. Still constants or `.env`: call and reply limits, pool hour, prayer window, document hours, 60-day flag, session hours. Needed: all moved. [leads.py:32](../diwan/leads.py#L32), [nudge.py:22](../diwan/agents/nudge.py#L22), [documents.py:256](../diwan/documents.py#L256), [lobby.py:21](../diwan/agents/lobby.py#L21)
- [x] ✅ **Rule 4: agents never pay, sign, submit, file, clear or mark received** (L1000). There: charter check, role checks. [runner.py:140](../diwan/agents/runner.py#L140), test: [test_infra.py](../tests/test_infra.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **Rule 5: no room calls another room's functions** (L1001). Needed: see the rule above.
- [ ] 🟡 **Rule 6: client messages inside 24h or by template, else a broker Task** (L1002). There: most paths. Document reminders go out with neither check, and without checking "stop". Needed: the check in `_send`. [documents.py:284](../diwan/documents.py#L284), [reception.py:530](../diwan/agents/reception.py#L530)
- [ ] ❌ **Rule 7: spec disagreements go to open-questions.md** (L1003). Needed: the file; start with the Conflicts below.
- [ ] 🟡 **Rule 8: only fictional people and companies** (L1004). There: names are fictional, but real developers appear in tests and demo data. Needed: fictional names. [test_deal_property.py](../tests/test_deal_property.py), [demo_feed.xml:344](../diwan/demo_feed.xml#L344)
- [ ] ❓ **Rule 9: how each task is finished** (L1005). Needs the office's answer: this is a working habit, not code. Should it be enforced by a template?

### Definition of done for each room (L1008-1015)

- [ ] 🟡 **Room shows only its own stats, Tasks, Facts, Stuck items** (L1010). There: Compliance, Finance, Operations and Review are partly filtered. Needed: all rooms and Stuck. [office3d.html:582](../web/office3d.html#L582)
- [ ] ❌ **Every consumed event has a handler, every emitted one a consumer** (L1011). Needed: the registry.
- [ ] ❌ **Agent Tasks start in 5 minutes or show why** (L1012). Needed: see Command 0.
- [ ] ❌ **The room's PA answers "what's waiting on me?"** (L1013). Needed: per-room PAs. Nova's "my day" answers per person and `/api/desk/work` lists work, but no room has one. [nova.py:258](../diwan/agents/nova.py#L258), [deal_desk.py:330](../diwan/deal_desk.py#L330)
- [ ] 🟡 **Every way out of a room has a test** (L1014). There: many happy paths for Deal, Finance, Compliance. Needed: unhappy paths; most don't exist yet.
- [ ] 🟡 **The correction rule works per room** (L1015). There: for Compliance, Finance, Operations and Review. Needed: Sales and Records work resting on Facts, and qualification answers. [office.py:97](../diwan/office.py#L97), test: [test_desk_rules.py](../tests/test_desk_rules.py)

### Seed scenarios (L1017-1030)

None of the ten is a scenario test yet. Lines are 🟡 when part of it is built.

- [ ] 🟡 **Sara, cash buyer, corrects the payer** (L1021). There: the same story with Karim in the deal flow. Needed: a Sara scenario on WhatsApp. browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **Karim, mortgage, valuation AED 150,000 short** (L1022). Needed: mortgage stages and valuation-gap options.
- [ ] ❌ **Al Noor Trading LLC, director, board resolution** (L1023). Needed: company KYC, ownership declaration, resolution check. Only a trade licence is listed. [desk_rules.py:33](../diwan/desk_rules.py#L33)
- [ ] ❌ **Priya sells under POA, mortgage and tenant** (L1024). Needed: POA check and tenanted sale. A liability step exists as text. [desk_rules.py:49](../diwan/desk_rules.py#L49)
- [ ] 🟡 **Omar's buyer walks after the MOU** (L1025). There: Lost releases the listing. Needed: deposit options to the owner. [deal_property.py:198](../diwan/deal_property.py#L198), browser: [property_flow.py](../e2e/property_flow.py)
- [ ] 🟡 **Tenant Ahmed: 4 cheques, bounce, renews, moves out** (L1026). There: 4 cheques, a renewal and move-out task. Needed: bounced cheque, the second year, deposit settlement. browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Off-plan Lina** (L1027). There: path, schedule, developer commission, with other names. Needed: this scenario. browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Selfie, expired passport, wrong-unit deed** (L1028). There: an expired document is refused. Needed: selfie and wrong-unit checks. [documents.py:167](../diwan/documents.py#L167), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] 🟡 **WhatsApp and Instagram lead, same phone** (L1029). There: a person merges. Needed: duplicate detection, which is manual. [leads.py:244](../diwan/leads.py#L244), test: [test_front_door.py](../tests/test_front_door.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [ ] ❌ **"Send the deposit to this new account"** (L1030). Needed: a fraud guard with a Now flag.
- [ ] ❓ **Dubai document lists confirmed** (L1032). Needs the office's answer: conveyancer and compliance officer to confirm the lists. Current default in code: "Dubai's usual practice" in the Deal rules.

### Departments not covered (L1115)

- [x] ✅ **Staff accounts and roles covered** (L1115). There: logins and role assignment. [access.py:289](../diwan/access.py#L289), [roles.py:14](../diwan/roles.py#L14), test: [test_access.py](../tests/test_access.py), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] 🟡 **Broker licence expiry covered** (L1115). There: each broker's BRN number. Needed: an expiry date and a warning. [desk_rules.py:40](../diwan/desk_rules.py#L40)

### The whole lifecycle (L1119-1132)

- [ ] ❌ **Step 0: each post traced to the Cases it brings, `lead.attributed`** (L1119). Needed: attribution. Nothing in the code does this; `lead.attributed` is also not in the catalog.
- [ ] ❌ **Step 0: Records reports which content produced deals** (L1119). Needed: the report.
- [ ] 🟡 **1 First contact** (L1121). There: any channel opens a lead and Rania replies. Needed: duplicates proposed for merge. [reception.py:494](../diwan/agents/reception.py#L494), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **2 Qualify** (L1122). There: owner's form with quotes, hot leads, nurture. Needed: heat score. [qualify.html](../web/qualify.html), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **3 Match and view** (L1123). There: options, booking, reminders, no-show, visit summary. Needed: access arrangements, and feedback as Facts (summary is a separate record). [graph.py:423](../diwan/graph.py#L423), browser: [visit_flow.py](../e2e/visit_flow.py)
- [ ] ❌ **4 Offer: offers as Facts, side by side, acceptance quoted** (L1124). Needed: all of it; conversion takes a typed price. [desk_stages.py:105](../diwan/desk_stages.py#L105)
- [ ] 🟡 **5 Paperwork** (L1125). There: checklist by path, uploads with checks, signatures, reminders. Needed: party-type lists, WhatsApp receipts, the ladder.
- [ ] 🟡 **6 Gates** (L1126). There: screening, source-of-funds view, Review on drafts. Needed: a gate that blocks, and owner approval.
- [ ] 🟡 **7 Official steps** (L1127). There: Form F field plan, step ticks. Needed: real fills, NOC, Ejari, permits, events.
- [ ] 🟡 **8 Money** (L1128). There: invoices, marked payments, receipts as PDF, other-agency split. Needed: receipts sent to clients, broker payouts.
- [ ] 🟡 **9 Handover** (L1129). There: one step text. Needed: keys, utilities, condition report as items; `case.closed`.
- [ ] 🟡 **10 Living with it** (L1130). There: renewal and move-out tasks, cheque dates. Needed: everything run on a schedule, referrals, new linked Cases.
- [ ] ❌ **11 Off the path, each with a defined ending** (L1131). There: corrections are defined. Needed: walk-aways, refusals, bounced cheques, complaints, fraud guard, staff changes, data requests.
- [ ] ❌ **12 Learning** (L1132). Needed: experiments. Lessons taught to an agent exist, but nothing measures or rolls back. [lessons.py](../diwan/agents/lessons.py)

### Each department's lifecycle and rhythm (L1134-1151)

What really runs on a clock: `morning_loop` every minute (rounds, Lobby chase, document reminders, lead sweep, follow-ups, reminders and broker list, studio run, publishing, competitor refresh, listing feed), and `custom_loop` every 3 seconds. [app.py:57](../diwan/app.py#L57). Nothing weekly or monthly exists anywhere except the studio's own weekly plan.

- [ ] 🟡 **Front Desk: greet, brief, meetings, decisions, errands, wrap** (L1140). There: all but wrap. [nova.py:506](../diwan/agents/nova.py#L506), test: [test_frontdesk.py](../tests/test_frontdesk.py), browser: [office_flow.py](../e2e/office_flow.py)
- [ ] 🟡 **Front Desk daily: 07:30 brief** (L1140). There: rounds run 30 minutes before the earliest person's time, default 09:00, and the brief waits to be opened. Needed: default 07:30, sent to people. [app.py:67](../diwan/app.py#L67), [nova.py:558](../diwan/agents/nova.py#L558), test: [test_frontdesk.py](../tests/test_frontdesk.py)
- [ ] ❌ **Front Desk daily: end-of-day wrap** (L1140). Needed: the job.
- [ ] ❌ **Front Desk weekly: Monday numbers** (L1140). Needed: the job.
- [ ] ❌ **Front Desk monthly: owner review** (L1140). Needed: the job.
- [ ] 🟡 **Marketing: idea to archived** (L1141). There: the studio's run. Part F has the detail. Needed: starting on `listing.live`. [rhythm.py:249](../diwan/agents/rhythm.py#L249), test: [test_studio.py](../tests/test_studio.py), browser: [studio_flow.py](../e2e/studio_flow.py)
- [x] ✅ **Marketing daily: approvals and posting** (L1141). There: automatic run if turned on; approved posts go out on time. [app.py:79](../diwan/app.py#L79), test: [test_studio.py](../tests/test_studio.py), browser: [studio_flow.py](../e2e/studio_flow.py)
- [ ] ❌ **Marketing daily: pause anything with an expired permit or old price** (L1141). Needed: the job. A permit is checked before posting, not afterwards.
- [ ] ❌ **Marketing weekly: leads and deals per post** (L1141). Needed: attribution and the job.
- [ ] ❌ **Marketing monthly: campaign results, spend vs cap, next month's plan** (L1141). Needed: the job; the studio plans at most a week.
- [ ] 🟡 **Sales: new to converted, lost, nurture** (L1142). There: see stages. Hand to Deal is the same record; Records gets nothing.
- [x] ✅ **Sales daily: call-now queue** (L1142). There: Attention cards, swept every minute. [leads.py:172](../diwan/leads.py#L172), test: [test_leads.py](../tests/test_leads.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **Sales daily: broker sweep 08:30** (L1142). There: each broker's appointment list, an hour before opening (09:00 by default). Needed: the time as a setting; full sweep of their leads. [reminders.py:113](../diwan/agents/reminders.py#L113), test: [test_calendar.py](../tests/test_calendar.py)
- [x] ✅ **Sales daily: follow-ups** (L1142). There: `nudge.sweep`. [app.py:74](../diwan/app.py#L74), test: [test_nudge.py](../tests/test_nudge.py), browser: [quiet_flow.py](../e2e/quiet_flow.py)
- [ ] 🟡 **Sales daily: listing availability checks** (L1142). There: a staleness mark and a manual re-confirm; the feed sync every 30 minutes if set. Needed: a daily check that asks. [knowledge.py:71](../diwan/knowledge.py#L71), [app.py:82](../diwan/app.py#L82)
- [ ] 🟡 **Sales weekly: quiet clients** (L1142). There: handled by the minute by follow-ups. Needed: a weekly list. [nudge.py:265](../diwan/agents/nudge.py#L265)
- [ ] ❌ **Sales weekly: listing-to-buyer matches, seller reports** (L1142). Needed: both.
- [ ] ❌ **Sales monthly: renewals due in 90 days** (L1142). Needed: the job.
- [ ] 🟡 **Deal: checklist to ready for transfer** (L1143). There: all but the end event; starts on Convert. Needed: `deal.ready_for_transfer`, and `listing.signed` as a start.
- [ ] 🟡 **Deal daily: missing items and follow-up ladder** (L1143). There: document reminders. Needed: the ladder and a missing-items list. [app.py:72](../diwan/app.py#L72), test: [test_desk_rules.py](../tests/test_desk_rules.py)
- [ ] 🟡 **Deal weekly: deals stuck by days in stage** (L1143). There: a KPI worked out when opened; by last step done. Needed: a weekly job, by stage. [desk_kpis.py:65](../diwan/desk_kpis.py#L65)
- [ ] ❌ **Deal monthly: Form A and document expiries** (L1143). Needed: the job.
- [ ] 🟡 **Compliance: KYC to cleared / needs info / blocked** (L1144). There: screening, source-of-funds view. Needed: risk rating, EDD, the three endings, a start on `payment.marked_received`.
- [ ] 🟡 **Compliance daily: hits and holds for the officer** (L1144). There: shown in the morning brief as open tasks and checks. Needed: a hits list; holds don't exist. [nova.py:524](../diwan/agents/nova.py#L524)
- [ ] ❌ **Compliance weekly: re-screen open Cases** (L1144). Needed: the job. Screening runs once per person.
- [ ] ❌ **Compliance monthly: report drafts, threshold review, document retention** (L1144). Needed: the job.
- [ ] 🟡 **Finance: draft to payout** (L1145). There: draft, send, mark received, receipt, other-agency split. Needed: approve step, reminders, broker payout.
- [ ] 🟡 **Finance daily: due today, overdue, mark received** (L1145). There: shown on the Deal desk when opened. Needed: a daily list. [finance.py:65](../diwan/agents/finance.py#L65), browser: [deal_flow.py](../e2e/deal_flow.py)
- [ ] ❌ **Finance weekly: chasing list** (L1145). Needed: the job.
- [ ] ❌ **Finance monthly: close the month, payouts, VAT figures** (L1145). Needed: the job.
- [ ] 🟡 **Operations: form to handover** (L1146). There: Form F, ticks, closing, move-out task. Needed: trigger events, booking, handover.
- [ ] ❌ **Operations daily: today's appointments, drafts to submit** (L1146). Needed: a list; the calendar covers viewings only.
- [ ] ❌ **Operations weekly: waiting-on-outsiders aging** (L1146). Needed: the job. `waiting_on` is free text.
- [ ] ❌ **Operations monthly: permit renewals due** (L1146). Needed: the job.
- [ ] 🟡 **Review: check to passed or sent back** (L1147). There: Fact-staleness check only. Needed: numbers, completeness, authority, promises, holds; a card. [review.py:67](../diwan/agents/review.py#L67)
- [ ] ❌ **Review daily: queue under the owner's time limit** (L1147). Needed: the queue and limit.
- [ ] ❌ **Review weekly: send-back patterns to the Lobby** (L1147). Needed: the job.
- [ ] 🟡 **Records: file, index, answer, report, raise** (L1148). There: filing and answers. Needed: reports and raising. [records.py:124](../diwan/agents/records.py#L124), test: [test_records.py](../tests/test_records.py)
- [ ] ❌ **Records starts on every event** (L1148). Needed: a subscriber; it reads on request.
- [ ] ❌ **Records daily: expiry and renewal scan** (L1148). Needed: the job.
- [ ] ❌ **Records: Monday report, monthly funnel, speed, money, per-broker numbers** (L1148). Needed: both. Deal KPIs exist on demand. [desk_kpis.py](../diwan/desk_kpis.py)
- [ ] ❌ **Records yearly: retention clean-up approved by the officer** (L1148). Needed: the job.
- [ ] ❌ **Lobby: thread to keep or roll back** (L1149). Needed: the whole room.
- [ ] ❌ **Lobby daily, weekly, monthly jobs** (L1149). Needed: all of them.
- [ ] ❌ **Idle or dead-end departments show on the Stuck board** (L1151). Needed: the board and a flow check.

<a id="part-b"></a>

## Part B: Front Desk, PAs and access

How this was checked: every line below comes from reading the working tree. For Nova's words, the seeded demo office was also run in memory, with no model plugged in, by typing the spec's own example sentences into `nova.converse` (rules path, nothing in the repo or the live office touched). Quoted replies are from that run. A plugged-in model only changes how `route` picks a specialist; it adds no travel, email, reminder or mode behaviour.

The short version: there is one assistant, Nova, on owner-only pages. No staff member has a PA today: `index.html`, `office3d.html` and every `/api/nova/*` route are closed to them, and a test asserts it. Nova has no modes.

### Room 1 · Front Desk: the owner's PA (L40-84)

**The room itself**

- [x] 🧪 **Knows the whole office** (L42). There: Nova reads the one graph and does rounds of six department leads. [nova.py:488](../diwan/agents/nova.py#L488), [nova.py:491](../diwan/agents/nova.py#L491), test: [test_frontdesk.py](../tests/test_frontdesk.py#L73). No browser check of the rounds; Marketing is not one of the six leads.
- [ ] 🟡 **Turns anything the owner says into Tasks for the right room** (L42). There: "Tell Priya…" becomes a Lobby card and a Task; "Prepare Form F…" routes to a specialist. Anything else gets "Which team should take this?" and no Task. [lobby.py:146](../diwan/agents/lobby.py#L146), [nova.py:383](../diwan/agents/nova.py#L383). Needed: a catch-all that makes a Task once a team is picked; today the option buttons on `index.html` just resend the sentence with the option in brackets ([index.html:55](../web/index.html#L55)).
- [ ] ❌ **Speaks for the owner only when allowed** (L42). Needed: a per-recipient setting for what Nova may say in the owner's name; nothing sends in the owner's name today.
- [x] 🧪 **Rania stays client-facing, in Sales** (L42). There: charter puts Rania under the Sales lead; Nova never messages clients. [charters.py:55](../diwan/agents/charters.py#L55), test: [test_reception.py](../tests/test_reception.py).

**Modes**

- [ ] ❌ **Nova always knows her mode and shows it on screen** (L44). Needed: a `mode` per person (event `mode.changed`), read by `nova.converse`, shown as a chip on `office3d.html` and `index.html`. No mode concept exists in the code.
- [ ] ❌ **Arrival: fires on first open of the day** (L48). There: nothing fires; the owner presses "Play briefing". [office3d.html:921](../web/office3d.html#L921). Needed: a per-person "greeted today" record and auto-start on the first page load after midnight Dubai time.
- [ ] 🟡 **Arrival: fires on "good morning"** (L48). There: "good morning" gets a greeting and a count ("Good afternoon, Layla. All good here. Nothing needs you right now."), not the brief. [nova.py:273](../diwan/agents/nova.py#L273). Needed: first-of-day greeting leads into the brief.
- [x] 🧪 **Greets by name, by time of day** (L48). There: "Good morning, Layla. 3 things need you." [nova.py:543](../diwan/agents/nova.py#L543), test: [test_frontdesk.py](../tests/test_frontdesk.py#L94). Wording is formal rather than "Morning, Khalid".
- [ ] 🟡 **Says what needs the owner and by when ("Two things need you before 11")** (L48). There: a count only. Needed: the earliest due time in the greeting.
- [ ] ❌ **Leads with the top 3, never a wall of text** (L48). There: `brief()` reads every line, then every department. [nova.py:547](../diwan/agents/nova.py#L547). Needed: rank, cut to 3, the rest behind "more".
- [ ] 🟡 **Brief mode on "what's going on?"** (L49). There: "brief me" / "what's new" / "what's happening" work, but "what's going on?" got "Which deal do you mean…". [nova.py:199](../diwan/agents/nova.py#L199). Needed: add the phrase; test it.
- [ ] ❌ **Never repeats what the owner already dismissed** (L49). Needed: a dismiss action (event `brief.dismissed`) and a filter in `brief()`; the `since` argument exists but no caller passes it.
- [ ] ❌ **Meeting mode: trigger "Hey Pocket"** (L50). There: "Hey Pocket" is treated as small talk ("All good here. 8 things need you"). Needed: wake-phrase handling. No "pocket" anywhere in the code.
- [ ] ❌ **Meeting mode: trigger "I'm in a meeting"** (L50). There: reply was "Which team should take this?". Needed: intent that opens a meeting session.
- [ ] ❌ **Meeting mode: trigger from a calendar event marked meeting** (L50). Needed: a "meeting" flag on calendar entries and a sweep that switches mode at start time.
- [ ] 🟡 **Meeting mode: goes silent, listens and transcribes** (L50). There: the Meeting page listens and transcribes live, but it is a broker's table phone tied to one deal, not Nova, and only Sales and the owner can open it. [meeting.html:86](../web/meeting.html#L86), [app.py:812](../diwan/app.py#L812), test: [test_scribe.py](../tests/test_scribe.py#L78). Needed: an owner session not tied to a deal.
- [ ] ❌ **Meeting mode: speaks only to its wake word** (L50). Needed: wake-word detection in the transcript stream and a text answer path.
- [x] 🧪 **Meeting mode: never interrupts, voice-replies or sends during the meeting** (L50). There: true by absence: the Meeting page has no way to speak or send until it ends. [meeting.html:69](../web/meeting.html#L69). No test states it.
- [ ] 🟡 **After a meeting: summary** (L50). There: a visit summary of the client's turns only (interest, liked, worries, budget, next step), with quotes. [visit.py:59](../diwan/agents/visit.py#L59), [visit.py:95](../diwan/agents/visit.py#L95), test: [test_calendar.py](../tests/test_calendar.py#L168), browser: [visit_flow.py](../e2e/visit_flow.py). Needed: a summary of the whole meeting, including what the staff said; the Meeting page does not show the summary it gets back.
- [ ] ❌ **After a meeting: decisions** (L50). Needed: a decisions list on `meeting.ended`, each with its quote.
- [ ] ❌ **After a meeting: action items with owners, each linked to exact quotes** (L50). Needed: extraction in the end-meeting path ([app.py:800](../diwan/app.py#L800)) that calls `office.add_task` with an owner and the quote's Fact id.
- [ ] 🟡 **Ask: answers from Records** (L51). There: numbers and documents go to the Records team; pipeline too. [records.py:124](../diwan/agents/records.py#L124), test: [test_records.py](../tests/test_records.py). But plain questions fail: "How's the Marina deal?" returned "I don't have that in the office's records", and "Who hasn't called Sara back?" the same. Needed: a broader question reader (see L798).
- [ ] 🟡 **Ask: answers from the calendar** (L51). There: only a count and list of booked viewings. [nova.py:314](../diwan/agents/nova.py#L314). Needed: "what's on Thursday", the owner's own meetings, free times.
- [x] ✅ **Ask: answers from the Case log** (L51). There: facts, tasks, cards and what changed, with history. [nova.py:106](../diwan/agents/nova.py#L106), test: [test_nova.py](../tests/test_nova.py#L78), browser: [deal_flow.py:130](../e2e/deal_flow.py#L130).
- [ ] ❌ **Ask: answers from the web** (L51). Needed: a search tool for Nova with cited results; her charter says "The office's own records only" ([charters.py:38](../diwan/agents/charters.py#L38)).
- [x] ✅ **Ask: says where the answer came from** (L51). There: every answer carries record ids, shown as chips. [nova.py:252](../diwan/agents/nova.py#L252), [index.html:57](../web/index.html#L57), test: [test_nova.py](../tests/test_nova.py#L117), browser: [deal_flow.py:130](../e2e/deal_flow.py#L130).
- [x] 🧪 **Ask: never guesses a number; says "not recorded"** (L51). There: "I don't have that in the office's records", period questions ask back, unsupported model answers are hidden. [nova.py:232](../diwan/agents/nova.py#L232), [records.py:75](../diwan/agents/records.py#L75), test: [test_nova.py](../tests/test_nova.py#L97), [test_records.py](../tests/test_records.py#L46). Words differ from the spec's "not recorded".
- [ ] ❌ **Errand: "Check ticket prices"** (L52). There: "Which team should take this?". Needed: errand runner with search.
- [ ] ❌ **Errand: "book the vacation"** (L52). Same reply. Needed: as L66.
- [ ] ❌ **Errand: "email Ahmed"** (L52). Same reply. Needed: as L67.
- [ ] ❌ **Errand: shows the plan and the exact message or booking** (L52). Needed: an errand card (event `errand.drafted`) with a preview.
- [x] 🧪 **Errand: waits for the owner's yes** (L52). There: the one thing Nova drafts for a person, the Lobby card, is read back and posts only on yes. [lobby.py:118](../diwan/agents/lobby.py#L118), test: [test_frontdesk.py](../tests/test_frontdesk.py#L32), browser: [office_flow.py:103](../e2e/office_flow.py#L103). Applies to Lobby cards only until errands exist.
- [x] 🧪 **Errand: never pays, books, sends or signs without a yes** (L52). There: Nova has no such tool, and submit, approve, release and file are refused and logged. [nova.py:54](../diwan/agents/nova.py#L54), test: [test_nova.py](../tests/test_nova.py#L144). No browser check of the refusals. "Sign" is not refused (see L1051).
- [ ] ❌ **Do not disturb: on the owner's word** (L53). There: "do not disturb" got "Which team should take this?". Needed: a DND setting per person.
- [ ] ❌ **Do not disturb: after hours** (L53). Needed: per-person hours. The only quiet hours are the client-facing ones. [nudge.py:73](../diwan/agents/nudge.py#L73).
- [ ] ❌ **Do not disturb: queues everything except urgent; no pings for routine** (L53). Needed: a hold-and-release queue in `leads.notify`, which sends every notice at once. [leads.py:474](../diwan/leads.py#L474).

**Morning brief**

- [ ] 🟡 **Built at 7:30 Dubai time** (L55). There: rounds run 30 minutes before the earliest person's briefing time; the default time is 09:00, so 08:30. [app.py:66](../diwan/app.py#L66), [nova.py:558](../diwan/agents/nova.py#L558), test: [test_frontdesk.py](../tests/test_frontdesk.py#L86). Needed: default 07:30 for the brief itself. Only the department round is prepared; the lines are composed when read. `test_nova.py` still names seven o'clock.
- [ ] ❌ **On working days only** (L55). There: runs every day, Fridays and weekends too. Needed: a working-days check in `briefing_due`. [nova.py:565](../diwan/agents/nova.py#L565).
- [x] 🧪 **Ready before the owner arrives** (L55). There: `briefing.ready` is logged by the loop. [nova.py:502](../diwan/agents/nova.py#L502). `nova.morning()`, which would log each person's brief, is never called ([nova.py:579](../diwan/agents/nova.py#L579)). No test.
- [ ] 🟡 **Urgent: anything overdue** (L57). There: Lobby cards that are late only. [nova.py:519](../diwan/agents/nova.py#L519), test: [test_frontdesk.py](../tests/test_frontdesk.py#L53). Needed: overdue Tasks, Attention cards and payments in the brief.
- [ ] 🟡 **Urgent: any Compliance flag** (L57). There: open checks reach the owner only as a department line after rounds, in Compliance's sentence, not first. [nova.py:471](../diwan/agents/nova.py#L471), test: [test_frontdesk.py](../tests/test_frontdesk.py#L82). Needed: lead with them.
- [ ] ❌ **Urgent: any payment due today** (L57). There: on the Deal desk overview only. [deal_desk.py:249](../diwan/deal_desk.py#L249). Needed: a brief line.
- [ ] ❌ **Urgent: any client who asked for a call and has not had one** (L57). There: Attention cards exist; the brief does not read them. [leads.py:128](../diwan/leads.py#L128). Needed: add to `brief()`.
- [ ] ❌ **Urgent comes first** (L57). There: order is by card type, then departments. Needed: a severity sort.
- [ ] ❌ **Today: meetings and viewings** (L58). There: no calendar in the owner's brief; brokers get a separate notice. [reminders.py:109](../diwan/agents/reminders.py#L109). Needed: today's appointments in `brief()`.
- [ ] ❌ **Today: each client's last message and what they care about** (L58). Needed: pull from the chat and the qualify state.
- [ ] ❌ **Pipeline: new leads since yesterday** (L59). Needed: count from `lead.*` events since the last brief.
- [ ] ❌ **Pipeline: hot leads** (L59). Needed: from the deal's `hot` prop.
- [ ] ❌ **Pipeline: deals that moved stage** (L59). Needed: from `stage.changed` events.
- [ ] 🟡 **Pipeline: deals stuck more than N days (owner sets N)** (L59). There: computed on the Deal desk KPIs, N is an owner setting (`stuck_days`, 7), and not in the brief. [desk_kpis.py:64](../diwan/desk_kpis.py#L64), [desk_rules.py:29](../diwan/desk_rules.py#L29). Needed: brief line.
- [ ] ❌ **Money: invoices sent** (L60). Needed: brief section from the invoice events.
- [ ] ❌ **Money: payments marked received** (L60). Needed: as above.
- [ ] ❌ **Money: commissions due** (L60). Needed: as above, from [finance.py:125](../diwan/agents/finance.py#L125).
- [ ] 🟡 **Decisions waiting, one line each** (L61). There: open cards addressed to the owner appear with their text. [nova.py:511](../diwan/agents/nova.py#L511). Needed: all approvals in Review, not only cards naming the owner.
- [ ] ❌ **Approve / send back button in the brief** (L61). There: chips only on `index.html`; the buttons live on the Deal desk ([deal_desk.py:369](../diwan/deal_desk.py#L369)). Needed: buttons in the brief calling the same route.
- [ ] ❌ **One idea from the Lobby, if relevant** (L62). There: the code's "Lobby board" is a list of work requests, not ideas. [lobby.py:1](../diwan/agents/lobby.py#L1). Needed: an idea source and one brief line.

**Errands Nova can run**

- [ ] ❌ **Each errand ends in a draft the owner approves** (L64). Needed: the errand card from L52.
- [ ] ❌ **Travel: search flights and hotels for dates and a budget** (L66). Needed: a travel provider or browser tool.
- [ ] ❌ **Travel: compare 3 options** (L66). Needed: comparison card.
- [ ] ❌ **Travel: hold if the site allows; the owner pays** (L66). Needed: as above, stopping before pay.
- [ ] ❌ **Travel: read "this email", pull names and dates, confirm back before searching** (L66). There: "Book my trip from this email" got "Which team should take this?". Needed: email read access, then a read-back. Blocked by the L81 question.
- [ ] ❌ **Email and messages: draft replies in the owner's style** (L67). There: "Draft a reply to Ahmed" got "Which team…". Needed: mailbox connection and a style sample.
- [ ] ❌ **Email and messages: schedule sends** (L67). Needed: scheduled send. Only studio posts are scheduled.
- [ ] 🟡 **Email and messages: chase people who have not answered** (L67). There: Lobby cards are chased an hour before due; clients get follow-ups. [lobby.py:175](../diwan/agents/lobby.py#L175), test: [test_frontdesk.py](../tests/test_frontdesk.py#L53). Needed: chasing emails and outsiders.
- [ ] ❌ **Calendar: book, move, decline for the owner** (L68). There: brokers' calendar only, on the Calendar page; Nova cannot touch it. Needed: Nova tools and an owner calendar.
- [ ] 🟡 **Calendar: protect focus time** (L68). There: people can add busy blocks by hand. [app.py:1605](../diwan/app.py#L1605). Needed: Nova sets them.
- [ ] ❌ **Calendar: add travel time between viewings** (L68). Needed: gap rule in `slots`.
- [ ] ❌ **Research: prices** (L69). Needed: Nova web search with citations.
- [ ] ❌ **Research: competitor listings** (L69). Needed: as above. The studio's competitor watch is Instagram only and not reachable from Nova.
- [ ] ❌ **Research: a developer's track record** (L69). Needed: as above.
- [ ] ❌ **Research: a news item about a project** (L69). Needed: as above.
- [ ] ❌ **On the laptop or phone: open a file, find a document, fill a form** (L70). There: "find a document" works inside the archive only. Needed: a desktop or browser agent.
- [ ] ❌ **Stops before any Submit, Pay or Send on a device** (L70). Needed: arrives with the above. The office's own Form F does stop before Submit ([operations.py:64](../diwan/agents/operations.py#L64)).
- [ ] ❌ **Reminders: "remind me Thursday to call Sara" becomes a Task with a due time** (L71). There: "Which team should take this?", no Task. Lobby's `DELEGATE` even matches "remind X" but needs a named person other than "me". [lobby.py:25](../diwan/agents/lobby.py#L25). Needed: "remind me" intent, a Task for the speaker with `due`.

**What Front Desk emits**

- [x] ✅ **`task.created` to any room from the owner's instructions** (L75). There: from route and from Lobby posts. [nova.py:424](../diwan/agents/nova.py#L424), [lobby.py:157](../diwan/agents/lobby.py#L157), test: [test_nova.py](../tests/test_nova.py#L130), browser: [office_flow.py:97](../e2e/office_flow.py#L97).
- [ ] ❌ **`task.created` from meeting action items** (L75). Needed: as L50.
- [ ] ❌ **`fact.recorded` when the owner relays what a client said** (L76). There: "Sara now wants 3 beds, not 2" got "Which team…"; no Fact. Needed: intent that calls `office.record_fact` with the owner as source. The code's event is `fact.created`.
- [ ] ❌ **That relayed Fact can trigger the correction rule** (L76). Needed: follows from the line above; the rule itself exists in [scribe.py:142](../diwan/agents/scribe.py#L142).
- [ ] ❌ **`approval.given` when the owner decides from the brief** (L77). There: approval exists, on the desk only. Needed: buttons in the brief (L61).
- [ ] ❌ **`approval.declined` from the brief** (L77). There: no such event; `approval.refused` means a stale one was blocked. [events.py:15](../diwan/events.py#L15). Needed: the event or an agreed mapping to `review.returned`.

**Open questions**

- [ ] ❓ **Which email and calendar does the owner use?** (L81). Needs the office's answer: Gmail or Outlook. Current default: none connected; `/api/calendar.ics` exports a file one way ([app.py:1529](../diwan/app.py#L1529)); Zoom links exist ([zoom.py](../diwan/providers/zoom.py)).
- [ ] ❓ **Voice replies on the phone, or text only?** (L82). Needs the office's answer. Current default: `office3d.html` speaks through the browser; no phone app.
- [ ] ❓ **Who else may talk to Nova, and what may they not see?** (L83). Needs the office's answer. Current default: the owner only (the gate), and the owner can pick any name in "I am" and "Speaking as".

### A PA for every staff member (L385-400)

- [ ] ❌ **Every signed-in person gets their own PA** (L387). There: `/api/nova/*` and `index.html` are not in the staff lists, so they are owner-only, and a test asserts it. [access.py:49](../diwan/access.py#L49), [access.py:53](../diwan/access.py#L53), [test_access.py:112](../tests/test_access.py#L112). Needed: open the routes to staff with scoped answers, then change that test.
- [ ] 🟡 **Nova stays the owner's PA** (L387). There: Nova is the owner's on the screens, but her code still briefs everyone, and owner logic is hard-coded to `layla`. [nova.py:285](../diwan/agents/nova.py#L285), [nova.py:537](../diwan/agents/nova.py#L537). Needed: use `access.is_owner`.
- [ ] ❌ **"Omar's PA", "Layla's PA" and so on exist as named things** (L387). Needed: a PA identity per person.
- [ ] ❌ **"Ask Nova…" box becomes "Ask your PA"** (L387). There: still "Ask Nova, or tell her who needs to do what…". [office3d.html:109](../web/office3d.html#L109). `inbox.html` also links brokers to "Ask Nova" on a page that sends them away ([inbox.html:671](../web/inbox.html#L671)).
- [ ] ❌ **The box talks to the signed-in person's PA** (L387). There: the box has an "I am" picker defaulting to Layla. [office3d.html:846](../web/office3d.html#L846), [office3d.html:915](../web/office3d.html#L915). Needed: use `SESSION.person`.
- [ ] ❌ **Identity: one PA per staff account, named by the person** (L393). Needed: `pa_name` setting, default "[Name]'s PA".
- [ ] ❌ **Identity: voice and tone set per person** (L393). Needed: person settings; voice today is one fixed browser voice list.
- [x] 🧪 **Scope: acts only as the signed-in person** (L387). There: the gate rewrites `by`, `person`, `as` on every staff request. [access.py:355](../diwan/access.py#L355), test: [test_access.py:118](../tests/test_access.py#L118). Browser checks run with the gate off.
- [ ] ❌ **Scope: PA sees only what the role allows** (L394). There: `nova.ask` reads the whole graph for any `person`: as Omar, it answered "How much does Karim earn?" and any deal. [nova.py:208](../diwan/agents/nova.py#L208). Needed: a scope filter on graph reads before staff get a PA.
- [ ] ❌ **Scope: never another broker's clients unless shared or a lead** (L394). There: `/api/chats` with the default "all" view, `/api/chats/{phone}`, `/api/deals` and `/api/desk/*` return every client to every broker. [app.py:959](../diwan/app.py#L959), [inbox.py:119](../diwan/inbox.py#L119), [app.py:667](../diwan/app.py#L667). Needed: per-broker filters and a "shared" flag; tests.
- [ ] 🟡 **On call: chat box on every page** (L395). There: chat box on `office3d.html` and `index.html` only (owner); Maya has a separate Marketing lead chat in the studio. [mchat.js](../web/mchat.js). Needed: a box in `app.js`'s `header()`.
- [ ] 🟡 **On call: push-to-talk on the phone** (L395). There: a mic button in the browser on `office3d.html`, owner only. [office3d.html:109](../web/office3d.html#L109). Needed: for staff, on a phone layout.
- [ ] ❌ **On call: optional wake word on desktop** (L395). Needed: wake-word listener.
- [ ] 🟡 **On call: WhatsApp to the person's own number** (L395). There: one way only: notices go out by template when a number and `NOTIFY_TEMPLATE` are set; a staff reply goes nowhere. [leads.py:474](../diwan/leads.py#L474). Needed: inbound from a staff number routed to their PA.
- [ ] 🟡 **Morning: a short brief for that person only** (L396). There: `brief(person)` works for each person but no staff screen can open it. [nova.py:506](../diwan/agents/nova.py#L506), test: [test_nova.py](../tests/test_nova.py#L166). Needed: a route and a place on their home page.
- [ ] 🟡 **Morning: their calls** (L396). There: Attention cards show in the Inbox, not the brief. Needed: brief line.
- [ ] 🟡 **Morning: their viewings** (L396). There: a morning notice of the day's appointments, brokers only. [reminders.py:109](../diwan/agents/reminders.py#L109), test: [test_calendar.py](../tests/test_calendar.py#L133). Needed: inside the brief.
- [x] 🧪 **Morning: Tasks due and items waiting on them** (L396). There: cards and Tasks with `needs_person`. [nova.py:511](../diwan/agents/nova.py#L511), [nova.py:524](../diwan/agents/nova.py#L524), test: [test_nova.py](../tests/test_nova.py#L166). Note it reads stored `who`, not `roles.current`, so work does not follow a reassigned role here.
- [ ] 🟡 **Morning: anything a lead assigned overnight** (L396). There: Lobby cards addressed to them. Needed: a since-yesterday filter, and any Task, not only Lobby ones.
- [ ] ❌ **Doing: drafts for the person through the PA** (L397). There: drafts exist per feature (follow-ups, Form F, invoices), none reachable through a staff PA. Needed: PA tools over them.
- [ ] ❌ **Doing: schedules** (L397). Needed: as above.
- [ ] 🟡 **Doing: reminds** (L397). There: Lobby chase; no self-reminders. Needed: L71 for staff.
- [ ] 🟡 **Doing: fills forms up to Submit** (L397). There: Form F plan fills from Facts and stops. [operations.py:64](../diwan/agents/operations.py#L64), test: [test_deal_desk.py](../tests/test_deal_desk.py#L182). Needed: a real portal; PA access.
- [ ] 🟡 **Doing: searches Records** (L397). There: through Nova, for the owner. Needed: staff access, scoped.
- [ ] 🟡 **Doing: asks before sending anything to a client** (L397). There: broker follow-ups wait for a person. [followup.py:116](../diwan/agents/followup.py#L116), test: [test_followup.py](../tests/test_followup.py). Rania and the documents reminder send on their own by design (see Conflicts).
- [x] ✅ **Doing: never approves on the person's behalf** (L397). There: refused in Nova; approval needs the named approver. [nova.py:58](../diwan/agents/nova.py#L58), test: [test_deal_desk.py](../tests/test_deal_desk.py#L33), browser: [deal_flow.py](../e2e/deal_flow.py).
- [ ] 🟡 **Handoff: "Tell Finance the deposit came in" creates a Task or Event for Finance** (L398). There: works, owner only, as a Lobby card, but asks "By when should Ahmed have 'The deposit came in' done?" as if it were an order. [lobby.py:71](../diwan/agents/lobby.py#L71), test: [test_frontdesk.py](../tests/test_frontdesk.py#L64). Needed: telling versus asking; staff access.
- [ ] ❌ **Handoff: Finance's PA picks it up** (L398). Needed: PAs. Today it waits for Ahmed, who cannot reach `/api/lobby` at all; only the owner's "Mark done as Ahmed" closes it ([office3d.html:904](../web/office3d.html#L904)).
- [x] 🧪 **Handoff: no PA-to-PA messages; everything on the log** (L398). There: Lobby posts and Tasks are events; no direct channel exists. [lobby.py:150](../diwan/agents/lobby.py#L150), test: [test_frontdesk.py](../tests/test_frontdesk.py#L32).
- [ ] 🟡 **Escalation: overdue Task nudges the person first** (L399). There: Attention cards and Lobby cards only, not Tasks in general. [leads.py:187](../diwan/leads.py#L187), [lobby.py:186](../diwan/agents/lobby.py#L186), test: [test_leads.py](../tests/test_leads.py#L101). Needed: a Task sweep.
- [ ] ❌ **Escalation: then the room lead's PA** (L399). There: skipped: an overdue card goes straight to the broker and `layla`; Rashid is not told. [leads.py:191](../diwan/leads.py#L191). Needed: a chain step.
- [ ] 🟡 **Escalation: then Nova (owner)** (L399). There: the owner is told for Attention cards, and the asker for Lobby cards. Needed: general Tasks.
- [ ] 🟡 **Memory: preferences kept as settings, not loose notes** (L400). There: `briefing_time` per person, set by talking or a control; brokers' shift, days, away and phone set by the owner. [nova.py:573](../diwan/agents/nova.py#L573), [leads.py:53](../diwan/leads.py#L53). Needed: "call me before 10", "I don't do Sundays" captured from speech, per person, with a staff-readable page.

### Who sees which rooms (L402-413)

How the code maps: a "room" is a page plus API prefixes in [access.py:49](../diwan/access.py#L49). Access is by **department**, with no row or field filter. All pytest; the browser checks run with `DIWAN_AUTH=off`.

- [x] 🧪 **Owner: all nine rooms** (L406). There: `is_owner` passes every page and route. [access.py:98](../diwan/access.py#L98), test: [test_access.py:105](../tests/test_access.py#L105).
- [ ] ❌ **Broker · Front Desk: own brief** (L407). There: 403 on `/api/nova/brief`. Needed: open the route, own id only (add to `OWN_PATH`). Same fix for every "Own brief" cell below.
- [ ] 🟡 **Broker · Sales: own leads** (L407). There: can open Sales; sees all leads. [inbox.py:119](../diwan/inbox.py#L119). Needed: filter to own, plus the Pool.
- [ ] 🟡 **Broker · Deal: own deals** (L407). There: can open the desk; sees all deals. [deal_desk.py:308](../diwan/deal_desk.py#L308). Needed: filter.
- [ ] 🟡 **Broker · Ops: status only** (L407). There: full task content comes back from `/api/desk/deals/{deal}`. [deal_desk.py:346](../diwan/deal_desk.py#L346). Needed: a done/blocked projection.
- [ ] 🟡 **Broker · Finance: own commission** (L407). There: `/api/desk/kpis` and every deal's `commission` are open to all Sales. [deal_desk.py:707](../diwan/deal_desk.py#L707). Needed: own only.
- [ ] 🟡 **Broker · Compliance: status only** (L407). There: not status: screenings, source of funds and checks come back in full, and `check.` events are in the Sales event list. [access.py:66](../diwan/access.py#L66). Needed: strip contents. The broker also reads the file a client must not be tipped off about.
- [ ] ❌ **Broker · Review: own items** (L407). There: no Review room or filter for staff; review events flow unfiltered. Needed: a filtered view.
- [ ] ❌ **Broker · Records: own numbers** (L407). There: Records answers go through Nova, closed to staff. Needed: scoped route.
- [ ] ❌ **Broker · Lobby: read** (L407). There: `/api/lobby` is owner-only. Needed: add it; decide which "Lobby" this means (see Conflicts).
- [ ] ❌ **Sales lead · Front Desk: own brief** (L408). As above. Rashid's brief is empty today ("Nothing needs you").
- [x] 🧪 **Sales lead · Sales: all leads** (L408). There: `department()` maps Sales manager to Sales. [access.py:82](../diwan/access.py#L82), test: [test_access.py:99](../tests/test_access.py#L99).
- [x] 🧪 **Sales lead · Deal: all deals** (L408). There: `/api/desk/` is open to Sales. [access.py:61](../diwan/access.py#L61). No test for Rashid specifically.
- [ ] 🟡 **Sales lead · Ops: status only** (L408). There: full content. Needed: as broker.
- [ ] 🟡 **Sales lead · Finance: team commission** (L408). There: all of it, plus nothing to separate team from office. Needed: the team definition and a filter.
- [ ] 🟡 **Sales lead · Compliance: status only** (L408). There: full content. Needed: as broker.
- [ ] ❌ **Sales lead · Review: team items** (L408). Needed: filtered view.
- [ ] ❌ **Sales lead · Records: team numbers** (L408). Needed: scoped route.
- [ ] ❌ **Sales lead · Lobby: read, propose** (L408). There: closed; the only "propose" is a Knowledge change proposal. Needed: an idea route.
- [ ] ❌ **Deal / Ops staff · Front Desk: own brief** (L409). As above.
- [ ] ❌ **Deal / Ops staff · Sales: read** (L409). There: 403 on `/api/chats` and `inbox.html`. [access.py:58](../diwan/access.py#L58). Needed: read-only access for Ops.
- [x] 🧪 **Deal / Ops staff · Deal: all** (L409). There: `deal.html` and `/api/desk/`. [access.py:50](../diwan/access.py#L50), test: [test_access.py:80](../tests/test_access.py#L80) (for Compliance; Ops is not tested).
- [x] 🧪 **Deal / Ops staff · Ops: all** (L409). There: same page. No Ops-specific test.
- [ ] 🟡 **Deal / Ops staff · Finance: status only** (L409). There: amounts and payments in full; writes are role-checked. Needed: a status projection.
- [ ] 🟡 **Deal / Ops staff · Compliance: status only** (L409). There: full content. Needed: as above.
- [ ] ❌ **Deal / Ops staff · Review: own items** (L409). Needed: filtered view.
- [ ] ❌ **Deal / Ops staff · Records: deals** (L409). Needed: route.
- [ ] ❌ **Deal / Ops staff · Lobby: read** (L409). As above.
- [ ] ❌ **Finance · Front Desk: own brief** (L410). As above.
- [x] 🧪 **Finance · Sales: no** (L410). There: 403. [access.py:58](../diwan/access.py#L58), test: [test_access.py:80](../tests/test_access.py#L80) (signs in Priya; same rule). `ahmed` is not actually exercised.
- [ ] 🟡 **Finance · Deal: amounts** (L410). There: the entire deal with quotes and parties. Needed: an amounts-only view.
- [ ] 🟡 **Finance · Ops: no** (L410). There: Ops steps come in the same desk payload. Needed: strip them.
- [x] 🧪 **Finance · Finance: all** (L410). There: via `deal.html`. Role checks: [test_deal_desk.py](../tests/test_deal_desk.py#L156).
- [ ] 🟡 **Finance · Compliance: payment flags** (L410). There: full compliance content. Needed: flags only.
- [ ] ❌ **Finance · Review: own items** (L410). Needed: filtered view.
- [ ] ❌ **Finance · Records: money** (L410). Needed: route.
- [ ] ❌ **Finance · Lobby: read** (L410). As above.
- [ ] ❌ **Compliance officer · Front Desk: own brief** (L411). As above.
- [ ] ❌ **Compliance officer · Sales: read** (L411). There: 403, and a test asserts it. [test_access.py:80](../tests/test_access.py#L80). Needed: read-only route; change the test.
- [x] 🧪 **Compliance officer · Deal: read** (L411). There: can read; writes only for their role. [deal_desk.py:434](../diwan/deal_desk.py#L434). Can also hit other desk writes that do not check a role. No test.
- [x] 🧪 **Compliance officer · Ops: read** (L411). There: same page. No test.
- [x] 🧪 **Compliance officer · Finance: payments** (L411). There: payments in the deal view. Sees more than payments. No test.
- [x] ✅ **Compliance officer · Compliance: all** (L411). There: the Compliance tab, only Priya records. test: [test_deal_desk.py](../tests/test_deal_desk.py#L84), browser: [deal_flow.py:158](../e2e/deal_flow.py#L158).
- [ ] ❌ **Compliance officer · Review: own items** (L411). Needed: filtered view.
- [ ] ❌ **Compliance officer · Records: compliance files** (L411). Needed: route; compliance documents are not separated from others in `/media`, where any deal-team member may open `doc-`, `sig-` and `deal-` files ([access.py:348](../diwan/access.py#L348)).
- [ ] ❌ **Compliance officer · Lobby: read** (L411). As above.
- [ ] ❌ **"Status only" means done or blocked, not contents** (L413). Needed: one projection function. `Ledger.summary` ([deal_desk.py:176](../diwan/deal_desk.py#L176)) is close, but no route serves only that to these roles. `access.USER` is read only by the event filter, so no route can tell who is asking.

### Front Desk · Nova: blocks and command (L437-452)

- [ ] ❌ **Block: Today, with each client's last message** (L439). Needed: a Front Desk panel. `index.html` is a chat plus a feed; HQ shows agent counts only ([office3d.html:651](../web/office3d.html#L651)).
- [ ] 🟡 **Block: Urgent strip (overdue, Compliance flags, unanswered "call me", payments due)** (L439). There: pieces on the Deal desk and Inbox, none together. Needed: one strip.
- [ ] 🟡 **Block: Decisions waiting (approve / send back)** (L439). There: the Deal desk's work queue has them. [deal_desk.py:331](../diwan/deal_desk.py#L331). Needed: on Front Desk.
- [ ] 🟡 **Block: Pipeline at a glance by stage** (L439). There: Deal desk overview. [deal_desk.py:340](../diwan/deal_desk.py#L340). Needed: on Front Desk, with leads.
- [ ] 🟡 **Block: Money today** (L439). There: next 7 days and overdue on the desk. [deal_desk.py:265](../diwan/deal_desk.py#L265). Needed: today's figures on Front Desk.
- [ ] 🟡 **Block: Stuck list** (L439). There: stuck deals tile on the desk. [deal.html:337](../web/deal.html#L337), test: [test_desk_rules.py](../tests/test_desk_rules.py). Needed: on Front Desk.
- [ ] ❌ **Block: Errands in progress** (L439). Needed: errands first.
- [ ] ❌ **Block: Lobby idea of the day** (L439). Needed: idea source.
- [ ] ❌ **Block: Mode chip** (L439). Needed: modes first.
- [ ] 🟡 **Command 1: first open of the day, greeting and top 3** (L444). See L48. Needed: as there.
- [ ] 🟡 **Command 1: brief built from Events of the last 24 hours across all rooms** (L444). There: built from open state plus "done today", not a 24-hour window; Marketing is left out of the rounds. [nova.py:459](../diwan/agents/nova.py#L459), [nova.py:488](../diwan/agents/nova.py#L488). Needed: a window and Marketing.
- [ ] ❌ **Command 2: answers only to the wake phrase, records and transcribes** (L445). See L50.
- [ ] ❌ **Command 2: summary, decisions, action items linked to quotes; Tasks in the right rooms** (L445). See L50.
- [x] ✅ **Command 2: client statements become Facts and can trigger the correction rule** (L445). There: every meeting turn goes through the Scribe. [scribe.py:162](../diwan/agents/scribe.py#L162), test: [test_scribe.py](../tests/test_scribe.py#L35), browser: [deal_flow.py:65](../e2e/deal_flow.py#L65).
- [ ] 🟡 **Command 3: Ask from Records, calendar and Event log with the source; "not recorded"** (L446). See L51.
- [ ] ❌ **Command 4: travel search** (L447). See L66.
- [ ] ❌ **Command 4: email drafts** (L447). See L67.
- [ ] ❌ **Command 4: reminders** (L447). See L71.
- [ ] ❌ **Command 4: a Confirm button on each draft** (L447). There: Lobby read-back only, with Yes and Cancel options. Needed: errand cards.
- [ ] ❌ **Command 5: Do not disturb queues everything except Now** (L448). See L53.
- [ ] ❌ **Command: chat box on every page talks to the signed-in user's PA; Nova only for the owner** (L449). See L387, L395.
- [ ] 🟡 **Test: brief contents from a seeded day** (L450). There: per-person checks on a demo office. [test_nova.py](../tests/test_nova.py#L166). Needed: a seeded day that covers the six sections.
- [ ] ❌ **Test: meeting mode creates Tasks with quotes** (L450). Needed: after the feature.
- [x] 🧪 **Test: no send without confirm** (L450). There: for Lobby posts. [test_frontdesk.py](../tests/test_frontdesk.py#L32).

### Later: meeting agent and the 3D client space (L597-617)

Marked "later" by the spec. Nothing here blocks the loop.

- [ ] ❌ **Meeting agent: joins Zoom, Meet or Teams as "Diwan notes"** (L603). There: Zoom only creates a meeting link for a video viewing. [zoom.py](../diwan/providers/zoom.py). Needed: a meeting bot.
- [ ] ❌ **Meeting agent: only when the meeting owner adds it** (L603). Needed: as above.
- [ ] ❌ **Meeting agent: announces itself** (L603). Needed: as above.
- [x] ✅ **Recording consent is asked at the start** (L603). There: for the table phone, in English and Arabic; nothing is heard before it. [meeting.html:22](../web/meeting.html#L22), [app.py:817](../diwan/app.py#L817), test: [test_scribe.py](../tests/test_scribe.py#L23), browser: [visit_flow.py:93](../e2e/visit_flow.py#L93). Needs carrying to the online agent.
- [ ] 🟡 **Listens silently, transcribes, statements become Facts with quotes and timestamps, same pipeline as Scribe** (L604). There: the pipeline is ready and in-person works. [scribe.py:168](../diwan/agents/scribe.py#L168). Needed: online audio.
- [ ] ❌ **After the call: summary, decisions** (L605). Needed: see L50.
- [ ] ❌ **After the call: action items as Tasks in the right rooms** (L605). Needed: see L50.
- [x] ✅ **After the call: a follow-up draft for the broker** (L605). There: on ending a meeting. [app.py:807](../diwan/app.py#L807), [meeting.html:77](../web/meeting.html#L77), test: [test_followup.py](../tests/test_followup.py#L64), browser: [visit_flow.py](../e2e/visit_flow.py).
- [ ] ❌ **Quiet question in the side chat, from Facts, never by voice unless asked** (L606). Needed: a side-chat tool calling `nova.ask`.
- [ ] 🟡 **In-person and online meetings produce the same output** (L607). There: in-person only, and no Front Desk meeting mode to share. Needed: both built on one function.
- [ ] ❌ **3D showroom: reception with Rania** (L611). Needed: a client scene. `office3d.html` is the staff office.
- [ ] ❌ **3D showroom: project galleries** (L611). Needed: as above.
- [ ] ❌ **3D showroom: a viewing room per listing** (L611). Needed: as above.
- [ ] ❌ **3D showroom: a meeting room where a broker or the meeting agent joins** (L611). Needed: as above.
- [ ] ❌ **Clients enter by a link from WhatsApp or a post** (L612). Needed: a token route like `docs.html`.
- [ ] ❌ **No staff rooms, Tasks or Facts visible to clients there** (L612). Needed: a public scene with its own data route. The gate would close `office3d.html` to them today.
- [ ] ❌ **What a client says inside becomes a Fact on their Case** (L613). Needed: call `scribe.hear`.
- [ ] ❌ **Shares the 3D engine, not the data: separate scene and permission set** (L614). Needed: split the engine out of `office3d.html`, which holds it all in one page.
- [x] 🧪 **Keep in mind: one Facts pipeline for chat, calls, meetings** (L616). There: `scribe.hear` serves WhatsApp, portal leads and meetings. [reception.py:1136](../diwan/agents/reception.py#L1136), [leads.py:422](../diwan/leads.py#L422), [app.py:795](../diwan/app.py#L795), test: [test_scribe.py](../tests/test_scribe.py). Call notes do not pass through it.
- [x] 🧪 **Keep in mind: meetings write only through Events** (L616). There: start, consent, utterance and end are events. [office.py:56](../diwan/office.py#L56). The rule is by convention; nothing enforces it. No test.

### A day in each position (L792-808)

- [ ] 🟡 **Two-screen test: the usual thing never needs more than two screens** (L794). There: not measured; no e2e counts screens. Owner work spans `office3d`, `deal`, `inbox`; Rashid has no board. Needed: a checked list per person.

**Owner**

- [ ] 🟡 **08:00: Nova greets, top 3, brief: urgent, money, decisions** (L798). There: greeting and needs lines, on a button press; no top 3 or money. See L48, L60.
- [ ] 🟡 **Day: meetings in Pocket mode** (L798). There: Meeting page only; see L50.
- [x] ✅ **Day: approves from cards** (L798). There: on the Deal desk, not the brief. [deal_desk.py:369](../diwan/deal_desk.py#L369), test: [test_deal_desk.py](../tests/test_deal_desk.py#L33), browser: [deal_flow.py](../e2e/deal_flow.py).
- [ ] ❌ **Day: asks "how's the Marina deal?"** (L798). There: that exact sentence got "I don't have that in the office's records", though "Summarise the Marina deal" works ([nova.py:261](../diwan/agents/nova.py#L261)). Needed: add to `SUMMARY`; test it. This is the spec's headline example.
- [ ] ❌ **End of day: 2-line wrap: closed, stuck, tomorrow's first thing** (L798). Needed: an evening job and a line.
- [ ] ❌ **Unasked: prepares decisions with options** (L798). There: cards carry a question and buttons, but no options analysis. Needed: option drafting.
- [ ] 🟡 **Unasked: chases overdue staff Tasks** (L798). There: Lobby cards and Attention cards only. See L399.
- [ ] 🟡 **Unasked: flags anything legal or compliance** (L798). There: after rounds, as a department line. See L57.
- [x] 🧪 **Never: search for a document** (L798). There: ask Nova; the Archivist finds it. [records.py:103](../diwan/agents/records.py#L103), test: [test_records.py](../tests/test_records.py#L39).
- [x] ✅ **Never: retype a client's words** (L798). There: quotes are stored once. test: [test_scribe.py](../tests/test_scribe.py#L35), browser: [deal_flow.py:65](../e2e/deal_flow.py#L65).
- [x] ✅ **Never: approve something without seeing what it rests on** (L798). There: `rests_on` on tasks; stale approvals refused. [deal_desk.py:72](../diwan/deal_desk.py#L72), test: [test_nova.py](../tests/test_nova.py#L59), browser: [deal_flow.py](../e2e/deal_flow.py).

**Broker (Omar)**

- [ ] 🟡 **08:00: Omar's PA: calls to make** (L799). There: the Inbox "attention" tab. [inbox.py:130](../diwan/inbox.py#L130). Needed: in a PA brief.
- [ ] 🟡 **08:00: viewings** (L799). There: morning notice. See L396.
- [ ] 🟡 **08:00: quiet clients** (L799). There: Inbox shows the follow-up state and Nurture tab. Needed: a list in the brief.
- [ ] 🟡 **08:00: call-now items** (L799). There: same tab. Needed: in the brief.
- [ ] 🟡 **Day: calls from the queue** (L799). There: cards with Called, Messaged, No answer. [inbox.html:228](../web/inbox.html#L228), test: [test_leads.py](../tests/test_leads.py#L206). Sales reviewer owns the queue details.
- [ ] 🟡 **Day: viewings with the client's last messages** (L799). There: the chat is one click from a calendar item. Needed: last message on the appointment.
- [ ] 🟡 **Day: records voice notes after visits** (L799). There: typed notes on "done", or the live Meeting page. [app.py:1705](../diwan/app.py#L1705), test: [test_calendar.py](../tests/test_calendar.py#L168). Needed: recording a voice note after the visit.
- [ ] 🟡 **End: outcome for every call** (L799). There: closing a card records one of four actions. Needed: a sweep for calls with none (see L1058).
- [ ] 🟡 **End: tomorrow's viewings confirmed** (L799). There: Rania's reminder goes out; no "confirmed" state. [reminders.py:68](../diwan/agents/reminders.py#L68), test: [test_calendar.py](../tests/test_calendar.py#L116). Needed: a confirm state.
- [ ] 🟡 **Unasked: books viewings in free time** (L799). There: Rania does, with the client, inside the broker's shift. [reception.py:733](../diwan/agents/reception.py#L733), test: [test_reception.py](../tests/test_reception.py#L52), browser: [calendar_flow.py](../e2e/calendar_flow.py). Needed: a PA doing it for the broker.
- [x] ✅ **Unasked: drafts follow-ups** (L799). There: after viewings and meetings. [followup.py:75](../diwan/agents/followup.py#L75), test: [test_followup.py](../tests/test_followup.py#L32), browser: [visit_flow.py](../e2e/visit_flow.py).
- [ ] ❌ **Unasked: reminds 15 min before calls** (L799). There: phone appointments are skipped in reminders, and brokers get none. [reminders.py:80](../diwan/agents/reminders.py#L80). Needed: a broker notice.
- [ ] ❌ **Unasked: nudges for missing outcomes** (L799). Needed: a sweep. The word "outcome" appears nowhere in `diwan/` or `web/`.
- [ ] 🟡 **Never: fill a form from scratch** (L799). There: forms fill from Facts where a Fact exists. Agency forms covered by [test_desk_rules.py](../tests/test_desk_rules.py).
- [x] 🧪 **Never: chase documents by hand** (L799). There: Rania reminds on a schedule, then a task to call. [documents.py:254](../diwan/documents.py#L254), test: [test_desk_rules.py](../tests/test_desk_rules.py#L729).
- [ ] 🟡 **Never: wonder who called a client last** (L799). There: the chat history and event log show it. Needed: a "last contact" line on the lead.

**Sales lead**

- [ ] ❌ **08:00: team board** (L800). There: nothing for Rashid; `/api/team` lists shifts only. [app.py:1202](../diwan/app.py#L1202). Needed: a board page.
- [ ] 🟡 **08:00: leads per broker** (L800). There: "leads today" in the team list. [leads.py:90](../diwan/leads.py#L90). Needed: on a board.
- [ ] ❌ **08:00: call-now response times** (L800). Needed: from `attention.*` events.
- [ ] 🟡 **08:00: unassigned leads** (L800). There: the Pool tab. Needed: on a board.
- [x] 🧪 **Day: reassigns** (L800). There: from a lead's profile. [app.py:1191](../diwan/app.py#L1191), [leads.py:209](../diwan/leads.py#L209), test: [test_leads.py](../tests/test_leads.py#L206).
- [ ] ❌ **Day: coaches** (L800). Needed: define what this is.
- [ ] 🟡 **Day: reviews hot leads** (L800). There: a hot mark on each lead; no hot tab or list. Needed: a hot list for him.
- [ ] 🟡 **End: team numbers** (L800). There: Deal desk KPIs are open to him. Needed: Sales numbers by broker.
- [ ] ❌ **End: escalations** (L800). Needed: see L399.
- [ ] ❌ **Unasked: escalates unanswered call-now items** (L800). There: to the owner. [leads.py:191](../diwan/leads.py#L191). Needed: to Rashid first.
- [ ] ❌ **Unasked: daily sweep per broker** (L800). Needed: a job.
- [ ] ❌ **Never: ask each broker for a status update** (L800). Needed: the board above.

**Deal coordinator**

- [x] ✅ **08:00: deals board: missing items per deal** (L801). There: deal list and work queue. [deal_desk.py:331](../diwan/deal_desk.py#L331), browser: [deal_flow.py:327](../e2e/deal_flow.py#L327).
- [x] 🧪 **08:00: items waiting on outsiders** (L801). There: `waiting_on` on steps. [operations.py:108](../diwan/agents/operations.py#L108), [deal.html:436](../web/deal.html#L436). Filled for transfer steps only. No test.
- [x] 🧪 **Day: sends portal links** (L801). There: link per party, copied or sent by Rania's reminder. [deal_desk.py:853](../diwan/deal_desk.py#L853). No test.
- [x] ✅ **Day: reviews uploads** (L801). There: checked and confirmed on the desk. [documents.py:162](../diwan/documents.py#L162), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py).
- [ ] ❌ **Day: answers client questions on documents** (L801). There: Rania hands document questions to the broker. [reception.py:108](../diwan/agents/reception.py#L108). Needed: a route to the coordinator.
- [ ] 🟡 **End: every deal has a next step and date** (L801). There: next step shown on many; no check that each has a date. Needed: a sweep.
- [x] 🧪 **Unasked: sends the follow-up ladder** (L801). There: every N days up to M, then a call task. [documents.py:254](../diwan/documents.py#L254), test: [test_desk_rules.py](../tests/test_desk_rules.py#L729).
- [x] ✅ **Unasked: rebuilds checklists after corrections** (L801). There: the plan is sent back and remade. [operations.py:53](../diwan/agents/operations.py#L53), test: [test_deal_desk.py](../tests/test_deal_desk.py#L182), browser: [deal_flow.py](../e2e/deal_flow.py).
- [x] ✅ **Unasked: prepares Form F from Facts** (L801). There: [operations.py:25](../diwan/agents/operations.py#L25), test: [test_nova.py](../tests/test_nova.py#L130), browser: [deal_flow.py](../e2e/deal_flow.py).
- [ ] 🟡 **Never: check a signature or ID by eye first** (L801). There: format and expiry are checked for IDs; signatures are not compared. [documents.py:162](../diwan/documents.py#L162). Finer detail with the Deal reviewer.
- [x] ✅ **Never: retype prices into forms** (L801). There: fields come from Facts. Same evidence as Form F.

**Operations**

- [ ] 🟡 **08:00: portal drafts ready to Submit** (L802). There: a Form F plan and a Submit task. No portal connection. [operations.py:64](../diwan/agents/operations.py#L64).
- [ ] 🟡 **08:00: appointments today** (L802). There: no trustee or office appointment list; dates are free text on steps. Needed: dated tasks and a today view.
- [x] ✅ **Day: submits drafts** (L802). There: a person records the reference; only the role may. [operations.py:81](../diwan/agents/operations.py#L81), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py:230](../e2e/deal_flow.py#L230).
- [ ] 🟡 **Day: attends trustee appointments** (L802). There: a step to tick. [operations.py:112](../diwan/agents/operations.py#L112).
- [ ] 🟡 **Day: handovers** (L802). There: only as an owner-defined step if added. Needed: a named step for handover.
- [x] 🧪 **End: transfers marked complete** (L802). There: tick and close. [operations.py:245](../diwan/agents/operations.py#L245), test: [test_desk_rules.py](../tests/test_desk_rules.py).
- [ ] ❌ **Unasked: fills portals up to Submit** (L802). Needed: a portal integration or a browser agent.
- [ ] 🟡 **Unasked: tracks NOC and trustee** (L802). There: tasks with who they wait on; no chasing. The `transfer` agent has no handler. [nova.py:441](../diwan/agents/nova.py#L441). Needed: dates and a chase.
- [ ] 🟡 **Unasked: reminds clients what to bring** (L802). There: photo ID for viewings only. [reminders.py:62](../diwan/agents/reminders.py#L62). Needed: for trustee appointments.
- [ ] ❌ **Never: search for which form version is current** (L802). Needed: a form-version record; `FIELDS` and form templates are not versioned against an authority. Deal reviewer may add detail.

**Finance**

- [x] ✅ **08:00: due today, overdue** (L803). There: Finance tab and desk overview. [deal_desk.py:249](../diwan/deal_desk.py#L249), test: [test_deal_desk.py](../tests/test_deal_desk.py#L145), browser: [deal_flow.py](../e2e/deal_flow.py).
- [x] ✅ **08:00: payments to mark** (L803). There: Received button. [deal_desk.py:481](../diwan/deal_desk.py#L481), test: [test_deal_desk.py](../tests/test_deal_desk.py#L156), browser: [deal_flow.py:195](../e2e/deal_flow.py#L195).
- [x] ✅ **Day: marks received** (L803). Same evidence; a reference is required and a receipt filed.
- [x] 🧪 **Day: approves invoices** (L803). There: drafted, then a person marks it sent. [finance.py:158](../diwan/agents/finance.py#L158), [finance.py:200](../diwan/agents/finance.py#L200), test: [test_desk_rules.py](../tests/test_desk_rules.py#L235).
- [x] 🧪 **Day: prepares payouts** (L803). There: split payments per deal. [finance.py:191](../diwan/agents/finance.py#L191), test: [test_desk_rules.py](../tests/test_desk_rules.py#L235). No payout list across deals.
- [ ] ❌ **End: cash summary** (L803). Needed: a daily job and a line.
- [ ] 🟡 **Unasked: drafts invoices from Facts** (L803). There: drafted on a person's button, from the deal's terms. [deal_desk.py:597](../diwan/deal_desk.py#L597). Needed: on each trigger, unasked.
- [ ] ❌ **Unasked: reads proofs and flags mismatches** (L803). There: the "proof" here is compliance's source-of-funds list; nothing reads a payment proof. Needed: read the file, compare amount, payer, reference.
- [ ] ❌ **Unasked: chases overdue invoices** (L803). Needed: a sweep. Nothing in `finance.py` chases.
- [x] 🧪 **Never: calculate VAT or commission splits by hand** (L803). There: worked out in code. [finance.py:125](../diwan/agents/finance.py#L125), test: [test_desk_rules.py](../tests/test_desk_rules.py#L92).

**Compliance officer**

- [x] ✅ **08:00: corrections** (L804). There: the check is raised first. [compliance.py:20](../diwan/agents/compliance.py#L20), test: [test_nova.py](../tests/test_nova.py#L41), browser: [deal_flow.py:327](../e2e/deal_flow.py#L327).
- [x] ✅ **08:00: screening hits** (L804). There: results recorded by Priya. [compliance.py:77](../diwan/agents/compliance.py#L77), browser: [deal_flow.py:155](../e2e/deal_flow.py#L155). A person enters the result; no list provider.
- [x] 🧪 **08:00: holds** (L804). There: checks and funding questions stop money. Not named as "holds". No test.
- [x] ✅ **08:00: cases needing source of funds** (L804). There: [compliance.py:111](../diwan/agents/compliance.py#L111), test: [test_deal_desk.py](../tests/test_deal_desk.py#L106), browser: [deal_flow.py:168](../e2e/deal_flow.py#L168).
- [x] ✅ **Day: decides hits** (L804). There: Priya only. Same evidence.
- [ ] 🟡 **Day: asks for documents** (L804). There: a funding question to the broker, proof marked by hand. [compliance.py:185](../diwan/agents/compliance.py#L185), test: [test_deal_desk.py](../tests/test_deal_desk.py#L221). Needed: a request without going through the broker, if wanted.
- [ ] 🟡 **Day: signs off risk** (L804). There: closes the check. Needed: a recorded risk sign-off on the case.
- [ ] ❌ **End: open holds with reasons** (L804). Needed: a daily list. Live view exists, no end-of-day line.
- [ ] 🟡 **Unasked: runs screening** (L804). There: raises a task for each party; a person does it. [compliance.py:63](../diwan/agents/compliance.py#L63), test: [test_deal_desk.py](../tests/test_deal_desk.py#L84). Needed: a screening provider.
- [x] ✅ **Unasked: compares the money story with documents** (L804). There: numbers and missing proof, no verdict. [compliance.py:111](../diwan/agents/compliance.py#L111), test: [test_deal_desk.py](../tests/test_deal_desk.py#L106), browser: [deal_flow.py:168](../e2e/deal_flow.py#L168).
- [x] 🧪 **Unasked: drafts reports** (L804). There: at the cash threshold. [compliance.py:162](../diwan/agents/compliance.py#L162), test: [test_deal_desk.py](../tests/test_deal_desk.py#L118).
- [x] ✅ **Never: discover a payer change after the transfer** (L804). There: the correction tells Compliance first and money work waits. test: [test_nova.py](../tests/test_nova.py#L41), browser: [deal_flow.py:65](../e2e/deal_flow.py#L65).

**Marketing**

- [x] ✅ **08:00: scripts to approve** (L805). There: the studio's approval cards. [app.py:490](../diwan/app.py#L490), test: [test_studio.py](../tests/test_studio.py), browser: [studio_flow.py](../e2e/studio_flow.py).
- [ ] ❌ **08:00: listings needing content** (L805). Needed: a list of listings with a permit and no recent post.
- [x] ✅ **Day: approves scripts** (L805). Same evidence.
- [x] ✅ **Day: shoots** (L805). There: film list and footage upload. [app.py:434](../diwan/app.py#L434), test: [test_studio.py](../tests/test_studio.py#L597), browser: [studio_flow.py](../e2e/studio_flow.py).
- [x] 🧪 **End: posts scheduled** (L805). There: approved posts go out at their slot. [studio.py:1202](../diwan/agents/studio.py#L1202), test: [test_studio.py](../tests/test_studio.py).
- [x] 🧪 **Unasked: researches competitors** (L805). There: daily refresh when turned on. [app.py:80](../diwan/app.py#L80), test: [test_lead_chat.py](../tests/test_lead_chat.py#L56).
- [x] 🧪 **Unasked: writes scripts from listing Facts** (L805). There: from the listing, in the studio run. test: [test_studio.py](../tests/test_studio.py#L597). "Facts" here means listing fields, not client Facts.
- [ ] ❌ **Unasked: withdraws scripts when a price changes** (L805). There: only a check at review that the price matches. Needed: a listing-change subscriber that withdraws the script.
- [x] 🧪 **Never: post an ad without a permit number** (L805). There: the permit checker holds it. [charters.py:242](../diwan/agents/charters.py#L242), test: [test_studio.py](../tests/test_studio.py#L58).

**When someone is away**

- [ ] 🟡 **A person sets out-of-office** (L807). There: an `away` tick, brokers only, set by the owner in Settings; routing skips them. [leads.py:74](../diwan/leads.py#L74), [settings.html:249](../web/settings.html#L249), test: [test_leads.py](../tests/test_leads.py#L39). Needed: set by the person, for any role, with dates.
- [ ] ❌ **Their PA tells clients who is covering** (L807). Needed: a client message on the away state.
- [ ] ❌ **The room lead's PA reassigns Now items** (L807). Needed: a sweep. Open cards stay; only the 60-minute Pool rule moves anything ([leads.py:179](../diwan/leads.py#L179)).
- [ ] ❌ **Nothing waits in an absent person's queue beyond the owner's limit** (L807). Needed: an owner setting and a sweep. The Pool minutes are an env value, not on Settings.

### What every PA has: the shared kit (L1036-1051)

- [ ] ❌ **One engine, configured per role** (L1038). There: Nova, the Marketing lead chat and Rania are three separate programs. [nova.py:173](../diwan/agents/nova.py#L173), [lead_chat.py:206](../diwan/agents/lead_chat.py#L206). Needed: one PA module with role config.
- [ ] 🟡 **Reach: chat on every page** (L1042). See L395.
- [ ] 🟡 **Reach: push-to-talk on phone** (L1042). See L395.
- [ ] ❌ **Reach: wake word on desktop** (L1042). See L395.
- [ ] 🟡 **Reach: WhatsApp to the person's own number** (L1042). One way. See L395.
- [ ] 🟡 **Reach: push notifications** (L1042). There: a browser notification on the Inbox only, while the tab is open. No service worker. [inbox.html:383](../web/inbox.html#L383). Needed: web push for all staff.
- [x] 🧪 **Reach limit: speaks only to its own person; never to clients except through Rania or an approved message** (L1042). There: Nova has no client send. [charters.py:38](../diwan/agents/charters.py#L38). True because she has no such tool. No test.
- [ ] 🟡 **Knowledge: Cases, Facts, Tasks, Documents, Events the role may see** (L1043). There: yes for the owner; no role filter. See L394.
- [ ] 🟡 **Knowledge: the calendar** (L1043). There: viewings only. See L51.
- [ ] ❌ **Knowledge: the office's knowledge base** (L1043). There: Nova never calls `knowledge.search`; only Rania and the header search do. Needed: add it to `ask`.
- [ ] ❌ **Knowledge: Settings** (L1043). There: Nova cannot answer "what's our cash threshold?". Needed: read access to settings.
- [x] 🧪 **Knowledge limit: says "not recorded" instead of guessing** (L1043). See L51.
- [x] ✅ **Knowledge limit: cites the record behind every answer** (L1043). See L51. Small talk and the Lobby read-back carry none, as they should.
- [ ] 🟡 **Memory: working hours** (L1044). There: broker shift and days, owner-set. [leads.py:53](../diwan/leads.py#L53).
- [ ] ❌ **Memory: call windows** (L1044). Needed: person setting. "No calls" exists for clients, not staff.
- [ ] ❌ **Memory: tone** (L1044). Needed: person setting.
- [ ] ❌ **Memory: language** (L1044). Needed: person setting.
- [ ] ❌ **Memory: what to brief first** (L1044). Needed: person setting read by `brief()`.
- [ ] ❌ **Memory limit: viewable and editable by the person** (L1044). There: `/api/settings/{person}` and Settings are owner-only. Needed: own-path access.
- [ ] 🟡 **Memory limit: archived, not deleted, when they leave** (L1044). There: removing a login ends access; settings stay in the log, so nothing is deleted, but nothing archives either. [access.py:164](../diwan/access.py#L164). Needed: a leave action.
- [ ] 🟡 **Morning brief: built at the person's start time** (L1045). There: a per-person time is stored, and rounds use the earliest one; the person's brief is composed when opened, so nothing arrives at their time. [app.py:66](../diwan/app.py#L66). Needed: per-person build and delivery.
- [ ] ❌ **Morning brief: from overnight Events** (L1045). There: from open state. See L444.
- [ ] ❌ **Morning brief: max 5 items before "more"** (L1045). Needed: a cap.
- [ ] ❌ **Reminders: any "remind me" becomes a Task with a due time** (L1046). See L71.
- [ ] ❌ **Reminders limit: respects quiet hours unless Now** (L1046). Needed: staff quiet hours and a Now level.
- [ ] 🟡 **Drafting: messages** (L1047). There: client follow-ups. [followup.py:75](../diwan/agents/followup.py#L75), test: [test_followup.py](../tests/test_followup.py). Not through a PA.
- [ ] ❌ **Drafting: emails** (L1047). Needed: no email channel exists.
- [ ] 🟡 **Drafting: forms** (L1047). There: Form F, agency forms. Not through a PA.
- [ ] 🟡 **Drafting: invoices** (L1047). There: on the desk. Not through a PA.
- [ ] 🟡 **Drafting: summaries** (L1047). There: visit summary. Not through a PA.
- [ ] 🟡 **Drafting limit: every draft shows the Facts it used** (L1047). There: Form F plan cites them; a follow-up stores `refs` but the Meeting page and Inbox show text only. [followup.py:106](../diwan/agents/followup.py#L106). Needed: show them.
- [ ] 🟡 **Doing: schedule** (L1048). Rania only. Needed: PA tool.
- [ ] 🟡 **Doing: book viewings in free time** (L1048). Rania only, with clients. See L799.
- [ ] 🟡 **Doing: create and assign Tasks** (L1048). There: Nova, owner only. See L42.
- [ ] 🟡 **Doing: fill portals up to Submit** (L1048). There: a plan, no portal. See L802.
- [ ] 🟡 **Doing: search Records** (L1048). There: Nova, owner only.
- [ ] 🟡 **Doing limit: asks before anything a client or outsider will see** (L1048). See L397 and Conflicts.
- [ ] 🟡 **Handoff: "Tell Finance…" creates a Task or Event** (L1049). See L398.
- [x] 🧪 **Handoff limit: Tasks and Events only** (L1049). See L398.
- [ ] 🟡 **Escalation: nudge, then lead's PA, then Nova** (L1050). See L399.
- [ ] ❌ **Escalation limit: chain from Settings** (L1050). Needed: a chain setting. The steps are in code.
- [x] 🧪 **Never: pay** (L1051). There: `release` and "pay him/her/them…" refused and logged. [nova.py:59](../diwan/agents/nova.py#L59), test: [test_nova.py](../tests/test_nova.py#L144). "Pay the invoice" is not matched, but no tool exists.
- [ ] ❌ **Never: sign** (L1051). There: "Sign the form for Karim" got "Which team…": no refusal. Add `sign` to `REFUSE`; `ONLY_PEOPLE` has no entry either. [people.py:22](../diwan/people.py#L22).
- [x] 🧪 **Never: submit** (L1051). Refused and logged. [nova.py:57](../diwan/agents/nova.py#L57), test: [test_nova.py](../tests/test_nova.py#L144).
- [x] 🧪 **Never: file a report** (L1051). Refused and logged. [nova.py:61](../diwan/agents/nova.py#L61), test: [test_nova.py](../tests/test_nova.py#L144).
- [ ] ❌ **Never: clear a screening hit** (L1051). There: "Clear the screening hit for Karim" was **routed**: a Task went to the Screening analyst with "will pick it up". No hit was cleared, since only Priya can record it, but it must refuse. Add to `REFUSE`.
- [ ] ❌ **Never: mark money received** (L1051). There: "Which team…": no refusal. The code rule stands in `mark_received`, but Nova does not refuse it. Add to `REFUSE`.
- [x] 🧪 **Never: approve on the person's behalf** (L1051). There: refused. [nova.py:58](../diwan/agents/nova.py#L58). `test_nova.py` covers the others; "approve" itself has no parametrised case.
- [ ] ❌ **Never: change Settings** (L1051). There: Nova does: "Set Rania to autopilot" replied "Rania is now on autopilot" (`autonomy.changed`), and "Brief me at 9:30" sets a time. [nova.py:185](../diwan/agents/nova.py#L185), [nova.py:194](../diwan/agents/nova.py#L194). Needed: refuse autonomy changes (see Conflicts for the briefing time).
- [ ] ❌ **Never: send bank details** (L1051). There: "Send Karim our bank details" got "Which team…". Needed: a refusal; the fraud guard is also absent (no word for it in `diwan/`).
- [ ] 🟡 **Hard-coded refusals, logged** (L1051). There: yes for the five in `REFUSE`; note `converse` only reaches them through `route`, and a sentence that looks like a question goes to `ask` and is not refused. [nova.py:205](../diwan/agents/nova.py#L205), test: [test_nova.py](../tests/test_nova.py#L146). Needed: check `REFUSE` before `ask`, and extend it.

### Each PA (L1053-1065)

**Nova (owner)**

- [ ] 🟡 **Unasked: greets on arrival** (L1057). See L48.
- [ ] 🟡 **Unasked: morning brief across all rooms** (L1057). See L55-62.
- [ ] 🟡 **Unasked: flags compliance holds** (L1057). See L57.
- [ ] ❌ **Unasked: flags overdue money** (L1057). See L57.
- [ ] ❌ **Unasked: flags unanswered call-me** (L1057). Notice only, not in the brief. See L57.
- [ ] ❌ **Unasked: flags stuck deals** (L1057). See L59.
- [ ] ❌ **Unasked: Pocket meeting mode** (L1057). See L50.
- [ ] ❌ **Unasked: weekly Monday numbers** (L1057). Needed: a Monday job. Nothing weekly exists at Nova.
- [ ] ❌ **Unasked: one Lobby idea** (L1057). See L62.
- [ ] ❌ **"How's the Marina deal?"** (L1057). Fails. See L798.
- [ ] ❌ **"Who hasn't called Sara back?"** (L1057). "I don't have that in the office's records." Needed: read Attention cards.
- [ ] ❌ **"Book my trip from this email."** (L1057). See L66.
- [ ] ❌ **"Draft a reply to Ahmed."** (L1057). See L67.
- [ ] ❌ **"Remind me Thursday to call the developer."** (L1057). See L71.
- [x] 🧪 **Asks first: any send, booking, purchase, approval** (L1057). There: Lobby read-back; no other tool exists. [lobby.py:104](../diwan/agents/lobby.py#L104), test: [test_frontdesk.py](../tests/test_frontdesk.py#L32).
- [ ] ❌ **Ends its day: 2-line wrap** (L1057). See L798.

**Broker's PA**

- [ ] ❌ **The PA itself** (L1058). There: no broker can reach any PA. Every line below is about the data or job behind it.
- [ ] 🟡 **Today's calls, viewings and quiet clients** (L1058). See L799.
- [ ] 🟡 **Call-now alerts** (L1058). There: `notify.sent` plus a browser notice. [leads.py:128](../diwan/leads.py#L128), test: [test_leads.py](../tests/test_leads.py).
- [ ] ❌ **Reminders 15 min before calls** (L1058). See L799.
- [x] ✅ **Drafts follow-ups** (L1058). See L799.
- [ ] ❌ **Nudges for missing outcomes** (L1058). See L799.
- [ ] ❌ **Listing availability checks with owners** (L1058). Needed: an owner contact and a check job.
- [ ] ❌ **Permit expiry reminders for their listings** (L1058). Needed: a permit expiry date on listings; the code stores only a number and "expir" never touches a listing.
- [ ] ❌ **Form A expiry reminders** (L1058). Needed: an expiry on Form A and a sweep.
- [ ] 🟡 **"Book Sara a viewing Thursday after 4."** (L1058). There: done by hand on the Calendar, or by Rania with the client. Needed: PA tool.
- [ ] 🟡 **"What did Karim say about budget?"** (L1058). There: Nova answers with the quote, owner only, and for any broker's client.
- [ ] ❌ **"Send him the 3 closest options."** (L1058). Needed: PA tool over `reception.matches`, with a confirm.
- [ ] ❌ **"Log: viewing done, liked the view, worried about service charges."** (L1058). Needed: spoken log into `visit.summarize`.
- [x] 🧪 **Asks first: every client message, offer or document sent** (L1058). There: the broker sends follow-ups. [followup.py:116](../diwan/agents/followup.py#L116). No PA can send, so this holds by default. No test.
- [ ] ❌ **Ends its day: every call has an outcome** (L1058). See L799.
- [ ] 🟡 **Ends its day: tomorrow's viewings confirmed with clients** (L1058). See L799.
- [ ] ❌ **Ends its day: confirmed with owners** (L1058). Needed: owner contact and message.

**Sales lead's PA**

- [ ] ❌ **The PA itself** (L1059). There: the charter called "Sales lead" is a meetings agent, not a broker-facing PA. [charters.py:45](../diwan/agents/charters.py#L45). Needed: its own PA.
- [ ] ❌ **Team board** (L1059). See L800.
- [ ] ❌ **Escalates unanswered call-now after 10 min** (L1059). There: 15 minutes to the owner, 60 to the Pool. [leads.py:32](../diwan/leads.py#L32), [leads.py:179](../diwan/leads.py#L179). Needed: a 10-minute owner setting and Rashid in the chain.
- [ ] ❌ **Daily sweep per broker** (L1059). See L800.
- [ ] 🟡 **Unassigned leads** (L1059). See L800.
- [ ] 🟡 **Duplicate leads to merge** (L1059). There: a merge action on a lead by a person; no finding of duplicates. [leads.py:244](../diwan/leads.py#L244). Needed: a suggestion list.
- [ ] 🟡 **Listing-to-buyer matches** (L1059). There: for one chat when a client asks. [reception.py:653](../diwan/agents/reception.py#L653). Needed: on a new listing, across buyers.
- [ ] ❌ **"Who's slowest to call back this week?"** (L1059). Needed: response-time numbers.
- [ ] ❌ **"Give Omar's leads to Layla while he's away."** (L1059). There: "Which team…". Reassign is one lead at a time. Needed: bulk move with a confirm. (Layla is the owner in the demo; substitute a broker.)
- [ ] ❌ **"Which hot leads have no viewing?"** (L1059). There: the word "viewing" tripped the listing of viewings: "No viewings are booked yet." Needed: a real query.
- [x] 🧪 **Asks first: reassigning a client, changing routing** (L1059). There: only a person does it, on screen. No PA can. No test.
- [ ] 🟡 **Ends its day: team numbers** (L1059). See L800.
- [ ] ❌ **Ends its day: leads with no next step** (L1059). Needed: a sweep.

**Deal coordinator's PA**

- [ ] ❌ **The PA itself** (L1060). Needed: as above. Joseph has the desk but no PA.
- [x] ✅ **Missing items per deal** (L1060). See L801.
- [x] 🧪 **Sends follow-up ladder** (L1060). See L801.
- [x] ✅ **Rebuilds checklists after corrections** (L1060). See L801.
- [x] ✅ **Prepares Form F from Facts** (L1060). See L801.
- [ ] 🟡 **Expiry warnings on uploaded documents** (L1060). There: at upload, a flag if it expires soon, and expired is refused. No later warning. [documents.py:168](../diwan/documents.py#L168). Needed: a sweep; a test.
- [ ] 🟡 **Waiting-on-outsider aging** (L1060). There: shows "waiting 3d" and medians per step. [deal.html:436](../web/deal.html#L436), [desk_kpis.py:83](../diwan/desk_kpis.py#L83). Needed: a chase when too old.
- [ ] 🟡 **"What's missing for Sara's deal?"** (L1060). There: the desk shows it; Nova replied "I don't have that in the office's records". Needed: an intent.
- [ ] 🟡 **"Send Karim the portal link again."** (L1060). There: a button/link on the desk; not by words.
- [ ] ❌ **"Has the bank sent the final offer?"** (L1060). Needed: a step or a document kind for it, and an answer.
- [x] 🧪 **Asks first: sending forms** (L1060). There: a person generates signing links. [deal_desk.py:825](../diwan/deal_desk.py#L825). No test.
- [x] 🧪 **Asks first: overriding a failed upload check** (L1060). There: a failed check refuses the file; there is no override at all. No test.
- [ ] 🟡 **Ends its day: every deal has a next step and a date** (L1060). See L801.

**Operations PA**

- [ ] ❌ **The PA itself** (L1061). Needed: as above.
- [ ] 🟡 **Portal drafts ready to Submit** (L1061). See L802.
- [ ] 🟡 **Trustee and NOC tracking** (L1061). See L802.
- [ ] 🟡 **Reminds clients what to bring** (L1061). See L802.
- [ ] ❌ **Permit renewals drafted** (L1061). Needed: permit expiry first. See L1058.
- [ ] 🟡 **Handovers and move-outs scheduled** (L1061). There: a rental's renewal question and move-out are dated at closing. [operations.py:275](../diwan/agents/operations.py#L275), test: [test_desk_rules.py](../tests/test_desk_rules.py#L353). Handovers are not.
- [x] ✅ **Recalls forms after corrections** (L1061). There: the plan is sent back; a draft on replaced words is returned. test: [test_deal_desk.py](../tests/test_deal_desk.py#L182), browser: [deal_flow.py](../e2e/deal_flow.py). The word used is "sent back".
- [ ] ❌ **"Book the trustee for next Tuesday."** (L1061). There: routed to the Transfer tracker as a Task with no handler, for a deal it asks about; nothing is booked. [nova.py:49](../diwan/agents/nova.py#L49). Needed: a date-bearing step and a booking draft.
- [ ] ❌ **"What does Sara need to bring?"** (L1061). Needed: a checklist per appointment type.
- [ ] ❌ **"Prepare Ejari for 1204."** (L1061). Needed: an Ejari form and route. Only a text mention at move-out.
- [x] ✅ **Asks first: every Submit (always a person)** (L1061). There: [operations.py:81](../diwan/agents/operations.py#L81), [nova.py:57](../diwan/agents/nova.py#L57), browser: [deal_flow.py:230](../e2e/deal_flow.py#L230).
- [ ] ❌ **Asks first: messages to developers or government** (L1061). Needed: no such channel exists to ask about.
- [ ] 🟡 **Ends its day: transfers and Ejaris marked** (L1061). There: ticks and close; no daily wrap.
- [ ] ❌ **Ends its day: tomorrow's appointments confirmed** (L1061). Needed: see L802.

**Finance lead's PA**

- [ ] ❌ **The PA itself** (L1062). Needed: as above.
- [ ] 🟡 **Invoices drafted at each trigger** (L1062). See L803.
- [x] ✅ **Due and overdue lists** (L1062). See L803.
- [ ] ❌ **Reads payment proofs and flags mismatches** (L1062). See L803.
- [x] 🧪 **Cheque dates** (L1062). There: [finance.py:249](../diwan/agents/finance.py#L249), test: [test_desk_rules.py](../tests/test_desk_rules.py#L339).
- [ ] ❌ **Installment reminders** (L1062). There: instalments are dated tasks; nobody is reminded. [finance.py:265](../diwan/agents/finance.py#L265). Needed: a sweep with a confirm.
- [ ] 🟡 **Commission splits and payout list** (L1062). There: per deal; no list. See L803.
- [ ] ❌ **"What's outstanding from developers?"** (L1062). Needed: a query. Nova's "payer" intent would answer about a deal.
- [ ] ❌ **"Mark AED 50,000 received from Sara" opens the form for the person to confirm** (L1062). There: "Which team…". Needed: an intent that opens the Received form, not a refusal alone.
- [ ] ❌ **"What do I owe brokers this month?"** (L1062). Needed: a query. "commission" gives what the office earned, not what it owes.
- [x] ✅ **Asks first: the person confirms every Mark received** (L1062). There: [finance.py:80](../diwan/agents/finance.py#L80), test: [test_deal_desk.py](../tests/test_deal_desk.py#L156), browser: [deal_flow.py:195](../e2e/deal_flow.py#L195).
- [x] 🧪 **Asks first: sending invoices** (L1062). There: a person marks it sent. [finance.py:200](../diwan/agents/finance.py#L200). Nothing emails it. No test.
- [ ] ❌ **Asks first: sending reminders** (L1062). Needed: arrives with reminders.
- [ ] ❌ **Ends its day: cash summary** (L1062). See L803.

**Compliance officer's PA**

- [ ] ❌ **The PA itself** (L1063). Needed: as above.
- [ ] 🟡 **Corrections side by side** (L1063). There: old and new quotes in the check; a side-by-side view on the Compliance tab is the Compliance reviewer's. test: [test_nova.py](../tests/test_nova.py#L41).
- [x] ✅ **Screening hits** (L1063). See L804.
- [x] ✅ **Source-of-funds files ready** (L1063). See L804.
- [x] 🧪 **Holds with reasons** (L1063). See L804.
- [x] 🧪 **Report drafts** (L1063). See L804.
- [x] 🧪 **Threshold alerts** (L1063). There: cash at or above the owner's limit. [desk_rules.py:27](../diwan/desk_rules.py#L27), test: [test_deal_desk.py](../tests/test_deal_desk.py#L118).
- [ ] ❌ **Fraud-guard flags** (L1063). Needed: detect "send to this new account", raise a Now flag. No fraud code exists.
- [ ] ❌ **"Why is Sara's deal on hold?"** (L1063). There: "I don't have that in the office's records", though the funding question is open. Needed: an intent.
- [ ] 🟡 **"What did she say about where the money comes from?"** (L1063). There: Nova's payer words find it once she knows the deal, owner only. Needed: Priya's access.
- [ ] 🟡 **"Draft the cash report for Case 118."** (L1063). There: routed by words to the Report drafter. [nova.py:46](../diwan/agents/nova.py#L46). Owner only, and "Case 118" is not understood: deals are named, so Nova asks which deal. Needed: Priya's access; case numbers.
- [ ] ❌ **Asks first: any request for documents from a client** (L1063). Needed: PA first.
- [x] 🧪 **Asks first: every draft report** (L1063). There: Priya files with a reference. [compliance.py:92](../diwan/agents/compliance.py#L92), test: [test_deal_desk.py](../tests/test_deal_desk.py#L118).
- [ ] ❌ **Ends its day: open holds and hits waiting for a decision** (L1063). See L804.

**Marketing PA**

- [ ] 🟡 **The PA itself** (L1064). There: the closest to a real PA: the Marketing lead chat, by text and voice, proposes and waits for a yes. [lead_chat.py:206](../diwan/agents/lead_chat.py#L206), test: [test_lead_chat.py](../tests/test_lead_chat.py#L46). It is not named for the person, has no brief, and stays on marketing only.
- [x] ✅ **Scripts to approve** (L1064). See L805.
- [ ] ❌ **Listings needing content** (L1064). See L805.
- [x] 🧪 **Competitor posts worth a look** (L1064). See L805.
- [ ] ❌ **Pauses posts when a permit expires** (L1064). There: `_missing` never looks at the permit at publish time, and permits have no expiry. [studio.py:1194](../diwan/agents/studio.py#L1194). Needed: a check at publish and a sweep.
- [ ] ❌ **Pauses posts when a listing is withdrawn** (L1064). Needed: same check on listing status.
- [x] 🧪 **"Make 3 reels for 1204 Marina Crest."** (L1064). There: proposes a run and waits. [lead_chat.py:181](../diwan/agents/lead_chat.py#L181). The studio's run is one listing, not three reels on request. No test.
- [x] 🧪 **"What worked for competitors this week?"** (L1064). There: from the board and Why they win. test: [test_lead_chat.py](../tests/test_lead_chat.py#L37).
- [x] ✅ **Asks first: every post, with Review first** (L1064). There: the script and post wait for a person, after the studio's checks. test: [test_studio.py](../tests/test_studio.py), browser: [studio_flow.py](../e2e/studio_flow.py). Marketing reviewer covers whether that is the same Review as every other room.
- [ ] ❌ **Ends its day: posts scheduled for tomorrow** (L1064). Needed: a daily line.

**Rania (clients, not a PA)**

- [x] ✅ **Replies within the 24h window** (L1065). There: free text in the window, templates after. [reception.py:587](../diwan/agents/reception.py#L587), test: [test_inbox.py](../tests/test_inbox.py#L49), browser: [calendar_flow.py:152](../e2e/calendar_flow.py#L152).
- [x] ✅ **Qualifies** (L1065). There: test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py).
- [x] ✅ **Books viewings** (L1065). There: [reception.py:733](../diwan/agents/reception.py#L733), test: [test_reception.py](../tests/test_reception.py#L52), browser: [calendar_flow.py](../e2e/calendar_flow.py).
- [x] 🧪 **Sends portal links** (L1065). There: in the document reminders. [documents.py:284](../diwan/documents.py#L284), test: [test_desk_rules.py](../tests/test_desk_rules.py#L729). The first link is handed over by a person.
- [ ] ❌ **Sends receipts** (L1065). There: a receipt PDF is filed and downloadable; nothing sends it to the client. [deal_desk.py:912](../diwan/deal_desk.py#L912). Needed: a send after `mark_received`, if the office wants it.
- [x] ✅ **Follow-ups on schedule** (L1065). There: [nudge.py:264](../diwan/agents/nudge.py#L264), test: [test_nudge.py](../tests/test_nudge.py#L40), browser: [quiet_flow.py](../e2e/quiet_flow.py).
- [x] 🧪 **Answers client questions about listings** (L1065). There: from permitted listings only. test: [test_reception.py](../tests/test_reception.py#L31). No browser check.
- [x] 🧪 **Answers about the process and documents** (L1065). There: from confirmed knowledge when it exists. test: [test_client_answers.py](../tests/test_client_answers.py).
- [x] 🧪 **Outside the knowledge base goes to the broker** (L1065). There: hands over when sources do not cover it. [reception.py:47](../diwan/agents/reception.py#L47), test: [test_reception.py](../tests/test_reception.py).
- [x] 🧪 **Returns advice goes to the broker** (L1065). There: fixed answer. [reception.py:997](../diwan/agents/reception.py#L997), test: [test_reception.py](../tests/test_reception.py#L70).
- [ ] 🟡 **Visa, legal and tax advice goes to the broker** (L1065). There: no named rule; `NOT_MINE` lists cash, AML, discounts and so on, not these. It holds only if knowledge is silent, and the model rule "anything the sources do not answer". [reception.py:28](../diwan/agents/reception.py#L28). Needed: add the words; test each.
- [x] 🧪 **Always on** (L1065). There: webhook-driven, day and night; follow-ups respect quiet hours. [app.py:57](../diwan/app.py#L57). No test.

<a id="part-c"></a>

## Part C: Sales

### Room 2 · Sales: the purpose (L85-87)

- [x] ✅ **Any first message opens a lead with a named broker** (L87). There: a new chat opens a `lead-…` deal and assigns a broker by round-robin among those on shift. [reception.py:491](../diwan/agents/reception.py#L491), [leads.py:96](../diwan/leads.py#L96), test: [test_leads.py](../tests/test_leads.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **Known intent on the lead** (L87). There: the customer type (buyer, tenant, seller, landlord) is read from the words or by the model and shown with their quote. [qualify.py:114](../diwan/qualify.py#L114), [inbox.html:552](../web/inbox.html#L552), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] ❌ **A heat score on every lead** (L87). Needed: a computed score (hot, warm, cold) stored on the deal. Today a lead is only "hot" or not hot; see the heat lines below.
- [x] ✅ **A next step owned by a person** (L87). There: an Attention card with a due time, one per conversation, that leaves only with a recorded action. [leads.py:128](../diwan/leads.py#L128), [leads.py:150](../diwan/leads.py#L150), test: [test_leads.py](../tests/test_leads.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **Rania is the client-facing agent** (L87). There: `reception.message` answers every chat, with charter `rania` under `sales`. [reception.py:1150](../diwan/agents/reception.py#L1150), [charters.py:55](../diwan/agents/charters.py#L55), test: [test_reception.py](../tests/test_reception.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **Sales lead is the brokers' PA, who tells them what to do and chases them** (L87). There: a `sales` charter exists but its job is "Owns what comes out of meetings"; broker chasing is done by the card sweep, which acts as Rania. [charters.py:45](../diwan/agents/charters.py#L45), [leads.py:172](../diwan/leads.py#L172). Needed: give Sales lead that job in its charter and make it the actor on broker notices, sweeps and escalations.

### Channels in (L89)

- [x] ✅ **WhatsApp** (L89). There: AiSensy and Meta Cloud webhooks and sending, plus the sandbox phone on the same path. [app.py:1891](../diwan/app.py#L1891), [app.py:1910](../diwan/app.py#L1910), [reception.py:530](../diwan/agents/reception.py#L530), test: [test_inbox.py](../tests/test_inbox.py), [test_reception.py](../tests/test_reception.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] ❌ **Instagram DM** (L89). There: only comments arrive; `parse_comments` ignores anything but field `comments`. [instagram.py:154](../diwan/providers/instagram.py#L154). Needed: the Instagram messaging webhook and a send call.
- [x] 🧪 **Instagram comments** (L89). There: the webhook passes comments to Rania, who replies under the comment. [app.py:533](../diwan/app.py#L533), [reception.py:538](../diwan/agents/reception.py#L538). `ig:` chats are tested in [test_reception.py](../tests/test_reception.py); the webhook and `parse_comments` have no test, and no browser check. Rania's reply is public, under the comment.
- [ ] ❌ **Facebook** (L89). Needed: Page messages and comments webhook, parser and sender, in a new provider or `providers/meta.py`.
- [ ] ❌ **TikTok** (L89). Needed: a provider and webhook. TikTok appears only in Studio captions.
- [ ] ❌ **Website form** (L89). Needed: a public lead endpoint and form that opens a lead. `/api/chats/incoming` is the sandbox phone, not a form.
- [x] ✅ **Property Finder, Bayut, Dubizzle portal leads** (L89). There: signed webhook per portal, listing feed, enquiry joins or opens a lead. Field names are guessed until each portal's documentation arrives (the file says so). [app.py:1255](../diwan/app.py#L1255), [portals.py:189](../diwan/providers/portals.py#L189), [leads.py:399](../diwan/leads.py#L399), test: [test_leads.py](../tests/test_leads.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] ❌ **Phone call notes** (L89). There: no way to log a call's notes as a lead's words; the Meeting screen is for recorded meetings. Needed: a "log a call" form on the lead that feeds the Scribe.
- [ ] 🟡 **Walk-ins added by hand** (L89). There: a broker can create a lead only by adding an appointment on the calendar. [reception.py:771](../diwan/agents/reception.py#L771), test: [test_client_answers.py](../tests/test_client_answers.py), browser: [own_time_flow.py](../e2e/own_time_flow.py). Needed: "New lead" in the Inbox without an appointment, with source "walk-in".
- [ ] ❌ **Referrals** (L89). Needed: a source value "referral" with who referred them, on the same "New lead" form. Leads carry no source field beyond the message channel.

### Discovery: reading the first message (L91-101)

- [x] ✅ **Portal enquiry: starts from the listing** (L95). There: `from_listing` fills type, area, property type and bedrooms from the listing, marked as such; never the budget. [leads.py:430](../diwan/leads.py#L430), test: [test_front_door.py](../tests/test_front_door.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] 🧪 **Portal enquiry: asks only what's missing** (L95). There: answered fields are skipped by the form; a first message goes only by the owner's template, after which she continues. [qualify.py:237](../diwan/qualify.py#L237), [leads.py:454](../diwan/leads.py#L454), test: [test_front_door.py](../tests/test_front_door.py). The browser check stops at the template.
- [x] 🧪 **Portal enquiry: intent buy or rent from the listing** (L95). There: `rent` gives tenant, otherwise buyer. [leads.py:438](../diwan/leads.py#L438), test: [test_front_door.py](../tests/test_front_door.py)
- [ ] 🟡 **"Still available?" on a post: confirms** (L96). There: the post's `media_id` is parsed but dropped, so Rania does not know which post was meant; the word "available" just runs a listing search. [app.py:541](../diwan/app.py#L541), [reception.py:37](../diwan/agents/reception.py#L37). Needed: map post to listing and confirm that listing's status. No test.
- [ ] ❌ **"Still available?": then one question, to live in or invest?** (L96). Needed: a `purpose` field on the form (see Qualifying), asked first for this entry.
- [ ] 🟡 **"Still available?": intent buy or rent** (L96). There: only from their words, not from the post. Needed: take it from the listing, as `from_listing` does for portals.
- [ ] 🟡 **"I want to sell my flat in JVC": sets intent Sell** (L97). There: `DETECT` picks seller and the form follows. [qualify.py:116](../diwan/qualify.py#L116). Needed: mark it as a listing lead, and a test: no test or browser check drives a seller.
- [ ] 🟡 **Seller's first questions** (L97). There: area, type, asking price, occupancy. Needed: unit, title deed holder, mortgage on it (see Qualifying).
- [ ] 🟡 **"Can you manage my apartment?": landlord or property management** (L98). There: the rules' landlord pattern has no "manage"; only a connected model can set it. [qualify.py:115](../diwan/qualify.py#L115). Needed: add the words, a management flag, and a test.
- [ ] 🟡 **Landlord's first questions: unit, current tenant, rent** (L98). There: area, type, beds, expected rent, occupancy. Needed: unit and current tenant.
- [x] ✅ **"Hi": a warm hello and one question** (L99). There: the owner's first message or "I'm Rania… buy, rent, or sell?". [reception.py:1208](../diwan/agents/reception.py#L1208), [reception.py:1048](../diwan/agents/reception.py#L1048), test: [test_sales_journey.py](../tests/test_sales_journey.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **"Price?" with no context: hello and one question** (L99). There: rules mode replies "Which property do you mean?" and lists three listings, not the question, and ignores the setting that holds back listings. [reception.py:1005](../diwan/agents/reception.py#L1005), test pins this: [test_reception.py](../tests/test_reception.py). Needed: the hello and buying, selling, renting or just looking.
- [x] 🧪 **Unknown until answered** (L99). There: verdict DISCOVERY until a type is known, and stage stays New. [qualify.py:223](../diwan/qualify.py#L223), [inbox.py:270](../diwan/inbox.py#L270), test: [test_qualify.py](../tests/test_qualify.py)
- [x] ✅ **Company or service question: answers from the knowledge base** (L100). There: confirmed customer-facing cards only. [reception.py:1045](../diwan/agents/reception.py#L1045), test: [test_reception.py](../tests/test_reception.py), browser: [knowledge_flow.py](../e2e/knowledge_flow.py)
- [ ] 🟡 **Then asks if they have a property in mind** (L100). There: adds the buy, rent, sell or let question when the type is unknown. [reception.py:1420](../diwan/agents/reception.py#L1420). Needed: the wording, if the office cares. No test.
- [ ] ❌ **Company question: intent Marketing / nurture** (L100). Needed: set that intent; a nurture entry exists only for "just looking" words.
- [ ] ❌ **Spam, job seekers, suppliers: polite routing** (L101). Needed: detection in `reception.message`, a reply per kind, and a target inbox for each.
- [ ] ❌ **Spam, job seekers, suppliers: "Not a lead"** (L101). Needed: an intent that closes the lead without counting it or assigning a broker. Today every message opens a lead and takes a round-robin turn.

### Qualifying (L103-108)

- [x] ✅ **The owner's form** (L103). There: the owner edits questions, conditions and versions on the Qualification page; only the owner saves. So the missing fields below can be added without code. [qualify.py:162](../diwan/qualify.py#L162), [qualify.html](../web/qualify.html), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **One question at a time** (L103). There: the verdict names one next question and the prompt allows only that. [qualify.py:245](../diwan/qualify.py#L245), [qualify.py:386](../diwan/qualify.py#L386), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **Each answer stored with the client's words** (L103). There: `qualify.answer` keeps the quote; a quote they did not write is dropped; the profile shows it. It is a `qualify.answer`, not `fact.created`. [qualify.py:326](../diwan/qualify.py#L326), [inbox.html:554](../web/inbox.html#L554), test: [test_qualify.py](../tests/test_qualify.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [ ] 🟡 **Buyer: purpose, live or invest** (L105). There: not on the default form; only "invest" as a word that means buyer. Needed: a `purpose` choice in `DEFAULT_FORM`. [qualify.py:80](../diwan/qualify.py#L80)
- [x] ✅ **Buyer: area** (L105). There: [qualify.py:65](../diwan/qualify.py#L65), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **Buyer: type** (L105). There: [qualify.py:66](../diwan/qualify.py#L66), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **Buyer: beds** (L105). There: [qualify.py:68](../diwan/qualify.py#L68), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **Buyer: budget** (L105). There: "must answer" money field. [qualify.py:82](../diwan/qualify.py#L82), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] ✅ **Buyer: cash or mortgage** (L105). There: and her own "cash or mortgage?" answer is not treated as a compliance topic. [qualify.py:83](../diwan/qualify.py#L83), [reception.py:1279](../diwan/agents/reception.py#L1279), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] 🧪 **Buyer: mortgage pre-approval** (L105). There: asked only after "Mortgage", optional by default. [qualify.py:84](../diwan/qualify.py#L84), test: [test_qualify.py](../tests/test_qualify.py)
- [x] ✅ **Buyer: timeline** (L105). There: [qualify.py:88](../diwan/qualify.py#L88), test: [test_client_answers.py](../tests/test_client_answers.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **Buyer: residency, UAE resident or not** (L105). There: not on the default form. Needed: a choice in `DEFAULT_FORM`; Compliance would also read it.
- [ ] 🟡 **Buyer: nationality only if Compliance needs it** (L105). There: an optional common field, so Rania never asks it. [qualify.py:75](../diwan/qualify.py#L75). Needed: a link so Compliance can ask for it on a deal.
- [ ] ❌ **Seller: unit** (L106). Needed: a field on the seller form.
- [ ] ❌ **Seller: title deed** (L106). Needed: a field; the title deed is only an uploaded document at the Deal stage.
- [ ] ❌ **Seller: mortgage outstanding** (L106). Needed: a field; it should switch on the "Seller's mortgage cleared" step.
- [x] 🧪 **Seller: expected price** (L106). There: `asking_price`. [qualify.py:98](../diwan/qualify.py#L98). Form tested, no conversation test of a seller.
- [x] 🧪 **Seller: vacant or tenanted** (L106). There: `occupancy_status`. [qualify.py:99](../diwan/qualify.py#L99). Form tested, no conversation test of a seller.
- [ ] ❌ **Seller: timeline** (L106). Needed: a field on the seller form.
- [x] 🧪 **Tenant: move-in date** (L107). There: `move_in`. [qualify.py:93](../diwan/qualify.py#L93), test: [test_qualify.py](../tests/test_qualify.py)
- [ ] ❌ **Tenants and landlords: cheques** (L107). Needed: a field; the deal's terms have cheques, the first conversation does not.
- [ ] ❌ **Tenants and landlords: ejari** (L107). Needed: a field.
- [ ] ❌ **Tenants and landlords: pets** (L107). Needed: a field.
- [ ] ❌ **Tenants and landlords: company or personal** (L107). Needed: a field.
- [ ] 🟡 **Heat from the owner's rules (budget fits, timeline under 60 days, finance ready)** (L108). There: the owner ticks what makes a lead hot: picks a listing, asks to view, qualifies, asks for a call; none read budget, timeline or finance. [reception.py:175](../diwan/agents/reception.py#L175), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py). Needed: rules on answers, in the form's condition format.

### The PA behaviour · Call now (L112)

- [x] ✅ **"Call me", "can someone call" are recognised** (L112). There: `CALL_ME`, English and Arabic. [reception.py:221](../diwan/agents/reception.py#L221), test: [test_front_door.py](../tests/test_front_door.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **Picks a call slot** (L112). There: a stated time works, and free times are offered when busy. There is no offered list of call slots to pick from, except when the time was taken. [reception.py:1062](../diwan/agents/reception.py#L1062), test: [test_client_answers.py](../tests/test_client_answers.py)
- [ ] 🟡 **Rania says "[broker] will call you in the next 10 minutes"** (L112). There: "Omar from our team will call you shortly", with no time. [reception.py:270](../diwan/agents/reception.py#L270), browser: [front_door_flow.py](../e2e/front_door_flow.py). Needed: the 10 minutes, out of working hours handled. See Conflicts.
- [x] ✅ **Broker gets a push** (L112). There: an on-screen notice, plus a browser notification while the Inbox page is open. Not a real push when the page is closed. [leads.py:474](../diwan/leads.py#L474), [inbox.html:392](../web/inbox.html#L392), test: [test_leads.py](../tests/test_leads.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] 🧪 **Broker gets a WhatsApp alert** (L112). There: through AiSensy when the broker has a number and `NOTIFY_TEMPLATE` is set. [leads.py:481](../diwan/leads.py#L481), test: [test_leads.py](../tests/test_leads.py)
- [x] ✅ **Alert: name** (L112). There: the card and notice carry the chat's label. [leads.py:146](../diwan/leads.py#L146), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [x] 🧪 **Alert: what they want** (L112). There: the qualification answers so far. [reception.py:1093](../diwan/agents/reception.py#L1093), test: [test_front_door.py](../tests/test_front_door.py)
- [ ] 🟡 **Alert: the last 3 messages** (L112). There: only the one message that asked, up to 160 characters. [reception.py:1109](../diwan/agents/reception.py#L1109). Needed: the last three on the card and notice.
- [ ] ❌ **Alert: one-tap call** (L112). There: no `tel:` link anywhere; "Called" only records that it happened. [inbox.html:228](../web/inbox.html#L228). Needed: a call link on the card and in the alert.
- [ ] 🟡 **Not called in 10 minutes: escalation** (L112). There: at 15 minutes the card goes overdue and the broker and owner hear; at 60 it goes to the Pool. Both are env settings. [leads.py:31](../diwan/leads.py#L31), [leads.py:172](../diwan/leads.py#L172), test: [test_leads.py](../tests/test_leads.py). Needed: a 10-minute timer on call cards.
- [ ] ❌ **Escalates to the next free broker** (L112). There: nobody is reassigned; other brokers are told it can be claimed. Needed: `leads.pick(exclude=…)` on the overdue step, plus `lead.assigned`.
- [ ] 🟡 **Tells the owner in the brief** (L112). There: a notice to Layla, hard-coded, but the brief does not read Attention cards. [leads.py:191](../diwan/leads.py#L191). Needed: an "escalated today" line in Nova's brief.

### The PA behaviour · Call later (L113)

- [ ] 🟡 **"Call me tomorrow after 4" becomes a task at that time** (L113). There: "at 4" and "4pm" work: a Phone call appointment plus a card due then. "After 4" is not read as a time, so it falls to "shortly". [slots.py:269](../diwan/slots.py#L269), [reception.py:1062](../diwan/agents/reception.py#L1062), test: [test_client_answers.py](../tests/test_client_answers.py), browser: [call_flow.py](../e2e/call_flow.py). Needed: "after", "before", "around".
- [ ] ❌ **In the client's time zone** (L113). There: every time is Dubai; no client time zone is stored. [slots.py:12](../diwan/slots.py#L12). Needed: a time zone on the lead, from the number or their words, and said back in it.
- [ ] ❌ **Sales lead reminds the broker 15 minutes before** (L113). There: reminders skip phone calls ("the broker's list has it"), and the card only alerts at creation and when overdue. [reminders.py:80](../diwan/agents/reminders.py#L80). Needed: a notice 15 minutes before the card is due.
- [x] ✅ **Rania tells the client the time is confirmed** (L113). There: "I've booked a call with Omar for…", and she answers "so he'll call at 10?" from the calendar. [reception.py:268](../diwan/agents/reception.py#L268), test: [test_client_answers.py](../tests/test_client_answers.py), browser: [call_flow.py](../e2e/call_flow.py)

### The PA behaviour · Hot lead, sweep, follow-ups (L114-116)

- [x] ✅ **Hot lead: Sales lead messages the broker with the facts** (L114). There: a card and notice from Rania: "🔥 Hot lead, ready to close", with listing, price, their words and answers. [reception.py:1478](../diwan/agents/reception.py#L1478), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] ❌ **Hot lead: "Book a viewing?" with buttons** (L114). There: the card has Called, Messaged, No answer and Not needed only. [inbox.html:228](../web/inbox.html#L228). Needed: a Book button, on the card and in the WhatsApp alert.
- [ ] 🟡 **Daily sweep: every morning each broker gets a list** (L115). There: one notice of the day's appointments, an hour before their start (not 08:30), and none if they have no appointments. [reminders.py:109](../diwan/agents/reminders.py#L109), test: [test_calendar.py](../tests/test_calendar.py), browser: [gaps_flow.py](../e2e/gaps_flow.py). Needed: 08:30, and a list even on an empty calendar.
- [ ] ❌ **Sweep: who to call** (L115). Needed: open call cards in the morning list.
- [ ] ❌ **Sweep: who's gone quiet** (L115). Needed: leads in the follow-up schedule or just nurtured.
- [ ] ❌ **Sweep: who's waiting on options** (L115). Needed: leads told "the broker will send options".
- [x] ✅ **Follow-ups on the owner's schedule** (L116). There: hours set on the Qualification page; a lead can have its own. [nudge.py:19](../diwan/agents/nudge.py#L19), [nudge.py:264](../diwan/agents/nudge.py#L264), test: [test_nudge.py](../tests/test_nudge.py), browser: [quiet_flow.py](../e2e/quiet_flow.py)
- [x] ✅ **Never at night** (L116). There: quiet hours; the sweep skips and the next time moves past them. [nudge.py:72](../diwan/agents/nudge.py#L72), test: [test_nudge.py](../tests/test_nudge.py), browser: [quiet_flow.py](../e2e/quiet_flow.py)
- [x] 🧪 **Never at Friday prayer** (L116). There: 11:30 to 13:30 on Fridays, a tick box. [nudge.py:22](../diwan/agents/nudge.py#L22), test: [test_nudge.py](../tests/test_nudge.py)
- [x] ✅ **Never the same message twice** (L116). There: a word-for-word repeat is skipped and logged. [nudge.py:294](../diwan/agents/nudge.py#L294), test: [test_nudge.py](../tests/test_nudge.py), browser: [quiet_flow.py](../e2e/quiet_flow.py)
- [ ] 🟡 **"Stop" means stop everywhere** (L116). There: follow-ups, reminders, nurture, Inbox sends and templates stop. Three other sends do not check it: document reminders and calendar move or cancel messages go through `_send` directly. [nudge.py:320](../diwan/agents/nudge.py#L320), [documents.py:284](../diwan/documents.py#L284), [reception.py:947](../diwan/agents/reception.py#L947), test: [test_nudge.py](../tests/test_nudge.py). Needed: the check inside `_send`.
- [ ] 🟡 **After-visit follow-ups speak about the visit** (L116, also case 6). There: the text exists, but the sweep looks the visit up as `viewing:V1` while the node id is `V1`, so it finds nothing and sends the general text. [nudge.py:283](../diwan/agents/nudge.py#L283). The test calls `text_for` directly and misses this. Needed: `g.nodes.get(st["visit"])`, and a sweep test.

### Exit: when a Case leaves Sales (L118-120)

- [ ] ❌ **The broker marks one outcome from four** (L120). There: no outcome control or event, only separate actions. Needed: an `Outcome` choice and an event.
- [x] ✅ **Outcome `converted`** (L120). There: the Convert button with the agreed price; moves to the path's converted stage and starts forms. [desk_stages.py:105](../diwan/desk_stages.py#L105), [inbox.html:608](../web/inbox.html#L608), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py)
- [x] ✅ **Outcome `follow up on [date]`** (L120). There: "Follow up on…" makes a card due then. [leads.py:296](../diwan/leads.py#L296), test: [test_front_door.py](../tests/test_front_door.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [x] ✅ **Outcome `not interested` (reason)** (L120). There: stage Lost needs a typed reason. Free text, no reason list. [desk_stages.py:69](../diwan/desk_stages.py#L69), [inbox.html:595](../web/inbox.html#L595), test: [test_front_door.py](../tests/test_front_door.py), browser: [property_flow.py](../e2e/property_flow.py)
- [ ] 🟡 **Outcome `no response`** (L120). There: "No answer" clears a card, and nothing follows from it; quiet leads drift to Nurture. [leads.py:27](../diwan/leads.py#L27). Needed: the outcome on the lead, with a next step.
- [ ] ❌ **`converted` emits `case.converted`** (L120). There: a `setting.changed` for the agreed price plus `stage.changed`; `case.converted` is in no code. [desk_stages.py:162](../diwan/desk_stages.py#L162). Needed: that event in `events.py`, `graph.py` and `_record`.
- [x] ✅ **Every Fact carried, nothing retyped** (L120). There: the lead and the deal are the same node, so facts and answers stay; `lead-` chats keep their deal. The event would not need to copy them. [inbox.py:165](../diwan/inbox.py#L165), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py)
- [x] ✅ **Deal takes over** (L120). There: the deal shows on the Deal desk with its path's stages, forms and steps. [desk_stages.py:79](../diwan/desk_stages.py#L79), test: [test_deal_desk.py](../tests/test_deal_desk.py), browser: [deal_flow.py](../e2e/deal_flow.py)

### Gaps to build (L122-126)

- [ ] ❌ **Outcomes** (L124). Needed: as above.
- [ ] ❌ **The broker escalation timer** (L124). Needed: as above.
- [ ] ❌ **Instagram / Facebook DM connection** (L125). Needed: as above. Comments and publishing work; DMs do not.
- [x] ✅ **Portal lead webhooks** (L125). There: as above. Real payloads not yet seen.
- [ ] ❌ **One heat-score setting used by Rania, the brief and Records alike** (L126). There: one hot setting, used by Rania only. Needed: the setting read by Nova's brief and by Records.

### Inbox rows of the bugs table (L368-372)

- [ ] 🟡 **One name per staff member** (L368). There: every name comes from `people.name(broker)`, and the header, the card and Rania's words all use the deal's broker now. But a site visit goes to the listing's agent, so the client can hear another name than the Inbox shows, and a transfer does not tell the client. [people.py:44](../diwan/people.py#L44), [reception.py:743](../diwan/agents/reception.py#L743). Needed: a test, a line to the client on transfer, and see Conflicts.
- [ ] ❌ **The signature matches the sender** (L368). There: a person's message has no signature, and a suggestion made before a transfer can be used as is. Needed: a check of a typed name against the sender, or an automatic signature. No test.
- [x] ✅ **"Qualified" means the form is complete, when set automatically** (L369). There: only `qualify.passed` moves it. [inbox.py:272](../diwan/inbox.py#L272), test: [test_qualify.py](../tests/test_qualify.py), browser: [front_door_flow.py](../e2e/front_door_flow.py)
- [ ] 🟡 **"Qualified" cannot be set by hand on an incomplete form** (L369). There: the profile's stage list moves it with no check. [desk_stages.py:47](../diwan/desk_stages.py#L47). Needed: the refusal, or the spec's stage rule.
- [ ] ❌ **The "step 3 of 8" bug** (L369). There: still on screen: a count of the pipeline stage, not of the form, so Qualified always says "step 3 of 8". [inbox.html:658](../web/inbox.html#L658). Needed: "Qualifying 3/8" from the form's answered and required counts; remove the fixed 8.
- [x] ✅ **Store the exact quote with each number** (L370, L462). There: a `deal_term` fact and `qualify.answer` keep the quote; the chip points to the fact. [scribe.py:122](../diwan/agents/scribe.py#L122), [inbox.py:74](../diwan/inbox.py#L74), test: [test_inbox.py](../tests/test_inbox.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [ ] ❌ **Budget out of range for the intent: Rania asks to confirm** (L370, L462). There: no range check; any amount of 1,000 or more is kept. [qualify.py:298](../diwan/qualify.py#L298). Needed: ranges per intent (settings), and a "just to confirm" question.
- [ ] 🟡 **The budget chip matches the budget answer** (L370). There: the tag reads the last `deal_term` fact, not the form's `budget_aed`, so the two can differ. [inbox.py:74](../diwan/inbox.py#L74). Needed: one source for the tag.
- [x] 🧪 **One suggestion per incoming message** (L371, L463). There: one `chat.suggested` per reply, and a burst gets one reply. [reception.py:1438](../diwan/agents/reception.py#L1438), [app.py:982](../diwan/app.py#L982), test: [test_burst.py](../tests/test_burst.py), [test_lessons.py](../tests/test_lessons.py)
- [ ] 🟡 **Only one suggestion shows** (L371). There: every old suggestion stays in the thread, and a repeated webhook delivery would make a second: `chat.received` has no provider message id to reject it. [inbox.html:346](../web/inbox.html#L346), [reception.py:1133](../diwan/agents/reception.py#L1133). Needed: a dedupe key, and hide suggestions that were answered.
- [ ] ❌ **Regenerate on request** (L371). Needed: a button and an endpoint that makes a new suggestion and replaces the old one.
- [x] ✅ **Convert opens the Case in Deal** (L372, L469). There: with no property named it goes to the Deal desk; otherwise a small form asks the price in place. [inbox.html:608](../web/inbox.html#L608), browser: [profile_flow.py](../e2e/profile_flow.py), [property_flow.py](../e2e/property_flow.py)
- [x] 🧪 **Convert shows the new Deal link** (L372, L469). There: the "Converted" card with "Open the deal →". [inbox.html:569](../web/inbox.html#L569). No check clicks the link, and [profile_flow.py:120](../e2e/profile_flow.py#L120) still expects the old words "Converted at AED…", which this card no longer writes, so check 10 looks stale.

### Sales command and blocks on screen (L453-472)

- [ ] 🟡 **Rania and Sales lead in the Sales room on the floor** (L458). There: the Sales room has Sales lead, Scribe, Deck and Follow-up, and its line says "Meetings become quoted facts"; Rania shows at the Front desk. [office3d.html:130](../web/office3d.html#L130). Needed: put Rania in Sales and rewrite the room's line. See Conflicts.
- [ ] ❌ **A Sales screen with these blocks** (L455). There: none. The Sales floor walls show facts and cards; the working screen is the Inbox. Needed: a Sales page, or Inbox views, for the eight below.
- [ ] 🟡 **Block: Call now queue** (L455). There: the "Needs you" tab, sorted by time left, with a countdown. [inbox.py:130](../diwan/inbox.py#L130), browser: [front_door_flow.py](../e2e/front_door_flow.py). Needed: call cards alone, minutes waited, one-tap call, escalation timer.
- [ ] 🟡 **Block: Hot leads** (L455). There: a 🔥 tag on each row. [inbox.html:279](../web/inbox.html#L279). Needed: a tab or filter; `listing()` has no hot view.
- [ ] 🟡 **Block: New leads by channel** (L455). There: a "New" tab and a portal tag on each row. Needed: counts by channel; `counts()` has none.
- [ ] ❌ **Block: Qualifying in progress, step x of n** (L455). There: a stage filter only. Needed: the x of n count (see above).
- [ ] 🟡 **Block: Follow-ups due today** (L455). There: the owner's next 20 follow-ups, on the Qualification page. [nudge.py:325](../diwan/agents/nudge.py#L325), [qualify.html:286](../web/qualify.html#L286). Needed: filtered to today and by broker, on the Sales screen.
- [ ] 🟡 **Block: Quiet clients** (L455). There: the Nurture tab mixes those who went quiet, those only looking and those not a fit; the profile shows each lead's state. [inbox.py:136](../diwan/inbox.py#L136). Needed: a quiet list of its own.
- [x] ✅ **Block: Each broker's day** (L455). There: the Calendar's day and week views per broker, with load. [slots.py:297](../diwan/slots.py#L297), [calendar.html](../web/calendar.html), test: [test_calendar.py](../tests/test_calendar.py), browser: [calendar_flow.py](../e2e/calendar_flow.py). Not on a Sales screen.
- [ ] 🟡 **Block: Outcome needed** (L455). There: the Calendar lists appointments "Past, not marked Done or No-show"; nothing lists calls with no outcome. [slots.py:376](../diwan/slots.py#L376). Needed: after a call card clears, ask for an outcome and list the leads without one.
- [ ] 🟡 **Fix first: one display name** (L460). There: see L368.
- [ ] 🟡 **Fix first: stage vs progress** (L461). There: see L369.
- [ ] 🟡 **Fix first: numbers** (L462). There: quotes yes, the out-of-range question no. See L370.
- [ ] 🟡 **Fix first: one suggestion** (L463). There: see L371.
- [ ] 🟡 **Build 1: Call now** (L465). There: a call card and alerts. Needed: last 3 messages, call button, 10-minute reassign. See L112.
- [ ] 🟡 **Build 2: Call later** (L466). There: the task and Rania's confirmation. Needed: client's time zone, the 15-minute reminder. See L113.
- [ ] 🟡 **Build 3: Sales lead daily sweep at 08:30** (L467). There: appointments only. See L115.
- [ ] ❌ **Build 4: Outcomes after every call** (L468). There: a card clears with a call result, never the lead's outcome. Needed: as L120.
- [ ] 🟡 **Build 5: Convert** (L469). There: the Deal link and the facts stay. Needed: `case.converted`.
- [ ] ❌ **Playwright: call now escalation** (L470). Needed: an e2e that waits past the timer. Overdue and Pool are pytest only.
- [ ] ❌ **Playwright: outcome required** (L470). Needed: the feature first.
- [ ] 🟡 **Playwright: convert lands in Deal with Facts** (L470). There: [profile_flow.py](../e2e/profile_flow.py) and [property_flow.py](../e2e/property_flow.py) convert and read the stage. Needed: open the Deal link and see the facts.

### Is the flow complete? The 15 gaps, status only (L620-640)

- [ ] 🟡 **1. Deal falls through** (L626). There: Lost with a typed reason, which releases the listing. [desk_stages.py:69](../diwan/desk_stages.py#L69), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py). Needed: reason list and what happens to money and paperwork.
- [ ] 🟡 **2. Who the party is** (L627). There: documents per role, and a company's trade licence. [desk_rules.py:32](../diwan/desk_rules.py#L32). Needed: non-resident, power of attorney, joint owners, estate.
- [x] ✅ **3. Co-broking** (L628). There: another agency's details and share, Form I, and the split in commission. [deal_property.py:21](../diwan/deal_property.py#L21), [finance.py:147](../diwan/agents/finance.py#L147), test: [test_deal_property.py](../tests/test_deal_property.py), browser: [property_flow.py](../e2e/property_flow.py). Who talks to the client is not modelled.
- [ ] 🟡 **4. Seller side and listings in full** (L629). There: Form A, permit number, price-change proposals, portal feed. Needed: listing intake from a seller lead, permit and listing expiry, photos flow.
- [ ] 🟡 **5. Seller has a mortgage** (L630). There: a fixed step in the ready path, "Seller's mortgage cleared: liability and clearance letters". [desk_rules.py:49](../diwan/desk_rules.py#L49). Needed: the Sales question that decides it.
- [ ] ❌ **6. Tenanted units being sold** (L631). There: only the occupancy answer. Needed: tenancy and notice steps.
- [ ] 🟡 **7. Deposit held, returned, refunded** (L632). There: who holds it (a setting), and a release task. [desk_rules.py:39](../diwan/desk_rules.py#L39), [finance.py:113](../diwan/agents/finance.py#L113). Needed: return and refund when a deal falls through.
- [ ] ❌ **8. Bounced cheques** (L633). Needed: an event, a chase and an owner decision; "bounce" is nowhere in the code.
- [ ] 🟡 **9. Rental renewals and move-out** (L634). There: one dated task each after close. [operations.py:275](../diwan/agents/operations.py#L275). Needed: the flows behind them.
- [ ] 🟡 **10. Expiry of what was uploaded** (L635). There: checked at upload only. [documents.py:162](../diwan/documents.py#L162). Needed: a daily watch; pre-approval, Form A and permit have no date.
- [ ] 🟡 **11. Client in another language** (L636). There: English and Arabic. [reception.py:79](../diwan/agents/reception.py#L79), test: [test_followup.py](../tests/test_followup.py), browser: [gaps_flow.py](../e2e/gaps_flow.py). Needed: Russian, Hindi, Chinese, and a setting.
- [ ] 🟡 **12. Consent and privacy** (L637). There: "stop" only. Needed: opt-in record, retention, delete on request.
- [ ] ❌ **13. Disputes and complaints** (L638). Needed: a log with an owner. The word appears only for a payer in dispute, in a test.
- [ ] 🟡 **14. Staff leave or are reassigned** (L639). There: a lead at a time by Transfer, with its card; an "away" tick; roles can change hands. [leads.py:209](../diwan/leads.py#L209), [roles.py:55](../diwan/roles.py#L55), test: [test_front_door.py](../tests/test_front_door.py). Needed: move all of a person's Cases at once, and their PA memory.
- [x] ✅ **15. Commission paid by the developer** (L640). There: `commission_from` per path, developer for off-plan, invoice to the developer. [desk_rules.py:60](../diwan/desk_rules.py#L60), test: [test_desk_rules.py](../tests/test_desk_rules.py), browser: [deal_flow.py](../e2e/deal_flow.py)

### Open questions only the office can answer (L642-650)

- [ ] ❓ **Which deal types the office does** (L644). Needs the office's answer: confirm the list. Default: three paths (ready, off-plan, rental) and deal kinds in Settings; demo values.
- [ ] ❓ **Commission rates and who pays; when invoiced** (L645). Needs the office's answer: the figures. Default: 2% buyer, 2% developer, 5% tenant. [desk_rules.py:44](../diwan/desk_rules.py#L44)
- [ ] ❓ **Does the office hold client money?** (L646). Needs the office's answer: yes or no, per deal type. Default: the `deposit_held_by` setting. [agency_forms.py:236](../diwan/agency_forms.py#L236)
- [ ] ❓ **Source-of-funds and cash thresholds** (L647). Needs the compliance officer's answer: the numbers. Default: cash report at AED 55,000; no source-of-funds threshold. [desk_rules.py:27](../diwan/desk_rules.py#L27)
- [ ] ❓ **Which mortgage brokers or banks** (L648). Needs the office's answer: the list. No setting exists; one is needed.
- [ ] ❓ **Languages Rania should speak** (L649). Needs the office's answer: the list. Default: English and Arabic, fixed; the Languages setting is for posts only. [business.py:128](../diwan/business.py#L128)
- [ ] ❓ **How long documents are kept, and who may delete them** (L650). Needs the office's answer: the period and the person. No setting exists; everything is kept.

### Part 4 · The 16 cases (L846-869)

- [ ] ❌ **1. Match on phone, email or name + listing** (L854). There: nothing compares chats; `email` from portals is stored and unused. Needed: a match check when a lead opens.
- [ ] ❌ **1. Propose a merge to the broker** (L854). Needed: a card with the two leads. Today the broker has to notice and type the other number.
- [x] ✅ **1. The merge itself** (L854). There: both histories in one thread, missing answers copied, the other lead closed. [leads.py:244](../diwan/leads.py#L244), test: [test_front_door.py](../tests/test_front_door.py), browser: [profile_flow.py](../e2e/profile_flow.py)
- [ ] 🟡 **1. Never merge automatically when two brokers own them** (L854). There: no automatic chat merge, but one broker alone can merge a colleague's lead, who is only told, and a WhatsApp from a known name joins that deal silently. [leads.py:273](../diwan/leads.py#L273), [reception.py:499](../diwan/agents/reception.py#L499). Needed: the other broker's yes or the Sales manager's. See Conflicts.
- [ ] 🟡 **2. First owner keeps the client** (L855). There: the owner stays, but `/assign` has no permission check, so anyone can Transfer. [app.py:1191](../diwan/app.py#L1191), [leads.py:209](../diwan/leads.py#L209). Needed: only the Sales lead or manager reassigns.
- [x] 🧪 **2. The move is logged** (L855). There: `lead.assigned` with who and why; `lead.claimed` from the Pool. [leads.py:115](../diwan/leads.py#L115), test: [test_leads.py](../tests/test_leads.py)
- [ ] ❌ **2. A claim on another broker's client and a decision** (L855). Needed: a claim event and a yes-or-no decision for the manager. Pool claims are the only kind.
- [ ] ❌ **3. On `listing.live`, match against qualified buyers** (L856). There: no such event, nothing runs when a listing arrives. `recommend()` could do the matching. [reception.py:324](../diwan/agents/reception.py#L324). Needed: the event, emitted when a listing gets a permit and is available, and a match job.
- [ ] ❌ **3. Brokers get a list** (L856). Needed: a notice or card per broker.
- [ ] ❌ **3. Rania sends only with the broker's yes** (L856). There: the opposite happens in one place: a follow-up sends a new listing that fits with no yes. [nudge.py:231](../diwan/agents/nudge.py#L231). See Conflicts.
- [ ] ❌ **4. Key or access arranged with the seller or tenant** (L857). Needed: a task when a viewing is booked.
- [ ] ❌ **4. Tenant notice** (L857). Needed: a message or task for tenanted units.
- [x] ✅ **4. Confirmation to the client 24h and 2h before** (L857). There: owner's times, in quiet-hour rules, template outside the window. [reminders.py:13](../diwan/agents/reminders.py#L13), test: [test_calendar.py](../tests/test_calendar.py), browser: [calendar_flow.py](../e2e/calendar_flow.py), [gaps_flow.py](../e2e/gaps_flow.py)
- [ ] ❌ **4. Broker travel time** (L857). There: appointments can sit back to back at different properties. Needed: a gap in `slots.is_open`.
- [x] 🧪 **5. Broker marks no-show** (L858). There: a button after the time, broker or owner only. [app.py:1690](../diwan/app.py#L1690), [calendar.html:577](../web/calendar.html#L577), test: [test_calendar.py](../tests/test_calendar.py). No browser check clicks it.
- [ ] ❌ **5. Rania sends one reschedule message** (L858). There: the no-show event triggers nothing. Needed: the message after `appointment.noshow`.
- [ ] ❌ **5. Second no-show lowers the heat score** (L858). Needed: heat score first; a count of no-shows.
- [x] ✅ **6. Broker's feedback** (L859). There: typed notes or a recorded visit become a summary with quotes. Voice note means the Meeting screen, not a phone note. [visit.py:59](../diwan/agents/visit.py#L59), test: [test_followup.py](../tests/test_followup.py), browser: [visit_flow.py](../e2e/visit_flow.py)
- [ ] 🟡 **6. Rania asks the client the next day** (L859). There: a visit follow-up at 24 hours, but the bug at [nudge.py:283](../diwan/agents/nudge.py#L283) sends the general text, and a reply is not read as feedback. Test only of `text_for`: [test_sales_journey.py](../tests/test_sales_journey.py). Needed: the fix, and storing the reply.
- [ ] 🟡 **6. Feedback is a Fact** (L859). There: `visit.summarized`, kept on the deal with quotes, not `fact.created`. [graph.py:423](../diwan/graph.py#L423). Needed: facts, or a decision that this counts.
- [ ] ❌ **6. Seller report includes it** (L859). Needed: a seller report; none exists.
- [ ] ❌ **7. All offers side by side for the seller** (L860). There: one deal, one agreed price. Needed: an offer per buyer on a listing, and the view.
- [ ] ❌ **7. Seller's choice quoted** (L860). Needed: with the above.
- [ ] ❌ **7. Others told politely** (L860). Needed: with the above.
- [ ] 🟡 **8. Rental move-out** (L861). There: one task, "Move-out: inspection, the security deposit refunded and Ejari cancelled", dated from the tenancy end. [operations.py:280](../diwan/agents/operations.py#L280). Needed: tenant notice as a Fact, inspection with photos vs move-in, deductions, landlord approval, deposit return tracked, Ejari cancellation.
- [ ] ❌ **9. Rent increase at renewal** (L862). There: a renewal question only. Needed: the rent index check and a result to the landlord with its source.
- [x] 🧪 **10. Returns: no advice or promise** (L863). There: a fixed reply and a handover, whichever model is on. [reception.py:997](../diwan/agents/reception.py#L997), test: [test_reception.py](../tests/test_reception.py)
- [ ] ❌ **10. Visas, legal, tax: same treatment** (L863). There: no pattern for them; the rules reply "Thank you, noted" and no one hears unless it was a question, and then only at qualifying. A model is told only "anything the sources do not answer". [reception.py:28](../diwan/agents/reception.py#L28). Needed: add them to the fixed topics.
- [x] 🧪 **10. Broker Task** (L863). There: `hand_over` adds a task and a card. [reception.py:566](../diwan/agents/reception.py#L566), test: [test_reception.py](../tests/test_reception.py)
- [ ] 🟡 **11. Payment instructions only from the developer's documents** (L864). There: the schedule comes from the signed SPA, and instalments go to escrow, never held. [finance.py:239](../diwan/agents/finance.py#L239), test: [test_deal_desk.py](../tests/test_deal_desk.py). Needed: where instructions reach the client.
- [ ] 🟡 **11. Rania never sends bank details from chat** (L864). There: she answers from cards and listings only, but nothing checks a reply for an IBAN or account number. Needed: a code check, like the amount check at [reception.py:1057](../diwan/agents/reception.py#L1057).
- [ ] ❌ **11. A change of account details is a Compliance flag** (L864). Needed: see the fraud guard.
- [ ] 🟡 **12. Broker licence number in People settings** (L865). There: each broker's BRN number is in the Deal desk rules, not People. [desk_rules.py:40](../diwan/desk_rules.py#L40). Needed: the expiry date.
- [ ] ❌ **12. Warn 30 days before** (L865). Needed: a sweep.
- [ ] ❌ **12. An expired broker can't be assigned new Cases** (L865). Needed: a check in `leads.pick` and `assign`.
- [ ] ❌ **13. Mortgage broker referral with consent** (L866). Needed: an event with consent and who it went to.
- [ ] ❌ **13. Referral fee is a Finance line** (L866). Needed: a line on the deal.
- [ ] 🟡 **14. Off-plan snagging (Phase 2)** (L867). There: a step name only. [desk_rules.py:65](../diwan/desk_rules.py#L65). Needed: list with photos, developer tasks, re-inspection. Later phase.
- [ ] ❌ **15. Property management room (Phase 2)** (L868). Needed: rent collection, maintenance, statements, renewals. Later phase.
- [ ] ❌ **16. Commercial and holiday homes (Phase 2)** (L869). There: the paths are editable, but no checklist or permit exists; Office is a property type. Needed: their paths. Later phase.
- [ ] ❌ **Fraud guard: never acted on by an agent** (L871). There: nothing reads "change bank details" or "pay another account"; `NOT_MINE` only catches "third party", "offshore" and similar. [reception.py:28](../diwan/agents/reception.py#L28). Needed: a fixed pattern before any reply.
- [ ] ❌ **Fraud guard: a Now flag to Finance and Compliance** (L871). Needed: a raised card to both.
- [ ] ❌ **Fraud guard: confirmed by phone with a known number** (L871). Needed: a task, with the known number on it.

### Listing upkeep (L873-887)

- [ ] 🟡 **Every check ends in one of three results** (L875). There: no checks. The feed sync does a version of it: refreshes fields, or marks a listing that left the feed off-market. [leads.py:332](../diwan/leads.py#L332), test: [test_leads.py](../tests/test_leads.py). Needed: the check itself.
- [ ] ❌ **Permit: an expiry date on the listing** (L879). There: a permit number only; a listing with a number is treated as good for ever. [knowledge.py:88](../diwan/knowledge.py#L88). Needed: the field, also in the feed and forms.
- [ ] ❌ **Permit: warnings at 14 and 3 days (settings)** (L879). Needed: a daily sweep and settings.
- [ ] ❌ **Permit: broker's PA reminds the broker** (L879). Needed: a notice.
- [ ] ❌ **Permit: renewal prepared up to Submit; a person submits** (L879). Needed: an Ops task and draft.
- [ ] ❌ **Permit: on expiry, every portal ad and Studio post paused, broker told** (L879). Needed: the pause, a status that stops `advertised()`, and a hold in Studio.
- [ ] ❌ **Form A expiring: 14 days before** (L880). Needed: an expiry on Form A; a signed form has none.
- [ ] ❌ **Form A: seller asked by WhatsApp** (L880). Needed: a message.
- [ ] ❌ **Form A: renew or close, `listing_expiring` stage** (L880). Needed: the stage; no listing-side stages exist.
- [ ] ❌ **Ready unit: every 7 days for sale, 3 for rent (settings)** (L881). Needed: a sweep and settings. The nearest thing marks a feed listing stale after 7 days. [knowledge.py:78](../diwan/knowledge.py#L78)
- [ ] ❌ **Ready unit: check before any viewing is booked** (L881). There: `book()` does not ask. [reception.py:733](../diwan/agents/reception.py#L733). Needed: the check, or a rule for what Rania says.
- [ ] ❌ **Broker's PA messages the seller or landlord** (L881). Needed: the seller's number on the listing; listings carry no owner contact.
- [ ] ❌ **Yes: listing refreshed with today's date** (L881). Needed: `listing.confirmed`.
- [ ] 🟡 **Price or status changed: a superseding Fact, so everything updates or is withdrawn** (L881). There: a price change is an accepted proposal, and Rania quotes it from her next message; the portal gets a task. It is not a Fact, and Studio ads and scripts are not updated. [leads.py:361](../diwan/leads.py#L361), [catalog.html:243](../web/catalog.html#L243), test: [test_leads.py](../tests/test_leads.py), browser: [knowledge_flow.py](../e2e/knowledge_flow.py). Needed: the link to ads and scripts.
- [ ] 🟡 **Sold or let elsewhere: withdrawn everywhere** (L881). There: reserved, sold, retired or off-market stop Rania and bring a task to take it off the portals. [leads.py:371](../diwan/leads.py#L371), test: [test_leads.py](../tests/test_leads.py). Needed: Studio posts withdrawn too.
- [ ] ❌ **Sold elsewhere: matched buyers told** (L881). Needed: the matched-buyer list (case 3).
- [ ] ❌ **Sold elsewhere: Case closed as lost, reason sold elsewhere** (L881). Needed: an automatic close on open deals with that listing.
- [ ] ❌ **No answer: a broker task to call after 48 hours** (L882). Needed: with the check.
- [ ] ❌ **No answer: marked unconfirmed, no viewings, ads paused** (L882). Needed: the status and owner's limit.
- [ ] ❌ **Listing not refreshed on a portal** (L883). Needed: the portal's rule in settings, a drafted refresh, a person's confirm.
- [ ] ❌ **Off-plan price list: updates on a new one or after 14 days** (L884). Needed: a date on prices; project cards only have a general review date. [knowledge.py:66](../diwan/knowledge.py#L66)
- [ ] ❌ **Old prices shown "to be confirmed", Rania won't quote** (L884). Needed: a check in `prompt_sources`, the listing lines and the amount guard.
- [ ] ❌ **Tenant moving out: re-listing 60 days before, with the landlord's yes** (L885). Needed: a trigger from the tenant's notice.
- [ ] ❌ **Event `permit.expiring`** (L887). Needed: in `events.py` and `graph.py`.
- [ ] ❌ **Event `permit.expired`** (L887). Needed: as above.
- [ ] ❌ **Event `listing.check_due`** (L887). Needed: as above.
- [ ] ❌ **Event `listing.confirmed`** (L887). Needed: as above.
- [ ] ❌ **Event `listing.unconfirmed`** (L887). Needed: as above.
- [ ] ❌ **Event `listing.withdrawn`** (L887). Needed: as above. Today withdrawal is a `listing.added` with a status.
- [ ] ❌ **Consumers: Ops, Sales, Marketing pauses posts** (L887). Needed: handlers.
- [ ] ❌ **Consumers: seller's weekly report shows when last confirmed** (L887). Needed: the report; see case 6.

<a id="part-d"></a>

## Part D: Deal and Operations

Read this first. None of the spec's Deal or Operations event names exist anywhere in the code (`case.converted`, `form.sent`, `form.ready`, `form.signed`, `form.expiring`, `doc.received`, `doc.filed`, `deal.ready_for_transfer`, `transfer.booked`, `transfer.completed`, `compliance.cleared`, `noc.received`, `funds.ready`, `oqood.received`, `ejari.ready`, `listing.ready`, `listing.signed`, `listing.live`, `case.closed`, and the rest: a search of diwan, web, tests and e2e finds none). The closest real events are named on each line. Marks: ✅ built with a browser check, 🧪 built with pytest only or no test, 🟡 partly there, ❌ not there, ❓ the office must answer.

### Room 3 · Deal: who owns it (L128-130)

- [ ] 🟡 **Deal owns the Case from conversion to ready-for-transfer** (L130). There: the Deal desk page and the Operations lead run a converted deal; conversion is `stage.changed` plus the agreed price in settings. [desk_stages.py:105](../diwan/desk_stages.py#L105), test: [deal_flow.py](../e2e/deal_flow.py#L760). Needed: a `case.converted` event carrying the Facts, and an end point (see Exit below).
- [ ] ❌ **Lead agent: Deal manager, a PA for the deal desk** (L130). Needed: a charter in [charters.py](../diwan/agents/charters.py) and an agent that owns the chase; today only `ops`, `formf` and `transfer` exist, and the transactions officer and broker do this work by hand.
- [ ] 🟡 **Makes sure every form is sent, signed and checked** (L130). There: agency forms and Form F track drafted, signing links and signed; "sent" is not recorded because the broker shares by hand. [agency_forms.py:59](../diwan/agency_forms.py#L59), test: [deal_flow.py](../e2e/deal_flow.py#L807). Needed: a `form.sent` record per form and per recipient.
- [x] ✅ **Deal does not judge identity or money** (L130). There: only the compliance holder confirms documents and records screening; Deal desk cards name who may act. [documents.py:218](../diwan/documents.py#L218), [compliance.py:77](../diwan/agents/compliance.py#L77), test: [deal_flow.py](../e2e/deal_flow.py#L158)
- [ ] ❌ **Waits for Compliance's clearance before anything binding** (L130). Needed: a block in [operations.py:81](../diwan/agents/operations.py#L81) and [signing.py:74](../diwan/signing.py#L74); today Form F can be drafted, signed and submitted with screening still open (only closing reads Compliance, [operations.py:195](../diwan/agents/operations.py#L195)).

### Checklist by deal type (L132-142)

- [ ] 🟡 **Checklist picked from the Case's Facts** (L132). There: the path comes from the sales desk's listing filter or the broker's choice, not from Facts. [desk_rules.py:107](../diwan/desk_rules.py#L107), test: [test_desk_rules.py](../tests/test_desk_rules.py#L80). Needed: a rule that reads the Facts (sale or rent, cash or mortgage, seller mortgage, off-plan) and picks a template.
- [x] ✅ **Owner can edit each template** (L132). There: rules panel edits each path's steps, who each waits on, stages and closing; `setting.changed` keeps who. [deal.html:259](../web/deal.html#L259), [desk_rules.py:180](../diwan/desk_rules.py#L180), test: [deal_flow.py](../e2e/deal_flow.py#L402)
- [ ] 🟡 **Five templates: secondary cash, secondary mortgage, off-plan, rental, listing** (L134-140). There: three paths (ready, offplan, rent). Path list is fixed in code, so the owner cannot add one. [desk_rules.py:85](../diwan/desk_rules.py#L85). Needed: separate cash and mortgage templates (or conditional lines), and a listing template.
- [x] ✅ **Secondary cash: Form A with seller and broker** (L136). There: drafted at conversion when we act for the seller; link for seller and broker. [agency_forms.py:49](../diwan/agency_forms.py#L49), [signing.py:24](../diwan/signing.py#L24), test: [property_flow.py](../e2e/property_flow.py#L108)
- [x] ✅ **Secondary cash: Form B with buyer and broker** (L136). There: drafted at conversion when we act for the buyer. [agency_forms.py:49](../diwan/agency_forms.py#L49), test: [deal_flow.py](../e2e/deal_flow.py#L836)
- [x] ✅ **Secondary cash: Form I if another agency is involved** (L136). There: A and I, or B and I, by who is on the other side. [agency_forms.py:49](../diwan/agency_forms.py#L49), test: [deal_flow.py](../e2e/deal_flow.py#L769)
- [x] ✅ **Secondary cash: Form F (MOU)** (L136). There: plan from live facts, PDF, signing links for each party. [operations.py:64](../diwan/agents/operations.py#L64), [signing.py:29](../diwan/signing.py#L29), test: [deal_flow.py](../e2e/deal_flow.py#L1012)
- [ ] 🟡 **Secondary cash: IDs and passports** (L136). There: buyer's and seller's portal link, on the sides we act for. Not tracked as checklist Tasks and not a gate before transfer. [documents.py:85](../diwan/documents.py#L85), test: [deal_flow.py](../e2e/deal_flow.py#L899). Needed: each document as a checklist line that can block.
- [ ] 🟡 **Secondary cash: title deed** (L136). There: in the seller's default list, typed number and a photo check only. [desk_rules.py:32](../diwan/desk_rules.py#L32). Needed: as a checklist line, and the unit check (see Upload checks).
- [ ] 🟡 **Secondary cash: developer NOC** (L136). There: a tick step with no document attached. [desk_rules.py:50](../diwan/desk_rules.py#L50), test: [deal_flow.py](../e2e/deal_flow.py#L246). Needed: upload of the NOC on the step.
- [ ] 🟡 **Secondary cash: DLD transfer appointment** (L136). There: tick step "Trustee office appointment booked" with no date. [desk_rules.py:52](../diwan/desk_rules.py#L52). Needed: date, place and an appointment record.
- [ ] 🟡 **Secondary mortgage: pre-approval, valuation, final offer letter** (L137). There: one tick step "Buyer's mortgage: valuation and the bank's final offer"; pre-approval only appears as text in Compliance's "balance funding" proof. [desk_rules.py:48](../diwan/desk_rules.py#L48), [compliance.py:150](../diwan/agents/compliance.py#L150). Needed: three lines, each with its document.
- [ ] 🟡 **Secondary mortgage: bank's manager's cheques** (L137). There: one tick step for all cheques. [desk_rules.py:51](../diwan/desk_rules.py#L51). Needed: a line per cheque with payee and amount.
- [ ] 🟡 **Secondary mortgage: liability letter if the seller has a mortgage** (L137). There: tick step on every ready deal; a person marks it "not needed" by hand. [desk_rules.py:49](../diwan/desk_rules.py#L49), [operations.py:123](../diwan/agents/operations.py#L123), test: [deal_flow.py](../e2e/deal_flow.py#L688). Needed: added only when the Facts say the seller has a mortgage.
- [ ] 🟡 **Off-plan: reservation form** (L138). There: tick step with the developer's KYC; no form or upload. [desk_rules.py:62](../diwan/desk_rules.py#L62), test: [deal_flow.py](../e2e/deal_flow.py#L632). Needed: the reservation document on the deal.
- [ ] 🟡 **Off-plan: booking payment** (L138). There: an expected payment only if the client's words promised one. [finance.py:16](../diwan/agents/finance.py#L16). Needed: a booking line on every off-plan deal, amount from the owner's percentage.
- [ ] 🟡 **Off-plan: SPA from the developer** (L138). There: tick step; the reference is typed in the schedule form. [desk_rules.py:63](../diwan/desk_rules.py#L63). Needed: SPA upload.
- [ ] 🟡 **Off-plan: Oqood registration** (L138). There: tick step, no certificate. [desk_rules.py:64](../diwan/desk_rules.py#L64). Needed: certificate upload.
- [x] ✅ **Off-plan: payment plan schedule** (L138). There: instalments entered, must add up, each on its date into escrow. [finance.py:265](../diwan/agents/finance.py#L265), test: [deal_flow.py](../e2e/deal_flow.py#L653)
- [ ] 🟡 **Rental: tenancy contract** (L139). There: tick step; start and end dates typed as terms. [desk_rules.py:75](../diwan/desk_rules.py#L75), test: [deal_flow.py](../e2e/deal_flow.py#L476). Needed: the contract generated and signed (see Rental step 4).
- [ ] 🟡 **Rental: Ejari** (L139). There: tick step; fee AED 220 shown. [desk_rules.py:78](../diwan/desk_rules.py#L78), test: [deal_flow.py](../e2e/deal_flow.py#L476). Needed: certificate upload.
- [x] ✅ **Rental: cheques** (L139). There: equal cheques spread from the start date, each expected on its day. [finance.py:249](../diwan/agents/finance.py#L249), test: [deal_flow.py](../e2e/deal_flow.py#L526)
- [x] ✅ **Rental: security deposit** (L139). There: Finance expects the owner's percentage of the yearly rent. [operations.py:149](../diwan/agents/operations.py#L149), test: [deal_flow.py](../e2e/deal_flow.py#L479)
- [ ] 🟡 **Rental: IDs** (L139). There: tenant only. [documents.py:47](../diwan/documents.py#L47). Needed: landlord's identity set too.
- [ ] ❌ **Rental: title deed copy** (L139). Needed: landlord party in [documents.py:44](../diwan/documents.py#L44) with `title_deed`.
- [ ] ❌ **Rental: landlord's authorisation if a POA** (L139). Needed: a POA document kind and a Fact or term saying a POA acts.
- [ ] ❌ **Listing template: Form A, title deed, ID, Trakheesi permit, photos booked** (L140). Needed: a listing path with a seller party; Form A today only exists on a buyer deal at conversion.
- [ ] 🟡 **Each line is a Task** (L142). There: transfer steps are tasks; documents and forms are tasks only once uploaded or drafted. [operations.py:105](../diwan/agents/operations.py#L105), test: [test_deal_desk.py](../tests/test_deal_desk.py#L204). Needed: one Task per line from conversion on.
- [ ] 🟡 **Each line has an owner room** (L142). There: all steps go to the transactions officer as agent `transfer`; `waiting_on` says who outside. [operations.py:108](../diwan/agents/operations.py#L108). Needed: an `owner_room` per step in the template (Deal, Operations, Compliance, Finance).
- [ ] ❌ **Each line has a due date** (L142). Needed: a `due` on steps; only payments and after-closing tasks have one today.
- [ ] ❌ **Each line lists the Facts it depends on** (L142). Needed: `rests_on` on transfer steps; [operations.py:108](../diwan/agents/operations.py#L108) sets none, so a correction never touches them.

### The client form portal (L144-151)

- [ ] 🟡 **WhatsApp with a private link and a list of what is needed** (L146). There: the first message is never sent. The link is created silently and a person copies it; the first WhatsApp is the reminder two days later, documents only. [documents.py:96](../diwan/documents.py#L96), [deal.html:836](../web/deal.html#L836), test: [test_desk_rules.py](../tests/test_desk_rules.py#L729). Needed: send on creation, naming the items, using the WhatsApp template rules.
- [ ] 🟡 **Signing links go by WhatsApp too** (L146). There: the broker copies each link. [deal.html:805](../web/deal.html#L805), test: [deal_flow.py](../e2e/deal_flow.py#L836). Needed: send through the same message, or see Conflicts.
- [ ] 🟡 **Seller gets the link too** (L146). There: seller's phone is forced empty and the name is "the seller". [documents.py:97](../diwan/documents.py#L97). Needed: seller name and phone on the deal.
- [x] ✅ **Link opens a mobile page with no login** (L147). There: public pages behind a token, narrow layout. [access.py:45](../diwan/access.py#L45), [docs.html:12](../web/docs.html#L12), test: [deal_flow.py](../e2e/deal_flow.py#L853)
- [ ] 🟡 **Page shows only this client's missing items** (L147). There: shows every item on the link, with received ones ticked, and forms sign on a separate page and link. [documents.py:115](../diwan/documents.py#L115). Needed: one link listing documents and forms together, missing only.
- [ ] 🟡 **Pre-filled from the Facts (name, unit, price)** (L147). There: the signing page shows the form's filled lines and name; the documents page shows the name only and the client types everything. [signing.py:117](../diwan/signing.py#L117), [docs.html:49](../web/docs.html#L49), test: [deal_flow.py](../e2e/deal_flow.py#L853). Needed: pre-fill on documents.
- [ ] ❌ **Signature drawn on screen (preferred)** (L148). Needed: a canvas on [sign.html:56](../web/sign.html#L56); only a file picker exists.
- [x] ✅ **Signature by uploaded photo** (L148). There: PNG or JPEG file. [signing.py:123](../diwan/signing.py#L123), test: [deal_flow.py](../e2e/deal_flow.py#L856)
- [x] ✅ **Checked on arrival, before the client leaves** (L149). There: the upload request itself runs the checks. [documents.py:174](../diwan/documents.py#L174), test: [deal_flow.py](../e2e/deal_flow.py#L919)
- [x] ✅ **A failed check asks for a re-upload on the spot, with the reason** (L149). There: error beside the item, button live again. [docs.html:60](../web/docs.html#L60), test: [deal_flow.py](../e2e/deal_flow.py#L919)
- [ ] ❌ **WhatsApp receipt on submit naming what came in and what is next** (L150). Needed: a send after `docs.received` and `sign.signed`; the client only sees a line on the page ("your broker will be in touch"). [docs.html:44](../web/docs.html#L44)
- [ ] 🟡 **The Task closes on submit** (L150). There: there is no Task to close at upload; a compliance check Task opens instead and closes on her confirmation. [documents.py:209](../diwan/documents.py#L209), test: [deal_flow.py](../e2e/deal_flow.py#L934). Needed: the checklist line closes at upload or at confirmation, one rule.
- [x] ✅ **Document stored on the Case** (L150). There: saved in media, filed with Records against the deal once confirmed. [documents.py:238](../diwan/documents.py#L238), test: [deal_flow.py](../e2e/deal_flow.py#L934)
- [ ] 🟡 **`doc.received` emitted** (L150). There: `docs.received` from the portal and `document.filed` after confirmation, but only `sign.signed` for signatures. [documents.py:207](../diwan/documents.py#L207). Needed: the spec's name, or the spec updated to these.
- [ ] 🟡 **Gentle nudge after 24 hours** (L151). There: every 2 days by default (setting, minimum 1 day), documents only. No nudge at all for unsigned forms. [documents.py:254](../diwan/documents.py#L254), test: [test_desk_rules.py](../tests/test_desk_rules.py#L729). Needed: the 24h first step, and signing links in the sweep.
- [ ] 🟡 **Broker call Task after 48 hours** (L151). There: after 3 reminders, about day 8 by default. [documents.py:272](../diwan/documents.py#L272), test: [test_desk_rules.py](../tests/test_desk_rules.py#L749). Needed: hours ladder.
- [ ] ❌ **Owner sees it in the brief after 72 hours** (L151). Needed: an owner line in [nova.py:506](../diwan/agents/nova.py#L506); the call Task goes only to the broker's brief.
- [ ] 🟡 **Same quiet hours as Sales** (L151). There: a fixed 09:00-20:00 in code, not the owner's quiet hours, and no Friday prayer. [documents.py:256](../diwan/documents.py#L256), compare [nudge.py:73](../diwan/agents/nudge.py#L73), test: [test_desk_rules.py](../tests/test_desk_rules.py#L743). Needed: use the nudge quiet check.
- [ ] 🟡 **Reminders owner-settable** (L151). There: `docs_reminder_days`, `docs_reminders`, `sign_link_days` exist in the rules and API, but no field on any screen. [desk_rules.py:31](../diwan/desk_rules.py#L31). Needed: fields in the rules panel.
- [ ] ❌ **An expired link can be replaced** (L147, L481). Needed: a "new link" action. The client is told "Ask your broker for a new one", but neither link can be remade: both skip a party or signer already asked, and the sweep stops at expiry, so the deal silently stalls. [signing.py:90](../diwan/signing.py#L90), [documents.py:93](../diwan/documents.py#L93), [documents.py:264](../diwan/documents.py#L264)

### Upload checks (L153-162)

- [ ] 🟡 **Answers within seconds** (L153). There: checks run in the request; nothing times them. No test. [documents.py:174](../diwan/documents.py#L174). Needed: nothing to build today; a limit once a vision call is added.
- [ ] ❌ **Signature: dark ink on a plain light background** (L157). Needed: an image test in [signing.py:123](../diwan/signing.py#L123), which reads only format, size and readability.
- [ ] ❌ **Signature: no face** (L157). Needed: a face detector or vision check. A selfie is accepted today.
- [ ] ❌ **Signature: no printed text block** (L157). Needed: a text-block test. A photo of a document is accepted today.
- [ ] ❌ **Signature: not blank** (L157). Needed: an ink-coverage test. A plain white image of 120x40 passes.
- [ ] ❌ **Signature: not a screenshot of a typed name** (L157). Needed: stroke analysis or vision.
- [ ] ❌ **Signature rejection message** (L157). Needed: the spec's message; today it only rejects by format and size.
- [ ] 🟡 **Passport / EID: document type is right** (L158). There: the client picks the slot; nothing reads the image, the compliance officer compares later. [documents.py:147](../diwan/documents.py#L147), test: [deal_flow.py](../e2e/deal_flow.py#L926). Needed: vision read at upload.
- [ ] 🟡 **Passport / EID: name matches the Case** (L158). There: typed name on EID front only, a flag for the officer rather than a rejection, skipped for the seller, and no name on the passport. [documents.py:197](../diwan/documents.py#L197), test: [test_desk_rules.py](../tests/test_desk_rules.py#L703). Needed: rejection, passport name, seller's name.
- [ ] 🟡 **Passport / EID: not expired** (L158). There: rejected, from the date the client types, so a false date passes. [documents.py:167](../diwan/documents.py#L167), test: [test_desk_rules.py](../tests/test_desk_rules.py#L683). Needed: date read from the image.
- [ ] ❌ **Passport / EID: all 4 corners visible** (L158). Needed: edge detection; only the page's words ask for it. [docs.html:45](../web/docs.html#L45)
- [ ] 🟡 **Passport / EID: readable** (L158). There: size, darkness, glare and blur on photos. A PDF skips them all. [documents.py:124](../diwan/documents.py#L124), [documents.py:189](../diwan/documents.py#L189), test: [deal_flow.py](../e2e/deal_flow.py#L919). Needed: run the checks on a PDF's page.
- [x] ✅ **Passport / EID: says which failed, in one line** (L158). There: one specific line per failure. [documents.py:124](../diwan/documents.py#L124), test: [deal_flow.py](../e2e/deal_flow.py#L919)
- [ ] ❌ **Title deed: DLD layout** (L159). Needed: a layout or vision check.
- [ ] ❌ **Title deed: unit number matches the Case, with the message** (L159). Needed: read the unit and compare with the deal's property; only a typed deed number exists. [documents.py:31](../diwan/documents.py#L31)
- [ ] ❌ **PDF form: signed on every signature line** (L160). Needed: page reading in [agency_forms.py:280](../diwan/agency_forms.py#L280); the check is only that the file starts `%PDF`, so any PDF counts as signed. [agency_forms.py:293](../diwan/agency_forms.py#L293)
- [ ] 🟡 **PDF form: right form version** (L160). There: online links are tied to one version and a replaced one cannot be signed; an uploaded PDF is not read. [signing.py:99](../diwan/signing.py#L99), test: [test_desk_rules.py](../tests/test_desk_rules.py#L613). Needed: a version mark on the printed form, checked on upload.
- [ ] ❌ **PDF form: says which page is unsigned** (L160). Needed: with the line above.
- [ ] 🟡 **A person sees every signed form in Review before anything official** (L162). There: signed forms file themselves with Records; no Review step reads them. Documents do go to the compliance officer. [signing.py:177](../diwan/signing.py#L177), [documents.py:209](../diwan/documents.py#L209). Needed: a review Task on every signed form, blocking use.

### Exit (L164-166)

- [ ] ❌ **All checklist Tasks done before exit** (L166). Needed: an exit gate. The transfer steps start at Form F submission and there is no ready-for-transfer point. [operations.py:102](../diwan/agents/operations.py#L102)
- [ ] ❌ **Compliance cleared before exit** (L166). Needed: a `compliance.cleared` state set by a person; closing reads it, transfer does not. [operations.py:195](../diwan/agents/operations.py#L195), [test_desk_rules.py](../tests/test_desk_rules.py#L167)
- [ ] ❌ **Finance has the deposit or booking marked received** (L166). Needed: a gate reading the `pay` task's result; [operations.py:81](../diwan/agents/operations.py#L81) does not.
- [ ] 🟡 **Review passed** (L166). There: every draft is auto-checked against live Facts on creation. That is staleness only, no person reviews. [review.py:67](../diwan/agents/review.py#L67), test: [deal_flow.py](../e2e/deal_flow.py#L227). Needed: exit gate on it.
- [ ] ❌ **Owner approved** (L166). Needed: an owner approval on the deal. Only a discount above the limit reaches the owner. [desk_stages.py:131](../diwan/desk_stages.py#L131)
- [ ] ❌ **Emit `deal.ready_for_transfer` to Operations** (L166). Needed: the event, and Operations' work triggered from it.
- [ ] 🟡 **Fact correction: only the affected forms are reissued** (L166). There: a price or payment correction sends back the forms whose slides use it and redrafts them; a deposit change only touches Form F. [office.py:97](../diwan/office.py#L97), [operations.py:53](../diwan/agents/operations.py#L53), test: [deal_flow.py](../e2e/deal_flow.py#L237). Needed: covers price and deposit Facts only; see next lines.
- [ ] ❌ **Fact correction: the checklist is rebuilt** (L166). Needed: steps resting on Facts and a rebuild; steps stay as they are.
- [ ] 🟡 **Unit corrected mid-deal** (L166). There: a change of property redrafts until a form is signed, then it is refused. [deal_property.py:42](../diwan/deal_property.py#L42), [agency_forms.py:135](../diwan/agency_forms.py#L135), test: [property_flow.py](../e2e/property_flow.py#L227). Needed: see Conflicts.
- [ ] ❌ **Buyer name corrected mid-deal** (L166). Needed: the customer's name as a Fact; `customer` is a plain deal field with no correction path that reaches forms.
- [ ] ❌ **Cash to mortgage corrected mid-deal** (L166). Needed: a funding Fact that adds the mortgage lines.

### Room 4 · Operations: the room (L168-170)

- [x] ✅ **Operations executes Tasks; a person decides** (L170). There: charter says "Submit anything" is forbidden; steps wait for the transactions officer. [charters.py:79](../diwan/agents/charters.py#L79), test: [deal_flow.py](../e2e/deal_flow.py#L230)
- [ ] 🟡 **Lead agent: Ops lead** (L170). There: charter runs on rules; it adds steps but holds no chase logic. [charters.py:79](../diwan/agents/charters.py#L79). Needed: an agent that picks up events.
- [ ] 🟡 **Form F clerk, browser, stops before Submit** (L170). There: it writes a field plan; no browser code exists in `diwan` (no Playwright import), so a person types everything into the portal. [operations.py:64](../diwan/agents/operations.py#L64), [deal.html:578](../web/deal.html#L578), test: [deal_flow.py](../e2e/deal_flow.py#L227). Needed: portal automation.
- [ ] ❌ **Scheduler for Operations** (L170). Needed: an Operations scheduler for appointments; the only `Scheduler` is Marketing's. [charters.py:236](../diwan/agents/charters.py#L236)
- [ ] 🟡 **Prepares and sends forms** (L170). There: prepares; a broker sends. [agency_forms.py:151](../diwan/agency_forms.py#L151), test: [deal_flow.py](../e2e/deal_flow.py#L769). Needed: sending from Operations.
- [ ] ❌ **Fills government and developer portals up to Submit** (L170). Needed: portal fills for NOC, trustee, Ejari and permit. None exists.
- [ ] ❌ **Books appointments and handover** (L170). Needed: bookings on the calendar; these are tick steps only.

### What Operations picks up (L172-181)

- [x] ✅ **Task for a form: builds it from the Case's Facts** (L176). There: filled from the record at conversion; what is not on file is printed blank. [agency_forms.py:182](../diwan/agency_forms.py#L182), test: [deal_flow.py](../e2e/deal_flow.py#L774)
- [ ] 🟡 **Sends to the client portal or the other agency** (L176). There: signing links, shared by hand. [signing.py:74](../diwan/signing.py#L74), test: [deal_flow.py](../e2e/deal_flow.py#L836). Needed: automatic send.
- [ ] ❌ **Emits `form.sent`** (L176). Needed: the event; `sign.link` only says a link was made.
- [ ] 🟡 **doc received: files it on the Case** (L177). There: filed once the compliance officer confirms, by `document.filed`. [documents.py:238](../diwan/documents.py#L238), test: [deal_flow.py](../e2e/deal_flow.py#L934). Needed: `doc.filed`, or adopt `document.filed`.
- [ ] 🟡 **Renames it to the office's convention** (L177). There: a fixed code pattern. [documents.py:205](../diwan/documents.py#L205). Needed: the convention as a setting.
- [ ] ❓ **The office's file-naming convention** (L177). Needs the office's answer: what is the convention? Default today: `doc-<token>-<kind>` and `deal-<id>-form-<X>-<draft>-signed.pdf`.
- [ ] ❌ **Attaches it to the portal draft** (L177). Needed: a link from a document to the Form F draft or portal fill.
- [ ] ❌ **ready_for_transfer: requests the developer NOC** (L178). Needed: a generated request; today a tick step.
- [ ] ❌ **Fills the DLD / trustee appointment request up to Submit** (L178). Needed: a portal fill.
- [ ] 🟡 **Books the trustee office slot** (L178). There: tick step, no date. [desk_rules.py:52](../diwan/desk_rules.py#L52), test: [test_deal_desk.py](../tests/test_deal_desk.py#L205). Needed: slot and date stored.
- [ ] ❌ **Emits `transfer.booked` after a person submits** (L178). Needed: the event; a tick writes only `task.done`.
- [ ] ❌ **Listing signed: prepares the Trakheesi application up to Submit** (L179). Needed: a listing trigger and a portal fill.
- [ ] ❌ **Listing signed: books photographer** (L179). Needed: a booking; nothing in the code does.
- [ ] ❌ **Listing signed: drafts the portal listing** (L179). Needed: an outbound portal draft; [portals.py](../diwan/providers/portals.py) reads a feed in.
- [ ] ❌ **Emits `listing.ready`** (L179). Needed: the event.
- [ ] ❌ **Rental signed: prepares Ejari up to Submit** (L180). Needed: a portal fill; today a tick step.
- [x] ✅ **Rental signed: collects cheques Task for Finance** (L180). There: the schedule of cheques as Finance tasks, entered by the transactions officer. [finance.py:265](../diwan/agents/finance.py#L265), test: [deal_flow.py](../e2e/deal_flow.py#L526)
- [ ] ❌ **Emits `ejari.ready`** (L180). Needed: the event.
- [ ] 🟡 **`transfer.completed` marked by a person** (L181). There: the "Title deed issued" step is ticked by the transactions officer. [desk_rules.py:53](../diwan/desk_rules.py#L53), [operations.py:112](../diwan/agents/operations.py#L112), test: [deal_flow.py](../e2e/deal_flow.py#L250). Needed: the event and its trigger of what follows.
- [ ] 🟡 **Handover checklist: keys, access cards** (L181). There: one tick step, for all of it, on the same list as the transfer. [desk_rules.py:54](../diwan/desk_rules.py#L54). Needed: its own list, started by the transfer.
- [ ] ❌ **DEWA / chiller transfer reminders** (L181). Needed: reminder messages; the step only names utilities.
- [ ] ❌ **Welcome message to the buyer** (L181). Needed: a template and a send.
- [ ] 🟡 **Emits `case.closed`** (L181). There: `sale.closed` plus stage Won, after the four closing items. [operations.py:245](../diwan/agents/operations.py#L245), test: [deal_flow.py](../e2e/deal_flow.py#L564). Needed: event name, or adopt `sale.closed`.

### Rules (L183-187)

- [ ] 🟡 **Every portal step stops before Submit, Pay or Sign** (L185). There: true for Form F, which never reaches the portal; `submit` is a person-only action. [charters.py:83](../diwan/agents/charters.py#L83), test: [deal_flow.py](../e2e/deal_flow.py#L227). Needed: the same for every other portal once built.
- [ ] 🟡 **Person sees a filled screen and a checklist of what was entered** (L185). There: the Form F plan lists each field and its source on the Deal desk; there is no filled portal screen. [deal.html:966](../web/deal.html#L966), test: [deal_flow.py](../e2e/deal_flow.py#L227). Needed: screenshot or filled screen.
- [ ] 🟡 **Forms built from Facts, never retyped** (L186). There: yes for price, deposit and payer; seller's name, IDs and title deed number are not on the Case and are printed blank or come from what signers type. [operations.py:25](../diwan/agents/operations.py#L25), [agency_forms.py:197](../diwan/agency_forms.py#L197), test: [deal_flow.py](../e2e/deal_flow.py#L237). Needed: confirmed document details feeding the forms.
- [x] ✅ **Superseded Fact: the sent version is withdrawn on our side** (L186). There: draft sent back, its link shows "replaced" and cannot be signed. [review.py:56](../diwan/agents/review.py#L56), [signing.py:102](../diwan/signing.py#L102), test: [deal_flow.py](../e2e/deal_flow.py#L235)
- [ ] ❌ **Superseded Fact: tells the client "Please ignore the Form B sent at 10:14"** (L186). Needed: a WhatsApp message to whoever got the form; the only trace is the link's page text. [sign.html:38](../web/sign.html#L38)
- [ ] 🟡 **Superseded Fact: resends the corrected one** (L186). There: a new version is drafted; new links wait for a person and nothing is sent. [operations.py:60](../diwan/agents/operations.py#L60), test: [test_desk_rules.py](../tests/test_desk_rules.py#L505). Needed: automatic resend.
- [ ] 🟡 **Each Task shows waiting-on** (L187). There: transfer steps only, free text from the template. [deal.html:583](../web/deal.html#L583), test: [deal_flow.py](../e2e/deal_flow.py#L246). Needed: on every Task, from a set list (client, other agency, developer, bank, government).
- [ ] 🟡 **Waiting too long goes to the brief** (L187). There: `stuck_days` (7) counts deals in the KPIs panel, not the brief, and measures no outside party. [desk_kpis.py:64](../diwan/desk_kpis.py#L64), test: [test_desk_rules.py](../tests/test_desk_rules.py#L415). Needed: a waiting limit, and a line in [nova.py:506](../diwan/agents/nova.py#L506).

### Deal · blocks on screen (L473-475)

- [ ] 🟡 **Deals by stage (board)** (L475). There: a table sortable by stage, and stage counts on the Overview; no board. [deal_desk.py:271](../diwan/deal_desk.py#L271), test: [deal_flow.py](../e2e/deal_flow.py#L272). Needed: a board view.
- [ ] 🟡 **Each deal's checklist with owner room and status per line** (L475). There: tasks under Compliance, Finance, Paperwork and Review, each with status; one list, not by line of a template. [deal.html:980](../web/deal.html#L980), test: [deal_flow.py](../e2e/deal_flow.py#L246). Needed: one checklist view.
- [ ] 🟡 **Client portal status: link sent** (L475). There: link exists and expiry shown; no record it was sent. [deal.html:834](../web/deal.html#L834). Needed: sent status.
- [ ] ❌ **Client portal status: opened** (L475). Needed: a page-opened event on `/api/docs` and `/api/sign`.
- [x] ✅ **Client portal status: items uploaded** (L475). There: each item as needed, to check, or confirmed. [deal.html:840](../web/deal.html#L840), test: [deal_flow.py](../e2e/deal_flow.py#L926)
- [x] 🧪 **Client portal status: failed checks** (L475). There: "Turned away" with the reason. [deal.html:843](../web/deal.html#L843); the page text is not asserted, test only for the log: [test_desk_rules.py](../tests/test_desk_rules.py#L672)
- [ ] 🟡 **Follow-up ladder 24h / 48h / 72h** (L475). There: a count of reminders. [deal.html:835](../web/deal.html#L835). Needed: the ladder with each rung's date.
- [ ] 🟡 **Waiting on (client, other agency, bank, developer)** (L475). There: people inside the office in the header, outside parties on transfer steps only. [deal.html:995](../web/deal.html#L995). Needed: one line, outsiders included.
- [ ] 🟡 **Gates panel: Compliance, Finance, Review, owner** (L475). There: a strip of Compliance, Money, Paperwork, Review; no owner gate and nothing blocks. [deal.html:994](../web/deal.html#L994), test: [deal_flow.py](../e2e/deal_flow.py#L308). Needed: an owner row, and gates that block.
- [ ] ❌ **A Deal room on the 3D floor** (L478). Needed: a `deal` entry in [office3d.html:129](../web/office3d.html#L129).
- [ ] 🟡 **Templates editable in Settings** (L480). There: in the rules panel on the Deal desk's Overview, not Settings. [deal.html:252](../web/deal.html#L252), test: [deal_flow.py](../e2e/deal_flow.py#L402). Needed: nothing if the office accepts where it lives.
- [ ] ❌ **Identity document lists editable by the owner on screen** (L480, L654). Needed: a panel for `documents`; the API takes them, but only from the six kinds. [desk_rules.py:139](../diwan/desk_rules.py#L139)
- [ ] 🟡 **Private, expiring link** (L481). There: random token, expires after the owner's 14 days. [documents.py:95](../diwan/documents.py#L95), test: [test_desk_rules.py](../tests/test_desk_rules.py#L613). Needed: WhatsApp send, and a way to replace an expired link.
- [ ] ❌ **Test: selfie uploaded as signature is rejected** (L487). Needed: the check and a Playwright test. Both missing.
- [ ] ❌ **Test: drawn signature accepted** (L487). Needed: drawn signature, then a test.
- [ ] ❌ **Test: WhatsApp receipt in sandbox** (L487). Needed: the receipt, then a test.
- [ ] ❌ **Test: gates block the transfer** (L487). Needed: the gates, then a test.

### Operations · blocks on screen (L490-504)

- [ ] 🟡 **Forms to send and sent (with version)** (L492). There: forms shown with version and signed state; "sent" is not known. [deal.html:879](../web/deal.html#L879), test: [deal_flow.py](../e2e/deal_flow.py#L769). Needed: sent state.
- [ ] 🟡 **Portal drafts ready for a person to Submit** (L492). There: Form F only, also as a My work row. [deal_desk.py:229](../diwan/deal_desk.py#L229), test: [deal_flow.py](../e2e/deal_flow.py#L241). Needed: NOC, trustee, Ejari and permit drafts.
- [ ] ❌ **Appointments (trustee, DLD, handover)** (L492). Needed: an Operations calendar; the calendar holds viewings only.
- [ ] 🟡 **Waiting on outsiders with days waited** (L492). There: My work shows "waiting on" and how long ago the step opened; not on the deal's cards. [deal.html:436](../web/deal.html#L436). Needed: on every view.
- [x] ✅ **Recalled forms** (L492). There: sent-back versions listed with the reason. [deal.html:888](../web/deal.html#L888), test: [deal_flow.py](../e2e/deal_flow.py#L235)
- [ ] 🟡 **Handover checklist** (L492). There: one line. [desk_rules.py:54](../diwan/desk_rules.py#L54). Needed: its items as lines.
- [ ] ❌ **Subscribe to the events in the table** (L497). Needed: an Operations listener; work starts from direct function calls and people pressing buttons.
- [ ] 🟡 **Each sent form records the Fact versions it used** (L498). There: each slide keeps its fact ids and a signature keeps a fingerprint of the lines; agency forms only link the price. [agency_forms.py:164](../diwan/agency_forms.py#L164), [signing.py:45](../diwan/signing.py#L45), test: [test_desk_rules.py](../tests/test_desk_rules.py#L609). Needed: every row's source.
- [ ] 🟡 **Recall with a short client message and resend** (L499). There: recall without the message. See Rules. Needed: message and send.
- [ ] 🟡 **Portal fills stop before Submit; show what was entered** (L500). There: Form F plan only. Needed: Form F fill by browser, NOC, trustee, Ejari, listing permit.
- [ ] 🟡 **Every Task shows waiting_on and days waiting** (L501). There: see Rules. Needed: on all Tasks.
- [ ] ❌ **Over the owner's limit goes to the brief** (L501). Needed: as in Rules.
- [ ] 🟡 **transfer.completed: handover checklist and welcome, then case.closed** (L502). There: closing starts when all steps are ticked, not on a transfer mark; no welcome. [operations.py:173](../diwan/agents/operations.py#L173), test: [deal_flow.py](../e2e/deal_flow.py#L532). Needed: as in the table above.
- [x] ✅ **Test: Ops room shows Tasks once a deal is at that point** (L503). There: after Form F is submitted the checklist shows, and the floor wall is drawn. test: [deal_flow.py](../e2e/deal_flow.py#L246), [deal_flow.py](../e2e/deal_flow.py#L263)
- [ ] 🟡 **Test: recall after a price correction** (L503). There: tests cover the send-back, not a client message. test: [test_desk_rules.py](../tests/test_desk_rules.py#L505), [deal_flow.py](../e2e/deal_flow.py#L235). Needed: an assertion on the message once built.

### Every upload: how a checklist is built (L652-654)

- [ ] 🟡 **Built from who the party is and what the deal is** (L654). There: one fixed list per side; no party type. [desk_rules.py:32](../diwan/desk_rules.py#L32), [documents.py:44](../diwan/documents.py#L44). Needed: a party type on each party, and lists by party type and deal type.
- [ ] 🟡 **The portal asks only for what this party in this deal is missing** (L654). There: only that party's list, but the list ignores what they gave on an earlier deal. [documents.py:115](../diwan/documents.py#L115), test: [test_desk_rules.py](../tests/test_desk_rules.py#L663). Needed: reuse of valid confirmed documents.
- [ ] ❓ **The lists are confirmed by the office's conveyancer** (L654). Needs the office's answer: has a conveyancer confirmed the lists? Current default: `DEFAULTS["documents"]`.
- [ ] 🟡 **Editable in Settings** (L654). There: API only, and limited to six kinds. [desk_rules.py:139](../diwan/desk_rules.py#L139). Needed: a panel, and owner-added kinds.

### 1 · Identity by party (L656-667)

- [x] ✅ **Resident: passport photo page upload** (L660). There: item with number and expiry. [documents.py:27](../diwan/documents.py#L27), test: [test_desk_rules.py](../tests/test_desk_rules.py#L667)
- [x] ✅ **Resident: Emirates ID front and back** (L660). There: two items, same-file check. [documents.py:27](../diwan/documents.py#L27), [documents.py:192](../diwan/documents.py#L192), test: [test_desk_rules.py](../tests/test_desk_rules.py#L689), [deal_flow.py](../e2e/deal_flow.py#L919)
- [ ] 🟡 **Resident check: document type** (L660). There: a person, not at upload. Needed: as in Upload checks.
- [ ] 🟡 **Resident check: name matches the Case** (L660). There: a flag, EID front only. [documents.py:197](../diwan/documents.py#L197), test: [test_desk_rules.py](../tests/test_desk_rules.py#L703). Needed: as above.
- [ ] ❌ **Resident check: name matches across both documents** (L660). Needed: a name on the passport, then a comparison.
- [x] ✅ **Resident check: EID number format** (L660). There: 784 format rejected if wrong; a bad check digit flags for the officer. [documents.py:155](../diwan/documents.py#L155), test: [test_desk_rules.py](../tests/test_desk_rules.py#L682), [deal_flow.py](../e2e/deal_flow.py#L926)
- [ ] 🟡 **Resident check: not expired** (L660). There: on the typed date. [documents.py:167](../diwan/documents.py#L167), test: [test_desk_rules.py](../tests/test_desk_rules.py#L683). Needed: date from the image.
- [ ] 🟡 **Resident check: corners visible, no glare** (L660). There: glare via "washed out" brightness; corners no. [documents.py:139](../diwan/documents.py#L139). Needed: corners.
- [ ] 🟡 **Warn 30 days before expiry** (L660). There: a flag for the officer at 60 days, nothing to the client. [documents.py:169](../diwan/documents.py#L169). Needed: 30 days as a setting, or see Conflicts.
- [x] 🧪 **Block at expiry at upload** (L660). There: refused. [documents.py:167](../diwan/documents.py#L167), test: [test_desk_rules.py](../tests/test_desk_rules.py#L683)
- [ ] ❌ **Block if a document expires later in the deal** (L660). Needed: a re-check of confirmed expiry dates before signing and transfer.
- [ ] ❌ **Non-resident: passport without Emirates ID** (L661). Needed: party type. Today everyone is asked for EID and visa, so a non-resident can never finish and is chased to the broker.
- [ ] ❌ **Non-resident: proof of address under 3 months** (L661). Needed: a `proof_of_address` kind with a dated field.
- [ ] ❌ **Non-resident check: dated within 3 months, name matches** (L661). Needed: as above.
- [ ] ❌ **Non-resident: address proof re-asked if older at transfer** (L661). Needed: a re-check at the transfer gate.
- [ ] ❌ **GCC national: passport or national ID** (L662). Needed: party type and a `national_id` kind.
- [ ] ❌ **Joint buyers: each person's identity set** (L663). Needed: several parties per side; a deal has one `customer`.
- [ ] ❌ **Joint buyers: who signs what** (L663). Needed: signers per form per person; one `buyer` signer today. [signing.py:24](../diwan/signing.py#L24)
- [ ] ❌ **Joint: every owner on every form that needs them** (L663). Needed: a form-level check.
- [ ] ❌ **Joint: expiry per person** (L663). Needed: with the identity sets.
- [ ] ❌ **Company: trade licence is asked for** (L664). Needed: a company party. `company` is a list in the rules and `trade_licence` a kind, but `parties()` never returns a company, so it is never requested. [desk_rules.py:33](../diwan/desk_rules.py#L33), [documents.py:44](../diwan/documents.py#L44)
- [ ] ❌ **Company: memorandum or articles** (L664). Needed: kind.
- [ ] ❌ **Company: board resolution naming this purchase and the signatory** (L664). Needed: kind and check.
- [ ] ❌ **Company: signatory's passport and EID** (L664). Needed: signatory as a party.
- [ ] ❌ **Company: ownership declaration and IDs of 25% or more owners** (L664). Needed: kind and owner parties.
- [ ] 🟡 **Company check: licence not expired** (L664). There: expiry check works for `trade_licence` but is unreachable, as above. [documents.py:31](../diwan/documents.py#L31), no test. Needed: a company party.
- [ ] ❌ **Company check: name identical across documents** (L664). Needed: comparison.
- [ ] ❌ **Company check: resolution names this unit and this signatory** (L664). Needed: reading the document.
- [ ] ❌ **Company check: owners add up** (L664). Needed: the sum.
- [ ] ❌ **Company: licence expiry checked at each stage** (L664). Needed: a check on stage moves.
- [ ] ❌ **Offshore: certificate of incorporation** (L665). Needed: kind.
- [ ] ❌ **Offshore: certificate of good standing** (L665). Needed: kind.
- [ ] ❌ **Offshore: register of directors and shareholders** (L665). Needed: kind.
- [ ] ❌ **Offshore: attestation stamp and Arabic translation attached** (L665). Needed: checks.
- [ ] ❌ **Offshore: good standing dated recently, re-asked past the limit** (L665). Needed: the check and a setting.
- [ ] ❓ **Good standing age limit** (L665). Needs the office's answer: how old may it be? No default.
- [ ] ❌ **POA: POA document, attorney's passport and EID, principal's passport** (L666). Needed: kinds and an attorney party.
- [ ] ❌ **POA check: covers this act and this unit or "any property"** (L666). Needed: reading the POA.
- [ ] ❌ **POA check: notarised, attested and translated if abroad** (L666). Needed: checks.
- [ ] ❌ **POA check: not revoked or expired** (L666). Needed: checks.
- [ ] ❌ **POA: block if it expires before transfer** (L666). Needed: a transfer date and the block.
- [ ] ❌ **Estate, inheritance or minor: court documents and heirs' IDs** (L667). Needed: kinds.
- [ ] ❌ **Estate: flag to a person and the office's lawyer, no automatic checklist** (L667). Needed: a flag that stops the checklist, and a lawyer role; [roles](../diwan/desk_rules.py#L24) has none.

### 2 · Deal documents (L669-680)

- [ ] 🟡 **Secondary cash, buyer: identity set** (L673). There: portal link. Needed: by party type (above).
- [ ] 🟡 **Secondary cash, buyer: deposit or security cheque** (L673). There: an expected payment, marked received with a reference; no cheque photo. [finance.py:80](../diwan/agents/finance.py#L80), test: [deal_flow.py](../e2e/deal_flow.py#L201). Needed: cheque upload.
- [ ] ❓ **Deposit amount and payee per the office's rule** (L673). Needs the office's answer: who is the payee? Defaults: 10%, "the seller's agency, in trust", and the payee field is not on any screen. [desk_rules.py:39](../diwan/desk_rules.py#L39)
- [x] ✅ **Secondary cash, buyer: source-of-funds documents if triggered** (L673). There: proof list per deal; the officer marks each received. It takes no file. [compliance.py:111](../diwan/agents/compliance.py#L111), [deal_desk.py:456](../diwan/deal_desk.py#L456), test: [deal_flow.py](../e2e/deal_flow.py#L171)
- [ ] 🟡 **Secondary cash, buyer: manager's cheque for the balance** (L673). There: inside one tick step. [desk_rules.py:51](../diwan/desk_rules.py#L51). Needed: its own line with the amount.
- [ ] 🟡 **Secondary cash, buyer: cheques for DLD fees and commission** (L673). There: fees and commission worked out and shown, no cheque collected. [finance.py:149](../diwan/agents/finance.py#L149), test: [deal_flow.py](../e2e/deal_flow.py#L990). Needed: lines for the cheques.
- [ ] 🟡 **Secondary cash, seller: identity set** (L673). There: only when we act for the seller; no name. [documents.py:51](../diwan/documents.py#L51). Needed: seller as a named party.
- [ ] 🟡 **Secondary cash, seller: title deed** (L673). There: default list. Needed: checks.
- [ ] ❌ **Secondary cash, seller: tenancy contract and Ejari if tenanted** (L673). Needed: a tenanted Fact and kinds.
- [ ] ❌ **Secondary cash, seller: service charge clearance** (L673). Needed: a kind and a gate on the NOC.
- [ ] 🟡 **Secondary cash, outside: developer NOC** (L673). There: tick step. Needed: document.
- [ ] 🟡 **Secondary cash, outside: trustee appointment confirmation** (L673). There: tick step. Needed: document.
- [x] ✅ **Office generates Form B, Form A, Form I, Form F** (L673). There: PDFs. [agency_forms.py:241](../diwan/agency_forms.py#L241), test: [deal_flow.py](../e2e/deal_flow.py#L774)
- [x] ✅ **Office generates invoices and receipts** (L673). There: tax invoice and receipt PDFs. [deal_desk.py:905](../diwan/deal_desk.py#L905), test: [deal_flow.py](../e2e/deal_flow.py#L966)
- [ ] ❌ **Buyer mortgage: pre-approval upload** (L674). Needed: kind and the bank letter check.
- [ ] ❌ **Buyer mortgage: signed valuation request** (L674). Needed: kind.
- [ ] ❌ **Buyer mortgage: bank final offer letter upload** (L674). Needed: kind.
- [ ] 🟡 **Buyer mortgage: bank's manager's cheques** (L674). There: tick step. Needed: lines.
- [ ] ❌ **Buyer mortgage, outside: bank valuation report** (L674). Needed: kind.
- [ ] ❌ **Buyer mortgage, outside: bank's transfer documents** (L674). Needed: kind.
- [ ] ❌ **Buyer mortgage: a mortgage timeline Task list** (L674). Needed: mortgage steps as their own list.
- [ ] 🟡 **Seller mortgage: liability letter (amount, valid date)** (L675). There: tick step, no fields. [desk_rules.py:49](../diwan/desk_rules.py#L49). Needed: document with amount and date.
- [ ] 🟡 **Seller mortgage: later the bank's clearance** (L675). There: same tick. Needed: its own line.
- [ ] ❌ **Seller mortgage: clearance and release at transfer** (L675). Needed: outside-party line.
- [ ] ❌ **Seller mortgage: payment split to the seller's bank** (L675). Needed: a split document.
- [ ] 🟡 **Off-plan, buyer: identity set** (L676). There: portal link. [documents.py:49](../diwan/documents.py#L49), test: no off-plan test of the link. Needed: test.
- [ ] 🟡 **Off-plan, buyer: reservation form** (L676). There: tick. Needed: document.
- [ ] 🟡 **Off-plan, buyer: booking payment proof** (L676). There: a reference on a receipt. Needed: upload.
- [ ] 🟡 **Off-plan, buyer: signed SPA** (L676). There: tick and reference. Needed: upload.
- [x] ✅ **Off-plan, buyer: installment payment proofs** (L676). There: each marked paid into escrow with the developer's receipt number, and a receipt filed; no image. [finance.py:92](../diwan/agents/finance.py#L92), test: [deal_flow.py](../e2e/deal_flow.py#L661)
- [ ] ❌ **Off-plan, outside: developer receipt on file** (L676). Needed: upload.
- [ ] 🟡 **Off-plan, outside: Oqood certificate** (L676). There: tick, and a closing line "SPA, Oqood certificate and receipts filed" a person ticks. [desk_rules.py:68](../diwan/desk_rules.py#L68). Needed: upload.
- [x] ✅ **Off-plan, outside: payment plan** (L676). There: schedule. test: [deal_flow.py](../e2e/deal_flow.py#L653)
- [ ] ❌ **Off-plan: reservation summary generated** (L676). Needed: a PDF.
- [x] ✅ **Off-plan: commission invoice to the developer** (L676). There: from the agreement. [finance.py:125](../diwan/agents/finance.py#L125), test: [deal_flow.py](../e2e/deal_flow.py#L626)
- [ ] ❌ **Off-plan resale: a path of its own** (L677). Needed: a path; the off-plan path has no Forms A, B or F.
- [ ] ❌ **Off-plan resale: payment to seller of paid-so-far plus premium** (L677). Needed: the sum.
- [ ] ❌ **Off-plan resale, seller: Oqood, SPA, developer payment statement** (L677). Needed: kinds.
- [ ] ❌ **Off-plan resale, outside: NOC with developer's minimum paid %** (L677). Needed: the check.
- [ ] ❌ **Off-plan resale: developer transfer fee confirmation** (L677). Needed: kind.
- [ ] ❌ **Off-plan resale, office: Form A, B, F and invoice** (L677). Needed: path setting.
- [ ] 🟡 **Rental, tenant: passport, visa / EID** (L678). There: portal link. [desk_rules.py:33](../diwan/desk_rules.py#L33), test: [test_desk_rules.py](../tests/test_desk_rules.py#L729). Needed: browser check on a tenant.
- [ ] 🟡 **Rental, tenant: rent cheques, number per agreement** (L678). There: the number chosen, tasks made; no photos. [finance.py:257](../diwan/agents/finance.py#L257), test: [deal_flow.py](../e2e/deal_flow.py#L526). Needed: cheque upload.
- [ ] 🟡 **Rental, tenant: security deposit cheque** (L678). There: expected and marked. test: [deal_flow.py](../e2e/deal_flow.py#L487). Needed: upload.
- [ ] ❌ **Rental, tenant: employer letter if company pays** (L678). Needed: kind and a rule.
- [ ] ❌ **Rental, landlord: identity set, title deed, DEWA account, POA** (L678). Needed: a landlord party and kinds.
- [ ] 🟡 **Rental, outside: Ejari certificate** (L678). There: tick, closing line. [desk_rules.py:81](../diwan/desk_rules.py#L81). Needed: upload.
- [ ] ❌ **Rental: tenancy contract generated** (L678). Needed: a form, as `agency_forms`.
- [x] ✅ **Rental: agency fee invoice** (L678). There: commission flow with the tenant as payer. [desk_rules.py:72](../diwan/desk_rules.py#L72), test: [deal_flow.py](../e2e/deal_flow.py#L479)
- [ ] ❌ **Rental: key handover form** (L678). Needed: a generated form.
- [ ] ❌ **Rental: move-in condition report with photos** (L678). Needed: a report and uploads.
- [ ] ❌ **Rental renewal: cheques, agreement to new rent, Ejari renewal, contract** (L679). Needed: a renewal path; the deal closes and a single Task is left. [operations.py:275](../diwan/agents/operations.py#L275)
- [ ] ❌ **Renewal: within the rent index rules** (L679). Needed: an index check.
- [ ] 🟡 **Renewal reminder 90 and 60 days ahead** (L679). There: one Task for the broker at 90 days (owner's number); none at 60. [operations.py:277](../diwan/agents/operations.py#L277), test: [deal_flow.py](../e2e/deal_flow.py#L565). Needed: a second date and a client message.
- [ ] ❌ **Listing, seller: identity set, title deed, Form A, floor plan, keys or access** (L680). Needed: a listing path.
- [ ] 🟡 **Listing, outside: listing / advertising permit** (L680). There: `permit` on a listing, typed; a listing without one is not advertised. [office.py:185](../diwan/office.py#L185), test: [test_listing_add.py](../tests/test_listing_add.py). Needed: an application and tracking.
- [ ] 🟡 **Listing record** (L680). There: `listing.added`. [listing_add.py:76](../diwan/listing_add.py#L76), test: [test_listing_add.py](../tests/test_listing_add.py). Needed: link to a seller and Form A.
- [ ] ❌ **Listing: photo booking** (L680). Needed: a booking.
- [ ] ❌ **Listing: portal drafts** (L680). Needed: drafts outbound.
- [ ] 🟡 **Listing: price-change log** (L680). There: the event log keeps each `listing.added` update with who; no screen. [graph.py:263](../diwan/graph.py#L263). Needed: a log view.

### 3 · The checks the portal runs (L682-697)

- [ ] ❌ **Drawn: at least two strokes, not a line or dot, not empty; message** (L686). Needed: drawing, then the check.
- [ ] ❌ **Signature photo: dark ink on light paper** (L687). Needed: as Upload checks.
- [ ] ❌ **Signature photo: no face** (L687). Needed: as Upload checks.
- [ ] ❌ **Signature photo: no printed paragraph** (L687). Needed: as Upload checks.
- [ ] ❌ **Signature photo: no ID card shape** (L687). Needed: shape check.
- [ ] ❌ **Signature photo: cropped to the signature** (L687). Needed: a crop check. Today only a minimum size of 120x40. [signing.py:136](../diwan/signing.py#L136)
- [ ] ❌ **Signature photo: rejection message** (L687). Needed: the message.
- [ ] 🟡 **ID: right document** (L688). There: slot chosen by the client; a person checks. Needed: vision.
- [ ] 🟡 **ID: name matches the Case** (L688). There: flag only. Needed: as above.
- [ ] 🟡 **ID: not expired** (L688). There: typed date. Needed: as above.
- [ ] ❌ **ID: readable MRZ** (L688). Needed: read the machine-readable zone. EID number format is on the typed value only.
- [ ] ❌ **ID: 4 corners** (L688). Needed: as above.
- [ ] 🟡 **ID: message names wrong document, name differs, expired, cut off, too blurry** (L688). There: expired and too blurry (and dark, small, glare). [documents.py:133](../diwan/documents.py#L133), test: [test_desk_rules.py](../tests/test_desk_rules.py#L681). Needed: the other three.
- [ ] 🟡 **Two-sided ID: both sides uploaded** (L689). There: two items, the back remains "Needed". [documents.py:27](../diwan/documents.py#L27), test: [test_desk_rules.py](../tests/test_desk_rules.py#L690). Needed: the message "We have the front; please add the back."
- [ ] ❌ **Deed / Oqood: layout matches** (L690). Needed: layout check; there is no Oqood kind.
- [ ] ❌ **Deed / Oqood: unit, building, community match, and the message** (L690). Needed: reading and comparison.
- [ ] ❌ **Signed PDF: every line signed by the right person** (L691). Needed: PDF reading on an upload. Online signing does require every signer before filing. [signing.py:177](../diwan/signing.py#L177)
- [x] ✅ **Signed PDF: current form version (online)** (L691). There: a replaced version cannot be signed. [signing.py:157](../diwan/signing.py#L157), test: [test_desk_rules.py](../tests/test_desk_rules.py#L613), [deal_flow.py](../e2e/deal_flow.py#L875)
- [ ] ❌ **Signed PDF: current form version (uploaded)** (L691). Needed: version check; the broker's upload is not read beyond `%PDF`.
- [ ] ❌ **Signed PDF: message "Page 2 is missing [buyer 2]'s signature"** (L691). Needed: with the above.
- [ ] ❌ **Cheque photo: all checks and the message** (L692). Needed: a `cheque` kind: shape, words and figures agree, payee, date, signed.
- [ ] ❌ **Bank letters: bank, client, amount, validity after the expected transfer; message** (L693). Needed: a kind, and an expected transfer date on the deal.
- [ ] ❌ **Proof of address: dated within 3 months, name matches, message** (L694). Needed: kind and check.
- [x] ✅ **Any upload: file opens (image)** (L695). There: decoded with Pillow. [documents.py:126](../diwan/documents.py#L126), test: [test_desk_rules.py](../tests/test_desk_rules.py#L681)
- [ ] ❌ **Any upload: file opens (PDF)** (L695). Needed: parse the PDF; a file starting `%PDF` passes, broken or blank. [documents.py:183](../diwan/documents.py#L183)
- [ ] ❌ **Any upload: not password-protected** (L695). Needed: a PDF encryption check.
- [x] 🧪 **Any upload: under the size limit** (L695). There: 8 MB, 3 MB for signatures. [documents.py:185](../diwan/documents.py#L185), [signing.py:126](../diwan/signing.py#L126); size limit itself not exercised by a test.
- [x] ✅ **Any upload: image or PDF** (L695). There: by file signature, not by name. [documents.py:183](../diwan/documents.py#L183), test: [test_desk_rules.py](../tests/test_desk_rules.py#L681)
- [ ] 🟡 **Any upload: message** (L695). There: different wording, one per cause. [documents.py:188](../diwan/documents.py#L188). Needed: office's wording.
- [ ] 🟡 **A person sees each document in Review before official use** (L697). There: the compliance officer, for documents only; nothing blocks using one she has not confirmed. [documents.py:216](../diwan/documents.py#L216), test: [deal_flow.py](../e2e/deal_flow.py#L934). Needed: Review step and a block.
- [ ] ❌ **A person can override a rejection with a reason** (L697). Needed: an override. A rejected file is not kept, so there is nothing to override. [documents.py:201](../diwan/documents.py#L201)
- [ ] ❓ **Vision provider for IDs** (L688). Needs the office's answer: which provider may read real IDs? Without one every "read the document" line above stays with a person; the code says so. [documents.py:8](../diwan/documents.py#L8)

### Each deal type: the rule for all steps (L699-701)

- [ ] ❌ **Every step names who, document, gate, Event, and what the client hears** (L701). Needed: these on the template. A step holds its text, who it waits on, and "after". [desk_rules.py:47](../diwan/desk_rules.py#L47)
- [ ] ❌ **A client message on each step that has one** (L701). Needed: messages on steps. No Operations step sends a client message; the only Deal desk client messages are document reminders. [documents.py:284](../diwan/documents.py#L284)
- [ ] ❌ **Steps marked (M) only with a mortgage, (SM) only with a seller's mortgage** (L701). Needed: conditions on steps; a person marks them not needed. [operations.py:123](../diwan/agents/operations.py#L123)

### Secondary sale (L703-723)

- [ ] ❌ **S1 Listing exists: Ops, Form A signed, permit live** (L707). Needed: Form A before a buyer exists; a listing carries a typed permit only.
- [ ] ❌ **S1 gate: seller KYC started** (L707). Needed: seller as a party in screening; [compliance.py:38](../diwan/agents/compliance.py#L38) screens the customer and named people.
- [ ] ❌ **S1 client: seller hears "Your listing is live", `listing.ready`** (L707). Needed: seller contact and event.
- [ ] ❌ **S2 Form B before the first viewing, gate on it** (L708). Needed: Form B at booking, a block in viewing booking. Code drafts it only at conversion. [agency_forms.py:87](../diwan/agency_forms.py#L87)
- [x] ✅ **S2 buyer enquires, qualifies, views; `viewing.done`** (L708). There: Sales flow, stage Viewed by the broker's Done. [app.py:1708](../diwan/app.py#L1708), test: [visit_flow.py](../e2e/visit_flow.py). Event is `stage.changed`.
- [x] 🧪 **S2 client: viewing details** (L708). There: reminders 24h and 2h before, with place. [reminders.py:56](../diwan/agents/reminders.py#L56), test: [test_calendar.py](../tests/test_calendar.py#L116)
- [ ] 🟡 **S3 Offer as a Fact (price, terms, quote)** (L709). There: the Scribe records `deal_term` with a quote; stage Offer is a button; no offer record or terms. [scribe.py:122](../diwan/agents/scribe.py#L122), [desk_stages.py:47](../diwan/desk_stages.py#L47), test: [test_desk_rules.py](../tests/test_desk_rules.py#L431). Needed: an `offer` fact kind and `offer.made`.
- [ ] ❌ **S3 client: seller hears "An offer of AED X came in."** (L709). Needed: seller contact.
- [ ] 🟡 **S4 Counter / accept, each counter a Fact** (L710). There: a corrected `deal_term`; the agreed price at conversion is a Fact with who entered it. [desk_stages.py:162](../diwan/desk_stages.py#L162), test: [deal_flow.py](../e2e/deal_flow.py#L760). Needed: counters listed as a chain.
- [ ] ❌ **S4 gate: seller's acceptance quoted** (L710). Needed: a Fact from the seller; the broker's entry is enough today.
- [x] ✅ **S4 `case.converted` ≈ convert** (L710). There: agreed price, property, forms, documents link. Event differs. [desk_stages.py:105](../diwan/desk_stages.py#L105), test: [property_flow.py](../e2e/property_flow.py#L105)
- [ ] ❌ **S4 client: both hear "Offer accepted. Next: the MOU."** (L710). Needed: a message.
- [x] ✅ **S5 Co-broke: Form I, split recorded** (L711). There: agency, ORN, agent, share as terms; Form I; split paid after commission. No `cobroke.agreed`. [agency_forms.py:106](../diwan/agency_forms.py#L106), [finance.py:228](../diwan/agents/finance.py#L228), test: [deal_flow.py](../e2e/deal_flow.py#L769). Silent as the spec says.
- [ ] 🟡 **S6 KYC both sides: identity sets** (L712). There: buyer and seller on our side only; a document request, not the seller's screening. [documents.py:51](../diwan/documents.py#L51), test: [deal_flow.py](../e2e/deal_flow.py#L899). Needed: the other side's party when co-broked.
- [ ] 🟡 **S6 gate: screening clear** (L712). There: officer records clear or possible match; nothing waits for it. [compliance.py:77](../diwan/agents/compliance.py#L77), test: [deal_flow.py](../e2e/deal_flow.py#L167). Needed: the block, `compliance.cleared` or `needs_info`.
- [ ] 🟡 **S6 client: portal request if missing** (L712). There: the link at conversion and reminders. Needed: a request raised by Compliance.
- [ ] 🟡 **S7 (SM) liability letter** (L713). There: tick. Needed: document.
- [ ] ❌ **S7 gate: valid past transfer date** (L713). Needed: letter date and a transfer date.
- [ ] ❌ **S7 client: seller told to ask the bank** (L713). Needed: message.
- [ ] 🟡 **S8 (M) valuation and final offer** (L714). There: tick. Needed: documents, `mortgage.final_offer`.
- [ ] ❌ **S8 gate: valuation at or above price, or the gap covered** (L714). Needed: valuation figure and the check.
- [ ] ❌ **S8 client: buyer updates at each bank step** (L714). Needed: messages.
- [x] ✅ **S9 MOU drafted from Facts by Deal** (L715). There: Form F plan. Silent as the spec says. No `form.ready`. [operations.py:37](../diwan/agents/operations.py#L37), test: [deal_flow.py](../e2e/deal_flow.py#L227)
- [ ] 🟡 **S9 gate: Review passed** (L715). There: automatic check only. [review.py:67](../diwan/agents/review.py#L67), test: [test_deal_desk.py](../tests/test_deal_desk.py#L211). Needed: a person, as at L697.
- [ ] ❌ **S9 gate: owner approved** (L715). Needed: an approval before links can be made. [signing.py:84](../diwan/signing.py#L84)
- [x] ✅ **S10 MOU signed by both, through the client portal** (L716). There: buyer, seller, broker, other broker each by link; filed with Records. [signing.py:177](../diwan/signing.py#L177), test: [deal_flow.py](../e2e/deal_flow.py#L1012)
- [ ] 🟡 **S10 deposit given** (L716). There: expected payment marked received with reference, by Finance. [finance.py:80](../diwan/agents/finance.py#L80), test: [deal_flow.py](../e2e/deal_flow.py#L201). Needed: tied to signing.
- [ ] ❌ **S10 gate: signatures valid; cheque checked** (L716). Needed: both checks.
- [ ] ❌ **S10 client: "MOU and deposit received, thank you."** (L716). Needed: message.
- [ ] 🟡 **S11 Developer NOC requested** (L717). There: tick step, waiting on the seller and developer. [desk_rules.py:50](../diwan/desk_rules.py#L50), test: [deal_flow.py](../e2e/deal_flow.py#L246). Needed: application, `noc.received`.
- [ ] ❌ **S11 gate: charges cleared** (L717). Needed: service charge clearance kind and block.
- [ ] ❌ **S11 client: seller told NOC requested** (L717). Needed: message.
- [ ] 🟡 **S12 Transfer booked** (L718). There: tick. [desk_rules.py:52](../diwan/desk_rules.py#L52). Needed: date, place, `transfer.booked`.
- [ ] ❌ **S12 gate: all gates on current Facts** (L718). Needed: the gate; steps do not rest on Facts.
- [ ] ❌ **S12 client: date, place, what to bring** (L718). Needed: message.
- [ ] 🟡 **S13 Cheques prepared** (L719). There: tick for all. [desk_rules.py:51](../diwan/desk_rules.py#L51). Needed: seller, seller's bank, DLD fees, commission lines, `funds.ready`.
- [ ] ❌ **S13 gate: amounts match the payment split** (L719). Needed: a payment split.
- [ ] ❌ **S13 client: buyer's exact cheque list with payees** (L719). Needed: message. The fees exist to feed it. [finance.py:149](../diwan/agents/finance.py#L149)
- [ ] 🟡 **S14 Transfer completes; a person marks it** (L720). There: tick on "Title deed issued". [operations.py:112](../diwan/agents/operations.py#L112), test: [deal_flow.py](../e2e/deal_flow.py#L250). Needed: new title deed on file; `transfer.completed`.
- [ ] ❌ **S14 client: both hear "Congratulations, the transfer is done."** (L720). Needed: message.
- [x] ✅ **S15 Invoice and commission by Finance** (L721). There: draft, send, collect, gated on agency forms signed; other agency's share. [finance.py:158](../diwan/agents/finance.py#L158), test: [deal_flow.py](../e2e/deal_flow.py#L441)
- [ ] 🟡 **S15 client: receipt** (L721). There: a PDF a person can open; nothing sends it. [deal_desk.py:912](../diwan/deal_desk.py#L912), test: [deal_flow.py](../e2e/deal_flow.py#L974). Needed: send.
- [ ] 🟡 **S16 Handover: keys, access cards, DEWA; closes** (L722). There: tick then the four closing items, `sale.closed`, Won. [operations.py:245](../diwan/agents/operations.py#L245), test: [test_desk_rules.py](../tests/test_desk_rules.py#L167). Needed: lines for each item.
- [ ] ❌ **S16 client: welcome note and review request** (L722). Needed: messages.
- [ ] ❌ **S17 Aftercare: `renewal.due`, `referral.asked`, Records and Sales** (L723). Needed: an aftercare task on a sale; only rentals keep running.
- [ ] ❌ **S17 client: "How's the new home?" 30 days later** (L723). Needed: scheduled message.

### Off-plan from a developer (L725-736)

- [ ] ❌ **O1 Availability and price list from the developer, dated** (L729). Needed: a price list store.
- [ ] ❌ **O1 gate: price list current** (L729). Needed: the date check.
- [ ] 🟡 **O1 `unit.held`** (L729). There: unit and project typed on the deal at conversion; only our own listings can be reserved. [deal_property.py:133](../diwan/deal_property.py#L133), test: [property_flow.py](../e2e/property_flow.py#L193). Needed: hold with a date.
- [ ] ❌ **O1 client: unit, price, payment plan** (L729). Needed: message.
- [ ] 🟡 **O2 Reservation: form and booking proof** (L730). There: stage Reservation, tick step, and a payment if promised. [desk_rules.py:61](../diwan/desk_rules.py#L61), test: [test_deal_property.py](../tests/test_deal_property.py#L146). Needed: documents.
- [ ] ❌ **O2 gate: payment to the developer's account only** (L730). Needed: payee on the booking; [finance.py:34](../diwan/agents/finance.py#L34) has none, and only scheduled instalments carry the escrow payee.
- [ ] ❌ **O2 client: "Unit reserved until [date]."** (L730). Needed: message.
- [ ] 🟡 **O3 KYC by Compliance, identity set** (L731). There: as S6, screening the customer once money is discussed. [compliance.py:51](../diwan/agents/compliance.py#L51). Needed: block.
- [ ] 🟡 **O3 client: portal request if missing** (L731). There: link at conversion once sides are said. Needed: as S6.
- [ ] 🟡 **O4 SPA signed** (L732). There: tick, then the plan is entered. [desk_rules.py:63](../diwan/desk_rules.py#L63), test: [deal_flow.py](../e2e/deal_flow.py#L666). Needed: upload.
- [ ] ❌ **O4 gate: all pages signed** (L732). Needed: check.
- [ ] ❌ **O4 client: "SPA received."** (L732). Needed: message.
- [ ] 🟡 **O5 Oqood registered, Ops tracks** (L733). There: tick. [desk_rules.py:64](../diwan/desk_rules.py#L64), test: [deal_flow.py](../e2e/deal_flow.py#L666). Needed: `oqood.received`.
- [ ] ❌ **O5 gate: certificate present** (L733). Needed: upload as gate.
- [ ] ❌ **O5 client: "Your unit is now registered."** (L733). Needed: message.
- [x] ✅ **O6 Commission invoiced to the developer, on its agreement** (L734). There: rate from the owner's developer agreement. [finance.py:133](../diwan/agents/finance.py#L133), test: [deal_flow.py](../e2e/deal_flow.py#L626). Silent as the spec says.
- [x] ✅ **O6 gate: developer's trigger met** (L734). There: refused until the buyer has paid the agreed share. [finance.py:170](../diwan/agents/finance.py#L170), test: [deal_flow.py](../e2e/deal_flow.py#L661)
- [x] ✅ **O7 Installments tracked by due date** (L735). There: dated tasks, overdue shown, kept after closing. [finance.py:68](../diwan/agents/finance.py#L68), test: [deal_flow.py](../e2e/deal_flow.py#L653). No `installment.due`.
- [ ] ❌ **O7 client: reminder 14 and 3 days before each installment** (L735). Needed: a sweep; nothing tells the client.
- [ ] 🟡 **O8 Handover at completion** (L736). There: a step that runs on after closing. [desk_rules.py:65](../diwan/desk_rules.py#L65), test: [deal_flow.py](../e2e/deal_flow.py#L669). Needed: handover notice and snag list.
- [ ] ❌ **O8 gate: final payment** (L736). Needed: a block on the step.
- [ ] ❌ **O8 client: snagging appointment** (L736). Needed: booking and message.

### Rental (L738-750)

- [x] ✅ **R1 Tenant qualifies, views** (L742). There: same Sales flow. test: [visit_flow.py](../e2e/visit_flow.py)
- [x] 🧪 **R1 client: viewing details** (L742). There: as S2. test: [test_calendar.py](../tests/test_calendar.py#L116)
- [ ] 🟡 **R2 Offer: rent, cheques, move-in as Facts** (L743). There: yearly rent as the agreed price; cheque count and start date are typed later, not Facts. [desk_stages.py:105](../diwan/desk_stages.py#L105), [desk_rules.py:242](../diwan/desk_rules.py#L242). Needed: all three as Facts.
- [ ] ❌ **R2 gate: landlord accepts, quoted** (L743). Needed: landlord as a party.
- [ ] ❌ **R2 client: "The landlord accepted."** (L743). Needed: message.
- [ ] 🟡 **R3 Documents and cheques through the portal** (L744). There: identity by link; cheques are not uploaded. Needed: cheque kind.
- [ ] 🟡 **R3 gate: cheques checked; dates and amounts match Facts** (L744). There: the plan must add up to the rent; a real cheque is not compared. [finance.py:300](../diwan/agents/finance.py#L300), test: [test_desk_rules.py](../tests/test_desk_rules.py#L339). Needed: compare the photo.
- [ ] ❌ **R3 client: "Cheques received."** (L744). Needed: message.
- [ ] ❌ **R4 Tenancy contract from Facts** (L745). Needed: generated contract; a tick today. [desk_rules.py:75](../diwan/desk_rules.py#L75)
- [ ] ❌ **R4 gate: Review; both sign** (L745). Needed: signing for a contract ([signing.py:24](../diwan/signing.py#L24) knows A, B, I, F).
- [ ] ❌ **R4 client: "Contract signed."** (L745). Needed: message.
- [ ] 🟡 **R5 Ejari by Ops** (L746). There: tick by the transactions officer, who is the person who submits. [operations.py:112](../diwan/agents/operations.py#L112), test: [deal_flow.py](../e2e/deal_flow.py#L528). Needed: application filled up to Submit, `ejari.ready`.
- [ ] ❌ **R5 client: Ejari certificate** (L746). Needed: upload and send.
- [x] ✅ **R6 Agency fee: invoice, receipt, marked received** (L747). There: the commission flow. [finance.py:219](../diwan/agents/finance.py#L219), test: [deal_flow.py](../e2e/deal_flow.py#L557)
- [ ] 🟡 **R6 client: receipt** (L747). There: PDF, not sent. Needed: send.
- [ ] 🟡 **R7 Move-in: keys** (L748). There: tick. [desk_rules.py:79](../diwan/desk_rules.py#L79), test: [deal_flow.py](../e2e/deal_flow.py#L528). Needed: condition report with photos.
- [ ] ❌ **R7 gate: both acknowledge** (L748). Needed: acknowledgement by tenant and landlord.
- [ ] 🟡 **R7 `case.closed`** (L748). There: `sale.closed`, listing marked let. [deal_property.py:213](../diwan/deal_property.py#L213), test: [test_deal_property.py](../tests/test_deal_property.py#L220). Needed: name.
- [ ] ❌ **R7 client: welcome, DEWA steps** (L748). Needed: message.
- [x] ✅ **R8 Cheque dates tracked** (L749). There: each cheque dated and shown overdue if late. [finance.py:68](../diwan/agents/finance.py#L68), test: [deal_flow.py](../e2e/deal_flow.py#L526). No `cheque.due`.
- [ ] ❌ **R8 client: landlord deposit reminder** (L749). Needed: landlord contact and a sweep.
- [x] ✅ **R9 Renewal 90 days before end** (L750). There: Task for the broker, dated from the contract, owner's number. No `renewal.due`. [operations.py:277](../diwan/agents/operations.py#L277), test: [deal_flow.py](../e2e/deal_flow.py#L593)
- [ ] ❌ **R9 client: "Your lease ends on [date]; shall we renew?"** (L750). Needed: a message; the broker asks by hand.

### Listing (L752-763)

- [ ] ❌ **L1 Seller enquiry, valuation from Records' comparable sales** (L756). Needed: a comparable-sales read, `valuation.sent`, and a suggested range; Records has only totals and a document search. [records.py:63](../diwan/agents/records.py#L63)
- [ ] ❌ **L2 Form A signed at sign-up** (L757). Needed: a listing deal; Form A needs a buyer's deal with a price. [agency_forms.py:196](../diwan/agency_forms.py#L196)
- [ ] ❌ **L2 gate: seller KYC, title deed, identity set** (L757). Needed: seller party.
- [ ] ❌ **L2 client: "Thanks, we're preparing your listing."** (L757). Needed: message, `listing.signed`.
- [ ] ❌ **L3 Permit application up to Submit; photo booking** (L758). Needed: both.
- [ ] ❌ **L3 gate: a person submits** (L758). Needed: with the portal fill.
- [ ] ❌ **L3 client: photo date** (L758). Needed: message.
- [ ] ❌ **L4 Live on portals** (L759). Needed: an outbound portal listing; `listing.live`.
- [x] ✅ **L4 In the Studio, reel scripts** (L759). There: Marketing's scripts from listings. Other reviewer's slice for detail. [studio_flow.py](../e2e/studio_flow.py)
- [x] 🧪 **L4 gate: permit number on every ad** (L759). There: post check, no permit holds the text. [qa.py:156](../diwan/agents/qa.py#L156), test: [test_studio.py](../tests/test_studio.py); no browser check for it.
- [ ] ❌ **L4 client: link to the listing** (L759). Needed: seller message.
- [ ] ❌ **L5 Weekly seller report** (L760). Needed: views, enquiries, viewings, feedback per listing, `seller.report`, and a weekly send.
- [ ] ❌ **L6 Price change: seller's instruction as a quoted Fact** (L761). Needed: a listing Fact. A listing's price is a field that a later `listing.added` overwrites, with no quote.
- [ ] ❌ **L6 Withdraws every ad, script and form using the old price** (L761). Needed: listing price linked to what uses it; a deal's form rests on the deal's price Fact, not the listing's.
- [ ] 🟡 **L7 Offer continues as secondary sale step 3** (L762). There: a buyer's deal can pick the listing and is compared with its price, so the listing joins a deal at conversion. [deal_property.py:82](../diwan/deal_property.py#L82), test: [property_flow.py](../e2e/property_flow.py#L105). Needed: sales and listing sides as one deal with the seller known.
- [ ] ❌ **L8 Form A about to expire: 14 days before, renewal** (L763). Needed: Form A end date, a sweep, `form.expiring`.
- [ ] ❌ **L8 client: "Your listing agreement ends soon; renew?"** (L763). Needed: message.

<a id="part-e"></a>

## Part E: Finance, Compliance, Review, Records, Lobby

Checked against the working tree on 2026-10-31 (uncommitted files included). "Deal" in the code is the spec's Case; `rests_on` is `depends_on_facts`. None of these events exist anywhere in the code: `payment.marked_received`, `compliance.cleared`, `compliance.needs_info`, `compliance.blocked`, `deal.ready_for_transfer`, `review.requested`, `case.converted`.

### Room 5 · Finance: who it is (L189-191)

- [ ] 🟡 **Finance marks around a person's click, no bank connected** (L191). There: a person marks money received and Diwan files a receipt; nothing else happens around that click. [finance.py:80](../diwan/agents/finance.py#L80). Needed: everything in the Mark received section below.
- [x] 🧪 **Finance lead exists as a role** (L191). There: the charter exists and Nova's rounds give a Finance update line. [charters.py:93](../diwan/agents/charters.py#L93), test: [test_infra.py](../tests/test_infra.py#L24) (no browser check).
- [ ] 🟡 **Finance lead tells the owner what's late and reconciles** (L191). There: overdue money shows on the Deal desk Overview, but the lead runs on rules and does no reconciling. [deal_desk.py:244](../diwan/deal_desk.py#L244). Needed: a reconcile step (expected against marked) and a late-money line in the owner's brief.

### Room 5 · Finance: Finance lead's job (L193-199)

- [ ] 🟡 **Bill at the agreed trigger** (L195). There: Finance presses Draft the invoice by hand; it is refused until the agency forms are signed or a developer's paid share is reached. [finance.py:158](../diwan/agents/finance.py#L158), test: [test_desk_rules.py](../tests/test_desk_rules.py#L314). Needed: an owner setting for the trigger (Form F signed, transfer completed, tenancy signed) and an automatic draft when it fires.
- [x] ✅ **Invoice drafted from Facts** (L195). There: each line rests on the live price fact; rate comes from the signed agreement, developer agreement or owner's rate. [finance.py:172](../diwan/agents/finance.py#L172), test: [deal_flow.py](../e2e/deal_flow.py#L427)
- [x] ✅ **Invoice names client or developer** (L195). There: billed to the customer, the developer or the named payer. [invoices.py:28](../diwan/invoices.py#L28), test: [deal_flow.py](../e2e/deal_flow.py#L966)
- [x] ✅ **Commission % and VAT 5% on the invoice** (L195). There: both on the draft and the PDF; VAT is an owner's setting. [finance.py:143](../diwan/agents/finance.py#L143), test: [deal_flow.py](../e2e/deal_flow.py#L966)
- [x] ✅ **TRN on the invoice** (L195). There: our TRN from the settings and the payer's from the deal's terms, marked "not registered / not given" if empty. [invoices.py:56](../diwan/invoices.py#L56), test: [deal_flow.py](../e2e/deal_flow.py#L966)
- [ ] ❌ **Due date on the invoice** (L195). Needed: a `due` on the send and collect tasks, an owner's payment-terms setting, and a line in `invoice_pdf`. Without it no invoice can ever be overdue.
- [ ] 🟡 **A person approves the invoice before it goes** (L195). There: Finance previews the PDF and presses "I sent it", which is the only gate; no Approval is recorded. [finance.py:200](../diwan/agents/finance.py#L200). Needed: an `approval.given` on the invoice, pinned to its facts, required before sending.
- [ ] ❌ **Invoice sent by email** (L195). Needed: an email provider (there is none in the repo) and a send step on the invoice task.
- [ ] ❌ **Invoice sent by WhatsApp** (L195). There: "I sent it" only records that a person sent it elsewhere. [deal.html:606](../web/deal.html#L606). Needed: send the PDF through `reception._send` with a template, and a stored delivery state.
- [ ] 🟡 **Every invoice and payment has one status: draft, sent, due, overdue, partly paid, received, written off** (L196). There: tasks are queued, done or withdrawn; payments add a worked-out overdue; draft and sent are read from steps. [finance.py:65](../diwan/agents/finance.py#L65). Needed: one status field per invoice and payment, adding due, partly paid and written off.
- [ ] 🟡 **Client payments tracked: deposit, booking amount, cheques** (L196). There: promises, the rental deposit, SPA instalments and rent cheques are all expected payments. [finance.py:265](../diwan/agents/finance.py#L265), test: [deal_flow.py](../e2e/deal_flow.py#L526). Needed: the statuses in the line above.
- [ ] ❌ **Polite reminders on the owner's schedule** (L197). Needed: an owner's reminder ladder setting and a sweep in `morning_loop` that drafts reminders for overdue invoices. No invoice reminder exists.
- [ ] ❌ **Overdue developer commission goes to the brief** (L197). Needed: invoice due dates, then a line in `nova.brief`. Today the open collect task reaches Ahmed's brief only, undated.
- [ ] ❌ **Broker's commission worked out once received** (L198). There: the sale records the office's commission only. Needed: a broker split rate setting and a per-broker amount. [operations.py:271](../diwan/agents/operations.py#L271)
- [x] ✅ **Co-broker share under Form I** (L198). There: receiving the commission raises a task to pay the other agency its share, which must be paid before closing. [finance.py:228](../diwan/agents/finance.py#L228), test: [deal_flow.py](../e2e/deal_flow.py#L700)
- [ ] ❌ **Payout list for the owner to pay** (L198). Needed: a list of broker and co-broker amounts due, on the Finance view, with who paid and when. Only the one co-broker task exists, and it is Finance's, not the owner's.
- [ ] 🟡 **Report: cash in this month** (L199). There: Nova's analyst answers commission closed by period, from sales only. [records.py:97](../diwan/agents/records.py#L97), test: [test_records.py](../tests/test_records.py#L28). Needed: cash actually marked received, by month.
- [ ] 🟡 **Report: outstanding** (L199). There: commission billed vs collected and money overdue are KPI tiles. [desk_kpis.py:115](../diwan/desk_kpis.py#L115), test: [deal_flow.py](../e2e/deal_flow.py#L582). Needed: one outstanding figure including client payments.
- [ ] 🟡 **Report: expected next 30 days** (L199). There: next 7 days, and a chart of 14 days ahead. [deal_desk.py:247](../diwan/deal_desk.py#L247). Needed: a 30-day figure.
- [ ] 🟡 **Report: per broker** (L199). There: commission by broker from Nova, per period, when asked. [records.py:91](../diwan/agents/records.py#L91). Needed: the same split on the Finance report for cash and outstanding.

### Room 5 · Finance: marking a payment received (L201-211)

- [x] ✅ **Open the payment and tap Mark received** (L203). There: "Received" on the payment card and in Finance's queue, Finance role only. [deal.html:566](../web/deal.html#L566), test: [deal_flow.py](../e2e/deal_flow.py#L201)
- [ ] ❌ **Enter the amount** (L204). There: the expected amount is assumed. [finance.py:91](../diwan/agents/finance.py#L91). Needed: an amount field on the form and on the route, stored on the event.
- [ ] ❌ **Enter the date** (L204). There: today is assumed. Needed: a date field.
- [ ] ❌ **Enter the method (transfer, cheque, manager's cheque, cash, card)** (L204). Needed: a dropdown, stored on the event. The promised method lives only in the task's title.
- [x] ✅ **Enter a reference** (L204). There: required; an empty one is refused. [finance.py:89](../diwan/agents/finance.py#L89), test: [deal_flow.py](../e2e/deal_flow.py#L196)
- [ ] ❌ **Proof asked for, optional** (L204). Needed: an upload (screenshot, cheque photo, bank SMS) on the card, filed against the payment.
- [ ] ❌ **Finance lead reads the proof and flags a mismatch before saving** (L205). Needed: reading the proof with a model, comparing it with the invoice, and a warning before the save.
- [ ] ❌ **Partial amounts keep the invoice open with the balance shown** (L206). There: marking closes the whole task for its full amount. Needed: part-payment events, a running balance, and the task staying open.
- [ ] ❌ **Saving emits `payment.marked_received`** (L207). There: it writes `task.done` and `document.filed`. [finance.py:93](../diwan/agents/finance.py#L93). Needed: the event, with subscribers.
- [ ] ❌ **Marking received unblocks Deal** (L207). There: no deal step waits on a payment; only a developer's commission trigger reads the amount paid. [finance.py:119](../diwan/agents/finance.py#L119). Needed: a Deal step that waits for the deposit event.
- [ ] 🟡 **Client's WhatsApp receipt** (L207). There: a receipt PDF is filed and can be opened; nothing is sent to the client. [invoices.py:69](../diwan/invoices.py#L69), test: [deal_flow.py](../e2e/deal_flow.py#L974). Needed: send it with the worded message and the PDF.
- [ ] ❌ **Cash above the threshold goes to Compliance before the receipt** (L208). There: a cash report is drafted when cash is promised, not when it is marked. [compliance.py:162](../diwan/agents/compliance.py#L162). Needed: a check at mark time, on the method and amount actually received, holding the receipt.
- [ ] ❌ **A payer who isn't the client goes to Compliance before the receipt** (L208). Needed: a payer field at Mark received, compared with the client, holding the receipt and raising a Compliance check.
- [x] 🧪 **Every mark logged with who did it** (L209). There: the event carries the actor; the task shows the reason. [finance.py:93](../diwan/agents/finance.py#L93), test: [test_deal_desk.py](../tests/test_deal_desk.py#L156) (no browser check of who did it).
- [ ] ❌ **Undo with a reason, never deleted** (L209). There: a mark can be neither undone nor voided; a second mark is refused. Needed: an undo event with a reason that reopens the task and marks the receipt void.
- [ ] ❌ **Later: bank alerts forwarded, Finance lead suggests matches, a person confirms** (L211). Needed: nothing yet; the spec marks it "if wanted".

### Room 6 · Compliance: who it is (L213-215)

- [ ] 🟡 **Nobody signs anything binding until Compliance clears** (L213). There: the only gate is the closing checklist, after everything is signed; signing links and Form F submit do not look at Compliance. [operations.py:195](../diwan/agents/operations.py#L195), test: [test_desk_rules.py](../tests/test_desk_rules.py#L167). Needed: a clearance check in `signing.make_links`, `agency_forms.signed` and `operations.submitted`.
- [ ] 🟡 **First room told whenever a Fact changes** (L215). There: only for payer, payment-promise and income facts. See the correction rule below. [compliance.py:17](../diwan/agents/compliance.py#L17). Needed: every kind of Fact.
- [x] 🧪 **Compliance lead, Screening analyst and Source-of-funds analyst on the roster** (L215). There: charters exist and run as code. [charters.py:108](../diwan/agents/charters.py#L108), test: [test_infra.py](../tests/test_infra.py#L24) (roster only).
- [ ] 🟡 **Devil's advocate** (L215). There: a charter marked planned; nothing runs it. [charters.py:136](../diwan/agents/charters.py#L136). Needed: an agent that argues against the money story on each source-of-funds file.
- [x] ✅ **A named compliance officer makes every final call** (L215). There: the role is assigned by the owner; only its holder records results, and the work moves with the role. [compliance.py:78](../diwan/agents/compliance.py#L78), test: [deal_flow.py](../e2e/deal_flow.py#L365)
- [x] ✅ **Only the officer files** (L215). There: filing is the officer recording a goAML reference; no agent may file. [compliance.py:92](../diwan/agents/compliance.py#L92), test: [deal_flow.py](../e2e/deal_flow.py#L180)

### Room 6 · Compliance: checks table (L217-227)

- [ ] 🟡 **KYC runs at conversion** (L221). There: conversion asks each party for documents through a link, and the officer confirms each. [documents.py:216](../diwan/documents.py#L216), test: [deal_flow.py](../e2e/deal_flow.py#L899). Needed: a KYC result on the deal that later steps can read.
- [x] ✅ **ID verified** (L221). There: format, check digit, expiry and picture checks at upload, then the officer compares. [documents.py:147](../diwan/documents.py#L147), test: [deal_flow.py](../e2e/deal_flow.py#L919)
- [ ] 🟡 **Names match across documents** (L221). There: the Emirates ID name is compared with the deal's name, not across all documents, and not for sellers. [documents.py:197](../diwan/documents.py#L197). Needed: compare every document's name.
- [ ] ❌ **Address captured** (L221). Needed: an address field on the KYC documents and the client's file.
- [ ] ❌ **Risk rating: low, medium, high** (L221). Needed: an officer-set rating per deal, an event for it, and a chip on the deal.
- [ ] 🟡 **Screening runs when KYC is done** (L222). There: it runs earlier, as soon as money is discussed, for the buyer, any named party and any payer. [compliance.py:38](../diwan/agents/compliance.py#L38), test: [deal_flow.py](../e2e/deal_flow.py#L155). See Conflicts.
- [ ] 🟡 **Screening again whenever a name changes** (L222). There: a new name gets a new task; a corrected spelling of the same name does not, because any shared word counts as the same person. [compliance.py:71](../diwan/agents/compliance.py#L71), test: [test_deal_desk.py](../tests/test_deal_desk.py#L84). Needed: a rerun on any change, and a test with a new third-party payer.
- [ ] 🟡 **Sanctions and terrorist list hits** (L222). There: no list is connected; the screen tells the officer to check the lists and record what she found. [deal.html:551](../web/deal.html#L551), test: [deal_flow.py](../e2e/deal_flow.py#L167). Needed: a list connection, or an honest record that this stays manual.
- [ ] ❌ **PEP status** (L222). Needed: a recorded PEP result per person; the result today is only clear or possible match. [compliance.py:84](../diwan/agents/compliance.py#L84)
- [ ] ❌ **Adverse media** (L222). Needed: an adverse-media result per person.
- [x] ✅ **Every hit goes to the person, never auto-cleared** (L222). There: a person records every result, so no agent can clear anything; a possible match needs its list entry. [compliance.py:77](../diwan/agents/compliance.py#L77), test: [deal_flow.py](../e2e/deal_flow.py#L163)
- [ ] 🟡 **Source of funds runs above a threshold, high risk or PEP** (L223). There: it runs on every deal with money facts, whatever the amount. [compliance.py:111](../diwan/agents/compliance.py#L111). Needed: a threshold setting, plus the risk and PEP triggers once those exist.
- [x] ✅ **Source of funds shows what the client said, with the exact quote** (L223). There: numbers side by side with quotes and fact ids. [compliance.py:125](../diwan/agents/compliance.py#L125), test: [deal_flow.py](../e2e/deal_flow.py#L156)
- [ ] 🟡 **Documents asked for (bank statements, sale deed, salary letter)** (L223). There: the needed proof is listed and the officer ticks Received; nobody asks the client, and sale deed is not on the list. [compliance.py:140](../diwan/agents/compliance.py#L140), test: [deal_flow.py](../e2e/deal_flow.py#L171). Needed: a request to the client through the documents link.
- [ ] 🟡 **Whether the documents support the story** (L223). There: Received only means filed; no file is kept or compared. [deal_desk.py:455](../diwan/deal_desk.py#L455). Needed: the document itself and an officer's "supports it or not" finding.
- [ ] ❌ **Payment pattern check runs on marked received** (L224). Needed: a check at mark time. Nothing runs then; `mark_received` calls no Compliance code.
- [ ] 🟡 **Pattern: cash amounts** (L224). There: cash promises at the threshold only. [compliance.py:169](../diwan/agents/compliance.py#L169), test: [test_desk_rules.py](../tests/test_desk_rules.py#L57). Needed: actual cash, added up across payments.
- [ ] 🟡 **Pattern: third-party payers** (L224). There: a payer named in words is screened; a payer who turns up at payment is not seen. [compliance.py:58](../diwan/agents/compliance.py#L58). Needed: the payer at Mark received.
- [ ] ❌ **Pattern: split payments** (L224). Needed: a rule across a deal's received payments.
- [ ] ❌ **Pattern: crypto** (L224). There: Rania only hands crypto questions to a person. [reception.py:28](../diwan/agents/reception.py#L28). Needed: crypto as a method, flagged.
- [ ] ❌ **Pattern: mismatch with the Fact** (L224). Needed: received amount and payer compared with the promise.
- [ ] ❌ **Mortgage check runs when the Case says mortgage** (L225). There: "cash or mortgage" is a qualification answer, not a Fact kind; nothing reads it. [qualify.py:83](../diwan/qualify.py#L83). Needed: a mortgage Fact and a check that starts from it.
- [ ] ❌ **Pre-approval present and in date** (L225). Needed: the document with an expiry date, checked.
- [ ] ❌ **Amount covers price minus down payment** (L225). Needed: the sum against the live price.
- [ ] ❌ **Bank valuation vs price** (L225). Needed: a valuation amount and the comparison.
- [ ] 🟡 **Seller's liability letter if the unit is mortgaged** (L225). There: a plain paperwork tick for Operations. [desk_rules.py:49](../diwan/desk_rules.py#L49). Needed: the letter as a document with its date, in a Compliance check.
- [ ] ❌ **Enhanced due diligence on high risk or PEP** (L226). Needed: a task raised by the rating, its extra documents list.
- [ ] ❌ **Senior sign-off on enhanced due diligence** (L226). Needed: an owner or senior approval recorded on it.
- [ ] 🟡 **Cash-transaction report drafted for the officer** (L227). There: a draft and a filing task appear on its own when a cash promise reaches the limit, not when a person decides. [compliance.py:174](../diwan/agents/compliance.py#L174), test: [deal_flow.py](../e2e/deal_flow.py#L177). Needed: a person's decision; see Conflicts.
- [ ] ❌ **Suspicious transaction report draft** (L227). Needed: a Draft report action for the officer and a report template. Nothing exists.
- [x] ✅ **Diwan drafts, the officer files** (L227). There: same as above; the task only records her goAML reference. [compliance.py:92](../diwan/agents/compliance.py#L92), test: [deal_flow.py](../e2e/deal_flow.py#L180)
- [ ] ❓ **Thresholds and report forms** (L227). Needs the office's answer: what are the reporting thresholds and forms, per the compliance officer? Current default: cash AED 55,000, owner-editable. [desk_rules.py:27](../diwan/desk_rules.py#L27)

### Room 6 · Compliance: the correction rule (L229-235)

- [x] ✅ **Step 1, a new Fact contradicts an old one: payer** (L231). There: replaces the old one, or both go to the broker if it is unclear. [office.py:97](../diwan/office.py#L97), test: [deal_flow.py](../e2e/deal_flow.py#L65)
- [x] 🧪 **Step 1: price** (L231). There: same engine. [office.py:14](../diwan/office.py#L14), test: [test_desk_rules.py](../tests/test_desk_rules.py#L119) (no browser check).
- [ ] ❌ **Step 1: "I'll take a mortgage after all"** (L231). There: the Scribe has no mortgage or finance Fact kind. [scribe.py:19](../diwan/agents/scribe.py#L19). Needed: a finance Fact kind.
- [x] ✅ **Step 2, Compliance told first, for money words** (L232). There: `check.raised` is written before anything is withdrawn, addressed to the officer. [office.py:101](../diwan/office.py#L101), test: [deal_flow.py](../e2e/deal_flow.py#L76)
- [ ] 🟡 **Step 2 for every change, including price** (L232). There: a price or party correction does not reach Compliance at all, though the spec's own example is "AED 3.1M not 2.8M". [compliance.py:22](../diwan/agents/compliance.py#L22). Needed: remove the money-only filter, and a test.
- [ ] 🟡 **Step 2 when no replacement was stated** (L232). There: a contradicting price or payer goes to the broker, not Compliance. [office.py:127](../diwan/office.py#L127). Needed: Compliance told before the broker.
- [x] ✅ **Step 2, both quotes side by side** (L232). There: old and new quotes in the check's text and on the Overview. [compliance.py:27](../diwan/agents/compliance.py#L27), test: [deal_flow.py](../e2e/deal_flow.py#L306)
- [x] ✅ **Step 3, open Tasks on the old Fact are withdrawn with the reason** (L233). There: `task.withdrawn` naming the facts and the new quote. [office.py:107](../diwan/office.py#L107), test: [deal_flow.py](../e2e/deal_flow.py#L80)
- [ ] 🟡 **Step 3, finished Tasks are reopened too** (L233). There: only open tasks are touched; a done screening or a received payment stays done, unmarked. [office.py:107](../diwan/office.py#L107). Needed: done tasks marked "based on superseded fact" and reopened.
- [x] ✅ **Step 3, Approvals go back** (L233). There: the approver gets a decision card with both quotes. [review.py:14](../diwan/agents/review.py#L14), test: [deal_flow.py](../e2e/deal_flow.py#L93)
- [x] ✅ **Step 3, drafts using the old Fact are sent back** (L233). There: names the slide and both quotes; Form F and agency forms are remade. [review.py:56](../diwan/agents/review.py#L56), test: [deal_flow.py](../e2e/deal_flow.py#L235)
- [ ] 🟡 **Step 3, any sent form is recalled by Operations** (L233). There: old signing links stop working, but nobody tells the people who hold the old form. [signing.py:102](../diwan/signing.py#L102). Needed: a recall message ("Please ignore the Form B sent at 10:14") to each person it went to.
- [ ] 🟡 **Step 4, Compliance decides whether new checks are needed** (L234). There: the officer can only mark the check Reviewed with a note; reruns happen only for new names. [deal_desk.py:393](../diwan/deal_desk.py#L393), test: [deal_flow.py](../e2e/deal_flow.py#L121). Needed: a choice of which checks rerun, raising those tasks.
- [ ] 🟡 **Step 4 example, a new payer means screening and source of funds again** (L234). There: a new payer gets a screening task and new proof lines by themselves. [compliance.py:58](../diwan/agents/compliance.py#L58). Needed: a test that replaces the payer with a new third party.
- [x] ✅ **Step 5, old approvals are refused if used** (L235). There: the guard refuses and logs the reason. [office.py:158](../diwan/office.py#L158), test: [deal_flow.py](../e2e/deal_flow.py#L89)
- [x] ✅ **Step 5, unrelated work stays untouched** (L235). There: only what rests on the replaced fact is reached. [graph.py:105](../diwan/graph.py#L105), test: [test_nova.py](../tests/test_nova.py#L41) and [deal_flow.py](../e2e/deal_flow.py#L80)

### Room 6 · Compliance: clearance (L237-239)

- [ ] ❌ **Compliance emits `compliance.cleared`** (L239). There: the closest is the deal's chip, worked out as "Clear" from tasks. [deal_desk.py:143](../diwan/deal_desk.py#L143). Needed: an officer's clear action, an event, pinned to Fact versions.
- [ ] ❌ **`compliance.needs_info`, and Deal asks the client through the portal** (L239). There: only a funding question to the broker. [compliance.py:185](../diwan/agents/compliance.py#L185). Needed: an officer's action that opens a client document request.
- [ ] ❌ **`compliance.blocked`: the Case stops and the owner is told** (L239). There: no hold exists; a charter lists "hold" but no code uses it. Needed: a blocked state that every Deal, Finance and signing action checks, and an owner notice.
- [ ] ❌ **No `deal.ready_for_transfer` without `compliance.cleared` on current Fact versions** (L239). There: transfer starts as soon as Form F is submitted. [operations.py:102](../diwan/agents/operations.py#L102). Needed: the event, the gate, and clearance withdrawn when a Fact is replaced.
- [ ] 🟡 **Open compliance work stops the deal closing** (L239). There: open screenings, reports and checks block closing, but a possible match counts as done, so a deal with an unresolved hit can close. [operations.py:195](../diwan/agents/operations.py#L195), test: [test_desk_rules.py](../tests/test_desk_rules.py#L167). Needed: keep a possible match open until the officer resolves it; no action exists for that today.

### Room 7 · Review: the gate (L241-243)

- [ ] 🟡 **Nothing reaches an approve button before Review** (L243). There: every draft is checked when made, but `office.approve` needs no review, and client messages and transfer requests are not drafts. [review.py:67](../diwan/agents/review.py#L67), test: [test_deal_desk.py](../tests/test_deal_desk.py#L211). Needed: Review as a required step before any approval.
- [x] ✅ **Fact checker runs on every draft** (L243). There: `check_draft` runs inside `make_draft`, for decks, invoices, Form F, forms and cash reports. [office.py:172](../diwan/office.py#L172), test: [deal_flow.py](../e2e/deal_flow.py#L434)
- [ ] ❌ **Devil's advocate checks every item** (L243). There: planned only, and its charter covers source-of-funds files. [charters.py:136](../diwan/agents/charters.py#L136). Needed: a run on each item. See Conflicts.
- [ ] 🟡 **The person sees what Review found** (L243). There: a "passed review" chip or the send-back reason on the draft. [deal.html:964](../web/deal.html#L964), test: [deal_flow.py](../e2e/deal_flow.py#L82). Needed: findings for items that pass.

### Room 7 · Review: what it checks (L245-252)

- [x] ✅ **Quotes: still the current Fact** (L247). There: a slide using a replaced fact is sent back. [review.py:72](../diwan/agents/review.py#L72), test: [test_deal_desk.py](../tests/test_deal_desk.py#L211) and [deal_flow.py](../e2e/deal_flow.py#L252)
- [ ] 🟡 **Quotes: every claim traces to an exact quote** (L247). There: agent packs have invented quotes removed, but a draft line with no fact behind it passes Review. [runner.py:137](../diwan/agents/runner.py#L137), test: [test_infra.py](../tests/test_infra.py#L49). Needed: a failed finding for a claim with no source.
- [ ] ❌ **Numbers match across all documents in the Case** (L248). There: only "does it use a replaced fact". Needed: a comparison of price, commission, VAT, dates and unit numbers across drafts and Facts. A typed number that differs passes.
- [ ] ❌ **Completeness: this stage's checklist is done** (L249). Needed: a per-stage checklist read by Review.
- [ ] 🟡 **Required signatures on every line** (L249). There: Form F and the invoice wait for the signed agency forms, as their own checks. [operations.py:95](../diwan/agents/operations.py#L95), test: [deal_flow.py](../e2e/deal_flow.py#L785). Needed: the same as a Review finding.
- [x] 🧪 **Authority: the agent was allowed to (the charter)** (L250). There: every proposed action is checked and refused outside the charter, in the runner rather than in Review. [runner.py:140](../diwan/agents/runner.py#L140), test: [test_infra.py](../tests/test_infra.py#L65) (no browser check).
- [ ] 🟡 **Authority: nothing sent or submitted without a yes** (L250). There: true for Form F; invoices record no yes. [operations.py:81](../diwan/agents/operations.py#L81). Needed: a Review finding that looks for the approval.
- [ ] 🟡 **Tone and promises in client-facing text** (L251). There: Marketing posts and Rania have banned wording, and follow-ups a tipping-off filter; Review itself reads no text. [studio.py:55](../diwan/agents/studio.py#L55). Needed: the same check on every client-facing item in Review, including visa claims and "price will go up".
- [ ] ❌ **Compliance: the item doesn't pass a hold** (L252). Needed: holds first, then a Review check.

### Room 7 · Review: what the person sees (L254-256)

- [ ] ❌ **One card per item** (L256). There: drafts sit inside each deal's departments; there is no Review queue. [deal.html:957](../web/deal.html#L957). Needed: a Review view listing every item.
- [ ] 🟡 **Card says what it is, and the room and agent that made it** (L256). There: kind and version; the deal's section shows the room; the agent is not shown. [deal.html:963](../web/deal.html#L963). Needed: the agent's name.
- [ ] ❌ **Green, amber, red verdict** (L256). There: passed or sent back only. Needed: three verdicts from the checks above.
- [ ] 🟡 **Each finding in one line** (L256). There: one reason on a send-back, for the first stale slide only. [review.py:57](../diwan/agents/review.py#L57), test: [deal_flow.py](../e2e/deal_flow.py#L82). Needed: all findings.
- [ ] 🟡 **Links to the quotes** (L256). There: fact ids in the text and on the slide; not clickable. [deal.html:967](../web/deal.html#L967). Needed: links.
- [ ] ❌ **Approve button on the card** (L256). There: approvals are not given from draft cards except on decks. Needed: Approve on every item.
- [ ] ❌ **Send back with a note to the agent** (L256). There: only the code sends back; a person cannot. Needed: the button and the note.
- [ ] ❌ **Edit** (L256). Needed: the person edits the item, recorded as an edit.
- [x] ✅ **Approve pins to the current Fact versions** (L256). There: an approval rests on fact ids, and re-approval moves it to the live ones. [review.py:40](../diwan/agents/review.py#L40), test: [deal_flow.py](../e2e/deal_flow.py#L107)
- [ ] ❌ **Send back creates a Task for the room with the note** (L256). Needed: a task, once a person can send back. Today `review.returned` raises no task.
- [ ] ❌ **Send-back patterns feed the Lobby and the agents' instructions** (L256). There: a 30-day count of sent-back drafts. [desk_kpis.py:45](../diwan/desk_kpis.py#L45). Needed: grouping by cause, and a route to the Lobby.

### Room 8 · Records: what it holds (L258-266)

- [x] ✅ **One system of record** (L260). There: everything is rebuilt from one append-only log. [events.py:61](../diwan/events.py#L61), test: [test_infra.py](../tests/test_infra.py#L78)
- [ ] ❓ **Kept for the retention period** (L260). Needs the office's answer: how long, per the compliance officer? Current default: nothing is ever removed; the deal page says "at least five years". [deal.html:652](../web/deal.html#L652)
- [x] 🧪 **Records clerk files and indexes** (L260). There: the Archivist; documents are filed against the deal automatically and found by question. [office.py:195](../diwan/office.py#L195), test: [test_records.py](../tests/test_records.py#L39) (no browser check).
- [x] 🧪 **Data analyst answers questions** (L260). There: computes from records, a model never produces a number. [records.py:63](../diwan/agents/records.py#L63), test: [test_records.py](../tests/test_records.py#L28) (no browser check).
- [ ] 🟡 **Case file: timeline of every Event** (L264). There: the deal's "What changed" list, limited to 14 events of 18 types. [deal.html:1007](../web/deal.html#L1007). Needed: the whole list.
- [x] ✅ **Case file: every Fact with its quote and superseded history** (L264). There: "What the customer said" shows replaced facts and what replaced them. [deal.html:974](../web/deal.html#L974), test: [deal_flow.py](../e2e/deal_flow.py#L78)
- [ ] 🟡 **Case file: every document version** (L264). There: draft versions and the client's documents show; filed receipts, proofs and closing documents have no list on the deal. [deal_desk.py:81](../diwan/deal_desk.py#L81). Needed: the deal's filed documents in one list.
- [ ] 🟡 **Case file: every approval and who gave it** (L264). There: shown under Finance only. [deal.html:518](../web/deal.html#L518), test: [deal_flow.py](../e2e/deal_flow.py#L107). Needed: in one case file.
- [ ] 🟡 **Register: deals closed** (L265). There: the Closed filter on the Deal desk, and an API no screen uses. [deal_desk.py:318](../diwan/deal_desk.py#L318), test: [deal_flow.py](../e2e/deal_flow.py#L573). Needed: a Records page; `/api/records` has no reader.
- [ ] 🟡 **Register: listings** (L265). There: the Catalog page. Needed: a place under Records.
- [ ] ❌ **Register: tenancies with renewal dates** (L265). There: dates sit in each deal's terms. [desk_rules.py:242](../diwan/desk_rules.py#L242). Needed: a list across deals.
- [ ] 🟡 **Register: commissions** (L265). There: on each sale, and from Nova per period. [records.py:97](../diwan/agents/records.py#L97). Needed: a register.
- [ ] 🟡 **Register: compliance files** (L265). There: screenings, proofs and reports sit on the deal. Needed: a compliance file view.
- [ ] ❓ **Compliance files kept for the legal period** (L265). Needs the office's answer: the legally required period, per the compliance officer. Current default: same as retention above.
- [x] 🧪 **Audit trail: who did what and when, agents included, read-only** (L266). There: every event names its actor, and the database refuses changes. [events.py:61](../diwan/events.py#L61), test: [test_infra.py](../tests/test_infra.py#L78) (no page shows it whole).
- [ ] ❌ **Nothing deleted, only marked void with a reason** (L266). There: nothing is deleted, but no void exists for a document or record. Needed: a void event with a reason, and the record shown as void.

### Room 8 · Records: what the Data analyst answers (L268-277)

- [x] 🧪 **Answers to the owner through Nova** (L268). There: numbers and documents questions go to the Records team. [records.py:124](../diwan/agents/records.py#L124), test: [test_records.py](../tests/test_records.py#L59) (no browser check).
- [ ] ❌ **Records dashboard** (L268). There: the Records floor shows the general walls. Needed: a page.
- [ ] 🟡 **Funnel: leads to qualified to viewing to offer to closed** (L270). There: a count of deals at each stage today. [deal_desk.py:271](../diwan/deal_desk.py#L271). Needed: how many passed each step, with where they drop.
- [ ] ❌ **Funnel by channel** (L270). Needed: the breakdown.
- [ ] ❌ **Funnel by broker** (L270). Needed: the breakdown.
- [ ] ❌ **Funnel by month** (L270). Needed: the breakdown.
- [ ] ❌ **Speed: time to first reply** (L271). Needed: worked out from the chat messages.
- [ ] ❌ **Speed: time to call after "call me"** (L271). Needed: worked out from the attention cards.
- [ ] 🟡 **Speed: days in each stage** (L271). There: each stage's date is stored but never counted; yes-to-closed and time per paperwork step are. [desk_kpis.py:77](../diwan/desk_kpis.py#L77), test: [test_desk_rules.py](../tests/test_desk_rules.py#L391). Needed: stage durations.
- [x] ✅ **Money: commission closed and pending** (L272). There: closed from sales, pending as billed vs collected. [desk_kpis.py:128](../diwan/desk_kpis.py#L128), test: [deal_flow.py](../e2e/deal_flow.py#L582)
- [ ] ❌ **Money: cost per lead by channel** (L272). Needed: ad spend joined to leads.
- [ ] ❌ **Money: average deal size** (L272). Needed: a figure from the sales.
- [ ] 🟡 **People: broker leaderboard** (L273). There: commission by broker, when asked with a period. [records.py:91](../diwan/agents/records.py#L91). Needed: a view, with test.
- [ ] ❌ **People: follow-up discipline** (L273). Needed: a per-broker measure.
- [ ] ❌ **People: send-back rate in Review** (L273). Needed: a per-broker or per-agent rate.
- [ ] 🟡 **Market: asking vs closing prices by area** (L274). There: agreed price against the listing, per broker. [desk_kpis.py:139](../diwan/desk_kpis.py#L139), test: [deal_flow.py](../e2e/deal_flow.py#L741). Needed: by area.
- [ ] 🟡 **Renewals: tenancies ending in 90 days become Sales Tasks** (L275). There: closing a rental raises one task for the broker, dated 90 days before the end; it is not a sweep, and sits under Operations. [operations.py:278](../diwan/agents/operations.py#L278), test: [deal_flow.py](../e2e/deal_flow.py#L565). Needed: a Sales task raised by a daily sweep over tenancies.
- [ ] ❌ **A closed Case turns into the next one** (L275). There: the renewal answer is a note. [operations.py:302](../diwan/agents/operations.py#L302). Needed: a new deal or lead opened from it.
- [ ] ❌ **Weekly report on Monday morning, in the brief** (L277). Needed: a scheduled report and a section in the owner's brief.
- [ ] 🟡 **Every number links to the records behind it** (L277). There: Nova's answers cite ids as chips, and KPI tiles open deals. [index.html:57](../web/index.html#L57), test: [test_records.py](../tests/test_records.py#L31). Needed: chips that open the record.

### Room 9 · Lobby (L279-295)

`diwan/agents/lobby.py` is not this room: it is the "Lobby board", a request board where staff ask each other for work. [lobby.py:1](../diwan/agents/lobby.py#L1)

- [ ] ❌ **A shared Lobby room for reading what works elsewhere** (L281). Needed: a new room, page and events.
- [ ] ❌ **Lobby host** (L281). Needed: a charter and an agent.
- [ ] ❌ **One representative from each room** (L281). Needed: charters.
- [ ] ❌ **Input: anonymised opt-in playbooks from other Diwan offices** (L285). Needed: an opt-in, a sharing service, and anonymising. The `mplay` playbook covers this office's own posts only.
- [ ] ❌ **Never client data, never identifying names or numbers** (L285). Needed: a filter on what goes in or out.
- [ ] 🟡 **Input: competitors' posts and reels** (L286). There: the Studio has them; nothing feeds a Lobby. [charters.py:170](../diwan/agents/charters.py#L170). Needed: the feed.
- [ ] ❌ **Input: portal listing trends** (L286). Needed: a source.
- [ ] ❌ **Input: DLD transaction data** (L286). Needed: a source.
- [ ] ❌ **Input: news on projects and regulation** (L286). Needed: a source.
- [ ] ❌ **Input: Review send-backs** (L287). Needed: the feed.
- [ ] ❌ **Input: lost deals with reasons** (L287). Needed: the dropdown below, then the feed.
- [ ] ❌ **Input: questions Rania couldn't answer** (L287). There: handed to a person, reason logged, not collected. [reception.py:47](../diwan/agents/reception.py#L47). Needed: the feed.
- [ ] ❌ **Weekly discussion thread per room** (L291). Needed: a thread, on a schedule.
- [ ] ❌ **Each thread proposes a change** (L291). Needed: the proposal.
- [ ] ❌ **A proposal is an experiment: what, for whom, how long, which number** (L292). Needed: an experiment record.
- [ ] ❌ **The owner approves the experiment** (L292). Needed: the approval.
- [ ] ❌ **After the period, Records reports whether it worked** (L292). Needed: the report.
- [ ] ❌ **The change is kept or rolled back** (L292). Needed: the decision, and a change that can be undone.
- [ ] ❌ **One idea a day in the morning brief** (L293). Needed: a brief line.
- [ ] 🟡 **An agent may suggest a change to its own instructions but cannot apply it** (L295). There: lessons are added by people and charters are code, so it can't apply one; it can't suggest either. [lessons.py:126](../diwan/agents/lessons.py#L126), test: [test_lessons.py](../tests/test_lessons.py). Needed: a suggestion path.
- [ ] ❌ **Compliance rules and the owner's settings can't be changed from the Lobby** (L295). Needed: the guard, once the Lobby exists. Today it is true only because there is no Lobby.

### Commands · Finance: blocks on screen (L506-508)

- [ ] 🟡 **Finance room screen** (L508). There: no room page; Finance is a section of each deal, plus Ahmed's queue and Overview tiles. [deal.html:970](../web/deal.html#L970). Needed: a page.
- [ ] ❌ **Invoices block with statuses** (L508). Needed: a list across deals.
- [x] ✅ **Mark received block** (L508). There: on the payment card and in the queue, for the fields that exist today. [deal.html:415](../web/deal.html#L415), test: [deal_flow.py](../e2e/deal_flow.py#L201)
- [x] ✅ **Expected payments, each tied to the client's words** (L508). There: shows the quote, the promised day and overdue. [deal.html:558](../web/deal.html#L558), test: [deal_flow.py](../e2e/deal_flow.py#L193)
- [ ] 🟡 **Commissions to split and pay out** (L508). There: the commission card per deal and a queue row for the other agency. [deal.html:663](../web/deal.html#L663), test: [deal_flow.py](../e2e/deal_flow.py#L700). Needed: a list, with broker payouts.
- [ ] 🟡 **Cash this month, outstanding, next 30 days** (L508). See the report lines above. [deal.html:218](../web/deal.html#L218). Needed: the three figures in one block.
- [ ] ❌ **Flags for Compliance** (L508). Needed: a block once Mark received raises flags.

### Commands · Finance: build list (L510-520)

- [ ] 🟡 **Invoice clerk's main job is outgoing commission invoices** (L512). There: the code does this, but the charter still says it reads supplier invoices. [charters.py:103](../diwan/agents/charters.py#L103). Needed: the charter's job changed.
- [ ] ❌ **Reading supplier invoices stays as a secondary job** (L512). There: charter only, marked for later; no code reads them. Needed: the reader.
- [ ] 🟡 **Drafts at the owner's trigger** (L514). Same as L195. [finance.py:158](../diwan/agents/finance.py#L158)
- [ ] 🟡 **Mark received with amount, date, method, reference, proof** (L515). Same as L204: reference only. [finance.py:80](../diwan/agents/finance.py#L80)
- [ ] ❌ **On save: emit, unblock, receipt, Compliance first** (L516). Same as L207-208.
- [ ] 🟡 **Split per broker and co-broker, payout list** (L517). Co-broker only, same as L198. [finance.py:228](../diwan/agents/finance.py#L228)
- [ ] ❌ **Reminders for overdue invoices** (L518). Same as L197.
- [ ] ❌ **Test: mismatched proof shows a flag** (L519). Needed: the feature, then this test.
- [ ] ❌ **Test: third-party payer goes to Compliance before the receipt** (L519). Needed: the feature, then this test.

### Commands · Compliance: blocks on screen (L522-524)

- [ ] 🟡 **Compliance room screen** (L524). There: no room page; a section of each deal, her queue and an Overview tile. [deal.html:220](../web/deal.html#L220). Needed: a page.
- [x] ✅ **Corrections: old vs new quote, side by side, newest first** (L524). There: on the Deal desk Overview, sorted newest first. [deal_desk.py:261](../diwan/deal_desk.py#L261), test: [deal_flow.py](../e2e/deal_flow.py#L306)
- [x] ✅ **Screening queue** (L524). There: her queue and the Not screened filter. [deal_desk.py:229](../diwan/deal_desk.py#L229), test: [deal_flow.py](../e2e/deal_flow.py#L327)
- [ ] 🟡 **Hits waiting for the officer** (L524). There: a Possible match filter; since she records the hit herself, nothing waits. [deal_desk.py:299](../diwan/deal_desk.py#L299). Needed: a resolve step.
- [x] ✅ **Source-of-funds files: what the client said vs documents** (L524). There: numbers and quotes above the proof list, per deal. [deal.html:944](../web/deal.html#L944), test: [deal_flow.py](../e2e/deal_flow.py#L156)
- [ ] ❌ **Risk rating per Case** (L524). Same as L221.
- [ ] ❌ **Holds: Cases blocked and why** (L524). Same as L239.
- [ ] 🟡 **Report drafts for the officer** (L524). Cash reports only. [deal_desk.py:298](../diwan/deal_desk.py#L298), test: [deal_flow.py](../e2e/deal_flow.py#L177). Needed: suspicious transaction drafts.
- [ ] 🟡 **Rule book** (L524). There: the owner's rules panel holds the cash limit; no rule book exists, though charters name one. [charters.py:110](../diwan/agents/charters.py#L110). Needed: a page.

### Commands · Compliance: build list (L526-536)

- [ ] 🟡 **Open Tasks assigned to an idle agent must start** (L528). There: screening waits for the officer by design, as no list is connected; the floor counts only cards, so the analyst looks idle. [office3d.html:627](../web/office3d.html#L627). Needed: open tasks counted as waiting.
- [ ] ❌ **Task titles name what raised them, not the client** (L528). There: "Screen Karim Haddad, the buyer". [compliance.py:73](../diwan/agents/compliance.py#L73). See Conflicts.
- [ ] 🟡 **Run KYC, screening, source of funds, payment-pattern and mortgage checks at their triggers** (L530). Each is covered in the table above: two run early, two never.
- [x] ✅ **Every hit goes to the named officer; agents never clear** (L531). Same as L222. [compliance.py:77](../diwan/agents/compliance.py#L77), test: [deal_flow.py](../e2e/deal_flow.py#L163)
- [ ] 🟡 **Correction rule** (L532). Works for money words. Same as L231-235. [office.py:97](../diwan/office.py#L97)
- [ ] ❌ **Emit cleared, needs_info, blocked; needs_info becomes a portal request** (L533). Same as L239.
- [ ] 🟡 **Report drafter prepares, Diwan never files** (L534). Cash only. [compliance.py:162](../diwan/agents/compliance.py#L162)
- [ ] 🟡 **Thresholds are settings** (L534). There: the cash limit is; source of funds has none. [desk_rules.py:27](../diwan/desk_rules.py#L27), test: [deal_flow.py](../e2e/deal_flow.py#L415). Needed: the other thresholds.
- [ ] 🟡 **Test: a new payer reruns screening and blocks transfer until cleared** (L535). There: no such test; the existing one covers a payer removed. [test_deal_desk.py](../tests/test_deal_desk.py#L84). Needed: the block, then this test.

### Commands · Review: blocks on screen (L538-540)

- [ ] ❌ **Items awaiting review, green, amber, red** (L540). Same as L256; nothing ever waits, as drafts pass at once.
- [ ] 🟡 **Findings per item, each linked to its quote** (L540). Same as L256. [deal.html:965](../web/deal.html#L965)
- [ ] 🟡 **Sent back with the note** (L540). There: a chip on the deal list and the reason on the draft, written by code. [deal_desk.py:167](../diwan/deal_desk.py#L167), test: [deal_flow.py](../e2e/deal_flow.py#L252). Needed: a person's note, in one list.
- [ ] 🟡 **Approved, with the Fact versions they're pinned to** (L540). There: in the Finance section, with quotes. [deal.html:522](../web/deal.html#L522), test: [deal_flow.py](../e2e/deal_flow.py#L107). Needed: under Review.
- [ ] ❌ **Patterns in send-backs this week** (L540). Same as L256.

### Commands · Review: build list (L542-551)

- [ ] ❌ **Every item needing approval emits `review.requested` first** (L544). There: no such event. Needed: the event on forms, invoices, late client messages, decks and transfer requests.
- [ ] 🟡 **Checks per item** (L546). Only "quotes current" and the charter run. Same as L247-252.
- [ ] ❌ **One card per item with Approve, Send back, Edit** (L547). Same as L256.
- [ ] 🟡 **Approve pins, Send back creates a Task** (L548). The first works, the second doesn't. Same as L256.
- [ ] ❌ **Weekly send-back patterns go to the Lobby** (L549). Same as L256.
- [ ] 🟡 **Test: an invoice whose price differs from the current Fact is red; approving is blocked** (L550). There: a replaced price sends the invoice back and sending is refused. [test_desk_rules.py](../tests/test_desk_rules.py#L119). Needed: red verdict, and the same for a number typed differently.

### Commands · Records: blocks on screen (L553-555)

- [ ] 🟡 **Search across all Cases** (L555). There: the Deal desk searches customer, property, broker and id; the header search covers knowledge and listings only. [deal_desk.py:315](../diwan/deal_desk.py#L315), test: [deal_flow.py](../e2e/deal_flow.py#L279). Needed: search over facts and documents too.
- [ ] 🟡 **Case file timeline** (L555). Same as L264. [deal.html:1003](../web/deal.html#L1003)
- [ ] 🟡 **Registers** (L555). Same as L265.
- [ ] 🟡 **Funnel by channel and broker** (L555). Same as L270.
- [ ] ❌ **Speed: first reply, call after "call me"** (L555). Same as L271.
- [ ] 🟡 **Money** (L555). Same as L272.
- [ ] ❌ **Renewals in the next 90 days** (L555). Needed: a block; the task sits in the broker's queue only.
- [ ] 🟡 **Audit trail** (L555). There: the last 8 events per agent on the Team page and the deal's list. [team.html:75](../web/team.html#L75). Needed: a page over the whole log.

### Commands · Records: build list (L557-567)

- [ ] ❌ **Open work wall shows Records' own work** (L559). There: the Records floor still shows every department's tasks, because it isn't in the desk list. [office3d.html:584](../web/office3d.html#L584). Needed: Records' own filing, reports and renewals.
- [ ] 🟡 **Case file view** (L561). Same as L264.
- [ ] 🟡 **Analyst answers from the PA chat, each number linked** (L562). There: answers with cited ids. [records.py:138](../diwan/agents/records.py#L138), test: [test_records.py](../tests/test_records.py#L28). Needed: links to the rows.
- [x] 🧪 **Says "not recorded" rather than estimating** (L562). There: no period gets a question, and no filed records says so. [records.py:76](../diwan/agents/records.py#L76), test: [test_records.py](../tests/test_records.py#L46) (no browser check).
- [ ] ❌ **Weekly Monday report** (L563). Same as L277.
- [ ] 🟡 **Tenancies ending in 90 days create Sales Tasks** (L564). Same as L275.
- [ ] 🟡 **Audit read-only, void with reason** (L565). Read-only is done; void isn't. Same as L266.
- [ ] ❌ **Test: a renewal Task appears for a seeded tenancy ending in 60 days** (L566). There: the tests cover a task at closing, a year out. [test_desk_rules.py](../tests/test_desk_rules.py#L353). Needed: the sweep, then this test.

### Commands · Lobby (L569-582)

- [ ] ❌ **This week's threads by room** (L571). Needed: as above.
- [ ] ❌ **Playbook cards (pattern, where seen, evidence)** (L571). Needed: as above.
- [ ] ❌ **Proposed experiments (change, audience, period, metric)** (L571). Needed: as above.
- [ ] ❌ **Running experiments with results from Records** (L571). Needed: as above.
- [ ] ❌ **Kept and rolled back** (L571). Needed: as above.
- [ ] ❌ **Add a Lobby room to the floor** (L574). There: the Front desk's "Lobby board" core is the request board. [office3d.html:130](../web/office3d.html#L130). Needed: a new room in `DEPTS`, under a name that doesn't clash.
- [ ] ❌ **Inputs** (L576). Same as L285-287.
- [ ] ❌ **Weekly thread per room ending in at most one experiment** (L577). Same as L291-292.
- [ ] ❌ **The owner approves; agents may not change their instructions or any compliance setting** (L578). Same as L292-295.
- [ ] ❌ **After the period Records reports; keep or roll back** (L579). Same as L292.
- [ ] ❌ **One idea a day in the brief** (L580). Same as L293.
- [ ] ❌ **Test: an approved experiment changes a follow-up template only for its audience and period** (L581). Needed: the feature, then this test.

### When things go wrong: the rule (L765-767)

- [ ] 🟡 **No unhappy path ends with the Case sitting still** (L767). There: a Stuck tile, only after paperwork starts. [desk_kpis.py:65](../diwan/desk_kpis.py#L65), test: [test_desk_rules.py](../tests/test_desk_rules.py#L391). Needed: a chaser for every open case, into the brief.
- [ ] ❌ **Agents prepare the options on money and legal outcomes** (L767). There: no option list exists for any row below. Needed: a template per row.
- [x] 🧪 **Money and legal outcomes are a person's call** (L767). There: no agent may approve, release, submit or file. [test_infra.py](../tests/test_infra.py#L35) (no browser check).

### When things go wrong: client corrects themselves (L771)

- [x] ✅ **Detected when a new Fact contradicts an old one** (L771). There: the Scribe's replaces, or one question to the broker when it is unclear. [office.py:116](../diwan/office.py#L116), test: [deal_flow.py](../e2e/deal_flow.py#L65)
- [ ] 🟡 **Compliance first** (L771). There: payer yes; price, finance and unit no. [compliance.py:22](../diwan/agents/compliance.py#L22). Needed: as L232.
- [x] ✅ **Dependent work withdrawn** (L771). Same as L233. [office.py:106](../diwan/office.py#L106), test: [deal_flow.py](../e2e/deal_flow.py#L80)
- [ ] 🟡 **Forms recalled** (L771). Same as L233.
- [ ] 🟡 **A change of unit** (L771). There: changing the property sends unsigned forms back, but it is a setting, not a Fact, so Compliance isn't told. [agency_forms.py:135](../diwan/agency_forms.py#L135). Needed: a Fact.
- [ ] 🟡 **Compliance officer decides, then broker** (L771). There: both answer cards, in no enforced order. [deal_desk.py:393](../diwan/deal_desk.py#L393). Needed: the broker's step waits for the officer.
- [x] ✅ **The Case continues** (L771). There: the stage doesn't change. Test: [deal_flow.py](../e2e/deal_flow.py#L65)

### When things go wrong: buyer goes quiet after the offer (L772)

- [ ] 🟡 **Detected: no reply past the follow-up ladder** (L772). There: the ladder runs only while Rania has the chat and stops once a person does, as is usual after an offer. [nudge.py:150](../diwan/agents/nudge.py#L150), test: [test_nudge.py](../tests/test_nudge.py#L104). Needed: a ladder for offer-stage deals.
- [ ] 🟡 **Broker call Task** (L772). There: one "gone quiet" card, if the owner picks that; the default is Nurture. [nudge.py:21](../diwan/agents/nudge.py#L21). Needed: always a call task at this stage.
- [ ] ❌ **Then owner brief** (L772). Needed: a brief line.
- [ ] ❌ **The seller is kept informed** (L772). Needed: a draft to the seller.
- [ ] 🟡 **Broker decides** (L772). There: the broker can mark Lost. [desk_stages.py:47](../diwan/desk_stages.py#L47), test: [test_desk_rules.py](../tests/test_desk_rules.py#L425). Needed: a prompt to decide.
- [ ] 🟡 **Continues or lost ("no response")** (L772). There: Lost with free text. [deal.html:715](../web/deal.html#L715). Needed: the dropdown.

### When things go wrong: buyer walks away after the MOU (L773)

- [ ] 🟡 **Detected: buyer says so, quoted** (L773). There: a person marks Lost with a typed reason, unconnected to any quote. [desk_stages.py:69](../diwan/desk_stages.py#L69). Needed: the quote as a Fact on the loss.
- [ ] ❌ **Deposit handling per Form F terms, prepared as options** (L773). Needed: an options card.
- [ ] ❌ **Seller told** (L773). Needed: a draft.
- [x] ✅ **Listing reactivated** (L773). There: Lost frees our reserved listing. [deal_property.py:201](../diwan/deal_property.py#L201), test: [property_flow.py](../e2e/property_flow.py#L244)
- [ ] ❌ **Owner decides with the office's lawyer** (L773). There: the broker or transactions officer can mark it lost alone. [desk_stages.py:28](../diwan/desk_stages.py#L28). Needed: an owner's decision after the MOU.
- [x] ✅ **Ends lost, listing back to live** (L773). There: as above, and open work is left as it was. Test: [test_deal_property.py](../tests/test_deal_property.py#L208)
- [ ] ❌ **Open work closes when a deal is lost** (L773). There: Lost does not withdraw tasks, so expected payments and forms stay open. [desk_stages.py:75](../diwan/desk_stages.py#L75). Needed: a withdraw on Lost.

### When things go wrong: seller withdraws after the MOU (L774)

- [ ] 🟡 **Detected: seller says so, quoted** (L774). Same as L773; there is no seller on the deal to quote. [desk_stages.py:69](../diwan/desk_stages.py#L69)
- [ ] ❌ **Deposit handling, reversed** (L774). Needed: an options card.
- [ ] ❌ **Buyer offered alternatives** (L774). Needed: a recommendation from the listings.
- [ ] ❌ **Owner decides with the lawyer** (L774). Same as L773.
- [ ] ❌ **Lost; buyer back to Sales** (L774). There: the deal is just Lost; a return needs a person, and the buyer isn't reopened. Needed: a new or reopened lead.

### When things go wrong: mortgage refused (L775)

- [ ] ❌ **Detected: bank letter** (L775). There: a paperwork step that can only be ticked or skipped. [desk_rules.py:48](../diwan/desk_rules.py#L48). Needed: the letter as a document, and a refused outcome.
- [ ] ❌ **Options: another bank, more cash, cancel per MOU** (L775). Needed: an options card.
- [ ] ❌ **Buyer and broker decide** (L775). Needed: the decision recorded.
- [ ] 🟡 **Continues or lost** (L775). There: Lost with free text works. [test_deal_property.py](../tests/test_deal_property.py#L208)

### When things go wrong: valuation below price (L776)

- [ ] ❌ **Detected: valuation report** (L776). Needed: the report's amount.
- [ ] ❌ **Gap shown (price minus valuation)** (L776). Needed: the sum.
- [ ] ❌ **Options: renegotiate, cover in cash, cancel** (L776). Needed: an options card.
- [ ] ❌ **Buyer and seller decide** (L776). Needed: the decision recorded.
- [ ] 🟡 **Continues with new Facts, or lost** (L776). There: a new price is a correction, and Lost works. [office.py:97](../diwan/office.py#L97), test: [test_desk_rules.py](../tests/test_desk_rules.py#L119)

### When things go wrong: seller's liability letter expires (L777)

- [ ] ❌ **Detected: expiry date** (L777). Needed: the date on the letter.
- [ ] ❌ **New letter Task before transfer** (L777). Needed: a sweep.
- [ ] ❌ **Seller decides, Case continues** (L777). Needed: the above.

### When things go wrong: developer NOC refused or delayed (L778)

- [ ] 🟡 **Detected: developer response** (L778). There: a step waiting on "the seller and the developer", showing in Stuck when idle; no refused state. [desk_rules.py:50](../diwan/desk_rules.py#L50), test: [deal_flow.py](../e2e/deal_flow.py#L246). Needed: a refused or delayed outcome.
- [ ] ❌ **Seller asked to clear** (L778). Needed: a draft.
- [ ] ❌ **Transfer date moved** (L778). There: no transfer date on the deal. Needed: the date.
- [ ] ❌ **Both told** (L778). Needed: drafts.
- [x] 🧪 **Case continues** (L778). There: the step stays open. Test: [test_deal_desk.py](../tests/test_deal_desk.py#L182) (no NOC-specific check).

### When things go wrong: screening hit or unclear source of funds (L779)

- [x] ✅ **Detected by Compliance** (L779). There: possible match recorded, and proof missing counted. [deal_desk.py:133](../diwan/deal_desk.py#L133), test: [deal_flow.py](../e2e/deal_flow.py#L163)
- [ ] ❌ **Case on hold** (L779). There: a red chip only; every step still works, and the deal can close. [operations.py:195](../diwan/agents/operations.py#L195). Needed: holds.
- [x] 🧪 **Client told only "we need more information"** (L779). There: agents may never mention checks; Rania deflects and follow-ups are filtered, but no such wording is sent by anyone. [followup.py:16](../diwan/agents/followup.py#L16), test: [test_followup.py](../tests/test_followup.py) (no browser check).
- [x] ✅ **Compliance officer decides** (L779). Same as L215.
- [ ] ❌ **Continues, or blocked and closed by the officer** (L779). There: she can't resolve a match or close a deal. Needed: resolve and block actions.

### When things go wrong: payment from a third party (L780)

- [ ] ❌ **Detected by Finance at Mark received** (L780). Needed: a payer field; today a third party is seen only in words, earlier.
- [ ] ❌ **Compliance first** (L780). Same as L208.
- [ ] ❌ **Receipt held** (L780). Needed: a receipt that is sent at all, then a hold. Today the PDF exists at once.
- [ ] ❌ **Officer decides, Case continues** (L780). Needed: the above.

### When things go wrong: cheque bounced (L781)

- [ ] ❌ **Detected: landlord or person marks it** (L781). There: rent cheques can only be marked received, and that can't be undone. [finance.py:240](../diwan/agents/finance.py#L240). Needed: a Bounced action.
- [ ] ❌ **Tenant told within 24h** (L781). Needed: a draft and a timer.
- [ ] ❌ **Replacement deadline** (L781). Needed: a task.
- [ ] ❌ **Landlord informed** (L781). Needed: a draft.
- [ ] ❌ **Owner brief** (L781). Needed: a line.
- [ ] ❌ **Landlord decides: continues or legal route** (L781). Needed: the decision recorded.

### When things go wrong: commission not paid (L782)

- [ ] ❌ **Detected: invoice overdue** (L782). Needed: a due date, as L195. Unpaid shows, undated. [desk_kpis.py:126](../diwan/desk_kpis.py#L126)
- [ ] ❌ **Reminder ladder** (L782). Same as L197.
- [ ] ❌ **Owner brief** (L782). Same as L197.
- [ ] ❌ **Dispute log** (L782). Needed: a record.
- [ ] ❌ **Owner decides** (L782). Needed: a decision, including write-off.
- [ ] 🟡 **Stays open in Finance; Case otherwise closed** (L782). There: the collect task stays open, but the deal cannot close until the commission is received. [operations.py:194](../diwan/agents/operations.py#L194), test: [test_desk_rules.py](../tests/test_desk_rules.py#L167). See Conflicts.

### When things go wrong: co-broker dispute (L783)

- [ ] ❌ **Detected: either agency** (L783). Needed: a way to record it.
- [ ] 🟡 **Form I and the Event log as evidence** (L783). There: both are kept; nothing gathers them. [agency_forms.py:280](../diwan/agency_forms.py#L280). Needed: an evidence view.
- [ ] ❌ **Owners of both agencies decide** (L783). Needed: the decision recorded.
- [ ] ❌ **Finance holds the split** (L783). There: Finance can pay it at any time. [finance.py:191](../diwan/agents/finance.py#L191). Needed: a hold.

### When things go wrong: client complaint (L784)

- [ ] ❌ **Detected: any channel, words like "complaint", "unhappy", "lawyer"** (L784). There: none of these words appear anywhere in the code. Needed: detection in `reception.receive`.
- [ ] ❌ **Complaint record with quotes** (L784). Needed: a new record type.
- [ ] ❌ **Owner told the same day** (L784). Needed: a notice.
- [ ] ❌ **No agent reply beyond acknowledgement** (L784). There: Rania keeps replying. Needed: an acknowledgement, then a handover.
- [ ] ❌ **Owner decides; separate complaint record** (L784). Needed: as above.

### When things go wrong: wrong document uploaded and accepted (L785)

- [ ] 🟡 **Detected by Review or a person** (L785). There: the officer sees each document before accepting; nothing looks after acceptance. [documents.py:216](../diwan/documents.py#L216), test: [test_desk_rules.py](../tests/test_desk_rules.py#L714). Needed: Review, and a way to reopen.
- [ ] ❌ **Document voided with reason** (L785). There: Send back works only before it is accepted. Needed: a void after acceptance.
- [ ] 🟡 **Client asked again** (L785). There: yes after a send-back, through the same link. [documents.py:233](../diwan/documents.py#L233), test: [test_desk_rules.py](../tests/test_desk_rules.py#L714). Needed: the same after a void.
- [ ] ❌ **Dependent steps reopened** (L785). Needed: steps that depend on a document; tasks rest only on Facts.
- [x] 🧪 **A person decides; Case continues** (L785). There: the officer's check. [documents.py:218](../diwan/documents.py#L218), test: [test_desk_rules.py](../tests/test_desk_rules.py#L693) (browser check covers confirming only).

### When things go wrong: staff member leaves (L786)

- [ ] 🟡 **Owner deactivates the account** (L786). There: a function removes a login; no screen or route calls it for that, and people are a fixed list in code. [access.py:164](../diwan/access.py#L164). Needed: a Deactivate action, and people as records.
- [ ] 🟡 **Cases and Tasks reassigned in one step** (L786). There: leads move one at a time; role work follows the role. [leads.py:209](../diwan/leads.py#L209), test: [deal_flow.py](../e2e/deal_flow.py#L371). Needed: one step for all of a broker's deals and tasks.
- [ ] ❌ **Their PA's preferences archived, not deleted** (L786). Needed: an archive step.
- [ ] ❌ **Clients told who their new broker is** (L786). Needed: a draft per client.
- [ ] 🟡 **Owner decides; Case continues** (L786). There: roles are owner-only. [roles.py](../diwan/roles.py). Needed: the rest.

### When things go wrong: client asks to delete their data (L787)

- [ ] ❌ **Detected: client message** (L787). Needed: detection.
- [ ] ❌ **Request logged** (L787). Needed: an event.
- [ ] ❌ **Data deleted except what the law requires** (L787). There: the log refuses deletes outright. [events.py:62](../diwan/events.py#L62). See Conflicts.
- [ ] ❌ **Client told what was kept and why** (L787). Needed: a draft.
- [ ] ❌ **Owner and compliance officer decide; closed** (L787). Needed: the decision.

### When things go wrong: client asks to stop messages (L788)

- [ ] 🟡 **Detected: "stop" in any language** (L788). There: English and Arabic, and only when that's the whole message. [nudge.py:24](../diwan/agents/nudge.py#L24), test: [quiet_flow.py](../e2e/quiet_flow.py#L142). Needed: other languages the office uses, and stop inside a longer message.
- [ ] 🟡 **Stop all automated messages on all channels** (L788). There: follow-ups, appointment reminders and nurture stop, but document reminders still go out, and Rania answers again if they write. [documents.py:284](../diwan/documents.py#L284), test: [test_nudge.py](../tests/test_nudge.py#L94). Needed: an opt-out check inside `_send`.
- [x] 🧪 **Brokers may still reply if the client writes** (L788). There: a person is refused until they write again. [reception.py:610](../diwan/agents/reception.py#L610), test: [test_sales_journey.py](../tests/test_sales_journey.py#L62) (no browser check).
- [x] ✅ **Automatic** (L788). There: no person is involved. [reception.py:1168](../diwan/agents/reception.py#L1168), test: [quiet_flow.py](../e2e/quiet_flow.py#L142)
- [x] ✅ **Case continues without automation** (L788). There: the deal stays open; the profile shows why no follow-ups go. [nudge.py:155](../diwan/agents/nudge.py#L155), test: [quiet_flow.py](../e2e/quiet_flow.py#L142)

### When things go wrong: lost reasons (L790)

- [ ] ❌ **A dropdown of reasons** (L790). There: free text on the Deal desk and the Inbox. [deal.html:715](../web/deal.html#L715) and [inbox.html:596](../web/inbox.html#L596). Needed: a dropdown on both.
- [ ] ❌ **The list: price, finance refused, valuation, found elsewhere, changed mind, no response, compliance, seller withdrew, other** (L790). Needed: the list, in code.
- [ ] 🟡 **"Other" takes a note** (L790). There: every reason is a note; a Lost without one is refused. [desk_stages.py:69](../diwan/desk_stages.py#L69), test: [test_desk_rules.py](../tests/test_desk_rules.py#L425). Needed: a note only for Other.
- [ ] 🟡 **Records can count them** (L790). There: fall-through lists each reason's text, only for deals past paperwork; automatic losses store `reason`, which it doesn't read. [desk_kpis.py:42](../diwan/desk_kpis.py#L42), test: [test_desk_rules.py](../tests/test_desk_rules.py#L391). Needed: a count by reason for every lost deal.

<a id="part-f"></a>

## Part F: Marketing

Two notes that affect many lines:

- [e2e/studio_flow.py](../e2e/studio_flow.py) stops being valid after the upload step: line 57 looks for a button "Approve & publish", and the button is now "Approve for this time" ([studio.html:537](../web/studio.html#L537)). So the browser check covers run, three scripts, change, pick, film list and post text, and nothing from footage onward.

- No file in e2e/ covers moments, the first nine posts or event posts. [docs/marketing-journey.md:141](marketing-journey.md) says comments are "tagged with the post" ✅; the code does not do that (see Closing the loop).

### Marketing / Studio command (L584-596)

- [x] 🧪 **Topic typo: the code has the right name** (L590). There: no "Reality" anywhere in code; the post title is "Meet {name}" from the brand name. [journey.py:31](../diwan/agents/journey.py#L31), test: [test_journey.py:54](../tests/test_journey.py#L54) (pytest only)
- [ ] 🟡 **Topic typo: the data still has it** (L590). There: the typo is a typed brand name, not code: event 751 in data/try.db sets brand name "Diwan Realty", so the job title reads "Meet Diwan Realty". data/diwan.db has brand "Alphadroid". Needed: a new `setting.changed` brand name "Diwan Realty" in the demo data (the log is append-only), and the same in whichever office database is live.
- [x] 🧪 **Permit question unanswered counts as Yes** (L591). There: blank means needed, and the Setup dropdown says "Not answered yet (treated as yes)". [business.py:134](../diwan/business.py#L134), [studio.html:317](../web/studio.html#L317), test: [test_studio.py:847](../tests/test_studio.py#L847) (pytest only)
- [ ] 🟡 **Default Yes for UAE real estate specifically** (L591). There: the default is Yes for every business, but "No" is accepted for a UAE brokerage with no warning. [business.py:106](../diwan/business.py#L106). Needed: when country is AE and the industry is real estate, preselect Yes and warn or refuse on No; a test.
- [ ] ❓ **Permit rule confirmed with the office** (L591). Needs the office's answer: does every Dubai property post need a Trakheesi number, and which posts are exempt? Current default in code: every listing or product post needs one, topics and brand posts do not.
- [x] 🧪 **Listing with no permit: nothing is made** (L591). There: the run stops with a blocked step, and the planner skips such listings. [studio.py:1315](../diwan/agents/studio.py#L1315), [rhythm.py:122](../diwan/agents/rhythm.py#L122), test: [test_studio.py:58](../tests/test_studio.py#L58), [test_products.py:51](../tests/test_products.py#L51) (pytest only; [knowledge_flow.py:308](../e2e/knowledge_flow.py#L308) itself says "studio: code test only")
- [x] 🧪 **Permit number must be in the post text** (L591). There: Content writer adds it; Review check `post-permit` and the Permit checker both hold without it. [studio.py:1095](../diwan/agents/studio.py#L1095), [studio.py:1142](../diwan/agents/studio.py#L1142), [qa.py:156](../diwan/agents/qa.py#L156), test: [test_studio.py:40](../tests/test_studio.py#L40) (pytest only)
- [ ] 🟡 **Permit required at the moment of approval** (L591). There: checked once, before the publish request is raised. Not checked again in `approve_post`, `publish` or `publish_due`, so a permit removed afterwards does not stop the post. [studio.py:1202](../diwan/agents/studio.py#L1202), [studio.py:1246](../diwan/agents/studio.py#L1246). Needed: run the permit check inside `publish`; a test.
- [x] 🧪 **Code default for the website is empty** (L592). There: the website field starts blank, the placeholder is "yourcompany.com", and demo.py sets no website. [business.py:70](../diwan/business.py#L70), [studio.html:320](../web/studio.html#L320) (no test)
- [ ] 🟡 **Demo data has no real brokerage website** (L592). There: data/try.db event 553 sets website https://samplebrokerage-sc.com, and with it the sign-off "Sample Brokerage", the hashtags #Sample BrokerageSmartConcept and #Sample Brokerage, 56 listings read from that site, 5 services and knowledge cards K7 onward. Needed: replace those in the snapshot (or remove the snapshot's site-derived events by rebuilding it), and have `demo.seed` set a fictional business and brand so nobody needs to type one.
- [ ] ❓ **Which site replaces it** (L592). Needs the office's answer: the office's own site, or a fictional one? Current: [demo_profile.md:73](../diwan/demo_profile.md#L73) already uses the fictional domain diwan-realty.example.
- [ ] 🟡 **Scripts go through Review** (L593). There: each script is checked by the room lead against written rules (`qa.review`, events `qa.passed` / `qa.failed`) before a person sees it. It is not the independent Review team: studio.py never calls [review.py](../diwan/agents/review.py) or emits `review.passed`. [studio.py:1270](../diwan/agents/studio.py#L1270), [qa.py:204](../diwan/agents/qa.py#L204). Needed: a Review step that reads what is true now and records `review.passed`/`review.returned` for scripts, as drafts do; a test.
- [ ] 🟡 **Posts go through Review** (L593). There: post text, slides, cut and versions get the room-lead check, then the Permit checker. Gaps: `after_footage` writes the post text unchecked when none exists, the rewrites inside `permit_gate` are not reviewed, and the rewritten script there never returns to the person. [studio.py:1539](../diwan/agents/studio.py#L1539), [studio.py:1303](../diwan/agents/studio.py#L1303). Needed: every path goes through the same Review; a rewritten script is picked again.
- [x] 🧪 **Nothing reaches the person before the check** (L593). There: scripts are offered only after `reviewed`; three failures raise it to a person. [studio.py:948](../diwan/agents/studio.py#L948), [qa.py:236](../diwan/agents/qa.py#L236), test: [test_studio.py:468](../tests/test_studio.py#L468) (pytest only)
- [ ] 🟡 **A person's own script must pass too** (L593). There: it is checked and the page says "things to fix before it can be used", but "Use this one" stays active and the server accepts it. [studio.py:1367](../diwan/agents/studio.py#L1367), [studio.html:581](../web/studio.html#L581), [app.py:505](../diwan/app.py#L505), test: [test_studio.py:530](../tests/test_studio.py#L530). Needed: refuse the pick while problems are listed, or decide with the owner that a person may override.
- [ ] 🟡 **What happens after a failed review** (L593). There: the escalation offers "Fix it myself", "Accept as is", "Stop this reel", but those words appear only in [qa.py:240](../diwan/agents/qa.py#L240), so no code acts on the answer. Needed: a handler for each option; a test.
- [x] 🧪 **A script remembers the listing it was written from** (L594). There: price, permit, status, beds, features, title are saved on the script and compared with the listing now; covers listings, products and own scripts. [studio.py:871](../diwan/agents/studio.py#L871), [studio.py:886](../diwan/agents/studio.py#L886), test: [test_studio.py:521](../tests/test_studio.py#L521) (pytest only)
- [ ] 🟡 **The dependency covers the whole post** (L594). There: only the script holds that snapshot. Post text, cut, slides and the scheduled post hold none, and it is a copy of the listing, not a link to Facts; a listing that disappears returns "no change" ([studio.py:892](../diwan/agents/studio.py#L892)). Needed: each made item records what it rests on.
- [ ] 🟡 **Price or status change: the script is withdrawn** (L594). There: the pick card shows "Out of date" with a Rewrite button, but "Use this one" still works; nothing is withdrawn. A changed price in the caption is caught at the permit gate; spoken or on-screen words are not. [studio.html:583](../web/studio.html#L583), [studio.py:1144](../diwan/agents/studio.py#L1144). Needed: a listener on listing changes that withdraws open scripts for that ref and blocks the pick.
- [ ] ❌ **Change after approval stops the post** (L594). Needed: `publish` and `publish_due` check `stale` and the listing's status; today a scheduled post goes out at its time even if the listing sold or the price moved ([studio.py:1233](../diwan/agents/studio.py#L1233)).

### Studio rows of the bugs table (L373-375)

- [ ] 🟡 **Typo "Meet Diwan Realty"** (L373). There: same as L590: code is right, data/try.db is wrong. Needed: the data fix above.
- [ ] 🟡 **"Do our posts need a permit?" set to No** (L374). There: data/try.db event 501 set it to "no", so in that snapshot no permit is ever required. A blank answer already means Yes. Needed: set it to "yes" in the snapshot, plus the UAE rule above.
- [ ] ❓ **Check the permit rule with the office** (L374). Needs the office's answer: same question as L591.
- [ ] 🟡 **Website set to a real brokerage's site** (L375). There: data/try.db only; code and demo.py are clean. README says demo data is fictional ([README.md:71](../README.md#L71)). Needed: the data fix above.

### Marketing: the full lifecycle, purpose and agents (L1069)

- [x] ✅ **The named agents exist** (L1069). There: Marketing lead, Brand brain, and the Research, Planning, Copywriter (Scripting), Production, Art director (Editing) and Publisher rooms, shown on the Marketing floor. [charters.py:158](../diwan/agents/charters.py#L158), [charters.py:254](../diwan/agents/charters.py#L254), test: [test_studio.py:630](../tests/test_studio.py#L630), browser: [views_flow.py](../e2e/views_flow.py)
- [ ] 🟡 **Marketing lead is the Marketing PA** (L1069). There: a chat with the Marketing lead, by text or voice, answering from studio data. [lead_chat.py](../diwan/agents/lead_chat.py), test: [test_lead_chat.py](../tests/test_lead_chat.py). Needed: the PA's daily lists and duties (see the PA's day).
- [ ] ❌ **Every lead traced to what brought it** (L1069). Needed: see Closing the loop.
- [ ] ❌ **Records tells Marketing what turned into deals** (L1069). Needed: see Closing the loop.

### Content stages (L1071-1083)

- [ ] ❌ **One stage per piece of content** (L1071). Needed: a content item with a stage, rebuilt from events in graph.py. Today there is no content node; `chain()` works out 4 or 5 steps per listing ref on the fly, so a listing has one line of work at a time. [studio.py:1585](../diwan/agents/studio.py#L1585)
- [ ] ❌ **Only these stage names** (L1071). Needed: idea, briefed, scripted, in_production, ready, scheduled, live, paused, withdrawn, archived. Today's steps are "Pick a script", "Film it", "Editing", "Approve publishing".
- [x] 🧪 **idea: owner Planning** (L1075). There: Idea generator under the Strategist. [studio.py:626](../diwan/agents/studio.py#L626), test: [test_studio.py:399](../tests/test_studio.py#L399) (pytest only)
- [ ] ❌ **idea from a Lobby idea** (L1075). Needed: a route from the Lobby to the studio. The Lobby board has no marketing team ([lobby.py:21](../diwan/agents/lobby.py#L21)) and no experiment code exists.
- [ ] 🟡 **idea from a competitor signal** (L1075). There: pinned outliers and read patterns feed ideas and can rank topics, but only once a run starts for a listing. [studio.py:427](../diwan/agents/studio.py#L427), [rhythm.py:161](../diwan/agents/rhythm.py#L161). Needed: a strong outlier creates an idea by itself.
- [ ] ❌ **idea from a new listing** (L1075). Needed: `listing.live` starts an idea. The charter says "A new listing" ([charters.py:161](../diwan/agents/charters.py#L161)) but runs start only from the Run button, the chat, or the daily rhythm when turned on ([app.py:77](../diwan/app.py#L77), [app.py:205](../diwan/app.py#L205)).
- [ ] ❌ **idea from a price change** (L1075). Needed: a listener on the price field; nothing reacts to it.
- [x] 🧪 **idea from a topic the owner sets** (L1075). There: typed topics and moments; a moment goes first until its script is approved. [topics.py:97](../diwan/topics.py#L97), [topics.py:127](../diwan/topics.py#L127), [journey.py:185](../diwan/agents/journey.py#L185), test: [test_journey.py:142](../tests/test_journey.py#L142), [test_studio.py:827](../tests/test_studio.py#L827) (pytest only)
- [ ] ❌ **idea leaves on brief approved by the person** (L1075). Needed: a person step after the idea. Today the first idea is picked automatically and scripts start at once. [studio.py:651](../diwan/agents/studio.py#L651)
- [ ] ❌ **briefed: enters on brief approved** (L1076). Needed: a brief as its own item and approval card. The nearest thing is the job text passed to the writers, which no person sees. [journey.py:287](../diwan/agents/journey.py#L287)
- [ ] ❌ **briefed: leaves on script drafted** (L1076). Needed: comes with the brief step.
- [x] ✅ **scripted: three scripts** (L1077). There: three on different angles, from the strategy, the job or the topic angles. [studio.py:935](../diwan/agents/studio.py#L935), test: [test_journey.py:181](../tests/test_journey.py#L181), browser: [studio_flow.py:25](../e2e/studio_flow.py#L25)
- [x] 🧪 **scripted: each from its own Facts** (L1077). There: written from the listing, service or topic record and confirmed company facts; amounts and claims are checked against them. No line-by-line fact reference. [studio.py:831](../diwan/agents/studio.py#L831), [qa.py:121](../diwan/agents/qa.py#L121), test: [test_studio.py:399](../tests/test_studio.py#L399) (pytest only)
- [x] ✅ **scripted: person picks one** (L1077). There: a pick card, only for the person named in Setup or the owner. [studio.py:1344](../diwan/agents/studio.py#L1344), [app.py:489](../diwan/app.py#L489), test: [test_eventpost.py:317](../tests/test_eventpost.py#L317), browser: [studio_flow.py:45](../e2e/studio_flow.py#L45)
- [ ] 🟡 **scripted: leaves with Review passed** (L1077). There: the room-lead check, not Review, and a person's own failing script can still be picked (see L593).
- [x] ✅ **in_production: enters on script picked** (L1078). There: picking a script writes the film list and post text and sends the broker a task; nothing costly starts before. [studio.py:1422](../diwan/agents/studio.py#L1422), test: [test_studio.py:40](../tests/test_studio.py#L40), browser: [studio_flow.py:46](../e2e/studio_flow.py#L46)
- [x] 🧪 **in_production: owner Production and Editing** (L1078). There: Producer, Shoot coordinator, AI video, Art director, Captions rooms. [charters.py:206](../diwan/agents/charters.py#L206) (pytest only)
- [x] 🧪 **in_production: video** (L1078). There: uploaded footage, a HeyGen presenter with recorded consent, a free computer-voice video on Windows or Mac; a real image path for event posts. Take is compared with the script. [studio.py:954](../diwan/agents/studio.py#L954), [studio.py:1545](../diwan/agents/studio.py#L1545), test: [test_studio.py:349](../tests/test_studio.py#L349), [test_studio.py:429](../tests/test_studio.py#L429), [test_studio.py:611](../tests/test_studio.py#L611) (pytest only; the browser branch is out of date, see note above)
- [x] 🧪 **in_production: captions** (L1078). There: burned in with ffmpeg from what was said, or the script if nothing can transcribe. [studio.py:1035](../diwan/agents/studio.py#L1035), test: [test_studio.py:417](../tests/test_studio.py#L417) (pytest only)
- [ ] 🟡 **in_production: cover** (L1078). There: two cover options from our own footage are shown. Nobody picks one, and `publish_reel` sends no cover to Instagram, so neither is used. [studio.py:1109](../diwan/agents/studio.py#L1109), [instagram.py:123](../diwan/providers/instagram.py#L123). Needed: pick a cover; send it with the reel; a test.
- [ ] 🟡 **in_production: permit number on screen** (L1078). There: the plan calls for a price card with the permit "added in editing", but no editing step adds one: `captions` only burns speech, and event images draw no permit. It appears only if the words were spoken. [studio.py:688](../diwan/agents/studio.py#L688), [studio.py:1035](../diwan/agents/studio.py#L1035), [eventpost.py:262](../diwan/agents/eventpost.py#L262). Needed: burn a price and permit card on the cut and images, and a check for it.
- [x] 🧪 **in_production: permit number in the caption** (L1078). There: added to the post text and checked. [studio.py:1095](../diwan/agents/studio.py#L1095), test: [test_studio.py:40](../tests/test_studio.py#L40) (pytest only)
- [ ] 🟡 **ready: needs the final cut** (L1079). There: approval is refused without a cut, but the request is still raised, with "(no cut yet: footage needed)". [studio.py:1189](../diwan/agents/studio.py#L1189), [studio.py:1194](../diwan/agents/studio.py#L1194), test: [test_eventpost.py:184](../tests/test_eventpost.py#L184). Needed: no ready state without a cut.
- [ ] 🟡 **ready: needs Review passed** (L1079). There: the permit gate and room-lead checks, not Review (see L593).
- [ ] ❌ **ready: needs a valid permit** (L1079). Needed: permit expiry on the listing and a date check. Today only "a number is there"; no listing has an expiry field.
- [x] 🧪 **ready: owner Publishing** (L1079). There: Publisher asks; one open request per listing. [studio.py:1184](../diwan/agents/studio.py#L1184), test: [test_eventpost.py:95](../tests/test_eventpost.py#L95) (pytest only)
- [ ] 🟡 **ready: person approves the post and its time** (L1079). There: "Approve for this time" or "Post now"; the time comes from the Scheduler and cannot be changed, and one slot is shared by every post. [studio.html:536](../web/studio.html#L536), [studio.py:1207](../diwan/agents/studio.py#L1207), test: [test_eventpost.py:282](../tests/test_eventpost.py#L282). Needed: the person sets the time; a slot per post.
- [x] 🧪 **scheduled: enters on approved** (L1080). There: the post waits for its time; Cancel stops it; a failure is said once. [studio.py:1202](../diwan/agents/studio.py#L1202), [studio.py:1233](../diwan/agents/studio.py#L1233), test: [test_eventpost.py:282](../tests/test_eventpost.py#L282), [test_eventpost.py:294](../tests/test_eventpost.py#L294), [test_eventpost.py:301](../tests/test_eventpost.py#L301) (pytest only)
- [ ] ❌ **scheduled: posted by a person** (L1080). Needed: a "Mark as posted" action with the link. Without Instagram connected, approval only lists what is missing. TikTok, YouTube Shorts and Property Finder versions are written but never go anywhere. [studio.py:1198](../diwan/agents/studio.py#L1198)
- [ ] 🟡 **scheduled: auto-post only if the owner switched it on** (L1080). There: approving always auto-posts at the time (when Instagram is connected); no such setting exists. The "Automatic" setting covers runs, not posting. [app.py:79](../diwan/app.py#L79), [rhythm.py:22](../diwan/agents/rhythm.py#L22). Needed: an owner setting, off by default. See Conflicts.
- [x] 🧪 **live: enters on posted** (L1081). There: reels, images and carousels publish through Instagram and record `content.made` kind published. Real posting is unverified: [sessions.md](sessions.md) line 82 says publishing is off. [studio.py:1246](../diwan/agents/studio.py#L1246), test: [test_studio.py:349](../tests/test_studio.py#L349), [test_eventpost.py:169](../tests/test_eventpost.py#L169) (pytest only)
- [ ] ❌ **live: leaves on paused, withdrawn or archived** (L1081). Needed: those states, and a way to act on a post already out; [instagram.py](../diwan/providers/instagram.py) has no call to hide or delete one, so it may need to be a task for a person.
- [ ] ❌ **paused: on permit expired** (L1082). Needed: expiry dates, a daily sweep, `post.paused` with the reason.
- [ ] ❌ **paused: on listing unconfirmed** (L1082). Needed: a listener on `listing.unconfirmed`. Off-market status exists; nothing in Marketing reacts.
- [ ] ❌ **paused: on price changed** (L1082). Needed: a listener on the price; pause every post that used the old one.
- [ ] ❌ **paused: fixed, back to ready** (L1082). Needed: a route back through Review. Today `unschedule` only cancels a waiting post, and it does not return to ready. [studio.py:1228](../diwan/agents/studio.py#L1228)
- [ ] ❌ **paused: leaves to withdrawn** (L1082). Needed: a withdraw action with a reason.
- [ ] ❌ **withdrawn/archived: on listing sold** (L1083). Needed: a listener on the status. The planner skips sold listings, but posts already scheduled or live are untouched. [rhythm.py:122](../diwan/agents/rhythm.py#L122)
- [ ] ❌ **withdrawn/archived: on Fact superseded** (L1083). Needed: a link from posts to Facts, and a consumer of `fact.superseded`.
- [ ] ❌ **withdrawn/archived: on campaign ended** (L1083). Needed: campaigns first.
- [ ] ❌ **withdrawn/archived is final** (L1083). Needed: comes with the stage record.
- [ ] 🟡 **Only live listings get content** (L1075, L1083). There: the planner drops sold, let, withdrawn and retired, but not reserved or off-market, and a person's Run has no status check at all, although [knowledge.py:88](../diwan/knowledge.py#L88) already defines "advertised" as available with a permit. [rhythm.py:122](../diwan/agents/rhythm.py#L122), [studio.py:1310](../diwan/agents/studio.py#L1310). Needed: use `advertised` in both.

### Events for Marketing (L1085)

- [ ] 🟡 **`content.idea` emitted** (L1085). There: `content.made` kind "ideas". [studio.py:652](../diwan/agents/studio.py#L652). Needed: the catalog name, carrying the source.
- [ ] ❌ **`content.briefed` emitted** (L1085). Needed: the brief step.
- [ ] 🟡 **`content.scripted` emitted** (L1085). There: `content.made` kind "script". [studio.py:871](../diwan/agents/studio.py#L871). Needed: the catalog name.
- [ ] 🟡 **`content.ready` emitted** (L1085). There: nearest is `approval.requested` kind publish. [studio.py:1190](../diwan/agents/studio.py#L1190). Needed: the catalog name, once cut, Review and permit all hold.
- [ ] 🟡 **`post.approved` emitted** (L1085). There: `decision.made` plus `content.made` kind "scheduled". [studio.py:1210](../diwan/agents/studio.py#L1210). Needed: the catalog name.
- [ ] 🟡 **`post.live` emitted** (L1085). There: `content.made` kind "published". [studio.py:1263](../diwan/agents/studio.py#L1263). Needed: the catalog name, with listing ref, angle and post link.
- [ ] ❌ **`post.paused` emitted** (L1085). Needed: event and handler.
- [ ] ❌ **`post.withdrawn` emitted** (L1085). Needed: event and handler; `content.made` kind "unscheduled" means only "cancelled before going out".
- [ ] ❌ **`campaign.started` emitted** (L1085). Needed: campaigns.
- [ ] ❌ **`campaign.ended` emitted** (L1085). Needed: campaigns.
- [ ] ❌ **`lead.attributed` emitted** (L1085). Needed: event, graph handler, a field on the Case.
- [ ] ❌ **Consumes `listing.live`** (L1085). Needed: the code has `listing.added`, which also carries every later edit, and Marketing does not listen to it.
- [ ] ❌ **Consumes `fact.superseded`** (L1085). Needed: the event exists for deal facts ([office.py:104](../diwan/office.py#L104)); a listing's price is not a Fact and the studio does not read it.
- [ ] ❌ **Consumes `permit.expired`** (L1085). Needed: event and sweep; neither exists.
- [ ] ❌ **Consumes `listing.withdrawn`** (L1085). Needed: event and consumer; a status on `listing.added` is the nearest.
- [ ] ❌ **Consumes `listing.unconfirmed`** (L1085). Needed: event and consumer.
- [ ] ❌ **Consumes `experiment.approved`** (L1085). Needed: the word "experiment" appears nowhere in diwan/ or web/.

### Closing the loop with Sales and Records (L1087-1093)

- [ ] ❌ **Tracked link on every post** (L1089). Needed: a link per post in the caption, and a redirect endpoint. Post text has only the sign-off. [studio.py:1098](../diwan/agents/studio.py#L1098)
- [ ] ❌ **Tracked link on every ad** (L1089). Needed: ads are not made here.
- [ ] ❌ **Tracked link on every portal listing** (L1089). Needed: a per-listing link or code. Portal enquiries already name the listing (see below).
- [ ] ❌ **Code word ("reply MARINA")** (L1089). Needed: a code per post, in the caption, recognised by Rania in `reception`.
- [ ] 🟡 **Lead from a comment names the post** (L1090). There: a comment opens a chat on channel instagram, but `parse_comments` reads `media_id` and the webhook drops it, so which post is lost. [instagram.py:168](../diwan/providers/instagram.py#L168), [app.py:541](../diwan/app.py#L541), [reception.py:1134](../diwan/agents/reception.py#L1134). Needed: pass the media id through and match it to the published post. [marketing-journey.md:141](marketing-journey.md) is wrong on this.
- [ ] ❌ **Lead from a DM** (L1090). Needed: Instagram messaging webhook; only the `comments` field is read. [instagram.py:161](../diwan/providers/instagram.py#L161)
- [ ] ❌ **Lead from a link** (L1090). Needed: the tracked link.
- [ ] ❌ **Lead from a code word** (L1090). Needed: the code word.
- [ ] 🟡 **Lead from a portal listing** (L1090). There: the enquiry keeps its portal and listing ref, and the Inbox shows the channel. [leads.py:420](../diwan/leads.py#L420), [inbox.py:94](../diwan/inbox.py#L94), test: [test_leads.py:176](../tests/test_leads.py#L176). Needed: record it as `lead.attributed`.
- [ ] ❌ **Sales records `lead.attributed` on the Case** (L1090). Needed: event, a source on the deal shown in the lead profile and the Case, and a manual way to set it.
- [x] 🧪 **Comments go straight to Sales** (L1091). There: every comment becomes a chat with Rania, and her reply goes back as a comment. `chat.received` is the code's `message.received`. [app.py:539](../diwan/app.py#L539), test: [test_studio.py:371](../tests/test_studio.py#L371) (pytest only; 🔑 not tried on real comments)
- [ ] 🟡 **Only buying questions go to Sales** (L1091). There: no filter: a "nice!" comment opens a chat too. Needed: sort comments first; decide what happens to the rest.
- [ ] ❌ **DMs go straight to Sales** (L1091). Needed: as above.
- [x] 🧪 **Marketing doesn't answer them** (L1091). There: the Marketing lead's instructions send leads and WhatsApp to Sales. [lead_chat.py:115](../diwan/agents/lead_chat.py#L115) (no test of this rule)
- [ ] 🟡 **Records: reach per post** (L1092). There: our own posts carry reach, views, likes and comments in the studio; none reach Records, which knows sales, invoices and documents only. [instagram.py:90](../diwan/providers/instagram.py#L90), [records.py:63](../diwan/agents/records.py#L63). Needed: a per-post report in Records.
- [ ] ❌ **Records: leads per post** (L1092). Needed: attribution, then a count.
- [ ] ❌ **Records: qualified leads per post** (L1092). Needed: same.
- [ ] ❌ **Records: viewings per post** (L1092). Needed: same.
- [ ] ❌ **Records: deals per post** (L1092). Needed: same; `sale.closed` has no source.
- [ ] ❌ **Records: commission per post** (L1092). Needed: same.
- [ ] 🟡 **Records: spend** (L1092). There: spend per ad is read live in the Studio, not stored or tied to a post. [ads.py:58](../diwan/providers/ads.py#L58). Needed: stored spend per ad, linked to the post and to Records.
- [ ] ❌ **Records: the same per campaign** (L1092). Needed: campaigns.
- [ ] ❌ **Weekly: what brought deals, not only views** (L1093). Needed: a weekly message from the Marketing PA. The strategy ranks angles only by likes and comments ([strategy.py:82](../diwan/agents/strategy.py#L82)).
- [ ] ❌ **The Lobby turns that into the next experiment** (L1093). Needed: Lobby experiments.

### Campaigns and spend (L1095-1099)

- [ ] ❌ **Campaign record: goal, audience, budget, dates, content** (L1097). Needed: `campaign.*` events, a graph node, a page in the Studio. The word does not appear in diwan/.
- [ ] ❌ **Spend is a setting with a hard cap** (L1097). Needed: a setting per campaign or month. [costs.py](../diwan/costs.py) caps model costs only.
- [ ] ❌ **Agents may draft ads and audiences** (L1098). Needed: an ad draft agent; the studio only pins competitors' ads by hand.
- [x] 🧪 **A person launches and pays** (L1098). There: true by absence: the ads provider only reads and has no call that creates, changes or pauses an ad. [ads.py:1](../diwan/providers/ads.py#L1), test: [test_ads.py:7](../tests/test_ads.py#L7) (pytest only)
- [x] 🧪 **Read our own ad results** (L1097). There: spend, reach, clicks, leads per ad, last 30 days, in the Studio and the chat. Not stored. [brand_api.py:188](../diwan/brand_api.py#L188), [studio.html:932](../web/studio.html#L932), test: [test_ads.py:7](../tests/test_ads.py#L7) (pytest only)
- [ ] ❌ **Cost per qualified lead over the limit is flagged in the brief** (L1099). Needed: an owner limit, qualified leads per campaign, a line in the brief. Marketing is not in Nova's rounds at all ([nova.py:488](../diwan/agents/nova.py#L488)).

### Rules that make it safe (L1101-1107)

- [ ] 🟡 **No post live without a permit number** (L1103). There: enforced before the request, not at posting, and off entirely if Setup says No (see L591). [studio.py:1141](../diwan/agents/studio.py#L1141)
- [ ] ❌ **The permit must be valid** (L1103). Needed: expiry date on the listing, checked at ready and at posting.
- [ ] ❓ **Which posts count** (L1103). Needs the office's answer: do topic, brand and project posts need a permit? Current default: no. A knowledge "project" card (with a payment plan, and fields for price and permit, [knowledge.py:33](../diwan/knowledge.py#L33)) posts as a topic with no permit check, even as a "moment". [studio.py:1141](../diwan/agents/studio.py#L1141), [journey.py:194](../diwan/agents/journey.py#L194)
- [ ] ❓ **Confirm the rule with the office** (L1103). Needs the office's answer: same question as L591.
- [ ] 🟡 **No post live without Review passed** (L1103). There: room-lead checks only, and the gaps listed at L593.
- [x] 🧪 **No post live without a person's approval** (L1103). There: the only roads to `publish` are a person's decision and a time they approved; only the named person or owner may approve. [app.py:489](../diwan/app.py#L489), [app.py:517](../diwan/app.py#L517), test: [test_eventpost.py:317](../tests/test_eventpost.py#L317) (pytest only)
- [x] 🧪 **Every price comes from the listing** (L1104). There: any amount not the listing's price is sent back in the script and held in the post; a model's stray amount falls back to the template. [qa.py:121](../diwan/agents/qa.py#L121), [studio.py:1144](../diwan/agents/studio.py#L1144), [studio.py:859](../diwan/agents/studio.py#L859), test: [test_products.py:45](../tests/test_products.py#L45), [test_studio.py:481](../tests/test_studio.py#L481) (pytest only)
- [ ] ❌ **Every size comes from a Fact** (L1104). Needed: a check like amounts, for sq ft and bedrooms. `MONEY` and `CLAIM` skip them. [studio.py:752](../diwan/agents/studio.py#L752), [qa.py:77](../diwan/agents/qa.py#L77)
- [x] 🧪 **Claims about us come from confirmed facts** (L1104). There: a track-record number not in the listing, brand or confirmed cards goes back; so does an invented memory on a topic post. [qa.py:89](../diwan/agents/qa.py#L89), [qa.py:84](../diwan/agents/qa.py#L84), test: [test_journey.py:173](../tests/test_journey.py#L173), [test_eventpost.py:361](../tests/test_eventpost.py#L361) (pytest only)
- [ ] 🟡 **From a current Fact** (L1104). There: checks read the listing as it is now, at check time only, and the listing is a record, not a Fact with a superseded history. Needed: decide whether listing fields become Facts; re-check at posting.
- [ ] ❌ **A superseded Fact pauses the post** (L1104). Needed: see `post.paused`.
- [ ] 🟡 **No promise of returns; Review rejects** (L1105). There: `BANNED` catches "guaranteed", "risk-free", "assured returns", "best investment", plus the brand's own never-claim list. Tried on the regex: "8% return" and "ROI of 8%" pass. [qa.py:21](../diwan/agents/qa.py#L21), [qa.py:142](../diwan/agents/qa.py#L142), [studio.py:55](../diwan/agents/studio.py#L55). Needed: a wider rule; a test of each phrase.
- [ ] ❌ **No promise of visas; Review rejects** (L1105). Needed: add visas. "golden visa" and "visa included" pass today.
- [ ] 🟡 **No promise of price rises; Review rejects** (L1105). There: only "will double" and "will rise". Needed: a wider rule, in English and Arabic; `BANNED` tests English words only.
- [x] 🧪 **Competitor content is studied** (L1106). There: scores, reads, patterns; writers get why a post worked, "never their words, numbers, awards". Their own moments are left out. [studio.py:842](../diwan/agents/studio.py#L842), [studio.py:583](../diwan/agents/studio.py#L583), [analysis.py](../diwan/agents/analysis.py), test: [test_studio.py:499](../tests/test_studio.py#L499) (pytest only)
- [ ] 🟡 **Competitor content is never copied** (L1106). There: an instruction to the model only. `too_close` compares with our own scripts, not theirs. [style.py:95](../diwan/agents/style.py#L95). Needed: a check of each script against the competitor text and transcript it built on.
- [ ] ❌ **Music must be licensed or the office's own** (L1106). Needed: a record of the audio's source. The studio does not handle music; a take arrives with whatever audio it has.
- [ ] 🟡 **Footage must be licensed or the office's own** (L1106). There: covers are our own frames, AI presenters need recorded consent, people in photos are flagged, a generated background is abstract only. Footage and photo uploads ask nothing about rights. [app.py:424](../diwan/app.py#L424), [studio.py:1551](../diwan/agents/studio.py#L1551), test: [test_eventpost.py:141](../tests/test_eventpost.py#L141), [test_studio.py:429](../tests/test_studio.py#L429). Needed: a rights answer at upload.
- [x] 🧪 **Seeded demo people and companies are fictional** (L1107). There: demo.py, demo_feed.xml and demo_profile.md use made-up names and sample permits. [demo.py:1](../diwan/demo.py#L1), [demo_profile.md:3](../diwan/demo_profile.md#L3) (no test)
- [ ] 🟡 **Demo snapshots are fictional** (L1107). There: data/try.db carries Sample Brokerage data and real competitors (@competitor_two, @competitor_one, @competitor_three, @rivalhomesandrivalhomes), and data/diwan.db carries brand "Alphadroid" and real accounts' posts. Both are in git. Needed: rebuild them from fictional data; a test that scans for them.
- [ ] ❓ **Real suppliers in the demo archive** (L1107). Needs the office's answer: is it fine that demo invoices name Property Finder, DEWA and du? [demo.py:39](../diwan/demo.py#L39)

### Marketing PA's day (L1109)

- [ ] 🟡 **Morning: posts to approve** (L1109). There: the Run tab shows waiting cards for the open listing. Nothing is sent in the morning, and Maya has no team in Nova's brief. [app.py:230](../diwan/app.py#L230), [nova.py:556](../diwan/agents/nova.py#L556). Needed: Marketing in the rounds, and an across-all-listings list.
- [ ] ❌ **Morning: listings without content** (L1109). Needed: a list of advertised listings with no script or post. The planner uses "not used yet" to pick, and shows no such list. [rhythm.py:125](../diwan/agents/rhythm.py#L125)
- [ ] 🟡 **Morning: competitor posts worth a look** (L1109). There: the daily refresh records new winners and the Competitors tab shows them, if turned on (off by default). Not in a morning list. [studio.py:515](../diwan/agents/studio.py#L515), [rhythm.py:294](../diwan/agents/rhythm.py#L294), test: [test_studio.py:782](../tests/test_studio.py#L782). Needed: put them in the list.
- [ ] ❌ **Morning: yesterday's leads by source** (L1109). Needed: attribution.
- [ ] ❌ **During the day: drafts briefs on request** (L1109). Needed: the brief step.
- [x] 🧪 **During the day: drafts scripts on request** (L1109). There: in chat it proposes a run or a rewrite and does it after a yes. [lead_chat.py:181](../diwan/agents/lead_chat.py#L181), test: [test_lead_chat.py:46](../tests/test_lead_chat.py#L46) (pytest only)
- [ ] ❌ **End of day: tomorrow's schedule** (L1109). Needed: a list from `scheduled()`, which exists but shows only one listing at a time on the page. [studio.py:1216](../diwan/agents/studio.py#L1216)
- [ ] ❌ **End of day: anything paused, with the reason** (L1109). Needed: the paused stage.

### Marketing definition of done (L1111)

- [ ] ❌ **A post's leads appear on the right Cases with their source** (L1111). Needed: tracked links or codes, the media id kept, `lead.attributed`. Not one post can name its leads today.
- [ ] ❌ **A price change pauses every post with the old price within minutes** (L1111). Needed: posts linked to listings, a listener, `post.paused`, a test. Today: a warning on the pick card only.
- [ ] ❌ **A permit expiry pauses every post for that unit** (L1111). Needed: expiry data, the sweep, `post.paused`, a test.
- [ ] ❌ **Records shows deals and commission per post** (L1111). Needed: attribution carried from lead to deal to `sale.closed`, then a Records report.

## All conflicts found

Places where the spec disagrees with itself or with something the code does on purpose. Duplicates across the parts are merged, and nothing here is resolved. The decisions to take are D1 to D52 in [the working checklist](closed-loop-checklist.md#decisions-needed-before-building).

- **Task reopened or withdrawn.** Spec L25 and L958 say Tasks reopen and `task.reopened`. Code deliberately withdraws them and makes new ones ([office.py:108](../diwan/office.py#L108), its header says "withdrawn"). *(Part A)*
- **Compliance told first on what.** Spec L25 says every superseded Fact. Code limits it to money facts ([compliance.py:22](../diwan/agents/compliance.py#L22), citing rooms.md rule 8). *(Part A)*
- **Fixed stage list or owner-edited stages.** Spec L891 says any other stage name is a bug. Code deliberately makes stages after Viewed the owner's setting ([desk_rules.py:163](../diwan/desk_rules.py#L163), [deal.html:295](../web/deal.html#L295)). *(Part A)*
- **Who moves a stage.** Spec L14 says the owner room only, L24 says a human approves. Code lets the broker, transactions officer and owner move any stage ([desk_stages.py:28](../diwan/desk_stages.py#L28)) and Rania move early ones ([inbox.py:252](../diwan/inbox.py#L252)). *(Part A)*
- **A single owner room.** Spec L14 says single; L913 gives `transferred` to "Finance + Ops". *(Part A)*
- **Closed never reopened.** Spec L944 says never. Code lets a Lost deal return with a reason, and re-reserves its listing ([desk_stages.py:71](../diwan/desk_stages.py#L71)). *(Part A)*
- **Quiet hours for clients.** Spec L309 says always. The charter deliberately has Rania answering "day and night" ([charters.py:56](../diwan/agents/charters.py#L56)). A reply to a message the client just sent may be meant as an exception. *(Part A)*
- **The stop rule on replies.** Same area: Rule 6 (L1002) permits messages inside 24 hours, while "stop" (L13) has no stated exception. Code lets a person answer if the client writes again ([test_sales_journey.py](../tests/test_sales_journey.py)). *(Part A)*
- **Call-now limit.** Spec L819 says default 10 minutes. Code and the Settings text say 15 ([leads.py:32](../diwan/leads.py#L32), [settings.html:131](../web/settings.html#L131)). *(Part A)*
- **Number of rooms.** Spec L9 and L36 say nine rooms. L1138 lists ten departments (Marketing added). The floor has eight plus a meeting room ([office3d.html:129](../web/office3d.html#L129)). *(Part A)*
- **What "Lobby" means.** Spec L38 and L1149 make it the improvement room. Code's Lobby board is requests between people ([lobby.py:1](../diwan/agents/lobby.py#L1)). Same word, two things. *(Part A)*
- **`lead.attributed`.** Used at L1119 and L1141, not in the catalog at L946, which says no other names are allowed. *(Part A)*
- **`converted` as a stage.** L902 and L1142 name it, and L1142 names `lost`. Neither is in the allowed list; `closed_lost` is. L898 and L1142 also treat `nurture` as a stage, while L891 calls it a side state. *(Part A)*
- **Snagging.** L922 needs "snagging done" to close off-plan. L1032 puts snagging in Phase 2. *(Part A)*
- **Retention and an unchangeable log.** Spec L822 and L1148 want deletion by retention period. Code's log refuses every delete ([events.py:62](../diwan/events.py#L62)), by design. *(Part A)*
- **Who sees what on a deal.** Spec L316 and L968 keep Finance to money and hits to the officer. Code deliberately shares one Deal desk across Sales, Operations, Finance and Compliance ([access.py:40](../diwan/access.py#L40)). *(Part A)*
- **Who reviews uploads.** Spec L842 says Review. Code gives the check to the compliance officer ([documents.py:210](../diwan/documents.py#L210)). *(Part A)*
- **Staff PAs against the gate.** Spec L387 and L449 give every person a PA. [access.py:1](../diwan/access.py#L1) says "a person sees only their department", and [test_access.py:112](../tests/test_access.py#L112) (`test_only_the_owner_reads_the_logs_nova_and_settings`) asserts Omar gets 403 on `/api/nova/say`. *(Part B)*
- **Sales read for Compliance and Ops.** Spec L409 and L411 say "Read". [test_access.py:80](../tests/test_access.py#L80) asserts Priya gets 403 on `/api/chats`. *(Part B)*
- **Department access against row and field access.** The table (L407-412) wants own leads, amounts only, status only. [access.py:49](../diwan/access.py#L49) grants whole prefixes, and `DEAL_TEAM` deliberately shares one desk. *(Part B)*
- **Sharing leads.** Spec L394 says never another broker's clients. The Pool deliberately shows and offers a late lead to every broker on shift ([leads.py:183](../diwan/leads.py#L183)), and the Inbox opens on "all" ([inbox.html:226](../web/inbox.html#L226)). *(Part B)*
- **Marketing has no row or column.** The table (L404-411) has six roles and nine rooms, none Marketing. L805 and L1064 give a Marketing person a day and a PA; [access.py:38](../diwan/access.py#L38) has an `mkt` department and a `Marketing manager` in [people.py:12](../diwan/people.py#L12). What may Maya see of Front Desk and Records? "Nine rooms" at L9 does not count Marketing either. *(Part B)*
- **Brief time.** Spec L55 says 7:30 for the owner, L1045 says the person's start time. The code default is 09:00 with rounds at 08:30 ([nova.py:558](../diwan/agents/nova.py#L558)); Nova's charter says "07:00 daily" ([charters.py:38](../diwan/agents/charters.py#L38)); `test_nova.py` says seven; a comment says "the 07:00 run" ([app.py:764](../diwan/app.py#L764)). *(Part B)*
- **Brief length.** L48 says lead with the top 3; L1045 says max 5 before "more"; L57-62 lists six sections. *(Part B)*
- **Settings by voice.** L1051 says no PA changes Settings. L400 and L1044 make preferences "settings" the person can edit. The code lets Nova set the briefing time and change an agent's autonomy by talk ([nova.py:185](../diwan/agents/nova.py#L185), [nova.py:194](../diwan/agents/nova.py#L194)). *(Part B)*
- **Sends without asking.** L1048 says ask before anything a client or outsider will see. L1060 has the coordinator's PA send the ladder unasked; L1061 reminds clients unasked; L1062 lists installment reminders as unasked and "sending reminders" as ask-first in one row. The code sends the documents ladder by itself ([documents.py:284](../diwan/documents.py#L284)). *(Part B)*
- **Consent against Pocket mode.** L50 says Nova goes silent and transcribes on a wake phrase. The code hears nothing until the client agrees ([office.py:60](../diwan/office.py#L60), [test_scribe.py](../tests/test_scribe.py#L23)), and L603 agrees with the code for online meetings. L50 does not mention consent. *(Part B)*
- **Ask's sources.** L51 includes the web. L446 lists Records, calendar and Event log. Nova's charter says "The office's own records only". *(Part B)*
- **Do not disturb words.** L53 says "items the owner marked urgent". L448 says "items marked Now". *(Part B)*
- **Escalation chain.** L399 fixes it (person, lead's PA, Nova). L1050 says it comes from Settings. The code goes person and owner at once ([leads.py:190](../diwan/leads.py#L190)). *(Part B)*
- **"Sales lead" means two things.** Spec: the broker-facing PA serving a person (L87, L1059). Code: an agent that "Owns what comes out of meetings" ([charters.py:45](../diwan/agents/charters.py#L45)); the person is Rashid, "Sales manager". *(Part B)*
- **One chair or two.** L801-802 and L1060-1061 treat Deal coordinator and Operations as two people with two PAs; L409 has one "Deal / Ops staff" row. The code has one Transactions officer, Joseph ([people.py:10](../diwan/people.py#L10)). `roles.py` has no coordinator role. *(Part B)*
- **Event names.** Spec uses `fact.recorded` (L76) and `approval.declined` (L77). The code has `fact.created`, and `approval.refused` means something else. *(Part B)*
- **Nova for the owner against Nova for all.** L42 and L449 say Nova is the owner's only. The code's `brief()` and rounds serve every person under the name Nova, and `morning()` iterates all of `PEOPLE`. *(Part B)*
- **Who takes an escalated lead.** The spec: the next free broker, automatically (L112). The code: any broker on shift claims it from the Pool, deliberately ([leads.py:10](../diwan/leads.py#L10)). *(Part C)*
- **Portal leads and Rania.** The spec has Rania start from the listing and ask what's missing (L95). The code keeps her silent unless the owner picks a template, and gives the broker a call card, because WhatsApp requires it ([leads.py:400](../diwan/leads.py#L400)). *(Part C)*
- **Who the client hears about.** The spec: one name throughout (L368). The code sends a site visit to the listing's agent, who has the keys, even when another broker owns the lead ([reception.py:743](../diwan/agents/reception.py#L743)). *(Part C)*
- **Convert needs a price.** The spec: `converted` is "offer accepted or client commits" (L120). The code refuses to convert without an agreed price, and a big discount waits for the owner ([desk_stages.py:115](../diwan/desk_stages.py#L115)). *(Part C)*
- **New listings to waiting buyers.** Case 3 (L856) says Rania sends only with the broker's yes. The quiet-clients work has her send a newly fitting listing by herself ([nudge.py:231](../diwan/agents/nudge.py#L231)), and L116 allows follow-ups on the owner's schedule. *(Part C)*
- **Merging by name.** Case 1 (L854) proposes merges and never merges automatically across brokers. The code deliberately joins a WhatsApp from a known customer's name to their one open deal ([reception.py:499](../diwan/agents/reception.py#L499), [test_inbox.py](../tests/test_inbox.py)). *(Part C)*
- **Fact or `qualify.answer`.** L103 says each answer is a Fact; L859 says the same for feedback. The code keeps both as their own events, and only the Scribe makes `fact.created`. Rania's prompt and the Inbox read them separately. *(Part C)*
- **Where Rania sits.** The spec puts her in Sales (L87, L458). The charter agrees, but the floor shows her at the Front desk ([office3d.html:130](../web/office3d.html#L130)). *(Part C)*
- **Step reference.** L124 points to "Outcomes (step 9)", but the numbered PA list ends at 5 (L112-116). *(Part C)*
- **Reading documents.** Spec L158 and L688 want the document read at upload. [documents.py:8](../diwan/documents.py#L8) deliberately has the client type the details and a person compare them until the owner approves a vision provider. *(Part D)*
- **Who sends links.** Spec L146 has the Deal manager send on WhatsApp. [signing.py:3](../diwan/signing.py#L3) and [deal.html:805](../web/deal.html#L805) say the broker shares them personally, approved in docs/deal-desk.md item 13. *(Part D)*
- **Who sends forms.** Spec L146 gives this to Deal; L176 gives it to Operations. *(Part D)*
- **One link or two.** Spec L147 is one page; the code has a signing link per form per person and one documents link per party, by design ([signing.py:1](../diwan/signing.py#L1)). *(Part D)*
- **Follow-up ladder.** Spec L151 is 24h, 48h, 72h with Deal manager. Code is every 2 days, 3 times, then a broker call, by Rania, tested as such ([documents.py:7](../diwan/documents.py#L7)). *(Part D)*
- **Expiry warning.** Spec L660 says 30 days. Code flags at 60 days ([documents.py:169](../diwan/documents.py#L169)). *(Part D)*
- **Default identity list.** Spec L660 has no visa for a sale; the code asks buyers for a residence visa ([desk_rules.py:32](../diwan/desk_rules.py#L32)). L678 asks for one on a rental only. *(Part D)*
- **When Form B happens.** Spec L708 needs Form B before the first viewing; L136 lists it as a Deal form after conversion; the code drafts it at conversion ([agency_forms.py:87](../diwan/agency_forms.py#L87)). *(Part D)*
- **Order of Form F.** Spec L715-716 signs the MOU after Compliance, Review and the owner and never mentions submitting it to DLD; L500 treats Form F as a portal fill. Code submits Form F first and only then opens "Form F signed" as the first step ([operations.py:102](../diwan/agents/operations.py#L102)). A Form F signed online before submission ticks nothing ([signing.py:188](../diwan/signing.py#L188)). *(Part D)*
- **Circular exit.** Spec L136 puts the NOC and DLD appointment on the checklist and L166 requires all lines done to emit `deal.ready_for_transfer`, yet L178 only starts the NOC and appointment on that event. L719 likewise has cheques after booking. *(Part D)*
- **When a deal closes.** Spec L722 and L736 close at handover. Code closes an off-plan deal once commission is paid and handover runs on after ([desk_rules.py:10](../diwan/desk_rules.py#L10)), tested at [test_desk_rules.py](../tests/test_desk_rules.py#L326). *(Part D)*
- **Correcting the unit.** Spec L166 reissues forms when the unit changes. Code refuses a property or terms change once any form is signed ([deal_property.py:42](../diwan/deal_property.py#L42), [desk_rules.py:302](../diwan/desk_rules.py#L302)). *(Part D)*
- **Discount gate.** Code holds conversion for the owner above a discount limit ([desk_stages.py:131](../diwan/desk_stages.py#L131)); spec L710 has no such gate. *(Part D)*
- **Rejected files.** Spec L697 lets a person override a rejection; [documents.py:201](../diwan/documents.py#L201) deliberately never keeps a rejected file. *(Part D)*
- **Meaning of `listing.ready`.** L179 emits it when the application and drafts are prepared; L707 means the listing is live; L758 and L759 separate it from `listing.live`. *(Part D)*
- **Form event names.** L176 uses `form.sent`, L715 `form.ready`, L745 `form.signed`, L716 and L732 `doc.received` for signed documents. *(Part D)*
- **Message wording.** Signature rejection differs between L157 and L687; the title deed message differs between L159 and L690. *(Part D)*
- **When Compliance gates a deal.** Spec L213 and L239: nothing binding is signed, and no transfer starts, until `compliance.cleared`. Code: forms are signed, Form F submitted and the transfer checklist run first; the Compliance gate is one item of the closing checklist, at the very end ([operations.py:195](../diwan/agents/operations.py#L195)), which the closing tests expect. *(Part E)*
- **When screening runs.** Spec L222: after KYC. Code deliberately screens as soon as money is discussed, before any KYC ([compliance.py:51](../diwan/agents/compliance.py#L51)), which is earlier and arguably safer. *(Part E)*
- **Who decides a cash report.** Spec L227: Reporting runs when a "person decides". Charter and code: drafted by itself at the threshold ([charters.py:125](../diwan/agents/charters.py#L125)), with the officer filing. *(Part E)*
- **Commission unpaid and closing.** Spec L782: "Stays open in Finance; Case otherwise closed". Code: the owner's closing checklist requires the commission paid before the deal can close ([desk_rules.py:55](../diwan/desk_rules.py#L55)). *(Part E)*
- **Deleting a client's data.** Spec L787 deletes data; spec L266 says nothing is deleted, only voided; the log refuses deletes at the database ([events.py:62](../diwan/events.py#L62)). *(Part E)*
- **Retention period.** Spec L260 and L265 say to confirm it with the compliance officer. The Deal desk already tells staff "at least five years" ([deal.html:652](../web/deal.html#L652)). *(Part E)*
- **Task titles.** Spec L528: titles name what raised them, not the client. The same line's own example ("Screen Ali Rahman") names the client, and the code does too: "Screen Karim Haddad, the buyer" is asserted in tests ([deal_flow.py:155](../e2e/deal_flow.py#L155)). *(Part E)*
- **Devil's advocate.** Spec L215 puts it in Compliance; spec L243 has it check every item in Review; the charter sits under Review and covers only source-of-funds files ([charters.py:136](../diwan/agents/charters.py#L136)). *(Part E)*
- **Agent names.** Spec L260 "Records clerk" against spec L553 "Archivist" (the code uses Archivist). Spec L215 has no Report drafter; spec L527 and the code do. *(Part E)*
- **Whose task a renewal is.** Spec L275: a Sales Task raised at 90 days. Code: an Operations after-closing task for the broker, raised at closing and dated ([operations.py:278](../diwan/agents/operations.py#L278)); the notice period is an owner's setting. *(Part E)*
- **Who posts.** Spec L1080: posted by a person, auto-post only if the owner switched it on. Code and the product owner's 31 Oct decision ([sessions.md](sessions.md) line 82, [studio.py:1202](../diwan/agents/studio.py#L1202)): an approved post goes out by itself at its time. *(Part F)*
- **What a price change does.** Spec L594: the script is withdrawn. L1082 and L1104: a price change or superseded Fact pauses the post, and it can be fixed. L1083: a superseded Fact sends it to withdrawn, which is final. *(Part F)*
- **Who Review is.** Spec L593: Review "like every other room". Code: [qa.py:1](../diwan/agents/qa.py#L1) is deliberately room-lead supervision, separate from the Review team, and [sessions.md](sessions.md) line 13 calls Marketing independent. *(Part F)*
- **Marketing and the brief.** Spec L1093, L1099 and L1109 put Marketing in the briefs and daily lists. Code: Nova's rounds leave Marketing out ([nova.py:488](../diwan/agents/nova.py#L488)); sessions.md line 13 has Marketing meeting Sales at one event only. *(Part F)*
- **Permit on every post or some.** Spec L1103: no post goes live without a valid permit number. Code, on purpose: "a topic sells no one thing, so it has no permit" ([studio.py:1141](../diwan/agents/studio.py#L1141), [topics.py:1](../diwan/topics.py#L1)), and a test holds it ([test_studio.py:841](../tests/test_studio.py#L841)). *(Part F)*
- **Generic product or one trade.** Spec assumes UAE real estate. Code keeps Setup free of any one industry: "Nothing has a default" ([business.py:1](../diwan/business.py#L1)), which sits against a UAE-only default at L591. *(Part F)*
- **A brief before scripts.** Spec L1075: a person approves a brief before scripts. Code, on purpose: the first person step is the script pick, so nothing waits before three scripts exist ([studio.py:1337](../diwan/agents/studio.py#L1337)). *(Part F)*
- **"Three fixes".** Spec L586 says three fixes; the list under it has five (L590-594). *(Part F)*
- **Stages and events do not line up inside the spec.** L1073-1083 has in_production, scheduled and archived, while L1085 has no event for entering any of them. *(Part F)*
- **Sold listing and stages.** L1082 pauses on "listing unconfirmed" and L1083 withdraws on "listing sold", but L1085 lists only `listing.withdrawn` and `listing.unconfirmed` to consume, so there is no named event for sold. *(Part F)*
