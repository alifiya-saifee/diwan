# Diwan: how the marketing runs

How the Marketing department works from day to day: what starts each step, how competitor research reaches the
scripts, when work is replaced, who decides, and what it costs. It sits under `docs/rooms.md` (what each room must
output) and the Marketing checklist in `docs/sessions.md` (what is built and checked). Written 29 Oct 2026 for the
product owner to correct before any of the **Proposed** parts are built.

Each section says what happens **today** (in the code now) and what is **proposed**.

## 1. The rhythm

| When | What happens | Today | Proposed |
|---|---|---|---|
| A competitor is added | Its profile and last 25 posts are read; its best posts and 30-day chart appear | Built | Same |
| Every day, 07:00 Dubai | Competitor posts refreshed | Nothing runs on its own: only when a person presses Run | Competitors refreshed daily (free) |
| On the chosen rhythm, 07:00 | Trend search, **then the scripts are written straight away** | Trend search only inside a Run, cached for a day | The Marketing manager picks the rhythm in Setup: **daily (default), every 2 days, or weekly** (decided by the product owner 29 Oct, since a video goes out every day). Each search is followed at once by the scripts for the video(s) it covers |
| Daily rhythm | One video for the day: the listing (or area, market or brand topic) whose turn it is, 3 scripts, the manager picks | Not built | A "Today's video" card on the Run tab with the 3 scripts ready when the manager arrives |
| Weekly rhythm (Monday) | **The week's plan**: a video for each posting day (which listing or topic, which lane: listing, area guide, market update, behind the scenes, client story) and its 3 scripts | Not built: the Lane balancer only reports the last 30 days | A plan card for the week, one row per day with its scripts; the manager approves the week, changes a day in plain words, or picks a script per day |
| A listing is chosen | Research → idea → 3 scripts → the manager picks | Built, started by Run this listing | Started from the weekly plan, or by Run as now |
| A script is picked | Film list to the broker, post text written | Built | Same |
| The take is uploaded | Take checked against the script, captions, covers, permit check, publish request to the owner | Built | Same |
| A post is published | Its numbers are read back over the following days | Publishing is off (no public address) | Stays off until the owner turns it on |

## 2. From competitor research to a script

**Today:** Competitor watch pins the top 3 posts above their account's average on the research board. The Idea
generator writes 3 ideas and names the cards each one uses, but always takes **idea 1**, which is usually the plain
listing idea. All 3 scripts are then written from that one idea, so the competitors' winning posts rarely reach a script.

**Proposed:**

1. **Each of the 3 scripts gets its own source.** Script 1 builds on the best competitor post that fits the listing,
   script 2 on the second, script 3 on a trend card or the listing alone. Each script card says it plainly:
   "Built like @competitor_one's reel: 2,542 likes + comments, 5.7x their average reel", with Open on Instagram.
2. **"Fits the listing"** means the same kind of property or area, read from the competitor's caption (for example
   villa, off-plan, Marina, Palm). With no fitting post, the best post overall is used and the card says so.
3. **What is borrowed is why it worked, never the post itself** (product owner, 30 Oct). For each above-average post,
   Diwan first works out *why* it hit, from its caption, cover and numbers: the hook type (a question, a price, a
   place), the format (a walkthrough, a person talking to camera, a carousel of photos), the call to action, the
   timing. It also decides whether that reason **can carry over** to us:
   - **Carries over:** a format, a hook, a structure, an angle (for example "a price reveal on an off-plan unit").
   - **Does not carry over:** anything tied to that brokerage's own moment: an event or party, an award, a
     partnership signing, a team photo, a celebrity, a holiday, a launch only they have. Such a post still counts for
     their average, but no script is built on it.
   - **No false claims:** the script uses only our listing's facts and our brand. It never borrows a competitor's
     numbers, awards, sales, partners or promises, and the review sends back any claim our listing doesn't support.
   The card says it in one line: "Built like @competitor_one's reel (2,542 likes + comments, 5.7x their average reel):
   it worked because a person explains one clear reason to buy, in the first 3 seconds."
