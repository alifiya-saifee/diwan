# Diwan — Closed-Loop Office Spec

Oct 31, 2026 · @Someone

## Why the rooms don't link today

The rooms break because each one keeps its own idea of the client and nobody owns the handoff. The fix is one shared spine that every room reads and writes, plus a written contract for each handoff: what a room needs before it starts, and what it must emit when it finishes.

**The spine (one of each, shared by all nine rooms)**

| Object | What it holds | Who writes it |
| --- | --- | --- |
| Person | One record per human: client, owner, broker, landlord, developer contact. Phone, email, WhatsApp, language, consent, "stop" flag. | Front Desk, Sales |
| Case | One record per client intent, from first message to keys. Has a single `stage` field and a single owner room. | Every room, but only the owner room advances `stage` |
| Fact | A thing the client said, with the exact quote, source (chat, call, meeting), timestamp and the Case it belongs to. Facts are never edited, only superseded. | Scribe, Sales, Deal |
| Task | One unit of work: owner room, assignee (agent or person), due date, the Facts it depends on, status. | Any room |
| Document | A file: form, ID, signature, invoice, receipt. Has a type, a check result and the Task it satisfies. | Deal, Operations, Finance |
| Approval | A person's yes on a specific version of a Task's output, pinned to the Fact versions it was based on. | Review, then a human |
| Event | Append-only log line: who, what, which Case, which Facts. Every room subscribes; no room calls another directly. | Every room |

**The three rules every room follows**

1. A room never calls another room. It writes an Event (`case.qualified`, `doc.signed`, `payment.marked_received`) and the next room picks it up. This is what makes the loop close: if an Event has no subscriber, the dashboard shows it as stuck.
2. A Case moves forward only when its exit checklist is complete. The owner room ticks the checklist; Review checks it; a human approves the move.
3. When a Fact is superseded (the client corrects themselves), every Task and Approval that depended on the old Fact is reopened, Compliance is told first, and nothing downstream may be approved until it is re-done.

**Where it most likely breaks now** (check these first)

- Lead and deal live in different tables, so a converted lead does not carry its Facts into Deal.
- Rooms call each other's functions instead of emitting Events, so a failed call silently drops the handoff.
- Tasks have no `depends_on_facts`, so a correction cannot find what to withdraw.
- Reminders and follow-ups are scheduled in more than one place, so some fire twice and some never.

## The loop at a glance

&#91;embedded content: the Diwan loop · 9 rooms, 4 gates\]

A Case is born in Sales, travels through Deal and Operations, and passes Compliance, Finance, Review and the owner before anything binding happens; when it closes, Records turns renewals and referrals into new Cases. Front Desk reads every Event to brief the owner, and the Lobby feeds improvements back into every room.

## Room 1 · Front Desk: the owner's PA

Front Desk is the owner's chief of staff: it knows the whole office, speaks for the owner only when allowed, and turns anything the owner says into Tasks for the right room. Lead agent: **Nova** (the owner-facing PA). Rania stays the client-facing receptionist in Sales.

**Modes** (Nova always knows which one it is in, and shows it on screen)

| Mode | Trigger | What Nova does | What Nova never does |
| --- | --- | --- | --- |
| Arrival | Owner opens the app or says good morning, first time that day | Greets by name in a human way ("Morning, Khalid. Two things need you before 11."), then the morning brief | Reads a wall of text; it leads with the top 3 |
| Brief | Arrival, or "what's going on?" | See the morning brief below | Repeats what the owner already dismissed |
| Meeting ("pocket") | "Hey Pocket", "I'm in a meeting", or a calendar event marked meeting | Goes silent. Listens and transcribes. Speaks only if spoken to by its wake word. After: summary, decisions, action items with owners, each linked to exact quotes | Interrupts, gives voice replies, sends anything during the meeting |
| Ask | Owner asks a question | Answers from Records, the calendar, the Case log or the web; says where the answer came from | Guesses a number; it says "not recorded" instead |
| Errand | "Check ticket prices", "book the vacation", "email Ahmed" | Researches, prepares, shows the plan and the exact message or booking; waits for the owner's yes | Pays, books, sends or signs without a yes |
| Do not disturb | Owner says so, or after hours | Queues everything except items the owner marked urgent | Pings for routine items |

**Morning brief** (built at 7:30 Dubai time on working days, ready before the owner arrives)

1. Urgent first: anything overdue, any Compliance flag, any payment due today, any client who asked for a call and has not had one.
2. Today: meetings and viewings with the client's last message and what they care about.
3. Pipeline: new leads since yesterday, hot leads, deals that moved stage, deals stuck more than N days (owner sets N).
4. Money: invoices sent, payments marked received, commissions due.
5. Decisions waiting for the owner: approvals in Review, with one line each and an approve / send back button.
6. One idea from the Lobby, if there is a relevant one.

**Errands Nova can run** (each ends in a draft the owner approves)

- Travel: search flights and hotels for dates and a budget, compare 3 options, hold if the site allows; the owner pays. "Book the vacation for the person in this email" = read that email, pull names and dates, confirm them back before searching.
- Email and messages: draft replies in the owner's style, schedule sends, chase people who have not answered.
- Calendar: book, move, decline, protect focus time, add travel time between viewings.
- Research: prices, competitor listings, a developer's track record, a news item about a project.
- On the laptop or phone: open a file, find a document, fill a form, through the desktop app or browser. Nova stops before any Submit, Pay or Send.
- Reminders: "remind me Thursday to call Sara" becomes a Task with a due time, not a note.

**What Front Desk emits**

- `task.created` to any room, from meeting action items or the owner's instructions.
- `fact.recorded` when the owner relays something a client said ("Sara now wants 3 beds, not 2"), which can trigger the correction rule.
- `approval.given` / `approval.declined` when the owner decides from the brief.

**Open questions**

- Which email and calendar does the owner use (Gmail, Outlook)? Needed before errands and step 8 of Sales.
- Does the owner want voice replies on the phone, or text only?
- Who else may talk to Nova (a manager, an assistant), and what may they not see?

## Room 2 · Sales: every inbound message becomes a qualified Case

Sales turns any first message, from any channel, into a Case with a known intent, a heat score and a next step owned by a named broker. Client-facing agent: **Rania**. Broker-facing PA: **Sales lead**, who tells brokers what to do next and chases them like a human PA would.

**Channels in:** WhatsApp, Instagram DM and comments, Facebook, TikTok, website form, Property Finder / Bayut / Dubizzle portal leads, phone call notes, walk-ins added by hand, referrals.

**Discovery: reading the first message**

| First message looks like | Rania starts with | Intent set to |
| --- | --- | --- |
| A portal enquiry on listing X | The listing; asks only what's missing (budget, timing, finance) | Buy or rent, from the listing |
| "Is this still available?" on a post | Confirms, then one question: to live in or invest? | Buy / rent |
| "I want to sell my flat in JVC" | Unit, size, expected price, title deed holder, mortgage on it? | Sell (listing lead) |
| "Can you manage my apartment?" | Unit, current tenant, rent | Landlord / property management |
| "Hi" or "price?" with no context | A warm hello and one question: buying, selling, renting or just looking? | Unknown until answered |
| A question about the company or a service | Answers from the knowledge base, then asks if they have a property in mind | Marketing / nurture |
| Spam, job seekers, suppliers | Polite routing to the right inbox | Not a lead |

**Qualifying** (the owner's form, one question at a time, each answer stored as a Fact with the client's words)

- Buyers: purpose (live / invest), area, type, beds, budget, cash or mortgage, mortgage pre-approval, timeline, residency (UAE resident / non-resident), nationality only if Compliance needs it.
- Sellers: unit, title deed, mortgage outstanding, expected price, vacant or tenanted, timeline.
- Tenants and landlords: move-in date, cheques, ejari, pets, company or personal.
- Heat score from the owner's rules (e.g. hot = budget fits + timeline under 60 days + finance ready).

**The PA behaviour (what makes it feel like a real assistant)**

1. Call now. When the client says "call me", "can someone call", or picks a call slot, Rania replies "Sure, \[broker\] will call you in the next 10 minutes" and the broker gets a push and WhatsApp alert: name, what they want, the last 3 messages, one-tap call. If the broker has not called in 10 minutes, Sales lead escalates to the next free broker and tells the owner in the brief.
2. Call later. "Call me tomorrow after 4" becomes a Task with that due time in the client's time zone. Sales lead reminds the broker 15 minutes before, and Rania tells the client the time is confirmed.
3. Hot lead. Sales lead messages the broker: "Sara is hot: 2-bed Marina, AED 2.4M, cash, wants to view this week. Book a viewing?" with buttons.
4. Daily broker sweep. Every morning each broker gets their list: who to call, who's gone quiet, who's waiting on options.
5. Follow-ups on the owner's schedule, never at night or at Friday prayer, never the same message twice; "stop" means stop everywhere.

**Exit: when a Case leaves Sales**

The broker marks the outcome: `converted` (offer accepted or client commits), `follow up on [date]`, `not interested` (reason), `no response`. `converted` emits `case.converted` with every Fact so far, and Deal takes over. Nothing is retyped.

**Gaps to build**

- Outcomes (step 9) and the broker escalation timer.
- Instagram / Facebook DM connection (Meta Graph API) and portal lead webhooks.
- One heat-score setting in the owner's settings, used by Rania, the brief and Records alike.

## Room 3 · Deal: the converted Case reaches signed paperwork

Deal owns the Case from `case.converted` to `deal.ready_for_transfer`: it picks the right checklist for the deal type, makes sure every form is sent, signed and checked, and chases the client until nothing is missing. Lead agent: **Deal manager** (a PA for the deal desk). Deal does not judge the client's money or identity; it waits for Compliance's clearance before anything binding.

