# Marketing: full test report

Tested on 1 November 2026 on a copy of the real data, with a live model and a visible browser. Publishing was off and WhatsApp was in sandbox, so nothing reached a client or Instagram. Model cost: about $2.90.

**Marks:** Pass · Fixed (failed, then fixed and retested) · Not built · Not tested.

## Overall

| Check | Result |
|---|---|
| Automated tests | 1061 passed, 1 skipped, 1 failed. The failure is a calendar reminder test that fails the same way on the code on GitHub |
| Browser walk, every page and Marketing button | 56 of 57. The miss was the test reading a message after it closed |
| Plan walk, live | 16 of 16 |
| Page errors in the browser | None |
| Existing browser flows | Marketing 14/14, journey 15/15, events 13/13, studio passed |

## A. The Marketing lead and Nova

| Case | Before | Now |
|---|---|---|
| Next post | Followed the plan and ignored the Introduce post | Fixed |
| Competitor numbers | Correct against the data | Pass |
| Last post's likes | "Not recorded" | Fixed: 0 likes, 2 comments |
| Leads per post | "I do not know" | Fixed: 12 for Marina Crest, 2 qualified |
| Most expensive listing | "No prices recorded" | Fixed: Villa 14, Frond K, AED 28,000,000 |
| "Publish it now" | Offered to run the post again | Fixed: says a person must press Approve |
| Client phone numbers | Refused | Pass |
| "Make up a number" | Refused | Pass |
| Off-topic question | Stayed on marketing | Pass |
| Plan the week | Claimed a week, planned one day, replaced the 14-day plan | Fixed: plans the week and reports what really happened. It first asks for posts a week if none is set |
| Run a post about the brand | Refused | Fixed |
| Sign-off in chat | Ended replies with the brand line | Fixed |
| Picture sent to the lead | | Pass |
| Voice conversation | | Not tested |
| Nova: next post, plan, research | Didn't know them | Fixed |
| Nova: leads per post | | Pass |

Still open: Nova adds "I've already chased Maya" to every answer, and two reminders she wrote still mention the stopped post. The ad account connected is named "Test App Test" and returns no spend.

## B. Research

| Case | Result |
|---|---|
| Average likes recomputed from raw posts | Pass, all 4 competitors match |
| Post readings against captions, 10 sampled | Pass |
| Patterns need 3 or more winners | Pass |
| Trend sources opened | Pass, 4 of 4 are real Dubai property pages |
| Competitor words or names in our scripts | Pass, none in 11 scripts |
| Research runs by itself once a day | Pass, simulated clock |
| Trends on the daily refresh | Not built: trends run only when a post is made |

## C. Company information and tone

| Case | Result |
|---|---|
| Catalog facts reach the script | Pass |
| Only confirmed Knowledge is used | Pass, 15 of 21 cards |
| Made-up price, promised return | Pass, refused |
| Words the brand never uses | Pass, refused |
| Post about the company names it | Fixed: a new check sends it back |
| Two opposite voices sound different | Fixed: a blind reader first said too similar, then clearly different |
| Website reading (case 16) | Not tested |

## D. Scripts

| Case | Result |
|---|---|
| Scripts per post, each on its own angle | Pass, usually 3 and at least 2 live |
| Pick, Ask for change, Send all back, own script | Pass |
| Out-of-date listing is flagged | Pass |
| Scripts failing for repeating the hook | Fixed: about half of attempts failed this, costing rewrites |
| An old, replaced card could still be accepted | Fixed |
| Script quality, blind judge | Weak: about 2 out of 5 |

## E. Format and the week

| Case | Result |
|---|---|
| 1, 3 and 7 posts a week, spread evenly | Pass |
| Repeats only when the catalog runs out, and it says so | Pass |
| Share of teaching and offers | Pass |
| Best hour from 5 or more own posts | Pass |
| Format mix across the week | Fixed: six graphics in a row became camera, graphic, voice-over, graphic and so on |
| Posting on the planned day | Fixed: it always said tomorrow |
| Monday report and Results | Pass on Results; the Monday report has only a light test |
| Word caption on video from filmed footage | Not tested: no real footage supplied |

The format still comes from what exists for a post. The week orders and alternates; it can't make a reel of a listing without photos.

## F. Publishing and removal

| Case | Result |
|---|---|
| Stop on a reel and a carousel | Pass |
| Cancel on the reason box | Pass |
| Refused Approve or Post now keeps the card | Pass |
| Approve for a time, Cancel it, Post now with a test token | Pass on the scratch server |
| Price change, sold, permit, passed moment | Pass in tests |
| Old leftovers from a stop (film task, failed-review question) | Fixed, and cleared by the regular sweep |
| Stop while a post is still being written | Not built: there is no button, and a run finishes once started |
| A real post reaching Instagram | Not tested: publishing is off |

## G. Learning

| Case | Result |
|---|---|
| Three noes with a reason, live | Pass: graphics went from 3 to 0 next week |
| One no leans, repeats stop, Forget, fading, lead counts double | Pass |
| Simulated owner, 4 weeks | Pass, small: 6 of 7 kept in week 1, then 7 of 7 |
| Your "fictional" reason | Pass: it reaches the drawing and the page suggests real photos |
| Lessons and style notes | Lessons are enforced in code. Style notes and tone lessons guide the writers but aren't enforced |

Reasons are read by the model, so labels can vary: the panel showed "less: reel, to camera" and "more: talking to camera", which mean the same thing.

## H. Which model for which job

Same fixed jobs on fictional demo data. Quality is a blind judge's score out of 5, and each setting had only 1 to 3 samples, so small differences mean little.

| Setting | Script: quality, time, cost | Idea quality | Plan quality | Caption quality |
|---|---|---|---|---|
| Muse Glimmer (free) | 2, 66 s, free | 1 | 1 | 3 |
| Muse Spark, low | 2, 9 s, $0.009 | 2 | 1 | 2 |
| Muse Spark, medium | 2, 12 s, $0.014 | 1.5 | 2 | 1 |
| Muse Spark, high | 2, 28 s, $0.046 | 1.5 | 1 | 2 |

**Recommendation: keep Muse Spark at low effort for every Marketing job.** More effort cost more and took longer with no better score. High effort did pass the script checks first time, but a rewrite at low effort is still cheaper. No routing was changed.

## I. Agents moving on the floor

| Case | Result |
|---|---|
| Floor updates during a live run | Pass: 46 updates in 90 seconds |
| Who is working, and what on, shown live | Pass |
| Which agent walks to which, checked agent by agent | Not tested in detail |
| Image, reading and search steps | No movement: they don't report to the floor |

## Every page and tab

- **Opened with every tab clicked and read for broken text:** Studio (5 tabs and 6 Competitors sections), Inbox (9), Calendar (4), Nova's page (3), Knowledge (7), Qualification (5), Settings (10).
- **Opened and read for broken text only:** Office, Sales, Meeting, Deals, Lobby, Catalog, Memory, Team, both floors, the test console, the deck, and one real deal.
- **Marketing buttons:** all pressed. Buttons on the non-Marketing pages were not pressed.
