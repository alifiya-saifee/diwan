# Diwan: problems found, fixes made and what is still open

As of 2 Nov 2026. Covers the work done with Claude Code on this laptop: Sales, logins, Nova, the owner's WhatsApp and the full browser test.

**Where things stand**

- The last full browser run was stopped on request, partway through the older flows. It passed 469 of 493 checks.
- Everything since commit `a9c794f` is uncommitted and sits in the working folder, including most fixes from the browser test.
- The real office (8030) and test office (8031) still run code from before the latest fixes.
- The fixes below are not all equally proven. Each one says how it was checked.

**How a fix was checked**

| Mark | Meaning |
|---|---|
| Browser | Passed in the last full browser run, in the real pages |
| Earlier | Passed when it was built, not re-run in the last browser run |
| Code tests | Passed automated tests only |
| Live Muse | Passed against the real model, outside the browser run |

---

## 1. Not resolved

### 1.1 Failing in the last run

| # | Problem | What is known | What is not known | Next step |
|---|---|---|---|---|
| 1 | **Conversations disappeared during the page walk.** The count went from 3 to 0 right after "Send" in the Ask your PA box on the 3D office page. 16 Inbox checks then failed for Layla and Omar, because Convert, Merge, Open the deal, Record a meeting and similar need a conversation to open. | The same failure happened in the previous run. An earlier run was clean, and pressing buttons one at a time on a fresh office did not reproduce it. Reset was not pressed. The log is append-only, so a display or visibility fault is more likely than lost data, but that is unproven. | The cause. "Send" is only the last press before the drop, not a proven cause. The check also uses the signed-in owner's session, so the session itself needs ruling out. | Repeat the walk on a saved copy and inspect the log and `/api/chats` at the moment it drops. Treat as serious until explained. |
| 2 | **Closing the deal failed: Form B stayed unsigned.** 41 passed, 6 failed. The paperwork gate stopped, which blocked the NOC, Layla's approval and the invoice. | It passed 56 of 56 in the previous run. Downloads also ran 10 fewer checks (49 against 59), possibly for the same reason. | Whether this is a recent change or timing in the run. | Rerun the closing flow alone and read the Form B step. |
| 3 | **"A 2 bed flat" was saved as "Not sure" on WhatsApp.** One recorded-meeting check failed on this. | The value was already "Not sure" before the meeting began, so the meeting did not change it. With the same script, the other run saved Apartment. Rania asked "apartment, villa or townhouse?" and the client answered "Buying, to live in" first. | Whether that answer caused it, or the model simply varied. | Test a later clear answer replacing "Not sure". |
| 4 | **Two older browser flows stopped partway.** `deal_flow` waited for a record code "(F7)" in a Nova answer. `rooms_flow` could not find a Form F step. | These look like old test steps, because Nova's answers changed. | Not confirmed as test faults. They could be real. | Read each one against the current app. |
| 5 | **One property check failed** (`property_flow`, 21 of 22). | Only the total was read. | Which check, and why. | Read the log. |
| 6 | **Two code tests fail** in `tests/test_lobby_room.py`. | "+6 days" isn't next week when the tests run on a Monday. | | Fix the test's date. |
| 7 | **Browser pages crashed twice.** The 3D office crashed once in a single-page test, and the Nova questions run crashed once at question 93. | Neither repeated. Memory stayed low in the questions run, at 3 to 5 MB. | The cause. Repeated 3D loads with video recording is a guess. | Watch for it recurring. |

### 1.2 Not finished in the test plan

| # | Item | State |
|---|---|---|
| 8 | 9 of the 14 older flows were never run, and `front_door_flow` was cut off. | Not run: calendar, call, visit, office, people, Lobby, profile, quiet and own-time flows. |
| 9 | Off-plan and rental, start to finish, with each operation type. | Only partly covered. The planned scripts for these were not written. |
| 10 | Each of Rania's decisions forced one by one, Layla's message controls, each reminder type, minutes against known answers, Lobby meeting room. | Partly covered by other runs, not case by case. |
| 11 | Every sales condition, tested on both sides of its limit. | Not done as a set. |
| 12 | Case studies 2 to 6 (off-plan, rental, messy client, early exits, trouble). | Not run as written. Only case 1 ran in full. |
| 13 | Full owner's day after the latest changes. | Last result 135 of 139, before those changes. |

### 1.3 Known faults and gaps

