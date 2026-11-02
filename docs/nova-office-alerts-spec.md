# Nova tells the owner what matters at the office, on their WhatsApp

Today Nova raises a few office matters in the app only (an unhappy client, a bank-details change, "ready to buy", a screening
match, a flagged payment). Staff get their urgent notices on their own WhatsApp, but the owner is left out on purpose: the
sales line is never how Nova reaches the owner. So when the owner is out, they hear nothing until they open the app.

## Checklist

- [x] **One way to the owner:** Nova's own line (`diwan/novaline.py`), and only when they're away from the app. In the app it
      stays a heads-up, as now. Off until that line is connected, so nothing changes until it is.
- [x] **What reaches them, once each:**
  - what Nova already raises: an unhappy client, a bank-details change, ready to buy, a screening match, a flagged payment,
    money in, a sale closed;
  - **a hot lead**: "Sara Khan is a hot lead: asked to view Unit 1204 (MC-1204). Omar has it.";
  - **a call request nobody has made**: the owner's urgent notices (a card past due, a lead gone to the Pool) go to
    their WhatsApp too;
  - **a viewing nobody confirmed**: held for the broker past the owner's time for an answer (2 hours unless set):
    "Omar hasn't confirmed Sara Khan's viewing of MC-1204, Tuesday 3 Nov, 4:00 PM. She asked 2 hours ago.";
  - **what's still stuck after a second chase** (Nova's office walk), as the line she already writes.
- [x] **When:**
  - trouble goes at once, whatever they're doing: a bank-details change, an unhappy client, a screening match, a flagged
    payment;
  - good news and hot leads wait while they're in a meeting or on do not disturb, and outside the hours the owner allows
    messages (late at night nothing but trouble).
- [x] **How:** what arrives together goes as one message ("Three things. 1. … 2. … 3. …"). Never the same matter twice.
      Names and the matter only, no client numbers. After WhatsApp's 24 hours the approved template carries it, as the
      personal line does now.
- [x] **Nothing is done for them:** Nova tells; the broker acts. Her message says who has it.
- [x] **Tests:** each alert once, held and released at the right moments, grouped, nothing sent when the line isn't
      connected or they're in the app; a fake WhatsApp, never a real one.
- [x] **Browser:** the owner's heads-up shows in the app for each kind; the WhatsApp side is checked by the tests (no real
      number in a demo).

## Not in this part
The meeting table (minutes, the owner's approval, each item to the right team), travel and restaurant search, money
refusals, Hey Pocket's speakers, the late-night tone in conversation, calls prepared for the owner.

## How it was checked (2 Nov)
- `tests/test_nova_office_alerts.py`: each kind once; held in do not disturb and at night, then sent; trouble at once; one
  message for what arrives together; a complaint Rania also told the owner about is still one message.
- `e2e/nova_alerts_flow.py`: in the browser, a hot lead and a bank-details change reach the owner's Nova within a minute,
  once each, and a broker's Nova isn't given them. The WhatsApp side runs against a stand-in, never a real number.
