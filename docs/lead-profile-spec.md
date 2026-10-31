# The lead profile: acting on a lead (approved 31 Oct 2026)

The broker reads the lead's profile beside the chat; now they act from it too. The client's side first: whatever the
broker does here, the client is never chased, never called after asking not to be, and never asked the same thing twice.
Built one part at a time; each line is checked in the browser like a user before it is ticked.

**Checked in the browser 31 Oct, 17/17** (`e2e/profile_flow.py`, rules mode, a scratch database, 1280 and phone); tests in
`tests/test_front_door.py` (8) and `tests/test_nudge.py` (1). The other browser checks still pass (94 steps over eight
checks, and the office walkthrough).
Tested in code only: the broker being told when someone else changes their lead (hot, follow-up, no calls, merge), and a
discount below the owner's limit waiting for the owner at Convert (the Deal desk's own check covers it).

## 1. Stage and quick actions
- [x] The profile shows the stage as a dropdown of the deal's own stages (Sales' stages, then its paperwork path), from
      the Deal desk's rules. Moving it uses those rules: Lost or moving back asks for a reason; Won only comes from
      closing; only the broker, the transactions officer or the owner moves it, and anyone else sees who can.
- [x] The chat header shows the stage and opens the profile; there is one place to change it. The Inbox's own fixed list
      of stages goes.
- [x] Hot: the broker marks the lead hot, or not, with an optional note. It shows wherever hot shows; the broker is told
      when someone else marks it.
- [x] Transfer: to another broker; the lead and its open card move, and the new broker is told.
- [x] Convert: asks the agreed price. Within the owner's discount limit the deal converts and its paperwork starts;
      further below the listing it waits for the owner (the Deal desk's rule). Afterwards it shows the agreed price.
- [x] Follow up on a date: day, time, call or message, a note. A card for the broker, due then, overdue and Pool like any
      card. Nothing is sent to the client. Refused while the lead already has an open card, with what that card is.

## 2. Asked: no calls
- [x] A switch on the profile. On: Rania never offers or promises a call (she says the broker will reply here), call
      cards become reply cards, and the lead shows "No calls" in the list. Logged with who and when.
- [x] If the client later asks for a call themselves, the switch turns off and the broker is told.

## 3. Follow-ups
- [x] Messages: this lead's follow-ups as a list, each sent (when, the words) or planned (when), or why none is due.
- [x] Change: a different schedule for this lead only. Stop: no more follow-ups for this lead (a person can still write
      to them). Resume.
- [x] Calls: this lead's call cards and phone calls, open and done.

## 4. Merge
- [x] Merge two conversations that are the same person (Instagram and WhatsApp, or two numbers): pick the other one by
      name or number. One thread shows both, each message marked with its channel; the answers this lead lacks come
      over (marked where from) and Rania finds appointments on either; the other lead's facts stay on it; the other lead
      closes as merged, and what they send there arrives here. The owner or the lead's broker only.

## Not in this part
The outcome stages (No response, Not interested, Follow-up as a stage) wait for the Deal desk to agree on the shared stage
list; the request is in docs/sessions.md.

## Checks
- [x] Tests offline; the browser check on a scratch database; 1280 and phone width.
