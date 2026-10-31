# Calendar basics and video links (approved 30 Oct 2026)

**Checked in the browser 30 Oct, 17/17** (`e2e/basics_flow.py`, rules mode, a scratch database, 1280 and phone);
tests `tests/test_calendar_basics.py` (9). **Zoom itself is tested in code only**, against a stand-in for Zoom's API: no Zoom
keys are in `.env` yet, so the browser shows the "not connected" path (no link invented, the broker told). The first
live Zoom meeting is still to be checked once the keys are added. Google Meet is listed as "needs the Google
connection". The Settings page's Zoom card was not used to save keys in the check (that writes the real `.env`).
Also code only: the 24-hour-window card (a fresh demo's clients have just written), and the broker being told when the
owner moves their appointment.

Part of the calendar (`docs/calendar-spec.md`, `docs/calendar-own-time-spec.md`). What a broker expects from any
calendar, and a real link for every online meeting so the client never waits for one. Each line is checked in the
browser like a user before it is ticked.

## Dates
- [x] A date picker jumps to any day (Week, Day and Month open on it).
- [x] Custom range: from and to (up to 3 months) shown as a list, day by day, with the numbers for that range.
- [x] Month view: every day of the month with its count and first appointments; busy days and days off shown; a click
      opens the day.

## Search and filters
- [x] Search by client name or phone across all dates (past and future, any status); a result opens its week.
- [x] Filter by kind of appointment and by status (booked, done, no-show, cancelled); cancelled is hidden unless
      asked for. The numbers follow what is shown.

## Change from the calendar
- [x] The broker (or the owner) moves an appointment: a new day and time with the same free-time check, or the nearest
      free times when it isn't free. Cancel asks for a reason (optional).
- [x] The client is told in one plain WhatsApp message ("Omar has moved your site visit to … " / "… has been
      cancelled. If you'd like another time, just reply here."). Outside WhatsApp's 24-hour window the message can't go
      without a template: the broker gets a card to tell the client, and the calendar says so.
- [x] Moved appointments get their reminders again; the broker of a moved appointment is told when the owner moves it.

## Export and print
- [x] Download the shown range as an `.ics` file (phones, Outlook and Google import it): one event per appointment,
      with client, place and link; busy time as "Busy".
- [x] Print a clean day sheet: the broker's day, time, client, phone, property, address and notes.

## Video links (the owner picks Zoom or Google Meet)
- [x] Owner setting: Zoom, Google Meet, or none. Shown only to the owner; says what is connected.
- [x] Owner setting "Create the link when Rania confirms a call" (on or off). On: the link is made at booking and goes
      in her confirmation. Off: nothing is made automatically; the appointment has "Create link" for the broker, and
      the link then goes to the client in one message.
- [x] With Zoom connected (`ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` in `.env`, a Server-to-Server
      OAuth app), each video call booked by Rania or by hand gets its own Zoom meeting; the link is in the client's
      confirmation, reminders, the calendar and the `.ics`. Moving it moves the meeting; cancelling deletes it.
- [x] Not connected, or Zoom refuses: no link is invented. The confirmation says the broker will send the link, the
      broker gets a card, and the reason is kept.
- [x] Google Meet: listed, marked "needs the Google connection" until that is built (separate plan).
- [ ] A live Zoom meeting made, moved and deleted with the office's own keys (waiting for the keys).

## Checks
- [x] Tests offline (Zoom's API answered by a stand-in in tests only); the browser check on a fresh scratch database;
      1280 and phone width.
