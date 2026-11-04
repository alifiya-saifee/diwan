# One look across the rooms (approved 4 Nov 2026, trimmed to what the video shows)

Each room was built at a different time, so they look like different apps: emoji next to serif titles, big empty boxes,
cards of uneven height in one row, "1760 min left" on one page and "23h left" on another, a top bar that cuts words off.
This pass makes them read as one product. **No feature changes, no new screens, no changed words except times and empty
states.** Freeze is 18:00 Dubai; each page is pushed only after its before/after is seen.

## Shared (web/app.css and web/app.js, so every page gets it)
- [ ] **One page header:** the serif title, one muted line under it, actions on the right, the same spacing on every
      page.
- [ ] **One card:** the same background, border, radius, padding and title style (small caps label, count on the
      right).
- [ ] **Line icons instead of emoji** in card titles and buttons: one small inline SVG set (phone, alert, flame, new,
      pen, clock, mic, calendar, bell). The emoji go.
- [ ] **Empty states shrink:** a card with nothing in it becomes one quiet line ("No hot leads"), not a tall box. In a
      row of cards, all of them are the height of the tallest one.
- [ ] **One way of writing time left:** under an hour "45 min left"; under two days "22h left"; otherwise "Thu 5 Nov".
      Overdue in red.
- [ ] **The top bar never cuts words off:** the menu scrolls inside itself (as now). The search box and the "Built with
      Meta Muse" pill shrink or hide below a set width, instead of clipping "Built with Me…" and "Search knowledg…".

## Trimmed for today (done by 14:00; the rest after the hackathon)
Only: the top bar (it is in every shot), one time format (update the tests that check it), empty sections shrinking and
even card heights. Line icons only on Sales and Inbox, and only if the three above are done by 13:00. Not today: the
Nova agenda (a feature, not a style), Calendar, the Office header, and anything aimed at Deals or Studio (another
session has unsaved work there); shared CSS is limited to rules those two pages don't use.

## Not in this pass
New features; changed wording beyond times and empty states; the 3D scene; mobile layouts beyond "nothing cut off at
1280px"; Meeting (already plain).

## Checks
- [ ] Before and after screenshots of each page at 1440 and 1280 wide, signed in as Layla, Omar and Maya (each person's
      own pages), on a Render-like local server with the demo day.
- [ ] Nothing that worked stops working: the full test suite and the 35 browser flows in e2e/ that touch these pages.
- [ ] Each page pushed only after its screenshots are seen; the live P0 check rerun after the last push.