| # | Problem | Effect |
|---|---|---|
| 14 | A nudge held past the 24-hour window with no template chosen is skipped, and only the log records it. | A client can silently get no follow-up. The owner must choose a template, and the app should show the skip. |
| 15 | Answering the scribe's "which one?" question changes no fact. | The answer is lost. |
| 16 | Read-backs are lost when the server restarts. | A pending yes disappears. |
| 17 | A client changing a viewing through Rania may move it automatically. | This could bypass the agent confirming the viewing. |
| 18 | Live recordings lose some speech at the end. | Stopping closes the connection straight away. The last runs heard at least 4 of 5 sentences, but the last words remain at risk. |
| 19 | Weak Nova replies: "Book me a flight" lists options without saying she can't book. "Call Mona" implies she can arrange it. "asdfgh" gets "I'm here". | Misleading, but nothing wrong is recorded. |
| 20 | Asked to pay the owner's mum, Nova refuses but offers Ahmed in Finance. | Mixes personal money with the office's. |
| 21 | Noise on a Live call can still get a reply, and each ignored fragment costs a model call. | Annoyance and cost. |
| 22 | Nova's own voice on laptop speakers can cut her off. Headphones avoid this. | Only tested with a stand-in voice for interrupting. |
| 23 | Arabic on Live is not supported; listening is set to English. | Arabic speakers can't use Live. |
| 24 | Live speech passes through Google or Microsoft in Chrome and Edge. | Matters around confidential client talk. |
| 25 | Nova's replies were slow at times: about 25 seconds in one day's test, on Meta's side. | She now says "One moment" after 7 seconds. |

**Still open in `docs/closed-loop-checklist.md`, not rechecked in this round:**

- The owner's "Viewing as" records actions under the other person's name.
- `POST /api/approvals` accepts any approver name.
- `DIWAN_AUTH=off` opens everything, and nothing stops it on a public address.
- A scheduled post goes out even if the listing has since changed.
- Any `%PDF` file may count as a signed form. `real_pdf` was added since, so this needs checking.
- Follow-ups after a visit may send the general text. The checklist still marks this open, though the follow-up run passed.

### 1.4 Waiting for a decision or someone outside

| # | Item | Who |
|---|---|---|
| 26 | **Revoke two old Instagram tokens** printed into a chat by mistake (`IGAA...` and `EAAh...`), then delete them from `.env`. Confirm whether this was done. | Owner |
| 27 | Compliance after the deal and before the deposit: confirm the order is correct. | Compliance officer |
| 28 | "Invalid number": it could not be found anywhere in the app. A screenshot or page name is needed. | Owner |
| 29 | The `after_viewing` WhatsApp template needs real approval. It is a sample today. | Owner, Meta |
| 30 | Client documents are unencrypted on disk, with no retention rule. Decide before hosting. | Owner |
| 31 | Decision D3: demo data holds a real brokerage's website, listings and branding. | Owner |
| 32 | Test chats are in the real office and Nova chases staff about them. Removing them needs a clean-up step. | Owner |
| 33 | Check Ali Rahman's agreed price of AED 20,000 against a budget of about 2 million. | Owner |
| 34 | Hosting: a public address, backups, HTTPS and a UAE region, with legal advice on data residency. | Owner |

### 1.5 Not built, or needs an outside account

- **Real WhatsApp:** nothing has run on it yet. It needs UAE support, AiSensy coexistence confirmed, a public address and a third number for Nova.
- **Email:** built, but needs the mailbox in `.env`. No real email has been sent.
- **Not connected:** Google or Outlook calendar, reading the inbox, flight and hotel booking, Instagram DMs, Facebook, TikTok, real phone push, and trustee, DLD, payment and sanctions services.
- **Not built:** dismissing an item from Nova's list, stuck deals on her watch list, naming her and setting her voice, notices on staff's own WhatsApp, her replying alone to plain client questions, WhatsApp group chats, Zoom assistant, phone calls.

---

## 2. Resolved

### 2.1 Sales flow and viewings