**Checklist by deal type** (picked from the Case's Facts; the owner can edit each template)

| Deal type | Forms and documents the checklist tracks |
| --- | --- |
| Secondary sale, cash | Form A (seller and broker), Form B (buyer and broker), Form I if another agency is involved, Form F (MOU), IDs and passports, title deed, developer NOC, DLD transfer appointment |
| Secondary sale, buyer mortgage | All of the above + mortgage pre-approval, valuation, final offer letter, bank's manager's cheques, liability letter if the seller has a mortgage |
| Off-plan | Reservation form, booking payment, SPA from the developer, Oqood registration, payment plan schedule |
| Rental | Tenancy contract, Ejari, cheques, security deposit, IDs, title deed copy, landlord's authorisation if a POA |
| Listing (seller signs up) | Form A, title deed, ID, Trakheesi / listing permit, photos booked |

Each line is a Task with an owner room (Deal, Operations, Compliance or Finance), a due date and the Facts it depends on.

**The client form portal** (the piece that closes the loop with the client)

1. Deal manager sends a WhatsApp message with a private link: "Hi Sara, 3 things to complete your offer: your passport, Emirates ID and signature on Form B. Takes 2 minutes."
2. The link opens a mobile page showing only this client's missing items, pre-filled from the Facts (name, unit, price). The client checks, uploads, signs.
3. Signature: the client draws it on screen (preferred) or uploads a photo of it.
4. Every upload is checked the moment it arrives, before the client leaves the page (below). A failed check asks for a re-upload right there, with the reason.
5. On submit, the client gets a WhatsApp: "Received your signed Form B and passport, thank you. Next: we'll send the MOU once the seller signs." The Task closes, the Document is stored on the Case, and `doc.received` is emitted.
6. If nothing arrives, Deal manager follows up: a gentle nudge after 24 hours, a broker call Task after 48, and the owner sees it in the brief after 72. Same quiet hours as Sales.

**Upload checks (run on upload, answer within seconds)**

| Expected | Passes if | Rejects with |
| --- | --- | --- |
| Signature | Dark ink strokes on a plain light background, no face, no printed text block, not blank, not a screenshot of a typed name | "This looks like a photo of \[a document / a person\], not a signature. Please sign on the white box or upload a photo of your signature on white paper." |
| Passport / Emirates ID | The document type is right, the name matches the Case, not expired, all 4 corners visible, readable | Which of those failed, in one line |
| Title deed | DLD title deed layout, unit number matches the Case | "The unit number doesn't match the one we have (Marina Crest 1204)." |
| Any PDF form | Signed on every signature line, right form version | Which page is unsigned |

A signature check is a first filter, not a forgery test. A person still sees every signed form in Review before it goes anywhere official.

**Exit**

All checklist Tasks done, Compliance cleared, Finance has the deposit or booking marked received, Review passed and the owner approved: emit `deal.ready_for_transfer` to Operations. If a Fact is corrected mid-deal (price, unit, buyer name, cash to mortgage), the checklist is rebuilt and only the affected forms are reissued.

## Room 4 · Operations: the forms go out and the official steps get done

Operations does the hands-on work the other rooms ask for: preparing and sending forms, filling government and developer portals up to the Submit button, booking appointments and handover. Lead agent: **Ops lead**, with the **Form F clerk** (browser, stops before Submit) and a **Scheduler**. Operations never decides; it executes Tasks that another room created.

**What Operations picks up**

| Event in | Operations does | Event out |
| --- | --- | --- |
| `task.created` for a form | Builds the form from the Case's Facts, sends it to the client portal or the other agency | `form.sent` |
| `doc.received` | Files it on the Case, renames it to the office's convention, attaches it to the portal draft | `doc.filed` |
| `deal.ready_for_transfer` | Requests the developer NOC, fills the DLD / trustee appointment request up to Submit, books the trustee office slot | `transfer.booked` (after a person submits) |
| Listing signed (Form A) | Prepares the Trakheesi / listing permit application up to Submit, books photographer, drafts portal listing | `listing.ready` |
| Rental signed | Prepares Ejari up to Submit, collects cheques Task for Finance | `ejari.ready` |
| `transfer.completed` (a person marks it) | Handover checklist: keys, access cards, DEWA / chiller transfer reminders, welcome message to the buyer | `case.closed` |

**Rules**

- Every portal step stops before Submit, Pay or Sign. The person sees a filled screen and a checklist of what was entered, then clicks.
- Every form Operations sends is built from Facts, never retyped. If a Fact is superseded, Operations withdraws the sent version ("Please ignore the Form B sent at 10:14; a corrected one follows") and resends.
- Each Task shows waiting-on: client, other agency, developer, bank, government. Waiting on an outside party for more than the owner's limit goes to the brief.

## Room 5 · Finance: invoices out, payments marked in, commissions split

Finance makes sure every deal is billed and every dirham is accounted for; because no bank is connected, a person marks money received and Finance does everything around that click. Lead agent: **Finance lead**, the finance PA: it drafts invoices, tracks what is due, tells the owner what's late, and reconciles.

**Finance lead's job, in plain words**

- Bill: when a Case reaches the agreed trigger (Form F signed, transfer completed, tenancy signed), draft the invoice from Facts: client or developer, commission %, VAT 5%, TRN, due date. A person approves; then it's sent by email and WhatsApp.
- Track: every invoice and every client payment (deposit, booking amount, cheques) has a status: draft, sent, due, overdue, partly paid, received, written off.
- Chase: polite reminders on the owner's schedule; overdue developer commissions go to the brief.
- Split: once received, calculate broker commission and any co-broker share (Form I), and prepare a payout list for the owner to pay.
- Report: cash in this month, outstanding, expected next 30 days, per broker.

**Marking a payment received (no bank feed)**

1. The person opens the invoice or payment and taps Mark received.
2. They enter amount, date, method (transfer, cheque, manager's cheque, cash, card) and a reference; a proof (screenshot, cheque photo, bank SMS) is optional but asked for.
3. Finance lead reads the proof if given and flags a mismatch ("Proof shows AED 50,000; invoice is AED 52,500") before saving.
4. Partial amounts keep the invoice open with the balance shown.
5. Saving emits `payment.marked_received`, which can unblock Deal (deposit received) and triggers the client's WhatsApp receipt ("We've received AED 50,000 for Marina Crest 1204. Receipt attached.").
6. Cash above the owner's threshold, or a payer who isn't the client, goes to Compliance before the receipt is sent.
7. Every mark is logged with who did it and can be undone with a reason, never deleted.

**Later, if wanted:** forward bank alert emails or SMS to a Finance inbox and let Finance lead suggest matches; a person still confirms.

## Room 6 · Compliance: nobody signs anything binding until Compliance clears the Case

Compliance checks who the client is, where the money comes from and whether the deal can go ahead, and it is the first room told whenever a Fact changes. Lead agent: **Compliance lead**, with the **Screening analyst** (code), the **Source-of-funds analyst** and the **Devil's advocate**. The office's named compliance officer (a person) makes every final call and every regulatory filing.

**Checks, and when they run**

| Check | Runs when | Output |
| --- | --- | --- |
| KYC / CDD | `case.converted` | ID verified, names match across documents, address, risk rating (low / medium / high) |
| Screening | KYC done, and again whenever a name changes | Sanctions and terrorist list hits, PEP status, adverse media; every hit goes to the person, never auto-cleared |
| Source of funds / wealth | Purchase price or cash amount above the owner's threshold, high risk, or PEP | What the client said (exact quote), documents asked for (bank statements, sale deed, salary letter), whether they support the story |
| Payment pattern | `payment.marked_received` | Cash amounts, third-party payers, split payments, crypto, mismatch with the Fact |
| Mortgage | Case says mortgage | Pre-approval present and in date, amount covers price minus down payment, bank valuation vs price, seller's liability letter if the unit is mortgaged |
| Enhanced due diligence | High risk or PEP | Extra documents, senior sign-off |
| Reporting | Person decides | Drafts for the officer: suspicious transaction report and cash-transaction report on goAML. Diwan drafts; the officer files. Thresholds and forms to be confirmed with the office's compliance officer. |

**The correction rule** (the heart of Diwan)

1. A new Fact contradicts an old one ("actually my brother is paying", "it's AED 3.1M not 2.8M", "I'll take a mortgage after all").
2. Compliance is told first, before any other room, with both quotes side by side.
3. Every Task and Approval whose `depends_on_facts` includes the old Fact is withdrawn: reopened, marked "based on superseded fact", and any sent form is recalled by Operations.
4. Compliance decides whether the change needs new checks (a new payer means screening and source of funds again).
5. Approvals pinned to old Fact versions are refused if anyone tries to use them. Work that did not depend on the old Fact stays untouched.

**Clearance**

Compliance emits `compliance.cleared`, `compliance.needs_info` (Deal asks the client through the portal) or `compliance.blocked` (the Case stops and the owner is told). Deal cannot emit `deal.ready_for_transfer` without `compliance.cleared` on the current Fact versions.

## Room 7 · Review: an agent checks it before a person sees it

Review is the gate between agent work and human approval: nothing reaches a person's approve button until the **Fact checker** and the **Devil's advocate** have checked it, and the person sees what they found. It removes the obvious mistakes so the human spends their minute on judgment, not typos.

**What Review checks on every item**

- Quotes: every claim about the client traces to an exact quote, and the quote is still the current Fact (not superseded).
- Numbers: price, commission, VAT, dates and unit numbers match the Facts and each other across all documents in the Case.
- Completeness: the checklist for this stage is done; required signatures are on every line.
- Authority: the agent that made it was allowed to (the charter), and nothing was sent or submitted without a yes.
- Tone and promises: client-facing text makes no promise the office can't keep (guaranteed returns, visa claims, "price will go up").
- Compliance: the item doesn't move a Case past a Compliance hold.

**What the person sees**

One card per item: what it is, the room and agent that made it, a green / amber / red verdict with each finding in one line, links to the quotes, and Approve, Send back (with a note to the agent) or Edit. Approve pins the approval to the current Fact versions. Send back creates a Task for the room with the note. Patterns in send-backs feed the Lobby and the agents' instructions.

## Room 8 · Records: the one place the truth lives, and the analyst who reads it

Records is the system of record: every Person, Case, Fact, Document, invoice, payment and Event, searchable and kept for the retention period. Its agents are the **Records clerk** (files and indexes) and the **Data analyst** (answers questions and writes reports).

**What Records holds**

- Case file: the timeline of every Event, every Fact with its quote and superseded history, every document version, every approval and who gave it.
- Registers: deals closed, listings, tenancies with renewal dates, commissions, compliance files (kept for the legally required period; confirm with the compliance officer).
- Audit trail: who did what and when, agents included. Read-only; nothing is deleted, only marked void with a reason.

**What the Data analyst answers** (to the owner through Nova, or on the Records dashboard)

- Funnel: leads to qualified to viewing to offer to closed, by channel, broker and month; where they drop.
- Speed: time to first reply, time to call after "call me", days in each stage.
- Money: commission closed and pending, cost per lead by channel, average deal size.
- People: broker leaderboard, follow-up discipline, send-back rate in Review.
- Market: asking vs closing prices by area from the office's own deals.
- Renewals coming up: tenancies ending in 90 days become Sales Tasks, which is how a closed Case turns into the next one.

Weekly report on Monday morning, in the brief. Every number links to the records behind it.

## Room 9 · Lobby: where the agents learn from other businesses

The Lobby is a shared room where agents read what is working for other businesses in the same field, discuss it, and propose changes to their own office; nothing changes until the owner approves. Agents: a **Lobby host** who runs the discussions and one representative from each room.

**What goes in**

- Playbooks: anonymised, opt-in patterns from other Diwan offices ("WhatsApp follow-up on day 3 with a floor plan gets 2x replies"). Never client data, never another office's names or numbers that identify them.
- Public signals: competitors' posts and reels (already in the content studio), portal listing trends, DLD transaction data, news on projects and regulation.
- The office's own lessons: Review send-backs, lost deals with reasons, the client questions Rania couldn't answer.

**What comes out**

- A weekly discussion thread per room: what others are doing, whether it fits this office, a proposed change (a new follow-up message, a qualifying question, a checklist step, a content idea).
- Each proposal is an experiment: what changes, for whom, for how long, and the number Records will watch. The owner approves; after the period Records reports whether it worked and the change is kept or rolled back.
- One idea a day can surface in the morning brief.

**Guardrails:** an agent may suggest a change to its own instructions but cannot apply it; compliance rules and the owner's settings can't be changed from the Lobby.

## Rules that apply in every room

These hold across all nine rooms, so behaviour doesn't drift room to room.

**Notifications** (one service, not one per room)

| Level | Example | How it reaches the person |
| --- | --- | --- |
| Now | Client asked for a call; Compliance hit; payment mismatch | Push + WhatsApp to the person, repeats once after 10 min, then escalates |
| Today | Viewing booked; form received; invoice approved | In-app, collected into a midday summary |
| Brief | Stuck deals, ideas, reports | Morning brief only |

Quiet hours, Friday prayer and do-not-disturb apply to client messages always, and to staff messages unless the level is Now.

**Who may do what**

- Agents may: read, draft, check, fill up to Submit, schedule reminders, message clients inside the 24-hour WhatsApp window or with approved templates.
- Only a person may: approve, submit to a government or developer portal, pay, sign, mark money received, file a regulatory report, clear a screening hit.
- Agents never hold portal, bank or email passwords; sign-in happens in the person's own browser session.
- Each person sees only their rooms: a broker sees their Cases; Finance sees money; the owner sees all.

**When something fails**

- A model call fails: retry once, then fall back to rules, and mark the output as fallback.
- An Event has no subscriber or a Task is overdue: it shows on a Stuck board and in the brief, never silently.
- A message can't be delivered (outside 24 hours, number blocked): Task for the broker to call.
- Every agent turn logs the charter version, inputs, the Facts used and the outcome, so any output can be replayed.

## Build order and the test that proves the loop closes

Build the spine first, then wire the rooms in the order a deal travels; each step is done when its part of the end-to-end test passes.

1. Spine: one Case per client intent, Facts with `superseded_by`, Tasks with `depends_on_facts`, Approvals pinned to Fact versions, an Event log with subscribers and a Stuck board.
2. Sales exit: broker outcomes; `case.converted` carries every Fact to Deal.
3. Deal: checklist templates per deal type; client form portal with upload checks and WhatsApp receipts; follow-up ladder.
4. Compliance gate: clearance required before `deal.ready_for_transfer`; correction rule end to end.
5. Finance: invoices from Facts; Mark received with proof check; client receipt.
6. Operations: form sending and recall; portal fills up to Submit; handover and `case.closed`.
7. Review: one card per item with findings; approvals pinned.
8. Front Desk: morning brief from all rooms' Events; meeting mode; errands.
9. Records analyst, renewals back into Sales; then the Lobby.

**The end-to-end test** (one fictional client, run in Playwright on a scratch database)

- [ ] Sara messages on WhatsApp "is the 2-bed in Marina still available?"; Rania qualifies her; she says "call me" and the broker gets an alert within 1 minute.
- [ ] Broker marks converted; Deal shows the secondary-sale cash checklist with her Facts already filled.
- [ ] Sara gets the portal link; uploads a selfie as a signature and is asked to re-upload; signs on screen; gets the WhatsApp receipt.
- [ ] Compliance screens and clears; Finance invoices; a person marks the deposit received; Sara gets the receipt.
- [ ] Sara writes "my brother will pay part of it": Compliance is flagged first, the payer-dependent Tasks reopen, the old approval is refused, unrelated Tasks stay done.
- [ ] Compliance clears again; Review passes; the owner approves; Operations fills the transfer request and stops before Submit.
- [ ] A person marks the transfer complete; the handover message goes out; the Case closes; Records shows it in the funnel.
- [ ] Next morning, Nova's brief mentions the closed deal and the commission due, and nothing is on the Stuck board.

# Part 2 · From screenshots to build commands

## What the screenshots show

The rooms look finished, but they are all showing the same office-wide data instead of their own, and three rooms from the spec (Deal, Lobby, a Sales PA) aren't on the floor yet. That matches the "it doesn't link" feeling: each room is a view on one shared pile, not a stage that receives work and hands it on.

**Bugs and inconsistencies seen**

| Where | What's wrong | Fix |
| --- | --- | --- |
| Every room | Same stats on every room: 52 agents, 5 tasks, 4 need people, 12 facts | Stats filtered to the room: its agents, its open Tasks, its items waiting for people, the Facts its Tasks depend on |
| Every room | "What the office knows" wall shows the same quotes everywhere; Records and Sales show the same Open work cards (N458, N479 for Omar) | Left wall = Facts this room's Tasks depend on; right wall = this room's Tasks only |
| Every room | The demo button is "Karim corrects himself" in every room | Keep one demo on HQ, or show each room's part of it |
| Compliance | Screening analyst shows *idle* while task T5 "Screen Ali Rahman" is open | Tasks aren't being picked up: an open Task with an owner agent must start it, or show why it's blocked |
| Compliance | T5 reads "named by Ali Rahman" | Should name who or what raised it (the Fact or the room) |
| Review | 0 tasks; Devil's advocate "Planned: no work yet" | Nothing is routed to Review. Every item awaiting a person's approval must pass through Review first |
| Operations | 0 tasks; Transfer tracker "no work yet" | Nothing emits work for Operations; needs `deal.ready_for_transfer` and form Tasks |
| Finance | Invoice clerk reads *supplier* invoices | The core job is outgoing commission invoices and Mark received; supplier bills are secondary |
| Inbox · Ali Rahman | Rania says "Hamza will contact you" but the assigned broker is Omar; Omar then writes "This is Hamza" | One name per staff member, used by Rania, the broker label and the signature |
| Inbox · Ali Rahman | Stage "Qualified" but progress says "step 3 of 8" | Either Qualified means the form is complete, or show "Qualifying 3/8" |
| Inbox · Ali Rahman | Tags: Buy, Off-plan, 2 bed, **AED 20K** | Budget looks misread (20K is a rent figure, not an off-plan price). Store the exact quote with the number and ask the client to confirm when it's out of range for the intent |
| Inbox | Two Rania suggestions for the same message | Show one suggestion, regenerate on request |
| Inbox | Convert button: unclear where it goes | Convert must open the Case in Deal with every Fact carried, and show the new Deal link |
| Studio | Topic "Meet Diwan Realty" | Typo: Realty |
| Studio | "Do our posts need a permit?" set to No | Dubai property ads generally need an advertising permit (Trakheesi); check with the office and default to Yes for UAE real estate |
| Studio | Website set to a real brokerage's site | The README says demo data is fictional; use the office's own site or a fictional one |

**Missing from the floor**

- Deal room (Deals is only a top-nav page): needs its own room with the checklist, client portal status and follow-ups.
- Lobby room: only a "Lobby board" orb inside Front Desk.
- Sales lead PA in the Sales room, and a "call now" queue.
- Finance: Mark received, invoice drafting, commission split.
- A Stuck board on HQ: Events with no taker and overdue Tasks.

## A PA for every staff member

Every signed-in person gets their own PA, always on call, that sees only what their role sees and acts only through the same rules as everyone else. Nova stays the owner's PA; Omar gets "Omar's PA", Layla gets "Layla's PA", and so on. The "Ask Nova, or tell her who needs to do…" box becomes "Ask your PA" and talks to the signed-in person's PA.

**How a personal PA works**

| Part | Rule |
| --- | --- |
| Identity | One PA per staff account, named by the person (default "\[Name\]'s PA"). Voice and tone set per person |
| Scope | Sees the rooms and Cases the person's role allows (table below). Never sees another broker's clients unless shared or the person is a lead |
| On call | Chat box on every page, push-to-talk on the phone, optional wake word on desktop, and WhatsApp to the person's own number |
| Morning | A short brief for that person only: their calls, viewings, Tasks due, items waiting on them, and anything a lead assigned overnight |
| Doing | Drafts, schedules, reminds, fills forms up to Submit, searches Records. Asks before sending anything to a client and never approves on the person's behalf |
| Handoff | "Tell Finance the deposit came in" = the PA creates a Task or Event for Finance; Finance's PA picks it up. PAs never message each other directly; they go through Tasks and Events so every handoff is on the log |
| Escalation | If a Task the person owns goes overdue, their PA nudges them first, then the room lead's PA, then Nova (owner) |
| Memory | Remembers the person's preferences ("call me before 10", "I don't do Sundays") as settings, not loose notes |

**Who sees which rooms**

| Role | Front Desk | Sales | Deal | Ops | Finance | Compliance | Review | Records | Lobby |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Owner | All | All | All | All | All | All | All | All | All |
| Broker | Own brief | Own leads | Own deals | Status only | Own commission | Status only | Own items | Own numbers | Read |
| Sales lead | Own brief | All leads | All deals | Status only | Team commission | Status only | Team items | Team numbers | Read, propose |
| Deal / Ops staff | Own brief | Read | All | All | Status only | Status only | Own items | Deals | Read |
| Finance | Own brief | No | Amounts | No | All | Payment flags | Own items | Money | Read |
| Compliance officer | Own brief | Read | Read | Read | Payments | All | Own items | Compliance files | Read |

"Status only" = sees whether a step is done or blocked, not its contents.

## Room by room: the PA, the blocks on screen, the command

Run Command 0 first, then one room per session, and run the end-to-end test after each. Paste each command as it stands to your coding AI; each one names what to read, what to build and how to prove it works.

**Every room shows the same frame** so staff learn it once: a room header with its own live stats, the PA panel on the right, a "Waiting on you" strip, the room's Tasks, the Facts those Tasks rest on, and a Stuck list.

### Command 0 · The spine (do this first)

```text
Read README.md, BUILD_LOG.md, docs/sessions.md, docs/deal-desk.md and the "Why the rooms don't link today" section of the spec.
Goal: every room reads and writes one shared spine, and no room calls another room's code directly.
1. Make sure there is one Case table: one row per client intent, with stage, owner_room, broker_id, created_from (channel), and links to Person. Leads in the Inbox and deals in Deals must be the same Case at different stages, not two tables.
2. Facts: exact quote, source, timestamp, case_id, superseded_by. Never update a Fact in place.
3. Tasks: owner_room, assignee (agent or person), due_at, status, depends_on_facts (list), waiting_on (client/bank/developer/government/person).
4. Approvals: pinned to the Fact ids and versions they were based on. Refuse to use an approval whose Facts were superseded.
5. Event log: append-only, with a subscriber registry. Each room declares the Events it consumes and emits. Add an HQ "Stuck" panel listing Events with no consumer, Tasks overdue, and Tasks assigned to an agent that has not started them within 5 minutes.
6. Agents must pick up their open Tasks: if an agent is idle while a Task is assigned to it, start it or show the blocking reason on the card.
7. Room stats and walls must be filtered by room: agents in the room, the room's open Tasks, items waiting for people in the room, and the Facts those Tasks depend on.
Tests: pytest for the correction rule (supersede a Fact, only dependent Tasks reopen, old approval refused) and a Playwright check that each room's stats differ.
Do not change the visual style. Report what you changed and what you could not.
```

### Front Desk · Nova (owner's PA)

**Blocks on screen:** Today (meetings, viewings, calls, with each client's last message) · Urgent strip (overdue, Compliance flags, unanswered "call me", payments due) · Decisions waiting for the owner (approve / send back) · Pipeline at a glance by stage · Money today · Stuck list · Errands in progress (travel, email drafts) · Lobby idea of the day · Mode chip (Arrival, Meeting, Do not disturb).

```text
Room: Front Desk. Agent: Nova, the owner's PA. Read the Front Desk section of the spec and the PA section.
Build:
1. Arrival: first open of the day, Nova greets the owner by name and gives the top 3 items, then the full morning brief built at 07:30 Asia/Dubai from Events of the last 24 hours across all rooms (urgent, today, pipeline, money, decisions waiting, one Lobby idea).
2. Meeting mode: wake phrase "Hey Pocket" or a calendar event marked meeting. Nova is silent, records and transcribes, answers only to the wake phrase, and afterwards produces summary, decisions and action items, each linked to exact quotes, and creates Tasks in the right rooms. Client statements become Facts (and can trigger the correction rule).
3. Ask: answers from Records, the calendar and the Event log with the source shown; says "not recorded" rather than guessing.
4. Errands: travel search, email drafts, reminders. Each ends in a draft with a Confirm button. Never pay, book, send or sign without the owner's yes.
5. Do not disturb: queue everything except items marked Now.
The chat box on every page talks to the signed-in user's own PA; Nova only for the owner.
Tests: brief contents from a seeded day; meeting mode creates Tasks with quotes; no send without confirm.
```

### Sales · Rania (clients) and Sales lead (brokers' PA)

**Blocks on screen:** Call now queue (who asked to be called, minutes waiting, one-tap call, escalation timer) · Hot leads · New leads by channel · Qualifying in progress (step x of n) · Follow-ups due today · Quiet clients · Each broker's day · Outcome needed (leads with no outcome after a call).

```text
Room: Sales. Agents: Rania (client-facing) and Sales lead (broker-facing PA; add it to the Sales room on the floor). Read the Sales section of the spec.
Fix first:
- One display name per staff member, used by Rania's promises, the broker label and message signatures (Ali Rahman's chat says Hamza while the broker is Omar).
- Stage vs progress: "Qualified" only when the owner's form is complete; otherwise "Qualifying 3/8".
- Numbers: store the exact quote with each parsed number; if a budget is out of range for the intent (e.g. AED 20K for an off-plan purchase), Rania asks the client to confirm.
- Show one Rania suggestion per incoming message.
Build:
1. Call now: "call me" creates a Now Task for the broker with the last 3 messages and a call button; push + WhatsApp alert; if not called in 10 minutes, Sales lead reassigns to the next free broker and tells the owner.
2. Call later: a stated time becomes a Task in the client's time zone; reminder 15 minutes before; Rania confirms the time to the client.
3. Sales lead daily sweep per broker at 08:30: who to call, who went quiet, who awaits options.
4. Outcomes after every call: converted / follow up on date / not interested + reason / no response.
5. Convert: emits case.converted carrying every Fact; the Case appears in the Deal room and the Inbox shows a link to it.
Tests: Playwright for call now escalation, outcome required, convert lands in Deal with Facts.
```

### Deal · Deal manager

**Blocks on screen:** Deals by stage (board) · Each deal's checklist with owner room and status per line · Client portal status (link sent, opened, items uploaded, failed checks) · Follow-up ladder (24h / 48h / 72h) · Waiting on (client, other agency, bank, developer) · Gates panel: Compliance, Finance, Review, owner.

```text
Room: Deal. Add a Deal room to the 3D floor (today Deals is only a top-nav page). Agent: Deal manager. Read the Deal section of the spec and docs/deal-desk.md.
Build:
1. On case.converted, pick a checklist template from the Case's Facts (secondary cash, secondary mortgage, off-plan, rental, listing). Templates editable in Settings. Each line becomes a Task with owner_room and depends_on_facts.
2. Client portal: a private, expiring link sent on WhatsApp. Mobile page shows only this client's missing items, pre-filled from Facts. Sign on screen or upload.
3. Upload checks run on upload, before the client leaves: signature (ink strokes on light background; reject faces, documents, blank, typed names), passport/Emirates ID (type, name matches, not expired, 4 corners), title deed (unit matches), PDF forms (every signature line signed). On fail, show the reason and ask to re-upload on the spot.
4. On submit: store Documents on the Case, close the Tasks, emit doc.received, and send the client a WhatsApp receipt naming what was received and what's next.
5. Follow-up ladder for missing items: nudge at 24h, broker call Task at 48h, owner brief at 72h; quiet hours and Friday prayer respected.
6. deal.ready_for_transfer only when all lines are done and compliance.cleared, payment received, Review passed and owner approved, all on current Fact versions.
7. A superseded Fact rebuilds the checklist and reissues only the affected forms.
Tests: Playwright: selfie uploaded as signature is rejected; drawn signature accepted; WhatsApp receipt in sandbox; gates block the transfer.
```

### Operations · Ops lead, Form F clerk, Transfer tracker

**Blocks on screen:** Forms to send and sent (with version) · Portal drafts ready for a person to Submit · Appointments (trustee, DLD, handover) · Waiting on outsiders with days waited · Recalled forms · Handover checklist.

```text
Room: Operations. Agents: Ops lead, Form F clerk, Transfer tracker. Read the Operations section of the spec.
Build:
1. Subscribe to task.created (form), doc.received, deal.ready_for_transfer, listing signed, rental signed, transfer.completed, as in the spec's table.
2. Forms are generated from Facts, never retyped; each sent form records the Fact versions it used.
3. On a superseded Fact, recall the sent form with a short client message and resend the corrected one.
4. Portal fills (Form F, NOC request, trustee booking, Ejari, listing permit) stop before Submit; show the filled screen and a list of what was entered for a person to submit.
5. Every Task shows waiting_on and days waiting; over the owner's limit goes to the brief.
6. On transfer.completed (marked by a person): handover checklist and welcome message; emit case.closed.
Tests: the Ops room shows Tasks after a deal reaches ready_for_transfer; a recall happens after a price correction.
```

### Finance · Finance lead (finance PA), Payment tracker, Invoice clerk

**Blocks on screen:** Invoices (draft, sent, due, overdue, partly paid, received) · Mark received · Expected payments, each tied to the client's words · Commissions to split and pay out · Cash this month, outstanding, next 30 days · Flags for Compliance.

```text
Room: Finance. Agents: Finance lead (PA), Payment tracker, Invoice clerk. Read the Finance section of the spec.
Change: the Invoice clerk's main job is outgoing commission invoices; reading supplier invoices stays as a secondary job.
Build:
1. Invoice drafts from Facts at the owner's trigger (Form F signed, transfer completed, tenancy signed): payer, commission %, VAT 5%, TRN, due date. A person approves; then send by email and WhatsApp.
2. Mark received (no bank feed): amount, date, method, reference, optional proof. Finance lead reads the proof and flags mismatches before saving. Partial payments keep the balance open. Undo with a reason, never delete.
3. On save emit payment.marked_received: unblocks Deal, sends the client a receipt, and sends cash above the threshold or a third-party payer to Compliance first.
4. Commission split per broker and co-broker; payout list for the owner to pay.
5. Reminders for overdue invoices on the owner's schedule.
Tests: mark received with a mismatched proof shows a flag; a third-party payer goes to Compliance before the receipt.
```

### Compliance · Compliance lead, Screening, Source-of-funds, Report drafter

**Blocks on screen:** Corrections (old quote vs new quote, side by side, newest first) · Screening queue and hits waiting for the officer · Source-of-funds files (what the client said vs documents) · Risk rating per Case · Holds (Cases blocked and why) · Report drafts for the officer · Rule book.

```text
Room: Compliance. Agents: Compliance lead, Screening analyst, Source-of-funds analyst, Report drafter, Devil's advocate. Read the Compliance section of the spec.
Fix first: open Tasks assigned to an idle agent must start (T5 "Screen Ali Rahman" while the Screening analyst is idle). Task titles name what raised them (a Fact id or a room), not the client.
Build:
1. Run KYC on case.converted; screening after KYC and again whenever a name or payer changes; source of funds above the owner's threshold, high risk or PEP; payment-pattern check on payment.marked_received; mortgage checks when the Case says mortgage.
2. Every screening hit goes to the named compliance officer; agents never clear a hit.
3. Correction rule: Compliance is notified first with both quotes; dependent Tasks and Approvals are withdrawn; Compliance decides which checks rerun.
4. Emit compliance.cleared / needs_info / blocked. needs_info becomes a client portal request through Deal.
5. Report drafter prepares drafts for the officer to file; Diwan never files. Thresholds are settings to confirm with the officer.
Tests: a new payer reruns screening and blocks transfer until cleared.
```

### Review · Fact checker, Devil's advocate

**Blocks on screen:** Items awaiting review (green / amber / red) · Findings per item, each linked to its quote · Sent back with the note · Approved, with the Fact versions they're pinned to · Patterns in send-backs this week.

```text
Room: Review. Agents: Fact checker, Devil's advocate. Read the Review section of the spec.
Fix: Review shows 0 tasks because nothing is routed to it. Every item that needs a person's approval (forms, invoices, client messages outside the 24h window, decks, transfer requests) must emit review.requested first.
Build:
1. Checks per item: quotes current, numbers consistent across the Case, checklist complete, authority (charter) respected, no promises the office can't keep, no Compliance hold bypassed.
2. One card per item: verdict, one line per finding, links to quotes, Approve / Send back with note / Edit.
3. Approve pins to current Fact versions; Send back creates a Task for the room with the note.
4. Weekly send-back patterns go to the Lobby.
Tests: an invoice with a price that differs from the current Fact is marked red; approving is blocked.
```

### Records · Archivist, Data analyst, Records lead

**Blocks on screen:** Search across all Cases · Case file timeline · Registers (deals, listings, tenancies with renewal dates, commissions) · Funnel by channel and broker · Speed (first reply, call after "call me") · Money · Renewals in the next 90 days · Audit trail.

```text
Room: Records. Agents: Records lead, Archivist, Data analyst. Read the Records section of the spec.
Fix: the Open work wall shows Sales and Compliance tasks; Records should show its own (filing, reports, renewals).
Build:
1. Case file view: timeline of Events, Facts with superseded history, documents with versions, approvals with who and when.
2. Data analyst answers questions from the PA chat with every number linked to the rows behind it; says "not recorded" rather than estimating.
3. Weekly Monday report into the owner's brief: funnel, speed, money, broker numbers.
4. Tenancies ending in 90 days create Sales Tasks (renewal), closing the loop back to Sales.
5. Audit: read-only; void with reason instead of delete.
Tests: a renewal Task appears for a seeded tenancy ending in 60 days.
```

### Lobby · Lobby host and one rep per room

**Blocks on screen:** This week's threads by room · Playbook cards (pattern, where seen, evidence) · Proposed experiments (change, audience, period, metric) · Running experiments with results from Records · Kept and rolled back.

```text
Room: Lobby. Add a Lobby room to the floor (today it is only an orb in Front Desk). Agents: Lobby host plus one rep per room. Read the Lobby section of the spec.
Build:
1. Inputs: competitor posts already in the Studio, the office's own send-backs and lost-deal reasons, questions Rania couldn't answer, and (later, opt-in) anonymised playbooks from other offices. Never client data.
2. Weekly thread per room that ends in at most one proposed experiment: change, who it applies to, period, the Records metric to watch.
3. The owner approves an experiment; agents may not change their own instructions or any compliance setting.
4. After the period, Records reports the result; keep or roll back.
5. One idea a day can appear in the owner's brief.
Tests: an approved experiment changes a follow-up template only for its audience and period.
```

### Marketing (content studio) · Marketing lead, Brand brain

The studio is the most finished room; three fixes keep it consistent with the rest:

```text
Room: Marketing / Studio.
1. Fix the topic typo "Meet Diwan Realty" to "Realty".
2. Set the permit question default to Yes for UAE real estate, and require the permit number on any listing post before it can be approved. Confirm the rule with the office.
3. Demo data must be fictional: replace the real brokerage website in Setup with the office's own or a fictional one.
4. Every script and post goes through Review before the person approves it, like every other room.
5. A reel built from a listing depends on that listing's Facts; if the price or status changes, the script is withdrawn.
```

## Later: meeting agent and the 3D client space

Both come after the loop closes; design them now so nothing built today blocks them.

**Meeting agent** (joins Zoom, Meet or Teams calls)

- Joins as a named participant ("Diwan notes") only when the meeting owner adds it, and announces itself; recording consent is asked at the start.
- Listens silently, transcribes, and turns client statements into Facts with exact quotes and timestamps, through the same pipeline as Scribe.
- After the call: summary, decisions, action items as Tasks in the right rooms, and a follow-up draft for the broker.
- Can answer a quiet question in the side chat ("what did he say his budget was?") from Facts, never by voice unless asked.
- Built on today's Meeting page and Front Desk's meeting mode, so in-person and online meetings produce the same output.

**3D space clients can walk** (a showroom, separate from the staff office)

- A client-facing floor: a reception with Rania, project galleries, a viewing room per listing, and a meeting room where a broker or the meeting agent joins.
- Clients enter by a link from WhatsApp or a post; no staff rooms, Tasks or Facts are visible to them.
- What a client says or asks inside becomes a Fact on their Case, just like a chat message.
- Shares the 3D engine with the staff office, not its data: a separate scene and a separate permission set.

**Keep in mind now:** one Facts pipeline for chat, calls, meetings and the showroom; no meeting or 3D feature may write to the database except through Events.

# Part 3 · The full detail, as each person would live it

## Is the flow complete?

No, not yet. Parts 1 and 2 close the happy path (lead to keys and back to Sales), but a real brokerage spends half its time on the paths that don't go straight, and those had no owner. This part fills them. After it, the remaining gaps are the ones listed as open questions at the bottom of this table, which need the office's answers rather than design.

| # | Gap | Why it matters | Now covered in |
| --- | --- | --- | --- |
| 1 | Deal falls through (buyer walks, seller withdraws, mortgage refused, valuation low) | Without an exit, Cases sit in Deal forever and the brief fills with false "stuck" items | When things go wrong |
| 2 | Who the party is: company buyer, non-resident, someone acting under a power of attorney, joint owners, an estate | Each needs different documents and a different KYC; one checklist breaks on the first company buyer | Every upload |
| 3 | Co-broking with another agency (Form I, split) | Commission split and who talks to the client change | Each deal type; Finance |
| 4 | Seller side and listings in full (Form A, permit, photos, portal, price changes) | Today the flow is buyer-shaped; half the revenue is listings | Each deal type |
| 5 | Seller has a mortgage on the unit | Needs a liability letter and bank clearance before transfer; the most common delay | Each deal type |
| 6 | Tenanted units being sold | Buyer inherits the tenant; tenancy and notice rules apply | Each deal type |
| 7 | Deposit cheque held, returned or refunded | Money held for a client is the highest-risk step | When things go wrong; Finance |
| 8 | Bounced cheques (rentals) | Very common; needs a defined chase and owner decision | When things go wrong |
| 9 | Rental renewals and move-out | Renewals are repeat revenue; move-out disputes are frequent | Each deal type |
| 10 | Expiry of what was uploaded (ID, visa, pre-approval, Form A, permit) | An expired document silently invalidates a later step | Every upload; Settings |
| 11 | Client in another language (Arabic, Russian, Hindi, Chinese) | Many Dubai clients write in their own language | Settings |
| 12 | Consent and privacy (WhatsApp opt-in, data kept, data deleted on request) | Required for messaging rules and data-protection law | Settings |
| 13 | Disputes and complaints | Needs a log and an owner, not a chat | When things go wrong |
| 14 | Staff leave or are reassigned | Their Cases and PA memory must pass to someone | A day in each position |
| 15 | Commission paid by the developer (off-plan) vs by the client | Different invoices, timing and chasing | Each deal type; Finance |

**Open questions only the office can answer** (put the answers in Settings)

- [ ] Which deal types the office actually does (sales, off-plan, rentals, property management, commercial).
- [ ] Commission rates and who pays, per deal type; when it is invoiced.
- [ ] Does the office hold client money (deposit cheques), or does the seller or the trustee hold it?
- [ ] Source-of-funds and cash thresholds, as set by the compliance officer.
- [ ] Which mortgage brokers or banks the office works with.
- [ ] Languages Rania should speak.
- [ ] How long documents are kept, and who may delete them.

## Every upload, and the check that runs on it

A checklist is built from two things: who the party is (identity documents) and what the deal is (deal documents). The client portal asks only for what this party in this deal is missing. These lists are drawn from common Dubai practice; have the office's conveyancer confirm them and edit the templates in Settings.

**1 · Identity: depends on who the party is**

| Party | Uploads | Checks on upload | Expiry rule |
| --- | --- | --- | --- |
| UAE resident individual | Passport (photo page); Emirates ID front and back | Document type; name matches the Case and across both; EID number format; not expired; all corners visible, no glare | Warn 30 days before expiry; block at expiry |
| Non-resident individual | Passport; proof of address under 3 months old (utility bill or bank statement) | As above; address document dated within 3 months; name matches | Address proof re-asked if older than 3 months at transfer |
| GCC national | Passport or national ID | As above | As above |
| Joint buyers or owners | Each person's identity set; who signs what | Every owner present on every form that needs them | Per person |
| Company (onshore or free zone) | Trade licence; memorandum / articles of association; board resolution authorising this purchase or sale and naming the signatory; signatory's passport and EID; ownership declaration and IDs of anyone owning 25% or more | Licence not expired; company name identical across documents; resolution names this unit and this signatory; owners add up | Licence expiry checked at each stage |
| Company (offshore or foreign) | As above + certificate of incorporation, certificate of good standing, register of directors and shareholders, all attested and legally translated to Arabic where required | Attestation stamp present; translation attached; good standing dated recently | Good standing re-asked if older than the office's limit |
| Acting under a power of attorney | POA document; attorney's passport and EID; principal's passport | POA covers this act (buy, sell, rent) and this unit or "any property"; notarised; attested and translated if issued abroad; not revoked or expired | Block if the POA expires before transfer |
| Estate, inheritance or a minor's property | Court inheritance certificate or court approval; heirs' or guardian's IDs | Flag to a person and the office's lawyer; no automatic checklist | Lawyer decides |

**2 · Deal documents: depends on the deal**

| Deal | From the buyer or tenant | From the seller or landlord | From outside parties | Generated by the office |
| --- | --- | --- | --- | --- |
| Secondary sale, cash | Identity set; deposit or security cheque (amount and payee per the office's rule); source-of-funds documents if triggered; manager's cheque for the balance at transfer; cheques or transfer for DLD fees and commission | Identity set; title deed; tenancy contract and Ejari if tenanted; service charge clearance | Developer NOC; trustee appointment confirmation | Form B (buyer), Form A (seller), Form I if co-broked, Form F (MOU), invoices, receipts |
| Secondary sale, buyer mortgage | All of the above + mortgage pre-approval; signed valuation request; bank final offer letter; bank's manager's cheques | As above | Bank valuation report; bank's transfer documents | As above + a mortgage timeline Task list |
| Seller has a mortgage | (buyer as above) | Liability letter from the seller's bank (outstanding amount, valid date); later the bank's clearance | Seller's bank: clearance and release at transfer | Payment split showing what goes to the seller's bank |
| Off-plan from developer | Identity set; reservation form; booking payment proof; signed sales and purchase agreement (SPA); installment payment proofs | (developer) | Developer receipt; Oqood registration certificate; payment plan | Reservation summary; commission invoice to the developer |
| Off-plan resale | Identity set; payment to seller for amount paid so far + premium | Identity set; Oqood; SPA; developer payment statement | Developer NOC (developers often require a minimum paid %); developer transfer fee confirmation | Form A, B, F; invoice |
| Rental (residential) | Passport; visa / EID; rent cheques (number per agreement); security deposit cheque; employer letter if company pays | Identity set; title deed; DEWA account; POA if not the owner | Ejari registration certificate | Tenancy contract; agency fee invoice; key handover form; move-in condition report with photos |
| Rental renewal | Renewal cheques | Agreement to new rent (within the rent index rules) | Ejari renewal | Renewal contract; renewal reminder 90 and 60 days ahead |
| Listing (seller signs with the office) | (none) | Identity set; title deed; Form A; floor plan if available; keys or access arrangement for photos | Listing / advertising permit | Listing record; photo booking; portal drafts; price-change log |

**3 · The checks the portal runs, in detail**

| Upload kind | Accept when | Reject with (the message the client sees) |
| --- | --- | --- |
| Drawn signature | At least two strokes; not a single line or dot; not empty | "Please sign with your usual signature." |
| Signature photo | Dark ink on light paper; no face, no printed paragraph, no ID card shape; cropped to the signature | "This looks like a photo of \[a person / a document\], not a signature. Please sign on white paper and photograph just the signature." |
| ID or passport | Right document; name matches Case; not expired; readable MRZ / number; 4 corners | One line naming what failed: wrong document, name differs, expired, cut off, too blurry |
| Two-sided ID | Both sides uploaded | "We have the front; please add the back." |
| Title deed / Oqood | Layout matches; unit, building, community match the Case | "The unit on this deed (1204) doesn't match the one we have (1402). Is this the right deed?" |
| Signed PDF form | Every signature line signed by the right person; current form version (matches Fact versions) | "Page 2 is missing \[buyer 2\]'s signature." |
| Cheque photo | Cheque shape; amount in words and figures agree; payee matches the office rule; dated; signed | "The amount in words and figures differ." |
| Bank letter, pre-approval, offer letter | Bank name; client name; amount; validity date after the expected transfer | "This pre-approval expires on 12 Nov, before the planned transfer." |
| Proof of address | Dated within 3 months; name matches | "This bill is from June; please send one from the last 3 months." |
| Any upload | File opens; not password-protected; under the size limit; image or PDF | "We couldn't open this file; please try a photo or PDF." |

Every check is a first filter. A person sees each document in Review before it is used for anything official, and a person can override a rejection with a reason.

## Each deal type, step by step

Every step names who acts, what document it needs, what gate it passes, the Event it emits, and what the client hears; a step with no client message is silent on purpose. Steps marked *(M)* apply only when the buyer has a mortgage; *(SM)* only when the seller has one.

### Secondary sale (resale of a ready unit)

| # | Step | Who | Document | Gate | Event | Client hears |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Listing exists (Form A signed, permit live) | Ops | Form A, title deed, permit | Seller KYC started | `listing.ready` | Seller: "Your listing is live." |
| 2 | Buyer enquires, qualifies, views | Sales | Form B before the first viewing | Form B signed | `viewing.done` | "Here are the details of tomorrow's viewing." |
| 3 | Offer made | Broker | Offer as a Fact (price, terms, quote) | None | `offer.made` | Seller: "An offer of AED X came in." |
| 4 | Counter / accept | Broker, seller | Each counter as a Fact | Seller's acceptance quoted | `case.converted` | Both: "Offer accepted. Next: the MOU." |
| 5 | Co-broke agreed (if another agency) | Deal | Form I | Split recorded | `cobroke.agreed` | (none) |
| 6 | KYC both sides | Compliance | Identity sets | Screening clear | `compliance.cleared` or `needs_info` | Portal request if missing |
| 7 | *(SM)* Seller's liability letter | Deal | Liability letter | Valid past transfer date | `doc.received` | Seller: "Please request a liability letter from your bank." |
| 8 | *(M)* Valuation and final offer | Deal, bank | Valuation, final offer letter | Valuation ≥ price, or the gap covered | `mortgage.final_offer` | Buyer: updates at each bank step |
| 9 | MOU drafted from Facts | Deal | Form F | Review passed; owner approved | `form.ready` | (none) |
| 10 | MOU signed by both, deposit given | Client portal | Signed Form F; deposit cheque | Signatures valid; cheque checked | `doc.received`, `payment.marked_received` | "MOU and deposit received, thank you." |
| 11 | Developer NOC requested | Ops | NOC application; service charge clearance | Charges cleared | `noc.received` | Seller: "NOC requested; usually takes a few working days." |
| 12 | Transfer booked | Ops | Trustee appointment | All gates on current Facts | `transfer.booked` | Both: date, place, what to bring (list) |
| 13 | Cheques prepared | Finance, client, bank | Manager's cheques: seller, *(SM)* seller's bank, DLD fees, commission | Amounts match the payment split | `funds.ready` | Buyer: exact cheque list with payees |
| 14 | Transfer completes | Person at trustee | New title deed | A person marks complete | `transfer.completed` | Both: "Congratulations, the transfer is done." |
| 15 | Invoice and commission | Finance | Invoice, receipt | Payment marked | `payment.marked_received` | Receipt |
| 16 | Handover | Ops | Keys, access cards, DEWA move | Checklist done | `case.closed` | Buyer: welcome note; ask for a review |
| 17 | Aftercare | Records, Sales | (none) | (none) | `renewal.due`, `referral.asked` | 30 days later: "How's the new home?" |

### Off-plan from a developer

| # | Step | Who | Document | Gate | Event | Client hears |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Project shared; unit picked | Sales | Availability and price list from the developer (dated) | Price list current | `unit.held` | Unit, price, payment plan |
| 2 | Reservation | Deal | Reservation form; booking payment proof | Payment to the developer's account only, never the office | `case.converted` | "Unit reserved until \[date\]." |
| 3 | KYC | Compliance | Identity set | Cleared | `compliance.cleared` | Portal request if missing |
| 4 | SPA signed | Client, developer | SPA | All pages signed | `doc.received` | "SPA received." |
| 5 | Oqood registered | Developer, Ops tracks | Oqood certificate | Present | `oqood.received` | "Your unit is now registered." |
| 6 | Commission invoiced to the developer | Finance | Invoice per the developer's agreement | Developer's trigger met (often a % paid by the buyer) | `invoice.sent` | (none) |
| 7 | Installments tracked | Finance | Payment proofs | Due dates | `installment.due` | Reminder 14 and 3 days before each installment |
| 8 | Handover at completion | Ops | Handover notice, snag list | Final payment | `case.closed` | Snagging appointment |

### Rental

| # | Step | Who | Document | Gate | Event | Client hears |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Tenant qualifies, views | Sales | (none) | (none) | `viewing.done` | Viewing details |
| 2 | Offer: rent, cheques, move-in | Broker | Offer as Facts | Landlord accepts (quoted) | `case.converted` | "The landlord accepted." |
| 3 | Documents and cheques | Client portal | Identity set; rent cheques; deposit cheque | Cheques checked; dates and amounts match Facts | `doc.received` | "Cheques received." |
| 4 | Contract | Deal | Tenancy contract from Facts | Review; both sign | `form.signed` | "Contract signed." |
| 5 | Ejari | Ops | Ejari application up to Submit | A person submits | `ejari.ready` | Ejari certificate |
| 6 | Agency fee | Finance | Invoice; receipt | Marked received | `payment.marked_received` | Receipt |
| 7 | Move-in | Ops | Keys; condition report with photos | Both acknowledge | `case.closed` | Welcome; DEWA steps |
| 8 | Cheque dates tracked | Finance | Each cheque's date | (none) | `cheque.due` | Landlord: deposit reminder |
| 9 | Renewal | Sales | Renewal terms | 90 days before end | `renewal.due` | "Your lease ends on \[date\]; shall we renew?" |

### Listing (a seller signs with the office)

| # | Step | Who | Document | Gate | Event | Client hears |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Seller enquiry, valuation | Sales | Comparable sales from Records | (none) | `valuation.sent` | Suggested price range with comparables |
| 2 | Form A signed | Deal | Form A, title deed, identity set | Seller KYC | `listing.signed` | "Thanks, we're preparing your listing." |
| 3 | Permit and photos | Ops | Permit application up to Submit; photo booking | A person submits | `listing.ready` | Photo date |
| 4 | Live on portals and in the Studio | Ops, Marketing | Portal listing; reel scripts | Review; permit number on every ad | `listing.live` | Link to the listing |
| 5 | Weekly seller report | Records | Views, enquiries, viewings, feedback | (none) | `seller.report` | Weekly summary |
| 6 | Price change | Broker, seller | Seller's instruction as a quoted Fact | Supersedes the old price | `fact.superseded` | Every ad, script and form using the old price is withdrawn |
| 7 | Offer received | Sales → Deal | Continues as secondary sale step 3 |  |  |  |
| 8 | Form A about to expire | Deal | Renewal | 14 days before | `form.expiring` | "Your listing agreement ends soon; renew?" |

## When things go wrong

Every unhappy path ends in one of three places: the Case continues with changed Facts, the Case closes as lost with a reason, or a person decides. No unhappy path ends with the Case sitting still. Money and legal outcomes are always a person's call; agents prepare the options.

| What happens | Detected by | What the office does | Who decides | Case ends |
| --- | --- | --- | --- | --- |
| Client corrects themselves (price, payer, finance, unit) | New Fact contradicts an old one | Correction rule: Compliance first, dependent work withdrawn, forms recalled | Compliance officer, then broker | Continues |
| Buyer goes quiet after the offer | No reply past the follow-up ladder | Broker call Task, then owner brief; the seller is kept informed | Broker | Continues or lost ("no response") |
| Buyer walks away after the MOU | Buyer says so (quoted) | Deposit handling per Form F terms prepared as options; seller told; listing reactivated | Owner with the office's lawyer | Lost; listing back to live |
| Seller withdraws after the MOU | Seller says so (quoted) | Same, reversed; buyer offered alternatives | Owner with the lawyer | Lost; buyer back to Sales |
| *(M)* Mortgage refused | Bank letter | Options: another bank, more cash, cancel per MOU terms | Buyer, broker | Continues or lost |
| *(M)* Valuation below price | Valuation report | Gap shown (price − valuation); options: renegotiate, cover in cash, cancel | Buyer and seller | Continues with new Facts, or lost |
| *(SM)* Seller's liability letter expires | Expiry date | New letter Task before transfer | Seller | Continues |
| Developer NOC refused or delayed (unpaid charges, minimum % not paid) | Developer response | Seller asked to clear; transfer date moved; both told | Seller | Continues |
| Screening hit or unclear source of funds | Compliance | Case on hold; client told only "we need more information" (never the reason) | Compliance officer | Continues, or blocked and closed by the officer |
| Payment from a third party | Finance at Mark received | Compliance first; receipt held | Compliance officer | Continues |
| Cheque bounced (rental) | Landlord or person marks it | Tenant told within 24h; replacement deadline; landlord informed; owner brief | Landlord | Continues, or landlord's legal route |
| Commission not paid (developer or client) | Invoice overdue | Reminder ladder; owner brief; dispute log | Owner | Stays open in Finance; Case otherwise closed |
| Co-broker dispute over the split | Either agency | Form I and the Event log as evidence | Owners of both agencies | Finance holds the split |
| Client complaint | Any channel; words like "complaint", "unhappy", "lawyer" | Complaint record with quotes; owner told the same day; no agent reply beyond acknowledgement | Owner | Separate complaint record |
| Wrong document uploaded and accepted | Review or a person | Document voided with reason; client asked again; dependent steps reopened | Person | Continues |
| Staff member leaves | Owner deactivates the account | Their Cases and Tasks reassigned in one step; their PA's preferences archived, not deleted; clients told who their new broker is | Owner | Continues |
| Client asks to delete their data | Client message | Request logged; data deleted except what the law requires the office to keep; client told what was kept and why | Owner, compliance officer | Closed |
| Client asks to stop messages | "Stop" in any language | Stop all automated messages on all channels; brokers may still reply if the client writes | (automatic) | Continues without automation |

**Lost reasons** (a dropdown, so Records can count them): price, finance refused, valuation, found elsewhere, changed mind, no response, compliance, seller withdrew, other (with note).

## A day in each position

Testing the design from each chair shows what each person must see and what their PA must do without being asked. If a person needs to open more than two screens to do the usual thing in their day, the design is missing a block.

| Person | 08:00 | During the day | End of day | Their PA does unasked | Must never have to |
| --- | --- | --- | --- | --- | --- |
| Owner | Nova greets, top 3, brief: urgent, money, decisions waiting | Meetings in Pocket mode; approves from cards; asks "how's the Marina deal?" | 2-line wrap: what closed, what's stuck, tomorrow's first thing | Prepares decisions with options; chases overdue staff Tasks; flags anything legal or compliance | Search for a document; retype a client's words; approve something without seeing what it rests on |
| Broker (Omar) | Omar's PA: calls to make, viewings, quiet clients, call-now items | Calls from the queue; viewings with the client's last messages; records voice notes after visits | Outcome for every call; tomorrow's viewings confirmed | Books viewings in free time; drafts follow-ups; reminds 15 min before calls; nudges for missing outcomes | Fill a form from scratch; chase documents by hand; wonder who called a client last |
| Sales lead | Team board: leads per broker, call-now response times, unassigned leads | Reassigns, coaches, reviews hot leads | Team numbers; escalations | Escalates unanswered call-now items; daily sweep per broker | Ask each broker for a status update |
| Deal coordinator | Deals board: missing items per deal, items waiting on outsiders | Sends portal links; reviews uploads; answers client questions on documents | Every deal has a next step and date | Sends the follow-up ladder; rebuilds checklists after corrections; prepares Form F from Facts | Check a signature or ID by eye first; retype prices into forms |
| Operations | Portal drafts ready to Submit; appointments today | Submits drafts; attends trustee appointments; handovers | Transfers marked complete | Fills portals up to Submit; tracks NOC and trustee; reminds clients what to bring | Search for which form version is current |
| Finance | Due today, overdue, payments to mark | Marks received; approves invoices; prepares payouts | Cash summary | Drafts invoices from Facts; reads proofs and flags mismatches; chases overdue invoices | Calculate VAT or commission splits by hand |
| Compliance officer | Corrections, screening hits, holds, cases needing source of funds | Decides hits; asks for documents; signs off risk | Open holds with reasons | Runs screening; compares the money story with documents; drafts reports | Discover a payer change after the transfer |
| Marketing | Scripts to approve; listings needing content | Approves scripts; shoots | Posts scheduled | Researches competitors; writes scripts from listing Facts; withdraws scripts when a price changes | Post an ad without a permit number |

**When someone is away:** a person sets out-of-office; their PA tells clients who is covering, the room lead's PA reassigns Now items, and nothing waits in an absent person's queue for more than the owner's limit.

## Owner settings, and what every upload stores

Every number or rule mentioned in this spec lives in one Settings page, so agents never hard-code a policy. One setting, read everywhere.

**Settings**

| Area | Settings |
| --- | --- |
| Office | Name, licence numbers, TRN, address, working hours, quiet hours, Friday prayer window, public holidays, languages Rania speaks |
| People | Staff, roles, rooms they see, display names (used by Rania and signatures), who covers whom, PA names |
| Sales | Qualifying forms per intent, heat-score rules, call-now response limit (default 10 min), follow-up schedule, lead routing (round-robin, by area, by language) |
| Deal | Checklist templates per deal type and party type, document expiry warnings, follow-up ladder (24 / 48 / 72h), portal link lifetime |
| Money | Commission rates per deal type and payer, VAT, invoice triggers, deposit rule (who holds it), payout split rules, reminder schedule |
| Compliance | Thresholds (source of funds, cash), screening lists, high-risk rules, the named officer, retention period, who may delete |
| Messaging | WhatsApp templates (approved), opt-in record, stop words in each language, which messages need approval |
| Marketing | Permit required (default Yes for UAE real estate), brand voice, posting hours |
| Review | Which items need Review and owner approval; who may approve what amount |
| Limits | Model spend limits, stuck thresholds (days per stage), escalation chain |

**What each upload stores** (one Document record)

| Field | Example |
| --- | --- |
| case\_id, party\_id, role | Case 118, Sara Malik, buyer |
| kind | passport, eid\_front, eid\_back, title\_deed, form\_b, form\_f, cheque, pre\_approval, liability\_letter, poa, trade\_licence … |
| file, pages, hash | stored file and a fingerprint so a re-upload of the same file is noticed |
| uploaded\_by, channel, at | client via portal, 2026-10-31 11:02 |
| extracted | name, number, dates, amounts, unit, as read |
| check\_result | passed / failed + each reason / overridden by whom and why |
| expires\_at | from the document; drives warnings |
| satisfies\_task | the checklist Task it closes |
| based\_on\_facts | for generated forms: the Fact ids and versions used |
| status | current / superseded / voided (with reason) |
| reviewed\_by, at | the person who saw it in Review |

With this part, every step from first message to keys, and every common way off that path, has an owner, a document, a gate, an Event and a client message. What remains open is the office's own answers in the checklist at the top of Part 3.

# Part 4 · Closing the last gaps, so the AI never has to guess

## Cases still missing after Part 3

A second pass, reading the spec as a broker, a client and a coding AI, found 16 more cases. Each now has a short flow; the ones marked *Phase 2* are designed here but built after the main loop works.

| # | Case | Flow | Room | Phase |
| --- | --- | --- | --- | --- |
| 1 | Same person writes on WhatsApp and Instagram | Match on phone, email or name + listing; propose a merge to the broker; never merge automatically when two brokers own them | Sales | 1 |
| 2 | Two brokers claim the same client | First owner keeps it unless the Sales lead reassigns; the claim and decision are logged | Sales | 1 |
| 3 | New listing matches waiting buyers | On `listing.live`, match against qualified buyers' Facts (area, beds, budget); brokers get a list; Rania may send it only with the broker's yes | Sales, Records | 1 |
| 4 | Viewing logistics | Key or access arranged with the seller or tenant (tenant notice), confirmation to the client 24h and 2h before, broker travel time | Sales, Ops | 1 |
| 5 | Viewing no-show | Broker marks no-show; Rania sends one reschedule message; second no-show lowers the heat score | Sales | 1 |
| 6 | Viewing feedback | Broker voice note or Rania asks the client the next day; feedback is a Fact; seller report includes it | Sales | 1 |
| 7 | Several offers on one unit | All offers listed side by side for the seller with quotes; seller's choice quoted; others told politely | Sales, Deal | 1 |
| 8 | Rental move-out | Tenant notice (as a Fact), move-out inspection with photos vs move-in report, deductions proposed with photos, landlord approves, deposit return tracked, Ejari cancellation | Ops, Finance | 1 |
| 9 | Rent increase at renewal | Broker checks the official rent index and the allowed increase; the result goes to the landlord with the source | Sales | 1 |
| 10 | Client asks about visas, returns, legal or tax | Rania gives no advice or promises; states that a specialist will answer; broker Task | Sales | 1 |
| 11 | Off-plan payments into escrow | Payment instructions always come from the developer's documents; Rania never sends bank details from chat; any change of account details is a Compliance flag | Deal, Compliance | 1 |
| 12 | Broker's own licence expiring | Broker licence number and expiry in People settings; warn 30 days before; an expired broker can't be assigned new Cases | Front Desk | 1 |
| 13 | Mortgage broker referral | Referral recorded with consent; referral fee is a Finance line | Deal, Finance | 1 |
| 14 | Off-plan snagging at handover | Snag list with photos; developer fix Tasks; re-inspection | Ops | 2 |
| 15 | Property management (ongoing landlord service) | Rent collection, maintenance requests, landlord statements, annual renewals | New Property management room | 2 |
| 16 | Commercial property and holiday homes | Separate checklists and permits | Deal | 2 |

**Fraud guard (applies everywhere):** any message asking to change bank details, pay a different account, or send money urgently is never acted on by an agent; it raises a Now flag to Finance and Compliance and is confirmed by phone with a known number.

### Listing upkeep: permits and "is it still available?"

A live listing is checked on a schedule so nothing expired or already sold stays advertised. Every check ends in one of three results: still available (dates refreshed), changed (new Facts, ads updated), or gone (every ad withdrawn the same day).

| What | When | Who acts | What happens |
| --- | --- | --- | --- |
| Advertising permit expiring | 14 and 3 days before expiry (settings) | Ops; broker's PA reminds the broker | Renewal application prepared up to Submit; a person submits. On the expiry day with no renewal, every portal ad and Studio post for that unit is paused automatically and the broker is told |
| Form A (listing agreement) expiring | 14 days before | Deal; seller asked by WhatsApp | Renew or close the listing (`listing_expiring` stage) |
| Ready unit: still available? | Every 7 days for sale, every 3 days for rent (settings), and before any viewing is booked | Broker's PA messages the seller or landlord: "Is 1204 Marina Crest still available at AED 2.4M?" | Yes: listing refreshed with today's date. Price or status changed: recorded as a Fact that supersedes the old one, so every ad, script and buyer list using it updates or is withdrawn. Sold or let elsewhere: listing withdrawn everywhere, matched buyers told, Case closed as lost (reason: sold elsewhere) |
| No answer from the owner | 48 hours after the check | Broker Task to call | After the owner's limit with no answer, the listing is marked unconfirmed: no new viewings, ads paused |
| Listing not refreshed on a portal | Portal's own refresh rule (settings) | Ops | Refresh drafted; a person confirms |
| Off-plan price list | When the developer sends a new one, or after 14 days | Sales | Prices older than the limit are shown as "to be confirmed" and Rania won't quote them |
| Tenant moving out of a let unit | On tenant notice | Sales | Re-listing prepared 60 days before the unit is free, with the landlord's yes |

Events added to the catalog for this: `permit.expiring`, `permit.expired`, `listing.check_due`, `listing.confirmed`, `listing.unconfirmed`, `listing.withdrawn`. Consumers: Ops, Sales, Marketing (pauses posts) and Records (the seller's weekly report shows when the listing was last confirmed).

## Case stages: the only allowed list

A Case is always in exactly one of these stages, and moves only on the event named. Any other stage name in the code is a bug; any move not listed here is refused and logged. Two side states can apply at any stage: **on\_hold** (Compliance or owner; the Case keeps its stage and nothing binding may happen) and **nurture** (client not ready; follow-ups only).

**Shared start: Sales**

| Stage | Owner room | Enters on | Leaves to | Leaves on |
| --- | --- | --- | --- | --- |
| new | Sales | first message, portal lead, manual add | discovering | Rania's first reply |
| discovering | Sales | Rania's first reply | qualifying, nurture, not\_a\_lead | intent known (`case.intent_set`) |
| qualifying | Sales | intent known | qualified | owner's form complete |
| qualified | Sales | form complete | viewing / valuation (seller) | viewing booked |
| viewing | Sales | viewing booked | offer | `offer.made` |
| offer | Sales | offer made | converted | `case.converted` (other side's acceptance quoted) |

**Sale (ready unit)**

| Stage | Owner room | Enters on | Leaves to | Leaves on |
| --- | --- | --- | --- | --- |
| documents | Deal | `case.converted` | cleared | all identity and deal documents in, checks passed |
| cleared | Deal | `compliance.cleared` on current Facts | mou\_signed | Form F signed by both, deposit `payment.marked_received` |
| mou\_signed | Deal | Form F signed | transfer\_ready | NOC, *(M)* final offer, *(SM)* liability letter, Review, owner approval |
| transfer\_ready | Operations | `deal.ready_for_transfer` | transfer\_booked | trustee slot submitted by a person |
| transfer\_booked | Operations | `transfer.booked` | transferred | person marks `transfer.completed` |
| transferred | Finance + Ops | `transfer.completed` | closed\_won | commission received and handover done |

**Off-plan**

| Stage | Owner room | Enters on | Leaves to | Leaves on |
| --- | --- | --- | --- | --- |
| reserved | Deal | booking payment marked | spa\_signed | SPA received |
| spa\_signed | Deal | SPA received | registered | Oqood received |
| registered | Finance | Oqood received | handover\_due | final installment marked, completion notice |
| handover\_due | Operations | completion notice | closed\_won | snagging done, keys handed |

**Rental**

| Stage | Owner room | Enters on | Leaves to | Leaves on |
| --- | --- | --- | --- | --- |
| documents | Deal | `case.converted` | contract\_signed | cheques and IDs checked, contract signed |
| contract\_signed | Operations | contract signed | moved\_in | Ejari submitted by a person, keys handed |
| moved\_in | Finance | keys handed | tenancy\_active | agency fee received |
| tenancy\_active | Records | fee received | renewal\_due / move\_out | 90 days before end / tenant notice |
| renewal\_due | Sales | `renewal.due` | tenancy\_active / move\_out | renewal signed / not renewed |
| move\_out | Operations | tenant notice | closed\_won | deposit settled, Ejari cancelled |

**Listing (seller side)**

| Stage | Owner room | Enters on | Leaves to | Leaves on |
| --- | --- | --- | --- | --- |
| listing\_signed | Deal | Form A signed | listing\_live | permit approved, photos, Review |
| listing\_live | Sales | `listing.live` | under\_offer | offer accepted |
| under\_offer | Deal | offer accepted | joins the Sale stages from documents | `case.converted` |
| listing\_expiring | Deal | Form A 14 days to expiry | listing\_live / closed\_lost | renewed / not renewed |

**Endings:** `closed_won` and `closed_lost` (with a lost reason). Every Case in a final stage still feeds aftercare and renewals; a closed Case is never reopened, a new linked Case is created instead.

## Event catalog: the only events rooms may use

These are the only event names; a room may not invent one without adding it here first. Every event also carries `case_id`, `actor` (agent or person), `at`, and `fact_ids` with versions.

| Event | Emitted by | Consumed by | Extra payload |
| --- | --- | --- | --- |
| `message.received` | Channels (WhatsApp, Instagram, portal, web) | Sales | channel, text, media |
| `case.created` | Sales | Records, Front Desk | source channel, listing if any |
| `case.intent_set` | Sales | Records | intent (buy, sell, rent, let, manage, not\_a\_lead) |
| `case.merged` | Sales (person confirms) | All rooms | merged\_from |
| `fact.recorded` | Sales, Scribe, Front Desk, meeting agent | Compliance (if money/identity), Records | quote, source |
| `fact.superseded` | Any room recording a correction | Compliance first, then every room with dependent Tasks | old\_fact, new\_fact |
| `task.created` / `task.done` / `task.reopened` | Any room | Owner room, Front Desk | owner\_room, assignee, due, depends\_on\_facts |
| `call.requested` | Sales | Broker's PA, Sales lead | requested time or now |
| `viewing.booked` / `viewing.done` / `viewing.no_show` | Sales | Records, Ops (access) | listing, time |
| `offer.made` / `offer.countered` | Sales | Deal, the other party's broker | amount, terms |
| `case.converted` | Sales (broker) | Deal, Compliance, Finance, Records | deal type, party types |
| `case.lost` | Any owner room | Records, Sales (nurture) | lost reason |
| `cobroke.agreed` | Deal | Finance | other agency, split |
| `doc.requested` / `doc.received` / `doc.rejected` | Deal (portal) | Owner of the Task, Review | kind, check result |
| `form.ready` / `form.sent` / `form.signed` / `form.recalled` | Deal, Ops | Review, client portal | form kind, version, fact\_ids |
| `compliance.cleared` / `compliance.needs_info` / `compliance.blocked` | Compliance | Deal, Finance, Front Desk | scope, reason (internal) |
| `screening.hit` | Compliance | Compliance officer only | list, match score |
| `mortgage.preapproved` / `mortgage.final_offer` / `mortgage.refused` | Deal | Compliance, Finance | bank, amount, expiry |
| `review.requested` / `review.passed` / `review.sent_back` | Any room / Review | Review / owner room | item, findings |
| `approval.given` / `approval.declined` | A person | Owner room | item, pinned fact versions |
| `deal.ready_for_transfer` | Deal | Operations | transfer date wanted |
| `noc.received` / `transfer.booked` / `transfer.completed` | Ops (person marks) | Finance, Records, Front Desk | date, trustee |
| `ejari.ready` / `listing.ready` / `listing.live` | Ops | Sales, Marketing | permit or Ejari number |
| `invoice.sent` / `payment.marked_received` / `payment.flagged` | Finance | Deal, Compliance, Records | amount, method, payer, proof |
| `cheque.due` / `cheque.bounced` / `installment.due` | Finance | Sales (client message), Front Desk | amount, date |
| `renewal.due` / `form.expiring` / `doc.expiring` | Records | Sales, Deal | expiry date |
| `case.closed` | Ops or Finance | Records, Sales (aftercare) | outcome |
| `complaint.opened` | Any room | Owner | quote |
| `experiment.approved` / `experiment.ended` | Lobby / Records | All rooms affected | change, audience, metric |
| unit.held | Sales (off-plan) | Deal, Records | developer, unit, hold expiry, price list date |
| listing.signed | Deal (Form A signed) | Ops, Compliance, Marketing | unit, asking price, Form A expiry |
| valuation.sent | Sales (seller valuation) | Records, Deal | range, comparables used |
| seller.report | Records (weekly) | Sales (broker sends it) | views, enquiries, viewings, feedback, last confirmed date |
| oqood.received | Deal / Ops | Finance, Records | registration number, date |
| funds.ready | Finance (person confirms the cheque list) | Ops, Compliance | each cheque: payee, amount |
| referral.asked | Sales (aftercare) | Records | referral name if given, consent |

**Rule:** every event in this table must have at least one consumer in code. The HQ Stuck board lists any event emitted with no consumer, which is how a broken handoff becomes visible on day one.

## No-guess rules, definition of done, and the scenarios to test

No spec covers every case a real office will meet, so the last piece is a rule for what the coding AI does when it reaches the edge of the spec: it stops and writes the question down, it doesn't invent. Paste this block at the top of every command in Part 2.

```text
Rules for building Diwan (read before any change):
1. The spec is the source of truth: Part 1 (rooms), Part 3 (documents, steps, unhappy paths, settings) and Part 4 (stages and events). Only the stages and events listed in Part 4 may be used.
2. If something you need is not in the spec (a stage, an event, a threshold, a document, a rule, a client message), do NOT invent it. Add it to docs/open-questions.md with the file and line where you needed it, use a clearly named placeholder setting, and carry on with the rest.
3. Every number, rate, threshold, schedule or template is a setting read from Settings, never a constant in code.
4. Agents never pay, sign, submit to a portal, file a report, clear a screening hit or mark money received. If your change would let an agent do any of these, stop and report it.
5. No room calls another room's functions. Rooms emit and consume events from the catalog only.
6. Every client-facing message is either inside the 24-hour WhatsApp window or an approved template; otherwise create a broker Task.
7. If two parts of the spec disagree (a stage, an event, a document, a rule), do not pick one: add both to docs/open-questions.md and build neither until answered.
8. Use only fictional people and companies in seed data and tests.
9. Finish each task with: what changed, the tests you added and ran, anything you added to open-questions.md, and anything you could not do.
```

**Definition of done for each room** (all must be true)

- [ ] The room shows only its own stats, Tasks, Facts and Stuck items.
- [ ] Every event the room consumes in the catalog has a handler, and every event it emits has a consumer.
- [ ] Every Task assigned to an agent in the room starts within 5 minutes or shows why it is blocked.
- [ ] The room's PA answers "what's waiting on me?" correctly for each role that can see the room.
- [ ] Every way out of the room (happy and unhappy) from Parts 3 and 4 has a test.
- [ ] The correction rule works for this room: superseding a Fact reopens only this room's dependent work.

**Seed scenarios** (fictional; each one is a Playwright test that runs end to end)

| Scenario | Proves |
| --- | --- |
| Sara, resident, cash buyer, secondary 2-bed; corrects the payer to her brother | Happy path + correction rule + third-party payer to Compliance |
| Karim, non-resident, mortgage buyer; valuation comes in AED 150,000 below price | Mortgage stages, valuation gap options, renegotiation as superseded Facts |
| Al Noor Trading LLC buys through a director with a board resolution | Company KYC, ownership declaration, resolution check |
| Priya sells under a power of attorney; her unit has a mortgage and a tenant | POA check, liability letter, tenanted sale |
| Omar's buyer walks after the MOU | Lost path, deposit options to the owner, listing back to live |
| Tenant Ahmed: 4 cheques, one bounces; renews next year; moves out the year after | Rental lifecycle, bounced cheque, renewal, move-out and deposit |
| Off-plan buyer Lina: reservation, SPA, Oqood, installments, developer commission | Off-plan stages and developer invoicing |
| A selfie uploaded as a signature, an expired passport, a deed with the wrong unit | Upload checks and re-upload messages |
| A WhatsApp lead and an Instagram lead from the same phone | Duplicate detection and merge by a person |
| "Please send the deposit to this new account" | Fraud guard: Now flag, no agent action |

**Honest status:** with Parts 1 to 4, the lifecycle from first message to keys, renewal and move-out has a defined stage, event, document, gate and owner at every step, including the common failures. What is still not defined is listed in two places, on purpose: the office's own answers (Part 3's checklist) and Phase 2 items (property management, commercial, holiday homes, snagging, the meeting agent, the 3D showroom). The list of Dubai documents and rules is from common practice, so have the office's conveyancer and compliance officer confirm it before going live.

# Part 5 · Every PA, in full, and the whole lifecycle on one page

## What every PA has (the shared kit)

All PAs are the same engine with a different role, so the coding AI builds the kit once and configures it per role.

| Part of the kit | What it is | Limits |
| --- | --- | --- |
| Reach | Chat on every page, voice (push-to-talk on phone, wake word on desktop), WhatsApp to the person's own number, push notifications | Speaks only to its own person; never to clients except through Rania or an approved message |
| Knowledge | Cases, Facts, Tasks, Documents and Events the role may see (Part 2 table); the calendar; the office's knowledge base; Settings | Says "not recorded" instead of guessing; cites the record behind every answer |
| Memory | The person's preferences as settings: working hours, call windows, tone, language, what to brief first | Viewable and editable by the person; archived, not deleted, when they leave |
| Morning brief | Built at the person's start time from overnight Events | Max 5 items before "more" |
| Reminders | Any "remind me" becomes a Task with a due time | Respects quiet hours unless the item is Now |
| Drafting | Messages, emails, forms, invoices, summaries, from Facts | Every draft shows the Facts it used |
| Doing | Schedule, book viewings in free time, create and assign Tasks, fill portals up to Submit, search Records | Asks before anything a client or outsider will see |
| Handoff | "Tell Finance…" creates a Task or Event for that room | Through Tasks and Events only, never PA-to-PA chat |
| Escalation | Overdue Task: nudge the person, then their lead's PA, then Nova | Escalation chain from Settings |
| Never, for any PA | Pay, sign, submit, file a report, clear a screening hit, mark money received, approve on the person's behalf, change Settings, send bank details | Hard-coded refusals, logged |

## Each PA

| PA (serves) | Does unasked | Answers / does when asked (examples) | Asks first | Ends its day by |
| --- | --- | --- | --- | --- |
| **Nova** (owner) | Greets on arrival; morning brief across all rooms; flags compliance holds, overdue money, unanswered call-me, stuck deals; Pocket meeting mode; weekly Monday numbers; one Lobby idea | "How's the Marina deal?" "Who hasn't called Sara back?" "Book my trip from this email." "Draft a reply to Ahmed." "Remind me Thursday to call the developer." | Any send, booking, purchase, approval | 2-line wrap: closed today, stuck, first thing tomorrow |
| **Broker's PA** (each broker) | Today's calls, viewings and quiet clients; call-now alerts; reminders 15 min before calls; drafts follow-ups; nudges for missing outcomes; listing availability checks with owners; permit and Form A expiry reminders for their listings | "Book Sara a viewing Thursday after 4." "What did Karim say about budget?" "Send him the 3 closest options." "Log: viewing done, liked the view, worried about service charges." | Every client message, offer or document sent | Every call has an outcome; tomorrow's viewings confirmed with clients and owners |
| **Sales lead's PA** | Team board; escalates unanswered call-now after 10 min; daily sweep per broker; unassigned leads; duplicate leads to merge; listing-to-buyer matches | "Who's slowest to call back this week?" "Give Omar's leads to Layla while he's away." "Which hot leads have no viewing?" | Reassigning a client, changing routing | Team numbers; leads with no next step |
| **Deal coordinator's PA** | Missing items per deal; sends follow-up ladder; rebuilds checklists after corrections; prepares Form F from Facts; expiry warnings on uploaded documents; waiting-on-outsider aging | "What's missing for Sara's deal?" "Send Karim the portal link again." "Has the bank sent the final offer?" | Sending forms; overriding a failed upload check | Every deal has a next step and a date |
| **Operations PA** | Portal drafts ready to Submit; trustee and NOC tracking; reminds clients what to bring; permit renewals drafted; handovers and move-outs scheduled; recalls forms after corrections | "Book the trustee for next Tuesday." "What does Sara need to bring?" "Prepare Ejari for 1204." | Every Submit (always a person); messages to developers or government | Transfers and Ejaris marked; tomorrow's appointments confirmed |
| **Finance lead's PA** | Invoices drafted at each trigger; due and overdue lists; reads payment proofs and flags mismatches; cheque dates; installment reminders; commission splits and payout list | "What's outstanding from developers?" "Mark AED 50,000 received from Sara" (opens the form for the person to confirm). "What do I owe brokers this month?" | Sending invoices and reminders; the person confirms every Mark received | Cash summary: in today, due tomorrow, overdue |
| **Compliance officer's PA** | Corrections side by side; screening hits; source-of-funds files ready; holds with reasons; report drafts; threshold alerts; fraud-guard flags | "Why is Sara's deal on hold?" "What did she say about where the money comes from?" "Draft the cash report for Case 118." | Any request for documents from a client; every draft report | Open holds and hits waiting for a decision |
| **Marketing PA** | Scripts to approve; listings needing content; competitor posts worth a look; pauses posts when a permit expires or a listing is withdrawn | "Make 3 reels for 1204 Marina Crest." "What worked for competitors this week?" | Every post (and Review first) | Posts scheduled for tomorrow |
| **Rania** (clients, not a PA) | Replies within the 24h window; qualifies; books viewings; sends portal links and receipts; follow-ups on schedule | Client questions about listings, the process and documents | Anything outside the knowledge base: advice on visas, returns, legal, tax goes to the broker | (always on) |

## Marketing: the full lifecycle

Marketing's job is to bring in leads Sales can close, and its loop closes only when every lead is traced back to the post, ad or listing that brought it, and Records tells Marketing what actually turned into deals. Agents: **Marketing lead** (the Marketing PA), **Brand brain**, Research, Planning, Scripting, Production, Editing, Publishing (as on the floor today).

**Content stages** (one per piece of content; only these names)

| Stage | Owner | Enters on | Leaves on |
| --- | --- | --- | --- |
| idea | Planning | Lobby idea, competitor signal, new listing (`listing.live`), price change, a topic the owner sets | Brief approved by the person |
| briefed | Planning | Brief approved | Script drafted |
| scripted | Scripting | Three scripts, each from its own Facts (listing, service or topic) | Person picks one; Review passed |
| in\_production | Production, Editing | Script picked | Final cut ready (video, captions, cover, permit number on screen and caption) |
| ready | Publishing | Final cut + Review passed + permit valid | Person approves the post and its time |
| scheduled | Publishing | Approved | Posted (by a person, or auto-post only if the owner switched it on) |
| live | Publishing | Posted | Paused, withdrawn or archived |
| paused | Publishing | Permit expired, listing unconfirmed, or price changed | Fixed (back to ready) or withdrawn |
| withdrawn / archived | Publishing | Listing sold, Fact superseded, or the campaign ended | (final) |

**Events for Marketing** (part of the catalog): `content.idea`, `content.briefed`, `content.scripted`, `content.ready`, `post.approved`, `post.live`, `post.paused`, `post.withdrawn`, `campaign.started`, `campaign.ended`, `lead.attributed`. Marketing consumes `listing.live`, `fact.superseded`, `permit.expired`, `listing.withdrawn`, `listing.unconfirmed`, `experiment.approved`.

**Closing the loop with Sales and Records**

1. Every post, ad and portal listing gets a tracked link or a code word ("reply MARINA").
2. When a lead arrives from a comment, DM, link or code, Sales records `lead.attributed` on the Case: which post, campaign or listing brought it.
3. Comments and DMs that are buying questions go straight to Sales as `message.received`; Marketing doesn't answer them.
4. Records reports per post and campaign: reach, leads, qualified leads, viewings, deals, commission, and spend if any.
5. Each week the Marketing PA tells the person what brought deals, not only views, and the Lobby turns that into the next experiment.

**Campaigns and spend** (paid ads, if the office runs them)

- A campaign has a goal, audience, budget, dates and the content it uses; spend is a setting with a hard cap.
- Agents may draft ads and audiences; a person launches and pays.
- A campaign whose cost per qualified lead exceeds the owner's limit is flagged in the brief.

**Rules that make it safe**

- No post goes live without a valid permit number (UAE real estate; confirm the rule with the office), Review passed and a person's approval.
- Every price, size or claim in a post comes from a current Fact; a superseded Fact pauses the post.
- No promises of returns, visas or price rises; Review rejects them.
- Competitor content is studied, never copied; music and footage must be licensed or the office's own.
- Fictional people and companies only in demos.

**Marketing PA's day:** morning list of posts to approve, listings without content, competitor posts worth a look, yesterday's leads by source; during the day drafts briefs and scripts on request; end of day, tomorrow's schedule and anything paused with the reason.

**Marketing definition of done:** a post's leads appear on the right Cases with their source; a price change pauses every post that used the old price within minutes; a permit expiry pauses every post for that unit; Records shows deals and commission per post.

## Departments not covered (by choice)

HR and hiring, payroll, office admin, IT and vendor management are outside Diwan's scope. Two pieces of them are covered because the deal flow depends on them: staff accounts and roles (Part 2) and broker licence expiry (Part 4).

## The whole lifecycle on one page

Each line is a stage group from Part 4; every arrow is an event from the catalog. Step 0 runs all the time: Marketing attracts leads with posts, ads and listings, each traced to the Cases it brings in (\`lead.attributed\`), and Records reports back which content produced deals.

1. **First contact** (Sales): any channel → `message.received` → Case created → Rania discovers intent → duplicates proposed for merge.
2. **Qualify** (Sales): owner's form, Facts with quotes → heat score → call-now or call-later Tasks for the broker → nurture if not ready.
3. **Match and view** (Sales): options and listing matches → viewing booked with access arranged → reminders → feedback as Facts → no-show handling.
4. **Offer** (Sales → Deal): offers as Facts, several offers side by side → acceptance quoted → `case.converted`.
5. **Paperwork** (Deal): checklist by deal type and party type → client portal uploads with instant checks → signatures → receipts on WhatsApp → follow-up ladder.
6. **Gates** (Compliance, Finance, Review, owner): KYC, screening, source of funds, payment checks, mortgage steps → Review → owner approval pinned to Facts.
7. **Official steps** (Operations): NOC, trustee, Ejari, permits filled up to Submit → a person submits → `transfer.completed` or contract signed.
8. **Money** (Finance): invoices from Facts → payments marked by a person → client receipts → commission splits and payouts.
9. **Handover** (Operations): keys, access, utilities, condition report → `case.closed`.
10. **Living with it** (Records, Sales): rental cheques, renewals at 90 days, move-out and deposit, listing availability checks and permit renewals, aftercare messages, referrals → new linked Cases.
11. **Off the path** (any room): corrections, walk-aways, refusals, bounced cheques, complaints, fraud guard, staff changes, data requests, each with a defined ending.
12. **Learning** (Lobby, Records): send-backs, lost reasons and competitor signals → experiments the owner approves → measured, kept or rolled back.

## Each department's own lifecycle

Every department runs two loops: the work that flows through it Case by Case, and the rhythm it keeps every day, week and month. Both are listed so the coding AI builds the scheduled jobs as well as the event handlers.

| Department | Starts on | Its own steps | Ends by handing to | Daily | Weekly / monthly |
| --- | --- | --- | --- | --- | --- |
| Front Desk (owner) | The owner's day; any event marked for the owner | Greet → brief → meetings (Pocket) → decisions → errands → wrap | Tasks to any room; approvals to owner rooms | 07:30 brief; end-of-day wrap | Monday numbers; monthly owner review: revenue, pipeline, people, experiments |
| Marketing | `listing.live`, a topic, a competitor signal, a Lobby idea | idea → briefed → scripted → in\_production → ready → scheduled → live → paused / withdrawn / archived | Sales (`message.received`, `lead.attributed`) | Approvals; posting; pause anything with an expired permit or old price | Weekly: leads and deals per post; monthly: campaign results, spend vs cap, content plan for next month |
| Sales | `message.received`, portal lead, referral, renewal | new → discovering → qualifying → qualified → viewing → offer → converted / lost / nurture | Deal (`case.converted`); Records (`case.lost`) | Call-now queue; broker sweep 08:30; follow-ups; listing availability checks | Weekly: quiet clients, listing-to-buyer matches, seller reports; monthly: renewals due in 90 days |
| Deal | `case.converted`, `listing.signed` | checklist built → portal links → uploads checked → forms signed → gates passed → ready for transfer | Operations (`deal.ready_for_transfer`) | Missing items; follow-up ladder | Weekly: deals stuck by days in stage; monthly: Form A and document expiries |
| Compliance | `case.converted`, `fact.superseded`, `payment.marked_received`, name or payer change | KYC → screening → risk rating → source of funds → (EDD) → cleared / needs info / blocked | Deal, Finance (`compliance.*`) | Hits and holds for the officer | Weekly: re-screen open Cases; monthly: report drafts, threshold review, document retention |
| Finance | Invoice triggers, `payment.marked_received`, cheque and installment dates | draft invoice → approve → send → remind → mark received → receipt → split commission → payout | Deal (deposit received), Records | Due today, overdue, mark received | Weekly: chasing list; monthly: close the month, commission payouts, VAT figures for the accountant |
| Operations | `deal.ready_for_transfer`, form Tasks, listing and rental signings, tenant notices | prepare form or portal draft → person submits → book appointment → attend → mark done → handover or move-out | Finance and Records (`transfer.completed`, `case.closed`) | Today's appointments; drafts to submit | Weekly: waiting-on-outsiders aging; monthly: permit renewals due |
| Review | `review.requested` from any room | check quotes, numbers, completeness, authority, promises, holds → card → passed / sent back | The requesting room; the person who approves | Queue under the owner's time limit | Weekly: send-back patterns to the Lobby |
| Records | Every event | file → index → answer questions → report → raise renewals and expiries | Sales (`renewal.due`), Deal (`doc.expiring`), Front Desk (reports) | Expiry and renewal scan | Monday report; monthly: funnel, speed, money, per-broker numbers; yearly: retention clean-up approved by the officer |
| Lobby | Send-backs, lost reasons, competitor signals, outside playbooks | thread → proposal → owner approves → experiment runs → Records measures → keep / roll back | Every room affected (`experiment.*`) | One idea for the brief | Weekly threads per room; monthly: experiments kept and rolled back |

**How the departments chain into one office:** Marketing feeds Sales; Sales feeds Deal; Deal pulls in Compliance and Finance as gates and Review before the owner; Operations does the official steps; Finance and Operations close the Case; Records turns closed Cases into renewals, expiries and reports that feed Sales, Marketing and the owner; the Lobby improves every room; Front Desk keeps the owner on top of all of it. A department with nothing coming in, or with work and no one to hand it to, shows on the HQ Stuck board.

**Is it done?** As a specification, yes: every stage, event, document, check, PA duty and failure path above has an owner and a defined ending, and anything the spec doesn't cover is caught by the no-guess rule instead of being invented. What remains is not design but answers and building: your office's settings (Part 3 checklist), confirmation of the Dubai document lists by your conveyancer and compliance officer, and the Phase 2 items.
