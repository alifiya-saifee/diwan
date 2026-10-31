# Marketing: closing the room

Session 1 (Marketing). Asked for by the product owner on 31 Oct 2026, to complete the Marketing section of the closed-loop
spec (`docs/closed-loop-spec.md`, "Marketing: the full lifecycle"). What was missing is listed in
`docs/closed-loop-checklist.md`.

## What gets built

| # | Piece | Done when |
|---|---|---|
| 1 | One stage for each piece of content | The spec's names, `idea` to `archived`, shown on a new Results tab and written as the spec's events |
| 2 | The brief | Pressing Write approves it. An automatic run stops at the idea and asks a person |
| 3 | Posts follow the facts | A price, permit, status or moment change pauses the piece, cancels what is scheduled and closes open cards. A sold or withdrawn listing withdraws it. Nothing is published that fails this |
| 4 | Permit expiry | A date on a listing, warnings 14 and 3 days ahead, paused on the day |
| 5 | Every post is traced | A code word in each caption ("say MARINA"), comments keep their post, `lead.attributed` on the lead |
| 6 | Results per post | Leads, qualified, viewings, deals, commission; engagement beside them |
| 7 | Strategy learns from leads | Angles that bring enquiries rank first |
| 8 | The Marketing day | Morning list, end-of-day list, Monday "what brought deals" |
| 9 | Campaigns | Goal, audience, budget, dates, a drafted ad, a monthly cap, a person launches, cost per qualified lead flagged over the limit |
| 10 | Tighter gates | A failed own script can't be picked; every post text is checked; no promises about visas or price rises; auto-posting is the owner's switch; a person can change the time |

## Decisions

- **A live post can't be deleted through Instagram's API.** "Paused" on a live post means Diwan stops relying on it, flags it, and
  gives a person the task of taking it down. This is said on the screen.
- **Pressing Write is the brief's approval.** The spec wants a person's yes before scripts. A person pressing the button has given
  it, so a second yes would only slow them down. An automatic run has no person, so it asks.
- **Auto-posting is off by default**, as the spec says. At the time, the person is told and presses Post now. With the switch on,
  it posts by itself.
- **Marketing reads the log.** Tracing runs on a sweep over what arrived, so no Sales code changes (rule 5 of the spec).
- **Listing changes** only suggest a new post. Nothing is written or paid for until a person presses.

## Not in this piece

These need an outside account or a decision, and are left on the checklist:

- Posting to Facebook, TikTok or YouTube; stories.
- A cloned voice.
- Email or WhatsApp campaigns to warm leads (needs approved templates).
- Launching ads from Diwan: a person launches and pays, as the spec says.
- Checking that the permit is on screen inside a filmed cut.
