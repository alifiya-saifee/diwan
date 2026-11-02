# Marketing session log, 31 October to 2 November 2026

Everything done on the Marketing room in this session: what was asked, what was built, what was tested, what went wrong and what is still open. For the owner and anyone picking the work up. Case-by-case test results are in [marketing-test-report.md](marketing-test-report.md), and how the room works is in [marketing-journey.md](marketing-journey.md).

## Where things stand

- All the code from this session is on GitHub `main`, last at commit `38d83f3`.
- This log itself is not pushed yet.
- Publishing stays off. Nothing was posted to Instagram and no client was contacted by any test.
- The hackathon is due on 4 November 2026 at 9 PM ET.

## What was asked, and what came of it

| Asked | What was done |
|---|---|
| One place for the future plan and what is pending | The Plan tab: Waiting for you, the plan, Going out, Came off |
| Rejected means removed, approved goes ahead | Remove takes a day off and it stays empty; Approve keeps it |
| Videos that feel natural | New shots about every 2.6 seconds, title, captions in chunks, end card. The voice is still the Windows one |
| Don't keep making new reels | No new reels on your servers; test videos were made only on scratch copies, on the copy of your data (port 8036) and on the test server (8031) |
| Ask how many and how far, don't assume | Plan from today asks how far ahead and how many posts a week |
| Update or change plan days | Change, Remove and the arrows on each day |
| AI frames instead of required photos | Make the frames with AI, for brand and topic posts only. A listing must use real photos |
| Plan a week, save tokens | One week by default, fewer drafts, one redraw of frames |
| Clicking a day opens the post | Done, and the label follows the post's stage |
| Posts must be relevant and professional | Every planned day names its evidence. A Creative Director scores AI pictures out of 5 |
| Competitors choose the format, real material first | Footage, then photos, then what competitors' winners show |
| Learn from rejections, like regression, not notes | `agents/taste.py`, below |
| Stop must really stop | Fixed, below |
| Full test, every tab, nothing left behind | Done, below, with limits listed |
| Push to GitHub | On `main` |

## What was built

| Part | File | What it does |
|---|---|---|
| The Strategist | `agents/planner.py` | The model chooses each day and says why; the code decides what may go on a day |
| The Creative Director | `agents/director.py` | Scores AI pictures against the post, the business and competitors |
| The learner | `agents/taste.py` | Online logistic regression over each post's features, replayed from the log |
| AI frames | `agents/freevideo.py` | Draws up to 6 illustrations from the approved script |
| Weekly mix | `agents/rhythm.py` | `spread_formats` and `mix_teaching` vary the week's formats |
| Planned-day posting | `agents/studio.py` | `planned_at` sends a post out on its own day |
| The lead's knowledge | `agents/lead_chat.py` | Next post, prices, likes, leads per post, what is waiting |
| Nova's view | `marketing_view.py` | Next post, plan, research, what was stopped |

### How the learning works

Every yes, no, change and lead moves weights on what the post was: format, subject, area, type of home, price, angle and opening.

- Recent decisions count more: a decision's effect halves about every 45 days.
- A real lead counts double a yes.
- A reason is read by the model and becomes lessons.
- One no leans; repeated noes stop something being chosen.
- The Plan tab shows what was learned, and any lesson can be forgotten.

## Bugs found and fixed

**Stop and removal**
- Stop saved the "no", but nothing read it, so the video stayed on the page.
- Stopped posts also stayed counted as done, kept the broker's film task and reused rejected AI frames.
- Pressing Cancel on the reason box still stopped the post.
- A stop left the failed-review question open.
- Remove replaced the day with the next best post; it now stays empty.

**Approval**
- A refused Approve or Post now made the card vanish, leaving the post stuck.
- Cancel it left no way to decide.
- An old, replaced script card could still be accepted.
- Your turn showed every post's cards, so the wrong one could be pressed.

**The lead and Nova**
- The lead said it had planned a week while planning one day and replacing the 14-day plan.
- It offered to re-run a post when told to publish it.
- It didn't know prices, likes, leads or the next post, and ended replies with the brand's sign-off.
- It could not run a post about the brand.
- Nova didn't know the next post, the plan or the research.

**Scripts and formats**
- About half of live script attempts failed because the model repeated the hook as a line.
- Two opposite brand voices came out too alike.
- A post about the company could leave out its name.
- A week could be six graphics in a row.
- Posts were always timed for tomorrow, ignoring the plan.
- One "too salesy" stopped all homes for sale.

