# Diwan

The back office of a Dubai real-estate brokerage, run by a team of chartered agents you can watch and correct.
Tell the business once: a client meeting becomes facts with exact quotes, the facts become work for every team, and
when the client corrects themselves the office flags compliance first, withdraws only the work that depended on the old
statement, and refuses approvals that no longer match the facts.

Built for the Meta Global AI Developer Hackathon. See [BUILD_LOG.md](BUILD_LOG.md) for what was built and when.

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env           # add whichever keys you have
.venv/bin/python -m diwan check          # what is plugged in and where each agent runs
.venv/bin/python -m diwan check --ping   # one tiny live call per configured provider
.venv/bin/python -m pytest -q
```

To start with the demo office's data (fictional chats, catalog listings, competitor posts, settings), copy the
snapshot in and point `.env` at it: `cp data/try.db data/usage.jsonl . && cp -R data/media .`, then
`DIWAN_DB=try.db` (`data/diwan.db` is the older office; `usage.jsonl` keeps the model spend counted against the
limits). Keys and limits in `.env` are never committed: set them again. The live files stay out of git; refresh
the snapshot instead.

## How an agent turn works

charter -> instructions -> model (live, or a marked recording) -> pack -> quote check -> authority check -> event log

| Runs on | Agents |
|---|---|
| Muse Spark (Meta Model API) | Nova, Sales lead, Scribe, Deck builder |
| Muse Spark Open (Baseten, Fireworks or Modal) | Compliance lead, Source-of-funds analyst, Devil's advocate |
| Code | Payment tracker, Screening analyst, Report drafter, Fact checker, leads that only route |
| Browser | Form F clerk (stops before Submit) |

## The client's journey, and how much of it is built

Front desk and Sales: from a client's first message to the keys. Rania (the AI receptionist) talks to the client; people
stay in charge. Everything below runs on a sandbox WhatsApp line with fictional data, and is checked in the browser as a
person would use it. See [docs/sessions.md](docs/sessions.md) for who owns what and the changelog, and
[docs/done-and-left.md](docs/done-and-left.md) for the detail. For the whole office against the
[closed-loop spec](docs/closed-loop-spec.md), see the [checklist](docs/closed-loop-checklist.md).

| Step | What happens | State |
|---|---|---|
| 1. First message | A client writes on WhatsApp, comments on a post or enquires on a portal. Rania finds out what they want; "just looking" is nurtured, not chased; a portal lead starts from its listing and is asked only what is missing. | Built |
| 2. Qualifying | The owner's own form, one question at a time, each answer kept with the client's words. "Call me" always reaches a broker; what makes a lead hot is the owner's setting. | Built |
| 3. Options | From their answers. When nothing fits exactly, the broker will send options and the closest ones are shown meanwhile. | Built |
| 4. Quiet clients | Follow-ups on the owner's schedule, never at night or at Friday prayer, never twice the same; "stop" means stop. | Built |
| 5. Appointments | Booked, moved and cancelled in the chat or on the calendar (day, week, month, list), in each broker's free time. Busy time, days off, appointments added by hand, a call at a time the client asks for, reminders, a calendar file, print. | Built |
| 6. Video links | Zoom links made when Rania confirms a call (the owner's switch). | Built and tested against a stand-in; waiting for real Zoom keys. Google Meet not built |
| 7. After the visit | A recording or the broker's notes become a summary in the client's own words, and the follow-up answers their worry. | Built (the microphone itself is not exercised in tests) |
| 8. Google or Outlook calendar | Reading each broker's own calendar so personal events block time. | Planned, not built |
| 9. Outcomes | "Follow up on a date", "not interested", "no response" chosen by the broker, with a reason. | Proposed, not built |
| 10. Agreement to keys | The offer, the paperwork, the closing and the sale recorded with Records. | Mostly the Deal desk's (see [docs/deal-desk.md](docs/deal-desk.md)); the front-desk side is proposed in [docs/agreement-to-keys-spec.md](docs/agreement-to-keys-spec.md) |

How it is checked: `pytest -q` (430 tests at the time of writing), 77 labelled conversations (`python -m diwan eval`),
and Playwright checks in `e2e/` that drive the real pages on a scratch database. A few live Muse Spark passes cost cents.
Known limits: no real WhatsApp line is connected; WhatsApp only allows free text within 24 hours of the client's last
message, after that only approved templates; when no model is connected Rania falls back to plain rules, which are cruder.

## Against the closed-loop spec

[docs/closed-loop-checklist.md](docs/closed-loop-checklist.md) lists what is there and what still needs to be there, room by room, with the risks to fix
first, the order to build and the questions only the office can answer. [docs/closed-loop-audit.md](docs/closed-loop-audit.md) has every requirement of
[the spec](docs/closed-loop-spec.md) with where it was found in the code. Checked 31 Oct 2026: 1,377 requirements, 17% built, 35% partly, 44% missing.

## The content studio

The Marketing side turns what competitors post into reels for the business. It reads their real Instagram posts, says why
the best ones worked, and writes three scripts for a listing, a product or service, or a topic to explain (an
informational video, spoken to camera), each from its own facts. It can read the company's website for its products and
properties, refresh competitor posts every day, and be talked to by text or voice. Everything starts in the Studio's Setup
tab. A person approves every script and every post; nothing is published without that.

### How a post is made

1. **Plan.** Setup → Rhythm sets how many posts a week and on which days. The plan fills those days from the listings,
   products, topics and occasions, and each day says what it builds on: a competitor pattern, a trend or one of our
   results. Never more than two posts about the company in a row. Any day can be approved, changed, rescheduled or removed.
2. **Occasions.** The calendar is researched for the business's own country with one web search, and every date is kept
   only with its source (Setup → Our occasions, editable). An occasion is offered 30 days ahead. One yes writes a greeting
   that goes out on the day itself and sells nothing.
3. **Research.** The competitors' real posts are read through Instagram's business discovery. A winner is a post well
   above that account's usual engagement, and Muse Spark says why each one won. For an occasion, last year's posts around
   the same day are read and the best ones brief the card. For a listing, its own web page (features kept only with a
   quote) and its area (facts kept only with a source) are read once.
4. **Format.** A listing becomes a single photo, a carousel or a reel. The choice comes from its selling point, what its
   photos show and which format wins among the competitors' posts. A greeting is a designed card unless the person
   chooses their own photos.
5. **Scripts.** Three scripts on different angles, in English and Arabic. Every amount must be on the listing. The
   Creative Director scores each one blind and rewrites any below 4 out of 5, and picks the strongest of three openings.
6. **Made and checked.** Pictures and cards carry the logo, the brand colours and Arabic set right to left. The free
   video reads the script over the photo that shows each line. The caption is written in the brand's voice and checked
   against the facts, the permit and the code word. Facebook, LinkedIn and YouTube versions are ready to copy, and
   every file is also kept in Supabase Storage when a bucket is set.
7. **Approval.** The post waits at the best hour, and the card says where that hour came from. A change asked on the
   card goes to whoever can fix it and comes back checked, with before and after.

| Job | Model |
|---|---|
| Reading competitor posts, the Marketing lead, ideas, scripts, captions, platform versions | Muse Spark |
| Web search (trends, occasions, the area) | Muse Spark with web search, sources kept |
| Looking at photos, pictures and frames (the Creative Director) | Muse Spark (vision) |
| Greeting backgrounds and AI frames for topics | Muse Image |
| Transcribing a competitor's winning video | Muse Voice Transcribe |
| The free video's voice, captions and cut | The computer's own voice and ffmpeg (no model) |

How it was tested, case by case with a blind judge, and what is still weak: [docs/marketing-real-user-test.md](docs/marketing-real-user-test.md).

Agents never hold portal or bank credentials. A person approves, submits, pays and files.
All people and deals in demos are fictional.