| Problem | Resolution | Checked |
|---|---|---|
| Rania booked a viewing alone, with no agent, no confirmed place and the client still in Qualifying | Rania asks and the agent confirms, on a place that is cleared | Browser |
| Compliance started at the first WhatsApp message | Compliance starts after the deal and before the deposit | Browser |
| Offers moved the stage by hand with nothing recorded | Offers, counter-offers and acceptance are recorded | Browser |
| "Stop" was ignored when a broker had the chat, and brokers could still message | "Stop" always counts; broker messages are blocked unless the client writes again | Earlier |
| A question mark unlocked listings early | Only a real question does | Earlier |
| "Saturday morning" and "Thursday instead" dead-ended | She offers that day's times and keeps the old booking until the client picks | Earlier |
| "Omar will contact you" with no alert behind it | An alert is always raised if none is open | Earlier |
| "The view is lovely" made a false hot lead | No longer hot | Earlier |
| Unsure clients treated as buyers; "just looking" not parked | Parked in Nurture | Earlier |
| "The second one" not understood | Refers to the list just shown | Code tests |
| First message fixed in code | The owner writes it, in English and Arabic | Earlier |
| No photos with options | Each option has a photo and description. Real WhatsApp needs `PUBLIC_BASE_URL` | Earlier |
| Follow-ups counted from the last message, not the appointment | 1, 3, 6 and 9 days from the appointment, and the owner can change them | Earlier |
| Two brokers could show the same unit at the same time | Rania, the calendar and adding by hand all refuse | Live Muse |
| Spam, job seekers, low budgets and visa or legal questions were mishandled | Each has its own handling | Earlier |
| "Pay this new account" | Goes to Finance and Compliance, and no agent acts on it | Live Muse |
| Lost leads kept open call cards | Lost clears them with a note | Browser |
| Follow-up after a viewing had no fixed wording or time | `after_viewing` template and a clock checked at 23 hours | Browser |

### 2.2 What talk changes on the record

| Problem | Resolution | Checked |
|---|---|---|
| "Maybe" or someone else's price changed the budget | Hearsay and "maybe" are skipped on every route | Browser, 36 of 36 |
| "Maybe" moved the stage | The not-sure answer no longer applies to money talk | Browser |
| "Dina's neighbour paid 9 million" through Nova changed the budget | Blocked, with or without a word like "my" or "a" | Browser |
| "Sorry, I meant 4 million, not 3" changed nothing in a meeting | Reads the correction | Browser |
| Meetings never updated the qualification form | They do, with a client's new budget and bedrooms | Browser |
| Pocket meeting's yes didn't reach the client's file | The yes goes to the read-back | Browser |
| "Mona said I'll pay it myself" | Goes to the client's file as the client's words, after a yes | Browser |

### 2.3 Meetings and recording

| Problem | Resolution | Checked |
|---|---|---|
| Live speakers came back as "A" and "B", so the first speaker was assumed to be the broker | Roles are read from what's said, and the page has "Swap broker and client" | Browser, both speaking orders |
| A broker's "villa" changed the client's property type | Only the client's words count | Browser |
| A broker's promise became a client fact | Not a fact now | Browser |
| Football talk could become a fact | Not a fact | Browser |
| Only some spoken turns were heard (3 of 5, then 1 of 5) | At least 4 of 5 heard in both runs, and all 5 in the client-first run. Part of the cause was the test audio, which now has silence at the end. See item 18 | Browser |
| Nova didn't know what was said in meetings | She answers from the last meeting or visit | Browser |
| No way to record a client refusing consent | A refuse button records nothing and points to written notes | Code reviewed only |

### 2.4 Nova

| Problem | Resolution | Checked |
|---|---|---|
| The first reply had no voice | Voice code rewritten | Browser |
| Fixed keyword replies: "I'm not sure" to normal questions | Muse thinks with the whole office in view and keeps the conversation | Browser, 113 of 113 |
| "Delete all the leads" was queued, and "ok" sent it | Refused | Browser |
| "Move Dina to Viewed" became a message to Nadia | She says plainly she doesn't move stages | Browser |
| Her own voice approved a draft | A yes must be short and tied to what she asked | Live Muse |
| "Reply to Ahmed saying..." counted as a yes | Only a real short yes counts | Live Muse |
| Polite "Could you approve...?" slipped past the refusal | Refused | Live Muse |
| "expect" triggered the payment tracker and a false "Muse not connected" | Trigger words inside a question no longer interrupt | Live Muse |
| She promised actions that never happened ("I'm about to block...") | If it fails, she says nothing has been done | Live Muse |
| "The whole day", "Tomorrow." and "Early morning" weren't understood | All handled | Live Muse |
| Reminders set twice, or at the wrong time | One reminder, moved rather than repeated | Live Muse |
| No notebook | Add, read, cross off, clear, private to each person | Earlier |
| She couldn't be interrupted, and she repeated the question | Mic stays open, and results start with the answer | Stand-in mic only |
| Formatting read aloud, and she heard herself | Formatting removed; her own words are ignored | Stand-in mic only |
| "Who hasn't called their leads back?" came out garbled | Gives "Calls owed" or says nobody owes one | Browser |
| She didn't know who's on shift or in the Pool | Both are in what she can see | Browser |
| Staff could see beyond their own area through her | Each person's PA sees only their part | Browser |
| Call cards bounced every 10 minutes after reaching the Pool | Stops at the Pool | Earlier |
| Rashid's task linked to flights | She's told a shared word isn't a link. Not proven against the real card | Live Muse, partly |
| Two chat boxes on one page | One way to reach her on each page | Earlier |
| Nova changed Settings by chat | Refuses and points to the Team page | Earlier |

