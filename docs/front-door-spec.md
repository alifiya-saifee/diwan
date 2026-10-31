# Part 1: the front door (approved 30 Oct 2026)

**Checked in the browser 30 Oct, 14/14** (`e2e/front_door_flow.py`, rules mode, a scratch database): every line below.
Tests: `tests/test_front_door.py` (10).

The client's side first (see the journey page). Each line is checked in the browser like a user before it is ticked.
Every number and choice is an owner setting, not code.

## 1. Not ready yet → Marketing nurtures them
- [x] A client who says they are only looking ("just looking", "not now", "maybe next year", "not interested", Arabic too)
      gets a warm reply that leaves the door open, and no question.
- [x] The lead moves to **Nurture**: logged with their words (`lead.nurture`). The broker's open card on it closes with
      "not ready yet", so no broker time is spent and nothing is overdue.
- [x] While nurtured, Rania still answers any question they ask, but asks no qualification questions and sends no listings.
- [x] The Inbox shows 🌱 Nurture on the lead, and a Nurture filter. Marketing reads the list (`/api/leads/nurture`):
      the client, why, their words, since when. Not-a-fit leads are on it too, with the owner's reason.
- [x] Who nurtures not-ready leads is the owner's setting: Marketing (default), the broker, or nobody.

## 2. They come back ready → reopened
- [x] A nurtured client who shows real intent (a budget, asks to view, asks for a call, picks a property, asks for
      options) is reopened (`lead.reopened`): the broker gets a notice with their words, and the same message is handled
      normally (qualifying goes on from what they already said).

## 3. "Can someone call me?" → a person, always
- [x] At any stage, a call request gets "Our team will call you shortly" (in their language) and the broker a call card
      with the conversation. Rania keeps the chat for anything else; "let me talk to a person here" still hands it over.
- [x] Once qualified, a call request is a 🔥 hot lead when the owner ticks "They ask for a call".

## 4. What makes a lead hot (owner's setting)
- [x] Two new choices: "They qualify" and "They ask for a call", next to "pick" and "viewing".
- [x] With "They qualify" ticked, a lead that qualifies gets the 🔥 hot card at once (with the options Rania sent).

## 5. Portal leads: start from what they enquired about
- [x] A Property Finder / Bayut / Dubizzle enquiry about a listing fills in what that listing tells us (buying or
      renting, area, property type, bedrooms), each marked "from the listing they enquired about". Never the budget.
- [x] When the client writes on WhatsApp, Rania asks only what is still missing.
- [x] The first message to a portal lead: the owner picks an approved template (or "none: the broker calls"). With one
      picked, Rania sends it at once; the broker's call card stays.

## Not in this part
Quiet clients (part 2), calendar (part 3), visit summary (part 4), agreement to keys (part 5).
