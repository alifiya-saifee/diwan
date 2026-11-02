# Closed-loop work: what was done, what was proven, what is left

Covers the sessions of 31 Oct to 2 Nov 2026. Dates in this file are the working dates of that session.

The short version: the journey from a WhatsApp chat to a closed deal works, signed in as the real people. The Lobby room exists. An investigation then
found serious gaps that are **not fixed yet**, including a confidentiality leak in the PA. The fix plan is written and waiting for approval.

## 1. What was built

### Understanding the spec

- `docs/closed-loop-spec.md`: the Closed-Loop Office spec, kept in the repo.
- `docs/closed-loop-checklist-detail.md`: every line of the spec checked against the code (1,955 lines).
- `docs/closed-loop-checklist.md`: the working checklist, updated as rooms were finished.
- `docs/open-questions.md`: decisions taken to keep building, and who confirms each.

### Deal, Operations, Finance and Compliance rooms

**Compliance**
- Clearance is tied to the current facts, so a changed price or payer makes it stale.
- Blockers, risk rating, high-risk sign-off, block, needs-information, suspicious transaction report draft.
- Payment patterns held before a receipt: cash at the limit, crypto, third party, several parts.

**Finance**
- Marking money: amount, method, day, payer, proof amount, reference.
- Part payments, undo with a reason, release approval.
- Receipts, invoices, commission and payouts, write-off.
- A deposit expected on every converted ready sale, even if the client never mentioned one.

**Operations**
- Paperwork steps, Form F, portal drafts, trustee booking, recall of a sent form, closing.

**Deal**
- Five gates before anything binding, computed from the record. Only the owner's approval is an act.
- Documents by party type, a 24, 48 and 72 hour ladder, expiry warnings, renewing links.
- Drawn signatures on a phone, with selfies refused.
- `diwan/client_msgs.py`: one way out to clients, respecting "stop", quiet hours and WhatsApp's 24 hours.
- `diwan/deal_gates.py`: the gates.

**Other**
- Bugs found by real runs and fixed: no deposit on chat deals, half-filled forms wiped by a refresh, the wrong price in the convert box, clearing with no
  documents, and the PA button covering Cancel.
- "Whose property": which property a deal is on, ours or another agency's, and the bigger Converted display in the Inbox.

### Room 9, the Lobby

- `diwan/lobby_room.py`, `diwan/lobby_api.py`, `web/lobby.html`, and the room on the 3D floor. A host and a rep from each of the 9 rooms.
- Weekly threads written by rules from the log. Each ends in at most one proposal. No model is called.
- Five kinds of experiment: a follow-up message, a qualifying question, a checklist step, a content idea, an agent's instructions.
- The owner approves and can edit first. Half the audience gets the change; the other half is the comparison.
- At the end of the period the change stops by itself, Records reports, and the owner keeps it or rolls it back. Rolling back leaves the office as it was.
- One idea a day in the owner's brief, and a monthly tally.
- Guardrails: compliance rules and settings can't change from the Lobby; Compliance and Review agents' instructions can't change; no promises of returns; no client names,
  numbers or emails.
- The staff board that shared the name now shows as "Requests board".

### Testing as the real people

The earlier browser runs had sign-in turned off. `e2e/people_flow.py` and `AUTH=1 e2e/chat_to_close_flow.py` run with real logins, a browser per person. That found and fixed:

| Problem | Who it hit |
|---|---|
| One-press "Received" skipped amount, method and payer, so cash or a stranger's money could miss Compliance | Finance |
| Brokers, Finance and Operations could read screening matches on the Deal desk | Compliance |
| The owner could clear a deal recorded as Priya | Audit trail |
| The owner's Deal desk opened as Priya, hiding her own buttons | Owner |
| Finance or Compliance could prepare Form F | Deal |
| Any new event wiped what a broker was typing in the Inbox | Sales |

Paying more than expected now asks first.

## 2. Last proven results