### 2.5 Owner's WhatsApp

| Problem | Resolution | Checked |
|---|---|---|
| Sales and personal could merge | Three separate lines; personal messages stay in a private file | Live Muse |
| Alerts about every message | She raises the matter only when it matters: 50 of 50, no emergency missed | Live Muse |
| Saving a number by hand | Removed; the page works like WhatsApp | Earlier |
| Family left out of an answer | Fixed and passed the recheck | Live Muse |
| Nothing goes without a yes | 0 messages sent without one | Live Muse |

### 2.6 Logins, safety and documents

| Problem | Resolution | Checked |
|---|---|---|
| No logins, and everyone saw every page | Logins, roles and department privacy enforced on the server | Browser |
| Brokers saw each other's leads | Their own leads and the Pool only | Earlier |
| Reset had no protection | Owner only, and it asks first | Code tests; Reset was not pressed in the browser |
| Client IDs and signed forms were open by link | Limited to the deal team (`deal_guard`, `file_guard`) | Browser |
| Downloaded signed copy might not be a real file | Checked as a real PDF | Browser, last full pass 59 of 59 |
| Passports and Emirates IDs: were they saved? | Saved and checked in the browser in the last full pass. See item 30 on encryption | Browser |
| A screening hit closed itself; people could go past Compliance | Now a hold that blocks the deal | Marked done in the checklist, not rechecked here |
| Receipts named the wrong payer, and payments couldn't be undone | Fixed | Marked done in the checklist, not rechecked here |
| Document reminders ignored "stop" and quiet hours | Same rules as other messages | Marked done in the checklist, not rechecked here |

### 2.7 Pages and test run

| Problem | Resolution | Checked |
|---|---|---|
| Settings page too long | Sidebar, one section at a time | Earlier |
| Refresh wiped what someone was typing | Fixed | Earlier |
| A timing bug behind the "stop" test (failed 8 of 25) | Uses log order, not the clock; passed 25 of 25 | Code tests |
| A deal term with no amount crashed the work list | Fixed | Earlier |
| Calendar Print froze the test for two hours | A test fault, not the app; the print dialog is stubbed in the test | Browser |
| The test run used up the USD 5 limit | Owner moved budget from Marketing, so Nova now has USD 15 and the test stops at USD 14 | Done |

---

## 3. Last test results

| Area | Previous run | Last run |
|---|---|---|
| Case 1, chat to deal | 53 of 53 | 53 of 53 |
| Closing the deal | 56 of 56 | **41 passed, 6 failed** |
| Downloads and signed copies | 59 of 59 | 49 of 49 |
| Every page and button | 105 passed, 16 failed | 105 passed, 17 failed |
| Talk changing the records | 29 passed, 7 failed | 36 of 36 |
| Follow-ups and "call me" | 50 passed, 1 failed | 51 of 51 |
| Nova's questions | 112 passed, 1 failed | 113 of 113 |
| Recorded meeting, broker first | 8 passed, 1 failed | 11 of 11 |
| Recorded meeting, client first | 6 passed, 3 failed | 10 passed, 1 failed |
| **Total** | | **469 passed, 24 failed** |

- **Older flows:** sales room 21 of 21, property 21 of 22, deal and rooms stopped partway, the rest not finished.
- **Code tests:** 1082 passed, 1 skipped, 2 failed (the Lobby date, item 6).
- **Spend:** USD 12.23 of the USD 15 for Nova and Sales, 4.33 of 10 for Marketing.
- **Limits of these results:** a pass means the check held. In the last run the replies were checked by the rules, not read one by one, and earlier reading did find faults that the checks had passed. WhatsApp, trustee, DLD, payments and sanctions lists were stand-ins.
