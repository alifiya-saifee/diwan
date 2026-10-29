# Deal desk: spec and definition of done

Session 3 (Review, Compliance, Finance, Operations). Contract: `docs/rooms.md` section 3, "Back office". Checklist:
`docs/sessions.md` section 3. This file says what "done" means for each checklist item and how it is checked in the
browser. Written 29 Oct 2026.

## Who uses it

| Person | Role | Comes to the Deal desk to |
|---|---|---|
| Priya | Compliance officer | see what changed about money first; record screening results; read the source-of-funds view; review a cash-report draft |
| Ahmed | Finance | see expected payments with their quotes; mark one received (with a reference); see what is overdue; re-approve or cancel an approval that rests on replaced words |
| Joseph | Transactions officer | read the Form F plan, fill the portal himself, mark it submitted; tick the transfer checklist |
| Omar (broker), Layla (owner) | | see where a deal stands and why something was sent back |

First five actions on the screen: pick a deal (or search for one); read what changed and who must act; answer the
card waiting for me; mark a payment received; open the Form F plan and see which fields come from which words.

## Rules this desk keeps (from rooms.md)

- Money facts reach Compliance before anyone else acts (the `check.raised` is the first event after the fact).
- Nothing an agent prepares is final: people screen-clear, release money, submit Form F and file reports.
- Every expected payment, Form F field, report line and slide names the fact it rests on; when that fact is replaced the
  work is withdrawn or sent back with both quotes.
- No invented results: with no sanctions list connected, screening prepares the check and a person records the result.

## Checklist (sessions.md section 3), with what done means

1. **The correction end to end.** On the demo office, "Actually, forget my brother. I'll pay it all myself." typed at the
   meeting table gives, in order: the new fact replacing F2 and F3 (history kept); a Compliance check with both quotes,
   first; Tariq's payment task and screening withdrawn; Ahmed's approval A1 turned into a card for him; executing A1
   refused with the reason; the deck sent back naming slide 3; Nova answering "who pays" with F7 and "F3, since replaced".
   *Browser:* meeting page → Deal desk shows each of these; Ahmed presses "Execute" on A1 and sees the refusal; he answers
   the card ("Re-approve on the new facts") and the new approval rests on F7 and executes once.
2. **Split by department, behaviour unchanged.** `agents/compliance.py` (money-change check, screening, source of funds,
   cash report), `agents/finance.py` (payment rules, received, overdue), `agents/operations.py` (Form F, transfer),
   `agents/review.py` (send-backs, draft review). `office.py` keeps the engine and calls them. Same event order, all tests
   green. *Code only* (nothing changes on screen).
3. **Compliance.** Every party is screened: the customer when the deal opens, any named party or third-party payer when
   said. A screening card shows name, role, the quote that named them, and what is missing (date of birth,
   nationality); Priya records "clear" or "possible match" with a note; the agent never clears anyone. The
   source-of-funds view puts the deal size, deposit and stated income side by side with their quotes and lists the proof
   still missing (filed documents count as received). A cash payment promise of AED 55,000 or more drafts a cash report
   with every quote, waiting for Priya; it is sent back if the promise is replaced.
   *Browser:* Priya's view of Karim's deal before and after the correction; a cash deposit said in a meeting produces the
   draft; a second correction sends it back.
4. **Finance.** One expected payment per live promise, each with its quote, payer, method and due date ("next week" is
   the fact's date + 7 days; no date said shows "no date said"). Ahmed marks one received with a reference; it moves to
   Received with who and when, and a receipt is filed with Records. Past due and not received shows Overdue. Releasing
   money is an approval only Ahmed gives, and it runs only while its facts are live.
   *Browser:* mark received (empty reference refused); an overdue payment; release refused after a correction.
5. **Operations.** Form F starts when the deal's stage becomes "Form F" (set in the Inbox) or when Nova is told
   "prepare Form F". The plan lists every field with its value and source fact, or empty with who must fill it, and stops
   before Submit. A replaced fact sends the plan back with the reason and a new plan is made from the live facts; Joseph
   cannot mark a sent-back plan submitted. The transfer checklist lists the steps (Form F signed, developer NOC, manager's
   cheques, trustee appointment, title deed) with who each one waits for; Joseph ticks them.
   *Browser:* plan → correction → plan sent back with the reason → new plan; Submit marked by Joseph; checklist ticked.
6. **Review.** A draft is checked when it is made: one using a replaced fact is sent back at once and never shown as
   ready; otherwise `review.passed`. Every send-back names the slide or field, the old quote and the new one.
   *Browser:* the deck after the correction shows "sent back" with both quotes; a new deck from live facts shows passed.
7. **The Deal desk screen and the floors.** `web/deal.html`: a list of deals (search by customer, property or deal id;
   filter "needs someone"; paged at 50) and one deal's Changes, Compliance, Payments, Paperwork and Review sections, each
   card with its quotes and the person it waits for. "Acting as" decides which buttons a person may press. The 3D floors
   of Compliance, Finance, Operations and Review show their open work from the log.
   *Browser:* 1280 wide and phone width, no sideways scroll; 300 deals in the list still pages and searches; an empty
   office says "No deals yet"; an unknown deal id says so.

## States every section must handle

Empty (no deals; a deal with no money facts; nothing to screen), errors (an action by the wrong person is refused with
who may do it; a missing reference; an unknown approval), and scale (hundreds of deals, dozens of facts per deal).

## Decisions for the product owner

1. **Sanctions lists.** No list is connected, so screening prepares the check and Priya records the result. Connecting
   a real list (UN consolidated, UAE local terrorist list) is a later step.
2. **When Form F starts:** when the broker sets the stage to "Form F" in the Inbox (session 2's stage list), or on Nova's
   instruction. Written in the changelog.
