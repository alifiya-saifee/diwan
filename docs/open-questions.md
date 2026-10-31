# Open questions

The spec's rule: where it is silent or disagrees with itself, write the question down instead of inventing an answer. This
file is that list for the Deal, Operations, Finance and Compliance rooms. "Decided" means built that way on 31 Oct 2026 so
the rooms work; each one is the recommended option and can be overruled. Numbers are settings: the owner changes them in
the Deal desk's rules without any code.

## Decided for now, to confirm

| # | Question | Decided | Who confirms |
|---|---|---|---|
| D1 | The spec's event names or the code's? | Old events stay (the log can't be rewritten). New work uses the spec's names, and key moments add one (`case.converted`, `case.lost`, `case.closed`). | Product owner |
| D2 | A fixed stage list or the owner's? | The owner's stages stay. A fixed list can be mapped on top later. | Product owner |
| D6 | Withdrawn or reopened? | Open work is withdrawn and made again, as today. `task.reopened` is used when a person undoes something. Clearance and owner approval go stale on a replaced Fact. | Product owner |
| D7 | Which corrections reach Compliance first? | Money facts, and now price too. | Compliance officer |
| D9 | Must commission be paid before closing? | Yes, as today. | Product owner |
| D23 | The NOC needs ready-for-transfer and ready-for-transfer needs the NOC | The NOC is an ordinary step before the gate. The trustee booking is what waits for ready-for-transfer. | Conveyancer |
| D25 | When are Forms A and B made? | At conversion, as today. | Conveyancer |
| D28 | When does an off-plan deal close? | Before handover, on purpose: our commission is paid long before. | Product owner |
| D31 | What is Form F, and in what order? | Signed first, then submitted. Compliance clears before anyone signs it. | Conveyancer |
| D33 | Who sees documents first? | The compliance officer, as today. | Compliance officer |
| D34 | Keep rejected uploads? | No, as today. A rejection can't be overridden yet. | Compliance officer |
| D35 | Follow-up ladder and expiry warning | The spec's: 24, 48, 72 hours, and 30 days. Both are settings. | Product owner |
| D38 | Does a held third-party deposit unblock Deal? | No. It counts once Compliance has looked at it and the receipt goes out. | Compliance officer |
| D41 | Screen before KYC or after? | Before, as today: stricter. | Compliance officer |

## Placeholders in the rules, to set

| Setting | Placeholder | Why it needs an answer |
|---|---|---|
| `sof_threshold_aed` | 0: source of funds asked on every deal | The compliance officer's threshold |
| `broker_share_pct` | 50 | What brokers keep of our commission; the spec doesn't say |
| `invoice_due_days` | 30 | Payment terms |
| `invoice_reminder_days` | 1, 7, 14 days after the due date | The owner's schedule |
| `invoice_trigger` per path | ready: transfer completed; rental: tenancy signed; off-plan: by hand once the developer owes it | When the office bills |
| `lost_reasons` | The spec's list plus "sold elsewhere" | D21 |
| `docs_by_party` | Common Dubai practice | The conveyancer confirms the lists |
| `good_standing_days` | 180 | The office's limit (the spec gives none) |

## Front Desk and Sales, decided 31 Oct

The first four are the owner's answers. The rest were built the recommended way, to confirm.

| # | Question | Decided | Who confirms |
|---|---|---|---|
| D16 | Which brokers see which chats? | Own leads and the Pool. Rashid and the owner see all. **The owner's decision.** | Done |
| D14 | The call timer | 10 minutes (a setting), then the next free broker, then the Pool at 60. **The owner's decision.** | Done |
| Form | The longer qualifying form | Every question the spec lists counts, and "not sure" is accepted. **The owner's decision.** | Done |
| D11 | Checks before a viewing | Instant booking stays. Form B stays at conversion. **The owner's decision.** | Done |
| D13 | Who is the Sales lead? | Rashid, a person, with his own PA. | Product owner |
| D15 | Heat score or the owner's triggers? | Both: the score shows on every lead, and makes it hot only if the owner ticks it. | Product owner |
| D17 | After "stop", if the client writes again | Rania stays silent; a card goes to a person, who may reply. | Product owner |
| D18 | New fits to past clients | The Sales room needs the broker's yes. The older follow-up that mentions a new fit still sends by itself. | Product owner |
| D19 | The same person on two channels | Proposed on the same email or full name, because Instagram gives no phone. | Product owner |
| D21 | Lost reasons | The spec's list, in the Inbox and after a call. A Lost lead can still come back with a reason. | Product owner |
| D49 | Meeting mode, now or Phase 2? | In-person notes now. Joining Zoom stays later. | Product owner |
| D50 | Morning brief | Ready 07:30 with an 08:00 briefing. Top 3 first. Broker's list at 08:30, a setting. | Product owner |
| Time zones | "In the client's time zone" | Only when they name one. Their phone's country is not used: many clients in Dubai keep a foreign number. | Product owner |
| Names | Who attends a site visit? | The lead's broker only: they have the client and are the point of contact. The listing's agent is told, so the keys reach them. **The owner's decision.** | Done |
| Working days | Which days the brief runs | Monday to Saturday, a setting. **The owner's decision.** | Done |

## Open, not built

- D3: the demo database holds a real brokerage's data. Needs a clean snapshot.
- D4: deleting a client's data against an append-only log. Needs a lawyer.
- D5: qualifying answers as Facts. Their words are kept with each answer, but a corrected answer does not yet trigger the correction rule. A Fact relayed by the owner does.
- D8: Review standing before every approval, Marketing included.
- D20: several offers on one unit. One live deal per listing stays.
- D39: "my brother will pay part of it". Two live payers are still treated as a contradiction.
- D40: who holds a deposit, and returning it. The options are prepared for the owner when a deal is lost; nothing moves money.
- Listing side (seller signs up, Form A first, permits, photos): not a deal path yet.
- Off-plan resale and commercial: not built.
- Mortgage figures: the steps exist, the amounts are not tracked.