4. **Reels first:** a reel that is above its account's average is preferred over an image post, because we make reels.
5. **What we can learn from each post** (decided by the product owner 29 Oct). Instagram gives competitors' reels
   **without the video or its sound**: on the demo data 0 of 62 reels came with a video file, only the cover image. So
   today's Transcript reader, which downloads the top reel, has never produced a transcript and cannot through the
   official API. Instead:

   | What we have | What is read from it | With |
   |---|---|---|
   | The caption (every post) | The hook (first line), call to action, price, area, Arabic | Rules, free |
   | The cover image (every post) | Text on the cover; a person (doing what), a property (what), or text only; the style | Muse Spark, image input at low reasoning: tested on a real cover, 4.7 s, about $0.006 a cover |
   | A video file: our own takes, or a competitor reel the Marketing manager saved and uploads | **Speech**: the spoken hook in the first 3 seconds and how much of the reel is talking. **Motion**: number of cuts, average shot length. **On screen**: a frame every 2 seconds read by the image model (person to camera, walkthrough, drone, text), giving the share of time a person is on camera and when the first face appears | Local Whisper (free, nothing leaves the Mac; Muse Voice when chosen), ffmpeg scene detection (free), Muse Spark for frames |

   Every trait becomes one of the measured comparisons in **Why they win** (for example "80% of their above-average
   reels show a person on the cover, against 30% of the rest"). Saving a competitor's video is the manager's call under
   Instagram's terms; Diwan only analyses a file a person uploads.

## 3. When scripts are replaced

**Today:** a "Pick a script" card stays until someone picks or sends it back. New research never reaches it, so the
card can be days old while the competitor tab shows newer winners.

**Proposed:**

1. Each script card shows **when it was written** and **from which research** ("written 29 Oct 13:41 from 2 board cards").
2. When the board changes after that (new competitor results, a new trend), the card is marked **"Out of date: newer
   research since it was written"** with one button, **Rewrite with the new research**. Nothing is rewritten on its own,
   because each rewrite costs model time.
3. Choosing another listing or pressing Run again replaces the open card, as today, and the old one is kept in the
   history.

## 4. Choosing the three angles

**Today:** the strategy picks up to 3 angles (price reveal, walkthrough, lifestyle, investor, market check). With fewer
than 3 of our own posts, every angle is "explore: not proven on our account", so the three scripts differ little.

**Proposed:**

1. **Until we have 3 posts of our own:** the angles come from what wins for competitors. Each competitor post above
   average is labelled with its angle from its caption, and the angles with the most above-average posts are used. The
   card says why: "walkthrough: 4 of competitors' 9 above-average posts".
2. **Once we have our own results:** as built: winning angles are kept, fading ones shifted, resting ones rested for
   30 days, one slot always tests something new.
3. **The three scripts must differ:** different angle, different source post, different opening line. The review
   sends back a script whose first line repeats another's.

## 4b. The manager's own scripts, and what Diwan remembers

Decided by the product owner 29 Oct. **Today** a person can only pick one of Diwan's scripts, ask for a change, or
send them all back; lessons a person teaches are kept (`agents/lessons.py`), but nothing is learned from what they
write or pick.

**Proposed:**

1. **Write my own.** On the Run tab, beside the three scripts: paste a full script or a rough draft, choose the
   listing and, if wanted, the angle.
2. **Diwan checks it, then proposes.** The same review as its own scripts: brand words and never-use words, the
   permit number, no promised returns, prices only from the listing. Each problem is pointed out, never silently
   fixed. Then two versions of **the same message on two other angles** (for example the manager's price reveal as a
   walkthrough and as a lifestyle piece), each saying which angle and why. The manager uses their own, takes a
   proposal, or asks for a change in plain words.
3. **Style notes, not copies.** From what the manager writes, picks, sends back and changes, Diwan keeps short style
   notes: "opens with a question", "short lines, under 10 words", "ends with a WhatsApp call", "prefers lifestyle over
   price for villas". Each note shows the scripts it came from. The writers follow the notes from then on; the words
   of the manager's scripts are never reused. Notes are listed in Setup → Our brand, and the manager can delete any of
   them.
4. **Never the same twice.** Every new script is compared with past ones, the manager's included: a script whose
   opening line or structure is too close to an earlier one goes back with the reason ("too close to C12 from
   20 Oct"). So the writers learn the kind of script the manager likes without repeating it.

## 5. Who decides

| Decision | Who | Where |
|---|---|---|
| The brand profile, the competitor list | Marketing manager | Studio → Setup |
| The week's listings | Marketing manager | the weekly plan card (proposed) |
| Which script, or a change to one | Marketing manager | Studio → Run → Your turn |
| An AI presenter video (paid, needs the person's consent) | Marketing manager | Your turn |
| Publishing a post | Owner | Your turn: Approve & publish |
| Turning publishing on (`PUBLIC_BASE_URL`) | Owner | `.env` |

The agents never publish, never message a competitor, and never claim returns.

## 6. What it costs

Measured on the last live run (29 Oct, 13:35 to 13:42):

| Step | Calls | Cost |
|---|---|---|
| Trend search (web search) | 2 | $0.47 |
| Idea | 1 | $0.01 |
| Scripts (3 written, 2 rewritten after review) | 5 | $0.04 |
| **One run** | **8** | **$0.51** |

Without the trend search a run is about **$0.04**. Competitor reading is free (Instagram Graph API). The monthly cap is
$25; spend so far this month is $2.26.

**What each rhythm costs** (trend search $0.47 + scripts $0.04 per video; covers of above-average posts only, a few
cents a week):

| Rhythm | Per month, about | Share of the $25 cap |
|---|---|---|
| Daily | $15 | 60% |
| Every 2 days | $8 + $0.04 a video on the other days | 35% |
| Weekly (7 videos planned) | $2 + $1.20 for the week's scripts ×4 = $7 | 28% |

The trend search makes **2 web searches** today; asking for 1 would halve its cost (to be measured). Setup shows the
estimate next to the rhythm choice, and the Meta models tooltip shows the month's spend.

## 7. Our industry, and whether a competitor is really one

**Today:** nothing says what industry the client is in, and anything can be added as a competitor: @test_clinic (a
clinic) was added on the demo server and removed again, and its result still shows on the Run tab.

**Proposed:**

1. **The industry is fixed when the client is set up**, in Setup → Our brand: the industry (here: real estate
   brokerage), the segments (buy, rent, off-plan, luxury, commercial) and the areas (Dubai Marina, JVC, Downtown…).
   It is filled from the company profile the Brand brain already reads, and a person confirms it.
2. **Each competitor is checked against it when it is added.** Muse Spark reads the account's last 25 captions (text
   only, about $0.01 an account) and answers: which industry, which segments and areas, with the captions that show it.
   The account is listed with the result: "✓ real estate · off-plan, luxury · Palm, Downtown", or "⚠ looks like a
   healthcare clinic (12 of 25 captions about treatments)". A mismatch is **only warned about**: it is added and used
   like any other, because the check can't be certain (decided by the product owner 29 Oct). The manager removes it if
   the warning is right.
3. **Each post is labelled too**, from its caption and, for above-average posts, its cover: a listing, an area guide,
   a market update, the team or culture, or off-topic. Off-topic posts (a team photo, a holiday) still count for the
   account's average but are not used as a script source, so a script is never "built like" a staff party photo.
4. **Closeness to us** decides which competitor post a script borrows from first: same segment and area beats same
   segment, which beats the rest.

AI never decides alone that an account is a competitor: it shows its reasons, and a person keeps or removes it.

## 8. What is fixed straight away (no decision needed)

- The Lane balancer still says "Instagram not connected" when it is connected: it should say how many of our posts it
  read.
- An old Competitor watch message with the earlier wording ("their usual", @test_clinic) stays on the Run tab until the
  next run.
- On the demo server the three saved accounts show "⚠ not checked yet" in Setup, because they were fetched before each
  check was recorded. An account whose posts were read should show "✓ fetched" with the date they were read.

## 9. How each proposed part is checked

Each item is checked in the browser on a test server with real competitor data, models offline except one measured
live run, and reported as checked in the browser, tested in code only, or not done:

1. Three scripts with three different named source posts, each with Open on Instagram.
2. Adding a competitor after the scripts were written marks the card "Out of date"; Rewrite replaces the scripts with
   ones that name the new post.
3. With no posts of our own, the three angles named on the card match the competitors' most common winning angles.
4. The weekly plan card lists 3 to 5 permitted listings with a reason each; changing it in plain words works.
5. A non-property account is added with the warning and stays off the board until confirmed.
6. One full live run's cost is shown and is under $0.10 without the trend search.
7. The manager pastes a script with a never-use word and no permit: both are pointed out, and two versions on other
   angles are proposed; using their own, taking a proposal and asking for a change all work.
8. After the manager picks and edits a few scripts, Setup lists the style notes with their source scripts; deleting
   one works; the next scripts follow the notes.
9. A new script whose first line nearly repeats an earlier one is sent back naming that script.

## 10. Ads (open)

- **Our own ads:** the Marketing API gives each ad's spend, impressions, reach, clicks, cost per click, leads and cost
  per lead, with its creative. Proposed use: rank our ads by cost per lead, feed the winning ad's angle into the
  strategy like a competitor post, and (with Front desk & Sales) follow each lead from its ad to a viewing. A test ad
  account exists (product owner, 29 Oct); it needs its ad account id and a token with `ads_read`.
- **Competitors' ads: they cannot be tracked automatically.** No source gives their spend, reach or results. Meta's
  Ad Library website shows a person any page's active ads (creative, text, start date, platforms), but its API returns
  only political ads and ads shown in the EU, not UAE property ads. What Diwan can do: a "See their ads" link on each
  competitor that opens their Ad Library page, and a "Pin this ad" field where the manager pastes an ad's link and text
  so it joins the research board like a post (no numbers, since none exist). Reading the Ad Library website
  automatically would break Meta's terms. **Built 29 Oct** (Competitors → Their ads): See their ads links, Pin this ad
  with start date, still running or end date and copy, "Running N days", remove. Follower growth shows in Overview once
  two days of checks are recorded.

## 11. Decisions for the product owner

Decided 30 Oct:
- **Budget:** Marketing **$20** a month, the rest of the office **$5** (the total stays $25). Built 30 Oct: each
  agent's spend counts against its own part, and when Marketing's $20 is used up the studio falls back to templates
  while Rania and the rest keep working (and the other way round). The Meta models tooltip shows Marketing's spend.
- **Ads:** our own ads' insights are to be built (the test ad account is connected and readable; nothing built yet);
  competitors' ads stay manual, since Meta gives no insights for them.
- **Yes** to: scripts built on why a competitor post worked (as in section 2), the out-of-date card with one-click
  rewrite, style notes and the never-the-same check, the trend rhythm in Setup, the industry and competitor check.

Decided 29 Oct:
- Competitors' hooks from the **caption and the cover** (covers read by Muse Spark), **covers of above-average posts
  only**, since those are the ones that performed.
- Competitor reel videos only when the manager **uploads a saved copy**; speech by **local Whisper first**.
- Trend search on a **rhythm the manager chooses (daily by default, every 2 days, weekly)**, and **the scripts are
  written as soon as it finishes**; weekly plans a video for every posting day of the week.
- The **industry is fixed when the client is set up**; competitors are checked against it.
- A **test ad account exists** for our own ads' insights; `.env` has `META_AD_ACCOUNT_ID` and `META_ADS_TOKEN` to fill.
- A competitor outside our industry is **warned about, never blocked**.
- Out-of-date scripts: **one-click rewrite**. The card says "Out of date: newer research since 07:00" and nothing
  changes until the manager presses Rewrite with the new research (about $0.04); the next scheduled search refreshes
  everything anyway.

Still open:

1. "Write my own" (section 4b): explained again to the product owner on 30 Oct; waiting for a yes or a change.