| Check | Result | Note |
|---|---|---|
| Full journey, signed in | 57 of 57 | |
| People, money, confidentiality, wrong-person cases | 68 of 68 | After the first run's 4 failures were fixed |
| Four rooms | 35 of 35 | Failed once, then passed |
| Property | 22 of 22 | |
| Lobby | 19 of 19 | |
| Deal desk flow | 113 of 114 | With longer waits, on a busy PC. The miss, a transfer step, was read correctly on the real screen |
| Automated tests | 1,036 passed, 2 failed, 1 skipped | Both failures in Marketing, in files another session was editing; not investigated |
| Office flow | Not rerun in full after the Inbox fix | The failing send worked 4 of 4 |

The PC ran out of memory during testing (140 MB free of 16 GB), which caused false timeouts. Later failures on that day should be read with that in mind.

## 3. The investigation: what does not work yet

Nothing in this section is fixed. Traced from the code; the PA questions were also run in an offline office.

### Worst first

1. **The PA leaks to brokers.** A broker asking "any report on Karim?" got the suspicious transaction report and its grounds. The tests missed it.
2. **Sellers and landlords are never screened.**
3. **A client's bank statement never counts as funds proof**, because of a capital-letter mismatch.
4. **Split cash isn't added up, and a cash report can be missed.** Off-plan payments lose their flags entirely.
5. **A broker's follow-up can reach the Pool within 60 minutes,** and another broker claiming it changes who gets the commission.
6. **Listing-side deals bill the buyer.**
7. **A write-off blocks closing forever.**

### What you asked about

| Area | Today |
|---|---|
| Document follow-ups | The ladder runs. Faults: the link can drop out after 24 hours; lost deals keep being chased; part-uploads skip the broker and owner steps |
| Form links to the client | Not sent automatically: a person copies each one |
| Unsigned forms | No reminder at all |
| Signature on the form | Saved and filed, but stacked at the end, on Diwan's own layout, not the real RERA or DLD form |
| Instalment follow-ups | Can't be added by anyone. No reminder after the due date. Bounced and post-dated cheques can't be recorded. Schedules can't be edited |
| Invoices | The PDF is real but rebuilt every time and never saved |
| Sending invoices | The person sends them. Supplier invoices don't exist |
| The deal PA | Can't answer what's missing, who signed, gates or invoice status |
| 3D rooms | Cards and robots follow real events. Compliance walls show no clearance or holds; the Deal room is nearly empty |
| Owner's "Acting as" | Offers buttons that are refused and hides her own. Caused by the sign-in fix above |

### Deal types

Only ready sale, off-plan and rental exist. Agency-to-agency works one way. Listing side is partial. Commercial and off-plan resale are missing.

The full step-by-step investigation, with every role and tab, is in the plan: `C:\Users\Lenovo\.claude\plans\partitioned-gathering-lighthouse.md`. Its first step is to
write that here as `docs/deal-investigation.md`, with one row per button.

## 4. Still simulated

Bank feed, sanctions lists, DLD and developer portals, reading IDs, live WhatsApp and email. To go further, these are needed from outside: a live WhatsApp line with approved templates,
an email account, and the blank RERA and DLD forms.

## 5. Decisions to confirm

In `docs/open-questions.md`: D1 to D41 for the rooms, L1 to L6 for the Lobby, A1 to A4 for who reads what. The compliance officer should confirm what people outside Compliance may see.
Placeholders still need real numbers: the broker's share (50%), the source-of-funds threshold, and invoice triggers.

## 6. Mistakes made along the way

- A script overwrote another session's untracked checklist. It was recovered from that session's transcript, and new files are now opened so they can't overwrite.
- Servers were reported as stopped when only their shell had closed.
- A test server link was reported as live and then stopped working.
- "Signed-in staff are locked out" was stated from reading code and turned out wrong for staff. The real fault was the owner's.
- A confidentiality check looked for one test phrase and so reported the PA as safe. It wasn't.

## 7. Where the code is

Everything above is on `main`. It went there through other sessions' commits, not a push from this one. Other sessions' newer local work is not part of this report.
