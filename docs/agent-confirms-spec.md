# The agent confirms a viewing: held until they do

The owner's rule (2 Nov, `docs/problems-and-fixes.md` 2.1): Rania never books a viewing alone; the client's broker talks to them
and confirms the place first. That is the app's default (`sales.rania_books` off). With it, Rania still knows what the client
asked for, so everything they say afterwards is answered from it.

## Checklist

- [x] A client asks to see a listing at a time. Rania checks the broker's free time, the unit, a tenant's notice and the
      gallery's hours, as when she books. If free, the time is **held** (a viewing "requested", waiting for the broker), and
      the client hears "Thanks, I've noted you'd like to see … Omar will talk to you and confirm the place and the time."
- [x] The broker gets one card: "Viewing request: <home>, <time>. Talk to the client, confirm the place, then book". A home
      someone lives in adds "someone lives there: check with the owner too".
- [x] Not free: "Omar is free for <home> on A, B or C. Which suits you?" (no "I can book"). No time: the same, from now.
      No listing: "Which property would you like to see?"
- [x] Naming the listing says buy or rent: "is it to buy or to rent?" is never asked after.
- [x] While it is held:
  - "cancel the viewing": the request is cancelled, the broker's card cleared and they're told;
  - "move it to Wednesday 5pm": the held time moves, the broker's card says the new time, and the client hears that Omar
    will confirm it;
  - "thanks": "You're welcome! Omar will confirm <time> with you." Then 🙂, then nothing;
  - "any news?", "what time is it again?": the time asked for, and that Omar will confirm it;
  - "my wife will come too": welcome, and the time once Omar confirms.
- [x] The broker answers in the Inbox: **Confirmed: book it** (booked, the client is told "Booked: …"), **Other times…** (the
      client picks one, booked at once), **Not possible** (the client is told, and offered other options).
- [x] Or on the calendar, ticking "I've talked to the client": the held viewing becomes the booking at the time they chose.
      No second viewing, and the held time never clashes with itself.
- [x] Once booked, a client moving it in the chat asks for the new time: it waits for the broker again, and its reminders
      wait too (`docs/problems-and-fixes.md` item 17). A broker moving it on the calendar moves it, as before.
- [x] When "Rania books" is on, nothing changes from `docs/viewing-access-spec.md`. (It is a setting the code reads, but no
      page sets it yet: the Sales rules don't save it, so today the broker always confirms.)
- [x] Tests: the 40 conversations run in both modes; their checks hold in each.
- [x] Browser: the flows that book a viewing confirm it as the broker first, as the app does by default.

## Also fixed on the way
- A reply with no question in it (a viewing request noted, a booking) no longer marks the next question as asked, so two
  messages later the client isn't treated as "not sure" about a question they were never asked.
- A follow-up picks up the question left open ("which would you like to see first, and at what time?"); a listing "that
  fits what you told me" only goes once they're qualified.
- The conversation tests send each follow-up at its due time, as the app's sweep does, not only at two fixed moments.
