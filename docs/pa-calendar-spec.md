# The PA runs the calendar (approved and built 3 Nov 2026)

Each person's PA already blocks their time, books a client viewing and sets reminders, always reading back first and acting only
on a yes. This part makes the PA the way you run your day: ask what's on, book meetings with colleagues and calls with clients,
with a Zoom link for online ones. Nothing is saved or sent without that person's yes, and nothing is invented: a link that
couldn't be made is not shown.

Found 3 Nov, in a scratch office: "Block Friday 3 to 5pm" blocked 5–6 PM; "what's on tomorrow" and "am I free" get no answer
without the model; a meeting with a colleague only blocks your own time; a video call with a client can't be booked by the PA.

## Read the calendar
- [x] "What's on today / tomorrow / Friday / this week?" lists that day's appointments and blocked time from the calendar
      itself, in time order: no model needed, so it is never guessed. (The rows are read out as they are; they are not
      reworded by Muse Spark.)
- [x] "Am I free Friday at 4?" answers yes, or no with what is there and the nearest free times.
- [x] A broker sees only their own calendar (they may ask whether a colleague is free at a time: free or busy, never why); the owner can ask about anyone ("What's Omar's day tomorrow?").

## Block time
- [x] Time ranges are read right: "3 to 5pm", "3-5pm", "from 3 until 5", "3pm for 2 hours" all block 3:00–5:00 PM.

## Meetings with colleagues
- [x] "Set up a meeting with Ahmed Thursday at 2 about the payment plan" checks both calendars. Read back: who, when, what
      about. If either is busy, the read-back says so and offers the nearest times both are free.
- [x] On yes: the meeting is on both people's calendars, and the colleague's PA tells them (who asked, when, what about).
- [x] "…on Zoom" (or "online", "video"): with Zoom connected, one Zoom meeting is made and its link is on both entries.
      Not connected: the meeting is booked without a link and the read-back says "Zoom isn't connected, so there's no link".
- [x] Cancelling or moving it (by either of them) through the PA changes both calendars and tells the colleague; a Zoom meeting is moved or deleted.

## Calls with clients
- [x] "Book Karim a video call Thursday at 3pm" (or "phone call") books that appointment kind with the client's broker,
      checked against the broker's free time, read back first.
- [x] On yes: on the calendar, the client gets the usual reminders. A video call gets its Zoom link in the
      confirmation (the existing Zoom path); not connected, the existing "the broker will send the link" path.

Built: `diwan/agents/frontdesk.py` (`_calendar_asks`, `_range`, `_meeting_asks`, `_make_meeting`, `_change_meeting`, `_call_asks`),
`diwan/slots.py` (`block(meeting=...)`, `keeps_calendar`), `diwan/video.py` (`meeting`, `meeting_moved`, `meeting_cancelled`),
tests in `tests/test_pa_calendar.py`. A colleague who doesn't keep a calendar here (Finance, Compliance...) is told, and the
meeting goes on the asker's calendar only; the read-back says so. A client with no WhatsApp conversation can't be booked a call
(the reminders and link would have nowhere to go); the PA says so.

## Not in this part
Flights, hotels and travel bookings (the PA keeps saying it can't book them); Google or Outlook calendar sync.

## Checks
- [x] Tests offline (Zoom answered by the existing stand-in).
- [x] In the browser like a user, on a scratch office (3 Nov): Layla asks what's on, blocks 3–5, books a meeting with Omar
      on Zoom (not-connected path); Omar gets the notice, sees it on his calendar page, books Karim a video call, moves the
      meeting (Layla is told) and cancels it.
- [x] With the office's own Zoom keys in `.env`: one real meeting made, moved and deleted (3 Nov, through the PA; Zoom confirmed each step, and the meeting no longer exists).
