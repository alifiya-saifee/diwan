# Part 3: the calendar and reminders (approved 30 Oct 2026)

Decided by the product owner: a demo calendar inside Diwan (Google and Outlook are not connected for the hackathon);
the owner sees every broker's calendar and can filter to one; a broker sees their own. Nothing about hours, days or
appointment types is fixed in code. Each line is checked in the browser like a user before it is ticked.

**Checked in the browser 30 Oct, 12/12** (`e2e/calendar_flow.py`, rules mode, a scratch database). Tests:
`tests/test_calendar.py` (12). Found while checking: "move the viewing" moved an earlier video call (fixed: Rania moves
the one they name); the week pushed the page sideways on a phone (fixed); the Calendar link in the shared header made it
wrap on every page, so the calendar opens from the Inbox bar instead.
Then checked in the browser too (`e2e/gaps_flow.py`, 5/5): cancelling in the chat, the broker's morning list, a reminder
as plain text inside the 24-hour window (with the map link), Arabic "just looking" and an Arabic follow-up. Still API only:
Done and No-show after the time (the browser checks they stay shut before it).

## Hours come from settings, not code
- [x] The office's opening hours and days are the owner's setting (demo: 10:00 to 19:00, Monday to Saturday).
- [x] Each broker's own shift and working days (Settings → Team) narrow it: Rania never offers a time outside them,
      or on a day off, or one that overlaps another appointment.

## Kinds of appointment (the owner's list)
- [x] Site visit (60 min, at the property), office meeting (60 min, at the office), video call (30 min). The owner can
      change the length, rename, add or remove one.
- [x] Rania books the kind the client asks for ("can we do a video call?", "meet at your office"); a property named
      with no kind is a site visit. The confirmation says where.

## Changing or cancelling in the chat
- [x] "Can we move it to Thursday at 5?": moved if that time is free (the broker is told), otherwise the nearest free times.
- [x] "I need to cancel": cancelled, the broker is told, and Rania offers another time without pushing.

## Reminders
- [x] The client: the day before and two hours before (the owner's times), with where to go and what to bring, never in
      quiet hours. Inside 24 hours of their last message as text, otherwise the approved reminder template.
- [x] The broker: each working morning, their appointments for the day.

## The calendar page
- [x] A week view: each broker's working hours shaded, appointments as blocks (kind, client, property, where).
- [x] The owner sees all brokers and can filter to one; a broker sees only their own. Clicking an appointment opens the chat.
- [x] After the time: "Done" (moves the lead to Viewed, which drafts the follow-up) or "No-show" (logged; the quiet-client
      follow-ups take it from there).
- [x] The owner edits the opening hours and the kinds of appointment there; a broker can't.

## Not in this part
Google or Outlook sync; the visit summary (part 4).
