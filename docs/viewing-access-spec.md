# Viewings by listing: ask the owner first when someone lives there (approved 2 Nov 2026)

This replaces D11 ("instant booking stays"). A viewing of a home someone lives in is never booked without the owner or tenant
agreeing. A vacant unit with keys at the office books at once. An off-plan unit is shown at the developer's sales gallery,
in its hours. The client's side first: they're told honestly what happens next, and never left waiting without a word.

**Checked 2 Nov:** tests offline (`tests/test_viewing_access.py`, 12); browser `e2e/viewing_access_flow.py` 9/9 (also run in a
visible window).

## 1. Each listing says how it's viewed
- [x] Three ways: **Book at once** (vacant, keys with us or a lockbox); **Ask the owner first** (lived in or tenanted,
      with the notice the tenant needs, in hours); **Developer's gallery** (off-plan: the gallery's address and hours).
- [x] Nobody has to set it: a ready or rental home asks the owner first, and an off-plan unit uses the developer's gallery
      with the office's hours, until someone changes it.
- [x] The listing's broker, the Sales manager or the owner change it on the listing, and it's logged with who.

## 2. Ask the owner first
- [x] The client asks for a time the broker is free: Rania doesn't book it. She says she'll check with the owner and
      confirm here, and names the time asked. The time is held on the broker's calendar as *waiting for the owner*, so
      nobody else gets it.
- [x] A time inside the tenant's notice is not offered: the first time offered is after it.
- [x] The broker gets a card due within the owner's limit (a setting, 2 hours by default), with three answers:
      **Owner said yes**, **Owner offers other times** (one to three), **Not possible**.
- [x] Yes: the viewing is booked; Rania tells the client it's confirmed, with the time, and reminders follow as usual.
- [x] Other times: Rania offers those times; the one the client picks is booked at once (the owner already agreed).
- [x] Not possible: the held time is freed; Rania tells the client kindly that it can't be shown then and the broker will
      suggest other options. No reason about the owner is given.
- [x] "Any news from the owner?" is answered honestly: still waiting, with the time asked.
- [x] The calendar shows the held time as waiting for the owner, with the same three answers.

## 3. The developer's gallery
- [x] Times are offered and booked only inside the gallery's hours and the broker's; the client is told to meet at the
      gallery, and the reminders say where it is.

## Not in this part
Several properties in one trip, travel time between viewings, family coming along, keys held by another agency.

## Checks
- [x] Tests offline (`tests/test_viewing_access.py`); a browser check (`e2e/viewing_access_flow.py`): a tenanted flat
      asked about → "I'll check with the owner" → the broker answers on the card → the client gets the confirmed time;
      an off-plan viewing books at the gallery in its hours.
