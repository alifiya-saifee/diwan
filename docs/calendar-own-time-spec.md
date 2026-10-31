# Calendar: the broker's own time (approved 30 Oct 2026)

**Checked in the browser 30 Oct, 18/18** (`e2e/own_time_flow.py`, rules mode, a scratch database, 1280 and phone);
tests `tests/test_own_time.py` (10). Tested in code only: "Needs attention" (an appointment past and not marked can't be
made in a fresh demo, since nothing books in the past; one now outside the broker's hours after the owner shortens the day).
Colleagues: a broker sees only their own calendar, so "colleagues see Busy only" applies to the owner's view of reasons.

Part of the calendar (`docs/calendar-spec.md`). A broker's day is not only what Rania books: the dentist, the school
run, a day off, a viewing they arranged on the phone. Until the calendar knows, Rania can book a client into a time the
broker can't keep, and the client is the one let down. Each line is checked in the browser like a user before it is
ticked.

## Busy time
- [x] On the calendar, "+ Busy" (or clicking an empty slot) opens a form: day, from, to, a reason (optional), repeat
      every week (optional). Saving shows the block on the grid at once.
- [x] Colleagues see "Busy" only; the reason shows to the broker and the owner.
- [x] Rania never offers or books a busy time, including each week's repeat; she offers the nearest free times instead.
- [x] A block over an appointment already booked is refused with the reason ("You have Site visit with Sara Khan at
      Tue 3 Nov, 4:00 PM: move it first"). A block that ends before it starts, or in the past, is refused.
- [x] The broker changes or deletes their own block; a repeating block can end from a date ("stop repeating").

## Day off
- [x] "Day off" takes a first and last day (and a reason, optional). Those days show as not bookable and Rania books
      nobody on them. If appointments are already booked in the range, it is refused, listing them, so they are moved
      first.

## An appointment added by hand
- [x] "+ Appointment": the client (an existing chat by name or number, or a new name and number), the kind of
      appointment (the owner's list), the property (for a site visit), day and time. The same free-time check as
      Rania: a busy or booked time is refused with the nearest free times.
- [x] It shows on the calendar and in the client's Inbox lead, the client gets the same reminders, and the broker's
      morning list includes it. Rania knows about it: "When is my viewing?" is answered, and "move it to 5pm" works.
- [x] Nothing is sent to the client when it is added by hand (the broker already agreed it with them on the phone);
      the reminders follow the owner's reminder setting.

## Who can do what
- [x] A broker adds and changes only their own busy time, days off and appointments; the owner does it for anyone;
      anyone else is refused. Every change is kept in the log with who and when.

## Checks
- [x] Tests offline; the browser check on a fresh scratch database; 1280 and phone width.

## The week at a glance (product owner 30 Oct: "make it professional, give it meaning")
- [x] Week, Day (a column per broker: who is free at 4pm) and Agenda views.
- [x] The week's numbers from the log: appointments against last week, by kind, time booked out of the bookable hours
      (busy time and days off taken out) and hours still free, what needs attention, the next appointment.
- [x] Each broker's load: a bar, appointments, hours free, days off; clicking it filters the calendar (owner).
- [x] Owner settings moved into ⚙; the "Viewing as" list comes from the people, not from the page.

## Not in this part
Google or Outlook calendars (a separate plan, to approve).