**The page and speed**
- A blocking Instagram check froze the Studio for about 25 seconds, as often as every 10 minutes. First load is now about 0.4 seconds on the test server.
- Background refreshes wiped typed text and chosen files.
- A failed alert loop wrote about 2,750 screen-only notices. None went to WhatsApp.
- Approval buttons ran off the side on a phone.
- Plan from today gave an error while the page was loading.

## What was tested

| Test | Result |
|---|---|
| Automated tests, on the branch before pushing to `main` | 1060 passed, 1 skipped, 2 failed |
| Browser walk of every page and Marketing button | 56 of 57; the miss was the test itself |
| Plan walk, live | 16 of 16 |
| Existing browser flows | Marketing 14/14, journey 15/15, events 13/13, studio passed |
| Learning, live | Graphics went from 3 to 0 after three noes |
| Model comparison | Keep Muse Spark at low effort |
| Trend sources opened | 4 of 4 real |
| Competitor averages recomputed | 4 of 4 match |
| Eid al Adha, on a copy | Works with one sentence of facts; see Still open |

The 2 failures are Lobby tests that fail the same way on the code before this work. A calendar test failed the day before and passed that day, so both look date-related.

Model use for the full test was about $2.90.

## Test data: what is and isn't on GitHub

**On GitHub:**
- `tests/test_marketing_week.py` and the Marketing tests
- `e2e/marketing_full_flow.py`
- `evals/marketing_models.py`
- [marketing-test-report.md](marketing-test-report.md)
- `data/diwan.db` and `data/media/`: an older demo snapshot, not from these tests

**Not on GitHub, on this computer only:**
- The copy of the real data used for testing, `~/.diwan/full/full.db`, which should stay private
- Raw run outputs, failure screenshots and model result files, in the session's temporary folder
- One-off test scripts, including the lead, Nova, tone and Eid checks
- `e2e/shots/views/`: 36 screenshots from other flows

## Still open

**Most important**
- Script quality scored about 2 out of 5 from a blind judge on every model setting.
- Only 1 of our own posts has been read, so the learner has almost no real results.
- Some of the 12 Marina Crest leads are test names.
- AI frames are clearly drawings. Real team or office photos, or filming, are needed.
- The voice is still the Windows one, and the choice between the free package and an own recording is waiting on the owner.

**Occasions such as Eid**
- A title alone is refused, so it needs a sentence of facts.
- There is no start date: adding it early makes it the next post at once.
- There is no occasion calendar and no reminders ahead.
- A greeting can drift into selling and carries the sign-off.

**Analysis**
- Competitors are measured on likes and comments only.
- Hooks in the first seconds, pacing and music aren't studied.
- Watch time isn't read for our own posts.
- Posts have no single goal to be judged on.

**Not built**
- Stopping a post while it is being written
- Trends on the daily refresh
- Floor movement for image, reading and search steps
- The Bitrix or Supabase connection asked for earlier

**Not tested**
- Scenario stories, listed below
- Voice conversation with the lead
- Website reading
- Real filmed footage
- A real post reaching Instagram
- Buttons on non-Marketing pages

**Small items**
- Nova repeats "I've already chased Maya" on her answers, and two of her reminders still mention the stopped post.
- The panel can show the same idea twice under different labels.
- The ad account is named "Test App Test" and returns no spend.
- The Sample Brokerage sign-off, hashtags and Who we are still need changing in Setup.
- "Bostan", mentioned earlier, was never explained.
- "3" was taken to mean 3 posts a week.

## Scenarios still to run

Each to be judged by whether the output is something you would publish:

- Ramadan, National Day, a project launch, market news
- A price cut or a sold listing after approval
- An Arabic post
- A week with no photos
- An angry comment
- A competitor's post going viral
- The owner rejecting everything
- An expired Instagram token
- The budget running out, or the model going down

## Next, in order

1. Run the scenarios above.
2. Build the occasion calendar.
3. Get real footage and a real voice.
4. Set a script standard, and reject anything under 4 out of 5.
5. Give each post a goal, and measure saves, shares and leads.
6. Break down the competitors' winning videos.
7. Publish real posts and clear the test leads.

## How this machine works

- Git can't write to `.git` in the Documents folder. Commit from a clone under `~/.diwan/push`.
- Other sessions share the repo: check every changed line before committing.
- Servers need restarting after Python changes; pages are served fresh.
