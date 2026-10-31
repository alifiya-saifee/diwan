# Part 2: when a client goes quiet (approved 30 Oct 2026)

**Checked in the browser 30 Oct, 13/13** (`e2e/quiet_flow.py`, rules mode, a scratch database; the clock is moved with
the sandbox-only `/api/nudges/run`, which a connected WhatsApp line refuses). Tests: `tests/test_nudge.py` (13).
Found while checking: with one template, follow-ups 2 and 3 were word for word the same, so a follow-up that would repeat
an earlier one is now skipped (logged with the reason). The sample template "still_looking" claims "new listings this
week", so a truthful one was added ("gentle_follow_up"); the panel asks the owner to pick words true for every client.
Tested in code only, not in the browser: Arabic follow-ups, the "new listing that fits" follow-up, the broker's
"gone quiet" card, skipping Won/Lost/not-a-fit leads, and the pause before a booked viewing.

The client's side first: space to think, and a nudge only when it brings something useful. Never a daily "just
checking in". Every number below is the owner's setting (Qualification page → "When a client goes quiet").
Each line is checked in the browser like a user before it is ticked.

## Who gets a follow-up
- [x] A conversation where Rania spoke last and the client hasn't replied. Not: a chat a person has taken over (the
      broker follows up), a lead in Nurture, a client who said "stop", a lead that is Won, Lost or not a fit, or a client
      with a viewing still to come.

## When
- [x] The owner's schedule, counted from the client's last message (default: after 20 hours, 3 days, 7 days). At most
      that many follow-ups; a reply from the client starts the count again.
- [x] Never in the owner's quiet hours (default 21:00 to 09:00 Dubai) and never during Friday prayer (11:30 to 13:30)
      when the owner ticks it: the follow-up waits for the next allowed time.

## What it says (useful, picking up where they left off)
- [x] Options sent, none picked: a new listing that fits and wasn't sent before, if there is one; otherwise "did any of
      them catch your eye? If none fit, tell me what to change".
- [x] Still qualifying: the one question still open, with "no rush".
- [x] Not started (type unknown): whether they want to buy, rent or sell, and that we're here when they're ready.
- [x] English or Arabic, as they wrote. Never a deadline, a "last chance", or a claim the records don't support.

## The 24-hour rule
- [x] Within 24 hours of the client's last message Rania writes freely. After that WhatsApp allows only an approved
      template: the owner picks one (its blanks: first name, area, broker). With none picked, follow-ups after 24 hours
      are skipped and the lead moves on to the last step.

## "Stop"
- [x] A client who says "stop", "don't message me" or "unsubscribe" gets one short confirmation and never gets another
      follow-up or nurture message. They can still write to us. A person cannot switch it back on.

## After the last follow-up
- [x] No reply a set time after the last one (default 3 days): the owner's choice: the lead goes to Nurture
      (Marketing, default) with "went quiet after 3 follow-ups", or the broker gets one "gone quiet" card. The broker hears once.

## Seeing it
- [x] The lead in the Inbox shows "Follow-ups: 1 of 3 sent · next Mon 2 Nov, 09:00" (or why none is due, or "stopped:
      they said …"). Each follow-up is marked in the chat.
- [x] The owner's panel lists the next follow-ups due across the office.

## Not in this part
The calendar and reminders (part 3), the visit summary (part 4).
